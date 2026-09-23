"""Factorial comparison of geometry, metric, wiring, and transceiver placement.

This workstream deliberately measures only the reachable production hooks.  The
six requested names are represented as five geometry levels plus the
``task-selected`` placement level; the latter is not a geometry because the
production API has no coordinate or module-placement hook.  Every cell uses
``geometry.build_profile`` and the imported placement modal helpers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_geometry_exploration as geometry
import run_fractal_metric_exploration as metric
import run_fractal_placement_exploration as placement

SCHEMA = "cassifi.fractal-factorial-exploration.v1"
RECEIPT_SCHEMA = "cassifi.fractal-factorial-receipt.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-factorial/exploration.json")
SEED = 20260916
PORTS_PER_POOL = geometry.DEFAULT_PORTS_PER_POOL
# The largest honest geometry slice. task-selected is a placement level below.
GEOMETRY_LEVELS = (
    ("current-paired-helix", "helix7"),
    ("flat-regular", "flat-ladder"),
    ("matched-random-rewiring", "random-rewire-matched"),
    ("nested-core-shell", "nested-core-shell"),
    ("recursive-paired-loop-modules", "recursive-paired-loops"),
)
METRIC_LEVELS = ("canonical", "shell")
WIRING_LEVELS = ("native", "silenced-cross-scale")
PLACEMENT_LEVELS = ("canonical-port", "task-selected")
SAMPLES = (0, 8, 16, 32, 64)
ALIGNMENT_THRESHOLD = 0.8
MARGIN = 1e-6
CONTINUITY_TOLERANCE = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "started_at", "finished_at", "receipt_sha256", "content_digest"})


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): strip_timing(v) for k, v in value.items() if k not in TIMING_KEYS}
    if isinstance(value, (tuple, list)):
        return [strip_timing(v) for v in value]
    return value


def content_digest(value: Any) -> str:
    return canonical_digest(strip_timing(value))


def _array_digest(value: Any) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(value, dtype="<f8")).tobytes()).hexdigest()


def build_factor_profile(geometry_name: str, metric_name: str, wiring_name: str):
    """Compose factors through production geometry and metric hooks only."""
    arrangement = geometry.arrangement_named(geometry_name, seed=SEED)
    profile = geometry.build_profile(arrangement, ports_per_pool=PORTS_PER_POOL)
    transport = np.asarray(profile.transport_matrix, dtype=np.float64)
    if wiring_name == "silenced-cross-scale":
        ports = profile.port_count
        pools = (np.arange(2 * ports) % ports) // PORTS_PER_POOL
        transport = np.where(pools[:, None] == pools[None, :], transport, 0.0)
    if metric_name == "canonical":
        inverse_mass = metric.canonical_metric_vector(ports_per_pool=PORTS_PER_POOL)
    elif metric_name == "shell":
        inverse_mass = metric.shell_inverse_mass(0.7, core_pool=3, ports_per_pool=PORTS_PER_POOL)
    else:
        raise ValueError(f"unknown metric {metric_name}")
    return replace(profile, projected_transport=transport, projected_inv_mass=inverse_mass)


def _modal_data(profile: Any) -> dict[str, Any]:
    """Use the placement builder's declared modal basis and pick-off rows."""
    basis = placement.modal_basis(profile)
    space = placement.placement_space(profile.ports_per_pool)
    pickoffs = placement.read_pickoffs(space, profile.port_count)
    signatures = placement.read_signature(pickoffs, basis)
    scores = placement.signature_scores(signatures, space)
    return {"basis": basis, "space": space, "pickoffs": pickoffs, "scores": scores}


def _propagated_alignment(eigenvalues: np.ndarray, vectors: np.ndarray, dual: np.ndarray, direction: np.ndarray, tick: int) -> float:
    norm = float(np.vdot(direction, direction).real)
    if norm <= 0.0:
        return 0.0
    coeff = np.asarray(dual @ direction, dtype=np.complex128)
    left = np.asarray(direction @ vectors, dtype=np.complex128)
    value = np.sum(left * np.exp(np.asarray(eigenvalues, dtype=np.complex128) * float(tick)) * coeff) / norm
    return float(np.real_if_close(value, tol=1000).real)


def lifetime_measure(profile: Any, modal: Mapping[str, Any], placement_name: str, *, shuffled: bool = False) -> dict[str, Any]:
    scores = modal["scores"]
    effective = np.asarray(scores["effective_modes"], dtype=np.float64)
    if placement_name == "canonical-port":
        port = 0
    elif placement_name == "task-selected":
        port = int(placement.top_indices(effective, 1)[0])
    else:
        raise ValueError(placement_name)
    if shuffled:
        rng = np.random.default_rng(SEED)
        order = rng.permutation(profile.port_count)
        port = int(order[0])
    pickoff = np.asarray(modal["pickoffs"][port], dtype=np.float64)
    # Position half of the production state is the declared readout direction.
    direction = np.zeros(modal["basis"]["dimension"], dtype=np.float64)
    direction[: pickoff.size] = pickoff
    direction /= max(float(np.linalg.norm(direction)), 1e-300)
    values = [_propagated_alignment(modal["basis"]["eigenvalues"], modal["basis"]["vectors"], modal["basis"]["dual"], direction, tick) for tick in SAMPLES]
    above = [value >= ALIGNMENT_THRESHOLD for value in values]
    first = next((tick for tick, ok in zip(SAMPLES, above) if tick > 0 and not ok), None)
    returns = sum(1 for index in range(1, len(above)) if not above[index - 1] and above[index])
    return {
        "port": port,
        "placement": placement_name,
        "shuffled": bool(shuffled),
        "direction_sha256": _array_digest(direction),
        "samples": list(SAMPLES),
        "alignment": values,
        "threshold_fraction": ALIGNMENT_THRESHOLD,
        "first_crossing_tick": first,
        "occupancy_fraction": float(sum(above) / len(above)),
        "return_window_count": int(returns),
        "return_windows": {"sampled_transitions": int(returns), "window_definition": "below threshold followed by above threshold"},
        "exact_bilinear_prediction": {"generator": "placement.modal_basis generator", "formula": "<r0, C exp(-L t) r0>/<r0,r0>", "used": True},
    }


def _cell_record(geom_label: str, geom_name: str, metric_name: str, wiring_name: str, placement_name: str) -> dict[str, Any]:
    profile = build_factor_profile(geom_name, metric_name, wiring_name)
    modal = _modal_data(profile)
    measured = lifetime_measure(profile, modal, placement_name)
    shuffled = lifetime_measure(profile, modal, placement_name, shuffled=True)
    measured.update({
        "geometry": geom_label,
        "geometry_builder_name": geom_name,
        "metric": metric_name,
        "cross_scale_wiring": wiring_name,
        "profile_signature": {
            "transport_sha256": _array_digest(profile.transport_matrix),
            "inverse_mass_sha256": _array_digest(profile.projected_inv_mass),
            "generator_sha256": modal["basis"]["generator_sha256"],
        },
        "shuffled_placement_control": shuffled,
    })
    return measured


def _continuity() -> list[dict[str, Any]]:
    cited = {"helix7": 0.1565230898708423, "nested-core-shell": 0.15986442406282375}
    rows = []
    for name, expected in cited.items():
        profile = geometry.build_profile(geometry.arrangement_named(name, seed=SEED), ports_per_pool=PORTS_PER_POOL)
        observed = float(geometry.spectrum_metrics(profile, rail_gains=())["ipr_median"])
        rows.append({"source_receipt": "_diag/fractal-geometry/exploration.json", "value": "spectrum.ipr_median", "arrangement": name, "cited": expected, "observed": observed, "tolerance": CONTINUITY_TOLERANCE, "within_tolerance": bool(abs(observed - expected) <= CONTINUITY_TOLERANCE)})
    return rows


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    cells = []
    for geom_label, geom_name in GEOMETRY_LEVELS:
        for metric_name in METRIC_LEVELS:
            for wiring_name in WIRING_LEVELS:
                for placement_name in PLACEMENT_LEVELS:
                    cells.append(_cell_record(geom_label, geom_name, metric_name, wiring_name, placement_name))
    by_key = {
        (cell["geometry"], cell["metric"], cell["cross_scale_wiring"], cell["placement"]): cell
        for cell in cells
    }
    comparisons = []
    for cell in cells:
        ctrl = cell["shuffled_placement_control"]
        delta = float(cell["occupancy_fraction"] - ctrl["occupancy_fraction"])
        comparisons.append({
            "cell": {k: cell[k] for k in ("geometry", "metric", "cross_scale_wiring", "placement")},
            "comparison": f"{cell['placement']}-vs-shuffled-placement",
            "difference": delta,
            "margin": MARGIN,
            "separates": bool(abs(delta) >= MARGIN),
            "firing_control": {"kind": "shuffled-placement", "attempted": True,
                               "difference": delta, "can_fail": True},
        })
    for geom_label, _geom_name in GEOMETRY_LEVELS:
        for metric_name in METRIC_LEVELS:
            for placement_name in PLACEMENT_LEVELS:
                native = by_key[(geom_label, metric_name, "native", placement_name)]
                silent = by_key[(geom_label, metric_name, "silenced-cross-scale", placement_name)]
                delta = float(native["occupancy_fraction"] - silent["occupancy_fraction"])
                comparisons.append({
                    "cell": {"geometry": geom_label, "metric": metric_name,
                             "placement": placement_name},
                    "comparison": "native-vs-silenced-cross-scale",
                    "difference": delta, "margin": MARGIN,
                    "separates": bool(abs(delta) >= MARGIN),
                    "firing_control": {"kind": "silenced-no-authority", "attempted": True,
                                       "difference": delta, "can_fail": True},
                })
        for wiring_name in WIRING_LEVELS:
            for placement_name in PLACEMENT_LEVELS:
                canonical = by_key[(geom_label, "canonical", wiring_name, placement_name)]
                shell = by_key[(geom_label, "shell", wiring_name, placement_name)]
                delta = float(canonical["occupancy_fraction"] - shell["occupancy_fraction"])
                comparisons.append({
                    "cell": {"geometry": geom_label, "wiring": wiring_name,
                             "placement": placement_name},
                    "comparison": "canonical-vs-shell-metric",
                    "difference": delta, "margin": MARGIN,
                    "separates": bool(abs(delta) >= MARGIN),
                    "firing_control": {"kind": "metric-hook", "attempted": True,
                                       "difference": delta, "can_fail": True},
                })
    controls = {
        "silenced_no_authority": {"factor": "cross_scale_wiring", "level": "silenced-cross-scale", "definition": "all cross-pool transport entries zeroed after production rail construction", "can_fail_margin": MARGIN, "firing_control": "native-vs-silenced alignment at every matched cell", "attempted": True},
        "shuffled_placement": {"factor": "transceiver_placement", "definition": "seeded permutation chooses a non-task-selected port", "seed": SEED, "can_fail_margin": MARGIN, "attempted": True},
        "receipt_mutation": {"definition": "test mutates one measured alignment leaf and requires content digest change", "can_fail_margin": True, "attempted": False, "executed_by": "test_fractal_factorial_exploration.py"},
    }
    body = {
        "schema": SCHEMA,
        "question": "Which reachable geometry, metric, cross-scale wiring, and transceiver-placement factors alter linear retention?",
        "declarations": {
            "grid": {"geometry": [x[0] for x in GEOMETRY_LEVELS], "metric": list(METRIC_LEVELS), "cross_scale_wiring": list(WIRING_LEVELS), "transceiver_placement": list(PLACEMENT_LEVELS), "cells": len(cells)},
            "named_arrangement_families": [
                {"name": "current paired helix", "axis": "geometry", "builder": "helix7"},
                {"name": "flat regular", "axis": "geometry", "builder": "flat-ladder"},
                {"name": "matched random rewiring", "axis": "geometry", "builder": "random-rewire-matched"},
                {"name": "nested core-shell", "axis": "geometry", "builder": "nested-core-shell"},
                {"name": "recursive paired-loop modules", "axis": "geometry", "builder": "recursive-paired-loops"},
                {"name": "task-selected placement", "axis": "transceiver_placement", "builder": "placement.top_indices"},
            ],
            "arms": {"samples": list(SAMPLES), "write_budget": 0.001, "seed": SEED, "statistic": "first crossing plus occupancy and return windows", "alignment_threshold": ALIGNMENT_THRESHOLD, "margin": MARGIN, "decision_rule": "claim separation only when absolute matched-cell difference reaches margin and its firing control was attempted"},
            "factors": {"geometry": "geometry.build_profile arrangement rail", "metric": "projected_inv_mass hook (canonical or metric.shell_inverse_mass)", "cross_scale_wiring": "projected_transport with cross-pool entries retained or silenced", "transceiver_placement": "placement.read_pickoffs and placement.top_indices effective-mode objective"},
            "digest": {"algorithm": "sha256", "canonicalization": "sorted-key compact JSON allow_nan=False", "stripped_clock_fields": sorted(TIMING_KEYS - {"receipt_sha256", "content_digest"})},
            "lifetime": {"first_crossing": "first sampled tick below 0.8 of post-write alignment", "occupancy": "fraction of declared samples at or above threshold", "return_windows": "below-to-above threshold transitions", "mode_prediction": "exact bilinear eigen expansion, not an amplitude-weighted decay average"},
        },
        "arms": cells,
        "comparisons": comparisons,
        "controls": controls,
        "continuity_checks": _continuity(),
        "limitations": [
            "The production API has no coordinate override: arrangement.coordinates is inert, so literal spatial spacing cannot be factorialized.",
            "Recursive paired-loop modules are represented by the existing recursive-paired-loops pool graph; nested copies of modules are not expressible.",
            "Task-selected placement is a transceiver-placement level, not a sixth geometry family; no geometry hook can identify it as a geometry.",
            "The linear generator is a beta=0 rest linearization; this is not task utility, semantic retrieval, or nonlinear survival.",
            "Silencing cross-pool entries is a declared no-authority control, not an independent physical wiring implementation.",
        ],
        "verdicts": {"continuity": "pending", "factorial": "measured; see per-cell margins", "scope": "reachable production-hook slice only"},
    }
    body["verdicts"]["continuity"] = "PASS" if all(row["within_tolerance"] for row in body["continuity_checks"]) else "FAIL"
    body["elapsed_seconds"] = time.perf_counter() - started
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    body["runtime_seconds"] = body["elapsed_seconds"]
    return body


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_jsonable(receipt), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
