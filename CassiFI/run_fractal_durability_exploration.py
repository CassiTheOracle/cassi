"""Measure whether a pattern written into the canonical field outlives unrelated activity and a restart.

The multiscale and geometry harnesses measured retention, leakage, closure, and
disturbance relaxation without ever checkpointing. This runner asks the
remaining question directly: is a written packet pattern a durable store or
decaying activity? One declared item is written as a bounded packet impulse at a
declared scale on a declared packet path, then read back through the canonical
packet readout after (a) nothing, (b) bounded unrelated canonical activity with
the heartbeat and sources on, (c) an exact restart, and (d) a restart plus that
activity, with single-item controls and 2/4/8-item interference arms. Declared
counterparts of the activity arms repeat the same write, restart and read with
``source_enabled=False`` on the advance, so the direction loss can be attributed
to the canonical source or to the body's own dynamics rather than assumed.

The restart path used for the item is the canonical workspace round trip
(``as_dict``/``from_dict``) with state-digest identity. The production owner is
probed separately under a bounded deterministic setup: its checkpoint path is
reachable and preserves the canonical workspace, but the owner's transition
surface exposes no packet-impulse operation, so an owner-checkpoint arm carrying
the written item would have to hand the owner an externally modified workspace
and would not be an owner write path. That is stated in the receipt.

Every number comes from the canonical packet and workspace APIs. These are
canonical-field numerical measurements in controlled conditions. They do not
establish task-level memory utility, semantic content, retrieval by a consumer,
owner-level checkpoint identity for a written item, or any advantage over
alternative architectures. Negative results are deliverables: if the written
pattern does not survive, the receipt reports the measured decay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_resonant_field import (
    ResonantProfile,
    ResonantWorkspace,
    advance_workspace,
    analyze_helical_packet,
    apply_helical_packet_impulse,
    initial_workspace,
)

SCHEMA = "cassifi.fractal-durability-exploration.v1"
EVENT_KIND = "reasoning-work"
# The declared packet path of the read frame: the whole balanced packet. Items
# are written at declared sub-paths inside it, so every write lands inside the
# support the readout covers.
READ_FRAME_PATH = ""
# The canonical impulse writes momentum lanes only; the two position channels
# are recipients in every arm.
POSITION_CHANNELS_DRIVABLE = False
# Distinctness of the declared item directions in the read frame is a measured
# property, not an assumption: the declared 8-item frame is exactly orthogonal
# because a root scale mode and every node detail mode are separate elements of
# the balanced Haar basis, so every item carries its own direction. This is the
# squared-cosine allowance under which they count as orthogonal, and the
# measured maximum is reported beside it.
ORTHOGONALITY_ALLOWANCE = 1e-24

# Declared source-state counterparts of the activity arms. ``advance_workspace``
# accepts exactly one source control: ``source_enabled``, which zeroes the
# heartbeat's kick allowance, and the operator's kick returns the state unchanged
# for a non-positive allowance. What that leaves running is declared in the
# receipt's ``source_control`` block, and what it disables is declared there too;
# no further component can be switched off independently through this surface.
# Each counterpart is declared from its baseline arm, so the written items, the
# restart, the read frame and the read tick are identical by construction and the
# source flag is the only difference.
SOURCE_OFF_MULTI_ITEM_COUNTS: tuple[int, ...] = (2, 4)
SOURCE_OFF_BASELINE_ARMS: tuple[str, ...] = (
    "activity-no-restart",
    "restart-and-activity",
    "no-item-restart-and-activity",
)
SOURCE_OFF_SUFFIX = "-sources-off"

# Declared margins, each reported beside the measurement that is compared against
# it. ``SOURCE_OFF_MARGIN`` is the read-tick recovery difference the two source
# states must reach for the source state to count as changing the measurement.
# ``ALIGNMENT_ENERGY_MARGIN`` is the separation between the written direction's
# retention and the frame's total-energy retention that decides whether the
# direction falls faster or slower than the energy.
SOURCE_OFF_MARGIN = 0.01
ALIGNMENT_ENERGY_MARGIN = 0.05

BOUNDARY = (
    "Canonical-field numerical measurements in controlled conditions only: one "
    "bounded packet impulse written into the canonical page, bounded unrelated "
    "canonical activity with sources and heartbeat on together with declared "
    "counterparts of that activity whose only difference is the source state, and "
    "an exact workspace round trip for the restart leg. The restart leg is "
    "workspace-level restart identity, not owner-checkpoint identity for the "
    "written item, because no owner transition accepts a packet impulse. Nothing "
    "here demonstrates task-level memory utility, semantic content, retrieval by "
    "a consumer, owner-level checkpoint identity for a written item, or any "
    "advantage over alternative architectures."
)

DEFINITIONS = {
    "declared_item": (
        "one (path, component, flow_signal) write declaration lowered through "
        "the canonical packet impulse; the impulse writes momentum lanes only"
    ),
    "read_frame": (
        "the packet coefficients of the declared read frame path, shape "
        "[mode, channel] flattened row-major: the single space in which every "
        "share and every distance in this receipt is measured"
    ),
    "captured_write_direction": (
        "the unit image of one item's impulse in the read frame, captured by "
        "writing that item alone into a fresh canonical workspace at the "
        "declared budget; it fixes the direction every share projects onto, and "
        "the declared overlap matrix is the pairwise squared cosine of these "
        "directions, measured rather than assumed"
    ),
    "measured_deposit": (
        "the read-frame norm of one write's actual coefficient increment inside "
        "the arm, measured before and after that write; sequential writes into a "
        "non-empty field deposit a different amount than the isolated capture, "
        "and deposit_attenuation records measured over captured"
    ),
    "recovery_fraction": (
        "(c_read . u)^2 / |c_in_arm|^2 with u the item's captured write direction "
        "and |c_in_arm|^2 that write's measured deposit inside the arm: the share "
        "of the item's own deposit still lying along the written direction at "
        "read time; for a multi-item arm the arm figure is the minimum over its "
        "items"
    ),
    "write_time_alignment": (
        "the same share measured immediately after the writes: one means the "
        "write landed on its own captured direction, so any fall below one at "
        "read time is what restart and activity did"
    ),
    "control_share": (
        "the same share of the written item's own measured deposit, projected "
        "onto a declared item direction the arm did not write: the write-A-read-B "
        "share, directly comparable with the item's own recovery fraction"
    ),
    "background_alignment": (
        "for every declared item, (c_read . u)^2 / |c_captured|^2 in that item's "
        "own isolated captured deposit; for items the arm did write this restates "
        "the recovery fraction in captured units, and for the no-item arm it is "
        "the whole readout: what the field's own activity reports along each "
        "declared direction in units of the deposit that would have been written"
    ),
    "total_packet_energy_ratio": (
        "|c_read|^2 / |c_pre_activity|^2 in the read frame, where c_pre_activity "
        "is measured after the write and the restart and before the unrelated "
        "activity; it is null when the arm starts from a zero-energy field, as "
        "the no-item arm does"
    ),
    "distance_from_pre_activity": (
        "||c_read - c_pre_activity|| in the read frame, with the same quantity "
        "relative to |c_pre_activity|; the no-item arm reports the same distance "
        "so activity drift is separable from item decay"
    ),
    "unrelated_activity": (
        "advance_workspace calls with source_enabled and the canonical heartbeat "
        "on, one call per declared sample gap, at the declared ready demand; the "
        "field's own activity coordinate and the advance receipt are recorded"
    ),
    "source_state": (
        "the declared value of advance_workspace's source_enabled for the "
        "unrelated activity: the baseline arms declare it on and each declared "
        "counterpart arm declares it off, which zeroes the heartbeat's kick "
        "allowance and nothing else; the source_control block declares what that "
        "disables, what keeps running, and which component cannot be switched off "
        "independently through this surface, with the measured positive heartbeat "
        "work and phase clocks of both states beside it"
    ),
    "source_contrast": (
        "the read-tick figure of a declared activity arm minus the same figure of "
        "its declared source-off counterpart: (c_read . u)^2 / |c_in_arm|^2 for "
        "the recovery pairs, identical by construction in write budget, written "
        "items, restart, read frame and read tick, and reported beside the "
        "declared source-off margin"
    ),
    "alignment_versus_energy": (
        "for one activity arm, the written direction's retention beside the read "
        "frame's total-energy retention over the same advance: the retention "
        "series are the declared headline item's share of its own measured "
        "deposit and the per-tick packet energy, each divided by its value before "
        "the activity; the two are compared at the read tick against the declared "
        "margin, and the direction falls faster than the energy when its "
        "retention is the lower of the two by more than that margin"
    ),
    "restart": (
        "ResonantWorkspace.as_dict -> ResonantWorkspace.from_dict, with the state "
        "digest and the page digest compared before and after; the identity "
        "reported is workspace-level restart identity"
    ),
    "cross_item_confusion": (
        "in a multi-item arm, the share of item i's measured deposit lying along "
        "item j's captured direction, (c_read . u_j)^2 / |c_in_arm_i|^2; the "
        "off-diagonal entries are the write-A-read-B interference proxy in deposit "
        "units and the diagonal entries are the per-item recovery fractions"
    ),
    "declared_frame_energy_fraction": (
        "in a multi-item arm, the fractions (c_read . u_j)^2 / sum_j' "
        "(c_read . u_j')^2 of the read packet's projection onto the declared item "
        "frame: the diagonal entries are the written items' shares of that "
        "projection and the entries on directions the arm did not write are the "
        "interference and leakage proxy, comparable across items because the "
        "directions are orthogonal within the declared allowance"
    ),
    "distinguishable_from_control": (
        "recovery_fraction exceeds control_share by at least the declared margin; "
        "reported both on deposit shares and on shares of the current read packet "
        "energy, which are directly comparable fractions because the declared item "
        "directions are orthogonal to the declared allowance"
    ),
    "item_direction_orthogonality_allowance": (
        "the declared maximum squared cosine allowed between two declared item "
        "directions for them to count as orthogonal; the measured maximum is "
        "reported beside it"
    ),
    "owner_probe": (
        "a bounded deterministic production-owner setup in a temporary home: "
        "advance, configure one chart, admit declared observations, prepare one "
        "query, restart, and read the prepared query back, recording whether the "
        "owner checkpoint preserves the canonical workspace and whether the "
        "prepared-query path addresses a written packet path"
    ),
}


@dataclass(frozen=True)
class ItemSpec:
    """One declared item: a bounded packet impulse at a declared scale and position."""

    name: str
    path: str
    component: str
    flow_signal: tuple[float, float]


# One root scale item, one root detail item, then node details down to width 7.
# The root scale image is orthogonal to every node detail image, and distinct
# node details are orthogonal by the Haar construction, so the eight declared
# items carry eight distinct directions in the read frame.
ITEM_SPECS: tuple[ItemSpec, ...] = (
    ItemSpec("root-scale", "", "scale", (1.0, 0.0)),
    ItemSpec("root-detail", "", "detail", (1.0, 0.0)),
    ItemSpec("left-detail", "L", "detail", (1.0, 0.0)),
    ItemSpec("right-detail", "R", "detail", (1.0, 0.0)),
    ItemSpec("left-left-detail", "LL", "detail", (1.0, 0.0)),
    ItemSpec("left-right-detail", "LR", "detail", (1.0, 0.0)),
    ItemSpec("right-left-detail", "RL", "detail", (1.0, 0.0)),
    ItemSpec("right-right-detail", "RR", "detail", (1.0, 0.0)),
)

# The headline item is written on the declared packet path at the coarsest
# scale; the control direction is a different scale at a different position.
HEADLINE_ITEM_INDEX = 0
CONTROL_ITEM_INDEX = 2


@dataclass(frozen=True)
class DurabilityConfig:
    """Declared measurement settings; every number in the receipt derives from these."""

    read_frame_path: str = READ_FRAME_PATH
    headline_item_index: int = HEADLINE_ITEM_INDEX
    control_item_index: int = CONTROL_ITEM_INDEX
    write_budget: float = 1e-3
    activity_ticks: int = 64
    activity_samples: tuple[int, ...] = (8, 16, 32, 64)
    activity_demand: float = 0.0
    source_enabled: bool = True
    multi_item_counts: tuple[int, ...] = (2, 4, 8)
    control_margin: float = 0.05
    owner_probe_ticks: int = 64
    owner_probe_observations: int = 4
    owner_probe_query_input: float = 1.75

    def __post_init__(self) -> None:
        if not self.activity_samples:
            raise ValueError("activity samples are required")
        if sorted(self.activity_samples) != list(self.activity_samples):
            raise ValueError("activity samples must be increasing")
        if self.activity_ticks != max(self.activity_samples):
            raise ValueError("the declared activity horizon must be the last sample")
        if not 0.0 < float(self.write_budget) <= 1.0:
            raise ValueError("write_budget must lie in (0,1]")
        if not 0.0 <= float(self.activity_demand) <= 1.0:
            raise ValueError("activity demand must lie in [0,1]")
        if not self.multi_item_counts or any(
            count < 2 or count > len(ITEM_SPECS) for count in self.multi_item_counts
        ):
            raise ValueError("multi-item counts must lie in [2, declared item count]")
        if sorted(set(self.multi_item_counts)) != list(self.multi_item_counts):
            raise ValueError("multi-item counts must be strictly increasing")
        for name in ("headline_item_index", "control_item_index"):
            index = int(getattr(self, name))
            if not 0 <= index < len(ITEM_SPECS):
                raise ValueError(f"{name} is outside the declared item list")
        if self.headline_item_index == self.control_item_index:
            raise ValueError("the headline item and the control item must differ")
        if float(self.control_margin) < 0.0:
            raise ValueError("the control margin cannot be negative")
        if int(self.owner_probe_observations) < 2:
            raise ValueError("the owner probe needs at least two observations")
        if not self.source_enabled:
            raise ValueError(
                "the baseline activity arms declare sources on and the declared "
                "source-off counterparts are their complement, so source_enabled "
                "must stay true for the declared pairing to hold"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "read_frame_path": self.read_frame_path,
            "headline_item_index": self.headline_item_index,
            "control_item_index": self.control_item_index,
            "write_budget": self.write_budget,
            "activity_ticks": self.activity_ticks,
            "activity_samples": list(self.activity_samples),
            "activity_demand": self.activity_demand,
            "source_enabled": self.source_enabled,
            "multi_item_counts": list(self.multi_item_counts),
            "control_margin": self.control_margin,
            "owner_probe_ticks": self.owner_probe_ticks,
            "owner_probe_observations": self.owner_probe_observations,
            "owner_probe_query_input": self.owner_probe_query_input,
        }


@dataclass(frozen=True)
class Arm:
    """One declared arm: which items are written, whether it restarts, whether it
    works, and which source state the advance declares."""

    name: str
    item_indices: tuple[int, ...]
    restart: bool
    activity: bool
    sources: bool = True


def source_off_arm_name(name: str) -> str:
    """The declared name of a baseline activity arm's source-off counterpart."""

    return f"{name}{SOURCE_OFF_SUFFIX}"


def source_off_baseline_names(config: DurabilityConfig) -> tuple[str, ...]:
    """The declared activity arms whose source-off counterparts are declared.

    A declared `k` without a matching multi-item arm in this configuration has no
    counterpart to be the complement of, so the declared baseline arm list is the
    requested names narrowed to the arms this configuration declares.
    """

    return SOURCE_OFF_BASELINE_ARMS + tuple(
        f"restart-and-activity-k{count}"
        for count in SOURCE_OFF_MULTI_ITEM_COUNTS
        if count in config.multi_item_counts
    )


def arm_declarations(config: DurabilityConfig) -> tuple[Arm, ...]:
    headline = (config.headline_item_index,)
    arms = [
        Arm("immediate", headline, False, False),
        Arm("activity-no-restart", headline, False, True, config.source_enabled),
        Arm("restart-no-activity", headline, True, False),
        Arm(
            "restart-and-activity",
            headline,
            True,
            True,
            config.source_enabled,
        ),
        Arm(
            "control-item-restart-and-activity",
            (config.control_item_index,),
            True,
            True,
            config.source_enabled,
        ),
        Arm("no-item-restart-and-activity", (), True, True, config.source_enabled),
    ]
    for count in config.multi_item_counts:
        indices = tuple(range(count))
        arms.append(Arm(f"restart-only-k{count}", indices, True, False))
        arms.append(
            Arm(
                f"restart-and-activity-k{count}",
                indices,
                True,
                True,
                config.source_enabled,
            )
        )
    declared = {arm.name: arm for arm in arms}
    for name in source_off_baseline_names(config):
        baseline = declared[name]
        if not baseline.activity:
            raise ValueError(
                f"declared source-off baseline {name!r} advances no activity, so "
                "its source state would not be observable"
            )
        arms.append(
            Arm(
                source_off_arm_name(name),
                baseline.item_indices,
                baseline.restart,
                baseline.activity,
                sources=not baseline.sources,
            )
        )
    return tuple(arms)


def canonical_json(value: Any) -> str:
    """Canonical JSON text for digesting: sorted keys, no insignificant space."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def receipt_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def page_sha256(workspace: ResonantWorkspace) -> str:
    """Digest of the canonical field page bytes alone (no profile descriptor)."""

    return hashlib.sha256(workspace.page_bytes).hexdigest()


def direction_sha256(direction: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(direction, dtype="<f8").tobytes()).hexdigest()


def read_frame(workspace: ResonantWorkspace, path: str) -> np.ndarray:
    """The declared read frame: flattened packet coefficients of the whole packet."""

    packet = analyze_helical_packet(workspace, path=path)
    return np.asarray(packet["coefficients"], dtype=np.float64).reshape(-1)


def squared_norm(vector: np.ndarray) -> float:
    return float(np.dot(vector, vector))


def share_along(vector: np.ndarray, direction: np.ndarray, deposited: float) -> float:
    """(c . u)^2 / deposited: the share of a reference energy along one direction."""

    if deposited <= 0.0:
        raise ValueError("share normalization requires a positive deposited energy")
    projection = float(np.dot(vector, direction))
    return (projection * projection) / deposited


def write_item(
    workspace: ResonantWorkspace, spec: ItemSpec, budget: float
) -> tuple[ResonantWorkspace, dict[str, Any]]:
    successor, receipt = apply_helical_packet_impulse(
        workspace,
        path=spec.path,
        component=spec.component,
        flow_signal=list(spec.flow_signal),
        work_budget=budget,
        evidence_tick=workspace.evidence_tick,
        event_kind=EVENT_KIND,
    )
    compact = {
        key: receipt[key]
        for key in (
            "schema",
            "accepted",
            "event_kind",
            "basis_sha256",
            "path",
            "component",
            "support",
            "mode",
            "flow_signal",
            "flow_channels",
            "requested_work",
            "applied_work",
            "impulse_amount",
            "balance_defect",
            "energy_roundoff_allowance",
            "source_state_sha256",
            "state_sha256",
        )
    }
    return successor, compact


def capture_items(
    config: DurabilityConfig, profile: ResonantProfile
) -> list[dict[str, Any]]:
    """Capture each declared item's write direction in the read frame from a fresh field."""

    captures: list[dict[str, Any]] = []
    for spec in ITEM_SPECS:
        workspace, receipt = write_item(initial_workspace(profile), spec, config.write_budget)
        vector = read_frame(workspace, config.read_frame_path)
        norm = float(np.linalg.norm(vector))
        if norm <= 0.0:
            raise RuntimeError(f"declared item {spec.name!r} deposited nothing in the read frame")
        direction = vector / norm
        captures.append(
            {
                "name": spec.name,
                "spec": spec,
                "path": spec.path,
                "component": spec.component,
                "flow_signal": list(spec.flow_signal),
                "scale_width": int(receipt["support"]["stop"]) - int(receipt["support"]["start"]),
                "support": receipt["support"],
                "mode": receipt["mode"],
                "requested_work": receipt["requested_work"],
                "applied_work": receipt["applied_work"],
                "impulse_amount": receipt["impulse_amount"],
                "balance_defect": receipt["balance_defect"],
                "energy_roundoff_allowance": receipt["energy_roundoff_allowance"],
                "deposited_energy": norm * norm,
                "direction": direction,
                "direction_sha256": direction_sha256(direction),
                "capture_state_sha256": workspace.state_sha256,
                "capture_page_sha256": page_sha256(workspace),
            }
        )
    return captures


def overlap_matrix(captures: Sequence[Mapping[str, Any]]) -> list[list[float]]:
    """Pairwise squared cosine of the captured directions, measured not assumed."""

    return [
        [
            float(np.dot(left["direction"], right["direction"])) ** 2
            for right in captures
        ]
        for left in captures
    ]


def restart_workspace(workspace: ResonantWorkspace) -> tuple[ResonantWorkspace, dict[str, Any]]:
    """Round-trip the canonical workspace through its own descriptor form."""

    before_state, before_page = workspace.state_sha256, page_sha256(workspace)
    restored = ResonantWorkspace.from_dict(workspace.as_dict())
    after_state, after_page = restored.state_sha256, page_sha256(restored)
    report = {
        "applied": True,
        "path": "resonant-workspace-as-dict-round-trip",
        "state_sha256_before": before_state,
        "state_sha256_after": after_state,
        "state_digest_identical": before_state == after_state,
        "page_sha256_before": before_page,
        "page_sha256_after": after_page,
        "page_digest_identical": before_page == after_page,
    }
    if not report["state_digest_identical"] or not report["page_digest_identical"]:
        raise RuntimeError("the canonical workspace round trip changed the field state")
    return restored, report


def activity_rows(
    workspace: ResonantWorkspace,
    config: DurabilityConfig,
    captures: Sequence[Mapping[str, Any]],
    written: Mapping[str, float],
    control_index: int | None,
    *,
    source_enabled: bool,
) -> tuple[ResonantWorkspace, list[dict[str, Any]], dict[str, Any]]:
    """Advance the declared unrelated activity, reading the frame at each declared sample."""

    rows: list[dict[str, Any]] = []
    current = workspace
    previous = 0
    dissipated = 0.0
    heartbeat_work = 0.0
    balance_defect = 0.0
    headline = ITEM_SPECS[config.headline_item_index].name
    reference = written.get(headline)
    for tick in config.activity_samples:
        current, advance = advance_workspace(
            current,
            ticks=int(tick) - previous,
            demand=config.activity_demand,
            source_enabled=bool(source_enabled),
        )
        previous = int(tick)
        vector = read_frame(current, config.read_frame_path)
        dissipated += float(advance["dissipated_work"])
        heartbeat_work += float(advance["positive_heartbeat_work"])
        balance_defect += float(advance["balance_defect"])
        rows.append(
            {
                "tick": int(tick),
                "field_ticks": int(current.field_ticks),
                "activity": float(current.activity),
                "heartbeat_phase": float(current.heartbeat_phase),
                "breath_phase": float(current.breath_phase),
                "dissipated_work": float(advance["dissipated_work"]),
                "positive_heartbeat_work": float(advance["positive_heartbeat_work"]),
                "residual_work": float(advance["residual_work"]),
                "operator_applications": int(advance["operator_applications"]),
                "source_enabled": bool(advance["source_enabled"]),
                "state_sha256": current.state_sha256,
                "page_sha256": page_sha256(current),
                "packet_energy": squared_norm(vector),
                "written_item_share": (
                    None
                    if reference is None
                    else share_along(
                        vector,
                        captures[config.headline_item_index]["direction"],
                        reference,
                    )
                ),
                "control_share": (
                    None
                    if control_index is None or reference is None
                    else share_along(vector, captures[control_index]["direction"], reference)
                ),
                "background_alignment": {
                    capture["name"]: share_along(
                        vector, capture["direction"], capture["deposited_energy"]
                    )
                    for capture in captures
                },
            }
        )
    summary = {
        "ticks": config.activity_ticks,
        "demand": config.activity_demand,
        "source_enabled": bool(source_enabled),
        "samples": list(config.activity_samples),
        "dissipated_work_total": dissipated,
        "positive_heartbeat_work_total": heartbeat_work,
        "balance_defect_total": balance_defect,
        "field_ticks": int(current.field_ticks),
        "activity": float(current.activity),
        "heartbeat_phase": float(current.heartbeat_phase),
        "breath_phase": float(current.breath_phase),
    }
    return current, rows, summary


def control_direction_index(config: DurabilityConfig, item_indices: Sequence[int]) -> int | None:
    """The declared control direction: an item the arm did not write, or none."""

    written = set(item_indices)
    for index in (config.control_item_index, config.headline_item_index):
        if index not in written:
            return index
    return None


def arm_readout(
    config: DurabilityConfig,
    captures: Sequence[Mapping[str, Any]],
    workspace: ResonantWorkspace,
    item_indices: Sequence[int],
    deposits: Mapping[str, float],
    write_shares: Mapping[str, float],
    pre_vector: np.ndarray,
) -> dict[str, Any]:
    """Every declared share and distance for one arm at its read tick."""

    vector = read_frame(workspace, config.read_frame_path)
    energy = squared_norm(vector)
    pre_energy = squared_norm(pre_vector)
    background = {
        capture["name"]: share_along(vector, capture["direction"], capture["deposited_energy"])
        for capture in captures
    }
    current_energy_shares = {
        capture["name"]: background[capture["name"]]
        * capture["deposited_energy"]
        / energy
        if energy > 0.0
        else 0.0
        for capture in captures
    }
    owned = [ITEM_SPECS[index].name for index in item_indices]
    own_shares = {
        capture["name"]: share_along(vector, capture["direction"], deposits[capture["name"]])
        for capture in (captures[index] for index in item_indices)
    }
    control_index = control_direction_index(config, item_indices)
    control = None if control_index is None else captures[control_index]["name"]
    control_share = None
    control_current = None
    if control_index is not None and owned:
        reference = deposits[owned[0]]
        control_share = share_along(vector, captures[control_index]["direction"], reference)
        control_current = (
            share_along(vector, captures[control_index]["direction"], reference)
            * reference
            / energy
            if energy > 0.0
            else 0.0
        )
    cross: dict[str, dict[str, float]] = {}
    frame_fraction: dict[str, float] = {}
    if len(item_indices) > 1:
        frame_total = sum(
            float(np.dot(vector, capture["direction"])) ** 2 for capture in captures
        )
        frame_fraction = {
            capture["name"]: (
                float(np.dot(vector, capture["direction"])) ** 2 / frame_total
                if frame_total > 0.0
                else 0.0
            )
            for capture in captures
        }
        for index in item_indices:
            capture = captures[index]
            cross[capture["name"]] = {
                other["name"]: share_along(vector, other["direction"], deposits[capture["name"]])
                for other in captures
            }
    recovery = min(own_shares.values()) if own_shares else None
    if not owned:
        recovery_current = None
    elif energy > 0.0:
        recovery_current = min(
            share_along(vector, captures[index]["direction"], deposits[ITEM_SPECS[index].name])
            * deposits[ITEM_SPECS[index].name]
            / energy
            for index in item_indices
        )
    else:
        recovery_current = 0.0
    return {
        "state_sha256": workspace.state_sha256,
        "page_sha256": page_sha256(workspace),
        "packet_energy": energy,
        "total_packet_energy_ratio": energy / pre_energy if pre_energy > 0.0 else None,
        "distance_from_pre_activity": float(np.linalg.norm(vector - pre_vector)),
        "distance_relative_to_pre_activity": (
            float(np.linalg.norm(vector - pre_vector)) / float(np.linalg.norm(pre_vector))
            if pre_energy > 0.0
            else None
        ),
        "written_items": owned,
        "write_time_alignment": dict(write_shares),
        "own_shares": own_shares,
        "background_alignment": background,
        "background_alignment_of_current_packet_energy": current_energy_shares,
        "control_item": control,
        "control_share": control_share,
        "control_share_of_current_packet_energy": control_current,
        "control_background_share": (
            None if control is None else background[control]
        ),
        "recovery_fraction": recovery,
        "recovery_fraction_of_current_packet_energy": recovery_current,
        "recovery_fraction_definition": (
            "minimum over written items" if len(item_indices) > 1 else "the written item"
        ),
        "distinguishable_from_control": (
            None
            if recovery is None or control_share is None
            else bool(recovery - control_share >= config.control_margin)
        ),
        "distinguishable_from_control_of_current_packet_energy": (
            None
            if recovery_current is None or control_current is None
            else bool(recovery_current - control_current >= config.control_margin)
        ),
        "cross_item_confusion": cross,
        "declared_frame_energy_fraction": frame_fraction,
        "declared_frame_projection_energy": (
            sum(float(np.dot(vector, capture["direction"])) ** 2 for capture in captures)
            if len(item_indices) > 1
            else None
        ),
        "declared_frame_projection_fraction_of_packet_energy": (
            sum(float(np.dot(vector, capture["direction"])) ** 2 for capture in captures) / energy
            if len(item_indices) > 1 and energy > 0.0
            else None
        ),
    }


def run_arm(
    config: DurabilityConfig,
    profile: ResonantProfile,
    captures: Sequence[Mapping[str, Any]],
    arm: Arm,
) -> dict[str, Any]:
    """Write the arm's items, apply the declared restart and activity, then read."""

    workspace = initial_workspace(profile)
    writes: list[dict[str, Any]] = []
    deposits: dict[str, float] = {}
    for index in arm.item_indices:
        spec = ITEM_SPECS[index]
        before = read_frame(workspace, config.read_frame_path)
        workspace, receipt = write_item(workspace, spec, config.write_budget)
        after = read_frame(workspace, config.read_frame_path)
        writes.append({"item": spec.name, **receipt})
        deposits[spec.name] = squared_norm(after - before)
    post_write_vector = read_frame(workspace, config.read_frame_path)
    write_shares = {
        ITEM_SPECS[index].name: share_along(
            post_write_vector,
            captures[index]["direction"],
            deposits[ITEM_SPECS[index].name],
        )
        for index in arm.item_indices
    }
    write_state = workspace.state_sha256
    restart_report: dict[str, Any] = {"applied": False}
    if arm.restart:
        workspace, restart_report = restart_workspace(workspace)
    pre_vector = read_frame(workspace, config.read_frame_path)
    pre_activity = {
        "state_sha256": workspace.state_sha256,
        "page_sha256": page_sha256(workspace),
        "packet_energy": squared_norm(pre_vector),
        "field_ticks": int(workspace.field_ticks),
        "activity": float(workspace.activity),
        "evidence_tick": int(workspace.evidence_tick),
    }
    if arm.activity:
        workspace, rows, activity_summary = activity_rows(
            workspace,
            config,
            captures,
            deposits,
            control_direction_index(config, arm.item_indices),
            source_enabled=arm.sources,
        )
    else:
        rows = []
        activity_summary = {
            "ticks": 0,
            "demand": config.activity_demand,
            "source_enabled": bool(arm.sources),
            "samples": [],
            "dissipated_work_total": 0.0,
            "positive_heartbeat_work_total": 0.0,
            "balance_defect_total": 0.0,
            "field_ticks": int(workspace.field_ticks),
            "activity": float(workspace.activity),
            "heartbeat_phase": float(workspace.heartbeat_phase),
            "breath_phase": float(workspace.breath_phase),
        }
    readout = arm_readout(
        config, captures, workspace, arm.item_indices, deposits, write_shares, pre_vector
    )
    return {
        "arm": arm.name,
        "declared": {
            "written_items": [ITEM_SPECS[index].name for index in arm.item_indices],
            "restart": bool(arm.restart),
            "activity": bool(arm.activity),
            "activity_ticks": config.activity_ticks if arm.activity else 0,
            "activity_demand": config.activity_demand,
            "source_enabled": bool(arm.sources),
            "write_budget": config.write_budget,
            "read_frame_path": config.read_frame_path,
            "restart_path": "resonant-workspace-as-dict-round-trip"
            if arm.restart
            else "not-applied",
        },
        "writes": writes,
        "measured_deposit_energy": deposits,
        "deposit_attenuation": {
            name: deposits[name] / captures[index]["deposited_energy"]
            for index, name in ((index, ITEM_SPECS[index].name) for index in arm.item_indices)
        },
        "post_write_readout_shares": write_shares,
        "write_state_sha256": write_state,
        "restart": restart_report,
        "pre_activity": pre_activity,
        "activity": activity_summary,
        "activity_rows": rows,
        "readout": readout,
    }


def declared_block(
    config: DurabilityConfig, profile: ResonantProfile, captures: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    frame = analyze_helical_packet(initial_workspace(profile), path=config.read_frame_path)
    overlap = overlap_matrix(captures)
    off_diagonal = [
        overlap[left][right]
        for left in range(len(captures))
        for right in range(len(captures))
        if left != right
    ]
    return {
        "schema": SCHEMA,
        "read_frame": {
            "path": config.read_frame_path,
            "support": frame["support"],
            "port_count": int(frame["port_count"]),
            "mode_count": len(frame["modes"]),
            "coefficient_shape": [len(frame["modes"]), len(frame["channels"])],
            "coefficient_count": int(len(frame["modes"]) * len(frame["channels"])),
            "channels": list(frame["channels"]),
            "basis": frame["basis"],
            "basis_sha256": frame["basis_sha256"],
        },
        "declared_items": [
            {
                key: value
                for key, value in capture.items()
                if key not in {"spec", "direction"}
            }
            for capture in captures
        ],
        "item_direction_overlap_squared_cosine": overlap,
        "orthogonality_allowance": ORTHOGONALITY_ALLOWANCE,
        "item_directions_mutually_orthogonal": all(
            value <= ORTHOGONALITY_ALLOWANCE for value in off_diagonal
        ),
        "maximum_off_diagonal_overlap": max(off_diagonal) if off_diagonal else 0.0,
        "declared_arms": [
            {
                "arm": arm.name,
                "written_items": [ITEM_SPECS[index].name for index in arm.item_indices],
                "restart": arm.restart,
                "activity": arm.activity,
                "source_enabled": bool(arm.sources),
            }
            for arm in arm_declarations(config)
        ],
        "control_item": ITEM_SPECS[config.control_item_index].name,
        "headline_item": ITEM_SPECS[config.headline_item_index].name,
        "position_channels_drivable": POSITION_CHANNELS_DRIVABLE,
        "config": config.as_dict(),
        "definitions": DEFINITIONS,
    }


def owner_restart_probe(config: DurabilityConfig) -> dict[str, Any]:
    """Attempt the production owner checkpoint and prepared-query paths under a bounded setup."""

    from cassi_field_atlas import RelationChart, VariableSpec, canonical_json_bytes
    from cassi_field_owner import FieldIntelligenceOwner, SourceInput

    def observation(name: str, values: Mapping[str, float]) -> Any:
        return SourceInput(
            source_id=name,
            content=canonical_json_bytes(dict(values)),
            media_type="application/json",
            codec="utf-8",
            observed_timestamp=name,
            scope="durability-probe",
            claim_category="controlled-measurement",
            fidelity="exact-record",
            labels=("durability-probe",),
        )

    home = Path(tempfile.mkdtemp(prefix="cassi-durability-owner-"))
    owner = FieldIntelligenceOwner(home)
    try:
        owner.advance(operation_id="durability:probe:advance", ticks=config.owner_probe_ticks)
        for name in ("bias", "input", "output"):
            variable = (
                VariableSpec(name, kind="constant", constant=1.0)
                if name == "bias"
                else VariableSpec(name, lower=-40.0, upper=40.0)
            )
            owner.configure_variable(f"durability:probe:variable:{name}", variable)
        owner.configure_chart(
            "durability:probe:relation",
            RelationChart.empty(
                chart_id="durability-gain",
                scope=("bias", "input", "output"),
                ridge=1e-5,
                observation_norm_bound=100.0,
                prior_mass=1e-3,
            ),
        )
        span = max(1, int(config.owner_probe_observations) // 2)
        observed_inputs = tuple(
            float(value) for value in range(-span, 0)
        ) + tuple(float(value) for value in range(1, span + 1))
        for index, value in enumerate(observed_inputs):
            values = {"bias": 1.0, "input": value, "output": 2.0 * value}
            owner.admit_observation(
                operation_id=f"durability:probe:learn:{index}",
                source=observation(f"durability-measurement:{index}", values),
                values=values,
                context={},
            )
        thought = owner.think(
            operation_id="durability:probe:think",
            observed={"input": config.owner_probe_query_input},
            requested=("output",),
        )
        prepared_id = str(thought["query_id"])
        committed_workspace = owner.state.resonant_workspace
        digest_before = committed_workspace.state_sha256
        tick_before = int(committed_workspace.field_ticks)
        generation_before = int(owner.state.generation)
        owner.close()
        owner = FieldIntelligenceOwner(home)
        restored = owner.state.resonant_workspace
        prepared = owner.query(query_id=prepared_id)
        return {
            "status": "reachable",
            "checkpoint_ticks": config.owner_probe_ticks,
            "observation_count": len(observed_inputs),
            "committed_generation": generation_before,
            "workspace_state_sha256_preserved_across_restart": restored.state_sha256 == digest_before,
            "workspace_field_ticks_preserved_across_restart": int(restored.field_ticks) == tick_before,
            "prepared_query_status": str(thought["status"]),
            "prepared_query_restart_stable": prepared["branches"] == thought["branches"],
            "prepared_query_addressed_variables": sorted(thought["branches"][0]["values"])
            if thought.get("branches")
            else [],
            "prepared_query_addressed_written_packet": False,
            "packet_impulse_transition_available": False,
            "reason": (
                "the owner transition surface exposes no packet-impulse operation "
                "(advance accepts ticks and source_enabled only) and configures no "
                "variable-to-port binding, so a prepared owner query resolves declared "
                "variables through chart evidence rather than the written packet path; "
                "an owner-checkpoint arm carrying the item would have to hand the owner "
                "an externally modified workspace, which bypasses the owner write path"
            ),
        }
    finally:
        try:
            owner.close()
        finally:
            shutil.rmtree(home, ignore_errors=True)


def restart_identity_block(
    config: DurabilityConfig, profile: ResonantProfile
) -> dict[str, Any]:
    """Identity of both restart paths for one written item, measured rather than assumed."""

    workspace, _receipt = write_item(initial_workspace(profile), ITEM_SPECS[config.headline_item_index], config.write_budget)
    written_state = workspace.state_sha256
    written_page = page_sha256(workspace)
    written_frame = read_frame(workspace, config.read_frame_path)
    restored, report = restart_workspace(workspace)
    restored_frame = read_frame(restored, config.read_frame_path)
    return {
        "declared_item": ITEM_SPECS[config.headline_item_index].name,
        "restart_path": report["path"],
        "write_state_sha256": written_state,
        "restart_state_sha256": report["state_sha256_after"],
        "state_digest_identical": report["state_digest_identical"],
        "page_digest_identical": report["page_digest_identical"],
        "read_frame_bit_identical": bool(np.array_equal(written_frame, restored_frame)),
        "read_frame_max_abs_difference": float(np.max(np.abs(written_frame - restored_frame))),
        "owner_checkpoint_carries_written_item": False,
    }


def source_control_block(arms: Mapping[str, Any]) -> dict[str, Any]:
    """What the declared source flag disables, what it leaves running, and the evidence."""

    measured = {
        name: {
            "declared_source_enabled": arm["declared"]["source_enabled"],
            "advance_source_enabled": arm["activity"]["source_enabled"],
            "positive_heartbeat_work_total": arm["activity"]["positive_heartbeat_work_total"],
            "field_ticks": arm["activity"]["field_ticks"],
            "heartbeat_phase_at_read": arm["activity"]["heartbeat_phase"],
            "breath_phase_at_read": arm["activity"]["breath_phase"],
        }
        for name, arm in arms.items()
        if arm["declared"]["activity"]
    }
    return {
        "declared": {
            "flag": "advance_workspace(..., source_enabled=<arm source state>)",
            "disabled": [
                "the canonical heartbeat's positive work injection: the advance "
                "forces the kick allowance to 0.0, and the operator's kick returns "
                "its input unchanged for a non-positive allowance, so a source-off "
                "arm measures positive_heartbeat_work_total of exactly 0.0",
            ],
            "still_active": [
                "the heartbeat phase clock and the breath phase clock, which advance "
                "from the tick count alone and are therefore identical in both "
                "source states at every sampled tick",
                "the body's own integration step, including its damping, its "
                "nonlinear coupling and its numerical dissipation",
                "the declared ready demand, which relaxes the field's activity "
                "coordinate toward activity_demand (0.0 here, so it drives nothing "
                "in either state)",
            ],
            "not_independently_disableable": [
                "source_enabled is the only downstream source control this surface "
                "declares: advance_workspace exposes no heartbeat-off, phase-clock-off "
                "or damping-off flag, so the heartbeat clock, the breath modulation of "
                "mobility and the body's own dissipation cannot be switched off "
                "independently while the background ticks advance, and neither can the "
                "declared impulse be applied without an advance",
            ],
            "measured_evidence": (
                "the measured block reports, per activity arm, the source state the "
                "advance receipt returned, the accumulated positive heartbeat work and "
                "the two phase clocks at the read tick; the source-off arms read "
                "positive_heartbeat_work_total 0.0 with phases identical to their "
                "source-on counterparts"
            ),
        },
        "measured": measured,
        "smallest_positive_source_work": min(
            (
                value["positive_heartbeat_work_total"]
                for value in measured.values()
                if value["positive_heartbeat_work_total"] > 0.0
            ),
            default=None,
        ),
        "largest_source_off_source_work": max(
            (
                value["positive_heartbeat_work_total"]
                for value in measured.values()
                if not value["declared_source_enabled"]
            ),
            default=None,
        ),
    }


def alignment_versus_energy_block(
    config: DurabilityConfig, arms: Mapping[str, Any]
) -> dict[str, Any]:
    """Retention of the written direction beside retention of the frame's total energy."""

    headline = ITEM_SPECS[config.headline_item_index].name
    per_arm: dict[str, Any] = {}
    for name, arm in arms.items():
        if not arm["declared"]["activity"] or headline not in arm["declared"]["written_items"]:
            continue
        write_share = float(arm["post_write_readout_shares"][headline])
        pre_energy = float(arm["pre_activity"]["packet_energy"])
        if write_share <= 0.0 or pre_energy <= 0.0:
            continue
        alignment_series = [
            {
                "tick": row["tick"],
                "alignment_retention": row["written_item_share"] / write_share,
                "energy_retention": row["packet_energy"] / pre_energy,
            }
            for row in arm["activity_rows"]
        ]
        read = alignment_series[-1]
        difference = read["alignment_retention"] - read["energy_retention"]
        per_arm[name] = {
            "read_tick": int(read["tick"]),
            "headline_item": headline,
            "write_time_share": write_share,
            "alignment_retention_at_read": read["alignment_retention"],
            "energy_retention_at_read": read["energy_retention"],
            "alignment_minus_energy": difference,
            "margin": ALIGNMENT_ENERGY_MARGIN,
            "falls_faster_than_energy": bool(difference <= -ALIGNMENT_ENERGY_MARGIN),
            "falls_slower_than_energy": bool(difference >= ALIGNMENT_ENERGY_MARGIN),
            "same_rate_as_energy": bool(abs(difference) < ALIGNMENT_ENERGY_MARGIN),
            "series": alignment_series,
        }
    return {
        "per_arm": per_arm,
        "margin": ALIGNMENT_ENERGY_MARGIN,
        "definition": DEFINITIONS["alignment_versus_energy"],
    }


def source_contrast_block(
    config: DurabilityConfig, arms: Mapping[str, Any]
) -> dict[str, Any]:
    """The declared source-on minus source-off figures and the alignment reading."""

    pairs: list[dict[str, Any]] = []
    for name in source_off_baseline_names(config):
        on = arms[name]
        off = arms[source_off_arm_name(name)]
        on_recovery = on["readout"]["recovery_fraction"]
        off_recovery = off["readout"]["recovery_fraction"]
        recovery_pair = on_recovery is not None and off_recovery is not None
        on_distance = float(on["readout"]["distance_from_pre_activity"])
        off_distance = float(off["readout"]["distance_from_pre_activity"])
        on_energy = on["readout"]["total_packet_energy_ratio"]
        off_energy = off["readout"]["total_packet_energy_ratio"]
        difference = (
            on_recovery - off_recovery if recovery_pair else on_distance - off_distance
        )
        pre_energy = float(on["pre_activity"]["packet_energy"])
        off_pre_energy = float(off["pre_activity"]["packet_energy"])
        pairs.append(
            {
                "arm": name,
                "sources_off_arm": source_off_arm_name(name),
                "written_items": on["declared"]["written_items"],
                "recovery_definition": on["readout"]["recovery_fraction_definition"],
                "read_tick": config.activity_ticks if on["declared"]["activity"] else 0,
                "contrast_figure": (
                    "recovery_fraction" if recovery_pair else "distance_from_pre_activity"
                ),
                "sources_on_recovery_fraction": on_recovery,
                "sources_off_recovery_fraction": off_recovery,
                "recovery_fraction_difference": (
                    None if not recovery_pair else difference
                ),
                "sources_on_total_packet_energy_ratio": on_energy,
                "sources_off_total_packet_energy_ratio": off_energy,
                "total_packet_energy_ratio_difference": (
                    None if on_energy is None or off_energy is None else on_energy - off_energy
                ),
                "sources_on_distance_from_pre_activity": on_distance,
                "sources_off_distance_from_pre_activity": off_distance,
                "difference": difference,
                "margin": SOURCE_OFF_MARGIN,
                "separated_by_margin": bool(abs(difference) >= SOURCE_OFF_MARGIN),
                "series": [
                    {
                        "tick": on_row["tick"],
                        "sources_on_written_item_share": on_row["written_item_share"],
                        "sources_off_written_item_share": off_row["written_item_share"],
                        "written_item_share_difference": (
                            None
                            if on_row["written_item_share"] is None
                            or off_row["written_item_share"] is None
                            else on_row["written_item_share"] - off_row["written_item_share"]
                        ),
                        "sources_on_energy_retention": (
                            None if pre_energy <= 0.0 else on_row["packet_energy"] / pre_energy
                        ),
                        "sources_off_energy_retention": (
                            None
                            if off_pre_energy <= 0.0
                            else off_row["packet_energy"] / off_pre_energy
                        ),
                    }
                    for on_row, off_row in zip(on["activity_rows"], off["activity_rows"])
                ],
            }
        )
    recovery_pairs = [row for row in pairs if row["contrast_figure"] == "recovery_fraction"]
    single = next(row for row in recovery_pairs if row["arm"] == "restart-and-activity")
    multi = {
        row["arm"]: row["recovery_fraction_difference"]
        for row in recovery_pairs
        if row["arm"].startswith("restart-and-activity-k")
    }
    minimum_multi = min(multi.values(), default=None)
    return {
        "declared_margin": SOURCE_OFF_MARGIN,
        "definition": DEFINITIONS["source_contrast"],
        "pairs": pairs,
        "single_item_arm": single["arm"],
        "single_item_difference": single["recovery_fraction_difference"],
        "single_item_separated_by_margin": single["separated_by_margin"],
        "single_item_without_restart_arm": "activity-no-restart",
        "single_item_without_restart_difference": next(
            row["recovery_fraction_difference"]
            for row in recovery_pairs
            if row["arm"] == "activity-no-restart"
        ),
        "multi_item_differences": multi,
        "minimum_multi_item_difference": minimum_multi,
        "minimum_multi_item_separated_by_margin": (
            None if minimum_multi is None else bool(abs(minimum_multi) >= SOURCE_OFF_MARGIN)
        ),
        "alignment_versus_energy": alignment_versus_energy_block(config, arms),
    }


def alignment_versus_energy_sentence(contrast: Mapping[str, Any]) -> str:
    """One plain sentence answering the alignment-versus-energy question for the source-off arm."""

    block = contrast["alignment_versus_energy"]
    off = block["per_arm"]["restart-and-activity-sources-off"]
    on = block["per_arm"]["restart-and-activity"]

    def direction(reading: Mapping[str, Any]) -> str:
        if reading["falls_faster_than_energy"]:
            return "faster than"
        if reading["falls_slower_than_energy"]:
            return "slower than"
        return "at the same rate as"

    return (
        f"With sources off the written direction's alignment falls {direction(off)} "
        f"the frame's total energy: alignment retention "
        f"{off['alignment_retention_at_read']!r} against energy retention "
        f"{off['energy_retention_at_read']!r} at tick {off['read_tick']}, a difference of "
        f"{off['alignment_minus_energy']!r} against the declared {block['margin']!r} margin. "
        f"With sources on it falls {direction(on)} the energy "
        f"({on['alignment_retention_at_read']!r} against {on['energy_retention_at_read']!r}, "
        f"difference {on['alignment_minus_energy']!r}), and the source state moves the read-tick "
        f"recovery by {contrast['single_item_difference']!r} against the declared "
        f"{contrast['declared_margin']!r} margin."
    )


def reading_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The headline measured numbers, in the order the questions were asked."""

    arms = body["arms"]
    return {
        "restart_identity": body["restart_identity"],
        "recovery_fraction_per_arm": {
            name: arm["readout"]["recovery_fraction"] for name, arm in arms.items()
        },
        "control_share_per_arm": {
            name: arm["readout"]["control_share"] for name, arm in arms.items()
        },
        "control_background_share_per_arm": {
            name: arm["readout"]["control_background_share"] for name, arm in arms.items()
        },
        "distinguishable_from_control_per_arm": {
            name: arm["readout"]["distinguishable_from_control"] for name, arm in arms.items()
        },
        "distinguishable_from_control_of_current_packet_energy_per_arm": {
            name: arm["readout"]["distinguishable_from_control_of_current_packet_energy"]
            for name, arm in arms.items()
        },
        "total_packet_energy_ratio_per_arm": {
            name: arm["readout"]["total_packet_energy_ratio"] for name, arm in arms.items()
        },
        "distance_from_pre_activity_per_arm": {
            name: arm["readout"]["distance_from_pre_activity"] for name, arm in arms.items()
        },
        "activity_series": {
            name: [
                {
                    "tick": row["tick"],
                    "written_item_share": row["written_item_share"],
                    "control_share": row["control_share"],
                    "packet_energy": row["packet_energy"],
                    "activity": row["activity"],
                }
                for row in arm["activity_rows"]
            ]
            for name, arm in arms.items()
            if arm["declared"]["activity"]
        },
        "multi_item_confusion": {
            name: {
                "written_items": arm["readout"]["written_items"],
                "own_shares": arm["readout"]["own_shares"],
                "minimum_recovery_fraction": arm["readout"]["recovery_fraction"],
                "maximum_off_diagonal_share": max(
                    (
                        value
                        for written, row in arm["readout"]["cross_item_confusion"].items()
                        for read, value in row.items()
                        if read != written
                    ),
                    default=0.0,
                ),
                "deposit_share_matrix": arm["readout"]["cross_item_confusion"],
                "declared_frame_energy_fraction": arm["readout"]["declared_frame_energy_fraction"],
                "unwritten_direction_energy_fraction_total": sum(
                    value
                    for read, value in arm["readout"]["declared_frame_energy_fraction"].items()
                    if read not in arm["readout"]["written_items"]
                ),
                "maximum_unwritten_direction_energy_fraction": max(
                    (
                        value
                        for read, value in arm["readout"]["declared_frame_energy_fraction"].items()
                        if read not in arm["readout"]["written_items"]
                    ),
                    default=0.0,
                ),
                "declared_frame_projection_fraction_of_packet_energy": arm["readout"][
                    "declared_frame_projection_fraction_of_packet_energy"
                ],
            }
            for name, arm in arms.items()
            if len(arm["declared"]["written_items"]) > 1
        },
        "owner_probe": body["owner_probe"],
        "source_control": body["source_control"],
        "source_contrast": body["source_contrast"],
        "source_off_alignment_sentence": alignment_versus_energy_sentence(
            body["source_contrast"]
        ),
    }


def measure(config: DurabilityConfig, profile: ResonantProfile | None = None) -> dict[str, Any]:
    """Run every declared arm and return the receipt body without its digest."""

    base = profile or ResonantProfile()
    captures = capture_items(config, base)
    arms = {
        arm.name: run_arm(config, base, captures, arm) for arm in arm_declarations(config)
    }
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": declared_block(config, base, captures),
        "restart_identity": restart_identity_block(config, base),
        "arms": arms,
        "source_control": source_control_block(arms),
        "source_contrast": source_contrast_block(config, arms),
        "owner_probe": owner_restart_probe(config),
    }
    body["reading"] = reading_block(body)
    body["boundary"] = BOUNDARY
    return body


def build_receipt(config: DurabilityConfig, profile: ResonantProfile | None = None) -> dict[str, Any]:
    body = measure(config, profile)
    return {**body, "receipt_digest": receipt_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("_diag/fractal-durability/exploration.json")
    )
    arguments = parser.parse_args()
    config = DurabilityConfig()
    started = perf_counter()
    receipt = build_receipt(config)
    elapsed = perf_counter() - started
    print(json.dumps(receipt["reading"], indent=1, sort_keys=True))
    print(json.dumps({"boundary": receipt["boundary"]}, indent=1, sort_keys=True))
    print(
        f"declared items: {len(ITEM_SPECS)} on read frame {config.read_frame_path!r} over ports "
        f"{receipt['declared']['read_frame']['support']['start']}.."
        f"{receipt['declared']['read_frame']['support']['stop'] - 1}"
    )
    print(
        f"restart path: {receipt['restart_identity']['restart_path']} "
        f"(state digest identical: {receipt['restart_identity']['state_digest_identical']})"
    )
    contrast = receipt["source_contrast"]
    print(
        "source-off counterparts: "
        + ", ".join(row["sources_off_arm"] for row in contrast["pairs"])
    )
    print(
        "source-on minus source-off recovery at the read tick (declared margin "
        f"{contrast['declared_margin']!r}): "
        f"single item {contrast['single_item_difference']!r}, "
        f"minimum multi-item {contrast['minimum_multi_item_difference']!r}"
    )
    print(receipt["reading"]["source_off_alignment_sentence"])
    print(f"receipt_digest: {receipt['receipt_digest']}")
    print(f"elapsed_seconds: {elapsed:.2f}")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(f"receipt: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
