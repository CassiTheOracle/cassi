"""Is the store's scale surface a composition surface or a magnitude surface?

DECLARED BEFORE THE FIRST RUN -- the question, the audit of the spent receipt,
the surfaces, the measured floors, the readings with a structural control on each
non-zero companion, the declared budget sweep, the physical firing control, the
branch rule, the blocks and the cost cap.

THE DELIVERABLE IS THE SWEEP, NOT A VERDICT AT ONE DRIVE.  The spent receipt's own
two-term rule, worked out on paper, does not measure a reading's size: a reading
that scales with the drive has ``|v - v_half| = |v| / 2``, so the rule's half-budget
term becomes five times the reading and the reading can never clear it, while a
reading that has stopped moving between neighbouring budgets has that term at or
below the numerical term and is judged on the numerical term alone.  The rule is
therefore a statement about the reading's *shape*, and asking for scaling in the
budget asks for exactly the shape the rule rejects.  So every measured row sweeps
the declared ladder (``SWEEP_MULTIPLES``: 0.25, 0.5, 1, 2, 4 times the level's own
write budget), publishes the whole sweep with both floor terms separately, finds
the plateau, compares it with the numerical term ``1e-9 * |own|``, and states which
shape the reading is: a plateau above the numerical term (composition evidence the
declared rule admits), a reading still climbing with the drive (a budget artifact,
a shape the declared rule rejects by construction), under the numerical term
(silent), or not measured.  **No single budget point in this receipt carries a
presence verdict.**

THE QUESTION.  ``run_store_addressing_tree`` found the store's addressing flat:
containment, aggregation, sibling and descent all sit at their floor.  It also
found three readings that are *not* zero and that no structural control covers:

  * the companion at the scale surfaces -- the reading stands about three times
    its **own positive control** (``fraction_of_the_positive_control`` ~2.998 at
    every level) and is nonetheless published ``at_the_floor`` by the spent
    receipt's declared two-term floor, whose terms are
    ``10 * |r(B) - r(B/2)|`` and ``1e-9 * |r_own|`` (0.05596 at four ports,
    fraction 0.01372 of its own deposit response).  The binding term there is the
    10x **half-budget difference**, so the reading is *strong but budget
    dependent* -- a different failure from 'too weak to see', and the thing to
    measure is how it scales with the deposit budget;
  * the R5 descendants reading -- 3 of 6 rows the spent receipt reads as present,
    at ~0.993-0.997;
  * the port fallback -- 2 of 2 rows the spent receipt reads as present, at
    ~2.09-2.37.

This runner asks the one question those three readings leave open, at the only
place in the whole measurement where a parent/child relation produced a response:
**is the response of a node's scale surface to deposits at its children a
composition -- a function of *which* children were written, at the field's own
size weights -- or is it magnitude alone?**  A composition surface answers "how
much, and of what"; a magnitude surface answers "how much, anywhere".

THE AUDIT OF THE SPENT RECEIPT, COMPUTED FROM THE PINNED ARTIFACT.  Before any
arm of this runner runs, ``spent_receipt_audit`` re-reads the pinned
``_diag/store-addressing-tree/`` receipt at its declared digests and publishes,
per level and per companion arm, whether the arm exists and where that is
visible in the spent receipt.  Two rules it states and applies:

  * **existence is proven by a published value, never by a key.**
    ``arms_finite`` is ``bool(arm is None or all(isfinite(...)))``, so an absent
    arm reads ``True`` there; a key in that mapping only means the runner
    *referenced* the name.  An arm is counted as existing at a level only when a
    value derived from it is non-``None`` in the published reading (its row of
    ``SPENT_ARM_EVIDENCE`` names that field).
  * **a zero is vacuous when the reading it is computed from is zero.**
    ``assignment_specific`` is ``present and |treatment - control| > floor``; when
    ``present`` is false the zero says nothing about the structural question and
    is published here with ``vacuous: true`` rather than read as a magnitude
    verdict.  ``counts_only`` is likewise false-vacuous where the flat null was
    never passed to the reading.

The audit's findings are carried in the receipt (``spent_receipt_audit``) and
summarised in the report; they are the reason this runner exists.

THE SURFACES.  Every figure is taken through the owner's own packet surface:

    write   owner.write_packet_impulse(operation_id, path=, component=,
            flow_signal=, work_budget=)                 -- one owner transition
    read    owner.read_packet_deposit(path=, component=, flow_signal=)
            -> recovered_deposit                         -- a readout

The read publishes ``readout_kind: "temporal-prediction"`` and
``evidence_added: False``: every figure here is a construction over the field's
own readouts and **none** is an observation.  A node's *scale* surface is
field-exposed and, below the root, **not** a declared item of the store's family
(``capacity.declared_family``), so the readings taken at the scale surfaces are
published with their own predicates and do **not** carry a branch verdict on the
store's declared addressing; the branch they carry is the one asked here, about
the scale surface itself, and it is declared in ``BRANCH_RULE`` before the run.

THE MEASURED FLOORS.  The spent receipt's floor was a two-term declared floor,
``max(FLOOR_FACTOR * |r(B) - r(B/2)|, EPS_FACTOR * |own|)``, whose first term
scaled the half-budget difference by 10.  This runner instead *measures* the floor
at every surface and publishes every term beside every reading.  The verdict floor
is one rule, declared before the first run:

    floor(surface, row) = max(floor_matched_budget, floor_half_budget)
    floor_matched_budget = |r(the treatment's own sources written at zero budget)
                            - r(same target, no deposit at all)|
    floor_half_budget    = |r(B) - r(B/2)| at the same sources and target

and published beside it, never binding on a verdict:

    term_no_deposit, term_zero_work        the two raw readout differences
    floor_declared_numerical               EPS_FACTOR * |the row's own control|
    spent_receipt_declared_floor            the spent receipt's own floor at the
                                           same reading and level, with the ratio
    narrowest_with_the_declared_numerical_term  the floor a reader gets by adding
                                           the numerical term to the measured one

so the gap between the floor the spent receipt used and the floor that is actually
there is visible rather than inherited.

THE READINGS, EACH WITH A STRUCTURAL CONTROL ON ITS NON-ZERO COMPANION.

  R-A  scale_containment_from_the_childrens_declared_detail_surfaces
       (the controls named for R-A and R-B are the *strict* ones: the
       shuffled-parent control is accepted only where the field's own helper picks
       a parent at the treated parent's own depth that is neither an ancestor nor a
       descendant -- at the root it picks a descendant, which is refused here and
       recorded as unavailable -- and the placement null is a non-sibling pair,
       which can never be one parent's two children, so it is never the same
       measurement as the shuffled arm counted twice)
       the spent receipt's own companion construction: deposits at the children's
       *declared detail* surfaces, read at the parent's *scale* surface.
       Controls: own (the parent's scale self-response), **shuffled parent** (the
       same two writes at another parent's children, read at the treated parent's
       scale), **flat null** (the same count and budget at two depth-matched
       nodes that are neither the children nor siblings of each other nor in the
       treated parent's subtree), duplicate, shared, half budget, no deposit.
  R-B  scale_containment_from_the_childrens_own_scale_surfaces
       the same reading in the geometry the field's own packet analysis composes
       from: deposits at the children's *scale* surfaces, read at the parent's.
       Controls: the same set, plus the shuffled *geometry* arm (the same
       construction at another parent, read at *that* parent's scale) and the
       delivered-budget variant of the whole reading, so the spent receipt's
       aggregation companion is re-taken with the controls it lacked.
  R-C  the_field_own_size_weighted_composition_beside_the_probe
       the physical firing control: the parent's scale response to the two child
       deposits, beside the field's own size-weighted composition of the
       children's measured own scale responses at the field's own weights, taken
       from the field's own transform (``cassi_resonant_field._packet_analyze``:
       ``scale = sqrt(left_size/size) * left_scale + sqrt(right_size/size) *
       right_scale``).  The weights are produced by *calling* that function on a
       unit probe and are published beside their closed form and their
       difference; the per-child propagation ratio ``alone/x`` is published beside
       the field's weight for the same child, since a weighted composition
       predicts that ratio and an unweighted accumulation predicts 1.  Any gap
       between the field's internal composition and its exposed surface is named
       here, not smoothed over.
  R-D  magnitude_or_composition_under_a_constant_total_budget
       the discriminator, and the test that is available at every row: the same
       total work (2B) placed as two deposits at the two children's scale
       surfaces at the write budget each, and as one deposit at one child's scale
       surface carrying the whole doubled budget, so a difference between them is
       a difference in *how many* children were written and in *which*, never in
       how much was written.  Beside those, the same total budget at the extra
       placement null's surfaces (a non-sibling pair outside the treated parent's
       subtree with the children's own port counts) where such a pair exists at
       the level, and one deposit at one child at the write budget.  The count
       matters if the two equal-total-work placements differ above the measured
       floor; the surface answers how much and not which if they agree.
  R-E  descendants_against_a_non_ancestor_source
       the R5 path, controlled: the same statistic with the deposits placed two
       levels below, beside **a non-ancestor source** -- the same count and budget
       at another node's descendants, read at the treated parent's scale surface.
  R-F  leaf_port_fallback_against_a_different_port
       the port path, controlled: a single-port node's children deposited at their
       port/scale surfaces, read at the parent's scale surface, beside **a
       different port's fallback** (the same count and budget at two other ports
       of the same parent, read at the same target) and beside the same child
       ports read at another parent's scale surface.

THE SWEEP, AND WHY THE RULE IS WORKED OUT ON PAPER FIRST.  The spent receipt's
companion stands about three times its own positive control
(``fraction_of_the_positive_control`` ~2.998 at every level) and is nonetheless
published ``at_the_floor`` by the spent receipt's declared two-term rule
``|v| > max(FLOOR_FACTOR * |v - v_half|, EPS_FACTOR * |own|)`` -- whose binding
term there is the ``10 * |v - v_half|`` half-budget difference, not the magnitude.
Worked out on paper, that rule is not a statement about a reading's size but about
its *shape*: if a reading scales with the drive then ``|v - v_half| = |v| / 2``, so
the half-budget term is ``FLOOR_FACTOR / 2`` times the reading and the reading can
never clear it, while a reading that has stopped moving between neighbouring
budgets has a half-budget term at or below the numerical term and is judged on the
numerical term alone.  So the informative measurement is a **budget sweep**, not a
second threshold: every measured row sweeps the declared ladder
(``SWEEP_MULTIPLES``: ``0.25, 0.5, 1, 2, 4`` times the level's own write budget),
publishes **every** point -- the treatment, its own positive control, the two floor
terms of the declared rule **separately** rather than folded into a ``max``, the
binding term at that point, and whether the rule admits the reading there -- finds
where the reading plateaus, compares the plateau against the numerical term
``EPS_FACTOR * |own|``, and states which shape the whole sweep is:

  * ``plateau_above_the_numerical_term`` -- the reading stops moving with the drive
    above the read noise: composition evidence, and the declared rule **admits**
    this shape, because at the plateau the half-budget term has fallen to the
    numerical term;
  * ``still_climbing_with_the_drive`` -- the reading rises at every declared point
    by more than the numerical term: a **budget artifact**, and the declared rule
    **rejects this shape by construction** (the arithmetic above).  The rule is
    mis-shaped for a reading that still scales; that is a different statement from
    the reading being absent, and the receipt says the first;
  * ``under_the_numerical_term`` -- silent at every declared point, and bounded by
    that term;
  * ``not_measured`` -- an arm of the sweep is missing, and no branch reads the row.

No single budget point carries a verdict anywhere in this receipt: every figure the
branch reads is a property of the whole sweep or a difference from a structural
control on the same held page.

THE BRANCH RULE, DECLARED BEFORE THE FIRST RUN (``BRANCH_RULE``).  Three branches
with equal standing plus ``inconclusive``; each level is classified by the
predicates below over its own measured rows, and the receipt publishes every
predicate's outcome and every named suppressing term, so a reader can re-derive
the branch from the row numbers without re-running anything.  The third branch is a
real outcome: a bound, the floor achieved, and what would have to be built are
published rather than a verdict being forced.  A missing structural control can
never produce the magnitude branch: that branch requires its evidence to be
measured.

THE COST.  ``MEASURED_TRIPLE_CAP`` complete triples per level (head and tail of
the level's own declared order, the tree runner's own selection) and
``PORT_FALLBACK_CAP`` leaf-child triples; 31 arms per complete triple, 7 per port
triple.  Each block has its own wall-clock budget and the receipt publishes
per-level runtimes, the arms measured, and the levels cut if the budget ran out.
Nothing in this runner re-runs ``run_store_addressing_tree``: its declarations
are imported at pinned digests and its finished receipt is read, not regenerated.

WHAT THIS RUNNER DOES NOT CLAIM.  It measures one surface's response to deposits
through the field's own exposed API on a held page.  It is not an observation, not
an account of the field's internal state, and not evidence about any other path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import cassi_field_atlas as atlas
import cassi_resonant_field as resonant
import run_fractal_durability_exploration as durability
import run_memory_store_scale as scale
import run_store_addressing_capacity as capacity
import run_store_addressing_rank as rank
import run_store_addressing_tree as tree

SCHEMA = "cassifi.scale-composition-surface.v1"
BLOCK_SCHEMA = "cassifi.scale-composition-surface.block.v1"
RECEIPT_PATH = Path("_diag/scale-composition-surface/exploration.json")
BLOCK_PATHS: dict[str, Path] = {
    "declared-profile": Path(
        "_diag/scale-composition-surface/block-declared-profile.json"
    ),
    "higher-resolution": Path(
        "_diag/scale-composition-surface/block-higher-resolution.json"
    ),
}
BLOCK_SPECS: dict[str, tuple[int, tuple[int, ...]]] = {
    "declared-profile": (4, (8, 28)),
    "higher-resolution": (8, (32,)),
}
BLOCK_BUDGET_SECONDS = 2700.0
MEASURED_TRIPLE_CAP = 3
PORT_FALLBACK_CAP = 2

# The evidence floor for a structural verdict: at least this many rows must carry
# both a measured structural control and a matched placement null, or the level
# reports the structural question as unmeasured rather than reading a missing
# control as evidence for either surface.
MIN_MATCHED_ROWS = 2

# The declared budget sweep.  The rule every reading in this runner is judged by,
# before this runner's own measured floor, is the spent receipt's two-term rule
# ``|v| > max(FLOOR_FACTOR * |v - v_half|, EPS_FACTOR * |own|)``.  Worked out on
# paper, that rule is a statement about the *shape* of the reading's dependence on
# the drive, not about its size: a reading that scales with the drive has
# ``|v - v_half| = |v| / 2``, so the half-budget term becomes ``FLOOR_FACTOR / 2``
# times the reading and the reading can never clear it, while a reading that has
# stopped moving between neighbouring budgets has a half-budget term at or below
# the numerical term.  The informative measurement is therefore where the reading
# plateaus, so the ladder below is swept at every measured row and the whole sweep
# is published rather than one point.  The multiples are declared here, before the
# first run, and are multiples of the level's own declared write budget.
SWEEP_MULTIPLES: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0, 4.0)

# A sweep point's change to the next coarser point is read against the numerical
# term at that point; a plateau is the first multiple from which every coarser
# point's change stays at or below that term.
PLATEAU_RULE = (
    "the plateau is the first declared multiple from which the reading's change to "
    "the next coarser declared multiple is at or below the numerical term "
    "EPS_FACTOR * |the point's own positive control|, and which stays so at every "
    "coarser multiple; the sweep publishes every point, the plateau's own value, its "
    "change to the next coarser point, and the numerical term it is compared with, "
    "so a reader can recompute the classification from the table"
)

# The pinned declarations this runner imports and reads.  A run refuses to start
# if any of them has moved: the tree runner's own source digest, and the
# received content digests of the three artifacts the audit reads.  The digests
# are literals, declared before the first run, and re-checked at run time.
TREE_RUNNER_PATH = Path("run_store_addressing_tree.py")
TREE_RECEIPT_DIR = Path("_diag/store-addressing-tree")
PINNED_TREE_RUNNER_SHA256 = (
    "10ee9adfe6a019a8744a007d4961913bab3e2404fda07803494ff9bd1577ef6c"
)
PINNED_TREE_BLOCK_DIGESTS: dict[str, tuple[Path, str]] = {
    "declared-profile": (
        TREE_RECEIPT_DIR / "block-declared-profile.json",
        "ae759b80c518337001c46b81414621d98acd024cdeda6fa8e48036531ebf22e6",
    ),
    "higher-resolution": (
        TREE_RECEIPT_DIR / "block-higher-resolution.json",
        "aeca536be8c140167d6523a74bd245276f2fa82186506c781104f348a086789e",
    ),
}
PINNED_TREE_RECEIPT_PATH = TREE_RECEIPT_DIR / "exploration.json"
PINNED_TREE_RECEIPT_DIGEST = (
    "5cd5fbb2d3048b5693d7ee9437323bc4657b227cb6af4462d29a28f1dfc35883"
)

# The declared branch rule.  Declared before the first run; the receipt publishes
# this mapping verbatim beside each level's predicate outcomes.
BRANCHES = (
    "the_scale_surface_composes_from_its_children",
    "the_scale_surface_is_a_magnitude_surface",
    "not_measurable_in_this_path",
    "inconclusive",
)
BRANCH_RULE: dict[str, Any] = {
    "the_scale_surface_composes_from_its_children": (
        "the positive controls fire on every measured row (each arm judged against its "
        "own measured floor, not the treatment's); at least two rows carry a scale-path "
        "treatment with a declared sweep shape and a measured structural control; at a "
        "majority of those rows the treatment separates from the shuffled-parent control "
        "by more than the published terms (the numerical term, the measured floor, and "
        "the comparison floor, each named); and at a majority of rows the count test "
        "separates too -- two children written at the write budget each (2B) are not the "
        "same response as one child written at twice it (2B), so the surface is not "
        "answering how much alone.  The row's declared budget sweep is carried beside the "
        "verdict, not folded into it: a row whose sweep plateaus above the numerical term "
        "is composition evidence the declared two-term rule admits, while a row whose "
        "sweep keeps climbing with the drive is a budget artifact that the declared rule "
        "rejects by construction, and the branch then rests on the structural separation "
        "and on the count test rather than on the reading's magnitude.  The verdict is "
        "scoped to the scale surfaces the level measured: rows where a treatment is "
        "absent, rows whose declared sweep is missing, and rows where the field's own "
        "shuffled-parent helper picks an ancestor or a descendant and the control is "
        "therefore refused, leave the denominator instead of voting against the surface, "
        "and the descendant, port-fallback and aggregation companions are reported beside "
        "the branch rather than read as evidence for it.  The physical firing control's "
        "own result is a caveat carried beside the verdict: whether the per-child "
        "propagation ratio is the field's own size weight, and if it is not, the gap is "
        "named with the ratios, the weights and the closest prediction"
    ),
    "the_scale_surface_is_a_magnitude_surface": (
        "at least one row carries a declared sweep shape and the magnitude evidence is "
        "actually measured, in one of three forms: (i) the count test at a constant "
        "total budget is available on every row and the two equal-total-work placements "
        "agree within the measured floor; (ii) the extra placement null exists and is "
        "matched on a majority of rows and the children's placement and that null's "
        "placement agree within the floor; or (iii) the structural controls exist and are "
        "read on every row and none of them separates from the treatment above the "
        "published terms.  A missing control is never read as evidence for this branch: "
        "a form whose comparison is unmeasured is reported as unmeasured and does not "
        "support the branch"
    ),
    "not_measurable_in_this_path": (
        "the scale-surface reading sits at or below the numerical term epsilon * |its own "
        "control| at every declared budget of every row of the level, so the sweep shape "
        "is under_the_numerical_term at every row: the reading is silent and is bounded "
        "by that term.  A row whose sweep is missing is reported as not measured and "
        "never as a silent one.  The bound is stated with both floor terms of the spent "
        "receipt's rule published separately at every sweep point, and with what would "
        "have to be built (a surface whose reading plateaus above its own read noise at "
        "some declared drive, or a non-readout observation channel)"
    ),
    "inconclusive": (
        "a non-finite or missing arm; a positive control at its own measured floor; or a "
        "level where no scale-path treatment carries a declared sweep beside a measured "
        "structural control, or where fewer than two such rows exist, or where the count "
        "test is unavailable -- the structural question is then untested at this level "
        "and a missing control is never read as evidence for either surface.  Every "
        "predicate's outcome, every sweep shape, every named binding term and the "
        "field-composition gap are published with the level, so this branch is a "
        "statement about the measurement, never about the surface"
    ),
}

# The fields of the spent receipt that prove an arm existed.  ``arms_finite``
# cannot: it is true for an arm that was passed as None.  A value of None in the
# published reading field is proof the arm was *not* built; a number is proof that
# it was built and executed.
SPENT_ARM_EVIDENCE: dict[str, dict[str, Any]] = {
    "companion_containment_scale": {
        "level_rows_key": "measured",
        "row_path": ("companion_scale_surfaces", "containment_scale"),
        "level_aggregate_prefix": "companion_scale",
        "own": ("scale_parent_own", "own_response"),
        "treatment": ("scale_children_home", "treatment_response"),
        "structural_control": ("scale_children_shuffled", "shuffled_response"),
        "flat_null": (None, "flat_response"),
        "half_budget": ("scale_children_home_half", "half_budget_response"),
        "published_arm_names": (
            "scale_parent_own",
            "scale_children_home",
            "scale_children_home_half",
            "scale_children_shuffled",
            "scale_child_own",
        ),
    },
    "companion_aggregation_scale": {
        "level_rows_key": "measured",
        "row_path": ("companion_scale_surfaces", "aggregation_scale"),
        "level_aggregate_prefix": "aggregation_scale",
        "own": ("deposit_scale_parent", "own_deposit_response"),
        "treatment": ("deposit_scale_children", "treatment_response"),
        "structural_control": (None, None),
        "flat_null": (None, None),
        "half_budget": (None, None),
        "published_arm_names": (
            "deposit_scale_children",
            "deposit_scale_parent",
            "scale_child_own",
        ),
    },
    "descendants": {
        "level_rows_key": "measured",
        "row_path": ("descendants",),
        "level_aggregate_prefix": "descendants",
        "own": ("parent_own", "own_response"),
        "treatment": ("descendants_home", "treatment_response"),
        "structural_control": (None, "shuffled_response"),
        "flat_null": (None, "flat_response"),
        "half_budget": ("descendants_half", "half_budget_response"),
        "published_arm_names": ("parent_own", "descendants_home", "descendants_half"),
    },
    "port_fallback": {
        "level_rows_key": "port_fallback_measured",
        "row_path": ("scale_containment",),
        "level_aggregate_prefix": "port_fallback",
        "own": ("scale_parent_own", "own_response"),
        "treatment": ("scale_children_home", "treatment_response"),
        "structural_control": (None, None),
        "flat_null": (None, None),
        "half_budget": (None, None),
        "published_arm_names": (
            "scale_parent_own",
            "scale_children_home",
            "scale_child_own",
        ),
    },
}

DECLARED_FLOOR_RULE = (
    "floor(surface, row) = max(floor_matched_budget, floor_half_budget), where "
    "floor_matched_budget = |r(the treatment's own sources written at zero budget) - "
    "r(same target, no deposit at all)| -- both measured at the same surface and the "
    "same declared budget, one fresh owner each, on the held page -- and "
    "floor_half_budget = |r(B) - r(B/2)| at the same sources and target.  "
    "floor_declared_numerical = EPS_FACTOR * |the row's own positive control| and the "
    "spent receipt's own two-term floor are published beside them for comparison and "
    "are never binding on a verdict."
)

DECLARED_READINGS: dict[str, dict[str, Any]] = {
    "R-A": {
        "name": "scale_containment_from_the_childrens_declared_detail_surfaces",
        "taken_at": (
            "the parent's scale surface, to deposits at the children's declared "
            "detail surfaces"
        ),
        "carries_the_branch": True,
        "structural_control": (
            "the same two writes at another parent's children's declared detail "
            "surfaces, read at the treated parent's scale surface -- accepted only "
            "where that parent is at the treated parent's own depth and is neither an "
            "ancestor nor a descendant of it, because the field's own helper falls back "
            "to any depth and at the root picks a descendant; a refused choice is "
            "recorded as an unavailable control, never as a zero"
        ),
        "flat_null": (
            "the same count and total work at a non-sibling pair outside the treated "
            "parent's subtree whose port counts match the children's as a multiset, read "
            "at the treated parent's scale surface.  Two nodes that are not siblings "
            "cannot be the two children of any parent, so this control is never the "
            "shuffled-parent arm's placement counted twice; where the level's tree holds "
            "no such pair the null is declared unavailable and the placement question is "
            "reported as unmeasured at that row"
        ),
    },
    "R-B": {
        "name": "scale_containment_from_the_childrens_own_scale_surfaces",
        "taken_at": (
            "the parent's scale surface, to deposits at the children's own scale "
            "surfaces -- the geometry the field's own packet analysis composes from"
        ),
        "carries_the_branch": True,
        "structural_control": (
            "the same two writes at another parent's children's scale surfaces, read at "
            "the treated parent's scale surface -- accepted only where that parent is at "
            "the treated parent's own depth and is neither an ancestor nor a descendant "
            "of it, because the field's own helper falls back to any depth and at the "
            "root picks a descendant; a refused choice is recorded as an unavailable "
            "control, never as a zero"
        ),
        "flat_null": (
            "the same count and total work at a non-sibling pair outside the treated "
            "parent's subtree whose port counts match the children's as a multiset, read "
            "at the treated parent's scale surface.  Two nodes that are not siblings "
            "cannot be the two children of any parent, so this control is never the "
            "shuffled-parent arm's placement counted twice; where the level's tree holds "
            "no such pair the null is declared unavailable and the placement question is "
            "reported as unmeasured at that row"
        ),
    },
    "R-C": {
        "name": "the_field_own_size_weighted_composition_beside_the_probe",
        "taken_at": (
            "the parent's scale surface beside the field's own size-weighted "
            "composition of the children's own measured scale responses"
        ),
        "carries_the_branch": True,
        "structural_control": "the field's own weights taken from its own transform, "
        "and the unweighted accumulation prediction, beside the probe",
        "flat_null": "not applicable: this reading compares the probe with two "
        "predictions rather than with a null placement",
    },
    "R-D": {
        "name": "magnitude_or_composition_under_a_constant_total_budget",
        "taken_at": "the parent's scale surface, to placements of the same total budget",
        "carries_the_branch": True,
        "structural_control": "the same total budget at one child's surface, at one "
        "child's surface with the whole budget, and at the flat null's surfaces",
        "flat_null": "the flat null placement is one of the four placements compared",
    },
    "R-E": {
        "name": "descendants_against_a_non_ancestor_source",
        "taken_at": (
            "the parent's scale surface, to deposits two levels below the parent at "
            "the descendants' own scale surfaces"
        ),
        "carries_the_branch": False,
        "structural_control": "the same count and budget at another node's "
        "descendants -- a non-ancestor source -- read at the treated parent's scale",
        "flat_null": "the non-ancestor source is the flat control for this path",
    },
    "R-F": {
        "name": "leaf_port_fallback_against_a_different_port",
        "taken_at": (
            "the parent's scale surface, to deposits at the port/scale surfaces of "
            "its single-port children"
        ),
        "carries_the_branch": False,
        "structural_control": "the same count and budget at two other ports of the "
        "same parent, read at the same target; and the same child ports read at "
        "another parent's scale surface",
        "flat_null": "the different-port placement is the flat control for this path",
    },
}
SPENT_READING_LEXICON = {
    "scope": (
        "the spent tree receipt's own single-budget vocabulary, quoted here so this "
        "runner's audit can name the fields it read from that pinned artifact.  These "
        "names are not this receipt's reading schema: no reading emitted by this runner "
        "carries a present/at-the-floor verdict at one budget point"
    ),
    "present": (
        "the spent receipt's treatment reading exceeds that row's measured floor"
    ),
    "assignment_specific": (
        "the spent receipt's reading is present AND its difference from the structural "
        "control exceeds the floor; computed only where the structural control exists"
    ),
    "assignment_specific_is_vacuous": (
        "true in the spent receipt where the row is not present: the zero then says "
        "nothing about the structural question and is not evidence for a magnitude "
        "surface"
    ),
}

READING_LEXICON = {
    "the_shape": (
        "the shape the row's declared budget sweep implies, and this receipt's reading "
        "verdict in place of any single-budget present/absent: "
        "plateau_above_the_numerical_term (the reading stops moving with the drive above "
        "the read noise -- composition evidence, and the declared two-term rule admits "
        "this shape because its half-budget term has fallen to the numerical term), "
        "still_climbing_with_the_drive (a budget artifact, and the declared rule rejects "
        "this shape by construction because a reading that moves with the drive has "
        "|v - v_half| comparable to |v|), under_the_numerical_term (silent, bounded by "
        "epsilon * |the row's own control|), not_measured (an arm of the sweep is "
        "missing), or no_sweep_declared_for_this_path (the declared ladder is taken at "
        "the scale surfaces; other paths state the absence of their own sweep)"
    ),
    "the_structural_separation": (
        "the treatment minus its structural control on the same held page, with the "
        "published terms it is compared with (the numerical term epsilon * |own|, the "
        "measured floor, and the comparison floor) each named, so a separation is read "
        "as a difference against named terms rather than as a verdict at one budget"
    ),
    "the_two_floor_terms": (
        "both terms of the spent receipt's declared rule at a sweep point, published "
        "separately rather than folded into a max: "
        "floor_factor * |v - v_half| and epsilon * |own|, with the term that bound at "
        "that point named beside them"
    ),
}


# --------------------------------------------------------------------------
# pinned declarations
# --------------------------------------------------------------------------
def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_pins() -> dict[str, Any]:
    """Refuse to run against moved declarations; publish what was checked."""

    checks: list[dict[str, Any]] = []
    source = TREE_RUNNER_PATH
    if not source.exists():
        raise SystemExit(f"the pinned tree runner is missing: {source}")
    found = sha256_of(source)
    checks.append(
        {
            "artifact": str(source),
            "declared": PINNED_TREE_RUNNER_SHA256,
            "found": found,
            "matches": bool(found == PINNED_TREE_RUNNER_SHA256),
        }
    )
    for name, (path, digest) in PINNED_TREE_BLOCK_DIGESTS.items():
        if not path.exists():
            raise SystemExit(f"the pinned tree block {name!r} is missing: {path}")
        body = json.loads(path.read_text(encoding="utf-8"))
        found_block = scale.receipt_digest(
            {key: value for key, value in body.items() if key != "content_digest"}
        )
        checks.append(
            {
                "artifact": str(path),
                "declared": digest,
                "found": found_block,
                "matches": bool(found_block == digest),
            }
        )
    if not PINNED_TREE_RECEIPT_PATH.exists():
        raise SystemExit(
            f"the pinned tree receipt is missing: {PINNED_TREE_RECEIPT_PATH}"
        )
    receipt_body = json.loads(PINNED_TREE_RECEIPT_PATH.read_text(encoding="utf-8"))
    found_receipt = scale.receipt_digest(receipt_body)
    checks.append(
        {
            "artifact": str(PINNED_TREE_RECEIPT_PATH),
            "declared": PINNED_TREE_RECEIPT_DIGEST,
            "found": found_receipt,
            "matches": bool(found_receipt == PINNED_TREE_RECEIPT_DIGEST),
        }
    )
    moved = [row["artifact"] for row in checks if not row["matches"]]
    if moved:
        raise SystemExit(
            "the declarations this runner imports have moved; refusing to run "
            "against an unpinned tree: " + ", ".join(moved)
        )
    return {
        "checked": checks,
        "every_declaration_matches_its_pin": True,
        "receipt_file_sha256": sha256_of(PINNED_TREE_RECEIPT_PATH),
        "declared": (
            "the tree runner's source digest and the received content digests of the "
            "three artifacts the audit reads are literals declared before this "
            "runner's first run and re-checked at every run; a moved declaration is "
            "a refusal, not a warning"
        ),
    }


def load_pinned_tree_receipt() -> dict[str, Any]:
    return json.loads(PINNED_TREE_RECEIPT_PATH.read_text(encoding="utf-8"))


def load_pinned_tree_blocks() -> dict[str, dict[str, Any]]:
    """The pinned block artifacts, which carry the raw per-level rows.

    The merged receipt publishes ``port_fallback_measured`` as a summary integer;
    the raw row list lives in the block artifact, so the audit reads the blocks for
    rows and refuses to coerce a summary integer into one.
    """

    return {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, (path, _digest) in PINNED_TREE_BLOCK_DIGESTS.items()
    }


# --------------------------------------------------------------------------
# the audit of the spent receipt
# --------------------------------------------------------------------------
def _row_field(row: Mapping[str, Any], path: Sequence[str]) -> Any:
    value: Any = row
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    return value


def _numbers(value: Any) -> list[float]:
    if isinstance(value, Mapping):
        return [item for item in value.values() for item in _numbers(item)]
    if isinstance(value, (list, tuple)):
        return [item for item in value for item in _numbers(item)]
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    return []


def spent_receipt_audit(
    blocks: Mapping[str, Mapping[str, Any]],
    *,
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Per level, per companion: which arms exist, which zeros are vacuous.

    Existence is proven by a published non-``None`` value derived from an arm, the
    row of ``SPENT_ARM_EVIDENCE`` naming that field.  ``arms_finite`` is published
    beside it as what it is: a mapping whose ``True`` does not distinguish an
    absent arm from an executed one.  The rows are read from the pinned *block*
    artifacts; where an artifact publishes a summary integer in the row slot the
    row list is reported unavailable rather than read as an empty list.
    """

    per_level: dict[str, Any] = {}
    for block_name, block_record in blocks.items():
        for level_name, level in block_record.get("levels", {}).items():
            key = f"{block_name}:N={level_name}"
            rows_unavailable: list[str] = []
            summaries: dict[str, int] = {}
            row_sets: dict[str, list[Any]] = {}
            for companion, spec in SPENT_ARM_EVIDENCE.items():
                slot = level.get(str(spec["level_rows_key"]))
                if isinstance(slot, bool) or slot is None:
                    row_sets[companion] = []
                    summaries[companion] = 0
                elif isinstance(slot, list):
                    row_sets[companion] = list(slot)
                    summaries[companion] = len(slot)
                else:
                    row_sets[companion] = []
                    summaries[companion] = int(slot)
                    rows_unavailable.append(companion)
            arms_finite: set[str] = set()
            for rows_here in row_sets.values():
                for row in rows_here:
                    arms_finite |= set((row.get("arms_finite") or {}).keys())
            companions: dict[str, Any] = {}
            for companion, spec in SPENT_ARM_EVIDENCE.items():
                source_rows = row_sets[companion]
                considered = [
                    row
                    for row in source_rows
                    if _row_field(row, tuple(spec["row_path"])) is not None
                ]
                readouts: dict[str, Any] = {}
                for role in ("own", "treatment", "structural_control", "flat_null"):
                    arm_name, field_name = spec[role]
                    if arm_name is None or field_name is None:
                        readouts[role] = {
                            "arm": None,
                            "arm_was_referenced_in_arms_finite": False,
                            "value_field": None,
                            "values": [],
                            "exists": False,
                            "declared": (
                                "the spent runner never passed an arm for this role to "
                                "this reading, so no value derived from one exists: "
                                "the structural question is untested at this surface"
                            ),
                        }
                        continue
                    values = [
                        _row_field(row, (*tuple(spec["row_path"]), field_name))
                        for row in considered
                    ]
                    numeric = [
                        float(value)
                        for value in values
                        if value is not None
                        and not isinstance(value, bool)
                        and isinstance(value, (int, float))
                    ]
                    readouts[role] = {
                        "arm": arm_name,
                        "arm_was_referenced_in_arms_finite": bool(
                            arm_name in arms_finite
                        ),
                        "values_published": len(values),
                        "value_field": field_name,
                        "values": numeric,
                        "values_absent": int(
                            sum(1 for value in values if value is None)
                        ),
                        "exists": bool(numeric),
                    }
                treatment = readouts["treatment"]["values"]
                control = readouts["structural_control"]["values"]
                records = [
                    _row_field(row, tuple(spec["row_path"])) for row in considered
                ]
                presence = [
                    bool(record.get("present"))
                    for record in records
                    if isinstance(record, Mapping) and "present" in record
                ]
                specificity = [
                    bool(record.get("assignment_specific"))
                    for record in records
                    if isinstance(record, Mapping) and "assignment_specific" in record
                ]
                floors = [
                    float(record.get("floor"))
                    for record in records
                    if isinstance(record, Mapping)
                    and isinstance(record.get("floor"), (int, float))
                    and not isinstance(record.get("floor"), bool)
                ]
                hidden = [
                    bool(record.get("a_nonzero_response_the_declared_floor_hides"))
                    for record in records
                    if isinstance(record, Mapping)
                    and "a_nonzero_response_the_declared_floor_hides" in record
                ]
                differences = [
                    abs(left - right) for left, right in zip(treatment, control)
                ]
                any_present = any(presence)
                any_specific = any(specificity)
                floors_here = list(floors)
                finite_differences = [
                    float(record.get("finite_difference_floor"))
                    for record in records
                    if isinstance(record, Mapping)
                    and isinstance(record.get("finite_difference_floor"), (int, float))
                ]
                own_responses = [
                    float(record.get("own_response"))
                    for record in records
                    if isinstance(record, Mapping)
                    and isinstance(record.get("own_response"), (int, float))
                ]
                ten_times = [
                    10.0 * value for value in finite_differences
                ]
                epsilon_terms = [
                    1e-9 * abs(value) for value in own_responses
                ]
                companions[companion] = {
                    "the_spent_rules_binding_term": {
                        "declared": (
                            "the spent receipt's floor is max(10 * |r(B) - r(B/2)|, "
                            "1e-9 * |r_own|); which of the two terms did the "
                            "suppressing is computed from the spent receipt's own "
                            "published floor beside its own published half-budget arm, "
                            "so the answer is a measurement of that artifact and not a "
                            "reconstruction"
                        ),
                        "ten_times_the_half_budget_difference": ten_times,
                        "the_numerical_term": epsilon_terms,
                        "binding_term": (
                            "the_10x_half_budget_difference_term"
                            if ten_times
                            and epsilon_terms
                            and max(ten_times) >= max(epsilon_terms)
                            else (
                                "the_numerical_term" if ten_times else None
                            )
                        ),
                        "the_treatments_implied_half_budget_response": [
                            float(record["treatment_response"])
                            - float(record["finite_difference_floor"])
                            for record in records
                            if isinstance(record, Mapping)
                            and isinstance(record.get("treatment_response"), (int, float))
                            and isinstance(
                                record.get("finite_difference_floor"), (int, float)
                            )
                        ],
                        "the_controls_half_budget_response_is_published": bool(
                            any(
                                isinstance(record, Mapping)
                                and record.get("own_half_budget_response") is not None
                                for record in records
                            )
                        ),
                        "declared_gap": (
                            "the spent receipt measured the treatment's half-budget arm "
                            "but published no half-budget arm for its own control, so "
                            "the scaling law itself cannot be settled from the spent "
                            "artifact: this runner measures both and publishes the "
                            "ratio of the two fractions"
                        ),
                    },
                    "declared": (
                        "what the spent receipt published for this companion at this "
                        "level: which arms a value proves, which zeros are vacuous, and "
                        "which structural arms are absent"
                    ),
                    "rows_in_the_artifact": int(summaries[companion]),
                    "rows_considered": int(len(considered)),
                    "rows_unavailable_in_this_artifact": bool(
                        companion in rows_unavailable
                    ),
                    "readouts": readouts,
                    "rows_the_spent_receipt_reads_as_present": int(
                        sum(1 for value in presence if value)
                    ),
                    "rows_the_spent_receipt_reads_as_assignment_specific": int(
                        sum(1 for value in specificity if value)
                    ),
                    "rows_with_a_nonzero_response_the_declared_floor_hid": int(
                        sum(1 for value in hidden if value)
                    ),
                    "declared_floor_values": floors,
                    "treatment_minus_control": differences,
                    "the_structural_question_was_tested": bool(
                        readouts["structural_control"]["exists"]
                        or readouts["flat_null"]["exists"]
                    ),
                    "the_zero_is_vacuous": bool(not any_present and not any_specific),
                    "read_as": (
                        "vacuous: nothing is present, so assignment-specificity is not "
                        "available at this surface and its zero is not evidence for a "
                        "magnitude surface"
                        if not any_present
                        else (
                            "assignment specific at "
                            f"{sum(1 for value in specificity if value)} of "
                            f"{len(specificity)} rows"
                            if any_specific
                            else "present but not assignment specific"
                        )
                    ),
                    "absent_structural_arms": [
                        role
                        for role in ("structural_control", "flat_null")
                        if not readouts[role]["exists"]
                    ],
                }
            # the two companion fractions: same surface, two budgets, two
            # denominators -- published together so the reader sees whether they
            # are one measurement or two.
            containment_fraction = level.get("readings", {}).get(
                "companion_scale_surfaces", {}
            )
            per_level[key] = {
                "block": block_name,
                "n": int(level_name),
                "ports_per_pool": int(block_record.get("resolution", 0)),
                "complete_triples": int(
                    level.get("readings", {}).get("complete_triples", 0)
                ),
                "port_triples": int(summaries.get("port_fallback", 0)),
                "arms_referenced_in_the_spent_arms_finite": sorted(arms_finite),
                "companions": companions,
                "the_two_companion_fractions": {
                    "containment_scale_greatest_fraction": containment_fraction.get(
                        "containment_scale_greatest_fraction"
                    ),
                    "aggregation_scale_greatest_fraction": containment_fraction.get(
                        "aggregation_scale_greatest_fraction"
                    ),
                    "the_same_number_to_the_published_precision": bool(
                        containment_fraction.get("containment_scale_greatest_fraction")
                        is not None
                        and containment_fraction.get(
                            "aggregation_scale_greatest_fraction"
                        )
                        is not None
                        and abs(
                            float(
                                containment_fraction[
                                    "containment_scale_greatest_fraction"
                                ]
                            )
                            - float(
                                containment_fraction[
                                    "aggregation_scale_greatest_fraction"
                                ]
                            )
                        )
                        <= 1e-9
                    ),
                    "declared": (
                        "the two companions divide the same treatment by two "
                        "denominators; where the two published greatest fractions "
                        "coincide the second carries no independent evidence about "
                        "this surface"
                    ),
                },
                "declared_floor_hidden_readings": level.get("readings", {}).get(
                    "readings_where_the_declared_floor_hides_a_nonzero_response"
                ),
            }
    vacuous = {
        key: [
            companion
            for companion, record in entry["companions"].items()
            if record["the_zero_is_vacuous"]
        ]
        for key, entry in per_level.items()
    }
    untested = {
        key: [
            companion
            for companion, record in entry["companions"].items()
            if not record["the_structural_question_was_tested"]
        ]
        for key, entry in per_level.items()
    }
    return {
        "source": {
            "merged_receipt": str(PINNED_TREE_RECEIPT_PATH),
            "receipt_digest": PINNED_TREE_RECEIPT_DIGEST,
            "blocks_read_for_rows": {
                name: str(path) for name, (path, _digest) in PINNED_TREE_BLOCK_DIGESTS.items()
            },
            "block_digests": {
                name: digest for name, (_path, digest) in PINNED_TREE_BLOCK_DIGESTS.items()
            },
            "runner_sha256": PINNED_TREE_RUNNER_SHA256,
            "merged_receipt_levels_are_summaries": (
                "the merged receipt publishes port_fallback_measured as a summary "
                "integer; the raw rows are read from the pinned block artifacts and an "
                "artifact that publishes a summary integer instead of rows is reported "
                "as rows_unavailable rather than read as an empty list"
            ),
        },
        "existence_rule": (
            "an arm is counted as existing at a level only where a non-None value "
            "derived from it is published in the spent receipt's own reading field "
            "(SPENT_ARM_EVIDENCE names the field); a key in arms_finite proves only "
            "that the spent runner referenced the name, because that mapping is true "
            "for an arm passed as None"
        ),
        "vacuity_rule": (
            "in the spent receipt, assignment_specific is present and "
            "|treatment - control| > floor; where the spent receipt's present is false "
            "the zero is published as vacuous and is never read as evidence for a "
            "magnitude surface, and counts_only with no flat null passed is vacuous in "
            "the same way"
        ),
        "scope": (
            "every field name named inside this audit (present, at_the_floor, "
            "assignment_specific, counts_only, and the spent rule's own keys) is the "
            "spent tree receipt's schema, quoted so the audit can say what it found "
            "there.  This runner's own readings carry none of them: they carry "
            "the_shape, the_structural_separation, and the declared budget sweep, and no "
            "single budget point in this receipt carries a verdict"
        ),
        "per_level": per_level,
        "levels_where_a_zero_is_vacuous": vacuous,
        "levels_where_the_structural_question_was_untested": untested,
    }


# --------------------------------------------------------------------------
# the field's own composition
# --------------------------------------------------------------------------
def node_bounds(path: str, port_count: int) -> tuple[int, int]:
    """The port window of one dyadic node, by the field's own split rule."""

    left, right = 0, int(port_count)
    for step in str(path):
        middle = left + (right - left) // 2
        if step == "L":
            right = middle
        elif step == "R":
            left = middle
        else:
            raise ValueError(f"not a dyadic path: {path!r}")
    return int(left), int(right)


def field_weights(
    port_count: int, parent_path: str, children_sizes: Sequence[int]
) -> dict[str, Any]:
    """The field's own composition weights, produced by calling its own transform.

    ``cassi_resonant_field._packet_analyze`` composes a node's scale coefficient as
    ``sqrt(left_size/size) * left_scale + sqrt(right_size/size) * right_scale``.
    The weights here are not re-derived from that line: each is obtained by
    calling the field's own function on a unit probe whose left (or right) child
    carries a constant field, and the closed form is published beside it with the
    difference, so a reader sees that the probe reproduces the field's own rule.
    """

    channels = len(resonant.HELICAL_PACKET_CHANNELS)
    left_port, right_port = node_bounds(str(parent_path), int(port_count))
    size = int(right_port - left_port)
    sizes = [int(value) for value in children_sizes]
    probe: dict[str, Any] = {
        "port_count": int(port_count),
        "parent_path": str(parent_path),
        "parent_support": int(size),
        "children_sizes": list(sizes),
        "channels": int(channels),
        "authority": (
            "cassi_resonant_field._packet_analyze: scale = "
            "sqrt(left_size/size) * left_scale + sqrt(right_size/size) * right_scale"
        ),
    }
    weights: list[float] = []
    closed: list[float] = []
    for side in (0, 1):
        array = np.zeros((int(channels), int(port_count)))
        window = array[:, left_port:right_port]
        window[0, :] = 0.0
        lo = 0 if side == 0 else sizes[0]
        hi = sizes[0] if side == 0 else sizes[0] + sizes[1]
        window[0, lo:hi] = 1.0 / math.sqrt(float(sizes[side]))
        scale_row = resonant._packet_analyze(window)
        weights.append(float(scale_row[0][0]))
        closed.append(math.sqrt(float(sizes[side]) / float(size)))
    probe["probed_weights"] = [float(value) for value in weights]
    probe["closed_form_weights"] = [float(value) for value in closed]
    probe["difference"] = [float(left - right) for left, right in zip(weights, closed)]
    probe["the_probe_reproduces_the_closed_form"] = bool(
        all(
            abs(left - right) <= 1e-12
            for left, right in zip(weights, closed)
        )
    )
    probe["weights_orthonormal"] = bool(
        abs(sum(value * value for value in weights) - 1.0) <= 1e-12
    )
    return probe


# --------------------------------------------------------------------------
# the arms of one complete triple
# --------------------------------------------------------------------------
def arm_value(arms: Mapping[str, Any], name: str | None) -> float | None:
    """One arm's greatest readout difference, or None where the arm is absent."""

    if name is None or name not in arms or arms[name] is None:
        return None
    return float(arms[name]["greatest_difference"])


def measured_floors(
    arms: Mapping[str, Any],
    *,
    own: float | None,
    no_deposit: str,
    zero_work: str,
    half_pairs: Mapping[str, str],
    epsilon_factor: float,
) -> dict[str, Any]:
    """The measured floor of one row, term by term, with its binding term named."""

    no_deposit_value = arm_value(arms, no_deposit)
    zero_work_value = arm_value(arms, zero_work)
    term_no_deposit = (
        abs(float(no_deposit_value)) if no_deposit_value is not None else 0.0
    )
    term_zero_work = abs(float(zero_work_value)) if zero_work_value is not None else 0.0
    floor_matched_budget = abs(
        (0.0 if zero_work_value is None else float(zero_work_value))
        - (0.0 if no_deposit_value is None else float(no_deposit_value))
    )
    halves: dict[str, Any] = {}
    for name, half_name in half_pairs.items():
        value = arm_value(arms, name)
        half = arm_value(arms, half_name)
        halves[name] = {
            "arm": str(name),
            "half_budget_arm": str(half_name),
            "value": value,
            "half_budget_value": half,
            "term": (
                abs(float(value) - float(half))
                if value is not None and half is not None
                else None
            ),
        }
    half_terms = [
        float(record["term"])
        for record in halves.values()
        if record["term"] is not None
    ]
    floor_half_budget = max(half_terms, default=0.0)
    floor_declared_numerical = (
        float(epsilon_factor) * abs(float(own)) if own is not None else 0.0
    )
    # The verdict floor is the steering's declared rule and nothing else:
    # max(|r(zero-work at the treatment's own sources) - r(no deposit)|,
    #     |r(B) - r(B/2)| at the same sources and target).
    # Every other term below is published for comparison and is never binding.
    value = max(float(floor_matched_budget), float(floor_half_budget))
    binding = (
        "floor_matched_budget"
        if float(floor_matched_budget) >= float(floor_half_budget)
        else "floor_half_budget"
    )
    # Every arm that has its own half-budget arm carries its own measured floor:
    # the same two terms, taken on the arm itself.  A positive control is judged
    # against its own floor and not against the treatment's, because the
    # treatment's budget term is a property of the treatment.
    arm_floors: dict[str, Any] = {}
    for name, half_name in half_pairs.items():
        arm_full = arm_value(arms, name)
        arm_half = arm_value(arms, half_name)
        term = (
            abs(float(arm_full) - float(arm_half))
            if arm_full is not None and arm_half is not None
            else None
        )
        arm_floors[str(name)] = {
            "arm": str(name),
            "half_budget_arm": str(half_name),
            "matched_budget_term": float(floor_matched_budget),
            "half_budget_term": term,
            "value": (
                max(float(floor_matched_budget), float(term))
                if term is not None
                else None
            ),
            "the_budget_term_was_measured": bool(term is not None),
            "binding_term": (
                None
                if term is None
                else (
                    "floor_matched_budget"
                    if float(floor_matched_budget) >= float(term)
                    else "floor_half_budget"
                )
            ),
        }
    return {
        "arm_floors": arm_floors,
        "rule": DECLARED_FLOOR_RULE,
        "value": float(value),
        "binding_term": str(binding),
        "floor_matched_budget": float(floor_matched_budget),
        "floor_half_budget": float(floor_half_budget),
        "the_measured_floor_is_exactly_zero": bool(float(value) == 0.0),
        "published_but_never_binding": {
            "term_no_deposit": float(term_no_deposit),
            "term_zero_work": float(term_zero_work),
            "floor_declared_numerical": float(floor_declared_numerical),
            "narrowest_with_the_declared_numerical_term": float(
                max(float(value), float(floor_declared_numerical))
            ),
            "declared": (
                "these are published beside the verdict floor so a reader can see the "
                "numerical resolution and the raw readout noise; the verdicts of this "
                "runner use the matched-budget floor alone, as declared before the run"
            ),
        },
        "half_budget_pairs": halves,
        "no_deposit_arm": str(no_deposit),
        "zero_work_arm": str(zero_work),
        "no_deposit_response": no_deposit_value,
        "zero_work_response": zero_work_value,
    }


def floor_terms_of(floors: Mapping[str, Any]) -> dict[str, Any]:
    """One row's floor, published term by term beside the binding one."""

    return {
        "floor_matched_budget": float(floors["floor_matched_budget"]),
        "floor_half_budget": float(floors["floor_half_budget"]),
        "binding_term": str(floors["binding_term"]),
        "the_measured_floor_is_exactly_zero": bool(
            floors["the_measured_floor_is_exactly_zero"]
        ),
        "published_but_never_binding": dict(floors["published_but_never_binding"]),
    }


def budget_sweep(
    arms: Mapping[str, Any],
    *,
    treatment_prefix: str,
    own_prefix: str,
    epsilon_factor: float,
    floor_factor: float,
    write_budget: float,
) -> dict[str, Any]:
    """Every declared budget point, the plateau, both floor terms, and the shape.

    The spent receipt's two-term rule is
    ``|v| > max(FLOOR_FACTOR * |v - v_half|, EPS_FACTOR * |own|)``.  Worked out on
    paper that rule does not measure a reading's size, it measures its *shape*: a
    reading that scales with the drive has ``|v - v_half| = |v| / 2``, so its
    half-budget term is ``FLOOR_FACTOR / 2`` times the reading and no such reading
    can ever clear it, while a reading that has stopped moving between neighbouring
    budgets has a half-budget term at or below the numerical term and is judged on
    the numerical term alone.  So this block sweeps the declared ladder, publishes
    every point with **both floor terms separately** rather than folded into a
    ``max``, finds where the reading plateaus, compares the plateau with the
    numerical term, and states which shape the reading is:

      * ``plateau_above_the_numerical_term`` -- the reading stops moving with the
        drive and stays above the read noise: composition evidence, and the declared
        two-term rule *admits* this shape, because its half-budget term has gone to
        the numerical term by the plateau.  Where the rule is evaluated at a drive
        the reading is still climbing from, the rule rejects the reading by
        construction -- the rule is mis-shaped for a reading that still scales, not
        the reading absent;
      * ``still_climbing_with_the_drive`` -- the reading keeps rising across every
        declared point and is a **budget artifact**;
      * ``under_the_numerical_term`` -- the reading is silent at every declared
        point, so the drive reaches nothing readable here;
      * ``not_measured`` -- an arm of the sweep is missing.

    No single budget point carries a verdict.  Every figure the branch reads is a
    property of the whole sweep or a difference from a structural control.
    """

    points: list[dict[str, Any]] = []
    for index, multiple in enumerate(SWEEP_MULTIPLES):
        tag = str(multiple).replace(".", "p")
        treatment = arm_value(arms, f"{treatment_prefix}_{tag}")
        own = arm_value(arms, f"{own_prefix}_{tag}")
        previous = (
            arm_value(
                arms,
                f"{treatment_prefix}_{str(SWEEP_MULTIPLES[index - 1]).replace('.', 'p')}",
            )
            if index > 0
            else None
        )
        numerical = (
            float(epsilon_factor) * abs(float(own)) if own is not None else None
        )
        half_term = (
            float(floor_factor) * abs(float(treatment) - float(previous))
            if treatment is not None and previous is not None
            else None
        )
        binding = None
        if numerical is not None and half_term is not None:
            binding = (
                "floor_factor_times_the_half_budget_difference"
                if float(half_term) >= float(numerical)
                else "epsilon_factor_times_the_own_response"
            )
        points.append(
            {
                "budget_multiple": float(multiple),
                "per_source_budget": float(write_budget) * float(multiple),
                "treatment_response": treatment,
                "own_positive_control": own,
                "fraction_of_its_own_control": (
                    float(treatment) / float(own)
                    if treatment is not None and own not in (None, 0.0)
                    else None
                ),
                "the_two_floor_terms": {
                    "half_budget_difference_times_the_factor": half_term,
                    "numerical_term_epsilon_times_the_own_response": numerical,
                },
                "the_binding_term_at_this_point": binding,
                "the_rule_admits_at_this_point": (
                    None
                    if treatment is None or numerical is None or half_term is None
                    else bool(
                        abs(float(treatment))
                        > max(float(half_term), float(numerical))
                    )
                ),
                "change_from_the_previous_declared_point": (
                    abs(float(treatment) - float(previous))
                    if treatment is not None and previous is not None
                    else None
                ),
            }
        )
    measured = [
        point
        for point in points
        if point["treatment_response"] is not None
        and point["the_two_floor_terms"][
            "numerical_term_epsilon_times_the_own_response"
        ]
        is not None
    ]
    plateau = None
    for index, point in enumerate(points):
        if point["treatment_response"] is None:
            continue
        if index + 1 >= len(points):
            break
        # A row whose reading sits under the numerical term is silent: its flat zero
        # is not a plateau of a reading and is reported as the silent shape instead.
        if abs(float(point["treatment_response"])) <= float(
            point["the_two_floor_terms"][
                "numerical_term_epsilon_times_the_own_response"
            ]
            or 0.0
        ):
            continue
        coarser = points[index + 1]
        if coarser["treatment_response"] is None:
            continue
        numerical = point["the_two_floor_terms"][
            "numerical_term_epsilon_times_the_own_response"
        ]
        change = coarser["change_from_the_previous_declared_point"]
        if numerical is None or change is None or float(change) > float(numerical):
            continue
        coarser_stays = all(
            later["change_from_the_previous_declared_point"] is not None
            and float(later["change_from_the_previous_declared_point"])
            <= float(
                later["the_two_floor_terms"][
                    "numerical_term_epsilon_times_the_own_response"
                ]
                or 0.0
            )
            for later in points[index + 1 :]
        )
        if coarser_stays:
            admitted_from = next(
                (
                    candidate
                    for candidate in points[index:]
                    if candidate.get("the_rule_admits_at_this_point")
                ),
                None,
            )
            plateau = {
                "from_budget_multiple": float(point["budget_multiple"]),
                "value": point["treatment_response"],
                "change_to_the_next_coarser_point": float(change),
                "numerical_term_compared_with": float(numerical),
                "the_plateau_is_above_the_numerical_term": bool(
                    abs(float(point["treatment_response"])) > float(numerical)
                ),
                "the_first_multiple_the_declared_rule_admits": (
                    None
                    if admitted_from is None
                    else float(admitted_from["budget_multiple"])
                ),
                "the_declared_rule_admits_the_plateau": bool(admitted_from is not None),
                "declared": (
                    "from this multiple the reading's change to the next coarser "
                    "declared multiple is at or below the numerical term, and stays so "
                    "at every coarser multiple.  The multiple from which the declared "
                    "two-term rule admits the reading is published beside it, because the "
                    "rule reads the change between neighbouring budgets: a point whose own "
                    "change from the next finer budget is still large is a point the rule "
                    "rejects, even where the reading has already stopped moving above it"
                ),
            }
            break
    if not measured:
        shape = "not_measured"
    elif plateau is not None and plateau["the_plateau_is_above_the_numerical_term"]:
        shape = "plateau_above_the_numerical_term"
    elif all(
        point["change_from_the_previous_declared_point"] is None
        or float(point["change_from_the_previous_declared_point"])
        > float(
            point["the_two_floor_terms"][
                "numerical_term_epsilon_times_the_own_response"
            ]
            or 0.0
        )
        for point in points[1:]
        if point["treatment_response"] is not None
    ):
        shape = "still_climbing_with_the_drive"
    elif all(
        abs(float(point["treatment_response"]))
        <= float(
            point["the_two_floor_terms"][
                "numerical_term_epsilon_times_the_own_response"
            ]
            or 0.0
        )
        for point in measured
    ):
        shape = "under_the_numerical_term"
    else:
        shape = "not_measured"
    return {
        "declared": (
            "the declared budget sweep: every declared multiple of the level's own "
            "write budget, the treatment and its own positive control at each, the two "
            "floor terms of the spent receipt's rule published separately at each "
            "point, the plateau and the numerical term it is compared with, and the "
            "shape the whole sweep implies.  No single point carries a verdict"
        ),
        "treatment_arm_prefix": str(treatment_prefix),
        "own_arm_prefix": str(own_prefix),
        "sweep_multiples": [float(value) for value in SWEEP_MULTIPLES],
        "plateau_rule": PLATEAU_RULE,
        "points": points,
        "the_plateau": plateau,
        "the_shape": shape,
        "the_shape_is_evidence": bool(shape == "plateau_above_the_numerical_term"),
        "the_shape_is_a_budget_artifact": bool(shape == "still_climbing_with_the_drive"),
        "the_shape_says_the_declared_rule_rejects_this_reading_by_construction": bool(
            shape == "still_climbing_with_the_drive"
        ),
        "declared_shapes": {
            "plateau_above_the_numerical_term": (
                "the reading stops moving with the drive above the read noise.  This is "
                "composition evidence, and the declared two-term rule admits this "
                "shape: at the plateau the half-budget term has fallen to the numerical "
                "term"
            ),
            "still_climbing_with_the_drive": (
                "the reading rises between neighbouring declared points by more than the "
                "numerical term at every point of the declared ladder, so the ladder never "
                "reaches a plateau: the reading's magnitude is a budget artifact rather "
                "than a measured magnitude, and it is reported as one -- the reading rises "
                "at every declared point by more than the numerical "
                "term.  This is a budget artifact, and the declared two-term rule "
                "rejects this shape by construction: a reading that scales with the "
                "drive has |v - v_half| comparable to |v|, so the half-budget term is a "
                "multiple of the reading and the reading can never clear it.  The rule "
                "is mis-shaped for a reading that still scales; this is not the same "
                "statement as the reading being absent"
            ),
            "under_the_numerical_term": (
                "the reading sits at or below EPS_FACTOR * |its own control| at every "
                "declared point: silent, and bounded by that term"
            ),
            "not_measured": (
                "an arm of the sweep is missing at this row, so no shape is claimed and "
                "no branch reads this row"
            ),
        },
    }


def response_reading(
    arms: Mapping[str, Any],
    *,
    key: str,
    treatment: str,
    own: str,
    structural_control: str | None,
    flat_null: str | None,
    floors: Mapping[str, Any],
    spent_declared_floor: float | None,
    treatment_half: str | None = None,
    own_half: str | None = None,
    epsilon_factor: float = 1e-9,
    floor_factor: float = 10.0,
    write_budget: float = 0.0,
    sweep_prefix: str | None = None,
) -> dict[str, Any]:
    """One reading at one row: its whole budget sweep, its floor and its control.

    ``sweep_prefix`` names the geometry whose declared sweep this reading carries.
    The sweep ladder is declared for the two scale-surface geometries this runner
    measures; a reading without one states that plainly instead of borrowing a
    verdict from another path's sweep.
    """

    declared = DECLARED_READINGS[key]
    sweep: dict[str, Any] = (
        budget_sweep(
            arms,
            treatment_prefix=str(sweep_prefix),
            own_prefix="parent_scale_own_sweep",
            epsilon_factor=float(epsilon_factor),
            floor_factor=float(floor_factor),
            write_budget=float(write_budget),
        )
        if sweep_prefix is not None
        else {
            "the_shape": "no_sweep_declared_for_this_path",
            "declared": (
                "the declared sweep ladder is taken at the two scale-surface geometries "
                "this runner measures; this reading is reported through its structural "
                "separation and, where it has one, its count test, and states the absence "
                "of its own sweep rather than borrowing another path's"
            ),
        }
    )
    treatment_value = arm_value(arms, treatment)
    own_value = arm_value(arms, own)
    control_value = arm_value(arms, structural_control)
    flat_value = arm_value(arms, flat_null)
    floor = float(floors["value"])
    value = float(treatment_value) if treatment_value is not None else None
    difference_from_control = (
        abs(float(value) - float(control_value))
        if value is not None and control_value is not None
        else None
    )
    difference_from_flat = (
        abs(float(value) - float(flat_value))
        if value is not None and flat_value is not None
        else None
    )
    arm_floors = floors.get("arm_floors", {})
    own_floor_record = arm_floors.get(str(own))
    control_floor_record = (
        arm_floors.get(str(structural_control))
        if structural_control is not None
        else None
    )
    own_floor = (
        own_floor_record["value"] if own_floor_record is not None else None
    )
    own_floor_used = float(own_floor) if own_floor is not None else float(floor)
    comparison_parts = [
        float(
            (arm_floors.get(str(treatment)) or {}).get("value")
            if (arm_floors.get(str(treatment)) or {}).get("value") is not None
            else floor
        )
    ]
    if control_floor_record is not None and control_floor_record["value"] is not None:
        comparison_parts.append(float(control_floor_record["value"]))
    comparison_floor = max(comparison_parts)
    return {
        "reading": str(declared["name"]),
        "taken_at": str(declared["taken_at"]),
        "observed": False,
        "constructed_from_readouts": True,
        "carries_the_branch": bool(declared["carries_the_branch"]),
        "declared": (
            "the treatment's greatest readout difference at the target, with its own "
            "measured floor and its structural control measured beside it on the same "
            "held page, and the shape of the whole declared budget sweep.  No single "
            "budget point carries a verdict here: the shape classifies the reading as a "
            "plateau above the numerical term (composition evidence the declared rule "
            "admits), a reading still climbing with the drive (a budget artifact the "
            "declared rule rejects by construction), a reading under the numerical term "
            "(silent), or not measured; the structural separation is published as a "
            "difference beside the published floor terms it is compared with"
        ),
        "arms": {
            "treatment": str(treatment),
            "own": str(own),
            "structural_control": structural_control,
            "flat_null": flat_null,
        },
        "own_response": own_value,
        "treatment_response": value,
        "structural_control_response": control_value,
        "flat_null_response": flat_value,
        "fraction_of_the_own_response": (
            float(value) / abs(float(own_value))
            if value is not None and own_value not in (None, 0.0)
            else None
        ),
        "difference_from_the_structural_control": difference_from_control,
        "difference_from_the_flat_null": difference_from_flat,
        "floor": float(floor),
        "floor_terms": floor_terms_of(floors),
        "floor_binding_term": str(floors["binding_term"]),
        "spent_receipt_declared_floor": spent_declared_floor,
        "floor_over_the_spent_declared_floor": (
            float(spent_declared_floor) / float(floor)
            if spent_declared_floor not in (None, 0.0) and float(floor) != 0.0
            else None
        ),
        "own_floor": own_floor,
        "own_floor_binding_term": (
            None if own_floor_record is None else own_floor_record["binding_term"]
        ),
        "the_positive_control_fires": bool(
            own_value is not None and abs(float(own_value)) > own_floor_used
        ),
        "the_shape": sweep["the_shape"],
        "the_structural_separation": {
            "difference_from_the_structural_control": difference_from_control,
            "exceeds_the_numerical_term": bool(
                difference_from_control is not None
                and own_value not in (None, 0.0)
                and difference_from_control > 1e-9 * abs(float(own_value))
            ),
            "exceeds_the_measured_floor": bool(
                difference_from_control is not None
                and difference_from_control > float(floor)
            ),
            "exceeds_the_comparison_floor": bool(
                difference_from_control is not None
                and difference_from_control > float(comparison_floor)
            ),
            "compared_with": {
                "numerical_term_epsilon_times_the_own_response": (
                    1e-9 * abs(float(own_value))
                    if own_value not in (None, 0.0)
                    else None
                ),
                "measured_floor": float(floor),
                "comparison_floor": float(comparison_floor),
            },
        },
        "comparison_floor": float(comparison_floor),
        "comparison_floor_declared": (
            "the greatest of the participating arms' own measured floors: the "
            "treatment's and the structural control's, each max(the matched-budget "
            "term, that arm's own half-budget difference).  An arm with no own "
            "half-budget arm is reported absent rather than given a borrowed term"
        ),
        "the_reading_is_structurally_separated": bool(
            difference_from_control is not None
            and difference_from_control > comparison_floor
        ),
        "the_reading_is_structurally_separated_under_the_measured_floor": bool(
            difference_from_control is not None and difference_from_control > floor
        ),
        "the_structural_separation_is_vacuous": bool(
            sweep["the_shape"] in ("not_measured", "under_the_numerical_term")
        ),
        "the_structural_separation_vacuity_reason": (
            None
            if sweep["the_shape"] not in ("not_measured", "under_the_numerical_term")
            else (
                "the reading is silent at every declared drive or its sweep is missing, so "
                "the separation is computed from a silent reading and a false there is "
                "not evidence about the structural question"
            )
        ),
        "counts_only": bool(
            difference_from_flat is not None
            and difference_from_flat <= float(comparison_floor)
        ),
        "counts_only_is_vacuous": bool(flat_value is None),
        "counts_only_vacuity_reason": (
            None
            if flat_value is not None
            else (
                "no flat-null response was measured for this reading; counts_only is "
                "false because its input is absent, not because the placement does not "
                "matter"
            )
        ),
        "the_structural_control_exists": bool(control_value is not None),
        "the_flat_null_exists": bool(flat_value is not None),
        "budget_sweep": sweep,
    }


def field_composition_reading(
    arms: Mapping[str, Any],
    *,
    key: str,
    probe: str,
    own: str,
    left_self: str,
    right_self: str,
    left_alone: str,
    right_alone: str,
    weights: Mapping[str, Any],
    floors: Mapping[str, Any],
    spent_declared_floor: float | None,
    treatment_half: str | None = None,
    own_half: str | None = None,
    epsilon_factor: float = 1e-9,
    floor_factor: float = 10.0,
) -> dict[str, Any]:
    """R-C: the field's own composition beside the probe, its gap named."""

    declared = DECLARED_READINGS[key]
    probe_value = arm_value(arms, probe)
    own_value = arm_value(arms, own)
    left_value = arm_value(arms, left_self)
    right_value = arm_value(arms, right_self)
    left_alone_value = arm_value(arms, left_alone)
    right_alone_value = arm_value(arms, right_alone)
    floor = float(floors["value"])
    field_weights = [float(value) for value in weights["probed_weights"]]
    predictions: dict[str, float | None] = {}
    if left_value is not None and right_value is not None:
        predictions["field_size_weighted_composition"] = float(
            field_weights[0] * float(left_value) + field_weights[1] * float(right_value)
        )
        predictions["unweighted_sum_of_the_childrens_own_responses"] = float(
            float(left_value) + float(right_value)
        )
        predictions["mean_of_the_childrens_own_responses"] = float(
            (float(left_value) + float(right_value)) / 2.0
        )
    else:
        predictions["field_size_weighted_composition"] = None
        predictions["unweighted_sum_of_the_childrens_own_responses"] = None
        predictions["mean_of_the_childrens_own_responses"] = None
    predictions["linear_magnitude_of_the_two_alone_arms"] = (
        float(float(left_alone_value) + float(right_alone_value))
        if left_alone_value is not None and right_alone_value is not None
        else None
    )
    distances = {
        name: (
            abs(float(prediction) - float(probe_value))
            if prediction is not None and probe_value is not None
            else None
        )
        for name, prediction in predictions.items()
    }
    finite = {
        name: float(value) for name, value in distances.items() if value is not None
    }
    closest = min(finite, key=lambda name: finite[name]) if finite else None
    within = [
        name for name, value in finite.items() if float(value) <= float(floor)
    ]
    ratios = {
        "left_alone_over_the_childs_own_response": (
            float(left_alone_value) / float(left_value)
            if left_alone_value is not None and left_value not in (None, 0.0)
            else None
        ),
        "right_alone_over_the_childs_own_response": (
            float(right_alone_value) / float(right_value)
            if right_alone_value is not None and right_value not in (None, 0.0)
            else None
        ),
    }
    return {
        "reading": str(declared["name"]),
        "taken_at": str(declared["taken_at"]),
        "observed": False,
        "constructed_from_readouts": True,
        "carries_the_branch": bool(declared["carries_the_branch"]),
        "declared": (
            "the field's own size-weighted composition of the children's measured own "
            "scale responses, taken from the field's own transform, beside the probe "
            "the store's surface actually reports for the same two deposits; the gap "
            "between the field's internal composition and its exposed surface is "
            "published as a distance, and the per-child propagation ratio is published "
            "beside the field's weight for the same child"
        ),
        "probe_arm": str(probe),
        "probe_response": probe_value,
        "own_response": own_value,
        "children_scale_self_responses": {
            "left_arm": str(left_self),
            "right_arm": str(right_self),
            "left": left_value,
            "right": right_value,
        },
        "children_scale_alone_seen_at_the_parent": {
            "left_arm": str(left_alone),
            "right_arm": str(right_alone),
            "left": left_alone_value,
            "right": right_alone_value,
        },
        "field_weights": {
            "probed_weights": field_weights,
            "closed_form_weights": [
                float(value) for value in weights["closed_form_weights"]
            ],
            "difference": [float(value) for value in weights["difference"]],
            "the_probe_reproduces_the_closed_form": bool(
                weights["the_probe_reproduces_the_closed_form"]
            ),
            "weights_orthonormal": bool(weights["weights_orthonormal"]),
            "parent_support": int(weights["parent_support"]),
            "children_sizes": list(weights["children_sizes"]),
            "authority": str(weights["authority"]),
        },
        "predicted_responses": predictions,
        "distance_from_the_probe": distances,
        "predictions_within_the_floor": within,
        "closest_prediction": closest,
        "per_child_propagation_ratio": ratios,
        "field_weight_per_child": {
            "left": field_weights[0],
            "right": field_weights[1],
        },
        "the_ratio_matches_the_fields_own_weight": {
            "left": bool(
                ratios["left_alone_over_the_childs_own_response"] is not None
                and abs(
                    float(ratios["left_alone_over_the_childs_own_response"])
                    - field_weights[0]
                )
                <= float(floor)
            ),
            "right": bool(
                ratios["right_alone_over_the_childs_own_response"] is not None
                and abs(
                    float(ratios["right_alone_over_the_childs_own_response"])
                    - field_weights[1]
                )
                <= float(floor)
            ),
        },
        "the_ratio_is_one_an_unweighted_accumulation": {
            "left": bool(
                ratios["left_alone_over_the_childs_own_response"] is not None
                and abs(
                    float(ratios["left_alone_over_the_childs_own_response"]) - 1.0
                )
                <= float(floor)
            ),
            "right": bool(
                ratios["right_alone_over_the_childs_own_response"] is not None
                and abs(
                    float(ratios["right_alone_over_the_childs_own_response"]) - 1.0
                )
                <= float(floor)
            ),
        },
        "floor": float(floor),
        "floor_terms": floor_terms_of(floors),
        "floor_binding_term": str(floors["binding_term"]),
        "spent_receipt_declared_floor": spent_declared_floor,
        "declared_substitutions": [
            "the child's own scale-surface self-response stands in for its scale "
            "coefficient: the field's transform is not applied to the store's internal "
            "state, only to the readouts it exposes",
            "the probe is the store's own surface response to the same two deposits, so "
            "a distance between it and the field's composition is a gap between the "
            "field's internal composition and its exposed surface, named here rather "
            "than smoothed over",
        ],
        "the_shape": "no_sweep_declared_for_this_path",
        "the_shape_declared": (
            "the declared sweep ladder is taken at the two scale-surface geometries this "
            "runner measures; this reading is the field's own composition compared with "
            "the store's exposed probe, so it carries no budget sweep of its own and says "
            "so instead of borrowing a shape from another path.  Its gap from the field's "
            "own weights is published as a distance with its floor terms"
        ),
        "the_positive_control_fires": bool(
            own_value is not None
            and abs(float(own_value))
            > float(
                (floors.get("arm_floors", {}).get(str(own)) or {}).get("value")
                if (floors.get("arm_floors", {}).get(str(own)) or {}).get("value")
                is not None
                else floor
            )
        ),
        "own_floor": (floors.get("arm_floors", {}).get(str(own)) or {}).get("value"),
        "the_structural_control_exists": bool(weights.get("probed_weights")),
        "the_flat_null_exists": False,
        "counts_only_is_vacuous": True,
        "counts_only_vacuity_reason": (
            "this reading compares the probe with two predictions rather than with a "
            "null placement, as declared: it has no flat-null arm to be vacuous about, "
            "and the comparison it does have is the field's own composition"
        ),
    }


def magnitude_reading(
    arms: Mapping[str, Any],
    *,
    key: str,
    two_children: str,
    one_child_full_budget: str,
    one_child_full_budget_right: str,
    flat_null: str,
    one_child_probe_budget_left: str,
    floors: Mapping[str, Any],
    spent_declared_floor: float | None,
    treatment_half: str | None = None,
    own_half: str | None = None,
    epsilon_factor: float = 1e-9,
    floor_factor: float = 10.0,
) -> dict[str, Any]:
    """R-D: the same total budget in four placements, and where they agree."""

    declared = DECLARED_READINGS[key]
    floor = float(floors["value"])
    values = {
        "two_deposits_at_the_two_childrens_scale_surfaces": arm_value(arms, two_children),
        "one_deposit_at_the_left_child_with_the_whole_budget": arm_value(
            arms, one_child_full_budget
        ),
        "one_deposit_at_the_right_child_with_the_whole_budget": arm_value(
            arms, one_child_full_budget_right
        ),
        "two_deposits_at_the_flat_null_surfaces": arm_value(arms, flat_null),
        "one_deposit_at_the_left_child_at_the_probe_budget": arm_value(
            arms, one_child_probe_budget_left
        ),
    }
    split = values["two_deposits_at_the_two_childrens_scale_surfaces"]
    flat = values["two_deposits_at_the_flat_null_surfaces"]
    single = values["one_deposit_at_the_left_child_with_the_whole_budget"]
    left_probe = values["one_deposit_at_the_left_child_at_the_probe_budget"]
    differences = {
        "two_children_minus_one_child_same_total": (
            abs(float(split) - float(single))
            if split is not None and single is not None
            else None
        ),
        "two_children_minus_the_flat_null": (
            abs(float(split) - float(flat))
            if split is not None and flat is not None
            else None
        ),
        "two_children_minus_twice_the_one_child_probe": (
            abs(float(split) - 2.0 * float(left_probe))
            if split is not None and left_probe is not None
            else None
        ),
    }
    constant_total = differences["two_children_minus_one_child_same_total"]
    counts_matter = bool(
        constant_total is not None and float(constant_total) > floor
    )
    counts_irrelevant = bool(
        constant_total is not None and float(constant_total) <= floor
    )
    placement_matters = bool(
        differences["two_children_minus_the_flat_null"] is not None
        and float(differences["two_children_minus_the_flat_null"]) > floor
    )
    placement_irrelevant = bool(
        differences["two_children_minus_the_flat_null"] is not None
        and float(differences["two_children_minus_the_flat_null"]) <= floor
    )
    return {
        "reading": str(declared["name"]),
        "taken_at": str(declared["taken_at"]),
        "observed": False,
        "constructed_from_readouts": True,
        "carries_the_branch": bool(declared["carries_the_branch"]),
        "declared": (
            "the same total budget in four placements: two deposits at the children's "
            "scale surfaces, one at a child's with the whole budget, two at the flat "
            "null's surfaces, and one at a child's at the probe budget.  Where the child "
            "and non-child placements agree within the floor the response answers how "
            "much and not which children"
        ),
        "arms": {
            "two_children": str(two_children),
            "one_child_full_budget": str(one_child_full_budget),
            "one_child_full_budget_right": str(one_child_full_budget_right),
            "flat_null": str(flat_null),
            "one_child_probe_budget": str(one_child_probe_budget_left),
        },
        "responses": values,
        "differences": differences,
        "floor": float(floor),
        "floor_terms": floor_terms_of(floors),
        "floor_binding_term": str(floors["binding_term"]),
        "spent_receipt_declared_floor": spent_declared_floor,
        "the_count_matters_at_a_constant_total_budget": counts_matter,
        "the_count_does_not_matter_at_a_constant_total_budget": counts_irrelevant,
        "the_count_test": (
            "two deposits, one at each of the treated parent's children, against one "
            "deposit at a single child carrying the whole write budget: the same total "
            "work with the count halved.  The two arms are built with the same total "
            "work -- two sources at the level's write budget against one source at twice "
            "it -- so the comparison is a count test and not a budget test.  Where the "
            "two agree within the floor the surface answers how much rather than which "
            "or how many children, and this comparison needs no placement null and so is "
            "available at every row"
        ),
        "the_count_test_holds_the_total_work_constant": {
            "two_children_at_the_write_budget": {
                "sources": 2,
                "per_source_budget": "the level's delivered write budget",
            },
            "one_child_at_twice_the_write_budget": {
                "sources": 1,
                "per_source_budget": "twice the level's delivered write budget",
            },
            "declared": (
                "both placements deposit the same total work, so a difference between "
                "them is a difference in how many children were written and in which, "
                "never a difference in how much was written"
            ),
        },
        "the_placement_matters": placement_matters,
        "the_placement_does_not_matter": placement_irrelevant,
        "the_shape": "no_sweep_declared_for_this_path",
        "the_shape_declared": (
            "the count test below is a constant-total-budget comparison with both of its "
            "own arms, not a single-budget verdict, and this reading carries no declared "
            "budget sweep of its own"
        ),
        "the_positive_control_fires": bool(
            split is not None
            and abs(float(split))
            > float(
                (
                    floors.get("arm_floors", {}).get(
                        str(one_child_full_budget)
                    )
                    or {}
                ).get("value")
                if (
                    floors.get("arm_floors", {}).get(str(one_child_full_budget)) or {}
                ).get("value")
                is not None
                else floor
            )
        ),
        "own_floor": (
            floors.get("arm_floors", {}).get(str(one_child_full_budget)) or {}
        ).get("value"),
        "the_structural_control_exists": bool(flat is not None),
        "the_flat_null_exists": bool(flat is not None),
        "counts_only_is_vacuous": bool(flat is None),
        "counts_only_vacuity_reason": (
            None
            if flat is not None
            else (
                "the flat placement was not measured for this row; the placement "
                "comparison is then unavailable rather than negative"
            )
        ),
    }


def leaf_triple_arm(
    profile: Any,
    settings: rank.AddressingRankConfig,
    page: Any,
    *,
    triple: Mapping[str, Any],
    shuffled: Mapping[str, Any] | None,
    other_ports: Sequence[Any],
    budget: float,
    deposit_budget: float,
    label: str,
) -> dict[str, Any]:
    """One leaf-child triple's arms: the port path with its own controls."""

    parent_scale = tree.Surface.from_dict(triple["parent"]["scale"])
    scales = [
        tree.Surface.from_dict(child["scale"])
        for child in triple["children"]
        if child.get("scale") is not None
    ]
    other = [surface for surface in other_ports if surface is not None]
    shuffled_scale = (
        tree.Surface.from_dict(shuffled["parent"]["scale"])
        if shuffled is not None
        else None
    )
    arms: dict[str, Any] = {}
    arms["port_parent_scale_own"] = tree.response(
        profile,
        settings,
        page,
        sources=[parent_scale],
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:port-parent-scale-own",
    )
    arms["port_parent_scale_own_half"] = tree.response(
        profile,
        settings,
        page,
        sources=[parent_scale],
        targets=[parent_scale],
        budget=float(budget) / 2.0,
        label=f"{label}:port-parent-scale-own-half",
    )
    arms["port_no_deposit"] = tree.response(
        profile,
        settings,
        page,
        sources=[],
        targets=[parent_scale],
        budget=0.0,
        label=f"{label}:port-no-deposit",
    )
    arms["port_children_scale_home"] = tree.response(
        profile,
        settings,
        page,
        sources=scales,
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:port-children-scale-home",
    )
    arms["port_children_scale_home_half"] = tree.response(
        profile,
        settings,
        page,
        sources=scales,
        targets=[parent_scale],
        budget=float(budget) / 2.0,
        label=f"{label}:port-children-scale-home-half",
    )
    arms["port_children_scale_zero_work"] = tree.response(
        profile,
        settings,
        page,
        sources=scales,
        targets=[parent_scale],
        budget=0.0,
        label=f"{label}:port-children-scale-zero-work",
    )
    arms["port_other_ports_same_target"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=list(other[: len(scales)]),
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:port-other-ports-same-target",
        )
        if len(other) >= len(scales) and scales
        else None
    )
    arms["port_children_shuffled_parent"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=scales,
            targets=[shuffled_scale],
            budget=float(budget),
            label=f"{label}:port-children-shuffled-parent",
        )
        if shuffled_scale is not None and scales
        else None
    )
    arms["port_children_scale_delivered_budget"] = tree.response(
        profile,
        settings,
        page,
        sources=scales,
        targets=[parent_scale],
        budget=float(deposit_budget),
        label=f"{label}:port-children-scale-delivered-budget",
    )
    return _arm_bundle(arms, label=label, parent_scale=parent_scale, scales=scales)


def _arm_bundle(
    arms: Mapping[str, Any], *, label: str, parent_scale: Any, scales: Sequence[Any]
) -> dict[str, Any]:
    return {
        "label": str(label),
        "parent_scale_surface": parent_scale.as_dict(),
        "children_scale_surfaces": [surface.as_dict() for surface in scales],
        "arms": {
            name: (
                None
                if arm is None
                else {
                    "budget": float(arm["budget"]),
                    "differences": {
                        key: float(value) for key, value in arm["differences"].items()
                    },
                    "per_declared_budget": {
                        key: float(value)
                        for key, value in arm["per_declared_budget"].items()
                    },
                    "greatest_difference": float(arm["greatest_difference"]),
                    "applied_work_total": float(arm["applied_work_total"]),
                    "every_write_accepted": bool(arm["every_write_accepted"]),
                    "page_moved_by_the_arm": bool(arm["page_moved_by_the_arm"]),
                }
            )
            for name, arm in arms.items()
        },
        "arms_present": sorted(name for name, arm in arms.items() if arm is not None),
        "arms_absent": sorted(name for name, arm in arms.items() if arm is None),
    }


def complete_triple_arms(
    profile: Any,
    settings: rank.AddressingRankConfig,
    page: Any,
    *,
    catalogue: Mapping[str, Any],
    triple: Mapping[str, Any],
    shuffled: Mapping[str, Any] | None,
    flat_detail: Sequence[Any],
    flat_scale: Sequence[Any],
    descendant_scale: Sequence[Any],
    non_ancestor_descendant_scale: Sequence[Any],
    weights: Mapping[str, Any],
    budget: float,
    deposit_budget: float,
    label: str,
) -> dict[str, Any]:
    """Every arm of one complete triple: the readings' treatments and controls."""

    parent = triple["parent"]
    children = triple["children"]
    parent_scale = tree.Surface.from_dict(parent["scale"])
    left_scale = tree.Surface.from_dict(children[0]["scale"])
    right_scale = tree.Surface.from_dict(children[1]["scale"])
    child_scales = [left_scale, right_scale]
    child_details = [
        tree.Surface.from_dict(child["item"]) if child.get("item") is not None else None
        for child in children
    ]
    shuffled_scales: list[Any] = []
    shuffled_details: list[Any] = []
    if shuffled is not None:
        for child in shuffled["children"]:
            if child.get("scale") is not None:
                shuffled_scales.append(tree.Surface.from_dict(child["scale"]))
            if child.get("item") is not None:
                shuffled_details.append(tree.Surface.from_dict(child["item"]))
    shuffled_parent_scale = (
        tree.Surface.from_dict(shuffled["parent"]["scale"])
        if shuffled is not None
        else None
    )
    half = float(budget) / 2.0
    arms: dict[str, Any] = {}
    arms["parent_scale_own"] = tree.response(
        profile,
        settings,
        page,
        sources=[parent_scale],
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:parent-scale-own",
    )
    arms["parent_scale_own_half"] = tree.response(
        profile,
        settings,
        page,
        sources=[parent_scale],
        targets=[parent_scale],
        budget=half,
        label=f"{label}:parent-scale-own-half",
    )
    arms["child_scale_own_left"] = tree.response(
        profile,
        settings,
        page,
        sources=[left_scale],
        targets=[left_scale],
        budget=float(budget),
        label=f"{label}:child-scale-own-left",
    )
    arms["child_scale_own_right"] = tree.response(
        profile,
        settings,
        page,
        sources=[right_scale],
        targets=[right_scale],
        budget=float(budget),
        label=f"{label}:child-scale-own-right",
    )
    arms["child_scale_own_left_half"] = tree.response(
        profile,
        settings,
        page,
        sources=[left_scale],
        targets=[left_scale],
        budget=half,
        label=f"{label}:child-scale-own-left-half",
    )
    arms["child_scale_alone_to_parent_left"] = tree.response(
        profile,
        settings,
        page,
        sources=[left_scale],
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:child-scale-alone-to-parent-left",
    )
    arms["child_scale_alone_to_parent_left_half"] = tree.response(
        profile,
        settings,
        page,
        sources=[left_scale],
        targets=[parent_scale],
        budget=half,
        label=f"{label}:child-scale-alone-to-parent-left-half",
    )
    arms["child_scale_alone_to_parent_right"] = tree.response(
        profile,
        settings,
        page,
        sources=[right_scale],
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:child-scale-alone-to-parent-right",
    )
    arms["children_scale_home"] = tree.response(
        profile,
        settings,
        page,
        sources=child_scales,
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:children-scale-home",
    )
    arms["children_scale_home_half"] = tree.response(
        profile,
        settings,
        page,
        sources=child_scales,
        targets=[parent_scale],
        budget=half,
        label=f"{label}:children-scale-home-half",
    )
    for multiple in SWEEP_MULTIPLES:
        tag = str(multiple).replace(".", "p")
        arms[f"children_detail_sweep_{tag}"] = (
            tree.response(
                profile,
                settings,
                page,
                sources=child_details,
                targets=[parent_scale],
                budget=float(budget) * float(multiple),
                label=f"{label}:children-detail-sweep-{tag}",
            )
            if all(child is not None for child in child_details)
            else None
        )
        arms[f"children_scale_sweep_{tag}"] = tree.response(
            profile,
            settings,
            page,
            sources=child_scales,
            targets=[parent_scale],
            budget=float(budget) * float(multiple),
            label=f"{label}:children-scale-sweep-{tag}",
        )
        arms[f"parent_scale_own_sweep_{tag}"] = tree.response(
            profile,
            settings,
            page,
            sources=[parent_scale],
            targets=[parent_scale],
            budget=float(budget) * float(multiple),
            label=f"{label}:parent-scale-own-sweep-{tag}",
        )
    arms["children_scale_shuffled_parent_same_target"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=shuffled_scales,
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:children-scale-shuffled-parent-same-target",
        )
        if shuffled_scales
        else None
    )
    arms["children_scale_shuffled_parent_same_geometry"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=shuffled_scales,
            targets=[shuffled_parent_scale],
            budget=float(budget),
            label=f"{label}:children-scale-shuffled-parent-same-geometry",
        )
        if shuffled_scales and shuffled_parent_scale is not None
        else None
    )
    arms["children_scale_flat_null"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=list(flat_scale),
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:children-scale-flat-null",
        )
        if flat_scale
        else None
    )
    arms["children_scale_duplicate"] = tree.response(
        profile,
        settings,
        page,
        sources=[left_scale, left_scale],
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:children-scale-duplicate",
    )
    arms["children_scale_shared"] = tree.response(
        profile,
        settings,
        page,
        sources=[parent_scale, parent_scale],
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:children-scale-shared",
    )
    arms["children_scale_zero_work"] = tree.response(
        profile,
        settings,
        page,
        sources=child_scales,
        targets=[parent_scale],
        budget=0.0,
        label=f"{label}:children-scale-zero-work",
    )
    arms["no_deposit"] = tree.response(
        profile,
        settings,
        page,
        sources=[],
        targets=[parent_scale],
        budget=0.0,
        label=f"{label}:no-deposit",
    )
    arms["children_detail_home"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=[surface for surface in child_details if surface is not None],
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:children-detail-home",
        )
        if all(surface is not None for surface in child_details)
        else None
    )
    arms["children_detail_home_half"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=[surface for surface in child_details if surface is not None],
            targets=[parent_scale],
            budget=half,
            label=f"{label}:children-detail-home-half",
        )
        if all(surface is not None for surface in child_details)
        else None
    )
    arms["children_detail_shuffled_parent_same_target"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=shuffled_details,
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:children-detail-shuffled-parent-same-target",
        )
        if shuffled_details
        else None
    )
    arms["children_detail_flat_null"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=list(flat_detail),
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:children-detail-flat-null",
        )
        if flat_detail
        else None
    )
    arms["children_detail_duplicate"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=[child_details[0], child_details[0]],
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:children-detail-duplicate",
        )
        if child_details[0] is not None
        else None
    )
    arms["children_detail_shared"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=[child_details[0], child_details[0]],
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:children-detail-shared",
        )
        if child_details[0] is not None
        else None
    )
    arms["magnitude_one_child_scale_whole_budget"] = tree.response(
        profile,
        settings,
        page,
        sources=[left_scale],
        targets=[parent_scale],
        budget=float(budget) * 2.0,
        label=f"{label}:magnitude-one-child-scale-whole-budget",
    )
    arms["magnitude_one_child_scale_whole_budget_right"] = tree.response(
        profile,
        settings,
        page,
        sources=[right_scale],
        targets=[parent_scale],
        budget=float(budget) * 2.0,
        label=f"{label}:magnitude-one-child-scale-whole-budget-right",
    )
    arms["descendants_scale_home"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=list(descendant_scale),
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:descendants-scale-home",
        )
        if descendant_scale
        else None
    )
    arms["descendants_scale_non_ancestor"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=list(non_ancestor_descendant_scale),
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:descendants-scale-non-ancestor",
        )
        if non_ancestor_descendant_scale
        else None
    )
    arms["descendants_scale_home_half"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=list(descendant_scale),
            targets=[parent_scale],
            budget=half,
            label=f"{label}:descendants-scale-home-half",
        )
        if descendant_scale
        else None
    )
    arms["delivered_scale_children_home"] = tree.response(
        profile,
        settings,
        page,
        sources=child_scales,
        targets=[parent_scale],
        budget=float(deposit_budget),
        label=f"{label}:delivered-scale-children-home",
    )
    arms["delivered_scale_parent_own"] = tree.response(
        profile,
        settings,
        page,
        sources=[parent_scale],
        targets=[parent_scale],
        budget=float(deposit_budget),
        label=f"{label}:delivered-scale-parent-own",
    )
    arms["delivered_scale_children_home_half"] = tree.response(
        profile,
        settings,
        page,
        sources=child_scales,
        targets=[parent_scale],
        budget=float(deposit_budget) / 2.0,
        label=f"{label}:delivered-scale-children-home-half",
    )
    arms["delivered_scale_parent_own_half"] = tree.response(
        profile,
        settings,
        page,
        sources=[parent_scale],
        targets=[parent_scale],
        budget=float(deposit_budget) / 2.0,
        label=f"{label}:delivered-scale-parent-own-half",
    )
    arms["delivered_scale_child_own"] = tree.response(
        profile,
        settings,
        page,
        sources=[left_scale],
        targets=[left_scale],
        budget=float(deposit_budget),
        label=f"{label}:delivered-scale-child-own",
    )
    arms["delivered_scale_children_shuffled_same_target"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=shuffled_scales,
            targets=[parent_scale],
            budget=float(deposit_budget),
            label=f"{label}:delivered-scale-children-shuffled-same-target",
        )
        if shuffled_scales
        else None
    )
    arms["delivered_scale_children_flat_null"] = (
        tree.response(
            profile,
            settings,
            page,
            sources=list(flat_scale),
            targets=[parent_scale],
            budget=float(deposit_budget),
            label=f"{label}:delivered-scale-children-flat-null",
        )
        if flat_scale
        else None
    )
    bundle = _arm_bundle(
        arms, label=label, parent_scale=parent_scale, scales=child_scales
    )
    bundle["field_weights"] = dict(weights)
    bundle["parent_path"] = str(parent["path"])
    return bundle


# --------------------------------------------------------------------------
# one level
# --------------------------------------------------------------------------
def matched_shuffled(
    shuffled: Mapping[str, Any] | None,
    parent_path: str,
    depth: int,
) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
    """The shuffled-parent control, or None where the tree runner's own helper crossed depths.

    ``run_store_addressing_tree.shuffled_parent`` falls back to any-depth complete
    triple when the level has no second complete triple at the treated parent's own
    depth, and at the root that fallback selects a descendant: the arm would then
    write inside the treated parent's own subtree while wearing the name of a
    shuffled parent.  This runner accepts the helper's choice only when its parent
    sits at the treated parent's own depth and is neither an ancestor nor a
    descendant of it, and records the crossing where it refuses.
    """

    if shuffled is None:
        return None, {
            "chosen_path": None,
            "accepted": False,
            "same_depth": None,
            "neither_ancestor_nor_descendant": None,
            "reason": (
                "the field's own helper found no other complete triple at this level, "
                "so there is no shuffled-parent control here"
            ),
        }
    other = str(shuffled["parent"]["path"])
    same_depth = int(shuffled["parent"]["depth"]) == int(depth)
    unrelated = bool(parent_path and other) and not (
        other.startswith(str(parent_path)) or str(parent_path).startswith(other)
    )
    accepted = bool(same_depth and unrelated)
    return (shuffled if accepted else None), {
        "chosen_path": other,
        "accepted": accepted,
        "same_depth": bool(same_depth),
        "neither_ancestor_nor_descendant": bool(unrelated),
        "reason": (
            "the helper's choice is at the treated parent's own depth and unrelated to "
            "it: accepted as the shuffled-parent control"
            if accepted
            else (
                "the helper's own rule crossed depths or picked an ancestor or a "
                "descendant of the treated parent -- refused here, because a control "
                "that writes inside the treated parent's own subtree is not a shuffled "
                "placement, and the row records the structural control as unavailable "
                "rather than accepting it"
            )
        ),
    }


def matched_descendants(
    triple: Mapping[str, Any],
    *,
    template: Sequence[Mapping[str, Any]],
    count: int,
    sizes: Mapping[str, int],
) -> list[Mapping[str, Any]]:
    """Up to ``count`` of a triple's descendants matching the template's class and size.

    A control is only a control when the node it writes is the same kind of node the
    treatment writes, so the node class and the port count are matched, and the match
    is published beside the arm.
    """

    wanted = {
        (str(row.get("node_class")), int(sizes.get(str(row.get("path")), 0)))
        for row in template
    }
    found: list[Mapping[str, Any]] = []
    for record in triple.get("descendants", ()):
        if record.get("scale") is None:
            continue
        key = (
            str(record.get("node_class")),
            int(sizes.get(str(record.get("path")), 0)),
        )
        if key in wanted:
            found.append(record)
        if len(found) >= int(count):
            break
    return found


def unrelated_descendants(
    triples: Sequence[Mapping[str, Any]],
    parent_path: str,
    *,
    template: Sequence[Mapping[str, Any]],
    count: int,
    sizes: Mapping[str, int],
) -> tuple[Mapping[str, Any] | None, list[Mapping[str, Any]]]:
    """The first non-ancestor source for the descendants reading, and its nodes.

    The structural control for the descendants reading must be a source that is
    neither in the treated parent's subtree nor contains it: a parent whose path is a
    prefix of the treated parent's path is an ancestor and one the treated parent's
    path prefixes is a descendant, and neither is a non-ancestor.  The search walks
    the field's own complete triples in declared order and takes the first one that
    can supply as many nodes of the treatment's own class and size as the treatment
    writes; where none can, there is no non-ancestor control at this level and the
    reading says so.
    """

    for row in triples:
        if str(row["triple_class"]) != "complete" or not row.get("descendants"):
            continue
        other = str(row["parent"]["path"])
        if other == str(parent_path):
            continue
        if other.startswith(str(parent_path)) or str(parent_path).startswith(other):
            continue
        found = matched_descendants(
            row, template=template, count=int(count), sizes=sizes
        )
        if len(found) >= int(count):
            return row, found
    return None, []


def flat_null_pair(
    port_count: int,
    *,
    parent_path: str,
    child_paths: Sequence[str],
    child_sizes: Sequence[int],
    sizes: Mapping[str, int],
    depths: Sequence[int],
    min_size: int,
    exclude_paths: Sequence[str] = (),
) -> tuple[list[dict[str, Any]], int | None]:
    """The placement null: a non-sibling pair outside the subtree, size-matched as a set.

    The null is deliberately a different *shape* of placement from the shuffled
    parent's children: two nodes that are not siblings of one another can never be
    the two children of any single parent, so this control cannot coincide with the
    shuffled-parent arm and the two are not one measurement counted twice.  The pair
    is size-matched to the treated children as a multiset, so the same count and the
    same total work are written; the search walks the children's own depth first and
    then every other depth, so a pair of the right size sitting at another depth is
    still found and its depth difference is published beside it.
    """

    needed = sorted(int(value) for value in child_sizes)
    banned = {str(path) for path in exclude_paths}
    for depth in depths:
        outstanding = list(needed)
        found: list[dict[str, Any]] = []
        for row in capacity.dyadic_nodes(int(port_count)):
            path = str(row["path"])
            if int(row["depth"]) != int(depth) or path in banned:
                continue
            if int(sizes.get(path, 0)) < int(min_size):
                continue
            if path.startswith(str(parent_path)) or str(parent_path).startswith(path):
                continue  # the root's subtree is the whole tree: no outside candidate
            if int(sizes.get(path, 0)) not in outstanding:
                continue
            if any(str(other["path"])[:-1] == path[:-1] for other in found):
                continue
            outstanding.remove(int(sizes.get(path, 0)))
            found.append(row)
            if not outstanding:
                break
        if not outstanding:
            return found, int(depth)
    return [], None


def surface_for(
    path: str,
    component: str,
    *,
    sizes: Mapping[str, int],
    family_keys: set[tuple[str, str]],
    refusals: list[dict[str, Any]] | None = None,
) -> Any:
    """One surface, or None where the field's own rule refuses it.

    A single-port node's detail surface does not exist -- the field's own refusal
    is "a leaf packet has no detail mode" -- so a detail surface is built only for
    a node whose support is larger than one port, and the refusal is recorded
    rather than raised.
    """

    size = int(sizes.get(str(path), 0))
    if str(component) == "detail" and size <= 1:
        if refusals is not None:
            refusals.append(
                {
                    "path": str(path),
                    "component": "detail",
                    "node_size": int(size),
                    "reason": (
                        "the field's own rule: a leaf packet has no detail mode"
                    ),
                }
            )
        return None
    if str(component) == "scale":
        return tree.scale_surface(str(path), size=size, family_keys=family_keys)
    return tree.item_surface(
        durability.ItemSpec(
            f"{component}-{path or 'root'}", str(path), str(component), (1.0, 0.0)
        ),
        size=size,
        family_keys=family_keys,
    )


def level_block(
    profile: Any,
    count: int,
    *,
    resolution: int,
    hold_settings: Mapping[str, Any],
    spent_level_floor: float | None,
) -> dict[str, Any]:
    """One declared count: its held page, its rows, and its branch."""

    family = capacity.declared_family(int(profile.port_count))
    specs: tuple[durability.ItemSpec, ...] = family["specs"]
    if int(count) > int(len(specs)):
        return {
            "n": int(count),
            "ports_per_pool": int(resolution),
            "constructible": False,
            "reason": (
                "the declared family has no item at this count at this resolution: "
                f"its addressable inventory is {len(specs)} items"
            ),
            "addressable_count": int(len(specs)),
        }
    started = time.perf_counter()
    settings = capacity.level_settings(int(count))
    catalogue = tree.level_catalogue(int(profile.port_count), int(count))
    nodes = capacity.dyadic_nodes(int(profile.port_count))
    sizes = {str(row["path"]): int(row["size"]) for row in nodes}
    family_keys = {(str(spec.path), str(spec.component)) for spec in specs}
    held = rank.held_state(
        profile,
        settings,
        indices=tuple(range(int(count))),
        gain=float(hold_settings["gain"]),
        phase_degrees=float(hold_settings["phase_degrees"]),
        phase_references=hold_settings["per_item"],
        captures=hold_settings["captures"],
        label=f"scale-composition-held-{count}",
    )
    page = held.pop("held_page_object")
    triples = catalogue["triples"]
    budget = float(settings.probe_budget)
    deposit_budget = float(settings.store_config.write_budget)
    positions = tree.selected_triples(triples, MEASURED_TRIPLE_CAP)
    port_positions = [
        position
        for position, row in enumerate(triples)
        if str(row["triple_class"]) == "leaf_child"
    ][:PORT_FALLBACK_CAP]
    rows: list[dict[str, Any]] = []
    port_rows: list[dict[str, Any]] = []
    rows_refused: list[dict[str, Any]] = []
    port_rows_refused: list[dict[str, Any]] = []
    for position in positions:
        triple = triples[position]
        shuffled, shuffled_record = matched_shuffled(
            tree.shuffled_parent(triples, position),
            str(triple["parent"]["path"]),
            int(triple["parent"]["depth"]),
        )
        child_depth = int(triple["parent"]["depth"]) + 1
        child_paths = [str(child["path"]) for child in triple["children"]]
        child_sizes = [
            int(sizes.get(str(child["path"]), 0)) for child in triple["children"]
        ]
        depths_tried = [int(child_depth)] + sorted(
            {
                int(row["depth"])
                for row in capacity.dyadic_nodes(int(profile.port_count))
                if int(row["depth"]) != int(child_depth)
            }
        )
        flat_scale_nodes, flat_depth = flat_null_pair(
            int(profile.port_count),
            parent_path=str(triple["parent"]["path"]),
            child_paths=child_paths,
            child_sizes=child_sizes,
            sizes=sizes,
            depths=depths_tried,
            min_size=1,
        )
        flat_detail_nodes = [
            row
            for row in flat_scale_nodes
            if int(sizes.get(str(row["path"]), 0)) > 1
        ] if len(flat_scale_nodes) == 2 else []
        flat_source = "non_sibling_pair_outside_the_subtree" 
        surface_refusals: list[dict[str, Any]] = []
        flat_detail = [
            surface
            for surface in (
                surface_for(
                    str(row["path"]),
                    "detail",
                    sizes=sizes,
                    family_keys=family_keys,
                    refusals=surface_refusals,
                )
                for row in flat_detail_nodes
            )
            if surface is not None
        ]
        if len(flat_detail) != 2:  # a short list is not the declared two-source null
            flat_detail = []
        flat_scale = [
            surface
            for surface in (
                surface_for(
                    str(row["path"]),
                    "scale",
                    sizes=sizes,
                    family_keys=family_keys,
                    refusals=surface_refusals,
                )
                for row in flat_scale_nodes
            )
            if surface is not None
        ]
        if len(flat_scale) != 2:  # a short list is not the declared two-source null
            flat_scale = []
        descendants = triple["descendants"]
        treatment_descendants = [
            record
            for record in (
                descendants[0],
                descendants[2] if len(descendants) > 2 else descendants[0],
            )
            if record.get("scale") is not None
        ]
        descendant_scale = [
            tree.Surface.from_dict(record["scale"]) for record in treatment_descendants
        ]
        unrelated, control_descendants = unrelated_descendants(
            triples,
            str(triple["parent"]["path"]),
            template=treatment_descendants,
            count=len(treatment_descendants),
            sizes=sizes,
        )
        non_ancestor = [
            tree.Surface.from_dict(record["scale"]) for record in control_descendants
        ]
        non_ancestor_record = {
            "parent_path": (
                str(unrelated["parent"]["path"]) if unrelated is not None else None
            ),
            "relation": (
                "neither is a prefix of the other: the control's parent is not an "
                "ancestor and not a descendant of the treated parent"
                if unrelated is not None
                else (
                    "no complete triple at this level has a parent unrelated to the "
                    "treated parent, so the descendants reading has no non-ancestor "
                    "control here and says so instead of substituting an ancestor, a "
                    "descendant or an equal parent"
                )
            ),
            "paths": [str(record.get("path")) for record in control_descendants],
            "node_classes": [
                str(record.get("node_class")) for record in control_descendants
            ],
            "sizes": [
                int(sizes.get(str(record.get("path")), 0))
                for record in control_descendants
            ],
            "treatment_paths": [
                str(record.get("path")) for record in treatment_descendants
            ],
            "treatment_sizes": [
                int(sizes.get(str(record.get("path")), 0))
                for record in treatment_descendants
            ],
            "class_and_size_matched_to_the_treatment": bool(
                control_descendants
                and len(control_descendants) == len(treatment_descendants)
                and sorted(
                    (
                        str(record.get("node_class")),
                        int(sizes.get(str(record.get("path")), 0)),
                    )
                    for record in control_descendants
                )
                == sorted(
                    (
                        str(record.get("node_class")),
                        int(sizes.get(str(record.get("path")), 0)),
                    )
                    for record in treatment_descendants
                )
            ),
        }
        weights = field_weights(
            int(profile.port_count),
            str(triple["parent"]["path"]),
            [
                int(sizes[str(child["path"])]) if str(child["path"]) in sizes else 0
                for child in triple["children"]
            ],
        )
        try:
            bundle = complete_triple_arms(
                profile,
                settings,
                page,
                catalogue=catalogue,
                triple=triple,
                shuffled=shuffled,
                flat_detail=flat_detail,
                flat_scale=flat_scale,
                descendant_scale=descendant_scale,
                non_ancestor_descendant_scale=non_ancestor,
                weights=weights,
                budget=budget,
                deposit_budget=deposit_budget,
                label=f"scale-composition-{count}-{position}",
            )
        except atlas.FieldIntelligenceError as refusal:
            # Only the field's own declared refusal is recorded as an unavailable row:
            # a programming error is left to propagate rather than being converted into
            # missing evidence that a branch could then be read over.
            rows_refused.append(
                {
                    "position": int(position),
                    "parent_path": str(triple["parent"]["path"]),
                    "surfaces_the_field_refused": surface_refusals,
                    "reason": f"{type(refusal).__name__}: {refusal}",
                    "declared": (
                        "an arm whose source or target surface the field refuses by its "
                        "own rule; the row is recorded here and is neither measured nor "
                        "read as an absent arm, so no reading of this level depends on it"
                    ),
                }
            )
            continue
        arms = bundle["arms"]
        children_sizes = [
            int(sizes.get(str(child["path"]), 0)) for child in triple["children"]
        ]
        flat_record = {
            "source": (
                str(flat_source)
                if len(flat_scale_nodes) == 2
                else "unavailable_at_this_resolution"
            ),
            "surfaces_the_field_refused": surface_refusals,
            "parents_children": child_paths,
            "depth": None if flat_depth is None else int(flat_depth),
            "the_childrens_depth": int(child_depth),
            "depth_matched_to_the_children": bool(
                flat_depth is not None and int(flat_depth) == int(child_depth)
            ),
            "the_pair_is_never_a_single_parents_children": True,
            "size_multiset_matched_to_the_children": bool(
                len(flat_scale_nodes) == 2
                and sorted(
                    int(sizes.get(str(row["path"]), 0)) for row in flat_scale_nodes
                )
                == sorted(child_sizes)
            ),
            "the_nodes_are_not_the_treated_parents_children": bool(
                len(flat_scale_nodes) == 2
                and not any(
                    str(row["path"]) in set(child_paths) for row in flat_scale_nodes
                )
            ),
            "paths": [str(row["path"]) for row in flat_scale_nodes],
            "paths_with_a_detail_mode": [
                str(row["path"]) for row in flat_detail_nodes
            ],
            "node_sizes": [
                int(sizes.get(str(row["path"]), 0)) for row in flat_scale_nodes
            ],
            "children_sizes": children_sizes,
            "the_null_does_not_exist_reason": (
                None
                if len(flat_scale_nodes) == 2
                else (
                    "this level's tree holds no pair of non-sibling nodes outside the "
                    "treated parent's subtree whose port counts match the treated "
                    "children's, so the count-and-budget-matched placement null does not "
                    "exist here and nothing is padded in to stand in for it: the "
                    "placement question is unmeasured at this row and is never read as a "
                    "null result"
                )
            ),
            "detail_null_reason": (
                None
                if len(flat_detail) == 2
                else (
                    "the placement null's pair carries no detail mode on both nodes (a "
                    "single-port node has no detail mode), so the detail-component "
                    "placement null is unavailable at this row"
                )
            ),
            "flat_detail_surfaces": [surface.as_dict() for surface in flat_detail],
            "flat_scale_surfaces": [surface.as_dict() for surface in flat_scale],
            "declared": (
                "the placement null for this runner's readings: the same count and the "
                "same total work written at a non-sibling pair outside the treated "
                "parent's subtree -- the placement that keeps the count, the budget and "
                "the total work and breaks the child relation, and that by construction "
                "is never the shuffled-parent arm's placement"
            ),
        }
        floors = measured_floors(
            arms,
            own=arm_value(arms, "parent_scale_own"),
            no_deposit="no_deposit",
            zero_work="children_scale_zero_work",
            half_pairs={
                "children_scale_home": "children_scale_home_half",
                "children_detail_home": "children_detail_home_half",
                "parent_scale_own": "parent_scale_own_half",
                "child_scale_alone_to_parent_left": "child_scale_alone_to_parent_left_half",
                "child_scale_own_left": "child_scale_own_left_half",
                "descendants_scale_home": "descendants_scale_home_half",
                "magnitude_one_child_scale_whole_budget": (
                    "child_scale_alone_to_parent_left"
                ),
                "delivered_scale_children_home": "delivered_scale_children_home_half",
                "delivered_scale_parent_own": "delivered_scale_parent_own_half",
            },
            epsilon_factor=float(settings.epsilon_factor),
        )
        readings = {
            "R-A_scale_containment_from_the_childrens_declared_detail_surfaces": response_reading(
                arms,
                key="R-A",
                treatment="children_detail_home",
                own="parent_scale_own",
                structural_control="children_detail_shuffled_parent_same_target",
                flat_null="children_detail_flat_null",
                floors=floors,
                spent_declared_floor=spent_level_floor,
                treatment_half="children_detail_home_half",
                own_half="parent_scale_own_half",
                epsilon_factor=float(settings.epsilon_factor),
                floor_factor=float(settings.floor_factor),
                write_budget=float(deposit_budget),
                sweep_prefix="children_detail_sweep",
            ),
            "R-B_scale_containment_from_the_childrens_own_scale_surfaces": response_reading(
                arms,
                key="R-B",
                treatment="children_scale_home",
                own="parent_scale_own",
                structural_control="children_scale_shuffled_parent_same_target",
                flat_null="children_scale_flat_null",
                floors=floors,
                spent_declared_floor=spent_level_floor,
                treatment_half="children_scale_home_half",
                own_half="parent_scale_own_half",
                epsilon_factor=float(settings.epsilon_factor),
                floor_factor=float(settings.floor_factor),
                write_budget=float(deposit_budget),
                sweep_prefix="children_scale_sweep",
            ),
            "R-C_the_field_own_size_weighted_composition_beside_the_probe": field_composition_reading(
                arms,
                key="R-C",
                probe="children_scale_home",
                own="parent_scale_own",
                left_self="child_scale_own_left",
                right_self="child_scale_own_right",
                left_alone="child_scale_alone_to_parent_left",
                right_alone="child_scale_alone_to_parent_right",
                weights=weights,
                floors=floors,
                spent_declared_floor=spent_level_floor,
                treatment_half="children_scale_home_half",
                own_half="parent_scale_own_half",
                epsilon_factor=float(settings.epsilon_factor),
                floor_factor=float(settings.floor_factor),
            ),
            "R-D_magnitude_or_composition_under_a_constant_total_budget": magnitude_reading(
                arms,
                key="R-D",
                two_children="children_scale_home",
                one_child_full_budget="magnitude_one_child_scale_whole_budget",
                one_child_full_budget_right="magnitude_one_child_scale_whole_budget_right",
                flat_null="children_scale_flat_null",
                one_child_probe_budget_left="child_scale_alone_to_parent_left",
                floors=floors,
                spent_declared_floor=spent_level_floor,
                treatment_half="children_scale_home_half",
                own_half="child_scale_alone_to_parent_left",
                epsilon_factor=float(settings.epsilon_factor),
                floor_factor=float(settings.floor_factor),
            ),
            "R-E_descendants_against_a_non_ancestor_source": response_reading(
                arms,
                key="R-E",
                treatment="descendants_scale_home",
                own="parent_scale_own",
                structural_control="descendants_scale_non_ancestor",
                flat_null=None,
                floors=floors,
                spent_declared_floor=spent_level_floor,
                treatment_half="descendants_scale_home_half",
                own_half="parent_scale_own_half",
                epsilon_factor=float(settings.epsilon_factor),
                floor_factor=float(settings.floor_factor),
            ),
        }
        delivered = response_reading(
            arms,
            key="R-B",
            treatment="delivered_scale_children_home",
            own="delivered_scale_parent_own",
            structural_control="delivered_scale_children_shuffled_same_target",
            flat_null="delivered_scale_children_flat_null",
            floors=floors,
            spent_declared_floor=spent_level_floor,
            treatment_half="delivered_scale_children_home_half",
            own_half="delivered_scale_parent_own_half",
            epsilon_factor=float(settings.epsilon_factor),
            floor_factor=float(settings.floor_factor),
        )
        delivered["reading"] = (
            "R-B-delivered the spent receipt's aggregation companion re-taken with the "
            "controls it lacked"
        )
        delivered["the_shape"] = "no_sweep_declared_for_this_path"
        delivered["the_shape_declared"] = (
            "this companion re-takes the spent receipt's aggregation arms with the "
            "controls it lacked, on the same geometry as R-B; the declared budget sweep is "
            "taken on R-B's own arms, and this re-take states that absence rather than "
            "borrowing their shape.  It is reported beside the branch and is not read as "
            "evidence for it"
        )
        delivered["reference_child_own_response"] = arm_value(
            arms, "delivered_scale_child_own"
        )
        delivered["delivered_budget"] = float(deposit_budget)
        row = {
            "position": int(position),
            "parent_path": str(triple["parent"]["path"]),
            "parent_depth": int(triple["parent"]["depth"]),
            "parent_size": int(triple["parent"]["size"]),
            "triple_class": str(triple["triple_class"]),
            "shuffled_parent_path": (
                str(shuffled["parent"]["path"]) if shuffled is not None else None
            ),
            "children_paths": [str(child["path"]) for child in triple["children"]],
            "parent_scale_surface": triple["parent"]["scale"],
            "children_scale_surfaces": [child["scale"] for child in triple["children"]],
            "flat_null": flat_record,
            "descendant_surfaces": [surface.as_dict() for surface in descendant_scale],
            "non_ancestor_descendant_surfaces": [
                surface.as_dict() for surface in non_ancestor
            ],
            "non_ancestor_control": non_ancestor_record,
            "fields_own_composition_weights": weights,
            "arms": arms,
            "arms_present": bundle["arms_present"],
            "arms_absent": bundle["arms_absent"],
            "floor": floors,
            "readings": readings,
            "the_spent_aggregation_companion_re_taken": delivered,
        }
        rows.append(row)
    for position in port_positions:
        triple = triples[position]
        shuffled = tree.shuffled_parent(triples, position)
        others: list[Any] = []
        for row in nodes:
            path = str(row["path"])
            if int(row["size"]) != 1:
                continue
            if path in {str(child["path"]) for child in triple["children"]}:
                continue
            others.append(
                tree.scale_surface(
                    path, size=1, family_keys=family_keys
                )
            )
        try:
            bundle = leaf_triple_arm(
                profile,
                settings,
                page,
                triple=triple,
                shuffled=shuffled,
                other_ports=others,
                budget=budget,
                deposit_budget=deposit_budget,
                label=f"scale-composition-{count}-port-{position}",
            )
        except atlas.FieldIntelligenceError as refusal:
            # As above: the field's declared refusal only.
            port_rows_refused.append(
                {
                    "position": int(position),
                    "parent_path": str(triple["parent"]["path"]),
                    "reason": f"{type(refusal).__name__}: {refusal}",
                    "declared": (
                        "a port arm whose surface the field refuses by its own rule; the "
                        "row is recorded here and is not read as an absent arm"
                    ),
                }
            )
            continue
        arms = bundle["arms"]
        floors = measured_floors(
            arms,
            own=arm_value(arms, "port_parent_scale_own"),
            no_deposit="port_no_deposit",
            zero_work="port_children_scale_zero_work",
            half_pairs={
                "port_children_scale_home": "port_children_scale_home_half",
                "port_parent_scale_own": "port_parent_scale_own_half",
                "port_children_scale_delivered_budget": (
                    "port_children_scale_home"
                ),
            },
            epsilon_factor=float(settings.epsilon_factor),
        )
        port_rows.append(
            {
                "position": int(position),
                "parent_path": str(triple["parent"]["path"]),
                "triple_class": str(triple["triple_class"]),
                "children_paths": [str(child["path"]) for child in triple["children"]],
                "shuffled_parent_path": (
                    str(shuffled["parent"]["path"]) if shuffled is not None else None
                ),
                "other_ports_tried": int(len(others)),
                "arms": arms,
                "arms_present": bundle["arms_present"],
                "arms_absent": bundle["arms_absent"],
                "floor": floors,
                "readings": {
                    "R-F_leaf_port_fallback_against_a_different_port": response_reading(
                        arms,
                        key="R-F",
                        treatment="port_children_scale_home",
                        own="port_parent_scale_own",
                        structural_control="port_other_ports_same_target",
                        flat_null="port_children_shuffled_parent",
                        floors=floors,
                        spent_declared_floor=spent_level_floor,
                        treatment_half="port_children_scale_home_half",
                        own_half="port_parent_scale_own_half",
                        epsilon_factor=float(settings.epsilon_factor),
                        floor_factor=float(settings.floor_factor),
                    )
                },
            }
        )
    readings: dict[str, Any] = {}
    for key in (
        "R-A_scale_containment_from_the_childrens_declared_detail_surfaces",
        "R-B_scale_containment_from_the_childrens_own_scale_surfaces",
        "R-C_the_field_own_size_weighted_composition_beside_the_probe",
        "R-D_magnitude_or_composition_under_a_constant_total_budget",
        "R-E_descendants_against_a_non_ancestor_source",
    ):
        readings[key] = aggregate_reading(key, rows)
    readings["R-F_leaf_port_fallback_against_a_different_port"] = aggregate_reading(
        "R-F_leaf_port_fallback_against_a_different_port", port_rows
    )
    readings["R-B-delivered"] = aggregate_reading(
        "R-B", rows, accessor="the_spent_aggregation_companion_re_taken"
    )
    readings["counts"] = {
        "rows_measured": int(len(rows)),
        "port_rows_measured": int(len(port_rows)),
        "triples_in_the_level": int(len(triples)),
        "complete_triples_in_the_level": int(
            catalogue["classes"]["complete"]
        ),
        "leaf_child_triples_in_the_level": int(catalogue["classes"]["leaf_child"]),
        "rows_with_a_structural_control": int(
            sum(
                1
                for row in rows
                for record in row["readings"].values()
                if record.get("the_structural_control_exists")
            )
        ),
        "rows_with_a_flat_null": int(
            sum(
                1
                for row in rows
                for record in row["readings"].values()
                if record.get("the_flat_null_exists")
            )
        ),
    }
    branch, reason, predicates = level_branch(rows, port_rows, readings)
    record = {
        "the_suppressing_term": predicates.get("suppression"),
        "n": int(count),
        "ports_per_pool": int(resolution),
        "constructible": True,
        "declared_levels": {
            "complete_triples_measured": [int(row["position"]) for row in rows],
            "leaf_child_triples_measured": [
                int(row["position"]) for row in port_rows
            ],
            "probe_budget": float(budget),
            "delivered_write_budget": float(deposit_budget),
            "epsilon_factor": float(settings.epsilon_factor),
            "floor_factor_of_the_spent_receipt": float(settings.floor_factor),
            "spent_receipt_declared_floor_used_beside_the_measured_one": spent_level_floor,
        },
        "field_own_compositions": [
            row["fields_own_composition_weights"] for row in rows
        ],
        "measured": rows,
        "port_fallback_measured": port_rows,
        "rows_the_field_refused": rows_refused,
        "port_rows_the_field_refused": port_rows_refused,
        "readings": readings,
        "branch": str(branch),
        "branch_reason": str(reason),
        "branch_predicates": predicates,
        "runtime_seconds": float(time.perf_counter() - started),
        "delivered_item_list_restored": bool(
            tuple(durability.ITEM_SPECS) == tree.DELIVERED_ITEM_SPECS
        ),
    }
    return record


def aggregate_reading(
    key: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    accessor: str = "readings",
) -> dict[str, Any]:
    """One reading's level aggregate: the shapes, the floors, and the separations.

    The aggregate publishes no single-budget verdict either.  It counts what shape
    each measured row's declared sweep is, which of the two floor terms of the
    spent receipt's rule bound at each sweep point, and how many rows' structural
    separations cleared the published terms; every row stays published beside it.
    """

    records: list[dict[str, Any]] = []
    for row in rows:
        if accessor == "readings":
            for name, record in row.get("readings", {}).items():
                if str(name).startswith(str(key)):
                    records.append(record)
        else:
            record = row.get(accessor)
            if isinstance(record, Mapping):
                records.append(record)
    if not records:
        return {
            "reading": str(key),
            "rows_measured": 0,
            "declared": "no row of this level measured this reading",
        }
    floors = [float(record["floor"]) for record in records if record.get("floor") is not None]
    treatment = [
        float(record["treatment_response"])
        for record in records
        if record.get("treatment_response") is not None
    ] if "treatment_response" in records[0] else [
        float(record["probe_response"])
        for record in records
        if record.get("probe_response") is not None
    ]
    fractions = [
        abs(float(record["fraction_of_the_own_response"]))
        for record in records
        if record.get("fraction_of_the_own_response") is not None
    ]
    shapes = [
        str((record.get("the_shape") or record.get("budget_sweep", {}).get("the_shape") or "not_measured"))
        for record in records
    ]
    sweep_points = [
        point
        for record in records
        for point in (record.get("budget_sweep") or {}).get("points", [])
    ]
    separations = [
        record.get("the_structural_separation") or {} for record in records
    ]
    return {
        "reading": str(records[0].get("reading", key)),
        "taken_at": str(records[0].get("taken_at", "")),
        "carries_the_branch": bool(records[0].get("carries_the_branch", False)),
        "declared": (
            "the row-type of this reading's record across the level's measured rows: the "
            "shapes the declared budget sweeps imply, both floor terms of the spent "
            "receipt's rule at every sweep point with the term that bound there, the "
            "structural separations against the published terms, the floor range with its "
            "binding terms, and the greatest fraction of the own response, with every row "
            "published beside it.  No aggregate here is a single-budget verdict"
        ),
        "rows_measured": int(len(records)),
        "the_shapes_seen": sorted(set(shapes)),
        "rows_whose_sweep_shows_a_plateau_above_the_numerical_term": int(
            sum(1 for shape in shapes if shape == "plateau_above_the_numerical_term")
        ),
        "rows_whose_sweep_keeps_climbing_with_the_drive": int(
            sum(1 for shape in shapes if shape == "still_climbing_with_the_drive")
        ),
        "rows_whose_sweep_is_under_the_numerical_term": int(
            sum(1 for shape in shapes if shape == "under_the_numerical_term")
        ),
        "rows_whose_sweep_is_missing": int(
            sum(
                1
                for shape in shapes
                if shape in ("not_measured", "no_sweep_declared_for_this_path")
            )
        ),
        "the_plateaus": [
            {
                "row_index": int(index),
                "from_budget_multiple": (
                    (record.get("budget_sweep") or {}).get("the_plateau") or {}
                ).get("from_budget_multiple"),
                "value": (
                    (record.get("budget_sweep") or {}).get("the_plateau") or {}
                ).get("value"),
                "numerical_term_compared_with": (
                    (record.get("budget_sweep") or {}).get("the_plateau") or {}
                ).get("numerical_term_compared_with"),
                "the_first_multiple_the_declared_rule_admits": (
                    (record.get("budget_sweep") or {}).get("the_plateau") or {}
                ).get("the_first_multiple_the_declared_rule_admits"),
                "the_declared_rule_admits_the_plateau": (
                    (record.get("budget_sweep") or {}).get("the_plateau") or {}
                ).get("the_declared_rule_admits_the_plateau"),
            }
            for index, record in enumerate(records)
            if (record.get("budget_sweep") or {}).get("the_plateau") is not None
        ],
        "the_two_floor_terms_over_every_sweep_point": {
            "half_budget_difference_times_the_factor": sorted(
                {
                    float(
                        point["the_two_floor_terms"][
                            "half_budget_difference_times_the_factor"
                        ]
                    )
                    for point in sweep_points
                    if point["the_two_floor_terms"][
                        "half_budget_difference_times_the_factor"
                    ]
                    is not None
                }
            ),
            "numerical_term_epsilon_times_the_own_response": sorted(
                {
                    float(
                        point["the_two_floor_terms"][
                            "numerical_term_epsilon_times_the_own_response"
                        ]
                    )
                    for point in sweep_points
                    if point["the_two_floor_terms"][
                        "numerical_term_epsilon_times_the_own_response"
                    ]
                    is not None
                }
            ),
        },
        "the_binding_terms_over_every_sweep_point": sorted(
            {
                str(point["the_binding_term_at_this_point"])
                for point in sweep_points
                if point.get("the_binding_term_at_this_point") is not None
            }
        ),
        "sweep_points_where_the_declared_rule_admits": int(
            sum(
                1
                for point in sweep_points
                if point.get("the_rule_admits_at_this_point")
            )
        ),
        "sweep_points_measured": int(len(sweep_points)),
        "rows_with_a_measured_structural_control": int(
            sum(1 for record in records if record.get("the_structural_control_exists"))
        ),
        "rows_whose_structural_separation_exceeds_the_numerical_term": int(
            sum(1 for record in separations if record.get("exceeds_the_numerical_term"))
        ),
        "rows_whose_structural_separation_exceeds_the_measured_floor": int(
            sum(1 for record in separations if record.get("exceeds_the_measured_floor"))
        ),
        "rows_whose_structural_separation_exceeds_the_comparison_floor": int(
            sum(
                1
                for record in separations
                if record.get("exceeds_the_comparison_floor")
            )
        ),
        "rows_with_a_flat_null": int(
            sum(1 for record in records if record.get("the_flat_null_exists"))
        ),
        "rows_with_a_count_test_separation": int(
            sum(1 for record in records if record.get("count_test_separates"))
        ),
        "floor_range": {
            "lowest": float(min(floors)) if floors else None,
            "greatest": float(max(floors)) if floors else None,
        },
        "floor_binding_terms": sorted(
            {str(record.get("floor_binding_term")) for record in records}
        ),
        "greatest_fraction_of_the_own_response": (
            float(max(fractions)) if fractions else None
        ),
        "least_fraction_of_the_own_response": (
            float(min(fractions)) if fractions else None
        ),
        "greatest_treatment_response": float(max(treatment)) if treatment else None,
        "least_treatment_response": float(min(treatment)) if treatment else None,
        "rows": records,
    }


def level_branch(
    rows: Sequence[Mapping[str, Any]],
    port_rows: Sequence[Mapping[str, Any]],
    readings: Mapping[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    """The declared branch rule, evaluated over the level's own rows."""

    def rows_of(key: str, source: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for row in source:
            for name, record in row.get("readings", {}).items():
                if str(name).startswith(str(key)):
                    found.append(record)
        return found

    b = rows_of("R-B", rows)
    a = rows_of("R-A", rows)
    c = rows_of("R-C", rows)
    d = rows_of("R-D", rows)
    e = rows_of("R-E", rows)
    f = rows_of("R-F", port_rows)

    def majority(values: Sequence[bool]) -> bool:
        return bool(values) and sum(1 for value in values if value) * 2 > len(values)

    def any_true(values: Sequence[bool]) -> bool:
        return bool(values) and any(values)

    arms_finite = all(
        (
            row.get("arms") is not None
            and all(
                arm is None
                or all(
                    np.isfinite(float(value))
                    for value in arm["differences"].values()
                )
                for arm in row["arms"].values()
            )
        )
        for row in [*rows, *port_rows]
    )
    controls_fire = bool(
        b and all(record.get("the_positive_control_fires") for record in [*a, *b])
    )
    scale_shapes = [
        str(record.get("the_shape")) for record in [*a, *b]
    ]
    plateau_rows = [
        shape == "plateau_above_the_numerical_term" for shape in scale_shapes
    ]
    climbing_rows = [shape == "still_climbing_with_the_drive" for shape in scale_shapes]
    silent_rows = [shape == "under_the_numerical_term" for shape in scale_shapes]
    sweep_taken = [
        shape not in ("not_measured", "no_sweep_declared_for_this_path")
        for shape in scale_shapes
    ]
    weight_agreement = [
        bool(
            record.get("the_ratio_matches_the_fields_own_weight", {}).get("left")
            or record.get("the_ratio_matches_the_fields_own_weight", {}).get("right")
        )
        for record in c
    ]
    unweighted = [
        bool(
            record.get("the_ratio_is_one_an_unweighted_accumulation", {}).get("left")
            or record.get("the_ratio_is_one_an_unweighted_accumulation", {}).get("right")
        )
        for record in c
    ]
    placement_irrelevant = [
        bool(record.get("the_placement_does_not_matter")) for record in d
    ]
    placement_matters = [bool(record.get("the_placement_matters")) for record in d]
    counts_matter = [
        bool(record.get("the_count_matters_at_a_constant_total_budget"))
        for record in d
    ]
    counts_irrelevant = [
        bool(record.get("the_count_does_not_matter_at_a_constant_total_budget"))
        for record in d
    ]
    count_tests_available = [
        record.get("the_count_matters_at_a_constant_total_budget") is not None
        for record in d
    ]
    scale_records = [*a, *b]
    # One vote per *row*, not per surface: a row counts where its scale path carries a
    # declared sweep and a measured structural control, and it counts as separated
    # where the treatment differs from that control by more than the published terms.
    # An absent arm, a refused control, and a row whose sweep is missing leave the
    # denominator rather than voting against the surface.
    adjudicable_rows = [
        [
            record
            for name, record in row.get("readings", {}).items()
            if str(name).startswith(("R-A", "R-B"))
            and str(record.get("the_shape"))
            not in ("not_measured", "no_sweep_declared_for_this_path")
            and record.get("the_structural_control_exists")
        ]
        for row in rows
    ]
    measured_rows = [records for records in adjudicable_rows if records]
    separated_given_measured = [
        any(
            bool((record.get("the_structural_separation") or {}).get("exceeds_the_comparison_floor"))
            for record in records
        )
        for records in measured_rows
    ]
    sweep_points = [
        point
        for record in scale_records
        for point in (record.get("budget_sweep") or {}).get("points", [])
    ]
    the_sweep = {
        "the_shapes_seen": sorted(set(scale_shapes)),
        "rows_whose_sweep_shows_a_plateau_above_the_numerical_term": int(
            sum(1 for value in plateau_rows if value)
        ),
        "rows_whose_sweep_keeps_climbing_with_the_drive": int(
            sum(1 for value in climbing_rows if value)
        ),
        "rows_whose_sweep_is_under_the_numerical_term": int(
            sum(1 for value in silent_rows if value)
        ),
        "rows_whose_sweep_is_missing": int(
            sum(1 for value in sweep_taken if not value)
        ),
        "the_plateaus": [
            {
                "row_index": int(index),
                "from_budget_multiple": (
                    (record.get("budget_sweep") or {}).get("the_plateau") or {}
                ).get("from_budget_multiple"),
                "value": (
                    (record.get("budget_sweep") or {}).get("the_plateau") or {}
                ).get("value"),
                "numerical_term_compared_with": (
                    (record.get("budget_sweep") or {}).get("the_plateau") or {}
                ).get("numerical_term_compared_with"),
                "the_first_multiple_the_declared_rule_admits": (
                    (record.get("budget_sweep") or {}).get("the_plateau") or {}
                ).get("the_first_multiple_the_declared_rule_admits"),
                "the_declared_rule_admits_the_plateau": (
                    (record.get("budget_sweep") or {}).get("the_plateau") or {}
                ).get("the_declared_rule_admits_the_plateau"),
            }
            for index, record in enumerate(scale_records)
            if (record.get("budget_sweep") or {}).get("the_plateau") is not None
        ],
        "the_two_floor_terms_over_every_sweep_point": {
            "half_budget_difference_times_the_factor": sorted(
                {
                    float(
                        point["the_two_floor_terms"][
                            "half_budget_difference_times_the_factor"
                        ]
                    )
                    for point in sweep_points
                    if point["the_two_floor_terms"][
                        "half_budget_difference_times_the_factor"
                    ]
                    is not None
                }
            ),
            "numerical_term_epsilon_times_the_own_response": sorted(
                {
                    float(
                        point["the_two_floor_terms"][
                            "numerical_term_epsilon_times_the_own_response"
                        ]
                    )
                    for point in sweep_points
                    if point["the_two_floor_terms"][
                        "numerical_term_epsilon_times_the_own_response"
                    ]
                    is not None
                }
            ),
        },
        "the_binding_terms_over_every_sweep_point": sorted(
            {
                str(point["the_binding_term_at_this_point"])
                for point in sweep_points
                if point.get("the_binding_term_at_this_point") is not None
            }
        ),
        "sweep_points_measured": int(len(sweep_points)),
        "sweep_points_where_the_declared_rule_admits": int(
            sum(
                1
                for point in sweep_points
                if point.get("the_rule_admits_at_this_point")
            )
        ),
        "the_declared_rule_admits_the_plateaus": bool(
            any(
                ((record.get("budget_sweep") or {}).get("the_plateau") or {}).get(
                    "the_declared_rule_admits_the_plateau"
                )
                for record in scale_records
            )
        ),
        "the_declared_rule_rejects_a_reading_still_climbing_with_the_drive_by_construction": bool(
            any(climbing_rows)
        ),
        "declared": (
            "the declared budget sweep, row by row: which shape each sweep implies, the "
            "plateau and the numerical term it is compared with, both floor terms of the "
            "spent receipt's rule at every point with the term that bound there, and how "
            "many points the declared rule admits.  The rule reduces to a statement about "
            "shape rather than size: a reading that moves with the drive has "
            "|v - v_half| comparable to |v| and so cannot clear the half-budget term, "
            "while a reading that has stopped moving has that term at or below the "
            "numerical term and is judged on the numerical term alone.  No verdict here is "
            "stated as a floor hiding a response, and no single budget point carries a "
            "verdict"
        ),
    }
    predicates = {
        "every_arm_is_finite": bool(arms_finite),
        "the_positive_controls_fire_on_every_row": controls_fire,
        "R-A_or_R-B_reading_has_a_sweep_and_a_measured_control_and_separates": bool(
            any(separated_given_measured)
        ),
        "R-A_or_R-B_separates_from_its_control_on_a_majority_of_measured_rows": majority(
            separated_given_measured
        ),
        "the_propagation_ratio_matches_the_fields_own_weight_at_a_majority": majority(
            weight_agreement
        ),
        "the_propagation_ratio_is_one_at_a_majority": majority(unweighted),
        "the_placement_does_not_matter_on_every_row": bool(
            placement_irrelevant
        ) and all(placement_irrelevant),
        "the_placement_matters_on_a_majority_of_rows": majority(placement_matters),
        "compound_separation_from_the_structural_controls_and_the_field_weights": bool(
            all(
                record.get("difference_from_the_structural_control") is not None
                and float(record["difference_from_the_structural_control"]) > 0.0
                for record in [*a, *b]
            )
        ),
        "the_sweep_shapes_seen": sorted(set(scale_shapes)),
        "the_sweep": the_sweep,
        "the_descendant_path_has_a_non_ancestor_control": majority(
            [bool(record.get("the_structural_control_exists")) for record in e]
        ),
        "rows_where_the_descendant_path_has_a_non_ancestor_control": int(
            sum(
                1 for record in e if bool(record.get("the_structural_control_exists"))
            )
        ),
        "rows_where_the_descendant_path_was_measured": int(len(e)),
        "the_port_path_has_a_different_port_control": majority(
            [bool(record.get("the_structural_control_exists")) for record in f]
        ),
        "rows_where_the_port_path_has_a_different_port_control": int(
            sum(
                1 for record in f if bool(record.get("the_structural_control_exists"))
            )
        ),
        "rows_where_the_port_path_was_measured": int(len(f)),
    }
    field_gap = {
        "rows_with_a_probe": int(len(c)),
        "closest_predictions": sorted(
            {str(record.get("closest_prediction")) for record in c}
        ),
        "predictions_within_the_measured_floor": sorted(
            {
                str(name)
                for record in c
                for name in (record.get("predictions_within_the_floor") or [])
            }
        ),
        "per_child_propagation_ratios": [
            record.get("per_child_propagation_ratio") for record in c
        ],
        "field_weights_per_child": [
            record.get("field_weight_per_child") for record in c
        ],
        "rows_whose_ratio_matches_the_fields_own_weight": int(
            sum(1 for value in weight_agreement if value)
        ),
        "rows_whose_ratio_is_one": int(sum(1 for value in unweighted if value)),
        "declared": (
            "the physical firing control's own result: which of the candidate "
            "compositions the store's exposed scale surface tracks -- the field's "
            "size-weighted composition of the children's scale responses, the "
            "unweighted sum of them, or a linear magnitude -- and the per-child "
            "propagation ratio beside the field's own weight for the same child.  Any "
            "gap between the field's internal composition and its exposed surface is "
            "named here rather than smoothed over, and it is a caveat on the branch "
            "verdict rather than a reason to withhold one"
        ),
    }
    predicates["the_gap_between_the_field_composition_and_the_exposed_surface"] = (
        field_gap
    )
    controls_measured = [
        bool(
            record.get("the_structural_control_exists")
            and record.get("the_flat_null_exists")
        )
        for record in scale_records
    ]
    matched_nulls = [
        bool(
            str(row.get("flat_null", {}).get("source"))
            != "unavailable_at_this_resolution"
            and row.get("flat_null", {}).get(
                "size_multiset_matched_to_the_children"
            )
            and row.get("flat_null", {}).get(
                "the_nodes_are_not_the_treated_parents_children"
            )
        )
        for row in rows
    ]
    matched_rows = int(
        sum(
            1
            for row in rows
            if any(
                record.get("the_structural_control_exists")
                for name, record in row.get("readings", {}).items()
                if str(name).startswith(("R-A", "R-B"))
            )
            and any(
                record.get("the_count_matters_at_a_constant_total_budget") is not None
                for name, record in row.get("readings", {}).items()
                if str(name).startswith("R-D")
            )
        )
    )
    predicates[
        "the_structural_controls_and_the_flat_null_are_measured_on_a_majority_of_rows"
    ] = majority(controls_measured)
    predicates[
        "the_placement_null_is_size_matched_and_not_the_parents_children_on_a_majority_of_rows"
    ] = majority(matched_nulls)
    predicates["rows_carrying_a_measured_control_and_a_matched_placement_null"] = (
        matched_rows
    )
    predicates[
        "at_least_two_rows_carry_a_measured_structural_control_and_a_count_test"
    ] = bool(matched_rows >= MIN_MATCHED_ROWS)
    predicates["the_count_matters_at_a_constant_total_budget_on_a_majority_of_rows"] = (
        majority(counts_matter)
    )
    predicates["rows_where_the_scale_path_carries_a_declared_sweep_and_a_control"] = int(
        len(measured_rows)
    )
    predicates["rows_where_that_reading_separates_from_its_control"] = int(
        sum(1 for value in separated_given_measured if value)
    )
    predicates[
        "the_scale_reading_separates_from_its_control_at_a_majority_of_the_rows_where_it_is_measured"
    ] = majority(separated_given_measured)
    predicates["sweep_shape_by_path"] = {
        "R-A_declared_detail_surfaces": {
            "the_shapes": sorted(
                {str(record.get("the_shape")) for record in a}
            ),
            "rows_measured": int(len(a)),
        },
        "R-B_childrens_own_scale_surfaces": {
            "the_shapes": sorted(
                {str(record.get("the_shape")) for record in b}
            ),
            "rows_measured": int(len(b)),
        },
        "declared": (
            "an arm that is absent at a row is reported as absent and never as a "
            "counter-example: the structural separation the branch reads is taken over "
            "the rows where the path carries a declared sweep and its control is measured, "
            "and the shape of each row's sweep is published beside it"
        ),
    }
    predicates[
        "the_count_does_not_matter_at_a_constant_total_budget_on_every_row"
    ] = bool(d) and all(counts_irrelevant)
    predicates["the_count_test_is_available_on_every_row"] = bool(d) and all(
        count_tests_available
    )
    predicates["the_placement_question_is_unmeasured_at_this_level"] = {
        "measured_rows_with_a_matched_placement_null": int(
            sum(1 for value in matched_nulls if value)
        ),
        "rows_the_level_measured": int(len(rows)),
        "declared": (
            "the extra placement null -- a non-sibling pair outside the treated "
            "parent's subtree with the children's own port counts -- asks whether the "
            "same count and total work placed anywhere else in the tree also moves the "
            "parent's scale surface.  Where the level's tree holds no such pair the "
            "question is unmeasured and is reported as unmeasured here: the branch "
            "verdict rests on the count test at a constant total budget and on the "
            "shuffled-parent control, neither of which needs this null"
        ),
    }
    predicates["the_placement_null_that_was_declared"] = {
        "construction": (
            "the same count and the same per-source budget written at a pair of nodes "
            "that are not siblings of each other, are not any of the treated parent's "
            "children, and lie outside the treated parent's subtree, read at the treated "
            "parent's own scale surface"
        ),
        "why_it_is_matched": (
            "the pair's port counts match the treated children's as a multiset, so the "
            "same count and the same total work are written"
        ),
        "why_it_is_not_the_shuffled_parent_arm": (
            "two nodes that are not siblings of one another cannot be the two children "
            "of any single parent, so this placement can never coincide with the "
            "shuffled-parent control's placement, and the two controls are not the same "
            "measurement counted twice"
        ),
        "rows_where_it_exists": int(sum(1 for value in matched_nulls if value)),
        "rows_the_level_measured": int(len(rows)),
        "when_it_does_not_exist": (
            "where the level's tree holds no such pair at any depth, the null is "
            "declared unavailable, the placement question is recorded as unmeasured at "
            "that row, and no reading of this level treats it as a null result"
        ),
    }
    predicates["the_size_weighting_is_the_fields_own"] = majority(weight_agreement)
    predicates["the_size_weighting_is_an_unweighted_accumulation"] = majority(
        unweighted
    )
    if not predicates["every_arm_is_finite"]:
        return (
            "inconclusive",
            "an arm returned a non-finite readout or is missing: the level's numbers "
            "are not usable, and no branch is claimed",
            predicates,
        )
    if not predicates["the_positive_controls_fire_on_every_row"]:
        return (
            "inconclusive",
            "a positive control is at its own measured floor on at least one row: the "
            "surface did not respond to a deposit at its own surface there, so no "
            "comparison above that floor is available at this level",
            predicates,
        )
    treatment_measured = [
        record.get("treatment_response") is not None for record in scale_records
    ]
    sweeps_taken = [
        shape
        for shape in scale_shapes
        if shape not in ("not_measured", "no_sweep_declared_for_this_path")
    ]
    scale_shaped = bool(sweeps_taken) and not all(
        shape == "under_the_numerical_term" for shape in sweeps_taken
    )
    if not sweeps_taken and not any(treatment_measured):
        return (
            "inconclusive",
            "the treatment's own arm was not built at any row of this level, so its "
            "zero is vacuous and is not read as 'no response': the surface did not "
            "answer this question here, and the vacuity is published with each row's "
            "reading",
            predicates,
        )
    if not scale_shaped:
        return (
            "not_measurable_in_this_path",
            "the scale-surface reading sits at or below the numerical term "
            "epsilon * |its own control| at every declared budget of every row of this "
            "level: silent, and bounded by that term.  Both floor terms of the spent "
            "receipt's rule are published separately at every sweep point beside the "
            "shape, and the bound is stated -- what would have to be built is a surface "
            "whose reading plateaus above its own read noise at some declared drive, or a "
            "non-readout observation channel",
            predicates,
        )
    placement_measured = bool(
        predicates[
            "the_placement_null_is_size_matched_and_not_the_parents_children_on_a_majority_of_rows"
        ]
        and predicates[
            "at_least_two_rows_carry_a_measured_structural_control_and_a_count_test"
        ]
    )
    magnitude_by_placement = bool(
        d
        and placement_measured
        and predicates["the_placement_does_not_matter_on_every_row"]
        and all(
            record.get("responses", {}).get("two_deposits_at_the_flat_null_surfaces")
            is not None
            for record in d
        )
    )
    magnitude_by_controls = bool(
        scale_records
        and predicates[
            "the_structural_controls_and_the_flat_null_are_measured_on_a_majority_of_rows"
        ]
        and not any(separated_given_measured)
    )
    # The count test is a self-contained controlled comparison -- two placements of
    # the same total work at the treated parent's own children -- so a magnitude
    # verdict may rest on it without borrowing evidence from a control that this
    # level did not measure.  It requires both of its own arms on every row, which
    # ``the_count_test_is_available_on_every_row`` reports.
    magnitude_by_counts = bool(
        d
        and predicates["the_count_test_is_available_on_every_row"]
        and predicates[
            "the_count_does_not_matter_at_a_constant_total_budget_on_every_row"
        ]
    )
    shape_caveat = (
        "the sweeps at this level show a plateau above the numerical term at "
        f"{predicates['the_sweep']['rows_whose_sweep_shows_a_plateau_above_the_numerical_term']}"
        " of "
        f"{predicates['the_sweep']['rows_whose_sweep_shows_a_plateau_above_the_numerical_term'] + predicates['the_sweep']['rows_whose_sweep_keeps_climbing_with_the_drive']}"
        " measured sweeps, and the declared two-term rule admits such a plateau, from the "
        "multiple named in the plateau record onward, because its half-budget term has "
        "fallen to the numerical term there; the rule is "
        "mis-shaped for a reading that still scales, not a statement that such a reading "
        "is absent"
        if predicates["the_sweep"][
            "rows_whose_sweep_shows_a_plateau_above_the_numerical_term"
        ]
        else (
            "the sweep keeps CLIMBING WITH THE DRIVE at every declared point at "
            f"{predicates['the_sweep']['rows_whose_sweep_keeps_climbing_with_the_drive']}"
            " rows, so the reading's magnitude is a budget artifact and the branch does "
            "not rest on it: the declared two-term rule rejects that shape by "
            "construction, because a reading that moves with the drive has |v - v_half| "
            "comparable to |v|.  The branch rests on the structural separation from the "
            "shuffled-parent arm and on the count test at a constant total budget, both "
            "of which are insensitive to the children's deposit budget by construction.  "
            if predicates["the_sweep"]["rows_whose_sweep_keeps_climbing_with_the_drive"]
            else (
                "no row of this level carries a declared sweep shape, so no shape caveat "
                "is claimed"
            )
        )
    )
    composition_evidence = bool(
        scale_records
        and scale_shaped
        and predicates[
            "at_least_two_rows_carry_a_measured_structural_control_and_a_count_test"
        ]
        and majority(separated_given_measured)
        and majority(counts_matter)
    )
    if composition_evidence:
        detail_path = (
            "the declared-detail path carries no declared sweep at any row of this "
            "level and is reported as absent rather than as a counter-example; "
            if not [
                shape
                for shape in predicates["sweep_shape_by_path"][
                    "R-A_declared_detail_surfaces"
                ]["the_shapes"]
                if shape not in ("not_measured", "no_sweep_declared_for_this_path")
            ]
            else ""
        )
        caveat = (
            detail_path
            + "the per-child propagation ratio is the field's own size weight at a "
            "majority of rows as well"
            if predicates["the_size_weighting_is_the_fields_own"]
            else (
                "the caveat is measured and named rather than withheld: the per-child "
                "propagation ratio is NOT the field's own size weight on a majority of "
                "rows (see "
                "the_gap_between_the_field_composition_and_the_exposed_surface), so the "
                "surface composes from its own children by the store's own rule rather "
                "than by the field's packet-analysis rule"
            )
        )
        return (
            "the_scale_surface_composes_from_its_children",
            "the scale surface responds to which children were written: at a majority of "
            "the rows where a treatment is present and its structural control is "
            "measured, the treated parent's scale surface separates from the "
            "shuffled-parent arm by more than the published terms, and at every measured "
            "row the count test at a constant total budget separates too -- two children "
            "written at the write budget each are not the same response as one child "
            "written at twice it.  The declared budget sweep is named beside it: "
            + shape_caveat
            + "  The verdict is scoped to the scale surfaces this "
            "level measured: the fields' aggregation companion has no control at this "
            "level at all, the descendant question has a non-ancestor control on "
            f"{predicates['rows_where_the_descendant_path_has_a_non_ancestor_control']}"
            f" of {predicates['rows_where_the_descendant_path_was_measured']} rows, and "
            "the port-fallback question on "
            f"{predicates['rows_where_the_port_path_has_a_different_port_control']} of "
            f"{predicates['rows_where_the_port_path_was_measured']} port rows -- each is "
            "reported beside the branch and none of them is read as evidence for it.  "
            + caveat,
            predicates,
        )
    if magnitude_by_counts or magnitude_by_placement or magnitude_by_controls:
        return (
            "the_scale_surface_is_a_magnitude_surface",
            (
                "two children written at the level's write budget each and one child "
                "written at twice that budget -- the same total work, one child instead "
                "of two -- give the same response within the measured floor at every "
                "measured row: with the total work held constant the surface answers how "
                "much and not which or how many children"
                if magnitude_by_counts
                else (
                    "with the same total budget the children's placement and the "
                    "placement null give the same response within the measured floor: the "
                    "surface answers how much and not which children"
                    if magnitude_by_placement
                    else (
                        "the treatment has a declared sweep and the structural controls "
                        "exist and are read on a majority of rows, and none of them "
                        "separates from the treatment above the published terms: the "
                        "surface answers how much and not which children, with the shape "
                        "of the sweep published beside the verdict"
                    )
                )
            ),
            predicates,
        )
    return (
        "inconclusive",
        "the treatment has a declared sweep at this level but neither the composition evidence "
        "nor the magnitude evidence is measured on a majority of rows, so the "
        "structural question is untested here: a missing control is never read as "
        "evidence for either surface.  The named missing evidence is published with the "
        "predicates, and the per-row responses, floors and controls are beside it",
        predicates,
    )


def block(
    resolution: int,
    counts: Sequence[int],
    *,
    name: str,
    budget_seconds: float,
    levels_override: Sequence[int] | None = None,
) -> dict[str, Any]:
    """One declared block: its census, its levels, and its own content digest."""

    started = time.perf_counter()
    pins = check_pins()
    tree_receipt = load_pinned_tree_receipt()
    audit = spent_receipt_audit(load_pinned_tree_blocks(), summary=tree_receipt)
    run_counts = tuple(int(value) for value in (levels_override or counts))
    profile, profile_record = capacity.resolution_profile(int(resolution))
    family = capacity.declared_family(int(profile.port_count))
    specs: tuple[durability.ItemSpec, ...] = family["specs"]
    block_settings = rank.AddressingRankConfig(
        item_indices=tuple(range(len(specs))),
        store_config=replace(
            rank.AddressingRankConfig().store_config,
            item_indices=tuple(range(len(specs))),
            neutrality_probe_items=(),
        ),
    )
    levels: dict[str, Any] = {}
    points_run: list[int] = []
    points_not_run: list[dict[str, Any]] = []
    points_not_constructible: list[dict[str, Any]] = []
    with capacity.family_installed(specs):
        captures, gain, phase_degrees, per_item = rank.hold_settings(
            profile, block_settings
        )
        hold_settings = {
            "captures": captures,
            "gain": float(gain),
            "phase_degrees": float(phase_degrees),
            "per_item": per_item,
        }
        installed = int(len(durability.ITEM_SPECS))
        elapsed = time.perf_counter() - started
        for count in run_counts:
            if float(elapsed) >= float(budget_seconds):
                points_not_run.append(
                    {
                        "n": int(count),
                        "reason": (
                            f"the block's declared wall-clock budget "
                            f"({budget_seconds:g} s) was already spent ({elapsed:.1f} s) "
                            "when this level's turn came"
                        ),
                    }
                )
                continue
            spent_floor = spent_declared_floor(audit, int(resolution), int(count))
            record = level_block(
                profile,
                int(count),
                resolution=int(resolution),
                hold_settings=hold_settings,
                spent_level_floor=spent_floor,
            )
            levels[str(count)] = record
            if bool(record.get("constructible")):
                points_run.append(int(count))
            else:
                points_not_constructible.append(
                    {"n": int(count), "reason": str(record.get("reason"))}
                )
            elapsed = time.perf_counter() - started
    record = {
        "schema": BLOCK_SCHEMA,
        "block": str(name),
        "resolution": int(resolution),
        "declared_counts": [int(value) for value in run_counts],
        "levels_override_used": (
            None if levels_override is None else [int(value) for value in levels_override]
        ),
        "profile": profile_record,
        "census": {
            "declared_rule": str(family["declared_rule"]),
            "port_count": int(family["port_count"]),
            "nodes": int(family["nodes"]),
            "declared_family_size": int(len(specs)),
            "head_matches_the_delivered_item_specs": bool(
                family["head_matches_the_delivered_item_specs"]
            ),
        },
        "delivered_item_list_restored": bool(
            tuple(durability.ITEM_SPECS) == tree.DELIVERED_ITEM_SPECS and installed == tree.DELIVERED_ITEM_COUNT
        ),
        "block_hold_settings": {
            "gain": float(hold_settings["gain"]),
            "phase_degrees": float(hold_settings["phase_degrees"]),
            "items_captured": int(installed),
            "captured_deposits": {
                str(capture["name"]): float(capture["deposited_energy"])
                for capture in hold_settings["captures"]
            },
            "declared": (
                "the block's own hold settings, taken from rank.hold_settings on the "
                "full declared family: the held page every arm of every level is "
                "measured on, so arms compare within a level and not across levels"
            ),
        },
        "pins": pins,
        "spent_receipt_audit": audit,
        "declared": {
            "question": (
                "is the store's scale surface a composition surface -- a function of "
                "which children were written -- or a magnitude surface?"
            ),
            "branch_rule": BRANCH_RULE,
            "branches": list(BRANCHES),
            "readings": {
                key: {
                    "name": value["name"],
                    "taken_at": value["taken_at"],
                    "carries_the_branch": value["carries_the_branch"],
                    "structural_control": value["structural_control"],
                    "flat_null": value["flat_null"],
                }
                for key, value in DECLARED_READINGS.items()
            },
            "floor_rule": DECLARED_FLOOR_RULE,
            "reading_lexicon": READING_LEXICON,
            "the_spent_receipts_reading_lexicon": SPENT_READING_LEXICON,
            "measured_triple_cap": int(MEASURED_TRIPLE_CAP),
            "port_fallback_cap": int(PORT_FALLBACK_CAP),
            "arms_per_complete_triple": 31,
            "arms_per_leaf_child_triple": 8,
            "declared_cost_cap_seconds_per_block": float(BLOCK_BUDGET_SECONDS),
            "this_block_budget_seconds": float(budget_seconds),
            "no_re_run_of_the_tree_runner": (
                "nothing here runs run_store_addressing_tree: its declarations are "
                "imported at the pinned source digest and its finished receipt is read "
                "at its pinned content digest"
            ),
        },
        "levels": levels,
        "points_run": points_run,
        "points_not_run": points_not_run,
        "points_not_constructible": points_not_constructible,
        "level_runtimes_seconds": {
            key: float(value.get("runtime_seconds", 0.0))
            for key, value in levels.items()
        },
        "declared_budget_seconds": float(budget_seconds),
        "runtime_seconds": float(time.perf_counter() - started),
    }
    record["content_digest"] = scale.receipt_digest(record)
    return record


def spent_declared_floor(
    audit: Mapping[str, Any], resolution: int, count: int
) -> float | None:
    """The spent receipt's own declared floor at this resolution and count."""

    for key, entry in audit["per_level"].items():
        if int(entry["n"]) != int(count) or int(entry["ports_per_pool"]) != int(resolution):
            continue
        record = entry["companions"]["companion_containment_scale"]
        values = [float(value) for value in record["declared_floor_values"]]
        if values:
            return float(min(values))
    return None


def merge_blocks(blocks: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The merged receipt: every block's rows in one table, with the verdicts."""

    rows: list[dict[str, Any]] = []
    for name, record in blocks.items():
        for level_name, level in record["levels"].items():
            if not bool(level.get("constructible")):
                rows.append(
                    {
                        "block": str(name),
                        "n": int(level_name),
                        "ports_per_pool": int(record["resolution"]),
                        "constructible": False,
                        "reason": str(level.get("reason")),
                    }
                )
                continue
            readings = level["readings"]
            rows.append(
                {
                    "block": str(name),
                    "n": int(level_name),
                    "ports_per_pool": int(record["resolution"]),
                    "constructible": True,
                    "runtime_seconds": float(level["runtime_seconds"]),
                    "branch": str(level["branch"]),
                    "rows_measured": int(readings["counts"]["rows_measured"]),
                    "port_rows_measured": int(readings["counts"]["port_rows_measured"]),
                    "R-A": subset(readings, "R-A"),
                    "R-B": subset(readings, "R-B"),
                    "R-B-delivered": subset(readings, "R-B-delivered"),
                    "R-C": subset(readings, "R-C"),
                    "R-D": subset(readings, "R-D"),
                    "R-E": subset(readings, "R-E"),
                    "R-F": subset(readings, "R-F"),
                    "count_test_separates": bool(
                        level.get("branch_predicates", {}).get(
                            "the_count_matters_at_a_constant_total_budget_on_a_majority_of_rows"
                        )
                    ),
                    "placement_null_rows": int(
                        (
                            level.get("branch_predicates", {}).get(
                                "the_placement_question_is_unmeasured_at_this_level"
                            )
                            or {}
                        ).get("measured_rows_with_a_matched_placement_null")
                        or 0
                    ),
                    "sweep_shape_by_path": level.get("branch_predicates", {}).get(
                        "sweep_shape_by_path"
                    ),
                    "the_sweep": level.get("branch_predicates", {}).get("the_sweep"),
                    "descendant_control_measured": (
                        f"{level.get('branch_predicates', {}).get('rows_where_the_descendant_path_has_a_non_ancestor_control')}"
                        f"/{level.get('branch_predicates', {}).get('rows_where_the_descendant_path_was_measured')}"
                    ),
                    "port_control_measured": (
                        f"{level.get('branch_predicates', {}).get('rows_where_the_port_path_has_a_different_port_control')}"
                        f"/{level.get('branch_predicates', {}).get('rows_where_the_port_path_was_measured')}"
                    ),
                }
            )
    branch_counts: dict[str, int] = {name: 0 for name in BRANCHES}
    for row in rows:
        if row.get("constructible"):
            branch_counts[str(row["branch"])] += 1
    first = next(iter(blocks.values()))
    return {
        "schema": SCHEMA,
        "question": (
            "is the store's scale surface a composition surface or a magnitude surface?"
        ),
        "declared": dict(first["declared"]),
        "pins": first["pins"],
        "spent_receipt_audit": first["spent_receipt_audit"],
        "blocks": {
            name: {
                "resolution": int(record["resolution"]),
                "declared_counts": list(record["declared_counts"]),
                "points_run": list(record["points_run"]),
                "points_not_run": list(record["points_not_run"]),
                "points_not_constructible": list(record["points_not_constructible"]),
                "level_runtimes_seconds": dict(record["level_runtimes_seconds"]),
                "runtime_seconds": float(record["runtime_seconds"]),
                "content_digest": str(record["content_digest"]),
            }
            for name, record in blocks.items()
        },
        "table": rows,
        "branch_counts": branch_counts,
        "the_declared_budget_sweep": the_declared_budget_sweep(rows),
        "report": report_lines(rows, blocks),
    }


def the_declared_budget_sweep(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The merged receipt's own sweep block: the ladder, the rule, and the shapes.

    The user-facing deliverable of this runner is this table rather than any verdict
    at one drive: the declared ladder, every level's scale-path sweep published as a
    table, the plateau each level reached (or the statement that the ladder never
    reached one), both floor terms of the spent receipt's rule published separately
    beside the points, and the shape the whole sweep is.
    """

    levels: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("constructible"):
            continue
        sweep = row.get("the_sweep") or {}
        r_b = row.get("R-B") or {}
        levels.append(
            {
                "block": str(row.get("block")),
                "n": int(row.get("n")),
                "branch": str(row.get("branch")),
                "the_shapes_seen": sweep.get("the_shapes_seen"),
                "the_plateaus": sweep.get("the_plateaus") or [],
                "the_numerical_term_term_present": bool(
                    (
                        sweep.get("the_two_floor_terms_over_every_sweep_point") or {}
                    ).get("numerical_term_epsilon_times_the_own_response")
                ),
                "the_two_floor_terms_over_every_sweep_point": sweep.get(
                    "the_two_floor_terms_over_every_sweep_point"
                ),
                "sweep_points_measured": sweep.get("sweep_points_measured"),
                "sweep_points_where_the_declared_rule_admits": sweep.get(
                    "sweep_points_where_the_declared_rule_admits"
                ),
                "the_binding_terms_over_every_sweep_point": sweep.get(
                    "the_binding_terms_over_every_sweep_point"
                ),
                "rows_whose_sweep_shows_a_plateau_above_the_numerical_term": sweep.get(
                    "rows_whose_sweep_shows_a_plateau_above_the_numerical_term"
                ),
                "rows_whose_sweep_keeps_climbing_with_the_drive": sweep.get(
                    "rows_whose_sweep_keeps_climbing_with_the_drive"
                ),
                "rows_whose_sweep_is_under_the_numerical_term": sweep.get(
                    "rows_whose_sweep_is_under_the_numerical_term"
                ),
                "the_scale_reading_separated_rows": (
                    f"{r_b.get('rows_whose_structural_separation_exceeds_the_comparison_floor')}"
                    f"/{r_b.get('rows_with_a_measured_structural_control')}"
                ),
            }
        )
    shapes = sorted(
        {
            str(shape)
            for level in levels
            for shape in (level["the_shapes_seen"] or [])
        }
    )
    return {
        "declared": (
            "the declared budget sweep is the deliverable: the ladder "
            f"{list(SWEEP_MULTIPLES)} times the level's own write budget, swept at every "
            "measured row of both scale paths, with the two floor terms of the spent "
            "receipt's rule published separately at every point rather than folded into a "
            "max, the plateau and the numerical term it is compared with, and the shape "
            "the whole sweep is.  No single budget point carries a verdict in this "
            "receipt"
        ),
        "sweep_multiples": [float(value) for value in SWEEP_MULTIPLES],
        "the_declared_rule": (
            "|v| > max(FLOOR_FACTOR * |v - v_half|, EPS_FACTOR * |own|), the spent "
            "receipt's own two-term rule"
        ),
        "the_rule_worked_out_on_paper": (
            "a reading that scales with the drive has |v - v_half| = |v| / 2, so the "
            "half-budget term becomes FLOOR_FACTOR / 2 times the reading and the reading "
            "can never clear it; a reading that has stopped moving between neighbouring "
            "budgets has that term at or below EPS_FACTOR * |own| and is judged on the "
            "numerical term alone.  The rule is therefore a statement about the reading's "
            "shape, and it rejects a reading that still scales by construction -- a "
            "different statement from the reading being absent"
        ),
        "the_shapes_seen": shapes,
        "levels": levels,
        "the_shape_classification": {
            "plateau_above_the_numerical_term": (
                "composition evidence, and the shape the declared rule admits"
            ),
            "still_climbing_with_the_drive": (
                "a budget artifact for the reading's magnitude; the branch rests on the "
                "structural separation and the count test, which do not scale with the "
                "drive"
            ),
            "under_the_numerical_term": (
                "silent, and bounded by epsilon times the row's own control"
            ),
            "not_measured": "an arm of the sweep is missing at that row",
        },
        "rows_the_declared_rule_admits": int(
            sum(
                int(level["sweep_points_where_the_declared_rule_admits"] or 0)
                for level in levels
            )
        ),
    }


def subset(readings: Mapping[str, Any], key: str) -> dict[str, Any]:
    """One reading's numeric summary, without its per-row records."""

    record = next(
        (
            value
            for name, value in readings.items()
            if isinstance(value, dict)
            and (str(name) == str(key) or str(name).startswith(str(key) + "_"))
        ),
        None,
    ) or {}
    sweep = {
        "the_shapes_seen": record.get("the_shapes_seen")
        or [record.get("the_shape")],
        "the_plateaus": record.get("the_plateaus") or [],
        "the_binding_terms_over_every_sweep_point": record.get(
            "the_binding_terms_over_every_sweep_point"
        )
        or [],
        "sweep_points_where_the_declared_rule_admits": record.get(
            "sweep_points_where_the_declared_rule_admits"
        ),
        "sweep_points_measured": record.get("sweep_points_measured"),
        "the_two_floor_terms_over_every_sweep_point": record.get(
            "the_two_floor_terms_over_every_sweep_point"
        )
        or {},
    }
    return {
        "reading": record.get("reading"),
        "rows_measured": record.get("rows_measured"),
        "the_shapes_seen": sweep.get("the_shapes_seen"),
        "the_plateaus": sweep.get("the_plateaus"),
        "sweep_points_measured": sweep.get("sweep_points_measured"),
        "sweep_points_where_the_declared_rule_admits": sweep.get(
            "sweep_points_where_the_declared_rule_admits"
        ),
        "the_binding_terms_over_every_sweep_point": sweep.get(
            "the_binding_terms_over_every_sweep_point"
        ),
        "the_two_floor_terms_over_every_sweep_point": sweep.get(
            "the_two_floor_terms_over_every_sweep_point"
        ),
        "rows_with_a_measured_structural_control": record.get(
            "rows_with_a_measured_structural_control"
        ),
        "rows_whose_structural_separation_exceeds_the_comparison_floor": record.get(
            "rows_whose_structural_separation_exceeds_the_comparison_floor"
        ),
        "rows_whose_structural_separation_exceeds_the_numerical_term": record.get(
            "rows_whose_structural_separation_exceeds_the_numerical_term"
        ),
        "rows_with_a_flat_null": record.get("rows_with_a_flat_null"),
        "greatest_fraction_of_the_own_response": record.get(
            "greatest_fraction_of_the_own_response"
        ),
        "floor_range": record.get("floor_range"),
        "floor_binding_terms": record.get("floor_binding_terms"),
        "greatest_treatment_response": record.get("greatest_treatment_response"),
        "rows": record.get("rows"),
    }


def _number(value: Any) -> str:
    """One sweep figure, printed at the precision the sweep is read at."""

    if value is None:
        return "absent"
    return f"{float(value):.6g}"


def report_lines(
    rows: Sequence[Mapping[str, Any]], blocks: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    lines: list[str] = []
    lines.append("the spent receipt's companions, audited before this runner's first arm:")
    audit = next(iter(blocks.values()))["spent_receipt_audit"]
    for key, companions in audit["levels_where_a_zero_is_vacuous"].items():
        lines.append(f"  {key}: vacuous zeros at {', '.join(companions) or 'none'}")
    for key, companions in audit["levels_where_the_structural_question_was_untested"].items():
        lines.append(
            f"  {key}: structural question untested for {', '.join(companions) or 'none'}"
        )
    for row in rows:
        if not row.get("constructible"):
            lines.append(f"{row['block']} N={row['n']}: not constructible")
            continue
        lines.append(
            f"{row['block']} N={row['n']}: branch {row['branch']} "
            f"(R-B rows {row['R-B'].get('rows_measured')} with sweeps "
            f"{row['R-B'].get('the_shapes_seen')} "
            f"separated "
            f"{row['R-B'].get('rows_whose_structural_separation_exceeds_the_comparison_floor')}/"
            f"{row['R-B'].get('rows_with_a_measured_structural_control')} of the rows with a "
            f"measured control, plateau at "
            f"{[p.get('from_budget_multiple') for p in (row['R-B'].get('the_plateaus') or [])]}, "
            f"declared rule admits "
            f"{row['R-B'].get('sweep_points_where_the_declared_rule_admits')}/"
            f"{row['R-B'].get('sweep_points_measured')} sweep points, "
            f"floor range {row['R-B'].get('floor_range')!r} "
            f"binding {row['R-B'].get('floor_binding_terms')}, "
            f"R-F rows {row['R-F'].get('rows_measured')} with control "
            f"{row['R-F'].get('rows_with_a_measured_structural_control')}, "
            f"{row['runtime_seconds']:.1f} s)"
        )
        for label in ("R-A", "R-B"):
            record = row.get(label) or {}
            for index, sweep_row in enumerate(record.get("rows") or []):
                points = (sweep_row.get("budget_sweep") or {}).get("points") or []
                if not points:
                    continue
                table = " | ".join(
                    f"x{point['budget_multiple']}: "
                    f"{_number(point['treatment_response'])} vs own "
                    f"{_number(point['own_positive_control'])}, half "
                    f"{_number(point['the_two_floor_terms']['half_budget_difference_times_the_factor'])}, "
                    f"num "
                    f"{_number(point['the_two_floor_terms']['numerical_term_epsilon_times_the_own_response'])}"
                    for point in points
                )
                lines.append(
                    f"    sweep {label} row {index}: shape "
                    f"{sweep_row.get('the_shape')} "
                    f"(plateau "
                    f"{(sweep_row.get('budget_sweep') or {}).get('the_plateau') or 'none'})"
                )
                lines.append(f"      {table}")
        lines.append(
            "    scope: the branch is read from the scale surfaces only "
            f"((R-A shapes {(row.get('sweep_shape_by_path') or {}).get('R-A_declared_detail_surfaces', {}).get('the_shapes')}, "
            f"R-B shapes {(row.get('sweep_shape_by_path') or {}).get('R-B_childrens_own_scale_surfaces', {}).get('the_shapes')}); "
            f"count test separates {row.get('count_test_separates')}; "
            f"matched placement null on {row.get('placement_null_rows')} of "
            f"{row.get('rows_measured')} rows; "
            f"non-ancestor descendant control measured {row.get('descendant_control_measured')}; "
            f"different-port control measured {row.get('port_control_measured')}"
        )
    return lines


def report(receipt: Mapping[str, Any]) -> str:
    lines = ["scale-composition-surface: the scale surface, composition or magnitude"]
    lines.extend(str(line) for line in receipt["report"])
    lines.append(f"branch counts: {receipt['branch_counts']}")
    for name, record in receipt["blocks"].items():
        lines.append(
            f"block {name}: resolution {record['resolution']} points {record['points_run']} "
            f"runtime {record['runtime_seconds']:.1f} s digest {record['content_digest']}"
        )
    lines.append(f"receipt_digest: {receipt['receipt_digest']}")
    return "\n".join(lines)


def write_json(path: Path, body: Mapping[str, Any]) -> None:
    """One receipt on disk, canonically ordered."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(body, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


FORBIDDEN_RECEIPT_WORDS = ("proportional",)


def words_the_declared_rule_rejects(receipt: Mapping[str, Any]) -> list[str]:
    """Refuse to publish a receipt carrying a word the declared rule rejects.

    The declared two-term rule rejects a reading that scales with the drive by
    construction, so a receipt that describes such a reading as *proportional* would
    be naming the shape as though it were the finding.  The scan is recursive over
    the serialized receipt -- including the spent-receipt audit and every nested
    declaration -- and is checked here, at the only place the receipt is written.
    """

    serialized = json.dumps(receipt, default=str).lower()
    return [word for word in FORBIDDEN_RECEIPT_WORDS if word in serialized]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--block",
        choices=[*BLOCK_PATHS, "merge"],
        default="merge",
        help="which declared block to run, or merge the finished blocks",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--levels",
        default=None,
        help=(
            "development override: a comma-separated item-count list, recorded in the "
            "receipt; the declared run uses the declared levels"
        ),
    )
    parser.add_argument("--budget-seconds", type=float, default=BLOCK_BUDGET_SECONDS)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="read the receipt on disk and print its report without measuring",
    )
    arguments = parser.parse_args(argv)
    if arguments.report_only:
        body = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        print(report(body))
        return 0
    if arguments.block == "merge":
        blocks: dict[str, Any] = {}
        for name, path in BLOCK_PATHS.items():
            if not path.exists():
                raise SystemExit(
                    f"the declared block {name!r} has not run: {path} is missing"
                )
            blocks[name] = json.loads(path.read_text(encoding="utf-8"))
        receipt = merge_blocks(blocks)
        rejected = words_the_declared_rule_rejects(receipt)
        if rejected:
            raise SystemExit(
                "the merged receipt carries a word the declared rule rejects: "
                + ", ".join(rejected)
            )
        receipt["receipt_digest"] = scale.receipt_digest(receipt)
        output = Path(arguments.output) if arguments.output else RECEIPT_PATH
        write_json(output, receipt)
        print(report(receipt))
        print(f"wrote {output}")
        return 0
    resolution, counts = BLOCK_SPECS[str(arguments.block)]
    override = (
        None
        if arguments.levels is None
        else tuple(int(value) for value in str(arguments.levels).split(","))
    )
    record = block(
        resolution,
        counts,
        name=arguments.block,
        budget_seconds=float(arguments.budget_seconds),
        levels_override=override,
    )
    rejected = words_the_declared_rule_rejects(record)
    if rejected:
        raise SystemExit(
            "the block receipt carries a word the declared rule rejects: "
            + ", ".join(rejected)
        )
    output = Path(arguments.output) if arguments.output else BLOCK_PATHS[arguments.block]
    write_json(output, record)
    print(
        f"block {arguments.block}: resolution {resolution}, points run {record['points_run']}"
    )
    for row in record["points_not_run"]:
        print(f"  not run: N={row['n']}: {row['reason']}")
    for n, level in sorted(record["levels"].items(), key=lambda item: int(item[0])):
        if not bool(level.get("constructible")):
            print(f"  N={n}: not constructible: {level['reason']}")
            continue
        readings = level["readings"]
        print(
            f"  N={n}: rows {readings['counts']['rows_measured']} port rows "
            f"{readings['counts']['port_rows_measured']} branch {level['branch']} "
            f"({level['runtime_seconds']:.1f} s)"
        )
    print(f"content_digest: {record['content_digest']}")
    print(f"runtime_seconds: {record['runtime_seconds']:.2f}")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
