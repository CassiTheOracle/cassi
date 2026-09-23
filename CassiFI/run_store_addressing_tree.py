"""Does the store's scale tree act as a tree, or is the addressing flat under a tree-shaped address space?

DECLARED BEFORE THE FIRST RUN -- surfaces and their addressability, the four
readings with their floors and normalizations, the controls, the branch rule
with four named branches, the axes, the blocks and the budget.

THE QUESTION.  The capacity receipt measured the declared family's inventory and
found that the addressable count is the port count -- 28 at four ports per pool,
56 at eight -- with every level's placement map full rank and every pair
separated at the predicted value.  What it never asked is whether the *tree*
carries meaning: a tree of addresses can be a flat list wearing a tree's
clothes, every node an independent cell with no relation to the nodes beneath
it.  This runner asks whether the store's addressing is hierarchical, and it
answers at the surfaces the field actually exposes.

THE FIELD-EXPOSED SURFACES, AND WHICH OF THEM IS AN ADDRESS.  Every figure in
this receipt is taken through the owner's own packet surface and nothing else:

    write   owner.write_packet_impulse(operation_id, path=, component=,
            flow_signal=, work_budget=)                  -- one owner transition
    read    owner.read_packet_deposit(path=, component=, flow_signal=)
            -> recovered_deposit                          -- a readout, no transition

The read publishes ``readout_kind: "temporal-prediction"`` and
``evidence_added: False``: it is a field-exposed API readout declared as a
temporal prediction of the canonical page, *not* an admitted observation.  No
figure in this receipt is an observation.  The receipt labels every surface:

    declared_item           the surface the store's declared family addresses:
                            the root's scale mode and every interior node's
                            detail mode (the capacity runner's own family rule,
                            reused verbatim -- ``run_store_addressing_capacity``)
    field_exposed_undeclared  a surface the field's own API executes but the
                            declared family does not address as an item: a
                            node's *scale* mode anywhere below the root, and a
                            single-port node's scale mode, which is that port
                            itself
    constructed             any aggregate, ratio or normalization this runner
                            builds from readouts -- never a branch verdict on
                            its own

Addressability is measured, not assumed: every parent's declared detail surface
is *executed* (one write, one read) and the outcome recorded per path; every
child that is a single-port node is executed at its detail surface (the field's
own refusal is recorded verbatim) and at its port/scale surface.

PER-READING SURFACE DECLARATION.  ``READING_SURFACES`` is declared before the
first run and published in the receipt (``declared.reading_surfaces``, and in
each block), and every published reading carries its own row of it beside its
numbers: ``taken_at`` (the field-exposed surface the value is taken at),
``node_class`` (the node class of the path that surface sits at),
``declared_item`` (whether that surface is a declared item of the family, with a
``declared_item_scope`` where the answer is path-sensitive), ``observed`` and
``constructed`` (no reading here is an observation: each is a construction over
the field's own readouts), and ``carries_the_branch``.  The authority for
``declared_item`` is one function -- ``capacity.declared_family(port_count)
['specs']`` -- and the pass that labels the address space is measured, not
assumed: every path's detail and scale surfaces are probed once and each probed
surface carries its own ``declared_family_item`` flag beside its outcome.  Two
path-sensitive facts are published rather than smoothed over: the root's *scale*
mode is family item 0 and is a declared item while every other node's scale mode
is field-exposed and undeclared, and the root's scale item is not a parent
because it has no children, so the root parent's own surface is its *detail*
mode, family item 1.

THE NODE CLASSES, MEASURED PER LEVEL.  A parent is a declared interior node in
the level's item set; its left and right children are classified by path:

    declared_detail   the child is a declared item of this level -- both its
                      detail and scale surfaces are field-exposed
    declared_beyond   the child is a declared item of the family but its index
                      is past this level's count: the reading is not available
                      at this count (a count limitation, recorded, not a failure)
    leaf_port         the child's support is a single port: the field refuses
                      its detail mode by its own rule ("a leaf packet has no
                      detail mode") and its scale mode is that one port
    beyond_leaf       the path descends beyond a leaf: not a node at all

THE FOUR READINGS.  Each is a response of one field-exposed surface to a
deposit at others, measured on the level's own held page (the declared items
written through the owner write path at the delivered write budget and held for
the declared horizon -- the delivered operating point), one fresh owner per arm:

  R1 containment   response at the parent's declared item surface to deposits at
                   its children's declared item surfaces, divided by the parent's
                   own response to a deposit at its own surface.  Statistic
                   ``containment_fraction``; the treatment, the shuffled control
                   and the flat null are measured on the same page at the same
                   budget.
  R2 aggregation   the deposit reading: the children deposited alone at the
                   delivered store write budget and the parent's surface read,
                   divided by the mean of what each child's own surface reads
                   when it is deposited alone at that budget.  Statistic
                   ``aggregation_fraction``.
  R3 sibling       response at one child's declared item surface to a deposit at
                   its sibling's, against the same measurement for two items
                   that are not siblings, each divided by the child's own
                   response to a deposit at its own surface.  Statistics
                   ``sibling_fraction`` and ``non_sibling_fraction``.
  R4 descent       response at the child's declared item surface to a deposit at
                   its parent's surface, divided by the parent's own response at
                   its own surface, against the flat null (the same measurement
                   with the source at a surface that is not an ancestor of the
                   child).  Statistic ``descent_fraction``.

  R1s--R2s companion  the containment and aggregation readings again with the
                   parent's *scale* surface as the target and the children's
                   *scale* surfaces as the sources: the field-exposed surface
                   where the field's own packet analysis composes a node's
                   summary from its children
                   (``cassi_resonant_field._packet_analyze``: a node's scale
                   coefficient is the size-weighted sum of its children's).
                   This is a field-exposed surface the store does not declare as
                   an item, so the companion readings are published with their
                   own predicates and do **not** carry the branch verdict.  The
                   companion is scoped to these two readings; the scale-surface
                   sibling and descent arms are not measured here.

  R5 descendants     a supplementary reading, admittedly constructed: the same
                   containment statistic with the deposits placed two levels
                   *below* the parent -- this level's grandchildren, which are
                   the parent's children's children and the same physical
                   intervals' children at the paired resolution -- at the
                   parent's own declared item surface, with its own half-budget
                   floor.  A path that is not a node at this resolution has no
                   surface here and is recorded, never written.  It does not
                   carry the branch verdict; it says whether a placement two
                   levels down reaches a declared surface, which the four
                   readings alone cannot see.

DECLARED FLOORS AND NORMALIZATIONS.  Every response reading is a finite
difference at the delivered probe budget (``run_store_addressing_rank``'s
``PROBE_BUDGET``, 1e-3), and carries its own measured floor:

    response_floor = max(FLOOR_FACTOR * |r(a) - r(a/2)|, EPS_FACTOR * |r_own|)

the first term the level's own finite-difference floor measured by re-running
the same arm at half budget, the second the declared numerical floor relative to
the arm's own positive control, with the delivered ``FLOOR_FACTOR`` and
``EPS_FACTOR``.  A reading is ``at_the_floor`` when its magnitude is at or below
that floor, ``present`` when it is above it, ``assignment_specific`` when the
treatment differs from the shuffled control by more than the floor, and
``counts_only`` when a present reading does not differ from the flat null by
more than the floor.  The deposit reading (R2) is a magnitude reading at the
delivered store write budget, not a finite difference; it is normalized by the
children's own deposits and carries the same EPS_FACTOR scale floor.

DECLARED CONTROLS.  Every predicate has a control that can fail:
  * positive control: the parent's own deposit at its own surface must be above
    the floor -- if it is not, the level is unreadable and the reading is
    recorded as such rather than as a zero;
  * zero-work probe: a write at zero work must be rejected and must move no read
    (measured once per triple);
  * blank page: a fresh owner's blank page reads nothing at any surface (once
    per block, over every surface the block addresses);
  * duplicate, from the rank pair: the children's contents written twice at one
    child's surface must not separate from the single write -- the two responses
    must agree within the containment reading's own measured floor.  That floor
    is reused deliberately: the duplicate arm is the same measurement shape (a
    response at the parent's declared item surface to deposits at child item
    surfaces at the same budget), and a *relative* test against the single
    write's own magnitude would degenerate to ``0 <= 0`` whenever every response
    is exactly zero;
  * shared, from the rank pair: every source written at one shared surface must
    give that surface's own response, and the same measured floor is used;
  * the shuffled control: the same contents attached to a parent they were not
    built from (the next complete triple's parent in the declared order, same
    depth, never the treated parent) -- it must *change* a present reading for
    the tree relation to be readable at all;
  * the flat null: the same number of items written at surfaces that are not
    siblings of one another and not the treated children -- the deepest declared
    level's two non-sibling items in the level's own order, so any reading
    attributable to node count alone is visible.
  * cross-resolution leg: the same placement patterns measured at both
    resolutions, each on a page held under *its own* resolution's profile; no
    surface is relabelled onto another resolution's page.  For every parent path
    named by either block the receipt publishes that resolution's own reading
    kind (at the floor or present), that path's own node class, and an explicit
    status where a resolution does not measure the pattern at all -- its
    children's surfaces do not exist there, its children are past that level's
    count, or the declared cap did not select it.  A pattern measured at both
    resolutions must give the same kind of reading at both; a refused-path
    census is published alongside it as a surface cross-check, not as the
    control.

DECLARED BRANCH RULE -- one of four, returned per level and across levels:

  the_tree_is_structural                at least one declared-item-surface
                                        reading is present and
                                        assignment_specific at every level where
                                        it is available, and no control fails
  the_tree_is_decorative                every declared-item-surface reading is
                                        at its floor at every level, and every
                                        shuffled and flat arm is at its floor:
                                        the declared addresses are independent
                                        cells and the tree is a labelling of a
                                        flat basis
  no_field_exposed_parent_surface_exists  the *parent* itself has no executable
                                        field surface at any level, so
                                        containment is not measurable here.
                                        Declared with equal standing and
                                        *tested*: the test is the parent's own
                                        declared detail write and read executed
                                        per parent, and a parent can only fail
                                        it if the field refuses its detail mode,
                                        which its own rule does only for a
                                        single-port node -- and a single-port
                                        node has no children.  The branch is
                                        therefore reported as tested, with the
                                        measured count of parents whose detail
                                        surface executed
  inconclusive                          anything else: a control failed, a
                                        positive control did not fire, or a
                                        reading is present without being
                                        assignment_specific (a placement-geometry
                                        artifact)

  A child's detail refusal is *not* this branch: it is recorded per reading as a
  surface limitation, with the port/scale fallback reading labelled, and that
  labelled reading does not carry the branch verdict on its own.

  The branch is taken on R1--R4 at the declared item surfaces only.  R5
  descendants and the scale-surface companion are published beside it with their
  own numbers and their own predicates; neither can decide the branch, and both
  are named in the receipt wherever they are reported.

AXES, BLOCKS AND BUDGET.  Axis 1 is the declared item count, axis 2 the profile
resolution (``ports_per_pool``) built by the delivered builder at that
resolution exactly as the capacity runner builds it.  The blocks are declared in
this order and each publishes its measured runtime:

    declared-profile     resolution 4, items 8, 16, 24, 28 -- 28 is the whole
                         addressable family at that resolution
    higher-resolution    resolution 8, items 32 -- where the same paths that are
                         single-port leaves at resolution 4 are interior nodes

Each block carries a declared wall-clock budget of 4200 s; a level that does not
fit is recorded as not run with its projected cost rather than shortened.  Every
receipt is content-stable: the store-scale runner's declared content digest,
reused rather than re-derived, with its declared clock leaves stripped.  No git
operation is performed anywhere in this runner.

DECLARED COST CAP AND PORT FALLBACK, fixed before the first run.  Arms are
counted against owners, and one owner costs on the order of 1.6 s on this rig, so
a level's cost is bounded by the number of triples it measures rather than by
shortening any reading:

    MEASURED_TRIPLE_CAP = 6      a level measures its complete triples up to six,
                                 taken from the head and the tail of the level's
                                 own declared order (the first three and the last
                                 three), so a capped level still measures its
                                 shallowest and its deepest complete parents.  The
                                 receipt publishes complete_triples (how many the
                                 level has) beside triples_measured (how many were
                                 read), and every at-the-floor count is stated
                                 against triples_measured;
    PORT_FALLBACK_CAP = 2        a level measures at most two of its
                                 single-port-child triples at the port/scale
                                 surfaces -- the child's own port is that
                                 surface -- recorded with the field's own refusal
                                 text from the surface table.  Those readings are
                                 labelled field-exposed-undeclared and never carry
                                 the branch verdict.

With the cap the declared levels measure: resolution 4 at 8, 16, 24 and 28 items
3, 6 (7 complete), 6 (9 complete) and 6 (11 complete) complete triples, and
resolution 8 at 32 items 6 (15 complete); each complete triple costs 26 arms and
each level adds at most two port-fallback triples at 3 arms, so the largest
level is about 162 owners, four minutes on this rig -- inside the envelope the
capacity runner's own per-level cost set (its 32-port-pool jacobian level cost
265 s with 32 owners per arm).  Every level's measured runtime is published
beside its projected cost in the receipt.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import cassi_resonant_field as resonant
import run_fractal_durability_exploration as durability
import run_fractal_metric_exploration as metric
import run_memory_consumer_path as consumer
import run_memory_store_scale as scale
import run_owner_surface_options as opts
import run_store_addressing_capacity as capacity
import run_store_addressing_rank as rank

SCHEMA = "cassifi.store-addressing-tree.v1"
BLOCK_SCHEMA = "cassifi.store-addressing-tree.block.v1"
RECEIPT_PATH = Path("_diag/store-addressing-tree/exploration.json")
BLOCK_PATHS: dict[str, Path] = {
    "declared-profile": Path("_diag/store-addressing-tree/block-declared-profile.json"),
    "higher-resolution": Path("_diag/store-addressing-tree/block-higher-resolution.json"),
}
BLOCK_SPECS: dict[str, tuple[int, tuple[int, ...]]] = {
    "declared-profile": (4, (8, 16, 24, 28)),
    "higher-resolution": (8, (32,)),
}
RESOLUTION_LEVELS: tuple[tuple[int, tuple[int, ...]], ...] = tuple(
    BLOCK_SPECS[name] for name in ("declared-profile", "higher-resolution")
)
DECLARED_LEVELS = tuple(
    int(count) for _resolution, counts in RESOLUTION_LEVELS for count in counts
)
BLOCK_BUDGET_SECONDS = 4200.0
# The declared cost ceiling: a level measures its complete triples up to this
# cap, taken from the head and the tail of the level's own declared order, and a
# level's port-fallback triples up to its own smaller cap.  The cap is declared
# before the run so a level's cost stays inside the delivered per-level envelope;
# the receipt publishes how many triples the level has and how many were
# measured, so a reader sees exactly what was and was not measured.
MEASURED_TRIPLE_CAP = 6
PORT_FALLBACK_CAP = 2
DELIVERED_ITEM_SPECS = tuple(durability.ITEM_SPECS)
DELIVERED_ITEM_COUNT = len(DELIVERED_ITEM_SPECS)
# The two declared placement modes' own surfaces, in the order the readings name
# them.
DECLARED_READINGS = ("containment", "aggregation", "sibling", "descent")
COMPANION_READINGS = (
    "containment_scale",
    "aggregation_scale",
    "sibling_scale",
    "descent_scale",
)
NODE_CLASSES = ("declared_detail", "declared_beyond", "leaf_port", "beyond_leaf")


def plain(value: Any) -> Any:
    """One measured mapping, detached from whatever published it."""

    return scale.plain(value)


# --------------------------------------------------------------------------
# the declared surfaces
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Surface:
    """One field-exposed surface, and what it is an address of.

    ``kind`` and ``declared_family_item`` are one authority, not two: the store's
    declared family is ``capacity.declared_family()``'s own item list, so a
    surface is a declared item exactly when its ``(path, component)`` pair is one
    of that family's specs.  ``addressability`` is the node class of the path the
    surface is taken at, which is a separate fact: a single-port node is a node of
    the field's tree while the family refuses to address it as an item.
    """

    name: str
    path: str
    component: str
    flow_signal: tuple[float, float]
    kind: str
    addressability: str
    declared_family_item: bool

    @classmethod
    def from_dict(cls, record: Mapping[str, Any]) -> "Surface":
        """Rebuild a surface from a record this runner already published."""

        return cls(
            name=str(record["name"]),
            path=str(record["path"]),
            component=str(record["component"]),
            flow_signal=tuple(float(value) for value in record["flow_signal"]),
            kind=str(record["kind"]),
            addressability=str(record["addressability"]),
            declared_family_item=bool(record["declared_family_item"]),
        )

    def spec(self) -> durability.ItemSpec:
        return durability.ItemSpec(
            self.name, self.path, self.component, self.flow_signal
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "component": self.component,
            "flow_signal": [float(value) for value in self.flow_signal],
            "kind": self.kind,
            "addressability": self.addressability,
            "declared_family_item": bool(self.declared_family_item),
            "field_exposed": True,
            "readout_kind": "temporal-prediction",
            "observed": False,
            "evidence_added": False,
            "this_is_a_readout_not_an_observation": True,
        }


def item_surface(
    spec: durability.ItemSpec,
    *,
    size: int,
    family_keys: set[tuple[str, str]],
) -> Surface:
    """The store's declared item surface of one family item."""

    component = str(spec.component)
    return Surface(
        name=str(spec.name),
        path=str(spec.path),
        component=component,
        flow_signal=(float(spec.flow_signal[0]), float(spec.flow_signal[1])),
        kind="declared_item",
        addressability="interior_node" if int(size) > 1 else "leaf_port",
        declared_family_item=(str(spec.path), component) in family_keys,
    )


def scale_surface(
    path: str,
    *,
    size: int,
    family_keys: set[tuple[str, str]],
) -> Surface:
    """A node's scale surface: the field exposes it whether or not the store does.

    The root's scale mode is the store's declared family item 0 (``root-scale``),
    so this surface is a declared item at the root path and an undeclared
    field-exposed surface at every other path; a single-port node's scale mode is
    the port itself, which the family does not address as an item.
    """

    declared = (str(path), "scale") in family_keys
    return Surface(
        name=f"scale-{path or 'root'}",
        path=str(path),
        component="scale",
        flow_signal=(1.0, 0.0),
        kind="declared_item" if declared else "field_exposed_undeclared",
        addressability="leaf_port" if int(size) <= 1 else "interior_node",
        declared_family_item=bool(declared),
    )


def read_surface(owner: Any, spec: durability.ItemSpec) -> float:
    """One field-exposed readout along one declared direction."""

    reading = plain(
        owner.read_packet_deposit(
            path=spec.path,
            component=spec.component,
            flow_signal=[float(value) for value in spec.flow_signal],
        )
    )
    return float(reading["recovered_deposit"])


def write_surface(
    owner: Any, spec: durability.ItemSpec, *, label: str, budget: float
) -> dict[str, Any]:
    """One field-exposed write along one declared direction."""

    result = plain(
        owner.write_packet_impulse(
            str(label),
            path=spec.path,
            component=spec.component,
            flow_signal=[float(value) for value in spec.flow_signal],
            work_budget=float(budget),
        )
    )
    receipt = plain(result["impulse_receipt"])
    return {
        "requested_work": float(receipt["requested_work"]),
        "applied_work": float(receipt["applied_work"]),
        "impulse_amount": float(receipt["impulse_amount"]),
        "accepted": bool(receipt["accepted"]),
    }


def surface_probe(
    owner: Any,
    path: str,
    component: str,
    *,
    family_keys: set[tuple[str, str]],
    size: int,
) -> dict[str, Any]:
    """Does this surface execute?  Measured by executing it, refusal recorded.

    The surface carries its own addressability beside its outcome: whether
    ``(path, component)`` is a declared item of ``capacity.declared_family()``,
    which is the authority for the whole address space, and the node class of the
    path.  The outcome and the addressability are separate measurements -- a
    surface can execute and still not be addressable as an item.
    """

    record: dict[str, Any] = {
        "path": str(path),
        "component": str(component),
        "declared_family_item": bool((str(path), str(component)) in family_keys),
        "node_class": (
            "beyond_leaf"
            if int(size) <= 0
            else ("single_port_node" if int(size) == 1 else "interior_node")
        ),
    }
    try:
        value = read_surface(
            owner, durability.ItemSpec("probe", str(path), str(component), (1.0, 0.0))
        )
    except Exception as error:  # the field's own declared refusal
        record["read"] = f"{type(error).__name__}: {error}"
        record["read_executes"] = False
    else:
        record["read"] = float(value)
        record["read_executes"] = True
    try:
        write = write_surface(
            owner,
            durability.ItemSpec("probe", str(path), str(component), (1.0, 0.0)),
            label=f"tree:probe:{component}:{path}",
            budget=float(rank.PROBE_BUDGET),
        )
    except Exception as error:  # the field's own declared refusal
        record["write"] = f"{type(error).__name__}: {error}"
        record["write_executes"] = False
        record["write_accepted"] = False
    else:
        record["write"] = write
        record["write_executes"] = True
        record["write_accepted"] = bool(write["accepted"])
    return record


# --------------------------------------------------------------------------
# the declared triples of one level
# --------------------------------------------------------------------------
def level_catalogue(port_count: int, count: int) -> dict[str, Any]:
    """The level's declared parents, their children's classes, and the nulls.

    Everything here is read off the capacity runner's own family rule and the
    field's own tree, and nothing is invented: the parents are the level's
    declared interior items, the children are the two dyadic children of each,
    the flat null is the deepest declared level's two non-sibling items in the
    level's own order, and the shuffled parent is the next complete triple's
    parent in the declared order at the same depth.
    """

    nodes = capacity.dyadic_nodes(int(port_count))
    size_of = {str(row["path"]): int(row["size"]) for row in nodes}
    depth_of = {str(row["path"]): int(row["depth"]) for row in nodes}
    family = capacity.declared_family(int(port_count))
    specs: tuple[durability.ItemSpec, ...] = family["specs"]
    # the addressability authority: a surface is a declared item exactly when its
    # (path, component) pair is one of the family's own specs
    family_keys: set[tuple[str, str]] = {
        (str(spec.path), str(spec.component)) for spec in specs
    }
    detail_index = {
        str(spec.path): index
        for index, spec in enumerate(specs)
        if str(spec.component) == "detail"
    }
    level_specs = tuple(specs[: int(count)])

    def child_record(path: str) -> dict[str, Any]:
        index = detail_index.get(str(path))
        if index is not None and int(index) < int(count):
            spec = specs[int(index)]
            return {
                "path": str(path),
                "node_class": "declared_detail",
                "index": int(index),
                "in_the_level": True,
                "item": item_surface(
                    spec, size=size_of[str(path)], family_keys=family_keys
                ).as_dict(),
                "scale": scale_surface(
                    path, size=size_of[str(path)], family_keys=family_keys
                ).as_dict(),
            }
        if index is not None:
            return {
                "path": str(path),
                "node_class": "declared_beyond",
                "index": int(index),
                "in_the_level": False,
                "item": None,
                "scale": scale_surface(
                    path, size=size_of[str(path)], family_keys=family_keys
                ).as_dict(),
            }
        if str(path) in size_of:
            return {
                "path": str(path),
                "node_class": "leaf_port",
                "index": None,
                "in_the_level": False,
                "item": None,
                "scale": scale_surface(
                    path, size=size_of[str(path)], family_keys=family_keys
                ).as_dict(),
            }
        return {
            "path": str(path),
            "node_class": "beyond_leaf",
            "index": None,
            "in_the_level": False,
            "item": None,
            "scale": None,
        }

    triples: list[dict[str, Any]] = []
    for index, spec in enumerate(level_specs):
        if str(spec.component) != "detail":
            # the root scale item is not a parent: it has no children
            continue
        parent_path = str(spec.path)
        if parent_path not in size_of:
            continue
        children = [child_record(parent_path + "L"), child_record(parent_path + "R")]
        classes = [str(child["node_class"]) for child in children]
        if all(item == "declared_detail" for item in classes):
            triple_class = "complete"
        elif any(item == "declared_beyond" for item in classes):
            triple_class = "beyond_the_level_count"
        elif any(item == "leaf_port" for item in classes):
            triple_class = "leaf_child"
        else:
            triple_class = "beyond_a_leaf"
        triples.append(
            {
                "parent": {
                    "index": int(index),
                    "path": parent_path,
                    "depth": int(depth_of.get(parent_path, len(parent_path))),
                    "size": int(size_of[parent_path]),
                    "item": item_surface(
                        spec, size=size_of[parent_path], family_keys=family_keys
                    ).as_dict(),
                    "scale": scale_surface(
                        parent_path,
                        size=size_of[parent_path],
                        family_keys=family_keys,
                    ).as_dict(),
                },
                "children": children,
                "descendants": [
                    {
                        "branch": str(branch),
                        "path": str(parent_path) + str(branch) + str(step),
                        **child_record(str(parent_path) + str(branch) + str(step)),
                    }
                    for branch in ("L", "R")
                    for step in ("L", "R")
                ],
                "triple_class": triple_class,
            }
        )

    # the flat null: the deepest declared level's two non-sibling items, in the
    # level's own order, never the treated children themselves.
    depth_of_item = {
        str(spec.path): len(str(spec.path)) for spec in level_specs
    }
    deepest = max(depth_of_item.values(), default=0)
    at_depth = [
        (index, spec)
        for index, spec in enumerate(level_specs)
        if depth_of_item[str(spec.path)] == deepest and str(spec.component) == "detail"
    ]
    flat: list[dict[str, Any]] = []
    for position in range(len(at_depth)):
        for other in range(position + 1, len(at_depth)):
            left_index, left_spec = at_depth[position]
            right_index, right_spec = at_depth[other]
            if str(left_spec.path)[:-1] == str(right_spec.path)[:-1] and (
                str(left_spec.path)[-1:] in ("L", "R")
                and str(right_spec.path)[-1:] in ("L", "R")
            ):
                continue
            flat = [
                item_surface(
                    left_spec,
                    size=size_of[str(left_spec.path)],
                    family_keys=family_keys,
                ).as_dict(),
                item_surface(
                    right_spec,
                    size=size_of[str(right_spec.path)],
                    family_keys=family_keys,
                ).as_dict(),
            ]
            break
        if flat:
            break
    return {
        "declared": (
            "the parents are the level's declared interior items; the children are "
            "the two dyadic children of each; the flat null is the deepest declared "
            "level's two non-sibling items in the level's own order; the shuffled "
            "parent is the next complete triple's parent in the declared order"
        ),
        "port_count": int(port_count),
        "count": int(count),
        "triples": triples,
        "flat_null": flat,
        "flat_null_available": bool(flat),
        "classes": {
            name: len([row for row in triples if str(row["triple_class"]) == name])
            for name in (
                "complete",
                "beyond_the_level_count",
                "leaf_child",
                "beyond_a_leaf",
            )
        },
    }


def shuffled_parent(triples: Sequence[Mapping[str, Any]], index: int) -> Mapping[str, Any] | None:
    """The next complete triple's parent at the same depth, wrapping, never itself."""

    parent = triples[index]["parent"]
    complete = [
        row
        for row in triples
        if str(row["triple_class"]) == "complete"
        and str(row["parent"]["path"]) != str(parent["path"])
    ]
    same_depth = [
        row for row in complete if int(row["parent"]["depth"]) == int(parent["depth"])
    ]
    candidates = same_depth or complete
    if not candidates:
        return None
    order = {
        str(row["parent"]["path"]): position
        for position, row in enumerate(
            [row for row in triples if str(row["triple_class"]) == "complete"]
        )
    }
    here = order.get(str(parent["path"]), 0)
    following = [
        row
        for row in candidates
        if order.get(str(row["parent"]["path"]), 0) > here
    ]
    return (following or candidates)[0]


# --------------------------------------------------------------------------
# the declared measurement: one arm, one fresh owner
# --------------------------------------------------------------------------
def response(
    profile: Any,
    settings: rank.AddressingRankConfig,
    page: Any,
    *,
    sources: Sequence[Surface],
    targets: Sequence[Surface],
    budget: float,
    label: str,
) -> dict[str, Any]:
    """One arm: one fresh owner on the held page, the sources written, targets read.

    The response of a target is its readout after the writes minus its readout
    before them, divided by the declared budget (the delivered finite-difference
    convention) and, separately, by the applied work, so the arithmetic is
    checkable either way.  Nothing is written outside this owner's own successor
    chain and the owner is closed and removed before the arm returns.
    """

    owner, home = consumer.open_owner(
        profile, workspace=page, prefix=settings.owner_home_prefix
    )
    try:
        before = {
            target.name: read_surface(owner, target.spec()) for target in targets
        }
        writes = [
            write_surface(
                owner,
                source.spec(),
                label=f"{label}:write:{position}",
                budget=float(budget),
            )
            for position, source in enumerate(sources)
        ]
        after = {
            target.name: read_surface(owner, target.spec()) for target in targets
        }
        page_after = durability.page_sha256(owner.state.resonant_workspace)
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)
    applied = float(sum(float(write["applied_work"]) for write in writes))
    differences = {
        name: float(after[name]) - float(before[name]) for name in before
    }
    divisor = float(budget) if float(budget) != 0.0 else 1.0
    return {
        "label": str(label),
        "budget": float(budget),
        "sources": [source.as_dict() for source in sources],
        "targets": [target.as_dict() for target in targets],
        "before": {name: float(value) for name, value in before.items()},
        "after": {name: float(value) for name, value in after.items()},
        "differences": {name: float(value) for name, value in differences.items()},
        "per_declared_budget": {
            name: float(value) / divisor for name, value in differences.items()
        },
        "per_applied_work": {
            name: (float(value) / applied if applied > 0.0 else 0.0)
            for name, value in differences.items()
        },
        "greatest_difference": max(
            (abs(float(value)) for value in differences.values()), default=0.0
        ),
        "writes": writes,
        "applied_work_total": float(applied),
        "every_write_accepted": bool(all(bool(write["accepted"]) for write in writes)),
        "page_moved_by_the_arm": bool(
            page_after != durability.page_sha256(page)
        ),
    }


def triple_arms(
    profile: Any,
    settings: rank.AddressingRankConfig,
    page: Any,
    *,
    catalogue: Mapping[str, Any],
    triple: Mapping[str, Any],
    shuffled: Mapping[str, Any] | None,
    budget: float,
    with_deposit: bool,
    label: str,
) -> dict[str, Any]:
    """Every declared arm of one triple, each its own fresh owner on the page."""

    parent = triple["parent"]
    children = triple["children"]
    parent_item = Surface.from_dict(parent["item"])
    parent_scale = Surface.from_dict(parent["scale"])
    left_item = Surface.from_dict(children[0]["item"])
    right_item = Surface.from_dict(children[1]["item"])
    left_scale = Surface.from_dict(children[0]["scale"])
    right_scale = Surface.from_dict(children[1]["scale"])
    half = float(budget) / 2.0
    arms: dict[str, Any] = {}
    arms["parent_own"] = response(
        profile,
        settings,
        page,
        sources=[parent_item],
        targets=[parent_item],
        budget=float(budget),
        label=f"{label}:parent-own",
    )
    arms["zero_work"] = response(
        profile,
        settings,
        page,
        sources=[parent_item],
        targets=[parent_item],
        budget=0.0,
        label=f"{label}:zero-work",
    )
    arms["children_home"] = response(
        profile,
        settings,
        page,
        sources=[left_item, right_item],
        targets=[parent_item],
        budget=float(budget),
        label=f"{label}:children-home",
    )
    arms["children_home_half"] = response(
        profile,
        settings,
        page,
        sources=[left_item, right_item],
        targets=[parent_item],
        budget=half,
        label=f"{label}:children-home-half",
    )
    arms["child_single"] = response(
        profile,
        settings,
        page,
        sources=[left_item],
        targets=[parent_item],
        budget=float(budget),
        label=f"{label}:child-single",
    )
    arms["child_own"] = response(
        profile,
        settings,
        page,
        sources=[left_item],
        targets=[left_item],
        budget=float(budget),
        label=f"{label}:child-own",
    )
    arms["duplicate"] = response(
        profile,
        settings,
        page,
        sources=[left_item, left_item],
        targets=[parent_item],
        budget=float(budget),
        label=f"{label}:duplicate",
    )
    arms["sibling"] = response(
        profile,
        settings,
        page,
        sources=[right_item],
        targets=[left_item],
        budget=float(budget),
        label=f"{label}:sibling",
    )
    arms["sibling_half"] = response(
        profile,
        settings,
        page,
        sources=[right_item],
        targets=[left_item],
        budget=half,
        label=f"{label}:sibling-half",
    )
    arms["descent"] = response(
        profile,
        settings,
        page,
        sources=[parent_item],
        targets=[left_item],
        budget=float(budget),
        label=f"{label}:descent",
    )
    arms["descent_half"] = response(
        profile,
        settings,
        page,
        sources=[parent_item],
        targets=[left_item],
        budget=half,
        label=f"{label}:descent-half",
    )
    # A supplementary reading: a deposit two levels below the parent -- this
    # level's grandchildren, the placements the paired coarser/finer resolution's
    # own tree calls children -- placed at the parent's declared item surface.
    # Only executable surfaces are placed (a path that is not a node at this
    # resolution has no surface here and is recorded, not written); the reading is
    # taken at both resolutions by this same construction on each resolution's own
    # page, and it does not carry the branch verdict.
    descendant_rows = [
        dict(row)
        for row in (triple.get("descendants") or ())
        if str(row.get("node_class")) != "beyond_leaf"
    ]
    descendant_surfaces: list[Surface] = []
    for row in descendant_rows:
        record = row.get("item") or row.get("scale")
        if record is None:
            continue
        descendant_surfaces.append(
            Surface.from_dict(record)
        )
    if descendant_surfaces:
        arms["descendants_home"] = response(
            profile,
            settings,
            page,
            sources=descendant_surfaces,
            targets=[parent_item],
            budget=float(budget),
            label=f"{label}:descendants-home",
        )
        arms["descendants_half"] = response(
            profile,
            settings,
            page,
            sources=descendant_surfaces,
            targets=[parent_item],
            budget=half,
            label=f"{label}:descendants-half",
        )
    if shuffled is not None and str(shuffled["triple_class"]) == "complete":
        shuffled_children = shuffled["children"]
        shuffled_left = Surface.from_dict(shuffled_children[0]["item"])
        shuffled_right = Surface.from_dict(shuffled_children[1]["item"])
        arms["children_shuffled"] = response(
            profile,
            settings,
            page,
            sources=[shuffled_left, shuffled_right],
            targets=[parent_item],
            budget=float(budget),
            label=f"{label}:children-shuffled",
        )
        arms["scale_children_shuffled"] = response(
            profile,
            settings,
            page,
            sources=[
                Surface.from_dict(shuffled_children[0]["scale"]),
                Surface.from_dict(shuffled_children[1]["scale"]),
            ],
            targets=[parent_scale],
            budget=float(budget),
            label=f"{label}:scale-children-shuffled",
        )
    flat = catalogue["flat_null"]
    if flat:
        flat_left = Surface.from_dict(flat[0])
        flat_right = Surface.from_dict(flat[1])
        arms["children_flat"] = response(
            profile,
            settings,
            page,
            sources=[flat_left, flat_right],
            targets=[parent_item],
            budget=float(budget),
            label=f"{label}:children-flat",
        )
        arms["flat_single"] = response(
            profile,
            settings,
            page,
            sources=[flat_left],
            targets=[parent_item],
            budget=float(budget),
            label=f"{label}:flat-single",
        )
        arms["shared"] = response(
            profile,
            settings,
            page,
            sources=[flat_left, flat_left],
            targets=[parent_item],
            budget=float(budget),
            label=f"{label}:shared",
        )
        arms["non_sibling"] = response(
            profile,
            settings,
            page,
            sources=[flat_right],
            targets=[flat_left],
            budget=float(budget),
            label=f"{label}:non-sibling",
        )
        arms["descent_flat"] = response(
            profile,
            settings,
            page,
            sources=[flat_left],
            targets=[left_item],
            budget=float(budget),
            label=f"{label}:descent-flat",
        )
    arms["scale_parent_own"] = response(
        profile,
        settings,
        page,
        sources=[parent_scale],
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:scale-parent-own",
    )
    arms["scale_children_home"] = response(
        profile,
        settings,
        page,
        sources=[left_scale, right_scale],
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:scale-children-home",
    )
    arms["scale_children_home_half"] = response(
        profile,
        settings,
        page,
        sources=[left_scale, right_scale],
        targets=[parent_scale],
        budget=half,
        label=f"{label}:scale-children-home-half",
    )
    arms["scale_child_own"] = response(
        profile,
        settings,
        page,
        sources=[left_scale],
        targets=[left_scale],
        budget=float(budget),
        label=f"{label}:scale-child-own",
    )
    if with_deposit:
        deposit_budget = float(settings.store_config.write_budget)
        arms["deposit_children"] = response(
            profile,
            settings,
            page,
            sources=[left_item, right_item],
            targets=[parent_item],
            budget=deposit_budget,
            label=f"{label}:deposit-children",
        )
        arms["deposit_parent"] = response(
            profile,
            settings,
            page,
            sources=[parent_item],
            targets=[parent_item],
            budget=deposit_budget,
            label=f"{label}:deposit-parent",
        )
        arms["deposit_child_own"] = response(
            profile,
            settings,
            page,
            sources=[left_item],
            targets=[left_item],
            budget=deposit_budget,
            label=f"{label}:deposit-child-own",
        )
        arms["deposit_scale_children"] = response(
            profile,
            settings,
            page,
            sources=[left_scale, right_scale],
            targets=[parent_scale],
            budget=deposit_budget,
            label=f"{label}:deposit-scale-children",
        )
        arms["deposit_scale_parent"] = response(
            profile,
            settings,
            page,
            sources=[parent_scale],
            targets=[parent_scale],
            budget=deposit_budget,
            label=f"{label}:deposit-scale-parent",
        )
    return arms


# --------------------------------------------------------------------------
# one level
# --------------------------------------------------------------------------
# Declared before the first run, not assembled afterwards: for every reading the
# field-exposed surface the value is taken at, the node class of the path that
# surface sits at, whether that surface is a *declared item* of the store's
# address family, and whether the reading is an observation or a construction over
# readouts -- and, for a construction, the construction in full with its
# parameters.  The receipt carries this table, and each published reading carries
# its own row of it.
#
# The authority for "declared item" is one function, not this table:
# ``capacity.declared_family(port_count)["specs"]``, the delivered 8-item list
# extended by its own rule -- ``root-scale`` (path "", component scale),
# ``root-detail`` (path "", component detail), then every *interior* node's
# detail mode; a single-port node is refused by the field's own rule ("a
# single-port node carries no detail mode") and is recorded, not declared.  So:
#
#   * every item surface this runner reads (the parents', the children's, the
#     flat null's) is a declared family item, including the root parent's, which
#     is the root's *detail* mode (family item 1).  The root's *scale* mode
#     (family item 0) is also a declared family item, and it is not a parent:
#     it has no children, so the level catalogue never treats it as one.
#   * the companion readings are taken at scale surfaces.  At the root path the
#     scale surface is family item 0, a declared item; at every other path it is
#     field-exposed and **not** a family item.  The companion is therefore
#     declared path-sensitive rather than uniformly undeclared, and each surface
#     carries its own ``declared_family_item`` flag so the mixed case is visible
#     per row.
#   * the port fallback is taken at a single-port node's scale surface, which is
#     the port itself: the field executes it and the family does not address it
#     as an item, so it is field-exposed, not declared.
#
# A readout is what the field's own API returns (``readout_kind``
# temporal-prediction, ``evidence_added`` false): the surface read is an
# observation of the field's output, and every value compared across surfaces is
# a construction over those readouts.  No reading here is an observation.
READING_SURFACES: dict[str, dict[str, Any]] = {
    "R1_containment": {
        "taken_at": (
            "the parent's declared-item surface: the parent node's detail mode, "
            "addressed by the parent's own path (the root parent's is family item 1, "
            "root-detail)"
        ),
        "node_class": "interior_node",
        "declared_item": True,
        "declared_item_scope": (
            "every surface it reads is a member of capacity.declared_family()'s specs: "
            "the parent's detail mode and the two children's detail modes"
        ),
        "observed": False,
        "constructed": True,
        "construction": (
            "the treatment arm's greatest readout difference at the parent's "
            "declared-item surface after the children are deposited at their own "
            "declared-item surfaces, divided by the arm's own positive control (the "
            "parent's own deposit read at the same surface), against the declared "
            "two-term floor"
        ),
        "parameters": {
            "positive_control_arm": "parent_own",
            "treatment_arm": "children_home",
            "finite_difference_arm": "children_home_half (same treatment, half probe budget)",
            "shuffled_arm": "children_shuffled (the same contents at the next complete triple's parent)",
            "flat_arm": "children_flat",
            "probe_budget": "declared probe_budget, halved for the finite-difference arm",
            "numerators": "the treatment's greatest readout difference",
            "denominator": "the positive control's own greatest readout difference",
            "floor": "max(FLOOR_FACTOR * |r(a) - r(a/2)|, EPS_FACTOR * |r_own|)",
        },
        "carries_the_branch": True,
    },
    "R2_aggregation": {
        "taken_at": (
            "the parent's declared-item surface for the treatment; the children's own "
            "declared-item surfaces and the parent's own declared-item surface for the "
            "two denominators"
        ),
        "node_class": "interior_node",
        "declared_item": True,
        "declared_item_scope": (
            "every surface it reads is a member of capacity.declared_family()'s specs"
        ),
        "observed": False,
        "constructed": True,
        "construction": (
            "two distinct constructions are published from one treatment: the parent's "
            "surface read after the children are deposited alone at the delivered store "
            "write budget, divided by (a) the mean of what each child's own surface "
            "reads when deposited alone at that same budget, and separately by (b) what "
            "the parent's own deposit reads at its own surface.  The branch predicate "
            "reads the treatment response against the numerical floor alone; (a) is the "
            "fraction the per-level aggregate publishes and (b) is published beside it"
        ),
        "parameters": {
            "treatment_arm": "deposit_children",
            "denominator_arms": {
                "childrens_own_deposit": "deposit_child_own (each child's surface, deposited alone)",
                "parents_own_deposit": "deposit_parent (the parent's own surface, deposited at its own surface)",
            },
            "write_budget": "the delivered store write budget, not the probe budget",
            "finite_difference_arm": "none: the deposit arms are not a probe finite difference, so this reading's floor is the numerical term alone",
            "floor": "EPS_FACTOR * |the parent's own deposit response at its own surface|",
        },
        "carries_the_branch": True,
    },
    "R3_sibling": {
        "taken_at": (
            "the sibling's own declared-item surface: the depositing child's own "
            "interior-node detail mode"
        ),
        "node_class": "interior_node",
        "declared_item": True,
        "declared_item_scope": (
            "every surface it reads is a member of capacity.declared_family()'s specs"
        ),
        "observed": False,
        "constructed": True,
        "construction": (
            "one child's surface response to a deposit at its sibling's surface, "
            "divided by that child's own response at its own surface, against the same "
            "measurement for two items that are not siblings (the flat null)"
        ),
        "parameters": {
            "positive_control_arm": "child_own",
            "treatment_arm": "sibling",
            "finite_difference_arm": "sibling_half",
            "flat_arm": "non_sibling (the deepest declared level's two non-sibling items)",
            "numerators": "the sibling treatment's greatest readout difference",
            "denominator": "the child's own greatest readout difference at its own surface",
            "floor": "max(FLOOR_FACTOR * |r(a) - r(a/2)|, EPS_FACTOR * |r_own|)",
        },
        "carries_the_branch": True,
    },
    "R4_descent": {
        "taken_at": (
            "the child's own declared-item surface, after a deposit at the parent's own "
            "declared-item surface"
        ),
        "node_class": "interior_node",
        "declared_item": True,
        "declared_item_scope": (
            "every surface it reads is a member of capacity.declared_family()'s specs"
        ),
        "observed": False,
        "constructed": True,
        "construction": (
            "the child's surface response to a deposit at its parent's surface, divided "
            "by the parent's own response at its own surface, against a source that is "
            "not an ancestor of the child (the flat null)"
        ),
        "parameters": {
            "positive_control_arm": "parent_own",
            "treatment_arm": "descent",
            "finite_difference_arm": "descent_half",
            "flat_arm": "descent_flat",
            "numerators": "the descent treatment's greatest readout difference",
            "denominator": "the parent's own greatest readout difference at its own surface",
            "floor": "max(FLOOR_FACTOR * |r(a) - r(a/2)|, EPS_FACTOR * |r_own|)",
        },
        "carries_the_branch": True,
    },
    "companion_scale_containment": {
        "taken_at": (
            "the parent's scale surface and the children's scale surfaces: the "
            "field-exposed surface where the field's own packet analysis composes a "
            "node's summary from its children (_packet_analyze's size-weighted sum)"
        ),
        "node_class": "interior_node",
        "declared_item": None,
        "declared_item_scope": (
            "path-sensitive, and not uniform: at the root path the scale surface is "
            "capacity.declared_family()'s item 0 (root-scale) and is a declared item; at "
            "every other path it is field-exposed and not a family item.  Read the "
            "per-surface declared_family_item flag rather than one boolean for the whole "
            "reading"
        ),
        "observed": False,
        "constructed": True,
        "construction": "R1's construction, moved to the scale surfaces unchanged",
        "parameters": {
            "positive_control_arm": "scale_parent_own",
            "treatment_arm": "scale_children_home",
            "finite_difference_arm": "scale_children_home_half",
            "shuffled_arm": "scale_children_shuffled",
            "flat_arm": "none",
            "floor": "the same two-term floor, at these surfaces",
        },
        "carries_the_branch": False,
        "companion": True,
    },
    "companion_scale_aggregation": {
        "taken_at": (
            "the parent's scale surface for the treatment; the children's and the "
            "parent's own scale surfaces for the two denominators"
        ),
        "node_class": "interior_node",
        "declared_item": None,
        "declared_item_scope": (
            "path-sensitive, as the companion containment reading: the root's scale "
            "surface is declared family item 0, every other scale surface is "
            "field-exposed and not a family item"
        ),
        "observed": False,
        "constructed": True,
        "construction": "R2's construction, moved to the scale surfaces unchanged",
        "parameters": {
            "treatment_arm": "deposit_scale_children",
            "denominator_arms": {
                "childrens_own_deposit": "scale_child_own",
                "parents_own_deposit": "deposit_scale_parent (the parent's own deposit read at its own scale surface)",
            },
            "floor": "EPS_FACTOR times the parent's own scale deposit response",
        },
        "carries_the_branch": False,
        "companion": True,
    },
    "descendants_supplementary": {
        "taken_at": (
            "the parent's declared-item surface, with the deposits placed two levels "
            "below it: this level's grandchildren, addressed at their own paths"
        ),
        "node_class": "interior_node",
        "declared_item": True,
        "declared_item_scope": (
            "the parent's surface and every grandchild's surface that this resolution "
            "declares are members of capacity.declared_family()'s specs; a grandchild "
            "path that is not a node at this resolution has no surface and is recorded, "
            "not written"
        ),
        "observed": False,
        "constructed": True,
        "construction": (
            "a two-level reading: a deposit at the grandchildren's own declared-item "
            "surfaces, read at the parent's own declared-item surface, divided by the "
            "parent's own response at its own surface"
        ),
        "parameters": {
            "positive_control_arm": "parent_own",
            "treatment_arm": "descendants_home",
            "finite_difference_arm": "descendants_half",
            "placements": "the parent's grandchildren, recorded per path; a path that is not a node at this resolution has no surface and is recorded rather than written",
            "floor": "max(FLOOR_FACTOR * |r(a) - r(a/2)|, EPS_FACTOR * |r_own|)",
        },
        "carries_the_branch": False,
        "supplementary": True,
    },
    "port_fallback_scale": {
        "taken_at": (
            "a single-port node's scale surface, which is that port itself, deposited at "
            "and read at the same path"
        ),
        "node_class": "single_port_node",
        "declared_item": False,
        "declared_item_scope": (
            "the field executes this surface; capacity.declared_family() refuses the node "
            "as an item -- its own refusal is 'a single-port node carries no detail mode' "
            "and its (path, component) pair is not among the family's specs -- so this "
            "surface is field-exposed and undeclared"
        ),
        "observed": False,
        "constructed": True,
        "construction": (
            "the port's own scale surface read after the same surface is deposited at, "
            "divided by the same surface's own response at the same budget"
        ),
        "parameters": {
            "treatment_arm": "port_fallback",
            "budget": "the declared probe budget",
            "floor": "the level's declared numerical floor against the arm's own response",
        },
        "carries_the_branch": False,
        "fallback": True,
    },
}


def reading_of(
    arms: Mapping[str, Any],
    *,
    name: str,
    settings: rank.AddressingRankConfig,
    own: str,
    treatment: str,
    control: str | None,
    flat: str | None,
    floor_arm: str | None,
) -> dict[str, Any]:
    """One reading: its response, its own measured floor, and its controls."""

    declared_surface = READING_SURFACES[name]

    def greatest(name: str | None) -> float | None:
        if name is None or name not in arms or arms[name] is None:
            return None
        return float(arms[name]["greatest_difference"])

    own_value = greatest(own)
    treatment_value = greatest(treatment)
    control_value = greatest(control)
    flat_value = greatest(flat)
    half_value = greatest(floor_arm)
    finite_difference_floor = (
        abs(float(treatment_value) - float(half_value))
        if treatment_value is not None and half_value is not None
        else 0.0
    )
    floor = max(
        float(settings.floor_factor) * float(finite_difference_floor),
        float(settings.epsilon_factor) * abs(float(own_value or 0.0)),
    )
    positive_control_fires = bool(
        own_value is not None and abs(float(own_value)) > floor
    )
    value = float(treatment_value) if treatment_value is not None else None
    return {
        "reading": str(name),
        "taken_at": str(declared_surface["taken_at"]),
        "node_class": str(declared_surface["node_class"]),
        "declared_item": declared_surface["declared_item"],
        "declared_item_scope": str(declared_surface["declared_item_scope"]),
        "observed": False,
        "constructed_from_readouts": True,
        "carries_the_branch": bool(declared_surface["carries_the_branch"]),
        "declared": (
            "the treatment's greatest readout difference divided by the arm's own "
            "positive control, with the level's own measured finite-difference floor "
            "from the same treatment at half budget and the declared numerical floor "
            "relative to the control"
        ),
        "own_response": own_value,
        "treatment_response": value,
        "shuffled_response": control_value,
        "flat_response": flat_value,
        "half_budget_response": half_value,
        "finite_difference_floor": float(finite_difference_floor),
        "floor": float(floor),
        "fraction_of_the_positive_control": (
            float(value) / abs(float(own_value))
            if value is not None and own_value not in (None, 0.0)
            else None
        ),
        "the_positive_control_fires": bool(positive_control_fires),
        "at_the_floor": bool(value is not None and abs(float(value)) <= floor),
        "present": bool(value is not None and abs(float(value)) > floor),
        "a_nonzero_response_the_declared_floor_hides": bool(
            value is not None
            and abs(float(value)) > float(settings.epsilon_factor) * abs(float(own_value or 0.0))
            and floor > abs(float(value))
        ),
        "declared_note": (
            "at_the_floor/present use the two-term floor exactly as declared: FLOOR_FACTOR "
            "times the level's own half-budget difference, and EPS_FACTOR times the arm's "
            "own response.  A response that is not proportional to budget makes the first "
            "term large, so a response above the numerical floor can still be recorded at "
            "the floor; a_nonzero_response_the_declared_floor_hides names that case and "
            "the raw responses and the fraction are published beside it, and the fraction "
            "alone is never read as a present reading"
        ),
        "assignment_specific": bool(
            value is not None
            and control_value is not None
            and abs(float(value) - float(control_value)) > floor
        ),
        "counts_only": bool(
            value is not None
            and flat_value is not None
            and abs(float(value) - float(flat_value)) <= floor
        ),
    }


def deposit_reading(
    arms: Mapping[str, Any],
    *,
    name: str,
    settings: rank.AddressingRankConfig,
    treatment: str,
    own: str,
    reference: str,
) -> dict[str, Any]:
    """The deposit reading: the children deposited alone, the parent's surface read."""

    declared_surface = READING_SURFACES[name]

    def value_of(name: str) -> float | None:
        if name not in arms or arms[name] is None:
            return None
        return float(arms[name]["greatest_difference"])

    treatment_value = value_of(treatment)
    own_value = value_of(own)
    reference_value = value_of(reference)
    floor = float(settings.epsilon_factor) * abs(float(own_value or 0.0))
    return {
        "reading": str(name),
        "taken_at": str(declared_surface["taken_at"]),
        "node_class": str(declared_surface["node_class"]),
        "declared_item": declared_surface["declared_item"],
        "declared_item_scope": str(declared_surface["declared_item_scope"]),
        "observed": False,
        "constructed_from_readouts": True,
        "carries_the_branch": bool(declared_surface["carries_the_branch"]),
        "declared": (
            "the parent's surface read after the children are deposited alone at the "
            "delivered store write budget, divided by what each child's own surface "
            "reads when deposited alone at the same budget, against the parent's own "
            "deposit at its own surface"
        ),
        "treatment_response": treatment_value,
        "reference_child_deposit": reference_value,
        "own_deposit_response": own_value,
        "fraction_of_the_childrens_own_deposit": (
            float(treatment_value) / abs(float(reference_value))
            if treatment_value is not None and reference_value not in (None, 0.0)
            else None
        ),
        "fraction_of_the_parents_own_deposit": (
            float(treatment_value) / abs(float(own_value))
            if treatment_value is not None and own_value not in (None, 0.0)
            else None
        ),
        "floor": float(floor),
        "the_positive_control_fires": bool(
            own_value is not None and abs(float(own_value)) > floor
        ),
        "at_the_floor": bool(
            treatment_value is not None and abs(float(treatment_value)) <= floor
        ),
        "present": bool(
            treatment_value is not None and abs(float(treatment_value)) > floor
        ),
        "declared_note": (
            "this reading's floor is the declared numerical floor alone, EPS_FACTOR times "
            "the parent's own deposit response at its own surface: the deposit arms are "
            "measured at the delivered store write budget rather than as a probe finite "
            "difference, so there is no half-budget arm and no finite-difference term, and "
            "present means the magnitude is above that numerical floor"
        ),
    }


def selected_triples(
    triples: Sequence[Mapping[str, Any]], cap: int
) -> list[int]:
    """The level's complete triples up to the declared cap, head and tail first.

    The selection is deterministic and declared: the first ``ceil(cap/2)`` and
    the last ``floor(cap/2)`` complete triples of the level's own declared order,
    so a capped level still measures its shallowest and its deepest parents
    rather than only the head.
    """

    complete = [
        position
        for position, row in enumerate(triples)
        if str(row["triple_class"]) == "complete"
    ]
    if len(complete) <= int(cap):
        return complete
    head = int(cap) - int(cap) // 2
    tail = int(cap) // 2
    chosen: list[int] = []
    for position in [*complete[:head], *complete[len(complete) - tail :]]:
        if position not in chosen:
            chosen.append(int(position))
    return chosen


def port_fallback(
    profile: Any,
    settings: rank.AddressingRankConfig,
    page: Any,
    *,
    triple: Mapping[str, Any],
    budget: float,
    label: str,
) -> dict[str, Any]:
    """One port-fallback reading: the children at their port surfaces.

    The child of a single-port node has no detail surface -- the field refuses
    it by its own rule -- so this reading is taken at the child's *scale*
    surface, which is that one port.  The authority for its addressability is
    ``capacity.declared_family()``: a single-port node is not one of its items,
    so the surface is field-exposed and undeclared, and the reading does not
    carry the branch verdict.
    """

    parent_scale = Surface.from_dict(triple["parent"]["scale"])
    def child_scale(child: Mapping[str, Any]) -> Surface | None:
        record = child.get("scale")
        if record is None:
            return None
        return Surface.from_dict(record)
    scales = [
        surface
        for surface in (child_scale(child) for child in triple["children"])
        if surface is not None
    ]
    arms: dict[str, Any] = {}
    arms["scale_parent_own"] = response(
        profile,
        settings,
        page,
        sources=[parent_scale],
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:port-scale-parent-own",
    )
    arms["scale_children_home"] = response(
        profile,
        settings,
        page,
        sources=scales,
        targets=[parent_scale],
        budget=float(budget),
        label=f"{label}:port-scale-children-home",
    )
    arms["scale_child_own"] = (
        response(
            profile,
            settings,
            page,
            sources=[scales[0]],
            targets=[scales[0]],
            budget=float(budget),
            label=f"{label}:port-scale-child-own",
        )
        if scales
        else None
    )
    own = float(arms["scale_parent_own"]["greatest_difference"])
    treatment = float(arms["scale_children_home"]["greatest_difference"])
    floor = float(settings.epsilon_factor) * abs(own)
    return {
        "position": int(triple["parent"]["index"]),
        "parent_path": str(triple["parent"]["path"]),
        "triple_class": str(triple["triple_class"]),
        "parent_scale_surface": parent_scale.as_dict(),
        "children_scales": [surface.as_dict() for surface in scales],
        "child_item_surfaces": [
            dict(child["item"]) if child["item"] is not None else None
            for child in triple["children"]
        ],
        "child_detail_refusals": [
            {
                "path": str(child["path"]),
                "node_class": str(child["node_class"]),
                "item_surface_exists": bool(child["item"] is not None),
            }
            for child in triple["children"]
        ],
        "scale_containment": {
            "reading": "port_fallback_scale",
            "taken_at": str(READING_SURFACES["port_fallback_scale"]["taken_at"]),
            "node_class": str(READING_SURFACES["port_fallback_scale"]["node_class"]),
            "declared_item": READING_SURFACES["port_fallback_scale"]["declared_item"],
            "declared_item_scope": str(
                READING_SURFACES["port_fallback_scale"]["declared_item_scope"]
            ),
            "observed": False,
            "constructed_from_readouts": True,
            "carries_the_branch": False,
            "declared": (
                "the same containment reading at the parent's scale surface with the "
                "children at their port/scale surfaces: capacity.declared_family() does "
                "not address a single-port node as an item (its own refusal is 'a "
                "single-port node carries no detail mode'), so this surface is "
                "field-exposed and undeclared, and the reading does not carry the branch"
            ),
            "own_response": own,
            "treatment_response": treatment,
            "fraction_of_the_positive_control": (
                treatment / abs(own) if own != 0.0 else None
            ),
            "floor": float(floor),
            "the_positive_control_fires": bool(abs(own) > floor),
            "at_the_floor": bool(abs(treatment) <= floor),
            "present": bool(abs(treatment) > floor),
        },
        "arms_finite": {
            name: bool(
                arm is None
                or all(
                    np.isfinite(float(value)) for value in arm["differences"].values()
                )
            )
            for name, arm in arms.items()
        },
    }


def level_block(
    profile: Any,
    count: int,
    *,
    resolution: int,
    hold_settings: Mapping[str, Any],
    surface_record: Mapping[str, Any],
    blank_reads: Mapping[str, Any],
) -> dict[str, Any]:
    """One declared count: its held page, its declared triples and their readings."""

    family = capacity.declared_family(int(profile.port_count))
    specs: tuple[durability.ItemSpec, ...] = family["specs"]
    if int(count) > int(len(specs)):
        return {
            "n": int(count),
            "ports_per_pool": int(resolution),
            "constructible": False,
            "reason": (
                "the declared family has no item at this count at this resolution: "
                f"the family's addressable inventory is {len(specs)} items and its "
                "next candidate path is refused by the field's own rule"
            ),
            "addressable_count": int(len(specs)),
        }
    started = time.perf_counter()
    settings = capacity.level_settings(int(count))
    catalogue = level_catalogue(int(profile.port_count), int(count))
    held = rank.held_state(
        profile,
        settings,
        indices=tuple(range(int(count))),
        gain=float(hold_settings["gain"]),
        phase_degrees=float(hold_settings["phase_degrees"]),
        phase_references=hold_settings["per_item"],
        captures=hold_settings["captures"],
        label=f"tree-held-{count}",
    )
    page = held.pop("held_page_object")
    triples = catalogue["triples"]
    measured_positions = selected_triples(triples, MEASURED_TRIPLE_CAP)
    measured: list[dict[str, Any]] = []
    for position in measured_positions:
        triple = triples[position]
        neighbour = shuffled_parent(triples, position)
        arms = triple_arms(
            profile,
            settings,
            page,
            catalogue=catalogue,
            triple=triple,
            shuffled=neighbour,
            budget=float(settings.probe_budget),
            with_deposit=True,
            label=f"tree-{count}-{position}",
        )
        containment = reading_of(
            arms,
            name="R1_containment",
            settings=settings,
            own="parent_own",
            treatment="children_home",
            control="children_shuffled",
            flat="children_flat",
            floor_arm="children_home_half",
        )
        sibling = reading_of(
            arms,
            name="R3_sibling",
            settings=settings,
            own="child_own",
            treatment="sibling",
            control=None,
            flat="non_sibling",
            floor_arm="sibling_half",
        )
        descent = reading_of(
            arms,
            name="R4_descent",
            settings=settings,
            own="parent_own",
            treatment="descent",
            control=None,
            flat="descent_flat",
            floor_arm="descent_half",
        )
        # The duplicate and shared controls are the same measurement shape as the
        # containment reading -- a response at the parent's declared item surface
        # to deposits at child item surfaces at the same budget -- so they reuse
        # that reading's own measured floor rather than a relative test that
        # degenerates when every response is exactly zero.
        shared_floor = float(
            max(float(containment["floor"]), float(sibling["floor"]))
        )
        reading = {
            "position": int(position),
            "parent_path": str(triple["parent"]["path"]),
            "triple_class": str(triple["triple_class"]),
            "shuffled_parent_path": (
                None if neighbour is None else str(neighbour["parent"]["path"])
            ),
            "surfaces": {
                "parent": dict(triple["parent"]["item"]),
                "parent_scale": dict(triple["parent"]["scale"]),
                "children": [dict(child["item"]) for child in triple["children"]],
                "children_scales": [
                    dict(child["scale"]) for child in triple["children"]
                ],
                "flat_null": list(catalogue["flat_null"]),
            },
            "containment": containment,
            "aggregation": deposit_reading(
                arms,
                name="R2_aggregation",
                settings=settings,
                treatment="deposit_children",
                own="deposit_parent",
                reference="deposit_child_own",
            ),
            "sibling": reading_of(
                arms,
                name="R3_sibling",
                settings=settings,
                own="child_own",
                treatment="sibling",
                control=None,
                flat="non_sibling",
                floor_arm="sibling_half",
            ),
            "descent": descent,
            "descendants": (
                None
                if arms.get("descendants_home") is None
                else reading_of(
                    arms,
                    name="descendants_supplementary",
                    settings=settings,
                    own="parent_own",
                    treatment="descendants_home",
                    control=None,
                    flat=None,
                    floor_arm="descendants_half",
                )
            ),
            "descendant_placements": {
                "declared": (
                    "the placements two levels below the parent: this level's own "
                    "grandchildren, which are the children of the parent's children and "
                    "the same physical intervals' children at the paired resolution; a "
                    "path that is not a node at this resolution has no surface here and "
                    "is recorded rather than written"
                ),
                "executable": int(
                    len(
                        [
                            row
                            for row in (triple.get("descendants") or ())
                            if str(row.get("node_class")) != "beyond_leaf"
                        ]
                    )
                ),
                "not_a_node_at_this_resolution": [
                    str(row["path"])
                    for row in (triple.get("descendants") or ())
                    if str(row.get("node_class")) == "beyond_leaf"
                ],
            },
            "controls": {
                "zero_work_response": float(
                    arms["zero_work"]["greatest_difference"]
                ),
                "zero_work_probes_are_rejected": bool(
                    not arms["zero_work"]["every_write_accepted"]
                ),
                "zero_work_moves_nothing": bool(
                    float(arms["zero_work"]["greatest_difference"])
                    <= float(settings.epsilon_factor)
                ),
                "duplicate_response": float(arms["duplicate"]["greatest_difference"]),
                "single_response": float(arms["child_single"]["greatest_difference"]),
                "duplicate_matches_the_single_write": bool(
                    abs(
                        float(arms["duplicate"]["greatest_difference"])
                        - float(arms["child_single"]["greatest_difference"])
                    )
                    <= float(shared_floor)
                ),
                "shared_response": (
                    None
                    if arms.get("shared") is None
                    else float(arms["shared"]["greatest_difference"])
                ),
                "flat_single_response": (
                    None
                    if arms.get("flat_single") is None
                    else float(arms["flat_single"]["greatest_difference"])
                ),
                "shared_matches_the_single_write": bool(
                    arms.get("shared") is not None
                    and arms.get("flat_single") is not None
                    and abs(
                        float(arms["shared"]["greatest_difference"])
                        - float(arms["flat_single"]["greatest_difference"])
                    )
                    <= float(shared_floor)
                ),
                "control_floor": float(shared_floor),
                "control_floor_is_the_containment_readings_own_measured_floor": True,
                "every_arm_moved_the_page": bool(
                    all(
                        bool(arm["page_moved_by_the_arm"])
                        for name, arm in arms.items()
                        if name != "zero_work"
                    )
                ),
                "shuffled_control_available": bool(
                    arms.get("children_shuffled") is not None
                    and arms.get("scale_children_shuffled") is not None
                ),
                "flat_null_available": bool(
                    arms.get("children_flat") is not None
                    and arms.get("non_sibling") is not None
                    and arms.get("descent_flat") is not None
                ),
            },
            "companion_scale_surfaces": {
                "declared": (
                    "the same readings at the parent's scale surface and the "
                    "children's scale surfaces: a field-exposed surface the store "
                    "does not declare as an item, so it does not carry the branch"
                ),
                "containment_scale": reading_of(
                    arms,
                    name="companion_scale_containment",
                    settings=settings,
                    own="scale_parent_own",
                    treatment="scale_children_home",
                    control="scale_children_shuffled",
                    flat=None,
                    floor_arm="scale_children_home_half",
                ),
                "aggregation_scale": deposit_reading(
                    arms,
                    name="companion_scale_aggregation",
                    settings=settings,
                    treatment="deposit_scale_children",
                    own="deposit_scale_parent",
                    reference="scale_child_own",
                ),
            },
            "arms_finite": {
                name: bool(all(np.isfinite(float(value)) for value in arm["differences"].values()))
                for name, arm in arms.items()
            },
        }
        reading["sibling"]["the_sibling_reading_differs_from_the_non_sibling_reading"] = bool(
            reading["sibling"]["present"] and not reading["sibling"]["counts_only"]
        )
        measured.append(reading)
    fallback: list[dict[str, Any]] = []
    fallback_measured: list[dict[str, Any]] = []
    for position, row in enumerate(triples):
        if str(row["triple_class"]) == "complete":
            continue
        if str(row["triple_class"]) in ("leaf_child", "beyond_a_leaf"):
            fallback.append(
                {
                    "position": int(position),
                    "parent_path": str(row["parent"]["path"]),
                    "triple_class": str(row["triple_class"]),
                    "children": [dict(child) for child in row["children"]],
                    "note": (
                        "the parent's own surface is executable; the child's detail "
                        "surface is refused by the field's own rule, so the reading "
                        "at that child's declared item surface is a surface "
                        "limitation and only the port/scale fallback is measured"
                    ),
                }
            )
    for position in [
        int(row["position"])
        for row in fallback[:PORT_FALLBACK_CAP]
    ]:
        fallback_measured.append(
            port_fallback(
                profile,
                settings,
                page,
                triple=triples[position],
                budget=float(settings.probe_budget),
                label=f"tree-{count}-port-{position}",
            )
        )
    record: dict[str, Any] = {
        "n": int(count),
        "ports_per_pool": int(resolution),
        "constructible": True,
        "family": {
            "declared_rule": str(family["declared_rule"]),
            "declared_family_size": int(len(specs)),
            "names": [str(spec.name) for spec in specs[: int(count)]],
            "head_matches_the_delivered_item_specs": bool(
                family["head_matches_the_delivered_item_specs"]
            ),
        },
        "settings": settings.as_dict(),
        "catalogue": {
            "declared": str(catalogue["declared"]),
            "triples": [
                {
                    "parent_path": str(row["parent"]["path"]),
                    "parent_index": int(row["parent"]["index"]),
                    "parent_depth": int(row["parent"]["depth"]),
                    "parent_size": int(row["parent"]["size"]),
                    "triple_class": str(row["triple_class"]),
                    "children": [dict(child) for child in row["children"]],
                }
                for row in triples
            ],
            "classes": dict(catalogue["classes"]),
            "flat_null": list(catalogue["flat_null"]),
            "flat_null_available": bool(catalogue["flat_null_available"]),
        },
        "page_sha256": str(held["held_page_sha256"]),
        "hold": dict(held),
        "measured": measured,
        "measured_triple_cap": int(MEASURED_TRIPLE_CAP),
        "measured_positions": [int(position) for position in measured_positions],
        "surface_limitations": fallback,
        "port_fallback_measured": fallback_measured,
        "port_fallback_cap": int(PORT_FALLBACK_CAP),
        "blank_reads": dict(blank_reads),
        "runtime_seconds": float(time.perf_counter() - started),
    }
    record["readings"] = level_readings(record, surface_record)
    return record


def level_readings(
    record: Mapping[str, Any], surface_record: Mapping[str, Any]
) -> dict[str, Any]:
    """What one level's own measured triples say, and its own branch."""

    measured = list(record["measured"])
    parents = [
        str(row["parent_path"]) for row in record["catalogue"]["triples"]
    ]
    parent_surface = surface_record["by_path"]
    parents_with_an_executable_surface = [
        path
        for path in parents
        if bool(parent_surface.get(path, {}).get("detail_write_executes"))
    ]
    complete = [row for row in measured if str(row["triple_class"]) == "complete"]
    readings = {
        "declared": (
            "each reading is taken over the level's own measured triples -- the "
            "level's complete triples up to the declared cap, taken from the head and "
            "the tail of the level's own order -- and carries its own measured floor; a "
            "reading is at the floor, present, assignment_specific or counts_only as "
            "its own arm's numbers say"
        ),
        "triples_measured": int(len(measured)),
        "complete_triples": int(
            len(
                [
                    row
                    for row in record["catalogue"]["triples"]
                    if str(row["triple_class"]) == "complete"
                ]
            )
        ),
        "measured_triple_cap": int(record.get("measured_triple_cap", 0)),
        "port_fallback_measured": int(len(record.get("port_fallback_measured", []))),
        "parents_in_the_level": int(len(parents)),
        "parents_with_an_executable_declared_detail_surface": int(
            len(parents_with_an_executable_surface)
        ),
        "every_parent_surface_executes": bool(
            len(parents_with_an_executable_surface) == len(parents) and parents
        ),
        "surface_limitation_triples": int(len(record["surface_limitations"])),
        "shuffled_control_available": bool(
            measured
            and all(
                bool(row["controls"]["shuffled_control_available"]) for row in measured
            )
        ),
        "flat_null_available": bool(
            measured
            and all(bool(row["controls"]["flat_null_available"]) for row in measured)
        ),
        "containment": {
            "greatest_fraction_of_the_positive_control": max(
                (
                    abs(float(row["containment"]["fraction_of_the_positive_control"]))
                    for row in complete
                    if row["containment"]["fraction_of_the_positive_control"] is not None
                ),
                default=None,
            ),
            "readings_at_the_floor": int(
                len([row for row in complete if bool(row["containment"]["at_the_floor"])])
            ),
            "readings_present": int(
                len([row for row in complete if bool(row["containment"]["present"])])
            ),
            "readings_assignment_specific": int(
                len(
                    [
                        row
                        for row in complete
                        if bool(row["containment"]["assignment_specific"])
                    ]
                )
            ),
            "readings_counts_only": int(
                len(
                    [row for row in complete if bool(row["containment"]["counts_only"])]
                )
            ),
            "every_positive_control_fires": bool(
                all(bool(row["containment"]["the_positive_control_fires"]) for row in complete)
            ),
        },
        "aggregation": {
            "greatest_fraction_of_the_childrens_own_deposit": max(
                (
                    abs(float(row["aggregation"]["fraction_of_the_childrens_own_deposit"]))
                    for row in complete
                    if row["aggregation"]["fraction_of_the_childrens_own_deposit"]
                    is not None
                ),
                default=None,
            ),
            "readings_at_the_floor": int(
                len([row for row in complete if bool(row["aggregation"]["at_the_floor"])])
            ),
            "readings_present": int(
                len([row for row in complete if bool(row["aggregation"]["present"])])
            ),
            "every_positive_control_fires": bool(
                all(
                    bool(row["aggregation"]["the_positive_control_fires"])
                    for row in complete
                )
            ),
        },
        "sibling": {
            "greatest_fraction_of_the_childs_own_control": max(
                (
                    abs(float(row["sibling"]["fraction_of_the_positive_control"]))
                    for row in complete
                    if row["sibling"]["fraction_of_the_positive_control"] is not None
                ),
                default=None,
            ),
            "readings_at_the_floor": int(
                len([row for row in complete if bool(row["sibling"]["at_the_floor"])])
            ),
            "readings_present": int(
                len([row for row in complete if bool(row["sibling"]["present"])])
            ),
            "readings_where_siblings_differ_from_non_siblings": int(
                len(
                    [
                        row
                        for row in complete
                        if bool(
                            row["sibling"][
                                "the_sibling_reading_differs_from_the_non_sibling_reading"
                            ]
                        )
                    ]
                )
            ),
            "every_positive_control_fires": bool(
                all(
                    bool(row["sibling"]["the_positive_control_fires"])
                    for row in complete
                )
            ),
        },
        "descent": {
            "greatest_fraction_of_the_positive_control": max(
                (
                    abs(float(row["descent"]["fraction_of_the_positive_control"]))
                    for row in complete
                    if row["descent"]["fraction_of_the_positive_control"] is not None
                ),
                default=None,
            ),
            "readings_at_the_floor": int(
                len([row for row in complete if bool(row["descent"]["at_the_floor"])])
            ),
            "readings_present": int(
                len([row for row in complete if bool(row["descent"]["present"])])
            ),
            "every_positive_control_fires": bool(
                all(
                    bool(row["descent"]["the_positive_control_fires"])
                    for row in complete
                )
            ),
        },
        "descendants": {
            "declared": (
                "a supplementary reading two levels below the parent at the parent's own "
                "declared item surface: it does not carry the branch verdict, and it is "
                "measured at both resolutions by the same construction on each "
                "resolution's own page"
            ),
            "readings_measured": int(
                len([row for row in complete if row.get("descendants") is not None])
            ),
            "greatest_fraction_of_the_positive_control": max(
                (
                    abs(float(row["descendants"]["fraction_of_the_positive_control"]))
                    for row in complete
                    if row.get("descendants") is not None
                    and row["descendants"]["fraction_of_the_positive_control"] is not None
                ),
                default=None,
            ),
            "readings_at_the_floor": int(
                len(
                    [
                        row
                        for row in complete
                        if row.get("descendants") is not None
                        and bool(row["descendants"]["at_the_floor"])
                    ]
                )
            ),
            "readings_present": int(
                len(
                    [
                        row
                        for row in complete
                        if row.get("descendants") is not None
                        and bool(row["descendants"]["present"])
                    ]
                )
            ),
            "every_positive_control_fires": bool(
                all(
                    bool(row["descendants"]["the_positive_control_fires"])
                    for row in complete
                    if row.get("descendants") is not None
                )
            ),
            "readings_where_the_declared_floor_hides_a_nonzero_response": int(
                len(
                    [
                        row
                        for row in complete
                        if row.get("descendants") is not None
                        and bool(
                            row["descendants"][
                                "a_nonzero_response_the_declared_floor_hides"
                            ]
                        )
                    ]
                )
            ),
            "placements_not_a_node_at_this_resolution": int(
                len(
                    [
                        path
                        for row in complete
                        for path in row["descendant_placements"][
                            "not_a_node_at_this_resolution"
                        ]
                    ]
                )
            ),
        },
        "companion_scale_surfaces": {
            "containment_scale_greatest_fraction": max(
                (
                    abs(
                        float(
                            row["companion_scale_surfaces"]["containment_scale"][
                                "fraction_of_the_positive_control"
                            ]
                        )
                    )
                    for row in complete
                    if row["companion_scale_surfaces"]["containment_scale"][
                        "fraction_of_the_positive_control"
                    ]
                    is not None
                ),
                default=None,
            ),
            "containment_scale_present": int(
                len(
                    [
                        row
                        for row in complete
                        if bool(
                            row["companion_scale_surfaces"]["containment_scale"]["present"]
                        )
                    ]
                )
            ),
            "containment_scale_assignment_specific": int(
                len(
                    [
                        row
                        for row in complete
                        if bool(
                            row["companion_scale_surfaces"]["containment_scale"][
                                "assignment_specific"
                            ]
                        )
                    ]
                )
            ),
            "aggregation_scale_greatest_fraction": max(
                (
                    abs(
                        float(
                            row["companion_scale_surfaces"]["aggregation_scale"][
                                "fraction_of_the_childrens_own_deposit"
                            ]
                        )
                    )
                    for row in complete
                    if row["companion_scale_surfaces"]["aggregation_scale"][
                        "fraction_of_the_childrens_own_deposit"
                    ]
                    is not None
                ),
                default=None,
            ),
            "readings_where_the_declared_floor_hides_a_nonzero_response": int(
                len(
                    [
                        row
                        for row in complete
                        if bool(
                            row["companion_scale_surfaces"]["containment_scale"][
                                "a_nonzero_response_the_declared_floor_hides"
                            ]
                        )
                    ]
                )
            ),
            "aggregation_scale_present": int(
                len(
                    [
                        row
                        for row in complete
                        if bool(
                            row["companion_scale_surfaces"]["aggregation_scale"]["present"]
                        )
                    ]
                )
            ),
        },
        "port_fallback": {
            "declared": (
                "the readings taken at the port/scale surfaces for the level's triples "
                "whose children are single-port nodes: field-exposed surfaces that are "
                "not declared item surfaces, so they do not carry the branch"
            ),
            "measured": int(len(record.get("port_fallback_measured", []))),
            "scale_containment_present": int(
                len(
                    [
                        row
                        for row in record.get("port_fallback_measured", [])
                        if bool(row["scale_containment"]["present"])
                    ]
                )
            ),
            "greatest_fraction_of_the_positive_control": max(
                (
                    abs(
                        float(
                            row["scale_containment"][
                                "fraction_of_the_positive_control"
                            ]
                        )
                    )
                    for row in record.get("port_fallback_measured", [])
                    if row["scale_containment"]["fraction_of_the_positive_control"]
                    is not None
                ),
                default=None,
            ),
            "child_item_surfaces_that_do_not_exist": int(
                len(
                    [
                        surface
                        for row in record.get("port_fallback_measured", [])
                        for surface in row["child_item_surfaces"]
                        if surface is None
                    ]
                )
            ),
            "every_arm_is_finite": bool(
                all(
                    all(bool(value) for value in row["arms_finite"].values())
                    for row in record.get("port_fallback_measured", [])
                )
            ),
        },
        "controls": {
            "every_zero_work_probe_was_rejected": bool(
                all(
                    bool(row["controls"]["zero_work_probes_are_rejected"])
                    for row in measured
                )
            ),
            "every_zero_work_probe_moved_nothing": bool(
                all(
                    bool(row["controls"]["zero_work_moves_nothing"])
                    for row in measured
                )
            ),
            "every_duplicate_matches_the_single_write": bool(
                all(
                    bool(row["controls"]["duplicate_matches_the_single_write"])
                    for row in measured
                )
            ),
            "every_shared_matches_the_single_write": bool(
                all(
                    bool(row["controls"]["shared_matches_the_single_write"])
                    for row in measured
                )
            ),
            "every_arm_moved_the_page": bool(
                all(
                    bool(row["controls"]["every_arm_moved_the_page"])
                    for row in measured
                )
            ),
            "every_arm_is_finite": bool(
                all(
                    all(bool(value) for value in row["arms_finite"].values())
                    for row in measured
                )
            ),
        },
    }
    readings["branch"] = level_branch(record, readings)
    return readings


def level_branch(record: Mapping[str, Any], readings: Mapping[str, Any]) -> str:
    """The declared branch for one level, from its own measured numbers.

    The branch is taken on the declared item surfaces only, and it needs every
    declared reading to be readable: the containment, aggregation, sibling and
    descent readings each need their own positive control, their own measured
    floor, and both nulls (the shuffled control and the flat null) available on
    the level's own page.  A missing reading or null is recorded as
    inconclusive rather than read as a zero.
    """

    if not bool(readings["parents_in_the_level"]):
        return "no_field_exposed_parent_surface_exists"
    if not bool(readings["every_parent_surface_executes"]):
        return "no_field_exposed_parent_surface_exists"
    controls = readings["controls"]
    if not all(bool(value) for value in controls.values()):
        return "inconclusive"
    complete = int(readings["triples_measured"])
    if complete == 0:
        return "inconclusive"
    if not (
        bool(readings["shuffled_control_available"])
        and bool(readings["flat_null_available"])
    ):
        return "inconclusive"
    if not (
        bool(readings["containment"]["every_positive_control_fires"])
        and bool(readings["aggregation"]["every_positive_control_fires"])
        and bool(readings["sibling"]["every_positive_control_fires"])
        and bool(readings["descent"]["every_positive_control_fires"])
    ):
        return "inconclusive"
    at_the_floor = {
        "containment": int(readings["containment"]["readings_at_the_floor"]),
        "aggregation": int(readings["aggregation"]["readings_at_the_floor"]),
        "sibling": int(readings["sibling"]["readings_at_the_floor"]),
        "descent": int(readings["descent"]["readings_at_the_floor"]),
    }
    present = {
        "containment": int(readings["containment"]["readings_present"]),
        "aggregation": int(readings["aggregation"]["readings_present"]),
        "sibling": int(readings["sibling"]["readings_present"]),
        "descent": int(readings["descent"]["readings_present"]),
    }
    # a present reading is readable as a tree relation only when the same
    # measurement changes with the shuffled control or with the non-sibling pair
    specific = int(readings["containment"]["readings_assignment_specific"]) + int(
        readings["sibling"]["readings_where_siblings_differ_from_non_siblings"]
    )
    present_total = int(present["containment"]) + int(present["sibling"])
    if present_total > 0 and specific >= present_total:
        return "the_tree_is_structural"
    if all(int(at_the_floor[name]) == complete for name in at_the_floor):
        return "the_tree_is_decorative"
    return "inconclusive"


# --------------------------------------------------------------------------
# the declared blocks
# --------------------------------------------------------------------------
def surface_table(profile: Any, paths: Sequence[str]) -> dict[str, Any]:
    """Which surfaces execute, measured by executing each one, refusal recorded."""

    owner, home = consumer.open_owner(profile, prefix="tree-surfaces-")
    family_keys = {
        (str(spec.path), str(spec.component))
        for spec in capacity.declared_family(int(profile.port_count))["specs"]
    }
    size_of = {
        str(row["path"]): int(row["size"])
        for row in capacity.dyadic_nodes(int(profile.port_count))
    }
    rows: dict[str, Any] = {}
    try:
        for path in paths:
            size = int(size_of.get(str(path), 0))
            rows[str(path)] = {
                "detail": surface_probe(
                    owner, str(path), "detail", family_keys=family_keys, size=size
                ),
                "scale": surface_probe(
                    owner, str(path), "scale", family_keys=family_keys, size=size
                ),
                "node_size": size,
            }
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)
    by_path = {
        str(path): {
            "detail_write_executes": bool(row["detail"]["write_executes"]),
            "detail_write_accepted": bool(row["detail"]["write_accepted"]),
            "detail_read_executes": bool(row["detail"]["read_executes"]),
            "detail_refusal": (
                None if bool(row["detail"]["write_executes"]) else str(row["detail"]["write"])
            ),
            "scale_write_accepted": bool(row["scale"]["write_accepted"]),
            "scale_read_executes": bool(row["scale"]["read_executes"]),
        }
        for path, row in rows.items()
    }
    return {"by_path": by_path, "rows": rows}


def blank_page_reads(profile: Any, paths: Sequence[str]) -> dict[str, Any]:
    """What a fresh owner's blank page reads at the block's surfaces."""

    owner, home = consumer.open_owner(profile, prefix="tree-blank-")
    try:
        page = durability.page_sha256(owner.state.resonant_workspace)
        item_reads: dict[str, float] = {}
        scale_reads: dict[str, float] = {}
        for path in sorted(set(str(value) for value in paths)):
            item_reads[str(path)] = read_surface(
                owner, durability.ItemSpec("blank", str(path), "detail", (1.0, 0.0))
            )
            scale_reads[str(path)] = read_surface(
                owner, durability.ItemSpec("blank", str(path), "scale", (1.0, 0.0))
            )
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)
    greatest = max(
        (abs(float(value)) for value in [*item_reads.values(), *scale_reads.values()]),
        default=0.0,
    )
    return {
        "blank_page_sha256": str(page),
        "detail_reads": item_reads,
        "scale_reads": scale_reads,
        "greatest_blank_read": float(greatest),
        "the_blank_page_reads_nothing": bool(
            greatest <= float(rank.EPS_FACTOR)
        ),
    }


def block(
    resolution: int,
    counts: Sequence[int],
    *,
    name: str,
    budget_seconds: float = BLOCK_BUDGET_SECONDS,
    levels_override: Sequence[int] | None = None,
) -> dict[str, Any]:
    """One declared block: one resolution, its surfaces, its levels, in order."""

    started = time.perf_counter()
    declared_counts = tuple(int(count) for count in counts)
    run_counts = (
        tuple(int(count) for count in declared_counts)
        if levels_override is None
        else tuple(int(count) for count in levels_override)
    )
    profile, profile_record = capacity.resolution_profile(int(resolution))
    family = capacity.declared_family(int(profile.port_count))
    specs: tuple[durability.ItemSpec, ...] = family["specs"]
    census = {
        "declared_rule": str(family["declared_rule"]),
        "port_count": int(family["port_count"]),
        "nodes": int(family["nodes"]),
        "leaves": int(family["leaves"]),
        "depths": dict(family["depths"]),
        "declared_family_size": int(len(specs)),
        "head_matches_the_delivered_item_specs": bool(
            family["head_matches_the_delivered_item_specs"]
        ),
        "orthogonality": capacity.family_orthogonality(
            int(profile.port_count), specs
        ),
    }
    # Every path this block's readings can name: the declared items' paths and
    # their two children's paths, which is exactly the set the triples classify
    # and the set the cross-resolution leg compares.
    surface_paths = sorted(
        {
            str(spec.path)
            for spec in specs
        }
        | {
            str(spec.path) + branch
            for spec in specs
            if str(spec.component) == "detail"
            for branch in ("L", "R")
        }
    )
    surfaces = surface_table(profile, surface_paths)
    blanks = blank_page_reads(
        profile, [str(spec.path) for spec in specs[: max(run_counts or (0,))]]
    )
    levels: dict[str, Any] = {}
    points_run: list[int] = []
    points_not_run: list[dict[str, Any]] = []
    points_not_constructible: list[dict[str, Any]] = []
    block_settings = rank.AddressingRankConfig(
        item_indices=tuple(range(len(specs))),
        store_config=replace(
            rank.AddressingRankConfig().store_config,
            item_indices=tuple(range(len(specs))),
            neutrality_probe_items=(),
        ),
    )
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
                            f"the block's declared wall-clock budget ({budget_seconds:g} s) "
                            f"was already spent ({elapsed:.1f} s) when this level's turn came"
                        ),
                    }
                )
                continue
            if int(count) > int(len(specs)):
                record_here = level_block(
                    profile,
                    int(count),
                    resolution=int(resolution),
                    hold_settings=hold_settings,
                    surface_record=surfaces,
                    blank_reads=blanks,
                )
                levels[str(count)] = record_here
                points_not_constructible.append(
                    {"n": int(count), "reason": str(record_here["reason"])}
                )
                elapsed = time.perf_counter() - started
                continue
            projected = capacity.projected_cost(levels, int(count))
            if (
                projected is not None
                and float(elapsed) + float(projected) > float(budget_seconds)
            ):
                points_not_run.append(
                    {
                        "n": int(count),
                        "reason": (
                            "the measured cost of the finished levels projects this level "
                            f"at {projected:.1f} s, which does not fit the remaining "
                            f"{float(budget_seconds) - float(elapsed):.1f} s of the "
                            "block's declared budget; the top of the range is cut rather "
                            "than the arms shortened"
                        ),
                    }
                )
                continue
            try:
                levels[str(count)] = level_block(
                    profile,
                    int(count),
                    resolution=int(resolution),
                    hold_settings=hold_settings,
                    surface_record=surfaces,
                    blank_reads=blanks,
                )
            except Exception as error:  # recorded, never swallowed
                points_not_run.append(
                    {
                        "n": int(count),
                        "reason": (
                            "the level's own measurement raised: "
                            f"{type(error).__name__}: {error}"
                        ),
                        "traceback": traceback.format_exc().splitlines()[-6:],
                    }
                )
                elapsed = time.perf_counter() - started
                continue
            points_run.append(int(count))
            elapsed = time.perf_counter() - started
    record: dict[str, Any] = {
        "schema": BLOCK_SCHEMA,
        "block": str(name),
        "resolution": int(resolution),
        "declared_counts": [int(count) for count in declared_counts],
        "counts_attempted": [int(count) for count in run_counts],
        "levels_override_used": bool(levels_override is not None),
        "profile": profile_record,
        "census": census,
        "surface_table": surfaces,
        "reading_surfaces": {
            name: dict(entry) for name, entry in READING_SURFACES.items()
        },
        "blank_page": blanks,
        "block_hold_settings": {
            "declared": (
                "measured once per block over the block's whole declared family by the "
                "store-scale runner's own hold_settings; every level of the block is "
                "held at these settings, which are the delivered operating point"
            ),
            "items_captured": int(installed),
            "measured_gain": float(hold_settings["gain"]),
            "phase_degrees": float(hold_settings["phase_degrees"]),
            "write_budget": float(block_settings.store_config.write_budget),
            "captured_deposits": {
                str(capture["name"]): float(capture["deposited_energy"])
                for capture in hold_settings["captures"]
            },
        },
        "levels": levels,
        "points_run": [int(count) for count in points_run],
        "points_not_run": points_not_run,
        "points_not_constructible": points_not_constructible,
        "declared_budget_seconds": float(budget_seconds),
        "runtime_seconds": float(time.perf_counter() - started),
        "delivered_item_list_restored": bool(
            tuple(durability.ITEM_SPECS) == DELIVERED_ITEM_SPECS
        ),
    }
    scale.assert_finite(record)
    record["content_digest"] = scale.receipt_digest(record)
    return record


# --------------------------------------------------------------------------
# the merged receipt
# --------------------------------------------------------------------------
def level_row(record: Mapping[str, Any]) -> dict[str, Any]:
    """One level's row in the shared table."""

    readings = record["readings"]
    return {
        "n": int(record["n"]),
        "resolution": int(record["ports_per_pool"]),
        "constructible": bool(record.get("constructible", False)),
        "complete_triples": int(readings.get("complete_triples", 0)),
        "triples_measured": int(readings.get("triples_measured", 0)),
        "surface_limitation_triples": int(
            readings.get("surface_limitation_triples", 0)
        ),
        "parents_in_the_level": int(readings.get("parents_in_the_level", 0)),
        "every_parent_surface_executes": bool(
            readings.get("every_parent_surface_executes", False)
        ),
        "containment_greatest_fraction": readings.get("containment", {}).get(
            "greatest_fraction_of_the_positive_control"
        ),
        "containment_at_the_floor": int(
            readings.get("containment", {}).get("readings_at_the_floor", 0)
        ),
        "containment_present": int(
            readings.get("containment", {}).get("readings_present", 0)
        ),
        "containment_assignment_specific": int(
            readings.get("containment", {}).get("readings_assignment_specific", 0)
        ),
        "aggregation_greatest_fraction": readings.get("aggregation", {}).get(
            "greatest_fraction_of_the_childrens_own_deposit"
        ),
        "aggregation_at_the_floor": int(
            readings.get("aggregation", {}).get("readings_at_the_floor", 0)
        ),
        "sibling_greatest_fraction": readings.get("sibling", {}).get(
            "greatest_fraction_of_the_childs_own_control"
        ),
        "sibling_at_the_floor": int(
            readings.get("sibling", {}).get("readings_at_the_floor", 0)
        ),
        "descent_greatest_fraction": readings.get("descent", {}).get(
            "greatest_fraction_of_the_positive_control"
        ),
        "descent_at_the_floor": int(
            readings.get("descent", {}).get("readings_at_the_floor", 0)
        ),
        "companion_scale_containment_greatest_fraction": readings.get(
            "companion_scale_surfaces", {}
        ).get("containment_scale_greatest_fraction"),
        "descendants_measured": int(
            readings.get("descendants", {}).get("readings_measured", 0)
        ),
        "descendants_greatest_fraction": readings.get("descendants", {}).get(
            "greatest_fraction_of_the_positive_control"
        ),
        "descendants_at_the_floor": int(
            readings.get("descendants", {}).get("readings_at_the_floor", 0)
        ),
        "descendants_present": int(
            readings.get("descendants", {}).get("readings_present", 0)
        ),
        "descendant_placements_not_a_node_here": int(
            readings.get("descendants", {}).get(
                "placements_not_a_node_at_this_resolution", 0
            )
        ),
        "port_fallback_measured": int(
            readings.get("port_fallback", {}).get("measured", 0)
        ),
        "port_fallback_scale_containment_present": int(
            readings.get("port_fallback", {}).get("scale_containment_present", 0)
        ),
        "port_fallback_greatest_fraction": readings.get("port_fallback", {}).get(
            "greatest_fraction_of_the_positive_control"
        ),
        "companion_scale_containment_present": int(
            readings.get("companion_scale_surfaces", {}).get(
                "containment_scale_present", 0
            )
        ),
        "companion_scale_containment_floor_hidden_responses": int(
            readings.get("companion_scale_surfaces", {}).get(
                "readings_where_the_declared_floor_hides_a_nonzero_response", 0
            )
        ),
        "descendants_floor_hidden_responses": int(
            readings.get("descendants", {}).get(
                "readings_where_the_declared_floor_hides_a_nonzero_response", 0
            )
        ),
        "companion_scale_containment_assignment_specific": int(
            readings.get("companion_scale_surfaces", {}).get(
                "containment_scale_assignment_specific", 0
            )
        ),
        "branch": str(readings.get("branch", "")),
        "runtime_seconds": float(record.get("runtime_seconds", 0.0)),
    }


def reading_block(document: Mapping[str, Any]) -> dict[str, Any]:
    """What the measured table says, with the branch and its companion."""

    table = [row for row in document["table"] if bool(row["constructible"])]
    branches = sorted({str(row["branch"]) for row in table})
    controls = {
        "every_zero_work_probe_was_rejected": all(
            bool(
                level["readings"]["controls"]["every_zero_work_probe_was_rejected"]
            )
            for block in document["blocks"].values()
            for level in block["levels"].values()
            if bool(level.get("constructible"))
        ),
        "every_zero_work_probe_moved_nothing": all(
            bool(level["readings"]["controls"]["every_zero_work_probe_moved_nothing"])
            for block in document["blocks"].values()
            for level in block["levels"].values()
            if bool(level.get("constructible"))
        ),
        "every_duplicate_matches_the_single_write": all(
            bool(
                level["readings"]["controls"]["every_duplicate_matches_the_single_write"]
            )
            for block in document["blocks"].values()
            for level in block["levels"].values()
            if bool(level.get("constructible"))
        ),
        "every_shared_matches_the_single_write": all(
            bool(level["readings"]["controls"]["every_shared_matches_the_single_write"])
            for block in document["blocks"].values()
            for level in block["levels"].values()
            if bool(level.get("constructible"))
        ),
        "every_arm_moved_the_page": all(
            bool(level["readings"]["controls"]["every_arm_moved_the_page"])
            for block in document["blocks"].values()
            for level in block["levels"].values()
            if bool(level.get("constructible"))
        ),
        "every_blank_page_reads_nothing": all(
            bool(block["blank_page"]["the_blank_page_reads_nothing"])
            for block in document["blocks"].values()
        ),
    }
    containment_floor = all(
        int(row["containment_at_the_floor"]) == int(row["triples_measured"])
        and int(row["triples_measured"]) > 0
        for row in table
    )
    aggregation_floor = all(
        int(row["aggregation_at_the_floor"]) == int(row["triples_measured"])
        and int(row["triples_measured"]) > 0
        for row in table
    )
    descent_floor = all(
        int(row["descent_at_the_floor"]) == int(row["triples_measured"])
        and int(row["triples_measured"]) > 0
        for row in table
    )
    companion_present = any(
        int(row["companion_scale_containment_present"]) > 0 for row in table
    )
    companion_specific = any(
        int(row["companion_scale_containment_assignment_specific"]) > 0
        for row in table
    )
    companion_hidden = any(
        int(row["companion_scale_containment_floor_hidden_responses"]) > 0
        for row in table
    )
    # the companion's own readings, off the measured rows rather than the summary
    # table: the branch-carrying readings are not the only thing this level
    # published, and the companion has its own floor counts and its own surfaces
    measured_rows = [
        row
        for block in document["blocks"].values()
        for level in block["levels"].values()
        if bool(level.get("constructible"))
        for row in level["measured"]
    ]
    companion_at_the_floor = bool(measured_rows) and all(
        bool(row["companion_scale_surfaces"]["containment_scale"]["at_the_floor"])
        for row in measured_rows
    )
    # the companion surfaces are not uniformly undeclared: the authority is the
    # family, so which of them are family items is read off the measured rows
    companion_declared_items = sorted(
        {
            f"{surface['path'] or '<root>'}/{surface['component']}"
            for row in measured_rows
            for surface in (
                [row["surfaces"]["parent_scale"]]
                + list(row["surfaces"]["children_scales"])
            )
            if bool(surface.get("declared_family_item"))
        }
    )
    cross = document.get("cross_resolution", {})
    companion_hidden_fraction = max(
        (
            abs(float(row["companion_scale_containment_greatest_fraction"]))
            for row in table
            if row["companion_scale_containment_greatest_fraction"] is not None
        ),
        default=None,
    )
    cross_measured = int(cross.get("patterns_measured_at_both_resolutions", 0) or 0)
    cross_agrees = bool(
        cross.get("every_pattern_measured_at_both_resolutions_gives_the_same_kind_of_reading")
    )
    branch = (
        branches[0]
        if len(branches) == 1
        else (
            "the_tree_is_structural"
            if "the_tree_is_structural" in branches
            else ("inconclusive" if len(branches) > 1 else "inconclusive")
        )
    )
    verdicts = {
        "every_declared_level_ran_and_is_constructible": bool(
            len(table) == len([row for row in document["table"]])
            and all(bool(row["constructible"]) for row in document["table"])
        ),
        "every_control_passed": bool(all(bool(value) for value in controls.values())),
        "every_parent_has_an_executable_declared_detail_surface": bool(
            all(bool(row["every_parent_surface_executes"]) for row in table)
        ),
        "containment_is_at_the_floor_at_every_measured_triple": bool(containment_floor),
        "aggregation_is_at_the_floor_at_every_measured_triple": bool(aggregation_floor),
        "descent_is_at_the_floor_at_every_measured_triple": bool(descent_floor),
        "every_level_published_its_complete_and_measured_triple_counts": bool(
            all(
                int(row["complete_triples"]) > 0
                and int(row["triples_measured"]) > 0
                and int(row["triples_measured"]) <= int(row["complete_triples"])
                for row in table
            )
        ),
        "no_declared_surface_reading_is_present": bool(
            all(int(row["containment_present"]) == 0 for row in table)
        ),
        "the_same_readings_are_present_at_the_undeclared_scale_surfaces": bool(
            companion_present
        ),
        "the_scale_surface_reading_is_assignment_specific": bool(companion_specific),
        "the_scale_surface_reading_is_at_the_floor_under_the_declared_rule": bool(
            not companion_present and not companion_hidden
        ),
        "no_scale_surface_response_is_hidden_by_the_declared_floor": bool(
            not companion_hidden
        ),
        "a_placement_pattern_measured_at_both_resolutions_gives_the_same_kind_of_reading": bool(
            cross_measured > 0 and cross_agrees
        ),
        "no_placement_pattern_has_a_parent_surface_at_every_resolution_with_a_child_surface_missing_at_one": bool(
            int(
                cross.get(
                    "count_of_patterns_where_the_parent_surface_exists_at_every_resolution_but_a_child_surface_does_not",
                    0,
                )
                or 0
            )
            == 0
        ),
    }
    negatives: list[dict[str, Any]] = []
    if not controls["every_zero_work_probe_moved_nothing"]:
        negatives.append(
            {
                "expectation": "a rejected zero-work write moves no read",
                "measured": "a zero-work arm moved a read",
            }
        )
    if not controls["every_duplicate_matches_the_single_write"]:
        negatives.append(
            {
                "expectation": "the duplicated placement does not separate from the single write",
                "measured": "the duplicate arm's response differs from the single write's",
            }
        )
    if not verdicts["every_parent_has_an_executable_declared_detail_surface"]:
        negatives.append(
            {
                "expectation": "every parent's declared detail surface executes",
                "measured": "at least one parent's declared detail surface did not execute",
            }
        )
    if not verdicts["every_level_published_its_complete_and_measured_triple_counts"]:
        negatives.append(
            {
                "expectation": (
                    "every level publishes how many complete triples it has and how many "
                    "it measured"
                ),
                "measured": (
                    "a level did not publish both counts or measured more triples than it "
                    "has"
                ),
            }
        )
    if any(
        int(row["triples_measured"]) < int(row["complete_triples"]) for row in table
    ):
        negatives.append(
            {
                "expectation": (
                    "a level's measured triples cover its complete triples"
                ),
                "measured": (
                    "the declared per-level cap bounded the measured triples below the "
                    "level's complete triples: the readings are stated over the measured "
                    "triples only, and the unmeasured ones are not claimed"
                ),
            }
        )
    if cross_measured > 0 and not cross_agrees:
        negatives.append(
            {
                "expectation": (
                    "the same placement pattern gives the same kind of reading at both "
                    "resolutions"
                ),
                "measured": (
                    "at least one placement pattern measured at both resolutions is at "
                    "the floor at one and present at the other: the reading there follows "
                    "the node count or the aggregation rather than the placement"
                ),
            }
        )
    if not verdicts[
        "no_placement_pattern_has_a_parent_surface_at_every_resolution_with_a_child_surface_missing_at_one"
    ]:
        negatives.append(
            {
                "expectation": (
                    "every resolution that addresses a parent also addresses its children"
                ),
                "measured": (
                    "at the coarser resolution the parent's own detail surface executes "
                    "while a child's does not: the child's refusal is a surface limitation "
                    "of that reading, named with its port/scale fallback, and it is not "
                    "read as the absence of a parent surface"
                ),
                "patterns": list(
                    cross.get(
                        "patterns_where_the_parent_surface_exists_at_every_resolution_but_a_child_surface_does_not",
                        [],
                    )
                ),
            }
        )
    if companion_present and not companion_specific:
        negatives.append(
            {
                "expectation": (
                    "a reading at the scale surfaces is assignment-specific (a parent's "
                    "summary follows its own children)"
                ),
                "measured": (
                    "the scale-surface reading is present but does not differ between the "
                    "treated and shuffled children"
                ),
            }
        )
    return {
        "declared": (
            "the branch is taken on the declared item surfaces only; the companion "
            "readings at the field-exposed scale surfaces are reported separately and "
            "carry their own predicates"
        ),
        "controls": controls,
        "verdicts": verdicts,
        "branches_returned_by_the_levels": branches,
        "branch": str(branch),
        "companion_scale_surfaces": {
            "a_reading_is_present": bool(companion_present),
            "the_reading_is_assignment_specific": bool(companion_specific),
            "the_reading_is_at_the_floor_under_the_declared_rule": bool(
                companion_at_the_floor
            ),
            "a_nonzero_response_the_declared_floor_hides": bool(companion_hidden),
            "declared_items_among_these_surfaces": sorted(
                companion_declared_items
            ),
            "the_store_declares_these_item_surfaces": (
                "path-sensitive, not uniform: the root's scale surface is the store's "
                "declared family item 0 (root-scale, path '' with component scale) and is "
                "a declared item; every other parent or child scale surface the companion "
                "reads is field-exposed and is not a family item.  The companion is "
                "['declared_item' if the surface is one of declared_items_among_these_"
                "surfaces else 'field_exposed_undeclared']"
            ),
            "carries_the_branch": False,
        },
        "cross_resolution_placements": {
            "declared": (
                "the same placement patterns measured at both resolutions, each on a page "
                "held under its own profile: no surface is relabelled onto another "
                "resolution's page"
            ),
            "patterns_named_by_either_block": int(
                cross.get("patterns_named_by_either_block", 0) or 0
            ),
            "patterns_measured_at_both_resolutions": int(cross_measured),
            "every_pattern_measured_at_both_resolutions_gives_the_same_kind_of_reading": bool(
                cross_agrees
            ),
            "patterns_measured_at_only_one_resolution": len(
                cross.get("patterns_measured_at_only_one_resolution", [])
            ),
            "patterns_where_the_parent_surface_exists_at_every_resolution_but_a_child_surface_does_not": list(
                cross.get(
                    "patterns_where_the_parent_surface_exists_at_every_resolution_but_a_child_surface_does_not",
                    [],
                )
            ),
            "the_matched_control_compares": list(
                cross.get("the_matched_control_compares", [])
            ),
            "patterns_where_the_supplementary_reading_differs_between_resolutions": list(
                cross.get(
                    "patterns_where_the_supplementary_reading_differs_between_resolutions",
                    [],
                )
            ),
            "supplementary_reading_scope": str(
                cross.get("supplementary_reading_scope", "")
            ),
        },
        "honest_negatives": negatives,
    }


def merge_blocks(blocks: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The declared blocks, assembled into one receipt with its own digests."""

    started = time.perf_counter()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "question": (
            "does the store's scale tree act as a tree, or is the addressing flat under "
            "a tree-shaped address space -- at the surfaces the field exposes, and at "
            "the surfaces the store declares?"
        ),
        "declared": {
            "surfaces": {
                "write": (
                    "owner.write_packet_impulse(operation_id, path=, component=, "
                    "flow_signal=, work_budget=): one owner transition, exactly-once "
                    "under its operation identity"
                ),
                "read": (
                    "owner.read_packet_deposit(path=, component=, flow_signal=) -> "
                    "recovered_deposit: readout_kind 'temporal-prediction', "
                    "evidence_added False -- a field-exposed API readout, not an "
                    "admitted observation; every figure in this receipt is such a "
                    "readout, and every aggregate this runner builds from them is a "
                    "construction and is labelled one"
                ),
                "declared_item": (
                    "the root's scale mode and every interior node's detail mode: the "
                    "capacity runner's own declared family rule, reused verbatim"
                ),
                "field_exposed_undeclared": (
                    "a node's scale mode anywhere below the root, and a single-port "
                    "node's scale mode, which is that port itself: the field executes "
                    "both, the declared family does not address either as an item"
                ),
                "addressability": (
                    "measured, not assumed: every parent's declared detail surface and "
                    "every child path's detail and scale surfaces are executed once and "
                    "the outcome, including the field's own refusal text, is recorded"
                ),
            },
            "readings": {
                "R1_containment": (
                    "response at the parent's declared item surface to deposits at its "
                    "children's declared item surfaces, over the parent's own response at "
                    "its own surface"
                ),
                "R2_aggregation": (
                    "the children deposited alone at the delivered store write budget, the "
                    "parent's surface read, over the mean of what each child's own surface "
                    "reads when deposited alone at that budget"
                ),
                "R3_sibling": (
                    "one child's surface response to a deposit at its sibling's, against "
                    "the same measurement for two items that are not siblings"
                ),
                "R4_descent": (
                    "the child's surface response to a deposit at its parent's surface, "
                    "over the parent's own response, against a source that is not an "
                    "ancestor of the child"
                ),
                "companion_scale": (
                    "R1-R4 again at the parent's and the children's scale surfaces: the "
                    "field-exposed surface where the field's own packet analysis composes "
                    "a node's summary from its children (_packet_analyze's size-weighted "
                    "sum).  Reported separately; does not carry the branch"
                ),
            },
            "reading_surfaces": {
                name: dict(entry) for name, entry in READING_SURFACES.items()
            },
            "reading_surfaces_authority": (
                "declared before the first run and carried per reading: for every reading "
                "the field-exposed surface the value is taken at, the node class of the "
                "path that surface sits at, whether that surface is a declared item of the "
                "store's address family, and whether the reading is an observation or a "
                "construction over readouts, with the construction's parameters.  "
                "declared_item is the authority of capacity.declared_family(port_count)"
                "['specs'] and is path-sensitive: the root's scale surface is family item 0 "
                "while every other node's scale surface is field-exposed and undeclared, "
                "and the root's scale item is not a parent because it has no children.  No "
                "reading in this receipt is an observation: each is a construction over "
                "readouts the field's own API returns (readout_kind temporal-prediction, "
                "evidence_added false), and each published reading carries its own row of "
                "this table beside its numbers"
            ),
            "floors_and_normalizations": (
                "response_floor = max(FLOOR_FACTOR * |r(a) - r(a/2)|, EPS_FACTOR * "
                "|r_own|), the first term this level's own finite-difference floor "
                "measured at half budget, the second the declared numerical floor "
                "relative to the arm's own positive control; at_the_floor, present, "
                "assignment_specific and counts_only are defined against it"
            ),
            "controls": {
                "positive_control": (
                    "the parent's own deposit at its own surface must be above the floor "
                    "or the level is recorded unreadable rather than zero"
                ),
                "zero_work_probe": "a zero-work write must be rejected and move no read",
                "blank_page": "a fresh owner's blank page reads nothing at any surface",
                "duplicate": "the children written twice at one child's surface must not "
                "separate from the single write",
                "shared": "every source at one shared surface must give that surface's own "
                "response",
                "shuffled": (
                    "the same contents attached to a parent they were not built from: the "
                    "next complete triple's parent in the declared order, never the "
                    "treated parent; a present reading whose shuffled control does not "
                    "differ from it is a placement-geometry artifact"
                ),
                "flat_null": (
                    "the same number of items at surfaces that are not siblings of one "
                    "another and are not the treated children: the deepest declared "
                    "level's two non-sibling items in the level's own order"
                ),
                "cross_resolution": (
                    "the same placement patterns measured at both resolutions, each on a "
                    "page held under its own resolution's profile -- no surface is "
                    "relabelled onto another resolution's page: for every parent path "
                    "measured at either resolution, the reading at each resolution with "
                    "that resolution's own floor and that path's own node class, so a "
                    "reading that survives only where a parent surface genuinely exists is "
                    "distinguishable from an artifact of the node count or of the "
                    "aggregation.  The refused-path census is reported alongside it as a "
                    "surface cross-check, not as the control"
                ),
                "descendants_supplementary": (
                    "a deposit two levels below the parent -- this level's grandchildren, "
                    "the children of the parent's children, which are the same physical "
                    "intervals' children at the paired resolution -- placed at the "
                    "parent's own declared item surface, with its own half-budget floor.  "
                    "It is a supplementary reading: it does not carry the branch verdict, "
                    "and a path that is not a node at this resolution is recorded, not "
                    "written"
                ),
            },
            "branch_rule": {
                "the_tree_is_structural": (
                    "at least one declared-item-surface reading is present and "
                    "assignment_specific at every level where it is available, and no "
                    "control fails"
                ),
                "the_tree_is_decorative": (
                    "every declared-item-surface reading is at its floor at every level "
                    "and every shuffled and flat arm is at its floor"
                ),
                "no_field_exposed_parent_surface_exists": (
                    "the parent itself has no executable field surface at any level; "
                    "tested by executing each parent's own detail write and read.  A "
                    "child's detail refusal is not this branch: it is a per-reading "
                    "surface limitation with its port/scale fallback labelled, and it "
                    "does not carry the verdict"
                ),
                "inconclusive": (
                    "a control failed, a positive control did not fire, or a reading is "
                    "present without being assignment_specific"
                ),
            },
            "axes": {
                "item_count": [int(count) for count in DECLARED_LEVELS],
                "resolution_ports_per_pool": [
                    int(resolution) for resolution, _counts in RESOLUTION_LEVELS
                ],
                "declared_resolution_levels": {
                    str(int(resolution)): [int(count) for count in counts]
                    for resolution, counts in RESOLUTION_LEVELS
                },
                "levels_override_used": bool(
                    any(
                        bool(block.get("levels_override_used"))
                        for block in blocks.values()
                    )
                ),
            },
            "probe_budget": float(rank.PROBE_BUDGET),
            "probe_budget_half": float(rank.PROBE_BUDGET) / 2.0,
            "hold_ticks": int(rank.HOLD_TICKS),
            "floor_factor": float(rank.FLOOR_FACTOR),
            "epsilon_factor": float(rank.EPS_FACTOR),
            "content_digest_definition": (
                "the store-scale runner's declared content digest, reused: sha256 of the "
                "canonical JSON of the body with the declared clock leaves and "
                "clock-derived digests stripped, taken before the digest is attached; "
                "each block carries its own digest under the same rule"
            ),
            "content_digest_strip_keys": list(scale.STRIP_KEYS),
            "content_digest_strip_keys_source": (
                "run_memory_store_scale.STRIP_KEYS, reused rather than re-derived"
            ),
            "no_git": "this runner writes receipts only; the release session commits",
        },
        "blocks": {str(name): dict(record) for name, record in sorted(blocks.items())},
        "runtime_seconds": float(time.perf_counter() - started),
    }
    rows = [
        level_row(level)
        for _name, record in sorted(blocks.items())
        for level in record["levels"].values()
    ]
    rows.sort(key=lambda row: (int(row["n"]), int(row["resolution"])))
    body["table"] = rows
    body["cross_resolution"] = cross_resolution(blocks)
    body["reading"] = reading_block(body)
    scale.assert_finite(body)
    body["receipt_digest"] = scale.receipt_digest(body)
    return body


def cross_resolution(blocks: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The same paths' surface existence at both resolutions, measured."""

    tables = {
        str(name): record["surface_table"]["by_path"]
        for name, record in sorted(blocks.items())
    }
    by_resolution = {
        str(int(record["resolution"])): record["surface_table"]["by_path"]
        for _name, record in sorted(blocks.items())
    }
    shared = sorted(
        set.intersection(*(set(table) for table in by_resolution.values()))
        if by_resolution
        else set()
    )
    rows = [
        {
            "path": str(path),
            "refused_at": [
                int(resolution)
                for resolution, table in sorted(
                    by_resolution.items(), key=lambda item: int(item[0])
                )
                if not bool(table[str(path)]["detail_write_executes"])
            ],
            "executes_at": [
                int(resolution)
                for resolution, table in sorted(
                    by_resolution.items(), key=lambda item: int(item[0])
                )
                if bool(table[str(path)]["detail_write_executes"])
            ],
            "refusal_text": {
                str(resolution): str(table[str(path)]["detail_refusal"])
                for resolution, table in sorted(
                    by_resolution.items(), key=lambda item: int(item[0])
                )
                if not bool(table[str(path)]["detail_write_executes"])
            },
        }
        for path in shared
    ]
    surfaces_that_exist_only_at_the_higher_resolution = [
        row
        for row in rows
        if row["refused_at"] and row["executes_at"]
        and max(row["executes_at"]) > max(row["refused_at"])
    ]
    matched = cross_resolution_placements(blocks)
    return {
        "declared": (
            "every path named by either block, with its detail surface executed at both "
            "resolutions, so a surface that exists only at the higher resolution is "
            "recorded as such rather than inferred from a node count.  The control "
            "itself is the matched-placement table below: the same placement pattern "
            "measured at both resolutions, each on a page held under its own "
            "resolution's profile, with an explicit status wherever a resolution does "
            "not measure that pattern"
        ),
        "blocks": sorted(tables),
        "paths_compared": int(len(shared)),
        "rows": rows,
        "paths": rows,
        "paths_that_exist_only_at_the_higher_resolution": [
            str(row["path"]) for row in surfaces_that_exist_only_at_the_higher_resolution
        ],
        "count_of_paths_that_exist_only_at_the_higher_resolution": int(
            len(surfaces_that_exist_only_at_the_higher_resolution)
        ),
        **matched,
    }


READING_FIELDS = ("containment", "aggregation", "sibling", "descent", "descendants")
# The matched-placement control compares the four declared readings, whose
# sources and targets are the same paths at both resolutions.  The supplementary
# reading is compared separately: its sources are this level's grandchildren, so
# its placement is *not* the same pattern at two resolutions and cannot be folded
# into the matching control.
MATCHED_FIELDS = ("containment", "aggregation", "sibling", "descent")
SUPPLEMENTARY_FIELDS = ("descendants",)


def reading_kinds(
    entry: Mapping[str, Any] | None, fields: Sequence[str] = MATCHED_FIELDS
) -> tuple[Any, ...] | None:
    """The kinds of reading a placement pattern takes at one resolution.

    A kind is the pair (reading name, whether the treatment sits at the declared
    floor), taken from the pattern's first measured entry at that resolution --
    every entry of a pattern is the same placement, so they share their kinds.
    """

    if not entry or str(entry.get("status")) != "measured" or not entry.get("entries"):
        return None
    first = entry["entries"][0]
    return tuple(
        (
            name,
            None if first.get(name) is None else bool(first[name]["at_the_floor"]),
        )
        for name in fields
    )


def placement_matches_across_resolutions(
    row: Mapping[str, Any], fields: Sequence[str] = MATCHED_FIELDS
) -> bool | None:
    """Whether a matched placement pattern gives the same kinds at every resolution.

    ``None`` when fewer than two resolutions measured it, which is not agreement.
    """

    status = row["status_at_each_resolution"]
    measured = [
        resolution
        for resolution in sorted(status, key=int)
        if str(status[resolution].get("status")) == "measured"
    ]
    kinds = [reading_kinds(status[resolution], fields) for resolution in measured]
    if len(kinds) < 2:
        return None
    return all(item == kinds[0] for item in kinds)


def reading_kind(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """One reading's own verdict, reduced to the numbers a match compares."""

    if value is None:
        return None
    return {
        "at_the_floor": bool(value["at_the_floor"]),
        "present": bool(value["present"]),
        "the_positive_control_fires": bool(value["the_positive_control_fires"]),
        "fraction_of_the_positive_control": value.get(
            "fraction_of_the_positive_control"
        ),
        "floor": float(value["floor"]),
    }


def cross_resolution_placements(
    blocks: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """The same placement pattern measured at both resolutions, matched.

    Each resolution's own block measured its own levels on a page held under its
    own profile; nothing is relabelled across resolutions.  A pattern is a
    parent path with its two child paths -- the placement, not the count -- and
    a pattern that a resolution does not measure is recorded with the reason it
    was not measured (its children's surfaces do not exist there, its children
    are past that level's count, the pattern is complete but was not selected by
    the declared cap, or the parent's own surface does not execute there).
    """

    per_resolution: dict[str, dict[str, Any]] = {}
    for _name, record in sorted(blocks.items()):
        resolution = str(int(record["resolution"]))
        by_path = record["surface_table"]["by_path"]
        measured: dict[str, list[dict[str, Any]]] = {}
        for level in record["levels"].values():
            if not bool(level.get("constructible", True)):
                continue
            for row in level["measured"]:
                path = str(row["parent_path"])
                measured.setdefault(path, []).append(
                    {
                        "n": int(level["n"]),
                        "triple_class": str(row["triple_class"]),
                        "children_paths": [
                            str(child["path"]) for child in row["surfaces"]["children"]
                        ],
                        "containment": reading_kind(row.get("containment")),
                        "aggregation": reading_kind(row.get("aggregation")),
                        "sibling": reading_kind(row.get("sibling")),
                        "descent": reading_kind(row.get("descent")),
                        "descendants": reading_kind(row.get("descendants")),
                    }
                )
        for entries in measured.values():
            entries.sort(key=lambda entry: int(entry["n"]))
        surface_limitations: dict[str, list[dict[str, Any]]] = {}
        for level in record["levels"].values():
            if not bool(level.get("constructible", True)):
                continue
            for row in level.get("surface_limitations", ()):
                pattern = str(row["parent_path"])
                surface_limitations.setdefault(pattern, []).append(
                    {
                        "n": int(level["n"]),
                        "triple_class": str(row["triple_class"]),
                        "children_paths": [str(child["path"]) for child in row["children"]],
                    }
                )
        per_resolution[resolution] = {
            "inventory": {
                str(path): {
                    "detail_write_executes": bool(entry["detail_write_executes"]),
                    "detail_refusal": entry["detail_refusal"],
                }
                for path, entry in by_path.items()
            },
            "measured": measured,
            "surface_limitations": surface_limitations,
        }

    paths = sorted(
        {
            str(path)
            for table in per_resolution.values()
            for path in table["inventory"]
        }
        | {
            str(path)
            for table in per_resolution.values()
            for path in table["measured"]
        }
    )
    rows_out: list[dict[str, Any]] = []
    for path in paths:
        children_paths = [str(path) + "L", str(path) + "R"]
        status: dict[str, Any] = {}
        inventory: dict[str, Any] = {}
        for resolution, table in sorted(
            per_resolution.items(), key=lambda item: int(item[0])
        ):
            entries = table["measured"].get(path)
            parent_executes = bool(
                table["inventory"].get(path, {}).get("detail_write_executes", False)
            )
            child_executes = [
                bool(table["inventory"].get(child, {}).get("detail_write_executes", False))
                for child in children_paths
            ]
            inventory[resolution] = {
                "parent_detail_write_executes": parent_executes,
                "children_detail_write_executes": dict(zip(children_paths, child_executes)),
                "children_detail_refusal": {
                    child: table["inventory"].get(child, {}).get("detail_refusal")
                    for child, executes in zip(children_paths, child_executes)
                    if not executes
                },
            }
            if entries:
                status[resolution] = {
                    "status": "measured",
                    "at_counts": [int(entry["n"]) for entry in entries],
                    "entries": entries,
                }
            elif not parent_executes:
                status[resolution] = {"status": "no_parent_surface_at_this_resolution"}
            elif not all(child_executes):
                status[resolution] = {
                    "status": "a_child_surface_does_not_exist_at_this_resolution",
                    "children_without_a_detail_surface": [
                        child
                        for child, executes in zip(children_paths, child_executes)
                        if not executes
                    ],
                    "surface_limitation_rows": table["surface_limitations"].get(path, []),
                }
            else:
                status[resolution] = {
                    "status": "not_measured_by_the_declared_cap_or_the_level_count"
                }
        kind_rows: dict[str, Any] = {
            "parent_path": path,
            "children_paths": children_paths,
            "status_at_each_resolution": status,
            "surfaces_at_each_resolution": inventory,
            "measured_at_resolutions": [
                resolution
                for resolution in sorted(status, key=int)
                if str(status[resolution].get("status")) == "measured"
            ],
            "the_parent_surface_executes_at_every_resolution": bool(
                all(
                    bool(entry["parent_detail_write_executes"])
                    for entry in inventory.values()
                )
            ),
        }
        kind_rows[
            "the_same_kind_of_reading_at_every_resolution_that_measures_it"
        ] = placement_matches_across_resolutions(kind_rows)
        kind_rows[
            "the_same_supplementary_reading_at_every_resolution_that_measures_it"
        ] = placement_matches_across_resolutions(kind_rows, SUPPLEMENTARY_FIELDS)
        rows_out.append(kind_rows)

    both = [row for row in rows_out if len(row["measured_at_resolutions"]) >= 2]
    supplementary_both = [
        row
        for row in both
        if row["the_same_supplementary_reading_at_every_resolution_that_measures_it"]
        is not None
    ]
    parent_always_child_never = [
        row
        for row in rows_out
        if bool(row["the_parent_surface_executes_at_every_resolution"])
        and any(
            entry["status"] == "a_child_surface_does_not_exist_at_this_resolution"
            for entry in row["status_at_each_resolution"].values()
        )
    ]
    return {
        "placement_patterns": rows_out,
        "patterns_named_by_either_block": int(len(rows_out)),
        "patterns_measured_at_both_resolutions": int(len(both)),
        "every_pattern_measured_at_both_resolutions_gives_the_same_kind_of_reading": bool(
            all(
                bool(row["the_same_kind_of_reading_at_every_resolution_that_measures_it"])
                for row in both
            )
        ),
        "the_matched_control_compares": list(MATCHED_FIELDS),
        "supplementary_reading_scope": (
            "the supplementary two-level reading is compared separately and is not part "
            "of the matched-placement control: its sources are this level's "
            "grandchildren, so at two resolutions it places different nodes and a "
            "difference between its two readings is a difference of placement, not a "
            "reading that follows the node count.  A pattern whose supplementary reading "
            "differs therefore does not fail the control; it is reported here"
        ),
        "patterns_where_the_supplementary_reading_differs_between_resolutions": [
            {
                "parent_path": str(row["parent_path"]),
                "measured_at": [
                    int(resolution) for resolution in row["measured_at_resolutions"]
                ],
            }
            for row in supplementary_both
            if not bool(
                row["the_same_supplementary_reading_at_every_resolution_that_measures_it"]
            )
        ],
        "patterns_measured_at_only_one_resolution": [
            {
                "parent_path": str(row["parent_path"]),
                "measured_at": [
                    int(resolution) for resolution in row["measured_at_resolutions"]
                ],
                "status": row["status_at_each_resolution"],
            }
            for row in rows_out
            if len(row["measured_at_resolutions"]) == 1
        ],
        "patterns_where_the_parent_surface_exists_at_every_resolution_but_a_child_surface_does_not": [
            str(row["parent_path"]) for row in parent_always_child_never
        ],
        "count_of_patterns_where_the_parent_surface_exists_at_every_resolution_but_a_child_surface_does_not": int(
            len(parent_always_child_never)
        ),
    }


def report(receipt: Mapping[str, Any]) -> str:
    """The receipt's own figures, branch first."""

    lines = [
        f"schema: {receipt['schema']}",
        f"branch: {receipt['reading']['branch']}",
        f"level branches: {receipt['reading']['branches_returned_by_the_levels']}",
        "levels:",
    ]
    for row in receipt["table"]:
        lines.append(
            f"  N={row['n']} res={row['resolution']} complete triples "
            f"{row['complete_triples']} measured {row['triples_measured']} "
            "surface-limitation triples "
            f"{row['surface_limitation_triples']} containment fraction "
            f"{row['containment_greatest_fraction']!r} at floor {row['containment_at_the_floor']}"
            f"/{row['triples_measured']} present {row['containment_present']} "
            f"assignment-specific {row['containment_assignment_specific']} "
            f"aggregation {row['aggregation_greatest_fraction']!r} descent "
            f"{row['descent_greatest_fraction']!r} descendants "
            f"{row['descendants_greatest_fraction']!r} at floor "
            f"{row['descendants_at_the_floor']}/{row['descendants_measured']} "
            "scale-surface containment "
            f"{row['companion_scale_containment_greatest_fraction']!r} "
            "port-fallback "
            f"{row['port_fallback_scale_containment_present']}/"
            f"{row['port_fallback_measured']} "
            f"({row['runtime_seconds']:.1f} s) branch {row['branch']}"
        )
    cross = receipt["cross_resolution"]
    lines.append(
        "cross-resolution: "
        f"{cross['count_of_paths_that_exist_only_at_the_higher_resolution']} "
        "paths exist only at the higher resolution; "
        f"{cross['patterns_measured_at_both_resolutions']} placement patterns "
        "measured at both resolutions, same kind of reading at every one that "
        f"measures it: "
        f"{cross['every_pattern_measured_at_both_resolutions_gives_the_same_kind_of_reading']}; "
        f"{cross['count_of_patterns_where_the_parent_surface_exists_at_every_resolution_but_a_child_surface_does_not']} "
        "patterns have a parent surface at every resolution while a child "
        "surface does not"
    )
    lines.append("verdicts:")
    for name, value in receipt["reading"]["verdicts"].items():
        lines.append(f"  {name}: {value}")
    lines.append(f"controls: {receipt['reading']['controls']}")
    lines.append(f"honest_negatives: {receipt['reading']['honest_negatives']}")
    lines.append(f"receipt_digest: {receipt['receipt_digest']}")
    lines.append(f"runtime_seconds: {receipt['runtime_seconds']:.2f}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------
def write_json(path: Path, body: Mapping[str, Any]) -> None:
    """One receipt on disk, canonically ordered."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(body, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


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
    arguments = parser.parse_args(argv)
    if arguments.block == "merge":
        blocks = {}
        for name, path in BLOCK_PATHS.items():
            if not path.exists():
                raise SystemExit(
                    f"the declared block {name!r} has not run: {path} is missing"
                )
            blocks[name] = json.loads(path.read_text(encoding="utf-8"))
        receipt = merge_blocks(blocks)
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
    output = Path(arguments.output) if arguments.output else BLOCK_PATHS[arguments.block]
    write_json(output, record)
    print(
        f"block {arguments.block}: resolution {resolution}, points run "
        f"{record['points_run']}"
    )
    for row in record["points_not_run"]:
        print(f"  not run: N={row['n']}: {row['reason']}")
    for n, level in sorted(record["levels"].items(), key=lambda item: int(item[0])):
        if not bool(level.get("constructible")):
            print(f"  N={n}: not constructible: {level['reason']}")
            continue
        readings = level["readings"]
        print(
            f"  N={n}: complete triples {readings['complete_triples']} "
            f"surface-limitation triples {readings['surface_limitation_triples']} "
            f"parents {readings['parents_with_an_executable_declared_detail_surface']}"
            f"/{readings['parents_in_the_level']} containment "
            f"{readings['containment']['greatest_fraction_of_the_positive_control']!r} "
            f"at floor {readings['containment']['readings_at_the_floor']}"
            f"/{readings['complete_triples']} scale containment "
            f"{readings['companion_scale_surfaces']['containment_scale_greatest_fraction']!r} "
            f"branch {readings['branch']} ({level['runtime_seconds']:.1f} s)"
        )
    print(f"content_digest: {record['content_digest']}")
    print(f"runtime_seconds: {record['runtime_seconds']:.2f}")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
