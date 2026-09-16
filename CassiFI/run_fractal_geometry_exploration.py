"""Bounded numerical exploration of declared arrangement geometries.

Question: which *declared arrangement geometries* of the seven-pool resonant
field -- the connection/metric structure across the paired ports -- make
bounded drives excite patterns that are persistent, distinguishable, structured
and accessible?  Arrangements here are candidate scaffolds, and every number in
the receipt is a geometric/access proxy.

What this measures (proxies, not memory utility):

* ``spectrum``   -- the effective linear generator of the arrangement, built
  exactly as the canonical module builds its operator (``_WaveOperator`` on a
  ``beta=0`` profile, applied to basis columns), then dense-eigendecomposed.
  Reported: eigenvalue ranges plus an inverse-participation-ratio localization
  measure per mode and the fraction of significantly participating modes.
* ``retention``  -- retained energy after a fixed horizon under the canonical
  damping, from a small fixed set of energy-bounded pool impulses, and whether
  that retention depends on where the impulse was applied.
* ``access``     -- the existing linear transceiver construction
  (``condense_workspace``): ``input_lift`` column norms, ``output_rows`` row
  norms, the condensation error bound, and a best-k coverage score across
  several declared port subsets; plus the condensed transceiver's own
  measured input->readout response.
* determinism    -- two independent constructions of one arrangement must give
  the same digests.

Run: ``python run_fractal_geometry_exploration.py --output _diag/fractal-geometry/exploration.json``

The receipt records, for every arrangement: the exact construction rule, exact
sizes, the declared seed, every measured number, and a digest.  Nothing here is
a memory-utility or task-performance claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_field_transceiver import (
    advance_transceiver,
    condense_workspace,
    reset_transceiver,
)
from cassi_resonant_field import (
    ResonantNumericalError,
    ResonantProblem,
    ResonantProfile,
    _WaveOperator,
    advance_workspace,
    apply_helical_packet_impulse,
    apply_pool_impulse,
    initial_workspace,
)

SCHEMA = "cassifi.fractal-geometry-exploration.v1"
RECEIPT_SCHEMA = "cassifi.fractal-geometry-receipt.v1"

# Declared construction unit: the canonical cross-pool strength convention on a
# boundary port pair, i.e. the canonical circuit edge (scale 1.0) plus the
# canonical neck edge (scale 0.7) that share that port pair.
CHAIN_SCALE = 1.7
CORE_SHELL_DECAY = 0.5
CORE_SHELL_CORE_POOL = 3
CORE_SHELL_INV_MASS_DECAY = 0.7
PAIR_LOOP_STRENGTH = 4.0
DEFECT_STRENGTH = 4.0
RANDOM_SEED = 20260915
FIBONACCI = (1, 1, 2, 3, 5, 8)

# Declared problem/metric envelope for the transceiver construction.
PRIOR_RIDGE = 0.05
PRIOR_MASS = 0.95

DEFAULT_PORTS_PER_POOL = 4
DEFAULT_RETENTION_TICKS = 64
DEFAULT_RESPONSE_TICKS = 32
DEFAULT_RANK = 8
DEFAULT_ERROR_ALLOWANCE = 1e-3
DEFAULT_INPUT_BOUND = 4.0
DEFAULT_HORIZON_TICKS = 64
DEFAULT_IMPULSE_WORK = 0.02
DEFAULT_IMPULSE_POOLS = (0, 3, 6)
QUARTIC_PROBE_TICKS = 16
QUARTIC_PROBE_POOL = 3
QUARTIC_PROBE_RAMP = 0.5
QUARTIC_PROBE_WORK = 0.02
# A common-mode impulse leaves the relative coordinate negligible, so the quartic
# term must be numerically invisible there; a counterflow impulse drives it
# directly and must move the retained energy.
QUARTIC_NULL_TOLERANCE = 1e-9
QUARTIC_EFFECT_TOLERANCE = 1e-8

# Declared localization threshold: a mode is localized when its inverse
# participation ratio reaches LOCALIZATION_IPR_FACTOR/dimension, i.e. when its
# effective support is below a quarter of the state.
LOCALIZATION_IPR_FACTOR = 4.0
# Declared derived probe: the arrangement's own rail with cross-pool entries scaled.
RAIL_GAIN_PROBE = 10.0
# Declared cross-arrangement margins.  Retention differences under the canonical
# damping separate between arrangements that change the mass metric (~3e-2) and
# arrangements that only change the connection graph (~1e-6 when only the link
# strengths move, ~1e-4 for the density-matched rewire), so the declared margins
# are 1e-3 (invariant) and 1e-2 (sensitive).
RAIL_INVARIANCE_TOLERANCE = 1e-3
MASS_SENSITIVITY_MARGIN = 1e-2
LOCALIZATION_MARGIN = 2e-2
RETENTION_RAIL_PAIRS = (
    ("flat-ladder", "random-rewire-matched"),
    ("flat-ladder", "sparse-long-link"),
    ("flat-ladder", "quasiperiodic-chain"),
)
RETENTION_MASS_PAIRS = (("helix7", "undivided"), ("helix7", "nested-core-shell"))
LOCALIZATION_PAIRS = (("isolated", "nested-core-shell"), ("quasiperiodic-chain", "nested-core-shell"))
GAIN_PROBE_NAMES = ("isolated", "nested-core-shell", "quasiperiodic-chain", "flat-ladder")


# --------------------------------------------------------------------------
# small json helpers
# --------------------------------------------------------------------------
def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


TIMING_KEYS = frozenset({
    "elapsed_seconds", "runtime_seconds", "condensation_elapsed_seconds", "receipt_sha256",
})


def strip_timing(value: Any) -> Any:
    """Drop wall-clock fields so a receipt digest covers measured numbers only."""
    if isinstance(value, Mapping):
        return {
            str(key): strip_timing(item) for key, item in value.items() if key not in TIMING_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [strip_timing(item) for item in value]
    return value


def content_digest(value: Any) -> str:
    """Digest of a receipt's measured content, excluding wall-clock fields."""
    return canonical_digest(strip_timing(value))


def _array_digest(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value, dtype="<f8").tobytes()).hexdigest()


# --------------------------------------------------------------------------
# declared arrangements
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Arrangement:
    """One declared arrangement: an exact construction rule over declared hooks."""

    name: str
    kind: str
    rule: str
    topology: str = "meaningful-helix"
    pool_links: tuple[tuple[int, int, float], ...] = ()
    core_shell_inverse_mass: bool = False
    density_reference: str | None = None
    seed: int | None = None
    note: str = ""


def _ring_distance(a: int, b: int, pools: int = 7) -> int:
    raw = abs(int(a) - int(b))
    return min(raw, pools - raw)


def _sequential_links(strengths: Sequence[float]) -> tuple[tuple[int, int, float], ...]:
    """Chain links pool ``a`` -> pool ``a+1`` with the declared per-link strength."""
    return tuple((index, index + 1, float(value)) for index, value in enumerate(strengths))

def _random_rewire_links(*, count: int = 6, seed: int = RANDOM_SEED) -> tuple[tuple[int, int, float], ...]:
    """Deterministic rewire drawn from one declared generator.

    Six sources ``0..count-1`` are re-pointed at a permutation of the seven
    pools, redrawn from one declared generator until the rewire is a bijection
    with no self-link.  The drawn destination assignment is the declared graph;
    its link strengths are normalized later (see
    :func:`density_matched_links`), so link count and *realized* interaction
    density match the declared ladder exactly.
    """
    rng = np.random.default_rng(seed)
    for _ in range(10000):
        order = [int(pool) for pool in rng.permutation(7)]
        links = [(source, order[source]) for source in range(count)]
        if all(a != b for a, b in links) and len({b for _, b in links}) == count:
            return tuple((a, b, CHAIN_SCALE) for a, b in links)
    raise ResonantNumericalError("declared rewire search exhausted")


def arrangements(*, seed: int = RANDOM_SEED) -> tuple[Arrangement, ...]:
    """Every candidate arrangement, with its exact construction rule."""
    ladder = _sequential_links((CHAIN_SCALE,) * 6)
    total = sum(FIBONACCI)
    fibonacci = _sequential_links(
        tuple(6.0 * CHAIN_SCALE * weight / total for weight in FIBONACCI)
    )
    sparse = ladder + ((0, 3, CHAIN_SCALE), (3, 6, CHAIN_SCALE))
    nested = tuple(
        (a, b, CHAIN_SCALE * CORE_SHELL_DECAY ** _ring_distance(a, b))
        for a in range(7)
        for b in range(7)
        if a != b
    )
    defect = tuple(
        (a, b, DEFECT_STRENGTH * CHAIN_SCALE if (a, b) == (0, 6) else weight)
        for a, b, weight in nested
    )
    pairs = ((0, 1), (2, 3), (4, 5))
    loops = tuple(
        [(a, b, PAIR_LOOP_STRENGTH * CHAIN_SCALE) for a, b in pairs]
        + [(b, a, PAIR_LOOP_STRENGTH * CHAIN_SCALE) for a, b in pairs]
        + [(1, 2, CHAIN_SCALE), (3, 4, CHAIN_SCALE), (5, 6, CHAIN_SCALE), (6, 0, CHAIN_SCALE)]
    )
    rewire = _random_rewire_links(seed=seed)
    return (
        Arrangement(
            name="helix7",
            kind="canonical-hook",
            topology="meaningful-helix",
            rule="ResonantProfile() defaults: canonical intra rings, canonical "
                 "double-helix circuit (including the two strand bridges), and the six "
                 "canonical neck links; no projected hook.",
            note="baseline: the current production body.",
        ),
        Arrangement(
            name="undivided",
            kind="canonical-hook",
            topology="undivided",
            rule="ResonantProfile(topology='undivided'): identical edge set, but "
                 "volumes become uniform (1.0 per port) and inertances become uniform "
                 "(1.0 per port), which rescales every canonical edge weight and flattens "
                 "the mass metric.",
            note="only arrangement that changes the mass metric through `topology` alone.",
        ),
        Arrangement(
            name="isolated",
            kind="canonical-hook",
            topology="isolated",
            rule="ResonantProfile(topology='isolated'): the circuit (and therefore both "
                 "strand bridges and the whole Yin strand chain) and the six neck links are "
                 "dropped; only the canonical intra rings remain, and those exist on the "
                 "Yang strand only. No pool is coupled to any other pool.",
            note="the Yin strand keeps no rail edge at all in this topology.",
        ),
        Arrangement(
            name="rewired",
            kind="canonical-hook",
            topology="rewired",
            rule="ResonantProfile(topology='rewired'): the canonical circuit destinations "
                 "are permuted by the canonical index shift 7 (edge i -> destination "
                 "(i+7) mod 56); intra and neck links are untouched, and the shift breaks "
                 "the two strand bridges.",
            note="same edge count and weight multiset as the baseline, different order.",
        ),
        Arrangement(
            name="flat-ladder",
            kind="declared-pool-graph",
            pool_links=ladder,
            rule="projected_transport = canonical intra rings (verbatim) + the two "
                 "canonical strand bridges (verbatim) + a regular seven-pool chain "
                 "(a -> a+1 for a=0..5) at scale 1.7 per link on both strands, with the "
                 "canonical edge weight rule coupling*scale/(length*sqrt(vol_u*vol_v)).",
        ),
        Arrangement(
            name="nested-core-shell",
            kind="declared-pool-graph",
            pool_links=nested,
            core_shell_inverse_mass=True,
            rule="projected_transport = canonical intra rings + strand bridges + every "
                 "ordered pool pair (a,b), a!=b, at scale 1.7*0.5**ring_distance(a,b) so "
                 "interaction magnitude decays monotonically with pool distance; "
                 "projected_inv_mass[port] = 0.7**ring_distance(pool, 3), a shell metric "
                 "decaying monotonically away from the core pool 3.",
            note="uses both the transport and the inverse-mass hook.",
        ),
        Arrangement(
            name="recursive-paired-loops",
            kind="declared-pool-graph",
            pool_links=loops,
            rule="projected_transport = canonical intra rings + strand bridges + mutual "
                 "intra-pair links for the pairs (0,1),(2,3),(4,5) at scale 1.7*4 "
                 "(strong, bidirectional), plus four sparse inter-pair links "
                 "1->2, 3->4, 5->6, 6->0 at scale 1.7, closing a recursive loop that "
                 "visits the leftover pool 6.",
        ),
        Arrangement(
            name="core-shell-defect",
            kind="declared-pool-graph",
            pool_links=defect,
            core_shell_inverse_mass=True,
            rule="nested-core-shell with exactly one deliberate defect link: the (0,6) "
                 "link carries scale 1.7*4 instead of the declared 1.7*0.5**1 = 0.85 "
                 "ring-distance rule, i.e. 8x the rule on a ring-adjacent pair.",
            note="single defect; every other link follows the nested rule.",
        ),
        Arrangement(
            name="sparse-long-link",
            kind="declared-pool-graph",
            pool_links=sparse,
            rule="flat-ladder plus two declared long links 0->3 and 3->6 at scale 1.7 "
                 "(8 links total, 2 of them long-range).",
        ),
        Arrangement(
            name="quasiperiodic-chain",
            kind="declared-pool-graph",
            pool_links=fibonacci,
            density_reference="flat-ladder",
            rule="flat-ladder chain a -> a+1 (a=0..5) with Fibonacci-like link scales: the "
                 "declared scales are proportional to F[a], F=(1,1,2,3,5,8), rescaled "
                 "uniformly so the realized cross-pool rail strength equals flat-ladder's "
                 "exactly; link count and realized interaction density match flat-ladder, "
                 "only the strength distribution is quasiperiodic.",
            note="nearest expressible variant: the module exposes no coordinate hook, so "
                 "quasiperiodic *spatial* spacing cannot be expressed -- see limitations.",
        ),
        Arrangement(
            name="random-rewire-matched",
            kind="declared-pool-graph",
            pool_links=rewire,
            density_reference="flat-ladder",
            seed=seed,
            rule="flat-ladder chain destinations replaced by a permutation of the seven "
                 "pools drawn from numpy.default_rng(seed), redrawn until the rewire is a "
                 "bijection with no self-link; each of the six links is then rescaled so its "
                 "realized canonical-rule weight equals one sixth of flat-ladder's realized "
                 "cross-pool rail strength, so link count and realized interaction density "
                 "match flat-ladder exactly while the pool graph differs.",
            note="matched interaction density in the realized rail, not merely in "
                 "declared scales; the drawn permutation contains the 2-cycle "
                 "(1,4)/(4,1), so the six directed links occupy five undirected "
                 "pool pairs.",
        ),
    )


def arrangement_named(name: str, *, seed: int = RANDOM_SEED) -> Arrangement:
    """Look one declared arrangement up by name."""
    for item in arrangements(seed=seed):
        if item.name == name:
            return item
    raise ResonantNumericalError(f"unknown arrangement {name!r}")


# --------------------------------------------------------------------------
# construction
# --------------------------------------------------------------------------
def canonical_parts(ports_per_pool: int) -> dict[str, Any]:
    """The canonical intra rings, strand bridges, coordinates and volumes."""
    base = ResonantProfile(ports_per_pool=ports_per_pool)
    n, p = base.port_count, base.ports_per_pool
    intra = tuple(edge for edge in base.edges if edge[3] == "intra")
    bridges = tuple(
        edge for edge in base.edges
        if edge[3] == "circuit" and ((edge[0] < n) != (edge[1] < n))
    )
    return {
        "base": base, "ports": n, "ports_per_pool": p, "intra": intra, "bridges": bridges,
        "coordinates": np.asarray(base.coordinates), "volumes": np.asarray(base.volumes),
        "coupling": base.coupling,
    }


def _edge_weight(parts: Mapping[str, Any], source: int, destination: int, scale: float) -> float:
    """The canonical edge weight rule, applied to a declared port pair."""
    coordinates, volumes = parts["coordinates"], parts["volumes"]
    length = max(float(np.linalg.norm(coordinates[destination] - coordinates[source])), 1e-12)
    return float(parts["coupling"]) * float(scale) / (
        length * math.sqrt(float(volumes[source]) * float(volumes[destination]))
    )


def pool_link_port_pairs(link: tuple[int, int, float], parts: Mapping[str, Any]) -> tuple[tuple[int, int, float], ...]:
    """Declared pool link (a -> b) as the canonical port pairs on both strands.

    Yang strand: last port of pool ``a`` -> first port of pool ``b`` (the
    canonical circuit/neck port pair).  Yin strand: the mirrored pair with the
    same orientation convention, i.e. first Yin port of ``b`` -> last Yin port
    of ``a``.
    """
    a, b, scale = int(link[0]), int(link[1]), float(link[2])
    n, p = int(parts["ports"]), int(parts["ports_per_pool"])
    return (
        (a * p + p - 1, b * p, scale),
        (n + b * p, n + a * p + p - 1, scale),
    )


def rail_from_pool_links(
    pool_links: Sequence[tuple[int, int, float]], *, ports_per_pool: int = DEFAULT_PORTS_PER_POOL
) -> np.ndarray:
    """Declared arrangement rail: canonical intra rings + bridges + declared pool graph."""
    parts = canonical_parts(ports_per_pool)
    dimension = 2 * int(parts["ports"])
    rail = np.zeros((dimension, dimension), dtype=np.float64)

    def add(source: int, destination: int, weight: float) -> None:
        if source == destination:
            return
        rail[destination, source] += weight
        rail[source, destination] -= weight

    for source, destination, weight, _kind in tuple(parts["intra"]) + tuple(parts["bridges"]):
        add(int(source), int(destination), float(weight))
    for link in pool_links:
        for source, destination, scale in pool_link_port_pairs(link, parts):
            add(source, destination, _edge_weight(parts, source, destination, scale))
    return rail


def core_shell_inverse_mass(ports_per_pool: int, *, decay: float = CORE_SHELL_INV_MASS_DECAY) -> np.ndarray:
    """Declared shell metric: inverse mass decaying monotonically from the core pool."""
    n, p = 7 * ports_per_pool, ports_per_pool
    values = np.empty(2 * n, dtype=np.float64)
    for pool in range(7):
        value = decay ** _ring_distance(pool, CORE_SHELL_CORE_POOL)
        for strand in (0, 1):
            for local in range(p):
                values[strand * n + pool * p + local] = value
    return values


def realized_pair_strength(link: tuple[int, int, float], parts: Mapping[str, Any]) -> float:
    """Realized canonical-rule weight of one declared pool link at unit scale."""
    return sum(
        _edge_weight(parts, source, destination, 1.0)
        for source, destination, _scale in pool_link_port_pairs((link[0], link[1], 1.0), parts)
    )


def density_matched_links(
    links: Sequence[tuple[int, int, float]],
    reference: Sequence[tuple[int, int, float]],
    *,
    ports_per_pool: int = DEFAULT_PORTS_PER_POOL,
) -> tuple[tuple[int, int, float], ...]:
    """Rescale declared links so the realized rail strength matches the reference exactly.

    The canonical weight rule depends on the declared port coordinates, so an
    arrangement that only changes *which* pools are linked would otherwise also
    change the total interaction strength.  Each link is given a uniform share of
    the reference's realized cross-pool strength, which makes link count and
    realized density match while the pool graph still differs.
    """
    parts = canonical_parts(ports_per_pool)
    total = sum(
        float(scale) * realized_pair_strength((source, destination, 1.0), parts)
        for source, destination, scale in reference
    )
    target = total / len(links)
    return tuple(
        (int(source), int(destination), target / realized_pair_strength((source, destination, 1.0), parts))
        for source, destination, _scale in links
    )


def effective_links(
    arrangement: Arrangement, *, ports_per_pool: int = DEFAULT_PORTS_PER_POOL
) -> tuple[tuple[int, int, float], ...]:
    """The links an arrangement actually uses, after any declared density matching."""
    if arrangement.density_reference is None:
        return arrangement.pool_links
    reference = arrangement_named(arrangement.density_reference)
    return density_matched_links(
        arrangement.pool_links, reference.pool_links, ports_per_pool=ports_per_pool
    )


def build_profile(arrangement: Arrangement, *, ports_per_pool: int = DEFAULT_PORTS_PER_POOL) -> ResonantProfile:
    """Build the declared arrangement through canonical hooks only."""
    if arrangement.kind == "canonical-hook":
        return ResonantProfile(ports_per_pool=ports_per_pool, topology=arrangement.topology)
    if arrangement.kind != "declared-pool-graph":
        raise ResonantNumericalError(f"unsupported arrangement kind {arrangement.kind!r}")
    rail = rail_from_pool_links(
        effective_links(arrangement, ports_per_pool=ports_per_pool),
        ports_per_pool=ports_per_pool,
    )
    inverse_mass = (
        core_shell_inverse_mass(ports_per_pool) if arrangement.core_shell_inverse_mass else None
    )
    return ResonantProfile(
        ports_per_pool=ports_per_pool,
        topology="meaningful-helix",
        projected_transport=rail,
        projected_inv_mass=inverse_mass,
    )


# --------------------------------------------------------------------------
# linear spectrum
# --------------------------------------------------------------------------
def independent_mass(profile: ResonantProfile) -> np.ndarray:
    """The arrangement's mass metric: diag(1/inertances) or the projected SPD matrix."""
    inverse_mass = profile.projected_inv_mass
    if inverse_mass is None:
        return np.diag(1.0 / np.asarray(profile.inertances, dtype=np.float64))
    raw = np.asarray(inverse_mass, dtype=np.float64)
    return np.diag(raw) if raw.ndim == 1 else raw


def independent_generator(profile: ResonantProfile) -> np.ndarray:
    """Closed-form reconstruction of the canonical rest linearization (RU1/RU2).

    This is an independent second construction of the same linear generator,
    written from the canonical algebra rather than from the production
    operator, and is used only to check the production operator.
    """
    n = profile.port_count
    rail = np.asarray(profile.transport_matrix, dtype=np.float64)
    identity = np.eye(2 * n)
    poisson = np.block([[rail, identity], [-identity, rail]])
    stiffness = profile.relative_stiffness
    potential = np.block([
        [np.eye(n) * (1 + stiffness) / 2, np.eye(n) * (1 - stiffness) / 2],
        [np.eye(n) * (1 - stiffness) / 2, np.eye(n) * (1 + stiffness) / 2],
    ])
    hessian = np.zeros((4 * n, 4 * n), dtype=np.float64)
    hessian[:2 * n, :2 * n] = potential
    hessian[2 * n:, 2 * n:] = independent_mass(profile)
    return (poisson - np.eye(4 * n) * profile.damping) @ hessian


def linear_generator(profile: ResonantProfile) -> np.ndarray:
    """The arrangement's effective linear dynamics, as the canonical module builds it.

    ``_WaveOperator`` on a ``beta=0`` profile is exactly linear, so applying
    ``flow(energy_gradient(e_i), quiet=False)`` to basis columns yields the
    dense generator (the same construction ``measure_body_response`` uses).
    """
    linear = replace(profile, beta=0.0)
    operator = _WaveOperator(initial_workspace(linear), None)
    dimension = 4 * profile.port_count
    identity = np.eye(dimension)
    return np.column_stack([
        np.asarray(operator.flow(operator.energy_gradient(identity[:, index])[1], False))
        for index in range(dimension)
    ])


def coupled_pool_pairs(rail: np.ndarray, ports_per_pool: int) -> tuple[tuple[int, int], ...]:
    """Undirected pool pairs that carry any rail entry (the effective pool graph)."""
    dimension = rail.shape[0]
    ports = dimension // 2
    pool = (np.arange(dimension) % ports) // ports_per_pool
    pairs = set()
    rows, columns = np.nonzero(rail)
    for source, destination in zip(rows.tolist(), columns.tolist()):
        left, right = int(pool[source]), int(pool[destination])
        if left != right:
            pairs.add((min(left, right), max(left, right)))
    return tuple(sorted(pairs))


def cross_pool_gain_profile(profile: ResonantProfile, gain: float) -> ResonantProfile:
    """Declared derived profile: this arrangement's own rail with cross-pool entries scaled.

    At ``gain == 1`` the rail is returned unchanged, so the derived profile must
    reproduce the arrangement's generator; that equality is measured, never assumed.
    """
    rail = np.asarray(profile.transport_matrix, dtype=np.float64)
    ports = profile.port_count
    pool = (np.arange(2 * ports) % ports) // profile.ports_per_pool
    cross = pool[:, None] != pool[None, :]
    scaled = np.where(cross, rail * float(gain), rail)
    return replace(profile, projected_transport=scaled)


def _generator_spectrum(generator: np.ndarray) -> dict[str, Any]:
    eigenvalues, eigenvectors = np.linalg.eig(generator)
    magnitude = np.abs(eigenvectors) ** 2
    participation = magnitude.sum(axis=0)
    participation[participation == 0.0] = 1.0
    ipr = np.asarray(((magnitude ** 2).sum(axis=0) / participation ** 2).real, dtype=np.float64)
    complex_modes = np.abs(eigenvalues.imag) > 1e-9
    frequencies = np.sort(np.abs(eigenvalues.imag[complex_modes]))
    return {
        "eigenvalues": eigenvalues,
        "ipr": ipr,
        "complex_modes": complex_modes,
        "frequencies": frequencies,
        "uniform_ipr": 1.0 / generator.shape[0],
    }


def spectrum_metrics(
    profile: ResonantProfile, *, rail_gains: Sequence[float] = (1.0, RAIL_GAIN_PROBE)
) -> dict[str, Any]:
    """Eigenvalue ranges, per-mode localization, and the declared cross-pool rail-gain probe."""
    generator = linear_generator(profile)
    dimension = generator.shape[0]
    reconstruction = independent_generator(profile)
    base = _generator_spectrum(generator)
    eigenvalues, ipr = base["eigenvalues"], base["ipr"]
    uniform = base["uniform_ipr"]
    frequencies = base["frequencies"]
    distinct = int(sum(
        1 for index in range(1, len(frequencies)) if frequencies[index] - frequencies[index - 1] > 0.01
    ))
    distinct += 1 if len(frequencies) else 0
    localized = ipr >= LOCALIZATION_IPR_FACTOR * uniform
    result: dict[str, Any] = {
        "definition": {
            "generator": "beta=0 _WaveOperator, one canonical flow(energy_gradient(e_i)) column per state coordinate",
            "localization": "IPR = sum|v|^4 / (sum|v|^2)^2 on the unit-norm right eigenvector",
            "localized_mode": f"IPR >= {LOCALIZATION_IPR_FACTOR}/dimension (effective support < a quarter of the state)",
            "rail_gain_probe": f"the arrangement's own rail with cross-pool entries scaled by {RAIL_GAIN_PROBE}",
        },
        "dimension": int(dimension),
        "real_part_range": [float(eigenvalues.real.min()), float(eigenvalues.real.max())],
        "maximum_growth_rate": float(eigenvalues.real.max()),
        "complex_mode_count": int(base["complex_modes"].sum()),
        "real_mode_count": int((~base["complex_modes"]).sum()),
        "imaginary_magnitude_range": [
            float(np.abs(eigenvalues.imag).min()), float(np.abs(eigenvalues.imag).max())
        ],
        "complex_frequency_range": (
            [float(frequencies.min()), float(frequencies.max())] if len(frequencies) else [0.0, 0.0]
        ),
        "distinct_frequencies_at_0.01": int(distinct),
        "ipr_uniform_reference": float(uniform),
        "ipr_by_mode": [float(value) for value in ipr],
        "ipr_min": float(ipr.min()),
        "ipr_median": float(np.median(ipr)),
        "ipr_mean": float(ipr.mean()),
        "ipr_max": float(ipr.max()),
        "localized_mode_fraction": float(localized.mean()),
        "localized_mode_count": int(localized.sum()),
        "significantly_participating_modes_at_2dim": int((ipr >= 2.0 * uniform).sum()),
        "generator_sha256": _array_digest(generator),
        "eigenvalue_sha256": canonical_digest(
            [complex(value).real for value in eigenvalues] + [complex(value).imag for value in eigenvalues]
        ),
        "independent_reconstruction_max_abs_difference": float(np.abs(generator - reconstruction).max()),
    }
    gain_rows: list[dict[str, Any]] = []
    for gain in rail_gains:
        derived = cross_pool_gain_profile(profile, gain)
        rail_identical = bool(np.array_equal(
            np.asarray(derived.transport_matrix), np.asarray(profile.transport_matrix)
        ))
        derived_generator = linear_generator(derived)
        derived_spectrum = _generator_spectrum(derived_generator)
        derived_ipr = derived_spectrum["ipr"]
        gain_rows.append({
            "gain": float(gain),
            "rail_identical_to_arrangement": rail_identical,
            "generator_max_abs_difference": float(np.abs(derived_generator - generator).max()),
            "maximum_growth_rate": float(derived_spectrum["eigenvalues"].real.max()),
            "imaginary_magnitude_range": [
                float(np.abs(derived_spectrum["eigenvalues"].imag).min()),
                float(np.abs(derived_spectrum["eigenvalues"].imag).max()),
            ],
            "ipr_median": float(np.median(derived_ipr)),
            "localized_mode_fraction": float((derived_ipr >= LOCALIZATION_IPR_FACTOR * uniform).mean()),
            "spectrum_changed": bool(np.abs(derived_generator - generator).max() > 1e-12),
        })
    result["cross_pool_gain"] = gain_rows
    return result


# --------------------------------------------------------------------------
# retention under the canonical damping
# --------------------------------------------------------------------------
def state_vector(workspace: Any) -> np.ndarray:
    n = workspace.profile.port_count
    field = workspace.field
    return np.concatenate([field[0, lane:9 * n:9, 0] for lane in range(4)])


def retention_metrics(
    profile: ResonantProfile,
    *,
    pools: Sequence[int] = DEFAULT_IMPULSE_POOLS,
    work: float = DEFAULT_IMPULSE_WORK,
    ticks: int = DEFAULT_RETENTION_TICKS,
) -> dict[str, Any]:
    """Retained energy after a fixed horizon from one-hot pool impulses."""
    rows: list[dict[str, Any]] = []
    finals: list[np.ndarray] = []
    for pool in pools:
        signal = np.zeros(7, dtype=np.float64)
        signal[int(pool)] = 1.0
        try:
            seeded, impulse = apply_pool_impulse(
                initial_workspace(profile), pool_signal=signal, work_budget=float(work),
                evidence_tick=1, event_kind="formation",
            )
            evolved, advance = advance_workspace(
                seeded, ticks=int(ticks), demand=0.0, source_enabled=False,
            )
        except (ResonantNumericalError, np.linalg.LinAlgError, ValueError) as error:
            rows.append({
                "impulse_pool": int(pool), "status": "failed",
                "reason": f"{type(error).__name__}: {error}",
            })
            continue
        start = float(impulse["end_energy"])
        end = float(advance["end_energy"])
        rows.append({
            "impulse_pool": int(pool), "status": "measured",
            "applied_work": float(impulse["applied_work"]),
            "post_impulse_energy": start,
            "retained_energy": end,
            "retention_ratio": end / start if start else 0.0,
            "subdivisions": int(advance["subdivisions"]),
            "nonlinear_iterations": int(advance["nonlinear_iterations"]),
        })
        finals.append(state_vector(evolved))
    separations: list[float] = []
    for left in range(len(finals)):
        for right in range(left + 1, len(finals)):
            a, b = finals[left], finals[right]
            na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
            if na == 0.0 or nb == 0.0:
                separations.append(0.0)
            else:
                separations.append(float(1.0 - abs(float(a @ b) / (na * nb))))
    measured = [row for row in rows if row["status"] == "measured"]
    ratios = [row["retention_ratio"] for row in measured]
    return {
        "definition": {
            "impulse": "apply_pool_impulse with a one-hot pool signal at the declared work budget",
            "horizon": "advance_workspace(source_enabled=False, demand=0.0) for the declared tick count",
            "retention_ratio": "advance end_energy / post-impulse energy",
            "site_dependence": "max-min of the per-pool retention ratios",
            "separation": "1 - |cos| between the normalized final state vectors of two impulse sites",
        },
        "work_budget": float(work), "ticks": int(ticks), "impulse_pools": [int(p) for p in pools],
        "by_pool": rows,
        "retention_min": float(min(ratios)) if ratios else None,
        "retention_max": float(max(ratios)) if ratios else None,
        "retention_mean": float(sum(ratios) / len(ratios)) if ratios else None,
        "site_dependence": float(max(ratios) - min(ratios)) if ratios else None,
        "minimum_site_separation": float(min(separations)) if separations else None,
        "all_sites_measured": len(measured) == len(pools),
    }


# --------------------------------------------------------------------------
# access through the existing linear transceiver construction
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PortSubset:
    name: str
    pools_in: tuple[int, ...]
    pools_out: tuple[int, ...]


PORT_SUBSETS = (
    PortSubset("all-pools", (0, 1, 2, 3, 4, 5, 6), (0, 1, 2, 3, 4, 5, 6)),
    PortSubset("spread-3", (0, 3, 6), (0, 3, 6)),
    PortSubset("single-pair", (0,), (6,)),
    PortSubset("adjacent-pair", (1, 2), (4, 5)),
)


def drive_id(pool: int) -> str:
    return f"fg:drive-pool-{pool}"


def read_id(pool: int) -> str:
    return f"fg:read-pool-{pool}"


def port_bindings(ports_per_pool: int) -> dict[str, dict[str, Any]]:
    """Deterministic declared bindings: drive on local port 0, read on local port 1."""
    out: dict[str, dict[str, Any]] = {}
    for pool in range(7):
        out[drive_id(pool)] = {
            "pool": pool, "port": pool * ports_per_pool, "component": "common",
            "binding_id": f"fractal-geometry:{drive_id(pool)}:common",
        }
        out[read_id(pool)] = {
            "pool": pool, "port": pool * ports_per_pool + 1, "component": "common",
            "binding_id": f"fractal-geometry:{read_id(pool)}:common",
        }
    return out


def declared_problem(subset: PortSubset) -> ResonantProblem:
    """Declared learned objective: ridge + uniform prior precision on the two ports per pool."""
    inputs = tuple(drive_id(pool) for pool in subset.pools_in)
    outputs = tuple(read_id(pool) for pool in subset.pools_out)
    variable_ids = inputs + outputs
    size = len(variable_ids)
    precision = PRIOR_RIDGE * np.eye(size) + (PRIOR_MASS / size) * np.ones((size, size))
    return ResonantProblem(
        variable_ids=variable_ids, precision=precision, linear_b=np.zeros(size),
        observed={name: 0.0 for name in inputs}, affine_constraints=None,
    )


def subset_kernel(
    profile: ResonantProfile, subset: PortSubset, *,
    rank: int = DEFAULT_RANK, error_allowance: float = DEFAULT_ERROR_ALLOWANCE,
    input_bound: float = DEFAULT_INPUT_BOUND, horizon_ticks: int = DEFAULT_HORIZON_TICKS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Condense the linear transceiver for one declared subset (beta=0 construction)."""
    linear = replace(profile, beta=0.0)
    workspace = initial_workspace(linear)._copy(bindings=port_bindings(linear.ports_per_pool))
    problem = declared_problem(subset)
    kernel, _working, receipt = condense_workspace(
        workspace, problem,
        input_ids=tuple(drive_id(pool) for pool in subset.pools_in),
        output_ids=tuple(read_id(pool) for pool in subset.pools_out),
        rank=rank, error_allowance=error_allowance, input_bound=input_bound,
        horizon_ticks=horizon_ticks,
    )
    return kernel, receipt


def _response_matrix(kernel: Mapping[str, Any], *, ticks: int, force_full: bool) -> dict[str, Any]:
    """Measured input -> readout response of the condensed transceiver itself."""
    rows: list[list[float]] = []
    bounds: list[float] = []
    modes: set[str] = set()
    for name in kernel["input_ids"]:
        state = reset_transceiver(kernel)
        state, receipt = advance_transceiver(
            kernel, state, inputs={name: 1.0}, ticks=int(ticks), force_full=bool(force_full),
        )
        rows.append([float(receipt["values"][out]) for out in kernel["output_ids"]])
        bounds.append(float(receipt["error_bound"]))
        modes.add(str(receipt["mode"]))
    matrix = np.asarray(rows, dtype=np.float64)
    return {
        "matrix": matrix.tolist(),
        "max_error_bound": max(bounds) if bounds else 0.0,
        "modes": sorted(modes),
        "input_ids": list(kernel["input_ids"]),
        "output_ids": list(kernel["output_ids"]),
    }


def access_metrics(
    profile: ResonantProfile, *, subsets: Sequence[PortSubset] = PORT_SUBSETS,
    rank: int = DEFAULT_RANK, error_allowance: float = DEFAULT_ERROR_ALLOWANCE,
    input_bound: float = DEFAULT_INPUT_BOUND, horizon_ticks: int = DEFAULT_HORIZON_TICKS,
    response_ticks: int = DEFAULT_RESPONSE_TICKS, include_response: bool = True,
) -> dict[str, Any]:
    """Reach, read sensitivity, condensation bound and best-k coverage per subset."""
    rows: list[dict[str, Any]] = []
    primary: dict[str, Any] | None = None
    for subset in subsets:
        kernel, receipt = subset_kernel(
            profile, subset, rank=rank, error_allowance=error_allowance,
            input_bound=input_bound, horizon_ticks=horizon_ticks,
        )
        certificate = kernel["certificate"]
        lift = np.asarray(kernel["input_lift"], dtype=np.float64)
        output = np.asarray(kernel["output_rows"], dtype=np.float64)
        rom = kernel["rom"]
        drive = np.asarray(rom["drive"], dtype=np.float64) if rom is not None else np.zeros((0, 0))
        read = np.asarray(rom["output"], dtype=np.float64) if rom is not None else np.zeros((0, 0))
        reach = [float(value) for value in np.linalg.norm(drive[:, : len(subset.pools_in)], axis=0)]
        sense = [float(value) for value in np.linalg.norm(read, axis=1)] if read.size else []
        row = {
            "subset": subset.name,
            "k_in": len(subset.pools_in), "k_out": len(subset.pools_out),
            "input_ids": [drive_id(pool) for pool in subset.pools_in],
            "output_ids": [read_id(pool) for pool in subset.pools_out],
            "status": kernel["status"], "rank": int(kernel["rank"]),
            "dimensions": _jsonable(kernel["dimensions"]),
            "input_lift_column_norms": [float(value) for value in np.linalg.norm(lift, axis=0)],
            "output_rows_row_norms": [float(value) for value in np.linalg.norm(output, axis=1)],
            "rom_drive_column_norms": reach,
            "rom_read_row_norms": sense,
            "structural_coverage": (min(reach) * min(sense)) if reach and sense else 0.0,
            "condensation_error_bound": (
                float(certificate["uniform_unexpanded_output_error_bound"])
                if certificate.get("available") else None
            ),
            "state_residual_norm": certificate.get("state_residual_norm"),
            "input_residual_norm": certificate.get("input_residual_norm"),
            "transition_norm_bound": float(kernel["bounds"]["growth"]),
            "output_gain": float(kernel["bounds"]["output_gain"]),
            "input_gain": float(kernel["bounds"]["input_gain"]),
            "condensation_elapsed_seconds": float(receipt["elapsed_seconds"]),
        }
        rows.append(row)
        if subset.name == "all-pools":
            primary = kernel
    structural = {
        row["subset"]: row["structural_coverage"] for row in rows
    }
    best_subset = max(structural, key=lambda name: structural[name])
    result: dict[str, Any] = {
        "definition": {
            "problem": "ResonantProblem(variable_ids = declared drive+read ids, "
                       "precision = 0.05*I + 0.95*ones/m, observed = drive ids at 0.0); "
                       "the same declared learned objective for every arrangement.",
            "bindings": "explicit deterministic bindings: drive ids on local port 0, read ids on local port 1",
            "input_lift_column_norms": "norms of the kernel's input_lift columns (drive reach); "
                                       "structurally equal to 1 for every arrangement because the input hook is a state pin",
            "output_rows_row_norms": "norms of the kernel's output_rows rows (read sensitivity); "
                                     "structurally equal to 1 for every arrangement because the readout is a port pick-off",
            "coverage": "max over declared subsets of (min reach over the subset's drive ports) * "
                        "(min read sensitivity over the subset's read ports)",
            "response": "advance_transceiver from reset_transceiver with a unit held input on one drive port "
                        "for the declared response ticks; measured, not bounded.",
        },
        "subsets": rows,
        "structural_coverage": structural,
        "coverage_score": float(structural[best_subset]),
        "coverage_score_subset": best_subset,
        "condensation_error_bound_max": float(max(
            row["condensation_error_bound"] for row in rows if row["condensation_error_bound"] is not None
        )) if any(row["condensation_error_bound"] is not None for row in rows) else None,
    }
    if include_response and primary is not None:
        full = _response_matrix(primary, ticks=response_ticks, force_full=True)
        compact = _response_matrix(primary, ticks=response_ticks, force_full=False)
        full_matrix = np.asarray(full["matrix"], dtype=np.float64)
        compact_matrix = np.asarray(compact["matrix"], dtype=np.float64)
        difference = np.abs(full_matrix - compact_matrix)
        row_norms = np.linalg.norm(full_matrix, axis=1)
        column_norms = np.linalg.norm(full_matrix, axis=0)
        tolerance = compact["max_error_bound"] + full["max_error_bound"] + 1e-8
        result["response"] = {
            "horizon_ticks": int(response_ticks),
            "full_matrix": full["matrix"], "compact_matrix": compact["matrix"],
            "full_modes": full["modes"], "compact_modes": compact["modes"],
            "compact_max_error_bound": compact["max_error_bound"],
            "full_max_error_bound": full["max_error_bound"],
            "compact_vs_full_max_difference": float(difference.max()),
            "compact_vs_full_within_bound": bool(difference.max() <= tolerance),
            "worst_drive_row_norm": float(row_norms.min()),
            "best_drive_row_norm": float(row_norms.max()),
            "worst_read_column_norm": float(column_norms.min()),
            "best_read_column_norm": float(column_norms.max()),
            "response_l1": float(np.abs(full_matrix).sum()),
            "response_max_abs": float(np.abs(full_matrix).max()),
            "measured_coverage": float(row_norms.min() * column_norms.min()),
        }
    return result


# --------------------------------------------------------------------------
# hook-effect probes
# --------------------------------------------------------------------------
def hook_effect(profile: ResonantProfile, *, quartic_probe: bool = True) -> dict[str, Any]:
    """Measure which declared hooks actually change the canonical dynamics."""
    ports_per_pool = profile.ports_per_pool
    rail = np.asarray(profile.transport_matrix, dtype=np.float64)
    alternate = replace(profile, topology="meaningful-helix")
    edge_rail = np.zeros_like(rail)
    for source, destination, weight, _kind in profile.edges:
        edge_rail[int(destination), int(source)] += float(weight)
        edge_rail[int(source), int(destination)] -= float(weight)
    result: dict[str, Any] = {
        "declared_topology": profile.topology,
        "projected_transport_used": profile.projected_transport is not None,
        "projected_inv_mass_used": profile.projected_inv_mass is not None,
        "projected_quartic_weights_used": profile.projected_quartic_weights is not None,
        "topology_changes_rail": bool(not np.array_equal(rail, alternate.transport_matrix)),
        "rail_equals_edge_rail": bool(np.array_equal(rail, edge_rail)),
        "edge_count_metadata": len(profile.edges),
        "edge_strength_l1_metadata": float(sum(abs(edge[2]) for edge in profile.edges)),
        "rail_strength_l1": float(np.abs(rail).sum()),
        "rail_antisymmetry_max_abs": float(np.abs(rail + rail.T).max()),
        "rail_dimension": int(rail.shape[0]),
        "rail_nonzero_entries": int(np.count_nonzero(rail)),
    }
    ports = profile.port_count
    pool = (np.arange(2 * ports) % ports) // profile.ports_per_pool
    cross = pool[:, None] != pool[None, :]
    result.update({
        "coupled_pool_pairs": [list(pair) for pair in coupled_pool_pairs(rail, profile.ports_per_pool)],
        "cross_pool_entries": int(np.count_nonzero(rail * cross)),
        "cross_pool_strength_l1": float(np.abs(rail * cross).sum()),
        "intra_pool_strength_l1": float(np.abs(rail * ~cross).sum()),
    })
    mass = np.diag(independent_mass(profile))
    result["inverse_mass_by_pool"] = [
        float(mass[pool_index * profile.ports_per_pool]) for pool_index in range(profile.pools)
    ]
    if not quartic_probe:
        return result
    n = profile.port_count
    ramp = np.ones(n, dtype=np.float64)
    for index in range(1, n):
        ramp[index] = 1.0 + QUARTIC_PROBE_RAMP * (index // ports_per_pool)
    weighted = replace(profile, projected_quartic_weights=ramp)
    base_linear = linear_generator(profile)
    weighted_linear = linear_generator(weighted)
    signal = np.zeros(7, dtype=np.float64)
    signal[QUARTIC_PROBE_POOL] = 1.0

    def retention(candidate: ResonantProfile, path: str, component: str, flow: tuple[float, float]) -> float | None:
        try:
            seeded, impulse = apply_helical_packet_impulse(
                initial_workspace(candidate), path=path, component=component,
                flow_signal=np.asarray(flow, dtype=np.float64),
                work_budget=QUARTIC_PROBE_WORK, evidence_tick=1, event_kind="formation",
            )
            _evolved, advance = advance_workspace(
                seeded, ticks=QUARTIC_PROBE_TICKS, demand=0.0, source_enabled=False,
            )
        except (ResonantNumericalError, np.linalg.LinAlgError, ValueError):
            return None
        return float(advance["end_energy"]) / float(impulse["end_energy"])

    def pool_retention(candidate: ResonantProfile) -> float | None:
        try:
            seeded, impulse = apply_pool_impulse(
                initial_workspace(candidate), pool_signal=signal, work_budget=DEFAULT_IMPULSE_WORK,
                evidence_tick=1, event_kind="formation",
            )
            _evolved, advance = advance_workspace(
                seeded, ticks=QUARTIC_PROBE_TICKS, demand=0.0, source_enabled=False,
            )
        except (ResonantNumericalError, np.linalg.LinAlgError, ValueError):
            return None
        return float(advance["end_energy"]) / float(impulse["end_energy"])

    def arm(kind: str, runner) -> dict[str, Any]:
        base, with_quartic = runner(profile), runner(weighted)
        difference = (
            None if base is None or with_quartic is None else abs(base - with_quartic)
        )
        return {
            "impulse": kind,
            "base_retention_ratio": base,
            "quartic_retention_ratio": with_quartic,
            "abs_retention_difference": difference,
        }

    common = arm(
        "common (pool impulse: momentum along the common coordinate only)",
        pool_retention,
    )
    counterflow = arm(
        "counterflow (packet impulse path=L component=scale flow_signal=(0,1): "
        "momentum along the relative coordinate only)",
        lambda candidate: retention(candidate, "L", "scale", (0.0, 1.0)),
    )
    result["quartic_probe"] = {
        "ramp": "1 + 0.5*pool_index applied to all ports of each pool via projected_quartic_weights",
        "probe_pool": QUARTIC_PROBE_POOL, "probe_ticks": QUARTIC_PROBE_TICKS,
        "linear_generator_max_abs_difference": float(np.abs(base_linear - weighted_linear).max()),
        "linear_spectrum_changed": bool(not np.allclose(base_linear, weighted_linear, atol=0.0, rtol=0.0)),
        "common_impulse": common,
        "counterflow_impulse": counterflow,
        "null_arm_within_tolerance": bool(
            common["abs_retention_difference"] is not None
            and common["abs_retention_difference"] < QUARTIC_NULL_TOLERANCE
        ),
        "nonlinear_retention_changed": bool(
            counterflow["abs_retention_difference"] is not None
            and counterflow["abs_retention_difference"] > QUARTIC_EFFECT_TOLERANCE
        ),
    }
    return result


# --------------------------------------------------------------------------
# per-arrangement measurement
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ExploreConfig:
    ports_per_pool: int = DEFAULT_PORTS_PER_POOL
    retention_ticks: int = DEFAULT_RETENTION_TICKS
    response_ticks: int = DEFAULT_RESPONSE_TICKS
    rank: int = DEFAULT_RANK
    error_allowance: float = DEFAULT_ERROR_ALLOWANCE
    input_bound: float = DEFAULT_INPUT_BOUND
    horizon_ticks: int = DEFAULT_HORIZON_TICKS
    impulse_work: float = DEFAULT_IMPULSE_WORK
    impulse_pools: tuple[int, ...] = DEFAULT_IMPULSE_POOLS
    include_response: bool = True
    include_quartic_probe: bool = True
    seed: int = RANDOM_SEED

    @classmethod
    def compact(cls) -> "ExploreConfig":
        return cls(
            retention_ticks=8, response_ticks=4, include_response=False,
            include_quartic_probe=False,
        )


def measure_arrangement(
    arrangement: Arrangement, config: ExploreConfig, *, include_slow: bool = True
) -> dict[str, Any]:
    """Construct one arrangement twice and measure it."""
    started = time.perf_counter()
    profile = build_profile(arrangement, ports_per_pool=config.ports_per_pool)
    rail = np.asarray(profile.transport_matrix, dtype=np.float64)
    parts = canonical_parts(config.ports_per_pool)
    declared = effective_links(arrangement, ports_per_pool=config.ports_per_pool)
    links = [
        {
            "source_pool": int(source), "destination_pool": int(destination),
            "declared_scale": float(scale),
            "port_pairs": [
                {"source": int(u), "destination": int(v), "weight": _edge_weight(parts, u, v, s)}
                for u, v, s in pool_link_port_pairs((source, destination, scale), parts)
            ],
        }
        for source, destination, scale in declared
    ]
    construction = {
        "name": arrangement.name,
        "kind": arrangement.kind,
        "construction_rule": arrangement.rule,
        "note": arrangement.note,
        "declared_seed": arrangement.seed,
        "declared_topology_hook": arrangement.topology,
        "ports_per_pool": int(profile.ports_per_pool),
        "pools": int(profile.pools),
        "port_count": int(profile.port_count),
        "state_dimension": int(4 * profile.port_count),
        "rail_dimension": int(rail.shape[0]),
        "pool_links": links,
        "pool_link_count": len(links),
        "declared_link_strength_l1": float(sum(abs(link["declared_scale"]) for link in links)),
        "raw_declared_pool_links": [
            {"source_pool": int(source), "destination_pool": int(destination), "unit_scale": float(scale)}
            for source, destination, scale in arrangement.pool_links
        ],
        "density_reference": arrangement.density_reference,
        "rail_sha256": _array_digest(rail),
    }
    record: dict[str, Any] = {
        "construction": construction,
        "hooks": hook_effect(profile, quartic_probe=config.include_quartic_probe),
        "spectrum": spectrum_metrics(profile),
    }
    if include_slow:
        record["retention"] = retention_metrics(
            profile, pools=config.impulse_pools, work=config.impulse_work,
            ticks=config.retention_ticks,
        )
        record["access"] = access_metrics(
            profile, rank=config.rank, error_allowance=config.error_allowance,
            input_bound=config.input_bound, horizon_ticks=config.horizon_ticks,
            response_ticks=config.response_ticks, include_response=config.include_response,
        )
    # declared determinism check: an independent second construction of the same
    # arrangement must reproduce the same construction, rail and spectrum digests.
    second = build_profile(arrangement, ports_per_pool=config.ports_per_pool)
    second_rail = np.asarray(second.transport_matrix, dtype=np.float64)
    second_spectrum = spectrum_metrics(second, rail_gains=())
    first = record["spectrum"]
    determinism = {
        "rail_sha256": _array_digest(second_rail),
        "rail_identical": bool(np.array_equal(rail, second_rail)),
        "generator_sha256": second_spectrum["generator_sha256"],
        "generator_identical": second_spectrum["generator_sha256"] == first["generator_sha256"],
        "eigenvalue_sha256": second_spectrum["eigenvalue_sha256"],
        "eigenvalue_digest_identical": second_spectrum["eigenvalue_sha256"] == first["eigenvalue_sha256"],
        "profile_sha256": canonical_digest(second.as_dict()),
        "profile_sha256_identical": canonical_digest(second.as_dict()) == canonical_digest(profile.as_dict()),
    }
    if include_slow:
        replay = retention_metrics(
            second, pools=(QUARTIC_PROBE_POOL,), work=config.impulse_work,
            ticks=min(config.retention_ticks, QUARTIC_PROBE_TICKS),
        )
        original = retention_metrics(
            profile, pools=(QUARTIC_PROBE_POOL,), work=config.impulse_work,
            ticks=min(config.retention_ticks, QUARTIC_PROBE_TICKS),
        )
        determinism["retention_replay_identical"] = bool(
            replay["by_pool"] == original["by_pool"]
        )
        determinism["retention_replay"] = replay["by_pool"]
    determinism["deterministic"] = bool(
        determinism["rail_identical"] and determinism["generator_identical"]
        and determinism["eigenvalue_digest_identical"] and determinism["profile_sha256_identical"]
    )
    record["determinism"] = determinism
    record["elapsed_seconds"] = time.perf_counter() - started
    return record


def comparisons(records: Sequence[Mapping[str, Any]], *, rail_gain: float = RAIL_GAIN_PROBE) -> dict[str, Any]:
    """Declared cross-arrangement comparisons with margins that can fail."""
    by_name = {record["construction"]["name"]: record for record in records}

    def ratios(name: str) -> dict[int, float] | None:
        record = by_name.get(name)
        if record is None:
            return None
        retention = record.get("retention")
        if not retention:
            return None
        return {
            row["impulse_pool"]: row["retention_ratio"]
            for row in retention["by_pool"] if row["status"] == "measured"
        }

    def retention_row(left: str, right: str) -> dict[str, Any] | None:
        a, b = ratios(left), ratios(right)
        if not a or not b:
            return None
        shared = sorted(set(a) & set(b))
        differences = {pool: abs(a[pool] - b[pool]) for pool in shared}
        worst = max(differences.values()) if differences else 0.0
        return {
            "left": left, "right": right, "metric": "max abs difference of per-pool retention ratios",
            "per_pool_difference": {str(pool): value for pool, value in differences.items()},
            "measured": float(worst),
        }

    def spectrum_row(left: str, right: str) -> dict[str, Any] | None:
        if left not in by_name or right not in by_name:
            return None
        a, b = by_name[left]["spectrum"], by_name[right]["spectrum"]
        return {
            "left": left, "right": right,
            "metric": "abs difference of median inverse participation ratio",
            "left_value": a["ipr_median"], "right_value": b["ipr_median"],
            "measured": float(abs(a["ipr_median"] - b["ipr_median"])),
        }

    rail_invariance = []
    for left, right in RETENTION_RAIL_PAIRS:
        row = retention_row(left, right)
        if row is None:
            continue
        row["expectation"] = "invariant: identical mass metric, different rail"
        row["margin"] = RAIL_INVARIANCE_TOLERANCE
        row["satisfied"] = bool(row["measured"] <= row["margin"])
        rail_invariance.append(row)
    mass_sensitivity = []
    for left, right in RETENTION_MASS_PAIRS:
        row = retention_row(left, right)
        if row is None:
            continue
        row["expectation"] = "sensitive: the mass metric differs"
        row["margin"] = MASS_SENSITIVITY_MARGIN
        row["satisfied"] = bool(row["measured"] >= row["margin"])
        mass_sensitivity.append(row)
    localization = []
    for left, right in LOCALIZATION_PAIRS:
        row = spectrum_row(left, right)
        if row is None:
            continue
        row["expectation"] = "distinguishable: fewer inter-pool links localize modes more"
        row["margin"] = LOCALIZATION_MARGIN
        row["satisfied"] = bool(row["measured"] >= row["margin"])
        localization.append(row)
    gain_rows = []
    for record in records:
        name = record["construction"]["name"]
        gains = {row["gain"]: row for row in record["spectrum"]["cross_pool_gain"]}
        if 1.0 not in gains or rail_gain not in gains:
            continue
        unit, amplified = gains[1.0], gains[rail_gain]
        gain_rows.append({
            "arrangement": name,
            "unit_gain_generator_max_abs_difference": unit["generator_max_abs_difference"],
            "unit_gain_rail_identical": unit["rail_identical_to_arrangement"],
            "amplified_spectrum_changed": amplified["spectrum_changed"],
            "amplified_ipr_median": amplified["ipr_median"],
            "unit_ipr_median": unit["ipr_median"],
            "amplified_frequency_range": amplified["imaginary_magnitude_range"],
            "unit_frequency_range": unit["imaginary_magnitude_range"],
            "couples_no_pools": record["hooks"]["cross_pool_entries"] == 0,
        })
    return {
        "definition": {
            "rail_invariance": "arrangements with identical mass metrics must not be distinguished "
                               "by retention under the canonical damping",
            "mass_sensitivity": "arrangements that change the mass metric must be distinguished by retention",
            "localization": "arrangements with fewer inter-pool links must localize modes more",
            "cross_pool_gain": "scaling the arrangement's own cross-pool rail entries by the declared "
                               "gain separates arrangements that look alike at the canonical coupling scale",
        },
        "retention_rail_invariance": rail_invariance,
        "retention_mass_sensitivity": mass_sensitivity,
        "localization_separation": localization,
        "cross_pool_gain": gain_rows,
        "all_expectations_satisfied": bool(
            all(row["satisfied"] for row in rail_invariance + mass_sensitivity + localization)
            and all(row["unit_gain_generator_max_abs_difference"] <= 1e-12 for row in gain_rows)
        ),
    }


def exploration_declarations(config: ExploreConfig) -> dict[str, Any]:
    return {
        "question": "which declared arrangement geometries make bounded drives excite "
                    "persistent, distinguishable, structured and accessible patterns?",
        "scope": "bounded numerical exploration of declared connection/metric scaffolds; "
                 "arrangements are candidate scaffolds, not memory or task claims.",
        "ports_per_pool": config.ports_per_pool,
        "chain_scale_unit": CHAIN_SCALE,
        "chain_scale_origin": "canonical cross-pool convention: circuit edge (scale 1.0) plus "
                              "neck edge (scale 0.7) share one boundary port pair",
        "core_shell": {
            "transport_decay": CORE_SHELL_DECAY, "core_pool": CORE_SHELL_CORE_POOL,
            "pool_distance": "ring distance min(|a-b|, 7-|a-b|)",
            "inverse_mass_decay": CORE_SHELL_INV_MASS_DECAY,
        },
        "random_seed": config.seed,
        "retention": {"ticks": config.retention_ticks, "work_budget": config.impulse_work,
                      "impulse_pools": list(config.impulse_pools)},
        "access": {"rank": config.rank, "error_allowance": config.error_allowance,
                   "input_bound": config.input_bound, "horizon_ticks": config.horizon_ticks,
                   "response_ticks": config.response_ticks,
                   "prior_ridge": PRIOR_RIDGE, "prior_mass": PRIOR_MASS},
        "port_subsets": {
            subset.name: {"pools_in": list(subset.pools_in), "pools_out": list(subset.pools_out)}
            for subset in PORT_SUBSETS
        },
        "boundary": [
            "Every number is a geometric/access proxy on a declared scaffold.",
            "Acquisition (spectrum) is a linearization at rest with beta=0, not the evolving nonlinear body.",
            "Retention is energy ratio under the canonical damping and source-off advance, not recall quality.",
            "Access is measured through the declared learned objective and declared ports, not through a task.",
            "No arrangement claim here is a claim about memory utility, learning, or task performance.",
        ],
    }


def explore(
    config: ExploreConfig | None = None, *, names: Sequence[str] | None = None
) -> dict[str, Any]:
    config = config or ExploreConfig()
    started = time.perf_counter()
    selected = [item for item in arrangements(seed=config.seed) if names is None or item.name in names]
    if names is not None and len(selected) != len(tuple(names)):
        raise ResonantNumericalError(f"unknown arrangement name in {tuple(names)}")
    records = [measure_arrangement(item, config) for item in selected]
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "declarations": exploration_declarations(config),
        "arrangements": records,
        "comparisons": comparisons(records),
        "limitations": [
            "pools is fixed at exactly 7 and ports_per_pool must be >= 4, so no arrangement can "
            "change the pool count or the minimum port resolution.",
            "ResonantProfile.coordinates is computed from a fixed formula and has no declared hook, "
            "so spatial spacing (quasiperiodic intervals, literal shell radii) cannot be expressed; "
            "the nearest expressible variant modulates interaction strengths instead.",
            "profile.edges is ignored by project/_WaveOperator.rail whenever projected_transport is set, "
            "so every constructed arrangement must re-declare the intra/bridge structure explicitly and "
            "topology becomes metadata-only for it.",
            "projected_inv_mass accepts only a positive per-port vector or an SPD matrix on the 2n paired "
            "port coordinates; the shell metric is a diagonal (per-port) form.",
            "projected_quartic_weights is per-port, not per-pool, so a per-pool nonlinearity must be "
            "replicated across that pool's ports; it also cannot change the beta=0 linear spectrum at all.",
        ],
        "runtime_seconds": None,
        "receipt_sha256": None,
    }
    receipt["runtime_seconds"] = time.perf_counter() - started
    receipt["receipt_sha256"] = content_digest(receipt)
    return receipt


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def format_table(receipt: Mapping[str, Any]) -> str:
    pools = receipt["declarations"]["retention"]["impulse_pools"]
    access = receipt["declarations"]["access"]
    envelope = (
        f"rank={access['rank']} allowance={access['error_allowance']:g} "
        f"input_bound={access['input_bound']:g} horizon={access['horizon_ticks']} "
        f"response_ticks={access['response_ticks']} "
        f"precision={access['prior_ridge']:g}*I+{access['prior_mass']:g}*ones/m"
    )
    header = (
        f"{'arrangement':<23}{'kind':<20}{'rail_l1':>9}{'x-pool':>7}{'Re_max':>10}"
        f"{'|Im| range':>20}{'ipr_med':>9}{'loc%':>6}{'ret@' + '/'.join(str(p) for p in pools):>22}"
        f"{'spread':>9}{'stcov':>8}{'meascov':>9}{'det':>5}"
    )
    lines = [header, "-" * len(header)]
    worst_error = 0.0
    for record in receipt["arrangements"]:
        spectrum = record["spectrum"]
        hooks = record["hooks"]
        retention = record.get("retention") or {}
        rows = {row["impulse_pool"]: row for row in retention.get("by_pool", [])}
        ratios = " ".join(
            f"{rows[pool]['retention_ratio']:.3f}" if rows.get(pool, {}).get("status") == "measured"
            else "   -  "
            for pool in pools
        )
        access_record = record.get("access") or {}
        error = access_record.get("condensation_error_bound_max")
        worst_error = max(worst_error, error or 0.0)
        measured = (access_record.get("response") or {}).get("measured_coverage")
        lines.append(
            f"{record['construction']['name']:<23}"
            f"{record['construction']['kind']:<20}"
            f"{hooks['rail_strength_l1']:>9.4f}"
            f"{hooks['cross_pool_strength_l1']:>7.4f}"
            f"{spectrum['maximum_growth_rate']:>10.5f}"
            f"{spectrum['imaginary_magnitude_range'][0]:>10.4f}"
            f"{spectrum['imaginary_magnitude_range'][1]:>10.4f}"
            f"{spectrum['ipr_median']:>9.4f}"
            f"{100.0 * spectrum['localized_mode_fraction']:>6.1f}"
            f"{ratios:>24}"
            f"{(retention.get('site_dependence') or 0.0):>9.4f}"
            f"{(access_record.get('coverage_score') or 0.0):>8.4f}"
            f"{(measured if measured is not None else float('nan')):>9.4f}"
            f"{'yes' if record['determinism']['deterministic'] else 'NO':>5}"
        )
    lines.append("")
    lines.append(
        "columns: rail_l1 = sum|rail| actually used; x-pool = sum|rail| restricted to cross-pool "
        "entries; Re_max = max real eigenvalue of the beta=0 generator; |Im| range = |Im| eigenvalue "
        "range; ipr_med = median inverse participation ratio; loc% = fraction of modes with "
        f"IPR >= {LOCALIZATION_IPR_FACTOR}/dim; ret@... = retained energy ratio per impulse pool; "
        "spread = max-min retention; stcov = best-subset structural coverage; meascov = measured "
        "transceiver response coverage; det = determinism check."
    )
    lines.append(
        f"runtime_seconds: {receipt['runtime_seconds']:.2f}   "
        f"worst condensation error bound: {worst_error:.3g}   "
        f"declared access envelope: {envelope}"
    )
    lines.append(
        f"determinism: {sum(1 for r in receipt['arrangements'] if r['determinism']['deterministic'])}"
        f"/{len(receipt['arrangements'])} arrangements reproduce identical profile, rail, generator "
        f"and eigenvalue digests on a second independent construction."
    )
    declared = receipt["comparisons"]
    for section, label in (
        ("retention_rail_invariance", "retention rail-invariance (expect <= margin)"),
        ("retention_mass_sensitivity", "retention mass-sensitivity (expect >= margin)"),
        ("localization_separation", "localization separation (expect >= margin)"),
    ):
        for row in declared[section]:
            lines.append(
                f"{label}: {row['left']} vs {row['right']} measured={row['measured']:.3g} "
                f"margin={row['margin']:.3g} satisfied={row['satisfied']}"
            )
    for row in declared["cross_pool_gain"]:
        lines.append(
            f"cross-pool rail gain x{RAIL_GAIN_PROBE:g}: {row['arrangement']:<23} "
            f"unit-gain rail identical={row['unit_gain_rail_identical']} "
            f"spectrum changed={row['amplified_spectrum_changed']} "
            f"ipr_med {row['unit_ipr_median']:.4f} -> {row['amplified_ipr_median']:.4f} "
            f"couples_no_pools={row['couples_no_pools']}"
        )
    lines.append(f"all declared expectations satisfied: {declared['all_expectations_satisfied']}")
    lines.append(f"receipt_sha256: {receipt['receipt_sha256']}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--ports-per-pool", type=int, default=DEFAULT_PORTS_PER_POOL)
    args = parser.parse_args(argv)
    config = replace(ExploreConfig(), ports_per_pool=args.ports_per_pool)
    receipt = explore(config)
    rendered = json.dumps(_jsonable(receipt), indent=2, sort_keys=True, allow_nan=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(format_table(receipt))
    print(f"receipt_bytes: {len(rendered) + 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
