"""What sets the capacity of the placement addressing?

DECLARED BEFORE THE FIRST RUN -- statistic, discriminator, ceiling definition,
branches, controls, axes, levels and budget.

THE QUESTION.  The delivered rank receipt measured the eight declared items and
found the item-to-deposit map full rank at the crowded held state, with the
item-specific placement separating every pair at 1 - LOSS_ALLOWANCE.  Eight is
therefore not a measured ceiling: it is the size of the item list as declared.
This runner asks how many items the addressing carries, and what the ceiling
tracks, by extending the declared family along its own hierarchy.

THE DECLARED FAMILY RULE, verbatim.  ``run_fractal_durability_exploration``
declares its items as "one root scale item, one root detail item, then node
details down to width 7".  The items are packet placements on the field's own
floor-halving dyadic tree of the ``port_count`` ports of the profile
(``cassi_resonant_field._packet_support``, ``_packet_spatial_mode``).  The
declared extension continues that same rule, unchanged, in the tree's own
order:

    item 0        the root scale mode      (component "scale", path "")
    item 1        the root detail mode     (component "detail", path "")
    item 2, 3, .. then, at depth 1, 2, 3, ... in order, every node of the tree
                  whose support holds at least two ports, addressed with the
                  "detail" component, in the tree's own left-before-right
                  order.

The rule is the delivered one, continued; nothing new is invented.  It is
verified, not assumed: the first eight items of the declared family at the
declared profile must be the delivered ``ITEM_SPECS`` entry for entry (name,
path, component, flow signal), and that equality is measured and reported.

THE DECLARED FAMILY'S INVENTORY.  A node whose support is a single port carries
no detail mode: the field refuses it with its own error (measured, not assumed).
So the addressable family is exactly {the root scale} union {the nodes with a
support of at least two ports}, and its count is measured on the real surface
(one owner write per item) rather than assumed.  For a port count P the tree has
2P - 1 nodes, P of which are leaves, so the addressable family has
(P - 1) + 1 = P items: the inventory and the port count are the same number, and
that identity is what the sweep tests.

THE DECLARED SECOND AXIS.  The delivered profile is the metric builder's own
row at ``ports_per_pool = 4`` (port count 28).  At that resolution the family's
inventory is 28, so the declared range N = 8, 16, 24, 32 cannot be constructed
there: N = 32 has no 32nd item.  Reaching N = 32 therefore requires one declared
second axis, declared here before the run:

    axis 1  N (the number of declared items), in this order:
            8, 16, 24, 28, 32 at resolution 4 -- 28 is the whole inventory at
            that resolution and 32 is the count the inventory cannot reach, so
            the block records the structural boundary at its own profile -- and
            32 at resolution 8, where the 32nd item exists.
    axis 2  the profile resolution
            (``ports_per_pool``): 4 (the delivered profile, port count 28) and
            8 (port count 56).

The second resolution is built by the declared builder with its own declared
constructor argument: the metric row's own ladder inverse-mass vector re-expanded
at the new resolution (``metric.ladder_inverse_mass(..., ports_per_pool=8)``),
never the 28-port vector reused, and the built profile's own dimensions are
asserted (port count, page shape, inverse-mass length) before any arm runs.

DECLARED STATISTIC (the delivered one, unchanged).  On one page state,
``J[i][j] = (read at item i's placement after a probe write at item j's
placement - the same read before) / probe work``, one fresh owner per probe;
``tol = max(FLOOR_FACTOR * sigma_1(J(a) - J(a/2)), EPS_FACTOR * sigma_1(J))``;
rank = the count of singular values above tol; margin = ``sigma_min / tol``.

DECLARED DISCRIMINATOR (the delivered one, unchanged).  ``Jn = J /
mean(diag(J))``; the item separation of a pair is the largest absolute
difference between their normalized rows; a pair is distinguishable when its
separation exceeds ``CONTRAST_FLOOR``; an orthogonal pair is predicted at 1.0.

DECLARED PER-LEVEL ARMS (the delivered three, on the level's own page).  Each
level's page is the level's own held store -- the declared items written one at
a time through the owner write path at the declared write budget, then held for
the declared horizon through the owner at the measured neutral gain -- so the
page, the write budget, the hold and the profile are the delivered ones at every
level.  On that page: the specific arm (every item at its own placement, which
carries the half-probe finite-difference floor and the zero-work probe), the
shared arm (every item at item 0's placement, reusing the measured floor), and
the duplicate arm (item 1 at item 0's placement, reusing the measured floor).
Their predicates are the delivered ones, applied per level, so every sweep point
carries its own firing control.

DECLARED CEILING DEFINITION.  The ceiling is the smallest declared N at which
any of these holds:

    (a) the level is not constructible: the declared family has no N-th item at
        that level's resolution (measured: the inventory count and the field's
        own refusal for the next candidate path);
    (b) the specific arm's rank is below N;
    (c) the specific arm's margin ``sigma_min / tol`` is at or below 1 (the
        smallest singular value is inside the declared tolerance);
    (d) the specific arm's least item separation falls below
        ``1 - LOSS_ALLOWANCE`` (the 0.95 allowance).

DECLARED BRANCHES (what the ceiling tracks; the reading that decides each one).

    1. capacity-tracks-the-declared-scale-tree: every constructed level below
       the ceiling satisfies the declared bar (full rank, margin > 1, all pairs
       distinguishable, least separation at or above 1 - LOSS_ALLOWANCE), the
       ceiling is (a), and the inventory equals the port count at every measured
       resolution.  Reading: the addressing capacity is the field's own
       multi-scale depth -- the count of its dyadic nodes -- and the delivered
       eight-item list is a declared stopping depth, not a field limit.
    2. capacity-is-dynamical: a constructed level fails one of (b), (c), (d).
       Reading: the receipt reports, for the failing level and the level below
       it, the page's total deposit energy, the hold's measured deposits and
       applied drive work, the measured finite-difference floor and its ratio to
       sigma_1(J) -- the readings that say which of the page's own quantities
       the failure coincides with.
    3. smooth-degradation-with-no-ceiling: no level fails and none is
       unconstructible in the swept range, and the least separation falls
       monotonically.  Reading: a least-squares fit of the least separation
       against log(N) with its greatest absolute residual and its R^2, reported
       only when the least separation actually falls (a fit over equal values is
       reported as degenerate, not fitted).

DECLARED CONTROLS, unchanged and carried by every level.  The duplicate arm must
show rank exactly N - 1 with the duplicated pair at the contrast floor (the
firing control that proves the rank reading can fall below N); the shared arm
must show rank 1 with no pair distinguishable; the zero-work probe must be
rejected and must move no read (measured once per level, on the specific arm);
the finite-difference floor is measured on the level's own specific arm and
reused by that level's other arms; the blank page must read nothing; and the
delivered item list must be restored after the run (the extension is installed
in this process only).

DECLARED BUDGET AND BOUNDARY.  Each block declares its own wall-clock budget
(``BLOCK_BUDGET_SECONDS``); levels run in the declared order and a level is
started only when the measured cost of the finished levels projects it inside
the budget.  A level that does not run is reported with its reason.  The top of
the range is cut, never the declared arms: no level runs with a shortened arm.

WHAT THIS SWEEP DOES NOT ESTABLISH (declared).  Nothing here measures a
distribution over profiles, write budgets, holds or probe amplitudes; the
capacity identity is measured at two resolutions of one declared metric row; the
probe budget is fixed while the page's deposit grows with N, so a failure would
be a failure at this probe budget; the rank reading is a finite-difference
reading whose floor is the measured half-probe floor plus the declared relative
floor; and the family is extended along the field's own scale tree only, so no
claim is made about items outside that tree.

NO GIT.  This runner writes receipts only; the release session commits.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
import traceback
from collections import deque
from contextlib import contextmanager
from dataclasses import replace
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
import run_store_addressing_rank as rank

SCHEMA = "cassifi.store-addressing-capacity.v1"
BLOCK_SCHEMA = "cassifi.store-addressing-capacity.block.v1"
RECEIPT_PATH = Path("_diag/store-addressing-capacity/exploration.json")
BLOCK_PATHS = {
    "declared-profile": Path("_diag/store-addressing-capacity/block-declared-profile.json"),
    "higher-resolution": Path("_diag/store-addressing-capacity/block-higher-resolution.json"),
}

# The declared axes: (ports_per_pool, declared item counts), run in this order.
DECLARED_PROFILE_RESOLUTION = 4
BLOCK_SPECS: dict[str, tuple[int, tuple[int, ...]]] = {
    "declared-profile": (DECLARED_PROFILE_RESOLUTION, (8, 16, 24, 28, 32)),
    "higher-resolution": (8, (32,)),
}
RESOLUTION_LEVELS: tuple[tuple[int, tuple[int, ...]], ...] = tuple(
    BLOCK_SPECS[name] for name in ("declared-profile", "higher-resolution")
)
DECLARED_LEVELS = tuple(
    int(count) for _resolution, counts in RESOLUTION_LEVELS for count in counts
)
BLOCK_BUDGET_SECONDS = 4200.0
DELIVERED_ITEM_SPECS = tuple(durability.ITEM_SPECS)
DELIVERED_ITEM_COUNT = len(DELIVERED_ITEM_SPECS)


def plain(value: Any) -> Any:
    """One measured mapping, detached from whatever published it."""

    return scale.plain(value)


# --------------------------------------------------------------------------
# the declared family rule
# --------------------------------------------------------------------------
def dyadic_nodes(port_count: int) -> list[dict[str, Any]]:
    """Every node of the field's own floor-halving tree, in its own order.

    The order is the tree's breadth-first left-before-right order, which is the
    order the delivered item list already uses (root, then L, then R, then LL,
    LR, RL, RR), and it is the order the declared extension continues.
    """

    if isinstance(port_count, bool) or not isinstance(port_count, int) or port_count < 1:
        raise ValueError("the declared rule needs a positive integer port count")
    rows: list[dict[str, Any]] = []
    queue: deque[tuple[str, int, int]] = deque([("", 0, int(port_count))])
    while queue:
        path, start, stop = queue.popleft()
        rows.append(
            {
                "path": path,
                "depth": int(len(path)),
                "start": int(start),
                "stop": int(stop),
                "size": int(stop - start),
            }
        )
        if stop - start <= 1:
            continue
        middle = start + (stop - start) // 2
        queue.append((path + "L", start, middle))
        queue.append((path + "R", middle, stop))
    return rows


def declared_family(port_count: int) -> dict[str, Any]:
    """The declared family and the candidates its own rule refuses.

    The rule is the delivered one continued: the root scale, the root detail,
    then every node detail in the tree's own order, skipping -- and recording --
    the nodes whose support is a single port, which carry no detail mode.
    """

    rows = dyadic_nodes(port_count)
    specs: list[durability.ItemSpec] = [
        durability.ItemSpec("root-scale", "", "scale", (1.0, 0.0)),
        durability.ItemSpec("root-detail", "", "detail", (1.0, 0.0)),
    ]
    refused: list[dict[str, Any]] = []
    depths: dict[str, int] = {"0": 2}
    for row in rows:
        if row["depth"] == 0:
            continue
        if row["size"] <= 1:
            refused.append(
                {
                    "path": str(row["path"]),
                    "depth": int(row["depth"]),
                    "size": int(row["size"]),
                    "reason": "a single-port node carries no detail mode",
                }
            )
            continue
        index = len(specs)
        if index < DELIVERED_ITEM_COUNT:
            delivered = durability.ITEM_SPECS[index]
            if (delivered.path, delivered.component) != (row["path"], "detail"):
                raise RuntimeError(
                    "the declared extension rule does not reproduce the delivered "
                    f"item {index}: the rule gives {row['path']!r}, the delivered "
                    f"list has {delivered.path!r}"
                )
            spec = delivered
        else:
            spec = durability.ItemSpec(f"detail-{row['path']}", row["path"], "detail", (1.0, 0.0))
        specs.append(spec)
        depths[str(row["depth"])] = depths.get(str(row["depth"]), 0) + 1
    head_matches = tuple(
        (spec.name, spec.path, spec.component, tuple(spec.flow_signal))
        for spec in specs[:DELIVERED_ITEM_COUNT]
    ) == tuple(
        (spec.name, spec.path, spec.component, tuple(spec.flow_signal))
        for spec in durability.ITEM_SPECS
    )
    return {
        "declared_rule": (
            "root scale, root detail, then every node detail of the port-count "
            "dyadic tree in its own breadth-first left-before-right order; a node "
            "whose support is a single port is refused by the field's own rule and "
            "recorded, not declared"
        ),
        "port_count": int(port_count),
        "specs": tuple(specs),
        "refusals": refused,
        "nodes": len(rows),
        "leaves": len(refused),
        "depths": depths,
        "head_matches_the_delivered_item_specs": bool(head_matches),
    }


def mode_matrix(port_count: int, specs: Sequence[durability.ItemSpec]) -> np.ndarray:
    """The declared directions of a family, straight from the field's own rule."""

    columns = [
        resonant._packet_spatial_mode(port_count, spec.path, spec.component)[0]
        for spec in specs
    ]
    return np.asarray(columns, dtype=np.float64).T


def family_orthogonality(port_count: int, specs: Sequence[durability.ItemSpec]) -> dict[str, Any]:
    """How orthogonal the declared family's own spatial modes are, measured."""

    matrix = mode_matrix(port_count, specs)
    gram = matrix.T @ matrix
    off = (
        float(np.max(np.abs(gram - np.eye(gram.shape[0])))) if gram.size else 0.0
    )
    return {
        "declared": (
            "the field's own declared mode of each family item, taken from "
            "cassi_resonant_field._packet_spatial_mode, and the greatest absolute "
            "off-diagonal entry of their Gram matrix; zero is an orthogonal family"
        ),
        "items": int(matrix.shape[1]),
        "mode_norms_min": float(np.min(np.linalg.norm(matrix, axis=0))) if matrix.size else 0.0,
        "mode_norms_max": float(np.max(np.linalg.norm(matrix, axis=0))) if matrix.size else 0.0,
        "greatest_absolute_off_diagonal_gram_entry": off,
        "the_declared_family_is_orthonormal_at_the_measured_floor": bool(off <= 1e-12),
    }


@contextmanager
def family_installed(specs: Sequence[durability.ItemSpec]) -> Iterator[None]:
    """Extend the delivered item list in this process only, and restore it.

    Every instrument in this family reads ``durability.ITEM_SPECS`` by attribute
    at call time, so the delivered machinery -- the store-scale hold, the
    feedback drives and phase readouts, the rank runner's arms -- operates on the
    extended family unchanged.  The delivered runners are separate processes and
    keep their own list; this runner asserts the list is back to the delivered
    tuple when the block ends.
    """

    original = durability.ITEM_SPECS
    durability.ITEM_SPECS = tuple(specs)
    try:
        yield
    finally:
        durability.ITEM_SPECS = original


# --------------------------------------------------------------------------
# the profile at a declared resolution
# --------------------------------------------------------------------------
def resolution_profile(ports_per_pool: int) -> tuple[Any, dict[str, Any]]:
    """The delivered metric row at the declared resolution, built by its own builder."""

    row = metric.ladder_row(str(opts.OwnerSurfaceOptionsConfig().profile_name))
    base = metric.build_metric_profile(row)
    report: dict[str, Any] = {
        "row": str(row.name),
        "kind": str(row.kind),
        "declared_profile_ports_per_pool": int(base.ports_per_pool),
        "ports_per_pool": int(ports_per_pool),
    }
    if int(ports_per_pool) == int(base.ports_per_pool):
        profile = base
        report["built"] = (
            "the declared builder's own row at the declared profile resolution, "
            "unchanged"
        )
    else:
        if str(row.kind) not in ("ladder-geometric", "ladder-uniform"):
            raise RuntimeError(
                "the declared resolution change is only defined for the ladder rows "
                f"this builder expands by ports_per_pool; row {row.name!r} is {row.kind!r}"
            )
        vector = metric.ladder_inverse_mass(
            float(row.ladder_ratio),
            normalization=row.normalization,
            ports_per_pool=int(ports_per_pool),
        )
        profile = replace(
            base, ports_per_pool=int(ports_per_pool), projected_inv_mass=vector
        )
        report["built"] = (
            "the same declared row at the declared resolution: its own ladder "
            "inverse-mass vector re-expanded at this resolution by the metric "
            "harness's own constructor, replacing the delivered vector rather than "
            "reusing it"
        )
    # The built profile's own dimensions, asserted before any arm runs.
    port_count = int(profile.port_count)
    inertia = np.asarray(profile.projected_inv_mass, dtype=np.float64)
    expected_shape = (1, 9 * port_count + 9, 1)
    if port_count != 7 * int(ports_per_pool):
        raise RuntimeError(
            f"the built profile's port count {port_count} is not 7 x {ports_per_pool}"
        )
    if len(inertia) != 2 * port_count:
        raise RuntimeError(
            f"the built profile carries {len(inertia)} inverse-mass entries for "
            f"{port_count} ports; the declared layout needs {2 * port_count}"
        )
    if tuple(profile.page_shape) != expected_shape:
        raise RuntimeError(
            f"the built profile's page shape {tuple(profile.page_shape)} is not "
            f"{expected_shape} for {port_count} ports"
        )
    report.update(
        {
            "port_count": port_count,
            "page_shape": [int(value) for value in profile.page_shape],
            "inverse_mass_entries": int(len(inertia)),
            "inverse_mass_length_is_the_declared_layout": True,
            "inverse_mass_uniform": bool(float(inertia.max()) == float(inertia.min())),
        }
    )
    return profile, report


# --------------------------------------------------------------------------
# the inventory: which of the declared candidates the field accepts
# --------------------------------------------------------------------------
def inventory(profile: Any, family: Mapping[str, Any]) -> dict[str, Any]:
    """The declared family's addressable count, measured on the real surface."""

    specs: tuple[durability.ItemSpec, ...] = family["specs"]
    owner, home = consumer.open_owner(profile, prefix="capacity-inventory-")
    accepted = 0
    refused: list[dict[str, Any]] = []
    try:
        blank_page = durability.page_sha256(owner.state.resonant_workspace)
        blank_read = float(
            plain(
                owner.read_packet_deposit(
                    path=specs[0].path,
                    component=specs[0].component,
                    flow_signal=[float(value) for value in specs[0].flow_signal],
                )
            )["recovered_deposit"]
        )
        for index, spec in enumerate(specs):
            result = plain(
                owner.write_packet_impulse(
                    f"capacity:inventory:write:{index}",
                    path=spec.path,
                    component=spec.component,
                    flow_signal=[float(value) for value in spec.flow_signal],
                    work_budget=float(rank.PROBE_BUDGET),
                )
            )
            receipt = plain(result["impulse_receipt"])
            if bool(receipt["accepted"]):
                accepted += 1
            else:
                refused.append(
                    {"index": int(index), "path": spec.path, "outcome": "write not accepted"}
                )
        # The first candidate path the declared rule itself refuses, measured on
        # the same surface with the same call.
        boundary: list[dict[str, Any]] = []
        for row in family["refusals"][:1]:
            boundary.append(
                {
                    "path": str(row["path"]),
                    "depth": int(row["depth"]),
                    "size": int(row["size"]),
                    "outcome": measure_refusal(owner, str(row["path"]), "detail"),
                }
            )
        beyond = "L" * (int(profile.ports_per_pool).bit_length() + 8)
        boundary.append(
            {
                "path": beyond,
                "depth": int(len(beyond)),
                "size": 0,
                "outcome": measure_refusal(owner, beyond, "detail"),
            }
        )
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)
    return {
        "declared": (
            "every item of the declared family written once through the owner write "
            "path at the declared probe budget on one fresh owner, plus the first "
            "candidate path the rule refuses and a path that descends beyond a leaf, "
            "so the family's addressable count and the field's own refusal are both "
            "measured rather than assumed"
        ),
        "declared_family_size": int(len(specs)),
        "writes_accepted": int(accepted),
        "writes_refused": refused,
        "addressable_count": int(accepted),
        "nodes": int(family["nodes"]),
        "leaves_refused_by_the_rule": int(len(family["refusals"])),
        "depths": dict(family["depths"]),
        "head_matches_the_delivered_item_specs": bool(
            family["head_matches_the_delivered_item_specs"]
        ),
        "boundary": boundary,
        "blank_page_sha256": str(blank_page),
        "blank_page_read_on_the_root_scale": blank_read,
        "the_blank_page_reads_nothing": bool(abs(blank_read) <= float(rank.EPS_FACTOR)),
        "the_addressable_count_is_the_port_count": bool(
            int(accepted) == int(profile.port_count)
        ),
    }


def measure_refusal(owner: Any, path: str, component: str) -> str:
    """The field's own refusal for one packet path, as its own error text."""

    try:
        owner.write_packet_impulse(
            "capacity:inventory:refusal",
            path=path,
            component=component,
            flow_signal=[1.0, 0.0],
            work_budget=float(rank.PROBE_BUDGET),
        )
    except Exception as error:  # the field's own declared refusal
        return f"{type(error).__name__}: {error}"
    return "accepted"


# --------------------------------------------------------------------------
# one level of the sweep
# --------------------------------------------------------------------------
def level_settings(count: int) -> rank.AddressingRankConfig:
    """The delivered measurement settings at one declared item count."""

    indices = tuple(range(int(count)))
    return rank.AddressingRankConfig(
        item_indices=indices,
        store_config=replace(
            rank.AddressingRankConfig().store_config,
            item_indices=indices,
            neutrality_probe_items=(),
        ),
    )


def level_block(
    profile: Any,
    count: int,
    *,
    resolution: int,
    inventory_record: Mapping[str, Any],
    hold_settings: Mapping[str, Any],
) -> dict[str, Any]:
    """One declared N: its level's own held page, the delivered arms and controls.

    The block's own hold settings -- the measured captures, the measured neutral
    gain, the declared phase angle and the per-item phase references over the
    block's whole family -- are passed in, so every level of a block is held at
    the same measured settings.
    """

    family = declared_family(int(profile.port_count))
    specs = family["specs"]
    if int(count) > int(inventory_record["addressable_count"]):
        return {
            "n": int(count),
            "ports_per_pool": int(resolution),
            "constructible": False,
            "reason": (
                "the declared family has no item at this count at this resolution: "
                f"the family's addressable inventory is "
                f"{inventory_record['addressable_count']} items and its next "
                "candidate path is refused by the field's own rule"
            ),
            "declared_family_size": int(len(specs)),
            "addressable_count": int(inventory_record["addressable_count"]),
            "boundary": list(inventory_record["boundary"]),
        }
    captures = hold_settings["captures"]
    gain = float(hold_settings["gain"])
    phase_degrees = float(hold_settings["phase_degrees"])
    per_item = hold_settings["per_item"]
    started = time.perf_counter()
    # The level's own settings are built against the family the block installed,
    # so every declared item index in them resolves against the extended family.
    settings = level_settings(int(count))
    # The extension must have reached the delivered instruments before any
    # measurement is taken, and the arms must be addressing the declared
    # family's own items, not the delivered list's first N.
    addressed = [
        rank.placement_spec(index, "specific", settings).name for index in range(int(count))
    ]
    expected = [spec.name for spec in specs[: int(count)]]
    if addressed != expected:
        raise RuntimeError(
            "the installed family did not reach the delivered placement rule: "
            f"{addressed[:4]!r} != {expected[:4]!r}"
        )
    held = rank.held_state(
        profile,
        settings,
        indices=tuple(range(int(count))),
        gain=gain,
        phase_degrees=phase_degrees,
        phase_references=per_item,
        captures=captures,
        label=f"capacity-held-{count}",
    )
    page = held.pop("held_page_object")
    # The sweep's arms all address the level's own held page -- the declared items
    # written through the owner write path and then held for the declared horizon
    # -- which is the delivered operating point.  The page record carries that one
    # digest under the held key and, so the delivered arm machinery reads the same
    # page it always reads, under the written key too.
    page_record = {
        "held_page_sha256": str(held["held_page_sha256"]),
        "written_page_sha256": str(held["held_page_sha256"]),
        "page_kind": "the_levels_own_held_page",
    }
    arms = {
        "specific": rank.arm_block(
            profile,
            settings,
            page,
            mode="specific",
            label=f"capacity-held-{count}-specific",
            page_record=page_record,
            with_zero=True,
        )
    }
    measured_floor = float(
        arms["specific"]["rank"]["tolerance"]["finite_difference_floor"]
    )
    for mode in ("shared", "duplicate"):
        arms[mode] = rank.arm_block(
            profile,
            settings,
            page,
            mode=mode,
            label=f"capacity-held-{count}-{mode}",
            page_record=page_record,
            floor_value=measured_floor,
        )
    part_two = rank.part_two(arms, settings)
    deposits = rank.deposit_vector(profile, settings, page, mode="specific")
    deposits_reading = rank.difference_reading(deposits, settings)
    blank_owner, blank_home = consumer.open_owner(
        profile, prefix=settings.owner_home_prefix
    )
    try:
        blank_page_digest = durability.page_sha256(blank_owner.state.resonant_workspace)
        blank_reads = {
            durability.ITEM_SPECS[index].name: rank.read_at(
                blank_owner, rank.placement_spec(index, "specific", settings)
            )["recovered_deposit"]
            for index in range(int(count))
        }
    finally:
        blank_owner.close()
        shutil.rmtree(blank_home, ignore_errors=True)
    config_record = settings.as_dict()
    held_record = dict(held)
    specific = arms["specific"]
    record = {
        "n": int(count),
        "ports_per_pool": int(resolution),
        "constructible": True,
        "family": {
            "declared_rule": family["declared_rule"],
            "names": [spec.name for spec in specs[: int(count)]],
            "depths": dict(family["depths"]),
            "head_matches_the_delivered_item_specs": bool(
                family["head_matches_the_delivered_item_specs"]
            ),
        },
        "settings": config_record,
        "hold": held_record,
        "page_sha256": str(held["held_page_sha256"]),
        "arms": arms,
        "part_two": part_two,
        "readings": {
            "items": int(count),
            "rank": int(specific["rank"]["rank"]),
            "the_specific_arm_is_full_rank": bool(
                specific["rank"]["the_map_is_full_rank"]
            ),
            "singular_values": [float(value) for value in specific["rank"]["singular_values"]],
            "smallest_singular_value": float(specific["rank"]["singular_values"][-1]),
            "tolerance": float(specific["rank"]["tolerance"]["tolerance"]),
            "margin_smallest_singular_value_against_tolerance": float(
                specific["rank"]["smallest_singular_value_against_tolerance"]
            ),
            "measured_finite_difference_floor": float(measured_floor),
            "largest_singular_value": float(specific["map"]["largest_singular_value"]),
            "finite_difference_floor_relative_to_the_largest_singular_value": float(
                measured_floor / float(specific["map"]["largest_singular_value"])
                if float(specific["map"]["largest_singular_value"]) != 0.0
                else 0.0
            ),
            "least_item_separation": specific["separation"]["least_item_separation"],
            "greatest_item_separation": specific["separation"]["greatest_item_separation"],
            "pairs_above_the_contrast_floor": int(
                specific["separation"]["distinguishable_item_pairs"]
            ),
            "pairs_measured": int(specific["separation"]["item_pairs_measured"]),
            "every_pair_is_distinguishable": bool(
                specific["separation"]["every_item_pair_is_distinguishable"]
            ),
            "least_probe_separation": specific["separation"]["least_probe_separation"],
            "separation_histogram": separation_histogram(specific, settings),
            "duplicate_rank": int(arms["duplicate"]["rank"]["rank"]),
            "duplicate_rank_is_one_below_the_item_count": bool(
                int(arms["duplicate"]["rank"]["rank"]) == int(count) - 1
            ),
            "duplicated_pair_separation": part_two["duplicated_pair"]["separation"],
            "shared_rank": int(arms["shared"]["rank"]["rank"]),
            "shared_arm_separates_no_pair": bool(
                arms["shared"]["separation"]["no_item_pair_is_distinguishable"]
            ),
            "zero_work_probe_greatest_response": specific["zero_probe_greatest_response"],
            "zero_work_probes_are_rejected": bool(
                specific["zero_probe_map"]["zero_work_probes_are_rejected"]
            )
            if specific["zero_probe_map"] is not None
            else False,
            "deposits": deposits_reading["deposits"],
            "measured_deposit_total_energy": float(
                sum(float(value) for value in deposits_reading["deposits"])
            ),
            "measured_deposits_constant_at_the_tolerance": bool(
                deposits_reading["the_deposit_vector_is_constant_at_the_tolerance"]
            ),
            "deposit_relative_spread": float(
                deposits_reading["the_deposit_vector_relative_difference"]
            ),
            "hold_drive_applied_work_total": float(
                held_record.get("drive_applied_work_total", 0.0)
            ),
            "hold_frame_energy_ratio_at_horizon": float(
                held_record.get("frame_energy_ratio_at_horizon", 0.0)
            ),
            "blank_page_sha256": str(blank_page_digest),
            "blank_page_reads": {str(k): float(v) for k, v in blank_reads.items()},
            "blank_page_greatest_read": max(
                (abs(float(value)) for value in blank_reads.values()), default=0.0
            ),
            "the_blank_page_reads_nothing": bool(
                max((abs(float(value)) for value in blank_reads.values()), default=0.0)
                <= float(settings.epsilon_factor)
            ),
        },
        "runtime_seconds": float(time.perf_counter() - started),
    }
    record["predicates"] = level_predicates(record)
    return record


def separation_histogram(
    arm: Mapping[str, Any], settings: rank.AddressingRankConfig, bins: int = 10
) -> dict[str, Any]:
    """The declared distribution of one arm's pairwise separations."""

    values = [float(pair["separation"]) for pair in arm["separation"]["item_pairs"]]
    floor = float(settings.contrast_floor)
    if not values:
        return {"declared": "no pairs", "counts": [], "edges": [], "least": None, "greatest": None}
    edges = [floor * (index + 1) / float(bins) for index in range(bins)]
    edges = [*edges, 1.0]
    counts = [0] * (len(edges) - 1)
    for value in values:
        placed = False
        for index in range(len(edges) - 1):
            if float(edges[index]) <= value < float(edges[index + 1]):
                counts[index] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    return {
        "declared": (
            "counts of the arm's pairwise item separations in bins from the contrast "
            "floor to 1.0; the last bin holds the values at or above 1.0"
        ),
        "counts": [int(value) for value in counts],
        "edges": [float(value) for value in edges],
        "least": min(values),
        "greatest": max(values),
        "mean": float(sum(values) / float(len(values))),
    }


def level_predicates(record: Mapping[str, Any]) -> dict[str, bool]:
    """The declared per-level bar and the delivered controls, in one place."""

    readings = record["readings"]
    count = int(record["n"])
    least = readings["least_item_separation"]
    return {
        "the_specific_arm_is_full_rank": bool(readings["the_specific_arm_is_full_rank"]),
        "the_margin_exceeds_one": bool(
            float(readings["margin_smallest_singular_value_against_tolerance"]) > 1.0
        ),
        "the_least_separation_reaches_the_predicted_value": bool(
            least is not None
            and float(least) >= 1.0 - float(rank.LOSS_ALLOWANCE)
        ),
        "every_pair_is_distinguishable": bool(readings["every_pair_is_distinguishable"]),
        "the_all_pairs_count_is_the_pair_count": bool(
            int(readings["pairs_measured"]) == int(count) * (int(count) - 1)
        ),
        "the_duplicate_arm_has_rank_one_below_the_item_count": bool(
            readings["duplicate_rank_is_one_below_the_item_count"]
        ),
        "the_shared_arm_is_rank_one": bool(int(readings["shared_rank"]) == 1),
        "the_shared_arm_separates_no_pair": bool(readings["shared_arm_separates_no_pair"]),
        "the_zero_work_probe_moves_nothing": bool(
            readings["zero_work_probe_greatest_response"] is not None
            and float(readings["zero_work_probe_greatest_response"]) == 0.0
        ),
        "the_zero_work_probe_is_rejected": bool(readings["zero_work_probes_are_rejected"]),
        "the_blank_page_reads_nothing": bool(readings["the_blank_page_reads_nothing"]),
    }


def level_healthy(record: Mapping[str, Any]) -> bool:
    """The declared bar of the ceiling definition, branches (b), (c) and (d)."""

    if not bool(record.get("constructible")):
        return False
    predicates = record["predicates"]
    return bool(
        predicates["the_specific_arm_is_full_rank"]
        and predicates["the_margin_exceeds_one"]
        and predicates["the_least_separation_reaches_the_predicted_value"]
    )


# --------------------------------------------------------------------------
# one declared block
# --------------------------------------------------------------------------
def block(
    resolution: int,
    counts: Sequence[int],
    *,
    name: str,
    budget_seconds: float = BLOCK_BUDGET_SECONDS,
    levels_override: Sequence[int] | None = None,
) -> dict[str, Any]:
    """One declared block: one resolution, its inventory, its levels, in order."""

    started = time.perf_counter()
    declared_counts = tuple(int(count) for count in counts)
    run_counts = (
        tuple(int(count) for count in declared_counts)
        if levels_override is None
        else tuple(int(count) for count in levels_override)
    )
    profile, profile_record = resolution_profile(int(resolution))
    family = declared_family(int(profile.port_count))
    census = {
        "declared_rule": family["declared_rule"],
        "port_count": int(family["port_count"]),
        "nodes": int(family["nodes"]),
        "leaves": int(family["leaves"]),
        "depths": dict(family["depths"]),
        "declared_family_size": int(len(family["specs"])),
        "refusals": list(family["refusals"]),
        "head_matches_the_delivered_item_specs": bool(
            family["head_matches_the_delivered_item_specs"]
        ),
        "orthogonality": family_orthogonality(int(profile.port_count), family["specs"]),
    }
    inventory_record = inventory(profile, family)
    levels: dict[str, Any] = {}
    points_run: list[int] = []
    points_not_run: list[dict[str, Any]] = []
    points_not_constructible: list[dict[str, Any]] = []
    # The whole block runs with the block's own family installed, so every level
    # is measured by the delivered instruments against the extended family, and
    # the block's own hold settings are measured once, over that whole family.
    block_settings = rank.AddressingRankConfig(
        item_indices=tuple(range(len(family["specs"]))),
        store_config=replace(
            rank.AddressingRankConfig().store_config,
            item_indices=tuple(range(len(family["specs"]))),
            neutrality_probe_items=(),
        ),
    )
    with family_installed(family["specs"]):
        captures, gain, phase_degrees, per_item = rank.hold_settings(
            profile, block_settings
        )
        hold_settings = {
            "captures": captures,
            "gain": float(gain),
            "phase_degrees": float(phase_degrees),
            "per_item": per_item,
        }
        installed = len(durability.ITEM_SPECS)
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
            if int(count) > int(inventory_record["addressable_count"]):
                # No arm runs here: the declared family has no such item. The
                # record is the structural boundary reading, not a sweep point.
                record_here = level_block(
                    profile,
                    int(count),
                    resolution=int(resolution),
                    inventory_record=inventory_record,
                    hold_settings=hold_settings,
                )
                levels[str(count)] = record_here
                points_not_constructible.append(
                    {"n": int(count), "reason": str(record_here["reason"])}
                )
                elapsed = time.perf_counter() - started
                continue
            projected = projected_cost(levels, int(count))
            if projected is not None and float(elapsed) + float(projected) > float(budget_seconds):
                points_not_run.append(
                    {
                        "n": int(count),
                        "reason": (
                            "the measured cost of the finished levels projects this level at "
                            f"{projected:.1f} s, which does not fit the remaining "
                            f"{float(budget_seconds) - float(elapsed):.1f} s of the block's "
                            "declared budget; the top of the range is cut rather than the "
                            "arms shortened"
                        ),
                    }
                )
                continue
            try:
                levels[str(count)] = level_block(
                    profile,
                    int(count),
                    resolution=int(resolution),
                    inventory_record=inventory_record,
                    hold_settings=hold_settings,
                )
            except Exception as error:  # recorded, never swallowed: the level is not run
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
    tail = levels[str(run_counts[-1])] if run_counts and str(run_counts[-1]) in levels else None
    # The tail of the declared range can be the structural record, which carries no
    # arms and no runtime, so its own field is published as absent rather than read.
    tail_runtime = (
        None
        if tail is None or "runtime_seconds" not in tail
        else float(tail["runtime_seconds"])
    )
    record: dict[str, Any] = {
        "schema": BLOCK_SCHEMA,
        "block": str(name),
        "resolution": int(resolution),
        "declared_counts": [int(count) for count in declared_counts],
        "counts_attempted": [int(count) for count in run_counts],
        "levels_override_used": bool(levels_override is not None),
        "profile": profile_record,
        "census": census,
        "inventory": inventory_record,
        "block_hold_settings": {
            "declared": (
                "measured once per block over the block's whole declared family by the "
                "store-scale runner's own hold_settings: the captured write directions, "
                "the measured neutral gain, the declared phase angle and each item's own "
                "phase reference; every level of the block is held at these settings"
            ),
            "items_captured": int(installed),
            "measured_gain": float(hold_settings["gain"]),
            "phase_degrees": float(hold_settings["phase_degrees"]),
            "captured_deposits": {
                str(capture["name"]): float(capture["deposited_energy"])
                for capture in hold_settings["captures"]
            },
            "captured_direction_sha256": {
                str(capture["name"]): str(capture["direction_sha256"])
                for capture in hold_settings["captures"]
            },
        },
        "levels": levels,
        "points_run": [int(count) for count in points_run],
        "points_not_run": points_not_run,
        "points_not_constructible": points_not_constructible,
        "declared_budget_seconds": float(budget_seconds),
        "runtime_seconds": float(time.perf_counter() - started),
        "tail_level_n": None if tail is None else int(tail["n"]),
        "tail_level_constructible": (
            None if tail is None else bool(tail.get("constructible"))
        ),
        "tail_level_runtime_seconds": tail_runtime,
        "delivered_item_list_restored": bool(
            tuple(durability.ITEM_SPECS) == DELIVERED_ITEM_SPECS
        ),
    }
    record["content_digest"] = scale.receipt_digest(record)
    return record


def projected_cost(levels: Mapping[str, Any], count: int) -> float | None:
    """The next level's own projected cost, from the measured levels' own law.

    The declared statistic costs O(N^2) owner calls, so the projection is the
    finished level's own wall clock scaled by the square of the item ratio.
    """

    measured = [
        (int(record["n"]), float(record["runtime_seconds"]))
        for record in levels.values()
        if bool(record.get("constructible"))
    ]
    if not measured:
        return None
    items, seconds = max(measured)
    return float(seconds) * (float(count) / float(items)) ** 2


# --------------------------------------------------------------------------
# the ceiling reading
# --------------------------------------------------------------------------
def ceiling_reading(document: Mapping[str, Any]) -> dict[str, Any]:
    """The declared ceiling definition, applied to every measured level."""

    table = document["table"]
    constructible = [row for row in table if bool(row["constructible"])]
    unconstructible = [row for row in table if not bool(row["constructible"])]
    failing = [
        row
        for row in constructible
        if not bool(row["the_specific_arm_is_full_rank"])
        or not bool(row["the_margin_exceeds_one"])
        or not bool(row["the_least_separation_reaches_the_predicted_value"])
    ]
    ceiling_candidates = []
    for row in failing:
        ceiling_candidates.append(
            {
                "n": int(row["n"]),
                "kind": "dynamical",
                "reason": (
                    "the declared bar failed at this count: "
                    f"rank {row['rank']}/{row['n']}, margin "
                    f"{row['margin_smallest_singular_value_against_tolerance']!r}, "
                    f"least separation {row['least_item_separation']!r}"
                ),
            }
        )
    for row in unconstructible:
        ceiling_candidates.append(
            {
                "n": int(row["n"]),
                "kind": "structural",
                "reason": str(row["reason"]),
            }
        )
    ceiling_candidates.sort(key=lambda row: int(row["n"]))
    ceiling = ceiling_candidates[0] if ceiling_candidates else None
    inventories = {
        str(record["resolution"]): int(record["inventory"]["addressable_count"])
        for record in document["blocks"].values()
    }
    if ceiling is None:
        branch = "smooth-degradation-with-no-ceiling"
        reading = (
            "no measured level failed the declared bar and none was unconstructible "
            "inside the swept range, so the sweep found no ceiling there"
        )
    elif ceiling["kind"] == "structural" and not failing:
        branch = "capacity-tracks-the-declared-scale-tree"
        reading = (
            "every constructed level satisfies the declared bar and the ceiling is "
            "the declared family's own inventory: the capacity is the count of the "
            "field's dyadic nodes at that resolution, which is its port count, so "
            "the delivered eight-item list is a declared stopping depth rather than "
            "a field limit"
        )
    elif failing:
        branch = "capacity-is-dynamical"
        reading = (
            "a constructed level failed the declared bar inside the swept range, so "
            "the ceiling is below the structural inventory at this operating point"
        )
    else:
        branch = "mixed"
        reading = "the ceiling candidates disagree; the table above carries the reading"
    fit = degradation_fit(constructible)
    lowest_failing = min((int(row["n"]) for row in failing), default=None)
    correlated: dict[str, Any] = {
        "declared": (
            "for the failing level and the level below it: the readings that say "
            "which of the page's own quantities the failure coincides with"
        ),
        "lowest_failing_level": lowest_failing,
        "rows": [
            {
                "n": int(row["n"]),
                "resolution": int(row["resolution"]),
                "rank": int(row["rank"]),
                "margin": float(row["margin_smallest_singular_value_against_tolerance"]),
                "least_separation": row["least_item_separation"],
                "measured_deposit_total_energy": float(row["measured_deposit_total_energy"]),
                "hold_drive_applied_work_total": float(row["hold_drive_applied_work_total"]),
                "measured_finite_difference_floor": float(
                    row["measured_finite_difference_floor"]
                ),
                "finite_difference_floor_relative_to_the_largest_singular_value": float(
                    row["finite_difference_floor_relative_to_the_largest_singular_value"]
                ),
                "largest_singular_value": float(row["largest_singular_value"]),
                "probe_budget": float(row["probe_budget"]),
            }
            for row in table
            if lowest_failing is not None
            and int(row["n"]) in (lowest_failing, previous_level(table, lowest_failing))
        ],
    }
    return {
        "declared_definition": (
            "the ceiling is the smallest declared N at which the level is not "
            "constructible at its resolution, or the specific arm's rank is below N, "
            "or its margin sigma_min/tol is at or below 1, or its least item "
            "separation falls below 1 - LOSS_ALLOWANCE"
        ),
        "ceiling": ceiling,
        "dynamical_ceiling": lowest_failing,
        "structural_inventory_by_resolution": inventories,
        "branch": branch,
        "reading": reading,
        "correlated_readings": correlated,
        "degradation_fit": fit,
    }


def previous_level(table: Sequence[Mapping[str, Any]], n: int) -> int | None:
    """The measured level below one failing level, if there is one."""

    below = [int(row["n"]) for row in table if int(row["n"]) < int(n)]
    return max(below) if below else None


def degradation_fit(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The declared least-separation degradation fit, or its degeneracy."""

    values = [
        (int(row["n"]), float(row["least_item_separation"]))
        for row in rows
        if row["least_item_separation"] is not None
    ]
    values.sort()
    if len(values) < 3:
        return {
            "declared": "a least-squares fit of the least separation against log(N)",
            "fitted": False,
            "reason": "fewer than three measured levels carry a least separation",
        }
    separations = [value for _n, value in values]
    if max(separations) - min(separations) <= 1e-12:
        return {
            "declared": "a least-squares fit of the least separation against log(N)",
            "fitted": False,
            "reason": (
                "the least separation is the same value at every measured level "
                f"({min(separations)!r}), so no degradation is measurable and no "
                "exponent is fitted"
            ),
            "least_separation_min": min(separations),
            "least_separation_max": max(separations),
        }
    x = np.asarray([math.log(float(n)) for n, _value in values], dtype=np.float64)
    y = np.asarray(separations, dtype=np.float64)
    design = np.column_stack([np.ones_like(x), x])
    coefficients, *_rest = np.linalg.lstsq(design, y, rcond=None)
    predicted = design @ coefficients
    residual = y - predicted
    total = float(np.sum((y - float(np.mean(y))) ** 2))
    return {
        "declared": (
            "least squares of s_min = a + b * log(N) over the measured levels, with "
            "the greatest absolute residual and R^2"
        ),
        "fitted": True,
        "levels": [int(n) for n, _value in values],
        "intercept": float(coefficients[0]),
        "slope_per_log_n": float(coefficients[1]),
        "greatest_absolute_residual": float(np.max(np.abs(residual))),
        "r_squared": (
            float(1.0 - float(np.sum(residual**2)) / total) if total > 0.0 else None
        ),
    }


# --------------------------------------------------------------------------
# the merged receipt
# --------------------------------------------------------------------------
def table_row(record: Mapping[str, Any], inventory_record: Mapping[str, Any]) -> dict[str, Any]:
    """One sweep point's own shared table row."""

    if not bool(record.get("constructible")):
        return {
            "n": int(record["n"]),
            "resolution": int(record["ports_per_pool"]),
            "constructible": False,
            "addressable_count": int(record["addressable_count"]),
            "declared_family_size": int(record["declared_family_size"]),
            "reason": str(record["reason"]),
            # the field's own refusal for the next candidate path, so a refusal row
            # carries the boundary it stopped at rather than the reason text alone
            "boundary": list(record["boundary"]),
        }
    readings = record["readings"]
    predicates = record["predicates"]
    return {
        "n": int(record["n"]),
        "resolution": int(record["ports_per_pool"]),
        "constructible": True,
        "addressable_count": int(inventory_record["addressable_count"]),
        "rank": int(readings["rank"]),
        "the_specific_arm_is_full_rank": bool(readings["the_specific_arm_is_full_rank"]),
        "margin_smallest_singular_value_against_tolerance": float(
            readings["margin_smallest_singular_value_against_tolerance"]
        ),
        "smallest_singular_value": float(readings["smallest_singular_value"]),
        "largest_singular_value": float(readings["largest_singular_value"]),
        "tolerance": float(readings["tolerance"]),
        "measured_finite_difference_floor": float(
            readings["measured_finite_difference_floor"]
        ),
        "finite_difference_floor_relative_to_the_largest_singular_value": float(
            readings["finite_difference_floor_relative_to_the_largest_singular_value"]
        ),
        "least_item_separation": readings["least_item_separation"],
        "greatest_item_separation": readings["greatest_item_separation"],
        "pairs_above_the_contrast_floor": int(readings["pairs_above_the_contrast_floor"]),
        "pairs_measured": int(readings["pairs_measured"]),
        "separation_histogram": readings["separation_histogram"],
        "duplicate_rank": int(readings["duplicate_rank"]),
        "duplicated_pair_separation": readings["duplicated_pair_separation"],
        "shared_rank": int(readings["shared_rank"]),
        "shared_arm_separates_no_pair": bool(readings["shared_arm_separates_no_pair"]),
        "zero_work_probe_greatest_response": readings["zero_work_probe_greatest_response"],
        "zero_work_probes_are_rejected": bool(readings["zero_work_probes_are_rejected"]),
        "blank_page_greatest_read": float(readings["blank_page_greatest_read"]),
        "the_blank_page_reads_nothing": bool(readings["the_blank_page_reads_nothing"]),
        "measured_deposit_total_energy": float(readings["measured_deposit_total_energy"]),
        "measured_deposits_constant_at_the_tolerance": bool(
            readings["measured_deposits_constant_at_the_tolerance"]
        ),
        "deposit_relative_spread": float(readings["deposit_relative_spread"]),
        "hold_drive_applied_work_total": float(readings["hold_drive_applied_work_total"]),
        "hold_frame_energy_ratio_at_horizon": float(
            readings["hold_frame_energy_ratio_at_horizon"]
        ),
        "probe_budget": float(record["settings"]["probe_budget"]),
        "hold_ticks": int(record["settings"]["hold_ticks"]),
        "the_specific_arm_is_full_rank_predicate": bool(predicates["the_specific_arm_is_full_rank"]),
        "the_margin_exceeds_one": bool(predicates["the_margin_exceeds_one"]),
        "the_least_separation_reaches_the_predicted_value": bool(
            predicates["the_least_separation_reaches_the_predicted_value"]
        ),
        "the_duplicate_arm_has_rank_one_below_the_item_count": bool(
            predicates["the_duplicate_arm_has_rank_one_below_the_item_count"]
        ),
        "the_shared_arm_is_rank_one": bool(predicates["the_shared_arm_is_rank_one"]),
        "the_zero_work_probe_moves_nothing": bool(
            predicates["the_zero_work_probe_moves_nothing"]
        ),
        "runtime_seconds": float(record["runtime_seconds"]),
    }


def merge_blocks(blocks: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The declared blocks, assembled into one receipt with the ceiling reading."""

    started = time.perf_counter()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "question": (
            "how many items does the placement addressing carry, and what does its "
            "ceiling track -- the field's own scale-tree depth, the write budget, the "
            "hold, the page's own deposit, or nothing inside the swept range?"
        ),
        "declared": {
            "family_rule": (
                "root scale, root detail, then every node detail of the port-count "
                "dyadic tree in its own breadth-first left-before-right order, skipping "
                "the single-port nodes the field's own rule refuses; the delivered "
                "eight-item list is the head of this family and is verified entry for "
                "entry"
            ),
            "statistic": (
                "J[i][j] = (read at item i's placement after a probe write at item j's "
                "placement minus the same read before) / probe work, one fresh owner per "
                "probe on the level's own held page; tol = max(FLOOR_FACTOR * "
                "sigma_1(J(a) - J(a/2)), EPS_FACTOR * sigma_1(J)); rank = the count of "
                "singular values above tol; margin = sigma_min / tol"
            ),
            "discriminator": (
                "Jn = J / mean(diag(J)); the item separation of a pair is the largest "
                "absolute difference between their normalized rows; a pair is "
                "distinguishable when its separation exceeds CONTRAST_FLOOR; an "
                "orthogonal pair is predicted at 1.0"
            ),
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
                    any(bool(block.get("levels_override_used")) for block in blocks.values())
                ),
            },
            "ceiling_definition": (
                "the smallest declared N at which the level is not constructible at its "
                "resolution, or the specific arm's rank is below N, or its margin "
                "sigma_min/tol is at or below 1, or its least item separation falls "
                "below 1 - LOSS_ALLOWANCE"
            ),
            "predicted_separation_of_an_orthogonal_pair": 1.0,
            "required_separation_for_the_specific_arm": float(
                1.0 - float(rank.LOSS_ALLOWANCE)
            ),
            "contrast_floor": float(rank.CONTRAST_FLOOR),
            "loss_allowance": float(rank.LOSS_ALLOWANCE),
            "probe_budget": float(rank.PROBE_BUDGET),
            "probe_budget_half": float(rank.PROBE_BUDGET) / 2.0,
            "hold_ticks": int(rank.HOLD_TICKS),
            "floor_factor": float(rank.FLOOR_FACTOR),
            "epsilon_factor": float(rank.EPS_FACTOR),
            "controls": {
                "duplicated_placement": (
                    "the duplicate arm addresses the second item at the first item's "
                    "placement: rank exactly one below the item count and the duplicated "
                    "pair at the contrast floor, at every level"
                ),
                "shared_placement": (
                    "the shared arm addresses every item at one placement: rank one and "
                    "no pair distinguishable, at every level"
                ),
                "zero_work_probe": (
                    "a probe at zero work must be rejected and must move no read, "
                    "measured once per level on the specific arm"
                ),
                "finite_difference_floor": (
                    "each level's own specific arm carries the half probe, so every "
                    "level's tolerance carries a floor measured at that level, and the "
                    "level's other arms reuse it"
                ),
                "blank_page": "a fresh owner's blank page reads nothing at every level",
                "delivered_list_restored": (
                    "the extended item list is installed in this process only; the "
                    "delivered list is asserted back after every block"
                ),
                "substituted_axis_slack": (
                    "the delivered rank receipt reported a slack page at the delivered "
                    "eight-item arm; this sweep keeps the delivered operating point "
                    "(page, write budget, hold, profile) and reports the measured deposit "
                    "energy and hold work per level so that any failure can be read "
                    "against the page's own quantities"
                ),
            },
            "content_digest_definition": (
                "the store-scale runner's declared content digest, reused: sha256 of the "
                "canonical JSON of the body with the declared clock leaves and the "
                "declared clock-derived digests stripped, taken before the digest is "
                "attached; each block carries its own digest under the same rule"
            ),
            "content_digest_strip_keys": list(scale.STRIP_KEYS),
            "content_digest_strip_keys_source": (
                "run_memory_store_scale.STRIP_KEYS, reused rather than re-derived"
            ),
            "no_git": "this runner writes receipts only; the release session commits",
        },
        "blocks": {
            str(name): dict(record) for name, record in sorted(blocks.items())
        },
        "runtime_seconds": float(time.perf_counter() - started),
    }
    rows = [
        table_row(level, record["inventory"])
        for _name, record in sorted(blocks.items())
        for level in record["levels"].values()
    ]
    rows.sort(key=lambda row: (int(row["n"]), int(row["resolution"])))
    body["table"] = rows
    body["ceiling"] = ceiling_reading(body)
    body["reading"] = reading_block(body)
    scale.assert_finite(body)
    body["receipt_digest"] = scale.receipt_digest(body)
    return body


def reading_block(document: Mapping[str, Any]) -> dict[str, Any]:
    """What the measured table says, in one reading."""

    table = document["table"]
    ceiling = document["ceiling"]
    constructible = [row for row in table if bool(row["constructible"])]
    predicates = {
        "every_measured_level_is_full_rank": bool(
            all(bool(row["the_specific_arm_is_full_rank"]) for row in constructible)
        ),
        "every_measured_level_is_inside_its_margin": bool(
            all(
                float(row["margin_smallest_singular_value_against_tolerance"]) > 1.0
                for row in constructible
            )
        ),
        "every_measured_level_reaches_the_predicted_separation": bool(
            all(
                bool(row["the_least_separation_reaches_the_predicted_value"])
                for row in constructible
            )
        ),
        "every_measured_level_separates_every_pair": bool(
            all(
                int(row["pairs_above_the_contrast_floor"]) == int(row["pairs_measured"])
                for row in constructible
            )
        ),
        "every_measured_level_fires_the_duplicate_control": bool(
            all(
                bool(row["the_duplicate_arm_has_rank_one_below_the_item_count"])
                for row in constructible
            )
        ),
        "every_measured_level_fires_the_shared_control": bool(
            all(
                bool(row["the_shared_arm_is_rank_one"])
                and bool(row["shared_arm_separates_no_pair"])
                for row in constructible
            )
        ),
        "every_measured_level_fires_the_zero_work_control": bool(
            all(
                bool(row["zero_work_probes_are_rejected"])
                and bool(row["the_zero_work_probe_moves_nothing"])
                for row in constructible
            )
        ),
        "every_measured_level_reads_a_blank_page_at_nothing": bool(
            all(bool(row["the_blank_page_reads_nothing"]) for row in constructible)
        ),
        "the_delivered_item_list_is_restored": bool(
            all(
                bool(record["delivered_item_list_restored"])
                for record in document["blocks"].values()
            )
        ),
        "the_addressable_inventory_is_the_port_count_at_every_measured_resolution": bool(
            all(
                bool(record["inventory"]["the_addressable_count_is_the_port_count"])
                for record in document["blocks"].values()
            )
        ),
        "the_declared_rule_reproduces_the_delivered_item_list": bool(
            all(
                bool(record["inventory"]["head_matches_the_delivered_item_specs"])
                for record in document["blocks"].values()
            )
        ),
    }
    honest_negatives = [
        text
        for condition, text in (
            (
                predicates["every_measured_level_is_full_rank"],
                "at least one measured level's deposit map is not full rank, so the "
                "addressing does not carry that count at this operating point",
            ),
            (
                predicates["every_measured_level_reaches_the_predicted_separation"],
                "at least one measured level's least item separation is below the "
                "declared allowance, so two items are not tellable apart there",
            ),
            (
                predicates["every_measured_level_fires_the_duplicate_control"],
                "the duplicate control does not cost exactly one dimension at some "
                "measured level, so the rank reading's firing control is broken there",
            ),
            (
                predicates["every_measured_level_fires_the_shared_control"],
                "the shared control does not collapse to one direction at some measured "
                "level",
            ),
            (
                predicates["the_delivered_item_list_is_restored"],
                "the extended item list was not restored after a block, so this process's "
                "delivered instrumentation is not the delivered list",
            ),
        )
        if not condition
    ]
    return {
        "predicate": (
            "the declared per-level bar (full rank, margin above one, least separation at "
            "or above 1 - LOSS_ALLOWANCE, every pair distinguishable) and the declared "
            "controls (duplicate rank N-1, shared rank one, zero-work rejection and zero "
            "response, blank page) at every measured level, plus the structural "
            "predicates of the declared rule and the inventory"
        ),
        "verdicts": predicates,
        "ceiling_branch": str(ceiling["branch"]),
        "ceiling": ceiling["ceiling"],
        "ceiling_reading": str(ceiling["reading"]),
        "degradation_fit": ceiling["degradation_fit"],
        "honest_negatives": honest_negatives,
        "limitations": [
            "the sweep measures one declared metric row at two resolutions, the "
            "delivered write budget, the delivered hold horizon and one probe "
            "amplitude; nothing here measures a distribution over profiles, budgets, "
            "holds or amplitudes",
            "the declared family is extended along the field's own dyadic scale tree "
            "only, so the capacity reading is a claim about that tree, not about "
            "arbitrary packet placements",
            "the probe budget is fixed while the level's own page deposit grows with N, "
            "so a failure would be a failure at this probe budget, and the receipt "
            "reports the page's own deposit energy and the measured floor per level for "
            "that reading",
            "the rank reading is a finite-difference reading; a deficiency below the "
            "level's own measured floor plus the declared relative floor would not be "
            "visible",
            "the counts that did not run are listed with their reasons: an unrun level "
            "is not evidence of a ceiling, and the structural inventory is measured "
            "separately from the arms",
        ],
        "not_shown": [
            "which dynamical property of the field sets the addressing capacity, beyond "
            "the measured count of its own scale-tree nodes",
            "whether a hierarchical (multi-item-per-probe) placement would carry more "
            "than the port count; the delivered statistic addresses one item per probe",
        ],
    }


def report(receipt: Mapping[str, Any]) -> str:
    """The receipt's own figures, verdict first."""

    lines = [f"schema: {receipt['schema']}"]
    ceiling = receipt["ceiling"]
    lines.append(f"ceiling branch: {ceiling['branch']}")
    lines.append(f"ceiling: {ceiling['ceiling']}")
    lines.append(f"reading: {ceiling['reading']}")
    lines.append("inventory:")
    for name, record in sorted(receipt["blocks"].items()):
        inv = record["inventory"]
        lines.append(
            f"  {name}: ports_per_pool {record['resolution']} port_count "
            f"{inv['addressable_count']} addressable of {inv['declared_family_size']} "
            f"declared, {inv['leaves_refused_by_the_rule']} leaf candidates refused, "
            f"head matches the delivered list: "
            f"{inv['head_matches_the_delivered_item_specs']}, orthogonality "
            f"{record['census']['orthogonality']['greatest_absolute_off_diagonal_gram_entry']:.3e}"
        )
        for row in inv["boundary"]:
            lines.append(f"    boundary {row['path']!r}: {row['outcome']}")
    lines.append("sweep:")
    for row in receipt["table"]:
        if not bool(row["constructible"]):
            lines.append(
                f"  N={row['n']:<3} resolution {row['resolution']}  NOT CONSTRUCTIBLE: "
                f"{row['reason']}"
            )
            continue
        lines.append(
            f"  N={row['n']:<3} resolution {row['resolution']}  rank {row['rank']}/{row['n']} "
            f"margin {row['margin_smallest_singular_value_against_tolerance']:.6g} "
            f"least separation {row['least_item_separation']!r} pairs "
            f"{row['pairs_above_the_contrast_floor']}/{row['pairs_measured']} "
            f"duplicate rank {row['duplicate_rank']} shared rank {row['shared_rank']} "
            f"zero-probe {row['zero_work_probe_greatest_response']!r} "
            f"blank {row['blank_page_greatest_read']!r} "
            f"deposit energy {row['measured_deposit_total_energy']:.6g} "
            f"({row['runtime_seconds']:.1f} s)"
        )
    lines.append("verdicts:")
    for name, value in receipt["reading"]["verdicts"].items():
        lines.append(f"  {name}: {value}")
    lines.append(f"degradation fit: {receipt['reading']['degradation_fit']}")
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
                raise SystemExit(f"the declared block {name!r} has not run: {path} is missing")
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
    print(f"block {arguments.block}: resolution {resolution}, points run {record['points_run']}")
    for row in record["points_not_run"]:
        print(f"  not run: N={row['n']}: {row['reason']}")
    for n, level in sorted(record["levels"].items(), key=lambda item: int(item[0])):
        if not bool(level.get("constructible")):
            print(f"  N={n}: not constructible: {level['reason']}")
            continue
        readings = level["readings"]
        print(
            f"  N={n}: rank {readings['rank']}/{level['n']} margin "
            f"{readings['margin_smallest_singular_value_against_tolerance']:.6g} least "
            f"separation {readings['least_item_separation']!r} pairs "
            f"{readings['pairs_above_the_contrast_floor']}/{readings['pairs_measured']} "
            f"duplicate {readings['duplicate_rank']} shared {readings['shared_rank']} "
            f"({level['runtime_seconds']:.1f} s)"
        )
    print(f"content_digest: {record['content_digest']}")
    print(f"runtime_seconds: {record['runtime_seconds']:.2f}")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
