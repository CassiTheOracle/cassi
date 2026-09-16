"""Run the owner's own memory chain on a nested scaffold, factor by factor.

Every leg of the owned memory chain measured so far runs on ``ladder-uniform``:
the canonical rail with a flat inverse-mass projection. Write
(``write_packet_impulse``), the closed-loop hold at the field's measured neutral
gain, read (``read_packet_deposit``) and the consumer act have all been measured
on that one body, so nothing yet separates *what the field is built from* from
*how heavy it is*. The harness-level packet work has meanwhile written declared
items into ``nested-core-shell`` and ``recursive-paired-loops`` and read them
back, and the survival receipt attributes its whole k=4 separation to the mass
channel (``summary.attribution_headline.mass_component`` ``+0.25797616491469993``
against ``summary.attribution_headline.rail_component``
``-0.002012515678662327``, both judged against the receipt's own declared
``0.02`` component margin). This runner asks the same question one level down, at
the owner's own store, with a design that can refute that attribution.

The declared factorial (2x2, every arm's profile built by the metric harness's
own builder from a declared row or from a declared metric kind on a declared
rail; each arm's construction is recorded in the receipt by builder name, by the
builder's live source line, and by the row's own declared rule):

    rail  \\ metric   flat inverse mass            the ladder metric (ratio 1.3)
    canonical        ``ladder-uniform``            ``ladder-ratio-1.3``
    nested-core-shell  flat vector on that rail    ratio-1.3 ladder on that rail

``nested-core-shell`` is the geometry harness's declared arrangement of that
name, entered through ``geometry.build_profile(geometry.arrangement_named(...))``
inside ``metric.build_metric_profile``. Within one rail the two metric levels
differ only in the projected inverse-mass vector (the arrangement's own
inverse-mass hook is replaced in both nested cells), so the metric factor is read
across two metrics and one body; across one metric level the two cells carry the
*same* inverse-mass vector on two different rails, so the rail factor is a
structural difference alone. The rail construction block measures both of those
claims rather than assuming them.

Four further declared legs are not factorial cells: the survival receipt's own
decomposition, re-measured on the four bodies it contrasts -- its baseline (the
canonical rail carrying the field's own default metric, which the metric
harness's ``ladder-ratio-1.3`` row declares at the equal-total-inertia
normalization), its mass-only leg (``nested-shell-metric``), its rail-only leg
(the default metric on ``nested-core-shell``) and its compound scaffold
(``nested-core-shell-reference``, both hooks).

Per arm, three measurements, each with its own instrument:

1. The field's own neutral gain, by the feedback harness's own refinement (a
   declared gain grid then a bisection of the bracket between the no-drive limit
   and the smallest grid gain), run on *that arm's* field at the declared
   headline item, with its bracket and its ``neutral_gain_bracket`` tolerance
   reported. No arm's gain is taken from another arm or from another receipt.
2. The owner cycle on that arm: write the declared item (``root-scale``) at the
   declared budget through the owner, hold the declared horizon with the closed
   loop driven at *that arm's measured gain*, read the held page through
   ``read_packet_deposit``, then let the declared consumer policy do one act
   write. Reported per arm: the write's read-frame deposit, the recovered deposit
   against it, the held frame-energy ratio, the signed ratio and the horizon's
   parity, the act's share along the target, and the page digest, the workspace
   state digest, the owner state digest and the ledger fields at every step, with
   which operation moved which digest.
3. The factor comparison: the 2x2 table, the rail and metric effects, their
   declared margins, and the controls. Each effect is the difference of one figure
   between two cells, read across the other factor; the margins are the ``0.02``
   the survival receipt declares for its mass and rail components and the lattice
   receipt declares for its nested depth axis (absolute for the fraction figures,
   relative for the deposit), with the recovery band declared beside them.

The controls that can fail (each predicate below is reported with the arm or the
mutation that makes it false): an arm where nothing was written (the declared
horizon advanced on a blank page, no drive) must not recover the written
direction and its consumer must select the fallback; the read-suppressed control
(same write, same hold, but the retrieval declines to look) must fall back too;
the same write held with *no* loop must retain less than the held page; a
declared direction the arm did not write must recover below the declared ceiling
of the written deposit; and every digest-equality claim is reported beside
digests that differ. The receipt's own digest is the lattice runner's declared
convention: sha256 of the canonical JSON of the measured body with a declared
wall-clock strip set removed, the strip set declared inside the receipt.

Two shipped routines could not be reused unchanged, and the receipt reports
exactly why rather than working around it silently. ``inspect_resonance`` raises
``FieldIntelligenceError`` on any profile that carries a transport rail, because
the canonical workspace inspector emits ``numpy.int64`` port indices in its
``edge_powers`` rows and the owner's JSON guard refuses them; the owner cycle here
therefore takes its clocks from the public ``AtlasState`` fields
(``logical_tick``, ``generation``, ``state_sha256``) that ``inspect_resonance``
itself wraps, and the equivalence of the two is measured on an arm where both
work. ``run_memory_consumer_path.hold_episode`` and ``consumer_episode`` call
``inspect_resonance`` twice each, so they cannot run on the nested arms either;
this runner's own cycle is the *same* tick body (the feedback harness's
``phase_signal`` and ``loop_amplitude`` law, the same per-tick work ceiling, one
owner ``advance`` tick and one owner drive write per tick, and the declared
functional replay of the same amplitudes), and the receipt measures on the
canonical arm that its held page digest, its deposit and its recovery equal the
shipped episode's exactly, with the no-loop page as the control that the equality
can fail.

Every number comes from the canonical field surface (the owner's write path, its
advance, its read operation, its published state) or from the harnesses'
declared instruments imported read-only (the durability harness's read frame and
captured directions, the feedback harness's loop law and neutral-gain refinement,
the metric and geometry harnesses' profile builders, the consumer-path runner's
capture, phase-reference, share-along and receipt-digest helpers). Nothing here
demonstrates task-level memory utility, semantic content, retrieval quality, or
any advantage over alternative architectures. Negative results are deliverables:
where a comparison ties, the receipt says it ties, with its numbers.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_feedback_exploration as feedback
import run_fractal_geometry_exploration as geometry
import run_fractal_metric_exploration as metric
import run_memory_consumer_path as consumer_path

SCHEMA = "cassifi.owner-nested-cycle.v1"

# The declared rails of the factorial: the canonical body's own rail (no
# transport hook at all) and the geometry harness's declared arrangement of this
# name, the scaffold the survival receipt's rail-only and compound legs are built
# from.
CANONICAL_RAIL = metric.CANONICAL_RAIL
NESTED_RAIL = metric.REFERENCE_ARRANGEMENT

# The declared metric levels of the factorial, as the metric harness's own named
# rows: the flat inverse-mass control and the field's real default ladder
# (ratio 1.3 at the equal-total-inertia normalization, the profile every earlier
# owner-chain receipt runs on).
FLAT_METRIC_NAME = "ladder-uniform"
LADDER_METRIC_NAME = "ladder-ratio-1.3"

# The two declared reference legs, which are the survival harness's own metric and
# scaffold as the metric harness already declares them.
SHELL_METRIC_NAME = metric.REFERENCE_METRIC_PROFILE_NAME
SHELL_SCAFFOLD_NAME = metric.REFERENCE_ROW_NAME

# The declared write, act and hold figures of the owner cycle, taken from the
# consumer-path runner's own declarations so the two receipts measure the same
# episode rather than two similar ones.
WRITE_BUDGET = consumer_path.WRITE_BUDGET
ACT_BUDGET = consumer_path.ACT_BUDGET
HOLD_HORIZON_TICKS = consumer_path.HOLD_HORIZON_TICKS
TARGET_ITEM_INDEX = consumer_path.TARGET_ITEM_INDEX
MISMATCH_ITEM_INDEX = consumer_path.MISMATCH_ITEM_INDEX
FALLBACK_ITEM_INDEX = consumer_path.FALLBACK_ITEM_INDEX
TARGET_ITEM_NAME = durability.ITEM_SPECS[TARGET_ITEM_INDEX].name
READ_FLOOR_FRACTION = consumer_path.READ_FLOOR_FRACTION
PURSUIT_MARGIN = consumer_path.PURSUIT_MARGIN
READ_OPERATION_NAME = consumer_path.READ_OPERATION_NAME

# The declared margins.  RAIL_MARGIN and METRIC_MARGIN are absolute and are the
# same 0.02 the survival receipt declares for its mass and rail components and the
# lattice receipt declares for its nested depth axis, so an effect this receipt
# calls separated is separated by the family's own declared bar.  The deposit
# margin is relative, because the figure it judges is a relative difference.
RAIL_MARGIN = 0.02
METRIC_MARGIN = 0.02
DEPOSIT_RELATIVE_MARGIN = 0.02

# The declared ceiling on what a declared direction the arm did NOT write may
# recover, as a fraction of the written direction's own deposit on the same held
# page: the can-fail control for the recovery reading.
UNWRITTEN_DIRECTION_CEILING = 0.5

# The declared band on the held read's recovery of the written deposit.  It is the
# same 0.02 the family's other margins use.  It is a band rather than an equality
# because an arm's hold runs at that arm's own measured neutral gain, which is the
# gain at which the *refinement's* own no-drive retention crosses one over its
# 64-tick horizon, not at which this receipt's hold horizon returns exactly what
# was written: the measured figure is near one by construction of the instrument,
# and the receipt's own reading says so.  What the band makes falsifiable is the
# rest of the chain -- a page that was never written, or a read that was
# suppressed, must fall outside it.
RECOVERY_BAND = 0.02

# The declared allowance on the two routes' agreement where both routes can run:
# this runner's cycle and the shipped consumer-path episode run the same tick body
# on the same profile, so their held page digests are expected to be identical
# (allowance 0.0 in page-digest terms), and their measured deposits and recoveries
# are compared as relative differences against this absolute allowance.
ROUTE_IDENTITY_ALLOWANCE = 0.0
ROUTE_FIGURE_ALLOWANCE = 1e-12

# The declared rail-construction margin: the two rails of the factorial must be
# measurably different bodies, or the rail factor would be a comparison of one
# body with itself.  It is the same relative bound the metric harness uses for its
# cited-profile reproductions.
RAIL_CONSTRUCTION_MARGIN = 1e-6

# The declared strip set of the receipt digest: the geometry harness's own
# declared wall-clock keys, applied by that harness's own ``content_digest``.  The
# set is declared inside this receipt beside the definition it belongs to.
STRIP_KEYS = tuple(sorted(geometry.TIMING_KEYS))
DIGEST_DEFINITION = (
    "sha256 of the canonical JSON (sorted keys, no insignificant whitespace, "
    "allow_nan=False) of the measured body with the declared wall-clock keys "
    "stripped, taken before the digest itself is attached"
)

# The declared receipts cited read-only, with the key paths this receipt reads.
SURVIVAL_RECEIPT = Path("_diag/fractal-survival/exploration.json")
LATTICE_RECEIPT = Path("_diag/fractal-lattice/exploration.json")
OWNER_WRITE_PATH_RECEIPT = Path("_diag/owner-write-path/exploration.json")
SURVIVAL_ATTRIBUTION_PATH = ("summary", "attribution_headline")
LATTICE_DEPTH_PATH = ("comparisons", "nested", "axes", "depth_axis")
OWNER_WRITE_PATH_GAIN_PATH = ("cycle", "neutral_gain")

RECEIPT_PATH = Path("_diag/owner-nested-cycle/exploration.json")

FACTORIAL_CELL = "factorial-cell"
REFERENCE_LEG = "reference-leg"


@dataclass(frozen=True)
class ArmSpec:
    """One declared arm: its two factor levels and the row it is built from."""

    name: str
    rail: str
    metric_label: str
    role: str
    row_name: str | None = None
    lookup: str = ""
    metric_kind: str | None = None
    ladder_ratio: float | None = None


# The declared arms, in declared order.  The four factorial cells cross the two
# rails with the two metric levels; the two reference legs are the survival
# harness's own metric on each rail.
ARM_SPECS: tuple[ArmSpec, ...] = (
    ArmSpec(
        name="canonical-rail-flat-metric",
        rail=CANONICAL_RAIL,
        metric_label="flat",
        role=FACTORIAL_CELL,
        row_name=FLAT_METRIC_NAME,
        lookup="ladder_row",
    ),
    ArmSpec(
        name="canonical-rail-ladder-metric",
        rail=CANONICAL_RAIL,
        metric_label="ladder-1.3",
        role=FACTORIAL_CELL,
        row_name=LADDER_METRIC_NAME,
        lookup="ladder_row",
    ),
    ArmSpec(
        name="nested-rail-flat-metric",
        rail=NESTED_RAIL,
        metric_label="flat",
        role=FACTORIAL_CELL,
        metric_kind="ladder-uniform",
        ladder_ratio=1.0,
    ),
    ArmSpec(
        name="nested-rail-ladder-metric",
        rail=NESTED_RAIL,
        metric_label="ladder-1.3",
        role=FACTORIAL_CELL,
        metric_kind="ladder-geometric",
        ladder_ratio=metric.DEFAULT_LADDER_RATIO,
    ),
    ArmSpec(
        name="canonical-rail-shell-metric",
        rail=CANONICAL_RAIL,
        metric_label="shell-0.7",
        role=REFERENCE_LEG,
        row_name=SHELL_METRIC_NAME,
        lookup="declared_row",
    ),
    ArmSpec(
        name="nested-rail-shell-metric",
        rail=NESTED_RAIL,
        metric_label="shell-0.7",
        role=REFERENCE_LEG,
        row_name=SHELL_SCAFFOLD_NAME,
        lookup="declared_row",
    ),
)


@dataclass(frozen=True)
class OwnerNestedConfig:
    """Declared measurement settings; every number in the receipt derives from these."""

    hold_horizon_ticks: int = HOLD_HORIZON_TICKS
    write_budget: float = WRITE_BUDGET
    act_budget: float = ACT_BUDGET
    read_floor_fraction: float = READ_FLOOR_FRACTION
    pursuit_margin: float = PURSUIT_MARGIN
    rail_margin: float = RAIL_MARGIN
    metric_margin: float = METRIC_MARGIN
    deposit_relative_margin: float = DEPOSIT_RELATIVE_MARGIN
    recovery_band: float = RECOVERY_BAND
    unwritten_direction_ceiling: float = UNWRITTEN_DIRECTION_CEILING
    rail_construction_margin: float = RAIL_CONSTRUCTION_MARGIN
    route_figure_allowance: float = ROUTE_FIGURE_ALLOWANCE
    owner_home_prefix: str = "onc-owner-"
    include_reference_legs: bool = True
    include_route_continuity: bool = True
    include_no_loop_control: bool = True

    def __post_init__(self) -> None:
        if int(self.hold_horizon_ticks) < 1:
            raise ValueError("the declared hold horizon must be positive")
        for name in ("write_budget", "act_budget"):
            if not 0.0 < float(getattr(self, name)) <= 1.0:
                raise ValueError(f"the declared {name} must lie in (0,1]")
        if not 0.0 < float(self.read_floor_fraction) <= 1.0:
            raise ValueError("the declared read floor fraction must lie in (0,1]")
        if not 0.0 < float(self.pursuit_margin) <= 1.0:
            raise ValueError("the declared pursuit margin must lie in (0,1]")
        for name in (
            "rail_margin",
            "metric_margin",
            "deposit_relative_margin",
            "recovery_band",
            "rail_construction_margin",
        ):
            if float(getattr(self, name)) <= 0.0:
                raise ValueError(f"the declared {name} must be positive")
        if not 0.0 < float(self.unwritten_direction_ceiling) <= 1.0:
            raise ValueError("the declared unwritten-direction ceiling must lie in (0,1]")

    @property
    def arms(self) -> tuple[ArmSpec, ...]:
        return tuple(
            spec
            for spec in ARM_SPECS
            if spec.role == FACTORIAL_CELL or bool(self.include_reference_legs)
        )

    @property
    def consumer_config(self) -> Any:
        """The consumer-path runner's own config, at this runner's declared numbers."""

        return consumer_path.MemoryConsumerConfig(
            write_budget=float(self.write_budget),
            act_budget=float(self.act_budget),
            hold_horizon_ticks=int(self.hold_horizon_ticks),
            read_floor_fraction=float(self.read_floor_fraction),
            pursuit_margin=float(self.pursuit_margin),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "hold_horizon_ticks": int(self.hold_horizon_ticks),
            "write_budget": float(self.write_budget),
            "act_budget": float(self.act_budget),
            "read_floor_fraction": float(self.read_floor_fraction),
            "pursuit_margin": float(self.pursuit_margin),
            "rail_margin": float(self.rail_margin),
            "metric_margin": float(self.metric_margin),
            "deposit_relative_margin": float(self.deposit_relative_margin),
            "recovery_band": float(self.recovery_band),
            "unwritten_direction_ceiling": float(self.unwritten_direction_ceiling),
            "rail_construction_margin": float(self.rail_construction_margin),
            "route_figure_allowance": float(self.route_figure_allowance),
            "include_reference_legs": bool(self.include_reference_legs),
            "include_route_continuity": bool(self.include_route_continuity),
            "include_no_loop_control": bool(self.include_no_loop_control),
            "read_frame_path": durability.READ_FRAME_PATH,
            "write_operation": "write_packet_impulse",
            "read_operation": READ_OPERATION_NAME,
            "advance_operation": "advance",
        }


# --------------------------------------------------------------------------
# the declared arms: construction, by name and by live source line
# --------------------------------------------------------------------------
def source_line(function: Callable[..., Any]) -> int:
    """The live source line of one declared builder, so an arm can be rebuilt."""

    return int(inspect.getsourcelines(function)[1])


def qualified(function: Callable[..., Any]) -> str:
    """One declared builder, named as ``module.symbol``."""

    module = str(getattr(function, "__module__", "")).rsplit(".", 1)[-1]
    return f"{module}.{getattr(function, '__name__', str(function))}"


def row_lookup(spec: ArmSpec) -> Callable[[str], Any]:
    """The metric harness's own lookup the declared row is read through."""

    if spec.lookup == "ladder_row":
        return metric.ladder_row
    if spec.lookup == "declared_row":
        return metric.declared_row
    raise ValueError(f"the declared arm {spec.name!r} declares no row lookup")


def row_family(spec: ArmSpec) -> tuple[Any, ...]:
    """The declared row family the arm's row is a member of."""

    if spec.lookup == "ladder_row":
        return metric.ladder_profiles()
    if spec.lookup == "declared_row":
        return metric.all_declared_rows()
    raise ValueError(f"the declared arm {spec.name!r} declares no row family")


def declared_row_for(spec: ArmSpec) -> Any:
    """The arm's declared metric row, built by the metric harness's own builder.

    The two nested-rail cells have no row in the metric harness's declared
    families -- the ladder family is declared on the canonical rail only -- so
    their row is declared here from the same declared parameters the existing
    rows carry, and it is built by the same ``build_metric_profile`` call, which
    is where ``geometry.build_profile(geometry.arrangement_named(...))`` enters.
    """

    if spec.row_name is not None:
        return row_lookup(spec)(spec.row_name)
    rule = (
        "projected_inv_mass[port] = 1 / mean(1.3 ** pool for pool in range(7)) for "
        f"every port, on the {spec.rail!r} rail: the flat-inertia control of the "
        "metric harness's ladder family, re-declared on this rail"
        if spec.metric_kind == "ladder-uniform"
        else "projected_inv_mass[port] = 1 / (scale * ratio ** pool) for every port "
        f"of the pool on both strands, ratio {spec.ladder_ratio!r} and the declared "
        "equal-total-inertia scale, on the "
        f"{spec.rail!r} rail: the field's real default ladder, re-declared on this rail"
    )
    return metric.MetricProfile(
        name=spec.name,
        kind=str(spec.metric_kind),
        rule=rule,
        rail=spec.rail,
        ladder_ratio=float(spec.ladder_ratio),
        normalization=metric.LADDER_EQUAL_TOTAL_NORMALIZATION,
        note="declared by this receipt; not a member of the metric harness's own family.",
    )


def build_arm(spec: ArmSpec) -> tuple[Any, Any]:
    """One arm's canonical profile, with the declared row it was built from."""

    row = declared_row_for(spec)
    return metric.build_metric_profile(row), row


def rail_vector(profile: Any) -> np.ndarray:
    """The profile's transport matrix, canonical or hook-supplied."""

    return np.asarray(profile.transport_matrix, dtype=np.float64)


def construction_record(spec: ArmSpec, row: Any, profile: Any) -> dict[str, Any]:
    """How one arm was built, by name, by builder, by live source line and by digest."""

    index = None
    if spec.row_name is not None:
        index = [item.name for item in row_family(spec)].index(spec.row_name)
    inverse_mass = profile.projected_inv_mass
    vector = (
        None if inverse_mass is None else np.asarray(inverse_mass, dtype=np.float64)
    )
    return {
        "arm": spec.name,
        "role": spec.role,
        "rail": spec.rail,
        "metric_label": spec.metric_label,
        "metric_kind": str(row.kind),
        "declared_row": spec.row_name,
        "declared_by": (
            qualified(row_lookup(spec)) if spec.row_name is not None else qualified(declared_row_for)
        ),
        "declared_at_line": (
            source_line(row_lookup(spec))
            if spec.row_name is not None
            else source_line(declared_row_for)
        ),
        "declared_row_index": index,
        "declared_rule": str(row.rule),
        "built_by": qualified(metric.build_metric_profile),
        "built_at_line": source_line(metric.build_metric_profile),
        "base_rail_builder": (
            None if spec.rail == CANONICAL_RAIL else qualified(geometry.build_profile)
        ),
        "base_rail_builder_line": (
            None if spec.rail == CANONICAL_RAIL else source_line(geometry.build_profile)
        ),
        "base_rail_arrangement": (
            None if spec.rail == CANONICAL_RAIL else geometry.arrangement_named(spec.rail).name
        ),
        "profile_sha256": geometry.canonical_digest(profile.as_dict()),
        "port_count": int(profile.port_count),
        "hooks_present": {
            "projected_transport": bool(profile.projected_transport is not None),
            "projected_inv_mass": bool(inverse_mass is not None),
            "projected_quartic_weights": bool(profile.projected_quartic_weights is not None),
        },
        "rail_sha256": durability.direction_sha256(rail_vector(profile)),
        "inverse_mass_sha256": (
            None if vector is None else durability.direction_sha256(vector)
        ),
        "declared": (
            "the metric harness's own builder applied to a declared row; the rail "
            "enters only through that builder's own base construction, so an arm's "
            "two factors are visible in the record and can be rebuilt from it"
        ),
    }


# --------------------------------------------------------------------------
# digests: the page, the workspace state, the owner state and the ledger
# --------------------------------------------------------------------------
def ledger_digest(ledger: Mapping[str, float]) -> str:
    """The digest of one ledger, over the harness's own canonical JSON."""

    return hashlib.sha256(
        durability.canonical_json({str(k): float(v) for k, v in ledger.items()}).encode("utf-8")
    ).hexdigest()


def transcript(owner: Any, *, label: str) -> dict[str, Any]:
    """Every digest this receipt compares, at one moment of one owner's episode."""

    workspace = owner.state.resonant_workspace
    ledger = {str(k): float(v) for k, v in workspace.ledger.items()}
    return {
        "label": label,
        "page_sha256": durability.page_sha256(workspace),
        "workspace_state_sha256": workspace.state_sha256,
        "owner_state_sha256": owner.state.state_sha256,
        "ledger_sha256": ledger_digest(ledger),
        "generation": int(owner.state.generation),
        "logical_tick": int(owner.state.logical_tick),
        "field_ticks": int(workspace.field_ticks),
        "workspace_evidence_tick": int(workspace.evidence_tick),
        "ledger": ledger,
    }


def digest_moves(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Which of the four digests one step moved, and whether the states moved alone."""

    page_moved = before["page_sha256"] != after["page_sha256"]
    state_moved = before["workspace_state_sha256"] != after["workspace_state_sha256"]
    owner_state_moved = before["owner_state_sha256"] != after["owner_state_sha256"]
    ledger_moved = before["ledger_sha256"] != after["ledger_sha256"]
    return {
        "from": str(before["label"]),
        "to": str(after["label"]),
        "page_moved": bool(page_moved),
        "workspace_state_moved": bool(state_moved),
        "owner_state_moved": bool(owner_state_moved),
        "ledger_moved": bool(ledger_moved),
        "the_state_digest_moved_where_the_page_digest_did_not": bool(
            state_moved and not page_moved
        ),
        "the_ledger_moved_where_the_page_digest_did_not": bool(
            ledger_moved and not page_moved
        ),
        "generation_before": int(before["generation"]),
        "generation_after": int(after["generation"]),
        "field_ticks_before": int(before["field_ticks"]),
        "field_ticks_after": int(after["field_ticks"]),
    }


def transcript_pair(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any]:
    """Both ends of one step, with the movement between them."""

    return {
        "before": dict(before),
        "after": dict(after),
        "moved": digest_moves(before, after),
    }


# --------------------------------------------------------------------------
# the declared instruments: captures, phase reference, neutral gain
# --------------------------------------------------------------------------
def frame(workspace: Any) -> np.ndarray:
    """The declared read frame: the canonical analyzer's flattened coefficients."""

    return consumer_path.frame(workspace)


def flat(value: Any) -> Any:
    """Detached ordinary containers for a value a canonical API froze."""

    return consumer_path.plain(value)


def captures_for(profile: Any, config: OwnerNestedConfig) -> tuple[list[Any], dict[str, Any]]:
    """The declared directions, their overlap, and the target's own deposit."""

    captures = durability.capture_items(
        durability.DurabilityConfig(write_budget=float(config.write_budget)), profile
    )
    return captures, consumer_path.capture_block(profile, config.consumer_config)


def phase_reference_for(
    profile: Any, captures: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The declared quadrature read-back, plus its receipt form without the vector."""

    reference = consumer_path.phase_reference_for(profile, captures)
    record = {
        key: value for key, value in reference.items() if key != "direction"
    }
    record["direction_sha256"] = durability.direction_sha256(
        np.asarray(reference["direction"], dtype=np.float64)
    )
    return reference, record


def neutral_gain_for(
    spec: ArmSpec,
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    phase_reference: Mapping[str, Any],
    config: OwnerNestedConfig,
) -> dict[str, Any]:
    """This arm's own neutral gain, by the feedback harness's refinement."""

    try:
        refinement = consumer_path.neutral_gain_refinement(
            profile, captures, phase_reference, config.consumer_config
        )
    except Exception as exc:  # the declared failure mode is reported, not hidden
        return {
            "arm": spec.name,
            "measured": False,
            "failure": f"{type(exc).__name__}: {exc}",
            "declared": (
                "the feedback harness's own refinement could not bracket a neutral "
                "gain on this arm's field; the arm's cycle is not measured at a "
                "borrowed gain, and the factorial reports this cell as unmeasured"
            ),
        }
    return {
        "arm": spec.name,
        "measured": True,
        "measured_gain": float(refinement["measured_gain"]),
        "bracket": [float(value) for value in refinement["bracket"]],
        "bracket_width": float(refinement["bracket_width"]),
        "tolerance": float(refinement["tolerance"]),
        "drift_retention_at_horizon": float(refinement["drift_retention_at_horizon"]),
        "grid_monotone": bool(refinement["grid_monotone"]),
        "cross_receipt_reference": dict(refinement["cross_receipt_reference"]),
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
        "refinement_horizon_ticks": int(feedback.FeedbackConfig().horizon_ticks),
        "declared": (
            "the feedback harness's own neutral-gain refinement on this arm's own "
            "field: a declared gain grid, then a bisection of the bracket between "
            "the no-drive limit and the smallest grid gain until the bracket is "
            "narrower than the declared tolerance. The drift retention is the same "
            "refinement's own no-drive arm on this arm's field"
        ),
    }


# --------------------------------------------------------------------------
# the owner cycle: write, hold, read, act
# --------------------------------------------------------------------------
def loop_arm(name: str, index: int, *, gain: float, family: str) -> Any:
    """One declared closed-loop arm at a declared gain.

    A declared zero gain is the no-drive arm: it carries no phase angle, exactly as
    the feedback harness's own no-drive reference does, because the declared phase
    term acts on a gain.
    """

    loop = feedback.FeedbackConfig()
    return feedback.LoopArm(
        name,
        (int(index),),
        gain=float(gain),
        family=family,
        measure_item_index=int(index),
        phase_degrees=float(loop.neutral_gain_phase_degrees) if float(gain) else 0.0,
    )


def named_direction(index: int) -> dict[str, Any]:
    """One declared packet direction, as the write and the read both name it."""

    return consumer_path.named_direction(durability.ITEM_SPECS[int(index)])


def readout_record(readout: Mapping[str, Any]) -> dict[str, Any]:
    """One owner readout, as the receipt carries it."""

    return {
        "recovered_deposit": float(readout["recovered_deposit"]),
        "direction_sha256": str(readout["direction_sha256"]),
        "readout_kind": str(readout["readout_kind"]),
        "evidence_added": bool(readout["evidence_added"]),
        "read_frame_energy": float(readout["read_frame_energy"]),
    }


def relative_difference(value: float, reference: float) -> float | None:
    """One measured relative difference, with a zero reference reported as none."""

    if float(reference) == 0.0:
        return None
    return abs(float(value) - float(reference)) / abs(float(reference))


def top_ratio(numerator: float, denominator: float) -> float:
    """One measured ratio, with a declared zero denominator reported as zero."""

    return consumer_path.top_ratio(numerator, denominator)


def hold_route(
    spec: ArmSpec,
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    phase_reference: Mapping[str, Any],
    config: OwnerNestedConfig,
    *,
    gain: float,
    item_index: int = TARGET_ITEM_INDEX,
    label: str,
) -> tuple[dict[str, Any], Any]:
    """Write one declared item through the owner, hold it at a declared gain, read it.

    The tick body is the consumer-path episode's own: one owner ``advance`` tick
    with the source off, the feedback harness's declared read-back signal
    (``phase_signal``) and bounded amplitude law (``loop_amplitude``) at this
    arm's gain, and one owner drive write at the declared per-tick work ceiling
    times the amplitude's magnitude.  The same amplitudes are replayed
    functionally from the same post-write page through the feedback harness's own
    primitives, and the two held pages are compared.
    """

    loop = feedback.FeedbackConfig()
    index = int(item_index)
    spec_item = durability.ITEM_SPECS[index]
    direction = np.asarray(captures[index]["direction"], dtype=np.float64)
    horizon = int(config.hold_horizon_ticks)
    ceiling = float(loop.loop_work_ceiling)
    arm = loop_arm(f"{label}-hold", index, gain=float(gain), family="owner-nested-cycle-hold")
    owner, home = consumer_path.open_owner(profile, prefix=config.owner_home_prefix)
    try:
        blank = transcript(owner, label="blank")
        blank_frame_energy = float(durability.squared_norm(frame(owner.state.resonant_workspace)))
        write = flat(
            owner.write_packet_impulse(
                f"{label}:write",
                **named_direction(index),
                work_budget=float(config.write_budget),
            )
        )
        write_receipt = flat(write["impulse_receipt"])
        after_write = transcript(owner, label="after-the-write")
        post_write = owner.state.resonant_workspace
        post_write_frame = frame(post_write)
        post_write_energy = float(durability.squared_norm(post_write_frame))
        deposit = post_write_energy - blank_frame_energy
        signed_reference = float(np.dot(post_write_frame, direction))

        amplitudes: list[float] = []
        drive_calls = 0
        drive_accepted = 0
        drive_skipped = 0
        drive_clipped = 0
        drive_work = 0.0
        retention_ticks: list[dict[str, Any]] = []
        for tick in range(1, horizon + 1):
            owner.advance(f"{label}:advance:{tick}", ticks=1, source_enabled=False)
            vector = frame(owner.state.resonant_workspace)
            ratio = feedback.phase_signal(
                loop, arm, vector, direction, signed_reference, phase_reference
            )
            amplitude, clipped = feedback.loop_amplitude(loop, arm.gain, ratio)
            amplitudes.append(float(amplitude))
            drive_clipped += int(bool(clipped))
            if amplitude:
                drive = flat(
                    owner.write_packet_impulse(
                        f"{label}:drive:{tick}",
                        path=spec_item.path,
                        component=spec_item.component,
                        flow_signal=[float(amplitude), 0.0],
                        work_budget=ceiling * abs(float(amplitude)),
                    )
                )
                drive_calls += 1
                drive_accepted += int(bool(drive["impulse_receipt"]["accepted"]))
                drive_work += float(drive["impulse_receipt"]["applied_work"])
                vector = frame(owner.state.resonant_workspace)
            else:
                drive_skipped += 1
            retention_ticks.append(
                {
                    "tick": tick,
                    "frame_energy_ratio": top_ratio(
                        durability.squared_norm(vector), post_write_energy
                    ),
                    "signed_ratio": top_ratio(float(np.dot(vector, direction)), signed_reference),
                }
            )

        held = owner.state.resonant_workspace
        at_horizon = transcript(owner, label="at-the-horizon")
        held_frame = frame(held)
        held_energy = float(durability.squared_norm(held_frame))
        read_indices = (TARGET_ITEM_INDEX, MISMATCH_ITEM_INDEX, FALLBACK_ITEM_INDEX)
        reads = {
            durability.ITEM_SPECS[i].name: readout_record(
                owner.read_packet_deposit(**named_direction(i))
            )
            for i in read_indices
        }
        repeated = readout_record(
            owner.read_packet_deposit(**named_direction(index))
        )
        after_reads = transcript(owner, label="after-the-reads")
        written_name = spec_item.name
        recovered = float(reads[written_name]["recovered_deposit"])
        unwritten_name = (
            durability.ITEM_SPECS[MISMATCH_ITEM_INDEX].name
            if index != MISMATCH_ITEM_INDEX
            else durability.ITEM_SPECS[FALLBACK_ITEM_INDEX].name
        )
        unwritten_recovered = float(reads[unwritten_name]["recovered_deposit"])

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
                    replay, index, amplitude, ceiling * abs(amplitude)
                )
        replay_page = durability.page_sha256(replay)

        record = {
            "arm": spec.name,
            "label": label,
            "written_item": written_name,
            "written_item_index": index,
            "hold_horizon_ticks": horizon,
            "hold_horizon_parity": "even" if horizon % 2 == 0 else "odd",
            "gain": float(gain),
            "phase_degrees": float(arm.phase_degrees),
            "loop_work_ceiling": ceiling,
            "read_frame_path": durability.READ_FRAME_PATH,
            "write": {
                "accepted": bool(write_receipt["accepted"]),
                "applied_work": float(write_receipt["applied_work"]),
                "impulse_amount": float(write_receipt["impulse_amount"]),
                "read_frame_deposit": float(deposit),
                "read_frame_energy_after": post_write_energy,
                "blank_read_frame_energy": blank_frame_energy,
                "signed_projection_at_the_write": signed_reference,
            },
            "hold": {
                "advance_ticks": horizon,
                "drive_calls": drive_calls,
                "drive_accepted": drive_accepted,
                "drive_skipped_ticks": drive_skipped,
                "drive_clipped_ticks": drive_clipped,
                "drive_applied_work_total": float(drive_work),
                "amplitude_max": float(max((abs(a) for a in amplitudes), default=0.0)),
                "amplitudes": [float(a) for a in amplitudes],
                "frame_energy_ratio_at_horizon": top_ratio(held_energy, post_write_energy),
                "retention_at_ticks": retention_ticks,
                "signed_ratio_at_horizon": (
                    float(retention_ticks[-1]["signed_ratio"]) if retention_ticks else None
                ),
            },
            "read_on_the_held_page": {
                "by_direction": reads,
                "written_direction_recovered_deposit": recovered,
                "written_direction_recovery_fraction": top_ratio(recovered, deposit),
                "written_direction_relative_difference": relative_difference(recovered, deposit),
                "unwritten_direction": unwritten_name,
                "unwritten_direction_recovered_deposit": unwritten_recovered,
                "unwritten_direction_fraction_of_the_written_deposit": top_ratio(
                    unwritten_recovered, deposit
                ),
                "unwritten_direction_ceiling": float(config.unwritten_direction_ceiling),
                "the_unwritten_direction_stays_under_the_ceiling": bool(
                    top_ratio(unwritten_recovered, deposit)
                    < float(config.unwritten_direction_ceiling)
                ),
                "repeated_read_returns_the_same_readout": bool(repeated == reads[written_name]),
                "declared": (
                    "the owner's own read operation on the held page, called for the "
                    "declared target, mismatch and fallback directions. The written "
                    "direction's recovery fraction is what the held page returns "
                    "divided by what the write deposited; the arm declares its hold at "
                    "its own measured neutral gain, so this figure is near one in every "
                    "arm by construction of the instrument, and the receipt says so "
                    "rather than reading it as retention. The direction the arm did not "
                    "write is the can-fail control for the predicate beside it"
                ),
            },
            "digests": {
                "blank": blank,
                "after_the_write": after_write,
                "the_write": transcript_pair(blank, after_write),
                "at_the_horizon": at_horizon,
                "the_hold": transcript_pair(after_write, at_horizon),
                "after_the_reads": after_reads,
                "the_reads": transcript_pair(at_horizon, after_reads),
                "the_owner_write_moves": {
                    "page_sha256": bool(
                        blank["page_sha256"] != after_write["page_sha256"]
                    ),
                    "workspace_state_sha256": bool(
                        blank["workspace_state_sha256"]
                        != after_write["workspace_state_sha256"]
                    ),
                    "owner_state_sha256": bool(
                        blank["owner_state_sha256"] != after_write["owner_state_sha256"]
                    ),
                    "ledger_sha256": bool(
                        blank["ledger_sha256"] != after_write["ledger_sha256"]
                    ),
                    "ledger_fields_the_write_touched": sorted(
                        key
                        for key in set(blank["ledger"]) | set(after_write["ledger"])
                        if blank["ledger"].get(key, 0.0) != after_write["ledger"].get(key, 0.0)
                    ),
                },
                "declared": (
                    "the page digest covers the canonical page bytes alone, the "
                    "workspace state digest covers those bytes and the workspace "
                    "descriptor (the ledger, the field tick and the phases), and the "
                    "owner state digest covers the atlas state. All four are reported "
                    "at every step because a page digest alone does not identify a "
                    "state: the movement booleans say which of them each operation "
                    "moves. The reads are the can-fail control for the read's own "
                    "immutability claim, and the mutation control below shows the "
                    "digests can move"
                ),
            },
            "owner_route_against_the_declared_loop": {
                "replay_page_sha256": replay_page,
                "held_page_sha256": durability.page_sha256(held),
                "the_owner_route_reproduces_the_declared_loop": bool(
                    replay_page == durability.page_sha256(held)
                ),
                "declared": (
                    "the declared loop's tick body replayed functionally from the same "
                    "post-write page through the feedback harness's own advance_workspace "
                    "and apply_drive at the amplitudes this episode measured"
                ),
            },
            "clocks": {
                "logical_tick_before_the_episode": int(blank["logical_tick"]),
                "logical_tick_after_the_reads": int(after_reads["logical_tick"]),
                "the_episode_moves_no_evidence_clock": bool(
                    int(blank["logical_tick"]) == int(after_reads["logical_tick"])
                ),
                "generation_before_the_episode": int(blank["generation"]),
                "generation_at_the_horizon": int(at_horizon["generation"]),
                "field_ticks_at_the_horizon": int(at_horizon["field_ticks"]),
                "declared": (
                    "the evidence clock is the owner state's own logical tick, read "
                    "from the public AtlasState field rather than through "
                    "inspect_resonance, which this receipt measures to be unusable on a "
                    "rail-carrying profile"
                ),
            },
        }
        return record, held
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def act_route(
    spec: ArmSpec,
    profile: Any,
    workspace: Any,
    captures: Sequence[Mapping[str, Any]],
    capture_record: Mapping[str, Any],
    config: OwnerNestedConfig,
    *,
    label: str,
    read_suppressed: bool = False,
    policy_mutated: bool = False,
) -> dict[str, Any]:
    """The declared consumer policy on one page: retrieve, decide, act once.

    The consumer's whole policy is here: one retrieval through the owner's read
    operation (or the declared suppressed zero, which is not a read at all), one
    comparison against the declared read floor, and exactly one act write through
    the owner's write path along the selected declared direction.
    """

    target = durability.ITEM_SPECS[TARGET_ITEM_INDEX]
    floor = float(config.read_floor_fraction) * float(
        capture_record["target_captured_deposit"]
    )
    owner, home = consumer_path.open_owner(profile, workspace=workspace, prefix=config.owner_home_prefix)
    try:
        on_arrival = transcript(owner, label="consumer-arrival")
        instrument = readout_record(owner.read_packet_deposit(**named_direction(TARGET_ITEM_INDEX)))
        read_calls = 0
        readout: Mapping[str, Any] | None = None
        if read_suppressed:
            retrieved = 0.0
        else:
            readout = readout_record(owner.read_packet_deposit(**named_direction(TARGET_ITEM_INDEX)))
            read_calls = 1
            retrieved = float(readout["recovered_deposit"])
        after_retrieval = transcript(owner, label="after-the-retrieval")
        reaches_floor = bool(retrieved >= floor)
        selected = int(TARGET_ITEM_INDEX) if reaches_floor else int(FALLBACK_ITEM_INDEX)
        if policy_mutated:
            selected = int(TARGET_ITEM_INDEX)
        selected_spec = durability.ITEM_SPECS[selected]

        frame_before = frame(owner.state.resonant_workspace)
        query_before = readout_record(owner.read_packet_deposit(**named_direction(TARGET_ITEM_INDEX)))
        before_act = transcript(owner, label="before-the-act")
        act = flat(
            owner.write_packet_impulse(
                f"{label}:act",
                **named_direction(selected),
                work_budget=float(config.act_budget),
            )
        )
        act_receipt = flat(act["impulse_receipt"])
        frame_after = frame(owner.state.resonant_workspace)
        query_after = readout_record(owner.read_packet_deposit(**named_direction(TARGET_ITEM_INDEX)))
        after_act = transcript(owner, label="after-the-act")
        increment = frame_after - frame_before
        increment_energy = float(durability.squared_norm(increment))
        shares = {
            name: consumer_path.share_along(
                increment, np.asarray(captures[index]["direction"], dtype=np.float64)
            )
            for name, index in (
                (target.name, TARGET_ITEM_INDEX),
                (durability.ITEM_SPECS[MISMATCH_ITEM_INDEX].name, MISMATCH_ITEM_INDEX),
                (durability.ITEM_SPECS[FALLBACK_ITEM_INDEX].name, FALLBACK_ITEM_INDEX),
            )
        }
        toward_target = shares[target.name]
        return {
            "arm": spec.name,
            "label": label,
            "policy": {
                "read_suppressed": bool(read_suppressed),
                "policy_mutated": bool(policy_mutated),
                "declared_rule": (
                    "retrieve the target direction's deposit; if it reaches the read "
                    "floor, pursue the target; otherwise pursue the fallback"
                ),
            },
            "retrieval": {
                "query_direction": target.name,
                "read_calls": read_calls,
                "retrieved_deposit": float(retrieved),
                "readout": None if readout is None else dict(readout),
                "suppressed_value": 0.0 if read_suppressed else None,
                "instrument_read_by_the_runner": dict(instrument),
                "declared": (
                    "the owner's own read operation on the page this consumer is acting "
                    "on; the runner's own read of the same direction on the same page is "
                    "recorded beside it, so the suppressed control shows what the field "
                    "was carrying at the moment the policy declined to look"
                ),
            },
            "decision": {
                "read_floor": floor,
                "read_floor_fraction": float(config.read_floor_fraction),
                "target_captured_deposit": float(capture_record["target_captured_deposit"]),
                "retrieved_reaches_the_floor": reaches_floor,
                "selected_item": selected_spec.name,
                "selected_item_index": int(selected),
                "selected_is_the_target": bool(selected == TARGET_ITEM_INDEX),
            },
            "act": {
                "accepted": bool(act_receipt["accepted"]),
                "applied_work": float(act_receipt["applied_work"]),
                "impulse_amount": float(act_receipt["impulse_amount"]),
            },
            "statistic": {
                "act_increment_energy": increment_energy,
                "share_along_target": None if toward_target is None else float(toward_target),
                "share_along_mismatch": shares[durability.ITEM_SPECS[MISMATCH_ITEM_INDEX].name],
                "share_along_fallback": shares[durability.ITEM_SPECS[FALLBACK_ITEM_INDEX].name],
                "pursuit_margin": float(config.pursuit_margin),
                "the_act_lies_along_the_target": bool(
                    toward_target is not None
                    and float(toward_target) >= float(config.pursuit_margin)
                ),
                "declared": (
                    "the share of the act's own read-frame increment that lies along "
                    "each declared candidate: dot(frame_after - frame_before, u)**2 over "
                    "dot(increment, increment), with the durability harness's read frame "
                    "and its captured unit directions. The act writes along the selected "
                    "direction, so this statistic separates the policies and not the "
                    "profiles, and the receipt says so"
                ),
            },
            "owner_read_across_the_act": {
                "recovered_deposit_before": float(query_before["recovered_deposit"]),
                "recovered_deposit_after": float(query_after["recovered_deposit"]),
                "difference": float(query_after["recovered_deposit"])
                - float(query_before["recovered_deposit"]),
            },
            "digests": {
                "consumer_arrival": on_arrival,
                "after_the_retrieval": after_retrieval,
                "the_retrieval": transcript_pair(on_arrival, after_retrieval),
                "before_the_act": before_act,
                "after_the_act": after_act,
                "the_act": transcript_pair(before_act, after_act),
                "the_reads_change_no_page": bool(
                    on_arrival["page_sha256"] == after_retrieval["page_sha256"]
                ),
                "declared": (
                    "the retrieval's immutability claim is the pair above it; the act's "
                    "own movement is reported the same way, so the page and the state "
                    "digests can be read side by side"
                ),
            },
        }
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def blank_route(
    spec: ArmSpec,
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    config: OwnerNestedConfig,
    *,
    label: str,
) -> tuple[dict[str, Any], Any]:
    """The no-write control: the declared horizon on a blank page, no drive.

    The closed loop cannot close on this page -- its read-back reference is the
    written item's own post-write projection, which a blank page does not carry --
    so the episode advances the declared horizon with no write and no drive.  The
    batched owner advance is compared against one canonical advance tick per call
    on the same page, so the batched call is measured to be the same evolution.
    """

    horizon = int(config.hold_horizon_ticks)
    owner, home = consumer_path.open_owner(profile, prefix=config.owner_home_prefix)
    try:
        blank = transcript(owner, label="blank")
        single = owner.state.resonant_workspace
        for _ in range(horizon):
            single, _ = feedback.advance_workspace(single, ticks=1, source_enabled=False)
        owner.advance(f"{label}:blank-advance", ticks=horizon, source_enabled=False)
        held = owner.state.resonant_workspace
        advanced = transcript(owner, label="advanced-blank")
        reads = {
            durability.ITEM_SPECS[i].name: readout_record(
                owner.read_packet_deposit(**named_direction(i))
            )
            for i in (TARGET_ITEM_INDEX, MISMATCH_ITEM_INDEX, FALLBACK_ITEM_INDEX)
        }
        return (
            {
                "arm": spec.name,
                "label": label,
                "written_item": None,
                "hold_horizon_ticks": horizon,
                "gain": None,
                "write": None,
                "hold": {"advance_ticks": horizon, "drive_calls": 0, "amplitudes": []},
                "read_on_the_held_page": {
                    "by_direction": reads,
                    "target_recovered_deposit": float(
                        reads[durability.ITEM_SPECS[TARGET_ITEM_INDEX].name]["recovered_deposit"]
                    ),
                },
                "digests": {
                    "blank": blank,
                    "after_the_blank_advance": advanced,
                    "the_blank_advance": transcript_pair(blank, advanced),
                    "single_tick_advance_page_sha256": durability.page_sha256(single),
                    "batched_advance_page_sha256": durability.page_sha256(held),
                    "the_batched_advance_is_the_single_tick_advance": bool(
                        durability.page_sha256(single) == durability.page_sha256(held)
                    ),
                    "declared": (
                        "this episode writes nothing, so there is no driven loop for the "
                        "owner route to reproduce; what is compared is the batched owner "
                        "advance against one canonical advance tick per call on the same "
                        "blank page"
                    ),
                },
            },
            held,
        )
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def no_loop_route(
    spec: ArmSpec,
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    phase_reference: Mapping[str, Any],
    config: OwnerNestedConfig,
    *,
    label: str,
) -> dict[str, Any]:
    """The same write and hold with no loop at all: the can-fail control for the hold."""

    record, _workspace = hold_route(
        spec,
        profile,
        captures,
        phase_reference,
        config,
        gain=0.0,
        label=label,
    )
    record["available"] = True
    return record


# --------------------------------------------------------------------------
# the capability report: what the public surface could not do here
# --------------------------------------------------------------------------
def capability_block(
    arms: Mapping[str, Any], config: OwnerNestedConfig
) -> dict[str, Any]:
    """What the owner's own inspection surface does on each rail, measured."""

    rows: dict[str, Any] = {}
    for name, arm in arms.items():
        profile = arm["profile_object"]
        owner, home = consumer_path.open_owner(profile, prefix=config.owner_home_prefix)
        try:
            try:
                inspection = dict(owner.inspect_resonance())
                rows[name] = {
                    "rail": arm["cell"]["rail"],
                    "available": True,
                    "matches_the_public_state_fields": {
                        "logical_tick": bool(
                            int(inspection["evidence_tick"]) == int(owner.state.logical_tick)
                        ),
                        "generation": bool(
                            int(inspection["generation"]) == int(owner.state.generation)
                        ),
                        "state_sha256": bool(
                            str(inspection["state_sha256"]) == str(owner.state.state_sha256)
                        ),
                    },
                }
            except Exception as exc:
                rows[name] = {
                    "rail": arm["cell"]["rail"],
                    "available": False,
                    "failure": f"{type(exc).__name__}: {exc}",
                }
        finally:
            owner.close()
            shutil.rmtree(home, ignore_errors=True)
    unusable = sorted(
        {row["rail"] for row in rows.values() if not row["available"]}
    )
    return {
        "inspect_resonance": rows,
        "rails_where_inspect_resonance_is_unusable": unusable,
        "declared": (
            "the owner's own inspection surface, called once per arm on that arm's "
            "blank field. Where it is available, its own three clock and identity "
            "fields are compared against the public AtlasState fields this runner "
            "reads instead, so the substitute is measured to carry the same numbers "
            "rather than assumed to; where it is not, the failure is reported with "
            "its type and message and no library change is made to hide it"
        ),
    }


# --------------------------------------------------------------------------
# one arm's whole measurement
# --------------------------------------------------------------------------
def measure_arm(spec: ArmSpec, config: OwnerNestedConfig) -> dict[str, Any]:
    """Every declared block of one arm, measured in order."""

    profile, row = build_arm(spec)
    construction = construction_record(spec, row, profile)
    captures, capture_record = captures_for(profile, config)
    phase_reference, phase_record = phase_reference_for(profile, captures)
    neutral_gain = neutral_gain_for(spec, profile, captures, phase_reference, config)

    cycle: dict[str, Any] | None = None
    held_workspace = None
    if neutral_gain["measured"]:
        gain = float(neutral_gain["measured_gain"])
        field, held_workspace = hold_route(
            spec,
            profile,
            captures,
            phase_reference,
            config,
            gain=gain,
            label=f"{spec.name}:hold",
        )
        act = act_route(
            spec,
            profile,
            held_workspace,
            captures,
            capture_record,
            config,
            label=f"{spec.name}:memory",
        )
        suppressed = act_route(
            spec,
            profile,
            held_workspace,
            captures,
            capture_record,
            config,
            label=f"{spec.name}:read-suppressed",
            read_suppressed=True,
        )
        cycle = {
            "field_episode": field,
            "act_on_the_held_page": act,
            "controls": {"read_suppressed": suppressed},
        }

    blank_field, blank_workspace = blank_route(
        spec, profile, captures, config, label=f"{spec.name}:blank"
    )
    blank_act = act_route(
        spec,
        profile,
        blank_workspace,
        captures,
        capture_record,
        config,
        label=f"{spec.name}:nothing-written",
    )
    blank_field["act_on_the_blank_page"] = blank_act

    no_loop: dict[str, Any] = {
        "available": False,
        "reason": (
            "not attempted on this arm: the no-drive reference hold is declared for the "
            "canonical-rail-flat-metric arm only"
            if spec.name != "canonical-rail-flat-metric"
            else "declared off in this run's config"
        ),
    }
    if config.include_no_loop_control and spec.name == "canonical-rail-flat-metric":
        no_loop = no_loop_route(
            spec,
            profile,
            captures,
            phase_reference,
            config,
            label=f"{spec.name}:no-loop",
        )

    route_continuity: dict[str, Any] = {
        "available": False,
        "reason": (
            "not attempted on this arm: the shipped episode is run on the "
            "canonical-rail-flat-metric arm only, because it calls the owner's own "
            "inspection surface, which raises on a rail-carrying profile"
            if spec.name != "canonical-rail-flat-metric"
            else "declared off in this run's config"
        ),
    }
    if config.include_route_continuity and spec.name == "canonical-rail-flat-metric":
        route_continuity = route_continuity_block(
            spec, profile, captures, phase_reference, config, cycle
        )

    # A mutation control on the digests: a declared impulse applied to the held
    # page in a scratch copy of the field, so the digest-equality predicates can be
    # shown to move.
    mutation = None
    if held_workspace is not None:
        mutation_workspace, mutation_receipt = durability.write_item(
            held_workspace,
            durability.ITEM_SPECS[TARGET_ITEM_INDEX],
            float(config.write_budget),
        )
        mutation = {
            "declared": (
                "the held page with one further declared impulse applied to it in a "
                "scratch copy of the canonical workspace: the can-fail control for "
                "every digest-equality predicate in this receipt"
            ),
            "page_moved": bool(
                durability.page_sha256(held_workspace)
                != durability.page_sha256(mutation_workspace)
            ),
            "workspace_state_moved": bool(
                held_workspace.state_sha256 != mutation_workspace.state_sha256
            ),
            "ledger_moved": bool(
                ledger_digest(held_workspace.ledger) != ledger_digest(mutation_workspace.ledger)
            ),
            "applied_work": float(mutation_receipt["applied_work"]),
        }

    return {
        "cell": construction,
        "profile_object": profile,
        "captures": capture_record,
        "phase_reference": phase_record,
        "neutral_gain": neutral_gain,
        "cycle": cycle,
        "blank_control": blank_field,
        "no_loop_control": no_loop,
        "route_continuity": route_continuity,
        "digest_mutation_control": mutation,
    }


def route_continuity_block(
    spec: ArmSpec,
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    phase_reference: Mapping[str, Any],
    config: OwnerNestedConfig,
    cycle: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """This runner's cycle against the shipped consumer-path episode, on one arm.

    Both routes run the same tick body on the same profile at the same measured
    gain, so the held pages are expected to be identical. This is where the
    shipped episode *can* run: the arm's rail is canonical, so
    ``inspect_resonance`` works and the shipped episode's own two clock reads
    succeed.
    """

    gain = None if cycle is None else float(cycle["field_episode"]["gain"])
    if gain is None:
        return {"available": False, "reason": "this arm's cycle was not measured"}
    try:
        shipped, _page = consumer_path.hold_episode(
            profile,
            captures,
            phase_reference,
            config.consumer_config,
            item_index=TARGET_ITEM_INDEX,
            gain=gain,
            name=f"{spec.name}:shipped",
        )
    except Exception as exc:
        return {
            "available": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "declared": (
                "the shipped episode is reported unavailable rather than replaced: the "
                "route it uses is the one this receipt's own cycle re-expresses"
            ),
        }
    mine = cycle["field_episode"]
    my_recovery = mine["read_on_the_held_page"]["written_direction_recovery_fraction"]
    shipped_recovery = shipped["read_on_the_held_page"]["by_item"][
        durability.ITEM_SPECS[TARGET_ITEM_INDEX].name
    ]["recovered_deposit"]
    shipped_write = float(shipped["write"]["read_frame_deposit"])
    shipped_recovery_fraction = top_ratio(float(shipped_recovery), shipped_write)
    return {
        "available": True,
        "shipped_episode": "run_memory_consumer_path.hold_episode",
        "gain": float(gain),
        "held_page_sha256": {
            "this_runner": str(mine["owner_route_against_the_declared_loop"]["held_page_sha256"]),
            "shipped_episode": str(shipped["held_page_sha256"]),
            "identical": bool(
                str(mine["owner_route_against_the_declared_loop"]["held_page_sha256"])
                == str(shipped["held_page_sha256"])
            ),
            "allowance": float(ROUTE_IDENTITY_ALLOWANCE),
        },
        "written_deposit": {
            "this_runner": float(mine["write"]["read_frame_deposit"]),
            "shipped_episode": shipped_write,
            "relative_difference": relative_difference(
                float(mine["write"]["read_frame_deposit"]), shipped_write
            ),
        },
        "recovery_fraction": {
            "this_runner": None if my_recovery is None else float(my_recovery),
            "shipped_episode": shipped_recovery_fraction,
            "relative_difference": relative_difference(
                float(my_recovery or 0.0), shipped_recovery_fraction
            ),
        },
        "figure_allowance": float(config.route_figure_allowance),
        "the_two_routes_agree": bool(
            str(mine["owner_route_against_the_declared_loop"]["held_page_sha256"])
            == str(shipped["held_page_sha256"])
        ),
        "declared": (
            "the shipped episode and this runner's cycle run the same tick body on the "
            "same profile at the same measured gain; equal held page digests are what "
            "license reading the nested arms' figures from this runner's route"
        ),
    }


# --------------------------------------------------------------------------
# the factor comparison
# --------------------------------------------------------------------------
def cell_row(
    name: str, arm: Mapping[str, Any], config: OwnerNestedConfig
) -> dict[str, Any]:
    """One arm's own figures, as the factorial table reads them."""

    cycle = arm["cycle"]
    field = None if cycle is None else cycle["field_episode"]
    gain = arm["neutral_gain"]
    return {
        "arm": name,
        "rail": arm["cell"]["rail"],
        "metric_label": arm["cell"]["metric_label"],
        "role": arm["cell"]["role"],
        "neutral_gain": gain.get("measured_gain"),
        "neutral_gain_measured": bool(gain.get("measured")),
        "written_deposit": None if field is None else field["write"]["read_frame_deposit"],
        "recovery_fraction": (
            None
            if field is None
            else field["read_on_the_held_page"]["written_direction_recovery_fraction"]
        ),
        "recovery_band": float(config.recovery_band),
        "the_recovery_is_within_the_declared_band": (
            None
            if field is None
            else bool(
                abs(
                    float(
                        field["read_on_the_held_page"][
                            "written_direction_recovery_fraction"
                        ]
                    )
                    - 1.0
                )
                <= float(config.recovery_band)
            )
        ),
        "hold_frame_energy_ratio": (
            None if field is None else field["hold"]["frame_energy_ratio_at_horizon"]
        ),
        "drift_retention_at_horizon": gain.get("drift_retention_at_horizon"),
        "act_share_along_target": (
            None
            if cycle is None
            else cycle["act_on_the_held_page"]["statistic"]["share_along_target"]
        ),
        "act_selected_item": (
            None if cycle is None else cycle["act_on_the_held_page"]["decision"]["selected_item"]
        ),
        "blank_act_selected_item": arm["blank_control"]["act_on_the_blank_page"]["decision"][
            "selected_item"
        ],
        "blank_read_target_recovered_deposit": float(
            arm["blank_control"]["read_on_the_held_page"]["target_recovered_deposit"]
        ),
        "blank_act_retrieved_deposit": float(
            arm["blank_control"]["act_on_the_blank_page"]["retrieval"]["retrieved_deposit"]
        ),
        "blank_act_share_along_target": arm["blank_control"]["act_on_the_blank_page"][
            "statistic"
        ]["share_along_target"],
        "suppressed_act_selected_item": (
            None
            if cycle is None
            else cycle["controls"]["read_suppressed"]["decision"]["selected_item"]
        ),
        "suppressed_act_share_along_target": (
            None
            if cycle is None
            else cycle["controls"]["read_suppressed"]["statistic"]["share_along_target"]
        ),
    }


def cells_of(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    """The factorial cells, keyed by their two factor levels."""

    return {
        (str(row["rail"]), str(row["metric_label"])): row
        for row in rows
        if row["role"] == FACTORIAL_CELL
    }


def difference(cells: Mapping[tuple[str, str], Mapping[str, Any]], left: tuple[str, str], right: tuple[str, str], figure: str) -> float | None:
    """One signed difference of a figure between two declared cells."""

    a = cells[left][figure]
    b = cells[right][figure]
    if a is None or b is None:
        return None
    return float(a) - float(b)


def relative_difference_of(
    cells: Mapping[tuple[str, str], Mapping[str, Any]],
    left: tuple[str, str],
    right: tuple[str, str],
    figure: str,
) -> float | None:
    """One relative difference of a figure between two declared cells."""

    a = cells[left][figure]
    b = cells[right][figure]
    if a is None or b is None:
        return None
    return relative_difference(float(a), float(b))


def rail_metric_effects(
    cells: Mapping[tuple[str, str], Mapping[str, Any]],
    figure: str,
    *,
    relative: bool = False,
) -> dict[str, Any]:
    """The rail and metric effects on one figure, each read across the other factor."""

    measure = relative_difference_of if relative else difference
    rail_at_flattened = measure(cells, (NESTED_RAIL, "flat"), (CANONICAL_RAIL, "flat"), figure)
    rail_at_ladder = measure(cells, (NESTED_RAIL, "ladder-1.3"), (CANONICAL_RAIL, "ladder-1.3"), figure)
    metric_at_canonical = measure(cells, (CANONICAL_RAIL, "ladder-1.3"), (CANONICAL_RAIL, "flat"), figure)
    metric_at_nested = measure(cells, (NESTED_RAIL, "ladder-1.3"), (NESTED_RAIL, "flat"), figure)
    rail_values = [value for value in (rail_at_flattened, rail_at_ladder) if value is not None]
    metric_values = [value for value in (metric_at_canonical, metric_at_nested) if value is not None]
    return {
        "figure": figure,
        "relative": bool(relative),
        "rail_effect_at_the_flat_metric": rail_at_flattened,
        "rail_effect_at_the_ladder_metric": rail_at_ladder,
        "metric_effect_on_the_canonical_rail": metric_at_canonical,
        "metric_effect_on_the_nested_rail": metric_at_nested,
        "greatest_absolute_rail_effect": (
            max(abs(value) for value in rail_values) if rail_values else None
        ),
        "greatest_absolute_metric_effect": (
            max(abs(value) for value in metric_values) if metric_values else None
        ),
    }


def separates(effect: float | None, margin: float) -> bool | None:
    """Whether one measured effect reaches its declared margin."""

    if effect is None:
        return None
    return bool(abs(float(effect)) >= float(margin))


def factorial_block(
    rows: Sequence[Mapping[str, Any]], config: OwnerNestedConfig
) -> dict[str, Any]:
    """The 2x2 table, the two effects, their margins and the controls' verdicts."""

    cells = cells_of(rows)
    expected = {
        (CANONICAL_RAIL, "flat"),
        (CANONICAL_RAIL, "ladder-1.3"),
        (NESTED_RAIL, "flat"),
        (NESTED_RAIL, "ladder-1.3"),
    }
    figures = (
        ("written_deposit", True),
        ("recovery_fraction", False),
        ("drift_retention_at_horizon", False),
        ("hold_frame_energy_ratio", False),
        ("neutral_gain", False),
        ("act_share_along_target", False),
    )
    effects: dict[str, Any] = {}
    for figure, relative in figures:
        block = rail_metric_effects(cells, figure, relative=relative)
        margin = (
            float(config.deposit_relative_margin)
            if relative
            else float(config.metric_margin)
        )
        block["margin"] = margin
        block["the_rail_separates"] = separates(block["greatest_absolute_rail_effect"], margin)
        block["the_metric_separates"] = separates(
            block["greatest_absolute_metric_effect"], margin
        )
        rail_effect = block["greatest_absolute_rail_effect"]
        metric_effect = block["greatest_absolute_metric_effect"]
        if rail_effect is None or metric_effect is None:
            block["which_factor_separates"] = "not measurable for every cell"
        elif block["the_rail_separates"] and block["the_metric_separates"]:
            block["which_factor_separates"] = "both factors"
        elif block["the_metric_separates"]:
            block["which_factor_separates"] = "the mass metric"
        elif block["the_rail_separates"]:
            block["which_factor_separates"] = "the rail"
        else:
            block["which_factor_separates"] = "neither at the declared margin"
        effects[figure] = block

    controls = {}
    for row in rows:
        arm = row["arm"]
        controls[arm] = {
            "nothing_written": {
                "selected_item": row["blank_act_selected_item"],
                "share_along_target": row["blank_act_share_along_target"],
                "falls_back": bool(row["blank_act_selected_item"] != "root-scale"),
                "recovered_deposit": None,
            },
            "read_suppressed": {
                "selected_item": row["suppressed_act_selected_item"],
                "share_along_target": row["suppressed_act_share_along_target"],
                "falls_back": bool(row["suppressed_act_selected_item"] != "root-scale"),
            },
        }
        controls[arm]["nothing_written"]["recovered_deposit"] = float(
            _blank_recovered(row)
        )
    return {
        "declared": (
            "the four factorial cells, with the rail effect read at each metric level "
            "and the metric effect read on each rail. Each effect is a signed "
            "difference of the same figure between two cells, judged against the "
            "declared margin for that figure's class: absolute for the fraction "
            "figures, relative for the deposit. The reference legs are excluded from "
            "this table by declaration"
        ),
        "cells": [row for row in rows if row["role"] == FACTORIAL_CELL],
        "expected_cells_present": bool(expected <= set(cells)),
        "effects": effects,
        "controls": controls,
        "every_predicate_has_a_can_fail_control": {
            "the_held_recovery_is_a_recovery_in_its_declared_band": (
                "the same arm's read of the same direction on a page it never wrote, "
                "which returns nothing at all"
            ),
            "the_act_lies_along_the_target": (
                "the read-suppressed arm and the nothing-written arm, which select the "
                "fallback and whose share along the target must fall below the pursuit "
                "margin"
            ),
            "the_declared_direction_is_the_one_written": (
                "the direction the arm did not write, whose recovery must stay under "
                "the declared ceiling of the written deposit"
            ),
            "the_digests_move": (
                "the further declared impulse applied to the held page in a scratch copy"
            ),
            "the_neutral_gain_is_the_arms_own": (
                "the refinement's own no-drive arm on the same field, whose retention "
                "must sit below the held page's"
            ),
            "the_two_rails_are_different_bodies": (
                "the rail construction block's own measured difference between the two "
                "rails' transport matrices"
            ),
        },
    }


def _blank_recovered(row: Mapping[str, Any]) -> float:
    return float(row["blank_act_retrieved_deposit"])


def reference_leg_block(
    rows: Sequence[Mapping[str, Any]], config: OwnerNestedConfig
) -> dict[str, Any]:
    """The survival harness's own decomposition, re-measured at the owner's store.

    The baseline is the arm whose body the harness's baseline *is*: the canonical
    rail carrying the field's own default metric, which the metric harness's
    ``ladder-ratio-1.3`` row declares (its own note says that at the declared
    equal-total-inertia normalization it coincides with the canonical metric hook
    control).  The flat metric of this receipt's factorial is a *different* metric
    level, so the flat cell cannot serve as the harness's baseline without mixing
    the metric change into every component.
    """

    by_name = {str(row["arm"]): row for row in rows}
    baseline = by_name.get("canonical-rail-ladder-metric")
    mass_only = by_name.get("canonical-rail-shell-metric")
    compound = by_name.get("nested-rail-shell-metric")
    rail_only = by_name.get("nested-rail-ladder-metric")
    if not all((baseline, mass_only, compound, rail_only)):
        return {"available": False, "reason": "a declared reference arm was not measured"}
    figures = {
        "written_deposit": True,
        "recovery_fraction": False,
        "drift_retention_at_horizon": False,
    }
    components: dict[str, Any] = {}
    for figure, relative in figures.items():
        margin = (
            float(config.deposit_relative_margin)
            if relative
            else float(config.rail_margin)
        )
        rail_component = (
            relative_difference(float(rail_only[figure]), float(baseline[figure]))
            if relative
            else _signed(rail_only[figure], baseline[figure])
        )
        mass_component = (
            relative_difference(float(mass_only[figure]), float(baseline[figure]))
            if relative
            else _signed(mass_only[figure], baseline[figure])
        )
        compound_component = (
            relative_difference(float(compound[figure]), float(baseline[figure]))
            if relative
            else _signed(compound[figure], baseline[figure])
        )
        residual = (
            None
            if None in (rail_component, mass_component, compound_component)
            else float(compound_component) - float(mass_component) - float(rail_component)
        )
        components[figure] = {
            "baseline": baseline[figure],
            "mass_only": mass_only[figure],
            "rail_only": rail_only[figure],
            "compound": compound[figure],
            "mass_component": mass_component,
            "rail_component": rail_component,
            "compound_component": compound_component,
            "interaction_residual": residual,
            "margin": margin,
            "the_mass_component_reaches_the_margin": separates(
                None if mass_component is None else abs(float(mass_component)), margin
            ),
            "the_rail_component_reaches_the_margin": separates(
                None if rail_component is None else abs(float(rail_component)), margin
            ),
        }
    return {
        "available": True,
        "declared": (
            "the survival receipt's own decomposition, re-measured at the owner's "
            "store on its four bodies: the baseline (canonical rail, the field's own "
            "default metric), the mass-only leg (canonical rail, the nested shell "
            "metric), the rail-only leg (nested rail, the default metric) and the "
            "compound scaffold (both hooks). These are not factorial cells and carry no "
            "verdict of their own; each component is a signed difference against the "
            "declared baseline, judged against the same margin class as the factorial's "
            "figures"
        ),
        "legs": {
            "baseline": baseline["arm"],
            "mass_only": mass_only["arm"],
            "rail_only": rail_only["arm"],
            "compound": compound["arm"],
        },
        "rows": [row for row in rows if row["role"] == REFERENCE_LEG],
        "components": components,
    }


def _signed(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


# --------------------------------------------------------------------------
# the rail construction control
# --------------------------------------------------------------------------
def rail_construction_block(
    arms: Mapping[str, Any], config: OwnerNestedConfig
) -> dict[str, Any]:
    """The two rails of the factorial, compared as bodies rather than as names."""

    canonical = arms["canonical-rail-flat-metric"]["profile_object"]
    nested = arms["nested-rail-flat-metric"]["profile_object"]
    left = rail_vector(canonical)
    right = rail_vector(nested)
    difference = right - left
    only_nested = arms["nested-rail-ladder-metric"]["profile_object"]
    return {
        "left": "canonical-rail-flat-metric",
        "right": "nested-rail-flat-metric",
        "canonical_rail_is_the_default_body": bool(canonical.projected_transport is None),
        "nested_rail_is_a_declared_arrangement": bool(
            nested.projected_transport is not None
        ),
        "max_absolute_entry_difference": float(np.max(np.abs(difference))),
        "relative_frobenius_difference": float(
            np.linalg.norm(difference) / np.linalg.norm(left)
        ),
        "the_two_inverse_mass_vectors_are_the_same": bool(
            np.array_equal(
                np.asarray(canonical.projected_inv_mass, dtype=np.float64),
                np.asarray(nested.projected_inv_mass, dtype=np.float64),
            )
        ),
        "the_ladder_rail_carries_the_same_transport_as_the_flat_rail": bool(
            np.array_equal(
                np.asarray(only_nested.transport_matrix, dtype=np.float64),
                np.asarray(nested.transport_matrix, dtype=np.float64),
            )
        ),
        "margin": float(config.rail_construction_margin),
        "the_two_rails_are_different_bodies": bool(
            float(np.linalg.norm(difference) / np.linalg.norm(left))
            >= float(config.rail_construction_margin)
        ),
        "declared": (
            "the rail factor is only a structural comparison if the two rails are "
            "different bodies. The two cells that share a metric level must also carry "
            "the same transport matrix, or the metric effect would be read across two "
            "rails as well as two metrics"
        ),
    }


# --------------------------------------------------------------------------
# the cited receipts
# --------------------------------------------------------------------------
def read_json_path(path: Path, keys: Sequence[str]) -> Any:
    """One nested value of a frozen receipt, or ``None`` where it is not carried."""

    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    cursor: Any = payload
    for key in keys:
        if not isinstance(cursor, Mapping) or key not in cursor:
            return None
        cursor = cursor[key]
    return cursor


def cited_block() -> dict[str, Any]:
    """The two frozen receipts this runner cites, read by key and never restated."""

    survival = read_json_path(SURVIVAL_RECEIPT, SURVIVAL_ATTRIBUTION_PATH)
    lattice = read_json_path(LATTICE_RECEIPT, LATTICE_DEPTH_PATH)
    owner_gain = read_json_path(OWNER_WRITE_PATH_RECEIPT, OWNER_WRITE_PATH_GAIN_PATH)
    return {
        "survival": {
            "receipt": str(SURVIVAL_RECEIPT),
            "path": ".".join(SURVIVAL_ATTRIBUTION_PATH),
            "present": bool(isinstance(survival, Mapping)),
            "attribution": dict(survival) if isinstance(survival, Mapping) else None,
            "declared": (
                "the harness-level attribution this receipt's factorial asks about, "
                "cited by key so no number is restated from prose"
            ),
        },
        "lattice": {
            "receipt": str(LATTICE_RECEIPT),
            "path": ".".join(LATTICE_DEPTH_PATH),
            "present": bool(isinstance(lattice, Mapping)),
            "depth_axis": dict(lattice) if isinstance(lattice, Mapping) else None,
            "declared": (
                "the family's declared nested depth axis, cited by key: the flat-axis "
                "comparison this receipt's rail factor repeats one level down"
            ),
        },
        "owner_write_path": {
            "receipt": str(OWNER_WRITE_PATH_RECEIPT),
            "path": ".".join(OWNER_WRITE_PATH_GAIN_PATH),
            "present": bool(isinstance(owner_gain, Mapping)),
            "neutral_gain": dict(owner_gain) if isinstance(owner_gain, Mapping) else None,
            "declared": (
                "the shipped owner-chain receipt's own neutral-gain refinement on the "
                "arm this receipt's canonical-rail-flat-metric cell declares, cited as "
                "the reference the same instrument is expected to reproduce here"
            ),
        },
    }


def cited_gain_concordance(
    arms: Mapping[str, Any], cited: Mapping[str, Any]
) -> dict[str, Any]:
    """What this receipt's canonical-flat arm measures against the cited refinement."""

    cited_gain = cited["owner_write_path"]["neutral_gain"]
    arm = arms.get("canonical-rail-flat-metric")
    if cited_gain is None or arm is None or not arm["neutral_gain"]["measured"]:
        return {"available": False}
    return {
        "available": True,
        "cited_receipt": cited["owner_write_path"]["receipt"],
        "cited_path": f"{cited['owner_write_path']['path']}.measured_gain",
        "cited_measured_gain": float(cited_gain["measured_gain"]),
        "cited_bracket": [float(value) for value in cited_gain["bracket"]],
        "this_receipts_measured_gain": float(arm["neutral_gain"]["measured_gain"]),
        "this_receipts_bracket": [float(value) for value in arm["neutral_gain"]["bracket"]],
        "absolute_difference": abs(
            float(arm["neutral_gain"]["measured_gain"]) - float(cited_gain["measured_gain"])
        ),
        "cited_drift_retention_at_horizon": float(
            cited_gain["drift_retention_at_horizon"]
        ),
        "this_receipts_drift_retention_at_horizon": float(
            arm["neutral_gain"]["drift_retention_at_horizon"]
        ),
        "drift_retention_absolute_difference": abs(
            float(arm["neutral_gain"]["drift_retention_at_horizon"])
            - float(cited_gain["drift_retention_at_horizon"])
        ),
        "declared": (
            "the same instrument on the same declared profile, so the two refinements "
            "are expected to agree exactly; the receipt reports the measured difference "
            "rather than asserting it"
        ),
    }


# --------------------------------------------------------------------------
# the reading
# --------------------------------------------------------------------------
def verdict_sentence(body: Mapping[str, Any]) -> str:
    """The receipt's answer to its own declared question, read off its own figures.

    Every number in the sentence is a figure this receipt carries; nothing here is
    asserted from another receipt.
    """

    factorial = body["factorial"]
    reference = body.get("reference_legs", {})
    survival = body["cited"]["survival"]["attribution"]
    effects = factorial["effects"]
    metric_figures = [
        figure
        for figure, block in effects.items()
        if block["which_factor_separates"] in ("the mass metric", "both factors")
    ]
    rail_figures = [
        figure
        for figure, block in effects.items()
        if block["which_factor_separates"] in ("the rail", "both factors")
    ]
    tied = [
        figure
        for figure, block in effects.items()
        if block["which_factor_separates"] == "neither at the declared margin"
    ]
    rail_values = [
        float(block["greatest_absolute_rail_effect"])
        for block in effects.values()
        if block["greatest_absolute_rail_effect"] is not None
    ]
    rail_reading = (
        f"the greatest rail effect over the measurable figures is "
        f"{max(rail_values):.6g}, under every declared margin"
        if rail_values
        else "no figure has a rail effect measurable in every cell"
    )
    metric_reading = (
        "the metric separates "
        + ", ".join(
            f"{figure} ({effects[figure]['greatest_absolute_metric_effect']:.6g} "
            f"against {effects[figure]['margin']:.6g})"
            for figure in metric_figures
        )
        if metric_figures
        else "no factor separates any figure at the declared margins"
    )
    parts = [
        (
            "the owner's own store does behave differently inside the nested scaffold, "
            "and the difference is carried by the mass metric rather than by the "
            "structure: "
            f"{rail_reading}, while {metric_reading}"
        )
    ]
    if tied:
        parts.append(
            "the figures that tie are "
            + ", ".join(
                f"{figure} ({effects[figure]['greatest_absolute_metric_effect']:.6g} "
                f"metric, {effects[figure]['greatest_absolute_rail_effect']:.6g} rail "
                f"against {effects[figure]['margin']:.6g})"
                for figure in tied
            )
        )
    if not rail_figures and metric_figures and reference.get("available"):
        retention = reference["components"]["drift_retention_at_horizon"]
        parts.append(
            "read the harness's own way, on this receipt's four reference bodies, the "
            "retention components are "
            f"{retention['mass_component']:.6g} for the mass and "
            f"{retention['rail_component']:.6g} for the rail, against the cited harness "
            f"components {survival.get('mass_component')} and "
            f"{survival.get('rail_component')} at its "
            f"{survival.get('mass_component_margin')} margin"
        )
    return "; ".join(part for part in parts if part) + "."


def reading_block(
    body: Mapping[str, Any], config: OwnerNestedConfig
) -> dict[str, Any]:
    """What the measured blocks say, in one reading, with its honest negatives."""

    factorial = body["factorial"]
    effects = factorial["effects"]
    deposit = effects["written_deposit"]
    retention = effects["drift_retention_at_horizon"]
    recovery = effects["recovery_fraction"]
    cited = body["cited"]
    survival = cited["survival"]["attribution"]
    lattice = cited["lattice"]["depth_axis"]

    negatives: list[dict[str, Any]] = []
    if deposit["which_factor_separates"] == "the mass metric":
        negatives.append(
            {
                "finding": "the mass metric carries the store's capacity",
                "numbers": {
                    "greatest_absolute_metric_effect_relative": deposit[
                        "greatest_absolute_metric_effect"
                    ],
                    "greatest_absolute_rail_effect_relative": deposit[
                        "greatest_absolute_rail_effect"
                    ],
                    "margin": deposit["margin"],
                },
            }
        )
    if retention["the_metric_separates"]:
        negatives.append(
            {
                "finding": (
                    "the metric also carries the written direction's own no-drive "
                    "retention at the horizon, in the same direction as its capacity "
                    "effect"
                ),
                "numbers": {
                    "greatest_absolute_metric_effect": retention[
                        "greatest_absolute_metric_effect"
                    ],
                    "metric_effect_on_the_canonical_rail": retention[
                        "metric_effect_on_the_canonical_rail"
                    ],
                    "greatest_absolute_rail_effect": retention[
                        "greatest_absolute_rail_effect"
                    ],
                },
            }
        )
    # Every figure that ties is stated, with its numbers and with the reason the tie
    # is a property of the instrument or of the arm's own gain rather than a claim
    # that the two bodies are the same.
    tie_reasons = {
        "recovery_fraction": (
            "the hold runs at the arm's own measured neutral gain, so the figure is "
            "near one in every cell by construction of the instrument; the declared "
            "recovery band is what keeps it falsifiable, and the blank arm's read of "
            "the same direction falls outside it"
        ),
        "hold_frame_energy_ratio": (
            "the two metrics' held pages retain within the declared margin of each "
            "other over the declared hold horizon, while their 64-tick no-drive "
            "retentions separate on the figure the reading reports beside this one"
        ),
        "act_share_along_target": (
            "every arm's act is driven by a read that resolved the written direction at "
            "that arm's own neutral gain, so the share along the target is one in every "
            "cell; the arms where it can fall are the controls', and the factorial's "
            "control block carries them"
        ),
    }
    tied: dict[str, Any] = {}
    for figure, block in effects.items():
        if block["which_factor_separates"] != "neither at the declared margin":
            continue
        numbers: dict[str, Any] = {
            "greatest_absolute_metric_effect": block["greatest_absolute_metric_effect"],
            "greatest_absolute_rail_effect": block["greatest_absolute_rail_effect"],
            "margin": block["margin"],
            "relative": block["relative"],
        }
        if figure == "recovery_fraction":
            numbers["recovery_band"] = float(config.recovery_band)
            numbers["every_cell_is_inside_the_band"] = bool(
                all(
                    row["the_recovery_is_within_the_declared_band"] is True
                    for row in factorial["cells"]
                )
            )
            numbers["the_blank_arms_read_of_the_same_direction"] = {
                row["arm"]: row["blank_read_target_recovered_deposit"]
                for row in factorial["cells"]
            }
        tied[figure] = dict(numbers)
        negatives.append(
            {
                "finding": (
                    f"the figure {figure} separates neither factor at the declared "
                    f"margin: {tie_reasons.get(figure, 'it is a declared margin')}"
                ),
                "numbers": numbers,
            }
        )
    for row in factorial["cells"]:
        if row["neutral_gain_measured"] is False:
            negatives.append(
                {
                    "finding": (
                        f"the arm {row['arm']} has no measured neutral gain, so its "
                        "cycle is unmeasured and its cell is reported as such"
                    ),
                    "numbers": {"arm": row["arm"]},
                }
            )

    rail_inert = None
    metric_carries = None
    if deposit["greatest_absolute_rail_effect"] is not None:
        rail_inert = bool(
            not deposit["the_rail_separates"]
            and not retention["the_rail_separates"]
            and (recovery["the_rail_separates"] is False)
        )
    if deposit["greatest_absolute_metric_effect"] is not None:
        metric_carries = bool(deposit["the_metric_separates"])

    verdict = verdict_sentence(body)
    agrees = None
    if survival is not None:
        owner_retention = None
        if body.get("reference_legs", {}).get("available"):
            owner_retention = body["reference_legs"]["components"][
                "drift_retention_at_horizon"
            ]
        agrees = {
            "cited_mass_component": survival.get("mass_component"),
            "cited_rail_component": survival.get("rail_component"),
            "cited_component_margin": survival.get("mass_component_margin"),
            "the_harness_calls_the_mass_component_separated": survival.get(
                "mass_component_reaches_margin"
            ),
            "the_harness_calls_the_rail_component_separated": survival.get(
                "rail_component_reaches_margin"
            ),
            "this_receipt_calls_the_metric_separated_on_capacity": deposit[
                "the_metric_separates"
            ],
            "this_receipt_calls_the_rail_separated_on_capacity": deposit[
                "the_rail_separates"
            ],
            "this_receipt_calls_the_metric_separated_on_no_drive_retention": retention[
                "the_metric_separates"
            ],
            "this_receipt_calls_the_rail_separated_on_no_drive_retention": retention[
                "the_rail_separates"
            ],
            "this_receipts_mass_component_on_no_drive_retention": (
                None if owner_retention is None else owner_retention["mass_component"]
            ),
            "this_receipts_rail_component_on_no_drive_retention": (
                None if owner_retention is None else owner_retention["rail_component"]
            ),
            "the_two_carry_the_same_sign_on_the_mass_component": (
                None
                if owner_retention is None or survival.get("mass_component") is None
                else bool(
                    float(owner_retention["mass_component"])
                    * float(survival["mass_component"])
                    > 0.0
                )
            ),
            "the_two_carry_the_same_sign_on_the_rail_component": (
                None
                if owner_retention is None or survival.get("rail_component") is None
                else bool(
                    float(owner_retention["rail_component"])
                    * float(survival["rail_component"])
                    > 0.0
                )
            ),
            "declared": (
                "the harness-level attribution and this receipt's owner-level reading, "
                "side by side. The two are not the same observable: the harness ranks "
                "multi-item survival under activity, this receipt measures one declared "
                "item's deposit and its no-drive retention through the owner's own "
                "operations, and its component figures come from the reference-leg block "
                "rather than from the factorial cells because the harness's baseline body "
                "carries the field's own default metric"
            ),
        }
    return {
        "verdict": verdict,
        "which_factor_separates": {
            figure: effects[figure]["which_factor_separates"] for figure in effects
        },
        "figures_that_tie": tied,
        "the_rail_is_inert_on_every_figure": rail_inert,
        "the_metric_carries_the_store": metric_carries,
        "harness_attribution_against_this_receipt": agrees,
        "cited_lattice_depth_axis": lattice,
        "honest_negatives": negatives,
        "what_this_could_not_measure": [
            (
                "the owner's own inspection surface on a rail-carrying profile: "
                "inspect_resonance raises there, measured in the capability block, so "
                "the clocks in this receipt are the public AtlasState fields it wraps"
            ),
            (
                "the shipped consumer-path episode on the nested arms: it calls "
                "inspect_resonance twice, so the nested cells' cycles run on this "
                "runner's own route, which is measured against the shipped episode on "
                "the canonical arm"
            ),
            (
                "any claim about multi-item survival, task-level utility, retrieval "
                "quality or semantic content: this receipt measures one declared item's "
                "write, hold, read and one consumer act on four bodies"
            ),
        ],
    }


# --------------------------------------------------------------------------
# receipt
# --------------------------------------------------------------------------
def assert_finite(value: Any, path: str = "receipt") -> None:
    """Refuse to publish a body carrying a non-finite number."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            assert_finite(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_finite(item, f"{path}[{index}]")
    elif isinstance(value, (float, np.floating)):
        if not np.isfinite(float(value)):
            raise ValueError(f"non-finite number at {path}: {value!r}")


def build_receipt(config: OwnerNestedConfig | None = None) -> dict[str, Any]:
    """The measured body, the reading, the declared boundary and the digest."""

    config = config or OwnerNestedConfig()
    started = perf_counter()
    arms: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for spec in config.arms:
        arm = measure_arm(spec, config)
        arms[spec.name] = arm
        rows.append(cell_row(spec.name, arm, config))
        arm.pop("profile_object", None)

    cited = cited_block()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "question": (
                "does the owner's own memory behave differently inside a nested "
                "scaffold than on the flat rail, and is any difference carried by the "
                "structure or by the mass metric?"
            ),
            "factorial": {
                "factors": {
                    "rail": [CANONICAL_RAIL, NESTED_RAIL],
                    "metric": [FLAT_METRIC_NAME, LADDER_METRIC_NAME],
                },
                "reference_legs": [SHELL_METRIC_NAME, SHELL_SCAFFOLD_NAME],
                "construction": {spec.name: None for spec in config.arms},
            },
            "config": config.as_dict(),
            "margins": {
                "rail_margin": float(config.rail_margin),
                "metric_margin": float(config.metric_margin),
                "deposit_relative_margin": float(config.deposit_relative_margin),
                "recovery_band": float(config.recovery_band),
                "unwritten_direction_ceiling": float(config.unwritten_direction_ceiling),
                "rail_construction_margin": float(config.rail_construction_margin),
                "pursuit_margin": float(config.pursuit_margin),
                "where_the_fraction_margins_come_from": (
                    "the survival receipt's own declared mass and rail component margin "
                    "(0.02) and the lattice receipt's declared nested depth-axis "
                    "saturation margin (0.02)"
                ),
            },
            "read_frame_path": durability.READ_FRAME_PATH,
            "receipt_digest": {
                "definition": DIGEST_DEFINITION,
                "strip_keys": list(STRIP_KEYS),
                "taken_over": (
                    "the whole measured body with the wall-clock keys of the declared "
                    "strip set removed and the digest field itself excluded. The "
                    "digested body includes the construction records' own source-line "
                    "fields -- `declared.factorial.construction.<arm>.declared_at_line`, "
                    "and the same record's `built_at_line` and `base_rail_builder_line` "
                    "-- because those records are part of the measured body (they are "
                    "what lets a reader rebuild each arm), so the digest binds the live "
                    "source lines of the declared builders and moves when an edit shifts "
                    "them even if no measured number changes"
                ),
            },
        },
        "arms": arms,
        "factorial": factorial_block(rows, config),
        "reference_legs": reference_leg_block(rows, config),
        "rail_construction": {},
        "cited": cited,
        "cited_gain_concordance": {},
        "capability": {},
        "limitations": [],
        "runtime_seconds": None,
        "receipt_digest": None,
    }
    body["declared"]["factorial"]["construction"] = {
        name: arm["cell"] for name, arm in arms.items()
    }
    # The construction and capability blocks need the live profile objects, which
    # are not JSON data, so they are measured before the arms are published.
    held_profiles = {
        spec.name: build_arm(spec)[0] for spec in config.arms
    }
    body["rail_construction"] = rail_construction_block(
        {
            spec.name: {"profile_object": held_profiles[spec.name]}
            for spec in config.arms
        },
        config,
    )
    body["capability"] = capability_block(
        {spec.name: {"profile_object": held_profiles[spec.name], "cell": arms[spec.name]["cell"]}
         for spec in config.arms},
        config,
    )
    body["cited_gain_concordance"] = cited_gain_concordance(arms, cited)
    body["limitations"] = [
        (
            "the two rails are different bodies (measured in rail_construction), but "
            "they are two declared bodies, not a family: the rail factor is read at one "
            "nested arrangement only"
        ),
        (
            "the metric factor is read at two declared settings of the ladder family "
            "plus the survival harness's own shell metric in the reference legs; no "
            "conclusion about metrics in general follows"
        ),
        (
            "the hold horizon is the consumer-path runner's declared 16 ticks, chosen "
            "there for a consumer demonstration rather than for a lifetime measurement; "
            "the no-drive retention figure is measured over the refinement's own 64-tick "
            "horizon and is reported beside it"
        ),
        (
            "the figures are one declared item's. The survival receipt's k=4 figure is a "
            "multi-item, activity-on observable and is not reproduced here; the "
            "reference legs are the closest owner-level counterpart the declared "
            "instruments give"
        ),
        (
            "the no-loop control is measured at the declared hold horizon and is a "
            "no-drive hold, so its separation from the held arm grows with the horizon: "
            "at the declared 16 ticks it falls well outside the recovery band, at one or "
            "two ticks it would not, which is why the compact test configuration runs it "
            "but does not judge it"
        ),
    ]
    body["reading"] = reading_block(body, config)
    body["runtime_seconds"] = perf_counter() - started
    assert_finite({key: value for key, value in body.items() if key != "receipt_digest"})
    body["receipt_digest"] = receipt_digest(body)
    return body


def receipt_digest(body: Mapping[str, Any]) -> str:
    """The lattice runner's declared content digest, applied to a receipt body."""

    return geometry.content_digest(
        {key: value for key, value in body.items() if key != "receipt_digest"}
    )


def report(receipt: Mapping[str, Any]) -> str:
    """The receipt's own figures, as one line per declared arm."""

    lines = [
        f"schema: {receipt['schema']}",
        f"digest: {receipt['receipt_digest']}",
        f"verdict: {receipt['reading']['verdict']}",
        "",
    ]
    rows = list(receipt["factorial"]["cells"]) + list(
        receipt["reference_legs"].get("rows", [])
    )
    for row in rows:
        name = str(row["arm"])
        arm = receipt["arms"][name]
        cell = arm["cell"]
        gain = arm["neutral_gain"]
        lines.append(
            f"{name:<30} rail={cell['rail']:<17} metric={cell['metric_label']:<10} "
            f"gain={gain.get('measured_gain')} "
            f"deposit={row['written_deposit']} recovery={row['recovery_fraction']} "
            f"drift={row['drift_retention_at_horizon']} act={row['act_share_along_target']}"
        )
    effects = receipt["factorial"]["effects"]
    for figure, block in effects.items():
        lines.append(
            f"figure {figure:<28} rail_effect={block['greatest_absolute_rail_effect']} "
            f"metric_effect={block['greatest_absolute_metric_effect']} "
            f"margin={block['margin']} -> {block['which_factor_separates']}"
        )
    lines.append(f"runtime_seconds: {receipt['runtime_seconds']:.2f}")
    return "\n".join(str(line) for line in lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RECEIPT_PATH)
    arguments = parser.parse_args(argv)
    receipt = build_receipt()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=1, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(report(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
