"""Bounded numerical exploration of transceiver *port placement* against a declared arrangement.

Question (CassiFI `FRACTAL-MEMORY-EXPLORATION.md` section C, "First three bounded
explorations" item 3, at the level the current machinery can measure): which port
placements actually reach the field's recurring modes?  Which ports excite
distinct modes (controllability), which can tell them apart (observability), are
good write ports also good read ports, and does the best placement depend on the
declared arrangement?

Everything is built by importing the existing geometry harness
(`run_fractal_geometry_exploration`) and reusing its canonical helpers: the
declared arrangements (`arrangement_named`, `arrangements`), the arrangement
profile (`build_profile`), the frozen beta=0 linear generator
(`linear_generator`), the declared transceiver objective and condensation
(`declared_problem`, `subset_kernel`, `PORT_SUBSETS`, `port_bindings`), the
retention walk (`retention_metrics`), and the canonical JSON/digest helpers.

Declared constructions (all restated inside the receipt):

* **Modes.**  The arrangement's frozen linear generator ``G`` is rebuilt exactly
  as the geometry harness builds it (``linear_generator``: one canonical
  ``flow(energy_gradient(e_i))`` column per state coordinate of the beta=0
  profile), then densely eigendecomposed.  Right eigenvectors are placed in the
  declared gauge "unit 2-norm column"; ``W = Vhat^-1`` holds the dual (left)
  eigenvectors as rows.
* **Write pin.**  The write placement at port ``p`` is the canonical *state pin*
  the transceiver actually applies: the boundary image of the zero state under a
  declared placement objective that observes the port at 1.0, exactly as
  ``condense_workspace`` obtains ``input_lift`` (``boundary(0)`` minus the
  ``observed = 0.0`` base, which is zero).  Its modal amplitudes are the dual
  coefficients ``c = W @ pin`` -- the drive *excites* mode ``m`` with amplitude
  ``|c_m|``.
* **Read pick-off.**  The read placement at port ``p`` is the canonical *port
  pick-off* row ``condense_workspace`` builds from the declared binding:
  ``1/sqrt(2)`` at the port's two strand coordinates.  Its modal gains are the
  Euclidean projections ``b_m = |conj(Vhat)[:, m] . pick_off|`` -- the read
  *sees* mode ``m`` with gain ``|b_m|``.
* **Scores.**  Per port and per direction: participation entropy
  ``H = -sum p log p`` over the normalized modal mass, effective number of modes
  reached ``exp(H)``, maximum single-mode dominance ``max p``, and modal
  distinguishability = the participation-weighted mean pairwise separation of the
  port's normalized modal signatures, ``sum_{m<k} p_m p_k |s_hat_m - s_hat_k|``
  (0 = the port weighs every mode alike, so magnitudes alone exchange them;
  signature phase is deliberately excluded because it is eigenvector gauge).
* **Write/read transfer.**  For every declared ``(write port, read port)`` pair,
  ``T(w, r) = sum_m drive_participation_w(m) * read_gain_hat_r(m)`` -- the read
  port's normalized modal gain averaged over the modes the write port excites --
  plus its reverse ``T_rev(w, r) = sum_m read_participation_r(m) * drive_gain_hat_w(m)``.
* **Selection.**  Greedy best-k over ports (and over write/read pairs) for the
  declared coverage objective ``exp(H(mean of the selected profiles))``, compared
  with the existing deterministic binding order (drive on local port 0, read on
  local port 1, pools ascending) under the same declared objective.

Run: ``python run_fractal_placement_exploration.py --output _diag/fractal-placement/exploration.json``

The receipt records every definition, every measured number, a content digest
(invariant to wall-clock fields) and the boundary: this measures **modal access
on a declared linear scaffold**, not task performance, learning or memory
utility.
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

import run_fractal_geometry_exploration as geometry
from cassi_resonant_field import (
    ResonantNumericalError,
    ResonantProblem,
    ResonantProfile,
    _WaveOperator,
    initial_workspace,
)

SCHEMA = "cassifi.fractal-placement-exploration.v1"
RECEIPT_SCHEMA = "cassifi.fractal-placement-receipt.v1"

DEFAULT_PORTS_PER_POOL = geometry.DEFAULT_PORTS_PER_POOL
# The arrangements named by the placement question itself; the default run covers
# every declared arrangement because the whole set is cheap to measure.
REQUIRED_ARRANGEMENTS = ("helix7", "nested-core-shell", "recursive-paired-loops")

# The existing deterministic binding order offers seven sites (one drive port on
# local port 0 and one read port on local port 1 per pool), so the declared
# selection depth is seven.
DEFAULT_SELECTION_DEPTH = 7
TOP_PLACEMENTS = 5
# Declared tolerances and gauges.
PIN_TOLERANCE = 1e-9
EIGEN_RESIDUAL_TOLERANCE = 1e-10
EIGEN_CONDITION_LIMIT = 1e8
# Declared can-fail margins: these statements must separate.
PLACEMENT_MARGIN_EFFECTIVE_MODES = 2.0
PLACEMENT_MARGIN_PAIRS = (("helix7", 0, 4), ("nested-core-shell", 3, 13))
ARRANGEMENT_MARGIN_EFFECTIVE_MODES = 1.0
ARRANGEMENT_MARGIN_PAIR = ("helix7", "recursive-paired-loops")

PLACEMENT_VARIABLE = "fg:placement-port-{port}"
PLACEMENT_BINDING_PREFIX = "fractal-placement"
RETENTION_POOLS = (0, 1, 2, 3, 4, 5, 6)

_jsonable = geometry._jsonable


# --------------------------------------------------------------------------
# json helpers and small declared math
# --------------------------------------------------------------------------
def canonical_digest(value: Any) -> str:
    return geometry.canonical_digest(value)


def content_digest(value: Any) -> str:
    return geometry.content_digest(value)


def _array_digest(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value, dtype="<f8").tobytes()).hexdigest()


def _entropy(mass: np.ndarray) -> np.ndarray:
    """Shannon entropy in nats along the last axis with ``0 log 0 = 0``."""
    positive = mass > 0.0
    safe = np.where(positive, mass, 1.0)
    return np.asarray(np.where(positive, -mass * np.log(safe), 0.0).sum(axis=-1), dtype=np.float64)


def _average_ranks(values: np.ndarray) -> np.ndarray:
    """Deterministic average ranks; ties share one rank."""
    ordered = np.asarray(values, dtype=np.float64)
    order = np.argsort(ordered, kind="stable")
    sorted_values = ordered[order]
    ranks = np.empty(len(order), dtype=np.float64)
    index = 0
    while index < len(order):
        stop = index
        while stop + 1 < len(order) and sorted_values[stop + 1] == sorted_values[index]:
            stop += 1
        ranks[order[index:stop + 1]] = 0.5 * (index + stop) + 1.0
        index = stop + 1
    return ranks


def spearman(left: Sequence[float], right: Sequence[float]) -> float:
    """Rank correlation with average ranks; 0.0 when either vector is constant."""
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if a.shape != b.shape or a.size < 2:
        raise ResonantNumericalError("spearman needs two equal-length vectors")
    da, db = _average_ranks(a), _average_ranks(b)
    da, db = da - da.mean(), db - db.mean()
    denominator = math.sqrt(float(da @ da) * float(db @ db))
    return 0.0 if denominator == 0.0 else float(da @ db / denominator)


def gini_mean_difference(participation: np.ndarray, normalized: np.ndarray) -> np.ndarray:
    """``sum_{m<k} p_m p_k |s_m - s_k|`` per row of ``(ports, modes)`` arrays.

    Sorting each row ascending turns the double sum into
    ``sum_j p_j s_j (2 C_j - p_j - 1)`` with ``C`` the running sum of ``p``.
    """
    order = np.argsort(normalized, axis=1, kind="stable")
    p = np.take_along_axis(participation, order, axis=1)
    s = np.take_along_axis(normalized, order, axis=1)
    running = np.cumsum(p, axis=1)
    return np.asarray((p * s * (2.0 * running - p - 1.0)).sum(axis=1), dtype=np.float64)


# --------------------------------------------------------------------------
# declared placement space and the canonical pin / pick-off
# --------------------------------------------------------------------------
def placement_variable(port: int) -> str:
    return PLACEMENT_VARIABLE.format(port=int(port))


def placement_binding(port: int, ports_per_pool: int = DEFAULT_PORTS_PER_POOL) -> dict[str, Any]:
    """The canonical binding shape (``bind_workspace``'s own form) at any port."""
    port = int(port)
    return {
        "pool": port // int(ports_per_pool),
        "port": port,
        "component": "common",
        "binding_id": f"{PLACEMENT_BINDING_PREFIX}:{placement_variable(port)}:common",
    }


def placement_bindings(ports_per_pool: int = DEFAULT_PORTS_PER_POOL) -> dict[str, dict[str, Any]]:
    count = 7 * int(ports_per_pool)
    return {placement_variable(port): placement_binding(port, ports_per_pool) for port in range(count)}


def placement_problem(port: int) -> ResonantProblem:
    """Declared placement objective: the harness's ``declared_problem`` rule at one variable.

    ``precision = PRIOR_RIDGE*I + (PRIOR_MASS/m)*ones(m, m)`` with ``m = 1``,
    ``linear_b = 0`` and the observed placement variable pinned at 1.0.  At the
    declared binding ports this objective reproduces ``declared_problem``'s
    ``input_lift`` exactly; that equality is measured, not assumed (see the
    ``kernel_identity`` block of the receipt).
    """
    name = placement_variable(port)
    precision = geometry.PRIOR_RIDGE * np.eye(1) + (geometry.PRIOR_MASS / 1.0) * np.ones((1, 1))
    return ResonantProblem(
        variable_ids=(name,), precision=precision, linear_b=np.zeros(1),
        observed={name: 1.0}, affine_constraints=None,
    )


def canonical_common_pattern(port: int, port_count: int) -> np.ndarray:
    """The declared common coordinate at one port: ``(e_p + e_{n+p})/sqrt(2)``."""
    vector = np.zeros(4 * int(port_count), dtype=np.float64)
    vector[int(port)] = 1.0 / math.sqrt(2.0)
    vector[int(port_count) + int(port)] = 1.0 / math.sqrt(2.0)
    return vector


@dataclass(frozen=True)
class PlacementSpace:
    """Every candidate placement: all ports of the arrangement's paired strand pair."""

    ports_per_pool: int
    port_count: int

    @property
    def pools(self) -> int:
        return self.port_count // self.ports_per_pool

    @property
    def ports(self) -> tuple[int, ...]:
        return tuple(range(self.port_count))

    def pool_of(self, port: int) -> int:
        return int(port) // self.ports_per_pool

    def local_of(self, port: int) -> int:
        return int(port) % self.ports_per_pool

    def declared_drive_ports(self) -> tuple[int, ...]:
        return tuple(
            int(binding["port"])
            for _pool, binding in sorted(
                (
                    (int(name.rsplit("-", 1)[-1]), value)
                    for name, value in geometry.port_bindings(self.ports_per_pool).items()
                    if name.startswith("fg:drive-pool-")
                ),
                key=lambda item: item[0],
            )
        )

    def declared_read_ports(self) -> tuple[int, ...]:
        return tuple(
            int(binding["port"])
            for _pool, binding in sorted(
                (
                    (int(name.rsplit("-", 1)[-1]), value)
                    for name, value in geometry.port_bindings(self.ports_per_pool).items()
                    if name.startswith("fg:read-pool-")
                ),
                key=lambda item: item[0],
            )
        )

    def declared_pairs(self) -> tuple[tuple[int, int], ...]:
        return tuple(zip(self.declared_drive_ports(), self.declared_read_ports()))


def placement_space(ports_per_pool: int = DEFAULT_PORTS_PER_POOL) -> PlacementSpace:
    return PlacementSpace(ports_per_pool=int(ports_per_pool), port_count=7 * int(ports_per_pool))


def placement_state_pins(space: PlacementSpace, profile: ResonantProfile) -> dict[str, Any]:
    """The canonical state pin at every declared port, from the production operator.

    The pin is ``boundary(0)`` of the production ``_WaveOperator`` under the
    declared placement objective -- the same object ``condense_workspace`` keeps
    as an ``input_lift`` column.  The ``observed = 0.0`` base is zero, so this is
    the whole lift column.
    """
    linear = replace(profile, beta=0.0)
    n = linear.port_count
    dimension = 4 * n
    workspace = initial_workspace(linear)._copy(bindings=placement_bindings(linear.ports_per_pool))
    tolerance = max(float(linear.tolerance), 1e-10)
    pins = np.zeros((space.port_count, dimension), dtype=np.float64)
    residuals = np.zeros(space.port_count, dtype=np.float64)
    for port in space.ports:
        operator = _WaveOperator(workspace, placement_problem(port))
        pin = np.asarray(operator.boundary(np.zeros(dimension), tolerance), dtype=np.float64)
        pins[port] = pin
        residuals[port] = float(
            np.max(np.abs(np.asarray(operator.constraints) @ pin - np.asarray(operator.targets)))
        )
    patterns = np.vstack([canonical_common_pattern(port, n) for port in space.ports])
    return {
        "pins": pins,
        "patterns": patterns,
        "constraint_residual_max": float(residuals.max()) if residuals.size else 0.0,
        "unit_norm_deviation_max": float(np.max(np.abs(np.linalg.norm(pins, axis=1) - 1.0))),
        "pattern_max_abs_difference": float(np.max(np.abs(pins - patterns))),
        "pin_sha256": _array_digest(pins),
    }


def read_pickoffs(space: PlacementSpace, port_count: int) -> np.ndarray:
    """The canonical port pick-off row at every declared port.

    Exactly the row ``condense_workspace`` builds from a binding: ``1/sqrt(2)``
    at the port's two strand coordinates.
    """
    return np.vstack([canonical_common_pattern(port, port_count) for port in space.ports])


# --------------------------------------------------------------------------
# modal basis and per-port signatures
# --------------------------------------------------------------------------
def modal_basis(profile: ResonantProfile) -> dict[str, Any]:
    """Dense eigendecomposition of the frozen beta=0 generator, in a declared gauge."""
    generator = geometry.linear_generator(profile)
    eigenvalues, raw = np.linalg.eig(generator)
    norms = np.linalg.norm(raw, axis=0)
    if not np.all(norms > 0.0):
        raise ResonantNumericalError("degenerate eigenvector column")
    vectors = raw / norms
    condition = float(np.linalg.cond(vectors))
    if not math.isfinite(condition) or condition > EIGEN_CONDITION_LIMIT:
        raise ResonantNumericalError(f"eigenvector basis conditioning {condition} exceeds the declared limit")
    dual = np.linalg.inv(vectors)
    residual = float(
        np.linalg.norm(generator @ vectors - vectors * eigenvalues, ord="fro")
        / max(float(np.linalg.norm(generator, ord="fro")), 1e-300)
    )
    return {
        "generator": generator,
        "eigenvalues": eigenvalues,
        "vectors": vectors,
        "dual": dual,
        "dimension": int(generator.shape[0]),
        "eigenvector_condition_number": condition,
        "eigendecomposition_residual": residual,
        "unit_column_norm_deviation_max": float(np.max(np.abs(norms - 1.0))),
        "zero_magnitude_mode_count": int(np.count_nonzero(np.abs(eigenvalues) <= 1e-12)),
        "maximum_growth_rate": float(eigenvalues.real.max()),
        "median_decay_rate": float(np.median(-eigenvalues.real)),
        "generator_sha256": _array_digest(generator),
        "eigenvalue_sha256": canonical_digest(
            [complex(value).real for value in eigenvalues] + [complex(value).imag for value in eigenvalues]
        ),
    }


def drive_signature(pins: np.ndarray, basis: Mapping[str, Any]) -> np.ndarray:
    """``|c|`` for ``c = dual @ pin``: the modal amplitude the write pin excites."""
    return np.abs(np.asarray(pins, dtype=np.float64) @ np.asarray(basis["dual"]).T)


def read_signature(pickoffs: np.ndarray, basis: Mapping[str, Any]) -> np.ndarray:
    """``|b|`` for ``b = conj(Vhat)^T @ pick_off``: the modal gain the read sees."""
    vectors = np.asarray(basis["vectors"])
    return np.abs(np.asarray(pickoffs, dtype=np.float64) @ np.conj(vectors))


def signature_scores(signature: np.ndarray, space: PlacementSpace) -> dict[str, Any]:
    """Declared per-port placement scores from a ``(ports, modes)`` signature."""
    mass = np.asarray(signature, dtype=np.float64).sum(axis=1)
    peak = np.asarray(signature, dtype=np.float64).max(axis=1)
    reached = mass > 0.0
    participation = np.zeros_like(signature, dtype=np.float64)
    participation[reached] = np.asarray(signature, dtype=np.float64)[reached] / mass[reached, None]
    normalized = np.zeros_like(signature, dtype=np.float64)
    peaked = peak > 0.0
    normalized[peaked] = np.asarray(signature, dtype=np.float64)[peaked] / peak[peaked, None]
    entropy = _entropy(participation)
    effective = np.where(reached, np.exp(entropy), 0.0)
    dominance = np.where(reached, participation.max(axis=1), 1.0)
    distinguishability = np.where(
        reached, gini_mean_difference(participation, normalized), 0.0
    )
    dominant = np.where(reached, np.argmax(participation, axis=1), -1)
    rows = [
        {
            "port": port,
            "pool": space.pool_of(port),
            "local": space.local_of(port),
            "reached": bool(reached[port]),
            "signature_mass": float(mass[port]),
            "entropy_nats": float(entropy[port]),
            "effective_modes": float(effective[port]),
            "max_dominance": float(dominance[port]),
            "distinguishability": float(distinguishability[port]),
            "dominant_mode": int(dominant[port]),
            "participation_sha256": _array_digest(participation[port]),
        }
        for port in space.ports
    ]
    return {
        "ports": rows,
        "participation": participation,
        "normalized": normalized,
        "effective_modes": effective,
        "max_dominance": dominance,
        "distinguishability": distinguishability,
        "unreached_ports": [port for port in space.ports if not bool(reached[port])],
    }


# --------------------------------------------------------------------------
# declared selection objective
# --------------------------------------------------------------------------
def cover(profiles: np.ndarray, indices: Sequence[int]) -> float:
    """Declared coverage of a placement set: ``exp(H(mean of the selected profiles))``."""
    selected = np.asarray(list(indices), dtype=np.int64)
    if selected.size == 0:
        return 0.0
    aggregate = np.asarray(profiles, dtype=np.float64)[selected].mean(axis=0)
    total = float(aggregate.sum())
    if total <= 0.0:
        return 0.0
    return float(math.exp(float(_entropy(aggregate / total))))


def greedy_cover(profiles: np.ndarray, depth: int) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """Greedy best-k over candidates in ascending index order (ties to the lower index)."""
    candidates = np.asarray(profiles, dtype=np.float64)
    total_candidates = candidates.shape[0]
    selected: list[int] = []
    coverage: list[float] = []
    accumulated = np.zeros(candidates.shape[1], dtype=np.float64)
    for _step in range(min(int(depth), total_candidates)):
        best_index, best_value = -1, -1.0
        for candidate in range(total_candidates):
            if candidate in selected:
                continue
            aggregate = accumulated + candidates[candidate]
            total = float(aggregate.sum())
            if total <= 0.0:
                continue
            value = float(math.exp(float(_entropy(aggregate / total))))
            if value > best_value:
                best_index, best_value = candidate, value
        if best_index < 0:
            break
        selected.append(best_index)
        accumulated = accumulated + candidates[best_index]
        coverage.append(best_value)
    return tuple(selected), tuple(coverage)


def top_indices(values: Sequence[float], count: int) -> tuple[int, ...]:
    """Deterministic top-k by descending value, ties to the lower index."""
    ordered = np.asarray(values, dtype=np.float64)
    return tuple(int(index) for index in np.lexsort((np.arange(ordered.size), -ordered))[: int(count)])


def set_overlap(left: Sequence[Any], right: Sequence[Any]) -> dict[str, Any]:
    """Jaccard overlap of two declared top sets (ports or port pairs)."""
    a, b = set(left), set(right)
    union = a | b
    return {
        "shared": len(a & b),
        "union": len(union),
        "jaccard": (len(a & b) / len(union)) if union else 1.0,
    }


def selection_tables(
    space: PlacementSpace, drive: Mapping[str, Any], read: Mapping[str, Any],
    pair_profiles: np.ndarray, depth: int,
) -> dict[str, Any]:
    """Greedy best-k against the existing deterministic binding order."""
    depth = int(min(depth, space.pools))
    declared_drive = space.declared_drive_ports()
    declared_read = space.declared_read_ports()
    declared_pairs = space.declared_pairs()
    pair_count = space.port_count * space.port_count

    greedy_drive, greedy_drive_curve = greedy_cover(drive["participation"], depth)
    greedy_read, greedy_read_curve = greedy_cover(read["participation"], depth)
    greedy_joint, greedy_joint_curve = greedy_cover(pair_profiles, depth)

    restricted_drive, restricted_drive_curve = greedy_cover(
        drive["participation"][np.asarray(declared_drive, dtype=np.int64)], depth
    )
    restricted_read, restricted_read_curve = greedy_cover(
        read["participation"][np.asarray(declared_read, dtype=np.int64)], depth
    )
    declared_pair_index = np.asarray(
        [pair_index(pair, space) for pair in declared_pairs], dtype=np.int64
    )
    restricted_joint, restricted_joint_curve = greedy_cover(pair_profiles[declared_pair_index], depth)

    def curve_for(profiles: np.ndarray, taken: Sequence[int]) -> list[float]:
        return [cover(profiles, taken[: step + 1]) for step in range(depth)]

    declared_drive_curve = curve_for(drive["participation"], declared_drive[:depth])
    declared_read_curve = curve_for(read["participation"], declared_read[:depth])
    declared_joint_curve = curve_for(
        pair_profiles, [pair_index(pair, space) for pair in declared_pairs[:depth]]
    )

    def comparison(greedy: Sequence[float], declared: Sequence[float]) -> dict[str, Any]:
        ratios, deltas = [], []
        for gain, base in zip(greedy, declared):
            ratios.append(float(gain / base) if base > 0.0 else None)
            deltas.append(float(gain - base))
        finite = [value for value in ratios if value is not None]
        return {
            "ratio": ratios,
            "delta": deltas,
            "max_ratio": max(finite) if finite else None,
            "max_ratio_depth": (finite.index(max(finite)) + 1) if finite else None,
            "final_ratio": finite[-1] if finite else None,
        }

    return {
        "definition": {
            "coverage": "exp(H(mean of the selected modal participation profiles)) over the declared modes",
            "greedy": "ascending candidate index, each step takes the candidate with the highest coverage; ties to the lower index",
            "declared_order": "the existing deterministic binding order: drive ids on local port 0 and read ids "
                              "on local port 1, pools ascending (geometry.port_bindings)",
            "restricted_greedy": "the same greedy rule over only the seven declared-binding ports",
            "joint_candidates": "all ordered write/read port pairs; a pair's profile is its transfer profile D_w(m)*gain_hat_r(m), normalized",
        },
        "depth": depth,
        "drive": {
            "greedy_ports": [int(port) for port in greedy_drive],
            "greedy_coverage": list(greedy_drive_curve),
            "declared_ports": [int(port) for port in declared_drive[:depth]],
            "declared_coverage": declared_drive_curve,
            "restricted_greedy_ports": [int(declared_drive[index]) for index in restricted_drive],
            "restricted_greedy_coverage": list(restricted_drive_curve),
            "gain": comparison(greedy_drive_curve, declared_drive_curve),
            "restricted_gain": comparison(restricted_drive_curve, declared_drive_curve),
        },
        "read": {
            "greedy_ports": [int(port) for port in greedy_read],
            "greedy_coverage": list(greedy_read_curve),
            "declared_ports": [int(port) for port in declared_read[:depth]],
            "declared_coverage": declared_read_curve,
            "restricted_greedy_ports": [int(declared_read[index]) for index in restricted_read],
            "restricted_greedy_coverage": list(restricted_read_curve),
            "gain": comparison(greedy_read_curve, declared_read_curve),
            "restricted_gain": comparison(restricted_read_curve, declared_read_curve),
        },
        "joint": {
            "candidate_pairs": int(pair_count),
            "greedy_pairs": [pair_of(index, space) for index in greedy_joint],
            "greedy_coverage": list(greedy_joint_curve),
            "declared_pairs": [list(pair) for pair in declared_pairs[:depth]],
            "declared_coverage": declared_joint_curve,
            "restricted_greedy_pairs": [list(declared_pairs[index]) for index in restricted_joint],
            "restricted_greedy_coverage": list(restricted_joint_curve),
            "gain": comparison(greedy_joint_curve, declared_joint_curve),
            "restricted_gain": comparison(restricted_joint_curve, declared_joint_curve),
        },
    }


def pair_index(pair: Sequence[int], space: PlacementSpace) -> int:
    return int(pair[0]) * space.port_count + int(pair[1])


def pair_of(index: int, space: PlacementSpace) -> list[int]:
    return [int(index) // space.port_count, int(index) % space.port_count]


# --------------------------------------------------------------------------
# write/read pair transfer
# --------------------------------------------------------------------------
def pair_tables(
    space: PlacementSpace, drive: Mapping[str, Any], read: Mapping[str, Any], top: int
) -> dict[str, Any]:
    """Every declared write/read pair's transfer score, its best/worst, and the rank signals."""
    transfer = np.asarray(drive["participation"]) @ np.asarray(read["normalized"]).T
    reverse = np.asarray(read["participation"]) @ np.asarray(drive["normalized"]).T
    flat_transfer = transfer.reshape(-1)
    flat_reverse = reverse.reshape(-1)
    order = np.lexsort(
        (np.arange(flat_transfer.size) % space.port_count,
         np.arange(flat_transfer.size) // space.port_count,
         -flat_transfer)
    )
    best = order[: int(top)]
    worst = order[::-1][: int(top)]

    def rows(indices: np.ndarray) -> list[dict[str, Any]]:
        return [
            {
                "write_port": int(index) // space.port_count,
                "read_port": int(index) % space.port_count,
                "write_pool": space.pool_of(int(index) // space.port_count),
                "read_pool": space.pool_of(int(index) % space.port_count),
                "transfer": float(transfer.reshape(-1)[index]),
                "reverse_transfer": float(flat_reverse[index]),
            }
            for index in indices
        ]

    best_read = np.argmax(transfer, axis=1)
    return {
        "definition": {
            "transfer": "sum_m drive_participation_w(m) * read_gain_hat_r(m): the read port's normalized "
                        "modal gain averaged over the modes the write port excites",
            "reverse_transfer": "sum_m read_participation_r(m) * drive_gain_hat_w(m)",
            "rank_correlation": "Spearman with average ranks over the declared ports, and the fraction of "
                                "write ports whose strongest read partner is their own port",
        },
        "pair_count": int(space.port_count * space.port_count),
        "order": {
            "port_count": int(space.port_count),
            "index": "write_port * port_count + read_port",
            "matrix_shape": [int(space.port_count), int(space.port_count)],
            "row": "write port, column: read port",
        },
        "transfer_matrix": [[float(value) for value in row] for row in transfer],
        "reverse_transfer_matrix": [[float(value) for value in row] for row in reverse],
        "best": rows(best),
        "worst": rows(worst),
        "mean_transfer": float(transfer.mean()),
        "min_transfer": float(transfer.min()),
        "max_transfer": float(transfer.max()),
        "mean_absolute_asymmetry": float(np.abs(transfer - reverse).mean()),
        "max_absolute_asymmetry": float(np.abs(transfer - reverse).max()),
        "write_read_rank_correlation": {
            "port_spearman": spearman(drive["effective_modes"], read["effective_modes"]),
            "port_count": int(space.port_count),
            "best_partner_is_itself_fraction": float(np.mean(best_read == np.arange(space.port_count))),
            "best_partner_ports": [int(port) for port in best_read],
        },
    }


# --------------------------------------------------------------------------
# per-arrangement measurement
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PlacementConfig:
    ports_per_pool: int = DEFAULT_PORTS_PER_POOL
    depth: int = DEFAULT_SELECTION_DEPTH
    top: int = TOP_PLACEMENTS
    seed: int = geometry.RANDOM_SEED
    retention_ticks: int = geometry.DEFAULT_RETENTION_TICKS
    retention_work: float = geometry.DEFAULT_IMPULSE_WORK
    include_retention: bool = True

    @classmethod
    def compact(cls) -> "PlacementConfig":
        return cls(depth=3, top=3, include_retention=False)


def _measure(profile: ResonantProfile, config: PlacementConfig) -> dict[str, Any]:
    """The declared placement measurement for one already-built profile."""
    space = placement_space(profile.ports_per_pool)
    basis = modal_basis(profile)
    pins = placement_state_pins(space, profile)
    pickoffs = read_pickoffs(space, profile.port_count)
    drive = signature_scores(drive_signature(pins["pins"], basis), space)
    read = signature_scores(read_signature(pickoffs, basis), space)
    pairs = pair_tables(space, drive, read, config.top)

    pair_profiles = np.zeros((space.port_count * space.port_count, basis["dimension"]), dtype=np.float64)
    for index in range(pair_profiles.shape[0]):
        write, partner = pair_of(index, space)
        profile_row = np.asarray(drive["participation"])[write] * np.asarray(read["normalized"])[partner]
        total = float(profile_row.sum())
        if total > 0.0:
            pair_profiles[index] = profile_row / total

    selection = selection_tables(space, drive, read, pair_profiles, config.depth)

    kernel, kernel_receipt = geometry.subset_kernel(profile, geometry.PORT_SUBSETS[0])
    lift = np.asarray(kernel["input_lift"], dtype=np.float64)
    output = np.asarray(kernel["output_rows"], dtype=np.float64)
    declared_drive = space.declared_drive_ports()
    declared_read = space.declared_read_ports()
    identity = {
        "subset": geometry.PORT_SUBSETS[0].name,
        "kernel_status": str(kernel["status"]),
        "input_lift_vs_port_pin_max_abs_difference": float(
            max(
                np.max(np.abs(lift[:, column] - pins["pins"][port]))
                for column, port in enumerate(declared_drive)
            )
        ),
        "output_rows_vs_port_pickoff_max_abs_difference": float(
            max(
                np.max(np.abs(output[row] - pickoffs[port]))
                for row, port in enumerate(declared_read)
            )
        ),
        "declared_drive_ports": [int(port) for port in declared_drive],
        "declared_read_ports": [int(port) for port in declared_read],
    }

    pin_pickoff = float(np.max(np.abs(pins["pins"] - pickoffs)))
    dual_vs_euclidean = float(
        np.max(
            np.abs(
                np.asarray(drive_signature(pins["pins"], basis))
                - np.asarray(read_signature(pins["pins"], basis))
            )
        )
    )

    record: dict[str, Any] = {
        "basis": {
            "definition": {
                "generator": "reused geometry.linear_generator: beta=0 _WaveOperator, one canonical "
                             "flow(energy_gradient(e_i)) column per state coordinate",
                "gauge": "right eigenvectors scaled to unit 2-norm; dual basis = inv(unit-column matrix)",
                "residual": "||G Vhat - Vhat diag(lambda)||_F / ||G||_F",
                "drive_signature": "|dual @ pin|: the modal amplitude the write pin excites",
                "read_signature": "|conj(Vhat)^T @ pick_off|: the modal gain the read sees",
            },
            "mode_count": int(basis["dimension"]),
            "eigenvector_condition_number": float(basis["eigenvector_condition_number"]),
            "eigendecomposition_residual": float(basis["eigendecomposition_residual"]),
            "unit_column_norm_deviation_max": float(basis["unit_column_norm_deviation_max"]),
            "zero_magnitude_mode_count": int(basis["zero_magnitude_mode_count"]),
            "maximum_growth_rate": float(basis["maximum_growth_rate"]),
            "median_decay_rate": float(basis["median_decay_rate"]),
            "generator_sha256": basis["generator_sha256"],
            "eigenvalue_sha256": basis["eigenvalue_sha256"],
        },
        "placements": {
            "definition": {
                "space": "every port of the paired strand pair (7 pools x ports_per_pool); pool = port // ports_per_pool",
                "write_pin": "production _WaveOperator boundary(0) under the declared placement objective "
                             "(observes the port at 1.0): the canonical input_lift column",
                "read_pickoff": "the canonical output_rows row for a binding at that port: 1/sqrt(2) at port and n+port",
                "participation": "signature / sum(signature) over the arrangement's modes",
                "effective_modes": "exp(H) with H = -sum p log p in nats",
                "max_dominance": "max p",
                "distinguishability": "sum_{m<k} p_m p_k |s_hat_m - s_hat_k|, s_hat = signature / max(signature)",
            },
            "drive": {"ports": drive["ports"], "unreached_ports": drive["unreached_ports"]},
            "read": {"ports": read["ports"], "unreached_ports": read["unreached_ports"]},
            "top": {
                "count": int(config.top),
                "drive": [
                    {"port": int(port), "effective_modes": float(drive["effective_modes"][port])}
                    for port in top_indices(drive["effective_modes"], config.top)
                ],
                "read": [
                    {"port": int(port), "effective_modes": float(read["effective_modes"][port])}
                    for port in top_indices(read["effective_modes"], config.top)
                ],
                "joint": [
                    {
                        "write_port": int(pair["write_port"]),
                        "read_port": int(pair["read_port"]),
                        "transfer": float(pair["transfer"]),
                    }
                    for pair in pairs["best"]
                ],
            },
            "pin_constraint_residual_max": float(pins["constraint_residual_max"]),
            "pin_unit_norm_deviation_max": float(pins["unit_norm_deviation_max"]),
            "pin_vs_canonical_common_pattern_max_abs_difference": float(pins["pattern_max_abs_difference"]),
            "pin_vs_pickoff_max_abs_difference": pin_pickoff,
            "drive_dual_vs_euclidean_max_abs_difference": dual_vs_euclidean,
            "pin_sha256": pins["pin_sha256"],
            "kernel_identity": identity,
        },
        "pairs": pairs,
        "selection": selection,
    }

    if config.include_retention:
        retention = geometry.retention_metrics(
            profile, pools=RETENTION_POOLS, work=config.retention_work, ticks=config.retention_ticks,
        )
        rows = {row["impulse_pool"]: row for row in retention["by_pool"]}
        measured = [pool for pool in RETENTION_POOLS if rows.get(pool, {}).get("status") == "measured"]
        ratios = [rows[pool]["retention_ratio"] for pool in measured]
        record["retention"] = {
            "definition": {
                "retention": "reused geometry.retention_metrics: advance end_energy / post-impulse energy after "
                             "the declared horizon from one-hot pool impulses",
                "crosscheck": "Spearman between per-pool retention ratio and the drive effective-mode count at "
                              "that pool's declared drive port",
                "scope": "a site-persistence cross-check only; it carries no modal-decomposition meaning",
            },
            "ticks": int(config.retention_ticks),
            "work_budget": float(config.retention_work),
            "pools": [int(pool) for pool in RETENTION_POOLS],
            "retention_ratios": [float(value) for value in ratios],
            "site_dependence": float(retention["site_dependence"]) if retention["site_dependence"] is not None else None,
            "spearman_vs_drive_effective_modes": (
                spearman(ratios, [float(drive["effective_modes"][port]) for port in declared_drive[: len(ratios)]])
                if len(ratios) == len(declared_drive) else None
            ),
        }
    return record


def measure_arrangement_placements(
    arrangement: geometry.Arrangement, config: PlacementConfig
) -> dict[str, Any]:
    """Construct one declared arrangement and measure its placement structure twice."""
    started = time.perf_counter()
    profile = geometry.build_profile(arrangement, ports_per_pool=config.ports_per_pool)
    record = _measure(profile, config)
    record["construction"] = {
        "name": arrangement.name,
        "kind": arrangement.kind,
        "construction_rule": arrangement.rule,
        "note": arrangement.note,
        "declared_seed": arrangement.seed,
        "ports_per_pool": int(profile.ports_per_pool),
        "pools": int(profile.pools),
        "port_count": int(profile.port_count),
        "state_dimension": int(4 * profile.port_count),
    }
    # declared determinism check: an independent second construction of the same
    # arrangement must reproduce the basis, the pins and the whole ranking table.
    second = geometry.build_profile(arrangement, ports_per_pool=config.ports_per_pool)
    replay = _measure(second, config)
    record["determinism"] = {
        "generator_identical": replay["basis"]["generator_sha256"] == record["basis"]["generator_sha256"],
        "eigenvalue_digest_identical": replay["basis"]["eigenvalue_sha256"] == record["basis"]["eigenvalue_sha256"],
        "pin_sha256_identical": replay["placements"]["pin_sha256"] == record["placements"]["pin_sha256"],
        "drive_ports_identical": replay["placements"]["drive"]["ports"] == record["placements"]["drive"]["ports"],
        "top_identical": replay["placements"]["top"] == record["placements"]["top"],
        "selection_identical": replay["selection"]["drive"]["greedy_ports"] == record["selection"]["drive"]["greedy_ports"]
        and replay["selection"]["joint"]["greedy_pairs"] == record["selection"]["joint"]["greedy_pairs"],
    }
    record["determinism"]["deterministic"] = bool(all(
        value for key, value in record["determinism"].items() if key != "deterministic"
    ))
    record["elapsed_seconds"] = time.perf_counter() - started
    return record


# --------------------------------------------------------------------------
# cross-arrangement dependence and the receipt
# --------------------------------------------------------------------------
def _top_set(record: Mapping[str, Any], family: str, count: int) -> tuple[Any, ...]:
    top = record["placements"]["top"]
    if family == "drive":
        return tuple(item["port"] for item in top["drive"][:count])
    if family == "read":
        return tuple(item["port"] for item in top["read"][:count])
    return tuple((item["write_port"], item["read_port"]) for item in top["joint"][:count])


def arrangement_dependence(records: Sequence[Mapping[str, Any]], count: int) -> dict[str, Any]:
    """Top placements per arrangement, their overlap across arrangements, and the declared margins."""
    names = [record["construction"]["name"] for record in records]
    families: dict[str, Any] = {}
    for family in ("drive", "read", "joint"):
        sets = {name: _top_set(record, family, count) for record, name in zip(records, names)}
        rows = []
        for left in range(len(names)):
            for right in range(left + 1, len(names)):
                overlap = set_overlap(sets[names[left]], sets[names[right]])
                rows.append({
                    "left": names[left], "right": names[right],
                    "shared": overlap["shared"], "jaccard": overlap["jaccard"],
                })
        jaccards = [row["jaccard"] for row in rows]
        consensus = set(sets[names[0]])
        for name in names[1:]:
            consensus &= set(sets[name])
        families[family] = {
            "top_sets": {name: [list(item) if isinstance(item, tuple) else item for item in sets[name]] for name in names},
            "pairwise": rows,
            "mean_jaccard": float(np.mean(jaccards)) if jaccards else None,
            "min_jaccard": float(np.min(jaccards)) if jaccards else None,
            "max_jaccard": float(np.max(jaccards)) if jaccards else None,
            "consensus": sorted(list(consensus)),
            "consensus_size": len(consensus),
            "distinct_top_sets": len({frozenset(sets[name]) for name in names}),
        }
    present = {record["construction"]["name"]: record for record in records}
    margins = []
    for arrangement_name, left, right in PLACEMENT_MARGIN_PAIRS:
        if arrangement_name not in present:
            continue
        ports = {row["port"]: row for row in present[arrangement_name]["placements"]["drive"]["ports"]}
        measured = abs(ports[left]["effective_modes"] - ports[right]["effective_modes"])
        margins.append({
            "kind": "placement", "arrangement": arrangement_name,
            "left": left, "right": right,
            "left_effective_modes": ports[left]["effective_modes"],
            "right_effective_modes": ports[right]["effective_modes"],
            "measured": float(measured), "margin": PLACEMENT_MARGIN_EFFECTIVE_MODES,
            "satisfied": bool(measured >= PLACEMENT_MARGIN_EFFECTIVE_MODES),
        })
    left_name, right_name = ARRANGEMENT_MARGIN_PAIR
    if left_name in present and right_name in present:
        left_best = max(row["effective_modes"] for row in present[left_name]["placements"]["drive"]["ports"])
        right_best = max(row["effective_modes"] for row in present[right_name]["placements"]["drive"]["ports"])
        margins.append({
            "kind": "arrangement", "left": left_name, "right": right_name,
            "left_best_effective_modes": float(left_best), "right_best_effective_modes": float(right_best),
            "measured": float(abs(left_best - right_best)), "margin": ARRANGEMENT_MARGIN_EFFECTIVE_MODES,
            "satisfied": bool(abs(left_best - right_best) >= ARRANGEMENT_MARGIN_EFFECTIVE_MODES),
        })
    return {
        "definition": {
            "top_sets": f"the declared top-{count} placements per arrangement from the declared scores",
            "overlap": "Jaccard overlap of the top-`count` sets of two arrangements",
            "consensus": "placements present in every arrangement's top-`count` set",
            "margins": "declared can-fail separation statements between two declared placements "
                       "and between two declared arrangements",
        },
        "families": families,
        "margins": margins,
        "all_margins_satisfied": bool(all(row["satisfied"] for row in margins)),
    }


def exploration_declarations(config: PlacementConfig) -> dict[str, Any]:
    space = placement_space(config.ports_per_pool)
    return {
        "schema": RECEIPT_SCHEMA,
        "question": "which port placements reach the arrangement's modes: which excite distinct modes, "
                    "which can tell them apart, are good write ports good read ports, and does the best "
                    "placement depend on the arrangement?",
        "scope": "bounded measurement of modal access on the declared linearization; placements are candidate "
                 "ports, not memory or task claims.",
        "ports_per_pool": int(config.ports_per_pool),
        "port_count": int(space.port_count),
        "candidate_ports": list(space.ports),
        "candidate_pairs": int(space.port_count ** 2),
        "declared_drive_ports": list(space.declared_drive_ports()),
        "declared_read_ports": list(space.declared_read_ports()),
        "declared_pairs": [list(pair) for pair in space.declared_pairs()],
        "selection_depth": int(config.depth),
        "top_placements": int(config.top),
        "placement_objective": {
            "precision": f"{geometry.PRIOR_RIDGE:g}*I + {geometry.PRIOR_MASS:g}*ones/m with m = 1",
            "observed": "the placement variable pinned at 1.0",
            "origin": "the harness's declared_problem rule evaluated at one variable",
        },
        "coverage_objective": "exp(H(mean of the selected modal participation profiles))",
        "tolerances": {
            "pin_tolerance": PIN_TOLERANCE,
            "eigen_residual_tolerance": EIGEN_RESIDUAL_TOLERANCE,
            "eigen_condition_limit": EIGEN_CONDITION_LIMIT,
        },
        "margins": {
            "placement_effective_modes": PLACEMENT_MARGIN_EFFECTIVE_MODES,
            "arrangement_effective_modes": ARRANGEMENT_MARGIN_EFFECTIVE_MODES,
            "placement_pairs": [list(item) for item in PLACEMENT_MARGIN_PAIRS],
            "arrangement_pair": list(ARRANGEMENT_MARGIN_PAIR),
        },
        "retention": {
            "pools": [int(pool) for pool in RETENTION_POOLS],
            "ticks": int(config.retention_ticks),
            "work_budget": float(config.retention_work),
            "included": bool(config.include_retention),
        },
        "seed": int(config.seed),
        "reused_helpers": [
            "geometry.arrangements / geometry.arrangement_named",
            "geometry.build_profile",
            "geometry.linear_generator",
            "geometry.port_bindings (the existing deterministic binding order)",
            "geometry.PORT_SUBSETS / geometry.subset_kernel (the canonical input_lift and output_rows)",
            "geometry.retention_metrics (the canonical site-persistence walk)",
            "geometry.canonical_digest / geometry.content_digest",
        ],
        "boundary": [
            "Every number is a modal-access proxy on the declared beta=0 linearization at rest, not the "
            "evolving nonlinear body.",
            "The canonical write pin and read pick-off are structure invariants of the declared objective and "
            "bindings (measured here), so every placement difference reported comes from the arrangement's "
            "eigenbasis alone.",
            "Modes are the state's eigenmodes, including any zero-eigenvalue direction; no task relevance ranks them.",
            "Distinguishability uses signature magnitude only; signature phase is eigenvector gauge and is excluded.",
            "Coverage, dominance and transfer are scalar proxies on a declared linear scaffold, not measured "
            "task performance, learning, recall quality or memory utility.",
            "Selection is compared against the declared deterministic binding order under the same declared "
            "objective, not against a task-measured utility.",
            "The input hook is a state pin and the readout is a port pick-off, so no input-energy or work "
            "accounting enters this harness.",
        ],
    }


def explore(
    config: PlacementConfig | None = None, *, names: Sequence[str] | None = None
) -> dict[str, Any]:
    """Measure the declared arrangements and return the placement receipt."""
    config = config or PlacementConfig()
    started = time.perf_counter()
    selected = [
        item for item in geometry.arrangements(seed=config.seed)
        if names is None or item.name in set(names)
    ]
    if names is not None and len(selected) != len(set(names)):
        raise ResonantNumericalError(f"unknown arrangement name in {tuple(names)}")
    records = [measure_arrangement_placements(item, config) for item in selected]
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "declarations": exploration_declarations(config),
        "arrangements": records,
        "arrangement_dependence": arrangement_dependence(records, config.top),
        "limitations": [
            "One port per direction: each read is a single-port pick-off, so simultaneous multi-port reads "
            "are outside this measurement.",
            "The canonical write pin and read pick-off coincide as state vectors, so any write/read asymmetry "
            "reported is the dual-versus-primal modal expansion, not a difference in port functionals.",
            "Eigenvector gauge is fixed at unit 2-norm, so only signature magnitudes are compared; complex "
            "phase information is not used.",
            "The eigendecomposition is dense and non-symmetric; the conditioning and eigen-residual are "
            "reported, and a basis above the declared conditioning limit is refused rather than reported.",
            "The candidate space is every port of the paired strand pair, so a placement is an index, not an "
            "interior/junction/boundary classification.",
            "The retention cross-check uses one declared work budget and one horizon, and carries no "
            "modal-decomposition meaning.",
            "Arrangements share the pool count, port resolution and coordinates, so no placement can change "
            "the scaffold size (see the geometry harness's own limitations).",
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
    declarations = receipt["declarations"]
    depth = declarations["selection_depth"]
    lines = [
        f"arrangements: {len(receipt['arrangements'])}  ports/arrangement: {declarations['port_count']}  "
        f"candidate pairs: {declarations['candidate_pairs']}  depth: {depth}  "
        f"top: {declarations['top_placements']}",
        f"declared binding order: drive {declarations['declared_drive_ports']}  "
        f"read {declarations['declared_read_ports']}",
        "",
    ]
    header = (
        f"{'arrangement':<23}{'modes':>6}{'cond':>7}{'eigres':>9}{'det':>5} "
        f"{'bestW':>6}{'Weff':>8}{'Wdom':>7}{'Wdist':>7} "
        f"{'bestR':>6}{'Reff':>8}{'Rdist':>7} {'rho':>6}"
    )
    lines.extend([header, "-" * len(header)])
    for record in receipt["arrangements"]:
        basis = record["basis"]
        placements = record["placements"]
        pairs = record["pairs"]
        drive_ports = {row["port"]: row for row in placements["drive"]["ports"]}
        read_ports = {row["port"]: row for row in placements["read"]["ports"]}
        drive_top = placements["top"]["drive"][0]["port"]
        read_top = placements["top"]["read"][0]["port"]
        lines.append(
            f"{record['construction']['name']:<23}"
            f"{basis['mode_count']:>6}"
            f"{basis['eigenvector_condition_number']:>7.2f}"
            f"{basis['eigendecomposition_residual']:>9.2e}"
            f"{'yes' if record['determinism']['deterministic'] else 'NO':>5} "
            f"{drive_top:>6}"
            f"{drive_ports[drive_top]['effective_modes']:>8.2f}"
            f"{drive_ports[drive_top]['max_dominance']:>7.4f}"
            f"{drive_ports[drive_top]['distinguishability']:>7.4f} "
            f"{read_top:>6}"
            f"{read_ports[read_top]['effective_modes']:>8.2f}"
            f"{read_ports[read_top]['distinguishability']:>7.4f} "
            f"{pairs['write_read_rank_correlation']['port_spearman']:>6.3f}"
        )
    lines.append(
        "columns: modes = state dimension; cond = eigenvector basis conditioning; eigres = relative "
        "eigen-residual; det = determinism check; bestW/bestR = top port by effective modes; Weff/Reff = "
        "effective modes (exp of participation entropy) at that port; Wdom = its maximum single-mode "
        "dominance; Wdist/Rdist = its modal distinguishability; rho = per-port Spearman between write and "
        "read quality."
    )
    lines.append("")
    header2 = (
        f"{'arrangement':<23}{'Tmax':>8}{'Tmin':>8}{'best pair':>12}{'T':>8}"
        f"{'gWf':>7}{'gWrk':>7}{'gWrkd':>7}{'gWk':>6}{'gWd':>5}{'gRf':>7}{'gJf':>7}{'gJr':>7}{'gJk':>7}{'gJd':>5}"
    )
    lines.extend([header2, "-" * len(header2)])
    for record in receipt["arrangements"]:
        pairs = record["pairs"]
        selection = record["selection"]
        best = pairs["best"][0]
        drive_gain = selection["drive"]["gain"]
        read_gain = selection["read"]["gain"]
        joint_gain = selection["joint"]["gain"]
        lines.append(
            f"{record['construction']['name']:<23}"
            f"{pairs['max_transfer']:>8.4f}"
            f"{pairs['min_transfer']:>8.4f}"
            f"{('(' + str(best['write_port']) + ',' + str(best['read_port']) + ')'):>12}"
            f"{best['transfer']:>8.4f}"
            f"{(drive_gain['final_ratio'] or 0.0):>7.3f}"
            f"{(selection['drive']['restricted_gain']['max_ratio'] or 0.0):>7.3f}"
            f"{(selection['drive']['restricted_gain']['max_ratio_depth'] or 0):>5}"
            f"{(drive_gain['max_ratio'] or 0.0):>6.3f}"
            f"{drive_gain['max_ratio_depth']:>5}"
            f"{(read_gain['final_ratio'] or 0.0):>7.3f}"
            f"{(joint_gain['final_ratio'] or 0.0):>7.3f}"
            f"{(selection['joint']['restricted_gain']['max_ratio'] or 0.0):>7.3f}"
            f"{(joint_gain['max_ratio'] or 0.0):>7.3f}"
            f"{joint_gain['max_ratio_depth']:>5}"
        )
    lines.append(
        f"columns: Tmax/Tmin = best and worst write-read transfer over all {declarations['candidate_pairs']} "
        f"declared pairs; gWf/gRf/gJf = greedy coverage ratio against the declared binding order at depth "
        f"{depth}; gWrk/gWrkd = the best ratio from greedily reordering only the declared binding ports and "
        f"the depth where it occurs (the restricted set is the declared set at depth {depth}, so that ratio "
        "returns to 1.0 there); gJr = the same for joint pairs; gWk/gJk = the largest ratio over the whole "
        "candidate space at any depth and gWd/gJd = that depth."
    )
    lines.append("")
    lines.append(f"top-{declarations['top_placements']} placements and the best/worst declared pairs:")
    for record in receipt["arrangements"]:
        top = record["placements"]["top"]
        pairs = record["pairs"]
        worst = pairs["worst"][0]
        lines.append(
            f"  {record['construction']['name']:<23} drive {[item['port'] for item in top['drive']]}"
            f"  read {[item['port'] for item in top['read']]}"
            f"  joint {[(item['write_port'], item['read_port']) for item in top['joint']]}"
            f"  worst ({worst['write_port']},{worst['read_port']})={worst['transfer']:.2e}"
        )
    lines.append("")
    dependence = receipt["arrangement_dependence"]["families"]
    for family in ("drive", "read", "joint"):
        entry = dependence[family]
        lines.append(
            f"arrangement dependence ({family}): mean Jaccard {entry['mean_jaccard']:.3f}  "
            f"min {entry['min_jaccard']:.3f}  max {entry['max_jaccard']:.3f}  "
            f"distinct top sets {entry['distinct_top_sets']}/{len(receipt['arrangements'])}  "
            f"consensus {entry['consensus']}"
        )
    lines.append("")
    for row in receipt["arrangement_dependence"]["margins"]:
        lines.append(
            f"declared margin ({row['kind']}): {row['left']} vs {row['right']} measured={row['measured']:.4f} "
            f"margin={row['margin']:.4g} satisfied={row['satisfied']}"
        )
    lines.append(
        f"all declared margins satisfied: {receipt['arrangement_dependence']['all_margins_satisfied']}"
    )
    lines.append(
        f"write/read rank correlation across arrangements: "
        f"mean {float(np.mean([r['pairs']['write_read_rank_correlation']['port_spearman'] for r in receipt['arrangements']])):.3f}  "
        f"min {float(np.min([r['pairs']['write_read_rank_correlation']['port_spearman'] for r in receipt['arrangements']])):.3f}"
    )
    lines.append(f"runtime_seconds: {receipt['runtime_seconds']:.2f}")
    lines.append(f"receipt_sha256: {receipt['receipt_sha256']}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--ports-per-pool", type=int, default=DEFAULT_PORTS_PER_POOL)
    parser.add_argument("--depth", type=int, default=DEFAULT_SELECTION_DEPTH)
    args = parser.parse_args(argv)
    config = replace(PlacementConfig(), ports_per_pool=args.ports_per_pool, depth=args.depth)
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
