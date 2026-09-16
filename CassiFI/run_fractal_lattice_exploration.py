"""Bounded numerical exploration of a double-helix lattice family on the canonical resonant page.

Question.  The canonical page is fixed at seven pools, two strands and four ports
per pool (28 paired positions, state dimension 112) and exposes exactly three
profile hooks.  The hypothesis under test is structural: the body is already a
three-dimensional double helix, so does re-spacing that helix -- and repeating its
cell as a lattice with a declared spacing law for the coupling between copies, up
to and including a golden-ratio law -- move the existing geometry, survival and
placement measures?

What this runner does, in order:

* ``recon``      -- reads the canonical field's derived geometry out of the module
  itself: the two strands, the one-turn longitudinal law, the point-reflected
  second strand, the bubble-shaped radius bulge along the axis, the measured
  anchor (the edge weights are derived from exactly those coordinates and the
  default transport is assembled from them), the declared adjacency kinds, and
  what the existing ``meaningful-helix`` declaration is.  It then states which
  arrangement-level changes are expressible and which are not.
* ``arrangements`` -- two declared families built from the field's own motif:
  (A) motif arms that change *one* law at a time -- the longitudinal station law
  (phi spacing, 1/phi spacing) or the coupling law applied to the derived weights
  (phi, 1/phi, 1.5x, 2.0x) -- and (B) lattices of copies on the built-in motif
  (a ring, a two-direction grid and a grid with three long cross-links, seven
  inter-copy spacing laws including a matched-random control, strand-to-strand
  rungs, and two shell-metric variants).  Every arm is normalized to a declared
  total coupling budget.
* measurement   -- the existing instruments, imported and reused unchanged: the
  geometry harness's linear generator, spectrum metrics, retention, access and
  hook probe; the durability harness's declared items, captures and arms, wrapped
  by the survival harness's own arm-record builder; the placement harness's own
  placement measurement and cross-arrangement dependence builder.
* ``spacing``   -- the spectrum measurement the phi hypothesis needs: eigenvalue
  gap statistics, mode participation-ratio and decay-rate distributions, a
  declared band self-similarity test over phi bands and octave bands, and a
  log-periodic order parameter with a measured synthetic positive control.
* ``comparisons`` -- declared margin checks, each with a firing control that moves
  one real measured number so the check must flip, a silenced control that
  compares an arm with itself, and continuity rows that reproduce numbers already
  frozen in the existing receipts and the field's own derivation.

Run: ``python run_fractal_lattice_exploration.py --output _diag/fractal-lattice/exploration.json``

Everything is a bounded canonical-field numerical measurement on a declared
scaffold.  Nothing here is a task-performance, memory-utility, semantic-content or
retrieval claim, and no arrangement claim is a claim about the evolving nonlinear
body.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry
import run_fractal_placement_exploration as placement
import run_fractal_survival_exploration as survival
from cassi_resonant_field import ResonantNumericalError, ResonantProfile

SCHEMA = "cassifi.fractal-lattice-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-lattice/exploration.json")

# Declared constants.
SEED = 20260916
PHI = (1.0 + math.sqrt(5.0)) / 2.0
POOLS = 7
PORTS_PER_POOL = geometry.DEFAULT_PORTS_PER_POOL
RUNG_SCALE = 1.0
FIBONACCI_WEIGHTS = (1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0)
# Longitudinal station laws (family A, hypothesis (a): the spacing law).
SPACING_LAWS = ("uniform", "phi", "phi-down")
# Coupling laws applied to the derived weights (family A, hypothesis (b)).
COUPLING_LAWS = ("uniform", "phi", "phi-down", "1.5x", "2.0x")
# Inter-copy spacing laws (family B).
INTER_COPY_LAWS = ("uniform", "phi-up", "phi-down", "fibonacci", "1.5x", "2.0x", "matched-random")
PATTERNS = ("ring", "grid", "grid-crosslinks")
PATTERN_OFFSETS: Mapping[str, tuple[int, ...]] = {"ring": (1,), "grid": (1, 2), "grid-crosslinks": (1, 2)}
CROSS_LINKS = ((0, 3), (1, 4), (2, 5))

# Declared derived magnitudes for the spectrum measurement.
BAND_RATIOS = (("phi", PHI), ("octave", 2.0))
ORDER_RATIOS = (("phi", PHI), ("2.0", 2.0), ("1.5", 1.5), ("3.0", 3.0))
ORDER_RATIO_OTHERS = ("2.0", "1.5", "3.0")
QUANTILES = (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)
SYNTHETIC_LADDER_LEVELS = 56
LEVEL_DEDUPLICATION_DECIMALS = 9

# Declared margins.
MARGIN_RECOVERY = float(survival.PROFILE_RECOVERY_MARGIN)
MARGIN_IPR = 0.01
MARGIN_ACCESS = 0.005
MARGIN_SELF_SIMILARITY = 0.05
MARGIN_PHI_ORDER = 0.01
MARGIN_SPEARMAN = 0.05
MARGIN_OVERLAP_PORTS = 1.0
TOP_PLACEMENTS_DECLARED = 7
MARGIN_WEIGHT_INVARIANCE = 1e-9
MARGIN_MASS_INVARIANCE = 0.5
MARGIN_DERIVATION_REPRODUCTION = 1e-12
CONTINUITY_ALLOWANCE = 1e-9
STATION_UNIFORMITY_ALLOWANCE = 1e-12

# Cross-strand rung laws: the declared scale of the rung at each of the 28 declared positions.
RUNG_LAWS = ("uniform", "phi")
# The nested-shell family: recursion depth of the nested core-shell motif, and the declared
# grading law of each shell's inertia.
NESTED_DEPTHS = (1, 2, 3, 4)
SHELL_LAWS = ("uniform", "phi", "2.0")
# Level 1 is the canonical core-shell partition itself (core pool 3, shell radius 1), whose
# *distance* rule is the canonical ring distance rather than a shell-index difference; levels 2 to
# 4 are declared (core pool, shell radius) partitions, and their distance is the absolute
# difference of their shell indices.
NESTED_SHELL_LEVELS = ((3, 1), (6, 1), (2, 1), (5, 1))
# The cited core-shell metric's own decay, used by the unnormalized continuity anchor that must
# reproduce the cited nested-core-shell arrangement at depth 1.
NESTED_REFERENCE_LAW = "reference"
SHELL_LAW_VALUES = {"uniform": 1.0, "phi": PHI, "2.0": 2.0, NESTED_REFERENCE_LAW: 0.7}
# The nested family's two declared axes: depth is read at the neutral shell law, the shell law at
# the deepest declared depth.
NESTED_DEPTH_AXIS_LAW = "uniform"
NESTED_LAW_AXIS_DEPTH = 4
# The unnormalized depth-1 reference-law arm: this runner's own reconstruction of the cited
# nested-core-shell construction, which its continuity rows reproduce.
NESTED_ANCHOR_NAME = "nested-depth1-reference-law"
# The bare-motif rung arms: (name, coupling law, rung law).
MOTIF_RUNG_ARMS = (
    ("motif-default-rungs", "uniform", "uniform"),
    ("motif-default-rungs-phi", "uniform", "phi"),
    ("motif-coupling-phi-rungs", "phi", "uniform"),
    ("motif-coupling-phi-rungs-phi", "phi", "phi"),
)

# --------------------------------------------------------------------------
# the rung-law controls: is the phi-rung gain specific to phi, or shared by any steep ramp?
# --------------------------------------------------------------------------
# Every control law is declared at the same 28 positions and normalized to the same declared
# channel total as the two primary laws, so the laws differ only in their *shape*.
RUNG_CONTROL_LAWS = ("1.5x", "2.0x", "phi-down", "centred", "single", "shuffled-phi")
# (name, coupling law, rung law) on the field's own body, i.e. the same body as the primary arms.
MOTIF_RUNG_LAW_CONTROL_ARMS = (
    ("motif-default-rungs-1.5x", "uniform", "1.5x"),
    ("motif-default-rungs-2.0x", "uniform", "2.0x"),
    ("motif-default-rungs-phi-down", "uniform", "phi-down"),
    ("motif-default-rungs-centred", "uniform", "centred"),
    ("motif-default-rungs-single", "uniform", "single"),
    ("motif-default-rungs-shuffled-phi", "uniform", "shuffled-phi"),
)
# The single-position law puts its whole declared channel on one declared position: the middle of
# the 28 declared positions.
SINGLE_RUNG_POSITION = 14
# The centred law's peak position (half-integer: the two middle positions share the peak).
CENTRED_RUNG_MIDPOINT = 13.5
# The shuffled control takes the phi law's own weight multiset and permutes it across the same
# 28 declared positions under one fixed seed, exactly as the matched-random inter-copy control does.
RUNG_CONTROL_SEED = SEED
MOTIF_RUNG_LAWS = RUNG_LAWS + RUNG_CONTROL_LAWS

# --------------------------------------------------------------------------
# the interaction grid: the mass channel crossed with a declared rail weight
# --------------------------------------------------------------------------
# The declared rail weight is a fraction of the geometry harness's flat-ladder budget, and the
# rail is always the ring-plus-rungs pattern.
INTERACTION_RAIL_FRACTIONS = (0.0, 0.25, 0.5, 1.0)
INTERACTION_PATTERN = "ring"
INTERACTION_RAIL_NAME = "ring-uniform-rungs"
INTERACTION_RAIL_MASS_NAME = "ring-uniform-rungs-mass"
INTERACTION_BASE_NAME = "interaction-rail-fraction"


def interaction_arm_name(fraction: float, mass: str) -> str:
    """The declared name of one interaction-grid cell."""
    label = f"{float(fraction):g}"
    return f"{INTERACTION_BASE_NAME}-{label}" + ("-mass" if mass == "core-shell" else "")


INTERACTION_ARMS = tuple(
    (interaction_arm_name(fraction, mass), float(fraction), mass)
    for mass in ("canonical", "core-shell")
    for fraction in INTERACTION_RAIL_FRACTIONS
)
INTERACTION_RAIL_LEG_NAMES = tuple(
    name for name, _fraction, mass in INTERACTION_ARMS if mass == "canonical"
)
INTERACTION_MASS_LEG_NAMES = tuple(
    name for name, _fraction, mass in INTERACTION_ARMS if mass == "core-shell"
)

# --------------------------------------------------------------------------
# the nested depth family under the anchor's own normalization
# --------------------------------------------------------------------------
# The same depth family, re-declared without the equal-total normalization, so a flat depth axis
# can be attributed either to depth itself or to the normalization.
NESTED_RAW_LAWS = (NESTED_REFERENCE_LAW, "uniform")
# The depth-1 reference-law arm is the existing continuity anchor, so it is not re-declared.
NESTED_RAW_ARMS = tuple(
    (f"nested-d{depth}-{law}-raw", int(depth), law)
    for law in NESTED_RAW_LAWS
    for depth in NESTED_DEPTHS
    if not (law == NESTED_REFERENCE_LAW and int(depth) == 1)
)
NESTED_ANCHOR_FAMILY_NAME = NESTED_ANCHOR_NAME


def nested_raw_family_names() -> tuple[str, ...]:
    """The unnormalized depth family: the existing anchor plus the newly declared raw arms."""
    return tuple(
        name for name, _depth, _law in NESTED_RAW_ARMS if name != NESTED_ANCHOR_FAMILY_NAME
    ) + (NESTED_ANCHOR_FAMILY_NAME,)

# Numbers already frozen in the existing receipts.
CITED_IPR_MEDIAN = {
    "helix7": 0.1565230898708423,
    "recursive-paired-loops": 0.28602472976220794,
    "nested-core-shell": 0.15986442406282375,
}
CITED_K4_RECOVERY = {
    "helix7": 0.0764836820747603,
    "nested-core-shell": 0.3351631005750861,
    "recursive-paired-loops": 0.061124304880849925,
}
CITED_HEADLINE_RECOVERY = {
    "helix7": 0.29462880739045766,
    "nested-core-shell": 0.3481552374975245,
    "recursive-paired-loops": 0.2702850816137677,
}
REFERENCE_NAME = "helix7"
NESTED_NAME = "nested-core-shell"
UNIFORM_MOTIF_NAME = "motif-default"
RING_UNIFORM_NAME = "ring-uniform"
MATCHED_RANDOM_NAME = "ring-matched-random"

# Attribution: the compound lattice arm and the two single-channel legs of its decomposition.
ATTRIBUTION_CANONICAL_NAME = UNIFORM_MOTIF_NAME
ATTRIBUTION_RAIL_ONLY_NAME = "ring-phi-up-rungs"
ATTRIBUTION_MASS_ONLY_NAME = "motif-shell-mass"
ATTRIBUTION_COMPOUND_NAME = "ring-phi-up-rungs-mass"
ATTRIBUTION_BARE_RUNG_NAMES = ("motif-default-rungs", "motif-default-rungs-phi")
ATTRIBUTION_NESTED_REFERENCE_NAME = NESTED_NAME
MARGIN_RAIL_COMPONENT = float(survival.RAIL_COMPONENT_MARGIN)
MARGIN_MASS_COMPONENT = float(survival.MASS_COMPONENT_MARGIN)
TOLERANCE_ATTRIBUTION_ADDITIVITY = float(survival.ATTRIBUTION_ADDITIVITY_TOLERANCE)
MARGIN_DEPTH_SATURATION = MARGIN_RECOVERY
# The normalization control must really vary the normalization: an unnormalized arm whose declared
# link channel matched the equal-budget family's would be a duplicate, and the depth contrast
# against it would be vacuous.  The declared channels differ by ~26% at depth 1 and ~88% at depth 4.
MARGIN_RAW_DECLARATION = 0.05

DEFAULT_SCOPE = "declared"
COMPACT_SCOPE = "compact"

_jsonable = geometry._jsonable
canonical_digest = geometry.canonical_digest
content_digest = geometry.content_digest
_array_digest = geometry._array_digest


# --------------------------------------------------------------------------
# the field's own motif: recovered edge scales and the derived rail
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class MotifEdge:
    """One edge of the field's own declared edge list, with its scale recovered from the field."""

    source: int
    destination: int
    kind: str
    declared_scale: float
    length: float


def motif_edge_table(ports_per_pool: int = PORTS_PER_POOL) -> tuple[MotifEdge, ...]:
    """The field's own edge list, with each edge's declared scale recovered from its weight.

    ``ResonantProfile.edges`` publishes ``coupling * scale / (length * sqrt(V_u V_v))``
    computed from the profile's own coordinates and volumes, so the declared scale
    of every edge is recoverable exactly by inverting that rule.  Nothing about the
    motif is restated here: the edge set, its kinds, its scales and its geometry all
    come out of the field.
    """
    profile = ResonantProfile(ports_per_pool=int(ports_per_pool))
    coordinates = np.asarray(profile.coordinates, dtype=np.float64)
    volumes = np.asarray(profile.volumes, dtype=np.float64)
    rows: list[MotifEdge] = []
    for source, destination, weight, kind in profile.edges:
        source, destination = int(source), int(destination)
        length = max(float(np.linalg.norm(coordinates[destination] - coordinates[source])), 1e-12)
        scale = float(weight) * length * math.sqrt(
            float(volumes[source]) * float(volumes[destination])
        ) / float(profile.coupling)
        rows.append(MotifEdge(source, destination, str(kind), float(scale), length))
    return tuple(rows)


def station_positions(ports_per_pool: int, spacing: str) -> tuple[np.ndarray, dict[str, Any]]:
    """The declared longitudinal stations of the ports under one station law.

    ``uniform`` is the field's own law: ``t_m = (m + 0.5) / (7 * ports_per_pool)``.
    A geometric law keeps the same longitudinal extent and the same two endpoint
    stations and re-spaces the interior, so consecutive station gaps carry the
    declared ratio exactly.
    """
    ports = POOLS * int(ports_per_pool)
    uniform = (np.arange(ports, dtype=np.float64) + 0.5) / float(ports)
    if spacing == "uniform":
        positions = uniform
        ratio = 1.0
    elif spacing in ("phi", "phi-down"):
        ratio = PHI if spacing == "phi" else 1.0 / PHI
        # t_k = t_min + extent*(ratio**k - 1)/(ratio**(ports-1) - 1), evaluated through its
        # exact consecutive gaps: t_k = a + b*ratio**k, so gap_k = b*ratio**k*(ratio - 1) and the
        # consecutive gap ratio is exactly `ratio`.  Accumulating the gaps instead of differencing
        # the closed form keeps that ratio exact to floating-point precision even for the smallest
        # gap of the progression, where differencing two nearby stations loses ~1e-11 relative.
        weights = ratio ** np.arange(ports - 1, dtype=np.float64)
        extent = float(uniform[-1] - uniform[0])
        gaps_declared = extent * weights / float(weights.sum())
        positions = float(uniform[0]) + np.concatenate(
            [np.zeros(1, dtype=np.float64), np.cumsum(gaps_declared)]
        )
    else:
        raise ResonantNumericalError(f"unknown station law {spacing!r}")
    gaps = np.diff(positions)
    gap_ratios = gaps[1:] / gaps[:-1]
    relative_deviation = float(np.abs(gap_ratios - ratio).max() / ratio) if gap_ratios.size else 0.0
    return positions, {
        "spacing_law": spacing,
        "ratio": float(ratio),
        "extent": [float(positions[0]), float(positions[-1])],
        "uniform_extent": [float(uniform[0]), float(uniform[-1])],
        "gap_min": float(gaps.min()),
        "gap_max": float(gaps.max()),
        "gap_mean": float(gaps.mean()),
        "consecutive_gap_ratio_min": float(gap_ratios.min()),
        "consecutive_gap_ratio_max": float(gap_ratios.max()),
        "consecutive_gap_ratio_target": float(ratio),
        "consecutive_gap_ratio_max_relative_deviation": relative_deviation,
        "consecutive_gap_ratio_precision_note": (
            "the stations are stored as double-precision longitudinal coordinates near the middle "
            "of the extent, so a gap is recovered as the exact difference of two rounded stations; "
            "the smallest gap is gap_min, and the achievable relative precision on its ratio is "
            "about the station rounding divided by gap_min, which is why the measured deviation is "
            "reported rather than asserted to be exactly zero"
        ),
    }


def spacing_coordinates(ports_per_pool: int, spacing: str) -> tuple[np.ndarray, dict[str, Any]]:
    """The declared coordinates of the two strands under one station law.

    Only the longitudinal station law changes.  The angle law ``2*pi*t``, the
    radius law ``1 + 0.08*sin(pi*t)`` and the point reflection ``(t, -x, -y)`` of
    the second strand are the field's own and are used verbatim.
    """
    positions, station_report = station_positions(ports_per_pool, spacing)
    angle = 2.0 * math.pi * positions
    radius = 1.0 + 0.08 * np.sin(math.pi * positions)
    yang = np.column_stack([positions, radius * np.cos(angle), radius * np.sin(angle)])
    yin = np.column_stack([positions, -yang[:, 1], -yang[:, 2]])
    return np.vstack([yang, yin]), station_report


def coupling_factor(law: str, index: int) -> float:
    """The declared factor one coupling law applies to an edge at a declared position index."""
    k = int(index)
    if law == "uniform":
        return 1.0
    if law == "phi":
        return float(PHI ** k)
    if law == "phi-down":
        return float(PHI ** (-k))
    if law == "1.5x":
        return float(1.5 ** k)
    if law == "2.0x":
        return float(2.0 ** k)
    raise ResonantNumericalError(f"unknown coupling law {law!r}")


def derived_rail(
    edges: Sequence[MotifEdge],
    coordinates: np.ndarray,
    volumes: np.ndarray,
    coupling: float,
    coupling_law: str = "uniform",
    ports_per_pool: int = PORTS_PER_POOL,
) -> np.ndarray:
    """Assemble the transport matrix from an edge list, exactly as the field assembles it.

    ``rail[destination, source] += weight`` and ``rail[source, destination] -= weight``
    with ``weight = coupling * scale * factor / (length * sqrt(V_u V_v))`` and the
    length taken from the supplied coordinates, i.e. the field's own rule with the
    declared station law in place of the built-in one.
    """
    ports = POOLS * int(ports_per_pool)
    dimension = 2 * ports
    rail = np.zeros((dimension, dimension), dtype=np.float64)
    for edge in edges:
        source, destination = int(edge.source), int(edge.destination)
        length = max(float(np.linalg.norm(coordinates[destination] - coordinates[source])), 1e-12)
        factor = coupling_factor(coupling_law, source % ports)
        weight = float(coupling) * float(edge.declared_scale) * factor / (
            length * math.sqrt(float(volumes[source]) * float(volumes[destination]))
        )
        rail[destination, source] += weight
        rail[source, destination] -= weight
    return rail


def motif_reference_weight(ports_per_pool: int = PORTS_PER_POOL) -> float:
    """The declared coupling budget of a motif arm: the field's own rail L1, measured."""
    return float(np.abs(np.asarray(
        ResonantProfile(ports_per_pool=int(ports_per_pool)).transport_matrix, dtype=np.float64
    )).sum())


def lattice_reference_weight(ports_per_pool: int = PORTS_PER_POOL) -> float:
    """The declared inter-copy budget: the geometry harness's own flat-ladder budget."""
    parts = geometry.canonical_parts(ports_per_pool)
    ladder = geometry.arrangement_named("flat-ladder").pool_links
    return float(sum(
        float(scale) * geometry.realized_pair_strength((int(a), int(b), 1.0), parts)
        for a, b, scale in ladder
    ))


def motif_rail(
    ports_per_pool: int = PORTS_PER_POOL, *, spacing: str = "uniform", coupling: str = "uniform"
) -> tuple[np.ndarray, dict[str, Any]]:
    """The derived rail of the field's own motif under one station law and one coupling law."""
    profile = ResonantProfile(ports_per_pool=int(ports_per_pool))
    edges = motif_edge_table(ports_per_pool)
    coordinates, station_report = spacing_coordinates(ports_per_pool, spacing)
    volumes = np.asarray(profile.volumes, dtype=np.float64)
    rail = derived_rail(
        edges, coordinates, volumes, float(profile.coupling), coupling,
        ports_per_pool=ports_per_pool,
    )
    reference = motif_reference_weight(ports_per_pool)
    total = float(np.abs(rail).sum())
    factor = reference / total
    rail = rail * factor
    report = {
        "spacing": dict(station_report),
        "coupling_law": coupling,
        "edge_count": len(edges),
        "declared_scale_min": float(min(edge.declared_scale for edge in edges)),
        "declared_scale_max": float(max(edge.declared_scale for edge in edges)),
        "edge_length_min": float(min(edge.length for edge in edges)),
        "edge_length_max": float(max(edge.length for edge in edges)),
        "rail_l1_before_normalization": total,
        "normalization_factor": float(factor),
        "rail_l1_after_normalization": float(np.abs(rail).sum()),
        "declared_coupling_budget_reference": reference,
    }
    return rail, report


def field_rail(ports_per_pool: int = PORTS_PER_POOL) -> np.ndarray:
    """The field's own default transport matrix."""
    return np.asarray(
        ResonantProfile(ports_per_pool=int(ports_per_pool)).transport_matrix, dtype=np.float64
    )


def motif_derivation_report(ports_per_pool: int = PORTS_PER_POOL) -> dict[str, Any]:
    """Continuity: reproduce the field's own transport from its own edges and coordinates."""
    derived, report = motif_rail(ports_per_pool, spacing="uniform", coupling="uniform")
    reference = field_rail(ports_per_pool)
    difference = float(np.abs(derived - reference).max())
    return {
        "definition": (
            "the field's own edge list with each declared scale recovered from the field's own "
            "weight rule, re-assembled with the field's own coordinates through the same rule"
        ),
        "max_abs_difference": difference,
        "allowance": MARGIN_DERIVATION_REPRODUCTION,
        "holds": bool(difference <= MARGIN_DERIVATION_REPRODUCTION),
        "derived_rail_sha256": _array_digest(derived),
        "field_rail_sha256": _array_digest(reference),
        "derived_rail_l1": float(np.abs(derived).sum()),
        "field_rail_l1": float(np.abs(reference).sum()),
        "report": report,
    }


# --------------------------------------------------------------------------
# recon: what the canonical page derives and what is expressible
# --------------------------------------------------------------------------
def recon_block() -> dict[str, Any]:
    """The canonical page's derived geometry and hook surface, read out of the module itself."""
    profile = ResonantProfile()
    ports = profile.port_count
    coordinates = np.asarray(profile.coordinates, dtype=np.float64)
    yang, yin = coordinates[:ports], coordinates[ports:]
    strand_pair_distance = np.linalg.norm(yin - yang, axis=1)
    volumes = np.asarray(profile.volumes, dtype=np.float64)
    kinds: dict[str, int] = {}
    yang_intra = yin_intra = yang_neck = yin_neck = 0
    cross_strand: list[dict[str, Any]] = []
    pool_of = lambda index: int(index % ports) // int(profile.ports_per_pool)
    for source, destination, _weight, kind in profile.edges:
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == "intra":
            yang_intra += int(source < ports)
            yin_intra += int(source >= ports)
        if kind == "neck":
            yang_neck += int(source < ports)
            yin_neck += int(source >= ports)
        if (source < ports) != (destination < ports):
            cross_strand.append({
                "source": int(source), "destination": int(destination), "kind": str(kind),
                "source_pool": pool_of(source), "source_port": int(source % ports),
                "destination_pool": pool_of(destination), "destination_port": int(destination % ports),
            })
    fields = [field.name for field in dataclasses.fields(ResonantProfile)]
    hook_fields = [name for name in fields if name.startswith("projected_")]
    stations = np.unique(yang[:, 0])
    station_gaps = np.diff(stations)
    gap_mean = float(station_gaps.mean()) if station_gaps.size else 0.0
    gap_relative_spread = (
        float(np.abs(station_gaps - gap_mean).max() / gap_mean) if gap_mean > 0.0 else None
    )
    return {
        "question": (
            "(a) what does the canonical field declare spatially, (b) what is the existing "
            "meaningful-helix declaration, and (c) which arrangement-level changes are "
            "expressible through the declared hooks?"
        ),
        "canonical_page": {
            "pools": int(profile.pools),
            "ports_per_pool": int(profile.ports_per_pool),
            "declared_positions": int(ports),
            "strands": 2,
            "state_dimension": int(4 * ports),
            "page_shape": list(profile.page_shape),
            "pools_fixed_by_construction": (
                "ResonantProfile.__post_init__ rejects pools != 7, so no arrangement can change "
                "the pool count or add a second helix as a separate object"
            ),
            "ports_per_pool_minimum": 4,
        },
        "declared_spatial_structure": {
            "dimensionality": (
                "three-dimensional: the embedding is a double helix in 3-space, and the page's "
                "own coordinate is the longitudinal station t"
            ),
            "coordinate_rule": (
                "t = (pool + (local+0.5)/ports_per_pool)/pools; angle = 2*pi*t; "
                "radius = 1 + 0.08*sin(pi*t); strand A row = (t, radius*cos(angle), "
                "radius*sin(angle)); strand B row = (t, -x, -y)"
            ),
            "strand_count": 2,
            "second_strand_is_the_point_reflection": bool(
                np.allclose(yin[:, 1:], -yang[:, 1:], atol=0.0, rtol=0.0)
            ),
            "strands_share_longitudinal_stations": bool(
                np.allclose(yang[:, 0], yin[:, 0], atol=0.0, rtol=0.0)
            ),
            "stations_are_uniform_in_t": bool(
                gap_relative_spread is not None and gap_relative_spread <= STATION_UNIFORMITY_ALLOWANCE
            ),
            "station_uniformity_allowance": STATION_UNIFORMITY_ALLOWANCE,
            "station_count": int(stations.size),
            "station_gap": float(gap_mean),
            "station_gap_relative_spread": gap_relative_spread,
            "station_gap_expected": float(1.0 / (POOLS * int(profile.ports_per_pool))),
            "longitudinal_extent": [float(stations.min()), float(stations.max())],
            "radius_law_is_a_bubble_bulge_along_the_axis": (
                "radius = 1 + 0.08*sin(pi*t), measured range below: the strand radius bulges "
                "and narrows along the axis, so the built-in motif is a double helix carrying a "
                "bubble-shaped bulge along its axis"
            ),
            "radius_range": [
                float(np.linalg.norm(yang[:, 1:], axis=1).min()),
                float(np.linalg.norm(yang[:, 1:], axis=1).max()),
            ],
            "strand_pair_3d_distance": {
                "min": float(strand_pair_distance.min()),
                "max": float(strand_pair_distance.max()),
                "mean": float(strand_pair_distance.mean()),
            },
            "volume_range": [float(volumes.min()), float(volumes.max())],
            "inertance_ladder": (
                "inertances = 1.3**pool replicated over the pool's ports on both strands, so the "
                "default mass metric is a geometric ladder along the pool coordinate"
            ),
            "inertance_range": [
                float(np.asarray(profile.inertances, dtype=np.float64).min()),
                float(np.asarray(profile.inertances, dtype=np.float64).max()),
            ],
            "declared_adjacency_kinds": {str(key): int(value) for key, value in sorted(kinds.items())},
            "intra_edges_by_strand": {"yang": int(yang_intra), "yin": int(yin_intra)},
            "neck_edges_by_strand": {"yang": int(yang_neck), "yin": int(yin_neck)},
            "do_the_28_positions_map_onto_something_spatial": (
                "yes: 28 positions = 7 pools x 4 sub-stations on the helix, uniformly spaced in "
                "t at the measured station gap above, each carrying two strand coordinates at "
                "the measured strand-pair distance; there is no second lattice axis and no bubble "
                "interior as state"
            ),
        },
        "the_geometry_is_load_bearing": {
            "statement": (
                "the coordinates are not decoration: every edge weight is "
                "coupling*scale/(length*sqrt(V_u V_v)) with the length taken from them, and the "
                "default transport matrix is assembled from the declared edge list with those "
                "weights whenever projected_transport is None, which is the default path"
            ),
            "weight_rule": "coupling * scale / (length * sqrt(V_u V_v)), length from the declared coordinates",
            "measured_reproduction": motif_derivation_report(),
        },
        "what_is_inert": {
            "statement": (
                "what is inert is an *arrangement-level coordinate override*: coordinates is a "
                "computed property, no field of ResonantProfile carries site positions, and "
                "nothing reads a supplied coordinate array.  The geometry the declared "
                "coordinates imply is nevertheless expressible, because the rail is a pure "
                "function of the coordinates through the rule above and projected_transport "
                "accepts any antisymmetric matrix."
            ),
            "coordinate_override_field_exists": False,
        },
        "meaningful_helix_declaration": {
            "circuit": (
                "one closed cycle over all 56 strand coordinates: Yang indices 0..27 in "
                "increasing order, the upper-endpoint bridge, Yin indices 27..0 in decreasing "
                "order, then the lower-endpoint bridge"
            ),
            "inter_strand_edges_declared": cross_strand,
            "inter_strand_edge_count": len(cross_strand),
            "is_it_already_a_double_helix": (
                "yes.  The embedding is a double helix (two strands, one complete turn over the "
                "longitudinal extent, the second strand the point reflection of the first, with "
                "a bubble-shaped radius bulge along the axis) and the built-in topology already "
                "joins the two strands into one closed loop; the connection graph, however, "
                "touches the two strands only at the two endpoints, so the built-in motif has no "
                "ladder of rungs between the strands."
            ),
            "intra_rings_by_strand": "declared on the Yang strand only (see intra_edges_by_strand)",
            "neck_links_by_strand": "declared on the Yang strand only (see neck_edges_by_strand)",
        },
        "hook_surface": {
            "dataclass_fields": fields,
            "projected_hook_fields": hook_fields,
            "only_three_hooks_move_the_body": (
                "projected_transport, projected_inv_mass and projected_quartic_weights are the "
                "only hook fields; the topology field is metadata whenever projected_transport is "
                "set, and the hook probe on every arrangement records that measured consequence"
            ),
        },
        "expressibility": {
            "literal_coordinate_override": "not expressible: there is no site-position hook and nothing reads a coordinate array",
            "the_rail_the_spacing_law_implies": (
                "expressible: re-derive the transport with the field's own weight rule from the "
                "declared coordinates and declare it through projected_transport; the "
                "reproduction above measures that the same derivation returns the field's own "
                "rail when the station law is the built-in uniform one"
            ),
            "literal_three_dimensional_bubble_lattice": (
                "not expressible: pools is fixed at exactly 7, there is one helix, the state is a "
                "fixed 9-lane page per mode with no bubble interior, and no lattice constant, "
                "cell count or site placement can be declared"
            ),
            "declared_translation_of_the_hypothesis": (
                "(a) spacing: the longitudinal station law of the built-in helix is re-spaced as "
                "a geometric progression of ratio phi or 1/phi over the same extent, and the rail "
                "the field's own weight rule assigns to that geometry is measured; "
                "(b) coupling: the built-in stations are kept and the derived weights are graded "
                "by phi**k or (1/phi)**k; the two are reported separately because spacing and "
                "coupling are different hypotheses; "
                "(c) lattice of copies: the built-in motif plus a declared inter-copy coupling "
                "lattice over the seven declared positions -- a ring, a two-direction grid, and a "
                "grid with three long cross-links -- with the coupling graded by a spacing law."
            ),
        },
    }


# --------------------------------------------------------------------------
# declared arrangement families
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class LatticeArrangement:
    """One declared arrangement: a motif arm or a lattice of copies on the built-in motif."""

    name: str
    kind: str
    spacing: str = "uniform"
    coupling: str = "uniform"
    pattern: str | None = None
    inter_copy_law: str | None = None
    rungs: bool = False
    rung_law: str = "uniform"
    mass: str = "canonical"
    depth: int = 1
    shell_law: str = "uniform"
    normalized: bool = True
    # the interaction grid's declared rail weight, as a fraction of the geometry budget
    rail_fraction: float | None = None
    rule: str = ""
    note: str = ""
    seed: int = SEED


def pattern_edges(pattern: str) -> tuple[tuple[int, int, int, str], ...]:
    """Declared edge order of one inter-copy pattern: ``(source, destination, law index, family)``."""
    if pattern not in PATTERN_OFFSETS:
        raise ResonantNumericalError(f"unknown inter-copy pattern {pattern!r}")
    rows: list[tuple[int, int, int, str]] = []
    for offset in PATTERN_OFFSETS[pattern]:
        for site in range(POOLS):
            rows.append((site, (site + offset) % POOLS, site, f"offset-{offset}"))
    if pattern == "grid-crosslinks":
        for index, (source, destination) in enumerate(CROSS_LINKS):
            rows.append((int(source), int(destination), index, "cross-link"))
    return tuple(rows)


def inter_copy_weight(law: str, index: int) -> float:
    """The declared weight of one inter-copy law at a declared sequence index."""
    k = int(index)
    if law == "uniform":
        return 1.0
    if law == "fibonacci":
        return float(FIBONACCI_WEIGHTS[k])
    if law == "phi-up":
        return float(PHI ** k)
    if law == "phi-down":
        return float(PHI ** (-k))
    if law == "1.5x":
        return float(1.5 ** k)
    if law == "2.0x":
        return float(2.0 ** k)
    raise ResonantNumericalError(f"inter-copy law {law!r} has no closed form")


def inter_copy_scales(pattern: str, law: str, *, seed: int = SEED) -> tuple[float, ...]:
    """The declared scale of every inter-copy edge of a pattern under one spacing law.

    ``matched-random`` is the declared control: it takes the phi-up weight multiset
    of the *same* edge list and permutes it across those edges under one fixed seed,
    holding edge count, declared total weight and the weight multiset fixed.
    """
    edges = pattern_edges(pattern)
    if law == "matched-random":
        weights = [inter_copy_weight("phi-up", edge[2]) for edge in edges]
        order = np.random.default_rng(seed).permutation(len(weights))
        return tuple(float(weights[int(position)]) for position in order)
    return tuple(inter_copy_weight(law, edge[2]) for edge in edges)


def inter_copy_rule(law: str) -> str:
    if law == "uniform":
        return "every inter-copy coupling at the same declared scale"
    if law == "fibonacci":
        return ("w_k = F[k+1] with F = (1, 2, 3, 5, 8, 13, 21): the integer Fibonacci "
                "grading whose consecutive ratios are the phi convergents")
    if law == "phi-up":
        return "w_k = phi**k: every consecutive inter-copy coupling ratio is exactly phi"
    if law == "phi-down":
        return "w_k = phi**-k: every consecutive inter-copy coupling ratio is exactly 1/phi"
    if law == "1.5x":
        return "w_k = 1.5**k"
    if law == "2.0x":
        return "w_k = 2.0**k"
    if law == "matched-random":
        return ("the phi-up weight multiset of this pattern's own edge list permuted across those "
                "same edges by numpy.default_rng(seed): same edge count, same declared total "
                "weight, same multiset, shuffled assignment")
    raise ResonantNumericalError(f"unknown inter-copy law {law!r}")


def spacing_rule(spacing: str) -> str:
    if spacing == "uniform":
        return "the built-in uniform station law t_m = (m + 0.5)/(7*ports_per_pool)"
    if spacing == "phi":
        return ("t_k a geometric progression of ratio phi over the built-in extent, endpoints "
                "held fixed, so consecutive station gaps carry ratio phi exactly")
    if spacing == "phi-down":
        return ("t_k a geometric progression of ratio 1/phi over the built-in extent, endpoints "
                "held fixed, so consecutive station gaps carry ratio 1/phi exactly")
    raise ResonantNumericalError(f"unknown station law {spacing!r}")


def coupling_rule(coupling: str) -> str:
    if coupling == "uniform":
        return "the derived weights unchanged"
    return (f"the derived weights multiplied by {coupling}**k with k the source's declared "
            f"position index (0..27)")


def rung_law_scale(law: str, position: int, ports: int = POOLS * PORTS_PER_POOL) -> float:
    """The declared scale of one strand-to-strand rung under one declared rung law.

    Every law is declared over the same ``ports`` declared positions and is normalized
    afterwards to the same declared channel total, so the laws differ only in shape.
    """
    k = int(position)
    last = int(ports) - 1
    if law == "uniform":
        return float(RUNG_SCALE)
    if law == "phi":
        return float(PHI ** k)
    if law == "1.5x":
        return float(1.5 ** k)
    if law == "2.0x":
        return float(2.0 ** k)
    if law == "phi-down":
        return float(PHI ** (last - k))
    if law == "centred":
        return float(PHI ** (-abs(float(k) - CENTRED_RUNG_MIDPOINT)))
    if law == "single":
        return float(RUNG_SCALE) if k == SINGLE_RUNG_POSITION else 0.0
    if law == "shuffled-phi":
        return float(shuffled_phi_scales(ports)[k])
    raise ResonantNumericalError(f"unknown rung law {law!r}")


def shuffled_phi_scales(ports: int = POOLS * PORTS_PER_POOL) -> tuple[float, ...]:
    """The phi rung law's own weight multiset, permuted across the same declared positions.

    This is the rung-level counterpart of the declared ``matched-random`` inter-copy
    control: the multiset, the position count and the declared channel total are held
    fixed and only the assignment is shuffled, under one fixed seed.
    """
    weights = [float(PHI ** k) for k in range(int(ports))]
    order = np.random.default_rng(RUNG_CONTROL_SEED).permutation(len(weights))
    return tuple(float(weights[int(index)]) for index in order)


def rung_law_rule(law: str) -> str:
    if law == "uniform":
        return (f"the uniform RUNG_SCALE set: every one of the 28 declared positions carries a rung "
                f"at the single scale {RUNG_SCALE}")
    if law == "phi":
        return ("the phi-graded set: w_j = phi**j at declared position j = 0..27, the same closed "
                "form as the inter-copy phi-up law, so consecutive rung scales carry ratio phi "
                "exactly")
    if law == "1.5x":
        return ("the 1.5-graded ramp: w_j = 1.5**j, an unbounded geometric ramp whose consecutive "
                "ratio is 1.5 exactly")
    if law == "2.0x":
        return ("the 2-graded ramp: w_j = 2.0**j, an unbounded geometric ramp whose consecutive "
                "ratio is 2.0 exactly")
    if law == "phi-down":
        return ("the reversed phi ramp: w_j = phi**(27-j), the same multiset as the phi law with "
                "its order reversed")
    if law == "centred":
        return ("the centred steep law: w_j = phi**(-|j - 13.5|), peak at the two middle declared "
                "positions and geometric falloff in both directions")
    if law == "single":
        return (f"the single-position law: the whole declared channel on declared position "
                f"{SINGLE_RUNG_POSITION} and zero elsewhere, so exactly one of the 28 declared "
                f"positions carries a rung")
    if law == "shuffled-phi":
        return ("the shuffled phi control: the phi law's own weight multiset permuted across the "
                "same 28 declared positions by numpy.default_rng(seed), so the multiset, the "
                "position count and the declared channel total are fixed and only the assignment "
                "is shuffled")
    raise ResonantNumericalError(f"unknown rung law {law!r}")


def rung_law_scales(law: str, ports_per_pool: int = PORTS_PER_POOL) -> tuple[float, ...]:
    """The raw declared rung scale at every declared position, before any normalization."""
    ports = POOLS * int(ports_per_pool)
    return tuple(rung_law_scale(law, position, ports) for position in range(ports))


def rung_law_scale_digest(law: str, ports_per_pool: int = PORTS_PER_POOL) -> str:
    """Digest of one rung law's raw declared scale list, so a declared shape is auditable."""
    return _array_digest(np.asarray(rung_law_scales(law, ports_per_pool), dtype=np.float64))


_scale_digest = rung_law_scale_digest


def nested_shell_index(level: int, pool: int) -> int:
    """One pool's declared shell index at one nesting level.

    Level 1 is the canonical core-shell partition itself (core pool 3, shell radius
    1); levels 2 and up are the declared (core, radius) partitions of
    ``NESTED_SHELL_LEVELS``.  A pool's shell index at a level is its ring distance
    to that level's core divided by that level's shell radius.
    """
    core, radius = NESTED_SHELL_LEVELS[int(level) - 1]
    return geometry._ring_distance(pool, int(core)) // int(radius)


def nested_level_distance(level: int, left: int, right: int) -> float:
    """The distance one nesting level contributes between two declared pools."""
    if level == 1:
        return float(geometry._ring_distance(left, right))
    return float(abs(nested_shell_index(level, left) - nested_shell_index(level, right)))


def nested_link_scales(
    depth: int, ports_per_pool: int = PORTS_PER_POOL
) -> tuple[tuple[int, int, float], ...]:
    """The declared nested pool graph at one recursion depth, before normalization.

    Every level multiplies the link scale by ``CORE_SHELL_DECAY ** distance`` under
    that level's own declared partition, so depth 1 with the canonical partition is
    exactly the nested link rule the geometry harness declares for
    ``nested-core-shell``.
    """
    if int(depth) not in NESTED_DEPTHS:
        raise ResonantNumericalError(f"unknown nesting depth {depth!r}")
    links: list[tuple[int, int, float]] = []
    for left in range(POOLS):
        for right in range(POOLS):
            if left == right:
                continue
            scale = float(geometry.CHAIN_SCALE)
            for level in range(1, int(depth) + 1):
                scale *= float(geometry.CORE_SHELL_DECAY) ** nested_level_distance(level, left, right)
            links.append((left, right, scale))
    return tuple(links)


def nested_shell_inverse_mass(
    depth: int, shell_law: str, ports_per_pool: int = PORTS_PER_POOL
) -> np.ndarray:
    """The declared shell metric of the nested family, a positive per-port diagonal.

    ``mass(p) = prod_j law**s_j(p)`` with ``s_j`` the shell index of level ``j``; at
    depth 1 with the reference law this is exactly
    ``geometry.core_shell_inverse_mass()``.
    """
    if int(depth) not in NESTED_DEPTHS:
        raise ResonantNumericalError(f"unknown nesting depth {depth!r}")
    if shell_law not in SHELL_LAW_VALUES:
        raise ResonantNumericalError(f"unknown shell law {shell_law!r}")
    value = float(SHELL_LAW_VALUES[shell_law])
    p = int(ports_per_pool)
    by_pool = np.ones(POOLS, dtype=np.float64)
    for pool in range(POOLS):
        for level in range(1, int(depth) + 1):
            by_pool[pool] *= value ** nested_shell_index(level, pool)
    if not np.isfinite(by_pool).all() or not (by_pool > 0.0).all():
        raise ResonantNumericalError(f"nested shell law {shell_law!r} at depth {depth} is not positive")
    return np.concatenate([np.repeat(by_pool, p), np.repeat(by_pool, p)])


def nested_rule(depth: int, shell_law: str, *, normalized: bool = True) -> str:
    """The declared construction rule of one nested-family arm."""
    levels = "; ".join(
        f"level {level}: "
        + ("the canonical core-shell partition, core pool 3, distance = the canonical ring distance"
           if level == 1
           else f"core pool {NESTED_SHELL_LEVELS[level - 1][0]}, shell radius "
                f"{NESTED_SHELL_LEVELS[level - 1][1]}, distance = |shell index difference|")
        for level in range(1, int(depth) + 1)
    )
    return (
        "projected_transport = the geometry harness's own declared arrangement construction "
        "(canonical intra rings + the two strand bridges + the declared pool graph through "
        "geometry.rail_from_pool_links, the same construction the cited nested-core-shell uses), "
        f"with the nested pool graph at recursion depth {int(depth)}: every level multiplies the "
        "link scale by CORE_SHELL_DECAY**d where d is that level's own declared distance "
        f"({levels}); projected_inv_mass = the declared nested shell metric "
        f"prod_j {shell_law!r}**s_j(p) over those levels' shell indices, a positive per-port "
        "diagonal; "
        + ("the declared link scales are normalized by one common factor to the geometry harness's "
           f"own flat-ladder budget ({lattice_reference_weight()!r})"
           if normalized else
           "UNNORMALIZED continuity anchor: the raw declared nested scales, i.e. exactly the "
           "geometry harness's own nested-core-shell construction, with no factor applied")
    )


def arrangement_inventory(scope: str = DEFAULT_SCOPE, *, seed: int = SEED) -> tuple[LatticeArrangement, ...]:
    """The declared lattice family, plus the three cited reference arrangements."""
    declarations: list[LatticeArrangement] = []

    def add_motif(name: str, spacing: str, coupling: str, *, rungs: bool = False,
                  rung_law: str = "uniform", mass: str = "canonical", note: str = "") -> None:
        if rungs and rung_law not in MOTIF_RUNG_LAWS:
            raise ResonantNumericalError(f"unknown rung law {rung_law!r}")
        declarations.append(LatticeArrangement(
            name=name, kind="motif", spacing=spacing, coupling=coupling, seed=seed,
            rungs=rungs, rung_law=rung_law, mass=mass,
            rule=(
                f"projected_transport = the rail the field's own weight rule assigns to the "
                f"declared geometry: the field's own edge list (scales recovered from the field's "
                f"own weights) re-assembled with the station law {spacing!r} "
                f"({spacing_rule(spacing)}) and the coupling law {coupling!r} "
                f"({coupling_rule(coupling)}); angle, radius and the point-reflected second "
                f"strand are the field's own; one common factor normalizes the whole rail to the "
                f"field's own rail L1 ({motif_reference_weight()!r})"
                + (f"; then one oriented antisymmetric rung is set at every one of the 28 declared "
                   f"positions from the {rung_law!r} rung law ({rung_law_rule(rung_law)}), the rung "
                   f"set normalized by one common factor to the motif body's own declared rail L1 "
                   f"({motif_reference_weight()!r}), in the Yang->Yin orientation"
                   if rungs else "")
                + (f"; projected_inv_mass = the geometry harness's core-shell shell metric "
                   f"0.7**ring_distance(pool, 3), which is the mass channel alone"
                   if mass == "core-shell" else "")
            ),
            note=note,
        ))

    def add_nested(name: str, depth: int, shell_law: str, *, normalized: bool = True,
                   note: str = "") -> None:
        declarations.append(LatticeArrangement(
            name=name, kind="nested", depth=int(depth), shell_law=shell_law,
            normalized=bool(normalized), mass="nested-shell", seed=seed,
            rule=nested_rule(depth, shell_law, normalized=normalized),
            note=note,
        ))

    def add_lattice(name: str, pattern: str, law: str, *, rungs: bool = False,
                    mass: str = "canonical", note: str = "") -> None:
        declarations.append(LatticeArrangement(
            name=name, kind="lattice", pattern=pattern, inter_copy_law=law, rungs=rungs,
            mass=mass, seed=seed,
            rule=(
                f"projected_transport = the built-in motif rail (the field's own derived "
                f"transport, unchanged) plus a declared inter-copy coupling lattice: pattern "
                f"{pattern!r} ({len(pattern_edges(pattern))} declared pool links written by "
                f"geometry.pool_link_port_pairs and geometry._edge_weight), spacing law {law!r} "
                f"({inter_copy_rule(law)}); the declared inter-copy scales are normalized by one "
                f"common factor to the geometry harness's flat-ladder budget "
                f"({lattice_reference_weight()!r})"
                + ("; plus 28 strand-to-strand rungs, one at every declared position, in the "
                   "Yang->Yin orientation" if rungs else "")
                + ("; projected_inv_mass = the geometry harness's core-shell shell metric "
                   "0.7**ring_distance(pool, 3)" if mass == "core-shell"
                   else "; projected_inv_mass = None, i.e. the canonical mass metric "
                        "diag(1/inertances) the survival harness uses")
            ),
            note=note,
        ))

    # (A) one law at a time on the field's own motif.
    add_motif(UNIFORM_MOTIF_NAME, "uniform", "uniform",
              note="the reference arm: this rail must reproduce the field's own transport matrix")
    add_motif("motif-spacing-phi", "phi", "uniform",
              note="hypothesis (a): only the longitudinal station law changes")
    add_motif("motif-spacing-phi-down", "phi-down", "uniform")
    add_motif("motif-coupling-phi", "uniform", "phi",
              note="hypothesis (b): only the derived weights are graded")
    add_motif("motif-coupling-phi-down", "uniform", "phi-down")
    add_motif("motif-coupling-1.5x", "uniform", "1.5x")
    add_motif("motif-coupling-2.0x", "uniform", "2.0x")
    # (B) lattices of copies on the built-in motif.
    for law in INTER_COPY_LAWS:
        add_lattice(f"ring-{law}", "ring", law)
    for law in ("uniform", "phi-up", "matched-random"):
        add_lattice(f"grid-{law}", "grid", law)
    for law in ("uniform", "phi-up", "matched-random"):
        add_lattice(f"grid-crosslinks-{law}", "grid-crosslinks", law)
    add_lattice("ring-uniform-rungs", "ring", "uniform", rungs=True,
                note="the built-in motif's only two entries between a position and its partner "
                     "strand coordinate are the two circuit bridges that close the ring (pool 6's "
                     "last Yang port -> pool 0's first Yin port, and pool 0's last Yin port -> pool "
                     "6's first Yang port); this arm declares the same oriented strand pair at all "
                     "28 declared positions")
    add_lattice("ring-phi-up-rungs", "ring", "phi-up", rungs=True)
    add_lattice("ring-uniform-rungs-mass", "ring", "uniform", rungs=True, mass="core-shell")
    add_lattice("ring-phi-up-rungs-mass", "ring", "phi-up", rungs=True, mass="core-shell",
                note="the full hypothesis (graded inter-copy coupling + rungs) with the mass "
                     "channel that carries the survival gain in the established scaffold contrast")
    # (C) the bare motif with its two strands connected, in both declared rung laws and both
    # declared coupling laws: this is the rung effect on the helix itself, without any copies.
    for rung_arm, rung_coupling, rung_law in MOTIF_RUNG_ARMS:
        add_motif(
            rung_arm, "uniform", rung_coupling, rungs=True, rung_law=rung_law,
            note="the built-in motif's only two entries between a position and its partner strand "
                 "coordinate are the two circuit bridges that close the ring (pool 6's last Yang "
                 "port -> pool 0's first Yin port, and pool 0's last Yin port -> pool 6's first "
                 "Yang port); this arm sets a rung at all 28 declared positions instead, so the "
                 "strand pair is connected along the whole helix and not only where the ring closes",
        )
    # (D) the mass channel alone, as the single-channel leg of the attribution decomposition.
    add_motif("motif-shell-mass", "uniform", "uniform", mass="core-shell",
              note="the attribution mass-only leg: the field's own rail unchanged, with the "
                   "geometry harness's shell metric as the mass channel and no rungs")
    # (D2) the rung-law controls: the phi law is an unbounded one-sided ramp, so the same channel
    # is also declared as two other steep ramps, its own reversal, a centred steep law, a single
    # position and a multiset-matched shuffle of itself.
    for control_arm, control_coupling, control_law in MOTIF_RUNG_LAW_CONTROL_ARMS:
        add_motif(
            control_arm, "uniform", control_coupling, rungs=True, rung_law=control_law,
            note="the rung-law control: the same 28 declared positions and the same declared rung "
                 "channel total as the two primary rung arms, under a different declared rung "
                 f"shape ({rung_law_rule(control_law)})",
        )
    # (E) the nested-shell family: recursion depth x shell law, plus the unnormalized depth-1
    # reference-law anchor that reconstructs the cited nested-core-shell construction.
    for depth in NESTED_DEPTHS:
        for shell_law in SHELL_LAWS:
            add_nested(f"nested-d{depth}-{shell_law}", depth, shell_law)
    add_nested(
        NESTED_ANCHOR_NAME, 1, NESTED_REFERENCE_LAW, normalized=False,
        note="the continuity anchor: depth 1 under the canonical partition with the reference law "
             "is the geometry harness's own nested-core-shell construction, so this arm's measured "
             "figures must reproduce the cited ones",
    )
    # (E2) the same depth family under the anchor's own normalization: the reference law and the
    # unity law, both unnormalized, so a flat normalized depth axis can be attributed either to
    # depth itself or to the equal-total normalization.
    for raw_arm, raw_depth, raw_law in NESTED_RAW_ARMS:
        add_nested(
            raw_arm, raw_depth, raw_law, normalized=False,
            note="the depth-normalization control: the same declared depth and shell law as the "
                 "normalized nested family, declared without the equal-total normalization, i.e. "
                 "under the anchor's own conditions",
        )
    # (F) the interaction grid: the shell mass channel crossed with a declared rail weight, the
    # rail always the ring-plus-rungs pattern, so the rail's damage can be read as a function of
    # the declared rail weight rather than only at the single declared lattice budget.
    for grid_arm, grid_fraction, grid_mass in INTERACTION_ARMS:
        declarations.append(LatticeArrangement(
            name=grid_arm, kind="interaction", pattern=INTERACTION_PATTERN,
            inter_copy_law="uniform", rungs=grid_fraction > 0.0,
            rail_fraction=grid_fraction, mass=grid_mass, seed=seed,
            rule=(
                f"projected_transport = the built-in motif rail plus a declared ring-plus-rungs "
                f"lattice whose whole declared channel is {grid_fraction!r} times the geometry "
                f"harness's flat-ladder budget ({lattice_reference_weight()!r}); the declared "
                f"channel is split between the ring pool links and the 28 uniform-rung scales by "
                f"the same canonical weight rule the lattice rung arms use"
                + ("" if grid_fraction > 0.0 else
                   "; at declared rail fraction 0 no link and no rung is declared, so the rail is "
                   "the field's own rail unchanged (a zero declared scale is not a declaration)")
                + ("; projected_inv_mass = the geometry harness's core-shell shell metric "
                   "0.7**ring_distance(pool, 3), i.e. the mass channel is on"
                   if grid_mass == "core-shell"
                   else "; projected_inv_mass = None, i.e. the canonical mass metric "
                        "diag(1/inertances) and the mass channel is off")
            ),
            note="the interaction grid: the mass channel crossed with the declared rail weight",
        ))

    if scope == COMPACT_SCOPE:
        keep = {
            UNIFORM_MOTIF_NAME, "motif-spacing-phi", "motif-coupling-phi",
            RING_UNIFORM_NAME, "ring-phi-up", MATCHED_RANDOM_NAME,
            "ring-uniform-rungs", "ring-phi-up-rungs", "ring-phi-up-rungs-mass",
            "motif-default-rungs", "motif-default-rungs-phi", "motif-coupling-phi-rungs",
            "motif-coupling-phi-rungs-phi",
            "motif-default-rungs-2.0x", "motif-default-rungs-single",
            ATTRIBUTION_MASS_ONLY_NAME,
            f"nested-d1-{NESTED_DEPTH_AXIS_LAW}", f"nested-d{NESTED_LAW_AXIS_DEPTH}-{NESTED_DEPTH_AXIS_LAW}",
            f"nested-d{NESTED_LAW_AXIS_DEPTH}-phi", NESTED_ANCHOR_NAME,
            f"nested-d{NESTED_DEPTHS[-1]}-{NESTED_REFERENCE_LAW}-raw",
            f"nested-d{NESTED_DEPTHS[-1]}-uniform-raw",
            interaction_arm_name(0.0, "canonical"),
            interaction_arm_name(1.0, "canonical"),
            interaction_arm_name(0.0, "core-shell"),
            interaction_arm_name(1.0, "core-shell"),
        }
        declarations = [item for item in declarations if item.name in keep]
    elif scope != DEFAULT_SCOPE:
        raise ResonantNumericalError(f"unknown scope {scope!r}")
    return tuple(declarations)


def reference_arrangements() -> tuple[str, ...]:
    """The arrangements already measured by the geometry and survival harnesses."""
    return ("helix7", "nested-core-shell", "recursive-paired-loops")


# --------------------------------------------------------------------------
# construction
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class BuiltArrangement:
    """One built arrangement: the declared channel weights after normalization.

    ``link_weight`` and ``rung_weight`` are the declared channel weights in the
    canonical weight rule's own terms (the weight a rail entry of that declared
    scale carries at its declared port pair); ``rung_channel_l1`` in the rung
    report is the magnitude the writer actually puts in the rail, which is the
    same number only where the declared scale *is* the rail entry.
    """

    name: str
    kind: str
    links: tuple[tuple[int, int, float], ...]
    rung_scales: tuple[float, ...]
    normalization_factor: float
    declared_total_weight: float
    link_weight: float
    rung_weight: float
    rung_law: str | None = None
    normalized: bool = True


def build_arrangement(
    arrangement: LatticeArrangement, ports_per_pool: int = PORTS_PER_POOL
) -> BuiltArrangement:
    """Normalize one arrangement's own declared scales to its declared budgets."""
    parts = geometry.canonical_parts(ports_per_pool)
    ports = POOLS * int(ports_per_pool)
    if arrangement.kind == "motif":
        motif_weight = motif_reference_weight(ports_per_pool)
        if not arrangement.rungs:
            return BuiltArrangement(
                name=arrangement.name, kind="motif", links=(), rung_scales=(),
                normalization_factor=1.0, declared_total_weight=motif_weight,
                link_weight=0.0, rung_weight=0.0,
            )
        raw = rung_law_scales(arrangement.rung_law, ports_per_pool)
        total = float(sum(abs(scale) for scale in raw))
        if not math.isfinite(total) or total <= 0.0:
            raise ResonantNumericalError(f"arrangement {arrangement.name!r} declares no rung weight")
        # the motif rung channel is declared in the rail's own units: the writer writes the
        # declared scale itself, so the channel is normalized to the motif body's rail L1 here.
        factor = motif_weight / total
        rung_scales = tuple(float(scale) * factor for scale in raw)
        rung_weight = float(sum(abs(scale) for scale in rung_scales))
        return BuiltArrangement(
            name=arrangement.name, kind="motif", links=(), rung_scales=rung_scales,
            normalization_factor=float(factor),
            declared_total_weight=float(motif_weight + rung_weight),
            link_weight=0.0, rung_weight=rung_weight, rung_law=arrangement.rung_law,
        )
    if arrangement.kind == "nested":
        raw = nested_link_scales(arrangement.depth, ports_per_pool)
        entries = [
            (int(source), int(destination), float(scale),
             geometry.realized_pair_strength((int(source), int(destination), 1.0), parts))
            for source, destination, scale in raw
        ]
        total = float(sum(scale * strength for _s, _d, scale, strength in entries))
        if not math.isfinite(total) or total <= 0.0:
            raise ResonantNumericalError(f"arrangement {arrangement.name!r} declares no weight")
        factor = 1.0 if not arrangement.normalized else lattice_reference_weight(ports_per_pool) / total
        links = tuple((source, destination, scale * factor) for source, destination, scale, _u in entries)
        link_weight = float(sum(scale * factor * strength for _s, _d, scale, strength in entries))
        return BuiltArrangement(
            name=arrangement.name, kind="nested", links=links, rung_scales=(),
            normalization_factor=float(factor), declared_total_weight=float(link_weight),
            link_weight=link_weight, rung_weight=0.0, normalized=bool(arrangement.normalized),
        )
    if arrangement.rung_law != "uniform":
        raise ResonantNumericalError(
            f"lattice arrangement {arrangement.name!r} declares rung law {arrangement.rung_law!r}; "
            "the lattice rung arms declare the uniform RUNG_SCALE set only"
        )
    # the interaction grid declares only a fraction of the geometry budget, and at declared
    # fraction 0 it declares nothing at all: a zero declared scale is not a declaration, and the
    # rung writer would otherwise clear the two canonical bridges for no declared channel.
    budget_fraction = (
        1.0 if arrangement.rail_fraction is None else float(arrangement.rail_fraction)
    )
    declares_channels = budget_fraction > 0.0
    edges = pattern_edges(arrangement.pattern)
    scales = inter_copy_scales(arrangement.pattern, arrangement.inter_copy_law, seed=arrangement.seed)
    entries: list[dict[str, Any]] = []
    for (source, destination, _index, family), scale in zip(edges, scales):
        entries.append({
            "kind": "pool-link", "family": family, "source": int(source),
            "destination": int(destination), "scale": float(scale),
            "unit_strength": geometry.realized_pair_strength((int(source), int(destination), 1.0), parts),
        })
    ports = POOLS * int(ports_per_pool)
    if arrangement.rungs and declares_channels:
        for position in range(ports):
            entries.append({
                "kind": "rung", "family": "strand-pair", "source": int(position),
                "destination": int(ports + position), "scale": float(RUNG_SCALE),
                "unit_strength": geometry._edge_weight(parts, position, ports + position, 1.0),
            })
    if not declares_channels:
        return BuiltArrangement(
            name=arrangement.name, kind=arrangement.kind, links=(), rung_scales=(),
            normalization_factor=0.0, declared_total_weight=0.0, link_weight=0.0, rung_weight=0.0,
        )
    total = float(sum(entry["scale"] * entry["unit_strength"] for entry in entries))
    if not math.isfinite(total) or total <= 0.0:
        raise ResonantNumericalError(f"arrangement {arrangement.name!r} declares no weight")
    factor = budget_fraction * lattice_reference_weight(ports_per_pool) / total
    links = tuple(
        (entry["source"], entry["destination"], entry["scale"] * factor)
        for entry in entries if entry["kind"] == "pool-link"
    )
    rung_scales = tuple(entry["scale"] * factor for entry in entries if entry["kind"] == "rung")
    link_weight = float(sum(
        entry["scale"] * entry["unit_strength"] * factor
        for entry in entries if entry["kind"] == "pool-link"
    ))
    rung_weight = float(sum(
        entry["scale"] * entry["unit_strength"] * factor
        for entry in entries if entry["kind"] == "rung"
    ))
    return BuiltArrangement(
        name=arrangement.name, kind=arrangement.kind, links=links, rung_scales=rung_scales,
        normalization_factor=float(factor), declared_total_weight=float(link_weight + rung_weight),
        link_weight=link_weight, rung_weight=rung_weight,
    )


def set_rungs(
    rail: np.ndarray, rung_scales: Sequence[float], ports_per_pool: int = PORTS_PER_POOL
) -> tuple[np.ndarray, dict[str, Any]]:
    """Set one declared strand-to-strand rung at every declared position.

    The rung is *set*, not accumulated: the entries between a declared position's two
    strand coordinates are cleared first and the declared oriented rung is written,
    so a declared position carrying a built-in endpoint bridge is re-declared by its
    rung instead of being double-counted.  The orientation convention is
    ``Yang coordinate -> Yin coordinate`` with the antisymmetric reverse entry.
    """
    output = np.asarray(rail, dtype=np.float64).copy()
    ports = POOLS * int(ports_per_pool)
    if len(rung_scales) != ports:
        raise ResonantNumericalError("one rung scale is required per declared position")
    replaced: list[list[int]] = []
    replaced_magnitudes: list[float] = []
    for position in range(ports):
        partner = ports + position
        if output[position, partner] != 0.0 or output[partner, position] != 0.0:
            replaced.append([int(position), int(partner)])
            replaced_magnitudes.append(float(abs(output[partner, position])))
        output[position, partner] = 0.0
        output[partner, position] = 0.0
    for position in range(ports):
        partner = ports + position
        weight = float(rung_scales[position])
        output[partner, position] += weight
        output[position, partner] -= weight
    if not np.array_equal(output, -output.T):
        raise ResonantNumericalError("the declared rungs broke rail antisymmetry")
    scales = np.asarray(rung_scales, dtype=np.float64)
    # measured back out of the rail the writer produced: a swapped or dropped orientation
    # convention would show up here and nowhere else.
    written = np.asarray([output[ports + position, position] for position in range(ports)])
    orientation_deviation = float(np.abs(written - scales).max()) if ports else 0.0
    return output, {
        "rungs_set": int(ports),
        "rung_orientation": "Yang coordinate -> Yin coordinate, antisymmetric reverse entry",
        "rung_weight": float(rung_scales[0]),
        "rung_canonical_entries": [int(position) for position in range(ports)],
        "rung_channel_l1": float(np.abs(scales).sum()),
        "rung_scale_min": float(scales.min()),
        "rung_scale_max": float(scales.max()),
        "orientation_max_absolute_deviation": orientation_deviation,
        "canonical_entries_replaced": replaced,
        "replaced_entry_magnitudes": replaced_magnitudes,
        "replaced_entry_count": len(replaced),
        "rail_nonzero_entries": int(np.count_nonzero(output)),
        "definition": (
            "one oriented rung per declared position; the rail entry written is the declared "
            "rung scale itself, in rail units, not the canonical weight rule's value at that "
            "port pair; rung_weight is the declared position-0 scale, rung_channel_l1 the whole "
            "declared set's L1"
        ),
    }


def rail_l1_identity(
    base_rail_l1: float, *, link_weight: float = 0.0, rung_channel_l1: float = 0.0,
    cleared_entry_l1: float = 0.0,
) -> float:
    """The rail L1 an arm's declared channels must realize, in matrix L1 units.

    The rail is antisymmetric, so one declared entry contributes its magnitude to
    *two* matrix entries; every declared channel total here is one-sided and is
    therefore doubled.  Each term is a declared scale or a measured entry, so the
    identity is a check on the construction, not a restatement of it.
    """
    return float(
        float(base_rail_l1) - 2.0 * float(cleared_entry_l1)
        + 2.0 * (float(link_weight) + float(rung_channel_l1))
    )


def cleared_entry_l1(rail_before_rungs: np.ndarray, rung_report: Mapping[str, Any]) -> float:
    """The one-sided magnitude of the canonical strand-pair entries the rungs replace."""
    rail = np.asarray(rail_before_rungs, dtype=np.float64)
    return float(sum(
        abs(rail[int(position), int(partner)])
        for position, partner in rung_report["canonical_entries_replaced"]
    ))


def arrangement_profile(
    arrangement: LatticeArrangement, ports_per_pool: int = PORTS_PER_POOL
) -> tuple[ResonantProfile, BuiltArrangement, dict[str, Any]]:
    """Build one declared arrangement's profile through the canonical hooks only."""
    built = build_arrangement(arrangement, ports_per_pool)
    parts = geometry.canonical_parts(ports_per_pool)
    ports = POOLS * int(ports_per_pool)
    report: dict[str, Any] = {
        "declared_motif_channel_weight": (
            motif_reference_weight(ports_per_pool) if arrangement.kind == "motif" else None
        ),
        "declared_rung_channel_weight": built.rung_weight if built.rung_scales else 0.0,
        "declared_link_channel_weight": built.link_weight,
    }
    if arrangement.kind == "motif":
        rail, motif_report = motif_rail(
            ports_per_pool, spacing=arrangement.spacing, coupling=arrangement.coupling
        )
        report["motif"] = motif_report
        report["normalization_factor"] = motif_report["normalization_factor"]
        motif_l1 = float(np.abs(rail).sum())
        report["motif_rail_l1"] = motif_l1
        if arrangement.rungs and built.rung_scales:
            rung_rail, rung_report = set_rungs(rail, built.rung_scales, ports_per_pool)
            cleared = cleared_entry_l1(rail, rung_report)
            rail = rung_rail
            report["rung_report"] = rung_report
            report["cleared_entry_l1"] = cleared
            report["declared_rail_l1"] = rail_l1_identity(
                motif_l1, rung_channel_l1=rung_report["rung_channel_l1"],
                cleared_entry_l1=cleared,
            )
        else:
            report["declared_rail_l1"] = motif_l1
    elif arrangement.kind == "nested":
        rail = geometry.rail_from_pool_links(built.links, ports_per_pool=ports_per_pool)
        base = geometry.rail_from_pool_links((), ports_per_pool=ports_per_pool)
        base_l1 = float(np.abs(base).sum())
        # an independent re-derivation: the same declared links written onto the same base by this
        # runner's own link writer, so the two constructions must agree entry by entry.
        rebuilt = np.array(base, dtype=np.float64, copy=True)
        for source, destination, scale in built.links:
            for link_source, link_destination, link_scale in geometry.pool_link_port_pairs(
                (source, destination, scale), parts
            ):
                weight = geometry._edge_weight(parts, link_source, link_destination, link_scale)
                rebuilt[link_destination, link_source] += weight
                rebuilt[link_source, link_destination] -= weight
        report.update({
            "base_rail_l1": base_l1,
            "link_channel_raw_l1": float(sum(abs(scale) for _s, _d, scale in nested_link_scales(
                arrangement.depth, ports_per_pool
            ))),
            "depth": int(arrangement.depth),
            "shell_law": arrangement.shell_law,
            "normalized": bool(arrangement.normalized),
            "independent_reconstruction_max_absolute_difference": float(
                np.abs(rail - rebuilt).max()
            ),
            "declared_rail_l1": rail_l1_identity(base_l1, link_weight=built.link_weight),
        })
    else:
        rail = field_rail(ports_per_pool).copy()
        for source, destination, scale in built.links:
            for link_source, link_destination, link_scale in geometry.pool_link_port_pairs(
                (source, destination, scale), parts
            ):
                weight = geometry._edge_weight(parts, link_source, link_destination, link_scale)
                rail[link_destination, link_source] += weight
                rail[link_source, link_destination] -= weight
        report.update({
            "motif_rail_l1": float(np.abs(field_rail(ports_per_pool)).sum()),
            "inter_copy_fraction_of_declared_total": (
                built.declared_total_weight / (built.declared_total_weight + motif_reference_weight(ports_per_pool))
            ),
            "rail_fraction": (
                None if arrangement.rail_fraction is None else float(arrangement.rail_fraction)
            ),
            "declared_budget_fraction": (
                1.0 if arrangement.rail_fraction is None else float(arrangement.rail_fraction)
            ),
        })
        if arrangement.rungs and built.rung_scales:
            rung_rail, rung_report = set_rungs(rail, built.rung_scales, ports_per_pool)
            cleared = cleared_entry_l1(rail, rung_report)
            rail = rung_rail
            report["rung_report"] = rung_report
            report["cleared_entry_l1"] = cleared
            report["declared_rail_l1"] = rail_l1_identity(
                report["motif_rail_l1"], link_weight=built.link_weight,
                rung_channel_l1=rung_report["rung_channel_l1"], cleared_entry_l1=cleared,
            )
        else:
            report["declared_rail_l1"] = rail_l1_identity(
                report["motif_rail_l1"], link_weight=built.link_weight
            )
    if arrangement.mass == "core-shell":
        inverse_mass = geometry.core_shell_inverse_mass(ports_per_pool)
        source = "projected_inv_mass: geometry.core_shell_inverse_mass(), the shell metric"
    elif arrangement.mass == "nested-shell":
        inverse_mass = nested_shell_inverse_mass(
            arrangement.depth, arrangement.shell_law, ports_per_pool
        )
        source = (
            f"projected_inv_mass: nested shell metric, depth {int(arrangement.depth)}, "
            f"law {arrangement.shell_law!r}"
        )
    else:
        inverse_mass = None
        source = "canonical diag(1/inertances); projected_inv_mass is None"
    values = (
        np.asarray(ResonantProfile(ports_per_pool=int(ports_per_pool)).inertances, dtype=np.float64)
        if inverse_mass is None else np.asarray(inverse_mass, dtype=np.float64)
    )
    if inverse_mass is None:
        values = 1.0 / values
    report["mass_metric_audit"] = {
        "source": source,
        "per_port_count": int(values.size),
        "min": float(values.min()), "max": float(values.max()),
        "l1": float(np.abs(values).sum()),
    }
    report["measured_rail_l1"] = float(np.abs(rail).sum())
    report["rail_l1_absolute_difference"] = float(
        abs(report["measured_rail_l1"] - report["declared_rail_l1"])
    )
    profile = ResonantProfile(
        ports_per_pool=int(ports_per_pool), topology="meaningful-helix",
        projected_transport=rail, projected_inv_mass=inverse_mass,
    )
    return profile, built, report


def profile_for_name(
    name: str, scope: str = DEFAULT_SCOPE, *, seed: int = SEED, ports_per_pool: int = PORTS_PER_POOL
) -> tuple[ResonantProfile, dict[str, Any]]:
    """The profile of a declared arrangement, or of one of the cited reference arrangements."""
    if name in reference_arrangements():
        declared = geometry.arrangement_named(name)
        return geometry.build_profile(declared, ports_per_pool=ports_per_pool), {
            "builder": "geometry.build_profile(geometry.arrangement_named(name))",
            "declared_geometry_links": len(declared.pool_links),
            "declared_total_weight": None,
        }
    arrangement = arrangement_lookup(name, scope, seed=seed)
    profile, built, report = arrangement_profile(arrangement, ports_per_pool)
    return profile, {
        "builder": "run_fractal_lattice_exploration.arrangement_profile(arrangement)",
        "declared_inter_copy_links": len(built.links),
        "declared_rungs": len(built.rung_scales),
        "declared_total_coupling_weight": built.declared_total_weight,
        "declared_link_weight": built.link_weight,
        "declared_rung_weight": built.rung_weight,
        "normalization_factor": built.normalization_factor,
        "report": report,
    }


def arrangement_lookup(name: str, scope: str = DEFAULT_SCOPE, *, seed: int = SEED) -> LatticeArrangement:
    for arrangement in arrangement_inventory(scope, seed=seed):
        if arrangement.name == name:
            return arrangement
    raise ResonantNumericalError(f"no declared arrangement is named {name!r}")


# --------------------------------------------------------------------------
# spectrum measurement for the spacing hypothesis
# --------------------------------------------------------------------------
def _spread(values: Sequence[float | None]) -> float | None:
    finite = [float(value) for value in values
              if value is not None and math.isfinite(float(value))]
    if len(finite) < 2:
        return None
    return float(np.std(np.asarray(finite, dtype=np.float64)))


def _log_spread(values: Sequence[float | None]) -> float | None:
    positive = [math.log(float(value)) for value in values
                if value is not None and float(value) > 0.0 and math.isfinite(float(value))]
    return _spread(positive)


def log_periodic_order(levels: Sequence[float], ratio: float) -> float:
    """Magnitude of the mean of ``exp(2*pi*i*log(level)/log(ratio))`` over the levels.

    One when the levels form an exact geometric ladder of the tested ratio; near
    ``1/sqrt(n)`` when the levels carry no such scaling.
    """
    values = np.asarray([float(value) for value in levels], dtype=np.float64)
    positive = values[values > 0.0]
    if positive.size == 0:
        raise ResonantNumericalError("the log-periodic order parameter needs positive levels")
    phase = 2.0 * math.pi * np.log(positive) / math.log(float(ratio))
    return float(abs(np.exp(1j * phase).mean()))


def synthetic_order_controls() -> dict[str, Any]:
    """Positive control: the order parameter on constructed exact ladders of a declared ratio."""
    anchor = 0.418
    ladders = {
        "phi-ladder": np.asarray([anchor * PHI ** k for k in range(SYNTHETIC_LADDER_LEVELS)]),
        "2.0-ladder": np.asarray([anchor * 2.0 ** k for k in range(SYNTHETIC_LADDER_LEVELS)]),
        "arithmetic": np.asarray([anchor + 0.01 * k for k in range(SYNTHETIC_LADDER_LEVELS)]),
    }
    return {
        "definition": (
            "the log-periodic order parameter measured on constructed level sets: an exact "
            "geometric ladder of one ratio, of another ratio, and an arithmetic set"
        ),
        "levels_per_ladder": int(SYNTHETIC_LADDER_LEVELS),
        "order_by_ladder": {
            name: {label: log_periodic_order(levels, ratio) for label, ratio in ORDER_RATIOS}
            for name, levels in ladders.items()
        },
    }


def spectrum_bands(profile: ResonantProfile) -> dict[str, Any]:
    """Gap statistics, participation/decay distributions and the declared self-similarity test."""
    generator = geometry.linear_generator(profile)
    base = geometry._generator_spectrum(generator)
    eigenvalues = base["eigenvalues"]
    ipr = np.asarray(base["ipr"], dtype=np.float64)
    frequency = np.abs(eigenvalues.imag)
    decay = np.abs(eigenvalues.real)
    complex_modes = np.asarray(base["complex_modes"], dtype=bool)
    positive = complex_modes & (frequency > 0.0)
    levels = np.unique(np.round(frequency[positive], LEVEL_DEDUPLICATION_DECIMALS))
    if levels.size < 4:
        raise ResonantNumericalError("the spectrum has too few positive levels to band")
    gaps = np.diff(levels)
    ratios = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    log_ratios = np.log(levels[1:] / levels[:-1])
    mode_frequency = frequency[positive]
    mode_ipr = ipr[positive]
    mode_decay = decay[positive]

    banding: dict[str, Any] = {}
    for label, ratio in BAND_RATIOS:
        anchors = np.floor(np.log(levels / levels[0]) / math.log(float(ratio)) + 1e-12).astype(np.int64)
        mode_band = np.floor(
            np.log(mode_frequency / levels[0]) / math.log(float(ratio)) + 1e-12
        ).astype(np.int64)
        gap_band = np.floor(
            np.log(levels[:-1] / levels[0]) / math.log(float(ratio)) + 1e-12
        ).astype(np.int64)
        rows: list[dict[str, Any]] = []
        for index in sorted(set(int(value) for value in anchors)):
            level_mask = anchors == index
            mode_mask = mode_band == index
            gap_mask = gap_band == index
            band_gaps = gaps[gap_mask]
            band_ratios = ratios[gap_mask[: ratios.size]] if ratios.size else np.zeros(0)
            band_modes = mode_ipr[mode_mask]
            band_decays = mode_decay[mode_mask]
            rows.append({
                "band": int(index),
                "level_count": int(level_mask.sum()),
                "mode_count": int(mode_mask.sum()),
                "frequency_min": float(levels[level_mask].min()),
                "frequency_max": float(levels[level_mask].max()),
                # a band can hold levels but no modes once a declared law spreads the spectrum far
                # enough (the 2.0**j rung ramp does); an empty band reports no median rather than a
                # nan, because the receipt forbids non-finite numbers
                "median_participation_ratio": (
                    None if band_modes.size == 0 else float(np.median(band_modes))
                ),
                "median_decay_rate": (
                    None if band_decays.size == 0 else float(np.median(band_decays))
                ),
                "gap_count": int(band_gaps.size),
                "median_gap": float(np.median(band_gaps)) if band_gaps.size else None,
                "mean_gap_ratio": float(band_ratios.mean()) if band_ratios.size else None,
                "median_log_level_ratio": (
                    float(np.median(log_ratios[gap_mask])) if band_gaps.size else None
                ),
            })
        spreads = {
            "participation": _log_spread([row["median_participation_ratio"] for row in rows]),
            "decay": _log_spread([row["median_decay_rate"] for row in rows]),
            "gap_ratio": _spread([row["mean_gap_ratio"] for row in rows]),
            "log_level_ratio": _spread([row["median_log_level_ratio"] for row in rows]),
        }
        available = [value for value in spreads.values() if value is not None]
        banding[label] = {
            "banding_definition": (
                f"band k covers levels in [level_min*{float(ratio)!r}**k, "
                f"level_min*{float(ratio)!r}**(k+1)); mode and gap attributes are assigned by the "
                f"same rule"
            ),
            "ratio": float(ratio),
            "band_count": len(rows),
            "bands": rows,
            "spreads": spreads,
            "self_similarity_index": (float(np.mean(available)) if available else None),
        }

    orders = {label: log_periodic_order(levels, ratio) for label, ratio in ORDER_RATIOS}
    other = max(orders[label] for label in ORDER_RATIO_OTHERS)
    return {
        "definition": {
            "generator": "reused geometry.linear_generator: beta=0 _WaveOperator, one canonical "
                         "flow(energy_gradient(e_i)) column per state coordinate",
            "mode_decay_rate": "|Re(lambda)| of the frozen linear generator's eigenvalue",
            "mode_participation_ratio": "the geometry harness's own generator spectrum IPR",
            "levels": f"positive |Im(lambda)| of complex modes, deduplicated at "
                      f"{LEVEL_DEDUPLICATION_DECIMALS} decimals",
            "gaps": "consecutive differences of the deduplicated levels",
            "gap_ratio": "min(s_n, s_n+1)/max(s_n, s_n+1) of consecutive gaps",
            "self_similarity_index": "mean of the declared band spreads (participation, decay, gap "
                                     "ratio, log level ratio): small means the distribution has the "
                                     "same shape in every band",
            "log_periodic_order": "|mean exp(2*pi*i*log(level)/log(ratio))| over the levels: 1 for "
                                  "an exact geometric ladder of that ratio, near 1/sqrt(n) otherwise",
            "finitude": "a finite 112-mode truncation approximates a scale-invariant spectrum; it "
                        "does not realize a singular-continuous spectrum",
        },
        "level_count": int(levels.size),
        "level_range": [float(levels.min()), float(levels.max())],
        "gap_statistics": {
            "count": int(gaps.size),
            "min": float(gaps.min()), "median": float(np.median(gaps)),
            "mean": float(gaps.mean()), "max": float(gaps.max()), "std": float(gaps.std()),
            "gap_ratio_mean": float(ratios.mean()) if ratios.size else None,
            "gap_ratio_median": float(np.median(ratios)) if ratios.size else None,
            "gap_ratio_std": float(ratios.std()) if ratios.size else None,
            "log_level_ratio_median": float(np.median(log_ratios)),
            "log_level_ratio_std": float(np.std(log_ratios)),
        },
        "mode_distributions": {
            "participation_ratio_quantiles": [float(v) for v in np.quantile(ipr, QUANTILES)],
            "participation_ratio_mean": float(ipr.mean()),
            "participation_ratio_std": float(ipr.std()),
            "decay_rate_quantiles": [float(v) for v in np.quantile(decay, QUANTILES)],
            "decay_rate_mean": float(decay.mean()),
            "decay_rate_std": float(decay.std()),
            "decay_rate_range": [float(decay.min()), float(decay.max())],
        },
        "banding": banding,
        "log_periodic_order_by_ratio": orders,
        "phi_ratio_excess": float(orders["phi"] - other),
    }


# --------------------------------------------------------------------------
# measurement of one arrangement
# --------------------------------------------------------------------------
def geometry_block(profile: ResonantProfile, *, include_access: bool = True) -> dict[str, Any]:
    """The geometry harness's own instruments, on the declared profile."""
    block = {
        "spectrum": geometry.spectrum_metrics(profile),
        "bands": spectrum_bands(profile),
        "retention": geometry.retention_metrics(
            profile, pools=geometry.DEFAULT_IMPULSE_POOLS,
            work=geometry.DEFAULT_IMPULSE_WORK, ticks=geometry.DEFAULT_RETENTION_TICKS,
        ),
        "hooks": geometry.hook_effect(profile),
    }
    if include_access:
        block["access"] = geometry.access_metrics(profile)
    return block


def survival_block(
    profile: ResonantProfile, config: durability.DurabilityConfig, counts: Sequence[int]
) -> dict[str, Any]:
    """The durability harness's declared arms through the survival harness's own record builder."""
    arms = {arm.name: arm for arm in durability.arm_declarations(config)}
    captures = durability.capture_items(config, profile)
    overlap = durability.overlap_matrix(captures)
    off_diagonal = [
        float(value) for left, row in enumerate(overlap)
        for right, value in enumerate(row) if left != right
    ]
    rows: dict[str, Any] = {}
    for name in ("restart-and-activity", *(f"restart-and-activity-k{int(count)}" for count in counts)):
        if name not in arms:
            raise ResonantNumericalError(f"the durability harness declares no arm {name!r}")
        record = survival.compact_arm_record(
            durability.run_arm(config, profile, captures, arms[name]), config.control_margin
        )
        rows[name] = {
            "declared_written_items": record["declared_written_items"],
            "recovery_fraction": record["recovery_fraction"],
            "per_item_recovery_fraction": record["per_item_recovery_fraction"],
            "max_off_diagonal_deposit_share": record["max_off_diagonal_deposit_share"],
            "unwritten_direction_energy_fraction_total": record["unwritten_direction_energy_fraction_total"],
            "control_item": record["control_item"],
            "control_share": record["control_share"],
            "control_margin": record["control_margin"],
            "distinguishable_from_control": record["distinguishable_from_control"],
            "activity_ticks": record["activity_ticks"],
            "read_state_sha256": record["read_state_sha256"],
        }
    return {
        "declared": {
            "config": config.as_dict(),
            "arm_names": list(rows),
            "recovery_definition": "reused survival.compact_arm_record: (c_read . u)^2 / |c_in_arm|^2, "
                                   "the minimum over the arm's items",
        },
        "max_off_diagonal_squared_cosine": max(off_diagonal, default=0.0),
        "orthogonality_allowance": float(durability.ORTHOGONALITY_ALLOWANCE),
        "arms": rows,
    }


def placement_block(profile: ResonantProfile, config: placement.PlacementConfig) -> dict[str, Any]:
    """The placement harness's own placement measurement, with its retention renamed."""
    record = placement._measure(profile, config)
    record["placement_retention"] = record.pop("retention", None)
    return record


def mass_metric_diagonal(profile: ResonantProfile) -> np.ndarray:
    """The built profile's mass metric diagonal, from whichever declared source supplies it."""
    inverse_mass = profile.projected_inv_mass
    if inverse_mass is None:
        return 1.0 / np.asarray(profile.inertances, dtype=np.float64)
    raw = np.asarray(inverse_mass, dtype=np.float64)
    return np.diag(raw) if raw.ndim == 2 else raw


def rail_cross_pool_l1(profile: ResonantProfile) -> float:
    """The rail's cross-pool strength: the measured coupling budget an arrangement carries."""
    rail = np.asarray(profile.transport_matrix, dtype=np.float64)
    dimension = rail.shape[0]
    ports = dimension // 2
    pool = (np.arange(dimension) % ports) // int(profile.ports_per_pool)
    cross = pool[:, None] != pool[None, :]
    return float(np.abs(rail[cross]).sum())


def measure_arrangement(name: str, config: "LatticeConfig") -> dict[str, Any]:
    """Construct one arrangement twice through the declared hooks and measure it."""
    started = time.perf_counter()
    profile, construction = profile_for_name(
        name, config.scope, seed=config.seed, ports_per_pool=config.ports_per_pool
    )
    rail = np.asarray(profile.transport_matrix, dtype=np.float64)
    arrangement = None if name in reference_arrangements() else arrangement_lookup(
        name, config.scope, seed=config.seed
    )
    field_residual = float(np.abs(rail - field_rail(config.ports_per_pool)).max())
    anchor_difference = None
    if name == NESTED_ANCHOR_NAME:
        cited = geometry.build_profile(geometry.arrangement_named(NESTED_NAME), ports_per_pool=config.ports_per_pool)
        anchor_difference = {
            "cited_arrangement": NESTED_NAME,
            "rail_max_absolute_difference": float(np.abs(
                rail - np.asarray(cited.transport_matrix, dtype=np.float64)
            ).max()),
            "inverse_mass_identical": bool(np.array_equal(
                np.asarray(profile.projected_inv_mass, dtype=np.float64),
                np.asarray(cited.projected_inv_mass, dtype=np.float64),
            )),
        }
    record: dict[str, Any] = {
        "construction": {
            "name": name,
            "family": "reference" if arrangement is None else arrangement.kind,
            "spacing_law": None if arrangement is None else arrangement.spacing,
            "coupling_law": None if arrangement is None else arrangement.coupling,
            "pattern": None if arrangement is None else arrangement.pattern,
            "inter_copy_law": None if arrangement is None else arrangement.inter_copy_law,
            "rungs": None if arrangement is None else arrangement.rungs,
            "rung_law": None if arrangement is None else arrangement.rung_law,
            "rail_fraction": (
                None if arrangement is None or arrangement.rail_fraction is None
                else float(arrangement.rail_fraction)
            ),
            "mass_channel": None if arrangement is None else arrangement.mass,
            "nesting_depth": None if arrangement is None else int(arrangement.depth),
            "shell_law": None if arrangement is None else arrangement.shell_law,
            "normalized": None if arrangement is None else bool(arrangement.normalized),
            "declared_rule": None if arrangement is None else arrangement.rule,
            "note": "" if arrangement is None else arrangement.note,
            "builder": construction["builder"],
            "declared_total_coupling_weight": construction.get("declared_total_coupling_weight"),
            "declared_link_weight": construction.get("declared_link_weight"),
            "declared_rung_weight": construction.get("declared_rung_weight"),
            "normalization_factor": construction.get("normalization_factor"),
            "ports_per_pool": int(profile.ports_per_pool),
            "pools": int(profile.pools),
            "port_count": int(profile.port_count),
            "state_dimension": int(4 * profile.port_count),
            "rail_sha256": _array_digest(rail),
            "rail_l1": float(np.abs(rail).sum()),
            "rail_cross_pool_strength_l1": rail_cross_pool_l1(profile),
            "rail_difference_from_field_rail": field_residual,
            "mass_metric_diagonal_sha256": _array_digest(mass_metric_diagonal(profile)),
            "construction_report": construction.get("report", {}),
            "anchor_comparison": anchor_difference,
        },
        "geometry": geometry_block(profile, include_access=config.include_access),
        "survival": survival_block(profile, config.durability_config(), config.survival_counts),
    }
    record.update(placement_block(profile, config.placement_config()))

    second, _construction = profile_for_name(
        name, config.scope, seed=config.seed, ports_per_pool=config.ports_per_pool
    )
    record["determinism"] = {
        "rail_identical": bool(np.array_equal(
            rail, np.asarray(second.transport_matrix, dtype=np.float64)
        )),
        "generator_identical": bool(
            _array_digest(geometry.linear_generator(profile))
            == _array_digest(geometry.linear_generator(second))
        ),
        "profile_sha256": canonical_digest(second.as_dict()),
        "profile_sha256_identical": canonical_digest(second.as_dict()) == canonical_digest(profile.as_dict()),
    }
    record["determinism"]["deterministic"] = all(
        value for key, value in record["determinism"].items() if key != "profile_sha256"
    )
    record["elapsed_seconds"] = time.perf_counter() - started
    return record


# --------------------------------------------------------------------------
# declared configuration
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class LatticeConfig:
    """Declared measurement settings for this runner."""

    scope: str = DEFAULT_SCOPE
    seed: int = SEED
    ports_per_pool: int = PORTS_PER_POOL
    survival_counts: tuple[int, ...] = (2, 4, 8)
    include_access: bool = True
    selection_depth: int = placement.DEFAULT_SELECTION_DEPTH
    top_placements: int = TOP_PLACEMENTS_DECLARED
    retention_ticks: int = geometry.DEFAULT_RETENTION_TICKS
    retention_work: float = geometry.DEFAULT_IMPULSE_WORK

    def arrangements(self) -> tuple[LatticeArrangement, ...]:
        return arrangement_inventory(self.scope, seed=self.seed)

    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.arrangements())

    def durability_config(self) -> durability.DurabilityConfig:
        return durability.DurabilityConfig(multi_item_counts=self.survival_counts)

    def placement_config(self) -> placement.PlacementConfig:
        return placement.PlacementConfig(
            ports_per_pool=self.ports_per_pool, depth=self.selection_depth,
            top=self.top_placements, seed=self.seed, retention_ticks=self.retention_ticks,
            retention_work=self.retention_work, include_retention=True,
        )

    @classmethod
    def compact(cls) -> "LatticeConfig":
        return cls(scope=COMPACT_SCOPE)


# --------------------------------------------------------------------------
# comparisons: basis, margin checks, firing and silenced controls, continuity
# --------------------------------------------------------------------------
SPACING_PHI_NAMES = ("motif-spacing-phi", "motif-spacing-phi-down")
MOTIF_COUPLING_PHI_NAMES = ("motif-coupling-phi", "motif-coupling-phi-down")
# the golden-ratio inter-copy laws: the ratio phi and its reciprocal; the other geometric ratios
# (1.5, 2.0) and the Fibonacci integer ladder are declared arms of their own.
INTER_COPY_PHI_NAMES = ("ring-phi-up", "ring-phi-down", "grid-phi-up", "grid-crosslinks-phi-up")


def _best_by(per: Mapping[str, Any], names: Sequence[str]) -> str | None:
    """The arm of ``names`` with the largest measured survival k4 recovery."""
    present = tuple(name for name in names if name in per)
    if not present:
        return None
    return max(present, key=lambda name: per[name]["survival_recovery"]["k4"])


def comparison_basis(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The measured scalars every declared comparison is evaluated on."""
    per_arrangement: dict[str, Any] = {}
    for record in records:
        name = record["construction"]["name"]
        arms = record["survival"]["arms"]
        bands = record["geometry"]["bands"]["banding"]
        construction = record["construction"]
        report = construction.get("construction_report") or {}
        rung_report = report.get("rung_report") or {}
        mass_audit = report.get("mass_metric_audit") or {}
        per_arrangement[name] = {
            "survival_recovery": {
                "headline": float(arms["restart-and-activity"]["recovery_fraction"]),
                "k2": float(arms["restart-and-activity-k2"]["recovery_fraction"]),
                "k4": float(arms["restart-and-activity-k4"]["recovery_fraction"]),
                "k8": float(arms["restart-and-activity-k8"]["recovery_fraction"]),
            },
            "ipr_median": float(record["geometry"]["spectrum"]["ipr_median"]),
            "access_coverage_score": (
                float(record["geometry"]["access"]["coverage_score"])
                if "access" in record["geometry"] else None
            ),
            "self_similarity_index": {
                label: bands[label]["self_similarity_index"] for label, _ratio in BAND_RATIOS
            },
            "phi_log_periodic_order": float(
                record["geometry"]["bands"]["log_periodic_order_by_ratio"]["phi"]
            ),
            "phi_ratio_excess": float(record["geometry"]["bands"]["phi_ratio_excess"]),
            "placement_write_read_spearman": float(
                record["pairs"]["write_read_rank_correlation"]["port_spearman"]
            ),
            "top7_drive_ports": [
                int(port) for port in placement._top_set(record, "drive", TOP_PLACEMENTS_DECLARED)
            ],
            "declared_total_coupling_weight": construction["declared_total_coupling_weight"],
            "declared_link_channel_weight": construction["declared_link_weight"],
            "declared_rung_channel_weight": construction["declared_rung_weight"],
            "declared_channel_total_weight": float(
                (construction["declared_link_weight"] or 0.0)
                + (construction["declared_rung_weight"] or 0.0)
            ),
            "motif_channel_rail_l1": report.get("motif_rail_l1"),
            "rung_channel_l1_one_sided": rung_report.get("rung_channel_l1"),
            "rung_scale_min": rung_report.get("rung_scale_min"),
            "rung_scale_max": rung_report.get("rung_scale_max"),
            "rung_orientation_max_absolute_deviation": rung_report.get(
                "orientation_max_absolute_deviation"
            ),
            "rung_canonical_entries_replaced": rung_report.get("canonical_entries_replaced"),
            "rail_l1_identity_absolute_difference": report.get("rail_l1_absolute_difference"),
            "mass_metric_min": mass_audit.get("min"),
            "mass_metric_max": mass_audit.get("max"),
            "mass_metric_l1": mass_audit.get("l1"),
            "mass_metric_diagonal_sha256": construction["mass_metric_diagonal_sha256"],
            "rail_cross_pool_strength_l1": float(construction["rail_cross_pool_strength_l1"]),
            "rail_l1": float(construction["rail_l1"]),
            "rail_difference_from_field_rail": construction["rail_difference_from_field_rail"],
            "nesting_depth": construction["nesting_depth"],
            "shell_law": construction["shell_law"],
            "normalized": construction["normalized"],
            "rail_fraction": construction["rail_fraction"],
        }
    non_reference = tuple(name for name in per_arrangement if name not in reference_arrangements())
    records_by_name = {record["construction"]["name"]: record for record in records}
    lattice_names = tuple(name for name in non_reference if _family_of(name) == "lattice")
    motif_names = tuple(name for name in non_reference if _family_of(name) == "motif")
    nested_names = tuple(name for name in non_reference if _family_of(name) == "nested")
    motif_rung_names = tuple(
        name for name in motif_names
        if per_arrangement[name]["rung_channel_l1_one_sided"] is not None
    )
    normalized_nested_names = tuple(
        name for name in nested_names if per_arrangement[name]["normalized"]
    )
    interaction_names = tuple(name for name in non_reference if _family_of(name) == "interaction")
    rung_law_control_names = tuple(
        arm[0] for arm in MOTIF_RUNG_LAW_CONTROL_ARMS if arm[0] in per_arrangement
    )
    nested_raw_names = tuple(
        name for name in nested_names if not per_arrangement[name]["normalized"]
    )
    best_spacing = _best_by(per_arrangement, SPACING_PHI_NAMES)
    best_motif_coupling = _best_by(per_arrangement, MOTIF_COUPLING_PHI_NAMES)
    best_inter_copy = _best_by(per_arrangement, INTER_COPY_PHI_NAMES)
    best_lattice = _best_by(per_arrangement, lattice_names)
    reference = REFERENCE_NAME if REFERENCE_NAME in per_arrangement else None
    uniform_motif = UNIFORM_MOTIF_NAME if UNIFORM_MOTIF_NAME in per_arrangement else None
    ring_uniform = RING_UNIFORM_NAME if RING_UNIFORM_NAME in per_arrangement else None
    matched_random = MATCHED_RANDOM_NAME if MATCHED_RANDOM_NAME in per_arrangement else None
    nested = NESTED_NAME if NESTED_NAME in per_arrangement else None

    motif_reference = motif_reference_weight()
    lattice_reference = lattice_reference_weight()

    def _deviations(names: Sequence[str], field: str, reference_value: float) -> list[float]:
        values = [
            abs(float(per_arrangement[name][field]) - reference_value) / reference_value
            for name in names
            if per_arrangement[name].get(field) is not None
        ]
        return values

    def _max(values: Sequence[float]) -> float | None:
        return max(values) if values else None

    motif_deviations = _deviations(motif_names, "motif_channel_rail_l1", motif_reference)
    lattice_deviations = _deviations(lattice_names, "declared_channel_total_weight", lattice_reference)
    nested_deviations = _deviations(
        normalized_nested_names, "declared_link_channel_weight", lattice_reference
    )
    rung_deviations = _deviations(motif_rung_names, "rung_channel_l1_one_sided", motif_reference)
    identity_deviations = [
        float(per_arrangement[name]["rail_l1_identity_absolute_difference"])
        for name in non_reference
        if per_arrangement[name]["rail_l1_identity_absolute_difference"] is not None
    ]
    orientation_deviations = [
        float(per_arrangement[name]["rung_orientation_max_absolute_deviation"])
        for name in non_reference
        if per_arrangement[name]["rung_orientation_max_absolute_deviation"] is not None
    ]
    rail_leg = [
        name for name in lattice_names
        if reference is not None and per_arrangement[name]["mass_metric_diagonal_sha256"]
        == per_arrangement[reference]["mass_metric_diagonal_sha256"]
    ]
    overlap = (
        placement.set_overlap(
            per_arrangement[best_lattice]["top7_drive_ports"],
            per_arrangement[reference]["top7_drive_ports"],
        )
        if best_lattice is not None and reference is not None else None
    )
    derivation = motif_derivation_report()

    # ----------------------------------------------------------------------
    # the rung-law controls: one body, one declared channel total, eight shapes
    # ----------------------------------------------------------------------
    default_body_law_names = tuple(
        name for name in (
            ("motif-default-rungs", "uniform"),
            ("motif-default-rungs-phi", "phi"),
        ) + tuple((arm[0], arm[2]) for arm in MOTIF_RUNG_LAW_CONTROL_ARMS)
        if name[0] in per_arrangement
    )

    def _law_row(name: str, law: str) -> dict[str, Any]:
        row = per_arrangement[name]
        return {
            "arrangement": name,
            "rung_law": law,
            "k2": float(row["survival_recovery"]["k2"]),
            "k4": float(row["survival_recovery"]["k4"]),
            "k8": float(row["survival_recovery"]["k8"]),
            "ipr_median": float(row["ipr_median"]),
            "access_coverage_score": row["access_coverage_score"],
            "placement_write_read_spearman": float(row["placement_write_read_spearman"]),
            "top7_drive_ports": list(row["top7_drive_ports"]),
            "rung_channel_l1_one_sided": row["rung_channel_l1_one_sided"],
            "rung_scale_min": row["rung_scale_min"],
            "rung_scale_max": row["rung_scale_max"],
            "rail_l1": float(row["rail_l1"]),
            "rung_scale_sha256": _scale_digest(law),
            "survival_recovery_pointers": {
                count: json_pointer(
                    "comparisons", "basis", "per_arrangement", name, "survival_recovery", count
                )
                for count in ("k2", "k4", "k8")
            },
        }

    rung_law_rows = [_law_row(name, law) for name, law in default_body_law_names]

    def _arm_recovery(name: str | None, count: str) -> float | None:
        if name is None or name not in per_arrangement:
            return None
        return float(per_arrangement[name]["survival_recovery"][count])

    canonical_k = {count: _arm_recovery(uniform_motif, count) for count in ("k2", "k4", "k8")}

    def _law_pick(law: str) -> dict[str, Any] | None:
        for row in rung_law_rows:
            if row["rung_law"] == law:
                return row
        return None

    k4_values = [row["k4"] for row in rung_law_rows]
    phi_row = _law_pick("phi")
    steep_rows = [row for row in rung_law_rows if row["rung_law"] in ("1.5x", "2.0x")]
    rung_law_scalars = {
        "law_count": len(rung_law_rows),
        "rows": rung_law_rows,
        "k4_min": min(k4_values) if k4_values else None,
        "k4_max": max(k4_values) if k4_values else None,
        "k4_spread": (max(k4_values) - min(k4_values)) if k4_values else None,
        "k4_best_law": (
            max(rung_law_rows, key=lambda row: row["k4"])["rung_law"] if rung_law_rows else None
        ),
        "k4_worst_law": (
            min(rung_law_rows, key=lambda row: row["k4"])["rung_law"] if rung_law_rows else None
        ),
        "phi_vs_steepest_ramp_k4_absolute_difference": (
            None if phi_row is None or not steep_rows
            else float(max(abs(phi_row["k4"] - row["k4"]) for row in steep_rows))
        ),
        "max_k4_difference_from_phi": (
            None if phi_row is None or not rung_law_rows
            else float(max(abs(phi_row["k4"] - row["k4"]) for row in rung_law_rows))
        ),
        "single_rung_k4_difference_from_canonical": (
            None if _law_pick("single") is None or canonical_k["k4"] is None
            else float(abs(_law_pick("single")["k4"] - canonical_k["k4"]))
        ),
        "shuffled_phi_vs_phi_k4_difference": (
            None if _law_pick("shuffled-phi") is None or phi_row is None
            else float(abs(_law_pick("shuffled-phi")["k4"] - phi_row["k4"]))
        ),
        "phi_down_vs_phi_k4_difference": (
            None if _law_pick("phi-down") is None or phi_row is None
            else float(abs(_law_pick("phi-down")["k4"] - phi_row["k4"]))
        ),
        "centred_vs_phi_k4_difference": (
            None if _law_pick("centred") is None or phi_row is None
            else float(abs(_law_pick("centred")["k4"] - phi_row["k4"]))
        ),
        "channel_max_relative_deviation": _max(_deviations(
            [name for name, _law in default_body_law_names],
            "rung_channel_l1_one_sided", motif_reference,
        )),
        "best_k8_delta_vs_canonical": (
            None if not rung_law_rows or canonical_k["k8"] is None
            else float(max(row["k8"] for row in rung_law_rows) - canonical_k["k8"])
        ),
        "best_k8_law": (
            max(rung_law_rows, key=lambda row: row["k8"])["rung_law"] if rung_law_rows else None
        ),
        "best_k4_delta_vs_canonical": (
            None if not rung_law_rows or canonical_k["k4"] is None
            else float(max(row["k4"] for row in rung_law_rows) - canonical_k["k4"])
        ),
        "k8_survivor_count": (
            sum(
                1 for row in rung_law_rows
                if canonical_k["k8"] is not None
                and row["k8"] - canonical_k["k8"] >= MARGIN_RECOVERY
            )
        ),
        "phi_k4": None if phi_row is None else float(phi_row["k4"]),
        "best_steep_ramp_k4": (
            None if not steep_rows else float(max(row["k4"] for row in steep_rows))
        ),
        "canonical_k2": canonical_k["k2"], "canonical_k4": canonical_k["k4"],
        "canonical_k8": canonical_k["k8"],
    }

    # ----------------------------------------------------------------------
    # the interaction grid: the mass channel against the declared rail weight
    # ----------------------------------------------------------------------

    def _grid_rows(names: Sequence[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name in names:
            row = per_arrangement.get(name)
            if row is None:
                continue
            rows.append({
                "arrangement": name,
                "rail_fraction": row["rail_fraction"],
                "declared_channel_total_weight": row["declared_channel_total_weight"],
                "rail_l1": float(row["rail_l1"]),
                "k2": float(row["survival_recovery"]["k2"]),
                "k4": float(row["survival_recovery"]["k4"]),
                "k8": float(row["survival_recovery"]["k8"]),
                "ipr_median": float(row["ipr_median"]),
                "access_coverage_score": row["access_coverage_score"],
                "placement_write_read_spearman": float(row["placement_write_read_spearman"]),
                "mass_metric_diagonal_sha256": row["mass_metric_diagonal_sha256"],
            })
        rows.sort(key=lambda item: (item["rail_fraction"] is None, item["rail_fraction"]))
        return rows

    rail_leg_rows = _grid_rows(INTERACTION_RAIL_LEG_NAMES)
    mass_leg_rows = _grid_rows(INTERACTION_MASS_LEG_NAMES)

    def _fit(rows: Sequence[Mapping[str, Any]], count: str) -> dict[str, Any] | None:
        usable = [row for row in rows if row["rail_fraction"] is not None]
        if len(usable) < 2:
            return None
        x = np.asarray([float(row["rail_fraction"]) for row in usable], dtype=np.float64)
        y = np.asarray([float(row[count]) for row in usable], dtype=np.float64)
        slope, intercept = np.polyfit(x, y, 1)
        predicted = slope * x + intercept
        residual = y - predicted
        return {
            "count": count,
            "slope_per_unit_rail_fraction": float(slope),
            "intercept_at_zero_rail_weight": float(intercept),
            "max_absolute_residual": float(np.abs(residual).max()),
            "residuals": [float(value) for value in residual],
            "spearman_k4_vs_rail_fraction": float(_spearman(x, y)),
            "successive_differences": [
                float(y[index + 1] - y[index]) for index in range(len(y) - 1)
            ],
            "monotone_decreasing": bool(bool(np.all(np.diff(y) <= 1e-12))),
            "monotone_increasing": bool(bool(np.all(np.diff(y) >= -1e-12))),
            "half_slopes": [
                float((y[len(y) // 2] - y[0]) / (x[len(y) // 2] - x[0]))
                if x[len(y) // 2] != x[0] else None,
                float((y[-1] - y[len(y) // 2]) / (x[-1] - x[len(y) // 2]))
                if x[-1] != x[len(y) // 2] else None,
            ],
        }

    def _spearman(left: np.ndarray, right: np.ndarray) -> float:
        def _rank(values: np.ndarray) -> np.ndarray:
            order = np.argsort(values, kind="stable")
            ranks = np.empty(len(values), dtype=np.float64)
            ranks[order] = np.arange(len(values), dtype=np.float64)
            return ranks
        a, b = _rank(left), _rank(right)
        a = a - a.mean()
        b = b - b.mean()
        denominator = float(np.sqrt(float((a * a).sum()) * float((b * b).sum())))
        return 0.0 if denominator == 0.0 else float((a * b).sum() / denominator)

    rail_fit = _fit(rail_leg_rows, "k4")
    mass_fit = _fit(mass_leg_rows, "k4")

    def _row_at(rows: Sequence[Mapping[str, Any]], fraction: float) -> Mapping[str, Any] | None:
        for row in rows:
            if row["rail_fraction"] is not None and float(row["rail_fraction"]) == float(fraction):
                return row
        return None

    def _grid_pair_difference(fraction: float, count: str) -> float | None:
        rail_row = _row_at(rail_leg_rows, fraction)
        mass_row = _row_at(mass_leg_rows, fraction)
        if rail_row is None or mass_row is None:
            return None
        return float(mass_row[count] - rail_row[count])

    def _reproduction(left: str | None, right: str | None) -> dict[str, Any] | None:
        if left is None or right is None or left not in per_arrangement or right not in per_arrangement:
            return None
        differences = {
            count: float(abs(
                per_arrangement[left]["survival_recovery"][count]
                - per_arrangement[right]["survival_recovery"][count]
            ))
            for count in ("k2", "k4", "k8")
        }
        return {
            "left": left, "right": right,
            "survival_max_absolute_difference": max(differences.values()),
            "survival_absolute_differences": differences,
            "rail_identity": bool(
                per_arrangement[left]["rail_l1"] == per_arrangement[right]["rail_l1"]
            ),
        }

    # the grid cells that must reproduce already-declared arms: the flat rail weight at both ends
    grid_reproductions = [
        _reproduction(interaction_arm_name(0.0, "core-shell"), ATTRIBUTION_MASS_ONLY_NAME),
        _reproduction(interaction_arm_name(0.0, "canonical"), uniform_motif),
        _reproduction(interaction_arm_name(1.0, "canonical"), INTERACTION_RAIL_NAME),
        _reproduction(interaction_arm_name(1.0, "core-shell"), INTERACTION_RAIL_MASS_NAME),
    ]

    interaction_scalars = {
        "fractions": [float(value) for value in INTERACTION_RAIL_FRACTIONS],
        "rail_leg_rows": rail_leg_rows,
        "mass_leg_rows": mass_leg_rows,
        "mass_minus_rail_k4_by_fraction": [
            {"rail_fraction": float(fraction), "k4_difference": _grid_pair_difference(fraction, "k4")}
            for fraction in INTERACTION_RAIL_FRACTIONS
        ],
        "rail_weight_cuts_the_mass_gain": (
            None if _row_at(mass_leg_rows, 1.0) is None or _row_at(mass_leg_rows, 0.0) is None
            else float(
                _row_at(mass_leg_rows, 0.0)["k4"] - _row_at(mass_leg_rows, 1.0)["k4"]
            )
        ),
        "rail_fit": rail_fit,
        "mass_fit": mass_fit,
        "threshold_gap_k4": (
            None if mass_fit is None or mass_fit["half_slopes"][0] is None
            or mass_fit["half_slopes"][1] is None
            else float(abs(mass_fit["half_slopes"][0] - mass_fit["half_slopes"][1]))
        ),
        "mass_leg_reproduces_the_mass_only_arm": grid_reproductions[0],
        "zero_rail_leg_reproduces_the_canonical_body": grid_reproductions[1],
        "full_rail_leg_reproduces_the_lattice_rung_arm": grid_reproductions[2],
        "full_rail_mass_leg_reproduces_the_lattice_rung_mass_arm": grid_reproductions[3],
        "mass_leg_largest_non_monotone_step": (
            None if mass_fit is None
            else float(max([0.0] + [
                value for value in mass_fit["successive_differences"] if value > 0.0
            ]))
        ),
        "reproduction_max_absolute_difference": (
            None if not all(entry is not None for entry in grid_reproductions)
            else float(max(entry["survival_max_absolute_difference"] for entry in grid_reproductions))
        ),
        "rail_identity_all_cells_reproduce": all(
            bool(entry["rail_identity"]) for entry in grid_reproductions if entry is not None
        ),
        "reproduction_rows": grid_reproductions,
    }

    # ----------------------------------------------------------------------
    # the nested depth family under the anchor's own normalization
    # ----------------------------------------------------------------------
    raw_reference_names = [
        NESTED_ANCHOR_NAME if depth == 1 else f"nested-d{depth}-{NESTED_REFERENCE_LAW}-raw"
        for depth in NESTED_DEPTHS
    ]
    raw_uniform_names = [f"nested-d{depth}-uniform-raw" for depth in NESTED_DEPTHS]
    normalized_uniform_names = [f"nested-d{depth}-uniform" for depth in NESTED_DEPTHS]

    def _depth_table(names: Sequence[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name in names:
            row = per_arrangement.get(name)
            if row is None:
                continue
            rows.append({
                "arrangement": name,
                "depth": row["nesting_depth"],
                "shell_law": row["shell_law"],
                "normalized": row["normalized"],
                "k2": float(row["survival_recovery"]["k2"]),
                "k4": float(row["survival_recovery"]["k4"]),
                "k8": float(row["survival_recovery"]["k8"]),
                "ipr_median": float(row["ipr_median"]),
                "access_coverage_score": row["access_coverage_score"],
                "rail_l1": float(row["rail_l1"]),
                "declared_link_channel_weight": row["declared_link_channel_weight"],
            })
        rows.sort(key=lambda item: item["depth"])
        return rows

    def _spread(rows: Sequence[Mapping[str, Any]], count: str) -> float | None:
        if len(rows) < 2:
            return None
        values = [float(row[count]) for row in rows]
        return float(max(values) - min(values))

    raw_reference_rows = _depth_table(raw_reference_names)
    raw_uniform_rows = _depth_table(raw_uniform_names)
    normalized_uniform_rows = _depth_table(normalized_uniform_names)
    nested_raw_scalars = {
        "reference_law_rows": raw_reference_rows,
        "uniform_law_rows": raw_uniform_rows,
        "normalized_uniform_rows": normalized_uniform_rows,
        "reference_law_k4_spread": _spread(raw_reference_rows, "k4"),
        "reference_law_k8_spread": _spread(raw_reference_rows, "k8"),
        "uniform_law_k4_spread": _spread(raw_uniform_rows, "k4"),
        "uniform_law_k8_spread": _spread(raw_uniform_rows, "k8"),
        "normalized_uniform_k4_spread": _spread(normalized_uniform_rows, "k4"),
        "normalized_uniform_k8_spread": _spread(normalized_uniform_rows, "k8"),
        "raw_minus_normalized_k4_spread": (
            None if _spread(raw_uniform_rows, "k4") is None
            or _spread(normalized_uniform_rows, "k4") is None
            else float(
                _spread(raw_uniform_rows, "k4") - _spread(normalized_uniform_rows, "k4")
            )
        ),
    }
    # the normalization control must really vary the normalization: compare each raw arm's declared
    # link channel with the equal-budget family's at the same depth and shell law
    raw_vs_normalized_declarations: list[dict[str, Any]] = []
    for raw_arm, raw_depth, raw_law in NESTED_RAW_ARMS:
        raw_row = per_arrangement.get(raw_arm)
        normalized_name = f"nested-d{raw_depth}-{raw_law}"
        normalized_row = per_arrangement.get(normalized_name)
        if raw_row is None or normalized_row is None:
            continue
        declared = float(raw_row["declared_link_channel_weight"])
        normalized_declared = float(normalized_row["declared_link_channel_weight"])
        raw_vs_normalized_declarations.append({
            "raw_arm": raw_arm,
            "normalized_arm": normalized_name,
            "depth": int(raw_depth),
            "shell_law": raw_law,
            "raw_declared_link_channel": declared,
            "normalized_declared_link_channel": normalized_declared,
            "relative_difference": (
                None if normalized_declared == 0.0
                else float(abs(declared - normalized_declared) / abs(normalized_declared))
            ),
        })
    nested_raw_scalars["raw_vs_normalized_declarations"] = raw_vs_normalized_declarations
    nested_raw_scalars["laws_with_an_equal_budget_counterpart"] = sorted({
        entry["shell_law"] for entry in raw_vs_normalized_declarations
    })
    nested_raw_scalars["laws_without_an_equal_budget_counterpart"] = sorted({
        law for _arm, _depth, law in NESTED_RAW_ARMS
        if law not in {entry["shell_law"] for entry in raw_vs_normalized_declarations}
    })
    nested_raw_scalars["min_relative_declared_link_difference"] = (
        None if not raw_vs_normalized_declarations
        else float(min(
            entry["relative_difference"] for entry in raw_vs_normalized_declarations
            if entry["relative_difference"] is not None
        ))
    )

    def _recovery_of(name: str | None, count: str) -> float | None:
        if name is None or name not in per_arrangement:
            return None
        return float(per_arrangement[name]["survival_recovery"][count])

    def _top7_difference(left: str | None, right: str | None) -> int | None:
        if left is None or right is None or left not in per_arrangement or right not in per_arrangement:
            return None
        return int(len(
            set(per_arrangement[left]["top7_drive_ports"])
            ^ set(per_arrangement[right]["top7_drive_ports"])
        ))

    # attribution: the compound arm against the canonical body and its two single-channel legs
    attribution: dict[str, Any] = {"names": {
        "canonical": ATTRIBUTION_CANONICAL_NAME if ATTRIBUTION_CANONICAL_NAME in per_arrangement else None,
        "rail_only": ATTRIBUTION_RAIL_ONLY_NAME if ATTRIBUTION_RAIL_ONLY_NAME in per_arrangement else None,
        "mass_only": ATTRIBUTION_MASS_ONLY_NAME if ATTRIBUTION_MASS_ONLY_NAME in per_arrangement else None,
        "compound": ATTRIBUTION_COMPOUND_NAME if ATTRIBUTION_COMPOUND_NAME in per_arrangement else None,
    }}
    canonical_name = attribution["names"]["canonical"]
    for count in ("k2", "k4", "k8"):
        base = _recovery_of(canonical_name, count)
        legs = {
            leg: _recovery_of(attribution["names"][leg], count)
            for leg in ("rail_only", "mass_only", "compound")
        }
        deltas = {
            leg: (None if base is None or value is None else float(value - base))
            for leg, value in legs.items()
        }
        residual = (
            None if any(value is None for value in deltas.values())
            else float(deltas["compound"] - (deltas["rail_only"] + deltas["mass_only"]))
        )
        attribution[count] = {
            "canonical": base, "legs": legs, "deltas": deltas,
            "additivity_residual": residual,
            "additive_within_tolerance": (
                None if residual is None
                else bool(abs(residual) <= TOLERANCE_ATTRIBUTION_ADDITIVITY)
            ),
        }
    # nested: the two declared axes and the unnormalized depth-1 continuity anchor
    anchor_name = NESTED_ANCHOR_NAME if NESTED_ANCHOR_NAME in per_arrangement else None
    depth_shallow = f"nested-d{NESTED_DEPTHS[0]}-{NESTED_DEPTH_AXIS_LAW}"
    depth_deep = f"nested-d{NESTED_DEPTHS[-1]}-{NESTED_DEPTH_AXIS_LAW}"
    depth_previous = f"nested-d{NESTED_DEPTHS[-2]}-{NESTED_DEPTH_AXIS_LAW}"
    law_deep = f"nested-d{NESTED_LAW_AXIS_DEPTH}-phi"
    nested_block_scalars: dict[str, Any] = {
        "anchor_name": anchor_name,
        "depth_axis_law": NESTED_DEPTH_AXIS_LAW,
        "depth_shallow_name": depth_shallow if depth_shallow in per_arrangement else None,
        "depth_deep_name": depth_deep if depth_deep in per_arrangement else None,
        "depth_previous_name": depth_previous if depth_previous in per_arrangement else None,
        "law_axis_depth": int(NESTED_LAW_AXIS_DEPTH),
        "law_axis_phi_name": law_deep if law_deep in per_arrangement else None,
        "law_axis_uniform_name": depth_deep if depth_deep in per_arrangement else None,
        "anchor_k4": _recovery_of(anchor_name, "k4"),
        "anchor_ipr_median": (
            None if anchor_name is None else float(per_arrangement[anchor_name]["ipr_median"])
        ),
        "anchor_rail_l1": (
            None if anchor_name is None else float(per_arrangement[anchor_name]["rail_l1"])
        ),
        "cited_single_nest_k4": CITED_K4_RECOVERY[NESTED_NAME],
        "cited_single_nest_ipr_median": CITED_IPR_MEDIAN[NESTED_NAME],
    }
    nested_block_scalars["anchor_vs_cited_k4_difference"] = (
        None if nested_block_scalars["anchor_k4"] is None
        else float(abs(nested_block_scalars["anchor_k4"] - CITED_K4_RECOVERY[NESTED_NAME]))
    )
    nested_block_scalars["anchor_vs_cited_ipr_median_difference"] = (
        None if nested_block_scalars["anchor_ipr_median"] is None
        else float(abs(nested_block_scalars["anchor_ipr_median"] - CITED_IPR_MEDIAN[NESTED_NAME]))
    )
    same_run_nest_k4 = _recovery_of(nested, "k4")
    nested_block_scalars["same_run_single_nest_k4"] = same_run_nest_k4
    nested_block_scalars["anchor_vs_same_run_k4_difference"] = (
        None if nested_block_scalars["anchor_k4"] is None or same_run_nest_k4 is None
        else float(abs(nested_block_scalars["anchor_k4"] - same_run_nest_k4))
    )
    deep_k4 = _recovery_of(nested_block_scalars["depth_deep_name"], "k4")
    shallow_k4 = _recovery_of(nested_block_scalars["depth_shallow_name"], "k4")
    previous_k4 = _recovery_of(nested_block_scalars["depth_previous_name"], "k4")
    phi_k4 = _recovery_of(nested_block_scalars["law_axis_phi_name"], "k4")
    nested_block_scalars.update({
        "depth_deep_k4": deep_k4, "depth_shallow_k4": shallow_k4,
        "depth_previous_k4": previous_k4, "law_axis_phi_k4": phi_k4,
        "deepest_vs_shallowest_k4_difference": (
            None if deep_k4 is None or shallow_k4 is None else float(abs(deep_k4 - shallow_k4))
        ),
        "depth3_to_depth4_k4_difference": (
            None if deep_k4 is None or previous_k4 is None else float(abs(deep_k4 - previous_k4))
        ),
        "deepest_phi_vs_uniform_k4_difference": (
            None if phi_k4 is None or deep_k4 is None else float(phi_k4 - deep_k4)
        ),
        "normalized_arm_count": len(normalized_nested_names),
    })
    rung_block_scalars = {
        "rung_arm_names": list(motif_rung_names),
        "rung_positions_declared": POOLS * PORTS_PER_POOL,
        "canonical_entries_replaced": (
            None if not motif_rung_names
            else per_arrangement[motif_rung_names[0]]["rung_canonical_entries_replaced"]
        ),
        "rungs_top7_differing_from_canonical": _top7_difference(
            "motif-default-rungs", uniform_motif
        ),
        "rungs_top7_differing_between_laws": _top7_difference(
            "motif-default-rungs", "motif-default-rungs-phi"
        ),
    }
    basis: dict[str, Any] = {
        "definition": (
            "measured scalars read out of the arrangement records; every declared check reads "
            "exactly these numbers, so each check's firing control can move one of them"
        ),
        "per_arrangement": per_arrangement,
        "lattice_names": list(lattice_names),
        "motif_names": list(motif_names),
        "nested_names": list(nested_names),
        "interaction_names": list(interaction_names),
        "rung_law_control_names": list(rung_law_control_names),
        "nested_raw_names": list(nested_raw_names),
        "motif_rung_names": list(motif_rung_names),
        "best_lattice_name": best_lattice,
        "best_phi_spacing_name": best_spacing,
        "best_motif_phi_coupling_name": best_motif_coupling,
        "best_inter_copy_phi_name": best_inter_copy,
        "uniform_motif_name": uniform_motif,
        "ring_uniform_name": ring_uniform,
        "matched_random_name": matched_random,
        "reference_name": reference,
        "nested_core_shell_name": nested,
        "motif_reference_weight": motif_reference,
        "lattice_reference_weight": lattice_reference,
        "motif_total_weight_max_relative_deviation": _max(motif_deviations),
        "lattice_total_weight_max_relative_deviation": _max(lattice_deviations),
        "nested_total_weight_max_relative_deviation": _max(nested_deviations),
        "motif_rung_channel_max_relative_deviation": _max(rung_deviations),
        "rail_l1_identity_max_absolute_difference": _max(identity_deviations),
        "rung_orientation_max_absolute_deviation": _max(orientation_deviations),
        "rail_leg_names": list(rail_leg),
        "rail_leg_mass_metric_distinct_variant_count": len({
            per_arrangement[name]["mass_metric_diagonal_sha256"] for name in rail_leg
        }),
        "motif_derivation_max_abs_difference": derivation["max_abs_difference"],
        "motif_default_rail_difference_from_field": (
            None if uniform_motif is None else None
        ),
        "top7_drive_ports_differing_from_reference": (
            None if overlap is None else int(
                len(set(per_arrangement[best_lattice]["top7_drive_ports"])
                    ^ set(per_arrangement[reference]["top7_drive_ports"]))
            )
        ),
        "attribution": attribution,
        "attribution_rail_delta_k4": attribution["k4"]["deltas"]["rail_only"],
        "attribution_mass_delta_k4": attribution["k4"]["deltas"]["mass_only"],
        "attribution_compound_delta_k4": attribution["k4"]["deltas"]["compound"],
        "attribution_residual_k2": attribution["k2"]["additivity_residual"],
        "attribution_residual_k4": attribution["k4"]["additivity_residual"],
        "attribution_residual_k8": attribution["k8"]["additivity_residual"],
        "attribution_rail_only_name": attribution["names"]["rail_only"],
        "attribution_mass_only_name": attribution["names"]["mass_only"],
        "attribution_compound_name": attribution["names"]["compound"],
        "attribution_canonical_name": canonical_name,
        "nested": nested_block_scalars,
        "nested_anchor_name": anchor_name,
        "nested_anchor_vs_cited_k4_difference": nested_block_scalars["anchor_vs_cited_k4_difference"],
        "nested_anchor_vs_same_run_k4_difference": nested_block_scalars["anchor_vs_same_run_k4_difference"],
        "nested_anchor_rail_max_absolute_difference": (
            None if anchor_name is None
            else (records_by_name.get(anchor_name, {}).get("construction", {}).get(
                "anchor_comparison", {}) or {}).get("rail_max_absolute_difference")
        ),
        "nested_depth_deep_name": nested_block_scalars["depth_deep_name"],
        "nested_depth_shallow_name": nested_block_scalars["depth_shallow_name"],
        "nested_deepest_vs_shallowest_k4_difference": nested_block_scalars[
            "deepest_vs_shallowest_k4_difference"
        ],
        "nested_depth3_to_depth4_k4_difference": nested_block_scalars[
            "depth3_to_depth4_k4_difference"
        ],
        "nested_law_axis_phi_name": nested_block_scalars["law_axis_phi_name"],
        "nested_law_axis_uniform_name": nested_block_scalars["law_axis_uniform_name"],
        "nested_deepest_phi_vs_uniform_k4_difference": nested_block_scalars[
            "deepest_phi_vs_uniform_k4_difference"
        ],
        "rung": rung_block_scalars,
        "rung_law": rung_law_scalars,
        "interaction": interaction_scalars,
        "nested_raw": nested_raw_scalars,
        # flat pointers for the declared checks, each read out of the blocks above
        "rung_law_k4_spread": rung_law_scalars["k4_spread"],
        "rung_law_channel_max_relative_deviation": rung_law_scalars["channel_max_relative_deviation"],
        "rung_law_phi_k4": rung_law_scalars["phi_k4"],
        "rung_law_best_steep_ramp_k4": rung_law_scalars["best_steep_ramp_k4"],
        "rung_law_phi_minus_best_steep_ramp_k4": (
            None if rung_law_scalars["phi_k4"] is None
            or rung_law_scalars["best_steep_ramp_k4"] is None
            else float(
                abs(rung_law_scalars["phi_k4"] - rung_law_scalars["best_steep_ramp_k4"])
            )
        ),
        "rung_law_best_k8_delta_vs_canonical": rung_law_scalars["best_k8_delta_vs_canonical"],
        "rung_law_best_k8_law": rung_law_scalars["best_k8_law"],
        "rung_law_best_k4_law": rung_law_scalars["k4_best_law"],
        "rung_law_k8_survivor_count": rung_law_scalars["k8_survivor_count"],
        "rung_law_single_k4_difference_from_canonical": rung_law_scalars[
            "single_rung_k4_difference_from_canonical"
        ],
        "rung_law_shuffled_phi_vs_phi_k4_difference": rung_law_scalars[
            "shuffled_phi_vs_phi_k4_difference"
        ],
        "rung_law_phi_down_vs_phi_k4_difference": rung_law_scalars[
            "phi_down_vs_phi_k4_difference"
        ],
        "rung_law_centred_vs_phi_k4_difference": rung_law_scalars[
            "centred_vs_phi_k4_difference"
        ],
        "rung_law_canonical_k4": rung_law_scalars["canonical_k4"],
        "rung_law_best_k4_delta_vs_canonical": rung_law_scalars["best_k4_delta_vs_canonical"],
        "interaction_rail_weight_cuts_the_mass_gain": interaction_scalars[
            "rail_weight_cuts_the_mass_gain"
        ],
        "interaction_mass_leg_largest_non_monotone_step": interaction_scalars[
            "mass_leg_largest_non_monotone_step"
        ],
        "interaction_mass_leg_fit_max_absolute_residual": (
            None if interaction_scalars["mass_fit"] is None
            else interaction_scalars["mass_fit"]["max_absolute_residual"]
        ),
        "interaction_rail_leg_fit_max_absolute_residual": (
            None if interaction_scalars["rail_fit"] is None
            else interaction_scalars["rail_fit"]["max_absolute_residual"]
        ),
        "interaction_threshold_gap_k4": interaction_scalars["threshold_gap_k4"],
        "interaction_reproduction_max_absolute_difference": interaction_scalars[
            "reproduction_max_absolute_difference"
        ],
        "interaction_rail_identity_all_cells_reproduce": interaction_scalars[
            "rail_identity_all_cells_reproduce"
        ],
        "nested_raw_reference_law_k4_spread": nested_raw_scalars["reference_law_k4_spread"],
        "nested_raw_uniform_law_k4_spread": nested_raw_scalars["uniform_law_k4_spread"],
        "nested_raw_uniform_law_k8_spread": nested_raw_scalars["uniform_law_k8_spread"],
        "nested_normalized_uniform_k4_spread": nested_raw_scalars["normalized_uniform_k4_spread"],
        "nested_raw_minus_normalized_k4_spread": nested_raw_scalars["raw_minus_normalized_k4_spread"],
        "nested_raw_min_relative_declared_link_difference": nested_raw_scalars[
            "min_relative_declared_link_difference"
        ],
        "rung_uniform_name": (
            MOTIF_RUNG_ARMS[0][0] if MOTIF_RUNG_ARMS[0][0] in per_arrangement else None
        ),
        "rung_phi_name": (
            MOTIF_RUNG_ARMS[1][0] if MOTIF_RUNG_ARMS[1][0] in per_arrangement else None
        ),
        "rung_coupling_phi_uniform_name": (
            MOTIF_RUNG_ARMS[2][0] if MOTIF_RUNG_ARMS[2][0] in per_arrangement else None
        ),
        "rung_coupling_phi_phi_name": (
            MOTIF_RUNG_ARMS[3][0] if MOTIF_RUNG_ARMS[3][0] in per_arrangement else None
        ),
        "motif_rungs_top7_differing_from_canonical": rung_block_scalars[
            "rungs_top7_differing_from_canonical"
        ],
        "motif_rungs_top7_differing_between_laws": rung_block_scalars[
            "rungs_top7_differing_between_laws"
        ],
    }
    # measured through the built profile, not only through the re-derivation
    for record in records:
        if record["construction"]["name"] == UNIFORM_MOTIF_NAME:
            basis["motif_default_rail_difference_from_field"] = record["construction"][
                "rail_difference_from_field_rail"
            ]
    return basis


def _family_of(name: str) -> str:
    """The declared family of an arrangement name, from the declared name sets."""
    if name.startswith("nested-"):
        return "nested"
    if name.startswith("motif-"):
        return "motif"
    if name.startswith(f"{INTERACTION_BASE_NAME}-"):
        return "interaction"
    return "lattice"


def _at(*keys: Any) -> tuple[Callable[[Mapping[str, Any]], Any], Callable[[dict[str, Any], Any], None]]:
    """A (getter, setter) pair for a path into the comparison basis.

    A key that is callable is resolved against the **root** basis, so a check can
    name a dynamically selected arrangement (the best spacing arm, the uniform
    control) without hard-coding which arm won; resolving it against the current
    container would look the selector up inside ``per_arrangement``, where it does
    not live.
    """
    def resolve(root: Mapping[str, Any], key: Any) -> Any:
        return key(root) if callable(key) else key

    def get(basis: Mapping[str, Any]) -> Any:
        node = basis
        for key in keys[:-1]:
            node = node.get(resolve(basis, key))
            if node is None:
                # an arm that the declared scope does not measure makes the check not-measured
                # rather than raising inside the basis walk
                return None
        if node is None:
            return None
        return node.get(resolve(basis, keys[-1]))

    def put(basis: dict[str, Any], value: Any) -> None:
        node = basis
        for key in keys[:-1]:
            node = node[resolve(basis, key)]
        node[resolve(basis, keys[-1])] = value

    return get, put


def _scalar(key: str) -> tuple[Callable[[Mapping[str, Any]], Any], Callable[[dict[str, Any], Any], None]]:
    return _at(key)


def _recovery(name_key: str, count: str):
    return _at("per_arrangement", lambda b, k=name_key: b[k], "survival_recovery", count)


def _self_similarity(label: str, name_key: str):
    return _at("per_arrangement", lambda b, k=name_key: b[k], "self_similarity_index", label)


def _per(name_key: str, field: str):
    return _at("per_arrangement", lambda b, k=name_key: b[k], field)


KIND_DIFFERENCE = "difference"
KIND_ABSOLUTE_DIFFERENCE = "absolute-difference"
KIND_INVARIANCE = "invariance"


@dataclass(frozen=True)
class MarginCheck:
    """One declared margin check: ``target - baseline >= margin`` unless a kind says otherwise."""

    id: str
    family: str
    statement: str
    margin: float
    kind: str
    target_get: Callable[[Mapping[str, Any]], Any]
    target_put: Callable[[dict[str, Any], Any], None]
    base_get: Callable[[Mapping[str, Any]], Any]
    base_put: Callable[[dict[str, Any], Any], None]


def _difference_check(
    check_id: str, family: str, statement: str, margin: float,
    target: tuple[Callable, Callable], base: tuple[Callable, Callable],
    kind: str = KIND_DIFFERENCE,
) -> MarginCheck:
    return MarginCheck(
        id=check_id, family=family, statement=statement, margin=float(margin), kind=kind,
        target_get=target[0], target_put=target[1], base_get=base[0], base_put=base[1],
    )


NULL_BASE = (lambda b: 0.0, lambda b, v: None)


def margin_checks() -> tuple[MarginCheck, ...]:
    checks: list[MarginCheck] = []
    for count in ("k2", "k4", "k8"):
        checks.append(_difference_check(
            f"survival_{count}_best_lattice_beats_the_canonical_body", "survival",
            f"on the survival {count} arm the best declared lattice recovers at least "
            f"{MARGIN_RECOVERY} more than the canonical meaningful-helix body",
            MARGIN_RECOVERY,
            _recovery("best_lattice_name", count), _recovery("reference_name", count),
        ))
    checks.extend([
        _difference_check(
            "survival_k4_best_lattice_beats_nested_core_shell", "survival",
            f"on the survival k4 arm the best declared lattice recovers at least {MARGIN_RECOVERY} "
            f"more than the cited nested-core-shell scaffold",
            MARGIN_RECOVERY,
            _recovery("best_lattice_name", "k4"), _recovery("nested_core_shell_name", "k4"),
        ),
        _difference_check(
            "survival_k4_phi_spacing_beats_uniform_spacing_on_the_motif", "survival",
            f"on the survival k4 arm the best phi-ratio station law recovers at least "
            f"{MARGIN_RECOVERY} more than the built-in uniform station law",
            MARGIN_RECOVERY,
            _recovery("best_phi_spacing_name", "k4"), _recovery("uniform_motif_name", "k4"),
        ),
        _difference_check(
            "survival_k4_phi_coupling_beats_uniform_coupling_on_the_motif", "survival",
            f"on the survival k4 arm the best phi-ratio coupling law recovers at least "
            f"{MARGIN_RECOVERY} more than the built-in ungraded coupling",
            MARGIN_RECOVERY,
            _recovery("best_motif_phi_coupling_name", "k4"), _recovery("uniform_motif_name", "k4"),
        ),
        _difference_check(
            "survival_k4_phi_graded_inter_copy_coupling_beats_uniform", "survival",
            f"on the survival k4 arm the best phi-graded inter-copy coupling recovers at least "
            f"{MARGIN_RECOVERY} more than the uniform inter-copy coupling",
            MARGIN_RECOVERY,
            _recovery("best_inter_copy_phi_name", "k4"), _recovery("ring_uniform_name", "k4"),
        ),
        _difference_check(
            "survival_k4_phi_graded_inter_copy_coupling_beats_matched_random", "survival",
            f"on the survival k4 arm the best phi-graded inter-copy coupling recovers at least "
            f"{MARGIN_RECOVERY} more than the matched-random control with the same edge count and "
            f"the same declared total weight",
            MARGIN_RECOVERY,
            _recovery("best_inter_copy_phi_name", "k4"), _recovery("matched_random_name", "k4"),
        ),
        _difference_check(
            "survival_k4_rungs_change_the_result", "survival",
            f"declaring the 28 strand-to-strand rungs moves the survival k4 figure of the uniform "
            f"ring lattice by at least {MARGIN_RECOVERY}",
            MARGIN_RECOVERY,
            _at("per_arrangement", "ring-uniform-rungs", "survival_recovery", "k4"),
            _recovery("ring_uniform_name", "k4"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "survival_k4_mass_channel_moves_the_lattice_result", "survival",
            f"adding the shell metric to the phi-graded rung lattice moves its survival k4 figure "
            f"by at least {MARGIN_RECOVERY}",
            MARGIN_RECOVERY,
            _at("per_arrangement", "ring-phi-up-rungs-mass", "survival_recovery", "k4"),
            _at("per_arrangement", "ring-phi-up-rungs", "survival_recovery", "k4"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "ipr_median_phi_spacing_differs_from_uniform_spacing", "geometry",
            f"the phi-ratio station law's median mode participation ratio differs from the "
            f"built-in uniform station law's by at least {MARGIN_IPR}",
            MARGIN_IPR,
            _per("best_phi_spacing_name", "ipr_median"), _per("uniform_motif_name", "ipr_median"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "ipr_median_phi_graded_inter_copy_coupling_differs_from_uniform", "geometry",
            f"the phi-graded inter-copy coupling's median mode participation ratio differs from "
            f"the uniform one's by at least {MARGIN_IPR}",
            MARGIN_IPR,
            _per("best_inter_copy_phi_name", "ipr_median"), _per("ring_uniform_name", "ipr_median"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "access_coverage_best_lattice_beats_the_canonical_body", "geometry",
            f"the best declared lattice's best-subset access coverage exceeds the canonical body's "
            f"by at least {MARGIN_ACCESS}",
            MARGIN_ACCESS,
            _per("best_lattice_name", "access_coverage_score"),
            _per("reference_name", "access_coverage_score"),
        ),
        _difference_check(
            "spectrum_phi_band_self_similarity_lower_for_phi_spacing_than_uniform", "spectrum",
            f"the built-in uniform station law's phi-band self-similarity index exceeds the "
            f"phi-ratio station law's by at least {MARGIN_SELF_SIMILARITY}",
            MARGIN_SELF_SIMILARITY,
            _self_similarity("phi", "uniform_motif_name"),
            _self_similarity("phi", "best_phi_spacing_name"),
        ),
        _difference_check(
            "spectrum_octave_band_self_similarity_lower_for_phi_spacing_than_uniform", "spectrum",
            f"the built-in uniform station law's octave-band self-similarity index exceeds the "
            f"phi-ratio station law's by at least {MARGIN_SELF_SIMILARITY}",
            MARGIN_SELF_SIMILARITY,
            _self_similarity("octave", "uniform_motif_name"),
            _self_similarity("octave", "best_phi_spacing_name"),
        ),
        _difference_check(
            "spectrum_phi_band_self_similarity_lower_for_phi_graded_lattice_than_uniform", "spectrum",
            f"the uniform inter-copy lattice's phi-band self-similarity index exceeds the "
            f"phi-graded inter-copy lattice's by at least {MARGIN_SELF_SIMILARITY}",
            MARGIN_SELF_SIMILARITY,
            _self_similarity("phi", "ring_uniform_name"),
            _self_similarity("phi", "best_inter_copy_phi_name"),
        ),
        _difference_check(
            "spectrum_phi_log_periodic_order_exceeds_the_contrast_ratios", "spectrum",
            f"the phi-ratio station law's log-periodic order at ratio phi exceeds its best order "
            f"at the contrast ratios 2.0, 1.5 and 3.0 by at least {MARGIN_PHI_ORDER}",
            MARGIN_PHI_ORDER,
            _per("best_phi_spacing_name", "phi_ratio_excess"), NULL_BASE,
        ),
        _difference_check(
            "placement_rank_agreement_best_lattice_beats_the_canonical_body", "placement",
            f"the best declared lattice's write-rank/read-rank Spearman agreement exceeds the "
            f"canonical body's by at least {MARGIN_SPEARMAN}",
            MARGIN_SPEARMAN,
            _per("best_lattice_name", "placement_write_read_spearman"),
            _per("reference_name", "placement_write_read_spearman"),
        ),
        _difference_check(
            "placement_top7_drive_ports_differ_from_the_canonical_body", "placement",
            f"the best declared lattice's top-7 drive ports differ from the canonical body's in at "
            f"least {int(MARGIN_OVERLAP_PORTS)} port",
            MARGIN_OVERLAP_PORTS,
            _scalar("top7_drive_ports_differing_from_reference"), NULL_BASE,
        ),
        _difference_check(
            "motif_arms_share_the_declared_total_coupling_weight", "invariance",
            f"every motif arm's measured motif rail channel realizes the built-in body's own rail L1, "
            f"to {MARGIN_WEIGHT_INVARIANCE} relative",
            MARGIN_WEIGHT_INVARIANCE,
            _scalar("motif_total_weight_max_relative_deviation"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "lattice_inter_copy_coupling_shares_the_declared_total_weight", "invariance",
            f"every lattice arm's declared link channel plus its declared rung channel equals the "
            f"geometry harness's declared budget, to {MARGIN_WEIGHT_INVARIANCE} relative",
            MARGIN_WEIGHT_INVARIANCE,
            _scalar("lattice_total_weight_max_relative_deviation"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "rail_leg_shares_one_mass_normalization", "invariance",
            "every rail-leg lattice carries the canonical body's mass metric, so the rail-leg "
            "comparison is at equal mass normalization",
            MARGIN_MASS_INVARIANCE,
            _scalar("rail_leg_mass_metric_extra_variant_count"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "derived_rail_reproduces_the_field_derivation", "continuity",
            f"re-deriving the transport from the field's own edges and coordinates reproduces the "
            f"field's own rail to {MARGIN_DERIVATION_REPRODUCTION}",
            MARGIN_DERIVATION_REPRODUCTION,
            _scalar("motif_derivation_max_abs_difference"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "motif_default_build_is_the_canonical_body", "continuity",
            f"the motif arm built through the derived rail reproduces the field's own rail to "
            f"{MARGIN_DERIVATION_REPRODUCTION}",
            MARGIN_DERIVATION_REPRODUCTION,
            _scalar("motif_default_rail_difference_from_field"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
    ])
    # the bare-motif rung family: the same instruments and the same attribution on the helix
    # alone, where the only declared change is the strand-to-strand rung channel.
    checks.extend([
        # the uniform-law rung arm alone: the phi-law row below is a separate declared check with
        # its own verdict, so a reader never has to decide which arm a rung verdict covers
        _difference_check(
            "motif_rungs_change_survival_k4", "rung",
            f"setting the {RUNG_LAWS[0]!r}-law rung set at all 28 declared positions of the bare "
            f"motif (the arm {ATTRIBUTION_BARE_RUNG_NAMES[0]!r} against the un-runged "
            f"{UNIFORM_MOTIF_NAME!r}) moves the survival k4 figure of the field's own body by at "
            f"least {MARGIN_RECOVERY}; this check covers the uniform-law rung arm only",
            MARGIN_RECOVERY,
            _recovery("rung_uniform_name", "k4"), _recovery("uniform_motif_name", "k4"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "motif_phi_rungs_change_survival_k4", "rung",
            f"setting the {RUNG_LAWS[1]!r}-law rung set at all 28 declared positions of the bare "
            f"motif (the arm {ATTRIBUTION_BARE_RUNG_NAMES[1]!r} against the un-runged "
            f"{UNIFORM_MOTIF_NAME!r}) moves the survival k4 figure of the field's own body by at "
            f"least {MARGIN_RECOVERY}; this check covers the phi-law rung arm only, at the same "
            f"declared margin as the uniform-law row",
            MARGIN_RECOVERY,
            _recovery("rung_phi_name", "k4"), _recovery("uniform_motif_name", "k4"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "motif_rung_laws_give_distinct_survival_k4", "rung",
            f"the two declared bare-motif rung laws are not interchangeable: the phi-law arm "
            f"{ATTRIBUTION_BARE_RUNG_NAMES[1]!r} differs from the uniform-law arm "
            f"{ATTRIBUTION_BARE_RUNG_NAMES[0]!r} in survival k4 by at least {MARGIN_RECOVERY}, so "
            f"the two rows above cannot be read as one rung verdict",
            MARGIN_RECOVERY,
            _recovery("rung_phi_name", "k4"), _recovery("rung_uniform_name", "k4"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "motif_phi_rungs_localize_modes_differently_from_uniform_rungs", "rung",
            f"the phi-graded rung set's median mode participation ratio differs from the uniform "
            f"rung set's by at least {MARGIN_IPR}",
            MARGIN_IPR,
            _per("rung_phi_name", "ipr_median"), _per("rung_uniform_name", "ipr_median"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "motif_rungs_move_the_access_coverage", "rung",
            f"setting the uniform rung set on the bare motif moves its best-subset access coverage "
            f"by at least {MARGIN_ACCESS}",
            MARGIN_ACCESS,
            _per("rung_uniform_name", "access_coverage_score"),
            _per("uniform_motif_name", "access_coverage_score"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "motif_rungs_move_the_write_read_rank_agreement", "rung",
            f"setting the uniform rung set on the bare motif moves its write-rank/read-rank "
            f"Spearman agreement by at least {MARGIN_SPEARMAN}",
            MARGIN_SPEARMAN,
            _per("rung_uniform_name", "placement_write_read_spearman"),
            _per("uniform_motif_name", "placement_write_read_spearman"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "motif_rungs_move_the_top7_drive_ports", "rung",
            f"setting the uniform rung set on the bare motif changes at least "
            f"{int(MARGIN_OVERLAP_PORTS)} of its top-7 drive ports",
            MARGIN_OVERLAP_PORTS,
            _scalar("motif_rungs_top7_differing_from_canonical"), NULL_BASE,
        ),
        _difference_check(
            "motif_phi_rungs_move_the_rank_agreement_against_uniform_rungs", "rung",
            f"the phi-graded rung set's write-rank/read-rank Spearman agreement differs from the "
            f"uniform rung set's by at least {MARGIN_SPEARMAN}",
            MARGIN_SPEARMAN,
            _per("rung_phi_name", "placement_write_read_spearman"),
            _per("rung_uniform_name", "placement_write_read_spearman"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "motif_phi_rungs_move_the_top7_drive_ports_against_uniform_rungs", "rung",
            f"the phi-graded rung set changes at least {int(MARGIN_OVERLAP_PORTS)} of the uniform "
            f"rung set's top-7 drive ports",
            MARGIN_OVERLAP_PORTS,
            _scalar("motif_rungs_top7_differing_between_laws"), NULL_BASE,
        ),
        _difference_check(
            "motif_rung_channel_carries_the_motif_body_budget", "invariance",
            f"every bare-motif rung arm's written rung channel equals the motif body's own declared "
            f"rail L1, to {MARGIN_WEIGHT_INVARIANCE} relative",
            MARGIN_WEIGHT_INVARIANCE,
            _scalar("motif_rung_channel_max_relative_deviation"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "declared_rungs_are_written_in_the_declared_orientation", "invariance",
            f"every declared rung is measured back out of the rail at exactly the declared scale in "
            f"the Yang->Yin orientation, to {MARGIN_DERIVATION_REPRODUCTION}",
            MARGIN_DERIVATION_REPRODUCTION,
            _scalar("rung_orientation_max_absolute_deviation"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "every_declared_arm_realizes_its_declared_rail_l1", "invariance",
            f"every declared arrangement's rail carries exactly the L1 its declared channels "
            f"account for, to {MARGIN_WEIGHT_INVARIANCE} absolute",
            MARGIN_WEIGHT_INVARIANCE,
            _scalar("rail_l1_identity_max_absolute_difference"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
    ])
    # the nested-shell family: recursion depth and shell law, against the same-run single nest
    checks.extend([
        _difference_check(
            "nested_depth1_anchor_reproduces_the_cited_single_nest", "nested",
            f"the depth-1 reference-law anchor reproduces the cited {NESTED_NAME!r} survival k4 "
            f"figure to {CONTINUITY_ALLOWANCE}",
            CONTINUITY_ALLOWANCE,
            _scalar("nested_anchor_vs_cited_k4_difference"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "nested_depth1_anchor_matches_the_cited_nest_rail", "nested",
            f"the depth-1 reference-law anchor's rail equals the geometry harness's own "
            f"{NESTED_NAME!r} rail entry by entry, to {MARGIN_DERIVATION_REPRODUCTION}",
            MARGIN_DERIVATION_REPRODUCTION,
            _scalar("nested_anchor_rail_max_absolute_difference"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "nested_depth1_anchor_agrees_with_the_same_run_single_nest", "nested",
            f"the depth-1 reference-law anchor agrees with the {NESTED_NAME!r} row measured in this "
            f"same run to {CONTINUITY_ALLOWANCE}",
            CONTINUITY_ALLOWANCE,
            _scalar("nested_anchor_vs_same_run_k4_difference"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "nested_deepest_differs_from_shallowest_at_equal_budget", "nested",
            f"at equal declared link budget and the neutral shell law, the deepest declared nesting "
            f"moves the survival k4 figure by at least {MARGIN_RECOVERY} against depth 1",
            MARGIN_RECOVERY,
            _recovery("nested_depth_deep_name", "k4"), _recovery("nested_depth_shallow_name", "k4"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "nested_depth_saturates_by_the_deepest_declared_depth", "nested",
            f"adding the fourth nesting level moves the survival k4 figure of the neutral-law family "
            f"by no more than {MARGIN_DEPTH_SATURATION}",
            MARGIN_DEPTH_SATURATION,
            _scalar("nested_depth3_to_depth4_k4_difference"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "nested_phi_shell_law_beats_uniform_at_the_deepest_depth", "nested",
            f"at the deepest declared depth the phi shell law recovers at least {MARGIN_RECOVERY} "
            f"more than the uniform shell law",
            MARGIN_RECOVERY,
            _recovery("nested_law_axis_phi_name", "k4"),
            _recovery("nested_law_axis_uniform_name", "k4"),
        ),
        _difference_check(
            "nested_arms_share_the_declared_weight_budget", "invariance",
            f"every normalized nested arm's declared link channel equals the geometry harness's "
            f"declared budget, to {MARGIN_WEIGHT_INVARIANCE} relative",
            MARGIN_WEIGHT_INVARIANCE,
            _scalar("nested_total_weight_max_relative_deviation"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
    ])
    # the attribution decomposition: two single-channel legs, the compound and their residual
    checks.extend([
        _difference_check(
            "attribution_rail_leg_moves_survival_k4", "attribution",
            f"the rail-only leg moves the canonical body's survival k4 figure by at least "
            f"{MARGIN_RAIL_COMPONENT}",
            MARGIN_RAIL_COMPONENT,
            _recovery("attribution_rail_only_name", "k4"), _recovery("attribution_canonical_name", "k4"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "attribution_mass_leg_moves_survival_k4", "attribution",
            f"the mass-only leg moves the canonical body's survival k4 figure by at least "
            f"{MARGIN_MASS_COMPONENT}",
            MARGIN_MASS_COMPONENT,
            _recovery("attribution_mass_only_name", "k4"), _recovery("attribution_canonical_name", "k4"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "attribution_compound_moves_survival_k4", "attribution",
            f"the compound arm moves the canonical body's survival k4 figure by at least "
            f"{MARGIN_RECOVERY}",
            MARGIN_RECOVERY,
            _recovery("attribution_compound_name", "k4"), _recovery("attribution_canonical_name", "k4"),
            kind=KIND_ABSOLUTE_DIFFERENCE,
        ),
        _difference_check(
            "attribution_additivity_residual_within_tolerance_k2", "attribution",
            f"the compound's k2 gain over the canonical body differs from the sum of its two "
            f"single-channel legs by no more than the declared additivity tolerance "
            f"{TOLERANCE_ATTRIBUTION_ADDITIVITY}",
            TOLERANCE_ATTRIBUTION_ADDITIVITY,
            _scalar("attribution_residual_k2"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "attribution_additivity_residual_within_tolerance_k4", "attribution",
            f"the compound's k4 gain over the canonical body differs from the sum of its two "
            f"single-channel legs by no more than the declared additivity tolerance "
            f"{TOLERANCE_ATTRIBUTION_ADDITIVITY}",
            TOLERANCE_ATTRIBUTION_ADDITIVITY,
            _scalar("attribution_residual_k4"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
    ])
    # the rung-law controls: the same body, the same declared channel total, eight shapes
    checks.extend([
        _difference_check(
            "rung_law_controls_share_the_declared_channel_budget", "invariance",
            f"every rung-law control arm's written rung channel equals the motif body's own declared "
            f"rail L1, to {MARGIN_WEIGHT_INVARIANCE} relative",
            MARGIN_WEIGHT_INVARIANCE,
            _scalar("rung_law_channel_max_relative_deviation"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "rung_law_controls_separate_the_result", "rung",
            f"across the eight declared rung shapes at one declared channel total, the survival k4 "
            f"figures span at least {MARGIN_RECOVERY}, i.e. the rung *shape* moves the result and not "
            f"only the rung presence",
            MARGIN_RECOVERY,
            _scalar("rung_law_k4_spread"), NULL_BASE,
        ),
        _difference_check(
            "rung_law_controls_from_the_steep_ramps_reach_the_phi_gain", "rung",
            f"the best declared steep-ramp rung law (1.5**j or 2.0**j) reaches the phi law's k4 "
            f"figure to within {MARGIN_RECOVERY}, i.e. the k4 gain is shared by steep ramps rather "
            f"than specific to phi",
            MARGIN_RECOVERY,
            _scalar("rung_law_phi_minus_best_steep_ramp_k4"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "rung_law_controls_survive_at_k8", "rung",
            f"at least one of the eight declared rung shapes recovers at least {MARGIN_RECOVERY} more "
            f"than the un-runged body on the survival k8 arm",
            MARGIN_RECOVERY,
            _scalar("rung_law_best_k8_delta_vs_canonical"), NULL_BASE,
        ),
        _difference_check(
            "single_rung_control_moves_survival_k4", "rung",
            f"putting the whole declared rung channel on one declared position moves the survival k4 "
            f"figure of the un-runged body by at least {MARGIN_RECOVERY}",
            MARGIN_RECOVERY,
            _scalar("rung_law_single_k4_difference_from_canonical"), NULL_BASE,
        ),
        _difference_check(
            "shuffled_phi_rung_control_differs_from_the_phi_ramp", "rung",
            f"the multiset-matched shuffle of the phi ramp (same weights, same positions, different "
            f"assignment) differs from the ordered phi ramp in survival k4 by at least "
            f"{MARGIN_RECOVERY}, i.e. the rung assignment carries the effect",
            MARGIN_RECOVERY,
            _scalar("rung_law_shuffled_phi_vs_phi_k4_difference"), NULL_BASE,
        ),
        _difference_check(
            "phi_rung_ramp_differs_from_its_own_reversal", "rung",
            f"the reversed phi ramp differs from the phi ramp in survival k4 by at least "
            f"{MARGIN_RECOVERY}, i.e. which end of the helix carries the channel matters",
            MARGIN_RECOVERY,
            _scalar("rung_law_phi_down_vs_phi_k4_difference"), NULL_BASE,
        ),
    ])
    # the interaction grid: the mass channel against the declared rail weight
    checks.extend([
        _difference_check(
            "interaction_rail_weight_cuts_the_mass_gain", "interaction",
            f"with the mass channel on, declaring the full rail weight instead of none costs at "
            f"least {MARGIN_MASS_COMPONENT} of survival k4",
            MARGIN_MASS_COMPONENT,
            _scalar("interaction_rail_weight_cuts_the_mass_gain"), NULL_BASE,
        ),
        _difference_check(
            "interaction_rail_damage_is_monotone_in_rail_weight", "interaction",
            f"the mass-leg survival k4 figure never rises by more than {MARGIN_WEIGHT_INVARIANCE} "
            f"from one declared rail weight to the next, i.e. the rail's damage on the mass channel "
            f"is monotone in the declared rail weight rather than reversing",
            MARGIN_WEIGHT_INVARIANCE,
            _scalar("interaction_mass_leg_largest_non_monotone_step"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "interaction_mass_leg_fit_is_linear_in_rail_weight", "interaction",
            f"a straight line in the declared rail weight reproduces the mass-leg survival k4 grid "
            f"to {MARGIN_RECOVERY}",
            MARGIN_RECOVERY,
            _scalar("interaction_mass_leg_fit_max_absolute_residual"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "interaction_rail_damage_is_gradual_rather_than_thresholded", "interaction",
            f"the fitted slope over the second half of the declared rail weights differs from the "
            f"first half's by no more than {MARGIN_RECOVERY}, i.e. the damage is gradual",
            MARGIN_RECOVERY,
            _scalar("interaction_threshold_gap_k4"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
        _difference_check(
            "interaction_grid_reproduces_the_declared_lattice_arms", "invariance",
            f"the grid's full-rail cell reproduces the already-declared lattice rung arm, and its "
            f"zero-rail cell reproduces the un-runged body, to {MARGIN_DERIVATION_REPRODUCTION}",
            MARGIN_DERIVATION_REPRODUCTION,
            _scalar("interaction_reproduction_max_absolute_difference"), NULL_BASE,
            kind=KIND_INVARIANCE,
        ),
    ])
    # the nested depth family under the anchor's own normalization
    checks.extend([
        _difference_check(
            "nested_raw_reference_law_depth_changes_the_result", "nested",
            f"without the equal-total normalization, under the anchor's own reference law, the "
            f"survival k4 figures of the declared depth family span at least {MARGIN_RECOVERY} "
            f"across depths 1-4, i.e. depth is not inert at that law",
            MARGIN_RECOVERY,
            _scalar("nested_raw_reference_law_k4_spread"), NULL_BASE,
        ),
        _difference_check(
            "nested_raw_unity_law_depth_changes_the_result", "nested",
            f"without the equal-total normalization, under the unity shell law, the survival k4 "
            f"figures of the declared depth family span at least {MARGIN_RECOVERY} across depths 1-4, "
            f"i.e. depth is not inert at that law either",
            MARGIN_RECOVERY,
            _scalar("nested_raw_uniform_law_k4_spread"), NULL_BASE,
        ),
        _difference_check(
            "nested_depth_spread_is_the_normalizations_doing", "nested",
            f"the unnormalized depth spread exceeds the equal-budget depth spread by at least "
            f"{MARGIN_RECOVERY}, i.e. the flat normalized depth axis is a normalization effect",
            MARGIN_RECOVERY,
            _scalar("nested_raw_minus_normalized_k4_spread"), NULL_BASE,
        ),
        _difference_check(
            "nested_raw_arms_are_declared_without_the_equal_budget_normalization", "nested",
            f"every unnormalized nested arm's declared link channel differs from the equal-budget "
            f"family's declared link channel at the same depth and shell law (at the laws both "
            f"families declare) by at least "
            f"{MARGIN_RAW_DECLARATION} relative, so the normalization control really varies the "
            f"normalization (a zero quantity would mean the raw arm is a duplicate of a normalized "
            f"arm and the depth contrast would be vacuous)",
            MARGIN_RAW_DECLARATION,
            _scalar("nested_raw_min_relative_declared_link_difference"), NULL_BASE,
        ),
    ])
    return tuple(checks)


def evaluate_check(basis: Mapping[str, Any], check: MarginCheck) -> dict[str, Any]:
    """One declared check's measured quantity and verdict."""
    target = check.target_get(basis)
    baseline = check.base_get(basis)
    if target is None or baseline is None:
        return {
            "id": check.id, "family": check.family, "statement": check.statement,
            "margin": float(check.margin), "kind": check.kind,
            "target": target, "baseline": baseline, "quantity": None, "holds": None,
            "comparison": "<=" if check.kind == KIND_INVARIANCE else ">=",
            "status": "not-measured",
        }
    target, baseline = float(target), float(baseline)
    if check.kind == KIND_DIFFERENCE:
        quantity = target - baseline
        holds = quantity >= float(check.margin)
    elif check.kind == KIND_ABSOLUTE_DIFFERENCE:
        quantity = abs(target - baseline)
        holds = quantity >= float(check.margin)
    elif check.kind == KIND_INVARIANCE:
        quantity = abs(target)
        # a declared invariance is an upper bound: the deviation must not exceed the margin
        holds = quantity <= float(check.margin)
    else:
        raise ResonantNumericalError(f"unknown check kind {check.kind!r}")
    return {
        "id": check.id, "family": check.family, "statement": check.statement,
        "margin": float(check.margin), "kind": check.kind,
        "target": target, "baseline": baseline, "quantity": float(quantity),
        "comparison": ">=" if check.kind != KIND_INVARIANCE else "<=",
        "holds": bool(holds), "status": "measured",
    }


def evaluate_checks(basis: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [evaluate_check(basis, check) for check in margin_checks()]


def _basis_copy(basis: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(_jsonable(basis), allow_nan=False))


def fire_check(basis: Mapping[str, Any], check: MarginCheck) -> dict[str, Any]:
    """The declared firing control: move one real measured number so the verdict flips.

    A check whose verdict already fails is fired into the passing verdict instead, so
    every declared check is shown in both verdicts and no check can be silently
    unfalsifiable (a check that cannot be moved either way is reported as such).
    """
    before = evaluate_check(basis, check)
    baseline = check.base_get(basis)
    if before["holds"] is None:
        # a reduced scope can leave a declared arm unmeasured; the firing control reports that
        # rather than raising, so every declared check still carries a row in every scope
        return {
            "id": check.id,
            "kind": check.kind,
            "direction": None,
            "mutation": (
                "not fired: the check is not measured in this scope, so there is no measured number "
                "to move"
            ),
            "verdict_before": None,
            "verdict_after": None,
            "flips": None,
        }
    direction = "toward-violation" if before["holds"] else "toward-satisfaction"
    if check.kind == KIND_DIFFERENCE:
        if baseline is None:
            raise ResonantNumericalError(f"check {check.id!r} has no baseline to fire against")
        if check.target_get(basis) is None:
            raise ResonantNumericalError(f"check {check.id!r} measured no target to move")
        moved = (
            float(baseline) + 0.5 * float(check.margin) if before["holds"]
            else float(baseline) + 2.0 * float(check.margin)
        )
        check.target_put(basis, moved)
        note = (
            f"set the checked quantity to {moved!r}: its baseline plus half the declared margin "
            f"(the verdict must fail)" if before["holds"]
            else f"set the checked quantity to {moved!r}: its baseline plus twice the declared "
                 f"margin (the verdict must hold)"
        )
    elif check.kind == KIND_ABSOLUTE_DIFFERENCE:
        if baseline is None:
            raise ResonantNumericalError(f"check {check.id!r} has no baseline to fire against")
        moved = (
            float(baseline) if before["holds"] else float(baseline) + 2.0 * float(check.margin)
        )
        check.target_put(basis, moved)
        note = (
            f"set the checked quantity to its baseline {float(baseline)!r}, so the difference is "
            f"zero (the verdict must fail)" if before["holds"]
            else f"set the checked quantity to its baseline plus twice the declared margin, so the "
                 f"difference exceeds it (the verdict must hold)"
        )
    else:
        moved = 4.0 * float(check.margin) if before["holds"] else 0.5 * float(check.margin)
        check.target_put(basis, moved)
        note = (
            "set the checked deviation to four times the declared margin (the verdict must fail)"
            if before["holds"] else
            "set the checked deviation to half the declared margin (the verdict must hold)"
        )
    after = evaluate_check(basis, check)
    return {
        "id": check.id,
        "kind": check.kind,
        "direction": direction,
        "mutation": note,
        "verdict_before": before["holds"],
        "verdict_after": after["holds"],
        "flips": bool(before["holds"] is not None and after["holds"] is not None
                      and before["holds"] != after["holds"]),
    }


def firing_controls(basis: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Run every declared check's firing control on a copy of the real measured basis."""
    rows: list[dict[str, Any]] = []
    for check in margin_checks():
        rows.append(fire_check(_basis_copy(basis), check))
    return rows


def silenced_controls(basis: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The silenced control for every separation check: compare an arm with itself.

    A declared separation that survives substituting the same measured arm on both
    sides would be reporting something other than a difference between arms, so
    every such check must fall silent.  A declared *invariance* is an upper bound
    and has no arm-versus-itself control; it is falsified by its out-of-band firing
    control instead, and those checks are listed in ``invariance_checks_without_silenced_control``.
    """
    rows: list[dict[str, Any]] = []
    for check in margin_checks():
        if check.kind == KIND_INVARIANCE:
            continue
        probe = _basis_copy(basis)
        baseline = check.base_get(probe)
        if baseline is None or check.target_get(probe) is None:
            continue
        check.target_put(probe, float(baseline))
        row = evaluate_check(probe, check)
        rows.append({
            "id": check.id,
            "kind": check.kind,
            "statement": "the same measured arm substituted for both sides of the comparison",
            "quantity": row["quantity"],
            "holds": row["holds"],
            "silent": bool(row["holds"] is False),
        })
    return rows


def continuity_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Reproduce numbers already frozen in the existing receipts."""
    measured: dict[str, dict[str, float]] = {}
    for record in records:
        name = record["construction"]["name"]
        measured[name] = {
            "ipr_median": float(record["geometry"]["spectrum"]["ipr_median"]),
            "survival_k4_recovery": float(
                record["survival"]["arms"]["restart-and-activity-k4"]["recovery_fraction"]
            ),
            "survival_headline_recovery": float(
                record["survival"]["arms"]["restart-and-activity"]["recovery_fraction"]
            ),
        }
    rows: list[dict[str, Any]] = []

    def add(name: str, quantity: str, cited: float, source: str) -> None:
        if name not in measured:
            return
        value = measured[name][quantity]
        difference = abs(value - cited)
        rows.append({
            "id": f"continuity_{name}_{quantity}",
            "arrangement": name,
            "quantity": quantity,
            "source": source,
            "cited": float(cited),
            "measured": float(value),
            "allowance": CONTINUITY_ALLOWANCE,
            "absolute_difference": float(difference),
            "holds": bool(difference <= CONTINUITY_ALLOWANCE),
        })

    geometry_source = "_diag/fractal-geometry/exploration.json"
    survival_source = "_diag/fractal-survival/exploration.json"
    for name, cited in CITED_IPR_MEDIAN.items():
        add(name, "ipr_median", cited, geometry_source)
    for name, cited in CITED_K4_RECOVERY.items():
        add(name, "survival_k4_recovery", cited, survival_source)
    for name, cited in CITED_HEADLINE_RECOVERY.items():
        add(name, "survival_headline_recovery", cited, survival_source)
    # the arm built through this runner's own derived rail must reproduce the canonical body's own
    # cited figures, which is the continuity statement of the motif-anchored construction
    for quantity, cited_map, source in (
        ("ipr_median", CITED_IPR_MEDIAN, geometry_source),
        ("survival_k4_recovery", CITED_K4_RECOVERY, survival_source),
        ("survival_headline_recovery", CITED_HEADLINE_RECOVERY, survival_source),
    ):
        if UNIFORM_MOTIF_NAME not in measured or REFERENCE_NAME not in cited_map:
            continue
        add(UNIFORM_MOTIF_NAME, quantity, cited_map[REFERENCE_NAME],
            f"{source} ({REFERENCE_NAME}, i.e. the field's own default body)")
    return rows


def rung_report_block(basis: Mapping[str, Any]) -> dict[str, Any]:
    """The bare-motif rung family against the un-runged motif, at the same declared budget."""
    per = basis["per_arrangement"]
    canonical = basis["uniform_motif_name"]
    rows: list[dict[str, Any]] = []

    def row(name: str | None) -> dict[str, Any] | None:
        if name is None or name not in per:
            return None
        current = per[name]
        reference = per[canonical] if canonical in per else None
        return {
            "arrangement": name,
            "rung_law": "phi" if name.endswith("-phi") else "uniform",
            "coupling_law": "phi" if "coupling-phi" in name else "uniform",
            "survival_recovery": current["survival_recovery"],
            "survival_k4_delta_vs_canonical": (
                None if reference is None
                else float(current["survival_recovery"]["k4"] - reference["survival_recovery"]["k4"])
            ),
            "survival_k2_delta_vs_canonical": (
                None if reference is None
                else float(current["survival_recovery"]["k2"] - reference["survival_recovery"]["k2"])
            ),
            "survival_k8_delta_vs_canonical": (
                None if reference is None
                else float(current["survival_recovery"]["k8"] - reference["survival_recovery"]["k8"])
            ),
            "ipr_median": current["ipr_median"],
            "access_coverage_score": current["access_coverage_score"],
            "placement_write_read_spearman": current["placement_write_read_spearman"],
            "top7_drive_ports": current["top7_drive_ports"],
            "rail_l1": current["rail_l1"],
            "rung_channel_l1_one_sided": current["rung_channel_l1_one_sided"],
            "rung_scale_min": current["rung_scale_min"],
            "rung_scale_max": current["rung_scale_max"],
        }

    for key in ("rung_uniform_name", "rung_phi_name",
                "rung_coupling_phi_uniform_name", "rung_coupling_phi_phi_name"):
        built = row(basis.get(key))
        if built is not None:
            rows.append(built)
    canonical_row = None if canonical not in per else {
        "arrangement": canonical,
        "survival_recovery": per[canonical]["survival_recovery"],
        "ipr_median": per[canonical]["ipr_median"],
        "access_coverage_score": per[canonical]["access_coverage_score"],
        "placement_write_read_spearman": per[canonical]["placement_write_read_spearman"],
        "top7_drive_ports": per[canonical]["top7_drive_ports"],
        "rail_l1": per[canonical]["rail_l1"],
        "rung_channel_l1_one_sided": None,
    }
    lattice_rung_arms = [
        name for name in basis["lattice_names"]
        if per[name]["rung_channel_l1_one_sided"] is not None
    ]
    held_check = next(
        (check for check in margin_checks() if check.id == "survival_k4_rungs_change_the_result"),
        None,
    )
    held_rung_measured = (
        None if held_check is None else evaluate_check(basis, held_check)["quantity"]
    )
    return {
        "definition": (
            "the same instruments on the bare helix with its two strands connected: the declared "
            "rung set is set at every one of the 28 declared positions in the Yang->Yin orientation "
            "with its antisymmetric reverse entry, and the motif rail underneath is the field's own "
            "derived rail, unchanged"
        ),
        "rung_laws": {law: rung_law_rule(law) for law in RUNG_LAWS},
        "rung_positions_declared": int(POOLS * PORTS_PER_POOL),
        "canonical_arm": canonical_row,
        "arms": rows,
        "canonical_entries_replaced": basis["rung"]["canonical_entries_replaced"],
        "top7_drive_ports_differing_from_canonical": basis[
            "motif_rungs_top7_differing_from_canonical"
        ],
        "top7_drive_ports_differing_between_the_two_rung_laws": basis[
            "motif_rungs_top7_differing_between_laws"
        ],
        "motif_rung_channel_budget": basis["motif_reference_weight"],
        "motif_rung_channel_max_relative_deviation": basis[
            "motif_rung_channel_max_relative_deviation"
        ],
        "held_lattice_rung_result": {
            "check": "survival_k4_rungs_change_the_result",
            "cited": 0.0740669,
            "measured_in_this_receipt": held_rung_measured,
            "absolute_difference_to_cited": (
                None if held_rung_measured is None
                else float(abs(held_rung_measured - 0.0740669))
            ),
            "agrees_within_declared_tolerance": (
                None if held_rung_measured is None
                else bool(abs(held_rung_measured - 0.0740669) <= MARGIN_RECOVERY)
            ),
            "origin": (
                "the already-declared lattice rung arms of this runner (ring-uniform-rungs against "
                "ring-uniform), measured by the held check of the same name; the figure is cited "
                "from that held result, and this receipt's own row for the same check is recorded "
                "beside it so a disagreement with the cited figure is visible rather than assumed "
                "away"
            ),
        },
        "lattice_rung_arms_for_convention_comparison": [
            {
                "arrangement": name,
                "declared_rung_weight_canonical_rule": per[name]["declared_rung_channel_weight"],
                "written_rung_channel_l1_one_sided": per[name]["rung_channel_l1_one_sided"],
                "rail_l1": per[name]["rail_l1"],
            }
            for name in lattice_rung_arms
        ],
        "boundary": (
            "the bare-motif rung channel is declared in the rail's own units and normalized to the "
            "motif body's own rail L1 (3.426843625438269), so its written rung channel is comparable "
            "with the motif's own entries; the earlier lattice rung arms declare their rung scales "
            "under the canonical weight rule and write them directly, which is why their written rung "
            "channel is much larger than its canonical-rule share of the lattice budget. The two rung "
            "channels are therefore not at the same declared magnitude, and the cross-family rung "
            "magnitudes are not comparable; the within-family contrasts (rung law against rung law, "
            "runged against un-runged) are at one declared budget each"
        ),
        "survival_k4_rows": _rung_survival_rows(basis),
        "law_controls": _rung_law_controls(basis),
    }


def json_pointer(*tokens: Any) -> str:
    """The RFC 6901 JSON Pointer for a path into the shipped receipt.

    Every number this runner reports in prose is pinned to one of these, so a reader can
    resolve the figure against the receipt itself instead of trusting the summary: the
    tokens are the receipt's own keys (list positions are integers), escaped as ~0/~1.
    """
    escaped = [
        str(token).replace("~", "~0").replace("/", "~1") for token in tokens
    ]
    return "/" + "/".join(escaped)


def _check_index(check_id: str) -> int:
    """The position of a declared check in the shipped ``comparisons.checks`` list.

    The list is built as ``[evaluate_check(basis, check) for check in margin_checks()]``, so the
    position here is the position there; a JSON Pointer into an array needs the index, not the id.
    """
    for index, check in enumerate(margin_checks()):
        if check.id == check_id:
            return index
    raise ResonantNumericalError(f"no declared check is named {check_id!r}")


def check_arm_coverage(basis: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Which declared arms a check's two sides name, where the runner can say so explicitly.

    Only checks whose two sides are declared single arms are listed; everything else carries its
    arm names in its own statement text.  The point of the explicit listing is that a refuted check
    must say which arm it refutes, so a holding check on a sibling arm cannot be read as refuted.
    """
    canonical = basis.get("uniform_motif_name")
    uniform_rung = basis.get("rung_uniform_name")
    phi_rung = basis.get("rung_phi_name")
    coverage: dict[str, dict[str, Any]] = {}
    rows = (
        ("motif_rungs_change_survival_k4", uniform_rung, canonical, phi_rung),
        ("motif_phi_rungs_change_survival_k4", phi_rung, canonical, uniform_rung),
        ("motif_rung_laws_give_distinct_survival_k4", phi_rung, uniform_rung, canonical),
    )
    for check_id, target_arm, baseline_arm, sibling in rows:
        coverage[check_id] = {
            "target_arm": target_arm,
            "baseline_arm": baseline_arm,
            "covers_the_arms": [name for name in (target_arm, baseline_arm) if name],
            "does_not_cover": [name for name in (sibling,) if name],
        }
    for check_id, arm in (
        ("motif_rungs_move_the_access_coverage", uniform_rung),
        ("motif_rungs_move_the_write_read_rank_agreement", uniform_rung),
        ("motif_rungs_move_the_top7_drive_ports", uniform_rung),
        ("motif_phi_rungs_move_the_rank_agreement_against_uniform_rungs", phi_rung),
        ("motif_phi_rungs_move_the_top7_drive_ports_against_uniform_rungs", phi_rung),
    ):
        coverage[check_id] = {
            "target_arm": arm,
            "baseline_arm": canonical if "against" not in check_id else uniform_rung,
            "covers_the_arms": [name for name in (arm,) if name],
            "does_not_cover": [],
        }
    return coverage


def refuted_declared_hypotheses(basis: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every declared check the measurement refutes, with the arm it covers.

    A refuted check is reported rather than dropped, and it names the arrangement it refutes where
    the runner can say so, so a refuted row can never be read as covering a sibling arm whose own
    declared check holds.
    """
    coverage = check_arm_coverage(basis)
    rows: list[dict[str, Any]] = []
    for check in margin_checks():
        verdict = evaluate_check(basis, check)
        if verdict["holds"] is not False:
            continue
        entry: dict[str, Any] = {
            "check": check.id,
            "family": check.family,
            "kind": check.kind,
            "statement": check.statement,
            "margin": verdict["margin"],
            "measured_quantity": verdict["quantity"],
            "target": verdict["target"],
            "baseline": verdict["baseline"],
            "pointer": json_pointer("comparisons", "checks", _check_index(check.id)),
        }
        if check.id in coverage:
            entry["arm_coverage"] = coverage[check.id]
            if check.id == "motif_rungs_change_survival_k4":
                entry["reading"] = (
                    "this refuted row covers the uniform-law rung arm only; the phi-law rung arm is "
                    "a separate declared arrangement with its own declared check "
                    "(motif_phi_rungs_change_survival_k4), which holds at the same declared margin"
                )
        rows.append(entry)
    return rows


def _rung_survival_rows(basis: Mapping[str, Any]) -> dict[str, Any]:
    """Which declared check covers which bare-rung arm, with both rows' verdicts side by side.

    The two bare-rung arms carry two separate declared checks at the same declared margin, so the
    uniform-law row is refuted while the phi-law row holds; a reader must be able to read that off
    the receipt without inferring it from the check id.
    """
    per = basis["per_arrangement"]
    canonical_name = basis["uniform_motif_name"]
    canonical_k4 = (
        None if canonical_name not in per
        else float(per[canonical_name]["survival_recovery"]["k4"])
    )
    checks = {check.id: check for check in margin_checks()}
    coverage = check_arm_coverage(basis)
    rows: list[dict[str, Any]] = []
    for check_id, arm_key in (
        ("motif_rungs_change_survival_k4", "rung_uniform_name"),
        ("motif_phi_rungs_change_survival_k4", "rung_phi_name"),
    ):
        check = checks.get(check_id)
        arm = basis.get(arm_key)
        if check is None or arm is None or arm not in per:
            continue
        veredict = evaluate_check(basis, check)
        arm_k4 = float(per[arm]["survival_recovery"]["k4"])
        row_index = len(rows)
        rows.append({
            "check": check_id,
            "family": check.family,
            "covers_the_arm": arm,
            "compared_against": canonical_name,
            "declared_margin": float(check.margin),
            "kind": check.kind,
            "arm_k4": arm_k4,
            "canonical_k4": canonical_k4,
            "k4_delta": (None if canonical_k4 is None else float(arm_k4 - canonical_k4)),
            "measured_quantity": veredict["quantity"],
            "verdict": veredict["holds"],
            "statement": check.statement,
            "arm_coverage": coverage.get(check_id),
            "survival_recovery_pointers": {
                count: json_pointer(
                    "comparisons", "basis", "per_arrangement", arm, "survival_recovery", count
                )
                for count in ("k2", "k4", "k8")
            },
            "canonical_survival_recovery_pointers": {
                count: json_pointer(
                    "comparisons", "basis", "per_arrangement", canonical_name,
                    "survival_recovery", count,
                )
                for count in ("k2", "k4", "k8")
            },
            "pointers": {
                "arm_k4": json_pointer(
                    "comparisons", "basis", "per_arrangement", arm, "survival_recovery", "k4"
                ),
                "canonical_k4": json_pointer(
                    "comparisons", "basis", "per_arrangement", canonical_name,
                    "survival_recovery", "k4",
                ),
                "check_row": json_pointer(
                    "comparisons", "checks", _check_index(check_id)
                ),
                "reconciliation_row": json_pointer(
                    "comparisons", "rung", "survival_k4_rows", "rows", row_index
                ),
            },
        })
    return {
        "definition": (
            "one row per declared bare-motif rung survival-k4 check: the check id, the arm it "
            "covers, the arm it is compared against, its declared margin and its verdict. The two "
            "rung laws are declared as two arms and covered by two checks, so a refuted rung verdict "
            "applies to the arm named in that row only"
        ),
        "pointer_definition": (
            "every pointer in this block is an RFC 6901 JSON Pointer into this receipt, resolved "
            "against the receipt root"
        ),
        "rows": rows,
        "reconciliation": (
            "the uniform-law arm and the phi-law arm are separate declared arrangements with "
            "separate declared checks at the same margin; the refuted row is the uniform-law arm, "
            "and the phi-law row holds, so no single rung verdict covers both arms"
        ),
        "coverage_check": "motif_rung_laws_give_distinct_survival_k4",
    }


def _rung_law_controls(basis: Mapping[str, Any]) -> dict[str, Any]:
    """The declared rung shapes at one declared channel total: is the k4 gain phi-specific?"""
    scalars = basis["rung_law"]
    rows = scalars["rows"]
    phi_row = next((row for row in rows if row["rung_law"] == "phi"), None)
    steep_rows = [row for row in rows if row["rung_law"] in ("1.5x", "2.0x")]
    best_steep = None if not steep_rows else max(steep_rows, key=lambda row: row["k4"])
    best_k8 = next(
        (row for row in rows if row["rung_law"] == scalars["best_k8_law"]), None
    )
    gap = (
        None if phi_row is None or best_steep is None
        else float(abs(phi_row["k4"] - best_steep["k4"]))
    )
    if gap is None or scalars["best_k8_delta_vs_canonical"] is None:
        specificity = "not-measured"
    elif gap <= MARGIN_RECOVERY:
        specificity = "shared by the steep ramps"
    else:
        specificity = "specific to the phi ramp"
    survives_k8 = (
        None if scalars["best_k8_delta_vs_canonical"] is None
        else bool(scalars["best_k8_delta_vs_canonical"] >= MARGIN_RECOVERY)
    )
    return {
        "definition": (
            "the same bare-motif body and the same 28 declared rung positions as the two primary "
            "rung arms, with the same declared rung channel total, under six further declared rung "
            "shapes: two other steep ramps (1.5**j, 2.0**j), the phi ramp reversed "
            "(phi**(27-j)), a centred steep law with its peak at the middle of the helix, a "
            "single-position law carrying the whole channel on the middle position, and a "
            "multiset-matched shuffle of the phi ramp's own weights"
        ),
        "laws": {law: rung_law_rule(law) for law in MOTIF_RUNG_LAWS},
        "rows": rows,
        "table": {
            "law_count": scalars["law_count"],
            "k4_spread": scalars["k4_spread"],
            "k4_best_law": scalars["k4_best_law"],
            "k4_worst_law": scalars["k4_worst_law"],
            "k4_min": scalars["k4_min"],
            "k4_max": scalars["k4_max"],
            "canonical_k2": scalars["canonical_k2"],
            "canonical_k4": scalars["canonical_k4"],
            "canonical_k8": scalars["canonical_k8"],
            "channel_budget": basis["motif_reference_weight"],
            "channel_max_relative_deviation": scalars["channel_max_relative_deviation"],
        },
        "phi_specificity": {
            "phi_k4": scalars["phi_k4"],
            "best_steep_ramp_k4": scalars["best_steep_ramp_k4"],
            "best_steep_ramp_law": None if best_steep is None else best_steep["rung_law"],
            "phi_minus_best_steep_ramp_k4_absolute_difference": gap,
            "within_margin": (None if gap is None else bool(gap <= MARGIN_RECOVERY)),
            "reading": specificity,
        },
        "survival_at_k8": {
            "best_law": scalars["best_k8_law"],
            "best_k8": None if best_k8 is None else best_k8["k8"],
            "best_k8_delta_vs_canonical": scalars["best_k8_delta_vs_canonical"],
            "survivor_count_at_the_declared_margin": scalars["k8_survivor_count"],
            "phi_k8": None if phi_row is None else phi_row["k8"],
            "survives": survives_k8,
        },
        "single_position_control": {
            "difference_from_canonical_k4": scalars["single_rung_k4_difference_from_canonical"],
            "position": int(SINGLE_RUNG_POSITION),
        },
        "assignment_controls": {
            "shuffled_phi_vs_phi_k4_difference": scalars["shuffled_phi_vs_phi_k4_difference"],
            "phi_down_vs_phi_k4_difference": scalars["phi_down_vs_phi_k4_difference"],
            "centred_vs_phi_k4_difference": scalars["centred_vs_phi_k4_difference"],
            "seed": int(RUNG_CONTROL_SEED),
        },
        "margins": {
            "channel_budget": MARGIN_WEIGHT_INVARIANCE,
            "law_spread": MARGIN_RECOVERY,
            "phi_vs_steep_ramp": MARGIN_RECOVERY,
            "k8_survival": MARGIN_RECOVERY,
        },
        "boundary": (
            "every law here is declared at the same 28 positions and normalized to the same "
            "declared rung channel total, so the laws differ only in their shape; the shuffled "
            "control takes the phi ramp's own weight multiset under one fixed seed, so it carries "
            "the same weights as the ramp and differs only in their assignment"
        ),
    }


def attribution_block(basis: Mapping[str, Any]) -> dict[str, Any]:
    """Deltas against the canonical body, the two single-channel legs and the residual."""
    per = basis["per_arrangement"]
    attribution = basis["attribution"]
    names = attribution["names"]

    def detail(name: str | None) -> dict[str, Any] | None:
        if name is None or name not in per:
            return None
        return {
            "arrangement": name,
            "survival_recovery": per[name]["survival_recovery"],
            "ipr_median": per[name]["ipr_median"],
            "access_coverage_score": per[name]["access_coverage_score"],
            "placement_write_read_spearman": per[name]["placement_write_read_spearman"],
            "mass_metric_diagonal_sha256": per[name]["mass_metric_diagonal_sha256"],
            "declared_channel_total_weight": per[name]["declared_channel_total_weight"],
        }

    table = [
        {"leg": leg, **detail(names[leg])} for leg in ("canonical", "rail_only", "mass_only", "compound")
        if names[leg] is not None and names[leg] in per
    ]
    same_run_nest = basis["nested"].get("same_run_single_nest_k4")
    best_lattice_k4 = (
        None if basis["best_lattice_name"] is None
        else per[basis["best_lattice_name"]]["survival_recovery"]["k4"]
    )
    return {
        "definition": (
            "the compound arm (graded inter-copy coupling + rungs + the shell mass channel) against "
            "the canonical body, with the rail-only leg (graded inter-copy coupling + rungs, "
            "canonical mass) and the mass-only leg (the field's own rail with the shell mass "
            "channel) as the two single-channel legs of its decomposition"
        ),
        "arms": table,
        "per_count": {
            count: {
                "canonical": attribution[count]["canonical"],
                "legs": attribution[count]["legs"],
                "deltas_vs_canonical": attribution[count]["deltas"],
                "additivity_residual": attribution[count]["additivity_residual"],
                "additive_within_tolerance": attribution[count]["additive_within_tolerance"],
            }
            for count in ("k2", "k4", "k8")
        },
        "tolerance": TOLERANCE_ATTRIBUTION_ADDITIVITY,
        "tolerance_origin": "survival.ATTRIBUTION_ADDITIVITY_TOLERANCE, read from that module",
        "rail_component_margin": MARGIN_RAIL_COMPONENT,
        "mass_component_margin": MARGIN_MASS_COMPONENT,
        "residual_definition": (
            "compound delta minus (rail-leg delta + mass-leg delta), so a value outside the tolerance "
            "means the two declared channels interact on this scaffold and the decomposition is not "
            "additive"
        ),
        "same_run_single_nest": {
            "arrangement": basis["nested_core_shell_name"],
            "measured_k4": same_run_nest,
            "cited_k4": CITED_K4_RECOVERY[NESTED_NAME],
        },
        "best_lattice_k4_vs_same_run_single_nest": {
            "best_lattice_name": basis["best_lattice_name"],
            "best_lattice_k4": best_lattice_k4,
            "same_run_single_nest_k4": same_run_nest,
            "difference": (None if best_lattice_k4 is None or same_run_nest is None
                           else float(best_lattice_k4 - same_run_nest)),
            "recovery_margin": MARGIN_RECOVERY,
        },
    }


def interaction_block(basis: Mapping[str, Any]) -> dict[str, Any]:
    """The compound arm's channels crossed: the mass leg against the declared rail weight."""
    scalars = basis["interaction"]
    rail_fit = scalars["rail_fit"]
    mass_fit = scalars["mass_fit"]
    cuts = scalars["rail_weight_cuts_the_mass_gain"]
    largest_step = scalars["mass_leg_largest_non_monotone_step"]
    threshold_gap = scalars["threshold_gap_k4"]
    monotone = (
        None if mass_fit is None else bool(mass_fit["monotone_decreasing"])
    )
    if cuts is None or monotone is None:
        shape = "not-measured"
    elif monotone:
        shape = "monotone"
    else:
        shape = "non-monotone or thresholded"
    return {
        "definition": (
            "the compound arm's two declared channels crossed: the shell mass channel on or off, "
            "against the ring-plus-rungs rail declared at a fraction of the geometry harness's "
            "flat-ladder budget, so the interaction can be read as a function of the declared rail "
            "weight instead of at the single declared lattice budget"
        ),
        "grid": {
            "pattern": INTERACTION_PATTERN,
            "declared_rail_fractions": scalars["fractions"],
            "rail_budget": basis["lattice_reference_weight"],
            "rail_weight_rule": (
                "the whole declared rail channel (ring pool links plus the 28 uniform rungs) is the "
                "declared fraction times the flat-ladder budget, split by the same canonical weight "
                "rule the lattice rung arms use; at fraction 0 no link and no rung is declared, so "
                "the rail is the field's own rail unchanged"
            ),
            "mass_channel_rule": (
                "projected_inv_mass = the geometry harness's core-shell shell metric "
                "0.7**ring_distance(pool, 3) with the mass channel on, and the canonical mass metric "
                "diag(1/inertances) with it off"
            ),
            "cells": [
                {
                    "rail_fraction": float(fraction),
                    "rail_leg_arm": next(
                        (row for row in scalars["rail_leg_rows"]
                         if row["rail_fraction"] == float(fraction)), None
                    ),
                    "mass_leg_arm": next(
                        (row for row in scalars["mass_leg_rows"]
                         if row["rail_fraction"] == float(fraction)), None
                    ),
                }
                for fraction in INTERACTION_RAIL_FRACTIONS
            ],
        },
        "fits": {
            "mass_leg_k4_vs_rail_fraction": mass_fit,
            "rail_leg_k4_vs_rail_fraction": rail_fit,
            "fit_rule": (
                "an ordinary least-squares straight line in the declared rail fraction through the "
                "four declared grid cells; the max absolute residual is the fit's worst miss, and "
                "the two half-slopes are the secant slopes over the first and second half of the "
                "declared fractions, whose gap measures how thresholded rather than gradual the "
                "damage is"
            ),
        },
        "interaction_terms": {
            "mass_minus_rail_k4_by_fraction": scalars["mass_minus_rail_k4_by_fraction"],
            "mass_gain_lost_to_the_full_rail_weight": cuts,
            "mass_leg_largest_non_monotone_step": largest_step,
            "mass_leg_monotone_decreasing": monotone,
            "half_slope_gap": threshold_gap,
            "spread_of_the_mass_leg_over_the_grid": (
                None if not scalars["mass_leg_rows"]
                else float(
                    max(row["k4"] for row in scalars["mass_leg_rows"])
                    - min(row["k4"] for row in scalars["mass_leg_rows"])
                )
            ),
            "spread_of_the_rail_leg_over_the_grid": (
                None if not scalars["rail_leg_rows"]
                else float(
                    max(row["k4"] for row in scalars["rail_leg_rows"])
                    - min(row["k4"] for row in scalars["rail_leg_rows"])
                )
            ),
        },
        "shape_of_the_damage": shape,
        "margins": {
            "cuts_the_mass_gain": MARGIN_MASS_COMPONENT,
            "monotone_step": MARGIN_WEIGHT_INVARIANCE,
            "linear_fit": MARGIN_RECOVERY,
            "half_slope_gap": MARGIN_RECOVERY,
            "grid_reproduces_the_declared_arms": MARGIN_DERIVATION_REPRODUCTION,
        },
        "reproductions": {
            "rows": scalars["reproduction_rows"],
            "max_absolute_difference": scalars["reproduction_max_absolute_difference"],
            "rule": (
                "the grid's two ends must be the already-declared arms they are declared to be: "
                "rail fraction 0 with the canonical mass metric is the un-runged body, rail fraction "
                "0 with the shell metric is the mass-only leg, rail fraction 1 is the lattice rung "
                "arm, and rail fraction 1 with the shell metric is the compound arm"
            ),
        },
        "boundary": (
            "the crossed arm is the bare-motif rail with the ring-plus-rungs lattice on top, not the "
            "lattice rung arm's own rail: at rail fraction 1 the grid reproduces the declared "
            "lattice rung arm, and the intermediate fractions are new declared arms, so the grid is "
            "a declared attenuation of one channel and not an interpolation of measured numbers"
        ),
    }


def nested_block(basis: Mapping[str, Any]) -> dict[str, Any]:
    """The nested-shell family: the depth x shell-law table and the two declared axes."""
    per = basis["per_arrangement"]
    rows: list[dict[str, Any]] = []
    for name in basis["nested_names"]:
        current = per[name]
        rows.append({
            "arrangement": name,
            "depth": current["nesting_depth"],
            "shell_law": current["shell_law"],
            "normalized": current["normalized"],
            "survival_recovery": current["survival_recovery"],
            "ipr_median": current["ipr_median"],
            "access_coverage_score": current["access_coverage_score"],
            "placement_write_read_spearman": current["placement_write_read_spearman"],
            "top7_drive_ports": current["top7_drive_ports"],
            "rail_l1": current["rail_l1"],
            "declared_link_channel_weight": current["declared_link_channel_weight"],
            "mass_metric_min": current["mass_metric_min"],
            "mass_metric_max": current["mass_metric_max"],
        })
    rows.sort(key=lambda item: (item["depth"], item["shell_law"], item["normalized"]))
    return {
        "definition": (
            "the nested core-shell motif at declared recursion depth 1 to 4 and declared shell laws, "
            "each level applying its own declared partition's decay to the pool graph and its own "
            "declared law to the shell metric"
        ),
        "levels": {
            "1": "the canonical core-shell partition (core pool 3), distance = canonical ring distance",
            **{
                str(level): (
                    f"core pool {NESTED_SHELL_LEVELS[level - 1][0]}, shell radius "
                    f"{NESTED_SHELL_LEVELS[level - 1][1]}, distance = |shell index difference|"
                )
                for level in range(2, len(NESTED_SHELL_LEVELS) + 1)
            },
        },
        "depths": [int(depth) for depth in NESTED_DEPTHS],
        "shell_law_values": {law: float(value) for law, value in SHELL_LAW_VALUES.items()},
        "shell_law_rule": (
            "mass(p) = prod_j law**s_j(p) with s_j the shell index of level j; the shell metric is "
            "positive and finite by construction (the check reports the measured minimum and maximum)"
        ),
        "normalization": (
            "one common factor rescales every normalized arm's declared link scales to the geometry "
            f"harness's flat-ladder budget ({basis['lattice_reference_weight']!r}); the depth-1 "
            "reference-law anchor is unnormalized by declaration"
        ),
        "base_rail": (
            "the nested arms are built on the geometry harness's own declared arrangement "
            "construction (canonical intra rings + the two strand bridges + the declared pool graph "
            "through geometry.rail_from_pool_links), which is the construction the cited "
            f"{NESTED_NAME!r} uses, and not on the field's default rail the lattice arms carry "
            "(which additionally holds the six canonical neck links)"
        ),
        "arms": rows,
        "axes": {
            "depth_axis": {
                "law": basis["nested"]["depth_axis_law"],
                "shallow": basis["nested"]["depth_shallow_name"],
                "deep": basis["nested"]["depth_deep_name"],
                "previous": basis["nested"]["depth_previous_name"],
                "deepest_vs_shallowest_k4_difference": basis["nested"][
                    "deepest_vs_shallowest_k4_difference"
                ],
                "depth3_to_depth4_k4_difference": basis["nested"]["depth3_to_depth4_k4_difference"],
                "saturation_margin": MARGIN_DEPTH_SATURATION,
            },
            "shell_law_axis": {
                "depth": basis["nested"]["law_axis_depth"],
                "phi": basis["nested"]["law_axis_phi_name"],
                "uniform": basis["nested"]["law_axis_uniform_name"],
                "phi_minus_uniform_k4_difference": basis["nested"][
                    "deepest_phi_vs_uniform_k4_difference"
                ],
            },
        },
        "same_run_single_nest": {
            "arrangement": basis["nested_core_shell_name"],
            "measured_k4": basis["nested"]["same_run_single_nest_k4"],
            "cited_k4": basis["nested"]["cited_single_nest_k4"],
            "absolute_difference": (
                None if basis["nested"]["same_run_single_nest_k4"] is None
                else float(abs(
                    basis["nested"]["same_run_single_nest_k4"] - basis["nested"]["cited_single_nest_k4"]
                ))
            ),
        },
        "depth1_reference_law_anchor": {
            "arrangement": basis["nested_anchor_name"],
            "rule": "depth 1 under the canonical partition with the reference law (0.7), unnormalized",
            "measured_k4": basis["nested"]["anchor_k4"],
            "cited_k4": basis["nested"]["cited_single_nest_k4"],
            "absolute_k4_difference_to_cited": basis["nested"]["anchor_vs_cited_k4_difference"],
            "absolute_k4_difference_to_same_run_nest": basis[
                "nested"]["anchor_vs_same_run_k4_difference"
            ],
            "rail_max_absolute_difference_to_the_cited_construction": basis[
                "nested_anchor_rail_max_absolute_difference"
            ],
            "measured_ipr_median": basis["nested"]["anchor_ipr_median"],
            "cited_ipr_median": basis["nested"]["cited_single_nest_ipr_median"],
            "absolute_ipr_median_difference_to_cited": basis["nested"][
                "anchor_vs_cited_ipr_median_difference"
            ],
        },
        "declared_weight_max_relative_deviation": basis["nested_total_weight_max_relative_deviation"],
        "depth_normalization_control": (
            _nested_normalization_control(basis)
        ),
    }


def _nested_normalization_control(basis: Mapping[str, Any]) -> dict[str, Any]:
    """The depth family re-declared under the anchor's own conditions, i.e. unnormalized.

    The equal-budget family's depth axis is flat; this block carries the same depth axis declared
    without the normalization, so the receipt can say whether depth is inert or whether the flat
    axis belongs to the normalization itself.
    """
    raw = basis["nested_raw"]
    depth_axis_law = basis["nested"]["depth_axis_law"]
    verdict = _nested_normalization_verdict(basis, raw)
    return {
        "declaration": (
            "the same depth family (the reference law and the unity shell law at the same declared "
            "depths) declared again without the equal-total normalization, i.e. under the depth-1 "
            "reference-law anchor's own conditions: each level's declared link scales are written "
            "as the geometry harness's own construction produces them, with no common rescaling "
            "factor; the anchor itself is the depth-1 reference-law arm of this family"
        ),
        "equal_budget_family": (
            "the normalized depth family, one common factor to the geometry harness's flat-ladder "
            f"budget ({basis['lattice_reference_weight']!r})"
        ),
        "raw_declared_link_channel_rows": raw["raw_vs_normalized_declarations"],
        "laws_with_an_equal_budget_counterpart": raw["laws_with_an_equal_budget_counterpart"],
        "laws_without_an_equal_budget_counterpart": raw[
            "laws_without_an_equal_budget_counterpart"
        ],
        "min_relative_declared_link_difference_from_the_equal_budget_family": raw[
            "min_relative_declared_link_difference"
        ],
        "declaration_margin": MARGIN_RAW_DECLARATION,
        "reference_law_raw_rows": raw["reference_law_rows"],
        "uniform_law_raw_rows": raw["uniform_law_rows"],
        "uniform_law_equal_budget_rows": raw["normalized_uniform_rows"],
        "depth_axis_law": depth_axis_law,
        "spreads": {
            "reference_law_raw_k4": raw["reference_law_k4_spread"],
            "reference_law_raw_k8": raw["reference_law_k8_spread"],
            "uniform_law_raw_k4": raw["uniform_law_k4_spread"],
            "uniform_law_raw_k8": raw["uniform_law_k8_spread"],
            "uniform_law_equal_budget_k4": raw["normalized_uniform_k4_spread"],
            "uniform_law_equal_budget_k8": raw["normalized_uniform_k8_spread"],
            "raw_minus_equal_budget_k4": raw["raw_minus_normalized_k4_spread"],
        },
        "spread_margin": MARGIN_RECOVERY,
        "verdict": verdict,
    }


def _nested_normalization_verdict(
    basis: Mapping[str, Any], raw: Mapping[str, Any]
) -> dict[str, Any]:
    """Where the flat depth axis belongs: to depth itself or to the equal-total normalization."""
    equal_budget_spread = raw["normalized_uniform_k4_spread"]
    raw_uniform_spread = raw["uniform_law_k4_spread"]
    raw_reference_spread = raw["reference_law_k4_spread"]
    equal_budget_flat = (
        None if equal_budget_spread is None
        else bool(equal_budget_spread <= MARGIN_RECOVERY)
    )
    raw_uniform_moves = (
        None if raw_uniform_spread is None
        else bool(raw_uniform_spread >= MARGIN_RECOVERY)
    )
    raw_reference_moves = (
        None if raw_reference_spread is None
        else bool(raw_reference_spread >= MARGIN_RECOVERY)
    )
    anchor_k4 = basis["nested"]["anchor_k4"]
    deep_raw_reference = (
        None if not raw["reference_law_rows"] else raw["reference_law_rows"][-1]["k4"]
    )
    deepest_vs_anchor = (
        None if deep_raw_reference is None or anchor_k4 is None
        else float(deep_raw_reference - anchor_k4)
    )
    if None in (equal_budget_flat, raw_uniform_moves, raw_reference_moves):
        place = "not-measured"
    elif equal_budget_flat and not raw_uniform_moves:
        place = "depth itself"
    elif equal_budget_flat and raw_uniform_moves:
        place = "the equal-total normalization"
    else:
        place = "the unnormalized reference-law family only"
    reference_has_counterpart = bool(
        raw["laws_with_an_equal_budget_counterpart"]
        and NESTED_REFERENCE_LAW in raw["laws_with_an_equal_budget_counterpart"]
    )
    readings: list[str] = []
    if equal_budget_flat is not None and raw_uniform_moves is not None:
        if equal_budget_flat and not raw_uniform_moves:
            readings.append(
                "at the unity shell law the depth axis is flat with the equal-total normalization "
                f"({equal_budget_spread!r}) and flat without it ({raw_uniform_spread!r}), so the flat "
                "axis at that law is a property of the declared depth partitions and not of the "
                "normalization"
            )
        elif equal_budget_flat and raw_uniform_moves:
            readings.append(
                "at the unity shell law the depth axis is flat under the equal-total normalization "
                f"({equal_budget_spread!r}) and separates the depths without it "
                f"({raw_uniform_spread!r}), so the flat axis at that law is the normalization's doing"
            )
    if raw_reference_moves is not None and raw_reference_moves:
        readings.append(
            "the unnormalized reference-law family is strongly depth-dependent "
            f"({raw_reference_spread!r} across the declared depths, the depth-1 anchor at "
            f"{anchor_k4!r} and the deepest at "
            f"{None if deep_raw_reference is None else deep_raw_reference!r}), and "
            + (
                "the reference law is declared unnormalized only, so no equal-budget replay of that "
                "law exists in the declared scope and the depth dependence is reported without "
                "attribution"
                if not reference_has_counterpart else
                "an equal-budget replay of that law is declared and can be read beside it"
            )
        )
    return {
        "question": (
            "is the flat depth axis inert in depth, or is the flat axis produced by the equal-total "
            "normalization? the two families differ in exactly that normalization, so the flat axis "
            "belongs to the normalization when the unnormalized replay of the same depth axis "
            "separates the depths while the equal-budget replay does not, and belongs to depth "
            "itself when both replays are flat"
        ),
        "flat_depth_axis_under_equal_budget": equal_budget_flat,
        "flat_depth_axis_without_the_normalization_reference_law": (
            None if raw_reference_moves is None else bool(not raw_reference_moves)
        ),
        "flat_depth_axis_without_the_normalization_unity_law": (
            None if raw_uniform_moves is None else bool(not raw_uniform_moves)
        ),
        "reference_law_has_an_equal_budget_counterpart": reference_has_counterpart,
        "equal_budget_uniform_k4_spread": equal_budget_spread,
        "raw_uniform_k4_spread": raw_uniform_spread,
        "raw_reference_law_k4_spread": raw_reference_spread,
        "raw_minus_equal_budget_k4_spread": raw["raw_minus_normalized_k4_spread"],
        "deepest_raw_reference_law_k4_minus_anchor_k4": deepest_vs_anchor,
        "place_of_the_flat_axis": place,
        "readings": readings,
        "rule": (
            "the unnormalized family's declared link channels are written as the harness's own "
            "construction produces them and differ from the equal-budget family's at the same depth "
            "and law by at least the declared margin, so the control really varies the "
            "normalization and not only the name; the two families share their depth levels and "
            "their base rail, and the declared link channels are compared on the shell laws that "
            "both families declare (the reference law is declared unnormalized only, so it has no "
            "equal-budget counterpart to compare against and is reported as such)"
        ),
    }


def continuity_firing_control(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Firing control for the continuity rows: move one measured value out of the allowance."""
    for row in rows:
        if row["quantity"] != "ipr_median":
            continue
        moved = float(row["cited"]) + 10.0 * float(row["allowance"])
        return {
            "id": row["id"],
            "mutation": "set the measured value to the cited value plus ten times the declared allowance",
            "measured_moved": moved,
            "verdict_before": bool(row["holds"]),
            "verdict_after": bool(abs(moved - float(row["cited"])) <= row["allowance"]),
            "flips": bool(row["holds"] and not abs(moved - float(row["cited"])) <= row["allowance"]),
        }
    return None


# --------------------------------------------------------------------------
# receipt
# --------------------------------------------------------------------------
def declaration_block(config: LatticeConfig) -> dict[str, Any]:
    return {
        "question": (
            "the body is already a three-dimensional double helix; do the derived geometry's laws "
            "-- the longitudinal station spacing (hypothesis a), the weight grading applied to the "
            "derived couplings (hypothesis b), and a lattice of copies of the motif with a declared "
            "inter-copy spacing law (hypothesis c) -- move the existing geometry, survival and "
            "placement measures, and does a golden-ratio law move them most?"
        ),
        "scope": (
            "bounded numerical exploration of declared geometries over the canonical seven-pool "
            "resonant page; every arrangement is a candidate scaffold, not a memory, "
            "task-performance or semantic-content claim"
        ),
        "scope_name": config.scope,
        "random_seed": int(config.seed),
        "phi": float(PHI),
        "fibonacci_weights": list(FIBONACCI_WEIGHTS),
        "spacing_laws": {
            law: {
                "rule": spacing_rule(law),
                "stations_report": station_positions(config.ports_per_pool, law)[1],
            }
            for law in SPACING_LAWS
        },
        "coupling_laws": {
            law: {
                "rule": coupling_rule(law),
                "factors_at_positions_0_to_7": [
                    float(coupling_factor(law, index)) for index in range(8)
                ],
            }
            for law in COUPLING_LAWS
        },
        "inter_copy_laws": {
            law: {
                "rule": inter_copy_rule(law),
                "declared_scales_on_grid_crosslinks": [
                    float(value) for value in inter_copy_scales("grid-crosslinks", law, seed=config.seed)
                ],
            }
            for law in INTER_COPY_LAWS
        },
        "patterns": {
            pattern: {
                "offsets": list(PATTERN_OFFSETS[pattern]),
                "cross_links": [list(pair) for pair in CROSS_LINKS] if pattern == "grid-crosslinks" else [],
                "declared_link_count": len(pattern_edges(pattern)),
                "declared_edges": [
                    {"source": int(a), "destination": int(b), "law_index": int(k), "family": family}
                    for a, b, k, family in pattern_edges(pattern)
                ],
            }
            for pattern in PATTERNS
        },
        "unit_cell": (
            "one declared position of the built-in motif: both strand coordinates at that station, "
            "the built-in intra ring and its neighbouring couplings, and (for the rung arms) a "
            "declared strand-to-strand rung in the Yang->Yin orientation with its antisymmetric "
            "reverse entry; cell-to-cell coupling is the declared pool link, which "
            "geometry.pool_link_port_pairs writes as one Yang hop and the counter-oriented Yin hop "
            "for that pool pair"
        ),
        "strand_bridges": (
            "the field's own rail holds exactly two entries between a declared position and its "
            "partner strand coordinate, and they are the two circuit bridges that close the ring: "
            "pool 6's last Yang port (coordinate 27) -> pool 0's first Yin port (coordinate 55), and "
            "pool 0's last Yin port (coordinate 28) -> pool 6's first Yang port (coordinate 0); every "
            "other strand-pair entry of the field's own rail is zero. A declared rung set therefore "
            "re-declares those two positions' strand pairs as well as adding the other 26, and the "
            "report lists the replaced canonical entries and their measured magnitudes"
        ),
        "lattice_of_copies": (
            "the seven declared positions of the built-in motif are the copies, read as the "
            "seven pool-local Yang/Yin port pairs of the one helix rather than as seven separated "
            "spatial cells; 'ring' couples every copy to the next (a circulant adjacency, the nearest "
            "expressible regular grid direction on the one-dimensional pool coordinate), 'grid' adds "
            "the offset-2 direction (two regular directions), and 'grid-crosslinks' adds three long "
            "cross-links at ring distance 3; every lattice arm keeps the built-in motif rail "
            "unchanged underneath.  Three disjoint cells of seven pools each are inexpressible: the "
            "pool count is fixed at exactly seven"
        ),
        "rung_laws": {
            law: {
                "rule": rung_law_rule(law),
                "raw_scales_at_positions_0_to_6": [
                    float(rung_law_scale(law, position)) for position in range(7)
                ],
                "raw_total_l1": float(sum(abs(value) for value in rung_law_scales(law))),
                "declared_channel_total_rail_units": motif_reference_weight(),
                "normalized_scales_at_positions_0_to_6_phi_arm":
                    [
                        float(value) * motif_reference_weight()
                        / float(sum(abs(scale) for scale in rung_law_scales(law)))
                        for value in rung_law_scales(law)[:7]
                    ],
            }
            for law in RUNG_LAWS
        },
        "rung_law_controls": {
            "laws": {
                law: {
                    "rule": rung_law_rule(law),
                    "raw_scales_at_positions_0_to_6": [
                        float(rung_law_scale(law, position)) for position in range(7)
                    ],
                    "raw_total_l1": float(sum(abs(value) for value in rung_law_scales(law))),
                    "declared_channel_total_rail_units": motif_reference_weight(),
                }
                for law in RUNG_CONTROL_LAWS
            },
            "arms": [
                {"arrangement": arm, "coupling_law": coupling, "rung_law": law}
                for arm, coupling, law in MOTIF_RUNG_LAW_CONTROL_ARMS
            ],
            "declared_positions": int(POOLS * PORTS_PER_POOL),
            "single_position_index": int(SINGLE_RUNG_POSITION),
            "centred_peak_midpoint": float(CENTRED_RUNG_MIDPOINT),
            "shuffle_seed": int(RUNG_CONTROL_SEED),
            "question": (
                "the phi rung law is an unbounded one-sided ramp; these laws are declared at the same "
                "positions and the same declared rung channel total, so the measured k4 gain can be "
                "attributed to the ramp's steepness or to phi's own way of placing the same weights "
                "rather than to rung presence alone"
            ),
            "declared_channel_convention": (
                "every control law is declared exactly as the two primary rung laws are: raw scales "
                "in the rail's own units, normalized to the motif body's own rail L1, written at all "
                "28 declared positions in the Yang->Yin orientation"
            ),
        },
        "interaction_grid": {
            "pattern": INTERACTION_PATTERN,
            "arms": [
                {"arrangement": arm, "declared_rail_fraction": float(fraction), "mass_channel": mass}
                for arm, fraction, mass in INTERACTION_ARMS
            ],
            "declared_rail_fractions": [float(value) for value in INTERACTION_RAIL_FRACTIONS],
            "rail_budget": lattice_reference_weight(),
            "rail_declaration": (
                "the whole declared rail channel is the declared fraction times the geometry "
                "harness's flat-ladder budget, split between the ring pool links and the 28 uniform "
                "rungs by the same canonical weight rule the lattice rung arms use; at declared "
                "fraction 0 no link and no rung is declared, so the rail is the field's own rail "
                "unchanged and the cell is the un-runged body (a zero declared scale is not a "
                "declaration)"
            ),
            "mass_channel_declaration": (
                "the mass leg declares projected_inv_mass = the geometry harness's core-shell shell "
                "metric 0.7**ring_distance(pool, 3); the no-mass leg leaves projected_inv_mass at "
                "the canonical diag(1/inertances) metric the survival harness uses"
            ),
            "question": (
                "the attribution shows the mass leg carrying the survival gain while the rail leg "
                "costs recovery and the compound lands far from the sum of the two; this grid "
                "crosses the two channels so the rail's damage on the mass channel can be read as a "
                "function of the declared rail weight"
            ),
        },
        "nested_normalization_control": {
            "arms": [
                {"arrangement": arm, "depth": int(depth), "shell_law": law}
                for arm, depth, law in NESTED_RAW_ARMS
            ],
            "anchor": {"arrangement": NESTED_ANCHOR_NAME, "depth": 1, "shell_law": NESTED_REFERENCE_LAW},
            "laws": list(NESTED_RAW_LAWS),
            "depths": [int(depth) for depth in NESTED_DEPTHS],
            "normalization": (
                "these arms are declared without the equal-total normalization: each level's declared "
                "link scales are written as the geometry harness's own construction produces them, "
                "with no common rescaling factor, i.e. under the depth-1 reference-law anchor's own "
                "conditions"
            ),
            "question": (
                "the equal-budget depth family is flat to a few parts in the fifth decimal place; this "
                "family repeats the same depth axis unnormalized, so the receipt can say whether depth "
                "is inert or whether the flat axis belongs to the normalization"
            ),
        },
        "rung_channel_convention": (
            "the bare-motif rung channel is declared in the rail's own units: the writer writes the "
            "declared scale itself as the rail entry, so the declared rung channel L1 is normalized "
            "to the motif body's own rail L1 (one rung channel per declaration, both rung laws at "
            "the same declared total).  The phi-graded law is an unbounded geometric ramp "
            "(w_j = phi**j over j = 0..27), so after normalization that declared channel is "
            "dominated by the last declared position; the measured minimum and maximum are reported "
            "on every rung arm.  The earlier lattice rung arms declare their rung scales under the "
            "canonical weight rule and write them directly, so their written rung channel is much "
            "larger than its canonical-rule share of the lattice budget; that path is unchanged and "
            "its held result is cited rather than re-measured"
        ),
        "nested_family": {
            "depths": [int(depth) for depth in NESTED_DEPTHS],
            "shell_laws": {law: float(value) for law, value in SHELL_LAW_VALUES.items()},
            "levels": {
                str(level): (
                    "the canonical core-shell partition (core pool 3), distance = canonical ring "
                    "distance" if level == 1 else
                    f"core pool {NESTED_SHELL_LEVELS[level - 1][0]}, shell radius "
                    f"{NESTED_SHELL_LEVELS[level - 1][1]}, distance = |shell index difference|"
                )
                for level in range(1, len(NESTED_SHELL_LEVELS) + 1)
            },
            "shell_metric_rule": "mass(p) = prod_j law**s_j(p) over the declared levels' shell indices",
            "normalization": (
                "one common factor rescales every normalized arm's declared link scales to the "
                f"geometry harness's flat-ladder budget ({lattice_reference_weight()!r})"
            ),
            "base_rail": (
                "built on the geometry harness's own declared arrangement construction (canonical "
                "intra rings + the two strand bridges + the declared pool graph through "
                "geometry.rail_from_pool_links), which is the construction the cited "
                f"{NESTED_NAME!r} uses; the lattice arms instead keep the field's default rail, "
                "which additionally holds the six canonical neck links"
            ),
            "depth_axis": {
                "law": NESTED_DEPTH_AXIS_LAW,
                "depths": [int(depth) for depth in NESTED_DEPTHS],
            },
            "shell_law_axis": {"depth": int(NESTED_LAW_AXIS_DEPTH), "laws": list(SHELL_LAWS)},
            "depth1_reference_law_anchor": {
                "name": NESTED_ANCHOR_NAME,
                "law": NESTED_REFERENCE_LAW,
                "law_value": float(SHELL_LAW_VALUES[NESTED_REFERENCE_LAW]),
                "normalized": False,
                "rule": nested_rule(1, NESTED_REFERENCE_LAW, normalized=False),
                "cited_figures": {
                    "survival_k4_recovery": CITED_K4_RECOVERY[NESTED_NAME],
                    "ipr_median": CITED_IPR_MEDIAN[NESTED_NAME],
                },
            },
        },
        "attribution": {
            "canonical": ATTRIBUTION_CANONICAL_NAME,
            "rail_only_leg": ATTRIBUTION_RAIL_ONLY_NAME,
            "mass_only_leg": ATTRIBUTION_MASS_ONLY_NAME,
            "compound": ATTRIBUTION_COMPOUND_NAME,
            "residual": (
                "compound delta minus (rail-leg delta + mass-leg delta); the declared tolerance is "
                "the survival harness's own additivity tolerance, and a residual outside it means "
                "the two channels interact and the decomposition is not additive"
            ),
            "margins": {
                "rail_component": MARGIN_RAIL_COMPONENT,
                "mass_component": MARGIN_MASS_COMPONENT,
                "additivity_tolerance": TOLERANCE_ATTRIBUTION_ADDITIVITY,
                "origin": "survival.RAIL_COMPONENT_MARGIN, survival.MASS_COMPONENT_MARGIN, "
                          "survival.ATTRIBUTION_ADDITIVITY_TOLERANCE, read from that module",
            },
            "same_run_single_nest": (
                f"the cited {NESTED_NAME!r} is measured in this run as well, so the best-lattice "
                "contrast and the depth-1 anchor contrast are against the same run's own row"
            ),
        },
        "spectrum_reporting": (
            "localization is reported as the inverse participation ratio, and a localization claim is "
            "never a spectrum-similarity claim: every arm also carries the beta=0 generator's real "
            "eigenvalue range, its maximum growth rate, its complex and real mode counts, its |Im| "
            "and complex-frequency ranges, its distinct-frequency count at 0.01, its localized-mode "
            "fraction, the phi-band and octave-band self-similarity indices, the log-periodic order "
            "at each declared contrast ratio, and per-mode IPR.  The declared checks that read the "
            "spectrum read those quantities, not the median IPR alone"
        ),
        "continuity_scope": (
            "the continuity rows that reproduce numbers already frozen in the geometry and survival "
            "receipts are measured on the geometry harness's own imported reference arrangements "
            "(helix7, nested-core-shell, recursive-paired-loops), which this runner constructs "
            "through geometry.build_profile and does not modify; three further rows reproduce the "
            "same cited figures on this runner's own derived motif rail, and one row reproduces the "
            "cited nested-core-shell figure on the depth-1 reference-law anchor"
        ),
        "normalization": {
            "motif_reference_weight": motif_reference_weight(),
            "motif_origin": "the field's own default rail L1, measured from ResonantProfile()",
            "lattice_reference_weight": lattice_reference_weight(),
            "lattice_origin": "geometry.arrangement_named('flat-ladder').pool_links under the "
                              "canonical metric rule, i.e. the geometry harness's own declared budget",
            "rule": "one common factor rescales the declared scales of an arm so its declared total "
                    "coupling weight matches its reference; the spacing-law and coupling-law ratios "
                    "are preserved because the factor is common",
            "mass_normalization": "projected_inv_mass = None for the rail leg, i.e. the canonical "
                                  "mass metric diag(1/inertances) the survival harness uses; the "
                                  "declared -mass and nested arms instead carry a declared per-port "
                                  "inverse-mass diagonal",
            "audit": (
                "every arm reports its declared channels in the units it declares them in: the raw "
                "declared L1 before normalization, the one common scale factor, the projected "
                "channel totals, the measured rail L1, the mass metric's measured minimum, maximum "
                "and L1, and the absolute difference between the measured rail L1 and the L1 the "
                "declared channels account for.  The identity behind that difference is "
                "declared_rail_l1 = base_rail_l1 - 2*cleared_entry_l1 + 2*(link_channel + "
                "rung_channel): the rail is antisymmetric, so one declared entry contributes its "
                "magnitude to two matrix entries, and every cleared or written entry is measured "
                "rather than assumed"
            ),
        },
        "survival": {
            "counts": [int(count) for count in config.survival_counts],
            "config": config.durability_config().as_dict(),
            "recovery_margin": MARGIN_RECOVERY,
            "recovery_margin_origin": "survival.PROFILE_RECOVERY_MARGIN, read from that module",
        },
        "placement": {
            "selection_depth": int(config.selection_depth),
            "top_placements": int(config.top_placements),
        },
        "margins": {
            "recovery": MARGIN_RECOVERY, "ipr": MARGIN_IPR, "access_coverage": MARGIN_ACCESS,
            "self_similarity": MARGIN_SELF_SIMILARITY, "phi_order": MARGIN_PHI_ORDER,
            "spearman": MARGIN_SPEARMAN, "overlap_ports": MARGIN_OVERLAP_PORTS,
            "weight_invariance": MARGIN_WEIGHT_INVARIANCE, "mass_invariance": MARGIN_MASS_INVARIANCE,
            "derivation_reproduction": MARGIN_DERIVATION_REPRODUCTION,
            "continuity_allowance": CONTINUITY_ALLOWANCE,
            "rail_component": MARGIN_RAIL_COMPONENT, "mass_component": MARGIN_MASS_COMPONENT,
            "attribution_additivity": TOLERANCE_ATTRIBUTION_ADDITIVITY,
            "depth_saturation": MARGIN_DEPTH_SATURATION,
            "rung_channel": MARGIN_WEIGHT_INVARIANCE,
            "rung_orientation": MARGIN_DERIVATION_REPRODUCTION,
            "rail_identity": MARGIN_WEIGHT_INVARIANCE,
        },
        "margins_origin": (
            "recovery is survival.PROFILE_RECOVERY_MARGIN, the two component margins and the "
            "additivity tolerance are the survival harness's own declared margins, and the "
            "remaining margins are this runner's declared measurement resolutions"
        ),
        "instrument_reuse": {
            "geometry": [
                "build_profile", "arrangement_named", "canonical_parts", "pool_link_port_pairs",
                "_edge_weight", "realized_pair_strength", "core_shell_inverse_mass",
                "linear_generator", "_generator_spectrum", "spectrum_metrics", "retention_metrics",
                "access_metrics", "hook_effect", "canonical_digest", "content_digest", "_jsonable",
            ],
            "durability": [
                "DurabilityConfig", "arm_declarations", "capture_items", "run_arm",
                "overlap_matrix", "ORTHOGONALITY_ALLOWANCE",
            ],
            "survival": ["compact_arm_record", "PROFILE_RECOVERY_MARGIN", "RAIL_COMPONENT_MARGIN",
                         "MASS_COMPONENT_MARGIN", "ATTRIBUTION_ADDITIVITY_TOLERANCE"],
            "placement": [
                "_measure", "PlacementConfig", "_top_set", "set_overlap", "arrangement_dependence",
                "DEFAULT_SELECTION_DEPTH", "TOP_PLACEMENTS",
            ],
            "geometry_rail_builder": ["rail_from_pool_links", "_ring_distance"],
        },
        "boundary": [
            "Every number is a geometric, spectral, survival or placement proxy on a declared scaffold.",
            "Hypothesis (a) is measured as the rail the field's own weight rule assigns to a "
            "re-spaced geometry; it is not a claim that the profile carries site positions.",
            "Hypothesis (b) is measured as a grading of the derived weights at the built-in "
            "stations, and is reported separately from hypothesis (a).",
            "The spectrum is the beta=0 linearization of the declared profile, not the evolving nonlinear body.",
            "The survival figures are shares of a measured deposit along a measured direction under "
            "the durability harness's declared activity, not recall quality and not retrieval.",
            "The placement figures are modal access on a declared linear scaffold, not a task.",
            "The rung arms are two-family declarations and their rung channels are not at one "
            "magnitude: the bare-motif rung channel is declared in the rail's own units at the motif "
            "body's own rail L1, while the earlier lattice rung arms declare their rung scales under "
            "the canonical weight rule and carry them inside the lattice budget.  Within-family "
            "contrasts are at one declared budget each; cross-family rung magnitudes are not "
            "comparable and are reported as measured numbers, not as a controlled contrast.",
            "The nested arms are built on the geometry harness's own declared arrangement "
            "construction (intra rings + the two strand bridges + the declared pool graph), which is "
            "the construction the cited nested-core-shell uses, while the lattice arms keep the "
            "field's default rail with its six neck links; the two families' base rails therefore "
            "differ by those six entries and only within-family contrasts are controlled.",
            "The attribution decomposition is a measurement, not an assumption of linearity: the "
            "residual is reported per survival count, and a residual outside the declared tolerance "
            "is the measured statement that the two channels interact.",
            "The nested family's shell metric is declared for its own arms; the nested arms do not "
            "carry the canonical mass metric, so their survival figures are not comparable with the "
            "motif and lattice rail legs whose mass metric is diag(1/inertances).",
            "No arrangement claim here is a claim about memory utility, learning, or task performance.",
        ],
    }


def limitations() -> list[str]:
    return [
        "pools is fixed at exactly 7, there is one helix, and no field carries site positions: a "
        "literal three-dimensional bubble lattice with a lattice constant, several cells at "
        "separate spatial sites, or a bubble interior as state is inexpressible.  The expressible "
        "forms are (i) the rail the field's own weight rule assigns to re-spaced coordinates, "
        "declared through projected_transport, and (ii) a coupling lattice over the 28 declared "
        "positions.",
        "profile.edges is ignored whenever projected_transport is set, so every arm re-declares the "
        "structure it uses through the hooks and the topology field is metadata for it; the hook "
        "probe records that measured consequence per arrangement.",
        "projected_transport is one antisymmetric matrix on the 56 strand coordinates, so a declared "
        "rung can only be an oriented strand-pair entry: a symmetric bidirectional exchange between "
        "the strands would cancel against its own reverse entry and cannot be declared.",
        "projected_inv_mass is per-port or a 56x56 SPD matrix, so the shell metric used by the "
        "declared mass arms is a diagonal per-position form.",
        "A geometric station law holds the two endpoint stations and the extent fixed and re-spaces "
        "only the interior, because the extent is what the angle and radius laws are written "
        "against; a law that also moved the endpoints would change the helix pitch, which is a "
        "different hypothesis and is not measured here.",
        "The band self-similarity test reads 112 finite modes; a finite truncation approximates, it "
        "does not realize, a singular-continuous spectrum, and no band statistic here is a claim "
        "about a self-similar measure on an infinite lattice.",
        "The declared inter-copy coupling is a coupling ratio, not a distance: a phi-graded coupling "
        "sequence and a phi-spaced lattice are different objects, and only the former is declared "
        "at the copy level here.",
        "The bare-motif rung channel is written as declared scales in the rail's own units, not as "
        "canonical weight rule values at the rung port pairs, because that is the convention "
        "set_rungs has always used; the rung channel is therefore a declared rail magnitude whose "
        "canonical-rule weight is reported separately where it differs, and the rung channel's "
        "physical reading (a coupling strength between the two strands) holds only up to that "
        "declared convention.",
        "The phi-graded rung law is an unbounded geometric ramp over the 28 declared positions, so "
        "after normalization it concentrates almost the whole declared rung channel at one end of "
        "the helix (the measured minimum and maximum scale are reported per arm).  It is one declared "
        "rung law, not a phi-spaced interval set and not a bounded grading.",
        "The nested family's extra levels are declared partitions on the same seven pools, not "
        "additional spatial shells: no field here carries per-pool radii, so a level's partition is "
        "expressed only through its decay law on the pool graph and its law on the mass diagonal.",
        "The nested depth axis and shell-law axis are read at declared fixed settings "
        "(law 'uniform' for depth, depth 4 for the law), so the reported contrasts are one slice of "
        "the depth x law product rather than its full interaction.",
        "The rung-law controls are declared laws of the same declared channel total, not a search: "
        "six shapes are declared alongside the two primary laws, and a shape that beats the phi ramp "
        "here says phi is not the only steep shape that moves the survival k4 figure, not that some "
        "other shape is the best of all possible shapes.",
        "The interaction grid attenuates one declared rail channel against one declared mass "
        "channel: the intermediate rail fractions are new declared arrangements rather than "
        "interpolations, the rail is always the ring-plus-rungs pattern, and a monotone or "
        "thresholded reading of the grid holds for this pattern at these declared fractions only.",
        "The unnormalized nested arms differ from the equal-budget family in exactly one declared "
        "thing, the common rescaling factor, so a depth contrast that appears only in the "
        "unnormalized family attributes the flat equal-budget axis to the normalization's declared "
        "scale rather than to the depth partitions themselves; both families share their depth "
        "levels and their base rail, the equal-budget comparisons are read at the shell laws both "
        "families declare (the reference law is declared unnormalized only), and no other "
        "construction difference is declared.",
    ]


def assert_finite(value: Any, path: str = "receipt") -> None:
    """No non-finite number may reach the receipt: the digest forbids it and so does the report."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            assert_finite(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_finite(item, f"{path}[{index}]")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ResonantNumericalError(f"non-finite number at {path}")


def build_receipt(config: LatticeConfig | None = None) -> dict[str, Any]:
    """Run every declared measurement and assemble the receipt."""
    config = config or LatticeConfig()
    started = time.perf_counter()
    names = config.names() + reference_arrangements()
    records = [measure_arrangement(name, config) for name in names]
    basis = comparison_basis(records)
    origin = float(basis["rail_leg_mass_metric_distinct_variant_count"] - 1)
    basis["rail_leg_mass_metric_extra_variant_count"] = origin
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "recon": recon_block(),
        "declarations": declaration_block(config),
        "arrangements": records,
        "placement_arrangement_dependence": placement.arrangement_dependence(records, 7),
        "order_parameter_positive_control": synthetic_order_controls(),
        "comparisons": {
            "basis": basis,
            "checks": evaluate_checks(basis),
            "firing_controls": firing_controls(basis),
            "silenced_controls": silenced_controls(basis),
            "invariance_checks_without_silenced_control": [
                check.id for check in margin_checks() if check.kind == KIND_INVARIANCE
            ],
            "checks_summary": {
                "total": len(evaluate_checks(basis)),
                "holding": sum(1 for row in evaluate_checks(basis) if row["holds"]),
                "failing": sum(1 for row in evaluate_checks(basis) if row["holds"] is False),
                "failing_ids": [
                    row["id"] for row in evaluate_checks(basis) if row["holds"] is False
                ],
                "refuted": sum(1 for row in evaluate_checks(basis) if row["holds"] is False),
                "refuted_ids": [
                    row["id"] for row in evaluate_checks(basis) if row["holds"] is False
                ],
                "rung_survival_k4_verdicts": [
                    {
                        "check": row["id"],
                        "covers_the_arm": (
                            check_arm_coverage(basis).get(row["id"], {}).get("target_arm")
                        ),
                        "compared_against": (
                            check_arm_coverage(basis).get(row["id"], {}).get("baseline_arm")
                        ),
                        "margin": row["margin"],
                        "measured_quantity": row["quantity"],
                        "verdict": row["holds"],
                    }
                    for row in evaluate_checks(basis)
                    if row["id"] in (
                        "motif_rungs_change_survival_k4",
                        "motif_phi_rungs_change_survival_k4",
                    )
                ],
                "definition": (
                    "a declared margin check that the measurement refutes is reported as refuted "
                    "with its measured quantity, not dropped; the firing control for the same check "
                    "moves its own measured number and must flip the verdict, so a refuted check is "
                    "still shown to be falsifiable in both directions.  The refuted rows are listed "
                    "in comparisons.refuted_declared_hypotheses, each naming the arrangement it "
                    "covers where the runner can say so, and rung_survival_k4_verdicts carries the "
                    "two bare-rung arms' rows side by side because their verdicts differ"
                ),
            },
            "refuted_declared_hypotheses": refuted_declared_hypotheses(basis),
            "continuity": continuity_rows(records),
            "continuity_firing_control": continuity_firing_control(continuity_rows(records)),
            "rung": rung_report_block(basis),
            "interaction": interaction_block(basis),
            "nested": nested_block(basis),
            "attribution": attribution_block(basis),
            "content_digest_definition": (
                "sha256 of the canonical JSON (sorted keys, no insignificant whitespace, "
                "allow_nan=False) of the measured body with wall-clock fields stripped, before the "
                "digest itself is attached"
            ),
        },
        "limitations": limitations(),
        "runtime_seconds": None,
        "receipt_sha256": None,
    }
    receipt["runtime_seconds"] = time.perf_counter() - started
    assert_finite(receipt)
    receipt["receipt_sha256"] = content_digest(receipt)
    return receipt


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def format_table(receipt: Mapping[str, Any]) -> str:
    basis = receipt["comparisons"]["basis"]
    lines = [
        f"scope: {receipt['declarations']['scope_name']}",
        f"{'arrangement':<28}{'k2':>10}{'k4':>10}{'k8':>10}{'ipr_med':>10}{'coverage':>10}{'selfsim':>10}",
    ]
    for name in (list(basis["motif_names"]) + list(basis["lattice_names"])
                 + list(basis["interaction_names"]) + list(basis["nested_names"])
                 + list(reference_arrangements())):
        row = basis["per_arrangement"].get(name)
        if row is None:
            continue
        self_similarity = row["self_similarity_index"]["phi"]
        coverage = row["access_coverage_score"]
        lines.append(
            f"{name:<28}{row['survival_recovery']['k2']:>10.6f}"
            f"{row['survival_recovery']['k4']:>10.6f}{row['survival_recovery']['k8']:>10.6f}"
            f"{row['ipr_median']:>10.6f}"
            f"{(coverage if coverage is not None else float('nan')):>10.6f}"
            f"{(self_similarity if self_similarity is not None else float('nan')):>10.6f}"
        )
    lines.append("")
    lines.append(f"best phi spacing arm: {basis['best_phi_spacing_name']}")
    lines.append(f"best phi coupling arm: {basis['best_motif_phi_coupling_name']}")
    lines.append(f"best inter-copy phi arm: {basis['best_inter_copy_phi_name']}")
    lines.append(f"best lattice arm: {basis['best_lattice_name']}")
    lines.append("")
    lines.append(f"{'check':<74}{'quantity':>12}{'margin':>10}  verdict")
    for row in receipt["comparisons"]["checks"]:
        quantity = row["quantity"]
        lines.append(
            f"{row['id']:<74}{(quantity if quantity is not None else float('nan')):>12.6f}"
            f"{row['margin']:>10.3g}  {row['holds']}"
        )
    lines.append("")
    lines.append(f"{'firing control':<74}{'before':>8}{'after':>8}  flips")
    for row in receipt["comparisons"]["firing_controls"]:
        lines.append(
            f"{row['id']:<74}{str(row['verdict_before']):>8}{str(row['verdict_after']):>8}  {row['flips']}"
        )
    lines.append("")
    for row in receipt["comparisons"]["continuity"]:
        lines.append(
            f"continuity {row['arrangement']}/{row['quantity']}: cited {row['cited']!r} "
            f"measured {row['measured']!r} difference {row['absolute_difference']:.3e} holds {row['holds']}"
        )
    rung = receipt["comparisons"]["rung"]
    lines.append("")
    lines.append(f"bare-motif rungs: {rung['rung_positions_declared']} declared positions, "
                 f"orientation Yang->Yin, canonical entries replaced "
                 f"{rung['canonical_entries_replaced']}")
    lines.append(f"{'rung arm':<32}{'law':>8}{'k2':>10}{'k4':>10}{'k8':>10}{'d_k4':>10}{'ipr_med':>10}"
                 f"{'rung_l1':>10}{'rail_l1':>10}")
    for row in rung["arms"]:
        lines.append(
            f"{row['arrangement']:<32}{row['rung_law']:>8}"
            f"{row['survival_recovery']['k2']:>10.6f}{row['survival_recovery']['k4']:>10.6f}"
            f"{row['survival_recovery']['k8']:>10.6f}"
            f"{row['survival_k4_delta_vs_canonical']:>10.6f}{row['ipr_median']:>10.6f}"
            f"{row['rung_channel_l1_one_sided']:>10.6f}{row['rail_l1']:>10.6f}"
        )
    held = rung["held_lattice_rung_result"]
    lines.append(
        f"held lattice rung result (cited): {held['check']} cited {held['cited']} vs this "
        f"receipt's own row {held['measured_in_this_receipt']} "
        f"(difference {held['absolute_difference_to_cited']})"
    )
    lines.append("")
    lines.append(f"{'bare-rung survival k4 row':<48}{'arm':<28}{'margin':>8}{'quantity':>11}  verdict")
    for row in rung["survival_k4_rows"]["rows"]:
        lines.append(
            f"{row['check']:<48}{str(row['covers_the_arm']):<28}{row['declared_margin']:>8.3g}"
            f"{row['measured_quantity']:>11.6f}  {row['verdict']}"
        )
    controls = rung["law_controls"]
    lines.append("")
    lines.append(f"{'rung law':<14}{'arm':<34}{'k2':>10}{'k4':>10}{'k8':>10}{'ipr_med':>10}"
                 f"{'coverage':>10}{'spearman':>10}")
    for row in controls["rows"]:
        coverage = row["access_coverage_score"]
        lines.append(
            f"{row['rung_law']:<14}{row['arrangement']:<34}"
            f"{row['k2']:>10.6f}{row['k4']:>10.6f}{row['k8']:>10.6f}"
            f"{row['ipr_median']:>10.6f}"
            f"{(coverage if coverage is not None else float('nan')):>10.6f}"
            f"{row['placement_write_read_spearman']:>10.6f}"
        )
    specificity = controls["phi_specificity"]
    k8 = controls["survival_at_k8"]
    lines.append(
        f"phi vs best steep ramp ({specificity['best_steep_ramp_law']}): |d k4| "
        f"{specificity['phi_minus_best_steep_ramp_k4_absolute_difference']} within margin "
        f"{specificity['within_margin']} -> {specificity['reading']}"
    )
    lines.append(
        f"k8: best law {k8['best_law']} at {k8['best_k8']} (delta vs canonical "
        f"{k8['best_k8_delta_vs_canonical']}), phi {k8['phi_k8']}, survivors at the declared margin "
        f"{k8['survivor_count_at_the_declared_margin']} -> survives {k8['survives']}"
    )
    interaction = receipt["comparisons"]["interaction"]
    lines.append("")
    lines.append(f"{'rail fraction':>14}{'mass k2':>10}{'mass k4':>10}{'mass k8':>10}"
                 f"{'rail k2':>10}{'rail k4':>10}{'rail k8':>10}{'mass-rail k4':>14}")
    for cell in interaction["grid"]["cells"]:
        mass = cell["mass_leg_arm"]
        rail = cell["rail_leg_arm"]
        difference = next(
            (
                entry["k4_difference"]
                for entry in interaction["interaction_terms"]["mass_minus_rail_k4_by_fraction"]
                if entry["rail_fraction"] == cell["rail_fraction"]
            ),
            None,
        )
        lines.append(
            f"{cell['rail_fraction']:>14.2f}"
            f"{mass['k2']:>10.6f}{mass['k4']:>10.6f}{mass['k8']:>10.6f}"
            f"{rail['k2']:>10.6f}{rail['k4']:>10.6f}{rail['k8']:>10.6f}"
            f"{(difference if difference is not None else float('nan')):>14.6f}"
        )
    fit = interaction["fits"]["mass_leg_k4_vs_rail_fraction"]
    lines.append(
        f"mass-leg fit: slope {fit['slope_per_unit_rail_fraction']} per unit rail fraction, "
        f"intercept {fit['intercept_at_zero_rail_weight']}, max|residual| "
        f"{fit['max_absolute_residual']}, spearman {fit['spearman_k4_vs_rail_fraction']}, "
        f"half-slope gap {interaction['interaction_terms']['half_slope_gap']}"
    )
    lines.append(
        f"rail damage: full rail costs the mass channel "
        f"{interaction['interaction_terms']['mass_gain_lost_to_the_full_rail_weight']}, largest "
        f"non-monotone step {interaction['interaction_terms']['mass_leg_largest_non_monotone_step']}, "
        f"multiple of the declared budget "
        f"{interaction['margins']['cuts_the_mass_gain']} -> {interaction['shape_of_the_damage']}"
    )
    normalization = receipt["comparisons"]["nested"]["depth_normalization_control"]
    lines.append("")
    lines.append(f"{'unnormalized nested arm':<30}{'depth':>6}{'law':>10}{'k2':>10}{'k4':>10}"
                 f"{'k8':>10}{'declared_link':>14}")
    for row in normalization["reference_law_raw_rows"] + normalization["uniform_law_raw_rows"]:
        lines.append(
            f"{row['arrangement']:<30}{row['depth']:>6}{row['shell_law']:>10}"
            f"{row['k2']:>10.6f}{row['k4']:>10.6f}{row['k8']:>10.6f}"
            f"{row['declared_link_channel_weight']:>14.6f}"
        )
    lines.append(
        f"depth axis without the normalization: reference-law k4 spread "
        f"{normalization['spreads']['reference_law_raw_k4']}, unity-law k4 spread "
        f"{normalization['spreads']['uniform_law_raw_k4']}, equal-budget unity-law k4 spread "
        f"{normalization['spreads']['uniform_law_equal_budget_k4']}"
    )
    lines.append(
        f"depth null belongs to: {normalization['verdict']['place_of_the_flat_axis']} "
        f"(flat under equal budget {normalization['verdict']['flat_depth_axis_under_equal_budget']}, "
        f"flat raw reference law "
        f"{normalization['verdict']['flat_depth_axis_without_the_normalization_reference_law']}, "
        f"flat raw unity law "
        f"{normalization['verdict']['flat_depth_axis_without_the_normalization_unity_law']})"
    )
    lines.append("")
    lines.append("refuted declared hypotheses:")
    for row in receipt["comparisons"]["refuted_declared_hypotheses"]:
        coverage = row.get("arm_coverage") or {}
        lines.append(
            f"  {row['check']} (family {row['family']}, margin {row['margin']:g}): measured "
            f"{row['measured_quantity']} covers "
            f"{coverage.get('covers_the_arms', 'the arms named in its own statement')}"
        )
    nested = receipt["comparisons"]["nested"]
    lines.append("")
    lines.append(f"{'nested arm':<28}{'depth':>6}{'law':>10}{'norm':>6}{'k2':>10}{'k4':>10}{'k8':>10}"
                 f"{'ipr_med':>10}{'coverage':>10}")
    for row in nested["arms"]:
        coverage = row["access_coverage_score"]
        lines.append(
            f"{row['arrangement']:<28}{row['depth']:>6}{row['shell_law']:>10}"
            f"{str(row['normalized']):>6}"
            f"{row['survival_recovery']['k2']:>10.6f}{row['survival_recovery']['k4']:>10.6f}"
            f"{row['survival_recovery']['k8']:>10.6f}{row['ipr_median']:>10.6f}"
            f"{(coverage if coverage is not None else float('nan')):>10.6f}"
        )
    anchor = nested["depth1_reference_law_anchor"]
    lines.append(
        f"depth-1 reference-law anchor: k4 {anchor['measured_k4']} vs cited "
        f"{anchor['cited_k4']} difference {anchor['absolute_k4_difference_to_cited']:.3e}; "
        f"rail max|diff| to the cited construction "
        f"{anchor['rail_max_absolute_difference_to_the_cited_construction']:.3e}"
    )
    lines.append(
        f"depth axis ({nested['axes']['depth_axis']['law']}): deepest vs shallowest "
        f"{nested['axes']['depth_axis']['deepest_vs_shallowest_k4_difference']:.6f}, "
        f"depth3->4 {nested['axes']['depth_axis']['depth3_to_depth4_k4_difference']:.6f}; "
        f"shell-law axis (depth {nested['axes']['shell_law_axis']['depth']}): phi - uniform "
        f"{nested['axes']['shell_law_axis']['phi_minus_uniform_k4_difference']:.6f}"
    )
    attribution = receipt["comparisons"]["attribution"]
    lines.append("")
    lines.append(f"{'attribution leg':<16}{'arrangement':<28}{'k2':>10}{'k4':>10}{'k8':>10}")
    for row in attribution["arms"]:
        lines.append(
            f"{row['leg']:<16}{row['arrangement']:<28}"
            f"{row['survival_recovery']['k2']:>10.6f}{row['survival_recovery']['k4']:>10.6f}"
            f"{row['survival_recovery']['k8']:>10.6f}"
        )
    for count in ("k2", "k4", "k8"):
        entry = attribution["per_count"][count]
        lines.append(
            f"attribution {count}: deltas rail {entry['deltas_vs_canonical']['rail_only']} mass "
            f"{entry['deltas_vs_canonical']['mass_only']} compound "
            f"{entry['deltas_vs_canonical']['compound']} residual "
            f"{entry['additivity_residual']} additive_within_tolerance "
            f"{entry['additive_within_tolerance']}"
        )
    nest_contrast = attribution["best_lattice_k4_vs_same_run_single_nest"]
    lines.append(
        f"best lattice k4 {nest_contrast['best_lattice_k4']} vs same-run single nest "
        f"{nest_contrast['same_run_single_nest_k4']} difference {nest_contrast['difference']} "
        f"(margin {nest_contrast['recovery_margin']})"
    )
    lines.append(f"receipt_sha256: {receipt['receipt_sha256']}")
    lines.append(f"runtime_seconds: {receipt['runtime_seconds']:.2f}")
    lines.append(
        f"checks: {sum(1 for row in receipt['comparisons']['checks'] if row['holds'])}"
        f"/{len(receipt['comparisons']['checks'])} hold; firing controls that flip: "
        f"{sum(1 for row in receipt['comparisons']['firing_controls'] if row['flips'])}"
        f"/{len(receipt['comparisons']['firing_controls'])}"
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scope", default=DEFAULT_SCOPE)
    parser.add_argument("--ports-per-pool", type=int, default=PORTS_PER_POOL)
    args = parser.parse_args(argv)
    config = LatticeConfig(scope=args.scope, ports_per_pool=args.ports_per_pool)
    receipt = build_receipt(config)
    rendered = json.dumps(_jsonable(receipt), indent=2, sort_keys=True, allow_nan=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(format_table(receipt))
    print(f"receipt_bytes: {len(rendered) + 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
