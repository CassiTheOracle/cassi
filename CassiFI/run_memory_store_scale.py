"""Does the store survive being used: the non-destructive act, and a store under rounds.

Part A -- the non-destructive act. Tonight's consumer act is an owner write along
the remembered direction, which rewrites the memory it acts on. The options
receipt measured a second way to move a declared readout: a coupled input
realization whose readout answers its input. This part asks whether a consumer
can act through a surface that moves the readout while leaving the stored
memory untouched, and answers on four arms:

  A1-owner-write-act          the known destructive case: the act is one owner
                              ``write_packet_impulse`` along the written item's
                              direction at the declared act budget.
  A2-owner-drive-act          the act is one ``advance_transceivers`` tick on a
                              transceiver the owner condensed from a learned
                              chart, at the declared drive amplitude.
  A3-coupled-drive-act        the act is one ``advance_transceiver`` tick on the
                              declared coupled input realization, built outside
                              the owner's surface with the options receipt's own
                              ``realization_kernel``.
  C1-drive-on-an-unwritten-page  the same A2 act on a page nothing was written
                              to: the readout movement must not depend on the
                              memory, and the memory read must be zero.

Each arm publishes, before and after its act, the page digest, the workspace
state digest, the owner state digest and the owner ledger digest (a digest of
the published event ids, active revision ids, event count and current
checkpoint manifest), the readout before and after, and the stored memory's own
read afterwards. Part A's controls are the declared zero-amplitude stimulus
(whose movement must be the tick's own dynamics, with no input-attributable
part), the shipped identity realization (the same drive with zero coupling,
whose input-attributable movement must be exactly zero -- the can-fail control
for "the readout moves with the input"), and C1's unwritten page. The finding is
either that a non-destructive act exists on a measured surface or that it does
not; both are reported.

Part B -- a multi-item store under repeated use. The declared items are the
durability harness's own ``ITEM_SPECS`` 0..7 (the candidate set every harness in
this family names). The store writes all eight through the owner write path at
the declared write budget, holds them for the declared even horizon through the
owner's own page with the feedback harness's per-item phase-locked drive law at
this profile's own measured neutral gain (measured here, not borrowed), replays
the same tick body through the feedback harness's primitives, and then runs the
declared consumer loop: R rounds that each retrieve one declared direction, read
it, and act through the owner write path on the direction the declared policy
selects. Every round's full read matrix is measured (reads are non-destructive),
so per-item recovery, cross-item interference and the read drift across rounds
are all figures rather than inferences. The last round's page is then used for
the identity control: two fresh owners take a copy of that byte-identical page,
one runs the consumer policy with its retrieval and one with the retrieval
suppressed, and the two acts' directions must separate.

Declared grid: N = 8 declared items times R = 8 rounds = 64 measured cells, the
full declared grid; it fits the declared budget, so nothing was reduced.

Cross-item leakage is measured three ways, all on the declared items' own
directions: the never-acted cells of the read matrix (each item's read while the
consumer has not yet acted on it, against its own held-page read), the held
page's own cross-item cells (each read normalized by the queried item's deposit
-- degenerate on this store, where the measured deposits agree to ~1e-15
relative, which is reported as a figure rather than assumed), and the falsifying
measurement: one fresh owner per declared item writes that item alone and every
declared direction is read on the resulting page, so each off-diagonal read is
measured where the page's content is known, alongside the same owner's read of
its blank page as the control.

Every figure below is read from this receipt, and every predicate has a
can-fail control that is measured in the same run.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_feedback_exploration as feedback
import run_fractal_geometry_exploration as geometry
import run_memory_consumer_path as consumer
import run_owner_surface_options as options
from cassi_field_atlas import (
    Guard,
    RelationChart,
    VariableSpec,
    canonical_json_bytes,
    sha256_value,
)
from cassi_field_owner import SourceInput

SCHEMA = "cassifi.memory-store-scale.v1"
RECEIPT_PATH = Path("_diag/memory-store-scale/exploration.json")

PART_A_ITEM_INDEX = 0
PART_B_ITEM_INDICES = tuple(range(8))
DECLARED_ROUNDS = 8
DECLARED_HOLD_HORIZON_TICKS = 2
WRITE_BUDGET = 1e-3
ACT_BUDGET = 1e-3
DRIVE_AMPLITUDE = 1.75
STORE_PHASE_READOUT_TICKS = 40
READ_RECOVERY_ALLOWANCE = 0.5
READ_DRIFT_ALLOWANCE = 0.05
READ_LEAKAGE_ALLOWANCE = 0.05
LEAKAGE_SEPARATION_FACTOR = 10.0
MEMORY_READ_RELATIVE_ALLOWANCE = 1e-9

INSTRUMENT_NAME = "store-magnitude"
INSTRUMENT_GAIN = 2.0
INSTRUMENT_VALUES = (-3.0, -2.0, -1.0, -0.5, 0.5, 1.0, 2.0, 3.0)
INSTRUMENT_CONTEXT = {"mechanism": "connected"}

READ_FRAME_PATH = durability.READ_FRAME_PATH
# The declared content-stability convention. The base set is the geometry harness's
# own wall-clock leaves, which already includes ``receipt_sha256`` -- a chained hash
# of a timed receipt -- so the family's convention already treats a digest derived
# from a timed receipt as stripped. This runner publishes two more digests of that
# class: the owner's current checkpoint manifest, which chains over receipts that
# carry ``elapsed_seconds``, and this runner's own ledger digest, which is computed
# over that manifest. They are declared here and the rule is that any value derived
# from a stripped value is stripped, rather than listed case by case.
CLOCK_LEAF_KEYS = tuple(sorted(geometry.TIMING_KEYS))
CLOCK_DERIVED_KEYS = (
    "current_manifest_sha256",
    "owner_ledger_sha256",
    "parent_manifest_sha256",
)
STRIP_KEYS = tuple(sorted(set(CLOCK_LEAF_KEYS) | set(CLOCK_DERIVED_KEYS)))
# Kept as the name the earlier harnesses in this family declare, for the receipt's
# own convention block; it is the geometry harness's clock-leaf set alone.
BASE_STRIP_KEYS = tuple(sorted(geometry.TIMING_KEYS))


# --------------------------------------------------------------------------
# declared settings
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class StoreScaleConfig:
    """Declared measurement settings; every number in the receipt derives from these."""

    part_a: bool = True
    part_b: bool = True
    part_a_item_index: int = PART_A_ITEM_INDEX
    item_indices: tuple[int, ...] = PART_B_ITEM_INDICES
    rounds: int = DECLARED_ROUNDS
    hold_horizon_ticks: int = DECLARED_HOLD_HORIZON_TICKS
    write_budget: float = WRITE_BUDGET
    act_budget: float = ACT_BUDGET
    drive_amplitude: float = DRIVE_AMPLITUDE
    instrument_values: tuple[float, ...] = INSTRUMENT_VALUES
    instrument_gain: float = INSTRUMENT_GAIN
    store_phase_readout_ticks: int = STORE_PHASE_READOUT_TICKS
    neutrality_probe_items: tuple[int, ...] = PART_B_ITEM_INDICES
    read_recovery_allowance: float = READ_RECOVERY_ALLOWANCE
    read_drift_allowance: float = READ_DRIFT_ALLOWANCE
    read_leakage_allowance: float = READ_LEAKAGE_ALLOWANCE
    leakage_separation_factor: float = LEAKAGE_SEPARATION_FACTOR
    memory_read_relative_allowance: float = MEMORY_READ_RELATIVE_ALLOWANCE
    owner_home_prefix: str = "mss-owner-"
    options_config: options.OwnerSurfaceOptionsConfig = field(
        default_factory=lambda: options.OwnerSurfaceOptionsConfig(
            headline_item_index=PART_A_ITEM_INDEX,
            write_budget=WRITE_BUDGET,
        )
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "part_a": bool(self.part_a),
            "part_b": bool(self.part_b),
            "part_a_item_index": int(self.part_a_item_index),
            "part_a_item": durability.ITEM_SPECS[int(self.part_a_item_index)].name,
            "item_indices": [int(index) for index in self.item_indices],
            "item_names": [
                durability.ITEM_SPECS[int(index)].name for index in self.item_indices
            ],
            "rounds": int(self.rounds),
            "grid_cells": int(len(self.item_indices) * int(self.rounds)),
            "hold_horizon_ticks": int(self.hold_horizon_ticks),
            "hold_horizon_parity": (
                "even" if int(self.hold_horizon_ticks) % 2 == 0 else "odd"
            ),
            "write_budget": float(self.write_budget),
            "act_budget": float(self.act_budget),
            "drive_amplitude": float(self.drive_amplitude),
            "instrument_values": [float(value) for value in self.instrument_values],
            "instrument_gain": float(self.instrument_gain),
            "store_phase_readout_ticks": int(self.store_phase_readout_ticks),
            "neutrality_probe_item_indices": [
                int(index) for index in self.neutrality_probe_items
            ],
            "read_recovery_allowance": float(self.read_recovery_allowance),
            "read_drift_allowance": float(self.read_drift_allowance),
            "read_leakage_allowance": float(self.read_leakage_allowance),
            "leakage_separation_factor": float(self.leakage_separation_factor),
            "memory_read_relative_allowance": float(
                self.memory_read_relative_allowance
            ),
            "coupled_relation": {
                "diagonal": float(options.COUPLED_DIAGONAL),
                "coupling": float(options.COUPLED_COUPLING),
            },
            "shipped_relation": {
                "diagonal": float(options.SHIPPED_DIAGONAL),
                "coupling": float(options.SHIPPED_COUPLING),
            },
            "transceiver_settings": {
                "rank": int(self.options_config.rank),
                "error_allowance": float(self.options_config.error_allowance),
                "input_bound": float(self.options_config.input_bound),
                "horizon_ticks": int(self.options_config.horizon_ticks),
                "authority_input_scan": [
                    float(value) for value in self.options_config.authority_input_scan
                ],
                "authority_window_ticks": [
                    int(value) for value in self.options_config.authority_window_ticks
                ],
                "authority_allowance": float(self.options_config.authority_allowance),
            },
            "read_floor_fraction": float(consumer.READ_FLOOR_FRACTION),
            "pursuit_margin": float(consumer.PURSUIT_MARGIN),
            "separation_margin": float(consumer.SEPARATION_MARGIN),
        }


def flat_profile() -> Any:
    """The metric harness's flat-inertia profile, as every harness in this family builds it."""

    return consumer.flat_profile()


# --------------------------------------------------------------------------
# small shared instruments
# --------------------------------------------------------------------------
def plain(value: Any) -> Any:
    """One measured mapping, detached from whatever published it."""

    return consumer.plain(value)


def owner_ledger_sha256(owner: Any) -> str:
    """The owner's ledger as one digest: evidence, active revisions, manifest."""

    return sha256_value(
        {
            "event_ids": sorted(str(value) for value in owner.evidence.all_event_ids()),
            "active_revision_ids": sorted(
                str(value) for value in owner.evidence.active_revision_ids()
            ),
            "event_count": int(owner.evidence.event_count),
            "current_manifest_sha256": str(owner.checkpoints.current_manifest_sha256),
        }
    )


def surface_snapshot(owner: Any) -> dict[str, Any]:
    """The four declared digests of one owner surface moment."""

    return {
        "page_sha256": durability.page_sha256(owner.state.resonant_workspace),
        "workspace_state_sha256": str(owner.state.resonant_workspace.state_sha256),
        "owner_state_sha256": str(owner.state.state_sha256),
        "owner_ledger_sha256": owner_ledger_sha256(owner),
        "generation": int(owner.state.generation),
        "logical_tick": int(owner.state.logical_tick),
    }


def snapshot_movement(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Which of the four declared digests moved between two surface moments."""

    keys = (
        "page_sha256",
        "workspace_state_sha256",
        "owner_state_sha256",
        "owner_ledger_sha256",
    )
    return {
        "page_moved": bool(before["page_sha256"] != after["page_sha256"]),
        "workspace_state_moved": bool(
            before["workspace_state_sha256"] != after["workspace_state_sha256"]
        ),
        "owner_state_moved": bool(
            before["owner_state_sha256"] != after["owner_state_sha256"]
        ),
        "owner_ledger_moved": bool(
            before["owner_ledger_sha256"] != after["owner_ledger_sha256"]
        ),
        "generation_moved_by": int(after["generation"]) - int(before["generation"]),
        "logical_tick_moved_by": int(after["logical_tick"]) - int(before["logical_tick"]),
    }


def memory_read(owner: Any, index: int) -> dict[str, Any]:
    """The stored memory's own read: the owner's read of the declared direction."""

    spec = durability.ITEM_SPECS[int(index)]
    reading = plain(owner.read_packet_deposit(**consumer.named_direction(spec)))
    return {
        "item": spec.name,
        "item_index": int(index),
        "recovered_deposit": float(reading["recovered_deposit"]),
        "read_frame_energy": float(reading["read_frame_energy"]),
        "readout_kind": str(reading["readout_kind"]),
        "evidence_added": bool(reading["evidence_added"]),
    }


def relative_difference(left: float, right: float) -> float:
    """One relative difference, with a declared zero denominator reported as zero."""

    magnitude = max(abs(float(left)), abs(float(right)))
    if magnitude == 0.0:
        return 0.0
    return float(abs(float(left) - float(right)) / magnitude)


def strip_clock_leaves(value: Any) -> Any:
    """Apply the declared strip rule to a whole body, at any depth.

    A key is dropped when it is a declared wall-clock leaf, and by rule when it is a
    declared clock-derived digest: a chained manifest hash, a chained receipt hash, or
    this runner's own ledger digest, which is computed over such a manifest. The rule
    covers derived-from-stripped values as a class; the movement booleans this runner
    computes from those digests stay in the body, so what the ledger did between two
    surface moments is still measured even though the clock-contaminated digest value
    is not what the content digest is taken over.
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
    """This receipt's content digest under the declared clock-strip rule.

    The geometry harness's own ``content_digest`` hard-codes the clock-leaf set alone,
    which is not enough for this body: it publishes a checkpoint manifest hash and a
    ledger digest derived from it. This function applies the declared set (clock
    leaves plus clock-derived digests) to the body and then takes the same canonical
    digest the family's convention defines.
    """

    return geometry.canonical_digest(
        strip_clock_leaves(
            {key: value for key, value in body.items() if key != "receipt_digest"}
        )
    )


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
    if isinstance(value, bool):
        return
    if isinstance(value, (int, str)) or value is None:
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite number at {path}: {value!r}")
        return
    raise ValueError(f"non-JSON value at {path}: {type(value).__name__}")


# --------------------------------------------------------------------------
# part A: the act arms
# --------------------------------------------------------------------------
def write_declared_item(owner: Any, index: int, *, label: str, budget: float) -> dict[str, Any]:
    """One owner write of one declared direction."""

    spec = durability.ITEM_SPECS[int(index)]
    result = plain(
        owner.write_packet_impulse(
            label,
            **consumer.named_direction(spec),
            work_budget=float(budget),
        )
    )
    receipt = plain(result["impulse_receipt"])
    return {
        "item": spec.name,
        "item_index": int(index),
        "requested_work": float(receipt["requested_work"]),
        "applied_work": float(receipt["applied_work"]),
        "impulse_amount": float(receipt["impulse_amount"]),
        "accepted": bool(receipt["accepted"]),
    }


def part_a_arm_report(
    *,
    arm: str,
    declared: str,
    readout_kind: str,
    readout_before: float | None,
    readout_after: float | None,
    snapshots_before: Mapping[str, Any],
    snapshots_after: Mapping[str, Any],
    memory_before: Mapping[str, Any] | None,
    memory_after: Mapping[str, Any] | None,
    extra: Mapping[str, Any],
    config: StoreScaleConfig,
) -> dict[str, Any]:
    """One part A arm's own figures, with the declared movement predicates."""

    movement = None
    if readout_before is not None and readout_after is not None:
        movement = float(readout_after) - float(readout_before)
    memory_difference = None
    if memory_before is not None and memory_after is not None:
        memory_difference = relative_difference(
            float(memory_before["recovered_deposit"]),
            float(memory_after["recovered_deposit"]),
        )
    return {
        "arm": str(arm),
        "declared": str(declared),
        "readout": {
            "kind": str(readout_kind),
            "before": None if readout_before is None else float(readout_before),
            "after": None if readout_after is None else float(readout_after),
            "movement": movement,
        },
        "snapshots": {
            "before": dict(snapshots_before),
            "after": dict(snapshots_after),
            "moved": snapshot_movement(snapshots_before, snapshots_after),
        },
        "memory_read": {
            "before": None if memory_before is None else dict(memory_before),
            "after": None if memory_after is None else dict(memory_after),
            "relative_difference": memory_difference,
            "the_stored_memory_is_unchanged": (
                None
                if memory_difference is None
                else bool(memory_difference <= float(config.memory_read_relative_allowance))
            ),
        },
        **dict(extra),
    }


def owner_write_act_arm(profile: Any, config: StoreScaleConfig) -> dict[str, Any]:
    """A1: the act is one owner write along the remembered direction."""

    index = int(config.part_a_item_index)
    spec = durability.ITEM_SPECS[index]
    owner, home = consumer.open_owner(profile, prefix=config.owner_home_prefix)
    try:
        write = write_declared_item(
            owner, index, label="store-scale:a1:write", budget=config.write_budget
        )
        memory_before = memory_read(owner, index)
        before = surface_snapshot(owner)
        act = write_declared_item(
            owner, index, label="store-scale:a1:act", budget=config.act_budget
        )
        after = surface_snapshot(owner)
        memory_after = memory_read(owner, index)
        return part_a_arm_report(
            arm="A1-owner-write-act",
            declared=(
                "the written direction is remembered, then the consumer acts: one "
                "owner write_packet_impulse along that same direction at the "
                "declared act budget. This is the destructive case the options "
                "receipt's coupled input was measured against"
            ),
            readout_kind="the owner's own read of the written direction (recovered_deposit)",
            readout_before=float(memory_before["recovered_deposit"]),
            readout_after=float(memory_after["recovered_deposit"]),
            snapshots_before=before,
            snapshots_after=after,
            memory_before=memory_before,
            memory_after=memory_after,
            extra={"write": write, "act": act},
            config=config,
        )
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def learn_instrument(owner: Any, config: StoreScaleConfig) -> dict[str, Any]:
    """The declared instrument: one learned relation over the declared values."""

    name = INSTRUMENT_NAME
    bias, input_id, output_id = (f"{name}:bias", f"{name}:input", f"{name}:output")
    for variable in (
        VariableSpec(bias, kind="constant", constant=1.0),
        VariableSpec(input_id, lower=-40.0, upper=40.0),
        VariableSpec(output_id, lower=-40.0, upper=40.0),
    ):
        plain(owner.configure_variable(f"configure:{variable.variable_id}", variable))
    plain(
        owner.configure_chart(
            f"configure:{name}:chart",
            RelationChart.empty(
                chart_id=name,
                scope=(bias, input_id, output_id),
                ridge=0.01,
                prior_mass=1e-4,
                observation_norm_bound=100.0,
                guards=(Guard("mechanism", "eq", "connected"),),
            ),
        )
    )
    revisions = []
    for position, value in enumerate(config.instrument_values):
        values = {bias: 1.0, input_id: float(value), output_id: float(config.instrument_gain) * float(value)}
        source = SourceInput(
            source_id=f"instrument:{name}:{position}",
            content=canonical_json_bytes(values),
            media_type="application/json",
            codec="utf-8",
            observed_timestamp=str(position),
            scope="memory-store-scale",
            claim_category="controlled-measurement",
            fidelity="exact-record",
            labels=("memory-store-scale",),
        )
        result = plain(
            owner.admit_observation(
                operation_id=f"learn:{name}:{position}",
                source=source,
                values=values,
                context=INSTRUMENT_CONTEXT,
                target_chart_ids=(name,),
            )
        )
        revisions.append(str(result["source"]["revision_id"]))
    return {
        "chart_id": name,
        "bias_id": bias,
        "input_id": input_id,
        "output_id": output_id,
        "declared_gain": float(config.instrument_gain),
        "values": [float(value) for value in config.instrument_values],
        "context": dict(INSTRUMENT_CONTEXT),
        "admitted_observations": len(revisions),
        "revision_ids": revisions,
    }


def owner_drive_act_arm(profile: Any, config: StoreScaleConfig, *, written: bool) -> dict[str, Any]:
    """A2 (written page) and C1 (unwritten page): the act is one transceiver tick."""

    arm = "A2-owner-drive-act" if written else "C1-drive-on-an-unwritten-page"
    index = int(config.part_a_item_index)
    spec = durability.ITEM_SPECS[index]
    output_id = f"{INSTRUMENT_NAME}:output"
    input_id = f"{INSTRUMENT_NAME}:input"
    owner, home = consumer.open_owner(profile, prefix=config.owner_home_prefix)
    try:
        blank_page = durability.page_sha256(owner.state.resonant_workspace)
        write = None
        if written:
            write = write_declared_item(
                owner,
                index,
                label="store-scale:a2:write",
                budget=config.write_budget,
            )
        page_before_the_instrument = durability.page_sha256(owner.state.resonant_workspace)
        memory_before = memory_read(owner, index)
        instrument = learn_instrument(owner, config)
        build = plain(
            owner.condense_transceiver(
                f"store-scale:{arm}:condense",
                transceiver_id=INSTRUMENT_NAME,
                chart_ids=(INSTRUMENT_NAME,),
                input_ids=(input_id,),
                output_ids=(output_id,),
                context=INSTRUMENT_CONTEXT,
                rank=int(config.options_config.rank),
                error_allowance=float(config.options_config.error_allowance),
                input_bound=float(config.options_config.input_bound),
                horizon_ticks=int(config.options_config.horizon_ticks),
            )
        )
        page_after_condensation = durability.page_sha256(owner.state.resonant_workspace)
        inspected = plain(owner.inspect_transceivers())["transceivers"][INSTRUMENT_NAME]
        published_before = float(inspected["response"]["values"][output_id])

        plain(owner.reset_transceiver(f"store-scale:{arm}:reset-zero", transceiver_id=INSTRUMENT_NAME))
        zero = plain(
            owner.advance_transceivers(
                f"store-scale:{arm}:zero",
                stimuli={INSTRUMENT_NAME: {input_id: 0.0}},
                context=INSTRUMENT_CONTEXT,
                ticks=1,
            )
        )
        readout_zero = float(zero["receipt"]["transceivers"][INSTRUMENT_NAME]["values"][output_id])
        plain(owner.reset_transceiver(f"store-scale:{arm}:reset-act", transceiver_id=INSTRUMENT_NAME))
        before = surface_snapshot(owner)
        act = plain(
            owner.advance_transceivers(
                f"store-scale:{arm}:act",
                stimuli={INSTRUMENT_NAME: {input_id: float(config.drive_amplitude)}},
                context=INSTRUMENT_CONTEXT,
                ticks=1,
            )
        )
        readout_after = float(act["receipt"]["transceivers"][INSTRUMENT_NAME]["values"][output_id])
        after = surface_snapshot(owner)
        memory_after = memory_read(owner, index)
        return part_a_arm_report(
            arm=arm,
            declared=(
                "the owner condenses a learned chart into its own transceiver and the "
                "consumer acts by advancing that transceiver one tick at the declared "
                "drive amplitude; the readout pair is the transceiver's own declared "
                "output at a fresh reset with the stimulus at zero and at the declared "
                "amplitude, so the comparison is at one tick from one declared state"
                + (
                    " on a page holding the written direction"
                    if written
                    else " on a page nothing was written to (the control)"
                )
            ),
            readout_kind="the owner's transceiver declared output",
            readout_before=readout_zero,
            readout_after=readout_after,
            snapshots_before=before,
            snapshots_after=after,
            memory_before=memory_before,
            memory_after=memory_after,
            extra={
                "written": bool(written),
                "blank_page_sha256": blank_page,
                "write": write,
                "instrument": instrument,
                "condensation": {
                    "page_before": page_before_the_instrument,
                    "page_after": page_after_condensation,
                    "the_condensation_changes_no_page": bool(
                        page_before_the_instrument == page_after_condensation
                    ),
                    "receipt_status": str(
                        build["receipt"].get("status", build["receipt"].get("kind", ""))
                    ),
                    "dimensions": plain(build["receipt"].get("dimensions")),
                },
                "published_readout_before_the_act": published_before,
                "the_published_readout_matches_the_zero_stimulus_tick": bool(
                    published_before == readout_zero
                ),
                "zero_amplitude": {
                    "readout": readout_zero,
                    "movement_from_the_published_value": float(readout_zero - published_before),
                    "declared": (
                        "the same advance at stimulus zero: the tick's own dynamics "
                        "move the published output, and the input-attributable part of "
                        "the movement is the difference against this arm's declared "
                        "amplitude tick, measured above"
                    ),
                },
                "transceiver_receipt": plain(act["receipt"]["transceivers"][INSTRUMENT_NAME]),
            },
            config=config,
        )
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def coupled_drive_act_arm(profile: Any, config: StoreScaleConfig) -> dict[str, Any]:
    """A3: the act is one tick of the declared coupled input realization."""

    index = int(config.part_a_item_index)
    spec = durability.ITEM_SPECS[index]
    direction = np.asarray(
        durability.capture_items(
            durability.DurabilityConfig(write_budget=float(config.write_budget)), profile
        )[index]["direction"],
        dtype=np.float64,
    )
    owner, home = consumer.open_owner(profile, prefix=config.owner_home_prefix)
    try:
        write = write_declared_item(
            owner, index, label="store-scale:a3:write", budget=config.write_budget
        )
        page = owner.state.resonant_workspace
        page_frame = durability.read_frame(page, config.options_config.read_frame_path)
        memory_before = memory_read(owner, index)
        rows: dict[str, Any] = {}
        for label, diagonal, coupling in (
            ("coupled", options.COUPLED_DIAGONAL, options.COUPLED_COUPLING),
            ("shipped", options.SHIPPED_DIAGONAL, options.SHIPPED_COUPLING),
        ):
            kernel, _working, build = options.realization_kernel(
                page, config.options_config, diagonal=diagonal, coupling=coupling
            )
            authority = options.authority_series(
                kernel,
                config.options_config,
                input_scan=config.options_config.authority_input_scan,
            )
            tick_one = authority["per_tick"]["1"]["outputs"]
            key = repr(float(config.drive_amplitude))
            readout_before = float(tick_one[repr(0.0)])
            readout_after = float(tick_one[key])
            state, act = transceiver_advance(
                kernel, float(config.drive_amplitude)
            )
            mapped = transceiver_mapped_page(profile, page, state)
            increment = (
                durability.read_frame(mapped, config.options_config.read_frame_path)
                - page_frame
            )
            rows[label] = {
                "declared": (
                    "the declared coupled relation from the options receipt's own "
                    "realization_kernel: every declared variable keeps 2 on its own "
                    "coordinate and the pair gains 1 between them"
                    if label == "coupled"
                    else "the shipped identity precision the library realizes by "
                    "default: the can-fail control for 'the readout moves with the "
                    "input'"
                ),
                "diagonal": float(diagonal),
                "coupling": float(coupling),
                "kernel_sha256": str(kernel["kernel_sha256"]),
                "authority": authority,
                "readout": {
                    "kind": "the realization's declared write-out at one tick from a fresh reset",
                    "before": readout_before,
                    "after": readout_after,
                    "movement": float(readout_after - readout_before),
                },
                "act": {
                    "amplitude": float(config.drive_amplitude),
                    "readout": float(act["values"]["write-out"]),
                    "state_vector_norm": float(
                        np.linalg.norm(np.asarray(state["state"], dtype=np.float64))
                    ),
                    "state_increment_share_along_the_written_direction": consumer.share_along(
                        increment, direction
                    ),
                    "state_increment_norm": float(np.linalg.norm(increment)),
                    "page_sha256": durability.page_sha256(mapped),
                    "the_stored_page_is_not_the_drive_state": bool(
                        durability.page_sha256(mapped)
                        != durability.page_sha256(page)
                    ),
                },
                "condensation": {
                    "dimensions": plain(build.get("dimensions")),
                    "status": str(build.get("status", build.get("kind", ""))),
                },
            }
        before = surface_snapshot(owner)
        memory_after = memory_read(owner, index)
        after = surface_snapshot(owner)
        coupled_row = rows["coupled"]
        shipped_row = rows["shipped"]
        allowance = float(config.options_config.authority_allowance)
        return part_a_arm_report(
            arm="A3-coupled-drive-act",
            declared=(
                "the act is one advance_transceiver tick of the declared coupled input "
                "realization built from the owner's own written page by the options "
                "receipt's realization_kernel, outside the owner's surface: the "
                "realization carries the page's declared write problem and its own "
                "working state, and no owner operation is called to drive it"
            ),
            readout_kind="the coupled realization's declared write-out",
            readout_before=float(coupled_row["readout"]["before"]),
            readout_after=float(coupled_row["readout"]["after"]),
            snapshots_before=before,
            snapshots_after=after,
            memory_before=memory_before,
            memory_after=memory_after,
            extra={
                "write": write,
                "realizations": rows,
                "controls": {
                    "shipped_relation_is_inert": {
                        "declared": (
                            "the same act on the shipped identity realization: its "
                            "readout must not move with the input, which is what makes "
                            "the coupled row's movement a property of the declared "
                            "relation rather than of the input code path"
                        ),
                        "authority_spread": float(
                            shipped_row["authority"]["authority_window_average_spread"]
                        ),
                        "readout_movement": float(shipped_row["readout"]["movement"]),
                        "the_coupled_row_exceeds_the_allowance": bool(
                            float(
                                coupled_row["authority"]["authority_window_average_spread"]
                            )
                            > allowance
                        ),
                        "the_shipped_row_is_inert": bool(
                            abs(float(shipped_row["readout"]["movement"])) <= allowance
                            and float(
                                shipped_row["authority"]["authority_window_average_spread"]
                            )
                            <= allowance
                        ),
                    },
                },
            },
            config=config,
        )
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def transceiver_advance(kernel: Mapping[str, Any], amplitude: float) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """One declared drive tick from a fresh reset of the realization."""

    from cassi_field_transceiver import advance_transceiver, reset_transceiver

    return advance_transceiver(
        kernel,
        reset_transceiver(kernel),
        inputs={"write-in": float(amplitude)},
        ticks=1,
    )


def transceiver_mapped_page(profile: Any, page: Any, state: Mapping[str, Any]) -> Any:
    """The library's own state-to-page mapping, at the page's own bindings."""

    from cassi_field_transceiver import _workspace

    return _workspace(
        profile, page.bindings, np.asarray(state["state"], dtype=np.float64)
    )


def part_a_block(profile: Any, config: StoreScaleConfig) -> dict[str, Any]:
    """Every declared part A arm and control, measured in order."""

    arms = {
        "A1-owner-write-act": owner_write_act_arm(profile, config),
        "A2-owner-drive-act": owner_drive_act_arm(profile, config, written=True),
        "A3-coupled-drive-act": coupled_drive_act_arm(profile, config),
        "C1-drive-on-an-unwritten-page": owner_drive_act_arm(profile, config, written=False),
    }
    write_arm = arms["A1-owner-write-act"]
    owner_drive = arms["A2-owner-drive-act"]
    coupled = arms["A3-coupled-drive-act"]
    unwritten = arms["C1-drive-on-an-unwritten-page"]
    allowance = float(config.memory_read_relative_allowance)
    authority_allowance = float(config.options_config.authority_allowance)
    paired = {
        name: (float(arm["readout"]["movement"]), None if arm["readout"]["movement"] is None else abs(float(arm["readout"]["movement"])) > authority_allowance)
        for name, arm in arms.items()
    }
    verdicts = {
        "the_owner_write_act_rewrites_the_memory": bool(
            write_arm["snapshots"]["moved"]["page_moved"]
            and float(write_arm["memory_read"]["relative_difference"]) > allowance
        ),
        "the_owner_write_act_moves_the_readout": bool(
            abs(float(write_arm["readout"]["movement"])) > authority_allowance
        ),
        "the_owner_drive_act_moves_the_readout": bool(
            abs(float(owner_drive["readout"]["movement"])) > authority_allowance
        ),
        "the_owner_drive_act_leaves_the_page_and_the_workspace_untouched": bool(
            not owner_drive["snapshots"]["moved"]["page_moved"]
            and not owner_drive["snapshots"]["moved"]["workspace_state_moved"]
        ),
        "the_owner_drive_act_moves_the_owner_state_and_ledger": bool(
            owner_drive["snapshots"]["moved"]["owner_state_moved"]
            and owner_drive["snapshots"]["moved"]["owner_ledger_moved"]
        ),
        "the_owner_drive_act_leaves_the_stored_memory_readable": bool(
            owner_drive["memory_read"]["the_stored_memory_is_unchanged"]
        ),
        "the_coupled_drive_act_moves_the_readout": bool(
            abs(float(coupled["readout"]["movement"])) > authority_allowance
        ),
        "the_coupled_drive_act_leaves_every_owner_digest_untouched": bool(
            not coupled["snapshots"]["moved"]["page_moved"]
            and not coupled["snapshots"]["moved"]["workspace_state_moved"]
            and not coupled["snapshots"]["moved"]["owner_state_moved"]
            and not coupled["snapshots"]["moved"]["owner_ledger_moved"]
        ),
        "the_coupled_drive_act_leaves_the_stored_memory_readable": bool(
            coupled["memory_read"]["the_stored_memory_is_unchanged"]
        ),
        "the_shipped_relation_is_inert_on_the_same_act": bool(
            coupled["controls"]["shipped_relation_is_inert"]["the_shipped_row_is_inert"]
        ),
        "the_drive_moves_the_readout_without_the_memory": bool(
            abs(float(unwritten["readout"]["movement"]))
            >= 0.5 * abs(float(owner_drive["readout"]["movement"]))
            and abs(float(unwritten["memory_read"]["before"]["recovered_deposit"]))
            <= float(write_arm["memory_read"]["before"]["recovered_deposit"]) * allowance
            and abs(float(unwritten["memory_read"]["after"]["recovered_deposit"]))
            <= float(write_arm["memory_read"]["before"]["recovered_deposit"]) * allowance
        ),
        "the_condensation_and_the_inspection_change_no_page": bool(
            owner_drive["condensation"]["the_condensation_changes_no_page"]
            and unwritten["condensation"]["the_condensation_changes_no_page"]
        ),
        "the_published_readout_is_the_zero_stimulus_tick": bool(
            owner_drive["the_published_readout_matches_the_zero_stimulus_tick"]
        ),
    }
    return {
        "declared": (
            "four arms on the declared written direction (A1 owner write, A2 the "
            "owner's own transceiver, A3 the coupled realization outside the owner "
            "surface, C1 the same owner drive on an unwritten page), each reporting "
            "the four declared surface digests before and after its act, its readout "
            "pair, and the stored memory's own read afterwards"
        ),
        "readout_movement": {
            name: {"movement": movement, "exceeds_the_authority_allowance": fires}
            for name, (movement, fires) in paired.items()
        },
        "arms": arms,
        "verdicts": verdicts,
        "honest_negatives": [
            text
            for condition, text in (
                (
                    verdicts["the_owner_drive_act_leaves_the_page_and_the_workspace_untouched"],
                    "the owner transceiver act moved the page or the workspace state, "
                    "so it is not a non-destructive act on this surface",
                ),
                (
                    verdicts["the_coupled_drive_act_leaves_every_owner_digest_untouched"],
                    "the coupled realization act moved an owner digest even though no "
                    "owner operation was called for it",
                ),
                (
                    verdicts["the_shipped_relation_is_inert_on_the_same_act"],
                    "the shipped identity realization answered its input, so the "
                    "coupled row's authority is not attributable to the declared "
                    "relation",
                ),
                (
                    verdicts["the_owner_drive_act_moves_the_readout"],
                    "the owner transceiver's readout did not move with its stimulus at "
                    "the declared amplitude",
                ),
            )
            if not condition
        ],
    }


# --------------------------------------------------------------------------
# part B: the store
# --------------------------------------------------------------------------
def hold_plan(
    loop: Any,
    gain: float,
    vector: np.ndarray,
    indices: Sequence[int],
    captures: Sequence[Mapping[str, Any]],
    arms: Mapping[int, Any],
    signed_references: Mapping[int, float],
    phase_references: Mapping[int, Mapping[str, Any]],
) -> list[tuple[int, float, bool]]:
    """One tick's declared per-item drive plan: each item's own read-back signal.

    This is the feedback harness's own per-item phase-locked scheme, applied to one
    frame: every declared item reads itself back through its own direction and its own
    declared phase reference, and the declared gain turns that signal into that item's
    amplitude for this tick. Both the owner route and the functional replay compute
    their plan through this one function, so the two routes differ only in which
    surface applies the drive.
    """

    plan: list[tuple[int, float, bool]] = []
    for index in indices:
        ratio = feedback.phase_signal(
            loop,
            arms[int(index)],
            vector,
            captures[int(index)]["direction"],
            float(signed_references[int(index)]),
            phase_references[int(index)],
        )
        amplitude, clipped = feedback.loop_amplitude(loop, float(gain), ratio)
        plan.append((int(index), float(amplitude), bool(clipped)))
    return plan


def store_episode(
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    config: StoreScaleConfig,
    *,
    gain: float,
    phase_degrees: float,
    phase_references: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    """Write the declared items, hold them through the owner, replay, read them all."""

    loop = feedback.FeedbackConfig()
    ceiling = float(loop.loop_work_ceiling)
    indices = tuple(int(index) for index in config.item_indices)
    horizon = int(config.hold_horizon_ticks)
    arms = {
        index: feedback.LoopArm(
            f"store-scale-hold-{durability.ITEM_SPECS[index].name}",
            (index,),
            gain=float(gain),
            family="memory-store-scale-hold",
            phase_degrees=float(phase_degrees),
        )
        for index in indices
    }
    owner, home = consumer.open_owner(profile, prefix=config.owner_home_prefix)
    try:
        blank_page = durability.page_sha256(owner.state.resonant_workspace)
        blank_energy = float(durability.squared_norm(durability.read_frame(owner.state.resonant_workspace, READ_FRAME_PATH)))
        writes: dict[str, Any] = {}
        deposits: dict[str, float] = {}
        energy = blank_energy
        for index in indices:
            spec = durability.ITEM_SPECS[index]
            writes[spec.name] = write_declared_item(
                owner,
                index,
                label=f"store-scale:store:write:{index}",
                budget=config.write_budget,
            )
            vector = durability.read_frame(owner.state.resonant_workspace, READ_FRAME_PATH)
            measured = float(durability.squared_norm(vector))
            deposits[spec.name] = measured - energy
            energy = measured
            writes[spec.name]["frame_energy_after"] = measured
            writes[spec.name]["deposit_increment"] = deposits[spec.name]
        post_write = owner.state.resonant_workspace
        post_write_page = durability.page_sha256(post_write)
        post_write_vector = durability.read_frame(post_write, READ_FRAME_PATH)
        signed_references = {
            index: float(np.dot(post_write_vector, captures[index]["direction"]))
            for index in indices
        }
        captured_deposits = {
            durability.ITEM_SPECS[index].name: float(captures[index]["deposited_energy"])
            for index in indices
        }
        amplitudes: dict[str, dict[str, float]] = {}
        ticks: list[dict[str, Any]] = []
        energy_ratio_max = 1.0
        for tick in range(1, horizon + 1):
            plain(owner.advance(f"store-scale:store:advance:{tick}", ticks=1, source_enabled=False))
            vector = durability.read_frame(owner.state.resonant_workspace, READ_FRAME_PATH)
            plan = hold_plan(
                loop,
                float(gain),
                vector,
                indices,
                captures,
                arms,
                signed_references,
                phase_references,
            )
            tick_row: dict[str, Any] = {
                "tick": int(tick),
                "ratios_before": {
                    durability.ITEM_SPECS[index].name: float(
                        np.dot(vector, captures[index]["direction"])
                    )
                    / signed_references[index]
                    for index in indices
                },
                "amplitudes": {},
                "drive_calls": 0,
                "applied_work": 0.0,
                "clipped": False,
            }
            for index, amplitude, clipped in plan:
                spec = durability.ITEM_SPECS[index]
                tick_row["amplitudes"][spec.name] = amplitude
                tick_row["clipped"] = bool(tick_row["clipped"] or clipped)
                if amplitude:
                    drive = plain(
                        owner.write_packet_impulse(
                            f"store-scale:store:drive:{tick}:{index}",
                            path=spec.path,
                            component=spec.component,
                            flow_signal=[float(amplitude), 0.0],
                            work_budget=ceiling
                            * abs(float(amplitude))
                            / float(len(plan)),
                        )
                    )
                    tick_row["drive_calls"] = int(tick_row["drive_calls"]) + 1
                    tick_row["applied_work"] = float(tick_row["applied_work"]) + float(
                        drive["impulse_receipt"]["applied_work"]
                    )
                    amplitudes.setdefault(spec.name, {})[str(tick)] = float(amplitude)
                    vector = durability.read_frame(owner.state.resonant_workspace, READ_FRAME_PATH)
            tick_row["frame_energy_ratio"] = float(
                durability.squared_norm(vector) / post_write_energy(post_write)
            )
            energy_ratio_max = max(energy_ratio_max, float(tick_row["frame_energy_ratio"]))
            ticks.append(tick_row)
        held = owner.state.resonant_workspace
        held_page = durability.page_sha256(held)
        held_vector = durability.read_frame(held, READ_FRAME_PATH)
        held_energy = float(durability.squared_norm(held_vector))
        reads_after_the_hold = {
            durability.ITEM_SPECS[index].name: memory_read(owner, index) for index in indices
        }
        # The declared loop replayed through the harness's own primitives from the
        # same start page at the amplitudes this episode measured.
        replay = post_write
        for _tick in range(1, horizon + 1):
            replay, _ = feedback.advance_workspace(
                replay,
                ticks=1,
                demand=float(loop.activity_demand),
                source_enabled=bool(loop.source_enabled),
            )
            plan = hold_plan(
                loop,
                float(gain),
                durability.read_frame(replay, READ_FRAME_PATH),
                indices,
                captures,
                arms,
                signed_references,
                phase_references,
            )
            for index, amplitude, _clipped in plan:
                if amplitude:
                    replay, _ = feedback.apply_drive(
                        replay,
                        int(index),
                        float(amplitude),
                        ceiling * abs(float(amplitude)) / float(len(plan)),
                    )
        replay_page = durability.page_sha256(replay)
        record = {
            "declared": (
                "the declared items written one at a time through the owner write path, "
                "then advanced tick by tick with the feedback harness's per-item "
                "phase-locked drive law at this profile's own measured neutral gain, "
                "each tick's plan computed from the frame the tick advanced to and each "
                "drive applied through the owner's own write; the same tick body is "
                "replayed through the harness's own primitives from the same start page "
                "and the two held pages are compared"
            ),
            "item_names": [durability.ITEM_SPECS[index].name for index in indices],
            "blank_page_sha256": blank_page,
            "blank_frame_energy": blank_energy,
            "post_write_page_sha256": post_write_page,
            "post_write_frame_energy": post_write_energy(post_write),
            "writes": writes,
            "measured_deposits": {
                name: float(value) for name, value in deposits.items()
            },
            "captured_deposits": captured_deposits,
            "gain": float(gain),
            "phase_degrees": float(phase_degrees),
            "loop_work_ceiling": ceiling,
            "horizon_ticks": horizon,
            "horizon_parity": "even" if horizon % 2 == 0 else "odd",
            "ticks": ticks,
            "drive_calls": int(sum(int(row["drive_calls"]) for row in ticks)),
            "drive_applied_work_total": float(
                sum(float(row["applied_work"]) for row in ticks)
            ),
            "held_page_sha256": held_page,
            "held_frame_energy": held_energy,
            "frame_energy_ratio_at_horizon": held_energy / post_write_energy(post_write),
            "frame_energy_ratio_max": energy_ratio_max,
            "reads_after_the_hold": reads_after_the_hold,
            "read_recovery_after_the_hold": {
                name: consumer.top_ratio(
                    float(reading["recovered_deposit"]),
                    float(deposits[name]),
                )
                for name, reading in reads_after_the_hold.items()
            },
            "owner_route_against_the_declared_loop": {
                "declared": (
                    "the same tick body replayed through the feedback harness's own "
                    "advance_workspace and apply_drive from the same post-write page at "
                    "the amplitudes this episode's own owner route produced"
                ),
                "replay_page_sha256": replay_page,
                "owner_page_sha256": held_page,
                "the_owner_route_reproduces_the_declared_loop": bool(
                    replay_page == held_page
                ),
            },
            "snapshot_after_the_hold": surface_snapshot(owner),
        }
        return record, held
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def post_write_energy(workspace: Any) -> float:
    """One page's own read-frame energy, the denominator of the declared energy ratio."""

    return float(durability.squared_norm(durability.read_frame(workspace, READ_FRAME_PATH)))


def consumer_rounds(
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    config: StoreScaleConfig,
    *,
    page: Any,
    deposits: Mapping[str, float],
) -> dict[str, Any]:
    """The declared consumer loop: retrieve one direction, read it, act, read the store."""

    indices = tuple(int(index) for index in config.item_indices)
    count = len(indices)
    owner, home = consumer.open_owner(profile, workspace=page, prefix=config.owner_home_prefix)
    try:
        arrival_page = durability.page_sha256(page)
        snapshots = [surface_snapshot(owner)]
        rounds: list[dict[str, Any]] = []
        selected: list[int] = []
        for number in range(int(config.rounds)):
            query = int(number % count)
            spec = durability.ITEM_SPECS[query]
            retrieval = memory_read(owner, query)
            floor = float(consumer.READ_FLOOR_FRACTION) * float(deposits[spec.name])
            retrieved = float(retrieval["recovered_deposit"])
            reaches = bool(retrieved >= floor)
            selected_index = query if reaches else int((query + 1) % count)
            selected.append(selected_index)
            selected_spec = durability.ITEM_SPECS[selected_index]
            before_the_act = surface_snapshot(owner)
            frame_before = durability.read_frame(owner.state.resonant_workspace, READ_FRAME_PATH)
            act = write_declared_item(
                owner,
                selected_index,
                label=f"store-scale:round:{number}:act",
                budget=config.act_budget,
            )
            frame_after = durability.read_frame(owner.state.resonant_workspace, READ_FRAME_PATH)
            after_the_act = surface_snapshot(owner)
            increment = frame_after - frame_before
            reads = {durability.ITEM_SPECS[index].name: memory_read(owner, index) for index in indices}
            rounds.append(
                {
                    "round": int(number),
                    "query_item": spec.name,
                    "query_item_index": query,
                    "retrieved_deposit": retrieved,
                    "read_floor": floor,
                    "retrieved_reaches_the_floor": reaches,
                    "selected_item": selected_spec.name,
                    "selected_item_index": selected_index,
                    "selected_is_the_queried_item": bool(selected_index == query),
                    "act": act,
                    "act_increment_energy": float(durability.squared_norm(increment)),
                    "act_share_along_the_queried_direction": consumer.share_along(
                        increment, captures[query]["direction"]
                    ),
                    "act_share_along_the_selected_direction": consumer.share_along(
                        increment, captures[selected_index]["direction"]
                    ),
                    "read_matrix_row": {
                        name: float(reading["recovered_deposit"])
                        for name, reading in reads.items()
                    },
                    "snapshots_before_the_act": before_the_act,
                    "snapshots_after_the_act": after_the_act,
                    "moved_by_the_act": snapshot_movement(before_the_act, after_the_act),
                }
            )
            snapshots.append(after_the_act)
        final_record_page = owner.state.resonant_workspace
        final_page = durability.page_sha256(final_record_page)
        ledger = owner_ledger_sha256(owner)
        owner_state = str(owner.state.state_sha256)
        generation = int(owner.state.generation)
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)
    record = {
        "declared": (
            "the consumer loop on the store's own held page: each round retrieves the "
            "declared query direction through the owner's read, compares it against "
            "the declared read floor (the read floor fraction of that item's own "
            "measured deposit), acts with one owner write along the selected direction "
            "at the declared act budget, and then reads every declared direction, so "
            "each round's full read matrix and its surface movement are measured"
        ),
        "arrival_page_sha256": arrival_page,
        "rounds": rounds,
        "selected_items": [durability.ITEM_SPECS[index].name for index in selected],
        "snapshots": snapshots,
        "final_page_sha256": final_page,
        "final_owner_state_sha256": owner_state,
        "final_owner_ledger_sha256": ledger,
        "final_generation": generation,
    }
    return record, final_record_page


def matrix_analysis(
    store: Mapping[str, Any],
    rounds: Mapping[str, Any],
    config: StoreScaleConfig,
) -> dict[str, Any]:
    """The declared read matrix, its recovery, its interference and its drift."""

    indices = tuple(int(index) for index in config.item_indices)
    names = [durability.ITEM_SPECS[index].name for index in indices]
    deposits = dict(store["measured_deposits"])
    rows = [
        {name: float(reading["recovered_deposit"]) for name, reading in store["reads_after_the_hold"].items()}
    ]
    for entry in rounds["rounds"]:
        rows.append({name: float(value) for name, value in entry["read_matrix_row"].items()})
    recovery = [
        [consumer.top_ratio(float(row[name]), float(deposits[name])) for name in names]
        for row in rows
    ]
    selected = [int(entry["selected_item_index"]) for entry in rounds["rounds"]]
    interference: list[dict[str, Any]] = []
    for position, row in enumerate(rows):
        if position == 0:
            interference.append(
                {
                    "round": -1,
                    "declared": (
                        "the held page before any act: the declared baseline every "
                        "later ratio is taken against"
                    ),
                    "ratios": {name: 1.0 for name in names},
                }
            )
            continue
        acted_before = selected[: position]
        interference.append(
            {
                "round": int(position - 1),
                "acted_items_before": [
                    durability.ITEM_SPECS[index].name for index in acted_before
                ],
                "ratios": {
                    name: consumer.top_ratio(float(row[name]), float(rows[0][name]))
                    for name in names
                },
                "never_acted_items": [
                    name
                    for index, name in zip(indices, names)
                    if index not in set(acted_before)
                ],
            }
        )
    drift_rows = [
        {
            "round": int(entry["round"]),
            "ratios": interference[int(entry["round"]) + 1]["ratios"],
            "never_acted_items": interference[int(entry["round"]) + 1]["never_acted_items"],
        }
        for entry in rounds["rounds"]
    ]
    never_acted_ratios = [
        (name, float(ratio))
        for entry in drift_rows
        for name, ratio in entry["ratios"].items()
        if name in entry["never_acted_items"]
    ]
    greatest_never_acted_drift = max(
        (abs(ratio - 1.0) for _name, ratio in never_acted_ratios), default=0.0
    )
    queried_recovery = []
    for position, entry in enumerate(rounds["rounds"]):
        query = int(entry["query_item_index"])
        following = rows[position + 1][durability.ITEM_SPECS[query].name]
        queried_recovery.append(
            {
                "round": int(entry["round"]),
                "query_item": durability.ITEM_SPECS[query].name,
                "recovery_after_the_round": consumer.top_ratio(
                    float(following), float(deposits[durability.ITEM_SPECS[query].name])
                ),
            }
        )
    recovery_at_horizon = {
        name: consumer.top_ratio(float(rows[-1][name]), float(deposits[name]))
        for name in names
    }
    energy = [
        float(after["page_sha256"] != before["page_sha256"])
        for before, after in zip(rounds["snapshots"], rounds["snapshots"][1:])
    ]
    # The held page's own cross-item cells: each item's read divided by the queried
    # item's own deposit. They are reported because the requested measurement names
    # them, and they are degenerate on this store: every declared item's measured
    # deposit agrees to ~1e-15 relative, so every such cell is that item's own
    # recovery and none of them can separate two items. The falsifier for cross-item
    # leakage is the single-item read block, where the content of the page is known.
    held_cells = {
        name: {
            other: (
                None
                if float(deposits[other]) == 0.0
                else float(rows[0][name]) / float(deposits[other])
            )
            for other in names
        }
        for name in names
    }
    held_off_diagonal = [
        (name, other, value)
        for name, row in held_cells.items()
        for other, value in row.items()
        if name != other and value is not None
    ]
    held_greatest = max((abs(float(v)) for _n, _o, v in held_off_diagonal), default=None)
    held_least = min((abs(float(v)) for _n, _o, v in held_off_diagonal), default=None)
    deposit_spread = (
        None
        if not deposits
        else float(
            max(float(v) for v in deposits.values()) - min(float(v) for v in deposits.values())
        )
        / float(max(abs(float(v)) for v in deposits.values()))
        if max(abs(float(v)) for v in deposits.values()) > 0.0
        else 0.0
    )
    return {
        "declared": (
            "the read matrix rows are the owner's own reads of every declared "
            "direction on the held page before any act and after every round; "
            "recovery divides each read by that item's own measured deposit, "
            "interference divides each later read by the same item's read on the "
            "held page before any act, and the never-acted columns are the cells "
            "whose item the consumer has not yet selected, which is the cross-item "
            "reading"
        ),
        "item_names": names,
        "deposits": deposits,
        "read_matrix": rows,
        "recovery_matrix": recovery,
        "recovery_at_horizon": recovery_at_horizon,
        "recovery_at_horizon_min": float(min(recovery_at_horizon.values())),
        "recovery_at_horizon_max": float(max(recovery_at_horizon.values())),
        "queried_recovery": queried_recovery,
        "queried_recovery_min": float(min(row["recovery_after_the_round"] for row in queried_recovery)),
        "interference": interference,
        "drift_rows": drift_rows,
        "never_acted_cells": [{"item": name, "ratio": ratio} for name, ratio in never_acted_ratios],
        "greatest_never_acted_read_drift": float(greatest_never_acted_drift),
        "held_page_cross_item_cells": held_cells,
        "held_page_off_diagonal_cells": [
            {"item": name, "queried_item": other, "normalized_read": value}
            for name, other, value in held_off_diagonal
        ],
        "held_page_greatest_off_diagonal_read": held_greatest,
        "held_page_least_off_diagonal_read": held_least,
        "measured_deposit_relative_spread": deposit_spread,
        "page_moved_in_every_round": bool(all(value > 0.0 for value in energy)),
        "generation_moved_by": int(rounds["final_generation"])
        - int(rounds["snapshots"][0]["generation"]),
        "rounds": int(config.rounds),
        "grid_cells": int(len(indices) * int(config.rounds)),
    }


def identity_control(
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    config: StoreScaleConfig,
    *,
    page: Any,
    query_index: int,
) -> dict[str, Any]:
    """The declared identity control on two copies of the store's final page."""

    count = len(config.item_indices)
    settings = replace(
        consumer.MemoryConsumerConfig(),
        target_item_index=int(query_index),
        mismatch_item_index=int((query_index + 1) % count),
        fallback_item_index=int((query_index + 2) % count),
        write_budget=float(config.write_budget),
        act_budget=float(config.act_budget),
        owner_home_prefix="mss-identity-",
    )
    held = {"episode": "the store's final page after the declared rounds"}
    normal = consumer.consumer_episode(
        profile,
        page,
        captures,
        settings,
        held_episode=held,
        name="store-scale:F-normal-read",
    )
    suppressed = consumer.consumer_episode(
        profile,
        page,
        captures,
        settings,
        held_episode=held,
        name="store-scale:B-identity-control-read-suppressed",
        read_suppressed=True,
    )
    normal_share = normal["statistic"]["share_along_target"]
    suppressed_share = suppressed["statistic"]["share_along_target"]
    difference = (
        None
        if normal_share is None or suppressed_share is None
        else float(normal_share) - float(suppressed_share)
    )
    pages = {
        "normal": normal["invariants"]["page_on_arrival"],
        "suppressed": suppressed["invariants"]["page_on_arrival"],
    }
    return {
        "declared": (
            "two fresh owners take a copy of the store's byte-identical final page; "
            "one runs the declared consumer policy with its retrieval, one with the "
            "retrieval suppressed, and the share of each act's increment along the "
            "queried direction is compared. This is the consumer receipt's own "
            "identity control, run on a page that eight rounds of use produced"
        ),
        "query_item": durability.ITEM_SPECS[int(query_index)].name,
        "query_item_index": int(query_index),
        "read_floor_fraction": float(consumer.READ_FLOOR_FRACTION),
        "separation_margin": float(consumer.SEPARATION_MARGIN),
        "pursuit_margin": float(consumer.PURSUIT_MARGIN),
        "pages": pages,
        "the_two_arms_start_from_a_byte_identical_page": bool(
            pages["normal"] == pages["suppressed"]
        ),
        "normal": {
            "retrieved_deposit": float(normal["retrieval"]["retrieved_deposit"]),
            "read_floor": float(normal["decision"]["read_floor"]),
            "retrieved_reaches_the_floor": bool(normal["decision"]["retrieved_reaches_the_floor"]),
            "selected_item": str(normal["decision"]["selected_item"]),
            "selected_is_the_queried_item": bool(normal["decision"]["selected_is_the_target"]),
            "share_along_the_queried_direction": None if normal_share is None else float(normal_share),
            "act_increment_energy": float(normal["statistic"]["act_increment_energy"]),
        },
        "suppressed": {
            "read_calls": int(suppressed["retrieval"]["read_calls"]),
            "retrieved_deposit": float(suppressed["retrieval"]["retrieved_deposit"]),
            "runner_instrument_read": (
                None
                if suppressed["instrument_read_by_the_runner"] is None
                else float(suppressed["instrument_read_by_the_runner"]["recovered_deposit"])
            ),
            "read_floor": float(suppressed["decision"]["read_floor"]),
            "selected_item": str(suppressed["decision"]["selected_item"]),
            "selected_is_the_queried_item": bool(suppressed["decision"]["selected_is_the_target"]),
            "share_along_the_queried_direction": None
            if suppressed_share is None
            else float(suppressed_share),
            "act_increment_energy": float(suppressed["statistic"]["act_increment_energy"]),
        },
        "share_difference": difference,
        "the_normal_arm_pursues_the_queried_direction": bool(
            normal_share is not None
            and float(normal_share) >= float(consumer.PURSUIT_MARGIN)
        ),
        "the_suppressed_arm_does_not": bool(
            suppressed_share is not None
            and float(suppressed_share) < float(consumer.PURSUIT_MARGIN)
        ),
        "the_control_still_separates_at_the_end_of_use": bool(
            difference is not None
            and float(difference) >= float(consumer.SEPARATION_MARGIN)
        ),
        "the_suppressed_arm_saw_the_field_carry_the_item_anyway": bool(
            suppressed["instrument_read_by_the_runner"] is not None
            and float(suppressed["instrument_read_by_the_runner"]["recovered_deposit"]) > 0.0
        ),
    }


def single_item_read_block(
    profile: Any,
    config: StoreScaleConfig,
    *,
    deposits: Mapping[str, float],
) -> dict[str, Any]:
    """What the store reads when exactly one declared item was written.

    Cross-item leakage needs a page whose content is known: one fresh owner per
    declared item writes that item alone at the declared write budget, every
    declared direction is read on it, and every read is normalized by the written
    item's own diagonal read. The diagonal cells are 1.0 by construction; the
    off-diagonal cells are the measured contamination, in units of the held
    item's own deposit. The first owner also reads every direction before
    anything is written, which is the control that says a read is zero when
    there is nothing there.
    """

    indices = tuple(int(index) for index in config.item_indices)
    names = [durability.ITEM_SPECS[index].name for index in indices]
    allowance = float(config.read_leakage_allowance)
    unwritten_reads: dict[str, float] | None = None
    unwritten_page = ""
    pages: dict[str, Any] = {}
    for position, witness in enumerate(indices):
        witness_name = durability.ITEM_SPECS[witness].name
        owner, home = consumer.open_owner(profile, prefix=config.owner_home_prefix)
        try:
            if position == 0:
                unwritten_page = durability.page_sha256(owner.state.resonant_workspace)
                unwritten_reads = {
                    name: float(memory_read(owner, index)["recovered_deposit"])
                    for index, name in zip(indices, names)
                }
            blank_page = durability.page_sha256(owner.state.resonant_workspace)
            write = write_declared_item(
                owner,
                witness,
                label=f"store-scale:isolation:write:{witness}",
                budget=config.write_budget,
            )
            reads = {
                name: float(memory_read(owner, index)["recovered_deposit"])
                for index, name in zip(indices, names)
            }
            written_page = durability.page_sha256(owner.state.resonant_workspace)
        finally:
            owner.close()
            shutil.rmtree(home, ignore_errors=True)
        diagonal = float(reads[witness_name])
        pages[witness_name] = {
            "witness_item": witness_name,
            "witness_item_index": int(witness),
            "blank_page_sha256": blank_page,
            "written_page_sha256": written_page,
            "the_write_moves_the_page": bool(blank_page != written_page),
            "write": write,
            "diagonal_read": diagonal,
            "measured_deposit": float(deposits[witness_name]),
            "diagonal_recovery": consumer.top_ratio(
                diagonal, float(deposits[witness_name])
            ),
            "reads": dict(reads),
            "normalized_reads": (
                None
                if diagonal == 0.0
                else {name: float(value) / diagonal for name, value in reads.items()}
            ),
        }
    cells: dict[str, dict[str, float | None]] = {}
    for witness_name, page in pages.items():
        normalized = page["normalized_reads"]
        cells[witness_name] = (
            None
            if normalized is None
            else {name: float(value) for name, value in normalized.items()}
        )
    off_diagonal = [
        (name, witness_name, abs(float(cell)))
        for witness_name, row in cells.items()
        if row is not None
        for name, cell in row.items()
        if name != witness_name
    ]
    diagonal_recoveries = {
        name: page["diagonal_recovery"] for name, page in pages.items()
    }
    greatest = max((value for _name, _witness, value in off_diagonal), default=None)
    least_diagonal = min(diagonal_recoveries.values(), default=None)
    separation = (
        None
        if greatest is None or least_diagonal is None or greatest == 0.0
        else float(least_diagonal) / float(greatest)
    )
    unwritten_greatest = (
        None if unwritten_reads is None else max((abs(v) for v in unwritten_reads.values()), default=0.0)
    )
    mean_deposit = (
        sum(float(value) for value in deposits.values()) / float(len(deposits))
        if deposits
        else 0.0
    )
    unwritten_relative = (
        None if unwritten_greatest is None or mean_deposit == 0.0 else float(unwritten_greatest) / mean_deposit
    )
    return {
        "declared": (
            "one fresh owner per declared item writes that item alone through the "
            "owner write path at the declared write budget and reads every declared "
            "direction on the resulting page; each read is divided by the written "
            "item's own diagonal read, so the diagonal cell is 1.0 by construction "
            "and every off-diagonal cell is the measured cross-item read in units of "
            "the held item's own deposit. The first owner reads every direction on "
            "its blank page before writing, which is the unwritten-page control"
        ),
        "item_names": names,
        "cells": cells,
        "diagonal_recoveries": diagonal_recoveries,
        "off_diagonal_cells": [
            {"item": name, "held_item": witness, "normalized_read": value}
            for name, witness, value in off_diagonal
        ],
        "greatest_off_diagonal_read": greatest,
        "least_diagonal_recovery": least_diagonal,
        "declared_leakage_allowance": allowance,
        "declared_separation_factor": float(config.leakage_separation_factor),
        "measured_separation_factor": separation,
        "the_store_leaks_nothing_across_items": bool(
            greatest is not None and float(greatest) <= allowance
        ),
        "the_leakage_measure_separates_a_written_item_from_an_unwritten_one": bool(
            least_diagonal is not None
            and float(least_diagonal) >= float(consumer.READ_FLOOR_FRACTION)
            and (
                separation is None
                or float(separation) >= float(config.leakage_separation_factor)
            )
        ),
        "unwritten_page_reads": unwritten_reads,
        "unwritten_page_sha256": unwritten_page,
        "unwritten_page_greatest_read": unwritten_greatest,
        "unwritten_page_read_relative_to_the_mean_deposit": unwritten_relative,
        "the_unwritten_page_reads_nothing": bool(
            unwritten_relative is not None and float(unwritten_relative) <= allowance
        ),
        "pages": pages,
    }


def part_b_block(profile: Any, config: StoreScaleConfig) -> dict[str, Any]:
    """Every declared part B block, measured in order."""

    capture_config = durability.DurabilityConfig(write_budget=float(config.write_budget))
    capture_sequences = durability.capture_items(capture_config, profile)
    captures = consumer.capture_block(profile, consumer.MemoryConsumerConfig(
        write_budget=float(config.write_budget),
        target_item_index=int(config.item_indices[0]),
        mismatch_item_index=int(config.item_indices[1 % len(config.item_indices)]),
        fallback_item_index=int(config.item_indices[2 % len(config.item_indices)]),
    ))
    phase_reference = consumer.phase_reference_for(profile, capture_sequences)
    refinement = consumer.neutral_gain_refinement(
        profile,
        capture_sequences,
        phase_reference,
        consumer.MemoryConsumerConfig(write_budget=float(config.write_budget)),
    )
    gain = float(refinement["measured_gain"])
    loop = feedback.FeedbackConfig()
    phase_degrees = float(loop.neutral_gain_phase_degrees)
    indices = tuple(int(index) for index in config.item_indices)
    readouts = feedback.item_phase_readouts(
        loop,
        capture_sequences,
        profile,
        ticks=int(config.store_phase_readout_ticks),
        indices=indices,
    )
    per_item = feedback.per_item_phase_references(loop, capture_sequences, readouts, indices)
    published_references = {
        int(index): {
            "isolated_signed_projection": float(reference["isolated_signed_projection"]),
            "quadrature_scale": float(reference["scale"]),
            "quadrature_scale_tick": int(reference["quadrature_scale_tick"]),
        }
        for index, reference in per_item.items()
    }
    neutrality = {
        int(index): consumer.neutrality_probe(
            profile,
            capture_sequences,
            phase_reference,
            consumer.MemoryConsumerConfig(write_budget=float(config.write_budget)),
            item_index=int(index),
            gain=gain,
        )
        for index in config.neutrality_probe_items
    }
    store, held_page = store_episode(
        profile,
        capture_sequences,
        config,
        gain=gain,
        phase_degrees=phase_degrees,
        phase_references=per_item,
    )
    rounds, final_page = consumer_rounds(
        profile,
        capture_sequences,
        config,
        page=held_page,
        deposits=store["measured_deposits"],
    )
    matrix = matrix_analysis(store, rounds, config)
    leakage = single_item_read_block(
        profile, config, deposits=store["measured_deposits"]
    )
    last_query = int(rounds["rounds"][-1]["query_item_index"])
    identity = identity_control(
        profile,
        capture_sequences,
        config,
        page=final_page,
        query_index=last_query,
    )
    recovery_allowance = float(config.read_recovery_allowance)
    drift_allowance = float(config.read_drift_allowance)
    verdicts = {
        "the_store_holds_every_declared_item": bool(
            float(matrix["recovery_at_horizon_min"]) >= recovery_allowance
        ),
        "every_round_retrieves_its_queried_direction": bool(
            all(bool(entry["retrieved_reaches_the_floor"]) for entry in rounds["rounds"])
        ),
        "the_consumer_pursues_what_it_retrieved": bool(
            all(bool(entry["selected_is_the_queried_item"]) for entry in rounds["rounds"])
        ),
        "the_other_items_reads_stay_inside_the_declared_band": bool(
            float(matrix["greatest_never_acted_read_drift"]) <= drift_allowance
        ),
        "the_store_leaks_nothing_across_items": bool(
            leakage["the_store_leaks_nothing_across_items"]
        ),
        "the_leakage_measure_separates_a_written_item_from_an_unwritten_one": bool(
            leakage[
                "the_leakage_measure_separates_a_written_item_from_an_unwritten_one"
            ]
        ),
        "the_unwritten_page_reads_nothing": bool(
            leakage["the_unwritten_page_reads_nothing"]
        ),
        "the_acts_keep_moving_the_page": bool(matrix["page_moved_in_every_round"]),
        "the_owner_route_reproduces_the_declared_loop": bool(
            store["owner_route_against_the_declared_loop"][
                "the_owner_route_reproduces_the_declared_loop"
            ]
        ),
        "the_measured_gain_is_neutral_on_every_probed_items_page": bool(
            all(
                bool(probe["the_measured_gain_is_neutral_on_this_items_page"])
                for probe in neutrality.values()
            )
        ),
        "the_identity_control_still_separates_at_the_end_of_use": bool(
            identity["the_control_still_separates_at_the_end_of_use"]
        ),
    }
    return {
        "captures": captures,
        "item_phase_references": published_references,
        "phase_readout_declared": {
            "phase_degrees": phase_degrees,
            "quadrature_coefficient": math.sin(math.radians(phase_degrees)),
            "readout_ticks": int(config.store_phase_readout_ticks),
            "declared": (
                "each declared item's own quadrature read-back, measured on that item's "
                "own isolated drift by the feedback harness's own instrument; at the "
                "declared phase angle the quadrature coefficient is the sine above"
            ),
        },
        "gain": {
            "refinement": refinement,
            "neutrality_probes": {
                str(index): probe for index, probe in neutrality.items()
            },
        },
        "store": store,
        "rounds": rounds,
        "matrix": matrix,
        "leakage": leakage,
        "identity_control": identity,
        "verdicts": verdicts,
        "honest_negatives": [
            text
            for condition, text in (
                (
                    verdicts["the_store_holds_every_declared_item"],
                    "at least one declared item's read does not recover its deposit at "
                    "the declared allowance after the declared rounds of use",
                ),
                (
                    verdicts["the_other_items_reads_stay_inside_the_declared_band"],
                    "the reads of the items the consumer has not yet acted on drift "
                    "outside the declared band across the rounds, so the store's items "
                    "are not independent under use",
                ),
                (
                    verdicts["the_store_leaks_nothing_across_items"],
                    "writing one declared item alone makes the store return another "
                    "declared item's read above the declared leakage allowance, so the "
                    "store's items are not separable by their own directions",
                ),
                (
                    verdicts["the_leakage_measure_separates_a_written_item_from_an_unwritten_one"],
                    "the cross-item read measure does not separate a written item from "
                    "an unwritten one on this profile, so the leakage band above is "
                    "vacuous",
                ),
                (
                    verdicts["the_owner_route_reproduces_the_declared_loop"],
                    "the owner route's held page is not the page the declared loop's own "
                    "primitives produce from the same start, so the held store is this "
                    "route's own measurement",
                ),
                (
                    verdicts["the_measured_gain_is_neutral_on_every_probed_items_page"],
                    "the measured neutral gain is not neutral on at least one probed "
                    "item's own page",
                ),
                (
                    verdicts["the_identity_control_still_separates_at_the_end_of_use"],
                    "the identity control does not separate on the store's final page: "
                    "the suppressed retrieval's act is not tellable from the normal "
                    "one after the declared rounds of use",
                ),
            )
            if not condition
        ],
    }


# --------------------------------------------------------------------------
# receipt
# --------------------------------------------------------------------------
def reading_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """What the measured blocks say, in one reading."""

    part_a = body.get("part_a") or {"verdicts": {}, "honest_negatives": []}
    part_b = body.get("part_b") or {"verdicts": {}, "honest_negatives": []}
    verdicts = {**part_a["verdicts"], **part_b["verdicts"]}
    return {
        "predicate": (
            "each declared surface movement predicate in part A, and in part B the "
            "declared recovery, interference, route and identity predicates, applied "
            "unchanged to every arm and control"
        ),
        "verdicts": verdicts,
        "honest_negatives": [
            *part_a["honest_negatives"],
            *part_b["honest_negatives"],
        ],
        "limitations": [
            "the acts are measured on one declared profile, one declared direction "
            "set, one declared act budget and one declared drive amplitude; nothing "
            "here measures a distribution over profiles, items or budgets",
            "the coupled realization's act is measured as a movement of the "
            "realization's own declared readout and of its own working state, which no "
            "operation writes back into the page: the receipt of this family's own "
            "transceiver work states that no such operation exists today, so the "
            "non-destructive act is measured on the surface that carries it",
            "the store's hold is short by declaration, so this receipt makes no claim "
            "about holding eight items over a long horizon; it claims what the "
            "declared rounds measure",
            "the identity control separates two policy arms on two copies of one "
            "byte-identical page; it is a direction measurement, not a claim that "
            "acting on a memory is useful in any wider sense",
        ],
    }


def build_receipt(config: StoreScaleConfig | None = None) -> dict[str, Any]:
    """Every declared measurement, assembled into one receipt."""

    settings = config or StoreScaleConfig()
    started = time.perf_counter()
    profile = flat_profile()
    part_a = part_a_block(profile, settings) if settings.part_a else None
    part_b = part_b_block(profile, settings) if settings.part_b else None
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "question": (
            "the field's memory survives being written and read; can a consumer act "
            "on it through a surface that leaves the stored memory untouched, and "
            "does a multi-item store survive being used round after round?"
        ),
        "declared": {
            "config": settings.as_dict(),
            "arms": {
                "A1-owner-write-act": (
                    "the remembered direction is rewritten by the consumer's act, the "
                    "known destructive case"
                ),
                "A2-owner-drive-act": (
                    "the consumer acts on a transceiver the owner condensed from a "
                    "learned chart: the readout moves with the stimulus and the page "
                    "does not"
                ),
                "A3-coupled-drive-act": (
                    "the consumer acts on the declared coupled input realization "
                    "outside the owner's surface; the shipped identity realization is "
                    "the inert control on the same act"
                ),
                "C1-drive-on-an-unwritten-page": (
                    "the A2 act on a page nothing was written to: the readout movement "
                    "must not depend on the memory and the memory read must be zero"
                ),
                "store-NxR": (
                    "the declared items written through the owner write path, held "
                    "through the owner's own page at the measured neutral gain, then "
                    "queried and acted on for the declared rounds"
                ),
            },
            "statistic": (
                "part A reports each arm's readout pair and the four declared surface "
                "digests before and after its act, with the relative difference of the "
                "stored memory's own read. Part B reports the read matrix of every "
                "declared direction across the declared rounds, its recovery against "
                "each item's own measured deposit, its interference against the held "
                "page's own reads, the single-item page's off-diagonal reads as the "
                "cross-item leakage measure, and the identity control's share difference"
            ),
            "content_digest_definition": (
                "sha256 of the canonical JSON (sorted keys, no insignificant "
                "whitespace, allow_nan=False) of the measured body with the declared "
                "wall-clock leaves stripped and, by the declared rule, every value "
                "derived from a stripped value stripped with them, taken before the "
                "digest itself is attached"
            ),
            "content_digest_strip_keys": list(STRIP_KEYS),
            "content_digest_strip_keys_source": (
                "run_fractal_geometry_exploration.TIMING_KEYS (the clock leaves this "
                "family's receipts already declare, which include receipt_sha256, a "
                "chained hash of a timed receipt) extended by this runner with the "
                "clock-derived digests it publishes"
            ),
            "content_digest_clock_leaf_keys": list(CLOCK_LEAF_KEYS),
            "content_digest_clock_derived_keys": {
                "current_manifest_sha256": (
                    "the owner's current checkpoint manifest: it chains over receipts "
                    "that carry elapsed_seconds, so it differs between two identical "
                    "runs while the event ids, the active revision ids and the event "
                    "count do not"
                ),
                "owner_ledger_sha256": (
                    "this runner's own ledger digest: it is the sha256 of the event "
                    "ids, the active revision ids, the event count and the current "
                    "manifest hash, so it inherits the manifest's clock dependence"
                ),
                "parent_manifest_sha256": (
                    "the same chaining hash as the owner publishes it in its receipts"
                ),
            },
            "content_digest_rule": (
                "the digest covers measured content: a key is stripped when it is a "
                "declared wall-clock leaf, and by rule when it is a value derived from "
                "a stripped value -- a chained manifest hash, a chained receipt hash, "
                "or a digest computed over one. Derived-from-stripped values are "
                "stripped as a class rather than listed case by case. Movement booleans "
                "this runner computes from those digests (the ledger-moved and "
                "owner-state-moved flags of every surface pair, and every page, frame "
                "and state digest, which are content addresses with no clock input) "
                "stay in the body, so stripping the clock-derived digests removes no "
                "measurement of what the surface did; it removes the two numbers whose "
                "value depends on wall-clock time"
            ),
            "declared_instruments": {
                "read_frame_and_captures": (
                    "run_fractal_durability_exploration.read_frame, capture_items, "
                    "overlap_matrix, page_sha256, squared_norm"
                ),
                "loop_law_and_gain": (
                    "run_fractal_feedback_exploration.phase_signal, loop_amplitude, "
                    "apply_drive, advance_workspace, item_phase_readouts, "
                    "per_item_phase_references"
                ),
                "consumer_path": (
                    "run_memory_consumer_path.open_owner, named_direction, "
                    "capture_block, phase_reference_for, neutral_gain_refinement, "
                    "neutrality_probe, consumer_episode, share_along"
                ),
                "coupled_realization": (
                    "run_owner_surface_options.realization_kernel, authority_series, "
                    "its declared coupled and shipped relation constants"
                ),
                "owner_write_path": "FieldIntelligenceOwner.write_packet_impulse",
                "owner_read_operation": "FieldIntelligenceOwner.read_packet_deposit",
                "owner_transceiver": (
                    "FieldIntelligenceOwner.configure_variable/configure_chart/"
                    "admit_observation/condense_transceiver/reset_transceiver/"
                    "advance_transceivers/inspect_transceivers"
                ),
            },
        },
        "part_a": part_a,
        "part_b": part_b,
        "runtime_seconds": float(time.perf_counter() - started),
    }
    body["reading"] = reading_block(body)
    assert_finite(body)
    body["receipt_digest"] = receipt_digest(body)
    return body


def report(receipt: Mapping[str, Any]) -> str:
    """The receipt's own figures, a few lines per declared block."""

    lines = [f"schema: {receipt['schema']}"]
    part_a = receipt.get("part_a")
    if part_a is not None:
        lines.append("part A - the act, by arm:")
        for name, arm in part_a["arms"].items():
            moved = arm["snapshots"]["moved"]
            lines.append(
                f"  {name:<30} readout {arm['readout']['before']!r} -> "
                f"{arm['readout']['after']!r}  page_moved={moved['page_moved']} "
                f"owner_state_moved={moved['owner_state_moved']} "
                f"memory_unchanged={arm['memory_read']['the_stored_memory_is_unchanged']}"
            )
    part_b = receipt.get("part_b")
    if part_b is not None:
        matrix = part_b["matrix"]
        lines.append(
            "part B - the store: gain "
            f"{part_b['gain']['refinement']['measured_gain']!r}, "
            f"items {len(matrix['item_names'])}, rounds {matrix['rounds']}, "
            f"cells {matrix['grid_cells']}"
        )
        lines.append(
            f"  recovery at horizon min {matrix['recovery_at_horizon_min']!r} "
            f"max {matrix['recovery_at_horizon_max']!r}; queried recovery min "
            f"{matrix['queried_recovery_min']!r}"
        )
        lines.append(
            "  greatest never-acted read drift "
            f"{matrix['greatest_never_acted_read_drift']!r} "
            f"(band {receipt['declared']['config']['read_drift_allowance']!r})"
        )
        leakage = part_b["leakage"]
        lines.append(
            "  cross-item leakage on the single-item pages: greatest off-diagonal "
            f"{leakage['greatest_off_diagonal_read']!r} (band "
            f"{leakage['declared_leakage_allowance']!r}), least diagonal recovery "
            f"{leakage['least_diagonal_recovery']!r} (floor "
            f"{receipt['declared']['config']['read_floor_fraction']!r}), separation "
            f"{leakage['measured_separation_factor']!r} (declared "
            f"{leakage['declared_separation_factor']!r})"
        )
        lines.append(
            "  unwritten-page greatest read "
            f"{leakage['unwritten_page_greatest_read']!r} "
            f"({leakage['unwritten_page_read_relative_to_the_mean_deposit']!r} of the "
            "mean deposit)"
        )
        identity = part_b["identity_control"]
        lines.append(
            f"  identity control at the end: share {identity['normal']['share_along_the_queried_direction']!r} "
            f"vs {identity['suppressed']['share_along_the_queried_direction']!r} "
            f"(difference {identity['share_difference']!r})"
        )
    lines.append("verdicts:")
    for name, value in receipt["reading"]["verdicts"].items():
        lines.append(f"  {name}: {value}")
    lines.append(f"receipt_digest: {receipt['receipt_digest']}")
    lines.append(f"runtime_seconds: {receipt['runtime_seconds']:.2f}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RECEIPT_PATH)
    parser.add_argument("--items", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=DECLARED_ROUNDS)
    parser.add_argument("--part-a", dest="part_a", action="store_true", default=True)
    parser.add_argument("--no-part-a", dest="part_a", action="store_false")
    parser.add_argument("--part-b", dest="part_b", action="store_true", default=True)
    parser.add_argument("--no-part-b", dest="part_b", action="store_false")
    arguments = parser.parse_args(argv)
    indices = tuple(range(int(arguments.items)))
    config = StoreScaleConfig(
        part_a=bool(arguments.part_a),
        part_b=bool(arguments.part_b),
        item_indices=indices,
        rounds=int(arguments.rounds),
        neutrality_probe_items=indices,
    )
    receipt = build_receipt(config)
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(report(receipt))
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
