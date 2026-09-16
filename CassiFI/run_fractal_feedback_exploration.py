"""Measure whether closing the field's read-back onto its own drive holds a written pattern.

The durability harness measured that a written packet item loses its direction
faster than the frame loses energy, with the source state changing the read-tick
recovery by only about 0.014-0.017, and that the loss is non-monotone (the
direction partly returns after almost vanishing). This runner asks the next
question directly: if the field's own read-back is driven back into the field
each tick, does a decaying pattern become a maintained one, and at what gain,
work cost, disturbance and item count?

Recon, recorded in the receipt's ``recon`` block:

* ``cassi_resonant_field``'s canonical advance has no per-tick drive argument.
  A genuine closed loop on the **full canonical page** is nevertheless
  expressible with existing canonical operations: one ``advance_workspace`` tick
  at a time, each followed by one ``apply_helical_packet_impulse`` whose flow
  signal is the sign of the read-back projection and whose work budget is
  bounded. Every arm below loops that page; no canonical operation is added.
* ``cassi_field_transceiver`` condenses a *bound* workspace into a temporal
  realization and advances that realization: its own reduced Krylov coordinates
  when compact admission holds, or its own full AVF realization otherwise. The
  canonical page is read once at condensation and never advanced or written by
  ``advance_transceiver``, so a transceiver loop is a loop on the condensed
  coordinates, not on the page. The transceiver recon block records the
  measured contract (per-call input envelope, per-tick state carry, the
  declared one-tick-delay connection surface at the owner level) and states
  what a full-field loop through the transceiver would require. Measured, that
  contract is not a loop: the per-tick input is applied to every tick of a call
  and the state carries across calls, but the input has no measurable authority
  over the output at this declared problem (relative spread 7.5e-16 under the
  durability profile, exactly zero under the beta=0 counterpart, over both one
  tick and a whole run), so this runner's loop is on the page rather than
  through the condensed kernel.

Every number comes from the canonical packet, workspace and impulse APIs. These
are canonical-field numerical measurements in controlled conditions under one
declared profile, one declared written item, one declared horizon, and the
declared source state of the durability harness's source-off arm. They do not
establish task-level memory utility, semantic content, retrieval by a consumer,
owner-level checkpoint identity, or any advantage over alternative
architectures. Negative results are deliverables: if the loop does not maintain
the pattern, the receipt reports the measured decay.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import math

import numpy as np

import run_fractal_durability_exploration as durability
from cassi_field_transceiver import advance_transceiver, condense_workspace, reset_transceiver
from cassi_resonant_field import (
    analyze_helical_packet,
    ResonantNumericalError,
    ResonantProblem,
    ResonantProfile,
    advance_workspace,
    apply_helical_packet_impulse,
    bind_workspace,
    initial_workspace,
)

SCHEMA = "cassifi.fractal-feedback-exploration.v1"
EVENT_KIND = durability.EVENT_KIND

# The durability receipt this runner continues. The source-off retention figures
# and the two energy-retention figures below are cited from it; the drift arm of
# this receipt is compared against them instead of re-measuring that harness.
CITED_RECEIPT = "_diag/fractal-durability/exploration.json"
CITED_SOURCE_OFF_RETENTION: dict[int, float] = {
    8: 0.7967617761274481,
    16: 0.36884561619700146,
    32: 0.030975071077481122,
    64: 0.31149818467501866,
}
CITED_SOURCE_OFF_ENERGY_RETENTION_AT_HORIZON = 0.7720435496915942
CITED_SOURCE_ON_RETENTION_AT_HORIZON = 0.29462880739045766
CITED_SOURCE_ON_ENERGY_RETENTION_AT_HORIZON = 0.9834193298916879
# The drift arm of this receipt must reproduce the cited figures exactly: it
# advances the same page under the same declared sources-off activity, one tick
# per call, and the receipt's ``stream_identity`` block measures that the
# one-tick stream and the durability harness's chunked stream agree bit for bit.
CITED_AGREEMENT_ALLOWANCE = 0.0

# The declared per-tick decay of the written mode: one minus the 8th root of the
# cited source-off retention at the first declared sample. It is the reference
# the loop gain multiplies, so a gain of one attempts to replace one tick's
# measured decay of the written mode's amplitude.
DECAY_REFERENCE_TICKS = 8
DECAY_REFERENCE_RETENTION = CITED_SOURCE_OFF_RETENTION[DECAY_REFERENCE_TICKS]
PER_TICK_DECAY = 1.0 - DECAY_REFERENCE_RETENTION ** (1.0 / DECAY_REFERENCE_TICKS)

# The lanes and lanes-rows the declared frame channels live on, and the
# tolerance under which a lane-row is called empty.
POSITION_LANE = "position-common"
MOMENTUM_LANE = "momentum-common"
DIRECTION_ROW_TOLERANCE = 1e-12

# The intrinsic lifetimes this receipt cites (it does not re-measure them): the
# first sampled tick at which the written item's alignment retention crosses
# below one twentieth of its post-write alignment, in the canonical helix7
# profile of the ladder harness. These are the ladder receipt's own figures,
# which this receipt cites rather than re-measuring. The two declared ladder
# items sit on different declared rung paths and therefore different widths.
CITED_LADDER_RECEIPT = "_diag/fractal-ladder/exploration.json"
CITED_LADDER_THRESHOLD_LABEL = "one twentieth of the post-write alignment (1/20)"
CITED_LADDER_SAMPLE_EVERY_TICKS = 16
CITED_LADDER_PROFILE = "helix7"
CITED_INTRINSIC_LIFETIME_TICKS = {
    # The ladder receipt's own figures for the declared helix7 profile, by the
    # declared item's index in the declared item list (root-scale 0, LL 4).
    "root-scale": 32.0,
    "left-left-detail": 64.0,
}
CITED_ITEM_WIDTHS = {"root-scale": 28, "left-left-detail": 7, "left-detail": 14}
CITED_LADDER_LIFETIME_MIN_TICKS = max(CITED_INTRINSIC_LIFETIME_TICKS.values())
# The ladder receipt's own grouped lifetime of the width-7 rung (the mean of its
# four width-7 items' lifetimes). This is a rung aggregate, not the second
# declared item's own lifetime, and is reported as such beside it.
CITED_WIDTH7_RUNG_MEAN_LIFETIME_TICKS = 76.0
CITED_WIDTH7_RUNG_WIDTH = 7

BOUNDARY = (
    "Canonical-field numerical measurements in controlled conditions only: one "
    "declared written packet item (and a two-item counterpart), the declared "
    "source-off activity of the durability harness, and a closed loop that "
    "advances the full canonical page one tick per call and applies one bounded "
    "canonical packet impulse per tick whose flow signal is the sign of the "
    "declared read-back projection. The loop is on the full page with the "
    "canonical read frame as its read-back; no reduced realization is looped and "
    "no canonical operation is added. A maintained pattern under the saturating "
    "loop is accompanied by the measured frame-energy amplification and by a "
    "measured disturbance of the unwritten declared directions above the "
    "baseline; the receipt reports both. Maintenance under the declared phase "
    "grid is the same trade at every phase that maintains: the retained "
    "alignment rises with the frame energy ratio, and the arms whose unwritten "
    "disturbance is reported as zero are re-concentrating the declared frame on "
    "the written direction rather than preserving an independent pattern; under "
    "the declared phase grid the arms that maintain are the negatively phased "
    "ones, whose frame energy ratio tracks the retained alignment to within a "
    "per-cent, with the declared-frame projection fraction and the unwritten "
    "share both reported. The ladder's critical interval is a property of the "
    "declared criterion, horizon and sample grid (the level is sampled, and the "
    "read-back projection oscillates with the measured quarter period), so a "
    "shared critical interval across items of different width is reported as "
    "measured rather than as an absence of scaling, and the ratio comparison is "
    "reported with the declared threshold difference between the cited lifetimes "
    "and the criterion. "
    "'Neutrally stable' means the declared "
    "criterion of this receipt (horizon retention at or above the written "
    "deposit, the last-half minimum retention also at or above it, and the "
    "horizon retention at least the declared fraction of the mid-run retention), "
    "not a stability analysis of the field's linearized dynamics. Nothing here "
    "demonstrates task-level memory utility, semantic content, retrieval by a "
    "consumer, owner-level checkpoint identity, a distribution of outcomes over "
    "profiles or items, or any advantage over alternative architectures. The "
    "cited intrinsic lifetimes are the ladder receipt's measurements, cited "
    "rather than re-measured, under that receipt's own threshold and sampling. "
    "The declared prediction is a superposed-response model of the loop: it holds "
    "the declared advance linear and the estimated actuator constants to the two "
    "declared calibration probes, so its residual per arm is reported rather than "
    "assumed small, and its domain is the inverted-phase setting, where the loop's "
    "own dynamics keep the deposit on the mode; the in-phase setting is measured "
    "beside it and falls outside the declared domain. The measured neutral gain is "
    "a property of the declared horizon and read-back, not a stability threshold of "
    "the field's dynamics. The declared long horizon shows decelerating but "
    "unbounded growth inside the declared 512 ticks: no plateau, no asymptotic "
    "energy ratio and no bound beyond the measured horizon is claimed, and the "
    "declared beta=0 counterpart differs from the declared profile only at the "
    "level reported as the declared nonlinearity activity bound, so this receipt "
    "does not attribute the stopping of any growth to the declared quartic "
    "coupling. The shared capacity scheme drives the same declared impulse on the item "
    "it does not read back on, and the declared time-multiplexed and per-item schemes "
    "are the declared alternatives to that drive, so the measured capacity limit is the "
    "largest number of declared items any *declared* scheme holds, not a bound on "
    "schedules no declared loop implements, and it is stated per declared gain regime: the "
    "headline figure is the measured neutral gain, the gain at which the loop neither grows "
    "nor decays the written mode, and the amplifying regime's rows are carried beside it and "
    "labelled as amplifying rather than pooled with them, because at an amplifying gain a "
    "written mode grows without bound inside the declared horizon and nothing there is held "
    "or cancelled in the sense the capacity question asks. The declared boundedness flag is "
    "likewise a statement about one arm at its own declared horizon, not a divergence "
    "claim: arms above the declared ratio that stayed finite are listed apart from any "
    "divergent arm, and the declared selected setting is chosen among arms inside the bound "
    "at that setting's own horizon, so the declared best stable setting and the flag cannot "
    "be read off one row. The composition legs run on the flat-inertia metric built by the "
    "metric harness, not on this receipt's default profile, and the flat profile's neutral "
    "gain is re-measured there by the same declared refinement rather than reused from the "
    "default field, so a composition verdict is a statement about the flat metric at that "
    "metric's own gain. The aim leg is cited from the ladder harness's committed receipt and "
    "is not re-measured here, and the cited figures are that harness's own declared-horizon "
    "measurements, so this receipt compares them rather than reproducing them. The per-item "
    "scheme normalizes each item "
    "against that item's own isolated-write post-write projection and its own measured "
    "quadrature scale, both of which are declared constants of this receipt rather than "
    "fitted quantities, and its measured outcome is reported beside the shared scheme's "
    "on the same margin. The genericity arms re-put the declared best "
    "setting on further declared items at the declared horizon, so their per-item "
    "amplification ratios are reported beside the scale-free growth rates that the "
    "declared criterion uses."
)

DEFINITIONS = {
    "written_item": (
        "the durability harness's declared headline item (index 0: the root "
        "scale mode of the whole balanced packet path), written through the "
        "canonical packet impulse at the declared write budget; the multi-item "
        "family writes the first two declared items"
    ),
    "read_frame": (
        "the durability harness's declared readout: the packet coefficients of "
        "the whole balanced packet path, flattened row-major, measured through "
        "analyze_helical_packet on the canonical page"
    ),
    "write_direction": (
        "the unit image of the headline item's own isolated write in the read "
        "frame, captured exactly as the durability harness captures it; every "
        "share in this receipt projects onto it"
    ),
    "measured_deposit": (
        "the read-frame norm of a write's actual coefficient increment inside "
        "the arm, measured before and after that write"
    ),
    "alignment_retention": (
        "(c_read . u)^2 / |c_in_arm|^2 with u the captured write direction and "
        "|c_in_arm|^2 the arm's measured deposit of that item: the share of the "
        "item's own deposit still lying along the written direction. Values "
        "above one mean the read frame holds more energy along the written "
        "direction than the write deposited"
    ),
    "signed_projection_ratio": (
        "(c_read . u) / (c_after_write . u): the loop's declared read-back "
        "amplitude, signed, in units of the projection immediately after the write"
    ),
    "loop_equation": (
        "per tick t, after one canonical advance tick: s_t = c_t . u (signed "
        "projection of the read frame onto the write direction); "
        "a_t = clip(g * per_tick_decay * s_t / s_0, -1, 1); the declared impulse "
        "is applied with flow_signal [a_t, 0.0] and work_budget "
        "loop_work_ceiling * |a_t|. The impulse's direction carries the sign of "
        "a_t and its injected work is exactly its budget, so the loop deposits a "
        "bounded amount of work along the current sign of the written mode, "
        "scaled by the gain, the declared per-tick decay and the read-back "
        "amplitude ratio. A zero amplitude calls the same operation with a zero "
        "flow signal and a zero budget, which is the canonical no-op path"
    ),
    "gain_normalisation": (
        "g multiplies per_tick_decay, the declared per-tick decay of the written "
        "mode derived from the cited source-off retention at 8 ticks "
        "(1 - R^(1/8)); g = 1 therefore attempts to replace one tick's measured "
        "decay of the written mode per tick, and g is bounded by the amplitude "
        "clip at |a_t| <= 1"
    ),
    "loop_work_ceiling": (
        "the declared per-tick work ceiling of the loop, set to the declared "
        "write budget so the loop and the open-loop refresh apply the same "
        "declared impulse scale: the refresh applies it at full amplitude every "
        "declared interval, the loop at the amplitude |a_t| every tick"
    ),
    "open_loop_refresh": (
        "the declared energy-bounded impulse of the write itself re-applied at "
        "every declared interval (8, 16, 32 ticks) with no read-back: the "
        "matched open-loop counterpart of the closed loop"
    ),
    "frame_energy_ratio": (
        "|c_t|^2 / |c_after_write|^2 in the read frame; its maximum over the run "
        "is the declared amplification figure"
    ),
    "boundedness": (
        "an arm is bounded when every read frame and every sampled state is finite and its "
        "maximum frame_energy_ratio is at or below the declared runaway ratio at that arm's "
        "own declared horizon; an arm above that ratio is reported with its own regime label "
        "-- amplifying past the declared bound at its own horizon when it stayed finite, "
        "divergent when it did not -- and is never reported as a maintained pattern or as a "
        "divergence on the strength of that bound alone. The declared selected setting is "
        "chosen among the arms that stay inside the bound at the selected setting's own "
        "declared horizon, so an arm can be the declared best stable setting there while the "
        "same setting's longer run is labelled as amplifying past the bound"
    ),
    "neutral_stability": (
        "the declared criterion for a maintained pattern: the alignment "
        "retention at the horizon is at or above the declared neutral level "
        "floor (the written deposit itself), the last-half minimum retention is "
        "at or above that floor, the horizon retention is at least the declared "
        "decay tolerance times the mid-run retention, and the arm is bounded"
    ),
    "disturbance_of_unwritten_directions": (
        "for every declared item direction the arm did not write, "
        "(c_read . u_j)^2 / |c_captured_j|^2 at the sampled ticks: the same "
        "background-alignment measure the durability harness reports, in units "
        "of the deposit item j would have been written with; the unwritten "
        "maximum at the horizon and its difference from the drift arm are "
        "reported"
    ),
    "declared_frame_projection_fraction": (
        "sum_j (c_read . u_j)^2 / |c_read|^2 over the eight declared item "
        "directions: the share of the read packet's energy that the declared "
        "item frame captures, so leakage outside the declared frame is visible"
    ),
    "workspace_ledger_terms": (
        "the canonical workspace ledger after the run, verbatim: "
        "positive_heartbeat_work, extracted_heartbeat_work, dissipated_work, "
        "numerical_dissipated_work, residual_work, parameter_work, "
        "boundary_work, helical_packet_work, balance_defect and stored_energy. "
        "The loop's own drive work is the helical_packet_work increment beyond "
        "the write's declared budget, reported separately as drive_work"
    ),
    "phase_loop_equation": (
        "the declared phase-aware loop: per tick t, after one canonical advance "
        "tick, the read frame is projected onto the captured write direction "
        "(in phase: S_t = (c_t . u) / (c_after . u)) and onto the declared "
        "quadrature direction (Q_t = (c_t . v) / D, D the declared quadrature "
        "scale); the read-back signal is cos(theta) * S_t + sin(theta) * Q_t and "
        "the drive is a_t = clip(g * per_tick_decay * signal, -1, 1), applied as "
        "the declared packet impulse with flow_signal [a_t, 0.0] and work budget "
        "loop_work_ceiling * |a_t|. theta = 0 is the declared proportional loop "
        "and reproduces its arms exactly; the declared grid is the phase-angle grid "
        "declared in 'declared.phase_angles_degrees' at the declared phase gains"
    ),
    "quadrature_direction": (
        "the same per-mode pattern as the captured write direction placed on the "
        "declared position lane and unit-normalized, because every declared write "
        "lands entirely on the declared momentum lane; the declared quadrature "
        "scale D is the drift baseline's own quadrature projection at its measured "
        "quarter-period tick, so the quadrature term enters the loop in the same "
        "declared units as the in-phase term and no fitted constant is introduced"
    ),
    "phase_prediction": (
        "the declared prediction under test: a phase-aware loop counters the "
        "intrinsic dephasing when an arm holds alignment retention above the drift "
        "baseline's, with a frame energy ratio above one and the largest unwritten "
        "declared direction at or below the declared allowance multiple of the "
        "baseline's, while staying inside the declared boundedness criterion; the "
        "receipt reports whether any declared (theta, g) arm meets it, and the "
        "measured best theta beside the declared quarter-period phase"
    ),
    "quarter_period": (
        "the first tick at which the drift baseline's in-phase/quadrature angle "
        "reaches a quarter turn (90 degrees), measured on the drift trajectory and "
        "reported with its angle, its quadrature projection (the declared "
        "quadrature scale) and the first tick at which the in-phase projection "
        "changes sign; the declared quarter-period phase of the read-back is "
        f"{90.0} degrees with a declared match tolerance"
    ),
    "refresh_ladder": (
        "the declared open-loop refresh intervals (the grid declared in "
        "'declared.ladder_intervals', with the horizon and sample grid declared "
        "there beside it), run for two declared items on different declared rung "
        "paths and therefore different declared widths "
        f"({CITED_ITEM_WIDTHS!r}), so their cited intrinsic lifetimes differ and "
        "the ratio comparison is not degenerate; the critical interval of an item "
        "is the largest declared interval whose arm satisfies the declared "
        "neutral-stability criterion, reported beside the smallest failing "
        "interval above it, so the boundary is bracketed at both ends"
    ),
    "cited_intrinsic_lifetime": (
        f"the ladder receipt ({CITED_LADDER_RECEIPT}) measures each declared "
        f"item's direction lifetime in the {CITED_LADDER_PROFILE} profile as the "
        f"first sampled tick (every {CITED_LADDER_SAMPLE_EVERY_TICKS} ticks) at "
        f"which alignment retention crosses below {CITED_LADDER_THRESHOLD_LABEL}; "
        f"this receipt cites that profile's per-item figures for its two declared "
        f"ladder items ({CITED_INTRINSIC_LIFETIME_TICKS!r}, with their declared "
        f"widths {CITED_ITEM_WIDTHS!r}) and does not re-measure them. The "
        "cited threshold is far below this receipt's declared floor (the written "
        "deposit itself), so the period-to-lifetime ratio compares a strict "
        "maintenance period against a deep-decay crossing and is reported with "
        "that difference declared"
    ),
    "best_declared_phase_setting": (
        "the declared phase grid arm with the largest measured retention at the "
        "declared horizon: the setting the round-3 long-horizon, capacity and "
        "genericity families repeat, so those families run at a measured best "
        "declared setting rather than at the selector's neutrally stable pick"
    ),
    "neutral_gain": (
        "the declared inverted-phase setting's gain at which the loop's horizon "
        "retention crosses the written deposit: measured by bisecting the declared "
        "gain grid's own bracket between the no-drive limit and its smallest gain "
        "until the bracket is narrower than the declared tolerance, with every probe "
        "kept as an arm, and predicted from the declared loop equation plus the "
        "declared actuator calibration"
    ),
    "declared_actuator_calibration": (
        "the declared loop's actuator is one energy-bounded packet impulse, whose "
        "deposited amount solves the generator's work balance against the state's own "
        "momentum along the impulse direction; the declared calibration measures that "
        "amount on the declared unloaded state and in both directions on the declared "
        "loaded (post-write) state, and fits the generator's two constants (lambda, mu) "
        "to those measurements, so the declared prediction of the loop uses no fitted "
        "physics beyond them and its residual is reported per probe"
    ),
    "declared_prediction": (
        "the declared closed-loop prediction superposes the declared free mode "
        "response with the measured response of every earlier declared loop command, "
        "taking the command from the declared loop equation and the deposit that "
        "command buys from the declared actuator calibration; it holds the declared "
        "advance's linearity fixed, is defined at the declared in-phase and inverted "
        "in-phase settings (whose quadrature read-back term vanishes), and is reported "
        "beside the declared linearized injection (the aligned branch's own load line), "
        "whose neutral gain is reported too"
    ),
    "long_horizon_family": (
        "the declared long horizon (at least 512 ticks, sampled every 16) run at the "
        "best declared phase setting and at the measured neutral gain, each beside its "
        "declared beta=0 counterpart (the same arm with the declared quartic coupling "
        "set to zero), with the drift-only arm over the same horizon as the control"
    ),
    "capacity_family": (
        "the declared capacity family writes the headline item and the declared second "
        "item, then runs the declared best setting locked on the headline item (its "
        "drive read back from the headline item only), the same setting driving both "
        "items from the one headline read-back with the declared per-tick work ceiling "
        "split equally, and the same two written items with no loop"
    ),
    "capacity_scheme": (
        "each declared capacity scheme writes the same two declared items and runs the "
        "same declared gain and phase angle over the declared long horizon: the shared "
        "scheme reads back once, on the headline item, and puts that one signed amplitude "
        "on every written item with the declared per-tick work ceiling split equally; the "
        "time-multiplexed schemes drive exactly one declared item per tick on a declared "
        "cycle (adjacent ticks, and declared blocks of ticks) and spend the whole declared "
        "ceiling on that item; the per-item scheme drives every item from that item's own "
        "read-back, that item's own declared quadrature reference and that item's own "
        "isolated post-write projection, so the two drives are not forced into one sign "
        "convention"
    ),
    "capacity_limit": (
        "the measured number of declared items this loop keeps simultaneously above their "
        "own no-loop controls by more than the declared capacity margin, stated per declared "
        "gain regime because the same scheme's outcome is a statement about one gain only: "
        "two when at least one declared scheme holds both in that regime, one otherwise, "
        "since one is the largest number any declared scheme achieves there. The headline "
        "figure is taken from the declared holding regime, the measured neutral gain at which "
        "the loop neither grows nor decays the written mode, and the amplifying regime's rows "
        "are carried beside it labelled as amplifying"
    ),
    "capacity_diagnosis": (
        "the declared diagnosis of one regime's shared scheme, read off that arm's own "
        "per-tick telemetry and recorded with the regime it belongs to: the two drive signals "
        "it applied, the correlation of each item's own per-tick projection with the amplitude "
        "that item's lane received, the fraction of ticks on which that amplitude sat against "
        "(or with) that item's own projection, the signed increment each item's own lane "
        "actually received, and the correlation of the two items' own projections inside the "
        "loop; the amplifying regime reads its declared telemetry twin, which is required to "
        "reproduce the untracked arm's measured series exactly, so the diagnosis cannot have "
        "changed the physics it reports"
    ),
    "capacity_regime": (
        "one declared gain at which the whole capacity family is run over the declared long "
        "horizon: the amplifying regime runs at the best declared phase setting's measured "
        "gain, at which the written mode grows without bound inside that horizon and no "
        "holding question can be answered; the neutral regime runs at the measured neutral "
        "gain of the declared loop, the measured gain at which the written mode neither "
        "grows nor decays; the bounded regime runs at the declared sub-saturation gain. Every "
        "regime writes the same two declared items and runs the same declared schemes, and "
        "each regime's rows are compared against the same drive-free two-item control and "
        "against the single-item loops of that regime's own gain, so no holding claim is read "
        "off another regime's rows"
    ),
    "composition_leg": (
        "the three measured ingredients re-measured on the declared flat-inertia metric, one "
        "leg each, together with the declared capacity curve, drive-split sweep and "
        "quiet-regime ladder that extend those legs at the flat profile's own gain, as "
        "defined in the next three entries. The hold leg is the declared single-item loop at "
        "the flat profile's own "
        "neutral gain over the declared long horizon; the aim leg is *cited* from the ladder "
        "harness's committed receipt and not re-measured here, because that harness already "
        "measured the deepest declared write against the profile's own headline write on the "
        "default metric and on the flat one; the capacity leg is the whole declared capacity "
        "family at the flat profile's neutral gain. Every measured leg is compared against the "
        "flat profile's own no-loop control at the same declared horizon, so a leg cannot "
        "borrow the default metric's control"
    ),
    "capacity_curve": (
        "the declared holding schemes re-run at the declared item counts on the flat metric at "
        "that metric's own measured neutral gain, each count answered against its own declared "
        "no-loop control that writes the same declared items. The declared per-tick work "
        "ceiling is the single-item budget at every count: a scheme that drives every item "
        "each tick divides it between them, and the multiplexed scheme spends it whole on the "
        "one item its declared cycle names that tick, whose cycle repeats and is truncated at "
        "the declared horizon with each item's driven-tick count reported. A scheme holds an "
        "item when that item's back-half mean exceeds its own control's by more than the "
        "declared margin, so the curve reports a count of held items and the work each item "
        "received rather than a single capacity number"
    ),
    "drive_split": (
        "the declared shared scheme on the same two declared items at the same declared gain, "
        "with the declared per-tick work ceiling divided in declared proportions and the "
        "loop's own read-back scalar applied to each item unchanged, so every split divides "
        "the same requested budget and only its division changes; the work the actuator "
        "actually applies comes from each item's own state and is reported per split. The "
        "declared split-dependence "
        "rule reads the largest measured swing in either item's back-half mean across the "
        "declared splits against the declared margin: a swing inside the margin is reported "
        "as two lanes that are not competing for one drive channel"
    ),
    "cross_projection": (
        "what one drive call did to the other driven item's own lane, measured around that "
        "same call from the two frames before and after it and reported per direction "
        "alongside the forward-projection-into-own-projection ratio, with the applied work "
        "those calls carried. The two items' per-tick increments are also compared with each "
        "other: their mean sign product over the ticks on which either lane was driven is the "
        "measured relative phase of the two lanes' drives, one meaning they always moved "
        "together and minus one meaning one lane gained what the other lost"
    ),
    "quiet_regime": (
        "the declared single-item hold on the flat metric holds its retention while its frame "
        "energy falls below its post-write reference, unlike the default field's hold at that "
        "field's own neutral gain. The hold is repeated on the declared further items at the "
        "same gain and re-run at the declared multiples of that gain, each arm over the "
        "declared long horizon with its own per-tick energy and work trajectory retained, so "
        "the receipt says from its own rows whether the falling-energy hold is a property of "
        "the flat profile or of the gain it was measured at"
    ),
    "flat_neutral_gain": (
        "the declared loop's neutral gain re-measured on the flat-inertia profile by the same "
        "declared grid, monotonicity check and bisection as the shipped one, to the same "
        "declared tolerance: the gain solves the loop's declared work balance against the "
        "state's momentum at the moment of the drive, so it is an operating point of the field "
        "it was measured on and the flat profile's own gain is measured there rather than the "
        "default field's gain being reused"
    ),
    "aiming_lever": (
        "the ratio of the ladder harness's own measured deepest-declared-write retention to "
        "that profile's own headline-write retention, on the default metric and on the flat "
        "one, read out of that harness's committed receipt: it is the size of what aiming buys "
        "on that metric. A lever above one by more than the declared lever margin means aiming "
        "still buys retention there; a lever of one means the metric already leaves the "
        "headline direction as slow as the best aimed write, so aiming has nothing left to buy "
        "and is not a lever on that metric"
    ),
    "per_item_read_back": (
        "the declared per-item scheme's read-back: each item's own write direction, its "
        "own declared quadrature direction and the quadrature projection at its own "
        "measured quarter-period tick, measured on that item's own isolated drift, so that "
        "item's in-phase and quadrature terms share one declared unit"
    ),
    "drive_cycle": (
        "a declared per-tick drive schedule over the arm's driven items: position p of the "
        "cycle names the driven item pumped on tick t when t mod the cycle length is p, so "
        "an adjacent cycle pumps one item per tick alternately and a block cycle pumps "
        "declared blocks of ticks per item; every driven item must appear in the cycle"
    ),
    "genericity_items": (
        "the declared genericity family repeats the declared best phase setting on the "
        "declared width-7 item (left-left-detail) and the declared width-14 item "
        "(left-detail), each beside its own no-loop control, and is judged by the "
        "declared criterion: every item's loop retention above its own no-loop "
        "retention, and every item's per-tick growth rate within the declared margin "
        "of the headline item's"
    ),
    "best_stable_loop_setting": (
        "the loop arm (from the declared gain sweep and the declared saturation "
        "ladder) with the largest alignment retention at the horizon among the "
        "arms that satisfy the declared boundedness criterion; the two-item "
        "family runs at that measured setting together with its matched no-loop "
        "two-item control"
    ),
    "transceiver_recon": (
        "a bounded probe of cassi_field_transceiver: condense a bound workspace "
        "under the durability profile and under a declared beta=0 counterpart, "
        "chain the per-tick output back into the next call's input, and record "
        "which coordinates are advanced, whether the canonical page moves, the "
        "input envelope, whether per-tick-varying input requires one call per "
        "tick, and how much authority the input has over the output (one tick "
        "from the kernel's reset state across a declared input scan, and a whole "
        "run at two constant input values)"
    ),
}


@dataclass(frozen=True)
class FeedbackConfig:
    """Declared measurement settings; every number in the receipt derives from these."""

    read_frame_path: str = durability.READ_FRAME_PATH
    headline_item_index: int = durability.HEADLINE_ITEM_INDEX
    write_budget: float = 1e-3
    horizon_ticks: int = 64
    durability_samples: tuple[int, ...] = (8, 16, 32, 64)
    sample_ticks: tuple[int, ...] = (8, 16, 24, 32, 40, 48, 56, 64)
    activity_demand: float = 0.0
    source_enabled: bool = False
    refresh_intervals: tuple[int, ...] = (4, 6, 8, 10, 12, 16, 24, 32)
    # The declared refresh ladder: the same two declared items swept at these
    # intervals over the declared ladder horizon, which is long enough for the
    # narrow item's cited intrinsic lifetime to be observable.
    ladder_intervals: tuple[int, ...] = (4, 6, 8, 10, 12, 16, 24, 32)
    ladder_horizon_ticks: int = 256
    ladder_sample_ticks: tuple[int, ...] = tuple(range(8, 257, 8))
    second_ladder_item: str = "left-left-detail"
    gains: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0)
    saturation_gains: tuple[float, ...] = (4.0, 8.0, 16.0, 32.0, 64.0)
    phase_angles_degrees: tuple[float, ...] = (0.0, 45.0, 90.0, 135.0, 180.0)
    phase_gains: tuple[float, ...] = (0.5, 1.0, 2.0, 4.0)
    # The declared neutral-gain refinement: the declared phase's gain sweep below the
    # declared gain grid's smallest positive gain, whose bracket measures the gain at
    # which the closed loop stops growing the written mode.
    neutral_gain_phase_degrees: float = 180.0
    neutral_gain_grid: tuple[float, ...] = (0.05, 0.1, 0.2, 0.35)
    # The declared long horizon, run at the best declared phase gain and at the
    # measured neutral gain (chosen by the declared refinement below, exactly as the
    # two-item arms are chosen by the declared loop setting).
    long_horizon_ticks: int = 512
    long_horizon_sample_ticks: tuple[int, ...] = tuple(range(16, 513, 16))
    # The declared floor of the long horizon. The shipped configuration declares the
    # full 512 ticks the measurement needs; the floor is declared separately so a
    # reduced-purpose configuration cannot quietly shorten the reported horizon.
    long_horizon_min_ticks: int = 512
    # The declared impulse amplitude law: the projection increment of one declared
    # packet impulse at declared fractions of the write budget, measured in-arm so the
    # declared prediction of the loop needs no fitted constant.
    impulse_amplitude_fractions: tuple[float, ...] = (1.0, 0.5, 0.25, 0.125)
    # The declared second item for the capacity arms, and the two declared items the
    # genericity arms repeat the best phase setting on (different declared widths).
    capacity_item: str = "left-detail"
    genericity_items: tuple[str, ...] = ("left-left-detail", "left-detail")
    # The declared tolerances of the round-3 comparisons: the declared prediction's
    # own retention budget (relative), the ceiling the predicted neutral gain is
    # searched to, and the bound below which the declared quartic coupling is called
    # inactive on a measured arm pair (relative).
    prediction_retention_allowance: float = 0.10
    neutral_gain_prediction_ceiling: float = 4.0
    nonlinearity_activity_bound: float = 1e-9
    # The declared refinement's bracket tolerance (absolute, in gain units) and the
    # allowance on the predicted neutral gain (relative to the measured one).
    neutral_gain_bracket: float = 0.002
    neutral_gain_allowance: float = 0.25
    plateau_growth_tolerance: float = 1.05
    capacity_suppression_margin: float = 0.01
    genericity_margin: float = 0.01
    beta_zero: float = 0.0
    # The declared time-multiplexed maintenance schedules: a loop that pumps exactly one
    # declared item per tick, alternating on a declared cycle. The adjacent schedule
    # alternates the items every tick; the block schedule alternates them in blocks of
    # this many ticks. Both spend the declared per-tick loop work ceiling on the single
    # item they drive, so their per-tick total draw matches the shared loop's split.
    capacity_alternate_block_ticks: int = 64
    # The declared gain regimes of the capacity family. An amplifying setting grows the
    # written mode without bound inside the declared horizon, so it cannot answer a
    # question about holding anything; the neutral regime runs at the measured neutral
    # gain (the measured gain at which the loop neither grows nor decays the mode) and the
    # bounded regime at a declared sub-saturation gain that stays inside the declared
    # boundedness bound over the declared long horizon. Every regime runs the same
    # declared schemes over the same declared horizon and is judged by the same margin.
    capacity_regimes: tuple[str, ...] = ("amplifying", "neutral", "bounded")
    capacity_bounded_gain: float = 1.0
    # The declared capacity curve: the declared item counts the three declared
    # holding schemes are re-run at, on the flat profile at its own measured neutral
    # gain, each against a no-loop control that writes the same declared items. The
    # declared total per-tick drive work is the single-item budget at every count: a
    # scheme that drives every item each tick divides that budget between them, and a
    # multiplexed scheme spends it whole on the one item it drives that tick.
    capacity_curve_counts: tuple[int, ...] = (2, 3, 4, 8)
    capacity_curve_schemes: tuple[str, ...] = (
        "shared",
        "time-multiplex-adjacent",
        "phase-locked-per-item",
    )
    # The declared drive-split sweep: the declared per-tick work ceiling is divided
    # between the two driven items in these declared proportions (the applied
    # amplitude is the loop's own read-back scalar in every split), so the sweep asks
    # whether two held items share one drive channel or occupy independent lanes.
    capacity_split_weights: tuple[tuple[float, float], ...] = (
        (0.5, 0.5),
        (0.7, 0.3),
        (0.3, 0.7),
        (0.9, 0.1),
        (0.1, 0.9),
    )
    # The declared quiet-regime legs: the declared items the single-item hold is
    # repeated on, and the declared multiples of the flat profile's own measured
    # neutral gain at which the hold is re-run, so the receipt can say whether a
    # falling frame energy while holding is a property of the profile or of the gain.
    quiet_regime_items: tuple[str, ...] = ("left-detail", "left-left-detail")
    quiet_regime_gain_factors: tuple[float, ...] = (1.0, 2.0, 4.0)
    # The declared per-item phase-locked maintenance scheme is compared at the same
    # declared gain, phase angle and margin as every other capacity scheme.
    capacity_schemes: tuple[str, ...] = (
        "locked-on-headline",
        "shared-two-item",
        "time-multiplex-adjacent",
        "time-multiplex-block",
        "phase-locked-per-item",
    )
    disturbance_allowance_multiple: float = 2.0
    quarter_period_phase_degrees: float = 90.0
    quarter_period_match_tolerance_degrees: float = 15.0
    ladder_ratio_tolerance: float = 0.05
    loop_work_ceiling: float = 1e-3
    multi_item_count: int = 2
    neutral_level_floor: float = 1.0
    neutral_decay_tolerance: float = 0.9
    runaway_energy_ratio: float = 100.0
    separation_margin: float = 0.01
    ledger_balance_allowance: float = 1e-12
    ledger_residual_allowance: float = 1e-11
    recon_rank: int = 8
    recon_error_allowance: float = 1e-3
    recon_input_bound: float = 4.0
    recon_input: float = 1.75
    recon_input_alternate: float = 3.0
    recon_input_scan: tuple[float, ...] = (0.0, 0.5, 1.75, 3.5)
    recon_authority_allowance: float = 1e-12
    recon_ticks: int = 4

    def __post_init__(self) -> None:
        if not self.sample_ticks:
            raise ValueError("sample ticks are required")
        if sorted(self.sample_ticks) != list(self.sample_ticks):
            raise ValueError("sample ticks must be increasing")
        if self.horizon_ticks != max(self.sample_ticks):
            raise ValueError("the declared horizon must be the last sample")
        if not set(self.durability_samples).issubset(self.sample_ticks):
            raise ValueError(
                "the durability samples must remain a declared subset of the samples"
            )
        if not set(CITED_SOURCE_OFF_RETENTION).issubset(self.sample_ticks):
            raise ValueError(
                "the ticks of the cited durability figures must remain declared samples, "
                "because this receipt continues them in agreement"
            )
        if self.horizon_ticks % 2 != 0:
            raise ValueError("the declared horizon must be even for the last-half split")
        if self.horizon_ticks // 2 not in self.sample_ticks:
            raise ValueError("the mid-run tick must be a declared sample")
        if not 0.0 < float(self.write_budget) <= 1.0:
            raise ValueError("write_budget must lie in (0,1]")
        if not 0.0 < float(self.loop_work_ceiling) <= 1.0:
            raise ValueError("the loop work ceiling must lie in (0,1]")
        if not 0.0 <= float(self.activity_demand) <= 1.0:
            raise ValueError("activity demand must lie in [0,1]")
        if self.source_enabled:
            raise ValueError(
                "every arm of this receipt declares the durability harness's "
                "source-off activity, whose cited retention figures this receipt "
                "continues, so source_enabled must stay false"
            )
        if not self.gains or self.gains[0] != 0.0:
            raise ValueError(
                "the declared gain sweep must start at zero so the loop-closure "
                "identity arm is part of the sweep"
            )
        if sorted(set(self.gains)) != list(self.gains):
            raise ValueError("declared gains must be strictly increasing")
        if sorted(set(self.saturation_gains)) != list(self.saturation_gains):
            raise ValueError("declared saturation gains must be strictly increasing")
        if min(self.gains) < 0.0 or min(self.saturation_gains) <= max(self.gains):
            raise ValueError("the saturation ladder must sit above the gain sweep")
        for interval in self.refresh_intervals:
            if interval <= 0 or interval >= self.horizon_ticks:
                raise ValueError("declared refresh intervals must lie inside the horizon")
        names = [spec.name for spec in durability.ITEM_SPECS]
        if self.second_ladder_item not in names:
            raise ValueError("the declared second ladder item must be a declared item")
        ladder_index = names.index(self.second_ladder_item)
        if ladder_index == int(self.headline_item_index):
            raise ValueError("the second ladder item must differ from the headline item")
        if self.second_ladder_item not in CITED_INTRINSIC_LIFETIME_TICKS:
            raise ValueError(
                "the second ladder item must be one whose intrinsic lifetime this "
                "receipt cites, because the ladder reports its ratio to it"
            )
        if names[int(self.headline_item_index)] not in CITED_INTRINSIC_LIFETIME_TICKS:
            raise ValueError("the headline item's cited intrinsic lifetime is required")
        if durability.ITEM_SPECS[ladder_index].path == (
            durability.ITEM_SPECS[int(self.headline_item_index)].path
        ):
            raise ValueError(
                "the two declared ladder items must sit on different declared rung "
                "paths, so their widths and lifetimes differ and the scaling test "
                "is not degenerate"
            )
        if not self.ladder_intervals:
            raise ValueError("the declared refresh ladder is required")
        if sorted(set(self.ladder_intervals)) != list(self.ladder_intervals):
            raise ValueError("declared ladder intervals must be strictly increasing")
        for interval in self.ladder_intervals:
            if interval <= 0 or interval >= self.ladder_horizon_ticks:
                raise ValueError("declared ladder intervals must lie inside the horizon")
        if int(self.ladder_horizon_ticks) < int(CITED_LADDER_LIFETIME_MIN_TICKS):
            raise ValueError(
                "the declared ladder horizon must be at least the longest cited "
                "intrinsic lifetime, so that lifetime is observable in the sweep"
            )
        ladder_samples = list(self.ladder_sample_ticks)
        if not ladder_samples or sorted(set(ladder_samples)) != ladder_samples:
            raise ValueError("declared ladder sample ticks must be strictly increasing")
        if int(self.ladder_horizon_ticks) != max(ladder_samples):
            raise ValueError("the declared ladder horizon must be its last sample")
        if int(self.ladder_horizon_ticks) % 2 != 0:
            raise ValueError("the declared ladder horizon must be even")
        if int(self.ladder_horizon_ticks) // 2 not in ladder_samples:
            raise ValueError("the ladder mid-run tick must be a declared sample")
        gaps = [
            right - left for left, right in zip(ladder_samples, ladder_samples[1:])
        ]
        if max(gaps) * 4 > int(max(self.ladder_intervals)):
            raise ValueError(
                "the ladder must be sampled at least four times per coarsest declared "
                "interval, so the criterion's minimum is taken over samples that "
                "resolve the deepest post-refresh decay of the coarsest arm"
            )
        if not self.phase_angles_degrees:
            raise ValueError("the declared phase grid is required")
        if sorted(set(self.phase_angles_degrees)) != list(self.phase_angles_degrees):
            raise ValueError("declared phase angles must be strictly increasing")
        if any(
            not 0.0 <= float(angle) < 360.0 for angle in self.phase_angles_degrees
        ):
            raise ValueError("declared phase angles must lie in [0,360)")
        if not self.phase_gains or min(self.phase_gains) <= 0.0:
            raise ValueError("the declared phase gains must be positive")
        if not self.neutral_gain_grid:
            raise ValueError("the declared neutral-gain refinement is required")
        if sorted(set(self.neutral_gain_grid)) != list(self.neutral_gain_grid):
            raise ValueError("declared neutral-gain candidates must be strictly increasing")
        if min(self.neutral_gain_grid) <= 0.0 or max(self.neutral_gain_grid) >= min(
            self.phase_gains
        ):
            raise ValueError(
                "the declared neutral-gain refinement must lie strictly below the "
                "declared phase grid's smallest gain, or it would repeat it"
            )
        if float(self.neutral_gain_phase_degrees) not in [
            float(angle) for angle in self.phase_angles_degrees
        ]:
            raise ValueError(
                "the declared neutral-gain phase must be one of the declared phase "
                "grid's angles, so the measured law uses the declared loop equation"
            )
        if int(self.long_horizon_ticks) < int(self.long_horizon_min_ticks):
            raise ValueError(
                "the declared long horizon must be at least its declared floor, so the "
                "growth and its plateau are observable well past the measured lifetimes"
            )
        long_samples = [int(t) for t in self.long_horizon_sample_ticks]
        if (
            not long_samples
            or sorted(set(long_samples)) != long_samples
            or max(long_samples) != int(self.long_horizon_ticks)
            or int(self.long_horizon_ticks) % 2 != 0
            or int(self.long_horizon_ticks) // 2 not in long_samples
        ):
            raise ValueError(
                "the declared long-horizon samples must be strictly increasing, end at "
                "the declared long horizon and include its midpoint"
            )
        if max(
            right - left for left, right in zip(long_samples, long_samples[1:])
        ) > 16:
            raise ValueError(
                "the declared long horizon must be sampled at no more than 16-tick "
                "spacing, so a plateau is resolved rather than assumed"
            )
        fractions = [float(f) for f in self.impulse_amplitude_fractions]
        if not fractions or max(fractions) != 1.0 or min(fractions) <= 0.0:
            raise ValueError(
                "the declared impulse amplitude fractions must be positive and include "
                "the full write budget as their reference"
            )
        if sorted(set(fractions), reverse=True) != fractions:
            raise ValueError("declared impulse amplitude fractions must be decreasing")
        names = [spec.name for spec in durability.ITEM_SPECS]
        if self.capacity_item not in names:
            raise ValueError("the declared capacity item must be a declared item")
        if self.capacity_item == names[int(self.headline_item_index)]:
            raise ValueError("the declared capacity item must differ from the headline item")
        if len(self.genericity_items) < 2 or len(set(self.genericity_items)) != len(
            self.genericity_items
        ):
            raise ValueError("the declared genericity items must be distinct")
        for name in self.genericity_items:
            if name not in names:
                raise ValueError(f"the declared genericity item {name!r} is not declared")
        if float(self.prediction_retention_allowance) <= 0.0:
            raise ValueError("the declared prediction allowance must be positive")
        if float(self.neutral_gain_allowance) <= 0.0:
            raise ValueError("the declared neutral-gain allowance must be positive")
        if float(self.neutral_gain_bracket) <= 0.0:
            raise ValueError("the declared neutral-gain bracket must be positive")
        if float(self.neutral_gain_prediction_ceiling) <= max(self.neutral_gain_grid):
            raise ValueError(
                "the declared prediction ceiling must exceed the declared refinement "
                "grid, so the predicted neutral gain is searched past it"
            )
        if float(self.nonlinearity_activity_bound) <= 0.0:
            raise ValueError("the declared nonlinearity activity bound must be positive")
        if float(self.plateau_growth_tolerance) <= 1.0:
            raise ValueError("the declared plateau growth tolerance must exceed one")
        if float(self.capacity_suppression_margin) < 0.0:
            raise ValueError("the declared capacity suppression margin cannot be negative")
        if float(self.genericity_margin) < 0.0:
            raise ValueError("the declared genericity margin cannot be negative")
        if float(self.disturbance_allowance_multiple) < 1.0:
            raise ValueError("the disturbance allowance must be at least the baseline")
        if not 0.0 <= float(self.quarter_period_match_tolerance_degrees) < 90.0:
            raise ValueError("the quarter-period match tolerance must lie in [0,90)")
        if float(self.ladder_ratio_tolerance) < 0.0:
            raise ValueError("the ladder ratio tolerance cannot be negative")
        if int(self.multi_item_count) < 2 or int(self.multi_item_count) > len(
            durability.ITEM_SPECS
        ):
            raise ValueError("the multi-item count must lie inside the declared item list")
        if float(self.neutral_decay_tolerance) <= 0.0:
            raise ValueError("the neutral decay tolerance must be positive")
        if float(self.runaway_energy_ratio) <= 1.0:
            raise ValueError("the runaway energy ratio must exceed one")
        if float(self.separation_margin) < 0.0:
            raise ValueError("the separation margin cannot be negative")
        if not self.recon_input_scan:
            raise ValueError("the declared input scan is required")
        if any(
            abs(float(value)) > float(self.recon_input_bound)
            for value in self.recon_input_scan
        ):
            raise ValueError("the declared input scan must stay inside the input envelope")
        if float(self.recon_authority_allowance) <= 0.0:
            raise ValueError("the authority allowance must be positive")
        if int(self.capacity_alternate_block_ticks) <= 0:
            raise ValueError("the declared multiplex block length must be positive")
        if int(self.long_horizon_ticks) % int(self.capacity_alternate_block_ticks):
            raise ValueError(
                "the declared multiplex block length must divide the declared long "
                "horizon, so both declared items receive whole blocks"
            )
        if (int(self.long_horizon_ticks) // int(self.capacity_alternate_block_ticks)) % 2:
            raise ValueError(
                "the declared long horizon must hold a whole number of declared "
                "multiplex block pairs, so the block schedule is balanced"
            )
        if not self.capacity_schemes:
            raise ValueError("the declared capacity schemes are required")
        if len(set(self.capacity_schemes)) != len(self.capacity_schemes):
            raise ValueError("the declared capacity schemes must be distinct")
        if not self.capacity_regimes:
            raise ValueError("the declared capacity gain regimes are required")
        if len(set(self.capacity_regimes)) != len(self.capacity_regimes):
            raise ValueError("the declared capacity regimes must be distinct")
        if "amplifying" not in self.capacity_regimes:
            raise ValueError(
                "the declared capacity regimes must include the amplifying regime the "
                "shipped two-item arms already measure"
            )
        unknown = set(self.capacity_regimes) - {"amplifying", "neutral", "bounded"}
        if unknown:
            raise ValueError(
                f"the declared capacity regimes {sorted(unknown)} are not declared regimes"
            )
        if float(self.capacity_bounded_gain) <= 0.0:
            raise ValueError("the declared bounded capacity gain must be positive")
        if float(self.capacity_bounded_gain) not in [
            float(gain) for gain in self.phase_gains
        ]:
            raise ValueError(
                "the declared bounded capacity gain must be one of the declared phase "
                "grid's gains, so the regime reuses a declared setting rather than "
                "inventing one"
            )
        if not self.capacity_curve_counts:
            raise ValueError("the declared capacity curve needs declared item counts")
        if list(self.capacity_curve_counts) != sorted(self.capacity_curve_counts):
            raise ValueError("the declared capacity curve counts must be increasing")
        if len(set(self.capacity_curve_counts)) != len(self.capacity_curve_counts):
            raise ValueError("the declared capacity curve counts must be distinct")
        if any(
            int(count) < 2 or int(count) > len(durability.ITEM_SPECS)
            for count in self.capacity_curve_counts
        ):
            raise ValueError(
                "a declared capacity curve count must be at least two and no more than "
                "the number of declared items"
            )
        declared_schemes = (
            "shared",
            "time-multiplex-adjacent",
            "phase-locked-per-item",
        )
        unknown_schemes = set(self.capacity_curve_schemes) - set(declared_schemes)
        if unknown_schemes:
            raise ValueError(
                f"the declared capacity curve schemes {sorted(unknown_schemes)} are not "
                "declared schemes"
            )
        if len(set(self.capacity_curve_schemes)) != len(self.capacity_curve_schemes):
            raise ValueError("the declared capacity curve schemes must be distinct")
        for count in self.capacity_curve_counts:
            if int(count) > int(self.long_horizon_ticks):
                raise ValueError(
                    "a declared capacity curve count must fit inside the declared long "
                    "horizon, so its scheme drives every declared item"
                )
        if not self.capacity_split_weights:
            raise ValueError("the declared drive-split sweep needs declared splits")
        for split in self.capacity_split_weights:
            if len(split) != 2:
                raise ValueError("a declared drive split is a two-item proportion")
            if any(float(weight) <= 0.0 for weight in split):
                raise ValueError(
                    "a declared drive split must give both items a positive share, so "
                    "no declared scheme drives nothing"
                )
            if abs(sum(float(weight) for weight in split) - 1.0) > 1e-12:
                raise ValueError(
                    "a declared drive split must sum to one, so every split requests the "
                    "same declared per-tick work"
                )
        if len(set(tuple(float(w) for w in s) for s in self.capacity_split_weights)) != len(
            self.capacity_split_weights
        ):
            raise ValueError("the declared drive splits must be distinct")
        if not self.quiet_regime_gain_factors:
            raise ValueError("the declared quiet-regime gain ladder is required")
        if any(float(factor) <= 0.0 for factor in self.quiet_regime_gain_factors):
            raise ValueError("a declared quiet-regime gain factor must be positive")
        if 1.0 not in [float(factor) for factor in self.quiet_regime_gain_factors]:
            raise ValueError(
                "the declared quiet-regime gain ladder must include the neutral gain "
                "itself, so the ladder is read against the hold it extends"
            )
        if len(set(self.quiet_regime_items)) != len(self.quiet_regime_items):
            raise ValueError("the declared quiet-regime items must be distinct")
        names = [spec.name for spec in durability.ITEM_SPECS]
        for item in self.quiet_regime_items:
            if item not in names:
                raise ValueError("a declared quiet-regime item must be a declared item")
            if item == names[int(self.headline_item_index)]:
                raise ValueError(
                    "the declared quiet-regime ladder extends the headline item's own "
                    "hold, so it must name further items rather than repeat it"
                )

    @property
    def capacity_item_index(self) -> int:
        """The declared capacity item's index in the declared item list."""

        names = [spec.name for spec in durability.ITEM_SPECS]
        if self.capacity_item not in names:
            raise ValueError("the declared capacity item must be a declared item")
        return names.index(self.capacity_item)

    @property
    def genericity_item_indices(self) -> tuple[int, ...]:
        """The declared genericity items' indices in the declared item list."""

        names = [spec.name for spec in durability.ITEM_SPECS]
        return tuple(names.index(name) for name in self.genericity_items)

    @property
    def second_ladder_item_index(self) -> int:
        """The declared second ladder item's index in the declared item list."""

        names = [spec.name for spec in durability.ITEM_SPECS]
        if self.second_ladder_item not in names:
            raise ValueError("the declared second ladder item must be a declared item")
        return names.index(self.second_ladder_item)

    def as_dict(self) -> dict[str, Any]:
        return {
            "read_frame_path": self.read_frame_path,
            "headline_item_index": self.headline_item_index,
            "write_budget": self.write_budget,
            "horizon_ticks": self.horizon_ticks,
            "durability_samples": list(self.durability_samples),
            "sample_ticks": list(self.sample_ticks),
            "activity_demand": self.activity_demand,
            "source_enabled": self.source_enabled,
            "refresh_intervals": list(self.refresh_intervals),
            "ladder_intervals": list(self.ladder_intervals),
            "ladder_horizon_ticks": self.ladder_horizon_ticks,
            "ladder_sample_ticks": list(self.ladder_sample_ticks),
            "second_ladder_item": self.second_ladder_item,
            "second_ladder_item_index": self.second_ladder_item_index,
            "second_ladder_item_path": (
                durability.ITEM_SPECS[self.second_ladder_item_index].path
            ),
            "headline_item": durability.ITEM_SPECS[self.headline_item_index].name,
            "headline_item_path": durability.ITEM_SPECS[self.headline_item_index].path,
            "cited_intrinsic_lifetime_ticks": dict(CITED_INTRINSIC_LIFETIME_TICKS),
            "cited_item_widths": dict(CITED_ITEM_WIDTHS),
            "cited_ladder_receipt": CITED_LADDER_RECEIPT,
            "cited_ladder_threshold": CITED_LADDER_THRESHOLD_LABEL,
            "cited_ladder_profile": CITED_LADDER_PROFILE,
            "cited_ladder_sample_every_ticks": CITED_LADDER_SAMPLE_EVERY_TICKS,
            "gains": list(self.gains),
            "saturation_gains": list(self.saturation_gains),
            "phase_angles_degrees": list(self.phase_angles_degrees),
            "phase_gains": list(self.phase_gains),
            "neutral_gain_phase_degrees": self.neutral_gain_phase_degrees,
            "neutral_gain_grid": list(self.neutral_gain_grid),
            "long_horizon_ticks": self.long_horizon_ticks,
            "long_horizon_min_ticks": self.long_horizon_min_ticks,
            "long_horizon_sample_ticks": list(self.long_horizon_sample_ticks),
            "impulse_amplitude_fractions": list(self.impulse_amplitude_fractions),
            "capacity_item": self.capacity_item,
            "genericity_items": list(self.genericity_items),
            "prediction_retention_allowance": self.prediction_retention_allowance,
            "neutral_gain_prediction_ceiling": self.neutral_gain_prediction_ceiling,
            "nonlinearity_activity_bound": self.nonlinearity_activity_bound,
            "cited_item_widths": {
                spec.name: int(CITED_ITEM_WIDTHS[spec.name])
                for spec in durability.ITEM_SPECS
                if spec.name in CITED_ITEM_WIDTHS
            },
            "neutral_gain_allowance": self.neutral_gain_allowance,
            "neutral_gain_bracket": self.neutral_gain_bracket,
            "plateau_growth_tolerance": self.plateau_growth_tolerance,
            "capacity_suppression_margin": self.capacity_suppression_margin,
            "capacity_alternate_block_ticks": self.capacity_alternate_block_ticks,
            "capacity_schemes": list(self.capacity_schemes),
            "capacity_regimes": list(self.capacity_regimes),
            "capacity_bounded_gain": self.capacity_bounded_gain,
            "capacity_curve_counts": list(self.capacity_curve_counts),
            "capacity_curve_schemes": list(self.capacity_curve_schemes),
            "capacity_split_weights": [list(split) for split in self.capacity_split_weights],
            "quiet_regime_items": list(self.quiet_regime_items),
            "quiet_regime_gain_factors": list(self.quiet_regime_gain_factors),
            "genericity_margin": self.genericity_margin,
            "beta_zero": self.beta_zero,
            "disturbance_allowance_multiple": self.disturbance_allowance_multiple,
            "quarter_period_phase_degrees": self.quarter_period_phase_degrees,
            "quarter_period_match_tolerance_degrees": (
                self.quarter_period_match_tolerance_degrees
            ),
            "ladder_ratio_tolerance": self.ladder_ratio_tolerance,
            "cited_intrinsic_lifetime_ticks": dict(CITED_INTRINSIC_LIFETIME_TICKS),
            "cited_ladder_receipt": CITED_LADDER_RECEIPT,
            "cited_ladder_threshold_label": CITED_LADDER_THRESHOLD_LABEL,
            "cited_ladder_sample_every_ticks": CITED_LADDER_SAMPLE_EVERY_TICKS,
            "loop_work_ceiling": self.loop_work_ceiling,
            "multi_item_count": self.multi_item_count,
            "neutral_level_floor": self.neutral_level_floor,
            "neutral_decay_tolerance": self.neutral_decay_tolerance,
            "runaway_energy_ratio": self.runaway_energy_ratio,
            "separation_margin": self.separation_margin,
            "ledger_balance_allowance": self.ledger_balance_allowance,
            "ledger_residual_allowance": self.ledger_residual_allowance,
            "recon_rank": self.recon_rank,
            "recon_error_allowance": self.recon_error_allowance,
            "recon_input_bound": self.recon_input_bound,
            "recon_input": self.recon_input,
            "recon_input_alternate": self.recon_input_alternate,
            "recon_input_scan": list(self.recon_input_scan),
            "recon_authority_allowance": self.recon_authority_allowance,
            "recon_ticks": self.recon_ticks,
            "per_tick_decay": PER_TICK_DECAY,
            "decay_reference_ticks": DECAY_REFERENCE_TICKS,
            "decay_reference_retention": DECAY_REFERENCE_RETENTION,
            "cited_agreement_allowance": CITED_AGREEMENT_ALLOWANCE,
        }


# The declared configuration every number in the shipped receipt derives from.
DECLARED = FeedbackConfig()


@dataclass(frozen=True)
class LoopArm:
    """One declared arm: which items are written, and how the page is driven."""

    name: str
    item_indices: tuple[int, ...]
    refresh_interval: int = 0
    gain: float = 0.0
    family: str = "single-item"
    phase_degrees: float = 0.0
    measure_item_index: int = durability.HEADLINE_ITEM_INDEX
    horizon_ticks: int = 0
    sample_ticks: tuple[int, ...] = ()
    # The declared profile override: None keeps the declared profile, a number sets
    # the quartic coupling of the arm's own profile (the declared beta=0 counterpart).
    profile_beta: float | None = None
    # The declared driven items: empty drives the arm's single measured item. A
    # multi-item loop drives every listed item each tick from the same read-back, with
    # the declared per-tick work ceiling split equally between them.
    drive_items: tuple[int, ...] = ()
    # The declared per-tick drive cycle, as positions in the arm's driven-item list: an
    # empty cycle drives every driven item every tick, while a declared cycle drives
    # exactly the one item it names on each tick, so the declared per-tick work ceiling
    # is spent on that item instead of being split. Every driven item must appear in the
    # cycle, so a multiplexed arm still pumps all of them.
    drive_cycle: tuple[int, ...] = ()
    # The declared per-item read-back: each driven item is read back through its own
    # direction and its own declared phase reference, with the declared gain applied to
    # each item's own signal, instead of one shared signal driving every item.
    phase_locked: bool = False
    # The declared split of the declared per-tick work ceiling between the driven items,
    # as proportions in the arm's driven-item order summing to one. None splits the
    # ceiling equally, which is what every arm measured before this seam did.
    drive_split: tuple[float, ...] | None = None
    # Whether the arm records its per-tick drive telemetry in the receipt.
    telemetry: bool = False
    # The declared gain regime the arm belongs to: an amplifying setting grows the mode
    # without bound inside its own horizon, a neutral setting neither grows nor decays it,
    # and a bounded setting amplifies but stays inside the declared boundedness bound over
    # the declared long horizon. The label is recorded so no row can be read as a holding
    # result when it was measured in the amplifying regime.
    regime: str = ""

    def __post_init__(self) -> None:
        if self.refresh_interval < 0:
            raise ValueError("a refresh interval cannot be negative")
        if self.gain < 0.0:
            raise ValueError("a declared gain cannot be negative")
        if self.refresh_interval and self.gain:
            raise ValueError("an arm is either an open-loop refresh or a closed loop")
        if int(self.horizon_ticks) < 0:
            raise ValueError("a declared arm horizon cannot be negative")
        if self.profile_beta is not None and not (
            isinstance(self.profile_beta, (int, float))
            and not isinstance(self.profile_beta, bool)
        ):
            raise ValueError("a declared arm profile coupling must be a number")
        if self.drive_items and any(
            int(index) not in set(int(i) for i in self.item_indices)
            for index in self.drive_items
        ):
            raise ValueError(
                "a declared multi-item loop can only drive items the arm writes"
            )
        if self.sample_ticks:
            if int(self.horizon_ticks) != max(int(t) for t in self.sample_ticks):
                raise ValueError("an arm horizon must be its last declared sample")
            if sorted(set(int(t) for t in self.sample_ticks)) != [
                int(t) for t in self.sample_ticks
            ]:
                raise ValueError("an arm's sample ticks must be strictly increasing")
        if not self.item_indices:
            raise ValueError("an arm must write at least one declared item")
        if not 0 <= int(self.measure_item_index) < len(durability.ITEM_SPECS):
            raise ValueError("the measured item must be a declared item")
        if self.phase_degrees and not self.gain:
            raise ValueError("a declared phase angle needs a declared gain to act on")
        driven = tuple(int(i) for i in (self.drive_items or (self.measure_item_index,)))
        if self.gain and int(self.measure_item_index) not in driven:
            raise ValueError(
                "a closed loop reads back on the item it drives, so the measured item "
                "must be one of the driven items"
            )
        if self.drive_cycle:
            if not self.gain:
                raise ValueError("a declared drive cycle needs a declared gain to act on")
            if sorted(set(int(p) for p in self.drive_cycle)) != list(
                range(len(driven))
            ):
                raise ValueError(
                    "a declared drive cycle must name every driven item at least once "
                    "and no other position"
                )
        if self.phase_locked:
            if not self.gain:
                raise ValueError("a declared per-item read-back needs a declared gain")
            if not self.phase_degrees:
                raise ValueError(
                    "a declared per-item read-back needs a declared phase angle, because "
                    "the loop re-injects against each item's own projection"
                )
            if len(driven) < 2:
                raise ValueError(
                    "a declared per-item read-back is a multi-item scheme, so it needs "
                    "at least two driven items"
                )
        if self.telemetry and not self.gain:
            raise ValueError("declared drive telemetry needs a declared gain")
        if self.drive_split is not None:
            if not self.gain:
                raise ValueError("a declared drive split needs a declared gain to act on")
            if len(self.drive_split) != len(driven):
                raise ValueError(
                    "a declared drive split must give one proportion per driven item"
                )
            if any(float(weight) <= 0.0 for weight in self.drive_split):
                raise ValueError(
                    "a declared drive split must give every driven item a positive share"
                )
            if abs(sum(float(weight) for weight in self.drive_split) - 1.0) > 1e-12:
                raise ValueError(
                    "a declared drive split must sum to one, so it spends exactly the "
                    "declared per-tick work ceiling"
                )


def frame_channels(config: FeedbackConfig) -> list[str]:
    """The declared read frame's channel names, read from the canonical analyzer."""

    return list(
        analyze_helical_packet(
            initial_workspace(ResonantProfile()), path=config.read_frame_path
        )["channels"]
    )


def quadrature_direction(
    config: FeedbackConfig, captures: Sequence[Mapping[str, Any]], index: int
) -> np.ndarray:
    """The declared quadrature readout: the item's mode pattern on the position lane.

    The declared writes land entirely on the momentum lane, so the conjugate
    readout is the same per-mode pattern placed on the declared position lane,
    unit-normalized. It is a declared construction, and its overlap with the
    write direction is measured and reported (zero for the declared items).
    """

    channels = frame_channels(config)
    if POSITION_LANE not in channels or MOMENTUM_LANE not in channels:
        raise ValueError("the declared read frame has no declared position/momentum lanes")
    direction = np.asarray(captures[index]["direction"], dtype=np.float64)
    block = direction.reshape(len(direction) // len(channels), len(channels))
    rows = np.where(np.linalg.norm(block, axis=1) > DIRECTION_ROW_TOLERANCE)[0]
    quadrature = np.zeros_like(block)
    quadrature[rows, channels.index(POSITION_LANE)] = block[
        rows, channels.index(MOMENTUM_LANE)
    ]
    flattened = quadrature.reshape(-1)
    norm = float(np.linalg.norm(flattened))
    if norm <= 0.0:
        raise ValueError("the declared item has no momentum content to conjugate")
    return flattened / norm


def phase_readout_block(
    config: FeedbackConfig,
    captures: Sequence[Mapping[str, Any]],
    profile: ResonantProfile | None = None,
    ticks: int | None = None,
) -> dict[str, Any]:
    """The declared quadrature readout's rotation, measured on the drift trajectory.

    Drift alone is advanced one tick at a time with sources off, and the read
    frame is projected onto the write direction (in phase) and onto the declared
    quadrature direction each tick. The declared quadrature scale is the
    quadrature projection at the measured quarter-period tick (the first tick at
    which the in-phase/quadrature angle reaches a quarter turn), so the phase
    grid's quadrature term is expressed in the same declared units as its
    in-phase term and no fitted constant enters the loop.
    """

    base = profile or ResonantProfile()
    horizon = int(ticks if ticks is not None else config.horizon_ticks)
    headline = int(config.headline_item_index)
    workspace, written = write_items(config, (headline,), base)
    deposit = written["deposits"][durability.ITEM_SPECS[headline].name]
    direction = write_direction(captures, headline)
    quadrature = quadrature_direction(config, captures, headline)
    after = durability.read_frame(workspace, config.read_frame_path)
    reference = float(np.dot(after, direction))
    energy_reference = durability.squared_norm(after)
    rows: list[dict[str, Any]] = [
        {
            "tick": 0,
            "in_phase_ratio": 1.0,
            "quadrature_projection": float(np.dot(after, quadrature)),
            "angle_degrees": 0.0,
            "frame_energy_ratio": 1.0,
            "alignment_retention": durability.share_along(after, direction, deposit),
        }
    ]
    for tick in range(1, horizon + 1):
        workspace, _advance = advance_workspace(
            workspace, ticks=1, demand=config.activity_demand, source_enabled=False
        )
        vector = durability.read_frame(workspace, config.read_frame_path)
        in_phase = float(np.dot(vector, direction))
        quadrature_projection = float(np.dot(vector, quadrature))
        rows.append(
            {
                "tick": tick,
                "in_phase_ratio": in_phase / reference,
                "quadrature_projection": quadrature_projection,
                "angle_degrees": float(
                    np.degrees(np.arctan2(quadrature_projection, in_phase))
                ),
                "frame_energy_ratio": durability.squared_norm(vector) / energy_reference,
                "alignment_retention": durability.share_along(vector, direction, deposit),
            }
        )
    quarter = next(
        (row for row in rows if abs(float(row["angle_degrees"])) >= 90.0), None
    )
    if quarter is None:
        raise ValueError(
            "the declared quadrature readout never reaches a quarter turn inside the "
            "declared horizon, so the phase grid has no declared reference scale"
        )
    reversal = next(
        (row for row in rows[1:] if float(row["in_phase_ratio"]) < 0.0), None
    )
    return {
        "declared": (
            "drift alone (sources off), one canonical advance tick at a time, read "
            "through the declared read frame; in_phase_ratio is the signed projection "
            "onto the captured write direction in units of its post-write value, "
            "quadrature_projection is the projection onto the declared quadrature "
            "direction in the read frame's own units, and angle_degrees is their angle"
        ),
        "profile_beta": float(base.beta),
        "ticks": horizon,
        "write_direction_lane": MOMENTUM_LANE,
        "quadrature_direction_lane": POSITION_LANE,
        "write_quadrature_overlap": float(np.dot(direction, quadrature)),
        "sign_references": {
            "in_phase": reference,
            "energy": energy_reference,
            "quadrature_scale": float(quarter["quadrature_projection"]),
            "quadrature_scale_tick": int(quarter["tick"]),
        },
        "quarter_period_tick": int(quarter["tick"]),
        "quarter_period_angle_degrees": float(quarter["angle_degrees"]),
        "sign_reversal_tick": None if reversal is None else int(reversal["tick"]),
        "rotation_rate_degrees_per_tick": float(
            quarter["angle_degrees"] / max(1, int(quarter["tick"]))
        ),
        "rows": rows,
    }


def item_phase_readouts(
    config: FeedbackConfig,
    captures: Sequence[Mapping[str, Any]],
    profile: ResonantProfile | None = None,
    ticks: int | None = None,
    indices: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Each declared item's own quadrature readout, measured on its own isolated drift.

    The declared per-item maintenance scheme drives every item against its own
    projection, so it needs each item's own read-back reference rather than the
    headline item's: the item is written alone, advanced one canonical tick at a time
    with sources off, and read through its own write direction and its own declared
    quadrature direction. The declared quadrature scale is that item's quadrature
    projection at its own measured quarter-period tick, exactly as the declared
    single read-back's scale is the headline item's. Nothing here is fitted.
    """

    base = profile or ResonantProfile()
    horizon = int(ticks if ticks is not None else config.long_horizon_ticks)
    stride = int(CITED_LADDER_SAMPLE_EVERY_TICKS)
    declared_indices = tuple(
        int(index)
        for index in (
            indices
            if indices is not None
            else (config.headline_item_index, config.capacity_item_index)
        )
    )
    items: dict[str, Any] = {}
    for index in declared_indices:
        spec = durability.ITEM_SPECS[index]
        workspace, written = write_items(config, (index,), base)
        deposit = float(written["deposits"][spec.name])
        direction = write_direction(captures, index)
        quadrature = quadrature_direction(config, captures, index)
        after = durability.read_frame(workspace, config.read_frame_path)
        reference = float(np.dot(after, direction))
        energy_reference = durability.squared_norm(after)
        quarter: dict[str, Any] | None = None
        reversal: int | None = None
        rows: list[dict[str, Any]] = []
        for tick in range(1, horizon + 1):
            workspace, _advance = advance_workspace(
                workspace,
                ticks=1,
                demand=config.activity_demand,
                source_enabled=False,
            )
            vector = durability.read_frame(workspace, config.read_frame_path)
            in_phase = float(np.dot(vector, direction))
            quadrature_projection = float(np.dot(vector, quadrature))
            angle_degrees = float(np.degrees(np.arctan2(quadrature_projection, in_phase)))
            if quarter is None and abs(angle_degrees) >= float(
                config.quarter_period_phase_degrees
            ):
                quarter = {
                    "tick": int(tick),
                    "angle_degrees": angle_degrees,
                    "quadrature_projection": quadrature_projection,
                }
            if reversal is None and in_phase < 0.0:
                reversal = int(tick)
            if tick % stride == 0 or (quarter and int(quarter["tick"]) == tick):
                rows.append(
                    {
                        "tick": int(tick),
                        "in_phase_ratio": in_phase / reference,
                        "quadrature_projection": quadrature_projection,
                        "angle_degrees": angle_degrees,
                        "alignment_retention": durability.share_along(
                            vector, direction, deposit
                        ),
                    }
                )
        if quarter is None:
            raise ValueError(
                f"the declared item {spec.name} never reaches a quarter turn inside the "
                "declared horizon, so it has no declared quadrature scale"
            )
        items[spec.name] = {
            "item": spec.name,
            "item_index": int(index),
            "profile_beta": float(base.beta),
            "write_direction_lane": MOMENTUM_LANE,
            "quadrature_direction_lane": POSITION_LANE,
            "write_quadrature_overlap": float(np.dot(direction, quadrature)),
            "post_write_signed_projection": reference,
            "post_write_energy": energy_reference,
            "post_write_deposit": deposit,
            "quadrature_scale": float(quarter["quadrature_projection"]),
            "quadrature_scale_tick": int(quarter["tick"]),
            "quarter_period_angle_degrees": float(quarter["angle_degrees"]),
            "rotation_rate_degrees_per_tick": float(
                quarter["angle_degrees"] / max(1, int(quarter["tick"]))
            ),
            "sign_reversal_tick": reversal,
            "rows": rows,
        }
    return {
        "declared": (
            "each declared item written alone and drifted one canonical tick at a time "
            "with sources off, read through its own write direction and its own declared "
            "quadrature direction; the quadrature scale is that item's quadrature "
            "projection at its own measured quarter-period tick, so the declared per-item "
            "loop drives each item in that item's own units"
        ),
        "sample_every_ticks": stride,
        "ticks": horizon,
        "items": items,
    }


def per_item_phase_references(
    config: FeedbackConfig,
    captures: Sequence[Mapping[str, Any]],
    readouts: Mapping[str, Any],
    indices: Sequence[int],
) -> dict[int, dict[str, Any]]:
    """The declared per-item read-back: each item's own quadrature direction and scale.

    The in-phase term of each item's own signal is its own projection in the arm's own
    post-write units (measured by :func:`run_stream`), and its quadrature term is that
    item's own declared quadrature direction in that item's own declared scale.
    """

    references: dict[int, dict[str, Any]] = {}
    for index in indices:
        name = durability.ITEM_SPECS[int(index)].name
        readout = readouts["items"][name]
        isolated = float(readout["post_write_signed_projection"])
        scale = float(readout["quadrature_scale"])
        if not isolated or not scale:
            raise ValueError(
                f"the declared item {name} has a zero isolated projection or quadrature "
                "scale, so it has no declared per-item read-back units"
            )
        references[int(index)] = {
            "direction": quadrature_direction(config, captures, int(index)),
            "scale": scale,
            "isolated_signed_projection": isolated,
            "quadrature_scale_tick": int(readout["quadrature_scale_tick"]),
        }
    return references


def phase_signal(
    config: FeedbackConfig,
    arm: LoopArm,
    vector: np.ndarray,
    direction: np.ndarray,
    signed_reference: float,
    phase_reference: Mapping[str, Any] | None,
) -> float:
    """The declared read-back signal: in-phase plus quadrature at the declared phase."""

    in_phase = float(np.dot(vector, direction)) / signed_reference
    if not arm.phase_degrees:
        return in_phase
    if phase_reference is None:
        raise ValueError("a declared phase angle needs the declared quadrature reference")
    quadrature = phase_reference["direction"]
    scale = float(phase_reference["scale"])
    theta = math.radians(float(arm.phase_degrees))
    quadrature_ratio = float(np.dot(vector, quadrature)) / scale
    return math.cos(theta) * in_phase + math.sin(theta) * quadrature_ratio


def impulse_probe(
    config: FeedbackConfig,
    captures: Sequence[Mapping[str, Any]],
    profile: ResonantProfile,
    index: int,
    direction: np.ndarray,
    reference: float,
    fraction: float,
    sign: float,
    loaded: bool,
) -> dict[str, Any]:
    """One declared impulse probe: the projection increment of one declared impulse.

    The probe is applied either to a freshly opened field (the declared unloaded
    state) or to a field that has just been written (the declared loaded state, which
    is the state the declared loop first drives at). The increment is measured along
    the item's declared read direction in units of the reference projection, so no
    fitted constant enters the declared calibration.
    """

    work = float(config.write_budget) * float(fraction)
    workspace, written = write_items(config, (index,), profile)
    before = durability.read_frame(workspace, config.read_frame_path)
    if not loaded:
        workspace = initial_workspace(profile)
        before = durability.read_frame(workspace, config.read_frame_path)
    projection_before = float(np.dot(before, direction))
    after_workspace, receipt = apply_drive(workspace, index, sign, work)
    after = durability.read_frame(after_workspace, config.read_frame_path)
    return {
        "fraction": float(fraction),
        "sign": float(sign),
        "loaded": bool(loaded),
        "work_budget": work,
        "impulse_amount": float(receipt["impulse_amount"]),
        "applied_work": float(receipt["applied_work"]),
        "accepted": bool(receipt["accepted"]),
        "projection_before": projection_before,
        "projection_after": float(np.dot(after, direction)),
        "increment": float(np.dot(after, direction)) - projection_before,
        "increment_ratio": (
            (float(np.dot(after, direction)) - projection_before) / reference
            if reference
            else None
        ),
        "projection_ratio": (projection_before / reference if reference else None),
    }


def probe_ratio(probe: Mapping[str, Any], reference: float) -> float:
    """The declared operating ratio of one impulse probe: its pre-impulse projection.

    The declared actuator's constants are stated against the declared loaded state, so a
    probe made on the unwritten field (whose projection is zero) is checked at ratio
    zero, where the generator's own equation reduces to the measured square-root law.
    """

    stored = probe.get("projection_ratio")
    if stored is None:
        return float(probe["projection_before"]) / float(reference) if reference else 0.0
    return float(stored)


def actuator_calibration_block(
    config: FeedbackConfig,
    captures: Sequence[Mapping[str, Any]],
    profile: ResonantProfile | None = None,
    ticks: int | None = None,
) -> dict[str, Any]:
    """Measure the declared loop actuator and the declared free mode response.

    The declared drive is one energy-bounded packet impulse: the frozen generator
    solves the requested work budget for the deposited amount, and because the
    state's own momentum along the impulse direction enters that solution the deposit
    is not proportional to the requested work. The declared calibration therefore
    measures the actuator twice, once on the declared unloaded state and once on the
    declared loaded state (post-write), in both impulse directions, and fits the two
    constants of the generator's own deposit equation to those measurements. The
    declared free mode response (the signed retention of one written item under drift
    alone) is measured alongside it, so the declared prediction needs no fitted
    physics beyond the two measured actuator constants.
    """

    base = profile or ResonantProfile()
    horizon = int(ticks if ticks is not None else config.horizon_ticks)
    index = int(config.headline_item_index)
    direction = write_direction(captures, index)
    readout = phase_readout_block(config, captures, base, horizon)
    free = [float(row["in_phase_ratio"]) for row in readout["rows"]]
    if abs(free[0] - 1.0) > 1e-9:
        raise ValueError("the declared free response must be measured from its write")
    workspace, written = write_items(config, (index,), base)
    after = durability.read_frame(workspace, config.read_frame_path)
    reference = float(np.dot(after, direction))
    loaded_probes: dict[str, Any] = {}
    for sign in (1.0, -1.0):
        for fraction in config.impulse_amplitude_fractions:
            key = f"{'aligned' if sign > 0 else 'anti'}-{repr(float(fraction))}"
            loaded_probes[key] = impulse_probe(
                config, captures, base, index, direction, reference,
                float(fraction), sign, True,
            )
    unloaded_probes: dict[str, Any] = {}
    for fraction in config.impulse_amplitude_fractions:
        key = f"unaligned-{repr(float(fraction))}"
        unloaded_probes[key] = impulse_probe(
            config, captures, base, index, direction, reference,
            float(fraction), 1.0, False,
        )
    aligned_unit = loaded_probes[f"aligned-{repr(1.0)}"]
    anti_unit = loaded_probes[f"anti-{repr(1.0)}"]
    unaligned_unit = unloaded_probes[f"unaligned-{repr(1.0)}"]
    amount_reference = float(unaligned_unit["impulse_amount"])
    if amount_reference <= 0.0:
        raise ValueError("the declared unloaded impulse deposits no measured amount")
    budget = float(config.write_budget)
    aligned_amount = float(aligned_unit["impulse_amount"])
    anti_amount = float(anti_unit["impulse_amount"])
    if aligned_amount <= 0.0 or anti_amount <= 0.0:
        raise ValueError("the declared loaded impulse deposits no measured amount")
    # The generator's declared deposit equation, solved for its two constants from
    # the two measured loaded-state amounts at the declared unit budget:
    #   aligned: root + lambda = 2b / amount,  anti: root + lambda = mu * amount
    mu = 2.0 * budget / (aligned_amount * anti_amount)
    lam = (mu * anti_amount * anti_amount - 2.0 * budget) / (2.0 * anti_amount)
    fit = {
        "lambda": lam,
        "mu": mu,
        "budget": budget,
        "amount_reference": amount_reference,
        "projection_reference": reference,
        "loaded_projection_ratio": 1.0,
    }
    checks: dict[str, Any] = {}
    for key, probe in {**loaded_probes, **unloaded_probes}.items():
        predicted = actuator_increment(
            float(probe["sign"]) * float(probe["fraction"]),
            probe_ratio(probe, reference),
            fit,
        )
        checks[key] = {
            "measured_increment_ratio": probe["increment_ratio"],
            "predicted_increment_ratio": predicted,
            "residual": (
                None
                if probe["increment_ratio"] is None
                else float(probe["increment_ratio"]) - predicted
            ),
        }
    residuals = [
        abs(float(row["residual"]))
        for row in checks.values()
        if row["residual"] is not None
    ]
    return {
        "declared": (
            "the declared loop actuator is one energy-bounded packet impulse; its "
            "deposit amount solves work = lambda*amount/amount_reference + "
            "mu*(amount/amount_reference)**2/2, and the two constants lambda and mu "
            "are measured from the aligned and anti-aligned unit-budget impulses on "
            "the loaded (post-write) state, with the unloaded unit impulse fixing the "
            "amount scale"
        ),
        "profile_beta": float(base.beta),
        "ticks": horizon,
        "fit": fit,
        "loaded_probes": loaded_probes,
        "unloaded_probes": unloaded_probes,
        "prediction_checks": checks,
        "prediction_check_max_residual": max(residuals) if residuals else None,
        "free_retention": free,
        "unit_projection_increment_ratio": {
            "aligned": aligned_unit["increment_ratio"],
            "anti": anti_unit["increment_ratio"],
            "unaligned": unaligned_unit["increment_ratio"],
        },
    }


def actuator_increment(
    amplitude: float, ratio: float, fit: Mapping[str, Any]
) -> float:
    """The declared actuator's projection increment for one declared loop command.

    This is the generator's own deposit equation expressed in units of the reference
    projection: the deposited amount solves the declared work balance with the state's
    own momentum along the impulse direction, so an impulse that agrees with the
    state's momentum delivers a small coherent amount while an impulse that opposes it
    must overshoot the state's momentum to spend the same work. Both branches are the
    declared generator's, and both are measured by the declared calibration.
    """

    work = float(fit["budget"]) * abs(float(amplitude))
    if work == 0.0:
        return 0.0
    lam = float(fit["lambda"])
    mu = float(fit["mu"])
    if mu <= 0.0:
        raise ValueError("the declared actuator has no positive kinetic metric")
    # The state's momentum along the impulse's own direction: a command that opposes
    # the mode's momentum drives the generator's overshoot branch, which is why the
    # deposit is not proportional to the requested work.
    linear = lam * float(ratio) * math.copysign(1.0, float(amplitude))
    root = math.sqrt(linear * linear + 2.0 * mu * work)
    if linear >= 0.0:
        amount = 2.0 * work / (root + linear)
    else:
        amount = (root - linear) / mu
    return math.copysign(amount, float(amplitude)) / float(fit["amount_reference"])


def linear_injection_increment(
    amplitude: float, ratio: float, fit: Mapping[str, Any]
) -> float:
    """The declared linearized injection: the aligned branch's own load line.

    The declared linear prediction treats the loop's re-injection as proportional to
    its command. On the declared loaded state the aligned branch's deposit is linear in
    the requested work with slope 1/(lambda * ratio), so in units of the reference
    projection the injection is amplitude * budget / (lambda * |ratio| *
    amount_reference): it is the declared generator's measured load line, continued by
    symmetry to the opposing command. It is reported beside the declared algebraic
    prediction, because the anti-aligned branch of the same actuator has no such
    proportionality: its leading deposit is set by the state's own momentum, not by the
    command, and that is the difference the two predictions measure.
    """

    load = abs(float(fit["lambda"]) * float(ratio))
    if load <= 0.0:
        raise ValueError(
            "the declared linearized injection has no finite slope on an unloaded mode"
        )
    return (
        float(amplitude)
        * float(fit["budget"])
        / (load * float(fit["amount_reference"]))
    )


def predict_retention_series(
    gain: float,
    phase_degrees: float,
    calibration: Mapping[str, Any],
    ticks: int,
    per_tick_decay: float = PER_TICK_DECAY,
    linearized: bool = False,
) -> list[float]:
    """The declared closed-loop prediction of the signed retention at every tick.

    The declared prediction superposes the frozen generator's measured free response of
    the written mode with the measured response of every earlier declared loop command,
    using the declared loop equation for the command and the declared actuator equation
    (with its measured constants) for the deposit that command buys. The prediction
    therefore holds the declared advance's linearity fixed and measures everything else;
    its residual against the arms is reported, not assumed away.
    """

    if abs(math.sin(math.radians(float(phase_degrees)))) > 1e-12:
        raise ValueError(
            "the declared prediction is defined for the declared in-phase and "
            "inverted in-phase settings, whose quadrature term vanishes"
        )
    cosine = math.cos(math.radians(float(phase_degrees)))
    free = [float(value) for value in calibration["free_retention"]]
    if len(free) < int(ticks) + 1:
        raise ValueError("the declared free response is shorter than the prediction")
    fit = calibration["fit"]
    amplitudes: list[float] = []
    deposits: list[float] = []
    series: list[float] = []
    for tick in range(1, int(ticks) + 1):
        pre = free[tick]
        for lag, deposit in enumerate(reversed(deposits), start=1):
            pre += deposit * free[lag]
        raw = float(gain) * float(per_tick_decay) * cosine * pre
        amplitude = float(max(-1.0, min(1.0, raw)))
        if linearized:
            deposit = linear_injection_increment(amplitude, pre, fit)
        else:
            deposit = actuator_increment(amplitude, pre, fit)
        amplitudes.append(amplitude)
        deposits.append(deposit)
        series.append(pre + deposit)
    return series


def predicted_neutral_gain(
    phase_degrees: float,
    calibration: Mapping[str, Any],
    ticks: int,
    search_ceiling: float,
    deposit: float = 1.0,
    scan_points: int = 200,
    linearized: bool = False,
) -> dict[str, Any]:
    """The declared prediction's own neutral gain: first bracket, then bisection."""

    def retention(gain: float) -> float:
        return predict_retention_series(
            gain, phase_degrees, calibration, ticks, linearized=linearized
        )[-1]

    grid = [
        float(search_ceiling) * index / float(scan_points)
        for index in range(scan_points + 1)
    ]
    bracket = None
    for low, high in zip(grid, grid[1:]):
        if retention(low) ** 2 < deposit <= retention(high) ** 2:
            bracket = (low, high)
            break
    if bracket is None:
        return {
            "found": False,
            "search_ceiling": float(search_ceiling),
            "retention_at_ceiling": retention(float(search_ceiling)) ** 2,
            "deposit": float(deposit),
            "linearized": bool(linearized),
        }
    low, high = bracket
    for _ in range(80):
        middle = 0.5 * (low + high)
        if retention(middle) ** 2 < deposit:
            low = middle
        else:
            high = middle
    return {
        "found": True,
        "gain": 0.5 * (low + high),
        "bracket": [low, high],
        "retention_at_gain": retention(0.5 * (low + high)) ** 2,
        "deposit": float(deposit),
        "search_ceiling": float(search_ceiling),
        "linearized": bool(linearized),
    }


def single_item_arm_declarations(config: FeedbackConfig) -> tuple[LoopArm, ...]:
    """The drift, refresh and closed-loop arms, all on the declared headline item."""

    headline = config.headline_item_index
    arms = [LoopArm("drift-no-refresh-no-loop", (headline,), family="drift")]
    for interval in config.refresh_intervals:
        arms.append(
            LoopArm(
                f"refresh-open-loop-every-{int(interval)}",
                (headline,),
                refresh_interval=int(interval),
                family="refresh",
            )
        )
    for gain in config.gains:
        arms.append(
            LoopArm(
                f"closed-loop-g{gain:g}",
                (headline,),
                gain=float(gain),
                family="closed-loop",
            )
        )
    for gain in config.saturation_gains:
        arms.append(
            LoopArm(
                f"closed-loop-saturation-g{gain:g}",
                (headline,),
                gain=float(gain),
                family="closed-loop-saturation",
            )
        )
    for interval in config.ladder_intervals:
        for family, item_index, prefix in (
            ("refresh-ladder", int(config.headline_item_index), ""),
            ("refresh-ladder-detail", int(config.second_ladder_item_index), "detail-"),
        ):
            arms.append(
                LoopArm(
                    f"refresh-ladder-{prefix}every-{int(interval)}",
                    (item_index,),
                    refresh_interval=int(interval),
                    family=family,
                    measure_item_index=item_index,
                    horizon_ticks=int(config.ladder_horizon_ticks),
                    sample_ticks=tuple(int(t) for t in config.ladder_sample_ticks),
                )
            )
    for angle in config.phase_angles_degrees:
        for gain in config.phase_gains:
            arms.append(
                LoopArm(
                    f"closed-loop-phase-{angle:g}deg-g{gain:g}",
                    (headline,),
                    gain=float(gain),
                    family="closed-loop-phase",
                    phase_degrees=float(angle),
                )
            )
    return tuple(arms)


def multi_item_arm_declarations(
    config: FeedbackConfig, selected: LoopArm
) -> tuple[LoopArm, ...]:
    """The two-item family: the selected loop setting beside its matched no-loop control."""

    items = tuple(range(int(config.multi_item_count)))
    return (
        LoopArm("drift-k2-control", items, family="multi-item"),
        LoopArm(
            f"{selected.name}-k2",
            items,
            refresh_interval=selected.refresh_interval,
            gain=selected.gain,
            family="multi-item",
        ),
    )


def neutral_gain_arm_declarations(config: FeedbackConfig) -> tuple[LoopArm, ...]:
    """The declared neutral-gain refinement: the inverted-phase gain grid."""

    headline = int(config.headline_item_index)
    return tuple(
        LoopArm(
            f"neutral-gain-g{float(gain):g}",
            (headline,),
            gain=float(gain),
            family="neutral-gain",
            phase_degrees=float(config.neutral_gain_phase_degrees),
        )
        for gain in config.neutral_gain_grid
    )


def measure_neutral_gain(
    config: FeedbackConfig,
    captures: Sequence[Mapping[str, Any]],
    phase_reference: Mapping[str, Any],
    profile: ResonantProfile,
    arms: dict[str, Any],
    drift_arm: str = "drift-no-refresh-no-loop",
    name_prefix: str = "",
) -> dict[str, Any]:
    """Measure the neutral gain of the declared loop by the declared refinement.

    The declared refinement measures the declared gain grid, checks that the horizon
    retention rises with the gain across it (the declared monotonicity the refinement
    relies on), then bisects the bracket between the no-drive limit and the smallest
    grid gain until the bracket is narrower than the declared tolerance. Every probe is
    a declared arm and every probe is kept in the receipt, so the measured neutral gain
    is a measurement rather than an interpolation over the grid.
    """

    headline = int(config.headline_item_index)
    grid_arms = [
        arm if not name_prefix else replace(arm, name=f"{name_prefix}{arm.name}")
        for arm in neutral_gain_arm_declarations(config)
    ]
    grid_rows: list[dict[str, Any]] = []
    for arm in grid_arms:
        arms[arm.name] = run_stream(config, captures, arm, phase_reference, profile)
        grid_rows.append(
            {
                "arm": arm.name,
                "gain": float(arm.gain),
                "retention_at_horizon": arms[arm.name]["neutral_stability"][
                    "measure_retention_at_horizon"
                ],
                "growth_rate_per_tick": growth_rate_per_tick(arms[arm.name]),
                "frame_energy_ratio": arms[arm.name]["horizon"]["frame_energy_ratio"],
            }
        )
    monotone = all(
        left["retention_at_horizon"] <= right["retention_at_horizon"] + 1e-12
        for left, right in zip(grid_rows, grid_rows[1:])
    )
    if drift_arm not in arms:
        raise ValueError(
            f"the declared refinement's no-drive reference {drift_arm!r} was not measured"
        )
    drift = arms[drift_arm]["neutral_stability"]["measure_retention_at_horizon"]
    low_gain, high_gain = 0.0, float(config.neutral_gain_grid[0])
    low_retention = drift
    high_retention = grid_rows[0]["retention_at_horizon"]
    if high_retention <= 1.0:
        raise ValueError(
            "the declared neutral-gain refinement cannot bracket the measured "
            "neutral gain: the smallest declared refinement gain already decays"
        )
    probes: list[dict[str, Any]] = []
    while high_gain - low_gain > float(config.neutral_gain_bracket):
        middle = 0.5 * (low_gain + high_gain)
        name = f"{name_prefix}neutral-gain-refine-g{middle:.6f}"
        arm = LoopArm(
            name,
            (headline,),
            gain=middle,
            family="neutral-gain-refine",
            phase_degrees=float(config.neutral_gain_phase_degrees),
        )
        arms[name] = run_stream(config, captures, arm, phase_reference, profile)
        retention = arms[name]["neutral_stability"]["measure_retention_at_horizon"]
        probes.append(
            {
                "arm": name,
                "gain": middle,
                "retention_at_horizon": retention,
                "growth_rate_per_tick": growth_rate_per_tick(arms[name]),
            }
        )
        if retention < 1.0:
            low_gain, low_retention = middle, retention
        else:
            high_gain, high_retention = middle, retention
    neutral = 0.5 * (low_gain + high_gain)
    return {
        "grid": grid_rows,
        "grid_monotone": bool(monotone),
        "probes": probes,
        "measured_gain": neutral,
        "bracket": [low_gain, high_gain],
        "bracket_width": high_gain - low_gain,
        "retention_below": low_retention,
        "retention_above": high_retention,
        "tolerance": float(config.neutral_gain_bracket),
        "drift_retention_at_horizon": drift,
    }


def growth_rate_per_tick(result: Mapping[str, Any]) -> float | None:
    """The measured per-tick growth rate of the arm's own retention over its horizon."""

    samples = result["samples"]
    if len(samples) < 2:
        return None
    first, last = samples[0], samples[-1]
    span = int(last["tick"]) - int(first["tick"])
    if span <= 0 or float(first["measure_retention"]) <= 0.0:
        return None
    ratio = float(last["measure_retention"]) / float(first["measure_retention"])
    return ratio ** (1.0 / span) - 1.0


def long_horizon_arm_declarations(
    config: FeedbackConfig, best_gain: float, measured_gain: float
) -> tuple[LoopArm, ...]:
    """The declared long horizon: the best declared setting and the measured neutral gain."""

    headline = int(config.headline_item_index)
    samples = tuple(int(t) for t in config.long_horizon_sample_ticks)
    arms = [
        LoopArm(
            "drift-long",
            (headline,),
            family="long-horizon",
            horizon_ticks=int(config.long_horizon_ticks),
            sample_ticks=samples,
        )
    ]
    # Each long-horizon arm is labelled with the declared gain regime its own gain puts it
    # in: the best declared phase setting's gain is the amplifying regime (the regime the
    # capacity family is run at), and the measured neutral gain is the neutral regime, so a
    # reader can see from the row itself which gain's statement it supports.
    for label, gain, beta, regime in (
        ("best-gain", float(best_gain), None, "amplifying"),
        ("measured-neutral-gain", float(measured_gain), None, "neutral"),
        (
            "beta-zero-best-gain",
            float(best_gain),
            float(config.beta_zero),
            "amplifying",
        ),
        (
            "beta-zero-measured-neutral-gain",
            float(measured_gain),
            float(config.beta_zero),
            "neutral",
        ),
    ):
        arms.append(
            LoopArm(
                f"long-horizon-{label}",
                (headline,),
                gain=gain,
                family="long-horizon",
                phase_degrees=float(config.neutral_gain_phase_degrees),
                horizon_ticks=int(config.long_horizon_ticks),
                sample_ticks=samples,
                profile_beta=beta,
                regime=regime,
            )
        )
    return tuple(arms)


# The declared arm-name suffix of each declared capacity scheme, and of the two declared
# per-regime single-item reference arms. The amplifying regime's arms shipped before the
# regime label existed and keep the names they were measured under; every later regime
# names its arms after its own regime, so a row can never be read as another regime's.
CAPACITY_SCHEME_SUFFIXES = {
    "locked-on-headline": "locked-on-headline",
    "shared-two-item": "shared-two-item",
    "time-multiplex-adjacent": "alternate-adjacent",
    "time-multiplex-block": "alternate-block",
    "phase-locked-per-item": "phase-locked-per-item",
}
CAPACITY_REFERENCE_SUFFIXES = ("single-item-headline", "single-item-second")
AMPLIFYING_CAPACITY_ARM_NAMES = {
    "locked-on-headline": "capacity-locked-on-headline",
    "shared-two-item": "capacity-two-item-loop",
    "time-multiplex-adjacent": "capacity-alternate-adjacent",
    "time-multiplex-block": "capacity-alternate-block",
    "phase-locked-per-item": "capacity-phase-locked-per-item",
}
AMPLIFYING_CAPACITY_REFERENCE_NAMES = {
    "single-item-headline": "long-horizon-best-gain",
    "single-item-second": "capacity-second-item-only-loop",
}


# The declared amplifying-regime diagnosis arm: the shared two-item loop shipped without
# per-tick telemetry, so the diagnosis reads the declared telemetry twin of that arm.
AMPLIFYING_CAPACITY_DIAGNOSIS_ARM = "capacity-two-item-telemetry"


def capacity_diagnosis_arm_name(regime: str) -> str:
    """The declared arm whose own per-tick telemetry diagnoses one regime's shared scheme."""

    if regime == "amplifying":
        return AMPLIFYING_CAPACITY_DIAGNOSIS_ARM
    return capacity_arm_name(regime, "shared-two-item")


def capacity_arm_name(regime: str, scheme: str) -> str:
    """The declared arm name of one declared capacity scheme in one declared regime."""

    if regime == "amplifying":
        if scheme in AMPLIFYING_CAPACITY_ARM_NAMES:
            return AMPLIFYING_CAPACITY_ARM_NAMES[scheme]
        if scheme in AMPLIFYING_CAPACITY_REFERENCE_NAMES:
            return AMPLIFYING_CAPACITY_REFERENCE_NAMES[scheme]
        raise ValueError(f"the declared scheme {scheme} has no amplifying arm name")
    if scheme in CAPACITY_SCHEME_SUFFIXES:
        return f"capacity-{regime}-{CAPACITY_SCHEME_SUFFIXES[scheme]}"
    if scheme in CAPACITY_REFERENCE_SUFFIXES:
        return f"capacity-{regime}-{scheme}"
    raise ValueError(f"the declared scheme {scheme} has no declared arm name")


def capacity_regime_arm_declarations(
    config: FeedbackConfig, regime: str, gain: float, telemetry: bool = True
) -> tuple[LoopArm, ...]:
    """One declared capacity regime: every declared scheme and both item references.

    The same declared schemes run in every regime at that regime's declared gain, over
    the same declared long horizon, with the same two declared items written and the same
    declared margin; the two single-item reference arms read back on one item each at the
    same gain, so a regime's rows can be compared against the single-item loop *of that
    regime* rather than against a different setting's.
    """

    headline = int(config.headline_item_index)
    second = int(config.capacity_item_index)
    items = (headline, second)
    samples = tuple(int(t) for t in config.long_horizon_sample_ticks)
    block = int(config.capacity_alternate_block_ticks)
    arms: list[LoopArm] = []
    for scheme in CAPACITY_SCHEME_SUFFIXES:
        if scheme == "locked-on-headline":
            drive_items: tuple[int, ...] = (headline,)
            extra: dict[str, Any] = {}
        elif scheme == "shared-two-item":
            drive_items = items
            extra = {}
        elif scheme == "time-multiplex-adjacent":
            drive_items = items
            extra = {"drive_cycle": (0, 1)}
        elif scheme == "time-multiplex-block":
            drive_items = items
            extra = {"drive_cycle": tuple([0] * block + [1] * block)}
        else:
            drive_items = items
            extra = {"phase_locked": True}
        arms.append(
            LoopArm(
                capacity_arm_name(regime, scheme),
                items,
                gain=float(gain),
                family="capacity",
                phase_degrees=float(config.neutral_gain_phase_degrees),
                horizon_ticks=int(config.long_horizon_ticks),
                sample_ticks=samples,
                drive_items=drive_items,
                telemetry=bool(telemetry),
                regime=regime,
                **extra,
            )
        )
    for scheme in CAPACITY_REFERENCE_SUFFIXES:
        index = headline if scheme.endswith("headline") else second
        arms.append(
            LoopArm(
                capacity_arm_name(regime, scheme),
                items,
                gain=float(gain),
                family="capacity",
                phase_degrees=float(config.neutral_gain_phase_degrees),
                horizon_ticks=int(config.long_horizon_ticks),
                sample_ticks=samples,
                drive_items=(index,),
                measure_item_index=int(index),
                telemetry=bool(telemetry),
                regime=regime,
            )
        )
    return tuple(arms)


# The declared curve schemes: the three declared holding schemes that held both declared
# items at the declared two-item count on the flat metric. The declared shared scheme's
# single read-back is the headline item, exactly as the two-item capacity family's is.
# The declared control arm of the composition legs: the flat profile's own no-loop arm,
# which writes the same two declared items as every capacity scheme and drives nothing.
COMPOSITION_CONTROL_ARM = "flat-two-item-no-loop"
# The shipped arm that is the default profile's own single-item hold at its own measured
# neutral gain: the quiet-regime verdict reads the flat profile's hold against this row.
DEFAULT_NEUTRAL_HOLD_ARM = "long-horizon-measured-neutral-gain"
CAPACITY_CURVE_SCHEME_SUFFIXES = {
    "shared": "shared",
    "time-multiplex-adjacent": "adjacent",
    "phase-locked-per-item": "per-item",
}


def capacity_curve_items(config: FeedbackConfig, count: int) -> tuple[int, ...]:
    """The first ``count`` items of the declared curve item order.

    The declared order starts with the two declared capacity items (the headline item and
    the declared second item), so the declared two-item count reproduces the shipped
    two-item pair exactly, and then continues through the declared item list in order.
    """

    names = [spec.name for spec in durability.ITEM_SPECS]
    order: list[int] = []
    for index in (int(config.headline_item_index), int(config.capacity_item_index)):
        if index not in order:
            order.append(index)
    for index in range(len(names)):
        if index not in order:
            order.append(index)
    if int(count) > len(order):
        raise ValueError(
            "a declared curve count cannot exceed the declared item list"
        )
    return tuple(order[: int(count)])


def capacity_curve_arm_name(count: int, scheme: str) -> str:
    """The declared arm name of one declared curve scheme at one declared count."""

    if scheme == "no-loop":
        return f"flat-curve-k{int(count)}-no-loop"
    if scheme not in CAPACITY_CURVE_SCHEME_SUFFIXES:
        raise ValueError(f"the declared curve scheme {scheme} is not a declared scheme")
    return f"flat-curve-k{int(count)}-{CAPACITY_CURVE_SCHEME_SUFFIXES[scheme]}"


def capacity_curve_arm_declarations(
    config: FeedbackConfig, gain: float, counts: Sequence[int] | None = None
) -> tuple[LoopArm, ...]:
    """The declared capacity curve: the declared schemes at the declared item counts.

    Every count writes the declared curve items and is answered against its own declared
    no-loop control at the same horizon. Each scheme spends the single-item declared
    per-tick work ceiling: the schemes that drive every item each tick divide it between
    them, and the multiplexed scheme spends it whole on the one item its declared cycle
    names that tick, so the curve measures what holding more items costs rather than
    letting the cost grow with the count. The declared cycle repeats and is truncated at
    the declared horizon, and each arm reports its own driven-tick count per item.
    """

    declared_counts = tuple(
        int(count) for count in (counts if counts is not None else config.capacity_curve_counts)
    )
    samples = tuple(int(t) for t in config.long_horizon_sample_ticks)
    arms: list[LoopArm] = []
    for count in declared_counts:
        items = capacity_curve_items(config, count)
        for scheme in ("no-loop", *config.capacity_curve_schemes):
            if scheme == "no-loop":
                arms.append(
                    LoopArm(
                        capacity_curve_arm_name(count, scheme),
                        items,
                        family="capacity-curve",
                        horizon_ticks=int(config.long_horizon_ticks),
                        sample_ticks=samples,
                        regime="flat",
                    )
                )
                continue
            extra: dict[str, Any] = {}
            if scheme == "time-multiplex-adjacent":
                extra = {"drive_cycle": tuple(range(len(items)))}
            elif scheme == "phase-locked-per-item":
                extra = {"phase_locked": True}
            arms.append(
                LoopArm(
                    capacity_curve_arm_name(count, scheme),
                    items,
                    gain=float(gain),
                    family="capacity-curve",
                    phase_degrees=float(config.neutral_gain_phase_degrees),
                    horizon_ticks=int(config.long_horizon_ticks),
                    sample_ticks=samples,
                    drive_items=items,
                    telemetry=True,
                    regime="flat",
                    **extra,
                )
            )
    return tuple(arms)


def capacity_split_arm_name(split: Sequence[float]) -> str:
    """The declared arm name of one declared drive split."""

    return "flat-split-" + "-".join(
        f"{int(round(float(weight) * 100))}" for weight in split
    )


def capacity_split_arm_declarations(
    config: FeedbackConfig, gain: float, splits: Sequence[Sequence[float]] | None = None
) -> tuple[LoopArm, ...]:
    """The declared drive-split sweep: the declared two-item loop under each declared split.

    Every split runs the declared shared scheme on the same two declared items at the same
    declared gain, with the declared per-tick work ceiling divided in the declared
    proportions, so the sweep asks whether the two items compete for one drive channel or
    occupy independent lanes without changing anything else about the loop.
    """

    declared_splits = tuple(
        tuple(float(weight) for weight in split)
        for split in (
            splits if splits is not None else config.capacity_split_weights
        )
    )
    items = (int(config.headline_item_index), int(config.capacity_item_index))
    samples = tuple(int(t) for t in config.long_horizon_sample_ticks)
    return tuple(
        LoopArm(
            capacity_split_arm_name(split),
            items,
            gain=float(gain),
            family="capacity-split",
            phase_degrees=float(config.neutral_gain_phase_degrees),
            horizon_ticks=int(config.long_horizon_ticks),
            sample_ticks=samples,
            drive_items=items,
            drive_split=split,
            telemetry=True,
            regime="flat",
        )
        for split in declared_splits
    )


def quiet_regime_hold_arm_name(item: str) -> str:
    """The declared arm name of the single-item hold on one declared quiet-regime item."""

    return f"flat-quiet-hold-{item}"


def quiet_regime_gain_arm_name(factor: float) -> str:
    """The declared arm name of the hold at one declared multiple of the neutral gain."""

    return f"flat-quiet-gain-x{float(factor):g}"


def quiet_regime_arm_declarations(
    config: FeedbackConfig, gain: float
) -> tuple[LoopArm, ...]:
    """The declared quiet-regime legs: further items held, and the declared gain ladder.

    The declared single-item hold is repeated on each declared further item at the flat
    profile's own measured neutral gain, and re-run on the headline item at the declared
    multiples of that gain, so the receipt can separate a property of the profile from a
    property of the gain by its own numbers.
    """

    headline = int(config.headline_item_index)
    samples = tuple(int(t) for t in config.long_horizon_sample_ticks)
    names = [spec.name for spec in durability.ITEM_SPECS]
    arms: list[LoopArm] = []
    # The headline item's own single-item frame is declared here as well, so every declared
    # quiet-regime hold writes exactly the one item it holds and the three holds are read on
    # the same construction rather than against the two-item capacity frame.
    for item in (names[headline], *config.quiet_regime_items):
        index = names.index(item)
        arms.append(
            LoopArm(
                quiet_regime_hold_arm_name(item),
                (index,),
                gain=float(gain),
                family="quiet-regime",
                phase_degrees=float(config.neutral_gain_phase_degrees),
                horizon_ticks=int(config.long_horizon_ticks),
                sample_ticks=samples,
                measure_item_index=int(index),
                telemetry=True,
                regime="flat",
            )
        )
    for factor in config.quiet_regime_gain_factors:
        arms.append(
            LoopArm(
                quiet_regime_gain_arm_name(factor),
                (headline,),
                gain=float(gain) * float(factor),
                family="quiet-regime",
                phase_degrees=float(config.neutral_gain_phase_degrees),
                horizon_ticks=int(config.long_horizon_ticks),
                sample_ticks=samples,
                telemetry=True,
                regime="flat",
            )
        )
    return tuple(arms)


def capacity_arm_declarations(config: FeedbackConfig, gain: float) -> tuple[LoopArm, ...]:
    """The declared capacity family on the headline item and the declared second item."""

    headline = int(config.headline_item_index)
    second = int(config.capacity_item_index)
    items = (headline, second)
    samples = tuple(int(t) for t in config.long_horizon_sample_ticks)
    return (
        LoopArm(
            "capacity-two-item-no-loop",
            items,
            family="capacity",
            horizon_ticks=int(config.long_horizon_ticks),
            sample_ticks=samples,
            regime="amplifying",
        ),
        LoopArm(
            "capacity-locked-on-headline",
            items,
            gain=float(gain),
            family="capacity",
            phase_degrees=float(config.neutral_gain_phase_degrees),
            horizon_ticks=int(config.long_horizon_ticks),
            sample_ticks=samples,
            drive_items=(headline,),
            regime="amplifying",
        ),
        LoopArm(
            "capacity-two-item-loop",
            items,
            gain=float(gain),
            family="capacity",
            phase_degrees=float(config.neutral_gain_phase_degrees),
            horizon_ticks=int(config.long_horizon_ticks),
            sample_ticks=samples,
            drive_items=items,
            regime="amplifying",
        ),
        # The declared per-item reference loop: the same declared setting and the same
        # two written items, but the loop reads back on the second item alone, so the
        # shared scheme's effect on that item is separated from that item's own
        # maintainability at this setting.
        LoopArm(
            "capacity-second-item-only-loop",
            items,
            gain=float(gain),
            family="capacity",
            phase_degrees=float(config.neutral_gain_phase_degrees),
            horizon_ticks=int(config.long_horizon_ticks),
            sample_ticks=samples,
            drive_items=(second,),
            measure_item_index=int(second),
            telemetry=True,
            regime="amplifying",
        ),
        # The declared diagnosis twin of the shared two-item loop: the same declared
        # settings with per-tick drive telemetry, which changes nothing about the physics
        # (its measured series is required to equal the untracked arm's exactly) and
        # reports what each item's lane actually received.
        LoopArm(
            "capacity-two-item-telemetry",
            items,
            gain=float(gain),
            family="capacity",
            phase_degrees=float(config.neutral_gain_phase_degrees),
            horizon_ticks=int(config.long_horizon_ticks),
            sample_ticks=samples,
            drive_items=items,
            telemetry=True,
            regime="amplifying",
        ),
        # The declared time-multiplexed schemes: one declared item per tick, on a
        # declared cycle, with the whole per-tick ceiling spent on that item.
        LoopArm(
            "capacity-alternate-adjacent",
            items,
            gain=float(gain),
            family="capacity",
            phase_degrees=float(config.neutral_gain_phase_degrees),
            horizon_ticks=int(config.long_horizon_ticks),
            sample_ticks=samples,
            drive_items=items,
            drive_cycle=(0, 1),
            telemetry=True,
            regime="amplifying",
        ),
        LoopArm(
            "capacity-alternate-block",
            items,
            gain=float(gain),
            family="capacity",
            phase_degrees=float(config.neutral_gain_phase_degrees),
            horizon_ticks=int(config.long_horizon_ticks),
            sample_ticks=samples,
            drive_items=items,
            drive_cycle=tuple(
                [0] * int(config.capacity_alternate_block_ticks)
                + [1] * int(config.capacity_alternate_block_ticks)
            ),
            telemetry=True,
            regime="amplifying",
        ),
        # The declared per-item scheme: each item read back through its own direction
        # and its own declared phase reference, so the two drives are not forced into one
        # sign convention.
        LoopArm(
            "capacity-phase-locked-per-item",
            items,
            gain=float(gain),
            family="capacity",
            phase_degrees=float(config.neutral_gain_phase_degrees),
            horizon_ticks=int(config.long_horizon_ticks),
            sample_ticks=samples,
            drive_items=items,
            phase_locked=True,
            telemetry=True,
            regime="amplifying",
        ),
    )


def genericity_arm_declarations(config: FeedbackConfig, gain: float) -> tuple[LoopArm, ...]:
    """The declared genericity family: the declared setting on each declared item."""

    arms: list[LoopArm] = []
    for index in config.genericity_item_indices:
        name = durability.ITEM_SPECS[index].name
        arms.append(
            LoopArm(
                f"genericity-{name}-loop",
                (index,),
                gain=float(gain),
                family="genericity",
                phase_degrees=float(config.neutral_gain_phase_degrees),
                measure_item_index=int(index),
            )
        )
        arms.append(
            LoopArm(
                f"genericity-{name}-no-loop",
                (index,),
                family="genericity",
                measure_item_index=int(index),
            )
        )
    return tuple(arms)


def arm_write_work(config: FeedbackConfig, item_indices: Sequence[int]) -> float:
    """The declared total work budget of writing the arm's items."""

    return float(config.write_budget) * len(item_indices)


def write_direction(captures: Sequence[Mapping[str, Any]], index: int) -> np.ndarray:
    return np.asarray(captures[index]["direction"], dtype=np.float64)


def item_reference_deposit(
    captures: Sequence[Mapping[str, Any]],
    item_deposits: Mapping[str, float],
    index: int,
) -> float:
    """The retention denominator of one declared item: measured in-arm, else declared.

    A written item is measured inside the arm; an item the arm did not write keeps
    the declared isolated-write deposit, which is the durability harness's own
    disturbance convention.
    """

    name = durability.ITEM_SPECS[index].name
    if name in item_deposits:
        return float(item_deposits[name])
    return float(captures[index]["deposited_energy"])


def write_items(
    config: FeedbackConfig,
    item_indices: Sequence[int],
    profile: ResonantProfile | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Write the arm's declared items and measure each deposit inside the arm."""

    workspace = initial_workspace(profile or ResonantProfile())
    writes: list[dict[str, Any]] = []
    deposits: dict[str, float] = {}
    for index in item_indices:
        spec = durability.ITEM_SPECS[index]
        before = durability.read_frame(workspace, config.read_frame_path)
        workspace, receipt = durability.write_item(workspace, spec, config.write_budget)
        after = durability.read_frame(workspace, config.read_frame_path)
        writes.append({"item": spec.name, **receipt})
        deposits[spec.name] = durability.squared_norm(after - before)
    return workspace, {"writes": writes, "deposits": deposits}


def apply_drive(
    workspace: Any,
    item_index: int,
    amplitude: float,
    drive_work: float,
) -> tuple[Any, dict[str, Any]]:
    """Apply the declared packet impulse for one item at a declared amplitude and work."""

    spec = durability.ITEM_SPECS[item_index]
    return apply_helical_packet_impulse(
        workspace,
        path=spec.path,
        component=spec.component,
        flow_signal=[float(amplitude), 0.0],
        work_budget=float(drive_work),
        evidence_tick=workspace.evidence_tick,
        event_kind=EVENT_KIND,
    )


def loop_amplitude(config: FeedbackConfig, gain: float, ratio: float) -> tuple[float, bool]:
    """The declared bounded drive amplitude and whether the amplitude clip fired."""

    raw = float(gain) * PER_TICK_DECAY * float(ratio)
    clipped = bool(raw > 1.0 or raw < -1.0)
    return float(max(-1.0, min(1.0, raw))), clipped


def sample_row(
    config: FeedbackConfig,
    captures: Sequence[Mapping[str, Any]],
    arm: LoopArm,
    workspace: Any,
    vector: np.ndarray,
    tick: int,
    item_deposits: Mapping[str, float],
    frame_energy_reference: float,
    signed_reference: float,
    drive: Mapping[str, Any],
) -> dict[str, Any]:
    """One declared sample: retention, energy, disturbance and ledger state."""

    energy = durability.squared_norm(vector)
    shares = {
        capture["name"]: durability.share_along(
            vector, capture["direction"], capture["deposited_energy"]
        )
        for capture in captures
    }
    unwritten = [index for index in range(len(captures)) if index not in set(arm.item_indices)]
    frame_total = sum(
        float(np.dot(vector, capture["direction"])) ** 2 for capture in captures
    )
    headline_index = config.headline_item_index
    measured_index = int(arm.measure_item_index)
    return {
        "tick": int(tick),
        "field_ticks": int(workspace.field_ticks),
        "activity": float(workspace.activity),
        "heartbeat_phase": float(workspace.heartbeat_phase),
        "breath_phase": float(workspace.breath_phase),
        "packet_energy": energy,
        "frame_energy_ratio": energy / frame_energy_reference,
        "alignment_retention": durability.share_along(
            vector,
            captures[headline_index]["direction"],
            item_reference_deposit(captures, item_deposits, headline_index),
        ),
        "measure_retention": durability.share_along(
            vector,
            captures[measured_index]["direction"],
            item_reference_deposit(captures, item_deposits, measured_index),
        ),
        "signed_projection_ratio": float(np.dot(vector, captures[headline_index]["direction"]))
        / signed_reference,
        "item_retention": {
            durability.ITEM_SPECS[index].name: durability.share_along(
                vector,
                captures[index]["direction"],
                item_deposits[durability.ITEM_SPECS[index].name],
            )
            for index in arm.item_indices
        },
        "item_shares": shares,
        "unwritten_max_share": max(
            (shares[captures[index]["name"]] for index in unwritten), default=None
        ),
        "declared_frame_projection_fraction": frame_total / energy if energy > 0.0 else None,
        "drive_amplitude": float(drive["amplitude"]),
        "drive_work_this_tick": float(drive["work"]),
        "drive_clipped": bool(drive["clipped"]),
        "drive_accepted": bool(drive["accepted"]),
        "drive_work_cumulative": float(drive["work_cumulative"]),
        "ledger": {key: float(value) for key, value in sorted(workspace.ledger.items())},
        "state_sha256": workspace.state_sha256,
        "page_sha256": durability.page_sha256(workspace),
    }


def arm_profile(
    arm: LoopArm, profile: ResonantProfile | None = None
) -> ResonantProfile:
    """The declared profile of one arm: the declared profile, or its beta override."""

    base = profile or ResonantProfile()
    if arm.profile_beta is None:
        return base
    return replace(base, beta=float(arm.profile_beta))


def run_stream(
    config: FeedbackConfig,
    captures: Sequence[Mapping[str, Any]],
    arm: LoopArm,
    phase_reference: Mapping[str, Any] | None = None,
    profile: ResonantProfile | None = None,
    phase_references: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write the arm's items, then advance the page tick by tick with the declared drive.

    ``phase_reference`` is the declared single read-back the shared loop uses (the
    measured item's own); ``phase_references`` maps each driven item to its own declared
    read-back and is what the declared per-item scheme uses, so each item is driven
    against its own projection instead of one shared sign convention.
    """

    arm_base = arm_profile(arm, profile)
    profile_beta = float(arm_base.beta)
    workspace, written = write_items(config, arm.item_indices, arm_base)
    deposits = written["deposits"]
    post_write = durability.read_frame(workspace, config.read_frame_path)
    frame_energy_reference = durability.squared_norm(post_write)
    headline_index = config.headline_item_index
    headline_name = durability.ITEM_SPECS[headline_index].name
    measure_index = int(arm.measure_item_index)
    driven_items = tuple(int(i) for i in (arm.drive_items or (measure_index,)))
    per_item_work = float(config.loop_work_ceiling) * abs(0.0)
    direction = write_direction(captures, measure_index)
    signed_reference = float(np.dot(post_write, direction))
    if not signed_reference:
        raise ValueError(
            "the measured item's post-write projection is zero, so the declared loop "
            "has no read-back reference"
        )
    drive_cycle = tuple(int(position) for position in arm.drive_cycle)
    driven_directions = {
        index: write_direction(captures, index) for index in driven_items
    }
    driven_references = {
        index: float(np.dot(post_write, driven_directions[index]))
        for index in driven_items
    }
    for index, reference in driven_references.items():
        if not reference:
            raise ValueError(
                f"the declared driven item {durability.ITEM_SPECS[index].name} has a "
                "zero post-write projection, so a per-item read-back cannot normalise it"
            )
    if arm.phase_locked and not phase_references:
        raise ValueError(
            "a declared per-item read-back needs the declared per-item phase references"
        )
    # The declared reference each driven item's own signal is expressed in. The shared
    # loop keeps the single read-back's in-arm units (the measured item's post-write
    # projection, exactly as every earlier arm uses). The declared per-item scheme uses
    # each item's own isolated-write projection, so that item's in-phase and quadrature
    # terms are both in that item's own declared units and neither carries the other
    # item's write. The combined post-write projections are still reported beside them,
    # so the declared choice is visible.
    live_references = {
        index: (
            float(phase_references[index]["isolated_signed_projection"])
            if arm.phase_locked and phase_references
            else float(driven_references[index])
        )
        for index in driven_items
    }
    if arm.phase_locked and any(not value for value in live_references.values()):
        raise ValueError(
            "a declared per-item read-back reference is zero, so its signal is undefined"
        )
    # The declared drive split: the declared per-tick work ceiling divided between the
    # driven items in the declared proportions, with the loop's own read-back scalar
    # applied to each item in every split. The declared proportions are normalised over
    # whichever items a tick's schedule actually drives, so a multiplexed arm still
    # spends the whole declared ceiling on the one item it drives.
    drive_split = (
        tuple(float(weight) for weight in arm.drive_split)
        if arm.drive_split is not None
        else None
    )
    split_by_index = (
        {
            index: drive_split[position]
            for position, index in enumerate(driven_items)
        }
        if drive_split is not None
        else None
    )
    # The per-tick quadrature read-out of every driven item, when the arm was given each
    # driven item's own declared quadrature reference: the in-phase and quadrature
    # components of that item's own signal are what a per-tick relative phase between two
    # driven items is computed from, so it is measured rather than inferred.
    driven_quadrature = {
        index: (
            phase_references[index]["direction"],
            float(phase_references[index]["scale"]),
        )
        for index in driven_items
        if phase_references and index in phase_references
    }
    write_shares = {
        durability.ITEM_SPECS[index].name: durability.share_along(
            post_write,
            captures[index]["direction"],
            deposits[durability.ITEM_SPECS[index].name],
        )
        for index in arm.item_indices
    }
    post_write_block = {
        "state_sha256": workspace.state_sha256,
        "page_sha256": durability.page_sha256(workspace),
        "packet_energy": frame_energy_reference,
        "field_ticks": int(workspace.field_ticks),
        "activity": float(workspace.activity),
        "signed_projection": signed_reference,
        "signed_projection_measured_item": durability.ITEM_SPECS[measure_index].name,
        "write_shares": write_shares,
    }
    horizon_ticks = (
        int(arm.horizon_ticks) if int(arm.horizon_ticks) else int(config.horizon_ticks)
    )
    sample_ticks = tuple(int(t) for t in (arm.sample_ticks or config.sample_ticks))
    rows: list[dict[str, Any]] = []
    drive_calls = 0
    drive_accepted = 0
    drive_clipped = 0
    drive_work_total = 0.0
    drive_work_max = 0.0
    amplitude_max = 0.0
    energy_ratio_max = 1.0
    # Per-item drive aggregates, counted by the loop itself rather than read off the
    # retained telemetry: an arm without per-tick rows still reports which items its
    # schedule drove, how often and with how much work.
    scheduled_ticks: dict[int, int] = {}
    applied_work_by_item: dict[int, float] = {}
    amplitude_max_by_item: dict[int, float] = {}
    telemetry_rows: list[dict[str, Any]] = []
    for tick in range(1, horizon_ticks + 1):
        workspace, _advance = advance_workspace(
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
        if arm.refresh_interval and tick % arm.refresh_interval == 0:
            for index in arm.item_indices:
                workspace, receipt = apply_drive(
                    workspace, index, 1.0, float(config.write_budget)
                )
                vector = durability.read_frame(workspace, config.read_frame_path)
                drive_calls += 1
                drive_accepted += int(receipt["accepted"])
                drive_work_total += float(receipt["applied_work"])
                drive_work_max = max(drive_work_max, float(receipt["applied_work"]))
                amplitude_max = max(amplitude_max, 1.0)
                drive = {
                    "amplitude": 1.0,
                    "work": float(receipt["applied_work"]),
                    "work_cumulative": drive_work_total,
                    "clipped": False,
                    "accepted": bool(receipt["accepted"]),
                }
        if arm.gain:
            # The declared per-tick schedule: a declared cycle drives exactly the one
            # item it names on this tick, so the declared per-tick work ceiling is spent
            # on that item; an arm with no declared cycle drives every driven item and
            # splits the same ceiling between them.
            scheduled = (
                (driven_items[drive_cycle[(tick - 1) % len(drive_cycle)]],)
                if drive_cycle
                else driven_items
            )
            readings = {
                index: float(np.dot(vector, driven_directions[index]))
                / live_references[index]
                for index in driven_items
            }
            telemetry_row = (
                {
                    "tick": int(tick),
                    "scheduled": [durability.ITEM_SPECS[i].name for i in scheduled],
                    "ratio_before": {
                        durability.ITEM_SPECS[i].name: float(readings[i])
                        for i in driven_items
                    },
                    "quadrature_before": {},
                    "amplitude": {},
                    "applied_work": {},
                    "clipped": {},
                    "increment": {},
                    "cross_increment": {},
                    "share_before": {},
                    "share_after": {},
                    "frame_energy_ratio": float(
                        durability.squared_norm(vector) / frame_energy_reference
                    ),
                    "work_this_tick": 0.0,
                }
                if arm.telemetry
                else None
            )
            if telemetry_row is not None and driven_quadrature:
                for index in driven_items:
                    direction_i, scale_i = driven_quadrature[index]
                    telemetry_row["quadrature_before"][
                        durability.ITEM_SPECS[index].name
                    ] = float(np.dot(vector, direction_i)) / scale_i
            tick_work = 0.0
            tick_accepted = True
            tick_clipped = False
            tick_amplitudes: dict[int, float] = {}
            if arm.phase_locked:
                # The declared per-item scheme reads every scheduled item back through
                # that item's own direction and phase reference, so each item's drive
                # follows its own signal.
                drive_plan = []
                for driven in scheduled:
                    ratio = phase_signal(
                        config,
                        arm,
                        vector,
                        driven_directions[driven],
                        live_references[driven],
                        phase_references[driven] if phase_references else None,
                    )
                    amplitude, clipped = loop_amplitude(config, arm.gain, ratio)
                    drive_plan.append((driven, amplitude, clipped))
            else:
                # The declared shared scheme reads back once, on the measured item, and
                # applies that one signed amplitude to every scheduled item: the signal
                # is taken from the vector before any of this tick's drives.
                ratio = phase_signal(
                    config, arm, vector, direction, signed_reference, phase_reference
                )
                amplitude, clipped = loop_amplitude(config, arm.gain, ratio)
                drive_plan = [
                    (driven, amplitude, clipped) for driven in scheduled
                ]
            scheduled_split_total = (
                sum(split_by_index[driven] for driven, _a, _c in drive_plan)
                if split_by_index is not None
                else float(len(drive_plan))
            )
            for driven, amplitude, clipped in drive_plan:
                item_name = durability.ITEM_SPECS[driven].name
                share = (
                    split_by_index[driven] / scheduled_split_total
                    if split_by_index is not None
                    else 1.0 / len(drive_plan)
                )
                per_item_work = float(config.loop_work_ceiling) * abs(amplitude) * share
                before = vector
                workspace, receipt = apply_drive(
                    workspace, driven, amplitude, per_item_work
                )
                vector = durability.read_frame(workspace, config.read_frame_path)
                drive_calls += 1
                drive_accepted += int(receipt["accepted"])
                tick_accepted = tick_accepted and bool(receipt["accepted"])
                tick_work += float(receipt["applied_work"])
                tick_clipped = tick_clipped or clipped
                tick_amplitudes[driven] = float(amplitude)
                scheduled_ticks[driven] = scheduled_ticks.get(driven, 0) + 1
                applied_work_by_item[driven] = applied_work_by_item.get(
                    driven, 0.0
                ) + float(receipt["applied_work"])
                amplitude_max_by_item[driven] = max(
                    amplitude_max_by_item.get(driven, 0.0), abs(float(amplitude))
                )
                if telemetry_row is not None:
                    telemetry_row["amplitude"][item_name] = float(amplitude)
                    telemetry_row["applied_work"][item_name] = float(
                        receipt["applied_work"]
                    )
                    telemetry_row["clipped"][item_name] = bool(clipped)
                    telemetry_row["increment"][item_name] = (
                        float(np.dot(vector, driven_directions[driven]))
                        - float(np.dot(before, driven_directions[driven]))
                    ) / live_references[driven]
                    # The cross-projection: what this one drive call did to every other
                    # driven item's own lane, measured around the same call.
                    for other in driven_items:
                        if other == driven:
                            continue
                        # Keyed by the driving item: several items are driven on the same
                        # tick, and each call's reading of the other lanes must survive.
                        telemetry_row["cross_increment"][
                            f"{item_name}->{durability.ITEM_SPECS[other].name}"
                        ] = (
                            float(np.dot(vector, driven_directions[other]))
                            - float(np.dot(before, driven_directions[other]))
                        ) / live_references[other]
                    telemetry_row["share_before"][item_name] = durability.share_along(
                        before, driven_directions[driven], deposits[item_name]
                    )
                    telemetry_row["share_after"][item_name] = durability.share_along(
                        vector, driven_directions[driven], deposits[item_name]
                    )
            tick_amplitude = tick_amplitudes.get(
                measure_index,
                sum(tick_amplitudes.values()) / len(tick_amplitudes),
            )
            if telemetry_row is not None:
                telemetry_row["ratio_after"] = {
                    durability.ITEM_SPECS[index].name: (
                        float(np.dot(vector, driven_directions[index]))
                        / live_references[index]
                    )
                    for index in driven_items
                }
                if driven_quadrature:
                    telemetry_row["quadrature_after"] = {}
                    for index in driven_items:
                        direction_i, scale_i = driven_quadrature[index]
                        telemetry_row["quadrature_after"][
                            durability.ITEM_SPECS[index].name
                        ] = float(np.dot(vector, direction_i)) / scale_i
                telemetry_row["work_this_tick"] = float(tick_work)
                telemetry_row["frame_energy_ratio_after"] = float(
                    durability.squared_norm(vector) / frame_energy_reference
                )
                telemetry_rows.append(telemetry_row)
            drive_clipped += int(tick_clipped)
            drive_work_total += tick_work
            drive_work_max = max(drive_work_max, tick_work)
            amplitude_max = max(
                amplitude_max, max(abs(value) for value in tick_amplitudes.values())
            )
            drive = {
                "amplitude": float(tick_amplitude),
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
                sample_row(
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
    ledger = {key: float(value) for key, value in sorted(workspace.ledger.items())}
    horizon = rows[-1]
    mid = next(row for row in rows if row["tick"] == horizon_ticks // 2)
    last_half = [row for row in rows if row["tick"] > horizon_ticks // 2]
    runaway = exceeds_runaway(config, energy_ratio_max)
    last_half_min = min(row["alignment_retention"] for row in last_half)
    measure_last_half_min = min(row["measure_retention"] for row in last_half)
    neutral = bool(
        not runaway
        and horizon["measure_retention"] >= float(config.neutral_level_floor)
        and measure_last_half_min >= float(config.neutral_level_floor)
        and horizon["measure_retention"]
        >= float(config.neutral_decay_tolerance) * mid["measure_retention"]
    )
    write_work = arm_write_work(config, arm.item_indices)
    return {
        "arm": arm.name,
        "declared": {
            "family": arm.family,
            "written_items": [
                durability.ITEM_SPECS[index].name for index in arm.item_indices
            ],
            "refresh_interval": int(arm.refresh_interval),
            "gain": float(arm.gain),
            "phase_degrees": float(arm.phase_degrees),
            "headline_item_index": int(config.headline_item_index),
            "measure_item_index": int(arm.measure_item_index),
            "measured_item": durability.ITEM_SPECS[int(arm.measure_item_index)].name,
            "loop_work_ceiling": float(config.loop_work_ceiling),
            "horizon_ticks": horizon_ticks,
            "samples": list(sample_ticks),
            "activity_demand": float(config.activity_demand),
            "source_enabled": bool(config.source_enabled),
            "write_budget": float(config.write_budget),
            "read_frame_path": config.read_frame_path,
            "profile_beta": profile_beta,
            "drive_item_index": int(measure_index),
            "drive_item": durability.ITEM_SPECS[measure_index].name,
            "drive_item_indices": [int(index) for index in driven_items],
            "drive_items": [
                durability.ITEM_SPECS[index].name for index in driven_items
            ],
            "drive_cycle": [int(position) for position in drive_cycle],
            "drive_cycle_items": (
                [
                    durability.ITEM_SPECS[driven_items[position]].name
                    for position in drive_cycle
                ]
                if drive_cycle
                else []
            ),
            "phase_locked": bool(arm.phase_locked),
            "telemetry": bool(arm.telemetry),
            "regime": arm.regime,
            "drive_reference_convention": (
                "each driven item's own isolated-write post-write projection, so that "
                "item's in-phase and quadrature terms share one declared unit"
                if arm.phase_locked
                else (
                    "the measured item's in-arm post-write projection, shared by every "
                    "driven item"
                    if len(driven_items) > 1
                    else "the driven item's in-arm post-write projection"
                )
            ),
            "drive_reference_values": {
                durability.ITEM_SPECS[index].name: float(live_references[index])
                for index in driven_items
            },
            "in_arm_post_write_projections": {
                durability.ITEM_SPECS[index].name: float(driven_references[index])
                for index in driven_items
            },
            "drive_work_split": (
                "one driven item" if len(driven_items) == 1
                else (
                    "declared per-tick cycle: one item per tick, the declared per-tick "
                    "loop work ceiling spent on that item"
                    if drive_cycle
                    else "per-tick loop work ceiling split equally between the driven items"
                )
            ),
            "drive_split": (
                [float(weight) for weight in drive_split]
                if drive_split is not None
                else None
            ),
            "drive_split_items": [
                durability.ITEM_SPECS[index].name for index in driven_items
            ],
            "drive_split_declared": (
                "the declared per-tick work ceiling divided between the driven items in "
                "these declared proportions, the loop's own read-back scalar applied to "
                "each item unchanged, so every declared split requests the same total work "
                "and the work applied per call is reported from the actuator's own receipt"
                if drive_split is not None
                else (
                    "no declared split: the declared per-tick work ceiling is divided "
                    "equally between the items a tick's schedule drives"
                )
            ),
            "scheduled_ticks": {
                durability.ITEM_SPECS[index].name: int(scheduled_ticks.get(index, 0))
                for index in driven_items
            },
            "applied_work_by_item": {
                durability.ITEM_SPECS[index].name: float(
                    applied_work_by_item.get(index, 0.0)
                )
                for index in driven_items
            },
            "mean_applied_work_per_item_per_tick": {
                durability.ITEM_SPECS[index].name: float(
                    applied_work_by_item.get(index, 0.0)
                )
                / float(horizon_ticks)
                for index in driven_items
            },
            "max_amplitude_by_item": {
                durability.ITEM_SPECS[index].name: float(
                    amplitude_max_by_item.get(index, 0.0)
                )
                for index in driven_items
            },
            "drive_read_back": (
                "per-item: each driven item read back through its own direction and its "
                "own declared phase reference"
                if arm.phase_locked
                else (
                    "shared: one read-back (the measured item's) drives every driven item"
                    if len(driven_items) > 1
                    else "one read-back on the driven item"
                )
            ),
            "drive": (
                "closed-loop read-back"
                if arm.gain
                else ("open-loop refresh" if arm.refresh_interval else "none")
            ),
        },
        **({"telemetry": telemetry_rows} if arm.telemetry else {}),
        "writes": written["writes"],
        "measured_deposit_energy": deposits,
        "deposit_attenuation": {
            name: deposits[name] / captures[index]["deposited_energy"]
            for index, name in (
                (index, durability.ITEM_SPECS[index].name) for index in arm.item_indices
            )
        },
        "post_write": post_write_block,
        "samples": rows,
        "horizon": {
            "tick": horizon_ticks,
            "alignment_retention": horizon["alignment_retention"],
            "mid_retention": mid["alignment_retention"],
            "last_half_min_retention": last_half_min,
            "last_half_retention_ratio": (
                horizon["alignment_retention"] / mid["alignment_retention"]
                if mid["alignment_retention"] > 0.0
                else None
            ),
            "packet_energy": horizon["packet_energy"],
            "frame_energy_ratio": horizon["frame_energy_ratio"],
            "frame_energy_ratio_max": energy_ratio_max,
            "item_retention": horizon["item_retention"],
            "unwritten_max_share": horizon["unwritten_max_share"],
            "unwritten_shares": {
                capture["name"]: horizon["item_shares"][capture["name"]]
                for capture in captures
                if capture["name"]
                not in {durability.ITEM_SPECS[index].name for index in arm.item_indices}
            },
            "declared_frame_projection_fraction": horizon[
                "declared_frame_projection_fraction"
            ],
            "state_sha256": horizon["state_sha256"],
            "page_sha256": horizon["page_sha256"],
        },
        "drive": {
            "calls": drive_calls,
            "accepted_calls": drive_accepted,
            "rejected_calls": drive_calls - drive_accepted,
            "clipped_ticks": drive_clipped,
            "max_amplitude": amplitude_max,
            "max_work_per_tick": drive_work_max,
            "drive_work_total": drive_work_total,
            "write_work_total": write_work,
            "drive_work_over_write_work": drive_work_total / write_work,
            "ledger_helical_packet_work": ledger.get("helical_packet_work"),
            "loop_work_ceiling": float(config.loop_work_ceiling),
        },
        "ledger": ledger,
        "ledger_check": {
            "balance_defect": ledger.get("balance_defect", 0.0),
            "balance_defect_within_allowance": bool(
                abs(ledger.get("balance_defect", 0.0))
                <= float(config.ledger_balance_allowance)
            ),
            "residual_work": ledger.get("residual_work", 0.0),
            "residual_work_within_allowance": bool(
                abs(ledger.get("residual_work", 0.0))
                <= float(config.ledger_residual_allowance)
            ),
            "positive_heartbeat_work": ledger.get("positive_heartbeat_work", 0.0),
            "extracted_heartbeat_work": ledger.get("extracted_heartbeat_work", 0.0),
            "dissipated_work": ledger.get("dissipated_work", 0.0),
            "balance_allowance": float(config.ledger_balance_allowance),
            "residual_allowance": float(config.ledger_residual_allowance),
        },
        "boundedness": {
            "energy_ratio_max": energy_ratio_max,
            "runaway": runaway,
            "runaway_energy_ratio": float(config.runaway_energy_ratio),
            "all_samples_finite": bool(
                all(
                    np.isfinite(row["packet_energy"])
                    and np.isfinite(row["alignment_retention"])
                    for row in rows
                )
            ),
        },
        "neutral_stability": {
            "neutrally_stable": neutral,
            "measured_item": durability.ITEM_SPECS[int(arm.measure_item_index)].name,
            "measure_retention_at_horizon": horizon["measure_retention"],
            "measure_mid_retention": mid["measure_retention"],
            "measure_last_half_min_retention": measure_last_half_min,
            "measure_last_half_retention_ratio": (
                horizon["measure_retention"] / mid["measure_retention"]
                if mid["measure_retention"] > 0.0
                else None
            ),
            "level_floor": float(config.neutral_level_floor),
            "decay_tolerance": float(config.neutral_decay_tolerance),
        },
        "final": {
            "state_sha256": workspace.state_sha256,
            "page_sha256": durability.page_sha256(workspace),
            "field_ticks": int(workspace.field_ticks),
            "chain": "full canonical page advanced one tick per call",
        },
    }


def drift_arm(config: FeedbackConfig) -> LoopArm:
    """The declared drift baseline: the headline item, no refresh and no loop."""

    return single_item_arm_declarations(config)[0]


def chunked_stream(config: FeedbackConfig, captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The same declared drift activity advanced in the durability harness's chunk gaps."""

    workspace, written = write_items(config, (config.headline_item_index,))
    headline = durability.ITEM_SPECS[config.headline_item_index].name
    deposit = written["deposits"][headline]
    rows: list[dict[str, Any]] = []
    previous = 0
    for tick in config.durability_samples:
        workspace, _advance = advance_workspace(
            workspace,
            ticks=int(tick) - previous,
            demand=config.activity_demand,
            source_enabled=config.source_enabled,
        )
        previous = int(tick)
        vector = durability.read_frame(workspace, config.read_frame_path)
        rows.append(
            {
                "tick": int(tick),
                "alignment_retention": durability.share_along(
                    vector,
                    captures[config.headline_item_index]["direction"],
                    deposit,
                ),
                "page_sha256": durability.page_sha256(workspace),
                "state_sha256": workspace.state_sha256,
            }
        )
    return {
        "chunks": [
            int(tick) - int(previous)
            for previous, tick in zip(
                (0, *config.durability_samples[:-1]), config.durability_samples
            )
        ],
        "rows": rows,
    }


def stream_identity_block(config: FeedbackConfig, captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Identity of the one-tick stream against the durability harness's chunked stream."""

    streamed = run_stream(config, captures, drift_arm(config))
    chunked = chunked_stream(config, captures)
    streamed_by_tick = {int(row["tick"]): row for row in streamed["samples"]}
    rows = [
        {
            "tick": int(chunk["tick"]),
            "one_tick_stream_retention": streamed_by_tick[int(chunk["tick"])][
                "alignment_retention"
            ],
            "one_tick_stream_page_sha256": streamed_by_tick[int(chunk["tick"])][
                "page_sha256"
            ],
            "chunked_page_sha256": chunk["page_sha256"],
            "page_digest_identical": (
                streamed_by_tick[int(chunk["tick"])]["page_sha256"]
                == chunk["page_sha256"]
            ),
        }
        for chunk in chunked["rows"]
    ]
    return {
        "chunked_advance_gaps": chunked["chunks"],
        "declared_identity": (
            "the declared one-tick stream (one advance_workspace call per tick) and the "
            "durability harness's chunked stream (one call per declared chunk gap) reach "
            "the same page at every declared chunk sample, so the loop's per-tick calling "
            "convention is the harness's own trajectory"
        ),
        "rows": rows,
        "identity_allowance": CITED_AGREEMENT_ALLOWANCE,
        "identical_at_every_sample": all(row["page_digest_identical"] for row in rows),
        "stream_final_page_sha256": streamed["final"]["page_sha256"],
        "chunked_final_page_sha256": chunked["rows"][-1]["page_sha256"],
    }


def cited_agreement(body: Mapping[str, Any]) -> dict[str, Any]:
    """The drift arm's figures beside the figures cited from the durability receipt."""

    drift = body["arms"]["drift-no-refresh-no-loop"]
    rows = []
    for tick, cited in CITED_SOURCE_OFF_RETENTION.items():
        sample = next(row for row in drift["samples"] if row["tick"] == tick)
        measured = sample["alignment_retention"]
        difference = measured - cited
        rows.append(
            {
                "tick": int(tick),
                "cited_source_off_retention": cited,
                "measured_drift_retention": measured,
                "difference": difference,
                "agrees_within_allowance": bool(abs(difference) <= CITED_AGREEMENT_ALLOWANCE),
            }
        )
    horizon = next(
        row
        for row in drift["samples"]
        if row["tick"] == max(CITED_SOURCE_OFF_RETENTION)
    )
    energy_difference = (
        horizon["frame_energy_ratio"] - CITED_SOURCE_OFF_ENERGY_RETENTION_AT_HORIZON
    )
    return {
        "source_receipt": CITED_RECEIPT,
        "rows": rows,
        "energy_row": {
            "cited_source_off_energy_retention": CITED_SOURCE_OFF_ENERGY_RETENTION_AT_HORIZON,
            "measured_drift_energy_retention": horizon["frame_energy_ratio"],
            "difference": energy_difference,
            "agrees_within_allowance": bool(
                abs(energy_difference) <= CITED_AGREEMENT_ALLOWANCE
            ),
        },
        "also_cited_not_recomputed": {
            "source_on_retention_at_horizon": CITED_SOURCE_ON_RETENTION_AT_HORIZON,
            "source_on_energy_retention_at_horizon": CITED_SOURCE_ON_ENERGY_RETENTION_AT_HORIZON,
            "source_state_read_tick_recovery_difference": (
                CITED_SOURCE_ON_RETENTION_AT_HORIZON
                - CITED_SOURCE_OFF_RETENTION[max(CITED_SOURCE_OFF_RETENTION)]
            ),
        },
        "agreement_allowance": CITED_AGREEMENT_ALLOWANCE,
        "all_rows_agree": bool(
            all(row["agrees_within_allowance"] for row in rows)
            and abs(energy_difference) <= CITED_AGREEMENT_ALLOWANCE
        ),
    }


def declared_problem(config: FeedbackConfig) -> ResonantProblem:
    """A declared two-port objective for the transceiver recon probe only."""

    return ResonantProblem(
        variable_ids=("feedback-in", "feedback-out"),
        precision=np.eye(2, dtype=np.float64),
    )


def transceiver_probe(config: FeedbackConfig, profile: ResonantProfile, label: str) -> dict[str, Any]:
    """Condense one bound workspace of the declared profile, then chain output back to input."""

    problem = declared_problem(config)
    workspace, _written = write_items(
        config, (config.headline_item_index,), profile
    )
    page_before = durability.page_sha256(workspace)
    bound = bind_workspace(workspace, problem)
    kernel, working, receipt = condense_workspace(
        bound,
        problem,
        input_ids=("feedback-in",),
        output_ids=("feedback-out",),
        rank=int(config.recon_rank),
        error_allowance=float(config.recon_error_allowance),
        input_bound=float(config.recon_input_bound),
        horizon_ticks=int(config.horizon_ticks),
    )
    chained: list[dict[str, Any]] = []
    values: list[float] = []
    inputs = {"feedback-in": float(config.recon_input)}
    for tick in range(1, int(config.recon_ticks) + 1):
        working, advance = advance_transceiver(kernel, working, inputs=inputs, ticks=1)
        value = float(advance["values"]["feedback-out"])
        values.append(value)
        chained.append(
            {
                "tick": tick,
                "input": float(inputs["feedback-in"]),
                "output": value,
                "mode": advance["mode"],
                "status": advance["status"],
                "error_bound": float(advance["error_bound"]),
                "counts": advance["counts"],
                "carried_ticks": int(working["ticks"]),
            }
        )
        inputs = {"feedback-in": value}
    constant_two_ticks = advance_transceiver(
        kernel,
        reset_transceiver(kernel),
        inputs={"feedback-in": float(config.recon_input)},
        ticks=2,
    )
    constant_two_ticks_value = float(constant_two_ticks[1]["values"]["feedback-out"])
    first = advance_transceiver(
        kernel,
        reset_transceiver(kernel),
        inputs={"feedback-in": float(config.recon_input)},
        ticks=1,
    )[0]
    second_same = advance_transceiver(
        kernel, first, inputs={"feedback-in": float(config.recon_input)}, ticks=1
    )[1]
    first = advance_transceiver(
        kernel,
        reset_transceiver(kernel),
        inputs={"feedback-in": float(config.recon_input)},
        ticks=1,
    )[0]
    second_other = advance_transceiver(
        kernel,
        first,
        inputs={"feedback-in": float(config.recon_input_alternate)},
        ticks=1,
    )[1]
    two_ticks_other = advance_transceiver(
        kernel,
        reset_transceiver(kernel),
        inputs={"feedback-in": float(config.recon_input_alternate)},
        ticks=2,
    )[1]
    constant_chains: dict[str, list[float]] = {}
    for value in (0.0, float(config.recon_input_alternate)):
        chain_values: list[float] = []
        chain_state = reset_transceiver(kernel)
        for _ in range(int(config.recon_ticks)):
            chain_state, tick_receipt = advance_transceiver(
                kernel, chain_state, inputs={"feedback-in": value}, ticks=1
            )
            chain_values.append(float(tick_receipt["values"]["feedback-out"]))
        constant_chains[repr(float(value))] = chain_values
    chain_letters = list(constant_chains.values())
    chain_difference = max(
        abs(left - right)
        for left, right in zip(chain_letters[0], chain_letters[1])
    )
    chain_magnitude = max(
        abs(value) for chain in chain_letters for value in chain
    )
    input_outputs = {}
    for value in config.recon_input_scan:
        _next, scan = advance_transceiver(
            kernel,
            reset_transceiver(kernel),
            inputs={"feedback-in": float(value)},
            ticks=1,
        )
        input_outputs[repr(float(value))] = float(scan["values"]["feedback-out"])
    scan_values = list(input_outputs.values())
    spread = max(scan_values) - min(scan_values)
    magnitude = max(abs(value) for value in scan_values)
    envelope_error = ""
    try:
        advance_transceiver(
            kernel,
            reset_transceiver(kernel),
            inputs={"feedback-in": float(config.recon_input_bound) + 1.0},
            ticks=1,
        )
    except ResonantNumericalError as error:
        envelope_error = str(error)
    return {
        "label": label,
        "profile_beta": float(profile.beta),
        "kernel_status": kernel["status"],
        "kernel_reason": kernel["reason"],
        "kernel_rank": int(kernel["rank"]),
        "kernel_dimensions": dict(kernel["dimensions"]),
        "kernel_certificate_available": bool(kernel["certificate"]["available"]),
        "condensation_receipt_mode": receipt["mode"],
        "working_state_mode": working["mode"],
        "working_state_keys": sorted(working),
        "chained_ticks": chained,
        "chained_outputs": values,
        "page_sha256_before_advance": page_before,
        "page_sha256_after_advance": durability.page_sha256(workspace),
        "page_unchanged_by_advance": durability.page_sha256(workspace) == page_before,
        "per_call_input_constant": {
            "two_ticks_constant_input": constant_two_ticks_value,
            "two_single_ticks_same_input": float(second_same["values"]["feedback-out"]),
            "two_single_ticks_second_input_alternate": float(
                second_other["values"]["feedback-out"]
            ),
            "two_ticks_alternate_input": float(two_ticks_other["values"]["feedback-out"]),
            "constant_call_equals_two_single_ticks": (
                constant_two_ticks_value
                == float(second_same["values"]["feedback-out"])
            ),
            "second_input_alternate_changes_the_value": (
                float(second_other["values"]["feedback-out"])
                != constant_two_ticks_value
            ),
        },
        "input_envelope": {
            "input_bound": float(config.recon_input_bound),
            "rejected_input": float(config.recon_input_bound) + 1.0,
            "raised": bool(envelope_error),
            "message": envelope_error,
        },
        "constant_input_chain_authority": {
            "declared": (
                "the declared number of one-tick calls from the kernel's own reset state, "
                "each call carrying the same declared input value; this measures whether "
                "the input channel can drive the output over a run at all, which is what "
                "a loop closed through this channel would need"
            ),
            "chains": constant_chains,
            "maximum_absolute_difference": chain_difference,
            "relative_difference": (
                chain_difference / chain_magnitude if chain_magnitude else None
            ),
            "authority_allowance": float(config.recon_authority_allowance),
            "input_drives_the_output_over_a_run": bool(
                (chain_difference / chain_magnitude if chain_magnitude else 0.0)
                > float(config.recon_authority_allowance)
            ),
        },
        "per_tick_input_authority": {
            "declared": (
                "one tick from the kernel's own reset state, with the declared input "
                "values; the output spread against the output magnitude measures how "
                "much authority the per-tick input has over the per-tick output"
            ),
            "inputs": [float(value) for value in config.recon_input_scan],
            "outputs": input_outputs,
            "spread": spread,
            "relative_spread": spread / magnitude if magnitude else None,
            "authority_allowance": float(config.recon_authority_allowance),
            "input_has_measurable_authority": bool(
                (spread / magnitude if magnitude else 0.0)
                > float(config.recon_authority_allowance)
            ),
        },
    }


def impulse_envelope_probe(config: FeedbackConfig) -> dict[str, Any]:
    """Measure the declared impulse envelope and its exact work balance."""

    workspace, written = write_items(config, (config.headline_item_index,))
    deposit = written["deposits"][durability.ITEM_SPECS[config.headline_item_index].name]
    _after, receipt = apply_drive(
        workspace, config.headline_item_index, 1.0, float(config.write_budget)
    )
    over_budget, under_budget = "", ""
    try:
        apply_drive(workspace, config.headline_item_index, 1.0, 1.5)
    except ResonantNumericalError as error:
        over_budget = str(error)
    try:
        apply_drive(workspace, config.headline_item_index, 1.0, -1e-3)
    except ResonantNumericalError as error:
        under_budget = str(error)
    return {
        "operation": (
            "apply_helical_packet_impulse(workspace, *, path, component, flow_signal, "
            "work_budget, evidence_tick, event_kind)"
        ),
        "declared_item_deposit_in_read_frame": deposit,
        "requested_work": float(receipt["requested_work"]),
        "applied_work": float(receipt["applied_work"]),
        "impulse_amount": float(receipt["impulse_amount"]),
        "balance_defect": float(receipt["balance_defect"]),
        "energy_roundoff_allowance": float(receipt["energy_roundoff_allowance"]),
        "work_equals_budget_within_allowance": bool(
            abs(float(receipt["applied_work"]) - float(receipt["requested_work"]))
            <= float(receipt["energy_roundoff_allowance"])
        ),
        "accepted_at_the_declared_budget": bool(receipt["accepted"]),
        "over_budget_rejected": bool(over_budget),
        "over_budget_message": over_budget,
        "under_budget_rejected": bool(under_budget),
        "under_budget_message": under_budget,
    }


def recon_block(config: FeedbackConfig, captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """What was looped, why the page is the looped object, and the transceiver contract."""

    profile = ResonantProfile()
    identity = stream_identity_block(config, captures)
    transceiver = [
        transceiver_probe(config, profile, "durability-profile"),
        transceiver_probe(config, ResonantProfile(beta=0.0), "declared-beta-zero-counterpart"),
    ]
    return {
        "canonical_advance": {
            "signature": (
                "advance_workspace(workspace, *, problem=None, ticks=1, demand=0.0, "
                "source_enabled=True, quiet=False, max_iterations=32, tolerance=None)"
            ),
            "per_tick_drive_argument": None,
            "read_from_source": (
                "cassi_resonant_field._advance accepts no per-tick external drive; the "
                "only bounded canonical write into the page is the helical packet impulse"
            ),
            "bounded_drive_operation": (
                "apply_helical_packet_impulse with work_budget in [0,1], a two-component "
                "flow signal that fixes the signed direction, and a recorded energy balance"
            ),
            "measured": impulse_envelope_probe(config),
            "period_chunking_identity": identity,
        },
        "full_page_loop": {
            "expressible_with_existing_operations": True,
            "used": True,
            "new_canonical_operations_added": [],
            "read_back": (
                "the declared read frame (the canonical packet coefficients of the whole "
                "balanced packet path), the same readout the durability receipt uses; "
                "the reduced realization is not used as the read-back in this receipt"
            ),
            "closing_path": (
                "one advance_workspace call of one tick per loop iteration, then one "
                "apply_helical_packet_impulse call whose flow signal is the declared "
                "bounded function of the read-back projection"
            ),
        },
        "transceiver": {
            "read_from_source": [
                "cassi_field_transceiver.advance_transceiver builds the input vector once "
                "per call (w = concatenate((u, [1.0])) before the tick loop) and applies it "
                "at every tick of that call, so per-tick-varying input needs one call per "
                "tick",
                "advance_transceiver rejects inputs whose magnitude plus uncertainty leaves "
                "the kernel's declared input_bound",
                "advance_transceiver returns next_state, and validate_transceiver accepts it "
                "as the next call's working state, so state carries across calls and the "
                "output of one call is available as the next call's input",
                "the condensed kernel advances its own coordinates: the reduced Krylov map "
                "when compact admission holds, otherwise the kernel's full AVF realization; "
                "the canonical page is read at condensation and is never advanced or written",
                "cassi_field_atlas.advance_transceivers routes declared source/target "
                "connections between transceiver ports with a one-tick delay "
                "(connection_delay_ticks 1), which is the owner-level surface for closing "
                "input from output; a receiving port must have exactly one driver and the "
                "connected variables must share kind, unit and frame",
            ],
            "measured": transceiver,
        },
        "reduced_versus_full": {
            "looped_here": "full canonical page",
            "reduced_realization_looped_here": False,
            "measured": {
                "kernel_statuses": {
                    probe["label"]: probe["kernel_status"] for probe in transceiver
                },
                "kernel_reasons": {
                    probe["label"]: probe["kernel_reason"] for probe in transceiver
                },
                "kernel_dimensions": {
                    probe["label"]: probe["kernel_dimensions"] for probe in transceiver
                },
                "working_state_modes": {
                    probe["label"]: probe["working_state_mode"] for probe in transceiver
                },
                "reduced_steps_per_call": {
                    probe["label"]: sorted(
                        {
                            int(tick["counts"]["reduced_steps"])
                            for tick in probe["chained_ticks"]
                        }
                    )
                    for probe in transceiver
                },
                "full_steps_per_call": {
                    probe["label"]: sorted(
                        {
                            int(tick["counts"]["full_steps"])
                            for tick in probe["chained_ticks"]
                        }
                    )
                    for probe in transceiver
                },
                "per_tick_input_relative_spread": {
                    probe["label"]: probe["per_tick_input_authority"]["relative_spread"]
                    for probe in transceiver
                },
                "input_has_measurable_authority": {
                    probe["label"]: probe["per_tick_input_authority"][
                        "input_has_measurable_authority"
                    ]
                    for probe in transceiver
                },
                "constant_input_chain_relative_difference": {
                    probe["label"]: probe["constant_input_chain_authority"][
                        "relative_difference"
                    ]
                    for probe in transceiver
                },
                "input_drives_the_output_over_a_run": {
                    probe["label"]: probe["constant_input_chain_authority"][
                        "input_drives_the_output_over_a_run"
                    ]
                    for probe in transceiver
                },
                "page_unchanged_by_transceiver_advance": {
                    probe["label"]: probe["page_unchanged_by_advance"]
                    for probe in transceiver
                },
            },
            "why": (
                "the durability receipt's written item is a canonical packet item whose "
                "workspace carries no bound problem, and condense_workspace needs ports "
                "inside a bound ResonantProblem; a condensation of that page would advance "
                "the kernel's own coordinates, so a reduced-realization loop would measure "
                "the condensed model rather than the page"
            ),
            "what_a_full_field_loop_through_the_transceiver_would_need": (
                "a canonical operation that writes an advanced transceiver realization "
                "state back into the page (or a transceiver whose state coordinates are the "
                "page's own); neither exists today, and neither was added here"
            ),
        },
    }


def select_best_stable_loop(arms: Mapping[str, Any]) -> LoopArm:
    """The declared rule for the best stable loop setting, applied to measured figures."""

    candidates = [
        row
        for row in arms.values()
        if row["declared"]["family"] in ("closed-loop", "closed-loop-saturation")
        and not row["boundedness"]["runaway"]
    ]
    if not candidates:
        raise RuntimeError("no declared loop arm stayed inside the boundedness criterion")
    best = max(
        candidates,
        key=lambda row: (row["horizon"]["alignment_retention"], -row["drive"]["drive_work_total"]),
    )
    return LoopArm(
        best["arm"],
        tuple(
            durability.ITEM_SPECS.index(spec)
            for spec in durability.ITEM_SPECS
            if spec.name in set(best["declared"]["written_items"])
        ),
        refresh_interval=int(best["declared"]["refresh_interval"]),
        gain=float(best["declared"]["gain"]),
        family="closed-loop",
    )


def separation_holds(difference: float, margin: float) -> bool:
    """The declared separation predicate: a measured difference against its margin."""

    return bool(float(difference) >= float(margin))


def exceeds_runaway(config: FeedbackConfig, energy_ratio_max: float) -> bool:
    """The declared boundedness predicate: the largest frame-energy ratio over the run."""

    return bool(
        not np.isfinite(energy_ratio_max)
        or float(energy_ratio_max) > float(config.runaway_energy_ratio)
    )


def selection_key(row: Mapping[str, Any]) -> str:
    """Which declared figure of an arm selects it inside its family."""

    if int(row["declared"]["measure_item_index"]) != int(
        row["declared"]["headline_item_index"]
    ):
        return (
            "measure_retention_at_horizon of the declared measured item "
            f"({row['declared']['measured_item']})"
        )
    return "alignment_retention at the horizon along the written direction"


def selection_retention(row: Mapping[str, Any]) -> float:
    """The declared selection figure of an arm: its measured item's horizon retention.

    For every family whose declared measured item is the headline item this is the
    headline alignment retention, so the declared non-detail families are selected
    exactly as before; a family measured on another declared item (the second
    refresh ladder) is selected on that item's own retention.
    """

    if int(row["declared"]["measure_item_index"]) != int(
        row["declared"]["headline_item_index"]
    ):
        return float(row["neutral_stability"]["measure_retention_at_horizon"])
    return float(row["horizon"]["alignment_retention"])


def family_best(
    body: Mapping[str, Any], family: str, *, positive_gain_only: bool = False
) -> dict[str, Any]:
    """The family's largest horizon retention and its work cost."""

    family_rows = [
        row for row in body["arms"].values() if row["declared"]["family"] == family
    ]
    rows = [
        row
        for row in family_rows
        if not positive_gain_only or row["declared"]["gain"] > 0.0
    ]
    if not rows:
        raise RuntimeError(f"no declared arm in family {family!r} matched the filter")
    best = max(rows, key=selection_retention)
    return {
        "arm": best["arm"],
        "gain": best["declared"]["gain"],
        "phase_degrees": best["declared"]["phase_degrees"],
        "refresh_interval": best["declared"]["refresh_interval"],
        "measured_item": best["declared"]["measured_item"],
        "selection_key": selection_key(best),
        "selection_retention_at_horizon": selection_retention(best),
        "measure_retention_at_horizon": best["neutral_stability"][
            "measure_retention_at_horizon"
        ],
        "measure_last_half_min_retention": best["neutral_stability"][
            "measure_last_half_min_retention"
        ],
        "alignment_retention_at_horizon": best["horizon"]["alignment_retention"],
        "mid_retention": best["horizon"]["mid_retention"],
        "last_half_min_retention": best["horizon"]["last_half_min_retention"],
        "last_half_retention_ratio": best["horizon"]["last_half_retention_ratio"],
        "drive_work_total": best["drive"]["drive_work_total"],
        "drive_work_over_write_work": best["drive"]["drive_work_over_write_work"],
        "frame_energy_ratio_at_horizon": best["horizon"]["frame_energy_ratio"],
        "frame_energy_ratio_max": best["horizon"]["frame_energy_ratio_max"],
        "neutrally_stable": best["neutral_stability"]["neutrally_stable"],
        "runaway": best["boundedness"]["runaway"],
        "arms_in_family": len(family_rows),
        "arms_compared": len(rows),
    }


def family_table(body: Mapping[str, Any], family: str) -> dict[str, Any]:
    return {
        name: {
            "gain": row["declared"]["gain"],
            "refresh_interval": row["declared"]["refresh_interval"],
            "phase_degrees": row["declared"]["phase_degrees"],
            "measured_item": row["declared"]["measured_item"],
            "alignment_retention_at_horizon": row["horizon"]["alignment_retention"],
            "measure_retention_at_horizon": row["neutral_stability"][
                "measure_retention_at_horizon"
            ],
            "measure_mid_retention": row["neutral_stability"]["measure_mid_retention"],
            "measure_last_half_min_retention": row["neutral_stability"][
                "measure_last_half_min_retention"
            ],
            "measure_last_half_retention_ratio": row["neutral_stability"][
                "measure_last_half_retention_ratio"
            ],
            "mid_retention": row["horizon"]["mid_retention"],
            "last_half_min_retention": row["horizon"]["last_half_min_retention"],
            "last_half_retention_ratio": row["horizon"]["last_half_retention_ratio"],
            "frame_energy_ratio_at_horizon": row["horizon"]["frame_energy_ratio"],
            "frame_energy_ratio_max": row["horizon"]["frame_energy_ratio_max"],
            "unwritten_max_share": row["horizon"]["unwritten_max_share"],
            "drive_work_total": row["drive"]["drive_work_total"],
            "drive_work_over_write_work": row["drive"]["drive_work_over_write_work"],
            "clipped_ticks": row["drive"]["clipped_ticks"],
            "max_amplitude": row["drive"]["max_amplitude"],
            "neutrally_stable": row["neutral_stability"]["neutrally_stable"],
            "runaway": row["boundedness"]["runaway"],
        }
        for name, row in body["arms"].items()
        if row["declared"]["family"] == family
    }


def separation_report(body: Mapping[str, Any], names: Sequence[str]) -> dict[str, Any]:
    """The declared separation among a set of arms, beside the declared margin."""

    rows = [body["arms"][name] for name in names]
    values = [row["horizon"]["alignment_retention"] for row in rows]
    ordered = [row["declared"]["gain"] for row in sorted(rows, key=lambda row: row["declared"]["gain"])]
    ordered_values = [
        row["horizon"]["alignment_retention"]
        for row in sorted(rows, key=lambda row: row["declared"]["gain"])
    ]
    monotone = all(
        later > earlier for earlier, later in zip(ordered_values, ordered_values[1:])
    )
    return {
        "arms": list(names),
        "retention_at_horizon": {row["arm"]: row["horizon"]["alignment_retention"] for row in rows},
        "maximum_minus_minimum": max(values) - min(values),
        "gains_in_order": ordered,
        "monotone_in_gain": bool(monotone),
    }


def phase_grid_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The declared phase grid beside its declared prediction, per declared gain."""

    config = body["declared"]
    arms = {
        name: row
        for name, row in body["arms"].items()
        if row["declared"]["family"] == "closed-loop-phase"
    }
    drift = body["arms"]["drift-no-refresh-no-loop"]
    drift_retention = drift["horizon"]["alignment_retention"]
    baseline_disturbance = drift["horizon"]["unwritten_max_share"]
    disturbance_allowance = (
        float(config["disturbance_allowance_multiple"]) * baseline_disturbance
    )
    refresh_work = body["arms"]["refresh-open-loop-every-8"]["drive"][
        "drive_work_total"
    ]
    rows: dict[str, Any] = {}
    for name, arm in arms.items():
        horizon = arm["horizon"]
        drive = arm["drive"]
        beats = bool(horizon["alignment_retention"] > drift_retention)
        rows[name] = {
            "theta_degrees": arm["declared"]["phase_degrees"],
            "gain": arm["declared"]["gain"],
            "alignment_retention_at_horizon": horizon["alignment_retention"],
            "mid_retention": horizon["mid_retention"],
            "last_half_min_retention": horizon["last_half_min_retention"],
            "last_half_retention_ratio": horizon["last_half_retention_ratio"],
            "frame_energy_ratio_at_horizon": horizon["frame_energy_ratio"],
            "frame_energy_ratio_max": horizon["frame_energy_ratio_max"],
            "drive_work_total": drive["drive_work_total"],
            "drive_work_over_write_work": drive["drive_work_over_write_work"],
            "drive_work_over_refresh_every_8": drive["drive_work_total"] / refresh_work,
            "unwritten_max_share": horizon["unwritten_max_share"],
            "unwritten_difference_from_baseline": (
                horizon["unwritten_max_share"] - baseline_disturbance
            ),
            "clipped_ticks": drive["clipped_ticks"],
            "max_amplitude": drive["max_amplitude"],
            "bounded": not arm["boundedness"]["runaway"],
            "beats_drift_baseline": beats,
            "prediction_met": bool(
                beats
                and horizon["frame_energy_ratio"] > 1.0
                and horizon["unwritten_max_share"] <= disturbance_allowance
                and not arm["boundedness"]["runaway"]
            ),
            "neutrally_stable": arm["neutral_stability"]["neutrally_stable"],
        }
    best_name = max(rows, key=lambda name: rows[name]["alignment_retention_at_horizon"])
    best = rows[best_name]
    best_by_gain = {}
    for gain in config["phase_gains"]:
        candidates = [
            (name, row) for name, row in rows.items() if row["gain"] == float(gain)
        ]
        name, row = max(candidates, key=lambda pair: pair[1]["alignment_retention_at_horizon"])
        best_by_gain[repr(float(gain))] = {
            "arm": name,
            "theta_degrees": row["theta_degrees"],
            "alignment_retention_at_horizon": row["alignment_retention_at_horizon"],
            "frame_energy_ratio_at_horizon": row["frame_energy_ratio_at_horizon"],
            "drive_work_total": row["drive_work_total"],
            "unwritten_max_share": row["unwritten_max_share"],
            "prediction_met": row["prediction_met"],
        }
    quarter = float(config["quarter_period_phase_degrees"])
    offset = float(best["theta_degrees"]) - quarter
    return {
        "declared_loop_equation": DEFINITIONS["phase_loop_equation"],
        "declared_prediction": DEFINITIONS["phase_prediction"],
        "prediction_terms": {
            "retention_above_drift_baseline": drift_retention,
            "frame_energy_ratio_above": 1.0,
            "unwritten_max_share_at_most": disturbance_allowance,
            "disturbance_allowance_multiple": float(
                config["disturbance_allowance_multiple"]
            ),
            "drift_baseline_unwritten_max_share": baseline_disturbance,
            "bounded": True,
        },
        "drift_baseline_retention": drift_retention,
        "refresh_every_8_drive_work": refresh_work,
        "per_arm": rows,
        "best_arm": best_name,
        "best_theta_degrees": best["theta_degrees"],
        "best_gain": best["gain"],
        "best_retention_at_horizon": best["alignment_retention_at_horizon"],
        "best_by_gain": best_by_gain,
        "quarter_period_tick": body["phase_readout"]["quarter_period_tick"],
        "quarter_period_phase_degrees": quarter,
        "quarter_period_match_tolerance_degrees": float(
            config["quarter_period_match_tolerance_degrees"]
        ),
        "best_theta_offset_from_quarter_period_degrees": offset,
        "best_theta_is_the_quarter_period": bool(
            abs(offset) <= float(config["quarter_period_match_tolerance_degrees"])
        ),
        "arms_meeting_prediction": sorted(
            name for name, row in rows.items() if row["prediction_met"]
        ),
        "arms_beating_drift_baseline": sorted(
            name for name, row in rows.items() if row["beats_drift_baseline"]
        ),
        "any_arm_meets_prediction": bool(
            any(row["prediction_met"] for row in rows.values())
        ),
    }


def refresh_ladder_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The declared refresh ladder per declared item, against the cited lifetimes."""

    config = body["declared"]
    families = (
        ("refresh-ladder", str(config["headline_item"])),
        ("refresh-ladder-detail", str(config["second_ladder_item"])),
    )
    items: dict[str, Any] = {}
    for family, label in families:
        rows = {
            name: row
            for name, row in body["arms"].items()
            if row["declared"]["family"] == family
        }
        recorded = {
            int(arm["declared"]["refresh_interval"]): arm for arm in rows.values()
        }
        assert set(recorded) == set(int(i) for i in config["ladder_intervals"])
        for arm in rows.values():
            if int(arm["declared"]["horizon_ticks"]) != int(
                config["ladder_horizon_ticks"]
            ):
                raise RuntimeError(
                    "a declared ladder arm must run the declared ladder horizon"
                )
            if arm["declared"]["measured_item"] != label:
                raise RuntimeError(
                    "a declared ladder arm must be measured on its declared item"
                )
        table = {
            str(interval): {
                "measure_retention_at_horizon": arm["neutral_stability"][
                    "measure_retention_at_horizon"
                ],
                "measure_mid_retention": arm["neutral_stability"][
                    "measure_mid_retention"
                ],
                "measure_last_half_min_retention": arm["neutral_stability"][
                    "measure_last_half_min_retention"
                ],
                "measure_last_half_retention_ratio": arm["neutral_stability"][
                    "measure_last_half_retention_ratio"
                ],
                "neutral_level_floor": arm["neutral_stability"]["level_floor"],
                "neutral_decay_tolerance": arm["neutral_stability"][
                    "decay_tolerance"
                ],
                "frame_energy_ratio_at_horizon": arm["horizon"]["frame_energy_ratio"],
                "drive_work_total": arm["drive"]["drive_work_total"],
                "unwritten_max_share": arm["horizon"]["unwritten_max_share"],
                "neutrally_stable": arm["neutral_stability"]["neutrally_stable"],
                "runaway": arm["boundedness"]["runaway"],
            }
            for interval, arm in sorted(recorded.items())
        }
        satisfying = sorted(
            interval
            for interval, arm in recorded.items()
            if arm["neutral_stability"]["neutrally_stable"]
        )
        critical = max(satisfying) if satisfying else None
        failing_above = sorted(
            interval
            for interval, arm in recorded.items()
            if not arm["neutral_stability"]["neutrally_stable"]
            and (critical is None or interval > critical)
        )
        smallest_failing = failing_above[0] if failing_above else None
        cited = float(config["cited_intrinsic_lifetime_ticks"][label])
        assert cited > 0.0
        items[label] = {
            "family": family,
            "measured_item": recorded[sorted(recorded)[0]]["declared"]["measured_item"],
            "item_index": int(
                recorded[sorted(recorded)[0]]["declared"]["measure_item_index"]
            ),
            "item_path": durability.ITEM_SPECS[
                int(recorded[sorted(recorded)[0]]["declared"]["measure_item_index"])
            ].path,
            "cited_item_width": int(config["cited_item_widths"][label]),
            "declared_horizon_ticks": int(config["ladder_horizon_ticks"]),
            "declared_sample_ticks": list(config["ladder_sample_ticks"]),
            "per_interval": table,
            "intervals_satisfying_neutral_stability": satisfying,
            "critical_interval_ticks": critical,
            "smallest_failing_interval_above_critical": smallest_failing,
            "bracket_gap_ticks": (
                None
                if critical is None or smallest_failing is None
                else smallest_failing - critical
            ),
            "cited_intrinsic_lifetime_ticks": cited,
            "cited_lifetime_basis": "the declared item's own ladder figure",
            "cited_rung_width": (
                int(CITED_WIDTH7_RUNG_WIDTH)
                if int(config["cited_item_widths"][label]) == CITED_WIDTH7_RUNG_WIDTH
                else None
            ),
            "cited_rung_mean_lifetime_ticks": (
                float(CITED_WIDTH7_RUNG_MEAN_LIFETIME_TICKS)
                if int(config["cited_item_widths"][label]) == CITED_WIDTH7_RUNG_WIDTH
                else None
            ),
            "critical_interval_over_cited_rung_mean": (
                None
                if int(config["cited_item_widths"][label]) != CITED_WIDTH7_RUNG_WIDTH
                or critical is None
                else critical / float(CITED_WIDTH7_RUNG_MEAN_LIFETIME_TICKS)
            ),
            "critical_interval_over_cited_lifetime": (
                None if critical is None else critical / cited
            ),
        }
    ratios = {
        label: items[label]["critical_interval_over_cited_lifetime"]
        for _, label in families
    }
    first_label, second_label = families[0][1], families[1][1]
    widths = {first_label: int(config["cited_item_widths"][first_label]),
              second_label: int(config["cited_item_widths"][second_label])}
    if widths[first_label] == widths[second_label]:
        raise RuntimeError(
            "the two declared ladder items must differ in declared width, or the "
            "scaling comparison is degenerate"
        )
    return {
        "declared_ladder": [int(interval) for interval in config["ladder_intervals"]],
        "declared_ladder_horizon_ticks": int(config["ladder_horizon_ticks"]),
        "declared_ladder_sample_ticks": list(config["ladder_sample_ticks"]),
        "declared_criterion": DEFINITIONS["neutral_stability"],
        "declared_citation": DEFINITIONS["cited_intrinsic_lifetime"],
        "items": items,
        "critical_interval_over_cited_lifetime": ratios,
        "items_pair": [first_label, second_label],
        "item_widths": {
            first_label: int(config["cited_item_widths"][first_label]),
            second_label: int(config["cited_item_widths"][second_label]),
        },
        "cited_lifetimes": {
            first_label: float(config["cited_intrinsic_lifetime_ticks"][first_label]),
            second_label: float(config["cited_intrinsic_lifetime_ticks"][second_label]),
        },
        "items_share_a_rung_path": False,
        "critical_intervals_agree_across_items": (
            items[first_label]["critical_interval_ticks"]
            == items[second_label]["critical_interval_ticks"]
        ),
        "ratios_agree_across_items_within_tolerance": bool(
            ratios[first_label] is not None
            and ratios[second_label] is not None
            and abs(ratios[first_label] - ratios[second_label])
            <= float(config["ladder_ratio_tolerance"])
        ),
        "ratio_agreement_tolerance": float(config["ladder_ratio_tolerance"]),
    }


def boundedness_regime(row: Mapping[str, Any]) -> str:
    """The declared regime label of one arm, read off that arm's own boundedness row.

    ``bounded`` when the arm stayed inside the declared runaway energy ratio at its own
    declared horizon; ``amplifying_beyond_declared_bound`` when it did not but every
    sample and the ratio itself are finite, which is a statement about that horizon and
    not a divergence; ``divergent`` when a sample or the ratio is non-finite.
    """

    boundedness = row["boundedness"]
    finite = bool(boundedness["all_samples_finite"]) and bool(
        np.isfinite(float(boundedness["energy_ratio_max"]))
    )
    if not finite:
        return "divergent"
    if bool(boundedness["runaway"]):
        return "amplifying_beyond_declared_bound"
    return "bounded"


def partition_boundedness(arms: Mapping[str, Any]) -> dict[str, Any]:
    """Split the measured arms by the declared boundedness predicate and divergence.

    The declared boundedness predicate names its bound ``runaway_energy_ratio``, so the
    arms it flags are reported under that declared name; the partition keeps the finite
    flagged arms apart from any divergent arm, so the flag can never be read as a
    divergence claim, and labels every arm, so a reader can see which regime one row
    belongs to without consulting another.
    """

    regime_by_arm = {name: boundedness_regime(row) for name, row in arms.items()}
    over_bound = sorted(
        name for name, regime in regime_by_arm.items() if regime != "bounded"
    )
    divergent = sorted(
        name for name, regime in regime_by_arm.items() if regime == "divergent"
    )
    return {
        "over_bound": over_bound,
        "divergent": divergent,
        "amplifying_but_finite": sorted(set(over_bound) - set(divergent)),
        "regime_by_arm": regime_by_arm,
    }


def reading_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The headline measured numbers, in the order the questions were asked."""

    arms = body["arms"]
    drift = arms["drift-no-refresh-no-loop"]
    refresh_names = [
        name for name, row in arms.items() if row["declared"]["family"] == "refresh"
    ]
    gain_names = [
        name for name, row in arms.items() if row["declared"]["family"] == "closed-loop"
    ]
    saturation_names = [
        name
        for name, row in arms.items()
        if row["declared"]["family"] == "closed-loop-saturation"
    ]
    best_refresh_name = max(
        refresh_names, key=lambda name: arms[name]["horizon"]["alignment_retention"]
    )
    best_refresh = arms[best_refresh_name]
    gain_separation = separation_report(
        body, [name for name in gain_names if arms[name]["declared"]["gain"] > 0.0]
    )
    refresh_minus_drift = (
        best_refresh["horizon"]["alignment_retention"]
        - drift["horizon"]["alignment_retention"]
    )
    positive_gain_names = [
        name for name in gain_names if arms[name]["declared"]["gain"] > 0.0
    ]
    best_gain_name = max(
        positive_gain_names,
        key=lambda name: arms[name]["horizon"]["alignment_retention"],
    )
    selected = body["selected_loop_setting"]
    multi = [
        row for row in arms.values() if row["declared"]["family"] == "multi-item"
    ]
    control = next(row for row in multi if row["arm"] == "drift-k2-control")
    looped_multi = next(row for row in multi if row["arm"] != "drift-k2-control")
    neutral_arms = sorted(
        name for name, row in arms.items() if row["neutral_stability"]["neutrally_stable"]
    )
    boundedness_partition = partition_boundedness(arms)
    over_bound_arms = boundedness_partition["over_bound"]
    divergent_arms = boundedness_partition["divergent"]
    amplifying_arms = boundedness_partition["amplifying_but_finite"]
    regime_by_arm = boundedness_partition["regime_by_arm"]
    selected_name = body["selected_loop_setting"]["name"]
    family_gain = float(body["best_declared_phase_setting"]["gain"])
    disturbance = {
        name: {
            "horizon_unwritten_max_share": row["horizon"]["unwritten_max_share"],
            "difference_from_drift": (
                row["horizon"]["unwritten_max_share"]
                - drift["horizon"]["unwritten_max_share"]
            ),
            "declared_frame_projection_fraction": row["horizon"][
                "declared_frame_projection_fraction"
            ],
        }
        for name, row in arms.items()
    }
    best_saturation = family_best(body, "closed-loop-saturation")
    neutral_gain = neutral_gain_block(body)
    long_horizon = long_horizon_block(body)
    capacity = capacity_block(body)
    genericity = genericity_block(body)
    composition = body.get("composition")
    return {
        "question": (
            "does closing the field's read-back onto its own drive hold a pattern that "
            "otherwise decays, and at what gain, work cost, disturbance and item count?"
        ),
        "looped_object": (
            "the full canonical page, advanced one tick per call, with the canonical read "
            "frame as the read-back; no reduced realization is looped, and the saturated "
            "maintenance it measures costs the frame-energy amplification and unwritten-"
            "direction disturbance reported per arm"
        ),
        "cited_continuation": body["cited_agreement"],
        "per_family_best": {
            "neutral_gain": family_best(body, "neutral-gain-refine"),
            "drift": family_best(body, "drift"),
            "refresh": family_best(body, "refresh"),
            "closed_loop_declared_gains": family_best(
                body, "closed-loop", positive_gain_only=True
            ),
            "closed_loop_saturation": family_best(body, "closed-loop-saturation"),
            "closed_loop_phase": family_best(body, "closed-loop-phase"),
            "refresh_ladder": family_best(body, "refresh-ladder"),
            "refresh_ladder_detail": family_best(body, "refresh-ladder-detail"),
            "multi_item": {
                "control_arm": control["arm"],
                "control_min_item_retention": min(control["horizon"]["item_retention"].values()),
                "loop_arm": looped_multi["arm"],
                "loop_min_item_retention": min(
                    looped_multi["horizon"]["item_retention"].values()
                ),
                "loop_item_retention": looped_multi["horizon"]["item_retention"],
                "control_item_retention": control["horizon"]["item_retention"],
                "gain_over_control": (
                    min(looped_multi["horizon"]["item_retention"].values())
                    - min(control["horizon"]["item_retention"].values())
                ),
                "drive_work_total": looped_multi["drive"]["drive_work_total"],
                "setting": {
                    "name": selected["name"],
                    "gain": selected["gain"],
                    "refresh_interval": selected["refresh_interval"],
                },
            },
        },
        "families": {
            "drift": family_table(body, "drift"),
            "refresh": family_table(body, "refresh"),
            "closed_loop_declared_gains": family_table(body, "closed-loop"),
            "closed_loop_saturation": family_table(body, "closed-loop-saturation"),
            "closed_loop_phase": family_table(body, "closed-loop-phase"),
            "refresh_ladder": family_table(body, "refresh-ladder"),
            "refresh_ladder_detail": family_table(body, "refresh-ladder-detail"),
            "multi_item": family_table(body, "multi-item"),
            "neutral_gain": family_table(body, "neutral-gain"),
            "neutral_gain_refine": family_table(body, "neutral-gain-refine"),
            "long_horizon": family_table(body, "long-horizon"),
            "capacity": family_table(body, "capacity"),
            "genericity": family_table(body, "genericity"),
        },
        "neutral_gain": neutral_gain,
        "long_horizon": long_horizon,
        "capacity": capacity,
        "genericity": genericity,
        **(
            {
                "composition": {
                    "question": composition["question"],
                    "profile": composition["profile"],
                    "flat_neutral_gain": composition["flat_neutral_gain"][
                        "measured_gain"
                    ],
                    "flat_neutral_bracket": composition["flat_neutral_gain"]["bracket"],
                    "flat_neutral_bracket_width": composition["flat_neutral_gain"][
                        "bracket_width"
                    ],
                    "hold": composition["hold"],
                    "drift_contrast": composition["drift_contrast"],
                    "aim": composition["aim"],
                    "capacity": {
                        "capacity_limit_items": composition["capacity"][
                            "capacity_limit_items"
                        ],
                        "schemes_holding_both_items": composition["capacity"][
                            "schemes_holding_both_items"
                        ],
                        "schemes": composition["capacity"]["schemes"],
                        "control": composition["capacity"]["control"],
                        "margin": composition["capacity"]["margin"],
                    },
                    "diagnosis": composition["diagnosis"],
                    "capacity_curve": {
                        "gain": composition["capacity_curve"]["gain"],
                        "margin": composition["capacity_curve"]["margin"],
                        "work_ceiling": composition["capacity_curve"]["work_ceiling"],
                        "counts": composition["capacity_curve"]["counts"],
                        "limit_by_scheme": composition["capacity_curve"][
                            "limit_by_scheme"
                        ],
                        "capacity_limit_evidence": composition["capacity_curve"][
                            "capacity_limit_evidence"
                        ],
                        "declared": composition["capacity_curve"]["declared"],
                    },
                    "split_sweep": composition["split_sweep"],
                    "quiet_regime": {
                        "gain": composition["quiet_regime"]["gain"],
                        "default_profile_hold": composition["quiet_regime"][
                            "default_profile_hold"
                        ],
                        "holds": {
                            item: {
                                key: value
                                for key, value in row.items()
                                if not key.endswith("_trajectory")
                            }
                            for item, row in composition["quiet_regime"]["holds"].items()
                        },
                        "gain_ladder": {
                            factor: {
                                key: value
                                for key, value in row.items()
                                if not key.endswith("_trajectory")
                            }
                            for factor, row in composition["quiet_regime"][
                                "gain_ladder"
                            ].items()
                        },
                        "two_item_frame_hold": {
                            key: value
                            for key, value in composition["quiet_regime"][
                                "two_item_frame_hold"
                            ].items()
                            if not key.endswith("_trajectory")
                        },
                        "items_with_falling_energy_while_holding": composition[
                            "quiet_regime"
                        ]["items_with_falling_energy_while_holding"],
                        "items_whose_throughput_increases_while_holding": composition[
                            "quiet_regime"
                        ]["items_whose_throughput_increases_while_holding"],
                        "every_declared_single_item_hold_increases_throughput": composition[
                            "quiet_regime"
                        ]["every_declared_single_item_hold_increases_throughput"],
                        "gain_factors_with_falling_energy": composition["quiet_regime"][
                            "gain_factors_with_falling_energy"
                        ],
                        "every_declared_gain_falls": composition["quiet_regime"][
                            "every_declared_gain_falls"
                        ],
                        "quoting_regime": composition["quiet_regime"]["quoting_regime"],
                        "declared": composition["quiet_regime"]["declared"],
                    },
                    "verdicts": composition["verdicts"],
                    "declared": composition["declared"],
                }
            }
            if composition is not None
            else {}
        ),
        "refresh_separation": {
            "best_arm": best_refresh_name,
            "best_retention_at_horizon": best_refresh["horizon"]["alignment_retention"],
            "drift_retention_at_horizon": drift["horizon"]["alignment_retention"],
            "difference": refresh_minus_drift,
            "declared_separation_margin": body["declared"]["separation_margin"],
            "separates": separation_holds(
                refresh_minus_drift, body["declared"]["separation_margin"]
            ),
            "drive_work_total": best_refresh["drive"]["drive_work_total"],
            "retention_per_unit_drive_work": (
                best_refresh["horizon"]["alignment_retention"]
                / best_refresh["drive"]["drive_work_total"]
                if best_refresh["drive"]["drive_work_total"] > 0.0
                else None
            ),
            "arms_satisfying_neutral_stability": sorted(
                name for name in refresh_names if arms[name]["neutral_stability"]["neutrally_stable"]
            ),
            "per_interval": family_table(body, "refresh"),
        },
        "gain_separation": {
            **gain_separation,
            "declared_separation_margin": body["declared"]["separation_margin"],
            "separates": separation_holds(
                gain_separation["maximum_minus_minimum"],
                body["declared"]["separation_margin"],
            ),
            "best_gain_arm": best_gain_name,
            "best_gain_retention_at_horizon": arms[best_gain_name]["horizon"][
                "alignment_retention"
            ],
            "drift_retention_at_horizon": drift["horizon"]["alignment_retention"],
            "best_gain_minus_drift": (
                arms[best_gain_name]["horizon"]["alignment_retention"]
                - drift["horizon"]["alignment_retention"]
            ),
        },
        "boundedness": {
            "runaway_ratio": body["declared"]["runaway_energy_ratio"],
            "runaway_arms": over_bound_arms,
            "runaway_flag_means": (
                "'runaway' here is the declared boundedness predicate evaluated over one "
                "arm's own run at that arm's own declared horizon: its largest frame-energy "
                f"ratio inside that horizon exceeds the declared runaway_energy_ratio. "
                "Because each arm is read at its own horizon, the flag is comparable across "
                "the long-horizon, two-item and regime families -- the same setting can be "
                "inside the bound at the declared phase horizon and flagged at the longer "
                "one. It is not a divergence claim and it does not make "
                "the arm a failure: every arm flagged in this receipt is finite at its own "
                "horizon, and the same setting is inside the bound at a shorter declared "
                "horizon. Divergent arms, if any, are listed separately under divergent_arms"
            ),
            "arms_over_declared_energy_bound": over_bound_arms,
            "declared": (
                "the declared boundedness predicate is evaluated over each arm's own run: "
                "an arm is flagged when its largest frame-energy ratio exceeds the declared "
                "bound inside its own declared horizon. The flag is therefore a statement "
                "about that arm at that horizon, not about divergence: every flagged arm in "
                "this receipt is finite, and an amplifying-but-finite arm and a divergent arm "
                "are now listed separately so a reader cannot take the flag for a divergence "
                "claim or read it off the same row as the declared best stable setting"
            ),
            "divergent_arms": divergent_arms,
            "amplifying_but_finite_arms": amplifying_arms,
            "all_flagged_arms_are_finite": bool(not divergent_arms),
            "regime_by_arm": regime_by_arm,
            "arms": {
                name: {
                    "frame_energy_ratio_max": row["horizon"]["frame_energy_ratio_max"],
                    "runaway": row["boundedness"]["runaway"],
                    "all_samples_finite": row["boundedness"]["all_samples_finite"],
                    "ledger_balance_within_allowance": row["ledger_check"][
                        "balance_defect_within_allowance"
                    ],
                    "ledger_residual_within_allowance": row["ledger_check"][
                        "residual_work_within_allowance"
                    ],
                }
                for name, row in arms.items()
            },
            "maximum_frame_energy_ratio": max(
                row["horizon"]["frame_energy_ratio_max"] for row in arms.values()
            ),
        },
        "settings_reconciliation": {
            "declared": (
                "two different declared settings appear in this receipt and they are not "
                "interchangeable: the declared selection rule's setting is chosen from the "
                "declared gain sweep and saturation ladder at those arms' own declared "
                "horizon, while the two-item, long-horizon, capacity and genericity families "
                "run at the best *declared phase* setting, which is selected by the declared "
                "phase rule at the declared phase horizon. The boundedness flag is evaluated "
                "over each arm's own run, so an arm can be the best stable setting at one "
                "horizon and over the declared energy bound at a longer one"
            ),
            "selected_loop_setting": {
                "name": selected_name,
                "gain": float(arms[selected_name]["declared"]["gain"]),
                "refresh_interval": int(arms[selected_name]["declared"]["refresh_interval"]),
                "horizon_ticks": int(arms[selected_name]["declared"]["horizon_ticks"]),
                "frame_energy_ratio_max": arms[selected_name]["boundedness"][
                    "energy_ratio_max"
                ],
                "over_declared_energy_bound": bool(
                    arms[selected_name]["boundedness"]["runaway"]
                ),
                "role": (
                    "the declared best stable loop setting of the declared gain sweep and "
                    "saturation ladder, measured at those arms' own declared horizon"
                ),
            },
            "families_declared_setting": {
                "name": body["best_declared_phase_setting"]["name"],
                "gain": family_gain,
                "phase_degrees": float(
                    body["best_declared_phase_setting"]["phase_degrees"]
                ),
                "horizon_ticks": int(body["declared"]["long_horizon_ticks"]),
                "role": (
                    "the declared best phase setting, which the two-item, long-horizon, "
                    "capacity and genericity families run at"
                ),
            },
            "why_arms_are_over_the_bound": (
                "the arms over the declared energy bound are the declared phase setting's "
                "arms run over the declared long horizon plus the amplifying-regime capacity "
                "family: at the declared phase horizon the same setting is inside the bound, "
                "and over 512 ticks its frame energy has grown past the declared bound while "
                "staying finite. The flag therefore says 'amplifying past the declared bound "
                "at its own horizon', and the receipt now lists the finite amplifying arms "
                "and any divergent arms separately, so 'best stable setting' and 'over the "
                "bound' can never be read off one row: the selected setting is chosen only "
                "among arms that stay inside the bound at its own horizon"
            ),
            "selected_setting_is_over_the_bound": bool(
                arms[selected_name]["boundedness"]["runaway"]
            ),
            "every_flagged_arm_is_finite": bool(not divergent_arms),
            "capacity_family_regime": (
                "the amplifying-regime capacity arms run at the same declared phase gain as "
                "the long-horizon family and are flagged over the bound for the same reason; "
                "the neutral and bounded regimes' arms are reported beside them with their "
                "own regime label, and the headline capacity figure is taken from the "
                "neutral regime"
            ),
        },
        "neutral_stability": {
            "criterion": {
                "level_floor": body["declared"]["neutral_level_floor"],
                "decay_tolerance": body["declared"]["neutral_decay_tolerance"],
                "bounded": True,
            },
            "arms_satisfying": neutral_arms,
            "arms": {
                name: row["neutral_stability"]["neutrally_stable"]
                for name, row in arms.items()
            },
        },
        "unwritten_direction_disturbance": {
            "drift_horizon_unwritten_max_share": drift["horizon"]["unwritten_max_share"],
            "per_arm": disturbance,
        },
        "phase_grid": phase_grid_block(body),
        "refresh_ladder": refresh_ladder_block(body),
        "saturation": {
            "clipped_ticks_by_gain": {
                name: arms[name]["drive"]["clipped_ticks"] for name in saturation_names
            },
            "max_amplitude_by_gain": {
                name: arms[name]["drive"]["max_amplitude"] for name in saturation_names
            },
            "best": best_saturation,
        },
    }


def neutral_gain_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The declared neutral gain: the measured refinement beside the declared prediction."""

    config = body["declared"]
    refinement = body["neutral_gain_refinement"]
    calibration = body["actuator_calibration"]["declared_profile"]
    ticks = int(config["horizon_ticks"])
    predicted = predicted_neutral_gain(
        float(config["neutral_gain_phase_degrees"]),
        calibration,
        ticks,
        float(config["neutral_gain_prediction_ceiling"]),
    )
    linearized = predicted_neutral_gain(
        float(config["neutral_gain_phase_degrees"]),
        calibration,
        ticks,
        float(config["neutral_gain_prediction_ceiling"]),
        linearized=True,
    )
    measured = float(refinement["measured_gain"])
    predicted_gain = float(predicted["gain"]) if predicted["found"] else None
    allowance = float(config["neutral_gain_allowance"])
    relative_error = (
        abs(predicted_gain - measured) / measured
        if predicted_gain is not None and measured > 0.0
        else None
    )
    phases = (0.0, float(config["neutral_gain_phase_degrees"]))
    pairs: list[dict[str, Any]] = []
    for name, row in body["arms"].items():
        if row["declared"]["family"] not in ("closed-loop-phase", "neutral-gain"):
            continue
        if float(row["declared"]["phase_degrees"]) not in phases:
            continue
        series = predict_retention_series(
            float(row["declared"]["gain"]),
            float(row["declared"]["phase_degrees"]),
            calibration,
            ticks,
        )
        measured_retention = row["neutral_stability"]["measure_retention_at_horizon"]
        predicted_retention = series[-1] ** 2
        pairs.append(
            {
                "arm": name,
                "gain": float(row["declared"]["gain"]),
                "phase_degrees": float(row["declared"]["phase_degrees"]),
                "measured_retention_at_horizon": measured_retention,
                "predicted_retention_at_horizon": predicted_retention,
                "relative_error": (
                    abs(predicted_retention - measured_retention) / measured_retention
                    if measured_retention > 0.0
                    else None
                ),
                "growth_rate_per_tick": growth_rate_per_tick(row),
            }
        )
    prediction_allowance = float(config["prediction_retention_allowance"])
    within = [
        row
        for row in pairs
        if row["phase_degrees"] == float(config["neutral_gain_phase_degrees"])
        and row["relative_error"] is not None
    ]
    outside_domain = [
        row
        for row in pairs
        if row["phase_degrees"] != float(config["neutral_gain_phase_degrees"])
    ]
    return {
        "question": (
            "at the declared inverted-phase setting, at which gain does the closed loop "
            "stop growing the written mode, and does the declared prediction find it?"
        ),
        "phase_degrees": float(config["neutral_gain_phase_degrees"]),
        "declared_grid": [float(g) for g in config["neutral_gain_grid"]],
        "measured": measured,
        "measured_bracket": refinement["bracket"],
        "measured_bracket_width": refinement["bracket_width"],
        "measured_tolerance": refinement["tolerance"],
        "grid_monotone_in_gain": refinement["grid_monotone"],
        "grid": refinement["grid"],
        "probes": refinement["probes"],
        "predicted": predicted,
        "predicted_linearized": linearized,
        "relative_error_of_prediction": relative_error,
        "allowance": allowance,
        "prediction_within_allowance": (
            None if relative_error is None else bool(relative_error <= allowance)
        ),
        "retention_prediction_pairs": pairs,
        "prediction_retention_allowance": prediction_allowance,
        "arms_within_retention_allowance": [
            row["arm"] for row in within if row["relative_error"] <= prediction_allowance
        ],
        "arms_outside_retention_allowance": [
            row["arm"] for row in within if row["relative_error"] > prediction_allowance
        ],
        "calibration_max_residual": calibration["prediction_check_max_residual"],
        "declared_domain": (
            "the declared prediction is defined at the declared inverted-phase "
            "setting, where the loop's own dynamics keep its deposit on the mode it "
            "reads back on; the declared in-phase arms are reported here as the "
            "measured boundary of that domain"
        ),
        "outside_declared_domain": outside_domain,
    }


def long_horizon_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The declared long horizon: growth, saturation, alignment and the linear control."""

    config = body["declared"]
    arms = body["arms"]
    names = {
        name: row
        for name, row in arms.items()
        if row["declared"]["family"] == "long-horizon"
    }
    calibration = body["actuator_calibration"]["declared_profile"]
    ticks = int(config["long_horizon_ticks"])
    per_arm: dict[str, Any] = {}
    for name, row in names.items():
        samples = row["samples"]
        horizon = row["horizon"]
        series = [
            {
                "tick": int(sample["tick"]),
                "measure_retention": sample["measure_retention"],
                "alignment_retention": sample["alignment_retention"],
                "frame_energy_ratio": sample["frame_energy_ratio"],
                "unwritten_max_share": sample["unwritten_max_share"],
                "signed_projection_ratio": sample["signed_projection_ratio"],
                "drive_amplitude": sample["drive_amplitude"],
                "drive_clipped": sample["drive_clipped"],
            }
            for sample in samples
        ]
        entry: dict[str, Any] = {
            "gain": float(row["declared"]["gain"]),
            "profile_beta": row["declared"]["profile_beta"],
            "horizon_ticks": int(horizon["tick"]),
            "retention_series": series,
            "horizon_measure_retention": horizon["measure_retention"]
            if "measure_retention" in horizon
            else row["neutral_stability"]["measure_retention_at_horizon"],
            "horizon_alignment_retention": horizon["alignment_retention"],
            "horizon_frame_energy_ratio": horizon["frame_energy_ratio"],
            "horizon_unwritten_max_share": horizon["unwritten_max_share"],
            "last_half_retention_ratio": horizon["last_half_retention_ratio"],
            "growth_rate_per_tick": growth_rate_per_tick(row),
            "max_drive_amplitude": row["drive"]["max_amplitude"],
            "clipped_ticks": row["drive"]["clipped_ticks"],
            "drive_work_over_write_work": row["drive"]["drive_work_over_write_work"],
            "written_direction_alignment_at_horizon": alignment_fraction(
                samples[-1]["item_retention"][row["declared"]["measured_item"]],
                samples[0]["item_retention"][row["declared"]["measured_item"]],
            ),
        }
        if float(row["declared"]["gain"]) > 0.0:
            series_prediction = predict_retention_series(
                float(row["declared"]["gain"]),
                float(row["declared"]["phase_degrees"]),
                calibration,
                ticks,
            )
            predicted = series_prediction[-1] ** 2
            entry["predicted_retention_at_horizon"] = predicted
            entry["prediction_relative_error"] = (
                abs(predicted - entry["horizon_measure_retention"])
                / entry["horizon_measure_retention"]
                if entry["horizon_measure_retention"] > 0.0
                else None
            )
        per_arm[name] = entry
    loop_names = [
        name
        for name, row in names.items()
        if float(row["declared"]["gain"]) > 0.0
        and row["declared"]["profile_beta"] != float(config["beta_zero"])
    ]
    beta_zero_names = [
        name
        for name, row in names.items()
        if row["declared"]["profile_beta"] == float(config["beta_zero"])
    ]
    comparisons: dict[str, Any] = {}
    for name in loop_names:
        counterpart = "long-horizon-beta-zero-" + name.removeprefix("long-horizon-")
        if counterpart not in per_arm:
            continue
        comparisons[name] = {
            "declared_profile_arm": name,
            "beta_zero_arm": counterpart,
            "declared_profile_retention": per_arm[name]["horizon_measure_retention"],
            "beta_zero_retention": per_arm[counterpart]["horizon_measure_retention"],
            "relative_difference": relative_difference(
                per_arm[counterpart]["horizon_measure_retention"],
                per_arm[name]["horizon_measure_retention"],
            ),
            "quartic_inactive_within_bound": bool(
                relative_difference(
                    per_arm[counterpart]["horizon_measure_retention"],
                    per_arm[name]["horizon_measure_retention"],
                )
                <= float(config["nonlinearity_activity_bound"])
            ),
        }
    plateau: dict[str, Any] = {}
    for name, entry in per_arm.items():
        if entry["gain"] <= 0.0:
            continue
        series = entry["retention_series"]
        half = [row for row in series if row["tick"] <= int(config["long_horizon_ticks"]) // 2]
        plateau[name] = {
            "first_half_growth_rate_per_tick": series_growth_rate(half),
            "second_half_growth_rate_per_tick": series_growth_rate(
                [row for row in series if row["tick"] >= int(config["long_horizon_ticks"]) // 2]
            ),
            "growth_decelerates": bool(
                series_growth_rate(
                    [row for row in series if row["tick"] >= int(config["long_horizon_ticks"]) // 2]
                )
                is not None
                and series_growth_rate(half) is not None
                and series_growth_rate(
                    [row for row in series if row["tick"] >= int(config["long_horizon_ticks"]) // 2]
                )
                < series_growth_rate(half)
            ),
            "energy_ratio_at_horizon": entry["horizon_frame_energy_ratio"],
            "unwritten_max_share_at_horizon": entry["horizon_unwritten_max_share"],
            "written_direction_alignment_at_horizon": entry[
                "written_direction_alignment_at_horizon"
            ],
            "saturated_within_declared_horizon": bool(
                entry["last_half_retention_ratio"] is not None
                and entry["last_half_retention_ratio"]
                <= float(config["plateau_growth_tolerance"])
            ),
        }
    return {
        "question": (
            "over the declared long horizon, does the maintenance saturate, does the "
            "written direction survive, does the unwritten share stay dark, and does the "
            "declared quartic coupling stop the growth?"
        ),
        "horizon_ticks": ticks,
        "sample_spacing_ticks": max(
            int(right) - int(left)
            for left, right in zip(
                config["long_horizon_sample_ticks"],
                config["long_horizon_sample_ticks"][1:],
            )
        ),
        "per_arm": per_arm,
        "plateau": plateau,
        "beta_zero_comparison": comparisons,
        "nonlinearity_activity_bound": float(config["nonlinearity_activity_bound"]),
        "any_plateau_within_horizon": any(
            entry["saturated_within_declared_horizon"] for entry in plateau.values()
        ),
        "all_growth_decelerates": all(
            entry["growth_decelerates"] for entry in plateau.values()
        ),
    }


def alignment_fraction(at_horizon: float | None, at_first_sample: float | None) -> float | None:
    """The share of the written direction that survives: horizon over first sample."""

    if at_horizon is None or at_first_sample is None or float(at_first_sample) == 0.0:
        return None
    return float(at_horizon) / float(at_first_sample)


def relative_difference(value: float, reference: float) -> float:
    """The absolute relative difference between two measured figures."""

    if reference == 0.0:
        return float("inf")
    return abs(float(value) - float(reference)) / abs(float(reference))


def series_growth_rate(rows: Sequence[Mapping[str, Any]]) -> float | None:
    """The per-tick growth rate of a sampled retention series."""

    if len(rows) < 2:
        return None
    first, last = rows[0], rows[-1]
    span = int(last["tick"]) - int(first["tick"])
    if span <= 0 or float(first["measure_retention"]) <= 0.0:
        return None
    return (float(last["measure_retention"]) / float(first["measure_retention"])) ** (
        1.0 / span
    ) - 1.0


def second_half_mean_retention(row: Mapping[str, Any], item: str) -> float | None:
    """The declared capacity aggregate: an item's mean retention over the back half.

    A single horizon sample of a drifting share oscillates with the mode's own
    rotation, so the capacity comparison is declared over the mean of the arm's own
    back-half samples rather than over one sample.
    """

    samples = [
        sample
        for sample in row["samples"]
        if int(sample["tick"]) >= int(row["declared"]["horizon_ticks"]) // 2
        and item in sample["item_retention"]
    ]
    if not samples:
        return None
    return float(sum(sample["item_retention"][item] for sample in samples) / len(samples))


def pearson_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    """The declared correlation of two measured per-tick signals, or None if undefined."""

    if len(left) != len(right) or len(left) < 2:
        return None
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    covariance = sum(
        (a - mean_left) * (b - mean_right) for a, b in zip(left, right)
    )
    variance_left = sum((a - mean_left) ** 2 for a in left)
    variance_right = sum((b - mean_right) ** 2 for b in right)
    if variance_left <= 0.0 or variance_right <= 0.0:
        return None
    return float(covariance / math.sqrt(variance_left * variance_right))


def sign_agreement(left: Sequence[float], right: Sequence[float]) -> float | None:
    """The declared fraction of ticks on which two measured signals share a sign."""

    pairs = [(a, b) for a, b in zip(left, right) if a != 0.0 and b != 0.0]
    if not pairs:
        return None
    return float(sum(1 for a, b in pairs if a * b > 0.0) / len(pairs))


def capacity_diagnosis_block(
    body: Mapping[str, Any],
    arm_name: str = "capacity-two-item-telemetry",
    regime: str = "amplifying",
    control_arm: str = "capacity-two-item-no-loop",
) -> dict[str, Any]:
    """The declared diagnosis of one regime's shared scheme, from its own telemetry.

    The shared loop reads back on the measured item alone and applies that one signed
    scalar to every driven item. This block reports the two per-tick drive signals it
    produced (their correlation and their sign pattern against each item's own
    projection), how the two items' own projections co-moved, and the signed increment
    each item's lane actually received, so the mechanism behind the measured outcome is
    read off the arm's own numbers rather than inferred. The declared regime is recorded
    with it, because the same scheme's outcome is a statement about that gain alone.
    """

    config = body["declared"]
    if arm_name not in body["arms"]:
        raise ValueError(f"the declared diagnosis arm {arm_name} was not measured")
    arm = body["arms"][arm_name]
    headline = config["headline_item"]
    second = config["capacity_item"]
    rows = arm["telemetry"]
    amplitude_headline = [float(row["amplitude"][headline]) for row in rows]
    amplitude_second = [float(row["amplitude"][second]) for row in rows]
    ratio_headline = [float(row["ratio_before"][headline]) for row in rows]
    ratio_second = [float(row["ratio_before"][second]) for row in rows]
    increment_headline = [float(row["increment"][headline]) for row in rows]
    increment_second = [float(row["increment"][second]) for row in rows]
    agreement_headline = sign_agreement(amplitude_headline, ratio_headline)
    agreement_second = sign_agreement(amplitude_second, ratio_second)
    anti_headline = sign_agreement(
        [-value for value in amplitude_headline], ratio_headline
    )
    anti_second = sign_agreement(
        [-value for value in amplitude_second], ratio_second
    )
    increment_headline = [float(row["increment"][headline]) for row in rows]
    increment_second = [float(row["increment"][second]) for row in rows]
    # The two items' own per-tick increments, compared with each other rather than each
    # against its own projection: this is the measured relative phase of the two lanes'
    # drives, read over the ticks on which either lane was actually driven.
    driven_mask = [
        bool(left != 0.0 or right != 0.0)
        for left, right in zip(increment_headline, increment_second)
    ]
    phase_pairs = [
        (left, right)
        for left, right, driven in zip(
            increment_headline, increment_second, driven_mask
        )
        if driven
    ]
    increment_relative_phase = (
        None
        if not phase_pairs
        else float(
            sum(
                (1 if left > 0.0 else (-1 if left < 0.0 else 0))
                * (1 if right > 0.0 else (-1 if right < 0.0 else 0))
                for left, right in phase_pairs
            )
            / len(phase_pairs)
        )
    )
    increment_sign_agreement = (
        None
        if not phase_pairs
        else float(
            sum(
                1
                for left, right in phase_pairs
                if (left > 0.0) == (right > 0.0) and (left < 0.0) == (right < 0.0)
            )
            / len(phase_pairs)
        )
    )
    # The cross-projection: what one drive call did to the other item's own lane, measured
    # around that same call and normalised by the driven item's own increment, so a value
    # near one means the two lanes are not separable under this drive and a value near zero
    # means the drive went into its own lane alone. Both directions are reported and the
    # applied work those calls carried is carried with them.
    cross_rows = [
        row
        for row in rows
        if row.get("cross_increment") and row["cross_increment"]
    ]
    cross_projection: dict[str, Any] = {}
    for driven_item, other_item in ((headline, second), (second, headline)):
        pairs = [
            (
                float(row["increment"][driven_item]),
                float(row["cross_increment"][f"{driven_item}->{other_item}"]),
                float(row["applied_work"][driven_item]),
            )
            for row in cross_rows
            if driven_item in row["increment"]
            and f"{driven_item}->{other_item}" in row["cross_increment"]
        ]
        if not pairs:
            cross_projection[f"{driven_item}_into_{other_item}"] = None
            continue
        own = [abs(pair[0]) for pair in pairs]
        other = [abs(pair[1]) for pair in pairs]
        mean_own = float(sum(own) / len(own))
        mean_other = float(sum(other) / len(other))
        cross_projection[f"{driven_item}_into_{other_item}"] = {
            "driven_item": driven_item,
            "other_item": other_item,
            "drive_calls_measured": len(pairs),
            "mean_abs_own_lane_increment": mean_own,
            "mean_abs_other_lane_increment": mean_other,
            "mean_signed_other_lane_increment": float(
                sum(pair[1] for pair in pairs) / len(pairs)
            ),
            "mean_applied_work_per_call": float(
                sum(pair[2] for pair in pairs) / len(pairs)
            ),
            "other_lane_fraction_of_own": (
                None if not mean_own else float(mean_other / mean_own)
            ),
        }
    declared_cross = [
        row
        for key, row in cross_projection.items()
        if row is not None
    ]
    max_cross_fraction = (
        None
        if not declared_cross
        else max(
            float(row["other_lane_fraction_of_own"])
            for row in declared_cross
            if row["other_lane_fraction_of_own"] is not None
        )
    )
    # The measured relative phase of the two driven signals themselves, when the arm was
    # given each driven item's own quadrature reference: each tick's (in-phase, quadrature)
    # pair is a phase, and the mean angle between the two items' pairs is the phase
    # difference the loop actually ran at rather than the declared angle.
    quadrature_phase_degrees: float | None = None
    if rows and rows[0].get("quadrature_before"):
        angles: list[float] = []
        for row in rows:
            if headline not in row["quadrature_before"] or second not in row["quadrature_before"]:
                continue
            in_phase_h = float(row["ratio_before"][headline])
            quadrature_h = float(row["quadrature_before"][headline])
            in_phase_s = float(row["ratio_before"][second])
            quadrature_s = float(row["quadrature_before"][second])
            real = in_phase_s * in_phase_h + quadrature_s * quadrature_h
            imaginary = quadrature_s * in_phase_h - in_phase_s * quadrature_h
            if real == 0.0 and imaginary == 0.0:
                continue
            angles.append(float(math.degrees(math.atan2(imaginary, real))))
        if angles:
            quadrature_phase_degrees = float(
                math.degrees(
                    math.atan2(
                        sum(math.sin(math.radians(a)) for a in angles),
                        sum(math.cos(math.radians(a)) for a in angles),
                    )
                )
            )
    mean_increment_headline = float(
        sum(increment_headline) / len(increment_headline)
    )
    mean_increment_second = float(sum(increment_second) / len(increment_second))
    shared_amplitude_difference = max(
        abs(a - b) for a, b in zip(amplitude_headline, amplitude_second)
    )
    deposits = arm["measured_deposit_energy"]
    mean_work_headline = float(
        sum(float(row["applied_work"][headline]) for row in rows) / len(rows)
    )
    mean_work_second = float(
        sum(float(row["applied_work"][second]) for row in rows) / len(rows)
    )
    margin = float(config["capacity_suppression_margin"])
    if control_arm not in body["arms"] or capacity_arm_name(regime, "single-item-second") not in body["arms"]:
        raise ValueError(
            f"the declared diagnosis controls of the {regime} regime were not measured"
        )
    control_second = second_half_mean_retention(body["arms"][control_arm], second)
    second_alone = second_half_mean_retention(
        body["arms"][capacity_arm_name(regime, "single-item-second")], second
    )
    # The declared mechanism test: the loop puts one scalar on both lanes, that scalar
    # deposits into the item it reads back on and removes from the other, and the other
    # item is maintained by the same setting as soon as the loop reads back on it — so
    # the suppression is the shared read-back's doing and not the item's own limits.
    mechanism_measured = bool(
        shared_amplitude_difference == 0.0
        and mean_increment_headline > 0.0 > mean_increment_second
        and second_alone is not None
        and control_second is not None
        and second_alone > control_second + margin
    )
    return {
        "arm": arm["arm"],
        "regime": regime,
        "gain": float(arm["declared"]["gain"]),
        "declared": (
            "the declared shared two-item loop drives every driven item with the one "
            "signed amplitude its single read-back produces; each item's own per-tick "
            "projection is read in that item's own declared units, the applied amplitude "
            "is what that item's lane received, and the signed increment is the change "
            "in that item's own projection the drive produced"
        ),
        "ticks": len(rows),
        "applied_amplitude_is_shared": shared_amplitude_difference == 0.0,
        "applied_amplitude_max_difference_between_items": float(
            shared_amplitude_difference
        ),
        "drive_signal_correlation": pearson_correlation(
            amplitude_headline, amplitude_second
        ),
        "readings_correlation": pearson_correlation(ratio_headline, ratio_second),
        "amplitude_against_own_projection_correlation": {
            headline: pearson_correlation(amplitude_headline, ratio_headline),
            second: pearson_correlation(amplitude_second, ratio_second),
        },
        "sign_agreement_with_own_projection": {
            headline: agreement_headline,
            second: agreement_second,
        },
        "anti_agreement_with_own_projection": {
            headline: anti_headline,
            second: anti_second,
        },
        "mean_signed_increment_into_own_lane": {
            headline: mean_increment_headline,
            second: mean_increment_second,
        },
        "item_deposit_energy": {
            headline: float(deposits[headline]),
            second: float(deposits[second]),
        },
        "mean_applied_work_per_item": {
            headline: mean_work_headline,
            second: mean_work_second,
        },
        "applied_work_over_item_deposit": {
            headline: mean_work_headline / float(deposits[headline]),
            second: mean_work_second / float(deposits[second]),
        },
        "mean_projection_increment_per_applied_work": {
            headline: mean_increment_headline / mean_work_headline,
            second: mean_increment_second / mean_work_second,
        },
        "second_item_alone_with_the_same_setting": second_alone,
        "second_item_without_any_loop": control_second,
        "summed_signed_increment_into_own_lane": {
            headline: float(sum(increment_headline)),
            second: float(sum(increment_second)),
        },
        "increment_correlation": pearson_correlation(
            increment_headline, increment_second
        ),
        "increment_sign_agreement": increment_sign_agreement,
        "increment_relative_phase": increment_relative_phase,
        "increment_relative_phase_declared": (
            "the mean product of the two items' per-tick increment signs over the ticks on "
            "which either lane was driven: one means the two lanes always moved together, "
            "minus one means one lane always gained what the other lost, and zero means the "
            "two lanes' increments were uncorrelated"
        ),
        "cross_projection": cross_projection,
        "max_cross_projection_fraction": max_cross_fraction,
        "quadrature_relative_phase_degrees": quadrature_phase_degrees,
        "mechanism": (
            (
                "the declared shared loop puts one signed scalar on both lanes (largest "
                f"difference between the two applied amplitudes {shared_amplitude_difference:.3g}), "
                "and that scalar is fixed by the item it reads back on: it sits against "
                f"that item's own projection on {anti_headline:.3f} of the declared ticks "
                f"(correlation {pearson_correlation(amplitude_headline, ratio_headline):.4f}) "
                f"against {anti_second:.3f} of them for the second item "
                f"(correlation {pearson_correlation(amplitude_second, ratio_second):.4f}), so "
                "the declared maintenance phase is addressed to both items; what separates "
                "them is what the pump deposits: a mean signed increment of "
                f"{mean_increment_headline:.6g} into the measured item's own lane against "
                f"{mean_increment_second:.6g} into the second item's, i.e. "
                f"{mean_increment_headline / mean_work_headline:.4g} against "
                f"{mean_increment_second / mean_work_second:.4g} of own-projection per unit of "
                f"applied work (each lane receiving {mean_work_headline:.6g} of work against "
                f"deposits of {float(deposits[headline]):.6g} and {float(deposits[second]):.6g}), "
                f"and the two items' own projections are correlated "
                f"{pearson_correlation(ratio_headline, ratio_second):.4f} inside the loop; the "
                "same setting over the same two written items maintains the second item when "
                f"the loop reads back on it instead ({second_alone!r} against {control_second!r} "
                "with no loop), so the suppression is the shared read-back's doing"
            )
            if mechanism_measured
            else (
                "the declared shared pump does not separate the two items' lanes at this "
                "gain: the two items' own per-tick increments moved together with a mean "
                f"sign product of {increment_relative_phase!r} (sign agreement "
                f"{increment_sign_agreement!r}, correlation "
                f"{pearson_correlation(increment_headline, increment_second)!r}), so this "
                "receipt reports the measured increments, the applied amplitude and the "
                "cross-projection of one item's drive into the other's lane "
                f"({max_cross_fraction!r} of the driven item's own increment at most) "
                "without naming a suppression mechanism"
            )
        ),
        "mechanism_measured": mechanism_measured,
        "per_item_share_series": {
            item: [
                float(row["share_after"][item])
                for row in rows
                if item in row["share_after"]
            ]
            for item in (headline, second)
        },
    }


def capacity_regime_table(
    body: Mapping[str, Any],
    regime: str,
    gain: float,
    control_arm: str = "capacity-two-item-no-loop",
) -> dict[str, Any]:
    """Every declared capacity scheme in one declared gain regime, at one declared margin.

    Each regime writes the same two declared items over the same declared long horizon and
    is compared over the same back-half means against the same drive-free no-loop control
    and against the single-item loops *of its own regime*, so a holding claim cannot be
    read off a different gain's rows.
    """

    config = body["declared"]
    arms = body["arms"]
    headline = config["headline_item"]
    second = config["capacity_item"]
    margin = float(config["capacity_suppression_margin"])
    if control_arm not in arms:
        raise ValueError(f"the declared control arm {control_arm!r} was not measured")
    control = arms[control_arm]
    control_headline = second_half_mean_retention(control, headline)
    control_second = second_half_mean_retention(control, second)
    single = arms[capacity_arm_name(regime, "single-item-headline")]
    single_headline = second_half_mean_retention(single, headline)
    single_second_arm = arms[capacity_arm_name(regime, "single-item-second")]
    single_second = second_half_mean_retention(single_second_arm, second)
    schemes: dict[str, Any] = {}
    for name in config["capacity_schemes"]:
        arm = arms[capacity_arm_name(regime, name)]
        measured_headline = second_half_mean_retention(arm, headline)
        measured_second = second_half_mean_retention(arm, second)
        rows = arm.get("telemetry", [])
        driven_ticks = {
            item: sum(1 for row in rows if item in row["scheduled"])
            for item in (headline, second)
        }
        item_drive_statistics: dict[str, Any] = {}
        for item in (headline, second):
            amplitudes = [
                float(row["amplitude"][item])
                for row in rows
                if item in row["amplitude"]
            ]
            if not amplitudes:
                item_drive_statistics[item] = None
                continue
            signs = [
                1 if value > 0.0 else (-1 if value < 0.0 else 0) for value in amplitudes
            ]
            consecutive = [
                (left, right)
                for left, right in zip(signs, signs[1:])
                if left and right
            ]
            item_drive_statistics[item] = {
                "driven_ticks": len(amplitudes),
                "mean_abs_amplitude": float(
                    sum(abs(value) for value in amplitudes) / len(amplitudes)
                ),
                "max_abs_amplitude": float(max(abs(value) for value in amplitudes)),
                "clipped_fraction": float(
                    sum(
                        1
                        for row in rows
                        if item in row["clipped"] and row["clipped"][item]
                    )
                    / len(amplitudes)
                ),
                "sign_change_fraction_on_driven_ticks": (
                    None
                    if not consecutive
                    else float(
                        sum(1 for left, right in consecutive if left != right)
                        / len(consecutive)
                    )
                ),
                "mean_applied_work": float(
                    sum(
                        float(row["applied_work"][item])
                        for row in rows
                        if item in row["applied_work"]
                    )
                    / len(amplitudes)
                ),
            }
        schemes[name] = {
            "arm": arm["arm"],
            "item_drive_statistics": item_drive_statistics,
            "drive_read_back": arm["declared"]["drive_read_back"],
            "drive_work_split": arm["declared"]["drive_work_split"],
            "headline_second_half_mean": measured_headline,
            "second_second_half_mean": measured_second,
            "headline_minus_control": (
                None
                if measured_headline is None or control_headline is None
                else measured_headline - control_headline
            ),
            "second_minus_control": (
                None
                if measured_second is None or control_second is None
                else measured_second - control_second
            ),
            "second_minus_own_single_item_loop": (
                None
                if measured_second is None or single_second is None
                else measured_second - single_second
            ),
            "headline_minus_single_item_loop": (
                None
                if measured_headline is None or single_headline is None
                else measured_headline - single_headline
            ),
            "headline_held_above_control": bool(
                measured_headline is not None
                and control_headline is not None
                and measured_headline > control_headline + margin
            ),
            "second_held_above_control": bool(
                measured_second is not None
                and control_second is not None
                and measured_second > control_second + margin
            ),
            "both_items_held": bool(
                measured_headline is not None
                and control_headline is not None
                and measured_headline > control_headline + margin
                and measured_second is not None
                and control_second is not None
                and measured_second > control_second + margin
            ),
            "driven_ticks": driven_ticks,
            "drive_calls": int(arm["drive"]["calls"]),
            "drive_work_total": arm["drive"]["drive_work_total"],
            "drive_work_per_tick": (
                None
                if not arm["declared"]["horizon_ticks"]
                else arm["drive"]["drive_work_total"]
                / float(arm["declared"]["horizon_ticks"])
            ),
        }
    holding = [name for name, row in schemes.items() if row["both_items_held"]]
    limit = 2 if holding else 1
    over_bound = sorted(
        row["arm"] for row in schemes.values() if arms[row["arm"]]["boundedness"]["runaway"]
    )
    return {
        "regime": regime,
        "gain": float(gain),
        "declared": (
            "every declared scheme writes the same two declared items, runs the declared "
            "long horizon at this regime's declared gain and the declared phase angle, and "
            "is compared over the same back-half means against the same drive-free no-loop "
            "two-item control and against the single-item loops of this same regime; a "
            "scheme holds an item when its mean exceeds that item's control mean by more "
            "than the declared margin. Every scheme spends at most the declared loop work "
            "ceiling times that tick's applied amplitude on each declared tick, which the "
            "per-tick telemetry of each scheme bounds directly; the work a scheme actually "
            "draws depends on the amplitudes its own state produces and is reported per "
            "scheme rather than held fixed"
        ),
        "scheme_arms_over_declared_energy_bound": over_bound,
        "margin": margin,
        "control": {
            "arm": control["arm"],
            "gain": float(control["declared"]["gain"]),
            "headline_second_half_mean": control_headline,
            "second_second_half_mean": control_second,
            "declared": (
                "the no-loop two-item control writes the same two declared items and "
                "drives nothing, so it is the same measured control in every regime"
            ),
        },
        "single_item_reference": {
            "arm": single["arm"],
            "gain": float(single["declared"]["gain"]),
            "headline_second_half_mean": single_headline,
        },
        "second_item_own_single_item_reference": {
            "arm": single_second_arm["arm"],
            "declared": (
                "the same declared setting over the same two written items with the loop "
                "reading back on the second item alone: this separates the shared pump's "
                "effect on that item from that item's own maintainability at this setting"
            ),
            "second_second_half_mean": single_second,
            "second_retention_at_horizon": single_second_arm["horizon"]["item_retention"][
                second
            ],
            "headline_second_half_mean": second_half_mean_retention(
                single_second_arm, headline
            ),
        },
        "schemes": schemes,
        "schemes_holding_both_items": holding,
        "capacity_limit_items": limit,
        "capacity_limit_evidence": (
            (
                f"in the {regime} regime (gain {float(gain)!r}) at least one declared scheme "
                "keeps both declared items above their own no-loop controls by more than the "
                "declared margin: "
                + ", ".join(holding)
                if holding
                else f"in the {regime} regime (gain {float(gain)!r}) no declared scheme keeps "
                "both declared items above their own no-loop controls by more than the "
                "declared margin, so the measured capacity of this loop at this gain is one "
                "pattern"
            )
        ),
    }


def capacity_curve_block(
    body: Mapping[str, Any], gain: float, counts: Sequence[int] | None = None
) -> dict[str, Any]:
    """The declared capacity curve: how many declared items hold as the count grows.

    Every declared count writes its declared items and is answered against its own declared
    no-loop control at the same horizon, item by item and then as a count, at the declared
    margin. The work columns are the loop's own per-item aggregates, so the receipt shows
    whether holding more items costs more drive or the same drive spread thinner rather
    than assuming either.
    """

    config = body["declared"]
    arms = body["arms"]
    margin = float(config["capacity_suppression_margin"])
    declared_counts = tuple(
        int(count) for count in (counts if counts is not None else config["capacity_curve_counts"])
    )
    counts_block: dict[str, Any] = {}
    for count in declared_counts:
        control_name = capacity_curve_arm_name(count, "no-loop")
        control = arms[control_name]
        item_names = list(control["declared"]["written_items"])
        control_means = {
            item: second_half_mean_retention(control, item) for item in item_names
        }
        schemes: dict[str, Any] = {}
        for scheme in config["capacity_curve_schemes"]:
            arm = arms[capacity_curve_arm_name(count, scheme)]
            rows = arm.get("telemetry", [])
            item_rows: dict[str, Any] = {}
            holding: list[str] = []
            for item in item_names:
                measured = second_half_mean_retention(arm, item)
                control_mean = control_means[item]
                difference = (
                    None
                    if measured is None or control_mean is None
                    else measured - control_mean
                )
                held = bool(
                    difference is not None and difference > margin
                )
                if held:
                    holding.append(item)
                item_rows[item] = {
                    "second_half_mean": measured,
                    "control_second_half_mean": control_mean,
                    "minus_control": difference,
                    "held_above_control": held,
                    "scheduled_ticks": int(
                        arm["declared"]["scheduled_ticks"].get(item, 0)
                    ),
                    "applied_work_per_tick": float(
                        arm["declared"]["mean_applied_work_per_item_per_tick"].get(
                            item, 0.0
                        )
                    ),
                    "retention_at_horizon": (
                        None
                        if item not in arm["horizon"]["item_retention"]
                        else float(arm["horizon"]["item_retention"][item])
                    ),
                    # The retained trace's own counts of this item's drive calls and of the
                    # calls that read this item's lane: they must equal the loop's own
                    # counts, or the trace is incomplete.
                    "increment_series_rows": sum(
                        1 for row in rows if item in row.get("increment", {})
                    ),
                    "cross_increment_series_rows": sum(
                        1
                        for row in rows
                        if any(
                            key.endswith(f"->{item}")
                            for key in row.get("cross_increment", {})
                        )
                    ),
                    "cross_increment_entries": sum(
                        1
                        for row in rows
                        for key in row.get("cross_increment", {})
                        if key.startswith(f"{item}->")
                    ),
                }
            tick_counts = [
                int(item_rows[item]["scheduled_ticks"]) for item in item_names
            ]
            measured_differences = [
                float(item_rows[item]["minus_control"])
                for item in item_names
                if item_rows[item]["minus_control"] is not None
            ]
            schemes[scheme] = {
                "smallest_hold_margin": (
                    min(measured_differences) if measured_differences else None
                ),
                "smallest_hold_margin_item": (
                    min(
                        (
                            (float(item_rows[item]["minus_control"]), item)
                            for item in item_names
                            if item_rows[item]["minus_control"] is not None
                        )
                    )[1]
                    if measured_differences
                    else None
                ),
                "smallest_hold_margin_multiple_of_the_declared_margin": (
                    None
                    if not measured_differences or not margin
                    else float(min(measured_differences) / margin)
                ),
                "arm": arm["arm"],
                "drive_read_back": arm["declared"]["drive_read_back"],
                "drive_work_split": arm["declared"]["drive_work_split"],
                "driven_tick_imbalance": (
                    max(tick_counts) - min(tick_counts) if tick_counts else 0
                ),
                "items_held": len(holding),
                "items_held_names": list(holding),
                "all_items_held": bool(len(holding) == len(item_names)),
                "item_rows": item_rows,
                "drive_work_total": arm["drive"]["drive_work_total"],
                "drive_work_per_tick": (
                    arm["drive"]["drive_work_total"]
                    / float(arm["declared"]["horizon_ticks"])
                ),
                "max_work_per_tick": arm["drive"]["max_work_per_tick"],
                "clipped_ticks": int(arm["drive"]["clipped_ticks"]),
                "over_declared_energy_bound": bool(arm["boundedness"]["runaway"]),
            }
        counts_block[str(count)] = {
            "count": count,
            "items": item_names,
            "control_arm": control["arm"],
            "control_gain": float(control["declared"]["gain"]),
            "control_second_half_mean": control_means,
            "schemes": schemes,
            "capacity_limit_items": max(
                (row["items_held"] for row in schemes.values()), default=0
            ),
            "schemes_holding_every_declared_item": [
                scheme
                for scheme, row in schemes.items()
                if row["all_items_held"]
            ],
            "largest_scheme_driven_tick_imbalance": max(
                (
                    int(row["driven_tick_imbalance"])
                    for row in schemes.values()
                ),
                default=0,
            ),
        }
    limit_by_scheme: dict[str, Any] = {}
    for scheme in config["capacity_curve_schemes"]:
        holders = [
            count
            for count in declared_counts
            if counts_block[str(count)]["schemes"][scheme]["all_items_held"]
        ]
        limit_by_scheme[scheme] = {
            "largest_count_holding_every_item": max(holders) if holders else None,
            "counts_holding_every_item": holders,
            "items_held_by_count": {
                str(count): counts_block[str(count)]["schemes"][scheme]["items_held"]
                for count in declared_counts
            },
        }
    return {
        "declared": (
            "every declared count writes the declared curve items in the declared curve "
            "order -- the two declared capacity items first, then the declared item list -- "
            "and is answered against its own declared no-loop control that writes the same "
            "items at the same horizon; a scheme holds an item when that item's back-half "
            "mean exceeds its own control's back-half mean by more than the declared margin. "
            "Each scheme spends the declared per-tick work ceiling: the schemes that drive "
            "every item each tick divide it between them, and the multiplexed scheme spends "
            "it whole on the one item its declared cycle names that tick, whose cycle "
            "repeats and is truncated at the declared horizon"
        ),
        "gain": float(gain),
        "margin": margin,
        "counts": counts_block,
        "limit_by_scheme": limit_by_scheme,
        "work_ceiling": float(config["loop_work_ceiling"]),
        "smallest_hold_margins_by_scheme": {
            scheme: {
                str(count): counts_block[str(count)]["schemes"][scheme][
                    "smallest_hold_margin"
                ]
                for count in declared_counts
            }
            for scheme in config["capacity_curve_schemes"]
        },
        "capacity_limit_evidence": (
            "the declared curve's per-scheme limits are "
            + ", ".join(
                f"{scheme}: "
                + (
                    str(row["largest_count_holding_every_item"])
                    if row["largest_count_holding_every_item"] is not None
                    else "no declared count"
                )
                for scheme, row in limit_by_scheme.items()
            )
        ),
    }


def capacity_split_block(
    body: Mapping[str, Any],
    gain: float,
    splits: Sequence[Sequence[float]] | None = None,
    control_arm: str = COMPOSITION_CONTROL_ARM,
) -> dict[str, Any]:
    """The declared drive-split sweep: one drive channel or two independent lanes?

    Every declared split runs the declared shared scheme on the same two declared items at
    the same declared gain with the declared per-tick work ceiling divided in the declared
    proportions, so the two items' retentions move only if the drive they receive moves.
    A split-independent outcome is two lanes that happen to work together; a split-dependent
    one is one drive channel the two items compete for.
    """

    config = body["declared"]
    arms = body["arms"]
    margin = float(config["capacity_suppression_margin"])
    headline = config["headline_item"]
    second = config["capacity_item"]
    declared_splits = tuple(
        tuple(float(weight) for weight in split)
        for split in (splits if splits is not None else config["capacity_split_weights"])
    )
    if control_arm not in arms:
        raise ValueError(f"the declared split control {control_arm!r} was not measured")
    control = arms[control_arm]
    control_headline = second_half_mean_retention(control, headline)
    control_second = second_half_mean_retention(control, second)
    rows_block: dict[str, Any] = {}
    for split in declared_splits:
        arm = arms[capacity_split_arm_name(split)]
        measured_headline = second_half_mean_retention(arm, headline)
        measured_second = second_half_mean_retention(arm, second)
        difference = (
            None
            if measured_headline is None or control_headline is None
            else measured_headline - control_headline
        )
        second_difference = (
            None
            if measured_second is None or control_second is None
            else measured_second - control_second
        )
        # The measured cross-lane leakage of this split's own drive calls: how much of the
        # increment one item's drive produced landed in the other item's lane, so the
        # split-dependence verdict can say whether the two items interact through their own
        # state or only through the single work budget their drive divides.
        split_rows = arm.get("telemetry", [])
        leakage: dict[str, float | None] = {}
        for driven_item, other_item in ((headline, second), (second, headline)):
            cross_key = f"{driven_item}->{other_item}"
            pairs = [
                (
                    abs(float(row["increment"][driven_item])),
                    abs(float(row["cross_increment"][cross_key])),
                )
                for row in split_rows
                if driven_item in row.get("increment", {})
                and cross_key in row.get("cross_increment", {})
            ]
            own = float(sum(pair[0] for pair in pairs) / len(pairs)) if pairs else 0.0
            other = float(sum(pair[1] for pair in pairs) / len(pairs)) if pairs else 0.0
            leakage[f"{driven_item}_into_{other_item}"] = (
                None if not own else other / own
            )
        rows_block[capacity_split_arm_name(split)] = {
            "split": [float(weight) for weight in split],
            "split_items": [headline, second],
            "cross_lane_fraction": leakage,
            "max_cross_lane_fraction": (
                None
                if not [value for value in leakage.values() if value is not None]
                else max(value for value in leakage.values() if value is not None)
            ),
            "headline_second_half_mean": measured_headline,
            "second_second_half_mean": measured_second,
            "headline_minus_control": difference,
            "second_minus_control": second_difference,
            "headline_held_above_control": bool(
                difference is not None and difference > margin
            ),
            "second_held_above_control": bool(
                second_difference is not None and second_difference > margin
            ),
            "both_items_held": bool(
                difference is not None
                and difference > margin
                and second_difference is not None
                and second_difference > margin
            ),
            "headline_applied_work_per_tick": float(
                arm["declared"]["mean_applied_work_per_item_per_tick"][headline]
            ),
            "second_applied_work_per_tick": float(
                arm["declared"]["mean_applied_work_per_item_per_tick"][second]
            ),
            "drive_work_per_tick": (
                arm["drive"]["drive_work_total"]
                / float(arm["declared"]["horizon_ticks"])
            ),
        }
    # The declared split-dependence test: the item each split starves must be measured
    # against the same item in the split that favours it. The declared rule reads the
    # largest measured swing in either item's retention across the declared splits and
    # compares it with the declared margin, so a swing inside the margin is reported as
    # split-independent rather than as a channel the items share.
    headline_means = [
        row["headline_second_half_mean"]
        for row in rows_block.values()
        if row["headline_second_half_mean"] is not None
    ]
    second_means = [
        row["second_second_half_mean"]
        for row in rows_block.values()
        if row["second_second_half_mean"] is not None
    ]
    headline_swing = (
        float(max(headline_means) - min(headline_means)) if headline_means else None
    )
    second_swing = (
        float(max(second_means) - min(second_means)) if second_means else None
    )
    swings = [swing for swing in (headline_swing, second_swing) if swing is not None]
    largest_swing = max(swings) if swings else None
    split_dependent = bool(largest_swing is not None and largest_swing > margin)
    return {
        "declared": (
            "the declared shared scheme on the same two declared items at the same declared "
            "gain under each declared split of the declared per-tick work ceiling, with the "
            "loop's own read-back scalar applied to each item unchanged, so every split "
            "requests the same total work and differs only in how that budget is divided "
            "between the two items; the applied work each split actually draws is reported "
            "from the actuator's own per-call receipts. The declared split-dependence rule "
            "reads the "
            "largest measured swing in either item's back-half mean across the declared "
            "splits against the declared margin"
        ),
        "gain": float(gain),
        "margin": margin,
        "splits": rows_block,
        "control": {
            "arm": control["arm"],
            "headline_second_half_mean": control_headline,
            "second_second_half_mean": control_second,
        },
        "headline_retention_swing": headline_swing,
        "second_retention_swing": second_swing,
        "largest_retention_swing": largest_swing,
        "largest_cross_lane_fraction": (
            None
            if not [
                float(row["max_cross_lane_fraction"])
                for row in rows_block.values()
                if row["max_cross_lane_fraction"] is not None
            ]
            else max(
                float(row["max_cross_lane_fraction"])
                for row in rows_block.values()
                if row["max_cross_lane_fraction"] is not None
            )
        ),
        "split_dependent": split_dependent,
        "lane_leakage_measured": (
            "the declared split arms' own drive calls were read on both lanes, so each split "
            "reports how much of one item's drive increment landed in the other item's lane"
        ),
        "split_dependence": (
            (
                "the two declared items' retentions move with the declared split by more "
                f"than the declared margin (largest swing {largest_swing!r}), so what the "
                "two held items share is the declared work budget their drive divides: the "
                "measured cross-lane leakage of the same drive calls is "
                f"{max((float(row['max_cross_lane_fraction']) for row in rows_block.values() if row['max_cross_lane_fraction'] is not None), default=None)!r} "
                "of the driven item's own increment, so the dependence runs through the "
                "shared read-back and its budget rather than through one item's state "
                "leaking into the other's"
            )
            if split_dependent
            else (
                "the two declared items' retentions do not move with the declared split by "
                f"more than the declared margin (largest swing {largest_swing!r}), so the "
                "two held items are not competing for one drive channel"
            )
        ),
        "splits_holding_both_items": [
            name
            for name, row in rows_block.items()
            if row["both_items_held"]
        ],
    }


def quiet_regime_block(
    body: Mapping[str, Any],
    default_hold: Mapping[str, Any],
    gain: float,
) -> dict[str, Any]:
    """The declared quiet regime: what the falling frame energy under a held direction is.

    The composition's hold leg holds one written item while its frame energy ends below the
    post-write reference, unlike the default field's hold at that field's own neutral gain.
    This block reads that arm's own retained trace, repeats the hold on the declared further
    items with a frame that carries the held item alone, and re-runs it at the declared
    multiples of the gain, so the receipt can say from its own rows what the falling frame
    energy belongs to: the profile, the gain, or what else the frame carries.
    """

    config = body["declared"]
    arms = body["arms"]
    margin = float(config["capacity_suppression_margin"])
    headline = config["headline_item"]
    items = [headline, *[str(item) for item in config["quiet_regime_items"]]]

    def hold_summary(arm: Mapping[str, Any], item: str) -> dict[str, Any]:
        rows = arm.get("telemetry", [])
        energy = [float(row["frame_energy_ratio_after"]) for row in rows]
        work = [float(row["work_this_tick"]) for row in rows]
        retention = [
            float(row["ratio_after"][item]) for row in rows if item in row["ratio_after"]
        ]
        return {
            "arm": arm["arm"],
            "item": item,
            "gain": float(arm["declared"]["gain"]),
            "written_items": list(arm["declared"]["written_items"]),
            "retention_at_horizon": float(
                arm["neutral_stability"]["measure_retention_at_horizon"]
            ),
            "neutrally_stable": bool(arm["neutral_stability"]["neutrally_stable"]),
            "frame_energy_ratio_at_horizon": float(arm["horizon"]["frame_energy_ratio"]),
            "frame_energy_ratio_max": float(arm["horizon"]["frame_energy_ratio_max"]),
            "energy_falls_while_holding": bool(
                arm["horizon"]["frame_energy_ratio"] < 1.0
                and arm["neutral_stability"]["measure_retention_at_horizon"] > 1.0
            ),
            "throughput_increases_while_holding": bool(
                arm["horizon"]["frame_energy_ratio"] > 1.0
                and arm["neutral_stability"]["measure_retention_at_horizon"] > 1.0
            ),
            "energy_trajectory": energy,
            "retention_trajectory": retention,
            "work_trajectory": work,
            "energy_first": energy[0] if energy else None,
            "energy_last": energy[-1] if energy else None,
            "energy_minimum": min(energy) if energy else None,
            "energy_monotone_falling": bool(
                all(right <= left for left, right in zip(energy, energy[1:]))
            ),
            "mean_work_per_tick": (float(sum(work) / len(work)) if work else 0.0),
            "drive_work_total": arm["drive"]["drive_work_total"],
            "drive_work_over_write_work": arm["drive"]["drive_work_over_write_work"],
            "unwritten_max_share_at_horizon": float(
                arm["horizon"]["unwritten_max_share"]
            ),
            "row_count": len(rows),
        }

    holds: dict[str, Any] = {}
    for item in items:
        holds[item] = hold_summary(arms[quiet_regime_hold_arm_name(item)], item)
    ladder: dict[str, Any] = {}
    for factor in config["quiet_regime_gain_factors"]:
        arm = arms[quiet_regime_gain_arm_name(factor)]
        summary = hold_summary(arm, headline)
        summary["gain_factor"] = float(factor)
        summary["gain"] = float(arm["declared"]["gain"])
        summary["clipped_ticks"] = int(arm["drive"]["clipped_ticks"])
        summary["over_declared_energy_bound"] = bool(arm["boundedness"]["runaway"])
        summary["energy_falls_at_horizon"] = bool(
            arm["horizon"]["frame_energy_ratio"] < 1.0
        )
        ladder[str(float(factor))] = summary
    # The composition's own hold arm writes two declared items and drives one, so the frame
    # whose energy falls is carrying an item the loop does not drive: the undriven written
    # item's own retention is read from the same arm's samples, so the fall is attributed
    # rather than assumed.
    two_item = arms[capacity_arm_name("flat", "single-item-headline")]
    two_item_rows = two_item.get("telemetry", [])
    two_item_energy = [float(row["frame_energy_ratio_after"]) for row in two_item_rows]
    undriven = next(
        item_name
        for item_name in two_item["declared"]["written_items"]
        if item_name not in two_item["declared"]["drive_items"]
    )
    undriven_retention = [
        float(row["item_retention"][undriven]) for row in two_item["samples"]
    ]
    driven_retention = [
        float(row["item_retention"][headline]) for row in two_item["samples"]
    ]
    two_item_frame = {
        "arm": two_item["arm"],
        "driven_item": headline,
        "undriven_written_item": undriven,
        "gain": float(two_item["declared"]["gain"]),
        "frame_energy_ratio_at_horizon": float(two_item["horizon"]["frame_energy_ratio"]),
        "frame_energy_ratio_max": float(two_item["horizon"]["frame_energy_ratio_max"]),
        "driven_retention_at_horizon": float(
            two_item["horizon"]["item_retention"][headline]
        ),
        "undriven_retention_at_horizon": float(
            two_item["horizon"]["item_retention"][undriven]
        ),
        "undriven_retention_first_sample": undriven_retention[0],
        "undriven_retention_last_sample": undriven_retention[-1],
        "undriven_retention_trajectory": undriven_retention,
        "driven_retention_trajectory": driven_retention,
        "energy_trajectory": two_item_energy,
        "energy_first": two_item_energy[0] if two_item_energy else None,
        "energy_last": two_item_energy[-1] if two_item_energy else None,
        "undriven_item_decays": bool(
            two_item["horizon"]["item_retention"][undriven]
            < two_item["horizon"]["item_retention"][headline]
        ),
        "undriven_share_of_the_written_pair": (
            None
            if (
                two_item["horizon"]["item_retention"][headline]
                + two_item["horizon"]["item_retention"][undriven]
            )
            == 0.0
            else float(
                two_item["horizon"]["item_retention"][undriven]
                / (
                    two_item["horizon"]["item_retention"][headline]
                    + two_item["horizon"]["item_retention"][undriven]
                )
            )
        ),
    }
    single_item_falls = [
        item for item, row in holds.items() if row["energy_falls_while_holding"]
    ]
    single_item_rises = [
        item for item, row in holds.items() if row["throughput_increases_while_holding"]
    ]
    ladder_falls = [
        factor for factor, row in ladder.items() if row["energy_falls_at_horizon"]
    ]
    every_single_item_rises = bool(len(single_item_rises) == len(holds))
    return {
        "declared": (
            "each declared quiet-regime hold writes exactly the one item it holds, runs the "
            "declared long horizon at the flat profile's own measured neutral gain, and "
            "retains its own per-tick trace, so the energy and work trajectories are the "
            "loop's measured rows rather than a summary of them. The declared gain ladder "
            "re-runs the same single-item hold at the declared multiples of that gain. The "
            "composition's own hold arm is reported beside them with both of its written "
            "items' retentions, because that arm's frame carries an item the loop does not "
            "drive and its falling energy has to be attributed to what the frame holds"
        ),
        "gain": float(gain),
        "margin": margin,
        "default_profile_hold": dict(default_hold),
        "holds": holds,
        "gain_ladder": ladder,
        "two_item_frame_hold": two_item_frame,
        "items_with_falling_energy_while_holding": single_item_falls,
        "items_whose_throughput_increases_while_holding": single_item_rises,
        "every_declared_single_item_hold_increases_throughput": every_single_item_rises,
        "gain_factors_with_falling_energy": ladder_falls,
        "every_declared_gain_falls": bool(len(ladder_falls) == len(ladder)),
        "quoting_regime": (
            (
                "the falling frame energy under a held direction belongs to the declared "
                "two-item frame, not to the flat profile and not to the gain: with only the "
                "held item written, the same loop at the same gain ends at "
                + ", ".join(
                    f"{item} {row['frame_energy_ratio_at_horizon']!r}"
                    for item, row in holds.items()
                )
                + " of its post-write frame energy and at "
                + ", ".join(
                    f"x{factor} {row['frame_energy_ratio_at_horizon']!r}"
                    for factor, row in ladder.items()
                )
                + " on the declared gain ladder, while the composition's hold arm ends at "
                f"{two_item_frame['frame_energy_ratio_at_horizon']!r} because the item it "
                f"writes but does not drive ({two_item_frame['undriven_written_item']!r}) "
                "decays to "
                f"{two_item_frame['undriven_retention_at_horizon']!r} against the driven "
                f"item's {two_item_frame['driven_retention_at_horizon']!r}"
            )
            if every_single_item_rises and not ladder_falls
            else (
                "the falling frame energy under a held direction is a property of the flat "
                "profile at this gain, because it is measured on every declared "
                "quiet-regime single-item frame and at every declared multiple of the gain"
                if len(single_item_falls) == len(holds) and len(ladder_falls) == len(ladder)
                else (
                    "the frame energy under a held direction does not fall uniformly across "
                    "the declared quiet-regime frames, so it is a property of the individual "
                    "held direction rather than of the profile"
                    if single_item_falls
                    else "the falling frame energy is not established on a single-item frame"
                )
            )
        ),
    }


def capacity_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The declared capacity family: does maintaining one item evict the other?"""

    config = body["declared"]
    arms = body["arms"]
    family = {
        name: row for name, row in arms.items() if row["declared"]["family"] == "capacity"
    }
    names = [spec["name"] for spec in config["declared_items"]]
    headline = config["headline_item"]
    second = config["capacity_item"]
    control = family["capacity-two-item-no-loop"]
    locked = family["capacity-locked-on-headline"]
    both = family["capacity-two-item-loop"]
    single = arms["long-horizon-best-gain"]
    per_arm = {
        "single_item_loop": {
            "arm": single["arm"],
            "gain": float(single["declared"]["gain"]),
            "headline_retention": single["horizon"]["item_retention"][headline],
            "headline_second_half_mean": second_half_mean_retention(single, headline),
            "horizon_ticks": int(single["horizon"]["tick"]),
            "drive_work_total": single["drive"]["drive_work_total"],
        },
        "two_item_no_loop": {
            "arm": control["arm"],
            "headline_retention": control["horizon"]["item_retention"][headline],
            "second_retention": control["horizon"]["item_retention"][second],
            "headline_second_half_mean": second_half_mean_retention(control, headline),
            "second_second_half_mean": second_half_mean_retention(control, second),
            "item_retention": control["horizon"]["item_retention"],
            "horizon_ticks": int(control["horizon"]["tick"]),
        },
        "locked_on_headline": {
            "arm": locked["arm"],
            "headline_retention": locked["horizon"]["item_retention"][headline],
            "second_retention": locked["horizon"]["item_retention"][second],
            "headline_second_half_mean": second_half_mean_retention(locked, headline),
            "second_second_half_mean": second_half_mean_retention(locked, second),
            "item_retention": locked["horizon"]["item_retention"],
            "measured_on": locked["declared"]["drive_items"],
            "horizon_ticks": int(locked["horizon"]["tick"]),
            "drive_work_total": locked["drive"]["drive_work_total"],
            "drive_work_over_write_work": locked["drive"]["drive_work_over_write_work"],
        },
        "two_item_loop": {
            "arm": both["arm"],
            "headline_retention": both["horizon"]["item_retention"][headline],
            "second_retention": both["horizon"]["item_retention"][second],
            "headline_second_half_mean": second_half_mean_retention(both, headline),
            "second_second_half_mean": second_half_mean_retention(both, second),
            "item_retention": both["horizon"]["item_retention"],
            "measured_on": both["declared"]["drive_items"],
            "horizon_ticks": int(both["horizon"]["tick"]),
            "drive_work_total": both["drive"]["drive_work_total"],
            "drive_work_split": both["declared"]["drive_work_split"],
        },
    }
    margin = float(config["capacity_suppression_margin"])
    locked_second = per_arm["locked_on_headline"]["second_second_half_mean"]
    control_second = per_arm["two_item_no_loop"]["second_second_half_mean"]
    locked_headline = per_arm["locked_on_headline"]["headline_second_half_mean"]
    control_headline = per_arm["two_item_no_loop"]["headline_second_half_mean"]
    second_item_loop = per_arm["two_item_loop"]["second_second_half_mean"]
    two_item_headline = per_arm["two_item_loop"]["headline_second_half_mean"]
    suppression = {
        "aggregate": (
            "the mean of each item's own back-half samples, because a single horizon "
            "sample of a drifting share oscillates with the mode's rotation"
        ),
        "second_item_second_half_mean_under_locked_loop": locked_second,
        "second_item_second_half_mean_without_loop": control_second,
        "difference": (
            None
            if locked_second is None or control_second is None
            else locked_second - control_second
        ),
        "margin": margin,
        "suppressed_beyond_control": bool(
            locked_second is not None
            and control_second is not None
            and locked_second < control_second - margin
        ),
        "held_above_control": bool(
            locked_second is not None
            and control_second is not None
            and locked_second > control_second + margin
        ),
        "headline_second_half_mean_under_locked_loop": locked_headline,
        "headline_second_half_mean_without_loop": control_headline,
    }
    two_item_verdict = {
        "aggregate": suppression["aggregate"],
        "headline_second_half_mean_two_item_loop": two_item_headline,
        "headline_second_half_mean_single_item_loop": per_arm["single_item_loop"][
            "headline_second_half_mean"
        ],
        "headline_second_half_mean_no_loop_control": control_headline,
        "second_second_half_mean_two_item_loop": second_item_loop,
        "second_second_half_mean_no_loop_control": control_second,
        "headline_two_item_minus_single_item": (
            None
            if two_item_headline is None
            or per_arm["single_item_loop"]["headline_second_half_mean"] is None
            else two_item_headline
            - per_arm["single_item_loop"]["headline_second_half_mean"]
        ),
        "headline_two_item_minus_no_loop_control": (
            None
            if two_item_headline is None or control_headline is None
            else two_item_headline - control_headline
        ),
        "second_two_item_minus_no_loop_control": (
            None
            if second_item_loop is None or control_second is None
            else second_item_loop - control_second
        ),
        "control_items_within_declared_count": len(names) >= 2,
        "margin": margin,
        "headline_held_by_two_item_loop": bool(
            two_item_headline is not None
            and control_headline is not None
            and two_item_headline > control_headline + margin
        ),
        "second_item_suppressed_by_two_item_loop": bool(
            second_item_loop is not None
            and control_second is not None
            and second_item_loop < control_second - margin
        ),
        "both_items_above_control_with_margin": bool(
            two_item_headline is not None
            and control_headline is not None
            and two_item_headline > control_headline + margin
            and second_item_loop is not None
            and control_second is not None
            and second_item_loop > control_second + margin
        ),
        "work_split": both["declared"]["drive_work_split"],
    }
    regime_gains = {
        name: float(gain) for name, gain in config["capacity_regime_gains"].items()
    }
    regimes = [
        name for name in config["capacity_regimes"] if name in regime_gains
    ]
    regime_tables = {
        name: capacity_regime_table(body, name, regime_gains[name]) for name in regimes
    }
    holding_regime = "neutral" if "neutral" in regime_tables else regimes[0]
    def capacity_diagnosis(body: Mapping[str, Any], regime: str) -> dict[str, Any]:
        """The declared diagnosis of one regime's shared scheme, from its own telemetry."""

        return capacity_diagnosis_block(
            body, capacity_diagnosis_arm_name(regime), regime
        )

    return {
        "question": (
            "with the loop locked on one item, is a second written item suppressed, and "
            "does a two-item loop hold both against the single-item and no-loop cases?"
        ),
        "items": {"headline": headline, "second": second},
        "per_arm": per_arm,
        "second_item_suppression": suppression,
        "two_item_loop_verdict": two_item_verdict,
        "diagnosis": capacity_diagnosis(body, "amplifying"),
        "diagnosis_by_regime": {
            name: capacity_diagnosis(body, name)
            for name in regimes
            if capacity_diagnosis_arm_name(name) in body["arms"]
            and "telemetry" in body["arms"][capacity_diagnosis_arm_name(name)]
        },
        "regimes": regime_tables,
        "regime_gains": {name: float(gain) for name, gain in regime_gains.items()},
        "schemes": regime_tables["amplifying"]["schemes"],
        "regime_of_schemes": "amplifying",
        "capacity_limit_by_regime": {
            name: table["capacity_limit_items"] for name, table in regime_tables.items()
        },
        "capacity_limit_items": regime_tables[holding_regime]["capacity_limit_items"],
        "capacity_limit_regime": holding_regime,
        "capacity_limit_declared": (
            "the headline capacity figure is taken from the declared holding regime, the "
            "measured neutral gain, because an amplifying setting grows the written mode "
            "without bound inside the declared horizon and cannot answer whether anything "
            "is held; the amplifying regime's rows are reported beside it, labelled"
        ),
        "declared_items": names,
    }


def genericity_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The declared genericity family: the declared setting on further declared items."""

    config = body["declared"]
    arms = body["arms"]
    family = {
        name: row for name, row in arms.items() if row["declared"]["family"] == "genericity"
    }
    headline_arm = arms[body["best_declared_phase_setting"]["name"]]
    headline_name = config["headline_item"]
    per_item: dict[str, Any] = {
        headline_name: {
            "arm": headline_arm["arm"],
            "width": config["cited_item_widths"].get(headline_name),
            "gain": float(headline_arm["declared"]["gain"]),
            "loop_retention": headline_arm["horizon"]["item_retention"][headline_name],
            "horizon_ticks": int(headline_arm["horizon"]["tick"]),
            "loop_growth_rate_per_tick": growth_rate_per_tick(headline_arm),
            "no_loop_retention": arms["drift-no-refresh-no-loop"]["horizon"][
                "item_retention"
            ][headline_name],
            "no_loop_growth_rate_per_tick": growth_rate_per_tick(
                arms["drift-no-refresh-no-loop"]
            ),
            "unwritten_max_share": headline_arm["horizon"]["unwritten_max_share"],
            "frame_energy_ratio": headline_arm["horizon"]["frame_energy_ratio"],
        }
    }
    for index in config["genericity_items"]:
        loop_name = f"genericity-{index}-loop"
        control_name = f"genericity-{index}-no-loop"
        item = index
        per_item[item] = {
            "arm": loop_name,
            "width": config["cited_item_widths"].get(item),
            "gain": float(family[loop_name]["declared"]["gain"]),
            "loop_retention": family[loop_name]["horizon"]["item_retention"][item],
            "horizon_ticks": int(family[loop_name]["horizon"]["tick"]),
            "loop_growth_rate_per_tick": growth_rate_per_tick(family[loop_name]),
            "no_loop_retention": family[control_name]["horizon"]["item_retention"][item],
            "no_loop_growth_rate_per_tick": growth_rate_per_tick(family[control_name]),
            "unwritten_max_share": family[loop_name]["horizon"]["unwritten_max_share"],
            "frame_energy_ratio": family[loop_name]["horizon"]["frame_energy_ratio"],
        }
    for item, row in per_item.items():
        row["amplification_over_no_loop"] = (
            row["loop_retention"] / row["no_loop_retention"]
            if row["no_loop_retention"]
            else None
        )
        row["no_loop_below_loop"] = bool(
            row["loop_retention"] > row["no_loop_retention"]
        )
    amplifications = {
        item: row["amplification_over_no_loop"]
        for item, row in per_item.items()
        if row["amplification_over_no_loop"] is not None
    }
    headline_amplification = amplifications.get(headline_name)
    margin = float(config["genericity_margin"])
    spread = (
        max(amplifications.values()) - min(amplifications.values())
        if amplifications
        else None
    )
    headline_rate = per_item[headline_name]["loop_growth_rate_per_tick"]
    rate_deviations = {
        item: (
            None
            if row["loop_growth_rate_per_tick"] is None or headline_rate is None
            else abs(float(row["loop_growth_rate_per_tick"]) - float(headline_rate))
        )
        for item, row in per_item.items()
    }
    return {
        "question": (
            "does the declared maintenance setting amplify only the headline item, or "
            "does it recur on the declared width-7 and width-14 items?"
        ),
        "per_item": per_item,
        "amplification_over_no_loop": amplifications,
        "amplification_spread": spread,
        "margin": margin,
        "declared_criterion": (
            "the declared setting is called generic when every declared item's loop "
            "retention exceeds its own no-loop retention and every item's per-tick "
            "growth rate is within the declared margin of the headline item's, since a "
            "retention *ratio* over a long horizon is dominated by each item's own "
            "lifetime rather than by the loop"
        ),
        "per_item_growth_rate_deviation": rate_deviations,
        "same_growth_rate_within_margin": {
            item: bool(deviation is not None and deviation <= margin)
            for item, deviation in rate_deviations.items()
        },
        "headline_loop_growth_rate_per_tick": headline_rate,
        "all_items_amplified": bool(
            all(row["no_loop_below_loop"] for row in per_item.values())
        ),
        "generic_by_declared_criterion": bool(
            all(row["no_loop_below_loop"] for row in per_item.values())
            and all(
                deviation is not None and deviation <= margin
                for deviation in rate_deviations.values()
            )
        ),
        "item_widths": {item: row["width"] for item, row in per_item.items()},
    }


def feedback_sentence(reading: Mapping[str, Any]) -> str:
    """One plain sentence answering the maintenance question with the measured figures."""

    composition_clause = composition_sentence_clause(reading)


    drift = reading["per_family_best"]["drift"]
    refresh = reading["per_family_best"]["refresh"]
    loop = reading["per_family_best"]["closed_loop_declared_gains"]
    saturation = reading["per_family_best"]["closed_loop_saturation"]
    multi = reading["per_family_best"]["multi_item"]
    neutral = reading["neutral_stability"]["arms_satisfying"]
    disturbance = reading["unwritten_direction_disturbance"]
    drift_disturbance = disturbance["drift_horizon_unwritten_max_share"]
    saturation_disturbance = disturbance["per_arm"][saturation["arm"]][
        "horizon_unwritten_max_share"
    ]
    phase = reading["phase_grid"]
    ladder = reading["refresh_ladder"]
    return (
        "With sources off, the drift baseline's alignment retention at the horizon is "
        f"{drift['alignment_retention_at_horizon']!r} (its mid-run sample is "
        f"{drift['mid_retention']!r} and its last-half minimum is "
        f"{drift['last_half_min_retention']!r}, so the baseline rebounds rather than "
        "monotonically decays); the strongest declared positive gain "
        f"({loop['gain']:g}) reaches {loop['alignment_retention_at_horizon']!r} for "
        f"{loop['drive_work_total']!r} of drive work, which is below the no-loop baseline, "
        f"while the saturating loop at gain {saturation['gain']:g} reaches "
        f"{saturation['alignment_retention_at_horizon']!r} for "
        f"{saturation['drive_work_total']!r} of drive work with a frame energy ratio of "
        f"{saturation['frame_energy_ratio_at_horizon']!r}, a last-half retention ratio of "
        f"{saturation['last_half_retention_ratio']!r} and a horizon unwritten-direction "
        f"share of {saturation_disturbance!r} against the baseline's "
        f"{drift_disturbance!r}; the open-loop refresh holds "
        f"{refresh['alignment_retention_at_horizon']!r} for {refresh['drive_work_total']!r} "
        f"of drive work, the arms satisfying the declared neutral-stability criterion are "
        f"{neutral!r}, and at two written items the selected loop setting "
        f"({multi['setting']['name']}) leaves a minimum item retention of "
        f"{multi['loop_min_item_retention']!r} against {multi['control_min_item_retention']!r} "
        "with no loop and a horizon unwritten-direction share of "
        f"{disturbance['per_arm'][multi['loop_arm']]['horizon_unwritten_max_share']!r} against "
        f"{disturbance['per_arm'][multi['control_arm']]['horizon_unwritten_max_share']!r}; "
        "under the declared phase grid the declared prediction is met by "
        f"{len(phase['arms_meeting_prediction'])} arms, all of them at the two most "
        "negative declared phases, and the measured best is theta "
        f"{phase['best_theta_degrees']!r} degrees at gain {phase['best_gain']!r} "
        f"reaching {phase['best_retention_at_horizon']!r} for "
        f"{phase['per_arm'][phase['best_arm']]['drive_work_total']!r} of drive work "
        f"({phase['per_arm'][phase['best_arm']]['drive_work_over_refresh_every_8']!r} of "
        "the refresh-every-8 work) with a frame energy ratio of "
        f"{phase['per_arm'][phase['best_arm']]['frame_energy_ratio_at_horizon']!r} and an "
        "unwritten-direction share of "
        f"{phase['per_arm'][phase['best_arm']]['unwritten_max_share']!r} against the "
        f"baseline's {phase['prediction_terms']['drift_baseline_unwritten_max_share']!r}, "
        f"which is {phase['best_theta_offset_from_quarter_period_degrees']!r} degrees from "
        "the declared quarter-period phase, so the declared quarter-period lag is not the "
        "phase that maintains; on the declared refresh ladder the critical interval is "
        f"{ladder['items'][ladder['items_pair'][0]]['critical_interval_ticks']!r} ticks for "
        f"the width-{ladder['item_widths'][ladder['items_pair'][0]]} item "
        f"({ladder['items_pair'][0]}) and "
        f"{ladder['items'][ladder['items_pair'][1]]['critical_interval_ticks']!r} ticks for "
        f"the width-{ladder['item_widths'][ladder['items_pair'][1]]} item "
        f"({ladder['items_pair'][1]}) over the declared "
        f"{ladder['declared_ladder_horizon_ticks']!r}-tick horizon shared by both, whose "
        "ratios to the cited intrinsic lifetimes are "
        f"{ladder['critical_interval_over_cited_lifetime'][ladder['items_pair'][0]]!r} and "
        f"{ladder['critical_interval_over_cited_lifetime'][ladder['items_pair'][1]]!r}, so "
        "the two ratios agree within the declared tolerance: "
        f"{ladder['ratios_agree_across_items_within_tolerance']!r}; refining the "
        "inverted-phase gain below the declared grid measures the neutral gain at "
        f"{reading['neutral_gain']['measured']!r} (bracket "
        f"{reading['neutral_gain']['measured_bracket']!r}, width "
        f"{reading['neutral_gain']['measured_bracket_width']!r}, grid monotone in "
        f"gain: {reading['neutral_gain']['grid_monotone_in_gain']!r}) against the "
        "declared prediction's "
        f"{reading['neutral_gain']['predicted']['gain'] if reading['neutral_gain']['predicted']['found'] else None!r} "
        f"(relative error {reading['neutral_gain']['relative_error_of_prediction']!r} "
        f"against the declared allowance {reading['neutral_gain']['allowance']!r}), while "
        "the declared linearized injection finds no neutral gain up to the declared "
        f"ceiling ({reading['neutral_gain']['predicted_linearized']['found']!r}), and the "
        "declared prediction reproduces the inverted-phase arms' horizon retention to "
        f"within {reading['neutral_gain']['prediction_retention_allowance']!r} for "
        f"{len(reading['neutral_gain']['arms_within_retention_allowance'])!r} of "
        f"{len(reading['neutral_gain']['arms_within_retention_allowance']) + len(reading['neutral_gain']['arms_outside_retention_allowance'])!r} "
        "declared arms; over the declared "
        f"{reading['long_horizon']['horizon_ticks']!r}-tick horizon sampled every "
        f"{reading['long_horizon']['sample_spacing_ticks']!r} ticks the loop at the best "
        "declared setting reaches "
        f"{reading['long_horizon']['per_arm']['long-horizon-best-gain']['horizon_measure_retention']!r} "
        "with a frame energy ratio of "
        f"{reading['long_horizon']['per_arm']['long-horizon-best-gain']['horizon_frame_energy_ratio']!r} "
        "and a horizon unwritten-direction share of "
        f"{reading['long_horizon']['per_arm']['long-horizon-best-gain']['horizon_unwritten_max_share']!r}, "
        "its growth decelerating but not saturating inside the declared horizon, its "
        "written-direction alignment at the horizon standing at "
        f"{reading['long_horizon']['per_arm']['long-horizon-best-gain']['written_direction_alignment_at_horizon']!r} "
        "of its first sample, and its declared beta=0 counterpart differing by "
        f"{reading['long_horizon']['beta_zero_comparison']['long-horizon-best-gain']['relative_difference']!r} "
        "(the declared quartic coupling is inactive at the declared amplitudes); at two "
        "written items the locked loop holds the headline item's back-half mean at "
        f"{reading['capacity']['per_arm']['locked_on_headline']['headline_second_half_mean']!r} "
        "while the second item's back-half mean is "
        f"{reading['capacity']['second_item_suppression']['second_item_second_half_mean_under_locked_loop']!r} "
        "against "
        f"{reading['capacity']['second_item_suppression']['second_item_second_half_mean_without_loop']!r} "
        "with no loop, a difference of "
        f"{reading['capacity']['second_item_suppression']['difference']!r} against the declared "
        f"margin {reading['capacity']['second_item_suppression']['margin']!r} (suppressed: "
        f"{reading['capacity']['second_item_suppression']['suppressed_beyond_control']!r}, held above: "
        f"{reading['capacity']['second_item_suppression']['held_above_control']!r}), so the locked loop "
        "is selective rather than evicting; the declared two-item loop holds the headline "
        "item's back-half mean at "
        f"{reading['capacity']['two_item_loop_verdict']['headline_second_half_mean_two_item_loop']!r} "
        "against the single-item loop's "
        f"{reading['capacity']['two_item_loop_verdict']['headline_second_half_mean_single_item_loop']!r} "
        "and suppresses the second item to "
        f"{reading['capacity']['two_item_loop_verdict']['second_second_half_mean_two_item_loop']!r} "
        "against "
        f"{reading['capacity']['two_item_loop_verdict']['second_second_half_mean_no_loop_control']!r} "
        "with no loop (suppressed: "
        f"{reading['capacity']['two_item_loop_verdict']['second_item_suppressed_by_two_item_loop']!r}), "
        "so the declared single read-back two-item loop does not maintain both ("
        f"{reading['capacity']['two_item_loop_verdict']['both_items_above_control_with_margin']!r}); "
        "against the same no-loop control the declared maintenance schemes are reported per "
        f"declared gain regime at gains {reading['capacity']['regime_gains']!r}, and the "
        "measured capacity in the declared holding regime (the measured neutral gain, where "
        "the loop neither grows nor decays the mode) is "
        f"{reading['capacity']['capacity_limit_items']!r} item(s) "
        f"({reading['capacity']['capacity_limit_regime']!r} regime, schemes holding both items: "
        f"{reading['capacity']['regimes'][reading['capacity']['capacity_limit_regime']]['schemes_holding_both_items']!r}"
        ", per-scheme back-half means "
        f"{ {name: (row['headline_second_half_mean'], row['second_second_half_mean']) for name, row in reading['capacity']['regimes'][reading['capacity']['capacity_limit_regime']]['schemes'].items()}!r}); "
        "the amplifying regime's rows are carried beside them and labelled as amplifying "
        f"(gain {reading['capacity']['regime_gains']['amplifying']!r}: schemes holding both items "
        f"{reading['capacity']['regimes']['amplifying']['schemes_holding_both_items']!r}, back-half means "
        f"{ {name: (row['headline_second_half_mean'], row['second_second_half_mean']) for name, row in reading['capacity']['schemes'].items()}!r}, "
        f"arms over the declared energy bound {reading['capacity']['regimes']['amplifying']['scheme_arms_over_declared_energy_bound']!r}), "
        "the shared scheme's measured mechanism being that "
        f"{reading['capacity']['diagnosis']['mechanism']!r}; "
        "the declared setting is generic by the declared criterion "
        f"({reading['genericity']['generic_by_declared_criterion']!r}) across the declared "
        "widths "
        f"{reading['genericity']['item_widths']!r} with loop growth rates "
        f"{ {item: row['loop_growth_rate_per_tick'] for item, row in reading['genericity']['per_item'].items()}!r} "
        "against no-loop rates "
        f"{ {item: row['no_loop_growth_rate_per_tick'] for item, row in reading['genericity']['per_item'].items()}!r}, "
        "though the raw amplification ratios over the declared horizon are item-specific "
        f"({reading['genericity']['amplification_over_no_loop']!r})"
        + composition_clause
    )


def composition_sentence_clause(reading: Mapping[str, Any]) -> str:
    """The composition legs, when the measurement carried them, as one sentence clause."""

    composition = reading.get("composition")
    if composition is None:
        return ""
    quiet = reading["composition"]["quiet_regime"]
    quiet_holds = quiet["holds"]
    quiet_headline = quiet_holds[next(iter(quiet_holds))]
    curve = reading["composition"]["capacity_curve"]
    split = reading["composition"]["split_sweep"]
    split_means = {
        name: (row["headline_second_half_mean"], row["second_second_half_mean"])
        for name, row in split["splits"].items()
    }
    return (
        "; "
        "composed on the flat-inertia metric ("
        f"{reading['composition']['profile']['name']!r}, built by the metric harness) the "
        "declared loop's neutral gain is re-measured there rather than reused "
        f"({reading['composition']['flat_neutral_gain']!r} in a bracket "
        f"{reading['composition']['flat_neutral_bracket']!r}), and at that gain the hold leg "
        f"is {reading['composition']['hold']['held_above_control']!r} with retention "
        f"{reading['composition']['hold']['retention_at_horizon']!r} against the flat no-loop "
        f"control's {reading['composition']['hold']['control_retention_at_horizon']!r}, the "
        "declared capacity family gives "
        f"{reading['composition']['capacity']['capacity_limit_items']!r} item(s) "
        f"(schemes holding both: {reading['composition']['capacity']['schemes_holding_both_items']!r}), "
        "the locked loop still reads back on the item it drives "
        f"({reading['composition']['verdicts']['locked_loop_holds_the_item_it_reads_back_on']!r}) "
        f"but the shared scheme now holds both "
        f"({reading['composition']['verdicts']['shared_scheme_holds_both_items']!r}), and the "
        "cited aiming lever is "
        f"{reading['composition']['aim']['aiming_lever_default']!r} on the default metric "
        f"against {reading['composition']['aim']['aiming_lever_flat']!r} on the flat one, so "
        "aiming survives the flat metric: "
        f"{composition['aim']['aiming_survives_the_flat_metric']!r}; the declared capacity "
        "curve runs the declared schemes at the declared item counts "
        f"{sorted(int(count) for count in curve['counts'])!r} with the "
        "declared per-tick work ceiling spent at every count, and the largest count at which "
        "each scheme holds every declared item is "
        f"{curve['limit_by_scheme']!r} "
        f"({curve['capacity_limit_evidence']!r}), the declared "
        "drive-split sweep reports the two declared items' retentions under the declared "
        "splits "
        f"{split_means!r} "
        f"with a split dependence of {split['split_dependent']!r} "
        f"({split['split_dependence']!r}), and under the flat hold the "
        "frame energy at the horizon is "
        f"{quiet_headline['frame_energy_ratio_at_horizon']!r} against the default profile's "
        "own neutral hold's "
        f"{quiet['default_profile_hold']['frame_energy_ratio_at_horizon']!r} "
        "at the same horizon, the falling-energy hold being reported on the declared items "
        f"{quiet['items_with_falling_energy_while_holding']!r} "
        f"and (falling at {quiet['gain_factors_with_falling_energy']!r} "
        f"of the declared gain ladder), the measured attribution being {quiet['quoting_regime']!r}"
    )


# The declared flat-inertia profile the composition legs run on. It is the metric
# harness's `ladder-uniform` member (equal total inertia, flat inertia), built through that
# harness's own declared builder rather than re-derived here, so the flat profile this
# receipt measures on is the harness's declared object and not a copy of it that could drift.
FLAT_PROFILE_NAME = "ladder-uniform"
FLAT_PROFILE_SOURCE = (
    "run_fractal_metric_exploration.build_metric_profile("
    "run_fractal_metric_exploration.ladder_row('ladder-uniform'))"
)
# The declared aim leg is cited from the ladder harness's committed receipt, not re-measured
# here: that harness's own default-profile deep-write surface and its flat-inertia
# counterpart, read out of the receipt by key so no figure is transcribed by hand. The
# declared instruments that produced them are named with the figures.
CITED_LADDER_AIM_DEFAULT_PROFILE = "helix7"
CITED_LADDER_AIM_FLAT_PROFILE = "flat-inertia"
# The declared aiming-lever margin: the aim leg survives the flat metric only when the
# cited flat lever exceeds one by more than this, so a lever of one (aiming buys nothing)
# and a lever of one plus a rounding difference are both reported as not surviving.
COMPOSITION_AIM_LEVER_MARGIN = 0.25
COMPOSITION_DRIFT_LABELS = ("headline", "narrow")
CITED_LADDER_AIM_INSTRUMENTS = {
    "headline_final_retention": (
        "run_fractal_ladder_exploration durability block: the profile's own headline "
        "item final retention over the declared ladder horizon"
    ),
    "best_deep_write_measured_final": (
        "run_fractal_ladder_exploration exhaustive_write_surface: the best measured "
        "final retention over the declared exhaustive single-write candidates"
    ),
}


def flat_inertia_profile() -> Any:
    """The declared flat-inertia profile, built by the metric harness's own builder."""

    import run_fractal_metric_exploration as metric

    return metric.build_metric_profile(metric.ladder_row(FLAT_PROFILE_NAME))


def cited_ladder_aim_block() -> dict[str, Any]:
    """The ladder receipt's own aim figures, read from its committed receipt.

    The composition's aim leg is a citation, not a measurement: the ladder harness already
    measured the deepest declared write on the default profile and on the flat profile, so
    this block reads those figures out of that receipt by key and reports the aiming lever
    -- how much the best deep write beats writing the profile's headline direction itself --
    on each metric.
    """

    path = Path(CITED_LADDER_RECEIPT)
    if not path.exists():
        raise FileNotFoundError(
            f"the cited ladder receipt {CITED_LADDER_RECEIPT!r} is required for the "
            "composition's cited aim leg"
        )
    receipt = json.loads(path.read_text(encoding="utf-8"))
    surface = receipt["exhaustive_write_surface"]
    profiles = receipt["profiles"]
    figures: dict[str, Any] = {}
    for label, name in (
        ("default_profile", CITED_LADDER_AIM_DEFAULT_PROFILE),
        ("flat_profile", CITED_LADDER_AIM_FLAT_PROFILE),
    ):
        headline_item = profiles[name]["items"][0]
        figures[label] = {
            "profile": name,
            "headline_item": headline_item.get("item", "the profile's first declared item"),
            "headline_final_retention": float(headline_item["final_retention"]),
            "best_deep_write_measured_final": float(surface[name]["best_measured_final"]),
        }
        figures[label]["aiming_lever"] = (
            figures[label]["best_deep_write_measured_final"]
            / figures[label]["headline_final_retention"]
        )
    return {
        "cited_receipt": CITED_LADDER_RECEIPT,
        "cited_instruments": CITED_LADDER_AIM_INSTRUMENTS,
        "declared": (
            "the aim leg is cited from the ladder harness's committed receipt and is not "
            "re-measured here: the deepest write that harness declared is compared with the "
            "profile's own headline write on the default metric and on the flat metric, and "
            "the aiming lever is the ratio of the two. A lever near one on the flat metric "
            "means flat already leaves the headline direction slow, so there is nothing left "
            "for aiming to buy; a lever far above one means aiming still buys retention"
        ),
        "default_profile": figures["default_profile"],
        "flat_profile": figures["flat_profile"],
        "aiming_lever_default": figures["default_profile"]["aiming_lever"],
        "aiming_lever_flat": figures["flat_profile"]["aiming_lever"],
        "aiming_survives_the_flat_metric": bool(
            figures["flat_profile"]["aiming_lever"] - 1.0
            > float(COMPOSITION_AIM_LEVER_MARGIN)
        ),
        "aiming_lever_margin": float(COMPOSITION_AIM_LEVER_MARGIN),
    }


def composition_block(
    config: FeedbackConfig,
    base: ResonantProfile,
    default_hold: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The composition legs: the declared ingredients re-measured on the flat metric.

    The declared loop's neutral gain is an operating point of the field it was measured on
    -- the refinement solves the loop's work balance against the state's momentum -- so this
    block re-sweeps the neutral gain on the flat-inertia profile with the same declared
    bracket and bisection, then runs the hold leg (the single-item loop at that gain over the
    declared long horizon) and the declared capacity family at that gain, each against the
    flat profile's own no-loop control at the same horizon. The aim leg is the cited ladder
    comparison, not a re-measurement.
    """

    flat = flat_inertia_profile()
    long_ticks = int(config.long_horizon_ticks)
    samples = tuple(int(t) for t in config.long_horizon_sample_ticks)
    items = (int(config.headline_item_index), int(config.capacity_item_index))
    captures = durability.capture_items(durable_config(config), flat)
    phase = phase_readout_block(config, captures, flat, long_ticks)
    phase_reference = {
        "direction": quadrature_direction(config, captures, config.headline_item_index),
        "scale": float(phase["sign_references"]["quadrature_scale"]),
    }
    arms: dict[str, Any] = {}
    control_arm = LoopArm(
        COMPOSITION_CONTROL_ARM,
        items,
        family="composition",
        horizon_ticks=long_ticks,
        sample_ticks=samples,
        regime="flat",
    )
    arms[control_arm.name] = run_stream(
        config, captures, control_arm, phase_reference, flat
    )
    # The flat metric's own drift, on the item the loop reads back on and on the narrowest
    # declared item, so the composition can say whether flat already slows every declared
    # direction rather than only the headline one.
    for label, index in (
        (COMPOSITION_DRIFT_LABELS[0], int(config.headline_item_index)),
        (COMPOSITION_DRIFT_LABELS[1], int(config.capacity_item_index)),
    ):
        name = f"flat-drift-{label}"
        arm = LoopArm(
            name,
            (index,),
            family="composition",
            horizon_ticks=long_ticks,
            sample_ticks=samples,
            measure_item_index=int(index),
            regime="flat",
        )
        arms[name] = run_stream(config, captures, arm, phase_reference, flat)
    refinement = measure_neutral_gain(
        config,
        captures,
        phase_reference,
        flat,
        arms,
        drift_arm=COMPOSITION_CONTROL_ARM,
        name_prefix="flat-",
    )
    gain = float(refinement["measured_gain"])
    item_readouts = item_phase_readouts(config, captures, flat, long_ticks, items)
    item_references = per_item_phase_references(config, captures, item_readouts, items)
    for arm in capacity_regime_arm_declarations(config, "flat", gain):
        arms[arm.name] = run_stream(
            config,
            captures,
            arm,
            phase_reference,
            flat,
            item_references if len(arm.drive_items or ()) > 1 else None,
        )
    # The declared capacity curve, drive-split sweep and quiet-regime legs: all of them run
    # at the flat profile's own measured neutral gain, never at the default field's, so a
    # row of any leg is a statement about this profile at this operating point.
    curve_counts = tuple(int(count) for count in config.capacity_curve_counts)
    curve_items = {
        count: capacity_curve_items(config, count) for count in curve_counts
    }
    curve_references = per_item_phase_references(
        config,
        captures,
        item_phase_readouts(
            config,
            captures,
            flat,
            long_ticks,
            tuple(
                sorted({index for indices in curve_items.values() for index in indices})
            ),
        ),
        tuple(
            sorted({index for indices in curve_items.values() for index in indices})
        ),
    )
    for arm in capacity_curve_arm_declarations(config, gain, curve_counts):
        references = (
            curve_references
            if (arm.drive_items or arm.phase_locked)
            else None
        )
        arms[arm.name] = run_stream(
            config,
            captures,
            arm,
            phase_reference,
            flat,
            references,
        )
    for arm in capacity_split_arm_declarations(config, gain):
        arms[arm.name] = run_stream(
            config,
            captures,
            arm,
            phase_reference,
            flat,
            item_references,
        )
    for arm in quiet_regime_arm_declarations(config, gain):
        arms[arm.name] = run_stream(config, captures, arm, phase_reference, flat)
    body_like = {"declared": config.as_dict(), "arms": arms}
    table = capacity_regime_table(
        body_like, "flat", gain, control_arm=COMPOSITION_CONTROL_ARM
    )
    diagnosis = capacity_diagnosis_block(
        body_like,
        capacity_arm_name("flat", "shared-two-item"),
        "flat",
        control_arm=COMPOSITION_CONTROL_ARM,
    )
    curve = capacity_curve_block(body_like, gain)
    split = capacity_split_block(body_like, gain, control_arm=COMPOSITION_CONTROL_ARM)
    quiet = quiet_regime_block(body_like, default_hold, gain)
    margin = float(config.capacity_suppression_margin)
    hold = arms[capacity_arm_name("flat", "single-item-headline")]
    control = arms[COMPOSITION_CONTROL_ARM]
    hold_retention = hold["neutral_stability"]["measure_retention_at_horizon"]
    control_retention = control["neutral_stability"]["measure_retention_at_horizon"]
    narrow = arms[f"flat-drift-{COMPOSITION_DRIFT_LABELS[1]}"]
    headline_drift = arms[f"flat-drift-{COMPOSITION_DRIFT_LABELS[0]}"]
    aim = cited_ladder_aim_block()
    hold_difference = float(hold_retention) - float(control_retention)
    drift_contrast = float(
        narrow["neutral_stability"]["measure_retention_at_horizon"]
    ) - float(headline_drift["neutral_stability"]["measure_retention_at_horizon"])
    return {
        "question": (
            "do the three measured ingredients -- a loop held at its own neutral gain, the "
            "selectivity of a locked loop, and the aiming lever -- survive when they are "
            "composed on a metric that changes the whole spectrum?"
        ),
        "declared": (
            "every leg here runs on the declared flat-inertia profile, built by the metric "
            "harness's own builder; the neutral gain is re-swept on that profile by the same "
            "declared grid and bisection as the shipped one, because the gain solves the "
            "loop's work balance against the state's momentum and is a property of the field "
            "it was measured on. The hold and capacity legs are measured against the flat "
            "profile's own no-loop control at the same declared horizon and the same two "
            "declared items, and the aim leg is cited from the ladder harness's receipt"
        ),
        "profile": {
            "name": FLAT_PROFILE_NAME,
            "source": FLAT_PROFILE_SOURCE,
            "beta": float(flat.beta),
            "declared": (
                "the equal-total-inertia flat-inertia member of the metric harness's declared "
                "ladder family, imported read-only through that harness's builder"
            ),
        },
        "flat_neutral_gain": refinement,
        "hold": {
            "arm": hold["arm"],
            "gain": gain,
            "retention_at_horizon": hold_retention,
            "alignment_retention_at_horizon": hold["horizon"]["alignment_retention"],
            "measure_retention_mid": hold["neutral_stability"]["measure_mid_retention"],
            "measure_last_half_min": hold["neutral_stability"][
                "measure_last_half_min_retention"
            ],
            "frame_energy_ratio": hold["horizon"]["frame_energy_ratio"],
            "unwritten_max_share": hold["horizon"]["unwritten_max_share"],
            "neutral_by_declared_criterion": hold["neutral_stability"][
                "neutrally_stable"
            ],
            "control_arm": control["arm"],
            "control_retention_at_horizon": control_retention,
            "control_frame_energy_ratio": control["horizon"]["frame_energy_ratio"],
            "control_unwritten_max_share": control["horizon"]["unwritten_max_share"],
            "retention_minus_control": hold_difference,
            "margin": margin,
            "held_above_control": bool(hold_difference > margin),
            "declared": (
                "the declared single-item loop on the headline item at the flat profile's own "
                "measured neutral gain, over the declared long horizon, against the flat "
                "profile's no-loop two-item control at the same horizon"
            ),
        },
        "drift_contrast": {
            "headline_arm": headline_drift["arm"],
            "headline_retention_at_horizon": headline_drift["neutral_stability"][
                "measure_retention_at_horizon"
            ],
            "narrow_arm": narrow["arm"],
            "narrow_item": narrow["declared"]["measured_item"],
            "narrow_retention_at_horizon": narrow["neutral_stability"][
                "measure_retention_at_horizon"
            ],
            "narrow_minus_headline": drift_contrast,
            "margin": margin,
            "narrow_held_above_headline": bool(drift_contrast > margin),
            "declared": (
                "the flat metric's own no-loop drift on the headline item and on the narrowest "
                "declared item, so the receipt can say from its own numbers whether flat slows "
                "every declared direction or only the headline one"
            ),
        },
        "aim": aim,
        "capacity": table,
        "capacity_curve": curve,
        "split_sweep": split,
        "quiet_regime": quiet,
        "diagnosis": diagnosis,
        "verdicts": {
            "hold": bool(
                hold["neutral_stability"]["neutrally_stable"]
                and hold_difference > margin
            ),
            "locked_loop_holds_the_item_it_reads_back_on": bool(
                table["schemes"]["locked-on-headline"]["headline_held_above_control"]
            ),
            "locked_loop_suppresses_the_item_it_does_not": bool(
                not table["schemes"]["locked-on-headline"]["second_held_above_control"]
            ),
            "shared_scheme_holds_both_items": bool(
                table["schemes"]["shared-two-item"]["both_items_held"]
            ),
            "a_multiplexed_scheme_holds_both_items": bool(
                table["schemes"]["time-multiplex-block"]["both_items_held"]
                or table["schemes"]["time-multiplex-adjacent"]["both_items_held"]
            ),
            "selectivity_pattern_preserved": bool(
                table["schemes"]["locked-on-headline"]["headline_held_above_control"]
                and not table["schemes"]["shared-two-item"]["both_items_held"]
            ),
            "capacity_items": int(table["capacity_limit_items"]),
            "capacity_curve_limits_by_scheme": {
                scheme: row["largest_count_holding_every_item"]
                for scheme, row in curve["limit_by_scheme"].items()
            },
            "capacity_curve_any_scheme_holds_every_declared_item_at_the_largest_count": bool(
                any(
                    row["largest_count_holding_every_item"]
                    == max(curve["counts"][str(count)]["count"] for count in curve["counts"])
                    for row in curve["limit_by_scheme"].values()
                )
            ),
            "drive_split_dependent": bool(split["split_dependent"]),
            "quiet_regime_single_item_frames_increase_throughput": bool(
                quiet["every_declared_single_item_hold_increases_throughput"]
            ),
            "quiet_regime_single_item_frames_falling": list(
                quiet["items_with_falling_energy_while_holding"]
            ),
            "quiet_regime_energy_falls_at_every_declared_gain": bool(
                quiet["every_declared_gain_falls"]
            ),
            "aiming_survives_the_flat_metric": bool(
                aim["aiming_survives_the_flat_metric"]
            ),
            "declared": (
                "hold is the declared neutral criterion on the flat loop *and* its retention "
                "above the flat no-loop control by more than the declared margin; the "
                "selectivity verdict is the shipped pattern on the default metric -- the "
                "locked loop holds the item it reads back on and the shared loop does not "
                "hold both -- reported beside the component readings (whether the locked loop "
                "suppresses the item it does not read back on, whether the shared loop holds "
                "both, whether any declared multiplexed scheme holds both), because on a "
                "metric that changes the whole spectrum those components need not move "
                "together; aiming survives when the cited flat aiming lever is above one by "
                "more than the declared lever margin"
            ),
        },
        "margin": margin,
        "aiming_lever_margin": float(COMPOSITION_AIM_LEVER_MARGIN),
        "arms": arms,
    }


def durable_config(config: FeedbackConfig) -> Any:
    """The durability harness configuration this exploration reuses by import."""

    return durability.DurabilityConfig(
        read_frame_path=config.read_frame_path,
        headline_item_index=config.headline_item_index,
        write_budget=config.write_budget,
        activity_ticks=int(config.horizon_ticks),
        activity_samples=config.durability_samples,
        activity_demand=config.activity_demand,
    )


def measure(
    config: FeedbackConfig,
    profile: ResonantProfile | None = None,
    composition: bool = True,
) -> dict[str, Any]:
    """Run every declared arm and return the receipt body without its digest.

    ``composition`` builds the composition legs, which measure the declared ingredients on
    the declared flat-inertia profile rather than on ``profile``. A caller that passes its
    own ``profile`` is measuring that profile, so it passes ``composition=False`` unless it
    wants both.
    """

    base = profile or ResonantProfile()
    beta_zero = replace(base, beta=float(config.beta_zero))
    captures = durability.capture_items(durable_config(config), base)
    calibration = actuator_calibration_block(
        config, captures, base, int(config.long_horizon_ticks)
    )
    calibration_beta_zero = actuator_calibration_block(
        config, captures, beta_zero, int(config.horizon_ticks)
    )
    phase = phase_readout_block(config, captures, base, int(config.long_horizon_ticks))
    phase_reference = {
        "direction": quadrature_direction(config, captures, config.headline_item_index),
        "scale": float(phase["sign_references"]["quadrature_scale"]),
    }
    single = single_item_arm_declarations(config)
    arms: dict[str, Any] = {
        arm.name: run_stream(config, captures, arm, phase_reference, base)
        for arm in single
    }
    selected = select_best_stable_loop(arms)
    for arm in multi_item_arm_declarations(config, selected):
        arms[arm.name] = run_stream(config, captures, arm, phase_reference, base)
    refinement = measure_neutral_gain(config, captures, phase_reference, base, arms)
    best_phase_arm = max(
        (row for row in arms.values() if row["declared"]["family"] == "closed-loop-phase"),
        key=selection_retention,
    )
    best_gain = float(best_phase_arm["declared"]["gain"])
    for arm in long_horizon_arm_declarations(
        config, best_gain, refinement["measured_gain"]
    ):
        arms[arm.name] = run_stream(config, captures, arm, phase_reference, base)
    item_readouts = item_phase_readouts(
        config,
        captures,
        base,
        int(config.long_horizon_ticks),
        (int(config.headline_item_index), int(config.capacity_item_index)),
    )
    item_references = per_item_phase_references(
        config,
        captures,
        item_readouts,
        (int(config.headline_item_index), int(config.capacity_item_index)),
    )
    for arm in capacity_arm_declarations(config, best_gain):
        arms[arm.name] = run_stream(
            config,
            captures,
            arm,
            phase_reference,
            base,
            item_references if arm.phase_locked else None,
        )
    # The declared regimes other than the amplifying one: the neutral regime runs at the
    # measured neutral gain (the gain at which the declared loop neither grows nor decays
    # the written mode) and the bounded regime at the declared sub-saturation gain. Every
    # regime carries the same per-tick telemetry, so each regime's claim is diagnosable
    # from its own rows and no regime is reported on weaker evidence than another.
    capacity_regime_gains = {"amplifying": float(best_gain)}
    for regime in config.capacity_regimes:
        if regime == "amplifying":
            continue
        gain = (
            float(refinement["measured_gain"])
            if regime == "neutral"
            else float(config.capacity_bounded_gain)
        )
        capacity_regime_gains[regime] = gain
        for arm in capacity_regime_arm_declarations(config, regime, gain):
            arms[arm.name] = run_stream(
                config,
                captures,
                arm,
                phase_reference,
                base,
                item_references if arm.phase_locked else None,
            )
    for arm in genericity_arm_declarations(config, best_gain):
        arms[arm.name] = run_stream(config, captures, arm, phase_reference, base)
    default_hold = {
        "arm": arms[DEFAULT_NEUTRAL_HOLD_ARM]["arm"],
        "gain": float(arms[DEFAULT_NEUTRAL_HOLD_ARM]["declared"]["gain"]),
        "retention_at_horizon": float(
            arms[DEFAULT_NEUTRAL_HOLD_ARM]["neutral_stability"][
                "measure_retention_at_horizon"
            ]
        ),
        "frame_energy_ratio_at_horizon": float(
            arms[DEFAULT_NEUTRAL_HOLD_ARM]["horizon"]["frame_energy_ratio"]
        ),
        "frame_energy_ratio_max": float(
            arms[DEFAULT_NEUTRAL_HOLD_ARM]["horizon"]["frame_energy_ratio_max"]
        ),
        "declared": (
            "the same declared single-item hold at the default profile's own measured "
            "neutral gain over the same declared long horizon, so the flat profile's hold "
            "is read against the default field's rather than in isolation"
        ),
    }
    composition = (
        composition_block(config, base, default_hold) if composition else None
    )
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            **config.as_dict(),
            "declared_items": [
                {
                    "name": spec.name,
                    "path": spec.path,
                    "component": spec.component,
                    "flow_signal": list(spec.flow_signal),
                }
                for spec in durability.ITEM_SPECS
            ],
            "headline_item": durability.ITEM_SPECS[config.headline_item_index].name,
            "profile_beta": float(base.beta),
            "capacity_regime_gains": {
                name: float(gain) for name, gain in capacity_regime_gains.items()
            },
            "capacity_regime_declared": (
                "the amplifying regime runs at the best declared phase setting's measured "
                "gain, the neutral regime at the measured neutral gain of the declared "
                "loop, and the bounded regime at the declared sub-saturation gain; every "
                "regime runs the same declared schemes over the declared long horizon"
            ),
            "event_kind": EVENT_KIND,
            "definitions": DEFINITIONS,
            "read_frame": durability.declared_block(
                durable_config(config), base, captures
            )["read_frame"],
        },
        "recon": recon_block(config, captures),
        "phase_readout": {
            **phase,
            "per_item": item_readouts,
            "per_item_declared": (
                "every declared capacity scheme's own read-back is declared here: the "
                "headline item's readout above is the shared loop's single read-back, and "
                "this per-item block gives each capacity item its own quadrature direction, "
                "its own isolated post-write projection and its own measured quadrature "
                "scale, measured the same way and fitted to nothing"
            ),
        },
        "actuator_calibration": {
            "declared_profile": calibration,
            "beta_zero_profile": calibration_beta_zero,
            "declared": (
                "the declared actuator calibration and the declared free mode "
                "response, measured once per declared profile and used by the declared "
                "prediction of the loop's own neutral gain"
            ),
        },
        **({"composition": composition} if composition is not None else {}),
        "arms": arms,
        "selected_loop_setting": {
            "name": selected.name,
            "gain": selected.gain,
            "refresh_interval": selected.refresh_interval,
            "rule": DEFINITIONS["best_stable_loop_setting"],
        },
        "best_declared_phase_setting": {
            "name": best_phase_arm["arm"],
            "gain": best_gain,
            "phase_degrees": float(best_phase_arm["declared"]["phase_degrees"]),
            "measure_retention_at_horizon": best_phase_arm["neutral_stability"][
                "measure_retention_at_horizon"
            ],
            "rule": DEFINITIONS["best_declared_phase_setting"],
        },
        "neutral_gain_refinement": refinement,
    }
    body["cited_agreement"] = cited_agreement(body)
    body["reading"] = reading_block(body)
    body["reading"]["sentence"] = feedback_sentence(body["reading"])
    body["boundary"] = BOUNDARY
    return body


def build_receipt(
    config: FeedbackConfig, profile: ResonantProfile | None = None
) -> dict[str, Any]:
    body = measure(config, profile, composition=profile is None)
    return {**body, "receipt_digest": durability.receipt_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("_diag/fractal-feedback/exploration.json")
    )
    arguments = parser.parse_args()
    config = DECLARED
    started = perf_counter()
    receipt = build_receipt(config)
    elapsed = perf_counter() - started
    print(json.dumps(receipt["reading"], indent=1, sort_keys=True))
    print(json.dumps({"boundary": receipt["boundary"]}, indent=1, sort_keys=True))
    print(receipt["reading"]["sentence"])
    print(f"receipt_digest: {receipt['receipt_digest']}")
    print(f"elapsed_seconds: {elapsed:.2f}")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
    print(f"receipt: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
