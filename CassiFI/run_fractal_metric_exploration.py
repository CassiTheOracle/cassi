"""Bounded numerical exploration of *designed* inverse-mass (metric) profiles.

The survival harness measured that a written multi-item pattern outlives the
declared activity far better on the ``nested-core-shell`` body than on the
canonical default, and its attribution contrast put that gain on the projected
inverse-mass (metric) hook rather than on the connection graph.  This runner asks
the design question that follows: can the inverse-mass profile be *chosen* so the
body's slow, weakly coupled modes sit where the declared items are written, and
does minimum multi-item recovery rank the designs?  It is the counter-hypothesis
to solver-side maintenance: structure by metric instead of by feedback.

Declared family (at most 24 profiles; every construction rule, contrast
parameter and seed is in the receipt):

* ``default-inertance`` -- the canonical default, no hook at all;
* ``nested-shell-metric`` -- the nested shell metric the survival harness
  already uses, applied alone through the hook (its ``mass-only`` arm);
* ``canonical-metric-hook`` -- the canonical metric re-expressed through the
  hook, the channel-fidelity control: it must reproduce the default;
* a graded shell family, inverse mass ``contrast ** ring_distance(pool, core)``
  over the declared contrast settings, whose setting 0.7 coincides with the
  nested shell metric by construction;
* a declared deterministic randomized family, per-pool multipliers
  ``contrast ** u`` with ``u`` drawn from one declared generator per seed.

The survival harness's own reference scaffold (``nested-core-shell``, both
hooks) is measured beside them as a declared reference row, and the profiles are
built only by replacing the canonical profile's ``projected_inv_mass`` hook
(except the cross-rail leg, which also declares another rail).

Measured per profile, all through the existing harnesses by import:

* the declared ``k = 4`` activity arm and, for context, the declared single-item
  arm (same items, budget, activity, horizon and readout as the survival
  harness), plus the ``k = 2`` and ``k = 8`` arms for the ranking's top three and
  the default as a declared scaling/overfitting check;
* the frozen linear generator as the geometry harness builds it, its
  eigenvalue/participation structure, and a declared battery of overlap measures
  between the captured write directions and the slow modes;
* the arm's own activity figures (heartbeat work, dissipated work, packet energy
  ratio), because the canonical heartbeat's work allowance is metric dependent.

The top profile and the default are then rerun on one other declared rail, so
the ranking can be read for generalization rather than as a property of one
rail.  Every number here is a canonical-field numerical measurement in
controlled conditions; negative results are deliverables.  Nothing here
demonstrates task-level memory utility, semantic content, retrieval by a
consumer, or any advantage over alternative architectures.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry
import run_fractal_ladder_exploration as ladder
import run_fractal_placement_exploration as placement
import run_fractal_survival_exploration as survival

SCHEMA = "cassifi.fractal-metric-exploration.v1"

# --------------------------------------------------------------------------
# declared scope
# --------------------------------------------------------------------------
# The declared survival arm and the context arms, looked up by name in the
# durability harness's own ``arm_declarations`` output so its declaration stays
# the source of truth.  The single-item arm is the durability harness's headline
# arm; the k=4 arm is the attribution headline arm the survival harness ranked
# its scaffolds on.
SURVIVAL_ARM_NAME = "restart-and-activity-k4"
SINGLE_ITEM_ARM_NAME = "restart-and-activity"
CONTEXT_ARM_NAMES = ("restart-and-activity-k2", "restart-and-activity-k8")
DEFAULT_PROFILE_NAME = "default-inertance"
REFERENCE_METRIC_PROFILE_NAME = "nested-shell-metric"
CANONICAL_HOOK_PROFILE_NAME = "canonical-metric-hook"
REFERENCE_ROW_NAME = "nested-core-shell-reference"
# The geometry harness's declared arrangement the survival harness uses as its
# reference scaffold; the reference row is that arrangement, not a metric-only row.
REFERENCE_ARRANGEMENT = "nested-core-shell"

# Declared rails.  ``canonical`` is the default body's own rail (no transport
# hook); the second declared rail is the geometry harness's arrangement of that
# name, used for the generalization leg.
CANONICAL_RAIL = "canonical"
CROSS_RAIL_ARRANGEMENT = "recursive-paired-loops"
CROSS_RAIL_DEFAULT_ROW_NAME = "cross-rail-default-metric"
CROSS_RAIL_TOP_ROW_NAME = "cross-rail-top-metric"

# Declared graded family: the shape parameter is the contrast of the monotone
# shell metric ``contrast ** ring_distance(pool, core)``, whose endpoint 1.0 is
# the flat metric and whose setting ``nested-core-shell``'s own decay (0.7)
# coincides with the reference metric by construction.
SHELL_CONTRASTS = (0.005, 0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 0.85, 1.0)
SHELL_CORE_POOL = geometry.CORE_SHELL_CORE_POOL
SHELL_REFERENCE_DECAY = geometry.CORE_SHELL_INV_MASS_DECAY

# Declared randomized family: per-pool multipliers ``contrast ** u`` with
# ``u ~ Uniform(-1, 1)`` drawn from ``numpy.random.default_rng(seed)``, the
# declared contrast cycled over the listed settings, one profile per seed.
RANDOM_PROFILE_COUNT = 8
RANDOM_SEED_BASE = 20260916
RANDOM_SEED_STEP = 101
RANDOM_CONTRASTS = (0.05, 0.2, 0.5, 0.85)
RANDOM_JITTER_BOUND = 1.0
MAX_DECLARED_PROFILES = 24

# Declared context: how many ranking leaders get the k=2/k=8 scaling arms beside
# the default profile.
CONTEXT_PROFILE_COUNT = 3

# Declared margins.  The ranking margin is the survival harness's own declared
# profile recovery margin, read from it rather than restated; the headline margin
# is this runner's own declared can-fail bound on the best profile's advantage
# over the default, and the reported-relation margin is the Spearman coefficient
# the declared primary overlap measure must reach for the relation to count as
# tracked at all.
RANKING_MARGIN = survival.PROFILE_RECOVERY_MARGIN
HEADLINE_SURVIVAL_MARGIN = 0.2
PRIMARY_RELATION_MARGIN = 0.3
# Declared validity bounds on the biorthogonal (dual) spectral decomposition the
# participation measure rests on: the share is only a participation share if
# reconstructing the state from it works (relative residual) and if the individual
# eigenmodes are separated enough to have individual shares at all (an exactly
# degenerate spectrum makes a per-mode share basis dependent).  Both gates are
# measured per profile and reported; a profile that fails either is reported with
# its participation number marked as not a participation share.
SPECTRAL_RESIDUAL_TOLERANCE = 1e-6
SPECTRAL_SEPARATION_TOLERANCE = 1e-12
# Declared degeneracy tolerance: eigenvalues closer than this are treated as one
# numerically repeated eigenvalue and re-based inside their cluster by the
# rotation control.  The designed family's smallest measured separation is
# 1e-09, so this tolerance only ever groups numerically identical eigenvalues.
DEGENERATE_CLUSTER_TOLERANCE = 1e-11
# Declared basis-rotation control on the participation share: an exactly repeated
# eigenvalue leaves the eigenvectors inside its cluster arbitrary, so the share of
# the declared slow set has to be unchanged by an arbitrary rotation inside each
# cluster for a per-mode share to mean anything.
SPECTRAL_ROTATION_TOLERANCE = 1e-8
CLUSTER_ROTATION_DRAWS = 4
CLUSTER_ROTATION_SEED = 20260916
# Declared activity-retention threshold: the arm's positive heartbeat work above
# which the body's own source work is counted as still running, used for the
# declared activity-preserving ranking beside the headline ranking.
ACTIVITY_RETENTION_THRESHOLD = 1e-6

# The figures of the two harnesses this runner reuses, cited as the reference
# points the measured rows must reproduce (survival receipt
# ``_diag/fractal-survival/exploration.json``; the geometry receipt cites the
# mass/rail retention split).
CITED_RECOVERY = {
    "helix7": 0.0764836820747603,
    "mass-only": 0.33445984698946024,
    "nested-core-shell": 0.3351631005750861,
    "recursive-paired-loops": 0.061124304880849925,
}
CITED_REPRODUCTION_TOLERANCE = 1e-12

DEFAULT_OUTPUT = Path("_diag/fractal-metric/exploration.json")

METRIC_HYPOTHESIS = (
    "If a designed inverse-mass profile is the mechanism, then profiles whose "
    "slow modes participate where the declared items are written should show a "
    "higher minimum per-item recovery after the declared activity than profiles "
    "whose slow modes do not, and the ranking should track the declared overlap "
    "measure rather than the size of the metric change."
)
ACTIVITY_CONFOUND_STATEMENT = (
    "The declared activity arm advances the canonical heartbeat and sources, and "
    "the heartbeat's work allowance is metric dependent: a profile that makes "
    "most ports very heavy also reduces the work the body's own activity can "
    "inject.  Every ranking entry is therefore reported beside the arm's "
    "positive heartbeat work, its dissipated work and its total packet energy "
    "ratio, and the ranking is read as conditional on the body still working."
)
SLOW_MODE_DEFINITION = (
    "Slow modes are the right eigenvectors of the frozen linear generator "
    "(geometry.linear_generator: the beta=0 _WaveOperator column by column).  "
    "Decay ordering uses |Re eigenvalue| (the mode's decay magnitude, since the "
    "retention question is decay over the declared horizon); frequency ordering "
    "uses |eigenvalue|.  The declared slow set of the primary measure is every "
    "mode whose decay magnitude is at or below the spectrum median (the slower "
    "half), so no mode count has to be declared."
)
OVERLAP_DEFINITION = (
    "The item direction is the captured write direction the survival harness "
    "reads (the unit read-frame vector of one declared packet item written into "
    "a fresh field), mapped into the generator's own state coordinates through "
    "the declared read-frame transform, which is verified against the canonical "
    "packet analysis for every profile.  A projector measure is the orthogonal "
    "projection energy of that direction onto the span of the declared slow "
    "eigenvectors, divided by the direction's own energy; a participation "
    "measure is the biorthogonal spectral share of the declared slow modes, "
    "taken as the coefficients of the direction in the eigenbasis by solving "
    "that basis directly (so a numerically repeated eigenvalue needs no "
    "per-eigenvalue pairing); its reconstruction residual and its change under "
    "an arbitrary rotation inside each numerically degenerate cluster are "
    "measured per profile and both are required to stay inside the declared "
    "tolerances; a port measure is the Bhattacharyya "
    "coefficient between the direction's port energy density and the slow modes' "
    "pooled port participation density."
)
MEASURE_DEFINITIONS: dict[str, str] = {
    "slow_projection_slower_half_by_decay": (
        "orthogonal projection onto every mode at or below the median decay "
        "magnitude (the declared primary measure)"
    ),
    "slow_participation_slower_half_by_decay": (
        "biorthogonal spectral participation share of the modes at or below the "
        "median decay magnitude"
    ),
    "port_overlap_slower_half_by_decay": (
        "Bhattacharyya overlap between the direction's port energy density and "
        "the port participation density pooled over every mode at or below the "
        "median decay magnitude"
    ),
    "slow_projection_slowest8_by_decay": (
        "orthogonal projection onto the 8 slowest modes by decay magnitude"
    ),
    "slow_projection_slowest8_by_frequency": (
        "orthogonal projection onto the 8 slowest modes by |eigenvalue|"
    ),
    "slow_projection_slowest28_by_frequency": (
        "orthogonal projection onto the 28 slowest modes by |eigenvalue|"
    ),
    "port_overlap_slowest8_by_decay": (
        "Bhattacharyya overlap between the direction's port energy density and "
        "the port participation density pooled over the 8 slowest modes by decay "
        "magnitude"
    ),
}
MEASURE_NAMES = tuple(MEASURE_DEFINITIONS)
PRIMARY_MEASURE = "slow_projection_slower_half_by_decay"
# The measures that rest on the biorthogonal (dual) expansion and therefore on the
# declared spectral validity gates; every other measure is an orthogonal
# projection or a port density and needs no such gate.
PARTICIPATION_MEASURES = frozenset(
    name for name in MEASURE_NAMES if name.startswith("slow_participation")
)

SPECTRAL_VALIDITY_DEFINITION = (
    "The participation measure expands the written direction in the frozen "
    "generator's eigenbasis and reports the share of that expansion in the "
    "declared slow set.  Two gates are measured for every profile and both must "
    "hold for the number to be a participation share: the relative residual of "
    "reconstructing the direction from the expansion, and the change of the "
    "share when every numerically degenerate eigenvalue cluster is re-based by "
    "an arbitrary rotation (an exactly repeated eigenvalue leaves the "
    "eigenvectors inside its cluster arbitrary, so a per-mode share would "
    "otherwise be a convention rather than a quantity); a profile whose spectrum "
    "has no numerically degenerate cluster is invariant under that control by "
    "construction, so the rotation is only run where a cluster actually exists.  "
    "A profile failing "
    "either gate is reported with its measured figures and is excluded from the "
    "participation measure of the overlap relation, and the exclusion is listed."
)

CONTENT_DIGEST_DEFINITION = (
    "sha256 over the canonical JSON of the receipt body with wall-clock fields "
    "removed, computed through the survival harness's own digest helper (which "
    "is the geometry harness's canonical digest)."
)
# --------------------------------------------------------------------------
# declared ladder family (the user's phi hypothesis, measured against the
# field's real default ladder 1.3 ** pool)
# --------------------------------------------------------------------------
LADDER_PROFILE_BOUND = 9
# The field's default inertia is a geometric ladder with ratio 1.3 per pool
# (cassi_resonant_field.py: inertances = 1.3 ** pool), so every ladder member is
# compared at the same declared normalization as that ladder, not against a flat
# inertia.  Two declared normalizations are used:
#   "equal-total-inertia": inertia[p] = scale * ratio ** p with scale chosen so
#       the pool-sum of inertias equals the field default's pool-sum, so only the
#       shape of the ladder changes between members;
#   "equal-endpoint-width": the same minimum (1.0) and maximum (1.3 ** 6)
#       inertia as the field default, spaced arithmetically, so the metric has an
#       equal spectral width with a different spacing law (the density-matched
#       variant).
PHI = (1.0 + math.sqrt(5.0)) / 2.0
LADDER_EQUAL_TOTAL_NORMALIZATION = "equal-total-inertia"
LADDER_EQUAL_WIDTH_NORMALIZATION = "equal-endpoint-width"
LADDER_NORMALIZATIONS = {
    LADDER_EQUAL_TOTAL_NORMALIZATION: (
        "inertia[p] = scale * ratio ** p with scale chosen so the pool-sum of "
        "inertias equals the field default ladder's pool-sum (1.3 ** pool), so "
        "only the shape of the ladder changes between members"
    ),
    LADDER_EQUAL_WIDTH_NORMALIZATION: (
        "the same minimum (1.0) and maximum (1.3 ** 6) inertia as the field "
        "default, spaced arithmetically: equal spectral width with a "
        "non-geometric spacing law, the density-matched variant"
    ),
}
DEFAULT_LADDER_RATIO = 1.3
LADDER_SHUFFLE_SEED = 20260917
LADDER_DECAY_BAND_DEFINITION = (
    "Bands of the decay spectrum are maximal runs of numerically distinct "
    "eigenvalue decay magnitudes (|Re eigenvalue|, the quantity the retention "
    "question decays with) whose consecutive ratio stays at or below the "
    "declared band gap tolerance; a run therefore ends where the spectrum jumps "
    "by more than that factor.  A band's centre is the multiplicity-weighted "
    "geometric mean of its decay magnitudes, the band ladder ratio is that "
    "centre spacing per band, and the separation test compares the smallest "
    "inter-band gap against the widest spread inside a band.  The same declared "
    "rule is applied to every profile, so a continuum (one band) and separated "
    "bands are read off one statistic rather than chosen per profile.  The "
    "declared gap tolerance is a clean split in the measured spectra: a run of "
    "distinct decay magnitudes continues while consecutive values stay within "
    "this relative gap, which separates the fine structure inside a family (at "
    "or below about 3% for every declared ladder) from the jump between "
    "families (at or above about 5%)."
)
POOL_FAMILY_LADDER_DEFINITION = (
    "The pool-family ladder assigns every mode to the pool holding most of its "
    "port energy density (ties to the lowest pool) and reports each family's "
    "centre decay rate and lifetime ladder ratio.  It measures which pool owns "
    "which lifetime and whether the families order along the pool axis; it is "
    "not a band decomposition, because the family sizes follow from the body's "
    "own port structure rather than from the separation of the decay rates, so "
    "the same pool count of families is produced even where the decay spectrum "
    "is a continuum.  Whether a family ladder is actually a ladder is decided by "
    "the ordered gate: every adjacent centre ratio must clear the widest spread "
    "inside a family, with all ratios pointing the same way."
)
BAND_GAP_TOLERANCE = 0.05
BAND_RATIO_TRACKING_TOLERANCE = 0.1

# --------------------------------------------------------------------------
# declared local family around the flat (uniform) inertia, and the independent
# instruments the flat-inertia result is re-measured through
# --------------------------------------------------------------------------
# The flat metric is the edge of the declared ladder family, so flatness may be
# an endpoint rather than an interior optimum.  The local family makes one
# declared pool (and one declared pool pair) lighter or heavier than the flat
# value, rescaled back to the field default's total inertia, so a fall of
# retention with the strength of the contrast is an endpoint reading and a peak
# inside the declared contrasts is an interior optimum of this declared axis.
UNIFORM_LOCAL_POOL = 3
UNIFORM_LOCAL_PAIR = (2, 5)
UNIFORM_LOCAL_CONTRASTS = (0.25, 0.5, 2.0, 4.0)
UNIFORM_LOCAL_PAIR_CONTRASTS = (0.5, 2.0)
UNIFORM_LOCAL_PROFILE_BOUND = 8
UNIFORM_LOCAL_RULE = (
    "projected_inv_mass = 1 / inertia(pool) with inertia the flat (uniform) "
    "inertia multiplied by the declared contrast on the declared pools and then "
    "rescaled so the pool-sum of inertias equals the field default's own "
    "pool-sum: the row differs from the flat row only by a declared pool "
    "contrast, at the same total inertia"
)
# The independent instruments, taken by import rather than re-implemented:
# the ladder harness's declared 256-tick source-off horizon per item, and the
# placement harness's declared per-pair transfer scores.
HORIZON_INSTRUMENT = "run_fractal_ladder_exploration.measured_series_for_item"
PLACEMENT_INSTRUMENT = "run_fractal_placement_exploration._measure (compact config)"
FLAT_CONFIRMATION_PROFILES = (
    "ladder-uniform",
    DEFAULT_PROFILE_NAME,
    "nested-shell-metric",
    "nested-core-shell-reference",
)
# The discriminating question for the flat metric: is its advantage item content,
# or one collective rigid mode that rings?  Every declared item direction is read
# in the read frame after a declared horizon that wrote a declared set of items
# (one item at a time, and the declared k=2/4/8 arms' own item sets), each read
# against that direction's own alone-write deposit, so an unwritten direction's
# share is comparable with a written direction's retention.  The declared margin
# is the absolute retention gap an item's own direction must hold over the
# largest share of a direction its write never wrote to be called distinguished.
CROSS_TALK_MARGIN = 0.05
CROSS_TALK_INSTRUMENT = (
    "read-frame share of every declared item direction after the declared "
    "ladder horizon (256 source-off ticks) on the declared write set"
)
# The two readings of the cross-talk table, stated in advance so the receipt
# reports one of them by measurement rather than asserting an interpretation.
CROSS_TALK_VERDICT_STORED = (
    "item-specific direction: on the flat profile every declared item's own "
    "read-frame direction holds at least the declared margin of retention over "
    "the largest share of a direction its own write never wrote, so the flat "
    "retention tracks which item was written in this declared read frame and is "
    "not one shared mode ringing; this is a statement about the declared "
    "read-frame directions only, not about a consumer's readout or task-level "
    "memory"
)
CROSS_TALK_VERDICT_RIGID_MODE = (
    "one collective mode: on the flat profile a declared direction that was never "
    "written reaches the written direction's retention within the declared "
    "margin, so the flat retention is the ring-down of a shared mode and the "
    "declared item directions are not separately resolved in this read frame"
)
# The equal-time reading, also stated in advance in both directions.
EQUAL_TIME_VERDICT_LEADS = (
    "equal dimensionless time: the flat profile still leads the field default on "
    "both the equal-time endpoint and the equal-time window mean by more than the "
    "declared margin, so the flat advantage is not only the fixed horizon "
    "spanning fewer of its own e-fold times; its narrow decay band (all declared "
    "item directions decaying together) is the mechanism, not graded inertia "
    "being worse in itself"
)
EQUAL_TIME_VERDICT_BAND_NARROWING = (
    "equal dimensionless time: at the same number of slowest-mode e-fold times the "
    "flat profile's lead over the field default falls below the declared margin on "
    "the equal-time endpoint, the equal-time window mean, or both, so the fixed-"
    "horizon advantage is (at least in part) the fixed horizon spanning fewer of "
    "the flat profile's own e-fold times; the remaining effect is the 20x narrower "
    "decay band, which is equal scales not drifting apart rather than graded "
    "inertia being worse"
)
# Equal total inertia normalises the mass sum, not the mode frequencies.  The
# declared dimensionless-time comparison replaces the fixed tick horizon with
# the tick count at which a profile spans the same number of its own slowest-mode
# e-fold times as the field default spans in the declared horizon, bounded by the
# declared tick cap so the leg stays finite; the raw decay-rate ratio is reported
# beside it with no measurement at all.
EQUAL_TIME_REFERENCE_PROFILE = DEFAULT_PROFILE_NAME
EQUAL_TIME_TICK_CAP = 4096
# The declared sample step of the item series reading; the ladder harness's own
# declared step is asserted equal to this in the tests rather than read here, so
# the module stays loadable under the harnesses' circular import.
EQUAL_TIME_SAMPLE_EVERY = 16
EQUAL_TIME_MARGIN = 0.02
EQUAL_TIME_INSTRUMENT = (
    "run_fractal_ladder_exploration item write, threshold and read path with the "
    "horizon replaced by the declared equal-e-fold tick count"
)
# The cross-talk instrument reads the declared item directions, and on the
# canonical default those directions are not the slow modes.  That is worth
# stating beside the verdict, because it is the difference between "this field
# cannot store" and "this write was not aimed at a slow mode".  The aimed-write
# figure is cited from the ladder harness's own receipt rather than re-measured;
# the overlap figures named beside it are recomputed from this receipt's own
# mechanism block, and the resolving test reads both back.
CITED_TARGETED_WRITE = {
    # A cited external figure with a source pointer, not a check: this runner has
    # no declared-basis measurement of a narrow-path write, so the pinned object
    # is the pointer and the cited value, and the value is never recomputed here.
    "kind": "cited_external_figure",
    "source_pointer": (
        "_diag/fractal-ladder/exploration.json#exhaustive_write_surface.helix7.measured_top[0]"
    ),
    "receipt": "_diag/fractal-ladder/exploration.json",
    "receipt_content_digest": (
        "6208400bec247bf31920642c28d235430010c5da8152de4a0ea59c7825072935"
    ),
    "record": "exhaustive_write_surface.helix7.measured_top[0]",
    "profile_note": (
        "helix7 is run_fractal_ladder_exploration.build_declared_profile('helix7') "
        "= durability.ResonantProfile(), the same no-hook canonical default body "
        "this runner reads as default-inertance"
    ),
    "item_path": "RRRR",
    "item_component": "detail",
    "item_width": 2,
    "dominant_in_slow_band": True,
    "slow_weight": 0.999999999999905,
    "measured_retention": 0.47079331020702286,
    "citation_tolerance": 1e-6,
}
CROSS_TALK_SCOPE_STATEMENT = (
    "Scope of this instrument: it reads the eight declared item directions in the "
    "declared read frame, each against its own alone-write deposit, so 'the item "
    "was not stored' and 'the written direction is not a slow mode of this metric' "
    "are two different readings of the same table.  On the canonical default the "
    "declared item directions are not the slow modes: the slow-mode overlap of the "
    "declared widest-arm item directions is lower than the flat profile's by "
    "{slow_overlap:.6f} on the mean and their slow-mode participation is lower by "
    "{slow_participation:.6f}, which is why an unaimed declared-item write decays "
    "on the default while other directions dominate the read frame.  The same "
    "default body does retain an aimed write: the ladder harness measured a "
    "{width}-port {path}/{component} impulse on that same no-hook default profile "
    "(cited, not recomputed: {receipt} record {record}) landing in the slow band "
    "(slow weight {slow_weight:.2f}) and retaining "
    "{targeted:.3f} at its declared horizon, against {headline:.4f} for the "
    "declared widest item {headline_item} on the same profile in this receipt's own "
    "table.  The two conclusions stand side by side and are one design answer: aim "
    "the write, and additionally choose a metric under which the declared item "
    "directions are slow modes - the flat metric is such a metric, and its "
    "{own_over_unwritten:.1f} own-over-unwritten ratio with {distinguished} of "
    "{item_count} declared directions distinguished is the measured form of that "
    "second half, not a claim that the default body cannot store at all."
)
CROSS_TALK_CONCLUSION_AIM = (
    "aim the write: on the default body a declared-item write decays because the "
    "declared directions are not its slow modes, and an aimed slow-band write on "
    "the same body retains {targeted:.3f}"
)
CROSS_TALK_CONCLUSION_METRIC = (
    "choose a metric that makes the declared items slow: the flat metric retains "
    "{flat_own:.4f} on the written direction against {flat_unwritten:.4f} on the "
    "directions the write never wrote, so the same declared items are resolvable "
    "without aiming"
)
LADDER_CLAIM_STATEMENT = (
    "Claims under test, the phi-ladder hypothesis: the scaffold's spacing should "
    "be the golden ratio, so (a) the band claim: a geometric inertia ladder of "
    "ratio R spaces the decay spectrum's bands by that same ratio R; and (b) the "
    "lifetime-ladder claim: the pool-family lifetime ladder is monotone along the "
    "pool axis with a ratio that tracks sqrt(R). Both are compared at the "
    "declared equal-total-inertia normalisation against the field's real default "
    "ladder (ratio 1.3, not a flat metric) and held to the declared band-ratio "
    "tracking tolerance, with the flat metric and the multiset-matched scrambled "
    "ladder as the controls. The ordering claim is kept separate from the "
    "separation claim: whether the coarse bands are actually separated is "
    "reported as its own structural figure, not folded into either claim. The "
    "control also separates what the value multiset determines from what the "
    "ladder order determines: the band span and count are reported as "
    "multiset-level figures and the family lifetime ladder, the family centres "
    "and the retention as order-level figures. A claim that fails is reported as "
    "failed, and no failed claim is redefined after the measurement as a weaker "
    "monotonicity statement."
)
DEFINITIONS = {
    "declared_profiles": (
        "Every profile is a canonical ResonantProfile whose projected_inv_mass "
        "hook is replaced by the declared positive vector (or left unset for the "
        "default); the canonical rail, coupling, damping, stiffness, time step "
        "and activity settings are untouched, and no canonical code is modified.  "
        "The hook vector is indexed strand-major as the canonical shell metric "
        "is: index = strand*port_count + pool*ports_per_pool + local."
    ),
    "inverse_mass_profile": (
        "A profile's inverse-mass vector assigns one positive value to every "
        "port of a pool (both strands, all local ports of the pool), so the "
        "smaller the value the heavier the port and the slower its motion."
    ),
    "graded_family": (
        "inverse mass = contrast ** ring_distance(pool, core) with the ring "
        "distance the canonical circular pool distance; the construction is "
        "monotone in pool distance for every contrast below 1."
    ),
    "randomized_family": (
        "per-pool multiplier = contrast ** u, u ~ Uniform(-bound, bound) drawn "
        "once per profile from numpy.random.default_rng(seed)."
    ),
    "graded_ladder_family": (
        "A declared row per ladder setting, measured in its own receipt block "
        "(ladder_family) so the metric family's declared row bound is untouched: "
        "geometric ladders of ratio 1.3 (the field's real default path), phi, "
        "1/phi, phi squared and the non-phi control 1.5; a flat (uniform) "
        "inertia at the field default's own mean inertia; the phi ladder's value "
        "multiset permuted across the pools under a fixed declared seed; and an "
        "arithmetic ladder at the field default's own endpoint width.  Every "
        "member is compared at the declared equal-total-inertia normalization "
        "(the pool-sum of the ladder's inertances equals the field default's "
        "1.3 ** pool sum), so only the shape of the ladder changes."
    ),
    "ladder_band_structure": LADDER_DECAY_BAND_DEFINITION,
    "ladder_pool_family": POOL_FAMILY_LADDER_DEFINITION,
    "ladder_claim": LADDER_CLAIM_STATEMENT,
    "uniform_local_family": (
        "The declared local family around the flat metric, measured in its own "
        "receipt block (uniform_local_family): the flat inertia with one declared "
        "pool (index 3) multiplied by each declared contrast, and the flat "
        "inertia with one declared pool pair (2 and 5) multiplied by each "
        "declared pair contrast, every row rescaled so the pool-sum of inertias "
        "equals the field default's own pool-sum.  It answers whether flat is an "
        "endpoint of the declared ladder family or an interior optimum of the "
        "declared local axis; a contrast of one would return the flat row."
    ),
    "independent_instruments": (
        "The flat-inertia confirmation is re-measured through two instruments "
        "taken by import, so the ranked figure is not its own confirmation: the "
        "ladder harness's declared per-item 256-tick source-off horizon "
        "(run_fractal_ladder_exploration.measured_series_for_item, per declared "
        "item alignment retention, lifetime and occupancy at the harness's "
        "declared one-twentieth threshold), and the placement harness's declared "
        "per-pair transfer scores "
        "(run_fractal_placement_exploration._measure with its compact declared "
        "config).  Per-item agreement is compared item by item against the field "
        "default, and the per-pair ranking agreement is the rank correlation of "
        "the shared declared pair grid against the default's own."
    ),
    "band_rule_reconciliation": (
        "Two declared band rules are reported on the same spectra rather than one "
        "being preferred: this runner's ratio-relative rule (decay_gap_bands, "
        "runs of numerically distinct decay magnitudes whose consecutive ratio "
        "stays inside the declared relative tolerance) and the ladder harness's "
        "range-relative rule (modal_block_for_profile: absolute gaps above one "
        "twentieth of the decay-rate span, continuum when the largest gap is "
        "below one fiftieth of that span), with the spectrum digest both rules "
        "were read from."
    ),
    "mechanism_comparison": (
        "The spectrum-level comparison of the flat profile against the field "
        "default and the phi ladder: the slow-mode participation and the "
        "slow-mode overlap of the eight declared item directions of the widest "
        "declared arm, and the decay-rate span of the frozen generator, reported "
        "side by side so the retention difference is read as a spectrum "
        "difference rather than asserted to be one."
    ),
    "cross_talk": (
        "The distinguishing measurement for the flat profile: after the declared "
        "write set and the declared source-off horizon, every declared item "
        "direction is read in the read frame, each against its own alone-write "
        "deposit, so the share of a direction the write never wrote sits beside "
        "the written directions' retention.  Write sets: each declared item alone "
        "(the declared k=1 write, done once per declared item), and the declared "
        "k=1, k=2, k=4 and k=8 arms' own declared item sets (the k=1 arm is the "
        "harness's single-item arm, which writes the first declared item; the "
        "k=2/4/8 arms write the declared prefixes, so only the k=8 arm writes "
        "every declared item and has no never-written direction).  An item's own "
        "direction is distinguished when its retention exceeds the largest share "
        "among the directions its write never wrote by at least the declared "
        "margin; if that fails, the retention is one shared mode ringing and not "
        "the item."
    ),
    "cross_talk_scope": (
        "The cross-talk instrument's read frame is the eight declared item "
        "directions; on the canonical default those directions are not the slow "
        "modes, so an unaimed declared-item write decaying on the default is a "
        "statement about the write and the metric together, not about the body's "
        "capacity.  The aimed-write figure (a two-port RRRR/detail impulse on the "
        "same no-hook default profile, in the slow band at slow weight 1.00, "
        "retaining 0.471) is a cited external figure carrying a source pointer: "
        "its receipt path, record path and that receipt's content digest are "
        "recorded in the scope block, and it is neither re-measured nor "
        "re-checked here, because this runner has no declared-basis measurement "
        "of a narrow-path write to check it against.  The two slow-mode figures "
        "the citation is read beside are this receipt's own, recomputed from its "
        "mechanism block; the test pins the pointer and the cited value."
    ),
    "equal_dimensionless_time": (
        "Equal total inertia normalises the pool-sum of inertias, not the mode "
        "frequencies, so the declared horizon is not the same amount of dynamics "
        "for every profile.  Each profile therefore reports its slowest declared "
        "decay rate, that rate's ratio to the field default's, the slowest-mode "
        "e-fold count the declared horizon spans, and its per-item retention "
        "measured at the tick count that spans the same e-fold count as the "
        "declared horizon does on the default (bounded by the declared tick cap, "
        "with the cap reported when it binds).  The instrument is the ladder "
        "harness's declared item write, threshold and read path with only the "
        "horizon replaced, and it reproduces the ladder harness's own instrument "
        "exactly at the ladder harness's own horizon."
    ),
    "survival_figure": (
        "minimum per-item recovery fraction of one declared activity arm, "
        "exactly as the survival harness reads it: each written item's share of "
        "its own deposited energy along its captured direction after the "
        "declared restart and activity, minimised over the written items."
    ),
    "slow_modes": SLOW_MODE_DEFINITION,
    "overlap": OVERLAP_DEFINITION,
    "content_digest": CONTENT_DIGEST_DEFINITION,
}

BOUNDARY = (
    "Controlled canonical-field measurement only, on the canonical seven-pool "
    "body at the declared resolution: declared packet items written through the "
    "canonical packet impulse at the durability harness's declared budget, the "
    "same declared unrelated canonical activity (sources and heartbeat on) for "
    "every profile, and the canonical workspace round trip for the restart leg; "
    "the arms and the readout are the survival harness's, taken by import.  "
    "Every designed profile moves only the projected inverse-mass hook, so the "
    "ranking is a ranking of metric profiles on one rail, with one declared "
    "second rail measured for generalization.  The ranking is a ranking of the "
    "declared four-item arm at the declared horizon: the declared k=2 and k=8 "
    "arms are reported beside it, and a profile whose advantage over the default "
    "inverts when the written set widens is ranked for four items only.  The "
    "ranking is conditional on the body still working: the canonical heartbeat's "
    "work allowance is metric dependent, and at the low-contrast end of the "
    "graded family the body's own positive heartbeat work collapses by many "
    "orders of magnitude, so a high recovery figure there measures a quieter "
    "body as much as a better store.  The graded family stops at the declared "
    "contrast 0.005 (an inverse-mass ratio of 1.25e-7 across the pool axis); the "
    "limiting family member with near-zero peripheral inverse mass was not "
    "declared or tested, so an optimum at that endpoint is an endpoint of this "
    "declared range and not an interior optimum of the metric space.  The "
    "mechanism reading is a rank correlation over the declared family only, on "
    "the declared overlap measures, and the measures disagree with each other, "
    "so no measure here is claimed to be the mechanism.  No claim is made about "
    "profiles outside the declared family, about other resolutions or "
    "topologies, or about durability without the declared activity.  The "
    "declared ladder family is a declared comparison at one normalization: the "
    "equal-total-inertia scale only, so the flat member is measured at the field "
    "default's own mean inertia rather than at equal spectral width, and the "
    "arithmetic member carries the density-matched equal-width normalization "
    "that the geometric members do not; a ladder result is therefore a result at "
    "one declared normalization and is not a statement about sparsity or about "
    "the value multiset alone.  The band structure is a reading of the frozen "
    "generator's decay spectrum under one declared gap tolerance: the spectra "
    "here are continua with jumps, so a band-count difference is a difference in "
    "where the spectrum jumps, not a claim that the modes organize into "
    "separated bands.  The multiset control shows the coarse spectrum (band "
    "count and band span) is essentially a property of the value multiset, while "
    "the family lifetime ladder and the retention are properties of the order "
    "the values are placed in; the run reports both, and the permutation "
    "agreement is a numerical agreement at the declared tolerance, not an "
    "identity.  " 
    "The ladder retention figures are the four-item arm at the "
    "declared horizon only, and the phi hypothesis is answered as measured, "
    "including where it fails.  The flat-inertia result is a result on the "
    "declared instruments only: the ladder harness's per-item horizon and the "
    "placement harness's per-pair transfer are other harnesses' declared "
    "readouts on this body, not task-level memory, and the local family fixes one "
    "declared pool and one declared pool pair at the declared equal-total-inertia "
    "normalization, so 'flat is an endpoint' means an endpoint of this declared "
    "local axis and not of a metric space.  The two band rules are both "
    "normalisation choices reported side by side; neither is claimed to be the "
    "band structure, and a band-count difference between them is a difference in "
    "the declared rule rather than in the spectrum.  The cross-talk table reads "
    "declared item directions in the declared read frame after a declared source-"
    "off horizon, which is not a consumer's readout, and its shares are squared "
    "read-frame projections, so two directions that share field support can both "
    "read high; the equal-time leg reports the same profiles at one declared "
    "dimensionless time per profile and says nothing about any other time; its "
    "e-fold conversion carries each profile's declared time step (0.08 per tick, "
    "the ladder harness's own declared physical scaling), so the figures are "
    "per-generator-time rates times ticks times that step.  The cross-talk table "
    "reads the declared item directions only: on the canonical default those "
    "directions are not the slow modes (the aimed-write figure of 0.471 is a "
    "cited external figure with a source pointer into the ladder harness's own "
    "receipt (_diag/fractal-ladder/exploration.json, record "
    "exhaustive_write_surface.helix7.measured_top[0], that receipt's content "
    "digest carried beside it in the declared block), neither re-measured nor "
    "recomputed here, and only its pointer and "
    "value are pinned; the two slow-mode figures this receipt reads it beside are "
    "its own, a flat-minus-default slow-mode overlap mean of +0.209091 and a "
    "slow-mode participation mean of +0.042544), so the table "
    "separates 'this write was not aimed at a slow mode' from 'this body cannot "
    "store', and neither reading is a claim about a consumer.  Two design readings "
    "follow from this receipt and stand side by side: aim the write, and choose a "
    "metric under which the declared item directions are slow modes.  Nothing "
    "here establishes task-level memory utility, semantic content, retrieval by "
    "a consumer, or any advantage over alternative architectures."
)


# --------------------------------------------------------------------------
# declared profiles
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class MetricProfile:
    """One declared inverse-mass profile: its construction rule and parameters.

    The inverse-mass vector itself is derived from these declared parameters by
    :func:`declared_inverse_mass`, so a declaration carries no array state.
    """

    name: str
    kind: str
    rule: str
    rail: str = CANONICAL_RAIL
    contrast: float | None = None
    seed: int | None = None
    core_pool: int | None = None
    jitter_bound: float | None = None
    note: str = ""
    ladder_ratio: float | None = None
    normalization: str = ""
    local_pools: tuple[int, ...] = ()

    @property
    def family(self) -> str:
        """Which declared family the row belongs to."""

        if self.kind.startswith("ladder"):
            return "ladder"
        if self.kind.startswith("uniform-local"):
            return "uniform-local"
        return "metric"


def ring_distance(left: int, right: int, *, pools: int = 7) -> int:
    """The declared circular pool distance between two pools."""

    raw = abs(int(left) - int(right))
    return min(raw, int(pools) - raw)


def shell_inverse_mass(
    contrast: float,
    *,
    core_pool: int = SHELL_CORE_POOL,
    ports_per_pool: int = geometry.DEFAULT_PORTS_PER_POOL,
) -> np.ndarray:
    """The declared graded shell metric: ``contrast ** ring_distance(pool, core)``."""

    value_by_pool = [
        float(contrast) ** ring_distance(pool, core_pool) for pool in range(7)
    ]
    return _expand_pools(value_by_pool, ports_per_pool)


def default_ladder_total_inertia(*, pools: int = 7) -> float:
    """The pool-sum of the field default's own inertances (the 1.3 ladder)."""

    return float(sum(DEFAULT_LADDER_RATIO**pool for pool in range(int(pools))))


def ladder_inertia_values(
    ratio: float,
    *,
    pools: int = 7,
    normalization: str = LADDER_EQUAL_TOTAL_NORMALIZATION,
) -> list[float]:
    """The declared inertia ladder of one ratio, at the declared normalization."""

    pools = int(pools)
    ratio = float(ratio)
    if normalization == LADDER_EQUAL_WIDTH_NORMALIZATION:
        low = 1.0
        high = float(DEFAULT_LADDER_RATIO) ** (pools - 1)
        step = (high - low) / float(pools - 1)
        return [low + step * pool for pool in range(pools)]
    raw = [1.0 for _ in range(pools)] if ratio == 1.0 else [
        ratio**pool for pool in range(pools)
    ]
    scale = default_ladder_total_inertia(pools=pools) / float(sum(raw))
    return [scale * value for value in raw]


def ladder_inverse_mass(
    ratio: float,
    *,
    normalization: str = LADDER_EQUAL_TOTAL_NORMALIZATION,
    ports_per_pool: int = geometry.DEFAULT_PORTS_PER_POOL,
) -> np.ndarray:
    """The declared inverse mass of one ladder: one over its declared inertia."""

    values = ladder_inertia_values(ratio, normalization=normalization)
    return _expand_pools([1.0 / value for value in values], ports_per_pool)


def uniform_local_inverse_mass(
    contrast: float,
    pools: Sequence[int],
    *,
    ports_per_pool: int = geometry.DEFAULT_PORTS_PER_POOL,
) -> np.ndarray:
    """The flat inertia with one declared pool contrast, at the field total.

    The pool contrast multiplies the flat inertia on the declared pools and the
    result is rescaled so the pool-sum of inertias equals the field default's own
    pool-sum, which is the same equal-total-inertia normalization every ladder
    member is compared at.  A contrast of one therefore returns the flat row.
    """

    values = [1.0 for _ in range(7)]
    for pool in pools:
        values[int(pool)] *= float(contrast)
    scale = default_ladder_total_inertia() / float(sum(values))
    return _expand_pools([1.0 / (scale * value) for value in values], ports_per_pool)


def random_inverse_mass(
    seed: int,
    contrast: float,
    *,
    bound: float = RANDOM_JITTER_BOUND,
    ports_per_pool: int = geometry.DEFAULT_PORTS_PER_POOL,
) -> np.ndarray:
    """The declared randomized metric: per-pool multipliers ``contrast ** u``."""

    generator = np.random.default_rng(int(seed))
    exponents = generator.uniform(-float(bound), float(bound), size=7)
    return _expand_pools(
        [float(contrast) ** float(exponent) for exponent in exponents], ports_per_pool
    )


def _expand_pools(
    value_by_pool: Sequence[float], ports_per_pool: int
) -> np.ndarray:
    """One inverse-mass value per pool, written strand-major over every port."""

    port_count = 7 * int(ports_per_pool)
    vector = np.empty(2 * port_count, dtype=np.float64)
    for strand in (0, 1):
        for pool in range(7):
            start = strand * port_count + pool * int(ports_per_pool)
            vector[start : start + int(ports_per_pool)] = float(value_by_pool[pool])
    return vector


def canonical_metric_vector(
    *, ports_per_pool: int = geometry.DEFAULT_PORTS_PER_POOL
) -> np.ndarray:
    """The canonical default's own metric, re-expressed through the hook.

    The canonical profile's inertances are ``1.3 ** pool`` per port, so its
    inverse masses are their reciprocals; the declared control profile sets
    exactly those values through the hook.
    """

    return _expand_pools([1.0 / (1.3 ** pool) for pool in range(7)], ports_per_pool)


def declared_profiles() -> tuple[MetricProfile, ...]:
    """Every declared profile of the designed family, with its construction rule."""

    shell_rule = (
        "projected_inv_mass[port] = contrast ** ring_distance(pool, core) for "
        f"every port of the pool on both strands, core pool {SHELL_CORE_POOL}, "
        "with the ring distance the canonical circular pool distance"
    )
    profiles = [
        MetricProfile(
            name=DEFAULT_PROFILE_NAME,
            kind="default",
            rule=(
                "ResonantProfile() defaults: canonical inertances 1.3**pool per "
                "port, no projected hook at all"
            ),
            note="baseline: the current production body.",
        ),
        MetricProfile(
            name=REFERENCE_METRIC_PROFILE_NAME,
            kind="reference-metric",
            rule=(
                "projected_inv_mass[port] = 0.7 ** ring_distance(pool, 3) from the "
                "geometry harness's own declared shell metric (its "
                "core_shell_inverse_mass), i.e. the nested shell profile's metric "
                "alone -- the survival harness's mass-only arm"
            ),
            contrast=SHELL_REFERENCE_DECAY,
            core_pool=SHELL_CORE_POOL,
            note="the declared reference metric of the survival contrast.",
        ),
        MetricProfile(
            name=CANONICAL_HOOK_PROFILE_NAME,
            kind="canonical-hook",
            rule=(
                "projected_inv_mass[port] = 1/1.3**pool, the canonical profile's "
                "own metric re-expressed through the hook, so this profile must "
                "reproduce the canonical default through a different hook path"
            ),
            note="channel-fidelity control: it must reproduce the default.",
        ),
    ]
    for contrast in SHELL_CONTRASTS:
        profiles.append(
            MetricProfile(
                name=f"shell-contrast-{contrast}",
                kind="graded",
                rule=shell_rule,
                contrast=float(contrast),
                core_pool=SHELL_CORE_POOL,
                note=(
                    "coincides with the reference metric by construction"
                    if float(contrast) == float(SHELL_REFERENCE_DECAY)
                    else ""
                ),
            )
        )
    for index in range(RANDOM_PROFILE_COUNT):
        seed = RANDOM_SEED_BASE + RANDOM_SEED_STEP * index
        contrast = RANDOM_CONTRASTS[index % len(RANDOM_CONTRASTS)]
        profiles.append(
            MetricProfile(
                name=f"random-seed-{seed}",
                kind="randomized",
                rule=(
                    "projected_inv_mass[port] = contrast ** u_pool with u_pool ~ "
                    "Uniform(-1, 1) drawn per pool from "
                    f"numpy.random.default_rng({seed}), contrast cycled over the "
                    f"declared settings {list(RANDOM_CONTRASTS)}"
                ),
                contrast=float(contrast),
                seed=int(seed),
                jitter_bound=RANDOM_JITTER_BOUND,
            )
        )
    return tuple(profiles)


def ladder_profiles() -> tuple[MetricProfile, ...]:
    """The declared graded-ladder family: the field's own ladder beside phi ladders.

    Every member sets only the projected inverse-mass hook, and every member is
    compared at the declared normalization, so the field's real default ladder
    (ratio 1.3) is the reference the phi hypothesis has to beat.
    """

    geometric_rule = (
        "projected_inv_mass[port] = 1 / (scale * ratio ** pool) for every port of "
        "the pool on both strands, with ratio the declared ladder ratio and scale "
        "the declared normalization: the equal-total-inertia scale makes the "
        "pool-sum of the ladder's inertances equal the field default's (1.3 ** "
        "pool), so only the shape of the ladder changes"
    )
    width_rule = (
        "projected_inv_mass[port] = 1 / inertia(pool) with inertia(pool) the "
        "arithmetic interpolation from the field default's smallest inertia (1.0) "
        "to its largest (1.3 ** 6): the same spectral width with a non-geometric "
        "spacing law"
    )
    members = [
        MetricProfile(
            name="ladder-ratio-1.3",
            kind="ladder-geometric",
            rule=geometric_rule,
            ladder_ratio=DEFAULT_LADDER_RATIO,
            normalization=LADDER_EQUAL_TOTAL_NORMALIZATION,
            note=(
                "the field's real default ladder: at the equal-total-inertia "
                "normalization its scale is exactly 1, so it coincides with the "
                "canonical metric hook control"
            ),
        ),
        MetricProfile(
            name="ladder-ratio-phi",
            kind="ladder-geometric",
            rule=geometric_rule,
            ladder_ratio=PHI,
            normalization=LADDER_EQUAL_TOTAL_NORMALIZATION,
            note="the declared phi hypothesis: ratio 1.618033988749895 per pool",
        ),
        MetricProfile(
            name="ladder-ratio-inverse-phi",
            kind="ladder-geometric",
            rule=geometric_rule,
            ladder_ratio=1.0 / PHI,
            normalization=LADDER_EQUAL_TOTAL_NORMALIZATION,
            note="the reciprocal ladder, 0.6180339887498949 per pool",
        ),
        MetricProfile(
            name="ladder-ratio-phi-squared",
            kind="ladder-geometric",
            rule=geometric_rule,
            ladder_ratio=PHI**2,
            normalization=LADDER_EQUAL_TOTAL_NORMALIZATION,
            note="phi squared, 2.618033988749895 per pool",
        ),
        MetricProfile(
            name="ladder-ratio-1.5",
            kind="ladder-geometric",
            rule=geometric_rule,
            ladder_ratio=1.5,
            normalization=LADDER_EQUAL_TOTAL_NORMALIZATION,
            note="non-phi geometric control",
        ),
        MetricProfile(
            name="ladder-uniform",
            kind="ladder-uniform",
            rule=(
                "projected_inv_mass[port] = 1 / mean(1.3 ** pool for pool in "
                "range(7)) for every port: a flat inertia at the field default's "
                "own mean inertia, so 'uniform' is measured at the same total "
                "inertia as every other member"
            ),
            ladder_ratio=1.0,
            normalization=LADDER_EQUAL_TOTAL_NORMALIZATION,
            note="the flat-inertia control.",
        ),
        MetricProfile(
            name="ladder-matched-random-phi",
            kind="ladder-matched-random",
            rule=(
                "the phi ladder's own seven pool inertances permuted across the "
                f"pools by numpy.random.default_rng({LADDER_SHUFFLE_SEED}): the "
                "same value multiset as the phi ladder, so only the ladder order "
                "along the pool axis changes"
            ),
            ladder_ratio=PHI,
            seed=int(LADDER_SHUFFLE_SEED),
            normalization=LADDER_EQUAL_TOTAL_NORMALIZATION,
            note=(
                "multiset-matched to the phi ladder; the control that separates "
                "the spacing law from the value multiset"
            ),
        ),
        MetricProfile(
            name="ladder-arithmetic-equal-width",
            kind="ladder-arithmetic",
            rule=width_rule,
            normalization=LADDER_EQUAL_WIDTH_NORMALIZATION,
            note=(
                "density-matched variant: the field default's own endpoint width "
                "with an arithmetic spacing law"
            ),
        ),
    ]
    return tuple(members)


def ladder_row(name: str) -> MetricProfile:
    """One declared ladder row by name."""

    for row in ladder_profiles():
        if row.name == name:
            return row
    raise KeyError(f"no declared ladder row named {name!r}")


def uniform_local_profiles() -> tuple[MetricProfile, ...]:
    """The declared local family around the flat metric: is flat an endpoint?

    Flat inertia is the edge of the declared ladder family, so the flat profile's
    lead may be an endpoint reading.  Each row here contrasts one declared pool
    (or one declared pool pair) against the flat value at the same total inertia,
    which turns "flat wins" into either "retention falls with every contrast"
    (an endpoint) or "retention peaks at a contrast inside the declared set" (an
    interior optimum of this declared axis).
    """

    rows: list[MetricProfile] = []
    for contrast in UNIFORM_LOCAL_CONTRASTS:
        rows.append(
            MetricProfile(
                name=f"uniform-local-pool{UNIFORM_LOCAL_POOL}-{contrast:g}x",
                kind="uniform-local-single",
                rule=UNIFORM_LOCAL_RULE,
                contrast=float(contrast),
                local_pools=(UNIFORM_LOCAL_POOL,),
                normalization=LADDER_EQUAL_TOTAL_NORMALIZATION,
                note=(
                    "flat inertia with pool "
                    f"{UNIFORM_LOCAL_POOL} multiplied by {contrast:g}"
                ),
            )
        )
    for contrast in UNIFORM_LOCAL_PAIR_CONTRASTS:
        rows.append(
            MetricProfile(
                name=f"uniform-local-pairs{UNIFORM_LOCAL_PAIR[0]}-{UNIFORM_LOCAL_PAIR[1]}-{contrast:g}x",
                kind="uniform-local-pair",
                rule=UNIFORM_LOCAL_RULE,
                contrast=float(contrast),
                local_pools=tuple(UNIFORM_LOCAL_PAIR),
                normalization=LADDER_EQUAL_TOTAL_NORMALIZATION,
                note=(
                    "flat inertia with pools "
                    f"{UNIFORM_LOCAL_PAIR[0]} and {UNIFORM_LOCAL_PAIR[1]} multiplied "
                    f"by {contrast:g}"
                ),
            )
        )
    return tuple(rows)


def uniform_local_row(name: str) -> MetricProfile:
    """One declared local row by name."""

    for row in uniform_local_profiles():
        if row.name == name:
            return row
    raise KeyError(f"no declared local row named {name!r}")


def reference_rows() -> tuple[MetricProfile, ...]:
    """The survival harness's own reference scaffold, as a declared reference row.

    It is not a member of the designed metric family: the geometry harness builds
    it from both declared hooks, so it is measured with the same arm for scale
    and excluded from the designed ranking.
    """

    return (
        MetricProfile(
            name=REFERENCE_ROW_NAME,
            kind="reference-rail",
            rail=REFERENCE_ARRANGEMENT,
            rule=(
                f"geometry.build_profile({REFERENCE_ARRANGEMENT}): the projected "
                "transport rail AND the nested shell inverse-mass profile, exactly "
                "as the survival harness builds its reference scaffold"
            ),
            note="the survival harness's reference scaffold; not a metric-only row.",
        ),
    )


def all_declared_rows() -> tuple[MetricProfile, ...]:
    """The designed family plus the declared reference row."""

    return declared_profiles() + reference_rows()


def declared_inverse_mass(profile: MetricProfile) -> np.ndarray | None:
    """The declared hook vector of one profile, or ``None`` where none is declared.

    The default declares no hook at all, and the reference scaffold row declares
    its hooks through the geometry harness's arrangement rather than through a
    vector of this family, so both return ``None`` here.
    """

    if profile.kind == "default":
        return None
    if profile.kind == "reference-rail":
        # The arrangement itself carries both hooks; the row declares no hook of
        # its own, and whether the built profile has one is measured.
        return None
    if profile.kind == "reference-metric":
        return geometry.core_shell_inverse_mass(
            geometry.DEFAULT_PORTS_PER_POOL, decay=profile.contrast
        )
    if profile.kind == "canonical-hook":
        return canonical_metric_vector()
    if profile.kind == "graded":
        return shell_inverse_mass(profile.contrast, core_pool=profile.core_pool)
    if profile.kind == "randomized":
        return random_inverse_mass(
            profile.seed, profile.contrast, bound=profile.jitter_bound
        )
    if profile.kind in {"ladder-geometric", "ladder-uniform"}:
        return ladder_inverse_mass(
            float(profile.ladder_ratio), normalization=profile.normalization
        )
    if profile.kind in {"uniform-local-single", "uniform-local-pair"}:
        return uniform_local_inverse_mass(float(profile.contrast), profile.local_pools)
    if profile.kind == "ladder-arithmetic":
        return ladder_inverse_mass(
            0.0, normalization=LADDER_EQUAL_WIDTH_NORMALIZATION
        )
    if profile.kind == "ladder-matched-random":
        inertias = ladder_inertia_values(
            float(profile.ladder_ratio), normalization=profile.normalization
        )
        order = np.random.default_rng(int(profile.seed)).permutation(len(inertias))
        return _expand_pools(
            [1.0 / inertias[int(index)] for index in order],
            geometry.DEFAULT_PORTS_PER_POOL,
        )
    raise RuntimeError(f"the declared family has no profile kind {profile.kind!r}")


def build_metric_profile(profile: MetricProfile) -> Any:
    """One declared profile, built through the canonical hooks only."""

    base = (
        durability.ResonantProfile()
        if profile.rail == CANONICAL_RAIL
        else geometry.build_profile(geometry.arrangement_named(profile.rail))
    )
    vector = declared_inverse_mass(profile)
    return base if vector is None else replace(base, projected_inv_mass=vector)


def declared_row(
    name: str, rows: Sequence[MetricProfile] | None = None
) -> MetricProfile:
    """Look one declared row up by name."""

    for row in rows if rows is not None else all_declared_rows():
        if row.name == name:
            return row
    raise RuntimeError(f"no declared profile row {name!r}")


# --------------------------------------------------------------------------
# the declared read-frame transform
# --------------------------------------------------------------------------
def basis_workspace(profile: Any, index: int) -> Any:
    """A canonical workspace whose state is one basis vector of the phase space."""

    port_count = int(profile.port_count)
    lane, local = divmod(int(index), port_count)
    page = np.zeros(profile.page_shape, dtype=np.float64).reshape(-1)
    page[lane : 9 * port_count : 9][local] = 1.0
    return durability.ResonantWorkspace(
        profile=profile, field_page=page.reshape(profile.page_shape)
    )


def canonical_read_frame(workspace: Any) -> np.ndarray:
    """The declared read frame of one workspace, through the canonical packet view."""

    packet = durability.analyze_helical_packet(workspace, path=durability.READ_FRAME_PATH)
    return np.asarray(packet["coefficients"], dtype=np.float64).reshape(-1)


def read_frame_transform(profile: Any) -> np.ndarray:
    """The read frame as a matrix on the generator's state coordinates.

    The columns are the canonical packet view of the canonical basis states, so
    the transform is a property of the declared read frame and the layout only.
    """

    dimension = 4 * int(profile.port_count)
    columns = [
        canonical_read_frame(basis_workspace(profile, index))
        for index in range(dimension)
    ]
    return np.column_stack(columns)


def read_frame_isometry_block(
    profile: Any,
    transform: np.ndarray,
    captures: Sequence[Mapping[str, Any]],
    config: durability.DurabilityConfig,
) -> dict[str, Any]:
    """Check the declared transform against the canonical packet view, per profile."""

    identity = np.eye(transform.shape[0])
    state_errors: list[float] = []
    direction_errors: list[float] = []
    for capture in captures:
        workspace, _receipt = durability.write_item(
            durability.initial_workspace(profile), capture["spec"], config.write_budget
        )
        state = geometry.state_vector(workspace)
        state_errors.append(
            float(np.max(np.abs(transform @ state - canonical_read_frame(workspace))))
        )
        mapped = transform.T @ np.asarray(capture["direction"], dtype=np.float64)
        direction_errors.append(
            float(
                abs(
                    1.0
                    - abs(
                        float(
                            np.dot(mapped, state)
                            / (np.linalg.norm(mapped) * np.linalg.norm(state))
                        )
                    )
                )
            )
        )
    return {
        "path": durability.READ_FRAME_PATH,
        "dimension": int(transform.shape[0]),
        "transform_orthonormality_max_abs_error": float(
            np.max(np.abs(transform.T @ transform - identity))
        ),
        "canonical_readout_max_abs_difference": max(state_errors, default=0.0),
        "captured_direction_angle_max_abs_error": max(direction_errors, default=0.0),
        "items_checked": len(captures),
    }


# --------------------------------------------------------------------------
# mechanism: slow modes and the declared overlap measures
# --------------------------------------------------------------------------
def eigen_ipr(eigenvectors: np.ndarray) -> np.ndarray:
    """The geometry harness's declared inverse participation ratio, per mode."""

    magnitude = np.abs(eigenvectors) ** 2
    participation = magnitude.sum(axis=0)
    participation[participation == 0.0] = 1.0
    return np.asarray(
        ((magnitude**2).sum(axis=0) / participation**2).real, dtype=np.float64
    )


def port_energy_density(vector: np.ndarray, port_count: int) -> np.ndarray:
    """The declared port energy density of one phase-space vector."""

    density = np.zeros(int(port_count), dtype=np.float64)
    for lane in range(4):
        block = vector[lane * int(port_count) : (lane + 1) * int(port_count)]
        density += np.abs(block) ** 2
    total = float(density.sum())
    return density / total if total > 0.0 else density


def port_pool_indices(port_count: int, ports_per_pool: int) -> np.ndarray:
    """The declared pool index of every port of the state's port axis."""

    return (np.arange(int(port_count)) // int(ports_per_pool)).astype(int)


def _bhattacharyya(left: np.ndarray, right: np.ndarray) -> float:
    """The declared port-density overlap of two participation densities."""

    return float(np.sum(np.sqrt(np.abs(left) * np.abs(right))))


def subspace_projection_energy(vector: np.ndarray, basis: np.ndarray) -> float:
    """The orthogonal projection energy of one vector onto a mode span."""

    energy = float(np.real(vector.conj() @ vector))
    if energy <= 0.0 or basis.shape[1] == 0:
        return 0.0
    projected = basis @ (np.linalg.pinv(basis.conj().T @ basis) @ (basis.conj().T @ vector))
    return float(np.real(projected.conj() @ projected) / energy)


def eigenvalue_separation(eigenvalues: np.ndarray) -> float:
    """The smallest distance between two distinct eigenvalues of the spectrum."""

    distance = np.abs(eigenvalues[:, None] - eigenvalues[None, :])
    np.fill_diagonal(distance, np.inf)
    return float(distance.min())


def eigenvalue_clusters(
    eigenvalues: np.ndarray, tolerance: float
) -> tuple[np.ndarray, int, int]:
    """Numerically identical eigenvalues grouped into clusters.

    Returns the cluster label of every mode, the cluster count and the largest
    cluster size; a profile with no numerical degeneracy gets one cluster per
    mode.
    """

    labels = np.full(eigenvalues.shape[0], -1, dtype=int)
    cluster = 0
    for index in range(eigenvalues.shape[0]):
        if labels[index] >= 0:
            continue
        labels[index] = cluster
        for other in range(index + 1, eigenvalues.shape[0]):
            if labels[other] < 0 and abs(
                complex(eigenvalues[index]) - complex(eigenvalues[other])
            ) < float(tolerance):
                labels[other] = cluster
        cluster += 1
    sizes = np.bincount(labels)
    return labels, int(cluster), int(sizes.max())


def modal_participation_shares(
    vector: np.ndarray, right: np.ndarray
) -> tuple[np.ndarray, float]:
    """The declared biorthogonal spectral shares of one state, and their residual.

    The shares are the coefficients of the state in the frozen generator's
    eigenbasis, taken by solving that basis directly (the biorthogonal rows are
    the rows of the inverse basis).  Solving rather than pairing left
    eigenvectors by eigenvalue keeps the expansion exact for a repeated
    spectrum, where a per-eigenvalue pairing is not well defined; the residual
    of the reconstruction is returned as the numerical validity gate.
    """

    amplitudes = np.linalg.solve(right, vector)
    residual = float(np.linalg.norm(vector - right @ amplitudes) / np.linalg.norm(vector))
    shares = np.abs(amplitudes) ** 2
    total = float(shares.sum())
    return (shares / total if total > 0.0 else shares), residual


def cluster_rotation_change(
    vector: np.ndarray,
    right: np.ndarray,
    slow_indices: np.ndarray,
    labels: np.ndarray,
    cluster_count: int,
    *,
    seed: int,
) -> float:
    """How much the declared slow-set share moves when degenerate clusters are re-based.

    An exactly repeated eigenvalue leaves the individual eigenvectors inside its
    cluster arbitrary, so a per-mode share is only meaningful if the share of the
    declared slow set is unchanged by an arbitrary rotation inside each cluster.
    The returned figure is the largest relative move of that share over the
    declared rotation draws, measured rather than assumed.
    """

    def slow_share(basis: np.ndarray) -> float:
        amplitudes = np.abs(np.linalg.solve(basis, vector)) ** 2
        total = float(amplitudes.sum())
        return float(amplitudes[slow_indices].sum() / total) if total > 0.0 else 0.0

    reference = slow_share(right)
    generator = np.random.default_rng(int(seed))
    worst = 0.0
    for _ in range(int(CLUSTER_ROTATION_DRAWS)):
        rotated = right.copy()
        for cluster in range(cluster_count):
            members = np.flatnonzero(labels == cluster)
            if members.size > 1:
                basis, _ = np.linalg.qr(
                    generator.normal(size=(members.size, members.size))
                    + 1j * generator.normal(size=(members.size, members.size))
                )
                rotated[:, members] = right[:, members] @ basis
        worst = max(worst, abs(slow_share(rotated) - reference) / max(reference, 1e-300))
    return float(worst)


def pool_family_ladder(
    eigenvalues: np.ndarray,
    right: np.ndarray,
    port_count: int,
    ports_per_pool: int,
) -> dict[str, Any]:
    """The decay-rate ladder indexed by the pool that owns each mode family.

    This is not a band decomposition of the spectrum: every mode is assigned to
    the pool holding most of its port energy density, so the groups are the
    body's own pool families and their sizes are a property of the body rather
    than a measurement of spectral separation.  What it measures is the lifetime
    ladder of the body: each family's centre decay rate, whether those centres
    order along the pool axis (a ladder) or not (a scramble), and whether the
    families separate at all (the smallest adjacent centre ratio against the
    widest spread inside a family).  The spectral band count itself is reported
    by :func:`decay_gap_bands`, which uses no body structure.
    """

    decay = np.abs(np.asarray(eigenvalues).real)
    pool_index = port_pool_indices(port_count, ports_per_pool)
    pool_count = int(port_count) // int(ports_per_pool)
    members: list[list[int]] = [[] for _ in range(pool_count)]
    for mode in range(right.shape[1]):
        density = port_energy_density(right[:, mode], port_count)
        shares = [float(density[pool_index == pool].sum()) for pool in range(pool_count)]
        # ties go to the lowest pool index, so the assignment is deterministic
        members[int(np.argmax(shares))].append(mode)
    centers: list[float] = []
    spreads: list[float] = []
    counts: list[int] = []
    for pool in range(pool_count):
        indices = np.asarray(members[pool], dtype=int)
        counts.append(int(indices.size))
        if indices.size == 0:
            continue
        values = decay[indices]
        centers.append(
            float(np.exp(np.mean(np.log(np.maximum(values, np.finfo(np.float64).tiny)))))
        )
        spreads.append(
            float(values.max() / values.min()) if float(values.min()) > 0.0 else float("inf")
        )
    ratios = [centers[index + 1] / centers[index] for index in range(len(centers) - 1)]
    magnitudes = [max(value, 1.0 / value) for value in ratios]
    widest = max(spreads) if spreads else 1.0
    lifetime_ratio = (
        float(np.exp(np.mean(np.log([abs(1.0 / value) for value in ratios]))))
        if ratios
        else 1.0
    )
    return {
        "definition": POOL_FAMILY_LADDER_DEFINITION,
        "family_count": len(centers),
        "family_mode_counts": counts,
        "family_centers": centers,
        "family_center_ratios": ratios,
        "lifetime_ladder_ratio": lifetime_ratio,
        "centers_monotone_along_pools": bool(
            all(value >= 1.0 for value in ratios) or all(value <= 1.0 for value in ratios)
        ),
        # A ladder is only a ladder where the families actually separate: every
        # adjacent centre ratio has to clear the widest spread inside a family,
        # and all of them have to point the same way.  A flat metric (one centre)
        # and a scrambled ladder both fail this, which is what makes it a gate.
        "ladder_ordered_beyond_spread": bool(
            ratios
            and widest > 0.0
            and (
                all(value >= widest for value in ratios)
                or all(value <= 1.0 / widest for value in ratios)
            )
        ),
        "smallest_adjacent_center_ratio_magnitude": min(magnitudes) if magnitudes else 1.0,
        "widest_within_family_spread": widest,
        "families_separated": bool(magnitudes and min(magnitudes) > widest),
    }


def decay_gap_bands(eigenvalues: np.ndarray) -> dict[str, Any]:
    """The band structure of the decay spectrum, read off the sorted decay rates.

    No body structure enters: numerically distinct decay magnitudes are sorted
    and a band ends wherever the consecutive ratio exceeds the declared band gap
    tolerance, so a continuum (one band) and separated bands are read from one
    declared rule applied to every profile.
    """

    decay = np.abs(np.asarray(eigenvalues).real)
    values, multiplicities = np.unique(np.round(decay, 12), return_counts=True)
    bands: list[list[int]] = [[0]]
    for index in range(1, values.size):
        if values[index] / values[index - 1] - 1.0 > float(BAND_GAP_TOLERANCE):
            bands.append([])
        bands[-1].append(index)
    centers: list[float] = []
    counts: list[int] = []
    spreads: list[float] = []
    for band in bands:
        members = np.asarray(band, dtype=int)
        weights = multiplicities[members].astype(np.float64)
        local = values[members]
        centers.append(
            float(
                np.exp(
                    float(np.sum(weights * np.log(np.maximum(local, np.finfo(np.float64).tiny))))
                    / float(weights.sum())
                )
            )
        )
        counts.append(int(weights.sum()))
        spreads.append(float(local.max() / local.min()) if float(local.min()) > 0.0 else float("inf"))
    ratios = [centers[index + 1] / centers[index] for index in range(len(centers) - 1)]
    gaps = [
        float(values[bands[index + 1][0]] / values[bands[index][-1]])
        for index in range(len(bands) - 1)
    ]
    ladder_ratio = (
        float((centers[-1] / centers[0]) ** (1.0 / float(len(centers) - 1)))
        if len(centers) > 1
        else 1.0
    )
    return {
        "definition": LADDER_DECAY_BAND_DEFINITION,
        "gap_tolerance": float(BAND_GAP_TOLERANCE),
        "band_count": len(centers),
        "band_mode_counts": counts,
        "band_centers": centers,
        "band_center_ratios": ratios,
        "inter_band_gaps": gaps,
        "band_ladder_ratio": ladder_ratio,
        "smallest_inter_band_gap": min(gaps) if gaps else 1.0,
        "widest_within_band_spread": max(spreads) if spreads else 1.0,
        "largest_band_mode_fraction": (
            float(max(counts)) / float(sum(counts)) if counts else 0.0
        ),
        "bands_separated": bool(
            gaps and min(gaps) > (max(spreads) if spreads else 1.0)
        ),
        "continuum": len(centers) == 1,
    }


def mechanism_block(
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    transform: np.ndarray,
    written_items: Sequence[str],
) -> dict[str, Any]:
    """The frozen generator's slow-mode structure and the declared overlaps."""

    generator = geometry.linear_generator(profile)
    eigenvalues, right = np.linalg.eig(generator)
    separation = eigenvalue_separation(eigenvalues)
    labels, cluster_count, largest_cluster = eigenvalue_clusters(
        eigenvalues, DEGENERATE_CLUSTER_TOLERANCE
    )
    ipr = eigen_ipr(right)
    decay_order = np.argsort(np.abs(eigenvalues.real), kind="stable")
    frequency_order = np.argsort(np.abs(eigenvalues), kind="stable")
    decay = np.abs(eigenvalues.real)
    slower_half = decay_order[: int(np.count_nonzero(decay <= np.median(decay)))]
    port_count = int(profile.port_count)
    ports_per_pool = int(profile.ports_per_pool)
    pool_index = port_pool_indices(port_count, ports_per_pool)
    slowest8_density = np.zeros(port_count, dtype=np.float64)
    for index in decay_order[:8]:
        slowest8_density += port_energy_density(right[:, index], port_count)
    slowest8_density = slowest8_density / float(slowest8_density.sum())
    slower_half_density = np.zeros(port_count, dtype=np.float64)
    for index in slower_half:
        slower_half_density += port_energy_density(right[:, index], port_count)
    slower_half_density = slower_half_density / float(slower_half_density.sum())
    pool_participation = np.asarray(
        [float(slowest8_density[pool_index == pool].sum()) for pool in range(7)]
    )
    harness_spectrum = geometry.spectrum_metrics(profile)
    items: list[dict[str, Any]] = []
    residuals: list[float] = []
    rotation_changes: list[float] = []
    for index, capture in enumerate(captures):
        direction = np.asarray(capture["direction"], dtype=np.float64)
        state = transform.T @ direction
        shares, residual = modal_participation_shares(state, right)
        residuals.append(residual)
        # A profile with no numerically degenerate cluster is invariant by
        # construction: every rotation draw is the identity, so the control is
        # only run where the spectrum actually leaves a cluster's basis arbitrary.
        rotation_changes.append(
            0.0
            if largest_cluster <= 1
            else cluster_rotation_change(
                state,
                right,
                slower_half,
                labels,
                cluster_count,
                seed=CLUSTER_ROTATION_SEED + index,
            )
        )
        items.append(
            {
                "name": capture["name"],
                "path": capture["path"],
                "component": capture["component"],
                "measured_scale_depth": int(
                    round(float(np.log2(port_count / int(capture["scale_width"]))))
                ),
                "written_in_arm": capture["name"] in written_items,
                "deposited_energy": float(capture["deposited_energy"]),
                "overlaps": {
                    "slow_projection_slower_half_by_decay": subspace_projection_energy(
                        state, right[:, slower_half]
                    ),
                    "slow_projection_slowest8_by_decay": subspace_projection_energy(
                        state, right[:, decay_order[:8]]
                    ),
                    "slow_projection_slowest8_by_frequency": subspace_projection_energy(
                        state, right[:, frequency_order[:8]]
                    ),
                    "slow_projection_slowest28_by_frequency": subspace_projection_energy(
                        state, right[:, frequency_order[:28]]
                    ),
                    "slow_participation_slower_half_by_decay": float(
                        shares[slower_half].sum()
                    ),
                    "port_overlap_slowest8_by_decay": _bhattacharyya(
                        port_energy_density(state, port_count), slowest8_density
                    ),
                    "port_overlap_slower_half_by_decay": _bhattacharyya(
                        port_energy_density(state, port_count), slower_half_density
                    ),
                },
                "spectral_reconstruction_residual": residual,
                "state_direction_sha256": survival.array_sha256(state),
            }
        )
    return {
        "definitions": {
            "slow_modes": SLOW_MODE_DEFINITION,
            "overlap": OVERLAP_DEFINITION,
            "measures": dict(MEASURE_DEFINITIONS),
            "primary_measure": PRIMARY_MEASURE,
        },
        "generator_sha256": survival.array_sha256(generator),
        "generator_dimension": int(generator.shape[0]),
        "right_eigenvector_matrix_condition_number": float(np.linalg.cond(right)),
        "minimum_eigenvalue_separation": separation,
        "numerically_repeated_spectrum": bool(
            separation < float(SPECTRAL_SEPARATION_TOLERANCE)
        ),
        "degenerate_cluster_count": cluster_count,
        "largest_degenerate_cluster_size": largest_cluster,
        "degenerate_cluster_tolerance": float(DEGENERATE_CLUSTER_TOLERANCE),
        "decay_magnitude_range": [float(decay.min()), float(decay.max())],
        "frequency_magnitude_range": [
            float(np.abs(eigenvalues).min()),
            float(np.abs(eigenvalues).max()),
        ],
        "slower_half_mode_count": int(len(slower_half)),
        "ipr_uniform_reference": float(1.0 / generator.shape[0]),
        "ipr_median": float(np.median(ipr)),
        "ipr_min": float(ipr.min()),
        "ipr_max": float(ipr.max()),
        "ipr_of_the_8_slowest_by_decay": [float(ipr[index]) for index in decay_order[:8]],
        "slowest_modes_participating_pools": [float(value) for value in pool_participation],
        "geometry_harness_spectrum": {
            "ipr_median": float(harness_spectrum["ipr_median"]),
            "ipr_min": float(harness_spectrum["ipr_min"]),
            "ipr_max": float(harness_spectrum["ipr_max"]),
            "localized_mode_fraction": float(harness_spectrum["localized_mode_fraction"]),
            "real_part_range": [float(value) for value in harness_spectrum["real_part_range"]],
            "generator_sha256": harness_spectrum["generator_sha256"],
            "independent_reconstruction_max_abs_difference": float(
                harness_spectrum["independent_reconstruction_max_abs_difference"]
            ),
            "ipr_median_difference_vs_this_runner": float(
                abs(float(harness_spectrum["ipr_median"]) - float(np.median(ipr)))
            ),
        },
        "spectral_reconstruction_residual_max": max(residuals, default=0.0),
        "pool_family_ladder": pool_family_ladder(
            eigenvalues, right, port_count, ports_per_pool
        ),
        "decay_gap_bands": decay_gap_bands(eigenvalues),
        "participation_basis_rotation_max_change": max(rotation_changes, default=0.0),
        "participation_measure_valid": bool(
            max(residuals, default=0.0) <= float(SPECTRAL_RESIDUAL_TOLERANCE)
            and max(rotation_changes, default=0.0)
            <= float(SPECTRAL_ROTATION_TOLERANCE)
        ),
        "participation_validity_tolerance": {
            "spectral_reconstruction_residual": float(SPECTRAL_RESIDUAL_TOLERANCE),
            "basis_rotation_share_change": float(SPECTRAL_ROTATION_TOLERANCE),
        },
        "items": items,
    }


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------
def measure_row(
    row: MetricProfile,
    config: durability.DurabilityConfig,
    arms: Mapping[str, Any],
    transform: np.ndarray,
    *,
    arm_names: Sequence[str],
) -> dict[str, Any]:
    """One declared row: its declaration, its arm readouts and its mechanism."""

    profile = build_metric_profile(row)
    captures = durability.capture_items(config, profile)
    arms_out = {
        name: survival.compact_arm_record(
            durability.run_arm(config, profile, captures, arms[name]),
            config.control_margin,
        )
        for name in arm_names
    }
    written_items = [
        durability.ITEM_SPECS[index].name
        for index in arms[SURVIVAL_ARM_NAME].item_indices
    ]
    metric = survival.mass_metric_signature(profile)
    vector = declared_inverse_mass(row)
    return {
        "declaration": {
            "name": row.name,
            "kind": row.kind,
            "rail": row.rail,
            "rule": row.rule,
            "contrast": row.contrast,
            "seed": row.seed,
            "core_pool": row.core_pool,
            "jitter_bound": row.jitter_bound,
            "note": row.note,
            "ladder_ratio": row.ladder_ratio,
            "normalization": row.normalization,
            "family": row.family,
            "local_pools": [int(pool) for pool in row.local_pools],
            "hook_set": vector is not None,
            "hook_vector_sha256": None if vector is None else survival.array_sha256(vector),
            "hook_vector_min": None if vector is None else float(vector.min()),
            "hook_vector_max": None if vector is None else float(vector.max()),
        },
        "profile_hooks": survival.profile_hook_signature(profile),
        "mass_metric": metric,
        "items": survival.capture_rows(
            config, durability.ResonantProfile().port_count, captures
        ),
        "read_frame_isometry": read_frame_isometry_block(
            profile, transform, captures, config
        ),
        "mechanism": mechanism_block(profile, captures, transform, written_items),
        "arms": arms_out,
    }


def cross_rail_block(
    config: durability.DurabilityConfig,
    arms: Mapping[str, Any],
    transform: np.ndarray,
    top: MetricProfile,
) -> dict[str, Any]:
    """The top profile and the default metric rerun on one other declared rail."""

    default_row = MetricProfile(
        name=CROSS_RAIL_DEFAULT_ROW_NAME,
        kind="default",
        rail=CROSS_RAIL_ARRANGEMENT,
        rule=(
            f"ResonantProfile built by the geometry harness from the "
            f"{CROSS_RAIL_ARRANGEMENT!r} rail, with no inverse-mass hook: the "
            "default metric on that rail"
        ),
    )
    top_row = replace(
        top,
        name=CROSS_RAIL_TOP_ROW_NAME,
        rail=CROSS_RAIL_ARRANGEMENT,
        rule=(
            f"the ranking's best declared metric profile ({top.name}: {top.rule}) "
            f"applied through the projected_inv_mass hook on the "
            f"{CROSS_RAIL_ARRANGEMENT!r} rail"
        ),
    )
    names = (CROSS_RAIL_DEFAULT_ROW_NAME, CROSS_RAIL_TOP_ROW_NAME)
    rows = {
        name: measure_row(row, config, arms, transform, arm_names=(SURVIVAL_ARM_NAME,))
        for name, row in ((CROSS_RAIL_DEFAULT_ROW_NAME, default_row), (CROSS_RAIL_TOP_ROW_NAME, top_row))
    }
    default_recovery = rows[CROSS_RAIL_DEFAULT_ROW_NAME]["arms"][SURVIVAL_ARM_NAME][
        "recovery_fraction"
    ]
    top_recovery = rows[CROSS_RAIL_TOP_ROW_NAME]["arms"][SURVIVAL_ARM_NAME][
        "recovery_fraction"
    ]
    difference = float(top_recovery) - float(default_recovery)
    return {
        "rail": CROSS_RAIL_ARRANGEMENT,
        "declared_rows": list(names),
        "top_profile": top.name,
        "default_metric_recovery": float(default_recovery),
        "top_metric_recovery": float(top_recovery),
        "difference": difference,
        "margin": float(RANKING_MARGIN),
        "differs_from_default_by_margin": bool(
            abs(difference) >= float(RANKING_MARGIN)
        ),
        "top_exceeds_default_by_margin": bool(difference >= float(RANKING_MARGIN)),
        "ranking_holds": bool(difference > 0.0),
        "survival_harness_cited_default_metric_recovery": CITED_RECOVERY[
            CROSS_RAIL_ARRANGEMENT
        ],
        "cited_reproduction_abs_difference": float(
            abs(float(default_recovery) - CITED_RECOVERY[CROSS_RAIL_ARRANGEMENT])
        ),
        "rows": rows,
    }


def measured_body(
    config: durability.DurabilityConfig | None = None
) -> dict[str, Any]:
    """Every declared row measured with the declared arms, plus the cross-rail leg."""

    config = config or durability.DurabilityConfig()
    arms = survival.declared_arm_lookup(config)
    for name in (SINGLE_ITEM_ARM_NAME, *CONTEXT_ARM_NAMES, SURVIVAL_ARM_NAME):
        if name not in arms:
            raise RuntimeError(f"the durability harness declares no arm {name!r}")
    rows = all_declared_rows()
    if len(rows) > MAX_DECLARED_PROFILES:
        raise RuntimeError(
            f"the declared family declares {len(rows)} profiles, above the "
            f"declared bound of {MAX_DECLARED_PROFILES}"
        )
    transform = read_frame_transform(durability.ResonantProfile())
    profiles: dict[str, Any] = {}
    declared_row_order: list[str] = []
    for row in rows:
        record = measure_row(
            row,
            config,
            arms,
            transform,
            arm_names=(SURVIVAL_ARM_NAME, SINGLE_ITEM_ARM_NAME),
        )
        profiles[row.name] = record
        declared_row_order.append(row.name)
    rows_by_name = {row.name: row for row in rows}
    designed_names = [row.name for row in declared_profiles()]
    measured_ranking = sorted(
        declared_row_order,
        key=lambda name: (
            -float(profiles[name]["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]),
            name,
        ),
    )
    designed_ranking = [name for name in measured_ranking if name in designed_names]
    context_names = _context_profile_names(designed_ranking, DEFAULT_PROFILE_NAME)
    for name in context_names:
        extra = measure_row(
            rows_by_name[name],
            config,
            arms,
            transform,
            arm_names=CONTEXT_ARM_NAMES,
        )
        profiles[name]["arms"].update(extra["arms"])
    return {
        "schema": SCHEMA,
        "declared": declared_block(
            config, rows, declared_row_order, designed_ranking, context_names
        ),
        "profiles": profiles,
        "ladder_family": measured_ladder_body(config, arms, transform),
        "uniform_local_family": measured_uniform_local_body(config, arms, transform),
        "flat_inertia_confirmation": flat_inertia_confirmation_block(
            config, arms, transform
        ),
        "band_rule_reconciliation": band_rule_reconciliation_block(config),
        "cross_talk": measured_cross_talk_body(config, arms),
        "cross_rail": cross_rail_block(
            config, arms, transform, rows_by_name[designed_ranking[0]]
        ),
    }


def measured_ladder_body(
    config: durability.DurabilityConfig,
    arms: Mapping[str, Any],
    transform: np.ndarray,
) -> dict[str, Any]:
    """Every declared ladder row measured with the same declared k-item arm.

    The comparison figures (the field default's own ladder and the nested
    reference scaffold) are the ones already measured in the metric family, so
    the ladder family is ranked against the same arm on the same body rather
    than against a re-measured baseline.
    """

    rows = ladder_profiles()
    if len(rows) > LADDER_PROFILE_BOUND:
        raise RuntimeError(
            f"the declared ladder family has {len(rows)} rows, above the declared "
            f"bound of {LADDER_PROFILE_BOUND}"
        )
    records: dict[str, Any] = {}
    order: list[str] = []
    for row in rows:
        records[row.name] = measure_row(
            row, config, arms, transform, arm_names=(SURVIVAL_ARM_NAME,)
        )
        order.append(row.name)
    return {"rows": records, "row_order": order}


def measured_uniform_local_body(
    config: durability.DurabilityConfig,
    arms: Mapping[str, Any],
    transform: np.ndarray,
) -> dict[str, Any]:
    """Every declared local row measured on the k4 and k8 arms, with the flat anchor."""

    rows = uniform_local_profiles()
    if len(rows) > UNIFORM_LOCAL_PROFILE_BOUND:
        raise RuntimeError(
            f"the declared local family has {len(rows)} rows, above the declared "
            f"bound of {UNIFORM_LOCAL_PROFILE_BOUND}"
        )
    records: dict[str, Any] = {}
    order: list[str] = []
    for row in (*rows, ladder_row("ladder-uniform")):
        records[row.name] = measure_row(
            row,
            config,
            arms,
            transform,
            arm_names=(SURVIVAL_ARM_NAME, CONTEXT_ARM_NAMES[1]),
        )
        order.append(row.name)
    return {
        "rows": records,
        "row_order": order,
        "anchor_profile": "ladder-uniform",
        "local_row_count": len(rows),
    }


def _horizon_instrument(profile: Any, captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The ladder harness's declared 256-tick source-off horizon, taken by import."""

    series = [
        ladder.measured_series_for_item(profile, index, captures)
        for index in range(len(durability.ITEM_SPECS))
    ]
    final = [float(row["final_alignment"]) for row in series]
    lifetimes = [int(row["lifetime_ticks"]) for row in series]
    return {
        "instrument": HORIZON_INSTRUMENT,
        "horizon_ticks": int(ladder.HORIZON_TICKS),
        "threshold_fraction": float(ladder.THRESHOLD_FRACTION),
        "per_item": [
            {
                "item": row["item"],
                "scale_width": int(row["scale_width"]),
                "lifetime_ticks": int(row["lifetime_ticks"]),
                "censored": bool(row["censored"]),
                "final_alignment": float(row["final_alignment"]),
                "occupancy": float(row["occupancy"]),
                "last_half_min": float(row["last_half_min"]),
            }
            for row in series
        ],
        "final_alignment_min": float(min(final)),
        "final_alignment_mean": float(sum(final) / len(final)),
        "censored_items": [row["item"] for row in series if row["censored"]],
        "mean_lifetime_ticks": float(sum(lifetimes) / len(lifetimes)),
    }


def _placement_instrument(record: Mapping[str, Any]) -> dict[str, Any]:
    """The placement harness's declared per-pair transfer scores, compact config."""

    pairs = record["pairs"]
    matrix = np.asarray(pairs["transfer_matrix"], dtype=np.float64)
    best = list(pairs["best"])
    return {
        "instrument": PLACEMENT_INSTRUMENT,
        "pair_count": int(matrix.size),
        "transfer_max": float(matrix.max()),
        "transfer_mean": float(matrix.mean()),
        "best_pair_write_port": int(best[0]["write_port"]),
        "best_pair_read_port": int(best[0]["read_port"]),
        "best_pair_transfer": float(best[0]["transfer"]),
        "transfer_matrix": matrix,
    }


def _declared_item_names() -> list[str]:
    return [spec.name for spec in durability.ITEM_SPECS]


def _direction_shares(
    config: durability.DurabilityConfig,
    captures: Sequence[Mapping[str, Any]],
    workspace: Any,
) -> list[float]:
    """Every declared item direction's share in one read frame.

    Each direction is normalised by its own alone-write deposit, exactly as the
    declared item readout does, so a share of a direction the write never wrote
    is directly comparable with a written direction's retention.
    """

    vector = durability.read_frame(workspace, config.read_frame_path)
    return [
        float(
            durability.share_along(
                vector,
                np.asarray(capture["direction"], dtype=np.float64),
                float(capture["deposited_energy"]),
            )
        )
        for capture in captures
    ]


def _written_horizon_workspace(
    config: durability.DurabilityConfig,
    profile: Any,
    item_indices: Sequence[int],
    horizon_ticks: int | None = None,
) -> Any:
    """Write the declared items into a fresh field, then advance the declared source-off horizon."""

    workspace = durability.initial_workspace(profile)
    for index in item_indices:
        workspace, _ = durability.write_item(
            workspace, durability.ITEM_SPECS[index], config.write_budget
        )
    workspace, _ = ladder.advance_workspace(
        workspace,
        ticks=int(ladder.HORIZON_TICKS if horizon_ticks is None else horizon_ticks),
        demand=0.0,
        source_enabled=False,
    )
    return workspace


def _scaled_horizon_series(
    config: durability.DurabilityConfig,
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    horizon_ticks: int,
) -> list[dict[str, Any]]:
    """The ladder harness's declared item series at a declared tick count.

    Same write, same read path, same threshold as
    ``run_fractal_ladder_exploration.measured_series_for_item``; only the horizon
    is the declared equal-e-fold tick count.  At the ladder harness's own horizon
    this reproduces that instrument exactly (asserted in the tests).
    """

    step = int(EQUAL_TIME_SAMPLE_EVERY)
    sample_ticks = list(range(step, int(horizon_ticks) + 1, step))
    if not sample_ticks or sample_ticks[-1] != int(horizon_ticks):
        sample_ticks.append(int(horizon_ticks))
    series: list[dict[str, Any]] = []
    for index, spec in enumerate(durability.ITEM_SPECS):
        capture = captures[index]
        direction = np.asarray(capture["direction"], dtype=np.float64)
        deposited = float(capture["deposited_energy"])
        workspace, _ = durability.write_item(
            durability.initial_workspace(profile), spec, config.write_budget
        )
        written = durability.read_frame(workspace, config.read_frame_path)
        initial = float(durability.share_along(written, direction, deposited))
        threshold = float(ladder.THRESHOLD_FRACTION) * initial
        current = workspace
        previous = 0
        retentions: list[tuple[int, float]] = []
        for tick in sample_ticks:
            current, _ = ladder.advance_workspace(
                current,
                ticks=int(tick) - previous,
                demand=0.0,
                source_enabled=False,
            )
            previous = int(tick)
            vector = durability.read_frame(current, config.read_frame_path)
            retentions.append(
                (int(tick), float(durability.share_along(vector, direction, deposited)))
            )
        crossings = [tick for tick, value in retentions if value < threshold]
        censored = not crossings
        values = [value for _, value in retentions]
        quarter = values[max(0, (3 * len(values)) // 4) :]
        series.append(
            {
                "item": spec.name,
                "scale_width": int(capture["scale_width"]),
                "final_alignment": float(retentions[-1][1]),
                "mean_alignment": float(sum(values) / len(values)),
                "last_quarter_min": float(min(quarter)) if quarter else float(retentions[-1][1]),
                "lifetime_ticks": int(horizon_ticks) if censored else int(crossings[0]),
                "censored": bool(censored),
                "sample_count": len(retentions),
            }
        )
    return series


def measured_cross_talk_body(
    config: durability.DurabilityConfig,
    arms: Mapping[str, Any],
) -> dict[str, Any]:
    """Item-direction cross-talk and the equal-dimensionless-time leg.

    Three declared write sets, all read at the declared horizon: one declared
    item at a time (the declared k=1 write of every declared item in turn, which
    is what a single-item arm writes), and the declared k=2, k=4 and k=8 arms'
    own declared item sets.  Every declared item direction is read after every
    write set, so the share of a direction the write never wrote is reported
    beside the written directions' retention, and the distinguishability of a
    written item is a measured margin rather than an assumption.  The same leg
    also carries the equal-dimensionless-time comparison: each profile's slowest
    declared decay rate, its ratio to the field default's, and its per-item
    retention measured at the tick count that spans the same number of slowest
    e-fold times as the declared horizon on the default.
    """

    by_name = {row.name: row for row in (*all_declared_rows(), *ladder_profiles())}
    item_names = _declared_item_names()
    declared_arms = (
        ("k1", SINGLE_ITEM_ARM_NAME),
        ("k2", CONTEXT_ARM_NAMES[0]),
        ("k4", SURVIVAL_ARM_NAME),
        ("k8", CONTEXT_ARM_NAMES[1]),
    )
    profiles: dict[str, Any] = {}
    equal_time: dict[str, Any] = {}
    records: dict[str, tuple[Any, Any]] = {}
    for name in FLAT_CONFIRMATION_PROFILES:
        row = by_name[name]
        profile = build_metric_profile(row)
        captures = durability.capture_items(config, profile)
        for _, arm_name in declared_arms:
            if arm_name not in arms:
                raise RuntimeError(f"the durability harness declares no arm {arm_name!r}")
        matrix: dict[str, dict[str, float]] = {}
        for index, item in enumerate(item_names):
            shares = _direction_shares(
                config, captures, _written_horizon_workspace(config, profile, (index,))
            )
            matrix[item] = {other: float(value) for other, value in zip(item_names, shares)}
        arm_records: dict[str, Any] = {}
        for label, arm_name in declared_arms:
            spec = arms[arm_name]
            written_indices = [int(index) for index in spec.item_indices]
            written_set = set(written_indices)
            shares = _direction_shares(
                config,
                captures,
                _written_horizon_workspace(config, profile, written_indices),
            )
            arm_records[label] = {
                "arm": arm_name,
                "written_items": [item_names[index] for index in written_indices],
                "written_shares": {
                    item_names[index]: float(shares[index]) for index in written_indices
                },
                "unwritten_items": [
                    item for index, item in enumerate(item_names) if index not in written_set
                ],
                "unwritten_shares": {
                    item: float(shares[index])
                    for index, item in enumerate(item_names)
                    if index not in written_set
                },
                "all_item_shares": {
                    item: float(value) for item, value in zip(item_names, shares)
                },
            }
        modal = ladder.modal_block_for_profile(profile, captures)
        records[name] = (profile, captures)
        equal_time[name] = {
            "slowest_decay_rate": float(modal["decay_rate_min"]),
            "fastest_decay_rate": float(modal["decay_rate_max"]),
            "efold_ticks_at_slowest": float(modal["efold_ticks_max"]),
            # the decay rates are per declared generator time and one tick advances
            # time_step of it, so an e-fold count over a tick horizon carries dt
            "time_step": float(profile.time_step),
            # the ladder harness's own modal block carries the decay span; the
            # frequency span is carried by this row's own mechanism record and is
            # attached in the summary rather than recomputed here
            "decay_magnitude_range": [
                float(modal["decay_rate_min"]),
                float(modal["decay_rate_max"]),
            ],
        }
        profiles[name] = {
            "profile": name,
            "declaration_family": row.family,
            "item_matrix": matrix,
            "arms": arm_records,
            "item_direction_sha256": {
                str(capture["name"]): capture["direction_sha256"] for capture in captures
            },
        }
    default_slowest = float(equal_time[EQUAL_TIME_REFERENCE_PROFILE]["slowest_decay_rate"])
    default_step = float(equal_time[EQUAL_TIME_REFERENCE_PROFILE]["time_step"])
    declared_efolds = float(ladder.HORIZON_TICKS) * default_step * default_slowest
    equal_time_rows: list[dict[str, Any]] = []
    for name in FLAT_CONFIRMATION_PROFILES:
        record = equal_time[name]
        profile, captures = records[name]
        slowest = float(record["slowest_decay_rate"])
        step = float(record["time_step"])
        record["profile"] = name
        record["instrument"] = EQUAL_TIME_INSTRUMENT
        record["reference_slowest_decay_rate"] = default_slowest
        record["reference_time_step"] = default_step
        record["slowest_decay_ratio_vs_reference"] = (
            float(slowest / default_slowest) if default_slowest else None
        )
        record["efolds_at_declared_horizon"] = float(ladder.HORIZON_TICKS) * step * slowest
        record["declared_reference_efolds"] = declared_efolds
        record["slowest_mode_is_marginal"] = bool(slowest <= 0.0)
        # equal dimensionless time: the same number of slowest-mode e-fold times as
        # the declared horizon spans on the reference profile, with each profile's
        # own time step carried because the decay rates are per generator time
        requested = (
            int(EQUAL_TIME_TICK_CAP)
            if slowest <= 0.0
            else int(round(declared_efolds / (slowest * step)))
        )
        capped = bool(requested > EQUAL_TIME_TICK_CAP)
        ticks = int(EQUAL_TIME_TICK_CAP) if capped else max(1, requested)
        record["equal_time_horizon_ticks"] = ticks
        record["equal_time_tick_cap"] = int(EQUAL_TIME_TICK_CAP)
        record["tick_cap_applied"] = capped
        record["tick_scale_vs_declared_horizon"] = float(ticks / float(ladder.HORIZON_TICKS))
        record["efolds_at_equal_time_horizon"] = float(ticks) * step * slowest
        record["equal_time_efold_residual"] = float(
            record["efolds_at_equal_time_horizon"] - declared_efolds
        )
        record["sample_every"] = int(EQUAL_TIME_SAMPLE_EVERY)
        series = _scaled_horizon_series(config, profile, captures, ticks)
        final = [float(row["final_alignment"]) for row in series]
        means = [float(row["mean_alignment"]) for row in series]
        record["per_item"] = series
        record["final_alignment_min"] = float(min(final))
        record["final_alignment_mean"] = float(sum(final) / len(final))
        record["mean_alignment_min"] = float(min(means))
        record["mean_alignment_mean"] = float(sum(means) / len(means))
        record["censored_items"] = [row["item"] for row in series if row["censored"]]
        record["mean_lifetime_ticks"] = float(
            sum(int(row["lifetime_ticks"]) for row in series) / len(series)
        )
        equal_time_rows.append(record)
    return {
        "profile_order": list(FLAT_CONFIRMATION_PROFILES),
        "item_names": item_names,
        "declared_arm_labels": [label for label, _ in declared_arms],
        "declared_arm_names": {label: arm_name for label, arm_name in declared_arms},
        "instrument": CROSS_TALK_INSTRUMENT,
        "horizon_ticks": int(ladder.HORIZON_TICKS),
        "margin": float(CROSS_TALK_MARGIN),
        "profiles": [profiles[name] for name in FLAT_CONFIRMATION_PROFILES],
        "equal_time": equal_time_rows,
    }


def flat_inertia_confirmation_block(
    config: durability.DurabilityConfig,
    arms: Mapping[str, Any],
    transform: np.ndarray,
) -> dict[str, Any]:
    """Re-measure the flat profile's lead through independent instruments.

    The ranked figure alone cannot distinguish "flat inertia is better" from "one
    item carried the minimum", so every confirmation profile is measured on all
    three declared k arms with the per-item recoveries recorded, then re-measured
    on two instruments taken by import from other harnesses: the ladder harness's
    declared 256-tick source-off horizon per declared item, and the placement
    harness's declared per-pair transfer scores.  The flat profile's lead is a
    confirmation only where it holds on the independent instrument too.
    """

    names = list(FLAT_CONFIRMATION_PROFILES)
    by_name = {row.name: row for row in (*all_declared_rows(), *ladder_profiles())}
    arm_names = (CONTEXT_ARM_NAMES[0], SURVIVAL_ARM_NAME, CONTEXT_ARM_NAMES[1])
    records: dict[str, Any] = {}
    for name in names:
        row = by_name[name]
        profile = build_metric_profile(row)
        captures = durability.capture_items(config, profile)
        arm_record = measure_row(row, config, arms, transform, arm_names=arm_names)
        records[name] = {
            "profile": name,
            "declaration_family": row.family,
            "arms": {
                label: {
                    "arm": arm_name,
                    "recovery_fraction": float(
                        arm_record["arms"][arm_name]["recovery_fraction"]
                    ),
                    "per_item_recovery": dict(
                        arm_record["arms"][arm_name]["per_item_recovery_fraction"]
                    ),
                    "heartbeat_work_total": float(
                        arm_record["arms"][arm_name]["activity_positive_heartbeat_work_total"]
                    ),
                }
                for label, arm_name in zip(("k2", "k4", "k8"), arm_names)
            },
            "horizon": _horizon_instrument(profile, captures),
            **_placement_instrument(
                placement._measure(profile, placement.PlacementConfig.compact())
            ),
        }
    flat = records["ladder-uniform"]
    default = records[DEFAULT_PROFILE_NAME]
    reference_metric = records["nested-shell-metric"]
    reference_scaffold = records["nested-core-shell-reference"]
    instrument_default = np.asarray(default["transfer_matrix"], dtype=np.float64)
    instrument_flat = np.asarray(flat["transfer_matrix"], dtype=np.float64)
    for name, record in records.items():
        matrix = np.asarray(record["transfer_matrix"], dtype=np.float64)
        record["transfer_rank_agreement_vs_default"] = _spearman(
            matrix.reshape(-1).tolist(), instrument_default.reshape(-1).tolist()
        )
        record["k4_minus_default_at_every_k"] = {
            label: float(
                record["arms"][label]["recovery_fraction"]
                - default["arms"][label]["recovery_fraction"]
            )
            for label in ("k2", "k4", "k8")
        }
    for record in records.values():
        record.pop("transfer_matrix", None)
    flat_ranks = _spearman(
        instrument_flat.reshape(-1).tolist(), instrument_default.reshape(-1).tolist()
    )
    flat_horizon = {
        row["item"]: float(row["final_alignment"]) for row in flat["horizon"]["per_item"]
    }
    default_horizon = {
        row["item"]: float(row["final_alignment"]) for row in default["horizon"]["per_item"]
    }
    horizon_shortfalls = [
        item for item, value in flat_horizon.items() if not value > default_horizon[item]
    ]
    for record in records.values():
        record["horizon_final_alignment_vs_default_per_item"] = {
            row["item"]: float(row["final_alignment"] - default_horizon[row["item"]])
            for row in record["horizon"]["per_item"]
        }
    return {
        "profile_order": names,
        "arm_labels": ["k2", "k4", "k8"],
        "rows": [records[name] for name in names],
        "flat_profile": "ladder-uniform",
        "default_profile": DEFAULT_PROFILE_NAME,
        "reference_metric_profile": "nested-shell-metric",
        "reference_scaffold_profile": "nested-core-shell-reference",
        "plateau_claim": (
            "the flat profile wins only if it exceeds the default on every declared "
            "k arm, on the independent horizon instrument's per-item final "
            "alignment, and on the independent placement instrument's per-pair "
            "transfer, not only on the ranked minimum"
        ),
        "flat_exceeds_default_on_every_declared_k": bool(
            all(
                flat["arms"][label]["recovery_fraction"]
                > default["arms"][label]["recovery_fraction"]
                for label in ("k2", "k4", "k8")
            )
        ),
        "flat_exceeds_default_on_every_horizon_item": not horizon_shortfalls,
        "flat_horizon_items_not_exceeding_default": horizon_shortfalls,
        "flat_horizon_items_exceeding_default": [
            row["item"] for row in flat["horizon"]["per_item"]
        ]
        if not horizon_shortfalls
        else [
            row["item"]
            for row in flat["horizon"]["per_item"]
            if row["final_alignment"] > default_horizon[row["item"]]
        ],
        "flat_horizon_final_alignment_min": float(flat["horizon"]["final_alignment_min"]),
        "default_horizon_final_alignment_min": float(default["horizon"]["final_alignment_min"]),
        "flat_horizon_final_alignment_mean": float(flat["horizon"]["final_alignment_mean"]),
        "default_horizon_final_alignment_mean": float(
            default["horizon"]["final_alignment_mean"]
        ),
        "flat_transfer_mean": float(flat["transfer_mean"]),
        "default_transfer_mean": float(default["transfer_mean"]),
        "flat_exceeds_default_on_transfer_mean": bool(
            float(flat["transfer_mean"]) > float(default["transfer_mean"])
        ),
        "flat_transfer_rank_agreement_vs_default": flat_ranks,
        "flat_horizon_vs_reference_metric_min": float(
            flat["horizon"]["final_alignment_min"]
            - reference_metric["horizon"]["final_alignment_min"]
        ),
        "flat_horizon_vs_reference_scaffold_min": float(
            flat["horizon"]["final_alignment_min"]
            - reference_scaffold["horizon"]["final_alignment_min"]
        ),
        "flat_arms_minus_reference_metric": {
            label: float(
                flat["arms"][label]["recovery_fraction"]
                - reference_metric["arms"][label]["recovery_fraction"]
            )
            for label in ("k2", "k4", "k8")
        },
        "flat_arms_minus_reference_scaffold": {
            label: float(
                flat["arms"][label]["recovery_fraction"]
                - reference_scaffold["arms"][label]["recovery_fraction"]
            )
            for label in ("k2", "k4", "k8")
        },
    }


def band_rule_reconciliation_block(
    config: durability.DurabilityConfig,
) -> dict[str, Any]:
    """Both declared band rules on the same spectra, with the numbers each uses.

    This runner reads bands as runs of numerically distinct decay magnitudes whose
    consecutive ratio stays inside a declared relative gap; the ladder harness
    reads bands as gaps above a declared fraction of the whole decay-rate range.
    The two rules normalise differently, so they can disagree on one spectrum, and
    the disagreement is reported per profile with the numbers each rule used
    instead of being resolved by preferring one of them.
    """

    names = [row.name for row in ladder_profiles()] + [DEFAULT_PROFILE_NAME]
    by_name = {row.name: row for row in (*all_declared_rows(), *ladder_profiles())}
    rows: list[dict[str, Any]] = []
    for name in names:
        row = by_name[name]
        profile = build_metric_profile(row)
        captures = durability.capture_items(config, profile)
        eigenvalues, _ = np.linalg.eig(geometry.linear_generator(profile))
        mine = decay_gap_bands(eigenvalues)
        theirs = ladder.modal_block_for_profile(profile, captures)
        rows.append(
            {
                "profile": name,
                "specified_spectrum_sha256": survival.array_sha256(
                    np.sort(np.abs(np.asarray(eigenvalues).real))
                ),
                "decay_rate_range": float(theirs["decay_rate_max"] - theirs["decay_rate_min"]),
                "this_runner_rule": {
                    "rule": (
                        "relative consecutive gap > declared tolerance between "
                        "numerically distinct decay magnitudes"
                    ),
                    "tolerance": float(BAND_GAP_TOLERANCE),
                    "band_count": int(mine["band_count"]),
                    "continuum": bool(mine["continuum"]),
                    "bands_separated": bool(mine["bands_separated"]),
                    "smallest_inter_band_gap": float(mine["smallest_inter_band_gap"]),
                },
                "ladder_harness_rule": {
                    "rule": (
                        "absolute gap > 0.05 * (max - min) of the decay rates, "
                        "continuum when the largest gap is below 0.02 * range"
                    ),
                    "qualifying_gap_count": int(len(theirs["band_gaps"])),
                    "band_count": int(theirs["band_count"]),
                    "continuum": bool(theirs["continuum"]),
                    "verdict": str(theirs["band_verdict"]),
                },
                "rules_agree_on_banded": bool(
                    (int(mine["band_count"]) > 1) == (int(theirs["band_count"]) > 1)
                ),
                "band_count_difference": int(theirs["band_count"]) - int(mine["band_count"]),
            }
        )
    disagreements = [row["profile"] for row in rows if not row["rules_agree_on_banded"]]
    resolution = (
        "resolution: the two declared rules normalise differently and are reported "
        "as measured.  This runner's rule is ratio-relative (it splits only where "
        "consecutive distinct decay magnitudes jump by more than the declared "
        "relative tolerance), while the ladder harness's rule is range-relative "
        "(it counts every gap above one twentieth of the whole decay-rate span), so "
        "a spectrum whose largest gap is under the range-relative threshold and "
        "over the ratio-relative threshold is one continuum with jumps here and "
        "several bands there; the reconciliation lists both counts per profile and "
        "the spectrum digest they were read from, and neither rule is claimed to be "
        "the band structure."
    )
    return {
        "profiles": rows,
        "profile_count": len(rows),
        "banded_under_this_runner_rule": [
            row["profile"] for row in rows if not row["this_runner_rule"]["continuum"]
        ],
        "banded_under_ladder_harness_rule": [
            row["profile"] for row in rows if not row["ladder_harness_rule"]["continuum"]
        ],
        "rules_agree_on_banded_for": [
            row["profile"] for row in rows if row["rules_agree_on_banded"]
        ],
        "rules_disagree_on_banded_for": disagreements,
        "resolution": resolution,
    }


def declared_arm_item_names(arm_name: str) -> list[str]:
    """The declared item names one declared arm writes, in declared order."""

    for arm in durability.arm_declarations(durability.DurabilityConfig()):
        if arm.name == arm_name:
            return [durability.ITEM_SPECS[index].name for index in arm.item_indices]
    raise KeyError(f"the durability harness declares no arm {arm_name!r}")


def _row_mechanism(body: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """One declared row's mechanism record, from whichever declared family holds it."""

    for container in (
        body["profiles"],
        body["ladder_family"]["rows"],
        body["uniform_local_family"]["rows"],
    ):
        record = container.get(name)
        if record is not None:
            return record["mechanism"]
    raise KeyError(f"no declared family holds a row named {name!r}")


def cross_talk_reading(
    matrix: Mapping[str, Mapping[str, float]],
    item_names: Sequence[str],
    margin: float,
) -> dict[str, Any]:
    """The distinguishability reading of one item-direction share matrix.

    Pure function of the matrix, so the declared margin's verdict can be
    recomputed and controlled independently of the measurement that produced the
    matrix: an item is distinguished when its own direction's share exceeds the
    largest share among the directions its own write never wrote by the margin.
    """

    own = {item: float(matrix[item][item]) for item in item_names}
    top_unwritten: dict[str, float] = {}
    top_unwritten_item: dict[str, str] = {}
    for written in item_names:
        others = [
            (other, float(matrix[written][other])) for other in item_names if other != written
        ]
        best = max(others, key=lambda pair: (pair[1], pair[0]))
        top_unwritten[written] = best[1]
        top_unwritten_item[written] = best[0]
    distinguished = [item for item in item_names if own[item] - top_unwritten[item] >= margin]
    mean_own = sum(own.values()) / len(item_names)
    mean_unwritten = sum(top_unwritten.values()) / len(item_names)
    return {
        "own_retention": own,
        "max_unwritten_share_per_written_item": top_unwritten,
        "max_unwritten_item_per_written_item": top_unwritten_item,
        "own_minus_max_unwritten_per_item": {
            item: float(own[item] - top_unwritten[item]) for item in item_names
        },
        "distinguished_items": distinguished,
        "distinguished_count": len(distinguished),
        "meets_margin": bool(len(distinguished) == len(item_names)),
        "mean_own_retention": float(mean_own),
        "mean_max_unwritten_share": float(mean_unwritten),
        "max_unwritten_share": float(max(top_unwritten.values())),
        "own_over_unwritten_ratio": float(mean_own / mean_unwritten)
        if mean_unwritten > 0.0
        else None,
        "margin": float(margin),
    }


def cross_talk_and_time_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """Item content versus one rigid mode, and the equal-dimensionless-time leg.

    The ranked retention figure cannot tell item content from a collective mode
    that rings: if a direction that was never written holds as much read-frame
    share as the written direction, the retention is the mode's ring-down and not
    the item.  Each profile therefore reports the full matrix of declared item
    directions read after each declared single-item write, and the written versus
    never-written shares of each declared k arm's own write set, each direction
    normalised by its own alone-write deposit, with the declared margin deciding
    whether an item's own direction is distinguished.  The equal-time leg then
    reports the same profiles' slowest declared decay rate, its ratio to the
    field default's, and the per-item retention measured at the tick count that
    spans the same number of slowest-mode e-fold times as the declared horizon
    does on the default, because equal total inertia normalises the mass sum and
    not the mode frequencies.
    """

    measured = body["cross_talk"]
    equal_time_measured = {row["profile"]: row for row in measured["equal_time"]}
    declared_horizon = {
        row["profile"]: {
            item["item"]: float(item["final_alignment"]) for item in row["horizon"]["per_item"]
        }
        for row in body["flat_inertia_confirmation"]["rows"]
    }
    margin = float(measured["margin"])
    item_names = list(measured["item_names"])
    rows: list[dict[str, Any]] = []
    for record in measured["profiles"]:
        name = record["profile"]
        matrix = record["item_matrix"]
        reading = cross_talk_reading(matrix, item_names, margin)
        arms_out: dict[str, Any] = {}
        for label in measured["declared_arm_labels"]:
            arm_record = record["arms"][label]
            written = {item: float(value) for item, value in arm_record["written_shares"].items()}
            unwritten = {item: float(value) for item, value in arm_record["unwritten_shares"].items()}
            written_values = list(written.values())
            unwritten_values = list(unwritten.values())
            reaching = [
                item
                for item, value in unwritten.items()
                if written_values and value >= min(written_values) - margin
            ]
            arms_out[label] = {
                "arm": arm_record["arm"],
                "written_items": list(arm_record["written_items"]),
                "written_shares": written,
                "written_min": float(min(written_values)) if written_values else None,
                "written_mean": float(sum(written_values) / len(written_values))
                if written_values
                else None,
                "unwritten_items": list(arm_record["unwritten_items"]),
                "unwritten_shares": unwritten,
                "unwritten_max": float(max(unwritten_values)) if unwritten_values else None,
                "unwritten_mean": float(sum(unwritten_values) / len(unwritten_values))
                if unwritten_values
                else None,
                "unwritten_reaching_written_min": reaching,
                "some_unwritten_reaches_a_written_share": bool(reaching),
                "written_set_covers_every_declared_item": bool(not unwritten),
            }
        rows.append(
            {
                "profile": name,
                "declaration_family": record["declaration_family"],
                "item_matrix": matrix,
                "arms": arms_out,
                **reading,
            }
        )
    by_profile = {row["profile"]: row for row in rows}
    flat = by_profile["ladder-uniform"]
    default = by_profile[DEFAULT_PROFILE_NAME]
    # the scoping record: the instrument's read frame, the reason the declared
    # directions decay on the canonical default (the two slow-mode figures are
    # recomputed from this receipt's own mechanism block, not restated), and the
    # aimed-write figure cited from the ladder harness's receipt without re-measuring
    mechanism = mechanism_comparison_block(body)
    comparison = mechanism.get("comparison") or {}
    slow_overlap = comparison.get("flat_minus_default_slow_overlap_mean")
    slow_participation = comparison.get("flat_minus_default_slow_participation_mean")
    widest_item = item_names[0]
    headline_retention = float(default["own_retention"][widest_item])
    cited = CITED_TARGETED_WRITE
    scope = {
        "read_frame": (
            "the eight declared item directions of the declared read frame, each "
            "normalised by its own alone-write deposit"
        ),
        "flat_minus_default_slow_overlap_mean": (
            None if slow_overlap is None else float(slow_overlap)
        ),
        "flat_minus_default_slow_participation_mean": (
            None if slow_participation is None else float(slow_participation)
        ),
        "declared_directions_are_the_slow_modes_on_the_default": bool(
            slow_overlap is not None and float(slow_overlap) <= 0.0
        ),
        "declared_widest_item": widest_item,
        "declared_widest_item_retention_on_the_default": headline_retention,
        "targeted_write": {
            "kind": cited["kind"],
            "source_pointer": cited["source_pointer"],
            "cited_not_recomputed": True,
            "receipt": cited["receipt"],
            "receipt_content_digest": cited["receipt_content_digest"],
            "record": cited["record"],
            "profile_note": cited["profile_note"],
            "item_path": cited["item_path"],
            "item_component": cited["item_component"],
            "item_width": int(cited["item_width"]),
            "dominant_in_slow_band": bool(cited["dominant_in_slow_band"]),
            "slow_weight": float(cited["slow_weight"]),
            "measured_retention": float(cited["measured_retention"]),
            "resolving_test": "test_cross_talk_scope_statement_resolves_its_citations",
        },
        "flat_own_over_unwritten_ratio": flat["own_over_unwritten_ratio"],
        "flat_distinguished_count": int(flat["distinguished_count"]),
        "item_count": len(item_names),
        "conclusions": [
            CROSS_TALK_CONCLUSION_AIM.format(targeted=float(cited["measured_retention"])),
            CROSS_TALK_CONCLUSION_METRIC.format(
                flat_own=float(flat["mean_own_retention"]),
                flat_unwritten=float(flat["mean_max_unwritten_share"]),
            ),
        ],
    }
    scope["statement"] = CROSS_TALK_SCOPE_STATEMENT.format(
        receipt=cited["receipt"],
        record=cited["record"],
        slow_overlap=float(scope["flat_minus_default_slow_overlap_mean"]),
        slow_participation=float(scope["flat_minus_default_slow_participation_mean"]),
        width=int(cited["item_width"]),
        path=cited["item_path"],
        component=cited["item_component"],
        slow_weight=float(cited["slow_weight"]),
        targeted=float(cited["measured_retention"]),
        headline=headline_retention,
        headline_item=widest_item,
        own_over_unwritten=float(flat["own_over_unwritten_ratio"]),
        distinguished=int(flat["distinguished_count"]),
        item_count=len(item_names),
    )
    equal_time_rows: list[dict[str, Any]] = []
    for record in measured["equal_time"]:
        name = record["profile"]
        mechanism = _row_mechanism(body, name)
        reference = declared_horizon[name]
        measured_items = {item["item"]: item for item in record["per_item"]}
        equal_time_rows.append(
            {
                "profile": name,
                "instrument": record["instrument"],
                "sample_every": int(record["sample_every"]),
                "slowest_decay_rate": float(record["slowest_decay_rate"]),
                "fastest_decay_rate": float(record["fastest_decay_rate"]),
                "time_step": float(record["time_step"]),
                "reference_time_step": float(record["reference_time_step"]),
                "efold_ticks_at_slowest": float(record["efold_ticks_at_slowest"]),
                "decay_magnitude_range": [float(value) for value in record["decay_magnitude_range"]],
                "frequency_magnitude_range": [
                    float(value) for value in mechanism["frequency_magnitude_range"]
                ],
                "row_mechanism_decay_magnitude_range": [
                    float(value) for value in mechanism["decay_magnitude_range"]
                ],
                "reference_profile": EQUAL_TIME_REFERENCE_PROFILE,
                "reference_slowest_decay_rate": float(record["reference_slowest_decay_rate"]),
                "slowest_decay_ratio_vs_reference": float(
                    record["slowest_decay_ratio_vs_reference"]
                ),
                "slowest_mode_is_marginal": bool(record["slowest_mode_is_marginal"]),
                "efolds_at_declared_horizon": float(record["efolds_at_declared_horizon"]),
                "declared_reference_efolds": float(record["declared_reference_efolds"]),
                "equal_time_horizon_ticks": int(record["equal_time_horizon_ticks"]),
                "equal_time_tick_cap": int(record["equal_time_tick_cap"]),
                "tick_cap_applied": bool(record["tick_cap_applied"]),
                "tick_scale_vs_declared_horizon": float(record["tick_scale_vs_declared_horizon"]),
                "efolds_at_equal_time_horizon": float(record["efolds_at_equal_time_horizon"]),
                "equal_time_efold_residual": float(record["equal_time_efold_residual"]),
                "declared_horizon_ticks": int(measured["horizon_ticks"]),
                "declared_horizon_per_item": reference,
                "declared_horizon_final_alignment_min": float(min(reference.values())),
                "declared_horizon_final_alignment_mean": float(
                    sum(reference.values()) / len(reference)
                ),
                "equal_time_per_item": {
                    item: float(value["final_alignment"])
                    for item, value in measured_items.items()
                },
                "equal_time_lifetime_ticks": {
                    item: int(value["lifetime_ticks"]) for item, value in measured_items.items()
                },
                "equal_time_censored_items": [
                    item for item, value in measured_items.items() if value["censored"]
                ],
                "equal_time_final_alignment_min": float(record["final_alignment_min"]),
                "equal_time_final_alignment_mean": float(record["final_alignment_mean"]),
                "equal_time_mean_alignment_min": float(record["mean_alignment_min"]),
                "equal_time_mean_alignment_mean": float(record["mean_alignment_mean"]),
                "equal_time_time_mean_per_item": {
                    item: float(value["mean_alignment"]) for item, value in measured_items.items()
                },
                "equal_time_last_quarter_min_per_item": {
                    item: float(value["last_quarter_min"])
                    for item, value in measured_items.items()
                },
                "delta_vs_declared_horizon_per_item": {
                    item: float(
                        measured_items[item]["final_alignment"] - reference[item]
                    )
                    for item in reference
                },
            }
        )
    time_by_profile = {row["profile"]: row for row in equal_time_rows}
    time_flat = time_by_profile["ladder-uniform"]
    time_default = time_by_profile[DEFAULT_PROFILE_NAME]
    time_comparison = {
        "margin": float(EQUAL_TIME_MARGIN),
        "flat_slowest_decay_ratio_vs_default": float(
            time_flat["slowest_decay_ratio_vs_reference"]
        ),
        "flat_equal_time_horizon_ticks": int(time_flat["equal_time_horizon_ticks"]),
        "default_equal_time_horizon_ticks": int(time_default["equal_time_horizon_ticks"]),
        "flat_minus_default_at_equal_time": float(
            time_flat["equal_time_final_alignment_mean"]
            - time_default["equal_time_final_alignment_mean"]
        ),
        "flat_leads_default_at_equal_time_by_margin": bool(
            time_flat["equal_time_final_alignment_mean"]
            - time_default["equal_time_final_alignment_mean"]
            >= float(EQUAL_TIME_MARGIN)
        ),
        # The flat profile's own spectrum oscillates (one declared period, per the
        # ladder harness's cited intrinsic side), so a single tick is phase
        # sensitive: the time-mean of the same window is reported as the primary
        # equal-time figure and the endpoint value beside it.
        "flat_minus_default_at_equal_time_time_mean": float(
            time_flat["equal_time_mean_alignment_mean"]
            - time_default["equal_time_mean_alignment_mean"]
        ),
        "flat_leads_default_at_equal_time_time_mean_by_margin": bool(
            time_flat["equal_time_mean_alignment_mean"]
            - time_default["equal_time_mean_alignment_mean"]
            >= float(EQUAL_TIME_MARGIN)
        ),
        "flat_minus_default_at_declared_horizon": float(
            time_flat["declared_horizon_final_alignment_mean"]
            - time_default["declared_horizon_final_alignment_mean"]
        ),
        "flat_leads_default_at_declared_horizon_by_margin": bool(
            time_flat["declared_horizon_final_alignment_mean"]
            - time_default["declared_horizon_final_alignment_mean"]
            >= float(EQUAL_TIME_MARGIN)
        ),
        "flat_decay_span_is_narrowest": bool(
            (time_flat["decay_magnitude_range"][1] - time_flat["decay_magnitude_range"][0])
            == min(
                row["decay_magnitude_range"][1] - row["decay_magnitude_range"][0]
                for row in equal_time_rows
            )
        ),
        "verdict": (
            EQUAL_TIME_VERDICT_LEADS
            if (
                time_flat["equal_time_mean_alignment_mean"]
                - time_default["equal_time_mean_alignment_mean"]
                >= float(EQUAL_TIME_MARGIN)
                and time_flat["equal_time_final_alignment_mean"]
                - time_default["equal_time_final_alignment_mean"]
                >= float(EQUAL_TIME_MARGIN)
            )
            else EQUAL_TIME_VERDICT_BAND_NARROWING
        ),
    }
    return {
        "measured": True,
        "instrument": measured["instrument"],
        "horizon_ticks": int(measured["horizon_ticks"]),
        "margin": margin,
        "item_names": item_names,
        "declared_arm_labels": list(measured["declared_arm_labels"]),
        "declared_arm_names": dict(measured["declared_arm_names"]),
        "profile_order": list(measured["profile_order"]),
        "rows": rows,
        "verdict": (
            CROSS_TALK_VERDICT_STORED if flat["meets_margin"] else CROSS_TALK_VERDICT_RIGID_MODE
        ),
        "every_profile_keeps_item_content": bool(
            all(row["meets_margin"] for row in rows)
        ),
        "profiles_without_item_content": [
            row["profile"] for row in rows if not row["meets_margin"]
        ],
        "flat_keeps_item_content": bool(flat["meets_margin"]),
        "flat_distinguished_count": int(flat["distinguished_count"]),
        "flat_min_own_minus_max_unwritten": float(
            min(flat["own_minus_max_unwritten_per_item"].values())
        ),
        "default_min_own_minus_max_unwritten": float(
            min(default["own_minus_max_unwritten_per_item"].values())
        ),
        "flat_cross_talk_is_the_smallest": bool(
            flat["mean_max_unwritten_share"]
            <= min(row["mean_max_unwritten_share"] for row in rows)
        ),
        "equal_time_rows": equal_time_rows,
        "equal_time_comparison": time_comparison,
        "scope": scope,
    }


def mechanism_comparison_block(
    body: Mapping[str, Any],
    profiles: Sequence[str] = ("ladder-uniform", DEFAULT_PROFILE_NAME, "ladder-ratio-phi"),
) -> dict[str, Any]:
    """Why the flat profile retains: participation, decay span and slow-mode overlap.

    The mechanism question is whether flat inertia concentrates the written
    directions into the slow modes, slows the whole spectrum, or does something
    else.  Each named profile reports the slow-mode participation of the eight
    declared item directions of the widest arm, the decay-rate span of its frozen
    spectrum, and the overlap of those same eight directions with the slow half
    of the spectrum, so the three readings can be compared side by side.
    """

    ladder_block = body.get("ladder_family") or {}
    sources: dict[str, Mapping[str, Any]] = dict(body["profiles"])
    if ladder_block.get("rows"):
        sources.update(ladder_block["rows"])
    written = declared_arm_item_names(CONTEXT_ARM_NAMES[1])
    rows: list[dict[str, Any]] = []
    for name in profiles:
        if name not in sources:
            continue
        mechanism = sources[name]["mechanism"]
        items = {item["name"]: item for item in mechanism["items"]}
        participation = [
            float(items[item]["overlaps"]["slow_participation_slower_half_by_decay"])
            for item in written
        ]
        overlap = [
            float(items[item]["overlaps"][PRIMARY_MEASURE]) for item in written
        ]
        span = [float(value) for value in mechanism["decay_magnitude_range"]]
        rows.append(
            {
                "profile": name,
                "item_count": len(written),
                "slow_participation_min": float(min(participation)),
                "slow_participation_mean": float(sum(participation) / len(participation)),
                "slow_mode_overlap_min": float(min(overlap)),
                "slow_mode_overlap_mean": float(sum(overlap) / len(overlap)),
                "per_item_slow_participation": dict(zip(written, participation)),
                "per_item_slow_mode_overlap": dict(zip(written, overlap)),
                "decay_rate_span": float(span[1] - span[0]),
                "decay_rate_min": float(span[0]),
                "decay_rate_max": float(span[1]),
                "slower_half_mode_count": int(mechanism["slower_half_mode_count"]),
                "slowest_modes_participating_pools": [
                    float(value) for value in mechanism["slowest_modes_participating_pools"]
                ],
            }
        )
    comparison: dict[str, Any] = {}
    if len(rows) >= 2:
        flat, other = rows[0], rows[1]
        comparison = {
            "flat_minus_default_slow_participation_mean": float(
                flat["slow_participation_mean"] - other["slow_participation_mean"]
            ),
            "flat_minus_default_slow_overlap_mean": float(
                flat["slow_mode_overlap_mean"] - other["slow_mode_overlap_mean"]
            ),
            "flat_minus_default_decay_span": float(
                flat["decay_rate_span"] - other["decay_rate_span"]
            ),
            "flat_concentrates_written_directions_into_slow_modes": bool(
                flat["slow_participation_mean"] > other["slow_participation_mean"]
            ),
            "flat_span_is_narrower_than_default": bool(
                flat["decay_rate_span"] < other["decay_rate_span"]
            ),
        }
    return {
        "definitions": {
            "slow_modes": SLOW_MODE_DEFINITION,
            "slow_participation_measure": MEASURE_DEFINITIONS[
                "slow_participation_slower_half_by_decay"
            ],
            "slow_mode_overlap_measure": MEASURE_DEFINITIONS[PRIMARY_MEASURE],
            "declared_item_set": (
                "the eight declared item directions of the widest declared arm "
                f"({CONTEXT_ARM_NAMES[1]})"
            ),
            "decay_rate_span": (
                "max minus min of the frozen generator's decay magnitudes "
                "(|Re eigenvalue|)"
            ),
        },
        "rows": rows,
        "comparison": comparison,
    }


def _context_profile_names(ranking: Sequence[str], default_name: str) -> list[str]:
    """The declared context rows: the ranking's leaders plus the default."""

    names: list[str] = []
    for name in [*ranking[:CONTEXT_PROFILE_COUNT], default_name]:
        if name not in names:
            names.append(name)
    return names


def declared_block(
    config: durability.DurabilityConfig,
    rows: Sequence[MetricProfile],
    declared_row_order: Sequence[str],
    designed_ranking: Sequence[str],
    context_names: Sequence[str],
) -> dict[str, Any]:
    return {
        "geometry_module": geometry.__name__,
        "geometry_schema": geometry.SCHEMA,
        "survival_module": survival.__name__,
        "survival_schema": survival.SCHEMA,
        "durability_module": durability.__name__,
        "durability_schema": durability.SCHEMA,
        "config": config.as_dict(),
        "control_margin": float(config.control_margin),
        "read_frame_path": durability.READ_FRAME_PATH,
        "survival_arm_name": SURVIVAL_ARM_NAME,
        "single_item_arm_name": SINGLE_ITEM_ARM_NAME,
        "context_arm_names": list(CONTEXT_ARM_NAMES),
        "declared_arm_names": [
            {
                "arm": arm.name,
                "written_items": [
                    durability.ITEM_SPECS[index].name for index in arm.item_indices
                ],
                "activity": bool(arm.activity),
                "source_enabled": bool(arm.sources),
            }
            for arm in durability.arm_declarations(config)
            if arm.name
            in (SURVIVAL_ARM_NAME, SINGLE_ITEM_ARM_NAME, *CONTEXT_ARM_NAMES)
        ],
        "profile_count": len(rows),
        "profile_bound": MAX_DECLARED_PROFILES,
        "default_profile": DEFAULT_PROFILE_NAME,
        "reference_metric_profile": REFERENCE_METRIC_PROFILE_NAME,
        "canonical_hook_profile": CANONICAL_HOOK_PROFILE_NAME,
        "reference_row": REFERENCE_ROW_NAME,
        "designed_profile_names": [row.name for row in declared_profiles()],
        "profile_declarations": [
            {
                "name": row.name,
                "kind": row.kind,
                "rail": row.rail,
                "rule": row.rule,
                "contrast": row.contrast,
                "seed": row.seed,
                "core_pool": row.core_pool,
                "jitter_bound": row.jitter_bound,
                "note": row.note,
            }
            for row in rows
        ],
        "graded_contrasts": list(SHELL_CONTRASTS),
        "graded_core_pool": SHELL_CORE_POOL,
        "random_profile_count": RANDOM_PROFILE_COUNT,
        "random_seeds": [
            RANDOM_SEED_BASE + RANDOM_SEED_STEP * index
            for index in range(RANDOM_PROFILE_COUNT)
        ],
        "random_contrasts": list(RANDOM_CONTRASTS),
        "random_jitter_bound": RANDOM_JITTER_BOUND,
        "cross_rail_arrangement": CROSS_RAIL_ARRANGEMENT,
        "declared_row_order": list(declared_row_order),
        "designed_ranking_by_k4_min_per_item_recovery": list(designed_ranking),
        "context_profile_names": list(context_names),
        "context_profile_count": CONTEXT_PROFILE_COUNT,
        "ranking_margin": float(RANKING_MARGIN),
        "headline_survival_margin": float(HEADLINE_SURVIVAL_MARGIN),
        "primary_relation_margin": float(PRIMARY_RELATION_MARGIN),
        "spectral_residual_tolerance": float(SPECTRAL_RESIDUAL_TOLERANCE),
        "spectral_rotation_tolerance": float(SPECTRAL_ROTATION_TOLERANCE),
        "spectral_separation_tolerance": float(SPECTRAL_SEPARATION_TOLERANCE),
        "degenerate_cluster_tolerance": float(DEGENERATE_CLUSTER_TOLERANCE),
        "cluster_rotation_draws": int(CLUSTER_ROTATION_DRAWS),
        "cluster_rotation_seed": int(CLUSTER_ROTATION_SEED),
        "primary_measure": PRIMARY_MEASURE,
        "measure_definitions": dict(MEASURE_DEFINITIONS),
        "measure_names": list(MEASURE_NAMES),
        "activity_retention_threshold": float(ACTIVITY_RETENTION_THRESHOLD),
        "cited_recovery": dict(CITED_RECOVERY),
        "cited_reproduction_tolerance": float(CITED_REPRODUCTION_TOLERANCE),
        "metric_hypothesis": METRIC_HYPOTHESIS,
        "activity_confound": ACTIVITY_CONFOUND_STATEMENT,
        "ladder_profile_bound": int(LADDER_PROFILE_BOUND),
        "ladder_default_ratio": float(DEFAULT_LADDER_RATIO),
        "ladder_shuffle_seed": int(LADDER_SHUFFLE_SEED),
        "ladder_normalizations": dict(LADDER_NORMALIZATIONS),
        "ladder_band_gap_tolerance": float(BAND_GAP_TOLERANCE),
        "ladder_band_ratio_tolerance": float(BAND_RATIO_TRACKING_TOLERANCE),
        "ladder_claim": LADDER_CLAIM_STATEMENT,
        "ladder_profile_declarations": [
            {
                "name": row.name,
                "kind": row.kind,
                "family": row.family,
                "rule": row.rule,
                "ladder_ratio": row.ladder_ratio,
                "normalization": row.normalization,
                "seed": row.seed,
                "note": row.note,
            }
            for row in ladder_profiles()
        ],
        "uniform_local_profile_bound": int(UNIFORM_LOCAL_PROFILE_BOUND),
        "uniform_local_pool": int(UNIFORM_LOCAL_POOL),
        "uniform_local_pair": [int(pool) for pool in UNIFORM_LOCAL_PAIR],
        "uniform_local_contrasts": [float(value) for value in UNIFORM_LOCAL_CONTRASTS],
        "uniform_local_pair_contrasts": [
            float(value) for value in UNIFORM_LOCAL_PAIR_CONTRASTS
        ],
        "uniform_local_rule": UNIFORM_LOCAL_RULE,
        "uniform_local_profile_declarations": [
            {
                "name": row.name,
                "kind": row.kind,
                "family": row.family,
                "rule": row.rule,
                "contrast": row.contrast,
                "local_pools": [int(pool) for pool in row.local_pools],
                "normalization": row.normalization,
                "note": row.note,
            }
            for row in uniform_local_profiles()
        ],
        "horizon_instrument": HORIZON_INSTRUMENT,
        "placement_instrument": PLACEMENT_INSTRUMENT,
        "flat_confirmation_profiles": list(FLAT_CONFIRMATION_PROFILES),
        "cross_talk_instrument": CROSS_TALK_INSTRUMENT,
        "cross_talk_margin": float(CROSS_TALK_MARGIN),
        "cross_talk_verdicts": [CROSS_TALK_VERDICT_STORED, CROSS_TALK_VERDICT_RIGID_MODE],
        "equal_time_instrument": EQUAL_TIME_INSTRUMENT,
        "equal_time_reference_profile": EQUAL_TIME_REFERENCE_PROFILE,
        "equal_time_tick_cap": int(EQUAL_TIME_TICK_CAP),
        "equal_time_sample_every": int(EQUAL_TIME_SAMPLE_EVERY),
        "equal_time_margin": float(EQUAL_TIME_MARGIN),
        "cross_talk_scope_statement": CROSS_TALK_SCOPE_STATEMENT,
        "cross_talk_scope_conclusions": [CROSS_TALK_CONCLUSION_AIM, CROSS_TALK_CONCLUSION_METRIC],
        "cited_targeted_write": {
            key: value for key, value in CITED_TARGETED_WRITE.items()
        },
        "definitions": DEFINITIONS,
    }


# --------------------------------------------------------------------------
# derived summary
# --------------------------------------------------------------------------
def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if a.size < 2 or float(a.std()) == 0.0 or float(b.std()) == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _average_ranks(values: Sequence[float]) -> np.ndarray:
    """Ascending ranks with ties averaged, so the rank correlation is defined."""

    array = np.asarray(values, dtype=np.float64)
    order = np.argsort(array, kind="stable")
    ranks = np.empty(array.size, dtype=np.float64)
    cursor = 0
    while cursor < array.size:
        stop = cursor
        while stop + 1 < array.size and array[order[stop + 1]] == array[order[cursor]]:
            stop += 1
        ranks[order[cursor : stop + 1]] = 0.5 * (cursor + stop) + 1.0
        cursor = stop + 1
    return ranks


def _spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 2:
        return None
    return _pearson(_average_ranks(left), _average_ranks(right))


def ranking_entries(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The declared ranking of the designed family by minimum per-item recovery."""

    declared = body["declared"]
    default = declared["default_profile"]
    reference = declared["reference_metric_profile"]
    margin = float(declared["ranking_margin"])
    designed = list(declared["designed_profile_names"])
    default_recovery = float(
        body["profiles"][default]["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]
    )
    reference_recovery = float(
        body["profiles"][reference]["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]
    )
    rows: list[dict[str, Any]] = []
    for name in designed:
        record = body["profiles"][name]
        arm = record["arms"][SURVIVAL_ARM_NAME]
        recovery = float(arm["recovery_fraction"])
        rows.append(
            {
                "profile": name,
                "kind": record["declaration"]["kind"],
                "rule": record["declaration"]["rule"],
                "contrast": record["declaration"]["contrast"],
                "seed": record["declaration"]["seed"],
                "k4_min_per_item_recovery": recovery,
                "k4_per_item_recovery": dict(arm["per_item_recovery_fraction"]),
                "single_item_recovery": float(
                    record["arms"][SINGLE_ITEM_ARM_NAME]["recovery_fraction"]
                ),
                "delta_vs_default": recovery - default_recovery,
                "delta_vs_reference_metric": recovery - reference_recovery,
                "differs_from_default_by_margin": bool(
                    abs(recovery - default_recovery) >= margin
                ),
                "exceeds_default_by_margin": bool(recovery - default_recovery >= margin),
                "heartbeat_work_total": float(arm["activity_positive_heartbeat_work_total"]),
                "dissipated_work_total": float(arm["activity_dissipated_work_total"]),
                "total_packet_energy_ratio": arm["total_packet_energy_ratio"],
                "activity_running": bool(
                    float(arm["activity_positive_heartbeat_work_total"])
                    >= float(declared["activity_retention_threshold"])
                ),
                "metric_diagonal_min": float(record["mass_metric"]["diagonal_min"]),
                "metric_diagonal_max": float(record["mass_metric"]["diagonal_max"]),
                "generator_sha256": record["mechanism"]["generator_sha256"],
            }
        )
    rows.sort(key=lambda row: (-row["k4_min_per_item_recovery"], row["profile"]))
    for position, row in enumerate(rows, start=1):
        row["rank"] = position
    return rows


def headline_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The declared headline: the best designed profile against both references."""

    declared = body["declared"]
    margin = float(declared["ranking_margin"])
    entries = ranking_entries(body)
    best = entries[0]
    default_name = declared["default_profile"]
    reference_name = declared["reference_metric_profile"]
    reference_row = declared["reference_row"]
    default_recovery = float(
        body["profiles"][default_name]["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]
    )
    reference_metric = float(
        body["profiles"][reference_name]["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]
    )
    reference_scaffold = float(
        body["profiles"][reference_row]["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]
    )
    best_recovery = float(best["k4_min_per_item_recovery"])
    return {
        "arm": SURVIVAL_ARM_NAME,
        "best_profile": best["profile"],
        "best_construction_rule": best["rule"],
        "best_recovery": best_recovery,
        "best_heartbeat_work_total": best["heartbeat_work_total"],
        "best_total_packet_energy_ratio": best["total_packet_energy_ratio"],
        "best_is_extreme_endpoint_of_the_graded_family": bool(
            best["kind"] == "graded"
            and best.get("contrast") in (min(SHELL_CONTRASTS), max(SHELL_CONTRASTS))
        ),
        "graded_family_contrasts": [float(value) for value in SHELL_CONTRASTS],
        "default_profile": default_name,
        "default_recovery": default_recovery,
        "reference_metric_profile": reference_name,
        "reference_metric_recovery": reference_metric,
        "reference_row": reference_row,
        "reference_scaffold_recovery": reference_scaffold,
        "best_minus_default": best_recovery - default_recovery,
        "best_minus_reference_metric": best_recovery - reference_metric,
        "best_minus_reference_scaffold": best_recovery - reference_scaffold,
        "margin": margin,
        "exceeds_default_by_margin": bool(best_recovery - default_recovery >= margin),
        "exceeds_reference_scaffold_by_margin": bool(
            best_recovery - reference_scaffold >= margin
        ),
        "headline_survival_margin": float(declared["headline_survival_margin"]),
        "exceeds_default_by_headline_margin": bool(
            best_recovery - default_recovery >= float(declared["headline_survival_margin"])
        ),
        "cited_reproduction": {
            name: {
                "cited": cited,
                "measured": float(
                    body["profiles"][measured_name]["arms"][SURVIVAL_ARM_NAME][
                        "recovery_fraction"
                    ]
                ),
                "absolute_difference": float(
                    abs(
                        float(
                            body["profiles"][measured_name]["arms"][SURVIVAL_ARM_NAME][
                                "recovery_fraction"
                            ]
                        )
                        - cited
                    )
                ),
            }
            for name, cited, measured_name in (
                ("helix7", CITED_RECOVERY["helix7"], default_name),
                ("mass-only", CITED_RECOVERY["mass-only"], reference_name),
                ("nested-core-shell", CITED_RECOVERY["nested-core-shell"], reference_row),
            )
        },
        "cited_reproduction_tolerance": float(CITED_REPRODUCTION_TOLERANCE),
        "cited_reproduction_holds": all(
            abs(
                float(
                    body["profiles"][measured_name]["arms"][SURVIVAL_ARM_NAME][
                        "recovery_fraction"
                    ]
                )
                - cited
            )
            <= float(CITED_REPRODUCTION_TOLERANCE)
            for cited, measured_name in (
                (CITED_RECOVERY["helix7"], default_name),
                (CITED_RECOVERY["mass-only"], reference_name),
                (CITED_RECOVERY["nested-core-shell"], reference_row),
            )
        ),
    }


def hook_fidelity_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The control that shows the hook channel reproduces the canonical metric."""

    declared = body["declared"]
    default = declared["default_profile"]
    control = declared["canonical_hook_profile"]
    default_record = body["profiles"][default]
    control_record = body["profiles"][control]
    difference = float(
        abs(
            float(control_record["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"])
            - float(default_record["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"])
        )
    )
    reference_row = body["profiles"][declared["reference_row"]]
    graded_setting = f"shell-contrast-{SHELL_REFERENCE_DECAY}"
    graded_match = bool(
        np.array_equal(
            np.asarray(declared_inverse_mass(declared_row(graded_setting))),
            np.asarray(
                declared_inverse_mass(declared_row(declared["reference_metric_profile"]))
            ),
        )
    )
    return {
        "canonical_hook_profile": control,
        "default_profile": default,
        "generator_identical_to_default": bool(
            control_record["mechanism"]["generator_sha256"]
            == default_record["mechanism"]["generator_sha256"]
        ),
        "k4_recovery_difference_vs_default": difference,
        "k4_recovery_reproduced": bool(difference <= float(CITED_REPRODUCTION_TOLERANCE)),
        "graded_setting_coinciding_with_reference_metric": graded_setting,
        "graded_setting_matches_reference_vector": graded_match,
        "graded_setting_recovery_difference_vs_reference": float(
            abs(
                float(
                    body["profiles"][graded_setting]["arms"][SURVIVAL_ARM_NAME][
                        "recovery_fraction"
                    ]
                )
                - float(
                    body["profiles"][declared["reference_metric_profile"]]["arms"][
                        SURVIVAL_ARM_NAME
                    ]["recovery_fraction"]
                )
            )
        ),
        "reference_row_uses_both_hooks": bool(
            reference_row["profile_hooks"]["has_projected_transport"]
            and reference_row["profile_hooks"]["has_projected_inv_mass"]
        ),
    }


def overlap_survival_relation(body: Mapping[str, Any]) -> dict[str, Any]:
    """Does survival track the declared overlap between items and slow modes?"""

    declared = body["declared"]
    designed = list(declared["designed_profile_names"])
    written = list(
        body["profiles"][declared["default_profile"]]["arms"][SURVIVAL_ARM_NAME][
            "written_items"
        ]
    )
    relation: dict[str, Any] = {}
    excluded: dict[str, list[str]] = {}
    for measure in MEASURE_NAMES:
        per_profile_overlap: list[float] = []
        per_profile_recovery: list[float] = []
        pooled_overlap: list[float] = []
        pooled_recovery: list[float] = []
        skipped: list[str] = []
        profile_overlaps: dict[str, float] = {}
        for name in designed:
            record = body["profiles"][name]
            if measure in PARTICIPATION_MEASURES and not record["mechanism"][
                "participation_measure_valid"
            ]:
                skipped.append(name)
                continue
            items = {item["name"]: item for item in record["mechanism"]["items"]}
            written_overlaps = [items[item]["overlaps"][measure] for item in written]
            per_item = record["arms"][SURVIVAL_ARM_NAME]["per_item_recovery_fraction"]
            profile_overlaps[name] = min(written_overlaps)
            per_profile_overlap.append(min(written_overlaps))
            per_profile_recovery.append(
                float(record["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"])
            )
            pooled_overlap.extend(written_overlaps)
            pooled_recovery.extend(float(per_item[item]) for item in written)
        if skipped:
            excluded[measure] = skipped
        relation[measure] = {
            "definition": MEASURE_DEFINITIONS[measure],
            "primary": measure == PRIMARY_MEASURE,
            "aggregation_for_the_profile_level_figure": "minimum over the written items",
            "profile_level_pearson": _pearson(per_profile_overlap, per_profile_recovery),
            "profile_level_spearman": _spearman(per_profile_overlap, per_profile_recovery),
            "pooled_per_item_pearson": _pearson(pooled_overlap, pooled_recovery),
            "pooled_per_item_spearman": _spearman(pooled_overlap, pooled_recovery),
            "pooled_pair_count": int(len(pooled_overlap)),
            "profiles_aggregated": list(profile_overlaps),
            "profiles": profile_overlaps,
        }
    primary = relation[PRIMARY_MEASURE]
    leader = relation[PRIMARY_MEASURE]["profiles"]
    return {
        "measures": relation,
        "primary_measure": PRIMARY_MEASURE,
        "primary_relation_margin": float(declared["primary_relation_margin"]),
        "highest_primary_overlap_profile": (
            max(leader, key=lambda name: leader[name]) if leader else None
        ),
        "lowest_primary_overlap_profile": (
            min(leader, key=lambda name: leader[name]) if leader else None
        ),
        "primary_relation_tracked": bool(
            primary["profile_level_spearman"] is not None
                and float(primary["profile_level_spearman"])
                >= float(declared["primary_relation_margin"])
        ),
        "reading": (
            "Declared reading: survival tracks the direction's overlap with the "
            "slow modes to the degree the primary measure's rank correlation "
            "shows; the battery is reported whole because the measures disagree, "
            "so a positive reading on the primary is evidence for the mechanism "
            "and a negative reading on a projector variant is evidence that the "
            "slow-mode identity of the written directions is measure-dependent."
        ),
        "participation_measures": sorted(PARTICIPATION_MEASURES),
        "profiles_excluded_for_participation_measures": excluded,
        "written_items": written,
    }


def scale_check_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The k=2 and k=8 declared arms beside the ranked k=4 figure."""

    declared = body["declared"]
    default = declared["default_profile"]
    margin = float(declared["ranking_margin"])
    arms_by_count = {
        "k2": CONTEXT_ARM_NAMES[0],
        "k4": SURVIVAL_ARM_NAME,
        "k8": CONTEXT_ARM_NAMES[1],
    }
    default_recoveries: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for name in declared["context_profile_names"]:
        record = body["profiles"][name]
        figures = {
            label: float(record["arms"][arm_name]["recovery_fraction"])
            for label, arm_name in arms_by_count.items()
        }
        if name == default:
            default_recoveries = figures
        rows.append(
            {
                "profile": name,
                "recoveries": figures,
                "per_item_recovery_at_k8": dict(
                    record["arms"][arms_by_count["k8"]]["per_item_recovery_fraction"]
                ),
                "activity_heartbeat_work_at_k8": float(
                    record["arms"][arms_by_count["k8"]][
                        "activity_positive_heartbeat_work_total"
                    ]
                ),
            }
        )
    for row in rows:
        row["advantage_over_default"] = {
            label: row["recoveries"][label] - default_recoveries.get(label, 0.0)
            for label in arms_by_count
        }
        row["holds_at_every_declared_k"] = bool(
            all(
                value >= margin for value in row["advantage_over_default"].values()
            )
        )
    return {
        "arms_by_count": arms_by_count,
        "margin": margin,
        "rows": rows,
        "context_profile_names": list(declared["context_profile_names"]),
        "reading": (
            "Declared reading: a profile only scales past the declared ranking "
            "if its advantage over the default survives at k=2 and k=8 as well as "
            "at the ranked k=4; a profile whose advantage inverts at a wider write "
            "set is a ranking of the declared arm, not a robust design rule."
        ),
        "profiles_scaling_at_every_declared_k": [
            row["profile"] for row in rows if row["holds_at_every_declared_k"]
        ],
    }


def ladder_family_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The declared ladder family: retention, slow-mode overlap and band structure.

    Every ladder row is measured against the field's real default ladder (ratio
    1.3, which is the canonical metric hook) and the nested reference scaffold at
    the same declared arm and normalization.  Two claims are reported as they
    come out rather than as they were hoped to come out:

    * the band claim, that a geometric inertia ladder spaces the decay-spectrum
      bands by its own declared ratio, and
    * the lifetime-ladder claim, that the pool-family lifetime ladder tracks the
      square root of the declared inertia ratio.

    Both are tested against the declared band-ratio tracking tolerance, the
    ordered-ladder gate, and the flat (one centre) and scrambled (matched-random)
    controls, which is what makes the verdicts falsifiable.
    """

    declared = body["declared"]
    ladder = body.get("ladder_family")
    if not ladder:
        return {"measured": False, "reason": "the receipt carries no ladder family"}
    default_name = declared["default_profile"]
    reference_name = declared["reference_metric_profile"]
    scaffold_name = declared["reference_row"]
    default_recovery = float(
        body["profiles"][default_name]["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]
    )
    reference_recovery = float(
        body["profiles"][reference_name]["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]
    )
    scaffold_recovery = float(
        body["profiles"][scaffold_name]["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]
    )
    written_items = list(
        body["profiles"][default_name]["arms"][SURVIVAL_ARM_NAME]["written_items"]
    )
    rows: list[dict[str, Any]] = []
    for name in ladder["row_order"]:
        record = ladder["rows"][name]
        arm = record["arms"][SURVIVAL_ARM_NAME]
        mechanism = record["mechanism"]
        bands = mechanism["decay_gap_bands"]
        family = mechanism["pool_family_ladder"]
        items = {item["name"]: item for item in mechanism["items"]}
        written_overlap = [items[item]["overlaps"][PRIMARY_MEASURE] for item in written_items]
        written_participation = [
            items[item]["overlaps"]["slow_participation_slower_half_by_decay"]
            for item in written_items
        ]
        recovery = float(arm["recovery_fraction"])
        ratio = record["declaration"]["ladder_ratio"]
        declared_ratio = float(ratio) if ratio else None
        sqrt_ratio = math.sqrt(abs(declared_ratio)) if declared_ratio else None
        band_deviation = (
            abs(math.log(bands["band_ladder_ratio"] / declared_ratio))
            if declared_ratio
            else None
        )
        lifetime_deviation = (
            abs(math.log(family["lifetime_ladder_ratio"] / sqrt_ratio))
            if sqrt_ratio
            else None
        )
        rows.append(
            {
                "profile": name,
                "kind": record["declaration"]["kind"],
                "declared_ladder_ratio": declared_ratio,
                "normalization": record["declaration"]["normalization"],
                "seed": record["declaration"]["seed"],
                "k4_min_per_item_recovery": recovery,
                "k4_per_item_recovery": dict(arm["per_item_recovery_fraction"]),
                "delta_vs_default_ladder": recovery - default_recovery,
                "delta_vs_reference_metric": recovery - reference_recovery,
                "delta_vs_reference_scaffold": recovery - scaffold_recovery,
                "exceeds_default_ladder_by_margin": bool(
                    recovery - default_recovery >= float(declared["ranking_margin"])
                ),
                "heartbeat_work_total": float(arm["activity_positive_heartbeat_work_total"]),
                "activity_preserving": bool(
                    float(arm["activity_positive_heartbeat_work_total"])
                    >= float(declared["activity_retention_threshold"])
                ),
                "heartbeat_work_ratio_vs_default_ladder": float(
                    arm["activity_positive_heartbeat_work_total"]
                )
                / float(
                    ladder["rows"]["ladder-ratio-1.3"]["arms"][SURVIVAL_ARM_NAME][
                        "activity_positive_heartbeat_work_total"
                    ]
                ),
                "participation_measure_valid": bool(mechanism["participation_measure_valid"]),
                # the written directions against the slow modes: the declared
                # primary measure, minimised over the written items like the
                # metric family's own profile-level aggregate, plus the
                # participation share of the same subspace.
                "slow_mode_overlap_min_written_item": float(min(written_overlap)),
                "slow_participation_min_written_item": float(min(written_participation)),
                "slowest_modes_participating_pools": [
                    float(value) for value in mechanism["slowest_modes_participating_pools"]
                ],
                "gap_bands": {
                    "band_count": int(bands["band_count"]),
                    "band_mode_counts": list(bands["band_mode_counts"]),
                    "band_centers": list(bands["band_centers"]),
                    "band_ladder_ratio": float(bands["band_ladder_ratio"]),
                    "smallest_inter_band_gap": float(bands["smallest_inter_band_gap"]),
                    "widest_within_band_spread": float(bands["widest_within_band_spread"]),
                    "largest_band_mode_fraction": float(bands["largest_band_mode_fraction"]),
                    "bands_separated": bool(bands["bands_separated"]),
                    "continuum": bool(bands["continuum"]),
                },
                "pool_family_ladder": {
                    "family_count": int(family["family_count"]),
                    "family_mode_counts": list(family["family_mode_counts"]),
                    "lifetime_ladder_ratio": float(family["lifetime_ladder_ratio"]),
                    "centers_monotone_along_pools": bool(
                        family["centers_monotone_along_pools"]
                    ),
                    "ladder_ordered_beyond_spread": bool(
                        family["ladder_ordered_beyond_spread"]
                    ),
                    "families_separated": bool(family["families_separated"]),
                    "widest_within_family_spread": float(
                        family["widest_within_family_spread"]
                    ),
                },
                "sqrt_declared_ladder_ratio": sqrt_ratio,
                "band_ratio_vs_declared_ladder_ratio": {
                    "absolute_deviation": (
                        abs(bands["band_ladder_ratio"] - declared_ratio)
                        if declared_ratio
                        else None
                    ),
                    "relative_deviation": band_deviation,
                    "tracks_declared_ratio": bool(
                        band_deviation is not None
                        and band_deviation <= float(BAND_RATIO_TRACKING_TOLERANCE)
                    ),
                },
                # The lifetime-ladder claim needs a ladder before it can track
                # anything, so its gate is the tolerance-free monotonicity of the
                # family centres along the pool axis: a flat metric and a
                # scrambled ladder both fail the gate, the geometric ladders pass
                # it, and the deviation is then read off the same declared margin.
                "lifetime_ladder_vs_sqrt_ratio": {
                    "absolute_deviation": (
                        abs(family["lifetime_ladder_ratio"] - sqrt_ratio)
                        if sqrt_ratio
                        else None
                    ),
                    "relative_deviation": lifetime_deviation,
                    "centers_monotone_along_pools": bool(
                        family["centers_monotone_along_pools"]
                    ),
                    "tracks_sqrt_ratio": bool(
                        lifetime_deviation is not None
                        and lifetime_deviation <= float(BAND_RATIO_TRACKING_TOLERANCE)
                        and bool(family["centers_monotone_along_pools"])
                    ),
                },
                "family_separation": {
                    "smallest_adjacent_center_ratio_magnitude": float(
                        family["smallest_adjacent_center_ratio_magnitude"]
                    ),
                    "widest_within_family_spread": float(
                        family["widest_within_family_spread"]
                    ),
                    "families_separated": bool(family["families_separated"]),
                    "ladder_ordered_beyond_spread": bool(
                        family["ladder_ordered_beyond_spread"]
                    ),
                },
            }
        )
    entries = {row["profile"]: row for row in rows}
    geometric = [
        row
        for row in rows
        if row["declared_ladder_ratio"] not in (None, 1.0)
        and row["kind"] in ("ladder-geometric", "ladder-matched-random")
    ]
    ordered_geometric = [
        name for name in entries if entries[name]["pool_family_ladder"]["ladder_ordered_beyond_spread"]
    ]
    ranking = sorted(rows, key=lambda row: (-row["k4_min_per_item_recovery"], row["profile"]))
    separated = [row["profile"] for row in rows if row["gap_bands"]["bands_separated"]]
    strongest_gap = max(rows, key=lambda row: row["gap_bands"]["smallest_inter_band_gap"])
    band_tracking = [row for row in geometric if row["band_ratio_vs_declared_ladder_ratio"]["tracks_declared_ratio"]]
    sqrt_tracking = [row for row in geometric if row["lifetime_ladder_vs_sqrt_ratio"]["tracks_sqrt_ratio"]]
    matched_random = entries.get("ladder-matched-random-phi")
    phi_row = entries.get("ladder-ratio-phi")
    multiset_agreement = None
    if matched_random is not None and phi_row is not None:
        phi_centers = list(phi_row["gap_bands"]["band_centers"])
        control_centers = list(matched_random["gap_bands"]["band_centers"])
        centers_difference = (
            max(
                abs(float(left) - float(right)) / max(abs(float(left)), abs(float(right)))
                for left, right in zip(phi_centers, control_centers)
            )
            if len(phi_centers) == len(control_centers) and phi_centers
            else None
        )
        multiset_agreement = {
            "question": (
                "the phi ladder and its multiset-matched permutation carry the same "
                "seven inertances in a different pool order: which parts of the "
                "measured spectrum follow the value multiset and which follow the "
                "order?"
            ),
            "phi_band_ladder_ratio": float(phi_row["gap_bands"]["band_ladder_ratio"]),
            "matched_random_band_ladder_ratio": float(
                matched_random["gap_bands"]["band_ladder_ratio"]
            ),
            "band_span_relative_difference": abs(
                math.log(
                    matched_random["gap_bands"]["band_ladder_ratio"]
                    / phi_row["gap_bands"]["band_ladder_ratio"]
                )
            ),
            "band_count_agrees": (
                phi_row["gap_bands"]["band_count"]
                == matched_random["gap_bands"]["band_count"]
            ),
            "band_centers_max_relative_difference": centers_difference,
            "phi_lifetime_ladder_ratio": float(
                phi_row["pool_family_ladder"]["lifetime_ladder_ratio"]
            ),
            "matched_random_lifetime_ladder_ratio": float(
                matched_random["pool_family_ladder"]["lifetime_ladder_ratio"]
            ),
            "lifetime_ladder_relative_difference": abs(
                math.log(
                    matched_random["pool_family_ladder"]["lifetime_ladder_ratio"]
                    / phi_row["pool_family_ladder"]["lifetime_ladder_ratio"]
                )
            ),
            "phi_recovery": float(phi_row["k4_min_per_item_recovery"]),
            "matched_random_recovery": float(
                matched_random["k4_min_per_item_recovery"]
            ),
            # The coarse spectrum follows the value multiset; which family owns
            # which lifetime, and what the body retains, follow the order.
            "band_span_is_stable_under_permutation": bool(
                abs(
                    math.log(
                        matched_random["gap_bands"]["band_ladder_ratio"]
                        / phi_row["gap_bands"]["band_ladder_ratio"]
                    )
                )
                <= float(BAND_RATIO_TRACKING_TOLERANCE)
                and phi_row["gap_bands"]["band_count"]
                == matched_random["gap_bands"]["band_count"]
            ),
            "lifetime_ladder_is_order_determined": bool(
                abs(
                    math.log(
                        matched_random["pool_family_ladder"]["lifetime_ladder_ratio"]
                        / phi_row["pool_family_ladder"]["lifetime_ladder_ratio"]
                    )
                )
                > float(BAND_RATIO_TRACKING_TOLERANCE)
            ),
        }
    return {
        "measured": True,
        "claim_under_test": LADDER_CLAIM_STATEMENT,
        "profile_bound": int(LADDER_PROFILE_BOUND),
        "profile_count": len(rows),
        "row_order": list(ladder["row_order"]),
        "rows": rows,
        "ranking_by_k4_min_per_item_recovery": [row["profile"] for row in ranking],
        "default_ladder_profile": "ladder-ratio-1.3",
        "default_ladder_recovery": float(
            entries["ladder-ratio-1.3"]["k4_min_per_item_recovery"]
        ),
        "field_default_recovery": default_recovery,
        "reference_metric_recovery": reference_recovery,
        "reference_metric_profile": reference_name,
        "scaffold_reference_recovery": scaffold_recovery,
        "scaffold_reference_profile": scaffold_name,
        "best_retention_profile": ranking[0]["profile"],
        "best_retention_recovery": ranking[0]["k4_min_per_item_recovery"],
        "best_retention_is_geometric_ladder": bool(
            ranking[0]["kind"] == "ladder-geometric"
        ),
        "phi_beats_default_ladder": bool(
            entries["ladder-ratio-phi"]["k4_min_per_item_recovery"]
            > entries["ladder-ratio-1.3"]["k4_min_per_item_recovery"]
        ),
        "phi_minus_default_ladder": float(
            entries["ladder-ratio-phi"]["k4_min_per_item_recovery"]
            - entries["ladder-ratio-1.3"]["k4_min_per_item_recovery"]
        ),
        "matched_random_minus_phi": float(
            entries["ladder-matched-random-phi"]["k4_min_per_item_recovery"]
            - entries["ladder-ratio-phi"]["k4_min_per_item_recovery"]
        ),
        "band_ratio_tolerance": float(BAND_RATIO_TRACKING_TOLERANCE),
        "band_ratio_claim_holds_for": [row["profile"] for row in band_tracking],
        "band_ratio_claim_fails_for": [
            row["profile"]
            for row in geometric
            if not row["band_ratio_vs_declared_ladder_ratio"]["tracks_declared_ratio"]
        ],
        "band_ratio_claim_deviations": {
            row["profile"]: row["band_ratio_vs_declared_ladder_ratio"]["relative_deviation"]
            for row in geometric
        },
        "sqrt_ratio_claim_holds_for": [row["profile"] for row in sqrt_tracking],
        "sqrt_ratio_claim_fails_for": [
            row["profile"]
            for row in geometric
            if not row["lifetime_ladder_vs_sqrt_ratio"]["tracks_sqrt_ratio"]
        ],
        "sqrt_ratio_claim_deviations": {
            row["profile"]: row["lifetime_ladder_vs_sqrt_ratio"]["relative_deviation"]
            for row in geometric
        },
        "matched_random_fails_sqrt_ratio_claim": bool(
            matched_random is not None
            and not matched_random["lifetime_ladder_vs_sqrt_ratio"]["tracks_sqrt_ratio"]
        ),
        "ordered_ladder_profiles": ordered_geometric,
        "separated_band_profiles": separated,
        "no_profile_shows_separated_bands": not separated,
        "family_separated_profiles": [
            row["profile"] for row in rows if row["family_separation"]["families_separated"]
        ],
        "no_profile_shows_separated_families": not any(
            row["family_separation"]["families_separated"] for row in rows
        ),
        "band_structure_vs_ladder_order": multiset_agreement,
        "strongest_inter_band_gap_profile": strongest_gap["profile"],
        "strongest_inter_band_gap": strongest_gap["gap_bands"]["smallest_inter_band_gap"],
        "continuum_profiles": [
            row["profile"] for row in rows if row["gap_bands"]["continuum"]
        ],
    }


def uniform_local_family_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The declared local family around the flat metric, ranked at k4 and k8.

    The question is whether the flat profile's lead is an endpoint of the
    declared ladder family or an interior optimum of the declared local axis:
    if retention falls with every declared contrast, flat is the edge; if it
    peaks at a contrast inside the declared set, the optimum is interior.
    """

    local = body.get("uniform_local_family")
    if not local:
        return {"measured": False, "reason": "the receipt carries no local family"}
    anchor_name = local["anchor_profile"]
    anchor = local["rows"][anchor_name]
    rows: list[dict[str, Any]] = []
    for name in local["row_order"]:
        if name == anchor_name:
            continue
        record = local["rows"][name]
        declaration = record["declaration"]
        figures = {
            "k4": float(record["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]),
            "k8": float(record["arms"][CONTEXT_ARM_NAMES[1]]["recovery_fraction"]),
        }
        anchor_figures = {
            "k4": float(anchor["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]),
            "k8": float(anchor["arms"][CONTEXT_ARM_NAMES[1]]["recovery_fraction"]),
        }
        rows.append(
            {
                "profile": name,
                "kind": declaration["kind"],
                "contrast": float(declaration["contrast"]),
                "local_pools": list(declaration["local_pools"]),
                "normalization": declaration["normalization"],
                "recovery": figures,
                "delta_vs_flat": {
                    label: figures[label] - anchor_figures[label]
                    for label in ("k4", "k8")
                },
                "per_item_recovery_at_k4": dict(
                    record["arms"][SURVIVAL_ARM_NAME]["per_item_recovery_fraction"]
                ),
                "per_item_recovery_at_k8": dict(
                    record["arms"][CONTEXT_ARM_NAMES[1]]["per_item_recovery_fraction"]
                ),
                "heartbeat_work_total": float(
                    record["arms"][SURVIVAL_ARM_NAME]["activity_positive_heartbeat_work_total"]
                ),
                "activity_preserving": bool(
                    float(
                        record["arms"][SURVIVAL_ARM_NAME][
                            "activity_positive_heartbeat_work_total"
                        ]
                    )
                    >= float(body["declared"]["activity_retention_threshold"])
                ),
            }
        )
    anchor_figures = {
        "k4": float(anchor["arms"][SURVIVAL_ARM_NAME]["recovery_fraction"]),
        "k8": float(anchor["arms"][CONTEXT_ARM_NAMES[1]]["recovery_fraction"]),
    }
    single = [row for row in rows if row["kind"] == "uniform-local-single"]
    single_by_contrast = sorted(single, key=lambda row: row["contrast"])
    best = max(rows, key=lambda row: (row["recovery"]["k4"], row["profile"]))
    best_k8 = max(rows, key=lambda row: (row["recovery"]["k8"], row["profile"]))
    single_pool_magnitude_groups = single_pool_contrast_magnitude_groups(rows)
    by_magnitude = {
        magnitude: [
            next(row for row in rows if row["profile"] == name) for name in names
        ]
        for magnitude, names in (
            (float(key.split("=")[1]), value)
            for key, value in single_pool_magnitude_groups.items()
        )
    }
    ordered_magnitudes = sorted(by_magnitude)
    single_pool_magnitude_monotone = bool(
        len(ordered_magnitudes) >= 2
        and all(
            max(
                row["recovery"][label]
                for row in by_magnitude[ordered_magnitudes[index + 1]]
            )
            < min(
                row["recovery"][label] for row in by_magnitude[ordered_magnitudes[index]]
            )
            for label in ("k4", "k8")
            for index in range(len(ordered_magnitudes) - 1)
        )
    )

    def _ordinal_reading(label: str) -> tuple[bool, str | None]:
        """Is the single-pool response monotone in the declared contrast, and where is its peak?"""

        values = [row["recovery"][label] for row in single_by_contrast]
        monotone = bool(
            all(left >= right for left, right in zip(values, values[1:]))
            or all(left <= right for left, right in zip(values, values[1:]))
        )
        peak = max(single_by_contrast, key=lambda row: (row["recovery"][label], row["profile"]))
        interior = peak["profile"] if (peak is not single_by_contrast[0] and peak is not single_by_contrast[-1]) else None
        return monotone, interior

    ordinal_k4, interior_peak_k4 = _ordinal_reading("k4")
    ordinal_k8, interior_peak_k8 = _ordinal_reading("k8")
    single_pool_ordinal_monotone = bool(ordinal_k4 and ordinal_k8)
    return {
        "measured": True,
        "anchor_profile": anchor_name,
        "anchor_recovery": anchor_figures,
        "profile_bound": int(UNIFORM_LOCAL_PROFILE_BOUND),
        "profile_count": len(rows),
        "declared_local_pool": int(UNIFORM_LOCAL_POOL),
        "declared_local_pair": [int(pool) for pool in UNIFORM_LOCAL_PAIR],
        "declared_contrasts": [float(value) for value in UNIFORM_LOCAL_CONTRASTS],
        "declared_pair_contrasts": [float(value) for value in UNIFORM_LOCAL_PAIR_CONTRASTS],
        "rows": rows,
        "single_pool_rows_in_declared_contrast_order": [
            row["profile"] for row in single_by_contrast
        ],
        "single_pool_ranking_by_k4": [
            row["profile"]
            for row in sorted(single, key=lambda row: (-row["recovery"]["k4"], row["profile"]))
        ],
        "single_pool_ranking_by_k8": [
            row["profile"]
            for row in sorted(single, key=lambda row: (-row["recovery"]["k8"], row["profile"]))
        ],
        "single_pool_k4_by_contrast": {
            f"{row['contrast']:g}": row["recovery"]["k4"] for row in single_by_contrast
        },
        "single_pool_k8_by_contrast": {
            f"{row['contrast']:g}": row["recovery"]["k8"] for row in single_by_contrast
        },
        "best_local_profile_at_k4": best["profile"],
        "best_local_profile_at_k8": best_k8["profile"],
        "best_local_exceeds_flat_at_k4": bool(best["recovery"]["k4"] > anchor_figures["k4"]),
        "best_local_exceeds_flat_at_k8": bool(best_k8["recovery"]["k8"] > anchor_figures["k8"]),
        # Endpoint or interior: every declared contrast reduces k4 retention
        # (monotone fall away from flat) or some contrast improves it.
        "contrasts_improving_k4_over_flat": [
            row["profile"] for row in rows if row["recovery"]["k4"] > anchor_figures["k4"]
        ],
        "contrasts_improving_k8_over_flat": [
            row["profile"] for row in rows if row["recovery"]["k8"] > anchor_figures["k8"]
        ],
        "every_declared_contrast_is_below_flat": bool(
            not any(row["recovery"]["k4"] > anchor_figures["k4"] for row in rows)
            and not any(row["recovery"]["k8"] > anchor_figures["k8"] for row in rows)
        ),
        # Two separate readings of the same local axis, both reported: the
        # ordinal response along the declared contrast (is the best local row at
        # an endpoint contrast or inside the declared set?) and the response
        # grouped by the magnitude |ln contrast| (does a stronger contrast always
        # do worse than a weaker one?).
        "single_pool_ordinal_monotone_in_declared_contrast": single_pool_ordinal_monotone,
        "single_pool_interior_peak_profile_at_k4": interior_peak_k4,
        "single_pool_interior_peak_profile_at_k8": interior_peak_k8,
        "single_pool_interior_peak_at_k4": interior_peak_k4 is not None,
        "single_pool_interior_peak_at_k8": interior_peak_k8 is not None,
        "contrast_magnitude_groups": single_pool_magnitude_groups,
        "retention_falls_with_contrast_magnitude": bool(single_pool_magnitude_monotone),
    }


def single_pool_contrast_magnitude_groups(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The single-pool local rows grouped by the magnitude of the declared contrast."""

    buckets: dict[float, list[str]] = {}
    for row in rows:
        if row["kind"] != "uniform-local-single":
            continue
        buckets.setdefault(round(abs(math.log(float(row["contrast"]))), 12), []).append(
            row["profile"]
        )
    return {
        f"|ln contrast|={magnitude:g}": sorted(names)
        for magnitude, names in sorted(buckets.items())
    }


def summarize(body: Mapping[str, Any]) -> dict[str, Any]:
    """Every derived figure and declared verdict, from the measured body alone."""

    declared = body["declared"]
    entries = ranking_entries(body)
    headline = headline_block(body)
    activity_preserving = [row for row in entries if row["activity_running"]]
    residuals = {
        name: float(
            body["profiles"][name]["mechanism"]["spectral_reconstruction_residual_max"]
        )
        for name in declared["declared_row_order"]
    }
    relation = overlap_survival_relation(body)
    scale = scale_check_block(body)
    return {
        "ranking": entries,
        "ranking_by_k4_min_per_item_recovery": [row["profile"] for row in entries],
        "ranking_margin": float(declared["ranking_margin"]),
        "ranking_activity_preserving": {
            "activity_retention_threshold": float(
                declared["activity_retention_threshold"]
            ),
            "profiles": [row["profile"] for row in activity_preserving],
            "best_activity_preserving_profile": (
                activity_preserving[0]["profile"] if activity_preserving else None
            ),
            "best_activity_preserving_recovery": (
                activity_preserving[0]["k4_min_per_item_recovery"]
                if activity_preserving
                else None
            ),
            "best_activity_preserving_heartbeat_work": (
                activity_preserving[0]["heartbeat_work_total"]
                if activity_preserving
                else None
            ),
        },
        "spectral_decomposition": {
            "definitions": SPECTRAL_VALIDITY_DEFINITION,
            "definitions_short": (
                "the participation share is the direction's coefficient in the "
                "frozen eigenbasis, normalised over the spectrum"
            ),
            "residual_tolerance": float(declared["spectral_residual_tolerance"]),
            "rotation_tolerance": float(declared["spectral_rotation_tolerance"]),
            "separation_tolerance": float(declared["spectral_separation_tolerance"]),
            "profiles": {
                name: {
                    "spectral_reconstruction_residual_max": float(
                        body["profiles"][name]["mechanism"][
                            "spectral_reconstruction_residual_max"
                        ]
                    ),
                    "participation_basis_rotation_max_change": float(
                        body["profiles"][name]["mechanism"][
                            "participation_basis_rotation_max_change"
                        ]
                    ),
                    "minimum_eigenvalue_separation": float(
                        body["profiles"][name]["mechanism"][
                            "minimum_eigenvalue_separation"
                        ]
                    ),
                    "numerically_repeated_spectrum": bool(
                        body["profiles"][name]["mechanism"][
                            "numerically_repeated_spectrum"
                        ]
                    ),
                    "participation_measure_valid": bool(
                        body["profiles"][name]["mechanism"]["participation_measure_valid"]
                    ),
                }
                for name in declared["declared_row_order"]
            },
            "valid_participation_profiles": [
                name
                for name in declared["declared_row_order"]
                if body["profiles"][name]["mechanism"]["participation_measure_valid"]
            ],
            "invalid_participation_profiles": [
                name
                for name in declared["declared_row_order"]
                if not body["profiles"][name]["mechanism"]["participation_measure_valid"]
            ],
            "max_residual": max(residuals.values(), default=0.0),
            "max_rotation_change": max(
                float(
                    body["profiles"][name]["mechanism"][
                        "participation_basis_rotation_max_change"
                    ]
                )
                for name in declared["declared_row_order"]
            ),
            "all_participation_measures_valid": bool(
                all(
                    body["profiles"][name]["mechanism"]["participation_measure_valid"]
                    for name in declared["declared_row_order"]
                )
            ),
        },
        "headline": headline,
        "hook_fidelity": hook_fidelity_block(body),
        "overlap_survival_relation": relation,
        "scale_check": scale,
        "ladder_family": ladder_family_block(body),
        "uniform_local_family": uniform_local_family_block(body),
        "flat_inertia_confirmation": {
            key: value
            for key, value in body["flat_inertia_confirmation"].items()
            if not isinstance(value, np.ndarray)
        },
        "band_rule_reconciliation": {
            key: value
            for key, value in body["band_rule_reconciliation"].items()
        },
        "mechanism_comparison": mechanism_comparison_block(body),
        "cross_talk_and_time": cross_talk_and_time_block(body),
        "cross_rail": {
            key: value for key, value in body["cross_rail"].items() if key != "rows"
        },
        "activity_confound": ACTIVITY_CONFOUND_STATEMENT,
    }


# --------------------------------------------------------------------------
# receipt
# --------------------------------------------------------------------------
def _plain(value: Any) -> Any:
    """Plain JSON types for arrays, numpy scalars and mappings."""

    if isinstance(value, np.ndarray):
        return [_plain(item) for item in value.tolist()]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def build_receipt(
    config: durability.DurabilityConfig | None = None
) -> dict[str, Any]:
    """The measured body, the derived summary, the declared boundary and the digest."""

    body = _plain(measured_body(config))
    full = _plain({**body, "summary": summarize(body), "boundary": BOUNDARY})
    return {**full, "content_digest": survival.digest_body(full)}


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------
def summary_lines(summary: Mapping[str, Any], declared: Mapping[str, Any]) -> list[str]:
    """A compact human-readable reading of the measured summary."""

    lines: list[str] = []
    lines.append(
        f"declared rows: {declared['profile_count']} (bound {declared['profile_bound']}), "
        f"arm {declared['survival_arm_name']}, read frame {declared['read_frame_path']!r}"
    )
    lines.append(
        f"graded contrasts: {declared['graded_contrasts']}; randomized profiles: "
        f"{declared['random_profile_count']} seeds from {declared['random_seeds'][0]}"
    )
    lines.append(
        f"ranking by k=4 minimum per-item recovery (margin {summary['ranking_margin']}):"
    )
    for row in summary["ranking"]:
        lines.append(
            f"  {row['rank']:2d}. {row['profile']:28s} k4={row['k4_min_per_item_recovery']:.6f} "
            f"single={row['single_item_recovery']:.6f} "
            f"delta_default={row['delta_vs_default']:+.6f} "
            f"heartbeat={row['heartbeat_work_total']:.3e} "
            f"energy_ratio={row['total_packet_energy_ratio']:.4f} "
            f"metric=[{row['metric_diagonal_min']:.3e}, {row['metric_diagonal_max']:.3e}]"
        )
    headline = summary["headline"]
    lines.append(
        f"headline ({headline['arm']}): best={headline['best_profile']} "
        f"{headline['best_recovery']:.6f} vs default {headline['default_recovery']:.6f} "
        f"(cited {CITED_RECOVERY['helix7']}) and reference scaffold "
        f"{headline['reference_scaffold_recovery']:.6f} "
        f"(cited {CITED_RECOVERY['nested-core-shell']}); "
        f"best-minus-default={headline['best_minus_default']:+.6f} "
        f"(margin {headline['margin']} -> {headline['exceeds_default_by_margin']}, "
        f"headline margin {headline['headline_survival_margin']} -> "
        f"{headline['exceeds_default_by_headline_margin']})"
    )
    lines.append(f"best construction rule: {headline['best_construction_rule']}")
    lines.append(
        f"cited figures reproduced: {headline['cited_reproduction_holds']}"
    )
    activity = summary["ranking_activity_preserving"]
    lines.append(
        "best activity-preserving profile (heartbeat work >= "
        f"{activity['activity_retention_threshold']:g}): "
        f"{activity['best_activity_preserving_profile']} "
        f"{activity['best_activity_preserving_recovery']}"
    )
    fidelity = summary["hook_fidelity"]
    lines.append(
        f"hook fidelity: canonical metric through the hook reproduces the default "
        f"generator={fidelity['generator_identical_to_default']} "
        f"recovery difference={fidelity['k4_recovery_difference_vs_default']:.3e}; "
        f"graded setting {fidelity['graded_setting_coinciding_with_reference_metric']} "
        f"matches the reference vector="
        f"{fidelity['graded_setting_matches_reference_vector']}"
    )
    relation = summary["overlap_survival_relation"]
    lines.append(
        "overlap vs survival (profile level, minimum over the written items):"
    )
    for measure, figures in relation["measures"].items():
        mark = "primary" if figures["primary"] else "       "
        lines.append(
            f"  {mark} {measure:46s} pearson="
            f"{_round_or_none(figures['profile_level_pearson'])} spearman="
            f"{_round_or_none(figures['profile_level_spearman'])} pooled_item_pearson="
            f"{_round_or_none(figures['pooled_per_item_pearson'])}"
        )
    lines.append(
        f"  primary relation tracked (spearman >= {relation['primary_relation_margin']}): "
        f"{relation['primary_relation_tracked']}"
    )
    scale = summary["scale_check"]
    lines.append("k=2/k=4/k=8 scaling of the ranking leaders and the default:")
    for row in scale["rows"]:
        lines.append(
            f"  {row['profile']:28s} "
            + ", ".join(
                f"{label}={value:.6f}" for label, value in row["recoveries"].items()
            )
            + f" advantage_default={{{', '.join(f'{label}: {value:+.4f}' for label, value in row['advantage_over_default'].items())}}}"
            + f" holds={row['holds_at_every_declared_k']}"
        )
    rail = summary["cross_rail"]
    lines.append(
        f"cross-rail {rail['rail']!r}: default metric {rail['default_metric_recovery']:.6f} "
        f"(cited {rail['survival_harness_cited_default_metric_recovery']}, difference "
        f"{rail['cited_reproduction_abs_difference']:.3e}) vs top metric "
        f"{rail['top_metric_recovery']:.6f} -> ranking holds="
        f"{rail['ranking_holds']}, exceeds default by margin="
        f"{rail['top_exceeds_default_by_margin']} (margin {rail['margin']})"
    )
    ladder = summary["ladder_family"]
    if not ladder.get("measured"):
        lines.append(f"declared ladder family: not measured ({ladder.get('reason')})")
        return lines
    lines.append(
        f"declared ladder family ({ladder['profile_count']} rows, bound "
        f"{ladder['profile_bound']}, normalization "
        f"{ladder['rows'][0]['normalization']!r}); default ladder "
        f"{ladder['default_ladder_profile']} k4={ladder['default_ladder_recovery']:.6f}, "
        f"field default {ladder['field_default_recovery']:.6f}, nested metric reference "
        f"{ladder['reference_metric_recovery']:.6f} "
        f"({ladder['reference_metric_profile']}), nested scaffold reference "
        f"{ladder['scaffold_reference_recovery']:.6f} "
        f"({ladder['scaffold_reference_profile']}):"
    )
    for row in ladder["rows"]:
        bands = row["gap_bands"]
        family = row["pool_family_ladder"]
        lines.append(
            f"  {row['profile']:30s} R={_ratio_label(row['declared_ladder_ratio'])} "
            f"k4={row['k4_min_per_item_recovery']:.6f} "
            f"delta_default={row['delta_vs_default_ladder']:+.6f} "
            f"slow_overlap={row['slow_mode_overlap_min_written_item']:.4f} "
            f"bands={bands['band_count']} band_ratio={bands['band_ladder_ratio']:.4f} "
            f"(declared R {_ratio_label(row['declared_ladder_ratio'])}, dev "
            f"{_ratio_label(row['band_ratio_vs_declared_ladder_ratio']['relative_deviation'])}) "
            f"largest_band={bands['largest_band_mode_fraction']:.3f} "
            f"separated={bands['bands_separated']} "
            f"lifetime_ratio={family['lifetime_ladder_ratio']:.4f} "
            f"(sqrt R {_ratio_label(row['sqrt_declared_ladder_ratio'])}, dev "
            f"{_ratio_label(row['lifetime_ladder_vs_sqrt_ratio']['relative_deviation'])}, "
            f"ordered={family['ladder_ordered_beyond_spread']})"
        )
    separated_text = (
        ", ".join(ladder["separated_band_profiles"])
        if ladder["separated_band_profiles"]
        else "none (every spectrum is a continuum with jumps)"
    )
    lines.append(
        f"  band claim (bands spaced by the declared ladder ratio, tolerance "
        f"{ladder['band_ratio_tolerance']:g}): holds for "
        f"{ladder['band_ratio_claim_holds_for']}, fails for "
        f"{ladder['band_ratio_claim_fails_for']}; separated-band profiles: "
        f"{separated_text}"
    )
    lines.append(
        f"  lifetime-ladder claim (pool-family ladder is monotone along the pool "
        f"axis and tracks sqrt(R), same tolerance): holds for "
        f"{ladder['sqrt_ratio_claim_holds_for']}, "
        f"fails for {ladder['sqrt_ratio_claim_fails_for']}; matched-random control "
        f"fails the claim={ladder['matched_random_fails_sqrt_ratio_claim']}; "
        f"continuum profiles={ladder['continuum_profiles']}"
    )
    lines.append(
        f"  ladder retention: best={ladder['best_retention_profile']} "
        f"{ladder['best_retention_recovery']:.6f} "
        f"(geometric ladder={ladder['best_retention_is_geometric_ladder']}); "
        f"phi beats the field's 1.3 ladder={ladder['phi_beats_default_ladder']} "
        f"(phi minus 1.3 = {ladder['phi_minus_default_ladder']:+.6f}); "
        f"matched-random minus phi = {ladder['matched_random_minus_phi']:+.6f}; "
        f"strongest inter-band gap {ladder['strongest_inter_band_gap_profile']} "
        f"{ladder['strongest_inter_band_gap']:.4f}"
    )
    order = ladder["band_structure_vs_ladder_order"]
    if order:
        lines.append(
            f"  spectrum vs ladder order (phi vs its multiset-matched permutation): "
            f"gap-band span {order['phi_band_ladder_ratio']:.6f} vs "
            f"{order['matched_random_band_ladder_ratio']:.6f} (relative difference "
            f"{order['band_span_relative_difference']:.2e}, band counts agree="
            f"{order['band_count_agrees']}, centres max relative difference "
            f"{_ratio_label(order['band_centers_max_relative_difference'])}) while the "
            f"pool-family lifetime ladders differ ({order['phi_lifetime_ladder_ratio']:.4f} "
            f"vs {order['matched_random_lifetime_ladder_ratio']:.4f}) and so does the "
            f"retention ({order['phi_recovery']:.6f} vs {order['matched_random_recovery']:.6f}) "
            f"-> the coarse spectrum is multiset-determined="
            f"{order['band_span_is_stable_under_permutation']}, the lifetime ladder and "
            f"retention are order-determined="
            f"{order['lifetime_ladder_is_order_determined']}"
        )
    lines.append(
        f"  separation reading (reported separately from the ordering claims): "
        f"profiles whose families separate beyond their own spread="
        f"{ladder['family_separated_profiles'] or 'none'}; "
        f"no profile shows separated families={ladder['no_profile_shows_separated_families']}"
    )
    local = summary["uniform_local_family"]
    if local.get("measured"):
        lines.append(
            f"declared local family around the flat metric ({local['profile_count']} "
            f"rows, bound {local['profile_bound']}; single declared pool "
            f"{local['declared_local_pool']} at contrasts {local['declared_contrasts']}, "
            f"declared pair {local['declared_local_pair']} at "
            f"{local['declared_pair_contrasts']}), anchor {local['anchor_profile']} "
            f"k4={local['anchor_recovery']['k4']:.6f} k8={local['anchor_recovery']['k8']:.6f}:"
        )
        for row in sorted(local["rows"], key=lambda item: -item["recovery"]["k4"]):
            lines.append(
                f"  {row['profile']:34s} contrast={row['contrast']:>6g} "
                f"pools={row['local_pools']} "
                f"k4={row['recovery']['k4']:.6f} (delta_flat "
                f"{row['delta_vs_flat']['k4']:+.6f}) k8={row['recovery']['k8']:.6f} "
                f"(delta_flat {row['delta_vs_flat']['k8']:+.6f}) "
                f"heartbeat={row['heartbeat_work_total']:.3e} "
                f"activity={row['activity_preserving']}"
            )
        lines.append(
            f"  local optimum: best k4 {local['best_local_profile_at_k4']} "
            f"(exceeds flat={local['best_local_exceeds_flat_at_k4']}), best k8 "
            f"{local['best_local_profile_at_k8']} "
            f"(exceeds flat={local['best_local_exceeds_flat_at_k8']}); every declared "
            f"contrast below flat={local['every_declared_contrast_is_below_flat']}; "
            f"single-pool response monotone along the declared contrast="
            f"{local['single_pool_ordinal_monotone_in_declared_contrast']} "
            f"(interior peak at k4="
            f"{local['single_pool_interior_peak_profile_at_k4'] or 'none'}, k8="
            f"{local['single_pool_interior_peak_profile_at_k8'] or 'none'}); retention "
            f"falls with the contrast magnitude |ln contrast|="
            f"{local['retention_falls_with_contrast_magnitude']} over "
            f"{local['contrast_magnitude_groups']}; contrasts improving k4="
            f"{local['contrasts_improving_k4_over_flat'] or 'none'}, k8="
            f"{local['contrasts_improving_k8_over_flat'] or 'none'}"
        )
    confirm = summary["flat_inertia_confirmation"]
    lines.append("flat-inertia confirmation (independent instruments, per declared k):")
    for row in confirm["rows"]:
        arms = ", ".join(
            f"{label}={row['arms'][label]['recovery_fraction']:.6f}"
            for label in confirm["arm_labels"]
        )
        horizon = row["horizon"]
        lines.append(
            f"  {row['profile']:30s} {arms} | horizon per-item final alignment "
            f"[{horizon['final_alignment_min']:.4f}, "
            f"{max(item['final_alignment'] for item in horizon['per_item']):.4f}] "
            f"mean={horizon['final_alignment_mean']:.4f} "
            f"mean_lifetime={horizon['mean_lifetime_ticks']:.1f} ticks "
            f"censored={len(horizon['censored_items'])} | placement transfer "
            f"max={row['transfer_max']:.6f} mean={row['transfer_mean']:.6f} "
            f"rank_agreement_vs_default="
            f"{_round_or_none(row['transfer_rank_agreement_vs_default'])}"
        )
    lines.append(
        f"  flat exceeds the default on every declared k="
        f"{confirm['flat_exceeds_default_on_every_declared_k']}, on every horizon item="
        f"{confirm['flat_exceeds_default_on_every_horizon_item']} (items not exceeding: "
        f"{confirm['flat_horizon_items_not_exceeding_default'] or 'none'}), on transfer "
        f"mean={confirm['flat_exceeds_default_on_transfer_mean']}; flat horizon final "
        f"alignment min {confirm['flat_horizon_final_alignment_min']:.4f} vs default "
        f"{confirm['default_horizon_final_alignment_min']:.4f} (mean "
        f"{confirm['flat_horizon_final_alignment_mean']:.4f} vs "
        f"{confirm['default_horizon_final_alignment_mean']:.4f})"
    )
    reconcile = summary["band_rule_reconciliation"]
    lines.append(
        f"band-rule reconciliation on {reconcile['profile_count']} shared spectra: "
        f"that rule banded for {reconcile['banded_under_this_runner_rule'] or 'none'}, "
        f"ladder-harness rule banded for "
        f"{reconcile['banded_under_ladder_harness_rule'] or 'none'}, disagreements="
        f"{reconcile['rules_disagree_on_banded_for'] or 'none'}"
    )
    for row in reconcile["profiles"]:
        lines.append(
            f"  {row['profile']:30s} range={row['decay_rate_range']:.3e} "
            f"that rule: bands={row['this_runner_rule']['band_count']} "
            f"continuum={row['this_runner_rule']['continuum']} | harness rule: "
            f"gaps={row['ladder_harness_rule']['qualifying_gap_count']} "
            f"bands={row['ladder_harness_rule']['band_count']} "
            f"continuum={row['ladder_harness_rule']['continuum']}"
        )
    lines.append(f"  {reconcile['resolution']}")
    mechanism = summary["mechanism_comparison"]
    lines.append(
        "mechanism comparison over the eight declared widest-arm item directions "
        "(slow-mode participation, slow-mode overlap, decay-rate span):"
    )
    for row in mechanism["rows"]:
        lines.append(
            f"  {row['profile']:30s} slow_participation min={row['slow_participation_min']:.4f} "
            f"mean={row['slow_participation_mean']:.4f} | slow_overlap "
            f"min={row['slow_mode_overlap_min']:.4f} mean={row['slow_mode_overlap_mean']:.4f} | "
            f"decay span={row['decay_rate_span']:.3e} "
            f"[{row['decay_rate_min']:.3e}, {row['decay_rate_max']:.3e}]"
        )
    if mechanism.get("comparison"):
        comp = mechanism["comparison"]
        lines.append(
            f"  flat minus default: slow participation mean "
            f"{comp['flat_minus_default_slow_participation_mean']:+.4f}, slow overlap mean "
            f"{comp['flat_minus_default_slow_overlap_mean']:+.4f}, decay span "
            f"{comp['flat_minus_default_decay_span']:+.3e} -> flat concentrates written "
            f"directions into slow modes="
            f"{comp['flat_concentrates_written_directions_into_slow_modes']}, flat span "
            f"narrower than default={comp['flat_span_is_narrower_than_default']}"
        )
    cross = summary["cross_talk_and_time"]
    lines.append(
        f"cross-talk / distinguishability ({cross['instrument']}, margin "
        f"{cross['margin']}, {len(cross['item_names'])} declared directions):"
    )
    for row in cross["rows"]:
        lines.append(
            f"  {row['profile']:30s} mean own={row['mean_own_retention']:.4f} "
            f"min own={min(row['own_retention'].values()):.4f} | mean largest "
            f"unwritten share={row['mean_max_unwritten_share']:.4f} "
            f"max={row['max_unwritten_share']:.4f} | own/unwritten="
            f"{_ratio_label(row['own_over_unwritten_ratio'])} | distinguished "
            f"{row['distinguished_count']}/{len(cross['item_names'])} "
            f"meets margin={row['meets_margin']}"
        )
        for label in cross["declared_arm_labels"]:
            arm = row["arms"][label]
            lines.append(
                f"    {label} written n={len(arm['written_items'])} "
                f"mean={_round_or_none(arm['written_mean'])} "
                f"min={_round_or_none(arm['written_min'])} | never written n="
                f"{len(arm['unwritten_items'])} max={_round_or_none(arm['unwritten_max'])} "
                f"mean={_round_or_none(arm['unwritten_mean'])} | never-written reaching "
                f"a written share={arm['unwritten_reaching_written_min'] or 'none'}"
            )
    lines.append(
        f"  flat item content kept={cross['flat_keeps_item_content']} "
        f"(distinguished {cross['flat_distinguished_count']}/"
        f"{len(cross['item_names'])}, worst own-minus-unwritten margin "
        f"{cross['flat_min_own_minus_max_unwritten']:+.4f}); default worst margin "
        f"{cross['default_min_own_minus_max_unwritten']:+.4f}; flat cross-talk is the "
        f"smallest of the measured profiles={cross['flat_cross_talk_is_the_smallest']}"
    )
    lines.append(f"  {cross['verdict']}")
    equal = cross["equal_time_comparison"]
    lines.append(
        "equal dimensionless time (slowest-mode e-fold times, reference "
        f"{equal['flat_slowest_decay_ratio_vs_default']:.4f}x slowest on the flat "
        f"profile):"
    )
    for row in cross["equal_time_rows"]:
        lines.append(
            f"  {row['profile']:30s} slowest decay={row['slowest_decay_rate']:.3e} "
            f"(per generator time, dt={row['time_step']:.2f} per tick) "
            f"ratio_vs_default={row['slowest_decay_ratio_vs_reference']:.4f} e-folds@"
            f"{row['declared_horizon_ticks']}ticks={row['efolds_at_declared_horizon']:.4f} | "
            f"equal-time ticks={row['equal_time_horizon_ticks']} "
            f"(x{row['tick_scale_vs_declared_horizon']:.2f}, cap applied="
            f"{row['tick_cap_applied']}) | retention at declared horizon "
            f"min={row['declared_horizon_final_alignment_min']:.4f} "
            f"mean={row['declared_horizon_final_alignment_mean']:.4f} | at equal time "
            f"min={row['equal_time_final_alignment_min']:.4f} "
            f"mean={row['equal_time_final_alignment_mean']:.4f} | decay span="
            f"{row['decay_magnitude_range'][1] - row['decay_magnitude_range'][0]:.3e} "
            f"frequency span=[{row['frequency_magnitude_range'][0]:.3e}, "
            f"{row['frequency_magnitude_range'][1]:.3e}]"
        )
    lines.append(
        f"  flat minus default at declared horizon="
        f"{equal['flat_minus_default_at_declared_horizon']:+.4f} (leads by margin="
        f"{equal['flat_leads_default_at_declared_horizon_by_margin']}); at equal "
        f"dimensionless time={equal['flat_minus_default_at_equal_time']:+.4f} endpoint / "
        f"{equal['flat_minus_default_at_equal_time_time_mean']:+.4f} window-mean (leads by "
        f"margin endpoint={equal['flat_leads_default_at_equal_time_by_margin']}, "
        f"window-mean={equal['flat_leads_default_at_equal_time_time_mean_by_margin']}); flat "
        f"decay span narrowest={equal['flat_decay_span_is_narrowest']}"
    )
    scope = cross["scope"]
    lines.append(
        f"cross-talk scope (cited figure, pointer not recomputation): read frame = "
        f"{scope['read_frame']}; declared directions are the slow modes on the "
        f"default={scope['declared_directions_are_the_slow_modes_on_the_default']} "
        f"(flat minus default slow overlap mean "
        f"{scope['flat_minus_default_slow_overlap_mean']:+.6f}, slow participation mean "
        f"{scope['flat_minus_default_slow_participation_mean']:+.6f}); aimed write on the "
        f"same default profile retains "
        f"{scope['targeted_write']['measured_retention']:.4f} "
        f"({scope['targeted_write']['item_path']}/{scope['targeted_write']['item_component']} "
        f"w{scope['targeted_write']['item_width']}, slow weight "
        f"{scope['targeted_write']['slow_weight']:.2f}, {scope['targeted_write']['kind']}) "
        f"vs {scope['declared_widest_item_retention_on_the_default']:.4f} for "
        f"{scope['declared_widest_item']} unaimed; source pointer "
        f"{scope['targeted_write']['source_pointer']} @ digest "
        f"{scope['targeted_write']['receipt_content_digest'][:12]}"
    )
    for conclusion in scope["conclusions"]:
        lines.append(f"  {conclusion}")
    return lines


def _ratio_label(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.4f}"


def _round_or_none(value: Any) -> str:
    return "none" if value is None else f"{float(value):+.3f}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args(argv)
    started = perf_counter()
    receipt = build_receipt()
    elapsed = perf_counter() - started
    for line in summary_lines(receipt["summary"], receipt["declared"]):
        print(line)
    print(json.dumps({"boundary": receipt["boundary"]}, indent=1, sort_keys=True))
    print(f"content_digest: {receipt['content_digest']}")
    print(f"elapsed_seconds: {elapsed:.2f}")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps({**receipt, "elapsed_seconds": elapsed}, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    print(f"receipt: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
