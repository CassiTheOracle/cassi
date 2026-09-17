"""Use the field's memory: retrieval that changes what a consumer does.

The field workstream before this one shows a written pattern can be stored by
``FieldIntelligenceOwner.write_packet_impulse``, held by a closed loop, and read
back exactly by ``FieldIntelligenceOwner.read_packet_deposit``. Nothing yet shows
a *consumer* acting on what it retrieved. This runner measures the first
end-to-end use: a deterministic task whose outcome depends on a retrieved memory.

The task (``carry the remembered direction forward``). The consumer asks the
field for one declared direction -- the *target* -- through the owner's own read
operation, and then actuates exactly one of its declared candidate directions
through the owner's own write path, at one declared act budget. Its policy is
declared in advance and has no state of its own:

    retrieve the target direction's deposit through the owner's read operation;
    if it reaches the declared read floor, pursue the target;
    otherwise pursue the declared fallback direction.

The behavioural statistic is an observable of the field, not a self-report: the
share of the act's own read-frame increment that lies along the target
(``dot(dframe, u_target)**2 / dot(dframe, dframe)``), where the increment is the
durability harness's declared read frame measured immediately before and after
the act on the owner's canonical page, and ``u_target`` is that harness's own
captured unit direction for the target item. The act's *amount* is one declared
budget in every arm, so what the statistic separates is direction, not effort.

The four declared arms, each on its own canonical field (its own owner home):

A ``A-memory-used``: the target item is written through the owner write path,
  held by the declared closed loop at this profile's own freshly measured
  neutral gain, and read back through the owner's read operation; the retrieval
  reaches the floor and the consumer pursues the target.
B ``B-identity-control-read-suppressed``: the same write and the same hold
  happen in full, but the consumer's read is suppressed -- it returns the
  declared zero without calling the owner read operation, and the runner's own
  instrument read records what the field was carrying at that moment. The
  retrieval misses the floor and the consumer pursues the fallback. This is the
  control that shows the behaviour comes from the retrieved content rather than
  from the write's side effects on the field: the write is present, the field
  carries the target's deposit, and the behaviour is still the fallback's.
C ``C-no-memory``: nothing is written; the declared hold horizon is advanced on
  a blank page with no drive, because the declared loop has no normalisation
  reference without a written item; the retrieval misses the floor and the
  consumer pursues the fallback.
D ``D-mismatch-control``: a different declared item is written and held than the
  one the consumer asks for; the retrieval of the target misses the floor and
  the consumer pursues the fallback. The same write mechanism ran as in A, on
  the same profile, with the same budget and the same hold, so this is the
  firing control for the claim that A's behaviour is attributable to the
  memory's *content*: if the write alone produced the behaviour, D would show it.

Declared margins (both in share units, reported beside the measurement):
``PURSUIT_MARGIN`` is what the target's share must reach for the arm to count as
pursuing the target; ``SEPARATION_MARGIN`` is what A must beat the controls by.
One further leg is not an arm but the can-fail control for the statistic itself:
``C-firing-control-policy-mutated`` runs C's field episode with the consumer's
policy mutated to ignore the retrieval, so the same statistic must invert to
pursuing the target; without it, a "share 0 in the controls" figure would be a
quantity that cannot be shown to move.

The declared hold runs at an even horizon. The declared loop's drive alternates
sign every tick, so a hold of odd parity leaves the held frame reversed in sign
at the horizon, and the read -- a squared projection -- then returns the written
deposit times that signed phase squared. The receipt publishes the signed ratio
at every tick of the hold, where that alternation is visible, declares the
horizon's parity, and makes the held-read recovery claim at the even parity its
own horizon has, with a direction the episode did not write as the can-fail
control for that claim.

What the read's own declaration implies for a consumer (part of the finding, not
a footnote). ``read_packet_deposit`` is declared as the design declares a readout
(FIELD-INTELLIGENCE-DESIGN.md 27.3; README.md 653-657): a *temporal prediction*
of the canonical page, labelled ``temporal-prediction``, which adds no observed
support and does not advance the evidence clock. The consumer here can
legitimately act on it, and the reason is narrow: the act is an *intervention*
(one more owner write), not an assertion about the world, so the consumer uses
the prediction as a control input rather than as support for a claim. Nothing in
this demonstration needs the read to be evidence anywhere: the consumer never
admits the readout through the owner's observation rule, and the receipt shows
the owner's evidence clock unchanged across every arm's whole episode while the
same key moves by one on an admission (the can-fail control for that
invariance). What the alternative declaration would move is measured beside it.

Every number in the receipt comes from the canonical field surface (the owner's
write path, its read operation, and its published clocks) or from the harnesses'
declared instruments imported read-only (the durability harness's read frame and
captured directions, the feedback harness's loop law and neutral-gain
refinement, the metric harness's profile). Negative results are deliverables:
where a comparison ties or a control fails to separate, the receipt says so with
its numbers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_feedback_exploration as feedback
import run_fractal_geometry_exploration as geometry
import run_owner_write_path_exploration as owner_path
from cassi_field_atlas import AtlasState, FieldAtlas, RelationChart, VariableSpec
from cassi_field_owner import FieldIntelligenceOwner
from cassi_resonant_field import advance_workspace, initial_workspace

SCHEMA = "cassifi.memory-consumer-path.v1"

# The declared item indices: the target is the direction the consumer asks for,
# the mismatch is what arm D writes instead, and the fallback is what the
# consumer pursues whenever the retrieval misses the floor. The declared items
# are the durability harness's own eight packet items; this runner measures their
# pairwise overlap in its own receipt rather than assuming the construction.
TARGET_ITEM_INDEX = 0
MISMATCH_ITEM_INDEX = 1
FALLBACK_ITEM_INDEX = 2

# The declared arm names, as the receipt, the tests and the reading all spell them.
ARM_MEMORY_USED = "A-memory-used"
ARM_IDENTITY_CONTROL = "B-identity-control-read-suppressed"
ARM_NO_MEMORY = "C-no-memory"
ARM_MISMATCH = "D-mismatch-control"
ARM_POLICY_MUTATED = "C-firing-control-policy-mutated"

# The declared write and act budgets: the same packet impulse budget for the
# memory's write and for the consumer's act, so the act's amount is held fixed
# across the arms and only its direction can move.
WRITE_BUDGET = 1e-3
ACT_BUDGET = 1e-3

# The declared hold horizon: the number of closed-loop ticks between the write
# and the read, run one tick per owner transition so the canonical field (the
# owner's own page) is the only adaptive state in the episode. It is short by
# declaration: this receipt asks whether a retrieved memory changes a consumer's
# behaviour, not whether the loop holds a pattern over a long horizon, which the
# owner-write-path receipt already measures at 512 ticks.
HOLD_HORIZON_TICKS = 16

# The declared read floor, as a fraction of the target's own captured deposit:
# the retrieval must reach this fraction of what one declared write of the target
# deposits for the consumer to pursue the target. The comparison is on the
# retrieved deposit the owner read returns, and the floor is reported in the
# receipt as an absolute value beside the write's own captured deposit.
READ_FLOOR_FRACTION = 0.5

# The declared margins, each reported beside the measurement it judges.
# PURSUIT_MARGIN: the target's share of the act increment at or above which the
# arm counts as pursuing the target. SEPARATION_MARGIN: the pursuit margin A must
# beat each control by, and the contrast the mismatch control D must fail by.
PURSUIT_MARGIN = 0.5
SEPARATION_MARGIN = 0.5

# The declared relative allowance on the held page's recovery of the written
# direction's deposit. It is deliberately wider than the exact identity a fresh
# single-write page carries (the owner-write-path receipt measures that at
# 1e-12): the declared hold drives the page on every tick of its horizon, so the
# deposit the read returns at the horizon differs from the deposit the write
# itself deposited, and the receipt reports the measured relative difference and
# this allowance beside each other, with a direction the episode did not write as
# the can-fail control for the same predicate.
READ_RECOVERY_ALLOWANCE = 1e-4

# The declared allowance on the candidate directions' distinctness in the read
# frame: the greatest off-diagonal squared cosine between the declared items'
# captured directions must stay inside it, and each direction's own squared
# cosine must stay inside it of one. The receipt reports the measured greatest
# off-diagonal value beside it.
ORTHOGONALITY_ALLOWANCE = 1e-12

# The declared profile: the metric harness's flat-inertia member, imported
# read-only through that harness's own builder. The neutral gain is measured
# afresh in this receipt by the feedback harness's own refinement, and its
# neutrality on each page this receipt holds is measured on that page; it is
# never taken from another profile's measurement.
PROFILE_NAME = owner_path.PROFILE_NAME
PROFILE_SOURCE = owner_path.PROFILE_SOURCE

# The family's own figure for this profile's neutral gain, as the owner-write-path
# receipt carries it at cycle.neutral_gain.measured_gain. It is a reference to
# concord with, never an input: this receipt's refinement measures the gain again
# and reports whether the two agree inside the refinement's own tolerance.
OWNER_WRITE_PATH_RECEIPT = "_diag/owner-write-path/exploration.json"
CITED_NEUTRAL_GAIN = 0.02734375

# The declared read operation's name, as the owner method, the dispatch and the
# receipt all spell it.
READ_OPERATION_NAME = owner_path.READ_OPERATION_NAME

# The declared content-stability rule this receipt's digest applies, and the two
# sets it is built from. CLOCK_LEAF_KEYS are the wall-clock leaves a receipt in
# this family publishes, the geometry harness's own declared set; CLOCK_DERIVED_KEYS
# are the keys whose value is derived from a stripped value -- a chained manifest
# hash, a chained receipt hash, or a digest computed over one -- which the rule
# strips as a class rather than case by case. This runner's measured body carries
# no inner wall-clock field and no such derived digest: no wall-clock value is
# ever handed to the owner here, so the only leaf the rule removes is the
# top-level ``runtime_seconds``, and CLOCK_DERIVED_KEYS is empty by measurement
# (a key belongs in it the moment this body grows one, as
# run_memory_store_scale.CLOCK_DERIVED_KEYS records for its own body). The set is
# declared inside the receipt beside the definition it belongs to, and
# ``receipt_digest`` below strips exactly this set: this runner reads its own
# declaration rather than another module's constant.
CLOCK_LEAF_KEYS = tuple(sorted(geometry.TIMING_KEYS))
CLOCK_DERIVED_KEYS: tuple[str, ...] = ()
STRIP_KEYS = tuple(sorted(set(CLOCK_LEAF_KEYS) | set(CLOCK_DERIVED_KEYS)))

RECEIPT_PATH = Path("_diag/memory-consumer-path/exploration.json")


@dataclass(frozen=True)
class MemoryConsumerConfig:
    """Declared measurement settings; every number in the receipt derives from these."""

    target_item_index: int = TARGET_ITEM_INDEX
    mismatch_item_index: int = MISMATCH_ITEM_INDEX
    fallback_item_index: int = FALLBACK_ITEM_INDEX
    write_budget: float = WRITE_BUDGET
    act_budget: float = ACT_BUDGET
    hold_horizon_ticks: int = HOLD_HORIZON_TICKS
    read_floor_fraction: float = READ_FLOOR_FRACTION
    pursuit_margin: float = PURSUIT_MARGIN
    separation_margin: float = SEPARATION_MARGIN
    read_recovery_allowance: float = READ_RECOVERY_ALLOWANCE
    owner_home_prefix: str = "mcp-owner-"

    def __post_init__(self) -> None:
        declared = (
            int(self.target_item_index),
            int(self.mismatch_item_index),
            int(self.fallback_item_index),
        )
        if len(set(declared)) != len(declared):
            raise ValueError("the declared target, mismatch and fallback items must differ")
        for name in ("target_item_index", "mismatch_item_index", "fallback_item_index"):
            index = int(getattr(self, name))
            if not 0 <= index < len(durability.ITEM_SPECS):
                raise ValueError(f"the declared {name} is outside the declared item list")
        if int(self.hold_horizon_ticks) < 1:
            raise ValueError("the declared hold horizon must be positive")
        for name in ("write_budget", "act_budget"):
            if not 0.0 < float(getattr(self, name)) <= 1.0:
                raise ValueError(f"the declared {name} must lie in (0,1]")
        if not 0.0 < float(self.read_floor_fraction) <= 1.0:
            raise ValueError("the declared read floor fraction must lie in (0,1]")
        for name in ("pursuit_margin", "separation_margin"):
            if not 0.0 < float(getattr(self, name)) <= 1.0:
                raise ValueError(f"the declared {name} must lie in (0,1]")
        if float(self.read_recovery_allowance) <= 0.0:
            raise ValueError("the declared recovery allowance must be positive")

    @property
    def target_spec(self) -> durability.ItemSpec:
        return durability.ITEM_SPECS[int(self.target_item_index)]

    @property
    def mismatch_spec(self) -> durability.ItemSpec:
        return durability.ITEM_SPECS[int(self.mismatch_item_index)]

    @property
    def fallback_spec(self) -> durability.ItemSpec:
        return durability.ITEM_SPECS[int(self.fallback_item_index)]

    @property
    def horizon_sample_ticks(self) -> tuple[int, ...]:
        return tuple(range(1, int(self.hold_horizon_ticks) + 1))

    def as_dict(self) -> dict[str, Any]:
        loop = feedback.FeedbackConfig()
        return {
            "target_item": self.target_spec.name,
            "target_item_index": int(self.target_item_index),
            "mismatch_item": self.mismatch_spec.name,
            "mismatch_item_index": int(self.mismatch_item_index),
            "fallback_item": self.fallback_spec.name,
            "fallback_item_index": int(self.fallback_item_index),
            "write_budget": float(self.write_budget),
            "act_budget": float(self.act_budget),
            "hold_horizon_ticks": int(self.hold_horizon_ticks),
            "read_floor_fraction": float(self.read_floor_fraction),
            "pursuit_margin": float(self.pursuit_margin),
            "separation_margin": float(self.separation_margin),
            "read_recovery_allowance": float(self.read_recovery_allowance),
            "read_frame_path": durability.READ_FRAME_PATH,
            "loop_work_ceiling": float(loop.loop_work_ceiling),
            "loop_phase_degrees": float(loop.neutral_gain_phase_degrees),
            "loop_source_enabled": bool(loop.source_enabled),
            "loop_activity_demand": float(loop.activity_demand),
            "neutral_gain_grid": [float(value) for value in loop.neutral_gain_grid],
            "neutral_gain_bracket": float(loop.neutral_gain_bracket),
            "per_tick_decay_reference": float(feedback.PER_TICK_DECAY),
        }


def flat_profile() -> Any:
    """The declared profile, built by the metric harness's own builder."""

    return owner_path.flat_profile()


def plain(value: Any) -> Any:
    """Detached ordinary JSON containers for a value a canonical API froze."""

    return owner_path.plain(value)


def strip_clock_leaves(value: Any) -> Any:
    """Apply this runner's declared strip set to a whole body, at any depth.

    A key is dropped when it is a declared wall-clock leaf, and by rule when it is
    a declared clock-derived digest: a value computed over a stripped value. The
    rule is read from this module's own declaration above, so adding a key to
    ``CLOCK_LEAF_KEYS`` or ``CLOCK_DERIVED_KEYS`` changes what the digest covers.
    """

    if isinstance(value, Mapping):
        return {
            str(key): strip_clock_leaves(item)
            for key, item in value.items()
            if str(key) not in STRIP_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [strip_clock_leaves(item) for item in value]
    return value


def receipt_digest(body: Mapping[str, Any]) -> str:
    """This receipt's content digest, under this runner's own declared strip rule.

    ``run_fractal_lattice_exploration.py`` states and applies the convention: the
    SHA-256 of the canonical JSON (sorted keys, no insignificant whitespace,
    allow_nan=False) of the measured body with the declared wall-clock keys
    stripped, taken before the digest itself is attached. The strip set is this
    runner's own declaration, published in the receipt, and it is applied here by
    ``strip_clock_leaves`` rather than by the geometry harness's fixed set, so what
    this receipt declares is what it applies.
    """

    return geometry.canonical_digest(
        strip_clock_leaves(
            {key: value for key, value in body.items() if key != "receipt_digest"}
        )
    )


def frame(workspace: Any) -> np.ndarray:
    """The declared read frame: the canonical analyzer's flattened coefficients."""

    return durability.read_frame(workspace, durability.READ_FRAME_PATH)


def named_direction(spec: durability.ItemSpec) -> dict[str, Any]:
    """One declared packet direction, as the write and the read both name it."""

    return {
        "path": spec.path,
        "component": spec.component,
        "flow_signal": [float(value) for value in spec.flow_signal],
    }


def share_along(increment: np.ndarray, direction: np.ndarray) -> float | None:
    """The share of one increment's energy that lies along a declared direction."""

    energy = float(np.dot(increment, increment))
    if energy <= 0.0:
        return None
    projection = float(np.dot(increment, direction))
    return (projection * projection) / energy


def open_owner(
    profile: Any, workspace: Any | None = None, prefix: str = "mcp-owner-"
) -> tuple[FieldIntelligenceOwner, Path]:
    """One owner over a fresh data home, holding the page this runner supplies.

    The page is installed through the owner's own constructor (the same public
    argument the owner-write-path runner's ``open_owner`` uses for a blank page),
    so an episode can continue on a page another owner wrote and held without
    either owner touching the other's state.
    """

    home = Path(tempfile.mkdtemp(prefix=prefix))
    state = AtlasState(
        resonant_workspace=workspace if workspace is not None else initial_workspace(profile)
    )
    return FieldIntelligenceOwner(home, initial_state=state), home


# --------------------------------------------------------------------------
# the declared instruments: profile, captures, phase reference, neutral gain
# --------------------------------------------------------------------------
def capture_block(profile: Any, config: MemoryConsumerConfig) -> dict[str, Any]:
    """The declared directions, their overlap, and the target's own deposit."""

    capture_config = durability.DurabilityConfig(write_budget=float(config.write_budget))
    captures = durability.capture_items(capture_config, profile)
    overlaps = durability.overlap_matrix(captures)
    target = captures[int(config.target_item_index)]
    diagonal = [float(overlaps[index][index]) for index in range(len(captures))]
    off_diagonal = [
        float(overlaps[i][j])
        for i in range(len(captures))
        for j in range(len(captures))
        if i != j
    ]
    greatest_overlap = max((abs(value) for value in off_diagonal), default=0.0)
    return {
        "declared": (
            "the durability harness's own captures: each declared item written "
            "through the canonical packet impulse into a fresh field at the declared "
            "write budget, its direction the unit read frame of that write, and the "
            "squared cosine between every pair measured rather than assumed"
        ),
        "item_names": [str(capture["name"]) for capture in captures],
        "target_name": str(target["name"]),
        "target_direction_sha256": str(target["direction_sha256"]),
        "target_captured_deposit": float(target["deposited_energy"]),
        "captured_deposits": {
            str(capture["name"]): float(capture["deposited_energy"]) for capture in captures
        },
        "pairwise_squared_cosine": {
            str(left["name"]): {
                str(right["name"]): float(overlaps[i][j])
                for j, right in enumerate(captures)
            }
            for i, left in enumerate(captures)
        },
        "on_diagonal_squared_cosine_min": float(min(diagonal)),
        "on_diagonal_squared_cosine_max": float(max(diagonal)),
        "greatest_off_diagonal_squared_cosine": float(greatest_overlap),
        "orthogonality_allowance": float(ORTHOGONALITY_ALLOWANCE),
        "the_declared_candidates_are_orthogonal_in_the_read_frame": bool(
            greatest_overlap <= float(ORTHOGONALITY_ALLOWANCE)
            and all(
                abs(value - 1.0) <= float(ORTHOGONALITY_ALLOWANCE) for value in diagonal
            )
        ),
        "why_orthogonality_matters": (
            "the consumer's retrieval of an unwritten declared direction is a "
            "projection on a direction the page does not carry, so the arms' "
            "separation rests on the declared directions being distinct in the read "
            "frame; the measured greatest off-diagonal squared cosine above is the "
            "figure that licenses it, and it is reported rather than assumed"
        ),
    }


def phase_reference_for(profile: Any, captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The declared quadrature read-back reference the loop's phase term is expressed in."""

    loop = feedback.FeedbackConfig()
    phase = feedback.phase_readout_block(
        loop, captures, profile, int(loop.horizon_ticks)
    )
    return {
        "direction": feedback.quadrature_direction(loop, captures, int(loop.headline_item_index)),
        "scale": float(phase["sign_references"]["quadrature_scale"]),
        "quarter_period_tick": int(phase["quarter_period_tick"]),
        "quarter_period_angle_degrees": float(phase["quarter_period_angle_degrees"]),
        "declared": (
            "the feedback harness's own quadrature read-out, measured on this "
            "profile's drift trajectory, with its quarter-period scale. At the "
            "declared phase angle its coefficient in the drive's read-back signal is "
            "the sine of that angle, reported below beside the drive law"
        ),
    }


def neutral_gain_refinement(
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    phase_reference: Mapping[str, Any],
    config: MemoryConsumerConfig,
) -> dict[str, Any]:
    """The declared loop's neutral gain on this profile, by the harness's own refinement.

    The feedback harness's own declared refinement is used unchanged: a declared
    gain grid, then a bisection of the bracket between the no-drive limit and the
    smallest grid gain. It runs at the declared headline item, which is this
    receipt's target item: the refinement's own configuration admits only the
    items whose cited intrinsic lifetime its receipt carries, so this is the one
    item the harness's refinement can measure, and this receipt's per-item
    neutrality probes below measure the gain on the pages it is used on.
    """

    spec = durability.ITEM_SPECS[int(config.target_item_index)]
    loop = feedback.FeedbackConfig(headline_item_index=int(config.target_item_index))
    drift = feedback.LoopArm(
        f"mcp-drift-{spec.name}",
        (int(config.target_item_index),),
        family="memory-consumer-path-drift",
        measure_item_index=int(config.target_item_index),
        horizon_ticks=int(loop.horizon_ticks),
        sample_ticks=tuple(int(tick) for tick in loop.sample_ticks),
    )
    arms = {drift.name: feedback.run_stream(loop, captures, drift, phase_reference, profile)}
    refinement = feedback.measure_neutral_gain(
        loop,
        captures,
        phase_reference,
        profile,
        arms,
        drift_arm=drift.name,
        name_prefix=f"mcp-{spec.name}-",
    )
    return {
        "declared_headline_item": spec.name,
        "declared_headline_item_index": int(config.target_item_index),
        "measured_gain": float(refinement["measured_gain"]),
        "bracket": [float(value) for value in refinement["bracket"]],
        "bracket_width": float(refinement["bracket_width"]),
        "tolerance": float(refinement["tolerance"]),
        "grid": [
            {
                "gain": float(row["gain"]),
                "retention_at_horizon": float(row["retention_at_horizon"]),
            }
            for row in refinement["grid"]
        ],
        "probes": [
            {
                "gain": float(row["gain"]),
                "retention_at_horizon": float(row["retention_at_horizon"]),
            }
            for row in refinement["probes"]
        ],
        "drift_retention_at_horizon": float(refinement["drift_retention_at_horizon"]),
        "grid_monotone": bool(refinement["grid_monotone"]),
        "cross_receipt_reference": {
            "cited_receipt": OWNER_WRITE_PATH_RECEIPT,
            "cited_path": "cycle.neutral_gain.measured_gain",
            "cited_gain": float(CITED_NEUTRAL_GAIN),
            "the_refinement_reproduces_the_cited_gain": bool(
                abs(float(refinement["measured_gain"]) - float(CITED_NEUTRAL_GAIN))
                <= max(float(refinement["tolerance"]), float(refinement["bracket_width"]))
            ),
            "declared": (
                "the same declared profile's neutral gain, as the owner-write-path "
                "receipt carries it: this refinement is the family's own instrument "
                "run again on this profile, so the two figures are expected to "
                "concord, and this receipt reports whether they do instead of "
                "importing the other receipt's number"
            ),
        },
        "declared": (
            "the feedback harness's own neutral-gain refinement, run on this "
            "profile with this item as the written and measured item"
        ),
    }


def neutrality_probe(
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    phase_reference: Mapping[str, Any],
    config: MemoryConsumerConfig,
    *,
    item_index: int,
    gain: float,
) -> dict[str, Any]:
    """The declared gain's neutrality measured on one written item's own page.

    The refinement above measures the profile's neutral gain at the target item,
    which is the one item the refinement's configuration admits. This probe runs
    the harness's own declared loop (``run_stream``) on the item the receipt is
    about to hold -- once at the measured gain and once at zero gain -- so the
    gain's neutrality on that item's page is measured rather than borrowed from
    the item the refinement was run at. The criterion is the refinement's own:
    the hold must retain at or above the written level where the no-drive arm
    decays below it.
    """

    loop = feedback.FeedbackConfig()
    spec = durability.ITEM_SPECS[int(item_index)]
    hold = feedback.LoopArm(
        f"mcp-neutrality-hold-{spec.name}",
        (int(item_index),),
        gain=float(gain),
        family="memory-consumer-path-neutrality",
        measure_item_index=int(item_index),
        phase_degrees=float(loop.neutral_gain_phase_degrees),
    )
    drift = replace(
        hold,
        name=f"mcp-neutrality-drift-{spec.name}",
        gain=0.0,
        phase_degrees=0.0,
        family="memory-consumer-path-neutrality-drift",
    )
    held = feedback.run_stream(loop, captures, hold, phase_reference, profile)
    decayed = feedback.run_stream(loop, captures, drift, phase_reference, profile)
    held_retention = float(held["neutral_stability"]["measure_retention_at_horizon"])
    drift_retention = float(decayed["neutral_stability"]["measure_retention_at_horizon"])
    return {
        "item": spec.name,
        "item_index": int(item_index),
        "gain": float(gain),
        "retention_at_the_measured_gain": held_retention,
        "retention_with_no_drive": drift_retention,
        "the_measured_gain_is_neutral_on_this_items_page": bool(
            held_retention >= 1.0 > drift_retention
        ),
        "declared": (
            "the feedback harness's own loop run on this item's page at the measured "
            "gain and at zero gain, judged by the refinement's own criterion"
        ),
    }


# --------------------------------------------------------------------------
# the field episodes: write, hold, read
# --------------------------------------------------------------------------
def hold_episode(
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    phase_reference: Mapping[str, Any],
    config: MemoryConsumerConfig,
    *,
    item_index: int,
    gain: float,
    name: str,
) -> tuple[dict[str, Any], Any]:
    """One declared field episode: write one item through the owner, hold it, read it.

    Every tick of the hold is an owner transition on the owner's own page -- one
    ``advance`` tick and, when the declared law gives a nonzero amplitude, one
    ``write_packet_impulse`` drive at the declared per-tick work ceiling -- so the
    canonical field is the only adaptive state in the episode and the held page
    the consumer reads is the page this owner published.

    The same tick body is replayed functionally from the same start page through
    the feedback harness's own primitives with the amplitudes this episode
    measured; the two routes' page digests are compared, so the claim that the
    owner route runs the declared loop is measured rather than assumed.
    """

    loop = feedback.FeedbackConfig()
    spec = durability.ITEM_SPECS[int(item_index)]
    direction = captures[int(item_index)]["direction"]
    horizon = int(config.hold_horizon_ticks)
    ceiling = float(loop.loop_work_ceiling)
    phase_degrees = float(loop.neutral_gain_phase_degrees)
    arm = feedback.LoopArm(
        f"mcp-hold-{name}",
        (int(item_index),),
        gain=float(gain),
        family="memory-consumer-path-hold",
        phase_degrees=phase_degrees,
    )
    owner, home = open_owner(profile, prefix=config.owner_home_prefix)
    try:
        blank_page_sha256 = durability.page_sha256(owner.state.resonant_workspace)
        clock_before = int(owner.inspect_resonance()["evidence_tick"])
        generation_before = int(owner.state.generation)
        blank_frame_energy = float(durability.squared_norm(frame(owner.state.resonant_workspace)))
        write = plain(
            owner.write_packet_impulse(
                f"{name}:write",
                **named_direction(spec),
                work_budget=float(config.write_budget),
            )
        )
        write_receipt = plain(write["impulse_receipt"])
        post_write = owner.state.resonant_workspace
        post_write_frame = frame(post_write)
        post_write_energy = float(durability.squared_norm(post_write_frame))
        deposit = post_write_energy - blank_frame_energy
        signed_reference = float(np.dot(post_write_frame, direction))

        amplitudes: list[float] = []
        drive_applied_work = 0.0
        drive_calls = 0
        drive_skipped_ticks = 0
        drive_clipped_ticks = 0
        drive_accepted = 0
        retention_at_ticks: list[dict[str, float]] = []
        for tick in range(1, horizon + 1):
            owner.advance(f"{name}:advance:{tick}", ticks=1, source_enabled=False)
            vector = frame(owner.state.resonant_workspace)
            ratio = feedback.phase_signal(
                loop, arm, vector, direction, signed_reference, phase_reference
            )
            amplitude, clipped = feedback.loop_amplitude(loop, arm.gain, ratio)
            amplitudes.append(float(amplitude))
            drive_clipped_ticks += int(bool(clipped))
            if amplitude:
                per_tick_work = ceiling * abs(float(amplitude))
                drive = plain(
                    owner.write_packet_impulse(
                        f"{name}:drive:{tick}",
                        path=spec.path,
                        component=spec.component,
                        flow_signal=[float(amplitude), 0.0],
                        work_budget=per_tick_work,
                    )
                )
                drive_calls += 1
                drive_accepted += int(bool(drive["impulse_receipt"]["accepted"]))
                drive_applied_work += float(drive["impulse_receipt"]["applied_work"])
                vector = frame(owner.state.resonant_workspace)
            else:
                drive_skipped_ticks += 1
            retention_at_ticks.append(
                {
                    "tick": float(tick),
                    "frame_energy_ratio": top_ratio(
                        durability.squared_norm(vector), post_write_energy
                    ),
                    "signed_ratio": top_ratio(
                        float(np.dot(vector, direction)), signed_reference
                    ),
                }
            )

        held = owner.state.resonant_workspace
        held_frame = frame(held)
        held_energy = float(durability.squared_norm(held_frame))
        reads = {
            str(capture["name"]): plain(
                owner.read_packet_deposit(**named_direction(durability.ITEM_SPECS[index]))
            )
            for index, capture in enumerate(captures)
        }
        page_before_the_reads = durability.page_sha256(held)
        generation_before_the_reads = int(owner.state.generation)
        clock_after = int(owner.inspect_resonance()["evidence_tick"])
        held_read = plain(owner.read_packet_deposit(**named_direction(spec)))
        page_after_the_reads = durability.page_sha256(owner.state.resonant_workspace)
        unwritten_index = (
            int(config.fallback_item_index)
            if int(item_index) != int(config.fallback_item_index)
            else int(config.mismatch_item_index)
        )
        mismatch_name = durability.ITEM_SPECS[unwritten_index].name
        unwritten_relative = (
            top_ratio(
                abs(float(reads[mismatch_name]["recovered_deposit"]) - float(deposit)),
                float(deposit),
            )
            if float(deposit) > 0.0
            else None
        )

        # The declared loop replayed through the harness's own primitives from the
        # same start page at the amplitudes this episode measured.
        replay = post_write
        for amplitude in amplitudes:
            replay, _ = feedback.advance_workspace(
                replay,
                ticks=1,
                demand=float(loop.activity_demand),
                source_enabled=bool(loop.source_enabled),
            )
            if amplitude:
                replay, _ = feedback.apply_drive(
                    replay, int(item_index), amplitude, ceiling * abs(amplitude)
                )
        replay_page_sha256 = durability.page_sha256(replay)
        held_page_sha256 = durability.page_sha256(held)
        return (
            {
                "episode": str(name),
                "written_item": spec.name,
                "written_item_index": int(item_index),
                "hold_horizon_ticks": horizon,
                "hold_horizon_parity": "even" if horizon % 2 == 0 else "odd",
                "gain": float(gain),
                "phase_degrees": phase_degrees,
                "quadrature_coefficient": math.sin(math.radians(phase_degrees)),
                "loop_work_ceiling": ceiling,
                "blank_page_sha256": blank_page_sha256,
                "post_write_page_sha256": durability.page_sha256(post_write),
                "held_page_sha256": held_page_sha256,
                "write": {
                    "accepted": bool(write_receipt["accepted"]),
                    "applied_work": float(write_receipt["applied_work"]),
                    "impulse_amount": float(write_receipt["impulse_amount"]),
                    "read_frame_deposit": float(deposit),
                    "read_frame_energy_after": post_write_energy,
                },
                "hold": {
                    "advance_ticks": horizon,
                    "drive_calls": drive_calls,
                    "drive_accepted": drive_accepted,
                    "drive_skipped_ticks": drive_skipped_ticks,
                    "drive_clipped_ticks": drive_clipped_ticks,
                    "drive_applied_work_total": float(drive_applied_work),
                    "amplitude_max": float(max((abs(a) for a in amplitudes), default=0.0)),
                    "amplitudes": [float(a) for a in amplitudes],
                    "frame_energy_ratio_at_horizon": top_ratio(held_energy, post_write_energy),
                    "retention_at_ticks": retention_at_ticks,
                },
                "read_on_the_held_page": {
                    "by_item": {
                        item: {
                            "recovered_deposit": float(readout["recovered_deposit"]),
                            "direction_sha256": str(readout["direction_sha256"]),
                            "readout_kind": str(readout["readout_kind"]),
                            "evidence_added": bool(readout["evidence_added"]),
                            "read_frame_energy": float(readout["read_frame_energy"]),
                        }
                        for item, readout in reads.items()
                    },
                    "written_direction_relative_difference": top_ratio(
                        abs(
                            float(reads[spec.name]["recovered_deposit"])
                            - float(deposit)
                        ),
                        float(deposit),
                    ),
                    "signed_ratio_at_horizon": (
                        float(retention_at_ticks[-1]["signed_ratio"])
                        if retention_at_ticks
                        else None
                    ),
                    "post_hold_recovery_allowance": float(config.read_recovery_allowance),
                    "the_written_directions_recovery_is_within_the_hold_allowance": bool(
                        float(deposit) > 0.0
                        and abs(
                            float(reads[spec.name]["recovered_deposit"]) - float(deposit)
                        )
                        <= float(config.read_recovery_allowance) * float(deposit)
                    ),
                    "unwritten_item": mismatch_name,
                    "unwritten_direction_relative_difference": unwritten_relative,
                    "the_unwritten_directions_recovery_misses_the_allowance": bool(
                        unwritten_relative is not None
                        and float(unwritten_relative)
                        > float(config.read_recovery_allowance)
                    ),
                    "declared": (
                        "the owner's own read operation, called once per declared item "
                        "on the held page, immediately before the writes below. The "
                        "written direction's deposit is recovered to the declared "
                        "post-hold allowance, which is wider than the exact identity a "
                        "fresh single-write page carries (the owner-write-path receipt "
                        "measures that at 1e-12) because the declared hold drives the "
                        "page for its whole horizon; the unwritten direction is the "
                        "can-fail control for the same predicate, and it must miss. "
                        "The raw relative difference above is the hold's own measured "
                        "phase at the horizon, not a read error: the declared loop's "
                        "drive alternates sign every tick, so a horizon of odd parity "
                        "leaves the held frame reversed in sign, and this read is a "
                        "squared projection, which returns the written deposit times "
                        "that signed phase squared. The signed ratio and the declared "
                        "horizon's parity are reported beside the difference, and this "
                        "receipt's own declared horizon is even"
                    ),
                    "instrument": (
                        "the owner's own read operation, called once per declared item "
                        "on the held page, immediately before the writes below"
                    ),
                },
                "read_invariants": {
                    "page_before_the_reads": page_before_the_reads,
                    "page_after_the_reads": page_after_the_reads,
                    "the_reads_change_no_page": page_before_the_reads == page_after_the_reads,
                    "generation_before_the_reads": generation_before_the_reads,
                    "generation_after_the_reads": int(owner.state.generation),
                    "the_reads_change_no_generation": generation_before_the_reads
                    == int(owner.state.generation),
                    "held_read_returns_the_same_readout_when_repeated": bool(
                        held_read == reads[spec.name]
                    ),
                },
                "clocks": {
                    "evidence_tick_before_the_episode": clock_before,
                    "evidence_tick_after_the_episode": clock_after,
                    "the_episode_moves_no_evidence_clock": clock_before == clock_after,
                    "generation_before_the_episode": generation_before,
                    "generation_at_the_horizon": int(owner.state.generation),
                    "field_ticks_at_the_horizon": int(held.field_ticks),
                },
                "owner_route_against_the_declared_loop": {
                    "replay_page_sha256": replay_page_sha256,
                    "the_owner_route_reproduces_the_declared_loop": bool(
                        replay_page_sha256 == held_page_sha256
                    ),
                    "declared": (
                        "the declared loop's tick body replayed functionally from the "
                        "same post-write page through the feedback harness's own "
                        "advance_workspace and apply_drive at the amplitudes this "
                        "episode measured: equal page digests at the horizon are what "
                        "license reading the owner-route hold above"
                    ),
                },
            },
            held,
        )
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def blank_episode(
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    config: MemoryConsumerConfig,
) -> tuple[dict[str, Any], Any]:
    """The no-memory field episode: the declared horizon on a blank page, no drive.

    The declared loop cannot close on this page: its read-back reference is the
    written item's own post-write projection, which a blank page does not carry,
    so the episode advances the same horizon with no write and no drive. The
    batched advance is compared against a single-tick advance of the canonical
    operator on the same page, so the batched call is measured to be the same
    evolution rather than assumed to be.
    """

    horizon = int(config.hold_horizon_ticks)
    owner, home = open_owner(profile, prefix=config.owner_home_prefix)
    try:
        blank = owner.state.resonant_workspace
        clock_before = int(owner.inspect_resonance()["evidence_tick"])
        single = blank
        for _ in range(horizon):
            single, _ = advance_workspace(single, ticks=1, source_enabled=False)
        owner.advance("blank:advance", ticks=horizon, source_enabled=False)
        held = owner.state.resonant_workspace
        reads = {
            str(capture["name"]): plain(
                owner.read_packet_deposit(**named_direction(durability.ITEM_SPECS[index]))
            )
            for index, capture in enumerate(captures)
        }
        page_before_the_reads = durability.page_sha256(held)
        page_after_the_reads = durability.page_sha256(owner.state.resonant_workspace)
        return (
            {
                "episode": "blank-no-memory",
                "written_item": None,
                "written_item_index": None,
                "hold_horizon_ticks": horizon,
                "hold_horizon_parity": "even" if horizon % 2 == 0 else "odd",
                "gain": None,
                "blank_page_sha256": durability.page_sha256(blank),
                "post_write_page_sha256": None,
                "held_page_sha256": durability.page_sha256(held),
                "write": None,
                "hold": {
                    "advance_ticks": horizon,
                    "drive_calls": 0,
                    "drive_accepted": 0,
                    "drive_skipped_ticks": horizon,
                    "drive_clipped_ticks": 0,
                    "drive_applied_work_total": 0.0,
                    "amplitude_max": 0.0,
                    "amplitudes": [],
                    "frame_energy_ratio_at_horizon": 0.0,
                    "retention_at_ticks": [],
                    "declared": (
                        "no write and no drive: the declared loop has no normalisation "
                        "reference on a blank page, so this episode advances the "
                        "declared horizon and nothing else"
                    ),
                },
                "read_on_the_held_page": {
                    "by_item": {
                        item: {
                            "recovered_deposit": float(readout["recovered_deposit"]),
                            "direction_sha256": str(readout["direction_sha256"]),
                            "readout_kind": str(readout["readout_kind"]),
                            "evidence_added": bool(readout["evidence_added"]),
                            "read_frame_energy": float(readout["read_frame_energy"]),
                        }
                        for item, readout in reads.items()
                    },
                    "written_direction_relative_difference": None,
                    "the_written_directions_recovery_is_within_the_hold_allowance": None,
                    "declared": (
                        "the owner's own read operation on the advanced blank page. "
                        "This episode writes nothing, so the written direction's "
                        "recovery predicate is not evaluated here and every declared "
                        "direction's read returns the zero reported above -- the "
                        "no-memory arm's own can-fail position"
                    ),
                    "instrument": (
                        "the owner's own read operation on the advanced blank page; "
                        "there is no written deposit on this page to recover"
                    ),
                },
                "read_invariants": {
                    "page_before_the_reads": page_before_the_reads,
                    "page_after_the_reads": page_after_the_reads,
                    "the_reads_change_no_page": page_before_the_reads == page_after_the_reads,
                    "generation_before_the_reads": int(owner.state.generation),
                    "generation_after_the_reads": int(owner.state.generation),
                    "the_reads_change_no_generation": True,
                    "held_read_returns_the_same_readout_when_repeated": True,
                },
                "clocks": {
                    "evidence_tick_before_the_episode": clock_before,
                    "evidence_tick_after_the_episode": int(
                        owner.inspect_resonance()["evidence_tick"]
                    ),
                    "the_episode_moves_no_evidence_clock": clock_before
                    == int(owner.inspect_resonance()["evidence_tick"]),
                    "generation_before_the_episode": 0,
                    "generation_at_the_horizon": int(owner.state.generation),
                    "field_ticks_at_the_horizon": int(held.field_ticks),
                },
                "owner_route_against_the_declared_loop": {
                    "single_tick_advance_page_sha256": durability.page_sha256(single),
                    "batched_advance_page_sha256": durability.page_sha256(held),
                    "the_batched_advance_is_the_single_tick_advance": bool(
                        durability.page_sha256(single) == durability.page_sha256(held)
                    ),
                    "declared": (
                        "this episode writes nothing, so there is no driven loop here "
                        "for the owner route to reproduce; what is compared is the "
                        "batched owner advance against one canonical advance tick per "
                        "call on the same blank page, and equal digests are what "
                        "license the batched call in this episode"
                    ),
                },
            },
            held,
        )
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


# --------------------------------------------------------------------------
# the consumer: retrieve, decide, act
# --------------------------------------------------------------------------
def consumer_episode(
    profile: Any,
    workspace: Any,
    captures: Sequence[Mapping[str, Any]],
    config: MemoryConsumerConfig,
    *,
    held_episode: Mapping[str, Any],
    name: str,
    read_suppressed: bool = False,
    policy_mutated: bool = False,
) -> dict[str, Any]:
    """One consumer episode on a page another owner wrote and held.

    The consumer's whole declared policy is here: one retrieval through the
    owner's read operation (or the declared suppressed zero, which is not a read
    at all), one comparison against the declared read floor, and one act through
    the owner's write path on the direction the policy selected. The act is the
    only write the consumer performs.
    """

    target = config.target_spec
    mismatch = config.mismatch_spec
    fallback = config.fallback_spec
    floor = float(config.read_floor_fraction) * float(
        _captured_deposit(captures, int(config.target_item_index))
    )
    owner, home = open_owner(profile, workspace=workspace, prefix=config.owner_home_prefix)
    try:
        clock_before = int(owner.inspect_resonance()["evidence_tick"])
        generation_before = int(owner.state.generation)
        page_on_arrival = durability.page_sha256(owner.state.resonant_workspace)
        instrument_read = None
        if read_suppressed:
            instrument_read = plain(owner.read_packet_deposit(**named_direction(target)))

        read_calls = 0
        readout: Mapping[str, Any] | None = None
        if read_suppressed:
            retrieved = 0.0
        else:
            readout = plain(owner.read_packet_deposit(**named_direction(target)))
            read_calls = 1
            retrieved = float(readout["recovered_deposit"])
        page_after_the_retrieval = durability.page_sha256(owner.state.resonant_workspace)

        reaches_floor = bool(retrieved >= floor)
        selected = int(config.target_item_index) if reaches_floor else int(config.fallback_item_index)
        if policy_mutated:
            selected = int(config.target_item_index)
        selected_spec = durability.ITEM_SPECS[selected]

        frame_before = frame(owner.state.resonant_workspace)
        page_before_the_act = durability.page_sha256(owner.state.resonant_workspace)
        query_read_before_the_act = plain(owner.read_packet_deposit(**named_direction(target)))
        act = plain(
            owner.write_packet_impulse(
                f"{name}:act",
                **named_direction(selected_spec),
                work_budget=float(config.act_budget),
            )
        )
        act_receipt = plain(act["impulse_receipt"])
        frame_after = frame(owner.state.resonant_workspace)
        page_after_the_act = durability.page_sha256(owner.state.resonant_workspace)
        query_read_after_the_act = plain(owner.read_packet_deposit(**named_direction(target)))
        increment = frame_after - frame_before
        increment_energy = float(durability.squared_norm(increment))
        shares = {
            target.name: share_along(increment, captures[int(config.target_item_index)]["direction"]),
            mismatch.name: share_along(
                increment, captures[int(config.mismatch_item_index)]["direction"]
            ),
            fallback.name: share_along(
                increment, captures[int(config.fallback_item_index)]["direction"]
            ),
        }
        clock_after = int(owner.inspect_resonance()["evidence_tick"])
        toward_target = shares[target.name]
        return {
            "arm": str(name),
            "declared": (
                "one consumer episode on the page this arm's field episode published: "
                "one retrieval through the owner's read operation (or the declared "
                "suppressed zero, which calls no read), one comparison of the "
                "retrieved deposit against the declared read floor, and one act -- "
                "exactly one owner write of the selected declared direction at the "
                "declared act budget"
            ),
            "field_episode": str(held_episode["episode"]),
            "policy": {
                "read_suppressed": bool(read_suppressed),
                "policy_mutated": bool(policy_mutated),
                "declared_rule": (
                    "retrieve the target direction's deposit; if it reaches the read "
                    "floor, pursue the target; otherwise pursue the fallback"
                ),
                "declared_mutation": (
                    "the retrieval is ignored and the target is pursued "
                    "unconditionally: the can-fail control for the statistic"
                )
                if policy_mutated
                else None,
            },
            "retrieval": {
                "query_item": target.name,
                "query_item_index": int(config.target_item_index),
                "read_calls": read_calls,
                "retrieved_deposit": float(retrieved),
                "readout_kind": None if readout is None else str(readout["readout_kind"]),
                "readout_declares_evidence_added": None
                if readout is None
                else bool(readout["evidence_added"]),
                "read_frame_energy": None
                if readout is None
                else float(readout["read_frame_energy"]),
                "read_direction_sha256": None
                if readout is None
                else str(readout["direction_sha256"]),
                "suppressed_value": 0.0 if read_suppressed else None,
                "instrument": (
                    "the owner's own read operation on the page this consumer is "
                    "acting on"
                ),
            },
            "instrument_read_by_the_runner": None
            if instrument_read is None
            else {
                "recovered_deposit": float(instrument_read["recovered_deposit"]),
                "readout_kind": str(instrument_read["readout_kind"]),
                "declared": (
                    "the runner's own read of the same direction on the same page, "
                    "taken before the consumer's retrieval and not passed to the "
                    "consumer: it measures what the field was carrying at the moment "
                    "the suppressed retrieval declined to look"
                ),
            },
            "decision": {
                "read_floor": floor,
                "read_floor_fraction": float(config.read_floor_fraction),
                "target_captured_deposit": float(
                    _captured_deposit(captures, int(config.target_item_index))
                ),
                "retrieved_reaches_the_floor": reaches_floor,
                "selected_item": selected_spec.name,
                "selected_item_index": int(selected),
                "selected_is_the_target": bool(selected == int(config.target_item_index)),
            },
            "act": {
                "requested_work": float(act_receipt["requested_work"]),
                "applied_work": float(act_receipt["applied_work"]),
                "accepted": bool(act_receipt["accepted"]),
                "impulse_amount": float(act_receipt["impulse_amount"]),
                "page_before": page_before_the_act,
                "page_after": page_after_the_act,
                "the_act_changes_the_page": page_before_the_act != page_after_the_act,
                "generation_before": generation_before,
                "generation_after": int(owner.state.generation),
                "the_act_advances_the_generation_by_one": int(owner.state.generation)
                == generation_before + 1,
            },
            "statistic": {
                "definition": (
                    "the share of the act's read-frame increment lying along each "
                    "declared candidate: dot(frame_after - frame_before, u)**2 over "
                    "dot(frame_after - frame_before, frame_after - frame_before), "
                    "measured with the durability harness's read frame and its "
                    "captured unit directions"
                ),
                "act_increment_energy": increment_energy,
                "share_along_target": None if toward_target is None else float(toward_target),
                "share_along_mismatch": shares[mismatch.name],
                "share_along_fallback": shares[fallback.name],
                "share_along_target_is_declared": None if toward_target is None else float(
                    toward_target
                )
                >= float(config.pursuit_margin),
                "the_act_deposited_something": increment_energy > 0.0,
                "pursuit_margin": float(config.pursuit_margin),
            },
            "owner_read_across_the_act": {
                "recovered_deposit_before": float(
                    query_read_before_the_act["recovered_deposit"]
                ),
                "recovered_deposit_after": float(query_read_after_the_act["recovered_deposit"]),
                "difference": float(query_read_after_the_act["recovered_deposit"])
                - float(query_read_before_the_act["recovered_deposit"]),
                "declared": (
                    "the owner's own read of the queried direction taken immediately "
                    "before and after the act, an owner-side observable of the same "
                    "act that does not use this runner's frame arithmetic"
                ),
            },
            "invariants": {
                "page_on_arrival": page_on_arrival,
                "page_after_the_retrieval": page_after_the_retrieval,
                "the_retrieval_changes_no_page": page_on_arrival == page_after_the_retrieval,
                "evidence_tick_before": clock_before,
                "evidence_tick_after": clock_after,
                "the_consumer_moves_no_evidence_clock": clock_before == clock_after,
            },
        }
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def _captured_deposit(
    captures: Sequence[Mapping[str, Any]], index: int
) -> float:
    return float(captures[int(index)]["deposited_energy"])


def top_ratio(numerator: float, denominator: float) -> float:
    """One measured ratio, with a declared zero denominator reported as zero."""

    if denominator == 0.0:
        return 0.0
    return float(numerator) / float(denominator)


# --------------------------------------------------------------------------
# the evidence clock: what the read's declaration leaves alone, and what moves it
# --------------------------------------------------------------------------
def evidence_clock_block(profile: Any) -> dict[str, Any]:
    """The alternative declaration, measured on a separate declared state.

    The receipt's arms show the owner's published evidence clock unchanged across
    every consumer episode. This block is the can-fail control for that
    invariance: the same published key, moved by one admission through the
    owner's own observation rule at the atlas level, so the arm figures above are
    shown to compare a quantity that can move.
    """

    variable = "memory-consumer-clock-control"
    atlas = FieldAtlas()
    state = atlas.add_variable(
        AtlasState(resonant_workspace=initial_workspace(profile)),
        VariableSpec(variable_id=variable, lower=-1.0, upper=1.0),
    )
    state = atlas.add_chart(
        state,
        RelationChart.empty(
            chart_id=variable,
            scope=(variable,),
            ridge=1e-5,
            observation_norm_bound=64.0,
            prior_mass=1e-3,
        ),
    )
    before = int(atlas.inspect_resonance(state)["evidence_tick"])
    event_id = hashlib.sha256(b"memory-consumer-path:clock-control:event").hexdigest()
    state, _ = atlas.admit_observation(
        state,
        event_id=event_id,
        source_revision_id=hashlib.sha256(
            b"memory-consumer-path:clock-control:source"
        ).hexdigest(),
        values={variable: 0.5},
        context={"declared": "memory-consumer-path evidence-clock control"},
    )
    after = int(atlas.inspect_resonance(state)["evidence_tick"])
    return {
        "declared": (
            "the same published quantity the arms read, moved by one admission "
            "through the owner's own observation-admission rule on a separate state "
            "of this profile"
        ),
        "evidence_tick_before_the_admission": before,
        "evidence_tick_after_the_admission": after,
        "an_admission_moves_the_evidence_clock": bool(after == before + 1),
        "instrument": "FieldAtlas.admit_observation, one declared variable, one chart",
    }


# --------------------------------------------------------------------------
# receipt
# --------------------------------------------------------------------------
def measure(config: MemoryConsumerConfig) -> dict[str, Any]:
    """Every declared block of this receipt, measured in order."""

    profile = flat_profile()
    captures = capture_block(profile, config)
    capture_sequences = durability.capture_items(
        durability.DurabilityConfig(write_budget=float(config.write_budget)), profile
    )
    phase_reference = phase_reference_for(profile, capture_sequences)
    refinement = neutral_gain_refinement(profile, capture_sequences, phase_reference, config)
    gain = float(refinement["measured_gain"])
    neutrality = {
        "target": neutrality_probe(
            profile,
            capture_sequences,
            phase_reference,
            config,
            item_index=int(config.target_item_index),
            gain=gain,
        ),
        "mismatch": neutrality_probe(
            profile,
            capture_sequences,
            phase_reference,
            config,
            item_index=int(config.mismatch_item_index),
            gain=gain,
        ),
    }

    target_field, target_page = hold_episode(
        profile,
        capture_sequences,
        phase_reference,
        config,
        item_index=int(config.target_item_index),
        gain=gain,
        name="target",
    )
    mismatch_field, mismatch_page = hold_episode(
        profile,
        capture_sequences,
        phase_reference,
        config,
        item_index=int(config.mismatch_item_index),
        gain=gain,
        name="mismatch",
    )
    blank_field, blank_page = blank_episode(profile, capture_sequences, config)

    arms = [
        consumer_episode(
            profile,
            target_page,
            capture_sequences,
            config,
            held_episode=target_field,
            name=ARM_MEMORY_USED,
        ),
        consumer_episode(
            profile,
            target_page,
            capture_sequences,
            config,
            held_episode=target_field,
            name=ARM_IDENTITY_CONTROL,
            read_suppressed=True,
        ),
        consumer_episode(
            profile,
            blank_page,
            capture_sequences,
            config,
            held_episode=blank_field,
            name=ARM_NO_MEMORY,
        ),
        consumer_episode(
            profile,
            mismatch_page,
            capture_sequences,
            config,
            held_episode=mismatch_field,
            name=ARM_MISMATCH,
        ),
        consumer_episode(
            profile,
            blank_page,
            capture_sequences,
            config,
            held_episode=blank_field,
            name=ARM_POLICY_MUTATED,
            policy_mutated=True,
        ),
    ]
    return {
        "captures": captures,
        "phase_reference": {
            key: value for key, value in phase_reference.items() if key != "direction"
        },
        "neutral_gain": {
            "refinement": refinement,
            "neutrality_on_the_written_items_pages": neutrality,
            "declared": (
                "one measured neutral gain for this profile, from the feedback "
                "harness's own refinement at the declared headline item; the gain's "
                "neutrality on each page this receipt actually holds is measured "
                "separately above and again by each field episode's own frame energy "
                "ratio at its horizon, because the refinement's configuration admits "
                "only the items whose cited intrinsic lifetime its receipt carries"
            ),
        },
        "field_episodes": {
            "target": target_field,
            "mismatch": mismatch_field,
            "blank": blank_field,
        },
        "arms": arms,
        "comparisons": comparison_block(arms, config),
        "evidence_clock": evidence_clock_block(profile),
    }


def arm_row(arm: Mapping[str, Any]) -> dict[str, Any]:
    """One declared arm's own figures, as the comparison block reads them."""

    return {
        "arm": str(arm["arm"]),
        "field_episode": str(arm["field_episode"]),
        "read_calls": int(arm["retrieval"]["read_calls"]),
        "retrieved_deposit": float(arm["retrieval"]["retrieved_deposit"]),
        "read_floor": float(arm["decision"]["read_floor"]),
        "retrieved_reaches_the_floor": bool(arm["decision"]["retrieved_reaches_the_floor"]),
        "selected_item": str(arm["decision"]["selected_item"]),
        "pursued_the_target": bool(arm["decision"]["selected_is_the_target"]),
        "act_increment_energy": float(arm["statistic"]["act_increment_energy"]),
        "share_along_target": arm["statistic"]["share_along_target"],
        "share_along_mismatch": arm["statistic"]["share_along_mismatch"],
        "share_along_fallback": arm["statistic"]["share_along_fallback"],
    }


def separation(value: float | None, margin: float) -> bool:
    """One declared separation predicate over two measured shares."""

    return bool(value is not None and float(value) >= float(margin))


def comparison_block(
    arms: Sequence[Mapping[str, Any]], config: MemoryConsumerConfig
) -> dict[str, Any]:
    """The four arms side by side, their margins, and the controls' verdicts."""

    rows = {str(arm["arm"]): arm_row(arm) for arm in arms}
    used = rows[ARM_MEMORY_USED]
    identity = rows[ARM_IDENTITY_CONTROL]
    none = rows[ARM_NO_MEMORY]
    mismatch = rows[ARM_MISMATCH]
    mutated = rows[ARM_POLICY_MUTATED]
    margin = float(config.pursuit_margin)
    separation_margin = float(config.separation_margin)

    def gap(left: Mapping[str, Any], right: Mapping[str, Any]) -> float | None:
        left_share, right_share = left["share_along_target"], right["share_along_target"]
        if left_share is None or right_share is None:
            return None
        return float(left_share) - float(right_share)

    greatest_control = max(
        float(identity["share_along_target"] or 0.0),
        float(none["share_along_target"] or 0.0),
    )
    a_minus_identity = gap(used, identity)
    a_minus_none = gap(used, none)
    a_minus_mismatch = gap(used, mismatch)
    a_minus_controls = (
        None if used["share_along_target"] is None else float(used["share_along_target"]) - greatest_control
    )
    return {
        "declared": (
            "the four declared arms' own figures, the declared margins applied to "
            "them, and the controls' verdicts. Every share below is the arm's own "
            "measured act increment along the target, so a figure of zero here is a "
            "measured zero rather than a missing measurement"
        ),
        "instrument": (
            "the durability harness's read frame and captured unit directions, "
            "applied to the owner's canonical page immediately before and after the "
            "consumer's act"
        ),
        "arm_table": [rows[name] for name in (ARM_MEMORY_USED, ARM_IDENTITY_CONTROL, ARM_NO_MEMORY, ARM_MISMATCH, ARM_POLICY_MUTATED)],
        "predicate": (
            "the target's share of the act increment reaches the declared pursuit "
            "margin; applied unchanged to every arm and to the mutated leg"
        ),
        "pursuit_margin": margin,
        "separation_margin": separation_margin,
        "A_share_along_target": used["share_along_target"],
        "B_share_along_target": identity["share_along_target"],
        "C_share_along_target": none["share_along_target"],
        "D_share_along_target": mismatch["share_along_target"],
        "A_minus_B": a_minus_identity,
        "A_minus_C": a_minus_none,
        "A_minus_D": a_minus_mismatch,
        "A_minus_the_greater_control": a_minus_controls,
        "the_memory_arm_pursues_the_target": separation(used["share_along_target"], margin),
        "the_identity_control_does_not_pursue_the_target": bool(
            not separation(identity["share_along_target"], margin)
        ),
        "the_no_memory_arm_does_not_pursue_the_target": bool(
            not separation(none["share_along_target"], margin)
        ),
        "the_mismatch_control_does_not_pursue_the_target": bool(
            not separation(mismatch["share_along_target"], margin)
        ),
        "A_separates_from_both_controls_by_the_declared_margin": separation(
            a_minus_controls, separation_margin
        ),
        "A_separates_from_B_by_the_declared_margin": separation(
            a_minus_identity, separation_margin
        ),
        "A_separates_from_C_by_the_declared_margin": separation(
            a_minus_none, separation_margin
        ),
        "A_separates_from_D_by_the_declared_margin": separation(
            a_minus_mismatch, separation_margin
        ),
        "memory_contribution_attributable_to_content": {
            "declared": (
                "what A's behaviour is worth relative to the arms in which the field "
                "was written or held but the retrieved content was not the one asked "
                "for: D wrote and held a different declared item with the same "
                "mechanism and the same budget, and B wrote and held the target with "
                "the consumer's read suppressed. The memory's contribution is the "
                "share difference, so it is the retrieved content that carries it"
            ),
            "against_the_mismatch_control": a_minus_mismatch,
            "against_the_identity_control": a_minus_identity,
            "both_hold_by_the_declared_margin": bool(
                separation(a_minus_mismatch, separation_margin)
                and separation(a_minus_identity, separation_margin)
            ),
        },
        "firing_control": {
            "declared": (
                "the same statistic on C's field episode with the consumer's policy "
                "mutated to ignore the retrieval and pursue the target "
                "unconditionally: the predicate A satisfies must fire here too, which "
                "is what shows the controls' zeroes are measured rather than vacuous"
            ),
            "mutated_arm": ARM_POLICY_MUTATED,
            "mutated_share_along_target": mutated["share_along_target"],
            "mutated_retrieved_deposit": mutated["retrieved_deposit"],
            "mutated_pursuits_the_target": bool(mutated["pursued_the_target"]),
            "the_predicate_fires_under_the_mutation": separation(
                mutated["share_along_target"], margin
            ),
            "the_unmutated_no_memory_arm_does_not_fire": bool(
                not separation(none["share_along_target"], margin)
            ),
            "mutated_share_against_the_unmutated_arm": gap(mutated, none),
        },
        "every_arm_actuated_something": {
            "declared": (
                "the act's own deposited energy per arm: a zero here would make the "
                "shares undefined rather than zero, so it is reported beside them"
            ),
            "act_increment_energy": {
                name: row["act_increment_energy"] for name, row in rows.items()
            },
            "all_arms_deposited_something": bool(
                all(float(row["act_increment_energy"]) > 0.0 for row in rows.values())
            ),
        },
    }


def reading_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """What the measured blocks say, in one reading."""

    comparisons = body["comparisons"]
    episodes = body["field_episodes"]
    clock = body["evidence_clock"]
    gains = body["neutral_gain"]
    target_episode = episodes["target"]
    mismatch_episode = episodes["mismatch"]
    blank_episode_block = episodes["blank"]
    verdicts = {
        "the_memory_arm_pursues_the_target": bool(
            comparisons["the_memory_arm_pursues_the_target"]
        ),
        "the_identity_control_does_not_pursue_the_target": bool(
            comparisons["the_identity_control_does_not_pursue_the_target"]
        ),
        "the_no_memory_arm_does_not_pursue_the_target": bool(
            comparisons["the_no_memory_arm_does_not_pursue_the_target"]
        ),
        "the_mismatch_control_does_not_pursue_the_target": bool(
            comparisons["the_mismatch_control_does_not_pursue_the_target"]
        ),
        "A_separates_from_both_controls_by_the_declared_margin": bool(
            comparisons["A_separates_from_both_controls_by_the_declared_margin"]
        ),
        "A_separates_from_D_by_the_declared_margin": bool(
            comparisons["A_separates_from_D_by_the_declared_margin"]
        ),
        "the_predicate_fires_under_the_policy_mutation": bool(
            comparisons["firing_control"]["the_predicate_fires_under_the_mutation"]
        ),
        "the_unmutated_no_memory_arm_does_not_fire": bool(
            comparisons["firing_control"]["the_unmutated_no_memory_arm_does_not_fire"]
        ),
        "every_arm_actuated_something": bool(
            comparisons["every_arm_actuated_something"]["all_arms_deposited_something"]
        ),
        "the_identity_control_field_carries_the_target_anyway": bool(
            float(
                body["arms"][1]["instrument_read_by_the_runner"]["recovered_deposit"]
            )
            > 0.0
        ),
        "the_held_read_recovers_the_written_deposit": bool(
            target_episode["read_on_the_held_page"][
                "the_written_directions_recovery_is_within_the_hold_allowance"
            ]
        ),
        "the_held_read_misses_an_unwritten_direction": bool(
            target_episode["read_on_the_held_page"][
                "the_unwritten_directions_recovery_misses_the_allowance"
            ]
        ),
        "the_owner_route_reproduces_the_declared_loop_on_the_written_page": bool(
            target_episode["owner_route_against_the_declared_loop"][
                "the_owner_route_reproduces_the_declared_loop"
            ]
        ),
        "the_batched_blank_advance_is_the_single_tick_advance": bool(
            blank_episode_block["owner_route_against_the_declared_loop"][
                "the_batched_advance_is_the_single_tick_advance"
            ]
        ),
        "the_reads_change_no_page_in_any_episode": bool(
            all(
                episode["read_invariants"]["the_reads_change_no_page"]
                for episode in (target_episode, mismatch_episode, blank_episode_block)
            )
        ),
        "the_reads_are_declared_temporal_predictions": bool(
            all(
                entry["readout_kind"] == "temporal-prediction"
                and not entry["evidence_added"]
                for episode in (target_episode, blank_episode_block)
                for entry in episode["read_on_the_held_page"]["by_item"].values()
            )
        ),
        "no_consumer_episode_moves_the_evidence_clock": bool(
            all(arm["invariants"]["the_consumer_moves_no_evidence_clock"] for arm in body["arms"])
        ),
        "no_field_episode_moves_the_evidence_clock": bool(
            all(
                episode["clocks"]["the_episode_moves_no_evidence_clock"]
                for episode in (target_episode, mismatch_episode, blank_episode_block)
            )
        ),
        "an_admission_moves_the_evidence_clock": bool(
            clock["an_admission_moves_the_evidence_clock"]
        ),
        "the_declared_candidates_are_orthogonal_in_the_read_frame": bool(
            body["captures"]["the_declared_candidates_are_orthogonal_in_the_read_frame"]
        ),
        "the_measured_gain_is_neutral_on_both_written_items_pages": bool(
            all(
                probe["the_measured_gain_is_neutral_on_this_items_page"]
                for probe in gains["neutrality_on_the_written_items_pages"].values()
            )
        ),
        "the_measured_gain_concords_with_the_family_receipt": bool(
            gains["refinement"]["cross_receipt_reference"][
                "the_refinement_reproduces_the_cited_gain"
            ]
        ),
        "the_declared_holds_run_at_even_horizon_parity": bool(
            all(
                episode["hold_horizon_parity"] == "even"
                for episode in (target_episode, mismatch_episode)
            )
        ),
    }
    prediction_reading = {
        "the_reads_declaration": (
            "read_packet_deposit is declared as the design declares a readout: a "
            "temporal prediction of the canonical page, labelled "
            f"{target_episode['read_on_the_held_page']['by_item'][target_episode['written_item']]['readout_kind']!r}, "
            "which adds no observed support and does not advance the evidence clock"
        ),
        "what_it_means_for_this_consumer": (
            "the consumer can legitimately act on it, and narrowly so: its act is an "
            "intervention -- one more owner write -- not an assertion about the "
            "world, so the prediction is a control input rather than support for a "
            "claim. A consumer whose act were a claim would instead have to admit "
            "the readout through the owner's observation rule, and that is a "
            "different operation"
        ),
        "does_this_demonstration_need_the_read_treated_as_evidence": False,
        "why_not": (
            "the consumer's decision uses the retrieved deposit as a number and "
            "admits nothing: the receipt's own figures show the owner's evidence "
            "clock unchanged across every field episode and every consumer episode "
            f"({verdicts['no_consumer_episode_moves_the_evidence_clock']}), while the "
            "same published key moves by one on an admission "
            f"({verdicts['an_admission_moves_the_evidence_clock']}), so the "
            "invariance is a live comparison and not a quantity that cannot move"
        ),
        "what_the_alternative_declaration_would_move": {
            "declared": (
                "if the read were declared as evidence instead, the same readout would "
                "enter the evidence store through the owner's observation-admission "
                "rule (one operation identity, one declared source), the evidence "
                "clock -- the state's logical tick the arms read -- and with it the "
                "checkpoint generation would move, and the recovered deposit would "
                "become an admitted observation about the world instead of a "
                "prediction of the page"
            ),
            "measured_evidence_clock_before_the_admission": clock[
                "evidence_tick_before_the_admission"
            ],
            "measured_evidence_clock_after_the_admission": clock[
                "evidence_tick_after_the_admission"
            ],
            "control_deliberately_outside_the_consumer_path": True,
        },
        "the_choice_left_open": (
            "this receipt does not take that reading and leaves the choice open; what "
            "it measures is that the consumer's behaviour does not depend on it"
        ),
    }
    honest_negatives = []
    if not verdicts["the_identity_control_does_not_pursue_the_target"]:
        honest_negatives.append(
            "the identity control pursued the target: its suppression did not take"
        )
    if not verdicts["the_mismatch_control_does_not_pursue_the_target"]:
        honest_negatives.append(
            "the mismatch control pursued the target: the retrieval of the target on "
            "a page holding a different item reached the floor"
        )
    if not verdicts["A_separates_from_both_controls_by_the_declared_margin"]:
        honest_negatives.append(
            "the consumer's behaviour does not separate: A's target share does not "
            "exceed the greater control's by the declared margin"
        )
    if not verdicts["the_owner_route_reproduces_the_declared_loop_on_the_written_page"]:
        honest_negatives.append(
            "the owner-route hold does not reproduce the declared loop's page on this "
            "page: the held-page figure is this route's own measurement"
        )
    if not verdicts["the_declared_holds_run_at_even_horizon_parity"]:
        honest_negatives.append(
            "the declared holds do not run at even horizon parity, so the held frame "
            "is sign-reversed at the horizon and the written direction's recovery "
            "figure carries that phase; the receipt reports the signed ratio beside it"
        )
    if not verdicts["the_measured_gain_is_neutral_on_both_written_items_pages"]:
        honest_negatives.append(
            "the measured neutral gain is not neutral on every page this receipt "
            "holds: at least one written item's own page retains below its written "
            "level at that gain, which the receipt's neutrality probes report per item"
        )
    if not verdicts["the_measured_gain_concords_with_the_family_receipt"]:
        honest_negatives.append(
            "this refinement's measured neutral gain does not concord with the "
            "figure the owner-write-path receipt carries for this profile; the "
            "receipt reports both figures and the refinement's own tolerance"
        )
    if not verdicts["the_held_read_recovers_the_written_deposit"]:
        honest_negatives.append(
            "the held read does not recover the written deposit within the declared "
            "post-hold allowance: the receipt reports both figures and the allowance"
        )
    return {
        "predicate": (
            "the target's share of the consumer's act increment reaches the declared "
            "pursuit margin, and A beats every control by the declared separation "
            "margin"
        ),
        "verdicts": verdicts,
        "prediction_reading": prediction_reading,
        "honest_negatives": honest_negatives,
        "limitations": [
            "the task is one declared deterministic policy over one declared set of "
            "candidate directions on one declared profile; nothing here measures a "
            "distribution over profiles, items, budgets or policies",
            "the consumer's act is the owner's write path, which is the only write "
            "actuator on the public surface; an actuator with a different physical "
            "law would be a different task",
            "the hold horizon is short by declaration, so this receipt makes no claim "
            "about holding over a long horizon; the owner-write-path receipt measures "
            "that at 512 ticks",
            "the statistic is a share along a declared direction, so it measures which "
            "direction the consumer actuated, not whether acting on a memory is "
            "useful in any wider sense",
        ],
    }


def assert_finite(value: Any, path: str = "receipt") -> None:
    """Refuse to publish a body carrying a non-finite number."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            assert_finite(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for position, item in enumerate(value):
            assert_finite(item, f"{path}[{position}]")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number at {path}: {value!r}")


def build_receipt(config: MemoryConsumerConfig | None = None) -> dict[str, Any]:
    """The complete receipt, digested by the lattice runner's own convention."""

    settings = config or MemoryConsumerConfig()
    started = time.perf_counter()
    body = measure(settings)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "question": (
            "the field's memory can be written, held and read back exactly; does "
            "reading it change what a consumer does, and is that change attributable "
            "to the retrieved content rather than to the write's side effects on the "
            "field?"
        ),
        "declared": {
            "config": settings.as_dict(),
            "arms": {
                ARM_MEMORY_USED: (
                    "the target item is written through the owner write path, held by "
                    "the declared closed loop at this profile's own measured neutral "
                    "gain, and read back through the owner's read operation; the "
                    "retrieval reaches the floor and the consumer pursues the target"
                ),
                ARM_IDENTITY_CONTROL: (
                    "the same write and the same hold, with the consumer's read "
                    "suppressed -- the declared zero, no read call -- while the "
                    "runner's own instrument read records the deposit the field was "
                    "carrying; the consumer pursues the fallback"
                ),
                ARM_NO_MEMORY: (
                    "nothing is written; the declared horizon is advanced on a blank "
                    "page with no drive; the consumer pursues the fallback"
                ),
                ARM_MISMATCH: (
                    "a different declared item is written and held than the one the "
                    "consumer asks for, by the same mechanism at the same budget; the "
                    "retrieval of the target misses the floor and the consumer pursues "
                    "the fallback. This is the firing control against the claim that "
                    "the write alone produces the behaviour"
                ),
                ARM_POLICY_MUTATED: (
                    "not an arm: C's field episode with the consumer's policy mutated "
                    "to ignore the retrieval, the can-fail control for the statistic"
                ),
            },
            "statistic": (
                "the share of the act's read-frame increment lying along the target: "
                "dot(dframe, u_target)**2 over dot(dframe, dframe), with dframe the "
                "durability harness's read frame before and after the consumer's act "
                "on the owner's canonical page and u_target that harness's captured "
                "unit direction for the target item. The act's budget is one declared "
                "value in every arm, so the statistic separates direction, not effort"
            ),
            "margins": {
                "pursuit_margin": float(settings.pursuit_margin),
                "separation_margin": float(settings.separation_margin),
                "read_floor_fraction": float(settings.read_floor_fraction),
            },
            "profile": {
                "name": PROFILE_NAME,
                "source": PROFILE_SOURCE,
                "declared": (
                    "the metric harness's flat-inertia member, imported read-only "
                    "through that harness's own builder; the neutral gain is measured "
                    "afresh in this receipt by the feedback harness's own refinement, "
                    "and its neutrality on each page this receipt holds is measured "
                    "on that page"
                ),
            },
            "declared_instruments": {
                "read_frame_and_captures": (
                    "run_fractal_durability_exploration.read_frame, capture_items, "
                    "overlap_matrix, page_sha256, squared_norm"
                ),
                "loop_law_and_gain": (
                    "run_fractal_feedback_exploration.phase_signal, loop_amplitude, "
                    "apply_drive, advance_workspace, measure_neutral_gain, "
                    "phase_readout_block, quadrature_direction"
                ),
                "profile_builder": PROFILE_SOURCE,
                "owner_write_path": "FieldIntelligenceOwner.write_packet_impulse",
                "owner_read_operation": (
                    f"FieldIntelligenceOwner.{READ_OPERATION_NAME} -> "
                    "FieldAtlas.read_packet_deposit -> packet_read_direction"
                ),
                "evidence_clock_control": (
                    "FieldAtlas.admit_observation on a separate state of this profile "
                    "carrying one declared variable and one declared chart"
                ),
                "digest_convention": (
                    "run_fractal_geometry_exploration.content_digest, declared in "
                    "run_fractal_lattice_exploration.py at its receipt assembly"
                ),
            },
            "content_digest_definition": (
                "sha256 of the canonical JSON (sorted keys, no insignificant "
                "whitespace, allow_nan=False) of the measured body with the declared "
                "wall-clock keys stripped, before the digest itself is attached"
            ),
            "content_digest_strip_keys": list(STRIP_KEYS),
            "content_digest_strip_keys_source": (
                "run_fractal_geometry_exploration.TIMING_KEYS, the strip set the "
                "lattice runner's convention declares; the measured body carries no "
                "inner wall-clock field, so the set removes only the top-level "
                "runtime_seconds here"
            ),
        },
        **body,
    }
    receipt["reading"] = reading_block(body)
    receipt["runtime_seconds"] = time.perf_counter() - started
    assert_finite(receipt)
    receipt["receipt_digest"] = receipt_digest(receipt)
    return receipt


def report(receipt: Mapping[str, Any]) -> str:
    """The receipt's own figures, as one line per declared arm."""

    comparisons = receipt["comparisons"]
    lines = [
        f"profile: {receipt['declared']['profile']['name']}",
        f"pursuit margin: {comparisons['pursuit_margin']}  "
        f"separation margin: {comparisons['separation_margin']}",
        f"{'arm':<36}{'retrieved':>14}{'floor':>12}{'pursued':>18}{'share_target':>14}",
    ]
    for row in comparisons["arm_table"]:
        share = row["share_along_target"]
        lines.append(
            f"{row['arm']:<36}{row['retrieved_deposit']:>14.10g}"
            f"{row['read_floor']:>12.6g}{row['selected_item']:>18}"
            f"{'None' if share is None else format(share, '.6f'):>14}"
        )
    lines.append(
        f"A - greater control: {comparisons['A_minus_the_greater_control']}  "
        f"A - D: {comparisons['A_minus_D']}"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(RECEIPT_PATH),
        help="where the receipt is written",
    )
    arguments = parser.parse_args()
    receipt = build_receipt(MemoryConsumerConfig())
    path = Path(arguments.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(report(receipt))
    print(f"wrote {path}")
    print(f"receipt_digest: {receipt['receipt_digest']}")
    print(f"runtime_seconds: {receipt['runtime_seconds']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
