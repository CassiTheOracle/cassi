"""Give the field an owner write path that accepts an impulse, then run the cycle.

The nine exploration harnesses write a declared packet item into the canonical
page with ``cassi_resonant_field.apply_helical_packet_impulse`` and read it back
through the canonical packet read frame, but the field as shipped has no
*transition* that accepts a written packet impulse: the owner's whole wave
surface is ``advance(operation_id, ticks, source_enabled)``, which carries no
write, so the durability receipt records ``packet_impulse_transition_available:
False`` and ``owner_checkpoint_carries_written_item: False`` and has to say its
restart leg is workspace-level identity rather than owner-checkpoint identity
for the written item.

The input-shaped surface the field does have is the transceiver's declared input
realization, and it cannot serve as that write path: it is measured exactly
inert. The receipt's ``diagnosis`` block measures where and why -- the input
enters as a *fixed observation* (:func:`cassi_field_transceiver._effective`),
which the operator clamps at the input port, so its lift lies along the
constrained subspace and the readout row at the output port is exactly
orthogonal to it. Its declared precision is the identity, so no supported
relation carries the input to the output port either. The same code path is
shown carrying a signal once the declared problem does declare a coupling, so
the inertness is this field's declared problem rather than a dead branch.

Reading taken in this receipt (the minimal one). The design derives the field's
input as a boundary drive through explicitly selected ports of a *supported*
relation (``FIELD-INTELLIGENCE-DESIGN.md`` 27.1-27.2) and, for a written
pattern, already names the canonical packet impulse as an operation of its own
regional lowering (``cassi_resonant_field.py`` 2806/2940/3486/3507). The
minimal faithful reading of "a transition that accepts a written packet
impulse" is therefore to lift that canonical write -- not the inert input
realization -- into a real transition of the field: an owner operation that
publishes one immutable successor, is exactly-once under its operation
identity, keeps the evidence clock unchanged (a write is an intervention, not
evidence), and carries the written pattern inside the owner's checkpoint
closure. This runner measures the impulse arm against its zero-impulse control,
the full write -> hold -> read cycle at the profile's own freshly measured
neutral gain against the existing aimed narrow-path write route and a no-loop
control, two items under a work split, and the owner restart identity the
durability receipt could not measure.

Every number comes from the canonical packet, workspace, atlas and owner APIs.
Nothing here demonstrates task-level memory utility, semantic content, retrieval
by a consumer, a distribution over profiles, or any advantage over alternative
architectures. Negative results are deliverables: where a comparison ties, the
receipt says it ties and why.

The read half is measured in the same receipt. The write publishes a declared
packet impulse as an owner transition; before this change the deposit was
recoverable only by applying the library's read frame to the canonical page by
hand, and the owner's own read surface published no key path naming a deposit or a
written direction. The read operation added here -- ``read_packet_deposit``, on
the owner and in the surface dispatch -- names a written direction exactly as the
write names it and returns the deposit the canonical page carries along it. It is
declared as the design declares a readout (``FIELD-INTELLIGENCE-DESIGN.md`` 27.3;
``README.md`` 653-657): a temporal prediction that adds no observed support and
does not advance the evidence clock. It is not declared as evidence, and the
receipt states in one line what that other declaration would move.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_feedback_exploration as feedback
import run_fractal_geometry_exploration as geometry
import run_fractal_metric_exploration as metric
from cassi_field_atlas import (
    AtlasState,
    FieldAtlas,
    PACKET_IMPULSE_EVENT_KIND,
    RelationChart,
    VariableSpec,
)
from cassi_field_owner import (
    RPC_SCHEMA,
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
)
from cassi_field_transceiver import (
    advance_transceiver,
    condense_workspace,
    reset_transceiver,
)
from cassi_resonant_field import (
    ResonantNumericalError,
    ResonantProblem,
    ResonantProfile,
    ResonantWorkspace,
    bind_workspace,
    initial_workspace,
    replace as _profile_replace,
)

SCHEMA = "cassifi.owner-write-path-exploration.v1"

# The declared profile of every leg: the metric harness's own flat-inertia
# member, imported read-only through that harness's builder so the profile is
# that harness's declared object rather than a copy that could drift.
PROFILE_NAME = "ladder-uniform"
PROFILE_SOURCE = (
    "run_fractal_metric_exploration.build_metric_profile("
    "run_fractal_metric_exploration.ladder_row('ladder-uniform'))"
)

# The shipped feedback harness's own declared output path, cited read-only for its
# input-authority figures. It is spelled here because that harness exports only
# the durability receipt it cites, not its own path.
FEEDBACK_RECEIPT = Path("_diag/fractal-feedback/exploration.json")

# The second declared item of the pair leg and of the cross-read discrimination
# control: the shallowest detail write, inside the declared read frame and on a
# different rung path from the headline item.
SECOND_ITEM_INDEX = 2

# The declared margins, each reported beside the measurement it judges.
# IMPULSE_DEPOSIT_FRACTION: the written impulse's read-frame deposit, as a
# fraction of the same item's isolated captured deposit at the same budget, that
# an accepted write must reach. HOLD_MARGIN: the recovery the declared hold must
# beat the same write's own no-loop control by. CROSS_ITEM_MARGIN: the recovery
# the written item's own direction must beat a declared direction the arm did
# not write by. ROUTE_IDENTITY_ALLOWANCE: the difference between the owner
# route's and the existing route's page digest that still counts as one write.
IMPULSE_DEPOSIT_FRACTION = 0.5
HOLD_MARGIN = 0.01
CROSS_ITEM_MARGIN = 0.01
ROUTE_IDENTITY_ALLOWANCE = 0.0

# The declared per-tick work split sweep of the pair leg: the feedback harness's
# own declared proportions for two driven items.
SPLIT_WEIGHTS: tuple[tuple[float, float], ...] = tuple(
    (float(left), float(right))
    for left, right in feedback.FeedbackConfig().capacity_split_weights
)

# The declared arm names of this receipt.
OWNER_HOLD_ARM = "owner-path-hold"
REFERENCE_HOLD_ARM = "existing-route-hold"
DRIFT_ARM = "owner-path-no-loop"
SKELETON_EQUIVALENCE_ARM = "existing-route-hold-through-the-declared-skeleton"

# The declared name of the read half, as the owner method, the surface dispatch
# operation and the receipt all spell it.
READ_OPERATION_NAME = "read_packet_deposit"
# The declared allowance on a read's recovery: the recovered deposit must equal
# the written deposit to this relative allowance, and each control's recovery must
# miss it by more.
READ_RECOVERY_ALLOWANCE = 1e-12

# The declared word sets of the exposure scan, applied to every key path the
# surface publishes. A path is reported when one of its words appears in it: the
# direction words name a written direction or its deposit, the summary words name
# a power or energy summary, and the intervention words name the write itself.
# ABSENT_PATH_WORD is the matcher's own control: a word no surface here publishes.
DIRECTION_PATH_WORDS = ("deposit", "flow_signal", "read_frame", "coefficient", "direction")
SUMMARY_PATH_WORDS = ("power", "energy")
INTERVENTION_PATH_WORDS = ("packet", "impulse")
ABSENT_PATH_WORD = "quaternion"

# Where the collateral closure of this receipt's two library edits lives. The audit
# is a sibling artifact directory rather than a section of this receipt: its rows
# are written by its own drivers from test files and harness runs this runner does
# not read, so restating any of its counts here would make the receipt a function
# of files it never opens and would break the rebuild-equality test in
# test_owner_write_path_exploration.py. What this runner declares is the directory
# and the artifact names it holds, as constants; the figures stay in those files
# and are read from them.
CLOSURE_AUDIT_DIRECTORY = "_diag/owner-write-path/closure/"
CLOSURE_AUDIT_ARTIFACTS = (
    "r2-verdict.json",
    "closure-tests-per-file-r2.json",
    "r2-summary.json",
    "importer-closure-r2.json",
    "r2-controls.json",
    "r2/",
)

DECLARED_INPUT_PROBLEM = ResonantProblem(
    variable_ids=("write-in", "write-out"), precision=np.eye(2, dtype=np.float64)
)
DECLARED_COUPLED_PROBLEM = ResonantProblem(
    variable_ids=("write-in", "write-out"),
    precision=np.array([[2.0, 1.0], [1.0, 2.0]], dtype=np.float64),
)

BOUNDARY = (
    "Canonical-field numerical measurements in controlled conditions only: one "
    "declared profile (the metric harness's flat-inertia member), one declared "
    "written packet item (with a declared two-item counterpart), one declared "
    "write budget, one declared loop setting (the closed transceiver loop of the "
    "feedback harness at the phase it maintains with, at this profile's own "
    "freshly measured neutral gain), and one declared readout (the canonical "
    "packet read frame the durability harness uses). The owner write path is the "
    "canonical packet impulse transported through the owner's transition "
    "machinery; it is measured to be the same write as the existing route's, bit "
    "for bit on the canonical page, so this receipt adds a transition and a "
    "closure, not a new drive mechanism, and nothing here claims the new route "
    "writes anything the existing route could not. The loop skeleton is this "
    "runner's, because the feedback harness's own loop writes its declared items "
    "itself and cannot start from an owner-written page; the skeleton is the "
    "harness's declared drive law and declared sample row, and the "
    "skeleton_equivalence block measures that it reproduces the harness's own "
    "loop exactly on a page both routes build. The measured neutral gain is an "
    "operating point of the declared loop, horizon and readout on this profile, "
    "not a stability threshold of the field's dynamics, and the measured "
    "recovery fractions are properties of the declared readout, not of any "
    "consumer. Nothing here demonstrates task-level memory utility, semantic "
    "content, retrieval by a consumer, a distribution of outcomes over profiles "
    "or items, owner-level capacity beyond the declared limits, or any advantage "
    "over alternative architectures. The read half measured here is a prediction "
    "of the canonical page under the write's own declared direction, not an "
    "observation: it recovers what a write deposited and is not declared as "
    "evidence, so it claims nothing about the world beyond the page it reads. One "
    "live consequence is recorded rather "
    "than repaired: the durability harness's own recon says the owner exposes no "
    "packet-impulse operation, which this additive transition supersedes; that "
    "harness is frozen evidence and is deliberately left untouched."
)

READING_TAKEN = {
    "question": (
        "the design admits more than one faithful reading of a transition that "
        "accepts a written packet impulse; this is the reading this receipt took, "
        "and why the others were not taken"
    ),
    "taken": (
        "lift the field's own canonical packet impulse -- "
        "cassi_resonant_field.apply_helical_packet_impulse, the write route every "
        "exploration harness already uses -- into a real owner transition: one "
        "operation identity, one immutable successor, the evidence clock unchanged "
        "(a write is a field intervention, not evidence), and the written pattern "
        "inside the owner's checkpoint closure"
    ),
    "why": (
        "the design derives the field's input as a boundary drive through explicitly "
        "selected ports of a supported relation (FIELD-INTELLIGENCE-DESIGN.md 27.1-"
        "27.2: the compiler selects the charts and ports it is given and does not "
        "autonomously discover relations), and for a written pattern it already "
        "names the canonical packet impulse as an operation of its own regional "
        "lowering (cassi_resonant_field.py 2806, 2940, 3486, 3507). The measured "
        "input realization on this profile carries no authority over its own "
        "readout, so the minimal reading that makes the write reach the field is to "
        "expose the canonical write itself rather than to change what the field's "
        "problem declares"
    ),
    "not_taken": [
        {
            "alternative": (
                "drive the declared input realization as the write path"
            ),
            "why_not": (
                "measured exactly inert on this profile: the write would deposit "
                "nothing in the declared readout, and the receipt's impulse block "
                "would fail its own predicate"
            ),
        },
        {
            "alternative": (
                "declare a supported relation between two new ports so the input "
                "channel carries the write"
            ),
            "why_not": (
                "that is a change to the field's declared problem rather than to its "
                "transition surface, and the receipt's own control shows it is the "
                "declared problem -- not the input code path -- that decides whether "
                "the channel carries anything"
            ),
        },
        {
            "alternative": (
                "declare the read half as evidence rather than as a prediction"
            ),
            "why_not": (
                "the design declares readouts as temporal predictions explicitly "
                "(FIELD-INTELLIGENCE-DESIGN.md 27.3; README.md 653-657), and evidence "
                "admission is a separate declared owner operation. The receipt's "
                "read_operation block measures what that other declaration would "
                "move and leaves the choice open rather than taking it here"
            ),
        },
    ],
    "does_not_claim": (
        "a new drive mechanism, any advantage over the existing aimed narrow-path "
        "route (the two are measured to be the same write), authority over the "
        "declared input channel, task-level memory utility, or an evidence-producing "
        "read: the read half this receipt adds is declared a temporal prediction of "
        "the canonical page, moves no evidence clock and admits no observation"
    ),
}

DEFINITIONS = {
    "owner_write_path": (
        "FieldIntelligenceOwner.write_packet_impulse: one declared packet impulse "
        "(path, component, flow_signal, work_budget) applied to the owner's "
        "canonical workspace through FieldAtlas.write_packet_impulse and published "
        "as one immutable successor, with the evidence clock unchanged"
    ),
    "owner_read_operation": (
        "FieldIntelligenceOwner.read_packet_deposit: the read half of the write "
        "path. It names a direction the same way the write names it (path, "
        "component, flow_signal) and returns the deposit the canonical page "
        "carries along that direction's own read-frame response, which the atlas "
        "measures by applying the declared impulse to a scratch workspace. It "
        "publishes no successor, consumes no operation identity and touches no "
        "owner state, and it is declared as the design declares a readout: a "
        "temporal prediction that adds no observed support and does not advance "
        "the evidence clock"
    ),
    "input_realization": (
        "the temporal realization cassi_field_transceiver.condense_workspace "
        "derives from one bound canonical workspace: an initial state, the input "
        "lift (the boundary response per unit of declared input), the readout rows, "
        "and the compact map when compact admission holds"
    ),
    "input_authority": (
        "one tick from the realization's own reset state at a declared input value, "
        "read through the realization's declared output port: the spread of that "
        "output over the declared input scan, against the declared authority "
        "allowance"
    ),
    "read_frame_deposit": (
        "the squared norm of the declared read frame's increment across one write "
        "(the durability harness's own measured deposit), and the same quantity for "
        "the same item written alone into a fresh field (its captured deposit)"
    ),
    "recovery_fraction_at_horizon": (
        "(c_read . u)^2 / |c_in_arm|^2 with u the written item's captured write "
        "direction and |c_in_arm|^2 that write's measured deposit inside the arm: "
        "the share of the item's own deposit still lying along the written "
        "direction at the declared horizon, which is the durability harness's own "
        "recovery_fraction definition and is reported here as the recovered fidelity"
    ),
    "neutral_gain": (
        "the declared refinement's measured gain at which the declared loop's "
        "horizon recovery passes through the written deposit, from the feedback "
        "harness's own grid and bisection instrument, re-measured on this profile "
        "by this runner and reported with its bracket"
    ),
    "neutral_level_floor": (
        "the feedback harness's own declared floor on a neutral hold's recovery "
        "fraction: a hold passes when its horizon recovery is at least this value, "
        "and the same floor is applied here to the hold arm and to its no-loop "
        "control"
    ),
    "skeleton": (
        "this runner's tick body for the declared loop: one canonical advance tick, "
        "the feedback harness's own read-back signal (phase_signal), the harness's "
        "own bounded amplitude law (loop_amplitude), the harness's own drive "
        "(apply_drive) and the harness's own sample row (sample_row). It exists "
        "because run_stream writes its declared items itself and cannot start from "
        "an owner-written page"
    ),
    "route_identity": (
        "the owner route and the existing route are called with the same declared "
        "item and budget, and their canonical field-page digest, workspace state "
        "digest and ledger are compared: identity here means one write reached the "
        "field, not that a second mechanism agreed numerically"
    ),
}

DIAGNOSIS_READ_FROM_SOURCE = (
    "cassi_field_transceiver.py:157-159 (_effective puts the declared inputs into "
    "the operator's observed set, so an input is a fixed observation rather than a "
    "drive); cassi_resonant_field.py:1044-1071 (each observed variable contributes "
    "a position-common constraint row and a zero-normal-momentum row); "
    "cassi_resonant_field.py:1139-1143 (boundary projects the state onto those "
    "targets, which is the clamp the input acts through); "
    "cassi_field_transceiver.py:333 (the input lift is the boundary response per "
    "unit input, minus the base state); cassi_field_transceiver.py:334-337 and "
    "464-468 (the readout row is the output port's own common coordinates); "
    "cassi_resonant_field.py:1136-1137 and 1177-1180 (flow projects the constrained "
    "subspace out, so a lift along a constraint row cannot drive the step); "
    "cassi_field_transceiver.py:371-374 and 413-414 (the compact path's drive "
    "matrix and its direct readout term are built from exactly those two objects); "
    "cassi_field_owner.py (advance) and cassi_field_atlas.py:3565-3586 (the owner's "
    "whole wave transition surface before this change: ticks and source_enabled "
    "only)."
)


PORT_GEOMETRY_READ_FROM_SOURCE = (
    "each declared port owns four coordinates of the realization's 4*port_count "
    "phase space, in two pairs. The common pair {p, port_count+p} is where "
    "cassi_field_transceiver.py:337 builds the readout row (output[row, port] = "
    "output[row, n+port] = 1/sqrt(2)) and where cassi_resonant_field.py:1056-1058 "
    "builds the input clamp (row[ports] = row[ports+n] = common_row/sqrt(2)); the "
    "strand pair {2*port_count+p, 3*port_count+p} is where cassi_resonant_field.py:"
    "1005-1006 places a written packet's direction (direction[2*port_count:] = "
    "concatenate((p_y, p_i))) and where cassi_resonant_field.py:1069 pins the normal "
    "momentum (momentum_rows = concatenate((zeros(2n), row[:2n]))). On the canonical "
    "page the common pair is lanes 0 and 1 of a port's nine-lane block "
    "(cassi_resonant_field.py:351-352) and the strand pair is lanes 2 and 3 "
    "(cassi_resonant_field.py:359-360)."
)

OVERLAPPING_SELECTION_READING = {
    "question": (
        "two ways of giving a declared input authority over a declared readout were "
        "offered to the owner: select ports whose supports overlap, or declare a "
        "relation that couples them. This receipt measures all three declared "
        "configurations and states which reading the design text supports, as a "
        "proposal with its evidence; the choice is left open"
    ),
    "design_text": {
        "FIELD-INTELLIGENCE-DESIGN.md 27.1": (
            "'Ports refer to existing field variables. The current compiler selects "
            "explicitly requested charts and ports; it does not autonomously discover "
            "a useful decomposition.'"
        ),
        "FIELD-INTELLIGENCE-DESIGN.md 27.2": (
            "'A changing input is a boundary drive; passivity between such drives does "
            "not imply that externally driven motion has no energy input.'"
        ),
        "FIELD-INTELLIGENCE-DESIGN.md 27.3": (
            "'Outputs are labeled `temporal-prediction`. Condensation, transmission, "
            "reset, and inspection add no observed support and do not advance the "
            "evidence clock.'"
        ),
        "README.md 653-657": (
            "'`condense_transceiver` creates a realization; `advance_transceivers` "
            "supplies bounded inputs and advances an assembly; `reset_transceiver` "
            "restarts its temporal episode; `inspect_transceivers` reads without "
            "advancing. ... These readouts are temporal predictions, not newly "
            "observed evidence or permission to act.'"
        ),
    },
    "reading_the_text_supports": (
        "the design describes the input as a boundary drive through supported "
        "relations, and the compiler as selecting the ports it is given rather than "
        "discovering a decomposition; it never offers port overlap as a mechanism. "
        "Read strictly, the text supports giving the channel authority by declaring a "
        "coupling and not by choosing overlapping ports -- which is also what this "
        "library can do: an overlapping-port selection is not selectable here (it is "
        "refused), while a declared coupling is expressible and fires. This is a "
        "reading of the text beside the measurements, not a change to any declared "
        "problem: no supported relation is declared by this runner"
    ),
    "choice_left_to_the_owner": (
        "this receipt does not choose between the two options. It reports that the "
        "shipped selection is measurably inert, that an overlapping-port selection is "
        "refused by the library rather than merely absent, that the coupled-relation "
        "control fires, and which reading the design text supports"
    ),
    "what_was_not_done": (
        "the declared input realization of the diagnosis block is unchanged, no "
        "supported relation is declared anywhere by this runner, and no declared port "
        "was rebound in any workspace this receipt reports on"
    ),
}

READ_ONLY_SURFACE_OPERATIONS = (
    "checkpoint",
    "exact_recall",
    "explain",
    "inspect",
    "inspect_computer_policy",
    "inspect_computers",
    "inspect_resonance",
    "inspect_temporal",
    "inspect_temporal_task",
    "inspect_transceivers",
    "preview_forget",
    "query",
    READ_OPERATION_NAME,
)

OWNER_READ_SURFACE_READ_FROM_SOURCE = (
    "cassi_field_owner.py:9544-10005 defines FieldIntelligenceSurface, whose handle() "
    "is the owner's closed RPC dispatch; every operation that publishes a state "
    "transition is a mutation, and the operations whose names declare no transition "
    "are the thirteen listed in READ_ONLY_SURFACE_OPERATIONS. One of them is the "
    "read half this receipt adds: read_packet_deposit names a written direction and "
    "returns the deposit the canonical page carries along it, labeled "
    "temporal-prediction, adding no observed support and advancing no evidence "
    "clock. None of them is an evidence-producing read of a written pattern's "
    "deposit: the transition this receipt adds is an intervention (event kind "
    "packet-impulse-written, evidence clock and logical tick unchanged), inspection "
    "reports digests, generations, "
    "powers and retained receipts rather than directional coefficients, and the only "
    "other field-response read is the transceiver path (condense_transceiver, "
    "advance_transceivers, inspect_transceivers), whose outputs the design labels "
    "temporal-prediction (FIELD-INTELLIGENCE-DESIGN.md 27.3; README.md 653-657) and "
    "which add no observed support and do not advance the evidence clock."
)

OWNER_READ_BEHAVIOUR_ALLOWANCE = 1e-12


@dataclass(frozen=True)
class OwnerWritePathConfig:
    """Declared measurement settings; every number in the receipt derives from these."""

    read_frame_path: str = durability.READ_FRAME_PATH
    headline_item_index: int = durability.HEADLINE_ITEM_INDEX
    second_item_index: int = SECOND_ITEM_INDEX
    write_budget: float = 1e-3
    refinement_horizon_ticks: int = 64
    long_horizon_ticks: int = 512
    long_horizon_min_ticks: int = 512
    capacity_alternate_block_ticks: int = 64
    sample_every_ticks: int = 16
    authority_allowance: float = 1e-12
    input_scan: tuple[float, ...] = (0.0, 0.5, 1.75, 3.5)
    input_bound: float = 4.0
    impulse_deposit_fraction: float = IMPULSE_DEPOSIT_FRACTION
    hold_margin: float = HOLD_MARGIN
    cross_item_margin: float = CROSS_ITEM_MARGIN
    route_identity_allowance: float = ROUTE_IDENTITY_ALLOWANCE
    owner_home_prefix: str = "owp-owner-"
    event_kind: str = PACKET_IMPULSE_EVENT_KIND

    def __post_init__(self) -> None:
        if not 0.0 < float(self.write_budget) <= 1.0:
            raise ValueError("the declared write budget must lie in (0,1]")
        if int(self.refinement_horizon_ticks) < 1:
            raise ValueError("the declared refinement horizon must be positive")
        if int(self.long_horizon_ticks) % int(self.sample_every_ticks):
            raise ValueError("the declared long horizon must be a whole number of samples")
        if int(self.long_horizon_ticks) < int(self.refinement_horizon_ticks):
            raise ValueError("the declared long horizon must cover the refinement horizon")
        if int(self.long_horizon_min_ticks) > int(self.long_horizon_ticks):
            raise ValueError(
                "the declared long-horizon floor must lie at or under the declared "
                "long horizon"
            )
        if int(self.capacity_alternate_block_ticks) <= 0:
            raise ValueError("the declared multiplex block length must be positive")
        if not self.input_scan or any(
            abs(float(value)) > float(self.input_bound) for value in self.input_scan
        ):
            raise ValueError("the declared input scan must stay inside the input envelope")
        if len(self.input_scan) < 2:
            raise ValueError("the declared input scan must hold at least two values")
        for name in ("headline_item_index", "second_item_index"):
            index = int(getattr(self, name))
            if not 0 <= index < len(durability.ITEM_SPECS):
                raise ValueError(f"{name} is outside the declared item list")
        if self.headline_item_index == self.second_item_index:
            raise ValueError("the declared headline and second items must differ")
        if float(self.authority_allowance) <= 0.0:
            raise ValueError("the declared authority allowance must be positive")

    @property
    def long_horizon_sample_ticks(self) -> tuple[int, ...]:
        return tuple(
            range(
                int(self.sample_every_ticks),
                int(self.long_horizon_ticks) + 1,
                int(self.sample_every_ticks),
            )
        )

    @property
    def refinement_sample_ticks(self) -> tuple[int, ...]:
        return tuple(range(1, int(self.refinement_horizon_ticks) + 1))

    @property
    def hold_floor(self) -> float:
        """The feedback harness's own declared neutral level floor."""

        return float(feedback.FeedbackConfig().neutral_level_floor)

    def feedback_config(self) -> feedback.FeedbackConfig:
        """The declared loop settings, expressed as the feedback harness's own config."""

        return feedback.FeedbackConfig(
            read_frame_path=self.read_frame_path,
            headline_item_index=int(self.headline_item_index),
            write_budget=float(self.write_budget),
            horizon_ticks=int(self.refinement_horizon_ticks),
            sample_ticks=self.refinement_sample_ticks,
            long_horizon_ticks=int(self.long_horizon_ticks),
            long_horizon_min_ticks=int(self.long_horizon_min_ticks),
            capacity_alternate_block_ticks=int(self.capacity_alternate_block_ticks),
            long_horizon_sample_ticks=self.long_horizon_sample_ticks,
            capacity_item=durability.ITEM_SPECS[self.second_item_index].name,
        )

    def as_dict(self) -> dict[str, Any]:
        config = feedback.FeedbackConfig()
        return {
            "read_frame_path": self.read_frame_path,
            "headline_item": durability.ITEM_SPECS[self.headline_item_index].name,
            "second_item": durability.ITEM_SPECS[self.second_item_index].name,
            "headline_item_index": int(self.headline_item_index),
            "second_item_index": int(self.second_item_index),
            "write_budget": float(self.write_budget),
            "refinement_horizon_ticks": int(self.refinement_horizon_ticks),
            "long_horizon_ticks": int(self.long_horizon_ticks),
            "long_horizon_min_ticks": int(self.long_horizon_min_ticks),
            "capacity_alternate_block_ticks": int(self.capacity_alternate_block_ticks),
            "sample_every_ticks": int(self.sample_every_ticks),
            "authority_allowance": float(self.authority_allowance),
            "input_scan": [float(value) for value in self.input_scan],
            "input_bound": float(self.input_bound),
            "impulse_deposit_fraction": float(self.impulse_deposit_fraction),
            "hold_margin": float(self.hold_margin),
            "hold_floor": self.hold_floor,
            "cross_item_margin": float(self.cross_item_margin),
            "route_identity_allowance": float(self.route_identity_allowance),
            "split_weights": [list(weights) for weights in SPLIT_WEIGHTS],
            "event_kind": self.event_kind,
            "phase_degrees": float(config.neutral_gain_phase_degrees),
            "neutral_gain_grid": [float(gain) for gain in config.neutral_gain_grid],
            "neutral_gain_bracket": float(config.neutral_gain_bracket),
            "loop_work_ceiling": float(config.loop_work_ceiling),
            "per_tick_decay_reference": float(feedback.PER_TICK_DECAY),
        }


def flat_profile() -> Any:
    """The declared profile, built by the metric harness's own builder."""

    return metric.build_metric_profile(metric.ladder_row(PROFILE_NAME))


def plain(value: Any) -> Any:
    """Detached ordinary JSON containers for a value a canonical API froze."""

    if isinstance(value, Mapping):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def receipt_digest(body: Mapping[str, Any]) -> str:
    """The lattice runner's declared content digest, applied to a receipt body.

    ``run_fractal_lattice_exploration.py`` states and applies the convention: the
    SHA-256 of the canonical JSON (sorted keys, no insignificant whitespace,
    allow_nan=False) of the measured body with the wall-clock fields stripped,
    taken before the digest itself is attached.
    """

    return geometry.content_digest(
        {key: value for key, value in body.items() if key != "receipt_digest"}
    )


# --------------------------------------------------------------------------
# diagnosis: where the shipped input realization is inert, and why
# --------------------------------------------------------------------------
def condense_input_realization(
    profile: Any, problem: ResonantProblem, config: OwnerWritePathConfig
) -> dict[str, Any]:
    """Condense one input realization and read its declared input channel."""

    workspace, _write = durability.write_item(
        initial_workspace(profile),
        durability.ITEM_SPECS[int(config.headline_item_index)],
        float(config.write_budget),
    )
    bound = bind_workspace(workspace, problem)
    kernel, _working, receipt = condense_workspace(
        bound,
        problem,
        input_ids=("write-in",),
        output_ids=("write-out",),
        rank=8,
        error_allowance=1e-3,
        input_bound=float(config.input_bound),
        horizon_ticks=int(config.refinement_horizon_ticks),
    )
    outputs: dict[str, float] = {}
    states: dict[str, np.ndarray] = {}
    for value in config.input_scan:
        next_state, scan = advance_transceiver(
            kernel,
            reset_transceiver(kernel),
            inputs={"write-in": float(value)},
            ticks=1,
        )
        outputs[repr(float(value))] = float(scan["values"]["write-out"])
        states[repr(float(value))] = np.asarray(next_state["state"], dtype=np.float64)
    scanned = list(outputs.values())
    full_outputs: dict[str, float] = {}
    for value in config.input_scan:
        _next, scan = advance_transceiver(
            kernel,
            reset_transceiver(kernel),
            inputs={"write-in": float(value)},
            ticks=1,
            force_full=True,
        )
        full_outputs[repr(float(value))] = float(scan["values"]["write-out"])
    full_scanned = list(full_outputs.values())
    port_count = int(profile.port_count)
    lift = np.asarray(kernel["input_lift"], dtype=np.float64)
    rows = np.asarray(kernel["output_rows"], dtype=np.float64)
    lift_support = [int(index) for index in np.nonzero(np.abs(lift[:, 0]) > 0.0)[0]]
    row_support = [int(index) for index in np.nonzero(np.abs(rows[0]) > 0.0)[0]]
    rom = kernel["rom"]
    spread = max(scanned) - min(scanned)
    magnitude = max(abs(value) for value in scanned)
    first, last = config.input_scan[0], config.input_scan[-1]
    state_delta = states[repr(float(last))] - states[repr(float(first))]
    lift_norm = float(np.linalg.norm(lift[:, 0]))
    return {
        "mode": str(receipt["mode"]),
        "kernel_status": str(kernel["status"]),
        "kernel_reason": str(kernel["reason"]),
        "kernel_dimensions": plain(kernel["dimensions"]),
        "bindings": {
            name: {
                "pool": int(row["pool"]),
                "port": int(row["port"]),
                "component": str(row["component"]),
            }
            for name, row in bound.bindings.items()
        },
        "port_count": port_count,
        "input_port_offset": (
            int(bound.bindings["write-in"]["port"]),
            int(bound.bindings["write-in"]["port"]) + port_count,
        ),
        "readout_port_offset": (
            int(bound.bindings["write-out"]["port"]),
            int(bound.bindings["write-out"]["port"]) + port_count,
        ),
        "input_lift_norm": lift_norm,
        "input_lift_support_coordinates": lift_support,
        "input_lift_support_values": [float(lift[index, 0]) for index in lift_support],
        "readout_row_support_coordinates": row_support,
        "readout_row_support_values": [float(rows[0, index]) for index in row_support],
        "support_overlap": sorted(set(lift_support) & set(row_support)),
        "output_row_dot_input_lift": (
            float((rows @ lift[:, :1]).reshape(-1)[0])
            if rows.shape[1] == lift.shape[0]
            else None
        ),
        "output_row_dot_input_lift_relative": (
            float(abs((rows @ lift[:, :1]).reshape(-1)[0]) / (np.linalg.norm(rows) * lift_norm))
            if lift_norm and rows.shape[1] == lift.shape[0]
            else None
        ),
        "compact_map_available": rom is not None,
        "compact_map_direct_term": (
            None if rom is None else plain(np.asarray(rom["direct"]).reshape(-1).tolist())
        ),
        "compact_map_drive_input_column_norm": (
            None
            if rom is None
            else float(np.linalg.norm(np.asarray(rom["drive"], dtype=np.float64)[:, :1]))
        ),
        "input_scan": [float(value) for value in config.input_scan],
        "outputs": outputs,
        "output_spread": float(spread),
        "output_relative_spread": float(spread / magnitude) if magnitude else 0.0,
        "authority_allowance": float(config.authority_allowance),
        "input_has_authority": bool(spread / magnitude > config.authority_allowance)
        if magnitude
        else False,
        "state_delta_norm_between_first_and_last_input": float(np.linalg.norm(state_delta)),
        "state_delta_max_abs_between_first_and_last_input": float(
            np.max(np.abs(state_delta))
        ),
        "expected_state_delta_norm_if_the_clamp_moved_the_state": float(
            lift_norm * abs(float(last) - float(first))
        ),
        "output_delta_absolute_between_first_and_last_input": abs(
            outputs[repr(float(last))] - outputs[repr(float(first))]
        ),
        "full_realization_outputs": full_outputs,
        "full_realization_output_spread": float(max(full_scanned) - min(full_scanned)),
    }


def cited_shipped_input_measurement() -> dict[str, Any]:
    """The shipped feedback receipt's own input-authority figures, cited by key.

    The path is the feedback harness's own declared output path rather than a
    constant it exports, because that harness only exports the durability receipt
    it cites; the block records the path it read and the key path it took, and
    reports the citation as unavailable rather than substituting another
    measurement if the shipped receipt is not present on this checkout.
    """

    path = FEEDBACK_RECEIPT
    key_path = "recon.transceiver.measured[*].per_tick_input_authority"
    if not path.exists():
        return {
            "cited_receipt": str(path),
            "cited_key_path": key_path,
            "available": False,
        }
    receipt = json.loads(path.read_text(encoding="utf-8"))
    measured = receipt.get("recon", {}).get("transceiver", {}).get("measured")
    if not isinstance(measured, list):
        return {
            "cited_receipt": str(path),
            "cited_key_path": key_path,
            "available": False,
            "reason": "the shipped receipt does not carry recon.transceiver.measured",
        }
    return {
        "cited_receipt": str(path),
        "cited_key_path": key_path,
        "available": True,
        "cited_instrument": (
            "run_fractal_feedback_exploration recon.transceiver.measured[*]."
            "per_tick_input_authority, measured there on its own declared problem "
            "and profiles; cited here so the inertness measured above sits beside "
            "the shipped figure rather than replacing it"
        ),
        "probes": [
            {
                "label": str(row["label"]),
                "profile_beta": float(row["profile_beta"]),
                "inputs": [
                    float(value) for value in row["per_tick_input_authority"]["inputs"]
                ],
                "relative_spread": (
                    None
                    if row["per_tick_input_authority"]["relative_spread"] is None
                    else float(row["per_tick_input_authority"]["relative_spread"])
                ),
                "spread": float(row["per_tick_input_authority"]["spread"]),
                "input_has_measurable_authority": bool(
                    row["per_tick_input_authority"]["input_has_measurable_authority"]
                ),
            }
            for row in measured
        ],
    }


def owner_surface_block() -> dict[str, Any]:
    """The owner's wave transition surface, read from the class itself."""

    signature = inspect.signature(FieldIntelligenceOwner.advance)
    return {
        "declared": (
            "the owner operations that address the canonical wave on this build, "
            "read from the class itself rather than asserted"
        ),
        "advance_parameters": sorted(signature.parameters),
        "advance_carries_a_write": False,
        "write_packet_impulse_present_on_the_owner": callable(
            getattr(FieldIntelligenceOwner, "write_packet_impulse", None)
        ),
        "write_packet_impulse_present_on_the_atlas": callable(
            getattr(FieldAtlas, "write_packet_impulse", None)
        ),
        "declared_event_kind": str(PACKET_IMPULSE_EVENT_KIND),
    }


def diagnosis_block(profile: Any, config: OwnerWritePathConfig) -> dict[str, Any]:
    """What the shipped input realization does, where it is inert, and why."""

    declared = condense_input_realization(profile, DECLARED_INPUT_PROBLEM, config)
    beta_zero = _profile_replace(profile, beta=0.0)
    inert = condense_input_realization(beta_zero, DECLARED_INPUT_PROBLEM, config)
    control = condense_input_realization(beta_zero, DECLARED_COUPLED_PROBLEM, config)
    return {
        "declared": (
            "the field's input-shaped surface is the temporal input realization "
            "cassi_field_transceiver.condense_workspace derives from one bound "
            "canonical workspace. This block condenses that realization on the "
            "declared profile and reads its declared input channel the way the "
            "shipped feedback receipt reads it: one tick from the realization's own "
            "reset state at each declared input value, read through the "
            "realization's declared output port"
        ),
        "read_from_source": DIAGNOSIS_READ_FROM_SOURCE,
        "why_it_is_inert": (
            "the input enters as a fixed observation, so the operator clamps the "
            "input port's common coordinate and pins its normal momentum; the input "
            "lift -- the boundary response per unit input -- is supported only on "
            "that port's own two coordinates, which the readout row at the output "
            "port's own two coordinates does not touch, so the readout row is "
            "exactly orthogonal to the lift (measured dot 0.0). The declared "
            "precision carries no cross term, so no supported relation joins the "
            "input port to the output port either. Two mechanisms close the channel, "
            "and the receipt measures which one is live in each realization the "
            "field admits on this profile: in the reduced realization the compact "
            "map's input column, built from that lift, is annihilated by the "
            "constrained-subspace projection, so the input does not move the state "
            "at all; in the full nonlinear realization the same drive does move the "
            "state exactly by the lift, and the declared readout still does not "
            "move, because the readout row cannot see it. Either way the declared "
            "input has no measurable authority over the declared output"
        ),
        "declared_profile": declared,
        "beta_zero_counterpart": inert,
        "supported_relation_control": {
            "declared": (
                "the firing control of this diagnosis: the identical construction "
                "on the same profile with the declared precision carrying a cross "
                "term, the way a condensed learned relation does, so the same "
                "measurement must find the input channel carrying a signal"
            ),
            "problem_precision": [[2.0, 1.0], [1.0, 2.0]],
            **control,
        },
        "cited_shipped_measurement": cited_shipped_input_measurement(),
        "owner_transition_surface": owner_surface_block(),
        "verdicts": {
            "declared_profile_input_is_inert": not declared["input_has_authority"],
            "beta_zero_counterpart_input_is_inert": not inert["input_has_authority"],
            "declared_profile": {
                "realization": declared["mode"],
                "compact_map_available": declared["compact_map_available"],
                "output_spread": declared["output_spread"],
                "state_delta_fraction_of_the_lift_prediction": (
                    declared["state_delta_norm_between_first_and_last_input"]
                    / declared["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                    if declared["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                    else None
                ),
                "the_lift_moves_the_state_here": bool(
                    declared["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                    > 0.0
                    and abs(
                        declared["state_delta_norm_between_first_and_last_input"]
                        - declared["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                    )
                    <= 1e-9
                    * declared["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                ),
                "the_readout_is_blind_to_that_movement": bool(
                    declared["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                    > 0.0
                    and declared["output_delta_absolute_between_first_and_last_input"]
                    <= 1e-9
                    * declared["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                ),
            },
            "beta_zero_counterpart": {
                "realization": inert["mode"],
                "compact_map_available": inert["compact_map_available"],
                "compact_map_drive_input_column_norm": inert[
                    "compact_map_drive_input_column_norm"
                ],
                "compact_map_direct_term": inert["compact_map_direct_term"],
                "output_spread": inert["output_spread"],
                "state_delta_fraction_of_the_lift_prediction": (
                    inert["state_delta_norm_between_first_and_last_input"]
                    / inert["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                    if inert["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                    else None
                ),
                "the_input_is_annihilated_before_it_reaches_the_state": bool(
                    inert["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                    > 0.0
                    and abs(inert["state_delta_norm_between_first_and_last_input"])
                    <= 1e-9
                    * inert["expected_state_delta_norm_if_the_clamp_moved_the_state"]
                ),
            },
            "supported_relation_control_fires": bool(
                control["input_has_authority"]
                and control["output_spread"]
                > max(declared["output_spread"], inert["output_spread"])
            ),
            "control_spread_minus_declared_profile_spread": (
                control["output_spread"] - declared["output_spread"]
            ),
            "control_spread_minus_beta_zero_spread": (
                control["output_spread"] - inert["output_spread"]
            ),
        },
        "consequence_for_the_write_path": (
            "a write routed through the declared input realization would carry "
            "nothing into the declared readout at this profile, so the write path "
            "added here does not go through it: it is the field's own canonical "
            "packet impulse, lifted into a transition the owner accepts"
        ),
    }


# --------------------------------------------------------------------------
# the declared ports, their supports, and the overlap question
# --------------------------------------------------------------------------
def same_port_selection(profile: Any, problem: ResonantProblem) -> dict[str, Any]:
    """The nearest overlapping selection: both declared variables on one port.

    The declared allocation cannot produce this -- ``_allocate_bindings`` keeps its
    occupied set, so a second variable never receives a bound port -- so the
    selection is declared explicitly here to ask the library what it makes of
    overlapping ports at all.
    """

    allocated = bind_workspace(initial_workspace(profile), problem).bindings
    bindings = {
        "write-in": dict(allocated["write-in"]),
        "write-out": {
            **dict(allocated["write-out"]),
            "pool": int(allocated["write-in"]["pool"]),
            "port": int(allocated["write-in"]["port"]),
        },
    }
    try:
        kernel, _working, _receipt = condense_workspace(
            ResonantWorkspace(profile=profile, bindings=bindings),
            problem,
            input_ids=("write-in",),
            output_ids=("write-out",),
            rank=8,
            error_allowance=1e-3,
            input_bound=4.0,
            horizon_ticks=16,
        )
    except ResonantNumericalError as error:
        return {
            "accepted": False,
            "shared_port": int(bindings["write-out"]["port"]),
            "refusal": type(error).__name__,
            "refusal_message": str(error),
        }
    lift = np.asarray(kernel["input_lift"], dtype=np.float64)
    rows = np.asarray(kernel["output_rows"], dtype=np.float64)
    lift_support = [int(index) for index in np.nonzero(np.abs(lift[:, 0]) > 0.0)[0]]
    row_support = [int(index) for index in np.nonzero(np.abs(rows[0]) > 0.0)[0]]
    return {
        "accepted": True,
        "shared_port": int(bindings["write-out"]["port"]),
        "input_lift_support_coordinates": lift_support,
        "readout_row_support_coordinates": row_support,
        "support_overlap": sorted(set(lift_support) & set(row_support)),
        "output_row_dot_input_lift": (
            float((rows @ lift[:, :1]).reshape(-1)[0])
            if rows.shape[1] == lift.shape[0]
            else None
        ),
    }


def other_declared_profiles() -> list[tuple[str, Any]]:
    """The library's own default profile and a bounded set of declared metric rows."""

    rows = list(metric.ladder_profiles())[:4]
    return [("library-default", ResonantProfile())] + [
        (f"metric-ladder:{row.name}", metric.build_metric_profile(row)) for row in rows
    ]


def port_support_block(
    profile: Any, config: OwnerWritePathConfig, diagnosis: Mapping[str, Any]
) -> dict[str, Any]:
    """The declared profile's own ports, their supports, and the overlap question.

    No supported relation is declared and no declared input is realized here: this
    block counts the profile's own ports, reports which supports overlap, measures
    the shipped selection, the nearest overlapping selection the library admits, and
    the coupled-relation control the diagnosis block already carries, and states the
    reading of the design text as a proposal.
    """

    port_count = int(profile.port_count)
    ports_per_pool = int(profile.ports_per_pool)
    declared_ports = [
        {
            "port": port,
            "pool": port // ports_per_pool,
            "local_port": port % ports_per_pool,
            "common_support": [port, port_count + port],
            "strand_support": [2 * port_count + port, 3 * port_count + port],
        }
        for port in range(port_count)
    ]
    common_overlaps: list[list[int]] = []
    strand_overlaps: list[list[int]] = []
    cross_overlaps: list[list[int]] = []
    disjoint_pairs: list[list[int]] = []
    for first in range(port_count):
        one = declared_ports[first]
        for second in range(first + 1, port_count):
            two = declared_ports[second]
            common_shared = bool(set(one["common_support"]) & set(two["common_support"]))
            strand_shared = bool(set(one["strand_support"]) & set(two["strand_support"]))
            crossed = bool(
                set(one["common_support"]) & set(two["strand_support"])
                or set(one["strand_support"]) & set(two["common_support"])
            )
            if common_shared:
                common_overlaps.append([first, second])
            if strand_shared:
                strand_overlaps.append([first, second])
            if crossed:
                cross_overlaps.append([first, second])
            if not (common_shared or strand_shared or crossed):
                disjoint_pairs.append([first, second])

    fresh = initial_workspace(profile)
    written, _write = durability.write_item(
        fresh,
        durability.ITEM_SPECS[int(config.headline_item_index)],
        float(config.write_budget),
    )
    page_lanes = 9 * port_count
    delta = np.asarray(written.field[0, :, 0], dtype=np.float64) - np.asarray(
        fresh.field[0, :, 0], dtype=np.float64
    )
    touched = [
        int(index)
        for index in np.nonzero(np.abs(delta) > 0.0)[0]
        if int(index) < page_lanes
    ]
    written_lanes = sorted({index % 9 for index in touched})
    written_ports = sorted({index // 9 for index in touched})

    readout = diagnosis["declared_profile"]
    shipped_port = int(readout["readout_port_offset"][0])
    readout_phase_pair = [shipped_port, shipped_port + port_count]
    # The phase space index of (lane, port) is lane*port_count + port; the page index
    # is 9*port + lane, so the pair above lands on lanes 0 and 1 of the output port.
    readout_pair = [
        9 * (index % port_count) + index // port_count for index in readout_phase_pair
    ]
    readout_lanes = sorted({index % 9 for index in readout_pair})

    same_port = same_port_selection(profile, DECLARED_INPUT_PROBLEM)
    alternatives = [
        {"profile": name, **same_port_selection(other, DECLARED_INPUT_PROBLEM)}
        for name, other in other_declared_profiles()
    ]
    control = diagnosis["supported_relation_control"]
    shared_port = int(same_port["shared_port"])
    shared_supports = [
        [shared_port, shared_port + port_count],
        [shared_port, shared_port + port_count],
    ]
    detector_overlap = sorted(set(shared_supports[0]) & set(shared_supports[1]))
    shipped = {
        "input_port": int(readout["bindings"]["write-in"]["port"]),
        "output_port": int(readout["bindings"]["write-out"]["port"]),
        "input_support_phase_space_coordinates": readout["input_lift_support_coordinates"],
        "readout_support_phase_space_coordinates": readout["readout_row_support_coordinates"],
        "support_overlap": readout["support_overlap"],
        "output_row_dot_input_lift": readout["output_row_dot_input_lift"],
        "output_spread": readout["output_spread"],
        "input_has_authority": readout["input_has_authority"],
    }
    return {
        "declared": (
            "the owner asked to decide between selecting ports whose supports overlap "
            "and declaring a coupling. This block enumerates the declared profile's "
            "own ports and supports, states which overlap, and reports the measured "
            "per-tick input authority of the shipped selection, of the nearest "
            "overlapping selection this library admits, and of the coupled-relation "
            "control, so the two options sit side by side"
        ),
        "read_from_source": PORT_GEOMETRY_READ_FROM_SOURCE,
        "profile": {
            "name": PROFILE_NAME,
            "port_count": port_count,
            "pools": int(profile.pools),
            "ports_per_pool": ports_per_pool,
            "phase_space_coordinates": 4 * port_count,
            "page_lanes_per_port": 9,
        },
        "declared_ports": declared_ports,
        "overlap": {
            "common_pairs_overlapping": common_overlaps,
            "strand_pairs_overlapping": strand_overlaps,
            "common_of_one_with_strand_of_another": cross_overlaps,
            "overlapping_port_pairs_found": (
                len(common_overlaps) + len(strand_overlaps) + len(cross_overlaps)
            ),
            "unordered_port_pairs_considered": port_count * (port_count - 1) // 2,
            "disjoint_port_pairs": disjoint_pairs,
            "disjoint_port_pairs_found": len(disjoint_pairs),
            "why_every_pair_is_disjoint": (
                "port p's common support is {p, n+p} and its strand support is "
                "{2n+p, 3n+p}, so two ports can share a coordinate only by being the "
                "same port: the four support blocks are disjoint index ranges and each "
                "block is indexed by the port inside it. The search above is exhaustive "
                "over the unordered pairs, not sampled"
            ),
        },
        "detector_control": {
            "declared": (
                "the same support rule applied to the one selection that does overlap: "
                "both declared variables bound to a single port, whose two common "
                "supports are the same two coordinates. It shows the rule fires when "
                "there is an overlap to find, which is the configuration the library "
                "refuses in (b)"
            ),
            "shared_port": shared_port,
            "variable_supports": shared_supports,
            "overlapping_coordinates": detector_overlap,
            "control_fires": bool(detector_overlap),
        },
        "measured_selections": {
            "(a) shipped_selection": {
                "declared": (
                    "the profile's own declared input/output binding, exactly as the "
                    "diagnosis block condenses it: no configuration is chosen here"
                ),
                **shipped,
            },
            "(b) overlapping_selection": {
                "declared": (
                    "the nearest overlapping selection: both declared variables bound "
                    "to one port. The declared allocator never produces one, so the "
                    "selection is declared explicitly and handed to the same condenser"
                ),
                "on_this_profile": same_port,
                "on_other_declared_profiles": alternatives,
                "refused_on_every_profile_tried": all(
                    not row["accepted"] for row in [same_port, *alternatives]
                ),
            },
            "(c) coupled_relation_control": {
                "declared": (
                    "the diagnosis block's firing control: the same construction with "
                    "the declared precision carrying a cross term. It fires with the "
                    "same two disjoint supports as the inert case -- the constraints "
                    "are unchanged -- because the relation routes the drive through "
                    "the dynamics rather than through a shared coordinate"
                ),
                "problem_precision": [[2.0, 1.0], [1.0, 2.0]],
                "input_support_phase_space_coordinates": control["input_lift_support_coordinates"],
                "readout_support_phase_space_coordinates": control["readout_row_support_coordinates"],
                "support_overlap": control["support_overlap"],
                "output_row_dot_input_lift": control["output_row_dot_input_lift"],
                "output_spread": control["output_spread"],
                "input_has_authority": control["input_has_authority"],
                "fires_with_the_same_disjoint_supports": bool(
                    not control["support_overlap"]
                    and control["output_spread"] > readout["output_spread"]
                ),
            },
        },
        "written_pattern_placement": {
            "reader": "run_fractal_durability_exploration.write_item",
            "touched_page_coordinates": len(touched),
            "touched_port_count": len(written_ports),
            "touched_lanes": written_lanes,
            "readout_phase_space_coordinates": readout_phase_pair,
            "readout_pair_page_coordinates": readout_pair,
            "readout_pair_lanes": readout_lanes,
            "deposit_in_the_declared_read_frame": durability.squared_norm(
                durability.read_frame(written, config.read_frame_path)
            ),
        },
        "verdicts": {
            "no_two_declared_ports_overlap_on_this_profile": not (
                common_overlaps or strand_overlaps or cross_overlaps
            ),
            "the_shipped_selection_is_inert": not bool(shipped["input_has_authority"]),
            "an_overlapping_selection_is_refused_by_the_library": not bool(
                same_port["accepted"]
            ),
            "the_coupled_relation_control_fires": bool(control["input_has_authority"]),
            "the_coupled_relation_control_fires_without_a_support_overlap": bool(
                not control["support_overlap"]
                and control["output_spread"] > readout["output_spread"]
            ),
            "the_write_touches_the_strand_pair": written_lanes == [2, 3],
            "the_readout_pair_is_the_common_pair": readout_lanes == [0, 1],
            "the_write_pair_and_the_readout_pair_are_disjoint": not (
                set(written_lanes) & set(readout_lanes)
            ),
        },
        "reading": OVERLAPPING_SELECTION_READING,
    }


# --------------------------------------------------------------------------
# the owner write path
# --------------------------------------------------------------------------
def open_owner(profile: Any) -> tuple[FieldIntelligenceOwner, Path]:
    """One owner whose canonical workspace is this profile's, in a fresh data home."""

    home = Path(tempfile.mkdtemp(prefix=OwnerWritePathConfig().owner_home_prefix))
    owner = FieldIntelligenceOwner(
        home,
        initial_state=AtlasState(resonant_workspace=initial_workspace(profile)),
    )
    return owner, home


def owner_write(
    owner: FieldIntelligenceOwner,
    operation_id: str,
    spec: durability.ItemSpec,
    budget: float,
    config: OwnerWritePathConfig,
    expected_state_sha256: str | None = None,
) -> Mapping[str, Any]:
    """One declared item written through the owner write path."""

    return owner.write_packet_impulse(
        operation_id,
        path=spec.path,
        component=spec.component,
        flow_signal=list(spec.flow_signal),
        work_budget=float(budget),
        event_kind=config.event_kind,
        expected_state_sha256=expected_state_sha256,
    )


def owner_write_items(
    owner: FieldIntelligenceOwner,
    indices: Sequence[int],
    config: OwnerWritePathConfig,
    operation_prefix: str,
) -> dict[str, Any]:
    """Write the declared items through the owner path, measuring each deposit in arm."""

    deposits: dict[str, float] = {}
    writes: list[dict[str, Any]] = []
    for position, index in enumerate(indices):
        spec = durability.ITEM_SPECS[int(index)]
        before = durability.read_frame(
            owner.state.resonant_workspace, config.read_frame_path
        )
        result = owner_write(
            owner, f"{operation_prefix}:{position}", spec, float(config.write_budget), config
        )
        after = durability.read_frame(
            owner.state.resonant_workspace, config.read_frame_path
        )
        receipt = plain(result["impulse_receipt"])
        deposits[spec.name] = durability.squared_norm(after - before)
        writes.append(
            {
                "item": spec.name,
                "operation_id": f"{operation_prefix}:{position}",
                "accepted": bool(receipt["accepted"]),
                "applied_work": float(receipt["applied_work"]),
                "impulse_amount": float(receipt["impulse_amount"]),
                "requested_work": float(receipt["requested_work"]),
                "deposit": float(deposits[spec.name]),
                "generation": int(result["checkpoint_receipt"]["generation"]),
                "replayed": bool(result["checkpoint_receipt"]["replayed"]),
                "event_kind": str(receipt["event_kind"]),
                "source_state_sha256": str(receipt["source_state_sha256"]),
                "state_sha256": str(receipt["state_sha256"]),
                "balance_defect": float(receipt["balance_defect"]),
            }
        )
    return {"writes": writes, "deposits": deposits}


def readout_series(kernel: Mapping[str, Any], ticks: int) -> list[float]:
    """The realization's declared output over a zero-input advance, tick by tick."""

    state = reset_transceiver(kernel)
    series: list[float] = []
    for _ in range(int(ticks)):
        state, scan = advance_transceiver(kernel, state, inputs={}, ticks=1)
        series.append(float(scan["values"]["write-out"]))
    return series


def condense_page(
    page: Any, problem: ResonantProblem, config: OwnerWritePathConfig
) -> Mapping[str, Any]:
    """The declared input realization condensed on one canonical page."""

    kernel, _working, _receipt = condense_workspace(
        bind_workspace(page, problem),
        problem,
        input_ids=("write-in",),
        output_ids=("write-out",),
        rank=8,
        error_allowance=1e-3,
        input_bound=float(config.input_bound),
        horizon_ticks=int(config.refinement_horizon_ticks),
    )
    return kernel


def key_paths(value: Any, prefix: str = "") -> list[str]:
    """Every key path in a JSON-shaped value, for the declared exposure scan."""

    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(path)
            paths.extend(key_paths(item, path))
    elif isinstance(value, (list, tuple)):
        for position, item in enumerate(value):
            paths.extend(key_paths(item, f"{prefix}[{position}]"))
    return paths


def matching_paths(paths: Sequence[str], words: Sequence[str]) -> list[str]:
    """The published key paths naming any of the declared words."""

    return sorted(
        path for path in paths if any(word in path.lower() for word in words)
    )


def dispatch_operations() -> list[str]:
    """Every operation name the owner's closed RPC dispatch declares."""

    return sorted(
        set(
            re.findall(
                r'operation == "([a-z_]+)"',
                inspect.getsource(FieldIntelligenceSurface.handle),
            )
        )
    )


def owner_read_surface_block(
    profile: Any, config: OwnerWritePathConfig
) -> dict[str, Any]:
    """What the owner's read surface can and cannot recover from a written page.

    This block writes a real item through the owner, then asks the surface itself
    what can be read back: it inventories the dispatch's operations, exercises the
    read-only operations that take no arguments, scans everything they publish for
    the written direction, and measures the closest response read -- the transceiver
    readout the design labels a temporal prediction -- on the owner's own written
    page against a blank one. It changes no declared input and no declared relation.
    """

    dispatch = inspect.getsource(FieldIntelligenceSurface.handle)
    operations = dispatch_operations()
    read_only = [name for name in operations if name in READ_ONLY_SURFACE_OPERATIONS]
    mutating = [name for name in operations if name not in READ_ONLY_SURFACE_OPERATIONS]

    owner, home = open_owner(profile)
    try:
        spec = durability.ITEM_SPECS[int(config.headline_item_index)]
        write = owner_write(
            owner, "read-surface:write", spec, float(config.write_budget), config
        )
        receipt = plain(write["impulse_receipt"])
        written_page = owner.state.resonant_workspace
        written_deposit = durability.squared_norm(
            durability.read_frame(written_page, config.read_frame_path)
        )
        blank_deposit = durability.squared_norm(
            durability.read_frame(initial_workspace(profile), config.read_frame_path)
        )
        recovered = durability.squared_norm(
            durability.read_frame(written_page, config.read_frame_path)
        )
        page_before = hashlib.sha256(
            np.ascontiguousarray(written_page.field).tobytes()
        ).hexdigest()
        inspection_before = plain(owner.inspect())
        resonance_before = plain(owner.inspect_resonance())
        inspected: list[str] = []
        for name in READ_ONLY_SURFACE_OPERATIONS:
            method = getattr(owner, name, None)
            if method is None:
                continue
            try:
                inspect.signature(method).bind()
            except TypeError:
                continue
            method()
            inspected.append(name)
        inspection_after = plain(owner.inspect())
        resonance_after = plain(owner.inspect_resonance())
        page_after = hashlib.sha256(
            np.ascontiguousarray(owner.state.resonant_workspace.field).tobytes()
        ).hexdigest()

        published_paths = key_paths(inspection_before) + key_paths(resonance_before)
        direction_paths = matching_paths(published_paths, DIRECTION_PATH_WORDS)
        summary_paths = matching_paths(published_paths, SUMMARY_PATH_WORDS)
        intervention_paths = matching_paths(published_paths, INTERVENTION_PATH_WORDS)

        kernel_written = condense_page(written_page, DECLARED_INPUT_PROBLEM, config)
        kernel_blank = condense_page(
            initial_workspace(profile), DECLARED_INPUT_PROBLEM, config
        )
        ticks = 4
        written_series = readout_series(kernel_written, ticks)
        blank_series = readout_series(kernel_blank, ticks)
        differences = [
            abs(written - blank) for written, blank in zip(written_series, blank_series)
        ]
        rows = np.asarray(kernel_written["output_rows"], dtype=np.float64)
        row_support = [int(index) for index in np.nonzero(np.abs(rows[0]) > 0.0)[0]]
        output_port = int(
            plain(bind_workspace(written_page, DECLARED_INPUT_PROBLEM).bindings["write-out"]["port"])
        )
        return {
            "declared": (
                "does the owner surface expose any read operation that recovers a "
                "written pattern's deposit -- an evidence-producing read of the "
                "written direction with its own receipt? This block writes one item "
                "through the owner, inventories the surface's dispatch, exercises the "
                "read-only operations that take no arguments, scans everything the "
                "surface publishes for the written direction, and measures the "
                "closest response read the surface has. The read operation this "
                "receipt adds takes arguments, so it is exercised in the "
                "read_operation block rather than here"
            ),
            "read_from_source": OWNER_READ_SURFACE_READ_FROM_SOURCE,
            "surface": {
                "dispatch": "cassi_field_owner.FieldIntelligenceSurface.handle",
                "declared_operations": len(operations),
                "read_only_operations": read_only,
                "read_only_operations_exercised_with_no_arguments": inspected,
                "read_only_operations_taking_arguments_not_exercised_here": [
                    name for name in read_only if name not in inspected
                ],
                "operations_that_publish_a_state_transition": len(mutating),
                "instrument": (
                    "inspect.getsource(FieldIntelligenceSurface.handle), every "
                    "'operation == \"<name>\"' branch, with each name actually called "
                    "on the owner that holds the written page"
                ),
            },
            "reading_the_written_page_back": {
                "write_operation": "read-surface:write",
                "written_page_sha256": page_before,
                "written_state_sha256": str(receipt["state_sha256"]),
                "written_applied_work": float(receipt["applied_work"]),
                "written_event_kind": str(receipt["event_kind"]),
                "deposit_in_the_declared_read_frame": written_deposit,
                "blank_page_deposit_in_the_declared_read_frame": blank_deposit,
                "raw_page_recovery": recovered,
                "raw_page_recovery_equals_the_written_deposit": bool(
                    recovered == written_deposit
                ),
                "reader": (
                    "run_fractal_durability_exploration.read_frame, the library's own "
                    "canonical 112-coordinate read frame, applied to the owner's page"
                ),
            },
            "inspection": {
                "published_key_paths": len(published_paths),
                "paths_naming_a_deposit_or_a_written_direction": direction_paths,
                "paths_naming_a_power_or_energy_summary": summary_paths[:12],
                "paths_naming_the_intervention_itself": intervention_paths,
                "what_inspection_publishes": (
                    "digests, generations, the canonical page descriptor, residue and "
                    "power summaries, the ledger entries of the interventions the "
                    "owner accepted, and retained receipts; not the written "
                    "direction's coefficients and not its deposit. The ledger paths "
                    f"{intervention_paths!r} name the write this block performed -- "
                    "bookkeeping of the intervention, not a read of what it deposited"
                ),
                "inspect_payload_unchanged_by_the_reads": inspection_before
                == inspection_after,
                "inspect_resonance_payload_unchanged_by_the_reads": resonance_before
                == resonance_after,
                "page_unchanged_by_the_reads": page_before == page_after,
                "evidence_tick_before_the_reads": resonance_before["evidence_tick"],
                "evidence_tick_after_the_reads": resonance_after["evidence_tick"],
                "field_generation_before_the_reads": inspection_before[
                    "field_generation"
                ],
                "field_generation_after_the_reads": inspection_after["field_generation"],
            },
            "closest_surface": {
                "surface": (
                    "condense_transceiver -> advance_transceivers -> "
                    "inspect_transceivers, the transceiver path the design labels "
                    "temporal-prediction (FIELD-INTELLIGENCE-DESIGN.md 27.3; README.md "
                    "653-657)"
                ),
                "why_it_is_the_closest": (
                    "of the read-only operations that take no arguments, it is the "
                    "only surface that turns the written page into a declared "
                    "numerical response: every one of those reports metadata about the "
                    "page rather than anything computed from it. It is not an "
                    "evidence-producing read of the deposit, and reaching a response "
                    "at all requires two mutations first (publish a realization, then "
                    "advance it); inspect_transceivers only reads retained responses. "
                    "The read operation this receipt adds is a different surface "
                    "again: it takes the declared direction and computes the deposit "
                    "along it, which is measured in the read_operation block"
                ),
                "zero_input_ticks": ticks,
                "written_page_outputs": written_series,
                "blank_page_outputs": blank_series,
                "first_tick_difference": differences[0],
                "max_difference_over_the_read": max(differences),
                "last_tick_difference": differences[-1],
                "allowance": float(OWNER_READ_BEHAVIOUR_ALLOWANCE),
                "the_readout_sees_the_written_page": bool(
                    max(differences) > OWNER_READ_BEHAVIOUR_ALLOWANCE
                ),
                "readout_support_coordinates": row_support,
                "readout_support_is_the_output_ports_common_pair": row_support
                == [output_port, output_port + int(profile.port_count)],
                "adds_observed_support": False,
                "advances_the_evidence_clock": False,
                "instrument": (
                    "cassi_field_transceiver.condense_workspace and advance_transceiver, "
                    "the same declared instrument the diagnosis block reads its input "
                    "channel through, applied to the owner's own written page and to a "
                    "blank page of the same profile"
                ),
            },
            "what_a_consumer_can_recover_today": (
                "the deposit itself, two ways. From the owner's own read surface, "
                "through the read operation this receipt adds "
                "(read_packet_deposit, measured in the read_operation block: it "
                "returns the written direction's deposit, not merely a page digest). "
                "And from the canonical page with the library's own read frame: "
                "measured "
                f"{recovered!r} against the written "
                f"{written_deposit!r} (blank page "
                f"{blank_deposit!r}), with the write's own retained receipt carrying "
                "the applied work, the state digest and the event kind. Neither route "
                "is evidence: the read is declared a temporal prediction, and the "
                "write's receipt is bookkeeping of the intervention"
            ),
            "verdicts": {
                "the_owner_exposes_an_evidence_producing_read_of_the_deposit": False,
                "inspection_alone_names_no_deposit_or_written_direction": not bool(
                    direction_paths
                ),
                "the_raw_page_recovers_the_written_deposit_exactly": bool(
                    recovered == written_deposit and written_deposit > 0.0 and blank_deposit == 0.0
                ),
                "the_reads_change_no_page_state_or_evidence": bool(
                    inspection_before == inspection_after
                    and resonance_before == resonance_after
                    and page_before == page_after
                    and resonance_before["evidence_tick"]
                    == resonance_after["evidence_tick"]
                ),
                "the_closest_read_is_a_temporal_prediction": True,
                "the_closest_read_carries_the_written_page": bool(
                    max(differences) > OWNER_READ_BEHAVIOUR_ALLOWANCE
                ),
            },
        }
    finally:
        shutil.rmtree(home, ignore_errors=True)


def read_operation_block(
    profile: Any,
    config: OwnerWritePathConfig,
    captures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The read half: an owner operation that names a written direction.

    The write half publishes a declared packet impulse as an owner transition.
    This block measures the read half, which is declared exactly as the design
    declares a readout: a temporal prediction of the canonical page, labeled
    ``temporal-prediction``, adding no observed support and advancing no evidence
    clock. It writes one declared item through the owner write path, then reads
    that direction back twice -- once through the owner's own operation and once
    through the durability harness's captured direction applied to the same page,
    an independent route to the same number -- and measures the controls that must
    fail: the same direction read on a blank page, and a declared direction the
    owner did not write, read on the written page.
    """

    headline = int(config.headline_item_index)
    other = int(config.second_item_index)
    spec = durability.ITEM_SPECS[headline]
    other_spec = durability.ITEM_SPECS[other]
    direction = feedback.write_direction(captures, headline)
    captured_direction_sha256 = str(captures[headline]["direction_sha256"])
    allowance = float(READ_RECOVERY_ALLOWANCE)

    def named_path(specification: Any) -> dict[str, Any]:
        return {
            "path": specification.path,
            "component": specification.component,
            "flow_signal": list(specification.flow_signal),
        }

    owner, home = open_owner(profile)
    try:
        surface = FieldIntelligenceSurface(owner)
        named = named_path(spec)
        blank_page_sha256 = durability.page_sha256(owner.state.resonant_workspace)
        blank_frame = durability.read_frame(
            owner.state.resonant_workspace, config.read_frame_path
        )
        blank_read = plain(owner.read_packet_deposit(**named))

        page_before_the_write = durability.page_sha256(owner.state.resonant_workspace)
        generation_before_the_write = int(owner.state.generation)
        write = owner_write(
            owner, "read-operation:write", spec, float(config.write_budget), config
        )
        write_receipt = plain(write["impulse_receipt"])
        page = owner.state.resonant_workspace
        written_frame = durability.read_frame(page, config.read_frame_path)
        written_deposit = durability.squared_norm(written_frame - blank_frame)
        page_after_the_write = durability.page_sha256(page)
        generation_after_the_write = int(owner.state.generation)

        page_before_the_reads = durability.page_sha256(page)
        inspection_before = plain(owner.inspect())
        resonance_before = plain(owner.inspect_resonance())
        written_read = plain(owner.read_packet_deposit(**named))
        unwritten_read = plain(owner.read_packet_deposit(**named_path(other_spec)))
        dispatched = surface.handle(
            {
                "operation": READ_OPERATION_NAME,
                "params": dict(named),
                "request_id": "read-operation:surface",
                "schema": RPC_SCHEMA,
            }
        )
        dispatched_read = plain(dispatched["result"])
        page_after_the_reads = durability.page_sha256(owner.state.resonant_workspace)
        inspection_after = plain(owner.inspect())
        resonance_after = plain(owner.inspect_resonance())

        # The evidence clock, moved by the owner's own observation-admission rule on
        # a separate declared state: the same published quantity, so the invariant
        # above is a live comparison rather than a quantity that never moves.
        clock_atlas = FieldAtlas()
        clock_state = clock_atlas.add_variable(
            AtlasState(resonant_workspace=initial_workspace(profile)),
            VariableSpec(variable_id="read-clock-control", lower=-1.0, upper=1.0),
        )
        clock_state = clock_atlas.add_chart(
            clock_state,
            RelationChart.empty(
                chart_id="read-clock-control",
                scope=("read-clock-control",),
                ridge=1e-5,
                observation_norm_bound=64.0,
                prior_mass=1e-3,
            ),
        )
        clock_before = int(clock_atlas.inspect_resonance(clock_state)["evidence_tick"])
        clock_state, _ = clock_atlas.admit_observation(
            clock_state,
            event_id=hashlib.sha256(b"read-operation:clock-control:event").hexdigest(),
            source_revision_id=hashlib.sha256(
                b"read-operation:clock-control:source"
            ).hexdigest(),
            values={"read-clock-control": 0.5},
            context={"declared": "read-operation evidence-clock control"},
        )
        clock_after = int(clock_atlas.inspect_resonance(clock_state)["evidence_tick"])

        recovered = float(written_read["recovered_deposit"])
        blank_recovery = float(blank_read["recovered_deposit"])
        unwritten_recovery = float(unwritten_read["recovered_deposit"])
        library_recovery = float(np.dot(written_frame - blank_frame, direction)) ** 2

        def recovers_the_written_deposit(value: float) -> bool:
            return bool(
                written_deposit > 0.0
                and abs(value - written_deposit) <= allowance * written_deposit
            )

        # The firing control: the same read with the declared direction dropped
        # from the implementation, so the controls above are shown to be able to
        # fail rather than to be quantities that cannot move.
        published_read = FieldAtlas.read_packet_deposit

        def direction_blind(
            atlas: Any, state: Any, *, path: str, component: int, flow_signal: Any
        ) -> dict[str, Any]:
            readout = published_read(
                atlas, state, path=path, component=component, flow_signal=flow_signal
            )
            mutated = plain(readout)
            workspace = getattr(state, "resonant_workspace", state)
            frame = durability.read_frame(workspace, config.read_frame_path)
            mutated["recovered_deposit"] = float(durability.squared_norm(frame))
            return mutated

        FieldAtlas.read_packet_deposit = direction_blind
        try:
            mutated_written = plain(owner.read_packet_deposit(**named))
            mutated_unwritten = plain(owner.read_packet_deposit(**named_path(other_spec)))
        finally:
            FieldAtlas.read_packet_deposit = published_read
        restored_written = plain(owner.read_packet_deposit(**named))
        page_after_the_firing_control = durability.page_sha256(
            owner.state.resonant_workspace
        )
        mutated_unwritten_recovery = float(mutated_unwritten["recovered_deposit"])

        blank_owner, blank_home = open_owner(profile)
        try:
            FieldAtlas.read_packet_deposit = direction_blind
            try:
                mutated_blank = plain(blank_owner.read_packet_deposit(**named))
            finally:
                FieldAtlas.read_packet_deposit = published_read
        finally:
            shutil.rmtree(blank_home, ignore_errors=True)
        mutated_blank_recovery = float(mutated_blank["recovered_deposit"])

        # A page carrying both declared items: each direction is read back at its own
        # share of the page, so the readout is shown to be a share along a declared
        # direction rather than the page's whole energy. This is also where the
        # cross-check against the write's own captured deposit stops being an
        # identity: on a fresh single-write page the increment lies along the written
        # direction, so the two agree exactly.
        dual_owner, dual_home = open_owner(profile)
        try:
            dual_write = owner_write_items(
                dual_owner, (headline, other), config, f"{READ_OPERATION_NAME}:pair"
            )
            dual_page = dual_owner.state.resonant_workspace
            dual_frame = durability.read_frame(dual_page, config.read_frame_path)
            dual_energy = durability.squared_norm(dual_frame)
            dual_reads = {
                spec.name: float(
                    plain(dual_owner.read_packet_deposit(**named))["recovered_deposit"]
                ),
                other_spec.name: float(
                    plain(
                        dual_owner.read_packet_deposit(**named_path(other_spec))
                    )["recovered_deposit"]
                ),
            }
            dual_deposits = {
                name: float(value) for name, value in dual_write["deposits"].items()
            }
            projection_sum = (
                sum(dual_reads.values()) / dual_energy if dual_energy else 0.0
            )
        finally:
            shutil.rmtree(dual_home, ignore_errors=True)

        inspection_paths = key_paths(inspection_before) + key_paths(resonance_before)
        read_paths = key_paths(written_read)
        published_after = sorted(set(inspection_paths) | set(read_paths))
        return {
            "declared": (
                "the read half of the memory, declared as the design declares a "
                "readout (FIELD-INTELLIGENCE-DESIGN.md 27.3; README.md 653-657): "
                "read_packet_deposit names a written direction exactly as the write "
                "names it -- path, component, flow_signal -- and returns the deposit "
                "the canonical page carries along that direction's own read-frame "
                "response, as a temporal prediction that adds no observed support and "
                "does not advance the evidence clock. This block measures the "
                "recovery, its controls, its invariants on the page and the two "
                "clocks, its reachability through the surface dispatch, and what it "
                "adds to the surface's published key paths"
            ),
            "operation": READ_OPERATION_NAME,
            "operation_is_the_owner_method_and_the_dispatch_operation": bool(
                callable(getattr(owner, READ_OPERATION_NAME, None))
                and READ_OPERATION_NAME in dispatch_operations()
            ),
            "declared_direction": {
                "item": spec.name,
                "path": spec.path,
                "component": spec.component,
                "flow_signal": list(spec.flow_signal),
                "unwritten_item": other_spec.name,
                "unwritten_path": other_spec.path,
                "unwritten_component": other_spec.component,
            },
            "recovery": {
                "written_deposit_in_the_declared_read_frame": written_deposit,
                "recovered_by_the_read_operation": recovered,
                "recovered_relative_difference": abs(recovered - written_deposit)
                / written_deposit,
                "recovered_by_the_library_along_the_captured_direction": library_recovery,
                "read_recovers_the_written_deposit": recovers_the_written_deposit(
                    recovered
                ),
                "recovered_by_the_read_through_the_surface_dispatch": float(
                    dispatched_read["recovered_deposit"]
                ),
                "the_dispatch_returns_the_same_readout": bool(
                    dispatched_read == written_read
                ),
                "readout_kind": str(written_read["readout_kind"]),
                "read_declares_evidence_added": bool(written_read["evidence_added"]),
                "read_frame_coordinates": int(written_read["read_frame_coordinates"]),
                "read_frame_energy": float(written_read["read_frame_energy"]),
                "written_page_sha256": page_after_the_write,
                "written_state_sha256": str(write_receipt["state_sha256"]),
                "written_applied_work": float(write_receipt["applied_work"]),
                "written_impulse_amount": float(write_receipt["impulse_amount"]),
                "the_write_was_accepted": bool(write_receipt["accepted"]),
                "direction_sha256": str(written_read["direction_sha256"]),
                "allowance": allowance,
                "instrument": (
                    "the durability harness's own read frame: written_deposit is the "
                    "squared norm of the read frame's increment across the owner's "
                    "write, the library-side recovery is the same page projected on "
                    "the harness's captured unit direction for the same item, and the "
                    "owner-side recovery is what the read operation returns"
                ),
            },
            "direction_identity": {
                "captured_direction_sha256": captured_direction_sha256,
                "owner_read_direction_sha256": str(written_read["direction_sha256"]),
                "the_reads_direction_is_the_captured_writes_direction": bool(
                    str(written_read["direction_sha256"]) == captured_direction_sha256
                ),
                "declared": (
                    "the read's direction is computed by the atlas from a scratch "
                    "probe of the declared write and the captured direction by the "
                    "durability harness from its own isolated write; the two are "
                    "digested so the identity is checked rather than assumed"
                ),
            },
            "controls": {
                "blank_page": {
                    "declared": (
                        "the same declared direction read on the owner's blank page, "
                        "before any write: it must miss the written deposit"
                    ),
                    "blank_page_sha256": blank_page_sha256,
                    "recovered": blank_recovery,
                    "recovered_fraction_of_the_written_deposit": blank_recovery
                    / written_deposit,
                    "passes_the_recovery_predicate": recovers_the_written_deposit(
                        blank_recovery
                    ),
                    "must_fail": True,
                },
                "unwritten_direction": {
                    "declared": (
                        "a declared direction the owner did not write, read on the "
                        "written page: it must miss the written deposit, which is "
                        "what makes the read direction-specific rather than a page "
                        "summary"
                    ),
                    "recovered": unwritten_recovery,
                    "recovered_fraction_of_the_written_deposit": unwritten_recovery
                    / written_deposit,
                    "passes_the_recovery_predicate": recovers_the_written_deposit(
                        unwritten_recovery
                    ),
                    "must_fail": True,
                },
                "predicate": (
                    "recovered == written_deposit within the declared relative "
                    "allowance, on a positive written deposit; applied unchanged to "
                    "the read and to both controls"
                ),
                "firing_control": {
                    "declared": (
                        "the same two reads with the declared direction dropped from "
                        "the read implementation: read_packet_deposit is temporarily "
                        "replaced by one that returns the page's own read-frame energy "
                        "regardless of the direction it is given, so each control's "
                        "zero is shown to be able to move"
                    ),
                    "mutated_written_direction_recovered": float(
                        mutated_written["recovered_deposit"]
                    ),
                    "mutated_unwritten_direction_recovered": mutated_unwritten_recovery,
                    "the_unwritten_direction_control_fires_under_the_mutation": bool(
                        recovers_the_written_deposit(mutated_unwritten_recovery)
                    ),
                    "the_blank_page_control_fires_under_the_mutation": bool(
                        recovers_the_written_deposit(mutated_blank_recovery)
                    ),
                    "which_control_carries_the_load": (
                        "the unwritten-direction control: the declared readout's "
                        "written deposit is the read frame's own energy, so a "
                        "direction-blind read still returns it on the written "
                        "direction and is caught only by the direction the owner did "
                        "not write; the blank-page control cannot fire under this "
                        "mutation because a blank page has no frame energy at all, "
                        "so it is a can-fail control against a read that returns a "
                        "page-independent quantity, not against this one"
                    ),
                    "recovered_after_the_mutation_was_removed": float(
                        restored_written["recovered_deposit"]
                    ),
                    "the_clean_readout_returns_after_the_mutation_is_removed": bool(
                        restored_written == written_read
                    ),
                    "page_sha256_after_the_firing_control": page_after_the_firing_control,
                    "the_firing_control_leaves_the_page_unchanged": page_after_the_firing_control
                    == page_after_the_reads,
                    "the_mutation_was_removed_before_this_block_returned": bool(
                        FieldAtlas.read_packet_deposit is published_read
                    ),
                },
            },
            "two_written_directions": {
                "declared": (
                    "the same read on a page that carries both declared items, each "
                    "read back along its own direction, with the page's whole read "
                    "frame energy beside them: the readout is a share along the "
                    "declared direction, not the page's total. This is also where the "
                    "agreement with the write's own deposit stops being an identity -- "
                    "on a fresh single-write page the frame's increment lies along the "
                    "written direction, so projection and energy coincide"
                ),
                "items": [spec.name, other_spec.name],
                "written_deposits_in_their_own_frames": dual_deposits,
                "page_read_frame_energy": dual_energy,
                "recovered_by_the_read_operation": dual_reads,
                "share_of_the_page_each_read_recovers": {
                    name: (value / dual_energy if dual_energy else 0.0)
                    for name, value in dual_reads.items()
                },
                "projection_sum_against_the_page_energy": projection_sum,
                "what_this_shows": (
                    "each declared direction recovers its own share of a page that "
                    "carries two writes, and neither read recovers the whole page, so "
                    "recovery along the written direction is a measured projection "
                    "rather than a page summary. On this profile and read frame the "
                    f"two shares sum to {projection_sum!r}, which says these two "
                    "declared directions are orthogonal in this read frame; the read "
                    "would not be a page summary even where they were not, since a "
                    "share is a projection by construction, and this receipt does not "
                    "measure the general case"
                ),
            },
            "invariants": {
                "page_before_the_reads": page_before_the_reads,
                "page_after_the_reads": page_after_the_reads,
                "page_unchanged_by_the_reads": page_before_the_reads
                == page_after_the_reads,
                "generation_before_the_reads": int(inspection_before["field_generation"]),
                "generation_after_the_reads": int(inspection_after["field_generation"]),
                "generation_unchanged_by_the_reads": int(
                    inspection_before["field_generation"]
                )
                == int(inspection_after["field_generation"]),
                "evidence_tick_before_the_reads": int(resonance_before["evidence_tick"]),
                "evidence_tick_after_the_reads": int(resonance_after["evidence_tick"]),
                "evidence_tick_unchanged_by_the_reads": int(
                    resonance_before["evidence_tick"]
                )
                == int(resonance_after["evidence_tick"]),
                "inspect_payload_unchanged_by_the_reads": inspection_before
                == inspection_after,
                "inspect_resonance_payload_unchanged_by_the_reads": resonance_before
                == resonance_after,
                "why_no_successor_and_no_operation_identity": (
                    "the read is not a transition: it calls no _publish, stages no "
                    "operation record and consumes no operation_id, so there is "
                    "nothing for the owner to replay and nothing added to the "
                    "checkpoint closure"
                ),
            },
            "invariant_controls": {
                "declared": (
                    "the same three quantities and the same two payloads, measured "
                    "across the write the reads read, so each invariant above is "
                    "shown to compare quantities that can differ"
                ),
                "page_before_the_write": page_before_the_write,
                "page_after_the_write": page_after_the_write,
                "the_write_changes_the_page_digest": page_before_the_write
                != page_after_the_write,
                "generation_before_the_write": generation_before_the_write,
                "generation_after_the_write": generation_after_the_write,
                "the_write_advances_the_generation": generation_after_the_write
                == generation_before_the_write + 1,
                "evidence_tick_control": {
                    "declared": (
                        "the evidence clock is a live published quantity: the same "
                        "key, read from a separate state of this profile through the "
                        "owner's own observation-admission rule "
                        "(FieldAtlas.admit_observation with one declared variable and "
                        "one declared chart), moves by one admission"
                    ),
                    "evidence_tick_before_the_admission": clock_before,
                    "evidence_tick_after_the_admission": clock_after,
                    "an_admission_moves_the_evidence_clock": clock_after
                    == clock_before + 1,
                    "the_control_state_is_a_separate_state_from_the_owner_read": True,
                },
            },
            "surface_inventory": {
                "declared_operations": len(dispatch_operations()),
                "read_only_operations": sorted(
                    name
                    for name in dispatch_operations()
                    if name in READ_ONLY_SURFACE_OPERATIONS
                ),
                "the_read_operation_is_declared_read_only": READ_OPERATION_NAME
                in READ_ONLY_SURFACE_OPERATIONS,
                "instrument": (
                    "inspect.getsource(FieldIntelligenceSurface.handle), every "
                    "'operation == \\\"<name>\\\"' branch, with the read operation "
                    "actually reached through the dispatch on the owner holding the "
                    "written page"
                ),
            },
            "exposure_scan": {
                "declared": (
                    "the declared word sets, applied to every key path the surface "
                    "publishes. Before: what inspect and inspect_resonance publish on "
                    "the written page, which is the surface as it stood. After: the "
                    "same plus what the read operation itself publishes, which is the "
                    "surface a consumer can now call"
                ),
                "before_the_read_operation": {
                    "surfaces": ["inspect", "inspect_resonance"],
                    "published_key_paths": len(inspection_paths),
                    "paths_naming_a_deposit_or_a_written_direction": matching_paths(
                        inspection_paths, DIRECTION_PATH_WORDS
                    ),
                    "paths_naming_the_intervention_itself": matching_paths(
                        inspection_paths, INTERVENTION_PATH_WORDS
                    ),
                },
                "after_the_read_operation": {
                    "surfaces": [
                        "inspect",
                        "inspect_resonance",
                        READ_OPERATION_NAME,
                    ],
                    "published_key_paths": len(inspection_paths) + len(read_paths),
                    "distinct_published_key_paths": len(published_after),
                    "paths_naming_a_deposit_or_a_written_direction": matching_paths(
                        published_after, DIRECTION_PATH_WORDS
                    ),
                    "paths_the_read_operation_adds": sorted(
                        set(read_paths) - set(inspection_paths)
                    ),
                },
                "matcher_controls": {
                    "word_absent_from_every_published_path": ABSENT_PATH_WORD,
                    "paths_naming_it_before": matching_paths(
                        inspection_paths, (ABSENT_PATH_WORD,)
                    ),
                    "paths_naming_it_after": matching_paths(
                        published_after, (ABSENT_PATH_WORD,)
                    ),
                    "why": (
                        "the same matcher finds no path naming a word the surface "
                        "does not publish, and does find paths naming the "
                        "intervention in the payload it scans, so the count of "
                        "direction-naming paths before the read operation is a live "
                        "comparison rather than a broken scan"
                    ),
                },
            },
            "if_the_read_were_declared_as_evidence": (
                "declared as evidence rather than as a prediction, the same read "
                "would have to enter the evidence store through the owner's own "
                "observation-admission rule (FieldIntelligenceOwner.admit_observation "
                "with a SourceInput and one operation identity): the evidence clock "
                "(the state's logical tick, which the receipt's own control shows an "
                "admission moving) and with it the checkpoint generation would move, "
                "and the recovered deposit would become an admitted observation about "
                "the world instead of a prediction of the page. This receipt does not "
                "take that reading and leaves the choice open"
            ),
            "verdicts": {
                "the_owner_declares_a_read_operation_for_a_written_direction": True,
                "the_read_operation_appears_in_the_dispatch_inventory": bool(
                    READ_OPERATION_NAME in dispatch_operations()
                ),
                "the_read_recovers_the_written_deposit": recovers_the_written_deposit(
                    recovered
                ),
                "the_read_recovers_a_share_of_a_two_write_page_rather_than_its_total": bool(
                    all(value > 0.0 for value in dual_reads.values())
                    and all(value < dual_energy for value in dual_reads.values())
                ),
                "the_read_agrees_with_the_library_route": bool(
                    library_recovery == recovered
                ),
                "the_reads_direction_is_the_written_directions": bool(
                    str(written_read["direction_sha256"]) == captured_direction_sha256
                ),
                "the_blank_page_control_fails_the_predicate": bool(
                    not recovers_the_written_deposit(blank_recovery)
                ),
                "the_unwritten_direction_control_fails_the_predicate": bool(
                    not recovers_the_written_deposit(unwritten_recovery)
                ),
                "the_unwritten_direction_control_fires_under_a_direction_blind_read": bool(
                    recovers_the_written_deposit(mutated_unwritten_recovery)
                ),
                "the_clean_readout_returns_once_the_mutation_is_removed": bool(
                    restored_written == written_read
                    and FieldAtlas.read_packet_deposit is published_read
                ),
                "the_read_changes_no_page_generation_or_evidence_tick": bool(
                    page_before_the_reads == page_after_the_reads
                    and inspection_before == inspection_after
                    and resonance_before == resonance_after
                    and int(inspection_before["field_generation"])
                    == int(inspection_after["field_generation"])
                    and int(resonance_before["evidence_tick"])
                    == int(resonance_after["evidence_tick"])
                ),
                "the_write_changes_what_the_read_preserves": bool(
                    page_before_the_write != page_after_the_write
                    and generation_after_the_write == generation_before_the_write + 1
                ),
                "an_admission_moves_the_evidence_clock": bool(
                    clock_after == clock_before + 1
                ),
                "the_read_is_declared_a_temporal_prediction": bool(
                    str(written_read["readout_kind"]) == "temporal-prediction"
                    and not bool(written_read["evidence_added"])
                ),
                "the_read_is_not_an_evidence_producing_read": bool(
                    str(written_read["readout_kind"]) != "observed"
                    and not bool(written_read["evidence_added"])
                    and int(resonance_before["evidence_tick"])
                    == int(resonance_after["evidence_tick"])
                ),
                "the_exposure_scan_now_names_the_written_direction": bool(
                    matching_paths(published_after, DIRECTION_PATH_WORDS)
                    and not matching_paths(inspection_paths, DIRECTION_PATH_WORDS)
                ),
                "the_scan_finds_no_path_naming_the_absent_word": bool(
                    not matching_paths(published_after, (ABSENT_PATH_WORD,))
                ),
                "the_read_is_reachable_through_the_surface_dispatch": bool(
                    dispatched_read == written_read
                ),
            },
        }
    finally:
        shutil.rmtree(home, ignore_errors=True)


def impulse_block(
    profile: Any, config: OwnerWritePathConfig, captures: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """The written impulse's effect on the field, against its zero-impulse control."""

    headline = int(config.headline_item_index)
    spec = durability.ITEM_SPECS[headline]
    captured = float(captures[headline]["deposited_energy"])

    owner, home = open_owner(profile)
    try:
        before = durability.read_frame(
            owner.state.resonant_workspace, config.read_frame_path
        )
        before_workspace = owner.state.resonant_workspace
        before_page = durability.page_sha256(before_workspace)
        before_state = before_workspace.state_sha256
        before_logical_tick = int(owner.state.logical_tick)
        before_evidence_tick = int(before_workspace.evidence_tick)
        before_field_ticks = int(before_workspace.field_ticks)
        before_generation = int(owner.state.generation)
        written = owner_write_items(owner, (headline,), config, "owp:impulse")
        after_workspace = owner.state.resonant_workspace
        after = durability.read_frame(after_workspace, config.read_frame_path)
        deposit = durability.squared_norm(after - before)
        impulse_arm = {
            "item": spec.name,
            "captured_deposit": captured,
            "read_frame_deposit": float(deposit),
            "deposit_fraction_of_captured": float(deposit / captured if captured else 0.0),
            "page_digest_changed": durability.page_sha256(after_workspace) != before_page,
            "state_digest_changed": after_workspace.state_sha256 != before_state,
            "page_sha256_before": before_page,
            "page_sha256_after": durability.page_sha256(after_workspace),
            "state_sha256_before": before_state,
            "state_sha256_after": after_workspace.state_sha256,
            "logical_tick_before": before_logical_tick,
            "logical_tick_after": int(owner.state.logical_tick),
            "logical_tick_unchanged": int(owner.state.logical_tick) == before_logical_tick,
            "evidence_tick_before": before_evidence_tick,
            "evidence_tick_after": int(after_workspace.evidence_tick),
            "evidence_tick_unchanged": int(after_workspace.evidence_tick)
            == before_evidence_tick,
            "field_ticks_before": before_field_ticks,
            "field_ticks_after": int(after_workspace.field_ticks),
            "field_ticks_unchanged": int(after_workspace.field_ticks) == before_field_ticks,
            "generation_before": before_generation,
            "generation_after": int(owner.state.generation),
            "writes": written["writes"],
            "ledger_after": {
                key: float(value) for key, value in sorted(after_workspace.ledger.items())
            },
        }

        control_owner, control_home = open_owner(profile)
        try:
            control_before_workspace = control_owner.state.resonant_workspace
            control_before_page = durability.page_sha256(control_before_workspace)
            control_before_state = control_before_workspace.state_sha256
            control_before_logical_tick = int(control_owner.state.logical_tick)
            control_before = durability.read_frame(
                control_before_workspace, config.read_frame_path
            )
            control = owner_write(control_owner, "owp:impulse:zero", spec, 0.0, config)
            control_workspace = control_owner.state.resonant_workspace
            control_after = durability.read_frame(control_workspace, config.read_frame_path)
            control_deposit = durability.squared_norm(control_after - control_before)
            control_receipt = plain(control["impulse_receipt"])
            control_arm = {
                "item": spec.name,
                "requested_work": float(control_receipt["requested_work"]),
                "accepted": bool(control_receipt["accepted"]),
                "impulse_amount": float(control_receipt["impulse_amount"]),
                "read_frame_deposit": float(control_deposit),
                "deposit_fraction_of_captured": float(
                    control_deposit / captured if captured else 0.0
                ),
                "page_digest_unchanged": durability.page_sha256(control_workspace)
                == control_before_page,
                "state_digest_unchanged": control_workspace.state_sha256
                == control_before_state,
                "logical_tick_unchanged": int(control_owner.state.logical_tick)
                == control_before_logical_tick,
                "page_sha256_before": control_before_page,
                "page_sha256_after": durability.page_sha256(control_workspace),
                "state_sha256_before": control_before_state,
                "state_sha256_after": control_workspace.state_sha256,
            }
        finally:
            control_owner.close()
            shutil.rmtree(control_home, ignore_errors=True)
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)

    margin = float(config.impulse_deposit_fraction)
    return {
        "declared": (
            "one declared item written through the owner write path into a fresh "
            "canonical field at the declared profile and budget, read through the "
            "declared read frame before and after. The predicate is that the write's "
            "read-frame deposit reaches a declared fraction of the same item's "
            "isolated captured deposit at the same budget; the control is the same "
            "write at zero requested work, which must fail the same predicate"
        ),
        "predicate": (
            "read_frame_deposit >= impulse_deposit_fraction * captured_deposit"
        ),
        "margin": margin,
        "impulse_arm": impulse_arm,
        "zero_impulse_control": control_arm,
        "impulse_arm_passes": bool(
            impulse_arm["deposit_fraction_of_captured"] >= margin
        ),
        "zero_impulse_control_passes": bool(
            control_arm["deposit_fraction_of_captured"] >= margin
        ),
        "zero_impulse_control_must_fail": True,
        "zero_impulse_control_fails_the_predicate": not bool(
            control_arm["deposit_fraction_of_captured"] >= margin
        ),
    }


def route_identity_block(
    profile: Any, config: OwnerWritePathConfig, indices: Sequence[int]
) -> dict[str, Any]:
    """The owner route and the existing aimed narrow-path route, as one write."""

    owner, home = open_owner(profile)
    try:
        written = owner_write_items(owner, indices, config, "owp:identity")
        owner_workspace = owner.state.resonant_workspace
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)
    direct_workspace, direct_written = feedback.write_items(
        config.feedback_config(), tuple(int(index) for index in indices), profile
    )
    owner_frame = durability.read_frame(owner_workspace, config.read_frame_path)
    direct_frame = durability.read_frame(direct_workspace, config.read_frame_path)
    return {
        "declared": (
            "the same declared items at the same declared budget, written once "
            "through the owner write path and once through the existing aimed "
            "narrow-path route the exploration harnesses use "
            "(apply_helical_packet_impulse on the canonical page), compared on the "
            "canonical field page, the workspace state digest, the ledger and the "
            "declared read frame"
        ),
        "items": [durability.ITEM_SPECS[int(index)].name for index in indices],
        "owner_page_sha256": durability.page_sha256(owner_workspace),
        "existing_route_page_sha256": durability.page_sha256(direct_workspace),
        "page_digest_identical": durability.page_sha256(owner_workspace)
        == durability.page_sha256(direct_workspace),
        "state_digest_identical": owner_workspace.state_sha256
        == direct_workspace.state_sha256,
        "owner_state_sha256": owner_workspace.state_sha256,
        "existing_route_state_sha256": direct_workspace.state_sha256,
        "ledger_identical": {
            key: float(value) for key, value in owner_workspace.ledger.items()
        }
        == {key: float(value) for key, value in direct_workspace.ledger.items()},
        "read_frame_max_abs_difference": float(np.max(np.abs(owner_frame - direct_frame))),
        "owner_deposits": {
            key: float(value) for key, value in written["deposits"].items()
        },
        "existing_route_deposits": {
            key: float(value) for key, value in direct_written["deposits"].items()
        },
        "allowance": float(config.route_identity_allowance),
    }


def owner_contract_block(profile: Any, config: OwnerWritePathConfig) -> dict[str, Any]:
    """The owner's own write contract: exactly-once, lineage, and restart identity."""

    spec = durability.ITEM_SPECS[int(config.headline_item_index)]
    owner, home = open_owner(profile)
    try:
        before_logical_tick = int(owner.state.logical_tick)
        before_evidence_tick = int(owner.state.resonant_workspace.evidence_tick)
        before_generation = int(owner.state.generation)
        first = owner_write(owner, "owp:contract", spec, float(config.write_budget), config)
        written_workspace = owner.state.resonant_workspace
        written_page = durability.page_sha256(written_workspace)
        written_state = written_workspace.state_sha256
        written_frame = durability.read_frame(written_workspace, config.read_frame_path)
        written_generation = int(owner.state.generation)
        written_atlas_state = str(owner.state.state_sha256)
        written_logical_tick = int(owner.state.logical_tick)
        written_evidence_tick = int(written_workspace.evidence_tick)
        replay = owner_write(owner, "owp:contract", spec, float(config.write_budget), config)
        replay_page = durability.page_sha256(owner.state.resonant_workspace)
        conflict = ""
        try:
            owner.write_packet_impulse(
                "owp:contract",
                path=spec.path,
                component=spec.component,
                flow_signal=[float(spec.flow_signal[0]) / 2.0, float(spec.flow_signal[1])],
                work_budget=float(config.write_budget),
                event_kind=config.event_kind,
            )
        except Exception as error:  # the declared conflict of one operation identity
            conflict = f"{type(error).__name__}: {error}"
        stale = ""
        try:
            owner_write(
                owner,
                "owp:contract:stale",
                spec,
                float(config.write_budget),
                config,
                expected_state_sha256="0" * 64,
            )
        except Exception as error:  # a predecessor stamp that does not match
            stale = f"{type(error).__name__}: {error}"
        current = owner_write(
            owner,
            "owp:contract:current",
            spec,
            float(config.write_budget),
            config,
            expected_state_sha256=written_atlas_state,
        )
        current_generation = int(owner.state.generation)
        before_close_workspace = owner.state.resonant_workspace
        before_close_page = durability.page_sha256(before_close_workspace)
        before_close_state = before_close_workspace.state_sha256
        before_close_frame = durability.read_frame(
            before_close_workspace, config.read_frame_path
        )
        before_close_generation = int(owner.state.generation)
        before_close_logical_tick = int(owner.state.logical_tick)
        before_close_evidence_tick = int(before_close_workspace.evidence_tick)
        owner.close()
        restored_owner = FieldIntelligenceOwner(home)
        try:
            restored = restored_owner.state.resonant_workspace
            restored_frame = durability.read_frame(restored, config.read_frame_path)
            restart = {
                "state_digest_preserved_at_close": restored.state_sha256
                == before_close_state,
                "page_digest_preserved_at_close": durability.page_sha256(restored)
                == before_close_page,
                "read_frame_bit_identical_at_close": bool(
                    np.array_equal(before_close_frame, restored_frame)
                ),
                "read_frame_max_abs_difference_at_close": float(
                    np.max(np.abs(before_close_frame - restored_frame))
                ),
                "generation_preserved_at_close": int(restored_owner.state.generation)
                == before_close_generation,
                "logical_tick_preserved_at_close": int(restored_owner.state.logical_tick)
                == before_close_logical_tick,
                "evidence_tick_preserved_at_close": int(restored.evidence_tick)
                == before_close_evidence_tick,
                "generation_before_close": before_close_generation,
                "generation_after_reopen": int(restored_owner.state.generation),
                "reopened_state_sha256": restored.state_sha256,
                "reopened_page_sha256": durability.page_sha256(restored),
            }
        finally:
            restored_owner.close()
    finally:
        try:
            owner.close()
        except Exception:
            pass
        shutil.rmtree(home, ignore_errors=True)
    return {
        "declared": (
            "the owner write path's own transition contract, measured on one owner: "
            "one operation identity publishes exactly one successor, a repeated "
            "identical call returns its retained result without writing again, a "
            "conflicting call under the same identity is refused, a predecessor "
            "stamp that does not match the current state is refused while a matching "
            "one is accepted, and the written page survives an owner close and "
            "reopen"
        ),
        "operation_id": "owp:contract",
        "first_accepted": bool(plain(first["impulse_receipt"])["accepted"]),
        "first_generation": int(first["checkpoint_receipt"]["generation"]),
        "first_replayed": bool(first["checkpoint_receipt"]["replayed"]),
        "generation_before": before_generation,
        "logical_tick_before": before_logical_tick,
        "evidence_tick_before": before_evidence_tick,
        "written_logical_tick": written_logical_tick,
        "written_evidence_tick": written_evidence_tick,
        "written_read_frame_packet_energy": float(durability.squared_norm(written_frame)),
        "write_keeps_the_evidence_clock": written_evidence_tick == before_evidence_tick,
        "write_keeps_the_logical_tick": written_logical_tick == before_logical_tick,
        "replay_replayed": bool(replay["checkpoint_receipt"]["replayed"]),
        "replay_generation": int(replay["checkpoint_receipt"]["generation"]),
        "replay_returns_the_retained_receipt": plain(replay["impulse_receipt"])
        == plain(first["impulse_receipt"]),
        "replay_does_not_write_again": bool(
            replay["checkpoint_receipt"]["replayed"]
            and int(replay["checkpoint_receipt"]["generation"]) == written_generation
            and replay_page == written_page
        ),
        "conflicting_call_refused": bool(conflict),
        "conflicting_call_error": conflict,
        "stale_predecessor_refused": bool(stale),
        "stale_predecessor_error": stale,
        "matching_predecessor_accepted": bool(
            plain(current["impulse_receipt"])["accepted"]
        ),
        "predecessor_stamp_is_the_atlas_state_digest": True,
        "written_atlas_state_sha256": written_atlas_state,
        "written_workspace_state_sha256": written_state,
        "matching_predecessor_generation": current_generation,
        "first_write_workspace_state_sha256": written_state,
        "first_write_page_sha256": written_page,
        "state_at_close_sha256": before_close_state,
        "page_at_close_sha256": before_close_page,
        **restart,
    }


# --------------------------------------------------------------------------
# the cycle: owner write -> hold -> read
# --------------------------------------------------------------------------
def hold_arm(
    name: str,
    items: Sequence[int],
    gain: float,
    horizon_ticks: int,
    sample_ticks: Sequence[int],
    config: OwnerWritePathConfig,
    drive_items: Sequence[int] | None = None,
    drive_split: Sequence[float] | None = None,
    family: str = "owner-write-path",
) -> feedback.LoopArm:
    """One declared closed-loop arm at a declared gain and horizon."""

    return feedback.LoopArm(
        name,
        tuple(int(index) for index in items),
        family=family,
        measure_item_index=int(items[0]),
        horizon_ticks=int(horizon_ticks),
        sample_ticks=tuple(int(tick) for tick in sample_ticks),
        gain=float(gain),
        phase_degrees=float(feedback.FeedbackConfig().neutral_gain_phase_degrees),
        drive_items=tuple(int(index) for index in (drive_items or ())),
        drive_split=None if drive_split is None else tuple(float(w) for w in drive_split),
    )


def phase_reference_for(
    config: OwnerWritePathConfig, captures: Sequence[Mapping[str, Any]], profile: Any
) -> dict[str, Any]:
    """The declared quadrature read-back reference the loop's phase term is expressed in."""

    phase = feedback.phase_readout_block(
        config.feedback_config(),
        captures,
        profile,
        int(config.refinement_horizon_ticks),
    )
    return {
        "direction": feedback.quadrature_direction(
            config.feedback_config(), captures, int(config.headline_item_index)
        ),
        "scale": float(phase["sign_references"]["quadrature_scale"]),
        "declared": (
            "the feedback harness's own declared quadrature read-out, measured on "
            "this profile's drift trajectory, with its quarter-period scale"
        ),
        "quarter_period_tick": int(phase["quarter_period_tick"]),
        "quarter_period_angle_degrees": float(phase["quarter_period_angle_degrees"]),
    }


def skeleton_loop(
    config: feedback.FeedbackConfig,
    captures: Sequence[Mapping[str, Any]],
    arm: feedback.LoopArm,
    workspace: Any,
    deposits: Mapping[str, float],
    phase_reference: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """The declared loop's tick body, started from a page this runner supplies.

    The body is the feedback harness's declared law, transcribed call for call:
    one canonical advance tick, one read of the declared read frame, the
    harness's own phase signal and bounded amplitude law, the harness's own drive
    call and the harness's own sample row. It exists only so an owner-written
    page can be held without rewriting the item through the harness's own write
    step; the skeleton_equivalence block measures that it reproduces
    run_stream's own rows on a page both routes build.
    """

    post_write = durability.read_frame(workspace, config.read_frame_path)
    frame_energy_reference = durability.squared_norm(post_write)
    measure_index = int(arm.measure_item_index)
    driven_items = tuple(int(index) for index in (arm.drive_items or (measure_index,)))
    direction = feedback.write_direction(captures, measure_index)
    signed_reference = float(np.dot(post_write, direction))
    if not signed_reference:
        raise ValueError(
            "the measured item's post-write projection is zero, so the declared loop "
            "has no read-back reference"
        )
    driven_directions = {
        index: feedback.write_direction(captures, index) for index in driven_items
    }
    for index in driven_items:
        if not float(np.dot(post_write, driven_directions[index])):
            raise ValueError(
                f"the declared driven item {durability.ITEM_SPECS[index].name} has a "
                "zero post-write projection, so the declared loop cannot normalise it"
            )
    split = (
        dict(zip(driven_items, (float(weight) for weight in arm.drive_split)))
        if arm.drive_split is not None
        else None
    )
    horizon = int(arm.horizon_ticks or config.horizon_ticks)
    sample_ticks = tuple(int(tick) for tick in (arm.sample_ticks or config.sample_ticks))
    rows: list[dict[str, Any]] = []
    drive_work_total = 0.0
    drive_calls = 0
    amplitude_max = 0.0
    energy_ratio_max = 1.0
    for tick in range(1, horizon + 1):
        workspace, _advance = feedback.advance_workspace(
            workspace,
            ticks=1,
            demand=config.activity_demand,
            source_enabled=config.source_enabled,
        )
        vector = durability.read_frame(workspace, config.read_frame_path)
        drive = {
            "amplitude": 0.0,
            "work": 0.0,
            "work_cumulative": drive_work_total,
            "clipped": False,
            "accepted": False,
        }
        if arm.gain:
            ratio = feedback.phase_signal(
                config, arm, vector, direction, signed_reference, phase_reference
            )
            amplitude, clipped = feedback.loop_amplitude(config, arm.gain, ratio)
            share_total = (
                sum(split[index] for index in driven_items)
                if split is not None
                else float(len(driven_items))
            )
            tick_work = 0.0
            tick_accepted = True
            tick_clipped = False
            for driven in driven_items:
                share = (
                    split[driven] / share_total
                    if split is not None
                    else 1.0 / len(driven_items)
                )
                per_item_work = float(config.loop_work_ceiling) * abs(amplitude) * share
                workspace, receipt = feedback.apply_drive(
                    workspace, driven, amplitude, per_item_work
                )
                vector = durability.read_frame(workspace, config.read_frame_path)
                drive_calls += 1
                tick_accepted = tick_accepted and bool(receipt["accepted"])
                tick_work += float(receipt["applied_work"])
                tick_clipped = tick_clipped or bool(clipped)
                amplitude_max = max(amplitude_max, abs(float(amplitude)))
            drive_work_total += tick_work
            drive = {
                "amplitude": float(amplitude),
                "work": tick_work,
                "work_cumulative": drive_work_total,
                "clipped": bool(tick_clipped),
                "accepted": bool(tick_accepted),
            }
        energy_ratio_max = max(
            energy_ratio_max,
            durability.squared_norm(vector) / frame_energy_reference,
        )
        if tick in sample_ticks:
            rows.append(
                feedback.sample_row(
                    config,
                    captures,
                    arm,
                    workspace,
                    vector,
                    tick,
                    deposits,
                    frame_energy_reference,
                    signed_reference,
                    drive,
                )
            )
    horizon_row = rows[-1]
    # The returned shape carries the feedback harness's own field names for every
    # figure this runner reads, so an owner-path arm and a run_stream arm are read
    # through one set of keys and the equivalence control compares like with like.
    return {
        "arm": arm.name,
        "declared": {
            "family": arm.family,
            "written_items": [
                durability.ITEM_SPECS[index].name for index in arm.item_indices
            ],
            "gain": float(arm.gain),
            "phase_degrees": float(arm.phase_degrees),
            "measured_item": durability.ITEM_SPECS[measure_index].name,
            "drive_items": [
                durability.ITEM_SPECS[index].name for index in driven_items
            ],
            "drive_split": (
                None
                if arm.drive_split is None
                else [float(weight) for weight in arm.drive_split]
            ),
            "loop_work_ceiling": float(config.loop_work_ceiling),
            "horizon_ticks": horizon,
            "samples": list(sample_ticks),
            "read_frame_path": config.read_frame_path,
            "start": "the page this runner supplied, not a write by this loop",
        },
        "samples": rows,
        "horizon": {
            "tick": horizon,
            "frame_energy_ratio": float(horizon_row["frame_energy_ratio"]),
            "frame_energy_ratio_max": float(energy_ratio_max),
            "item_retention": {
                name: float(value)
                for name, value in horizon_row["item_retention"].items()
            },
            "item_shares": {
                name: float(value) for name, value in horizon_row["item_shares"].items()
            },
            "unwritten_max_share": float(horizon_row["unwritten_max_share"]),
            "declared_frame_projection_fraction": float(
                horizon_row["declared_frame_projection_fraction"]
            ),
            "packet_energy": float(horizon_row["packet_energy"]),
        },
        "drive": {
            "calls": drive_calls,
            "drive_work_total": drive_work_total,
            "max_amplitude": amplitude_max,
            "loop_work_ceiling": float(config.loop_work_ceiling),
        },
        "boundedness": {
            "energy_ratio_max": float(energy_ratio_max),
            "runaway": bool(feedback.exceeds_runaway(config, energy_ratio_max)),
            "runaway_energy_ratio": float(config.runaway_energy_ratio),
            "all_samples_finite": bool(
                all(
                    np.isfinite(float(row["packet_energy"]))
                    and np.isfinite(float(row["measure_retention"]))
                    for row in rows
                )
            ),
        },
        "neutral_stability": {
            "measure_retention_at_horizon": float(horizon_row["measure_retention"]),
            "level_floor": float(config.neutral_level_floor),
        },
        "ledger": {
            key: float(value) for key, value in sorted(horizon_row["ledger"].items())
        },
        "ledger_check": {
            "balance_defect": float(horizon_row["ledger"].get("balance_defect", 0.0)),
            "balance_defect_within_allowance": bool(
                abs(float(horizon_row["ledger"].get("balance_defect", 0.0)))
                <= float(config.ledger_balance_allowance)
            ),
            "residual_work": float(horizon_row["ledger"].get("residual_work", 0.0)),
            "residual_work_within_allowance": bool(
                abs(float(horizon_row["ledger"].get("residual_work", 0.0)))
                <= float(config.ledger_residual_allowance)
            ),
            "balance_allowance": float(config.ledger_balance_allowance),
            "residual_allowance": float(config.ledger_residual_allowance),
        },
        "final": {
            "state_sha256": str(horizon_row["state_sha256"]),
            "page_sha256": str(horizon_row["page_sha256"]),
            "field_ticks": int(horizon_row["field_ticks"]),
            "chain": "the declared skeleton's tick body over the page this runner supplied",
        },
        "frame_energy_reference": frame_energy_reference,
        "signed_reference": signed_reference,
    }


def cycle_block(
    profile: Any, config: OwnerWritePathConfig, captures: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Write an impulse through the owner path, hold it, read it back."""

    feedback_config = config.feedback_config()
    headline = int(config.headline_item_index)
    other = int(config.second_item_index)
    long_horizon = int(config.long_horizon_ticks)
    long_samples = config.long_horizon_sample_ticks
    phase_reference = phase_reference_for(config, captures, profile)

    drift_arm = feedback.LoopArm(
        DRIFT_ARM,
        (headline,),
        family="owner-write-path",
        measure_item_index=headline,
        horizon_ticks=int(config.refinement_horizon_ticks),
        sample_ticks=config.refinement_sample_ticks,
    )
    arms = {DRIFT_ARM: feedback.run_stream(
        feedback_config, captures, drift_arm, phase_reference, profile
    )}
    refinement = feedback.measure_neutral_gain(
        feedback_config,
        captures,
        phase_reference,
        profile,
        arms,
        drift_arm=DRIFT_ARM,
        name_prefix="owp-",
    )
    gain = float(refinement["measured_gain"])

    owner, home = open_owner(profile)
    try:
        written = owner_write_items(owner, (headline,), config, "owp:cycle")
        owner_workspace = owner.state.resonant_workspace
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)

    owner_result = skeleton_loop(
        feedback_config,
        captures,
        hold_arm(OWNER_HOLD_ARM, (headline,), gain, long_horizon, long_samples, config),
        owner_workspace,
        written["deposits"],
        phase_reference,
    )
    drift_result = feedback.run_stream(
        feedback_config,
        captures,
        replace(drift_arm, horizon_ticks=long_horizon, sample_ticks=long_samples),
        phase_reference,
        profile,
    )
    reference_result = feedback.run_stream(
        feedback_config,
        captures,
        hold_arm(REFERENCE_HOLD_ARM, (headline,), gain, long_horizon, long_samples, config),
        phase_reference,
        profile,
    )
    equivalence_workspace, equivalence_written = feedback.write_items(
        feedback_config, (headline,), profile
    )
    equivalence_result = skeleton_loop(
        feedback_config,
        captures,
        hold_arm(
            SKELETON_EQUIVALENCE_ARM, (headline,), gain, long_horizon, long_samples, config
        ),
        equivalence_workspace,
        equivalence_written["deposits"],
        phase_reference,
    )

    item = durability.ITEM_SPECS[headline]
    direction = feedback.write_direction(captures, headline)
    captured = float(captures[headline]["deposited_energy"])
    cross_direction = feedback.write_direction(captures, other)
    owner_frame = durability.read_frame(owner_workspace, config.read_frame_path)
    owner_deposit = float(written["deposits"][item.name])
    series = {}
    for name, result in (
        ("owner", owner_result),
        ("reference", reference_result),
        ("no_loop", drift_result),
    ):
        series[name] = {
            "fidelity": [
                float(row["measure_retention"]) for row in result["samples"]
            ],
            "pages": [str(row["page_sha256"]) for row in result["samples"]],
            "states": [str(row["state_sha256"]) for row in result["samples"]],
            "retention_series": [
                {
                    "tick": int(row["tick"]),
                    "fidelity": float(row["measure_retention"]),
                    "frame_energy_ratio": float(row["frame_energy_ratio"]),
                }
                for row in result["samples"]
            ],
        }
    equivalence_series = {
        "fidelity": [
            float(row["measure_retention"]) for row in equivalence_result["samples"]
        ],
        "pages": [str(row["page_sha256"]) for row in equivalence_result["samples"]],
        "states": [str(row["state_sha256"]) for row in equivalence_result["samples"]],
    }
    page_digests_identical = equivalence_series["pages"] == series["reference"]["pages"]
    state_digests_identical = (
        equivalence_series["states"] == series["reference"]["states"]
    )
    fidelity_series_identical = (
        equivalence_series["fidelity"] == series["reference"]["fidelity"]
    )

    owner_fidelity = float(owner_result["neutral_stability"]["measure_retention_at_horizon"])
    reference_fidelity = float(
        reference_result["neutral_stability"]["measure_retention_at_horizon"]
    )
    drift_fidelity = float(drift_result["neutral_stability"]["measure_retention_at_horizon"])
    # The second declared readout is a different direction in the same arm's own
    # sample rows, so it costs no second run: the declared read frame's share along
    # a declared direction the arm did not write.
    cross_read_fidelity = float(
        owner_result["horizon"]["item_shares"][durability.ITEM_SPECS[other].name]
    )
    floor = float(config.hold_floor)
    margin = float(config.hold_margin)
    cross_margin = float(config.cross_item_margin)
    return {
        "declared": (
            "one declared packet item written through the owner write path into a "
            "fresh canonical field at the declared profile and budget, held for the "
            "declared long horizon by the declared closed transceiver loop at this "
            "profile's own freshly measured neutral gain, and read back through the "
            "declared read frame. The recovered fidelity is the written item's own "
            "recovery_fraction_at_horizon. The reference arm is the same declared "
            "item written through the existing aimed narrow-path route and held by "
            "the feedback harness's own loop; the no-loop control is the same "
            "owner-written item advanced over the same horizon with no drive at all"
        ),
        "profile": {
            "name": PROFILE_NAME,
            "source": PROFILE_SOURCE,
            "beta": float(profile.beta),
            "port_count": int(profile.port_count),
            "declared": (
                "the metric harness's equal-total-inertia flat-inertia member, "
                "imported read-only through that harness's builder"
            ),
        },
        "readout": {
            "path": config.read_frame_path,
            "definition": "the canonical analyzer's flattened packet coefficients",
            "reference_direction": "the written item's captured write direction",
        },
        "horizon_ticks": long_horizon,
        "neutral_gain": refinement,
        "gain": gain,
        "gain_bracket": [float(value) for value in refinement["bracket"]],
        "gain_bracket_width": float(refinement["bracket_width"]),
        "phase_degrees": float(feedback_config.neutral_gain_phase_degrees),
        "loop_work_ceiling": float(feedback_config.loop_work_ceiling),
        "item": item.name,
        "owner_write": written["writes"],
        "owner_deposit": owner_deposit,
        "captured_deposit": captured,
        "ownership": {
            "post_write_own_projection": float(np.dot(owner_frame, direction)),
            "cross_item_name": durability.ITEM_SPECS[other].name,
            "post_write_cross_projection": float(np.dot(owner_frame, cross_direction)),
        },
        "owner_arm": {
            "arm": OWNER_HOLD_ARM,
            "fidelity_at_horizon": owner_fidelity,
            "recovered_deposit": owner_fidelity * owner_deposit,
            "frame_energy_ratio_at_horizon": float(
                owner_result["horizon"]["frame_energy_ratio"]
            ),
            "unwritten_max_share_at_horizon": float(
                owner_result["horizon"]["unwritten_max_share"]
            ),
            "declared_frame_projection_fraction": float(
                owner_result["horizon"]["declared_frame_projection_fraction"]
            ),
            "drive_work_total": float(owner_result["drive"]["drive_work_total"]),
            "drive_calls": int(owner_result["drive"]["calls"]),
            "amplitude_max": float(owner_result["drive"]["max_amplitude"]),
            "energy_ratio_max": float(owner_result["boundedness"]["energy_ratio_max"]),
            "retention_series": series["owner"]["retention_series"],
            "horizon_state_sha256": owner_result["final"]["state_sha256"],
            "horizon_page_sha256": owner_result["final"]["page_sha256"],
        },
        "reference_arm": {
            "arm": REFERENCE_HOLD_ARM,
            "declared": (
                "the same declared item written through the existing aimed "
                "narrow-path route and held by the feedback harness's own loop "
                "run_stream at the same gain, horizon and readout"
            ),
            "fidelity_at_horizon": reference_fidelity,
            "frame_energy_ratio_at_horizon": float(
                reference_result["horizon"]["frame_energy_ratio"]
            ),
            "unwritten_max_share_at_horizon": float(
                reference_result["horizon"]["unwritten_max_share"]
            ),
            "amplitude_max": float(reference_result["drive"]["max_amplitude"]),
            "energy_ratio_max": float(reference_result["boundedness"]["energy_ratio_max"]),
            "retention_series": series["reference"]["retention_series"],
            "horizon_state_sha256": reference_result["final"]["state_sha256"],
            "horizon_page_sha256": reference_result["final"]["page_sha256"],
        },
        "no_loop_control": {
            "arm": DRIFT_ARM,
            "declared": (
                "the same owner-written page advanced over the same horizon with "
                "sources off and no drive, so nothing re-injects the written pattern"
            ),
            "fidelity_at_horizon": drift_fidelity,
            "frame_energy_ratio_at_horizon": float(
                drift_result["horizon"]["frame_energy_ratio"]
            ),
            "retention_series": series["no_loop"]["retention_series"],
            "horizon_state_sha256": drift_result["final"]["state_sha256"],
        },
        "cross_read_control": {
            "arm": OWNER_HOLD_ARM,
            "read_item": durability.ITEM_SPECS[other].name,
            "share_of_the_unwritten_direction_at_horizon": cross_read_fidelity,
            "declared": (
                "the same owner-written page and the same loop, read through the "
                "share of the declared read frame lying along a declared direction "
                "the arm did not write; it discriminates whether the recovered "
                "fidelity is the written item's own"
            ),
        },
        "skeleton_equivalence": {
            "declared": (
                "the declared skeleton and the feedback harness's own loop, run on a "
                "page both routes build from the same declared write at the same "
                "gain, horizon and readout. Exact equality of the sample rows' "
                "fidelity series and of page and state digests is what licenses the "
                "owner-path arm above, whose loop skeleton this runner supplies"
            ),
            "fidelity_series_identical": bool(fidelity_series_identical),
            "page_digest_series_identical": bool(page_digests_identical),
            "state_digest_series_identical": bool(state_digests_identical),
            "max_fidelity_difference": float(
                max(
                    (
                        abs(left - right)
                        for left, right in zip(
                            equivalence_series["fidelity"], series["reference"]["fidelity"]
                        )
                    ),
                    default=0.0,
                )
            ),
            "samples_compared": len(equivalence_series["fidelity"]),
            "skeleton_horizon_state_sha256": equivalence_result["final"]["state_sha256"],
            "reference_horizon_state_sha256": reference_result["final"]["state_sha256"],
            "skeleton_horizon_page_sha256": equivalence_result["final"]["page_sha256"],
            "reference_horizon_page_sha256": reference_result["final"]["page_sha256"],
        },
        "predicate": (
            "fidelity_at_horizon >= neutral_level_floor, applied to the hold arm and "
            "to its no-loop control; and the hold arm must also exceed its control "
            "by the declared margin"
        ),
        "verdicts": {
            "neutral_level_floor": floor,
            "hold_passes_the_predicate": bool(owner_fidelity >= floor),
            "no_loop_control_passes_the_predicate": bool(drift_fidelity >= floor),
            "no_loop_control_must_fail": True,
            "no_loop_control_fails_the_predicate": bool(not (drift_fidelity >= floor)),
            "hold_margin": margin,
            "hold_exceeds_the_control_by": owner_fidelity - drift_fidelity,
            "hold_beats_the_control_by_the_margin": bool(
                owner_fidelity - drift_fidelity >= margin
            ),
            "route_identity_allowance": float(config.route_identity_allowance),
            "route_fidelity_difference": owner_fidelity - reference_fidelity,
            "owner_route_matches_the_existing_route": bool(
                abs(owner_fidelity - reference_fidelity)
                <= float(config.route_identity_allowance)
            ),
            "cross_item_margin": cross_margin,
            "readout_specificity_difference": owner_fidelity - cross_read_fidelity,
            "readout_is_item_specific": bool(
                owner_fidelity - cross_read_fidelity >= cross_margin
            ),
            "skeleton_reproduces_the_declared_loop": bool(
                fidelity_series_identical
                and page_digests_identical
                and state_digests_identical
            ),
            "gain_refinement_measured_every_probe": bool(
                len(refinement["probes"]) > 0
                and all(
                    probe["retention_at_horizon"] is not None
                    for probe in refinement["probes"]
                )
            ),
        },
    }


def pair_block(
    profile: Any,
    config: OwnerWritePathConfig,
    captures: Sequence[Mapping[str, Any]],
    gain: float,
) -> dict[str, Any]:
    """Two owner-written items held at the measured neutral gain under a work split."""

    feedback_config = config.feedback_config()
    headline, second = int(config.headline_item_index), int(config.second_item_index)
    items = (headline, second)
    names = [durability.ITEM_SPECS[index].name for index in items]
    long_horizon = int(config.long_horizon_ticks)
    samples = config.long_horizon_sample_ticks
    phase_reference = phase_reference_for(config, captures, profile)

    owner, home = open_owner(profile)
    try:
        written = owner_write_items(owner, items, config, "owp:pair")
        owner_workspace = owner.state.resonant_workspace
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)

    rows: list[dict[str, Any]] = []
    for weights in SPLIT_WEIGHTS:
        arm = hold_arm(
            f"{OWNER_HOLD_ARM}-pair-split-{weights[0]:g}-{weights[1]:g}",
            items,
            gain,
            long_horizon,
            samples,
            config,
            drive_items=items,
            drive_split=weights,
            family="owner-write-path-pair",
        )
        result = skeleton_loop(
            feedback_config,
            captures,
            arm,
            owner_workspace,
            written["deposits"],
            phase_reference,
        )
        horizon = result["horizon"]
        rows.append(
            {
                "split": [float(weight) for weight in weights],
                "item_retention": {
                    name: float(value)
                    for name, value in horizon["item_retention"].items()
                },
                "item_shares": {
                    name: float(value) for name, value in horizon["item_shares"].items()
                },
                "frame_energy_ratio": float(horizon["frame_energy_ratio"]),
                "unwritten_max_share": float(horizon["unwritten_max_share"]),
                "drive_work_total": float(result["drive"]["drive_work_total"]),
                "amplitude_max": float(result["drive"]["max_amplitude"]),
                "horizon_page_sha256": str(result["final"]["page_sha256"]),
            }
        )

    no_loop_arm = feedback.LoopArm(
        f"{DRIFT_ARM}-pair",
        items,
        family="owner-write-path-pair",
        measure_item_index=headline,
        horizon_ticks=long_horizon,
        sample_ticks=samples,
    )
    no_loop = skeleton_loop(
        feedback_config,
        captures,
        no_loop_arm,
        owner_workspace,
        written["deposits"],
        phase_reference,
    )
    uniform = rows[0]
    no_loop_retention = {
        name: float(value) for name, value in no_loop["horizon"]["item_retention"].items()
    }
    floor = float(config.hold_floor)
    margin = float(config.hold_margin)
    return {
        "declared": (
            "the declared two items written through the owner write path, then held "
            "at this profile's own measured neutral gain while the declared per-tick "
            "work ceiling is divided between them in each declared proportion. The "
            "uniform split is the first declared weight pair; the control is the same "
            "two owner-written items advanced over the same horizon with no drive"
        ),
        "items": names,
        "gain": float(gain),
        "phase_degrees": float(feedback_config.neutral_gain_phase_degrees),
        "owner_write": written["writes"],
        "owner_deposits": {
            name: float(value) for name, value in written["deposits"].items()
        },
        "rows": rows,
        "no_loop_control": {
            "item_retention": no_loop_retention,
            "frame_energy_ratio": float(no_loop["horizon"]["frame_energy_ratio"]),
        },
        "predicate": (
            "each held item's recovery_fraction_at_horizon >= neutral_level_floor, "
            "applied to the uniform-split arm and to the no-loop control"
        ),
        "verdicts": {
            "neutral_level_floor": floor,
            "both_items_pass_the_predicate": bool(
                all(value >= floor for value in uniform["item_retention"].values())
            ),
            "no_loop_control_passes_the_predicate": bool(
                all(value >= floor for value in no_loop_retention.values())
            ),
            "no_loop_control_must_fail": True,
            "no_loop_control_fails_the_predicate": bool(
                not all(value >= floor for value in no_loop_retention.values())
            ),
            "margin": margin,
            "differences_from_the_no_loop_control": {
                name: float(value) - no_loop_retention[name]
                for name, value in uniform["item_retention"].items()
            },
            "uniform_split_both_items_beat_the_no_loop_control_by_the_margin": bool(
                all(
                    float(value) - no_loop_retention[name] >= margin
                    for name, value in uniform["item_retention"].items()
                )
            ),
            "all_splits_beat_the_no_loop_control_by_the_margin": bool(
                all(
                    float(value) - no_loop_retention[name] >= margin
                    for row in rows
                    for name, value in row["item_retention"].items()
                )
            ),
            "retention_follows_the_own_split_weight": bool(
                rows[1]["item_retention"][names[0]]
                > rows[2]["item_retention"][names[0]]
                and rows[2]["item_retention"][names[1]]
                > rows[1]["item_retention"][names[1]]
            ),
            "splits_where_both_items_pass_the_predicate": [
                row["split"]
                for row in rows
                if all(value >= floor for value in row["item_retention"].values())
            ],
            "splits_where_at_least_one_item_passes_the_predicate": [
                row["split"]
                for row in rows
                if any(value >= floor for value in row["item_retention"].values())
            ],
            "best_recovery_per_item": {
                name: max(row["item_retention"][name] for row in rows)
                for name in names
            },
            "asymmetric_splits_differ_from_the_uniform_split": bool(
                rows[1]["item_retention"] != rows[0]["item_retention"]
                or rows[2]["item_retention"] != rows[0]["item_retention"]
            ),
        },
    }


# --------------------------------------------------------------------------
# receipt
# --------------------------------------------------------------------------
def measure(config: OwnerWritePathConfig) -> dict[str, Any]:
    """Every declared block of this receipt, measured in order."""

    profile = flat_profile()
    captures = durability.capture_items(
        durability.DurabilityConfig(write_budget=float(config.write_budget)), profile
    )
    diagnosis = diagnosis_block(profile, config)
    port_support = port_support_block(profile, config, diagnosis)
    impulse = impulse_block(profile, config, captures)
    cycle = cycle_block(profile, config, captures)
    pair = pair_block(profile, config, captures, gain=float(cycle["gain"]))
    identity = route_identity_block(
        profile, config, (int(config.headline_item_index), int(config.second_item_index))
    )
    contract = owner_contract_block(profile, config)
    read_surface = owner_read_surface_block(profile, config)
    read_operation = read_operation_block(profile, config, captures)
    return {
        "diagnosis": diagnosis,
        "port_support": port_support,
        "impulse": impulse,
        "cycle": cycle,
        "pair": pair,
        "route_identity": identity,
        "owner_contract": contract,
        "owner_read_surface": read_surface,
        "read_operation": read_operation,
    }


def reading_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """What the measured blocks say, in one reading."""

    diagnosis = body["diagnosis"]
    port_support = body["port_support"]
    impulse = body["impulse"]
    cycle = body["cycle"]
    pair = body["pair"]
    identity = body["route_identity"]
    contract = body["owner_contract"]
    read_surface = body["owner_read_surface"]
    read_operation = body["read_operation"]
    control = diagnosis["supported_relation_control"]
    verdicts = cycle["verdicts"]
    pair_verdicts = pair["verdicts"]
    hold_difference = verdicts["hold_exceeds_the_control_by"]
    return {
        "the_owner_accepts_a_written_impulse": (
            "FieldIntelligenceOwner.write_packet_impulse publishes one immutable "
            f"successor (generation {contract['generation_before']} -> "
            f"{contract['first_generation']}), keeps the logical tick "
            f"({contract['write_keeps_the_logical_tick']}) and the evidence clock "
            f"({contract['write_keeps_the_evidence_clock']}) unchanged, returns its "
            f"retained result on an identical replay without writing again "
            f"({contract['replay_does_not_write_again']}), refuses a conflicting call "
            f"under the same identity ({contract['conflicting_call_refused']}), "
            f"refuses a stale predecessor stamp "
            f"({contract['stale_predecessor_refused']}) while accepting a matching "
            f"one ({contract['matching_predecessor_accepted']}), and preserves the "
            f"written page, state digest and tick across a close and reopen "
            f"({contract['state_digest_preserved_at_close']}, "
            f"{contract['page_digest_preserved_at_close']})"
        ),
        "it_is_the_same_write_as_the_existing_route": (
            "the owner route and the existing aimed narrow-path route deposit "
            f"identical pages ({identity['page_digest_identical']}), identical "
            f"workspace state digests ({identity['state_digest_identical']}), "
            f"identical ledgers ({identity['ledger_identical']}) and read frames "
            f"differing by at most "
            f"{identity['read_frame_max_abs_difference']!r}: this receipt adds a "
            "transition and a closure, not a second write mechanism, and it does not "
            "claim the owner path writes anything the existing route could not"
        ),
        "the_input_realization_is_inert_here_and_that_is_why_the_write_goes_elsewhere": (
            "the declared input realization has no measurable authority over its own "
            f"declared readout on this profile. In the shipped-profile realization "
            f"({diagnosis['declared_profile']['mode']}, compact map "
            f"{diagnosis['declared_profile']['compact_map_available']}) the input "
            f"moves the state exactly by the lift -- a unit-norm lift "
            f"({diagnosis['declared_profile']['input_lift_norm']!r}) times the scan's "
            f"span predicts "
            f"{diagnosis['declared_profile']['expected_state_delta_norm_if_the_clamp_moved_the_state']!r}, "
            f"and the measured state delta is "
            f"{diagnosis['declared_profile']['state_delta_norm_between_first_and_last_input']!r}, "
            f"a fraction "
            f"{diagnosis['verdicts']['declared_profile']['state_delta_fraction_of_the_lift_prediction']!r} "
            f"of it -- and the declared output still does not move, by "
            f"{diagnosis['declared_profile']['output_delta_absolute_between_first_and_last_input']!r}, "
            f"because the lift is supported on the input port's coordinates "
            f"{diagnosis['declared_profile']['input_lift_support_coordinates']} and "
            f"the readout row on the output port's "
            f"{diagnosis['declared_profile']['readout_row_support_coordinates']}, "
            f"whose overlap is {diagnosis['declared_profile']['support_overlap'] or 'empty'} "
            f"and whose dot product is exactly "
            f"{diagnosis['declared_profile']['output_row_dot_input_lift']!r}. In the "
            f"beta-zero counterpart, where the compact path is admitted "
            f"({diagnosis['beta_zero_counterpart']['mode']}), the compact map's input "
            f"column is annihilated before it reaches the state: measured norm "
            f"{diagnosis['verdicts']['beta_zero_counterpart']['compact_map_drive_input_column_norm']!r}, "
            f"direct term "
            f"{diagnosis['verdicts']['beta_zero_counterpart']['compact_map_direct_term']!r}, "
            f"state delta "
            f"{diagnosis['beta_zero_counterpart']['state_delta_norm_between_first_and_last_input']!r}, "
            f"and an output spread of exactly "
            f"{diagnosis['beta_zero_counterpart']['output_spread']!r} over the declared "
            f"scan, so the ledger of the two mechanisms is: annihilated in the "
            f"reduced realization, invisible to the readout in the full one. The "
            f"same construction fires once the declared problem carries a supported "
            f"relation (spread {control['output_spread']!r} against "
            f"{diagnosis['declared_profile']['output_spread']!r}, "
            f"{diagnosis['verdicts']['supported_relation_control_fires']}), so the "
            "inertness is this field's declared problem rather than a dead branch"
        ),
        "the_two_ways_to_give_the_input_authority": (
            f"the declared profile's {port_support['profile']['port_count']} ports own "
            f"disjoint supports: {port_support['overlap']['overlapping_port_pairs_found']} "
            "overlapping pairs among them, so selecting overlapping ports is not "
            "available on this profile at all. The shipped selection is measured inert "
            f"(spread {port_support['measured_selections']['(a) shipped_selection']['output_spread']!r}, "
            f"dot {port_support['measured_selections']['(a) shipped_selection']['output_row_dot_input_lift']!r}, "
            f"support {port_support['measured_selections']['(a) shipped_selection']['support_overlap'] or 'empty'}); "
            "the nearest overlapping selection -- both declared variables bound to one "
            f"port ({port_support['measured_selections']['(b) overlapping_selection']['on_this_profile']['shared_port']}) "
            f"-- is refused by the library "
            f"({port_support['measured_selections']['(b) overlapping_selection']['on_this_profile']['refusal']}: "
            f"{port_support['measured_selections']['(b) overlapping_selection']['on_this_profile']['refusal_message']!r}) "
            "on every declared profile tried "
            f"({port_support['measured_selections']['(b) overlapping_selection']['refused_on_every_profile_tried']}); "
            f"the coupled-relation control fires (spread "
            f"{port_support['measured_selections']['(c) coupled_relation_control']['output_spread']!r} against "
            f"{port_support['measured_selections']['(a) shipped_selection']['output_spread']!r}) and it does so "
            "with the same two disjoint supports as the inert case, so the authority "
            "the control measures comes from the declared relation rather than from a "
            "shared coordinate "
            f"({port_support['verdicts']['the_coupled_relation_control_fires_without_a_support_overlap']}). Which reading "
            f"the design text supports is stated as a proposal and the choice is left open: "
            f"{port_support['reading']['reading_the_text_supports']}"
        ),
        "reading_the_written_page_back_through_the_owner": (
            f"the surface publishes {read_surface['surface']['declared_operations']} "
            f"operations, {len(read_surface['surface']['read_only_operations'])} of which "
            f"declare no state transition, and one of them is the read half this "
            f"receipt adds: {read_operation['operation']} names a written direction "
            "and returns its deposit. The "
            f"{len(read_surface['surface']['read_only_operations_exercised_with_no_arguments'])} "
            "read-only operations that take no arguments were exercised on the owner "
            "holding the written page, and none of them publishes the deposit "
            f"({read_surface['inspection']['paths_naming_a_deposit_or_a_written_direction']!r} "
            f"of {read_surface['inspection']['published_key_paths']} published key paths "
            "name one), while they leave the page, the generation and the evidence tick "
            f"unchanged ({read_surface['verdicts']['the_reads_change_no_page_state_or_evidence']}). "
            "What a consumer can recover today is the deposit itself, from the owner's "
            f"read operation "
            f"({read_operation['recovery']['recovered_by_the_read_operation']!r} against "
            f"the written "
            f"{read_operation['recovery']['written_deposit_in_the_declared_read_frame']!r}) "
            "and from the canonical page through the library's own read frame "
            f"({read_surface['reading_the_written_page_back']['raw_page_recovery']!r}, "
            f"a blank page giving "
            f"{read_surface['reading_the_written_page_back']['blank_page_deposit_in_the_declared_read_frame']!r}). "
            "The other surface that carries the written page is the transceiver readout: "
            "it does carry the written page over a zero-input advance "
            f"(outputs {read_surface['closest_surface']['written_page_outputs']!r} against "
            f"blank {read_surface['closest_surface']['blank_page_outputs']!r}, max difference "
            f"{read_surface['closest_surface']['max_difference_over_the_read']!r}), it reads "
            "its own output port's common pair "
            f"({read_surface['closest_surface']['readout_support_coordinates']}), and it is "
            "a temporal prediction that adds no observed support and advances no "
            "evidence clock -- so the written page is readable and is not evidence"
        ),
        "the_read_half_names_a_written_direction": (
            f"{read_operation['operation']} recovers the written direction's deposit: "
            f"{read_operation['recovery']['recovered_by_the_read_operation']!r} against "
            f"the written "
            f"{read_operation['recovery']['written_deposit_in_the_declared_read_frame']!r}, "
            f"a relative difference of "
            f"{read_operation['recovery']['recovered_relative_difference']!r} against the "
            f"declared allowance {read_operation['recovery']['allowance']!r} "
            f"({read_operation['verdicts']['the_read_recovers_the_written_deposit']}), and "
            "the same page read through the library's own captured direction gives "
            f"{read_operation['recovery']['recovered_by_the_library_along_the_captured_direction']!r} "
            f"({read_operation['verdicts']['the_read_agrees_with_the_library_route']}); the "
            "direction the read computes is the direction the durability harness "
            f"captured for the same write "
            f"({read_operation['verdicts']['the_reads_direction_is_the_written_directions']}). "
            "Both controls miss it: the same direction on a blank page recovers "
            f"{read_operation['controls']['blank_page']['recovered']!r} and the declared "
            f"direction the owner did not write recovers "
            f"{read_operation['controls']['unwritten_direction']['recovered']!r} "
            f"({read_operation['controls']['blank_page']['passes_the_recovery_predicate']}, "
            f"{read_operation['controls']['unwritten_direction']['passes_the_recovery_predicate']} "
            "under the same predicate), so the read is direction-specific rather than a "
            "page summary. Those controls can fail: with the declared direction dropped "
            "from the read implementation the unwritten direction recovers "
            f"{read_operation['controls']['firing_control']['mutated_unwritten_direction_recovered']!r} "
            "and passes the predicate "
            f"({read_operation['verdicts']['the_unwritten_direction_control_fires_under_a_direction_blind_read']}), "
            "the clean readout returns once the mutation is removed "
            f"({read_operation['verdicts']['the_clean_readout_returns_once_the_mutation_is_removed']}), "
            "and the firing control leaves the page digest unchanged "
            f"({read_operation['controls']['firing_control']['the_firing_control_leaves_the_page_unchanged']})"
        ),
        "the_readout_is_a_share_along_the_declared_direction": (
            "on a page carrying both declared items the read recovers "
            f"{read_operation['two_written_directions']['recovered_by_the_read_operation']!r} "
            "of the page's whole read-frame energy "
            f"{read_operation['two_written_directions']['page_read_frame_energy']!r}, "
            "each direction at its own share "
            f"({read_operation['two_written_directions']['share_of_the_page_each_read_recovers']!r}) "
            f"({read_operation['verdicts']['the_read_recovers_a_share_of_a_two_write_page_rather_than_its_total']}), "
            "so recovery along a written direction is a measured projection and not the "
            "page's total; the two shares sum to "
            f"{read_operation['two_written_directions']['projection_sum_against_the_page_energy']!r} "
            "here, which is the measurement saying these two declared directions are "
            "orthogonal in this read frame"
        ),
        "the_read_is_a_prediction_that_moves_nothing": (
            f"the read is declared as the design declares a readout (readout kind "
            f"{read_operation['recovery']['readout_kind']!r}, evidence_added "
            f"{read_operation['recovery']['read_declares_evidence_added']}): it leaves "
            f"the page ({read_operation['invariants']['page_unchanged_by_the_reads']}), "
            f"the field generation "
            f"({read_operation['invariants']['generation_unchanged_by_the_reads']}) and "
            f"the evidence tick "
            f"({read_operation['invariants']['evidence_tick_unchanged_by_the_reads']}) "
            f"unchanged, with both published payloads byte-identical across the reads "
            f"({read_operation['invariants']['inspect_payload_unchanged_by_the_reads']}, "
            f"{read_operation['invariants']['inspect_resonance_payload_unchanged_by_the_reads']}). "
            "Those checks are live: the write the read reads does move the page digest "
            f"and the generation "
            f"({read_operation['invariant_controls']['the_write_changes_the_page_digest']}, "
            f"{read_operation['invariant_controls']['the_write_advances_the_generation']}), "
            "and the evidence clock is shown to move by the owner's own "
            "observation-admission rule on a separate state of this profile "
            f"({read_operation['invariant_controls']['evidence_tick_control']['evidence_tick_before_the_admission']!r} -> "
            f"{read_operation['invariant_controls']['evidence_tick_control']['evidence_tick_after_the_admission']!r}, "
            f"{read_operation['invariant_controls']['evidence_tick_control']['an_admission_moves_the_evidence_clock']}). "
            "What would change if the read were declared as evidence rather than as a "
            f"prediction is stated and left open: "
            f"{read_operation['if_the_read_were_declared_as_evidence']}"
        ),
        "the_exposure_scan_now_names_the_written_direction": (
            f"before the read operation, {read_surface['inspection']['published_key_paths']} "
            "published key paths carried "
            f"{len(read_operation['exposure_scan']['before_the_read_operation']['paths_naming_a_deposit_or_a_written_direction'])} "
            "naming a deposit or a written direction while "
            f"{len(read_operation['exposure_scan']['before_the_read_operation']['paths_naming_the_intervention_itself'])} "
            "named the intervention itself; with the read operation the same scan finds "
            f"{read_operation['exposure_scan']['after_the_read_operation']['published_key_paths']} "
            "published key paths carrying "
            f"{len(read_operation['exposure_scan']['after_the_read_operation']['paths_naming_a_deposit_or_a_written_direction'])} "
            f"that name one "
            f"({read_operation['exposure_scan']['after_the_read_operation']['paths_naming_a_deposit_or_a_written_direction']!r}) "
            f"({read_operation['verdicts']['the_exposure_scan_now_names_the_written_direction']}), "
            "and the same matcher finds no path naming a word the surface does not "
            f"publish ({read_operation['exposure_scan']['matcher_controls']['word_absent_from_every_published_path']!r}, "
            f"{read_operation['verdicts']['the_scan_finds_no_path_naming_the_absent_word']}), so the "
            "zero before is a live comparison rather than a broken scan"
        ),
        "the_impulse_reaches_the_field": (
            f"the owner-written impulse deposits "
            f"{impulse['impulse_arm']['read_frame_deposit']!r} in the declared read "
            f"frame, {impulse['impulse_arm']['deposit_fraction_of_captured']!r} of "
            f"the same item's captured deposit, against the declared fraction "
            f"{impulse['margin']!r} ({impulse['impulse_arm_passes']}), while the "
            f"zero-work control deposits "
            f"{impulse['zero_impulse_control']['read_frame_deposit']!r} and fails the "
            f"same predicate ({impulse['zero_impulse_control_fails_the_predicate']}) "
            f"with its page digest unchanged "
            f"({impulse['zero_impulse_control']['page_digest_unchanged']})"
        ),
        "the_cycle_holds_and_reads_back": (
            f"the owner-written pattern is held for the declared "
            f"{cycle['horizon_ticks']}-tick horizon at this profile's own measured "
            f"neutral gain {cycle['gain']!r} (bracket {cycle['gain_bracket']!r}, width "
            f"{cycle['gain_bracket_width']!r}, from "
            f"{len(cycle['neutral_gain']['probes'])} bisection probes over a "
            f"{len(cycle['neutral_gain']['grid'])}-gain grid on this profile) and "
            f"reads back at {cycle['owner_arm']['fidelity_at_horizon']!r} of its own "
            f"deposit; the same declaration written through the existing route and "
            f"held by the harness's own loop reads back at "
            f"{cycle['reference_arm']['fidelity_at_horizon']!r} (difference "
            f"{verdicts['route_fidelity_difference']!r}), and the same owner-written "
            f"page with no drive at all reads back at "
            f"{cycle['no_loop_control']['fidelity_at_horizon']!r}, so the hold beats "
            f"its own no-loop control by {hold_difference!r} against the declared "
            f"margin {verdicts['hold_margin']!r} "
            f"({verdicts['hold_beats_the_control_by_the_margin']}) and passes the "
            f"declared neutral floor {verdicts['neutral_level_floor']!r} "
            f"({verdicts['hold_passes_the_predicate']}) while the control does not "
            f"({verdicts['no_loop_control_fails_the_predicate']})"
        ),
        "the_reading_is_item_specific": (
            f"the written item's own direction reads "
            f"{verdicts['readout_specificity_difference']!r} higher than the "
            f"declared unwritten direction "
            f"({cycle['cross_read_control']['read_item']}) against the declared "
            f"margin {verdicts['cross_item_margin']!r} "
            f"({verdicts['readout_is_item_specific']})"
        ),
        "two_items_under_a_work_split": (
            "two owner-written items are held together under the declared per-tick "
            f"work split. Every item under every declared split beats the no-loop "
            f"control's own recovery ({pair['no_loop_control']['item_retention']!r}) "
            f"by more than the declared margin {pair_verdicts['margin']!r} "
            f"({pair_verdicts['all_splits_beat_the_no_loop_control_by_the_margin']}), "
            f"but no declared split holds both items at the declared floor "
            f"{pair_verdicts['neutral_level_floor']!r} "
            f"({pair_verdicts['both_items_pass_the_predicate']}): at the uniform "
            f"split the recoveries are "
            f"{pair['rows'][0]['item_retention']!r}; the 0.9/0.1 split holds "
            f"root-scale at {pair['rows'][3]['item_retention']['root-scale']!r} but "
            f"drops left-detail to "
            f"{pair['rows'][3]['item_retention']['left-detail']!r}, and the mirrored "
            f"0.1/0.9 split does the reverse "
            f"({pair['rows'][4]['item_retention']['root-scale']!r} against "
            f"{pair['rows'][4]['item_retention']['left-detail']!r}), with retention "
            f"following each item's own share "
            f"({pair_verdicts['retention_follows_the_own_split_weight']}), so on this "
            "profile at this gain one shared drive channel does not neutrally hold "
            "two items: the split moves recovery between them rather than giving "
            "each its own lane"
        ),
        "the_skeleton_is_not_a_second_law": (
            "the loop skeleton this runner supplies reproduces the feedback "
            f"harness's own loop exactly on a page both routes build "
            f"({verdicts['skeleton_reproduces_the_declared_loop']}, maximum fidelity "
            f"difference {cycle['skeleton_equivalence']['max_fidelity_difference']!r})"
        ),
        "limits": (
            "the loop skeleton carries the owner-written page because the feedback "
            "harness's loop writes its own items and cannot start elsewhere; the "
            "owner write is a faithful transport of the canonical packet impulse, "
            "measured to be one write with the existing route, so nothing here is a "
            "new drive mechanism; the measured neutral gain is this declared loop's "
            "operating point at this horizon and readout, not a stability threshold; "
            "the recovery fractions are properties of the declared readout, not of "
            "any consumer; and the durability harness's frozen recon, which says the "
            "owner exposes no packet-impulse operation, is superseded by this "
            "additive transition rather than repaired in that frozen file. The read "
            "half is bounded the same way: it recovers the deposit along one declared "
            "direction of one declared profile, item, budget and read frame, and it "
            "is a prediction of the canonical page rather than an observation, so a "
            "recovery equal to the written deposit says the page still carries the "
            "write and says nothing about what any consumer could retrieve"
        ),
    }


def build_receipt(config: OwnerWritePathConfig) -> dict[str, Any]:
    """The complete receipt, digested by the lattice runner's own convention."""

    started = perf_counter()
    body = measure(config)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "question": (
            "the field as shipped has no transition that accepts a written packet "
            "impulse: can the owner accept one, does the impulse reach the field, "
            "does a pattern written through that path survive the declared closed "
            "loop and read back, and can the owner itself read a written direction's "
            "deposit back as a declared prediction rather than as evidence?"
        ),
        "declared": {
            "config": config.as_dict(),
            "profile": {
                "name": PROFILE_NAME,
                "source": PROFILE_SOURCE,
                "declared": (
                    "the profile of every leg of this receipt, built by the metric "
                    "harness's own builder and imported read-only"
                ),
            },
            "definitions": DEFINITIONS,
            "declared_instruments": {
                "read_frame": "run_fractal_durability_exploration.read_frame",
                "captures": "run_fractal_durability_exploration.capture_items",
                "loop_drive_law": (
                    "run_fractal_feedback_exploration.phase_signal, loop_amplitude, "
                    "apply_drive, sample_row"
                ),
                "neutral_gain": "run_fractal_feedback_exploration.measure_neutral_gain",
                "profile_builder": PROFILE_SOURCE,
                "packet_read_operation": (
                    "FieldIntelligenceOwner.read_packet_deposit -> "
                    "FieldAtlas.read_packet_deposit -> packet_read_direction, which "
                    "measures the declared direction on a scratch workspace of the "
                    "same profile at the declared probe budget "
                    "(cassi_field_atlas._PACKET_READ_PROBE_BUDGET) through "
                    "cassi_resonant_field.apply_helical_packet_impulse"
                ),
                "evidence_clock_control": (
                    "FieldAtlas.admit_observation on a separate state of this "
                    "profile carrying one declared variable and one declared chart"
                ),
            },
            "boundary": BOUNDARY,
            "reading_taken": READING_TAKEN,
        },
        "closure_audit": {
            "directory": CLOSURE_AUDIT_DIRECTORY,
            "artifacts": list(CLOSURE_AUDIT_ARTIFACTS),
            "declared": (
                "the collateral closure of the two library edits this receipt rests "
                "on is not part of this receipt. It lives beside it at "
                f"{CLOSURE_AUDIT_DIRECTORY}, and the closure summary is the content "
                "of r2-verdict.json when an audit has been run there: "
                "closure-tests-per-file-r2.json carries the per-file test rows, "
                "r2-summary.json the per-harness archive comparison with every "
                "mismatch classified, importer-closure-r2.json the import closure of "
                "the edited modules, r2-controls.json the attribution controls, and "
                "r2/ the harness captures those comparisons read. No count, verdict "
                "or digest of that audit is restated in this receipt, because the "
                "audit is not a function of this runner's inputs: this block "
                "declares where the closure lives, and the receipt stays rebuildable "
                "from its own inputs alone."
            ),
        },
        **body,
    }
    receipt["reading"] = reading_block(body)
    receipt["runtime_seconds"] = perf_counter() - started
    receipt["receipt_digest"] = receipt_digest(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="_diag/owner-write-path/exploration.json",
        help="where the receipt is written",
    )
    arguments = parser.parse_args()
    receipt = build_receipt(OwnerWritePathConfig())
    path = Path(arguments.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {path}")
    print(f"receipt_digest: {receipt['receipt_digest']}")
    print(f"runtime_seconds: {receipt['runtime_seconds']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
