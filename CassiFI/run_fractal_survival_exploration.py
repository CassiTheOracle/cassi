"""Measure whether written-item survival depends on the scaffold, and whether item spacing changes cross-item interference.

The durability harness measured survival on the default scaffold alone: one
declared packet item written into the canonical page at a declared budget, then
bounded unrelated canonical activity with sources and heartbeat on, then read
back.  This runner asks the two remaining contrast questions directly, reusing
that harness's declared arms, items, activity and readout by import and the
geometry harness's declared arrangements by import.

(A) **Scaffold contrast.**  The same declared activity arms (the headline single
item and the k=4 item arm) run on three declared build profiles: the canonical
default, ``nested-core-shell`` and ``recursive-paired-loops`` as the geometry
harness builds them.  Reported are the recovery fractions, the difference
against the default profile, the durability harness's own control margin, and a
declared profile margin.

(B) **Spacing contrast.**  The declared 8 item directions are written in pairs at
declared scale distances, and the off-diagonal deposit-share structure and the
per-item recovery after the same declared activity are compared.  The declared
scale-distance metric is the absolute difference of declared scale depth
(``len(path)``: root 0, ``L``/``R`` 1, two-branch paths 2), cross-checked against
the measured packet support width of each captured item.

(C) **Attribution contrast.**  The ``nested-core-shell`` arrangement is built
from BOTH declared profile hooks -- a projected transport rail and a projected
inverse-mass profile -- so the scaffold contrast above confounds the two
channels.  The geometry harness's retention receipt already separates them (its
mass-metric pairs name ``helix7`` against ``undivided`` and against
``nested-core-shell``; its rail pairs name density-matched graph-only
arrangements), so the declared arms here do the same for survival: the nested
rail with the default mass profile (``rail-only``), the nested rail with the
nested mass profile (``nested-core-shell``, unchanged), the default rail with
the nested mass profile (``mass-only``), and the other declared mass contrast
``undivided``, which is *not* a mass-only variant (its ``topology`` hook changes
the rail too).  Reported per arm are the headline single-item and ``k = 4``
recovery under the same declared activity, the delta against the default, and
the decomposition of the ``k = 4`` gain into a rail component, a mass component
(each against its own declared margin, so each can fail) and the residual
against the declared additivity tolerance.  The declared near/far spacing pair
arms are also run on ``rail-only`` and ``mass-only``, so it can be read off
which channel carries the spacing separation.

Everything is a canonical-field numerical measurement in controlled conditions.
Negative results are deliverables: a contrast that does not separate, or
separates in a direction the declaration did not predict, is reported as
measured.  Nothing here demonstrates task-level memory utility, semantic
content, retrieval by a consumer, or any advantage over alternative
architectures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry

SCHEMA = "cassifi.fractal-survival-exploration.v1"

# --------------------------------------------------------------------------
# declared scope
# --------------------------------------------------------------------------
# The canonical default body, and the two declared alternative scaffolds built
# by the geometry harness through its canonical profile hooks.
DEFAULT_PROFILE_NAME = "helix7"
PROFILE_NAMES = ("helix7", "nested-core-shell", "recursive-paired-loops")

# The durability harness's own declared activity arms, looked up by name in its
# ``arm_declarations`` output so its declaration stays the source of truth.
SCAFFOLD_ARM_NAMES = ("restart-and-activity", "restart-and-activity-k4")
BACKGROUND_ARM_NAME = "no-item-restart-and-activity"
# The declared headline arm of the attribution decomposition: the multi-item arm
# the confounded contrast was reported on.
ATTRIBUTION_HEADLINE_ARM_NAME = "restart-and-activity-k4"

# Declared pairs, chosen from the durability harness's declared 8 item
# directions.  ``near`` is the closest declared scale pair (both depth 1),
# ``far`` the farthest (depth 0 against depth 2), and ``mid`` the declared
# intermediate (depth 1 against depth 2).
PAIR_DECLARATIONS = (
    ("near", (2, 3)),
    ("mid", (2, 4)),
    ("far", (0, 7)),
)
NEAR_PAIR_NAME = "near"
FAR_PAIR_NAME = "far"

# Declared attribution arms.  ``nested-core-shell`` is built by the geometry
# harness from BOTH declared hooks (projected transport AND projected inverse
# mass), so the scaffold contrast against the default profile cannot say which
# channel moved survival.  The geometry harness's own retention receipt already
# splits them: its ``RETENTION_MASS_PAIRS`` names the mass-metric contrasts
# (("helix7", "undivided") and ("helix7", "nested-core-shell")) and its
# ``RETENTION_RAIL_PAIRS`` the density-matched graph-only ones.  The declared
# arms below are that split for survival, every one of them built through the
# same declared profile hooks.
RAIL_ONLY_PROFILE_NAME = "rail-only"
MASS_ONLY_PROFILE_NAME = "mass-only"
COMPOUND_PROFILE_NAME = "nested-core-shell"
TOPOLOGY_MASS_PROFILE_NAME = "undivided"
ATTRIBUTION_PROFILE_NAMES = (
    DEFAULT_PROFILE_NAME,
    RAIL_ONLY_PROFILE_NAME,
    MASS_ONLY_PROFILE_NAME,
    COMPOUND_PROFILE_NAME,
    TOPOLOGY_MASS_PROFILE_NAME,
)
# The declared spacing contrast is run again on the two single-channel arms, so
# the document's "spacing separation is not scaffold-invariant" statement can
# name the channel that carries it.
SPACING_ATTRIBUTION_PROFILE_NAMES = (RAIL_ONLY_PROFILE_NAME, MASS_ONLY_PROFILE_NAME)

# The exact construction rule and the declared channel of each attribution arm.
# ``rail-only`` and ``mass-only`` take one hook of the compound arrangement each
# and leave the other hook unspecified, i.e. at its canonical default.
ATTRIBUTION_ARM_DECLARATIONS: tuple[dict[str, Any], ...] = (
    {
        "name": DEFAULT_PROFILE_NAME,
        "channel": "default",
        "rule": "ResonantProfile() defaults: the canonical rail built from the declared "
                "topology with no projected transport hook, and the canonical mass metric "
                "diag(1/inertances) with no projected inverse-mass hook.",
        "toggles": "nothing: the declared reference arm",
    },
    {
        "name": RAIL_ONLY_PROFILE_NAME,
        "channel": "rail",
        "rule": "projected_transport = rail_from_pool_links(effective_links("
                "arrangement_named('nested-core-shell'))), i.e. the canonical intra rings, "
                "the two canonical strand bridges, and every ordered pool pair (a, b), "
                "a != b, at scale 1.7*0.5**ring_distance(a, b) on both strands; "
                "projected_inv_mass = None, which is the canonical mass metric. Exactly the "
                "transport hook of the compound arm, with the default mass profile.",
        "toggles": "the projected transport hook only; the mass metric stays canonical",
    },
    {
        "name": MASS_ONLY_PROFILE_NAME,
        "channel": "mass",
        "rule": "projected_transport = None, which is the canonical default rail; "
                "projected_inv_mass = core_shell_inverse_mass(), the shell metric "
                "0.7**ring_distance(pool, 3) on every port of both strands. Exactly the "
                "inverse-mass hook of the compound arm, with the default rail.",
        "toggles": "the projected inverse-mass hook only; the rail stays canonical",
    },
    {
        "name": COMPOUND_PROFILE_NAME,
        "channel": "rail+mass",
        "rule": "geometry.build_profile(arrangement_named('nested-core-shell')): the "
                "rail-only transport hook and the mass-only inverse-mass hook together, "
                "unchanged from the scaffold contrast above.",
        "toggles": "both declared hooks at once",
    },
    {
        "name": TOPOLOGY_MASS_PROFILE_NAME,
        "channel": "topology hook (rail and mass together)",
        "rule": "ResonantProfile(topology='undivided'): the canonical edge set with uniform "
                "volumes (1.0 per port) and uniform inertances (1.0 per port). This is NOT a "
                "mass-only variant, and is declared as such: the canonical weight rule "
                "coupling*scale/(length*sqrt(vol_u*vol_v)) sees the uniform volumes, so the "
                "rail changes too, while the mass metric diag(1/inertances) flattens from "
                "1.3**-pool to 1.0. It toggles the topology hook, and therefore both "
                "channels at once, which is why its row is reported as a compound "
                "topology-hook contrast and is excluded from the rail/mass decomposition.",
        "toggles": "the topology hook: volumes (rail) and inertances (mass metric) together",
    },
)

# Declared attribution margins.  The two channel margins are the same declared
# recovery-scale threshold used for the scaffold contrast, and the additivity
# tolerance is a two-sided bound on the residual of the decomposition (the
# compound gain against the sum of the two single-channel components): the
# channels are declared additive when the residual stays within it, because the
# survival figure is a nonlinear share, not a linear response.
RAIL_COMPONENT_MARGIN = 0.02
MASS_COMPONENT_MARGIN = 0.02
ATTRIBUTION_ADDITIVITY_TOLERANCE = 0.01

# Declared margins.  The control margin is the durability harness's own declared
# margin and is read from its config rather than restated here.
PROFILE_RECOVERY_MARGIN = 0.02
SPACING_CONFUSION_MARGIN = 0.05
SPACING_RECOVERY_MARGIN = 0.05

DEFAULT_OUTPUT = Path("_diag/fractal-survival/exploration.json")

SCAFFOLD_HYPOTHESIS = (
    "recovery after the declared activity depends on the scaffold: for at least "
    "one declared non-default profile and one declared arm, the absolute "
    "difference of recovery against the default profile reaches the declared "
    "profile margin"
)
SPACING_HYPOTHESIS = (
    "under the same declared activity, measured on the declared default profile, "
    "the declared nearest pair (declared scale distance 0) shows a larger maximum "
    "off-diagonal deposit share than the declared farthest pair (declared scale "
    "distance 2), and the nearest pair's minimum per-item recovery is smaller, "
    "each by at least the declared margin; the same declared margins are applied "
    "to the no-activity baseline arm and to every other declared profile and "
    "reported as measured"
)
SCALE_DEPTH_DEFINITION = (
    "declared scale depth of a declared item is the number of L/R branches in "
    "its declared packet path -- root 0, L/R 1, two-branch paths 2 -- "
    "cross-checked against log2(port_count / measured packet support width) of "
    "the item's captured write direction"
)
ATTRIBUTION_HYPOTHESIS = (
    "the compound arm's recovery gain over the default profile is carried by one "
    "declared channel: the mass-only arm's component reaches the declared mass "
    "component margin while the rail-only arm's component stays at or below the "
    "declared rail component margin, and the two single-channel components sum to "
    "the compound gain within the declared additivity tolerance; the verdict is "
    "reported for both the headline single-item arm and the k=4 arm as measured"
)
SCALE_DISTANCE_DEFINITION = (
    "declared scale distance of a declared item pair is the absolute difference "
    "of the two items' declared scale depths; no tree or branch-graph distance is "
    "used, because the balanced partition makes a depth-1 sibling pair and a "
    "root/depth-2 pair equally distant in tree levels"
)
CONTENT_DIGEST_DEFINITION = (
    "sha256 of the canonical JSON (sorted keys, no insignificant whitespace, "
    "allow_nan=False) of the measured body with wall-clock fields stripped, "
    "before the digest itself is attached"
)

DEFINITIONS = {
    "declared_arm": (
        "one arm of the durability harness, looked up by name in its "
        "arm_declarations output: which declared items are written, whether the "
        "canonical workspace round trip is applied, and whether the declared "
        "unrelated activity is advanced"
    ),
    "declared_profile": (
        "one declared scaffold: the canonical default ResonantProfile(), or an "
        "arrangement built by the geometry harness through its canonical "
        "transport and inverse-mass hooks"
    ),
    "declared_activity": (
        "the durability harness's declared advance_workspace schedule: 64 ticks "
        "in four declared samples with source_enabled and the canonical heartbeat "
        "on at the declared demand; identical for every profile and every pair"
    ),
    "recovery_fraction": (
        "the durability harness's declared recovery: (c_read . u)^2 / |c_in_arm|^2 "
        "with u the item's captured write direction and |c_in_arm|^2 that write's "
        "measured deposit inside the arm; for a multi-item arm the arm figure is "
        "the minimum over its items"
    ),
    "control_share": (
        "the durability harness's declared control: the written item's own "
        "measured deposit projected onto a declared direction the arm did not "
        "write; the declared control margin is its own declared value"
    ),
    "cross_item_confusion": (
        "the durability harness's declared cross-item confusion: the share of "
        "item i's measured deposit lying along item j's captured direction; "
        "diagonal entries are the per-item recovery fractions and off-diagonal "
        "entries the write-A-read-B interference proxy in deposit units"
    ),
    "max_off_diagonal_deposit_share": (
        "the largest off-diagonal entry of cross_item_confusion in a multi-item "
        "arm: the declared scalar for cross-item confusion"
    ),
    "cross_item_confusion_baseline": (
        "the same declared cross-item confusion measured on a declared arm that "
        "writes the same pair and restarts but advances no activity; because the "
        "declared item directions are orthogonal within the declared allowance, "
        "each written item's deposit lies on its own direction in that arm, so the "
        "baseline off-diagonal entries are the two writes' deposit-amplitude ratio "
        "and the activity-driven part is the difference against them"
    ),
    "unwritten_direction_energy_fraction_total": (
        "the sum of declared_frame_energy_fraction over the declared directions "
        "the arm did not write: the unit-free share of the read packet's projection "
        "onto the declared item frame that sits on unwritten declared directions, "
        "which is the interference-specific companion to the deposit-share figure"
    ),
    "declared_scale_depth": SCALE_DEPTH_DEFINITION,
    "declared_scale_distance": SCALE_DISTANCE_DEFINITION,
    "profile_recovery_margin": (
        "declared threshold on the absolute recovery difference between a "
        "non-default profile and the default profile in one declared arm"
    ),
    "spacing_confusion_margin": (
        "declared threshold on the near-pair minus far-pair maximum off-diagonal "
        "deposit share"
    ),
    "spacing_recovery_margin": (
        "declared threshold on the far-pair minus near-pair minimum per-item "
        "recovery"
    ),
    "attribution_arm": (
        "one declared single-channel or compound arm, built through the same "
        "canonical profile hooks as the scaffold contrast: its exact construction "
        "rule and the channel it toggles are declared in the receipt's "
        "attribution arm declarations"
    ),
    "rail_component": (
        "the rail-only arm's recovery in one declared arm minus the default "
        "profile's recovery in the same declared arm: the declared survival effect "
        "of moving the projected transport while the mass metric stays canonical"
    ),
    "mass_component": (
        "the mass-only arm's recovery in one declared arm minus the default "
        "profile's recovery in the same declared arm: the declared survival effect "
        "of moving the projected inverse mass while the rail stays canonical"
    ),
    "compound_gain": (
        "the compound arm's (nested-core-shell) recovery in one declared arm minus "
        "the default profile's recovery in the same declared arm: the confounded "
        "gain the scaffold contrast reports"
    ),
    "attributed_gain": (
        "rail_component + mass_component: the two single-channel components summed "
        "against the default profile"
    ),
    "interaction_residual": (
        "compound_gain - attributed_gain: the part of the compound gain the two "
        "single-channel components do not reproduce; the survival figure is a "
        "nonlinear share, so this residual is measured rather than assumed zero"
    ),
    "rail_component_margin": (
        "declared threshold on the absolute rail component: the rail channel "
        "counts as carrying survival only when its magnitude reaches it"
    ),
    "mass_component_margin": (
        "declared threshold on the absolute mass component: the mass channel "
        "counts as carrying survival only when its magnitude reaches it"
    ),
    "attribution_additivity_tolerance": (
        "declared two-sided bound on the absolute interaction residual: the two "
        "single-channel components are declared additive only while the residual "
        "stays at or below it"
    ),
    "attribution_channel": (
        "the declared verdict of one arm's decomposition: 'rail' or 'mass' when "
        "exactly one component reaches its own margin, 'rail-and-mass' when both "
        "do, 'neither' when neither does; it is derived from the two component "
        "verdicts, never asserted"
    ),
    "mass_metric_signature": (
        "the diagonal of the built profile's mass metric, from the projected "
        "inverse-mass hook when it is set and otherwise from diag(1/inertances): "
        "the declared channel signature that makes a mass-only arm's mass change "
        "and a rail-only arm's unchanged mass metric explicit"
    ),
}

BOUNDARY = (
    "Controlled canonical-field measurement only: declared packet items written "
    "into the canonical page through the canonical packet impulse at the "
    "durability harness's declared budget, the same declared unrelated canonical "
    "activity (sources and heartbeat on) for every profile and every pair, and "
    "the canonical workspace round trip for the restart leg. The scaffold "
    "contrast reuses the durability harness's declared arms by import and the "
    "geometry harness's declared arrangements by import; the attribution contrast "
    "builds its single-channel arms from the one declared hook each of them "
    "carries, so its components are differences of measured recoveries, not a "
    "causal separation of the two hooks inside one run. The declared 'undivided' "
    "arm is a topology-hook contrast that moves both the rail and the mass metric, "
    "so it is reported as a compound arm and is excluded from the two-channel "
    "decomposition. Nothing here demonstrates task-level memory utility, semantic "
    "content, retrieval by a consumer, owner-level checkpoint identity for a "
    "written item, or any advantage over alternative architectures: the recovery "
    "figures are shares of a measured deposit along a measured direction, and the "
    "pair contrasts are measured on the declared default profile unless the "
    "receipt says otherwise."
)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def array_sha256(value: Any) -> str:
    """Digest of an array's little-endian float64 bytes."""

    return hashlib.sha256(
        np.ascontiguousarray(np.asarray(value, dtype="<f8")).tobytes()
    ).hexdigest()


def margin_holds(value: float, margin: float) -> bool:
    """The declared margin test: does the declared quantity reach the margin?"""

    return bool(float(value) >= float(margin))


def within_tolerance(value: float, tolerance: float) -> bool:
    """The declared invariance test: does the declared quantity stay at or below it?"""

    return bool(abs(float(value)) <= float(tolerance))


def attribution_rule_lookup(name: str) -> Mapping[str, Any]:
    """One declared attribution arm's construction rule and declared channel."""

    for row in ATTRIBUTION_ARM_DECLARATIONS:
        if row["name"] == name:
            return row
    raise RuntimeError(f"the attribution contrast declares no arm {name!r}")


def nested_rail() -> np.ndarray:
    """The compound arrangement's own projected transport rail, nothing else."""

    return geometry.rail_from_pool_links(
        geometry.effective_links(geometry.arrangement_named(COMPOUND_PROFILE_NAME))
    )


def nested_inverse_mass() -> np.ndarray:
    """The compound arrangement's own projected inverse-mass profile, nothing else."""

    return geometry.core_shell_inverse_mass(geometry.DEFAULT_PORTS_PER_POOL)


def build_attribution_profile(name: str) -> Any:
    """One declared attribution arm, through the canonical profile hooks only."""

    if name == RAIL_ONLY_PROFILE_NAME:
        return durability.ResonantProfile(projected_transport=nested_rail())
    if name == MASS_ONLY_PROFILE_NAME:
        return durability.ResonantProfile(projected_inv_mass=nested_inverse_mass())
    return build_declared_profile(name)


def mass_metric_signature(profile: Any) -> dict[str, Any]:
    """The built profile's mass metric diagonal, from whichever declared source supplies it."""

    inverse_mass = profile.projected_inv_mass
    if inverse_mass is None:
        diagonal = 1.0 / np.asarray(profile.inertances, dtype=np.float64)
        source = "inertances"
        matrix_sha256 = None
    else:
        raw = np.asarray(inverse_mass, dtype=np.float64)
        diagonal = np.diag(raw) if raw.ndim == 2 else raw
        source = "projected_inv_mass"
        matrix_sha256 = array_sha256(raw) if raw.ndim == 2 else None
    return {
        "source": source,
        "diagonal_sha256": array_sha256(diagonal),
        "diagonal_min": float(diagonal.min()),
        "diagonal_max": float(diagonal.max()),
        "diagonal_l1": float(np.abs(diagonal).sum()),
        "matrix_sha256": matrix_sha256,
    }


def recovery_delta_entry(base: Any, value: Any, margin: float) -> dict[str, Any]:
    """The declared delta of one recovery figure against the default profile's."""

    absolute = None if value is None or base is None else float(value) - float(base)
    return {
        "default_recovery_fraction": base,
        "profile_recovery_fraction": value,
        "absolute_difference": absolute,
        "relative_difference": (
            None if absolute is None or not base else absolute / float(base)
        ),
        "margin": float(margin),
        "separates": False if absolute is None else margin_holds(abs(absolute), margin),
    }


def declared_arm_lookup(config: durability.DurabilityConfig) -> dict[str, Any]:
    """Look the durability harness's own declared activity arms up by name."""

    arms = {arm.name: arm for arm in durability.arm_declarations(config)}
    for name in (BACKGROUND_ARM_NAME, *SCAFFOLD_ARM_NAMES):
        if name not in arms:
            raise RuntimeError(
                f"the durability harness declares no arm {name!r}; "
                f"its arms are {sorted(arms)}"
            )
    if ATTRIBUTION_HEADLINE_ARM_NAME not in SCAFFOLD_ARM_NAMES:
        raise RuntimeError(
            f"the declared attribution headline arm {ATTRIBUTION_HEADLINE_ARM_NAME!r} "
            f"is not one of the declared scaffold arms {list(SCAFFOLD_ARM_NAMES)}"
        )
    return arms


def build_declared_profile(name: str) -> Any:
    """The declared scaffold: the canonical default, or a geometry arrangement."""

    if name == DEFAULT_PROFILE_NAME:
        return durability.ResonantProfile()
    return geometry.build_profile(geometry.arrangement_named(name))


def profile_hook_signature(profile: Any) -> dict[str, Any]:
    """The declared hook fields of a built profile, plus a measured signature."""

    transport = np.asarray(profile.transport_matrix, dtype=np.float64)
    inverse_mass = profile.projected_inv_mass
    return {
        "topology": str(profile.topology),
        "ports_per_pool": int(profile.ports_per_pool),
        "port_count": int(profile.port_count),
        "has_projected_transport": profile.projected_transport is not None,
        "has_projected_inv_mass": inverse_mass is not None,
        "transport_l1": float(np.abs(transport).sum()),
        "transport_sha256": array_sha256(transport),
        "inverse_mass_sha256": (
            None
            if inverse_mass is None
            else array_sha256(np.asarray(inverse_mass, dtype=np.float64))
        ),
    }


def support_of(path: str, port_count: int) -> tuple[int, int]:
    """The declared balanced partition support of a declared packet path."""

    start, stop = 0, int(port_count)
    for branch in path:
        middle = start + (stop - start) // 2
        if branch == "L":
            stop = middle
        elif branch == "R":
            start = middle
        else:
            raise ValueError(f"declared packet path contains {branch!r}")
    return start, stop


def support_relation(left: tuple[int, int], right: tuple[int, int]) -> str:
    """How two declared supports sit in the balanced partition."""

    if left == right:
        return "identical"
    left_start, left_stop = left
    right_start, right_stop = right
    left_set = set(range(left_start, left_stop))
    right_set = set(range(right_start, right_stop))
    if not left_set & right_set:
        gap = (
            right_start - left_stop
            if left_stop <= right_start
            else left_start - right_stop
        )
        return "disjoint-adjacent" if gap == 0 else "disjoint-separate"
    if left_set <= right_set or right_set <= left_set:
        return "nested"
    return "overlapping"


# --------------------------------------------------------------------------
# declared blocks
# --------------------------------------------------------------------------
def item_declarations(config: durability.DurabilityConfig) -> list[dict[str, Any]]:
    """Every declared item with its declared scale depth."""

    port_count = durability.ResonantProfile().port_count
    rows: list[dict[str, Any]] = []
    for index, spec in enumerate(durability.ITEM_SPECS):
        support = support_of(spec.path, port_count)
        rows.append(
            {
                "index": index,
                "name": spec.name,
                "path": spec.path,
                "component": spec.component,
                "flow_signal": list(spec.flow_signal),
                "declared_scale_depth": len(spec.path),
                "declared_support": list(support),
                "declared_support_width": support[1] - support[0],
            }
        )
    return rows


def pair_declarations(config: durability.DurabilityConfig) -> list[dict[str, Any]]:
    """Every declared pair with its declared scale distance and support relation."""

    roles = {NEAR_PAIR_NAME: "near", FAR_PAIR_NAME: "far"}
    port_count = durability.ResonantProfile().port_count
    rows: list[dict[str, Any]] = []
    for name, indices in PAIR_DECLARATIONS:
        specs = [durability.ITEM_SPECS[index] for index in indices]
        depths = [len(spec.path) for spec in specs]
        supports = [support_of(spec.path, port_count) for spec in specs]
        rows.append(
            {
                "name": name,
                "role": roles.get(name, "intermediate"),
                "item_indices": [int(index) for index in indices],
                "item_names": [spec.name for spec in specs],
                "declared_scale_depths": depths,
                "declared_scale_distance": abs(depths[0] - depths[1]),
                "declared_supports": [list(support) for support in supports],
                "declared_support_relation": support_relation(supports[0], supports[1]),
            }
        )
    return rows


def declared_block(config: durability.DurabilityConfig) -> dict[str, Any]:
    return {
        "durability_module": durability.__name__,
        "durability_schema": durability.SCHEMA,
        "geometry_module": geometry.__name__,
        "geometry_schema": geometry.SCHEMA,
        "config": config.as_dict(),
        "control_margin": float(config.control_margin),
        "orthogonality_allowance": float(durability.ORTHOGONALITY_ALLOWANCE),
        "default_profile": DEFAULT_PROFILE_NAME,
        "profile_names": list(PROFILE_NAMES),
        "scaffold_arm_names": list(SCAFFOLD_ARM_NAMES),
        "background_arm_name": BACKGROUND_ARM_NAME,
        "item_declarations": item_declarations(config),
        "pair_declarations": pair_declarations(config),
        "near_pair": NEAR_PAIR_NAME,
        "far_pair": FAR_PAIR_NAME,
        "attribution_profile_names": list(ATTRIBUTION_PROFILE_NAMES),
        "attribution_arm_declarations": [
            dict(row) for row in ATTRIBUTION_ARM_DECLARATIONS
        ],
        "rail_only_profile": RAIL_ONLY_PROFILE_NAME,
        "mass_only_profile": MASS_ONLY_PROFILE_NAME,
        "compound_profile": COMPOUND_PROFILE_NAME,
        "topology_mass_profile": TOPOLOGY_MASS_PROFILE_NAME,
        "spacing_attribution_profile_names": list(SPACING_ATTRIBUTION_PROFILE_NAMES),
        "attribution_headline_arm": ATTRIBUTION_HEADLINE_ARM_NAME,
        "rail_component_margin": float(RAIL_COMPONENT_MARGIN),
        "mass_component_margin": float(MASS_COMPONENT_MARGIN),
        "attribution_additivity_tolerance": float(ATTRIBUTION_ADDITIVITY_TOLERANCE),
        "profile_recovery_margin": float(PROFILE_RECOVERY_MARGIN),
        "spacing_confusion_margin": float(SPACING_CONFUSION_MARGIN),
        "spacing_recovery_margin": float(SPACING_RECOVERY_MARGIN),
        "scaffold_hypothesis": SCAFFOLD_HYPOTHESIS,
        "spacing_hypothesis": SPACING_HYPOTHESIS,
        "attribution_hypothesis": ATTRIBUTION_HYPOTHESIS,
        "scale_depth_definition": SCALE_DEPTH_DEFINITION,
        "scale_distance_definition": SCALE_DISTANCE_DEFINITION,
        "content_digest_definition": CONTENT_DIGEST_DEFINITION,
        "definitions": DEFINITIONS,
    }


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------
def capture_rows(
    config: durability.DurabilityConfig,
    port_count: int,
    captures: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Per-item provenance of the captured write directions, with the depth cross-check."""

    rows: list[dict[str, Any]] = []
    for index, capture in enumerate(captures):
        width = int(capture["scale_width"])
        measured_depth = int(round(float(np.log2(port_count / width))))
        declared_depth = len(capture["spec"].path)
        if measured_depth != declared_depth:
            raise RuntimeError(
                f"declared item {capture['name']!r} has declared scale depth "
                f"{declared_depth} but a measured support width of {width}"
            )
        rows.append(
            {
                "index": index,
                "name": capture["name"],
                "path": capture["path"],
                "component": capture["component"],
                "declared_scale_depth": declared_depth,
                "measured_support_width": width,
                "measured_scale_depth": measured_depth,
                "support": dict(capture["support"]),
                "mode": dict(capture["mode"]),
                "deposited_energy": float(capture["deposited_energy"]),
                "direction_sha256": capture["direction_sha256"],
                "capture_state_sha256": capture["capture_state_sha256"],
            }
        )
    return rows


def compact_arm_record(
    out: Mapping[str, Any], control_margin: float
) -> dict[str, Any]:
    """The declared figures of one arm, in JSON-safe canonical form."""

    readout = out["readout"]
    cross = dict(readout["cross_item_confusion"])
    off_diagonal = [
        float(value)
        for written, row in cross.items()
        for read, value in row.items()
        if read != written
    ]
    frame_fraction = dict(readout["declared_frame_energy_fraction"])
    written_items = list(readout["written_items"])
    restart = out["restart"]
    return {
        "declared_written_items": list(out["declared"]["written_items"]),
        "written_items": written_items,
        "restart_applied": bool(restart.get("applied", False)),
        "restart_state_digest_identical": restart.get("state_digest_identical"),
        "restart_page_digest_identical": restart.get("page_digest_identical"),
        "write_time_alignment": dict(readout["write_time_alignment"]),
        "measured_deposit_energy": dict(out["measured_deposit_energy"]),
        "deposit_attenuation": dict(out["deposit_attenuation"]),
        "per_item_recovery_fraction": dict(readout["own_shares"]),
        "recovery_fraction": readout["recovery_fraction"],
        "control_item": readout["control_item"],
        "control_share": readout["control_share"],
        "control_margin": float(control_margin),
        "distinguishable_from_control": readout["distinguishable_from_control"],
        "total_packet_energy_ratio": readout["total_packet_energy_ratio"],
        "distance_from_pre_activity": readout["distance_from_pre_activity"],
        "cross_item_confusion": {
            written: dict(row) for written, row in cross.items()
        },
        "max_off_diagonal_deposit_share": max(off_diagonal, default=0.0),
        "off_diagonal_deposit_share_sum": float(sum(off_diagonal)),
        "declared_frame_energy_fraction": frame_fraction,
        "written_direction_energy_fraction_total": float(
            sum(value for name, value in frame_fraction.items() if name in written_items)
        ),
        "unwritten_direction_energy_fraction_total": float(
            sum(value for name, value in frame_fraction.items() if name not in written_items)
        ),
        "activity_ticks": int(out["declared"]["activity_ticks"]),
        "activity_dissipated_work_total": float(out["activity"]["dissipated_work_total"]),
        "activity_positive_heartbeat_work_total": float(
            out["activity"]["positive_heartbeat_work_total"]
        ),
        "read_state_sha256": readout["state_sha256"],
    }


def run_pair_arm(
    config: durability.DurabilityConfig,
    profile: Any,
    captures: Sequence[Mapping[str, Any]],
    name: str,
    item_indices: Sequence[int],
    *,
    activity: bool,
) -> dict[str, Any]:
    """One declared pair arm: write both declared items, restart, then optional activity."""

    arm = durability.Arm(name, tuple(int(index) for index in item_indices), True, activity)
    out = durability.run_arm(config, profile, captures, arm)
    return compact_arm_record(out, config.control_margin)


def measured_body_core(config: durability.DurabilityConfig | None = None) -> dict[str, Any]:
    """Run every declared arm on every declared profile and scaffold.

    The durability harness's owner probe is deliberately not used: it needs a
    temporary production-owner home and is not part of either contrast, so the
    declared arms are driven directly through the harness's own ``run_arm``.
    """

    config = config or durability.DurabilityConfig()
    arms = declared_arm_lookup(config)
    port_count = durability.ResonantProfile().port_count

    profiles: dict[str, Any] = {}
    scaffold: dict[str, Any] = {"per_profile": {}}
    spacing: dict[str, Any] = {"per_profile": {}}

    for name in PROFILE_NAMES:
        profile = build_declared_profile(name)
        captures = durability.capture_items(config, profile)
        overlap = durability.overlap_matrix(captures)
        off_diagonal = [
            float(value)
            for left, row in enumerate(overlap)
            for right, value in enumerate(row)
            if left != right
        ]
        max_off_diagonal = max(off_diagonal, default=0.0)
        profiles[name] = {
            "profile_hooks": profile_hook_signature(profile),
            "max_off_diagonal_squared_cosine": max_off_diagonal,
            "orthogonality_allowance": float(durability.ORTHOGONALITY_ALLOWANCE),
            "within_orthogonality_allowance": bool(
                max_off_diagonal <= durability.ORTHOGONALITY_ALLOWANCE
            ),
            "items": capture_rows(config, port_count, captures),
        }
        scaffold["per_profile"][name] = {
            arm_name: compact_arm_record(
                durability.run_arm(config, profile, captures, arms[arm_name]),
                config.control_margin,
            )
            for arm_name in (BACKGROUND_ARM_NAME, *SCAFFOLD_ARM_NAMES)
        }
        pairs = {
            pair_name: run_pair_arm(
                config, profile, captures, pair_name, indices, activity=True
            )
            for pair_name, indices in PAIR_DECLARATIONS
        }
        without_activity = {
            pair_name: run_pair_arm(
                config, profile, captures, pair_name, indices, activity=False
            )
            for pair_name, indices in PAIR_DECLARATIONS
        }
        spacing["per_profile"][name] = {
            "pairs": pairs,
            "pairs_without_activity": without_activity,
        }

    attribution: dict[str, Any] = {"per_arm": {}, "spacing": {"per_profile": {}}}
    for name in ATTRIBUTION_PROFILE_NAMES:
        profile = build_attribution_profile(name)
        captures = durability.capture_items(config, profile)
        rule = attribution_rule_lookup(name)
        attribution["per_arm"][name] = {
            "declared_channel": rule["channel"],
            "declared_construction_rule": rule["rule"],
            "declared_toggles": rule["toggles"],
            "profile_hooks": profile_hook_signature(profile),
            "mass_metric": mass_metric_signature(profile),
            "arms": {
                arm_name: compact_arm_record(
                    durability.run_arm(config, profile, captures, arms[arm_name]),
                    config.control_margin,
                )
                for arm_name in (BACKGROUND_ARM_NAME, *SCAFFOLD_ARM_NAMES)
            },
        }
        if name in SPACING_ATTRIBUTION_PROFILE_NAMES:
            attribution["spacing"]["per_profile"][name] = {
                "pairs": {
                    pair_name: run_pair_arm(
                        config, profile, captures, pair_name, indices, activity=True
                    )
                    for pair_name, indices in PAIR_DECLARATIONS
                }
            }

    return {
        "schema": SCHEMA,
        "declared": declared_block(config),
        "profiles": profiles,
        "scaffold": scaffold,
        "spacing": spacing,
        "attribution": attribution,
    }


# --------------------------------------------------------------------------
# derived summary
# --------------------------------------------------------------------------
def summarize(body_core: Mapping[str, Any]) -> dict[str, Any]:
    """Every derived figure and declared margin verdict, from the measured body alone."""

    declared = body_core["declared"]
    default = declared["default_profile"]
    profile_margin = float(declared["profile_recovery_margin"])
    confusion_margin = float(declared["spacing_confusion_margin"])
    recovery_margin = float(declared["spacing_recovery_margin"])
    arm_names = list(declared["scaffold_arm_names"])
    near_name = declared["near_pair"]
    far_name = declared["far_pair"]
    pair_meta = {row["name"]: row for row in declared["pair_declarations"]}

    scaffold_raw = body_core["scaffold"]["per_profile"]
    default_recovery = {
        arm_name: scaffold_raw[default][arm_name]["recovery_fraction"]
        for arm_name in arm_names
    }
    deltas: dict[str, Any] = {}
    for profile_name, arm_rows in scaffold_raw.items():
        if profile_name == default:
            continue
        per_arm: dict[str, Any] = {}
        for arm_name in arm_names:
            per_arm[arm_name] = recovery_delta_entry(
                default_recovery[arm_name],
                arm_rows[arm_name]["recovery_fraction"],
                profile_margin,
            )
        deltas[profile_name] = per_arm

    scaffold_per_profile = {
        profile_name: any(entry["separates"] for entry in per_arm.values())
        for profile_name, per_arm in deltas.items()
    }
    scaffold_dependence = any(scaffold_per_profile.values())

    control_rows: dict[str, Any] = {}
    for profile_name, arm_rows in scaffold_raw.items():
        control_rows[profile_name] = {
            arm_name: {
                "recovery_fraction": arm_rows[arm_name]["recovery_fraction"],
                "control_item": arm_rows[arm_name]["control_item"],
                "control_share": arm_rows[arm_name]["control_share"],
                "control_margin": arm_rows[arm_name]["control_margin"],
                "distinguishable_from_control": arm_rows[arm_name][
                    "distinguishable_from_control"
                ],
                "max_unwritten_direction_energy_fraction": max(
                    (
                        value
                        for item, value in arm_rows[arm_name][
                            "declared_frame_energy_fraction"
                        ].items()
                        if item not in arm_rows[arm_name]["written_items"]
                    ),
                    default=0.0,
                ),
            }
            for arm_name in arm_names
        }

    spacing_raw = body_core["spacing"]["per_profile"]

    def spacing_figures(blocks_by_profile: Mapping[str, Any], block_name: str) -> dict[str, Any]:
        return {
            profile_name: {
                pair_name: {
                    "item_names": pair_meta[pair_name]["item_names"],
                    "declared_scale_distance": pair_meta[pair_name][
                        "declared_scale_distance"
                    ],
                    "declared_support_relation": pair_meta[pair_name][
                        "declared_support_relation"
                    ],
                    "recovery_fraction": record["recovery_fraction"],
                    "per_item_recovery_fraction": record[
                        "per_item_recovery_fraction"
                    ],
                    "max_off_diagonal_deposit_share": record[
                        "max_off_diagonal_deposit_share"
                    ],
                    "off_diagonal_deposit_share_sum": record[
                        "off_diagonal_deposit_share_sum"
                    ],
                    "written_direction_energy_fraction_total": record[
                        "written_direction_energy_fraction_total"
                    ],
                    "unwritten_direction_energy_fraction_total": record[
                        "unwritten_direction_energy_fraction_total"
                    ],
                }
                for pair_name, record in blocks[block_name].items()
            }
            for profile_name, blocks in blocks_by_profile.items()
        }

    with_activity = spacing_figures(spacing_raw, "pairs")
    without_activity = spacing_figures(spacing_raw, "pairs_without_activity")

    def pair_separation(figures: Mapping[str, Any]) -> dict[str, Any]:
        near = figures[near_name]
        far = figures[far_name]
        confusion_gap = float(near["max_off_diagonal_deposit_share"]) - float(
            far["max_off_diagonal_deposit_share"]
        )
        recovery_gap = float(far["recovery_fraction"]) - float(
            near["recovery_fraction"]
        )
        confusion_separates = margin_holds(confusion_gap, confusion_margin)
        recovery_separates = margin_holds(recovery_gap, recovery_margin)
        return {
            "near_pair": near_name,
            "far_pair": far_name,
            "near_max_off_diagonal_deposit_share": near[
                "max_off_diagonal_deposit_share"
            ],
            "far_max_off_diagonal_deposit_share": far[
                "max_off_diagonal_deposit_share"
            ],
            "confusion_difference": confusion_gap,
            "confusion_margin": confusion_margin,
            "confusion_separates": confusion_separates,
            "near_recovery_fraction": near["recovery_fraction"],
            "far_recovery_fraction": far["recovery_fraction"],
            "recovery_difference": recovery_gap,
            "recovery_margin": recovery_margin,
            "recovery_separates": recovery_separates,
            "near_unwritten_direction_energy_fraction_total": near[
                "unwritten_direction_energy_fraction_total"
            ],
            "far_unwritten_direction_energy_fraction_total": far[
                "unwritten_direction_energy_fraction_total"
            ],
            "unwritten_direction_fraction_difference": float(
                near["unwritten_direction_energy_fraction_total"]
            )
            - float(far["unwritten_direction_energy_fraction_total"]),
            "separates": bool(confusion_separates and recovery_separates),
        }

    spacing_headline = pair_separation(with_activity[default])
    spacing_baseline = pair_separation(without_activity[default])
    spacing_per_profile = {
        profile_name: pair_separation(figures)["separates"]
        for profile_name, figures in with_activity.items()
    }
    spacing_by_profile = {
        profile_name: pair_separation(figures)
        for profile_name, figures in with_activity.items()
    }

    attribution_raw = body_core["attribution"]["per_arm"]
    rail_name = declared["rail_only_profile"]
    mass_name = declared["mass_only_profile"]
    compound_name = declared["compound_profile"]
    topology_name = declared["topology_mass_profile"]
    rail_margin = float(declared["rail_component_margin"])
    mass_margin = float(declared["mass_component_margin"])
    additivity_tolerance = float(declared["attribution_additivity_tolerance"])

    def attribution_recovery(profile_name: str, arm_name: str) -> Any:
        return attribution_raw[profile_name]["arms"][arm_name]["recovery_fraction"]

    attribution_default_recovery = {
        arm_name: attribution_recovery(default, arm_name) for arm_name in arm_names
    }
    attribution_deltas = {
        profile_name: {
            arm_name: recovery_delta_entry(
                attribution_default_recovery[arm_name],
                attribution_recovery(profile_name, arm_name),
                profile_margin,
            )
            for arm_name in arm_names
        }
        for profile_name in declared["attribution_profile_names"]
        if profile_name != default
    }

    components: dict[str, Any] = {}
    for arm_name in arm_names:
        base = attribution_default_recovery[arm_name]
        rail_recovery = attribution_recovery(rail_name, arm_name)
        mass_recovery = attribution_recovery(mass_name, arm_name)
        compound_recovery = attribution_recovery(compound_name, arm_name)
        topology_recovery = attribution_recovery(topology_name, arm_name)
        rail_component = float(rail_recovery) - float(base)
        mass_component = float(mass_recovery) - float(base)
        compound_gain = float(compound_recovery) - float(base)
        attributed_gain = rail_component + mass_component
        residual = compound_gain - attributed_gain
        rail_reaches = margin_holds(abs(rail_component), rail_margin)
        mass_reaches = margin_holds(abs(mass_component), mass_margin)
        if rail_reaches and mass_reaches:
            channel = "rail-and-mass"
        elif rail_reaches:
            channel = "rail"
        elif mass_reaches:
            channel = "mass"
        else:
            channel = "neither"
        components[arm_name] = {
            "default_recovery_fraction": base,
            "rail_only_recovery_fraction": rail_recovery,
            "mass_only_recovery_fraction": mass_recovery,
            "compound_recovery_fraction": compound_recovery,
            "topology_mass_recovery_fraction": topology_recovery,
            "topology_mass_gain": float(topology_recovery) - float(base),
            "rail_component": rail_component,
            "mass_component": mass_component,
            "compound_gain": compound_gain,
            "attributed_gain": attributed_gain,
            "interaction_residual": residual,
            "rail_component_margin": rail_margin,
            "rail_component_reaches_margin": rail_reaches,
            "mass_component_margin": mass_margin,
            "mass_component_reaches_margin": mass_reaches,
            "rail_over_mass_ratio": (
                None if not mass_component else abs(rail_component) / abs(mass_component)
            ),
            "additivity_tolerance": additivity_tolerance,
            "additivity_holds": within_tolerance(residual, additivity_tolerance),
            "declared_channel": channel,
        }

    headline_arm = declared["attribution_headline_arm"]
    attribution_headline = {
        "arm": headline_arm,
        **components[headline_arm],
    }

    attribution_spacing_raw = body_core["attribution"]["spacing"]["per_profile"]
    attribution_spacing_by_profile = {
        profile_name: pair_separation(figures)
        for profile_name, figures in spacing_figures(
            attribution_spacing_raw, "pairs"
        ).items()
    }

    return {
        "profile_hook_signatures": {
            name: profiles["profile_hooks"]
            for name, profiles in body_core["profiles"].items()
        },
        "scaffold_recovery_fraction": {
            profile_name: {
                arm_name: arm_rows[arm_name]["recovery_fraction"]
                for arm_name in arm_names
            }
            for profile_name, arm_rows in scaffold_raw.items()
        },
        "scaffold_recovery_delta_vs_default": deltas,
        "scaffold_recovery_margin": profile_margin,
        "scaffold_separates_per_profile": scaffold_per_profile,
        "scaffold_dependence": scaffold_dependence,
        "scaffold_control_margin_results": control_rows,
        "spacing_figures_default_profile": with_activity[default],
        "spacing_figures_per_profile": with_activity,
        "spacing_figures_without_activity_per_profile": without_activity,
        "spacing_headline": spacing_headline,
        "spacing_headline_without_activity": spacing_baseline,
        "spacing_separation_per_profile": spacing_by_profile,
        "spacing_separates_per_profile": spacing_per_profile,
        "attribution_recovery_fraction": {
            profile_name: {
                arm_name: rows["arms"][arm_name]["recovery_fraction"]
                for arm_name in arm_names
            }
            for profile_name, rows in attribution_raw.items()
        },
        "attribution_delta_vs_default": attribution_deltas,
        "attribution_components": components,
        "attribution_headline": attribution_headline,
        "attribution_hook_signatures": {
            profile_name: rows["profile_hooks"]
            for profile_name, rows in attribution_raw.items()
        },
        "attribution_mass_metric_signatures": {
            profile_name: rows["mass_metric"]
            for profile_name, rows in attribution_raw.items()
        },
        "attribution_spacing_figures_per_profile": spacing_figures(
            attribution_spacing_raw, "pairs"
        ),
        "attribution_spacing_separation_per_profile": attribution_spacing_by_profile,
        "attribution_spacing_separates_per_profile": {
            profile_name: figures["separates"]
            for profile_name, figures in attribution_spacing_by_profile.items()
        },
    }


def digest_body(body: Mapping[str, Any]) -> str:
    """The declared content digest of a measured body."""

    return geometry.content_digest(body)


def build_receipt(config: durability.DurabilityConfig | None = None) -> dict[str, Any]:
    """The measured body, the derived summary, the declared boundary and the digest."""

    body_core = measured_body_core(config)
    body = {
        **body_core,
        "summary": summarize(body_core),
        "boundary": BOUNDARY,
    }
    return {**body, "content_digest": digest_body(body)}


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------
def summary_lines(summary: Mapping[str, Any], declared: Mapping[str, Any]) -> list[str]:
    """A compact human-readable reading of the measured summary."""

    lines: list[str] = []
    default = declared["default_profile"]
    lines.append(
        "declared profiles: "
        + ", ".join(
            f"{name}"
            + (
                " (canonical default)"
                if name == default
                else " (projected transport"
                + (" + inverse mass" if summary["profile_hook_signatures"][name]["has_projected_inv_mass"] else "")
                + ")"
            )
            for name in declared["profile_names"]
        )
    )
    lines.append(
        f"declared activity: {declared['config']['activity_ticks']} ticks at samples "
        f"{declared['config']['activity_samples']}, demand "
        f"{declared['config']['activity_demand']}, source_enabled "
        f"{declared['config']['source_enabled']}"
    )
    lines.append(
        f"durability control margin: {declared['control_margin']}"
    )
    lines.append("scaffold contrast (recovery after the declared activity):")
    for profile_name in declared["profile_names"]:
        figures = summary["scaffold_recovery_fraction"][profile_name]
        lines.append(
            f"  {profile_name}: "
            + ", ".join(
                f"{arm}={value if value is None else round(value, 6)}"
                for arm, value in figures.items()
            )
        )
    for profile_name, per_arm in summary["scaffold_recovery_delta_vs_default"].items():
        lines.append(
            f"  delta {profile_name} vs {default} (margin "
            f"{summary['scaffold_recovery_margin']}): "
            + ", ".join(
                f"{arm}={round(entry['absolute_difference'], 6)}"
                f"->{entry['separates']}"
                for arm, entry in per_arm.items()
            )
        )
    lines.append(
        f"  scaffold dependence (any declared arm/profile reaches the margin): "
        f"{summary['scaffold_dependence']}"
    )
    headline = summary["spacing_headline"]
    baseline = summary["spacing_headline_without_activity"]
    pair_meta = {row["name"]: row for row in declared["pair_declarations"]}
    lines.append(
        "spacing contrast on the declared default profile (declared scale distance "
        f"{pair_meta[declared['near_pair']]['declared_scale_distance']} near vs "
        f"{pair_meta[declared['far_pair']]['declared_scale_distance']} far):"
    )
    for pair_name, figures in summary["spacing_figures_default_profile"].items():
        lines.append(
            f"  {pair_name} {figures['item_names']} distance "
            f"{figures['declared_scale_distance']} ({figures['declared_support_relation']}): "
            f"max_off_diagonal={round(figures['max_off_diagonal_deposit_share'], 6)}, "
            f"min_recovery={round(figures['recovery_fraction'], 6)}, "
            f"unwritten_direction_fraction="
            f"{round(figures['unwritten_direction_energy_fraction_total'], 6)}"
        )
    lines.append(
        f"  confusion difference near-far={round(headline['confusion_difference'], 6)} "
        f"(margin {headline['confusion_margin']}) -> {headline['confusion_separates']}"
    )
    lines.append(
        f"  recovery difference far-near={round(headline['recovery_difference'], 6)} "
        f"(margin {headline['recovery_margin']}) -> {headline['recovery_separates']}"
    )
    lines.append(
        f"  unwritten-direction fraction difference near-far="
        f"{round(headline['unwritten_direction_fraction_difference'], 6)}"
    )
    lines.append(f"  spacing separates: {headline['separates']}")
    lines.append(
        "  spacing separates per profile: "
        + ", ".join(
            f"{name}={value}"
            for name, value in summary["spacing_separates_per_profile"].items()
        )
    )
    lines.append(
        "  same declared margins on the no-activity baseline arm (default profile): "
        f"near max_off_diagonal="
        f"{round(baseline['near_max_off_diagonal_deposit_share'], 6)}, "
        f"far max_off_diagonal="
        f"{round(baseline['far_max_off_diagonal_deposit_share'], 6)}, "
        f"confusion -> {baseline['confusion_separates']}, "
        f"recovery -> {baseline['recovery_separates']}, "
        f"separates -> {baseline['separates']}"
    )
    lines.append("attribution contrast (declared channel of each arm):")
    rules = {row["name"]: row for row in declared["attribution_arm_declarations"]}
    for profile_name, figures in summary["attribution_recovery_fraction"].items():
        lines.append(
            f"  {profile_name} [{rules[profile_name]['channel']}]: "
            + ", ".join(
                f"{arm}={value if value is None else round(value, 6)}"
                for arm, value in figures.items()
            )
        )
    for profile_name, per_arm in summary["attribution_delta_vs_default"].items():
        lines.append(
            f"  delta {profile_name} vs {default} (margin "
            f"{summary['scaffold_recovery_margin']}): "
            + ", ".join(
                f"{arm}={round(entry['absolute_difference'], 6)}->{entry['separates']}"
                for arm, entry in per_arm.items()
            )
        )
    for arm_name, figures in summary["attribution_components"].items():
        lines.append(
            f"  decomposition {arm_name}: rail_component="
            f"{round(figures['rail_component'], 9)} (margin "
            f"{figures['rail_component_margin']} -> "
            f"{figures['rail_component_reaches_margin']}), mass_component="
            f"{round(figures['mass_component'], 9)} (margin "
            f"{figures['mass_component_margin']} -> "
            f"{figures['mass_component_reaches_margin']}), compound_gain="
            f"{round(figures['compound_gain'], 9)}, residual="
            f"{round(figures['interaction_residual'], 9)} (tolerance "
            f"{figures['additivity_tolerance']} -> {figures['additivity_holds']}), "
            f"channel={figures['declared_channel']}"
        )
    lines.append(
        "  attribution headline arm "
        f"{summary['attribution_headline']['arm']}: channel="
        f"{summary['attribution_headline']['declared_channel']}"
    )
    lines.append(
        "  spacing separates on the declared single-channel arms: "
        + ", ".join(
            f"{name}={value}"
            for name, value in summary[
                "attribution_spacing_separates_per_profile"
            ].items()
        )
        + f" (default profile {summary['spacing_separates_per_profile'][default]})"
    )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
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
