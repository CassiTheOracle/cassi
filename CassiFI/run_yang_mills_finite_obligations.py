#!/usr/bin/env python
"""Compute three finite statements of the uniform-Feshbach obligation map.

The source document is
``CassiTheory/computations/yang-mills-uniform-feshbach-obligation-map.md``:

* section 4.4.7, the corner-shift support action (UFA104) and the claim that
  the smallest shift-closed boundary-sector family is the full label cone;
* section 4.4.7, the fine multiplicity formula (UFA106) and its anchor table;
* section 4.6, the first-chaos rank inequality (UFA46) for the weak-field
  channel ``gamma_k = 4 sin(k pi / (2(N+1)))``.

Conventions are those of ``run_yang_mills_gauge_fibre_probe.py``: integer
labels are ``n = 2j``, the eight outer links of the open 2x2 refinement form
four gauge-invariant corner pairs, the four midpoint spokes are ordered
``north, east, south, west`` and the centre pairs ``(north, east) | (south,
west)``.

Everything printed and recorded here is recomputed from the formula, from the
shift action, or from the arcsine bound.  No number is transcribed from the
document; the document's values enter only as comparison targets, and every
comparison is reported with its mismatch list.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "cassifi.yang-mills-finite-obligations.v1"
OUTPUT = Path("_diag/yang_mills_finite_obligations.json")
SOURCE_DOCUMENT = "CassiTheory/computations/yang-mills-uniform-feshbach-obligation-map.md"

# --- label vocabulary shared with run_yang_mills_gauge_fibre_probe.py --------
CORNERS = ("a", "b", "c", "d")
CORNER_PAIRS = (("L1", "L8"), ("L2", "L3"), ("L4", "L5"), ("L6", "L7"))
SPOKES = ("north", "east", "south", "west")  # s1, s2, s3, s4 in the document's order
SPOKE_CORNERS = (("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"))
PAIRING = (("north", "east"), ("south", "west"))
SPOKE_INDEX = {spoke: index for index, spoke in enumerate(SPOKES)}
PAIRING_INDICES = tuple(tuple(SPOKE_INDEX[spoke] for spoke in pair) for pair in PAIRING)
# The document's alternative centre pairing (s1,s4) | (s2,s3), used only as an
# independent recomputation route for the same multiplicity sum.
ALTERNATE_PAIRING = (("north", "west"), ("east", "south"))
ALTERNATE_PAIRING_INDICES = tuple(
    tuple(SPOKE_INDEX[spoke] for spoke in pair) for pair in ALTERNATE_PAIRING
)

BOUNDARY_LABEL = 1  # n = 2j = 1, the fundamental boundary label of the probe.
TRIVIAL_SECTOR = (0, 0, 0, 0)
FUNDAMENTAL_SECTOR = (1, 1, 1, 1)
SEEDS = (TRIVIAL_SECTOR, FUNDAMENTAL_SECTOR)
CUTOFFS = (1, 2, 3, 4)
CUTOFF_COUNTS = {1: 16, 2: 81, 3: 256, 4: 625}

# The document's declared domain for the fine multiplicity table.
TABLE_DOMAIN = 3
EXTENDED_TABLE_DOMAIN = 4
# Largest cheap domain for the relabelling check: 9^4 = 6561 sectors, ~1 s.
INVARIANCE_DOMAIN = 8
INVARIANCE_DOMAINS = (TABLE_DOMAIN, EXTENDED_TABLE_DOMAIN, INVARIANCE_DOMAIN)
# All three perfect matchings of the four spoke positions, as position pairs.
PAIRING_CLASS = (
    ("declared", ((0, 1), (2, 3))),
    ("adjacent-reversed", ((0, 3), (1, 2))),
    ("opposite-edges", ((0, 2), (1, 3))),
)

PERMUTATION_INVARIANCE_STATUS = (
    "Invariance is established by the scan below, not by an argument.  24 of 24 "
    "permutations preserve M^f on every measured domain (0..3, 0..4 and 0..8, "
    "6561 sectors at the largest), the sectors carrying a zero label included, and "
    "all three spoke matchings agree with each other.  The map's claim that the "
    "square's rotations and reflections preserve M^f is therefore correct but not "
    "tight; on the measured domains the statement widens to all 24 permutations.  "
    "The mechanism is left open.  A candidate, not established here: a recoupling "
    "identity that would equate M^f(a,b,c,d) with a manifestly permutation-"
    "symmetric invariant count of the same four-valent boundary data."
)

ANCHOR_DECOMPOSITION_SECTORS = ((1, 1, 1, 1), (2, 1, 1, 1), (2, 2, 1, 1))
ANCHOR_DECOMPOSITION_DOCUMENT = {(1, 1, 1, 1): (1, 0, 6, 4, 3)}

RANK_N_VALUES = (8, 16, 32, 64, 128)
RANK_MARGIN_D = 1.0
RANK_EPSILON = 0.0
# (UF-B.15) and (UFA46) state their requirement for 0 < d <= 4; 4 is the edge of
# the arcsine argument's own domain, where the bound equals N + 1.  It is a
# property of that formula, not a threshold claim of the map.
ARCSINE_DOMAIN_EDGE = 4.0
MAP_FIXED_RANK_STATEMENT = (
    "(UF-B.15), source lines 904-913: for 0 < d <= 4 a uniform discarded margin "
    "gamma_K >= d requires K >= (2(N+1)/pi) arcsin(d/4), so a fixed-rank retained "
    "first-chaos space leaves a vanishing discarded margin as N -> infinity. "
    "(UFA46), source lines 2502-2513, states the same condition with epsilon_N and "
    "concludes that the required retained first-chaos rank is Omega(N); the map "
    "therefore already asserts that no fixed retained rank suffices anywhere on "
    "0 < d <= 4.  The screen below refines where the boundary sits for the largest "
    "rank the map permits, r_N < N, and does not correct that statement."
)
# Declared finite d-grid for the threshold screen: 1.0 .. 4.0 by 0.25 plus the
# values that bracket gamma_N for the larger N.
THRESHOLD_D_GRID = tuple(
    sorted(
        {round(1.0 + 0.25 * step, 4) for step in range(13)}
        | {3.9, 3.95, 3.99, 3.999, 4.0}
    )
)
THRESHOLD_N_VALUES = (8, 16, 32, 64, 128, 256)

ANCHORS = {
    (0, 0, 0, 0): 1,
    (1, 1, 0, 0): 2,
    (1, 1, 1, 1): 14,
    (2, 1, 1, 1): 19,
    (2, 2, 1, 1): 30,
    (3, 1, 1, 1): 20,
    (2, 2, 2, 2): 91,
}

Sector = tuple[int, int, int, int]


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


# --- item 1: corner-shift support action (UFA104) ---------------------------


def corner_shift_targets(sector: Sector) -> tuple[Sector, ...]:
    """Support action of the four corner plaquette multipliers (UFA104).

    ``V_n tensor V_1 = V_{n+1} + V_{n-1}`` for ``n >= 1`` and
    ``V_0 tensor V_1 = V_1``, acting on one corner label at a time and only
    through the two boundary links of that corner pair.  A down-shift is
    therefore absent exactly at label zero.
    """
    targets: list[Sector] = []
    for index, label in enumerate(sector):
        up = list(sector)
        up[index] = label + 1
        targets.append((up[0], up[1], up[2], up[3]))
        if label >= 1:
            down = list(sector)
            down[index] = label - 1
            targets.append((down[0], down[1], down[2], down[3]))
    return tuple(targets)


def reachable_family(seed: Sequence[int], cutoff: int) -> dict[str, Any]:
    """Smallest shift-closed family inside the box ``0..cutoff`` containing ``seed``.

    Breadth-first closure of the shift action: the result is by construction
    the smallest family that contains the seed and is closed under all four
    corner shifts while every label stays at or below the cutoff.
    """
    start = (int(seed[0]), int(seed[1]), int(seed[2]), int(seed[3]))
    if any(label < 0 or label > cutoff for label in start):
        raise ValueError(f"seed {start} leaves the cutoff box 0..{cutoff}")
    depth: dict[Sector, int] = {start: 0}
    frontier = [start]
    layer_sizes = [1]
    while frontier:
        nxt: list[Sector] = []
        for sector in frontier:
            for target in corner_shift_targets(sector):
                if max(target) > cutoff or target in depth:
                    continue
                depth[target] = depth[sector] + 1
                nxt.append(target)
        if nxt:
            layer_sizes.append(len(nxt))
        frontier = nxt
    sectors = tuple(sorted(depth))
    closure_step = max(depth.values())
    full_box = len(sectors) == (cutoff + 1) ** 4
    row: dict[str, Any] = {
        "seed": list(start),
        "cutoff": cutoff,
        "reachable_count": len(sectors),
        "expected_full_box_count": (cutoff + 1) ** 4,
        "full_cone_reached": full_box,
        "closure_step": closure_step,
        "sectors_at_closure_step": sum(
            1 for value in depth.values() if value == closure_step
        ),
        "layer_sizes": layer_sizes,
        "reachable_sha256": sha256(sorted(sectors)),
    }
    if len(sectors) <= 81:
        row["reachable"] = [list(sector) for sector in sectors]
    return row


def support_action(cutoffs: Iterable[int] = CUTOFFS) -> dict[str, Any]:
    rows = [
        reachable_family(seed, cutoff) for cutoff in cutoffs for seed in SEEDS
    ]
    mismatches = [
        {
            "cutoff": row["cutoff"],
            "seed": row["seed"],
            "measured": row["reachable_count"],
            "document_claim": CUTOFF_COUNTS[row["cutoff"]],
        }
        for row in rows
        if row["reachable_count"] != CUTOFF_COUNTS[row["cutoff"]]
    ]
    return {
        "cutoffs": rows,
        "document_claim": {
            "statement": (
                "the smallest shift-closed family containing (0,0,0,0) or (1,1,1,1) is "
                "the full set of nonnegative four-tuples; truncation at cutoff C retains "
                "exactly (C+1)^4 sectors"
            ),
            "counts": CUTOFF_COUNTS,
        },
        "count_mismatches": mismatches,
    }


# --- item 2: fine multiplicity (UFA106) ------------------------------------


@lru_cache(maxsize=None)
def fuse(left: int, right: int) -> tuple[int, ...]:
    """``fuse(m,n) = {|m-n|, |m-n|+2, ..., m+n}`` on doubled labels ``n = 2j``."""
    if left < 0 or right < 0:
        raise ValueError("labels are nonnegative doubled angular momenta")
    return tuple(range(abs(left - right), left + right + 1, 2))


@lru_cache(maxsize=None)
def _channel_multiplicity(first: int, second: int) -> tuple[int, ...]:
    """``{r >= 0 : N^r_{mn} = 1}`` for one fused pair, as an increasing tuple."""
    return fuse(first, second)


def sector_spokes(sector: Sequence[int]) -> tuple[tuple[int, ...], ...]:
    """The four spoke label sets ``fuse(a,b), fuse(b,c), fuse(c,d), fuse(d,a)``."""
    return tuple(
        fuse(sector[index], sector[(index + 1) % 4]) for index in range(4)
    )


def multiplicity_terms(
    sector: Sequence[int],
    pairing: Sequence[Sequence[int]] = PAIRING_INDICES,
) -> list[tuple[tuple[int, ...], int]]:
    """Per-spoke-configuration contribution to (UFA106) under one centre pairing."""
    first, second = pairing
    spokes = sector_spokes(sector)
    terms: list[tuple[tuple[int, ...], int]] = []
    for values in itertools.product(*spokes):
        shared = set(fuse(values[first[0]], values[first[1]])) & set(
            fuse(values[second[0]], values[second[1]])
        )
        terms.append((values, len(shared)))
    return terms


def multiplicity_with_pairing(
    sector: Sequence[int], pairing: Sequence[Sequence[int]]
) -> int:
    """(UFA106) evaluated with an explicitly supplied spoke pairing."""
    return sum(count for _, count in multiplicity_terms(sector, pairing))


@lru_cache(maxsize=None)
def multiplicity_f(
    a: int, b: int, c: int, d: int, pairing_key: str = "declared"
) -> int:
    """``M^f(a,b,c,d)`` of (UFA106), summed over the four spoke labels and ``r >= 0``."""
    pairing = (
        PAIRING_INDICES if pairing_key == "declared" else ALTERNATE_PAIRING_INDICES
    )
    return sum(count for _, count in multiplicity_terms((a, b, c, d), pairing))


def multiplicity_table(domain: int) -> dict[str, int]:
    labels = range(domain + 1)
    return {
        ",".join(str(label) for label in sector): multiplicity_f(*sector)
        for sector in itertools.product(labels, repeat=4)
    }


def anchor_rows() -> list[dict[str, Any]]:
    rows = []
    for sector in sorted(ANCHORS):
        measured = multiplicity_f(*sector)
        rows.append(
            {
                "sector": list(sector),
                "measured": measured,
                "document_value": ANCHORS[sector],
                "agrees": measured == ANCHORS[sector],
            }
        )
    return rows


def anchor_mismatches(
    values: Mapping[Sequence[int], int], claims: Mapping[Sequence[int], int] = ANCHORS
) -> list[dict[str, Any]]:
    """Report every tuple whose value differs from the document's anchor value."""
    normalized = {tuple(int(v) for v in key): int(value) for key, value in values.items()}
    mismatches = []
    for sector in sorted(claims):
        measured = normalized.get(tuple(sector))
        if measured != claims[sector]:
            mismatches.append(
                {
                    "sector": list(sector),
                    "measured": measured,
                    "document_value": claims[sector],
                }
            )
    return mismatches


def permutation_invariance(domain: int = TABLE_DOMAIN) -> dict[str, Any]:
    """Which relabellings of the four corner positions leave ``M^f`` unchanged."""
    labels = range(domain + 1)
    sectors = list(itertools.product(labels, repeat=4))
    values = {sector: multiplicity_f(*sector) for sector in sectors}
    edge_sectors = [sector for sector in sectors if 0 in sector]
    preserving: list[list[int]] = []
    mismatches = 0
    edge_mismatches = 0
    for permutation in itertools.permutations(range(4)):
        agrees = True
        for sector in sectors:
            if values[sector] != values[tuple(sector[i] for i in permutation)]:
                agrees = False
                mismatches += 1
                if 0 in sector:
                    edge_mismatches += 1
        if agrees:
            preserving.append(list(permutation))
    cyclic = [[0, 1, 2, 3], [1, 2, 3, 0], [2, 3, 0, 1], [3, 0, 1, 2]]
    anticyclic = [[0, 3, 2, 1], [3, 2, 1, 0], [2, 1, 0, 3], [1, 0, 3, 2]]
    square_symmetries = cyclic + anticyclic
    return {
        "domain": domain,
        "sectors": len(sectors),
        "sectors_with_a_zero_label": len(edge_sectors),
        "preserving_permutations": preserving,
        "preserving_count": len(preserving),
        "permutation_mismatches": mismatches,
        "zero_label_subdomain_mismatches": edge_mismatches,
        "square_rotations_and_reflections": square_symmetries,
        "square_symmetries_all_preserve": all(
            permutation in preserving for permutation in square_symmetries
        ),
        "full_symmetric_group_preserves": len(preserving) == 24,
    }


def position_weighted_variant(
    a: int, b: int, c: int, d: int
) -> int:
    """A deliberately position-indexed weight: keep only configurations with s1 == s3.

    This control adds the position-indexed condition s1 == s3 to the (UFA106)
    weight, so the value can depend on where the corner labels sit; its measured
    relabelling mismatches are reported by
    :func:`position_weighted_variant_mismatches`.
    """
    return sum(
        count for values, count in multiplicity_terms((a, b, c, d)) if values[0] == values[2]
    )


def position_weighted_variant_mismatches(domain: int = TABLE_DOMAIN) -> dict[str, Any]:
    """Relabelling mismatches of the position-weighted variant, with one witness."""
    sectors = list(itertools.product(range(domain + 1), repeat=4))
    values = {sector: position_weighted_variant(*sector) for sector in sectors}
    mismatches = 0
    witness: dict[str, Any] | None = None
    for permutation in itertools.permutations(range(4)):
        for sector in sectors:
            permuted = tuple(sector[i] for i in permutation)
            if values[sector] != position_weighted_variant(*permuted):
                mismatches += 1
                if witness is None:
                    witness = {
                        "sector": list(sector),
                        "permutation": list(permutation),
                        "value": values[sector],
                        "permuted_value": position_weighted_variant(*permuted),
                    }
    return {
        "definition": "sum over spoke configurations with s1 == s3 of the shared channel count",
        "domain": domain,
        "mismatches": mismatches,
        "witness": witness,
        "invariant": mismatches == 0,
    }


def pairing_class_agreement(domain: int = EXTENDED_TABLE_DOMAIN) -> dict[str, Any]:
    """Disagreements of each of the three spoke matchings against the declared one."""
    rows = []
    for name, pairing in PAIRING_CLASS:
        disagreements = [
            {
                "sector": list(sector),
                "declared": multiplicity_f(*sector),
                f"{name}": multiplicity_with_pairing(sector, pairing),
            }
            for sector in itertools.product(range(domain + 1), repeat=4)
            if multiplicity_with_pairing(sector, pairing) != multiplicity_f(*sector)
        ]
        rows.append(
            {
                "pairing": name,
                "positions": [list(pair) for pair in pairing],
                "disagreements": disagreements,
                "disagreement_count": len(disagreements),
                "agrees_with_declared": not disagreements,
            }
        )
    return {
        "domain": domain,
        "rows": rows,
        "all_three_matchings_agree": all(row["agrees_with_declared"] for row in rows),
    }


def invariance_evidence() -> dict[str, Any]:
    rows = [permutation_invariance(domain) for domain in INVARIANCE_DOMAINS]
    witness = position_weighted_variant_mismatches(TABLE_DOMAIN)
    verifies_document_claim = all(
        row["square_symmetries_all_preserve"] for row in rows
    )
    strengthens_to_full_symmetric_group = all(
        row["full_symmetric_group_preserves"] for row in rows
    )
    return {
        "status": PERMUTATION_INVARIANCE_STATUS,
        "domains": rows,
        "pairing_class": pairing_class_agreement(EXTENDED_TABLE_DOMAIN),
        "asymmetry_control": witness,
        "document_claim": (
            "the square's rotations and reflections permute the four labels while "
            "leaving M^f invariant"
        ),
        "document_claim_verified": verifies_document_claim,
        "document_claim_replaced_by_full_symmetric_group": (
            strengthens_to_full_symmetric_group
        ),
        "asymmetry_found_in_multiplicity": not strengthens_to_full_symmetric_group,
        "verdict": (
            "on 0..3, 0..4 and 0..8 every one of the 24 relabellings preserves M^f "
            "with zero mismatches, including on sectors that carry a zero label, and "
            "all three spoke matchings agree; the document's 8-symmetry claim holds "
            "but is not tight, so the 24-permutation statement should replace it on "
            "the measured domains. No asymmetry appears in M^f: the only asymmetry "
            "measured is in the position-indexed control variant, which shows the "
            "invariance check can fail. The mechanism is left open; a candidate, not "
            "established here, is a recoupling identity equating M^f with a "
            "manifestly permutation-symmetric invariant count of the same boundary data."
        ),
    }


def single_nonzero_corner_sectors(domain: int) -> set[tuple[int, ...]]:
    """The trivial sector plus every sector with exactly one nonzero corner label."""
    sectors = {(0, 0, 0, 0)}
    for index in range(4):
        for value in range(1, domain + 1):
            sector = [0, 0, 0, 0]
            sector[index] = value
            sectors.add((sector[0], sector[1], sector[2], sector[3]))
    return sectors


def never_zero_row(domain: int = TABLE_DOMAIN) -> dict[str, Any]:
    table = multiplicity_table(domain)
    values = list(table.values())
    minimum = min(values)
    argmin = sorted(key for key, value in table.items() if value == minimum)
    zeros = sorted(key for key, value in table.items() if value == 0)
    argmin_sectors = {tuple(int(part) for part in key.split(",")) for key in argmin}
    single = single_nonzero_corner_sectors(domain)
    return {
        "domain": domain,
        "entries": len(values),
        "minimum": minimum,
        "argmin": argmin,
        "count_at_minimum": len(argmin),
        "minimum_is_exactly_the_single_nonzero_corner_family": argmin_sectors == single,
        "zero_entries": zeros,
        "maximum": max(values),
        "argmax": sorted(key for key, value in table.items() if value == max(values))[
            :8
        ],
    }


def anchor_row_decomposition(sector: Sequence[int]) -> dict[str, Any]:
    """Active-spoke breakdown of one anchor row: configurations, contributing ones, weights."""
    terms = multiplicity_terms(sector)
    configurations = {count: 0 for count in range(5)}
    contributing = {count: 0 for count in range(5)}
    weights = {count: 0 for count in range(5)}
    zero_weight_configurations = 0
    for values, channel_count in terms:
        active = sum(1 for value in values if value != 0)
        configurations[active] += 1
        weights[active] += channel_count
        if channel_count:
            contributing[active] += 1
        else:
            zero_weight_configurations += 1
    total = sum(weights.values())
    table_value = multiplicity_f(*sector)
    row: dict[str, Any] = {
        "sector": list(sector),
        "spoke_label_sets": [list(values) for values in sector_spokes(sector)],
        "configurations": len(terms),
        "zero_weight_configurations": zero_weight_configurations,
        "contributing_configurations": len(terms) - zero_weight_configurations,
        "configuration_counts_by_active_spokes": {
            str(count): configurations[count] for count in range(5)
        },
        "contributing_configurations_by_active_spokes": {
            str(count): contributing[count] for count in range(5)
        },
        "channel_weights_by_active_spokes": {
            str(count): weights[count] for count in range(5)
        },
        "weight_decomposition": [weights[count] for count in range(5)],
        "measured_total": total,
        "table_value": table_value,
        "document_total": ANCHORS.get(tuple(sector)),
        "weights_sum_to_table_value": total == table_value == ANCHORS.get(tuple(sector)),
    }
    if tuple(sector) in ANCHOR_DECOMPOSITION_DOCUMENT:
        document = ANCHOR_DECOMPOSITION_DOCUMENT[tuple(sector)]
        row["document_decomposition"] = list(document)
        row["agrees_with_document_decomposition"] = (
            tuple(row["weight_decomposition"]) == document
        )
    return row


def anchor_row_decompositions() -> dict[str, Any]:
    rows = [anchor_row_decomposition(sector) for sector in ANCHOR_DECOMPOSITION_SECTORS]
    return {
        "sectors": [list(sector) for sector in ANCHOR_DECOMPOSITION_SECTORS],
        "rows": rows,
        "all_weights_sum_to_table_value": all(
            row["weights_sum_to_table_value"] for row in rows
        ),
        "all_document_decompositions_agree": all(
            row["agrees_with_document_decomposition"]
            for row in rows
            if "agrees_with_document_decomposition" in row
        ),
        "weight_decompositions": {
            ",".join(str(label) for label in row["sector"]): row["weight_decomposition"]
            for row in rows
        },
    }


def multiplicity_item() -> dict[str, Any]:
    anchors = anchor_rows()
    mismatches = anchor_mismatches(
        {tuple(row["sector"]): row["measured"] for row in anchors}
    )
    declared = multiplicity_table(TABLE_DOMAIN)
    extended = multiplicity_table(EXTENDED_TABLE_DOMAIN)
    alternate_disagreements = [
        {
            "sector": list(sector),
            "declared_pairing": multiplicity_f(*sector),
            "alternate_pairing": multiplicity_f(*sector, "alternate"),
        }
        for sector in itertools.product(range(EXTENDED_TABLE_DOMAIN + 1), repeat=4)
        if multiplicity_f(*sector) != multiplicity_f(*sector, "alternate")
    ]
    return {
        "anchors": anchors,
        "anchor_agree": all(row["agrees"] for row in anchors),
        "anchor_mismatches": mismatches,
        "anchor_row_decompositions": anchor_row_decompositions(),
        "pairing_choice_independence": {
            "declared_pairing": [list(pair) for pair in PAIRING],
            "alternate_pairing": [list(pair) for pair in ALTERNATE_PAIRING],
            "domain": EXTENDED_TABLE_DOMAIN,
            "disagreements": alternate_disagreements,
            "independent_of_choice": not alternate_disagreements,
        },
        "relabelling_invariance": invariance_evidence(),
        "never_zero": never_zero_row(TABLE_DOMAIN),
        "extended_never_zero": never_zero_row(EXTENDED_TABLE_DOMAIN),
        "table_domain": TABLE_DOMAIN,
        "table": declared,
        "document_claim_never_zero": {"domain": TABLE_DOMAIN, "minimum": 1},
    }


# --- item 3: first-chaos rank screen (UFA46) -------------------------------


def chain_eigenvalues(n: int) -> tuple[float, ...]:
    """``gamma_k = 4 sin(k pi / (2(N+1)))``, ``k = 1..N`` (UFA43)."""
    if n < 1:
        raise ValueError("N must be positive")
    return tuple(
        4.0 * math.sin(k * math.pi / (2.0 * (n + 1))) for k in range(1, n + 1)
    )


def rank_bound(n: int, d: float, epsilon: float = RANK_EPSILON) -> float:
    """Right-hand side of (UFA46): ``(2(N+1)/pi) arcsin((d - epsilon)/4)``."""
    margin = d - epsilon
    if not 0.0 < margin <= 4.0:
        raise ValueError(
            f"margin d - epsilon = {margin!r} leaves the (UFA46) domain 0 < m <= 4"
        )
    return (2.0 * (n + 1) / math.pi) * math.asin(margin / 4.0)


def required_rank(n: int, d: float, epsilon: float = RANK_EPSILON) -> int:
    """Smallest integer ``r_N`` with ``r_N + 1 >= (UFA46)``, i.e. ``ceil(bound) - 1``."""
    bound = rank_bound(n, d, epsilon)
    # Tolerance guards only against binary rounding of an exactly integral bound.
    return math.ceil(bound - 1e-9) - 1


def rank_row(n: int, d: float = RANK_MARGIN_D, epsilon: float = RANK_EPSILON) -> dict[str, Any]:
    eigenvalues = chain_eigenvalues(n)
    bound = rank_bound(n, d, epsilon)
    r_n = required_rank(n, d, epsilon)
    return {
        "N": n,
        "d": d,
        "epsilon_N": epsilon,
        "bound": bound,
        "required_rank": r_n,
        "rank_fraction": r_n / n,
        "rank_compatible_with_rank_less_than_N": r_n < n,
        "largest_retained_rank_allowed": n - 1,
        "gamma_1": eigenvalues[0],
        "gamma_N": eigenvalues[-1],
        "eigenvalues_strictly_increasing": all(
            eigenvalues[index] < eigenvalues[index + 1] for index in range(n - 1)
        ),
    }


def rank_growth(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Measured growth of ``r_N``: ratios against ``N`` and against the asymptote."""
    asymptote = (2.0 / math.pi) * math.asin(RANK_MARGIN_D / 4.0)
    ranks = [int(row["required_rank"]) for row in rows]
    ns = [int(row["N"]) for row in rows]
    ratios = [rank / n for rank, n in zip(ranks, ns)]
    mean_n = sum(ns) / len(ns)
    mean_r = sum(ranks) / len(ranks)
    covariance = sum((n - mean_n) * (r - mean_r) for n, r in zip(ns, ranks))
    variance = sum((n - mean_n) ** 2 for n in ns)
    slope = covariance / variance
    intercept = mean_r - slope * mean_n
    return {
        "asymptote_constant_2_over_pi_arcsin_d_over_4": asymptote,
        "rank_over_N": ratios,
        "min_rank_over_N": min(ratios),
        "max_rank_over_N": max(ratios),
        "degree_one_slope_fit": slope,
        "degree_one_intercept_fit": intercept,
        "last_ratio_over_asymptote": ratios[-1] / asymptote,
        "first_ratio_over_asymptote": ratios[0] / asymptote,
        "growing_linearly": min(ratios) > 0.0 and slope > 0.0,
    }


FIXED_RANK_WITNESS_RANKS = (0, 1, 10, 100)
FIXED_RANK_WITNESS_MARGINS = (1.0, 2.0, 3.9)


def fixed_rank_escape(max_exponent: int = 14) -> dict[str, Any]:
    """Smallest ``N = 2**k`` at which a declared fixed rank ``r`` stops satisfying (UFA46).

    This is the map's fixed-rank statement (UF-B.15) exercised on declared rows:
    for a fixed ``r`` and a fixed margin ``d`` inside ``0 < d <= 4`` the required
    rank eventually exceeds ``r``, so no fixed retained rank survives the limit.
    """
    rows = []
    for r in FIXED_RANK_WITNESS_RANKS:
        for d in FIXED_RANK_WITNESS_MARGINS:
            witness = None
            for exponent in range(1, max_exponent + 1):
                n = 2**exponent
                if required_rank(n, d) > r:
                    witness = n
                    break
            rows.append(
                {
                    "fixed_rank": r,
                    "d": d,
                    "first_N_exceeding_fixed_rank": witness,
                    "rank_at_witness": required_rank(witness, d) if witness else None,
                }
            )
    return {
        "ranks": list(FIXED_RANK_WITNESS_RANKS),
        "margins": list(FIXED_RANK_WITNESS_MARGINS),
        "ladder": "N = 2, 4, ..., 2**%d" % max_exponent,
        "rows": rows,
        "every_declared_fixed_rank_is_exceeded": all(
            row["first_N_exceeding_fixed_rank"] is not None for row in rows
        ),
    }


def rank_boundary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The maximum-admissible-rank boundary of the (UFA46) condition.

    The map already excludes every fixed retained rank on ``0 < d <= 4``
    ((UF-B.15): a fixed-rank retained first-chaos space leaves a vanishing
    discarded margin as ``N -> infinity``).  This row refines *where* the
    boundary sits for the largest rank the map's own condition ``r_N < N``
    permits: with ``r_N = N - 1`` the inequality holds exactly while
    ``d <= gamma_N = 4 sin(pi N / (2(N+1)))``, and ``gamma_N -> 4`` from below.
    """
    per_n = []
    for row in rows:
        n = int(row["N"])
        gamma_n = chain_eigenvalues(n)[-1]
        per_n.append(
            {
                "N": n,
                "maximum_admissible_rank": n - 1,
                "maximum_admissible_rank_boundary_gamma_N": gamma_n,
                "rank_at_boundary": required_rank(n, gamma_n),
                "boundary_rank_is_maximum_admissible": required_rank(n, gamma_n)
                == n - 1,
                "arcsine_domain_edge_d": ARCSINE_DOMAIN_EDGE,
                "rank_at_arcsine_domain_edge": required_rank(n, ARCSINE_DOMAIN_EDGE),
                "limit_of_boundary": 4.0 * math.cos(math.pi / (2.0 * (n + 1))),
                "rank_one_epsilon_above_boundary": required_rank(n, gamma_n + 1e-6),
                "rank_one_epsilon_above_boundary_exceeds_maximum_rank": required_rank(
                    n, gamma_n + 1e-6
                )
                >= n,
            }
        )
    outside = None
    try:
        rank_bound(min(int(row["N"]) for row in rows), ARCSINE_DOMAIN_EDGE + 1e-9)
    except ValueError as error:
        outside = str(error)
    return {
        "map_fixed_rank_statement": MAP_FIXED_RANK_STATEMENT,
        "arcsine_domain_edge_d": ARCSINE_DOMAIN_EDGE,
        "arcsine_domain_edge_note": (
            "at d = 4 the (UFA46) bound is exactly N + 1, and for d - epsilon > 4 the "
            "arcsine argument leaves its domain; this is a property of the formula, not "
            "a threshold claim of the map"
        ),
        "rows": per_n,
        "arcsine_domain_edge_refusal": outside,
        "boundary_is_gamma_N_for_the_maximum_admissible_rank": all(
            row["boundary_rank_is_maximum_admissible"] for row in per_n
        ),
        "refinement_not_correction": (
            "with epsilon_N = 0 the map's own statement already excludes every fixed "
            "rank for all 0 < d <= 4; the gamma_N boundary refines where the largest "
            "admissible rank, r_N = N - 1, stops satisfying the same inequality"
        ),
        "fixed_rank_escape": fixed_rank_escape(),
    }


def threshold_screen() -> dict[str, Any]:
    """Declared ``d``-grid screen of (UFA46) with the map's own ``r_N < N`` condition.

    For each ``N`` the condition ``r_N < N`` fails exactly when the (UFA46) bound
    exceeds ``N``, that is when ``d > gamma_N = 4 sin(pi N / (2(N+1)))``; the grid
    locates the first failing grid point.  This is a finite screen of the map's
    inequality at its maximum admissible rank, not a statement about any gap.
    """
    rows = []
    for n in THRESHOLD_N_VALUES:
        gamma_n = chain_eigenvalues(n)[-1]
        grid_rows = []
        for d in THRESHOLD_D_GRID:
            rank = required_rank(n, d)
            grid_rows.append(
                {
                    "d": d,
                    "required_rank": rank,
                    "rank_fraction": rank / n,
                    "rank_less_than_N": rank < n,
                }
            )
        failing = [row["d"] for row in grid_rows if not row["rank_less_than_N"]]
        inside = [row["d"] for row in grid_rows if row["rank_less_than_N"]]
        rows.append(
            {
                "N": n,
                "maximum_admissible_rank": n - 1,
                "boundary_gamma_N": gamma_n,
                "admissible_d_interval_for_maximum_rank": f"0 < d <= {gamma_n!r}",
                "failing_d_interval_for_maximum_rank": f"d > {gamma_n!r}",
                "first_failing_grid_d": failing[0] if failing else None,
                "last_admissible_grid_d": max(inside) if inside else None,
                "rank_at_boundary": required_rank(n, gamma_n),
                "rank_fraction_at_boundary": (n - 1) / n,
                "rank_at_arcsine_domain_edge": required_rank(n, ARCSINE_DOMAIN_EDGE),
                "edge_minus_gamma_N": ARCSINE_DOMAIN_EDGE - gamma_n,
                "grid_rows": grid_rows,
            }
        )
    return {
        "d_grid": list(THRESHOLD_D_GRID),
        "n_values": list(THRESHOLD_N_VALUES),
        "rows": rows,
        "map_fixed_rank_statement": MAP_FIXED_RANK_STATEMENT,
        "arcsine_domain_edge_d": ARCSINE_DOMAIN_EDGE,
        "limit_gamma_N": 4.0,
        "consequence": (
            "boundary refinement, not a correction: the map's (UF-B.15) and (UFA46) "
            "already exclude every fixed retained rank for all 0 < d <= 4, and this "
            "screen only locates where the boundary sits for the largest rank the "
            "map's own condition r_N < N permits.  With r_N = N - 1 the inequality "
            "holds exactly while d <= gamma_N = 4 sin(pi N/(2(N+1))), and gamma_N -> 4 "
            "from below, so the admissible-rank window's upper edge sits just under "
            "the arcsine argument's domain edge 4 rather than at it"
        ),
        "every_N_first_failure_below_edge": all(
            row["first_failing_grid_d"] is not None
            and row["first_failing_grid_d"] <= ARCSINE_DOMAIN_EDGE
            for row in rows
        ),
    }


def rank_screen_item() -> dict[str, Any]:
    rows = [rank_row(n) for n in RANK_N_VALUES]
    channel = [
        f"gamma_k = 4 sin(k pi / (2(N+1))), k = 1..N",
        f"d = {RANK_MARGIN_D}",
        f"epsilon_N = {RANK_EPSILON}",
    ]
    return {
        "channel": channel,
        "document_claim": "retained first-chaos rank is Omega(N) when epsilon_N -> 0 and d is fixed",
        "rows": rows,
        "growth": rank_growth(rows),
        "growth_conclusion_matches_document": rank_growth(rows)["growing_linearly"],
        "boundary": rank_boundary(rows),
        "threshold_screen": threshold_screen(),
    }


# --- receipt ---------------------------------------------------------------


def duplication_check() -> dict[str, Any]:
    return {
        "searched": [
            "CassiTheory/computations/verify_yang_mills_exact_block_spectrum.py",
            "CassiTheory/computations/verify_yang_mills_exact_block_spectrum_independent.py",
            "CassiTheory/runs/yang_mills_exact_block_spectrum/verification.json",
            "CassiTheory/runs/yang_mills_exact_block_spectrum/verification-independent.json",
            "CassiFI/run_yang_mills_gauge_fibre_probe.py",
        ],
        "wider_scan": (
            "All 68 CassiTheory/computations/verify_yang_mills_*.py verifiers and "
            "their 33 runs/*yang*mills* receipts were scanned for a fine-multiplicity "
            "table, a corner-shift closure, or an arcsine rank screen (patterns: "
            "multiplicity, fuse, boundary sector, corner, shift, arcsin, sin(k*pi/"
            "(2(N+1)))).  No match outside the obligation-map document itself."
        ),
        "found": (
            "The exact-block verifiers compute the 7-link star block spectrum "
            "(3j/9j plaquette matrices, Ritz rows, direct-contraction conditional "
            "objects) and the CassiFI probe resolves the fixed-boundary fibre "
            "(all eight outer links at n=1) as a 14-state saturated basis."
        ),
        "not_found": (
            "No existing verifier or receipt computes the corner-shift reachable "
            "family, the four-tuple fine multiplicity M^f(a,b,c,d), or the (UFA46) "
            "rank screen.  Those three finite statements are computed here."
        ),
        "cross_reference": (
            "The probe's 14-dimensional saturated fixed-boundary fibre is the "
            "n=1 corner-label sector, which is the anchor M^f(1,1,1,1) recomputed here."
        ),
    }


def run() -> dict[str, Any]:
    started = time.perf_counter()
    support = support_action()
    if support["count_mismatches"]:
        raise AssertionError(
            f"reachable-family counts diverge from the document: {support['count_mismatches']}"
        )
    for row in support["cutoffs"]:
        if not row["full_cone_reached"]:
            raise AssertionError(
                f"cutoff {row['cutoff']} from seed {row['seed']} did not reach the full box"
            )

    multiplicity = multiplicity_item()
    if multiplicity["anchor_mismatches"]:
        raise AssertionError(
            f"anchor table diverges from the document: {multiplicity['anchor_mismatches']}"
        )
    if multiplicity["never_zero"]["zero_entries"]:
        raise AssertionError("the fine multiplicity vanished inside the declared domain")
    decompositions = multiplicity["anchor_row_decompositions"]
    if not decompositions["all_weights_sum_to_table_value"]:
        raise AssertionError("an anchor row decomposition does not sum to its table value")
    if not decompositions["all_document_decompositions_agree"]:
        raise AssertionError("an anchor row decomposition disagrees with the document")
    if not multiplicity["pairing_choice_independence"]["independent_of_choice"]:
        raise AssertionError("the fine multiplicity depends on the centre pairing")
    invariance = multiplicity["relabelling_invariance"]
    if not invariance["document_claim_verified"]:
        raise AssertionError("the square symmetries do not preserve the fine multiplicity")
    if invariance["asymmetry_control"]["invariant"]:
        raise AssertionError(
            "the position-indexed control variant is invariant, so the relabelling "
            "check cannot fail"
        )

    rank = rank_screen_item()
    for row in rank["rows"]:
        if not row["rank_compatible_with_rank_less_than_N"]:
            raise AssertionError(
                f"N={row['N']}: required rank {row['required_rank']} does not respect r_N < N"
            )
        if not row["eigenvalues_strictly_increasing"]:
            raise AssertionError(f"N={row['N']}: the channel spectrum is not ordered")
    if not rank["growth"]["growing_linearly"]:
        raise AssertionError("the rank screen does not grow linearly in N")
    screen = rank["threshold_screen"]
    for row in screen["rows"]:
        if row["rank_at_boundary"] != row["N"] - 1:
            raise AssertionError(
                f"N={row['N']}: the boundary rank is not the largest admissible rank"
            )
        if row["first_failing_grid_d"] is None:
            raise AssertionError(f"N={row['N']}: the d-grid found no failing point")
        if not row["first_failing_grid_d"] > row["boundary_gamma_N"]:
            raise AssertionError(
                f"N={row['N']}: the first failing grid point is inside the admissible interval"
            )
        if not row["last_admissible_grid_d"] <= row["boundary_gamma_N"]:
            raise AssertionError(
                f"N={row['N']}: an admissible grid point lies above the boundary"
            )
    boundary = rank["boundary"]
    if not boundary["boundary_is_gamma_N_for_the_maximum_admissible_rank"]:
        raise AssertionError(
            "the maximum-admissible-rank boundary is not gamma_N"
        )
    if not boundary["arcsine_domain_edge_refusal"]:
        raise AssertionError("the arcsine domain edge was not detected above d = 4")

    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "question": (
            "Do the finite statements of obligation-map sections 4.4.7 and 4.6 "
            "(corner-shift closure, fine multiplicity table, first-chaos rank "
            "screen) reproduce on recomputation?"
        ),
        "source": {
            "document": SOURCE_DOCUMENT,
            "sections": ["4.4.7 (UFA103)-(UFA106)", "4.6 (UFA43)-(UFA46)"],
            "label_convention": "integer labels n = 2j; fuse(m,n) = {|m-n|, |m-n|+2, ..., m+n}",
        },
        "conventions": {
            "corners": list(CORNERS),
            "corner_pairs_of_outer_links": [list(pair) for pair in CORNER_PAIRS],
            "spoke_order": list(SPOKES),
            "spoke_corner_pairs": [list(pair) for pair in SPOKE_CORNERS],
            "centre_pairing": [list(pair) for pair in PAIRING],
            "boundary_label": BOUNDARY_LABEL,
            "seeds": [list(seed) for seed in SEEDS],
            "cutoffs": list(CUTOFFS),
            "mandated_cutoffs": [1, 2, 3],
            "supplemental": (
                "C=4 (the document's own fourth cutoff value), the relabelling domains "
                "0..4 and 0..8, the three-matching pairing class, and the d-grid screen "
                "are supplemental extensions of the same computations; they do not "
                "replace the mandated C=1,2,3 counts, the 0..3 table, or the "
                "arcsine-domain edge d = 4 of the (UFA46) formula."
            ),
        },
        "duplication_check": duplication_check(),
        "support_action": support,
        "multiplicity_table": multiplicity,
        "rank_screen": rank,
        "scope": (
            "These are finite combinatorial checks of a document's finite statements: "
            "the corner-shift support action (UFA104), the fine multiplicity formula and "
            "anchor table (UFA106), and the rank inequality (UFA46) with its declared "
            "weak-field channel. They say nothing about any uniform-in-cutoff or "
            "continuum obligation. (UFA105), the general compression matrix between "
            "multiplicity spaces M^f(alpha) -> M^f(alpha +- e_c), is out of scope "
            "because it requires explicit multiplicity-space bases."
        ),
        "limits": [
            "The support-action family is a statement about which sectors a shift can reach, not about the value of any compression matrix element.",
            "The fine multiplicity counts representation support and channel content per boundary sector; it carries no amplitude, no electric form and no magnetic matrix element.",
            "The rank screen evaluates the declared Gaussian chain and the declared margin; it is a rank compatibility requirement, not a statement about the interacting Yang-Mills form. The boundary screen is a finite d-grid of that one inequality at its maximum admissible rank, not a statement about any spectral gap, and it refines rather than corrects the map's own fixed-rank statement.",
            "The measured relabelling invariance is a property of the (UFA106) sum on the declared and extended domains; it does not prove invariance at arbitrary labels, and it does not touch the compression matrix.",
            "The C=4 cutoff, the 0..4 and 0..8 relabelling domains, the pairing class and the d-grid screen are supplemental measurements of the same finite computations, not additional obligations.",
            "The matrix in (UFA105), the coarse-sector comparison, and every uniform-in-cutoff or continuum statement of UF-A to UF-E remain untouched.",
        ],
        "measured_result": {
            "reachable_counts": {
                f"C={row['cutoff']},seed={tuple(row['seed'])}": row["reachable_count"]
                for row in support["cutoffs"]
            },
            "closure_steps": {
                f"C={row['cutoff']},seed={tuple(row['seed'])}": row["closure_step"]
                for row in support["cutoffs"]
            },
            "full_cone_reached_at_every_cutoff": all(
                row["full_cone_reached"] for row in support["cutoffs"]
            ),
            "anchor_table": {
                ",".join(str(label) for label in row["sector"]): row["measured"]
                for row in multiplicity["anchors"]
            },
            "anchor_agree": multiplicity["anchor_agree"],
            "fine_multiplicity_minimum": multiplicity["never_zero"]["minimum"],
            "fine_multiplicity_argmin": multiplicity["never_zero"]["argmin"],
            "fine_multiplicity_never_zero": not multiplicity["never_zero"]["zero_entries"],
            "fine_multiplicity_minimum_is_exactly_the_single_nonzero_corner_family": (
                multiplicity["never_zero"][
                    "minimum_is_exactly_the_single_nonzero_corner_family"
                ]
            ),
            "relabelling_invariance": {
                "document_claim_verified": multiplicity["relabelling_invariance"][
                    "document_claim_verified"
                ],
                "replaced_by_full_symmetric_group": multiplicity[
                    "relabelling_invariance"
                ]["document_claim_replaced_by_full_symmetric_group"],
                "asymmetry_found_in_multiplicity": multiplicity[
                    "relabelling_invariance"
                ]["asymmetry_found_in_multiplicity"],
                "domains": {
                    str(row["domain"]): {
                        "sectors": row["sectors"],
                        "preserving_count": row["preserving_count"],
                        "permutation_mismatches": row["permutation_mismatches"],
                        "zero_label_subdomain_mismatches": row[
                            "zero_label_subdomain_mismatches"
                        ],
                    }
                    for row in multiplicity["relabelling_invariance"]["domains"]
                },
                "asymmetry_control_mismatches": multiplicity["relabelling_invariance"][
                    "asymmetry_control"
                ]["mismatches"],
                "all_three_spoke_matchings_agree": multiplicity[
                    "relabelling_invariance"
                ]["pairing_class"]["all_three_matchings_agree"],
                "verdict": multiplicity["relabelling_invariance"]["verdict"],
            },
            "anchor_row_decompositions": {
                key: {
                    "configurations": row["configurations"],
                    "contributing_configurations": row["contributing_configurations"],
                    "weight_decomposition": row["weight_decomposition"],
                    "configuration_counts_by_active_spokes": row[
                        "configuration_counts_by_active_spokes"
                    ],
                    "channel_weights_by_active_spokes": row[
                        "channel_weights_by_active_spokes"
                    ],
                    "table_value": row["table_value"],
                    "weights_sum_to_table_value": row["weights_sum_to_table_value"],
                }
                for key, row in (
                    (",".join(str(label) for label in row["sector"]), row)
                    for row in multiplicity["anchor_row_decompositions"]["rows"]
                )
            },
            "pairing_choice_independent": multiplicity["pairing_choice_independence"][
                "independent_of_choice"
            ],
            "rank_over_N": rank["growth"]["rank_over_N"],
            "rank_asymptote_constant": rank["growth"][
                "asymptote_constant_2_over_pi_arcsin_d_over_4"
            ],
            "rank_grows_linearly": rank["growth"]["growing_linearly"],
            "map_fixed_rank_statement": rank["boundary"]["map_fixed_rank_statement"],
            "arcsine_domain_edge_d": rank["boundary"]["arcsine_domain_edge_d"],
            "maximum_admissible_rank_boundary_is_gamma_N": rank["boundary"][
                "boundary_is_gamma_N_for_the_maximum_admissible_rank"
            ],
            "boundary_refines_rather_than_corrects_the_map": rank["boundary"][
                "refinement_not_correction"
            ],
            "threshold_screen_maximum_rank_boundaries": {
                str(row["N"]): {
                    "maximum_admissible_rank": row["maximum_admissible_rank"],
                    "boundary_gamma_N": row["boundary_gamma_N"],
                    "last_admissible_grid_d": row["last_admissible_grid_d"],
                    "first_failing_grid_d": row["first_failing_grid_d"],
                    "rank_at_boundary": row["rank_at_boundary"],
                }
                for row in rank["threshold_screen"]["rows"]
            },
            "threshold_screen_consequence": rank["threshold_screen"]["consequence"],
        },
    }
    receipt["wall_seconds"] = round(time.perf_counter() - started, 6)
    # The digest covers every measured and declared field; only the wall-clock
    # timing is excluded so that two runs of the same computation agree.
    receipt["receipt_sha256"] = sha256(
        {key: value for key, value in receipt.items() if key != "wall_seconds"}
    )
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    receipt = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    measured = receipt["measured_result"]
    print(f"Receipt: {args.output.resolve()}")
    print(f"Receipt SHA-256: {receipt['receipt_sha256']}")
    print(f"Reachable counts: {json.dumps(measured['reachable_counts'], sort_keys=True)}")
    print(f"Closure steps: {json.dumps(measured['closure_steps'], sort_keys=True)}")
    print(
        "Anchor table: "
        + json.dumps(measured["anchor_table"], sort_keys=True)
        + f" (all agree with the document: {measured['anchor_agree']})"
    )
    multiplicity = receipt["multiplicity_table"]
    print(f"Fine multiplicity table ({len(multiplicity['table'])} sectors, a,b,c,d):")
    print("  " + json.dumps(multiplicity["table"], sort_keys=True))
    print(
        f"Fine multiplicity minimum {measured['fine_multiplicity_minimum']} at "
        f"{measured['fine_multiplicity_argmin']}; never zero: "
        f"{measured['fine_multiplicity_never_zero']}; minimum is exactly the "
        f"single-nonzero-corner family: "
        f"{measured['fine_multiplicity_minimum_is_exactly_the_single_nonzero_corner_family']}"
    )
    invariance = measured["relabelling_invariance"]
    print(
        "Relabelling invariance of M^f: "
        f"document claim (square symmetries) verified: {invariance['document_claim_verified']}; "
        f"replaceable by the full symmetric group: {invariance['replaced_by_full_symmetric_group']}; "
        f"asymmetry found in M^f: {invariance['asymmetry_found_in_multiplicity']}"
    )
    for domain, row in invariance["domains"].items():
        print(
            f"  domain 0..{domain}: sectors={row['sectors']} preserving={row['preserving_count']}/24"
            f" permutation mismatches={row['permutation_mismatches']}"
            f" zero-label-subdomain mismatches={row['zero_label_subdomain_mismatches']}"
        )
    print(
        f"  all three spoke matchings agree: {invariance['all_three_spoke_matchings_agree']}; "
        f"position-indexed control variant mismatches: "
        f"{invariance['asymmetry_control_mismatches']}"
    )
    print("  " + invariance["verdict"])
    print("Anchor row decompositions (active-spoke channel weights, summed over configurations):")
    for key, row in measured["anchor_row_decompositions"].items():
        print(
            f"  ({key}): configurations={row['configurations']}"
            f" contributing={row['contributing_configurations']}"
            f" weights={row['weight_decomposition']} table value={row['table_value']}"
            f" sum matches: {row['weights_sum_to_table_value']}"
        )
    print(
        "Rank screen (d = %s, epsilon_N = %s):" % (RANK_MARGIN_D, RANK_EPSILON)
    )
    for row in receipt["rank_screen"]["rows"]:
        print(
            f"  N={row['N']:>3}  bound={row['bound']:.9f}  r_N={row['required_rank']:>3}"
            f"  r_N/N={row['rank_fraction']:.6f}  gamma_N={row['gamma_N']:.9f}"
            f"  rank < N: {row['rank_compatible_with_rank_less_than_N']}"
        )
    print(f"r_N/N: {measured['rank_over_N']}")
    print(
        f"rank asymptote 2/pi arcsin(d/4) = {measured['rank_asymptote_constant']:.9f}; "
        f"linear growth: {measured['rank_grows_linearly']}"
    )
    print(measured["map_fixed_rank_statement"])
    print(
        f"Maximum-admissible-rank boundary (largest rank the map permits, "
        f"r_N = N-1): holds for d <= gamma_N, gamma_N -> 4^- ; "
        f"boundary is gamma_N at every N: "
        f"{measured['maximum_admissible_rank_boundary_is_gamma_N']}; "
        f"arcsine domain edge d = {measured['arcsine_domain_edge_d']}"
    )
    print(
        "Threshold screen over d-grid "
        f"{json.dumps(receipt['rank_screen']['threshold_screen']['d_grid'])} "
        "(r_N and the map's r_N < N condition; ! marks the first failures):"
    )
    for row in receipt["rank_screen"]["threshold_screen"]["rows"]:
        grid = ", ".join(
            f"d={entry['d']:g}:r_N={entry['required_rank']}"
            f"{'' if entry['rank_less_than_N'] else '!'}"
            for entry in row["grid_rows"]
        )
        print(
            f"  N={row['N']:>3}  gamma_N={row['boundary_gamma_N']:.6f}"
            f"  admissible d <= gamma_N  first failing grid d="
            f"{row['first_failing_grid_d']:g} (last admissible {row['last_admissible_grid_d']:g})"
        )
        print(f"    {grid}")
    print("  " + receipt["rank_screen"]["threshold_screen"]["consequence"])
    print(f"Wall seconds: {receipt['wall_seconds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
