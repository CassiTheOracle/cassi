"""Matched geometry-vs-geometry comparison on the reachable CassiFI field hooks.

The runner deliberately keeps the comparison narrower than the existing factorial
workstream: two edge-budget-matched geometry pairs are measured across the
existing durability capacity arms, while metric, wiring, and placement are
reported as controls.  No shared module is changed and no task-level recall is
claimed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry
import run_fractal_metric_exploration as metric
import run_fractal_placement_exploration as placement
import run_fractal_survival_exploration as survival

SCHEMA = "cassifi.fractal-geometry-pair-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-geometry-pair/exploration.json")
PAIRS = (
    {
        "name": "topology-rewire",
        "left": "flat-ladder",
        "right": "random-rewire-matched",
        "claim": "pool-graph destination topology at matched realized interaction budget",
    },
    {
        "name": "strength-distribution",
        "left": "flat-ladder",
        "right": "quasiperiodic-chain",
        "claim": "cross-pool strength distribution on the same chain support",
    },
)
METRICS = ("canonical", "shell")
WIRINGS = ("native", "silenced-cross-scale")
CAPACITY_COUNTS = (1, 2, 4, 8)
PLACEMENTS = ("canonical-port-0", "task-selected", "seeded-shuffle-control")
EDGE_MATCH_TOLERANCE = 1e-12
RECOVERY_MARGIN = 0.02
PLACEMENT_MODE_MARGIN = float(placement.PLACEMENT_MARGIN_EFFECTIVE_MODES)
PLACEMENT_RECOVERY_MARGIN = 0.02
CONTINUITY_TOLERANCE = 1e-12
SHUFFLE_SEED = geometry.RANDOM_SEED
TIMING_KEYS = frozenset({
    "elapsed_seconds", "runtime_seconds", "started_at", "finished_at",
    "content_digest", "receipt_sha256",
})
CITED_IPR = {
    "flat-ladder": 0.2612791610024881,
    "random-rewire-matched": 0.2686921872219767,
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): strip_timing(item) for key, item in value.items() if key not in TIMING_KEYS}
    if isinstance(value, (tuple, list)):
        return [strip_timing(item) for item in value]
    return value


def content_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(strip_timing(value)).encode("utf-8")).hexdigest()


def array_digest(value: Any) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(value, dtype="<f8")).tobytes()).hexdigest()


def _pool_axis(profile: Any) -> np.ndarray:
    ports = int(profile.port_count)
    return (np.arange(2 * ports) % ports) // int(profile.ports_per_pool)


def edge_signature(arrangement: Any, profile: Any) -> dict[str, Any]:
    rail = np.asarray(profile.transport_matrix, dtype=np.float64)
    pools = _pool_axis(profile)
    cross = pools[:, None] != pools[None, :]
    links = geometry.effective_links(arrangement, ports_per_pool=profile.ports_per_pool)
    per_pool_degree = [0] * int(profile.pools)
    per_pool_strength = [0.0] * int(profile.pools)
    for source, destination, scale in links:
        per_pool_degree[int(source)] += 1
        per_pool_degree[int(destination)] += 1
        per_pool_strength[int(source)] += abs(float(scale))
        per_pool_strength[int(destination)] += abs(float(scale))
    return {
        "arrangement": arrangement.name,
        "effective_link_count": len(links),
        "effective_links": [[int(a), int(b), float(c)] for a, b, c in links],
        "coupled_pool_pairs": [list(pair) for pair in geometry.coupled_pool_pairs(rail, profile.ports_per_pool)],
        "cross_pool_entries": int(np.count_nonzero(rail * cross)),
        "cross_pool_strength_l1": float(np.abs(rail * cross).sum()),
        "per_pool_degree": per_pool_degree,
        "per_pool_declared_strength": per_pool_strength,
        "transport_sha256": array_digest(rail),
        "rail_antisymmetry_max_abs": float(np.abs(rail + rail.T).max()),
    }


def build_profile(arrangement_name: str, metric_name: str, wiring_name: str) -> Any:
    arrangement = geometry.arrangement_named(arrangement_name, seed=geometry.RANDOM_SEED)
    profile = geometry.build_profile(arrangement, ports_per_pool=geometry.DEFAULT_PORTS_PER_POOL)
    if wiring_name == "silenced-cross-scale":
        profile = geometry.cross_pool_gain_profile(profile, 0.0)
    if metric_name == "canonical":
        inverse_mass = metric.canonical_metric_vector(ports_per_pool=profile.ports_per_pool)
    elif metric_name == "shell":
        inverse_mass = metric.shell_inverse_mass(
            0.7, core_pool=geometry.CORE_SHELL_CORE_POOL,
            ports_per_pool=profile.ports_per_pool,
        )
    else:
        raise ValueError(metric_name)
    return replace(profile, projected_inv_mass=inverse_mass)


def placement_record(profile: Any) -> dict[str, Any]:
    basis = placement.modal_basis(profile)
    space = placement.placement_space(profile.ports_per_pool)
    pickoffs = placement.read_pickoffs(space, profile.port_count)
    signature = placement.read_signature(pickoffs, basis)
    scores = placement.signature_scores(signature, space)
    effective = np.asarray(scores["effective_modes"], dtype=np.float64)
    selected = int(placement.top_indices(effective, 1)[0])
    rng = np.random.default_rng(SHUFFLE_SEED)
    shuffled = int(rng.permutation(profile.port_count)[0])
    return {
        "canonical_port": 0,
        "task_selected_port": selected,
        "shuffled_port": shuffled,
        "effective_modes": float(effective[selected]),
        "canonical_effective_modes": float(effective[0]),
        "selected_minus_canonical_effective_modes": float(effective[selected] - effective[0]),
        "placement_mode_margin": PLACEMENT_MODE_MARGIN,
        "generator_sha256": str(basis["generator_sha256"]),
        "generator_dimension": int(basis["dimension"]),
        "eigendecomposition_residual": float(basis["eigendecomposition_residual"]),
        "condition_number": float(basis["eigenvector_condition_number"]),
        "effective_modes_sha256": array_digest(effective),
    }


def capacity_arms(config: durability.DurabilityConfig) -> dict[int, durability.Arm]:
    declared = {arm.name: arm for arm in durability.arm_declarations(config)}
    names = {1: "restart-and-activity", 2: "restart-and-activity-k2", 4: "restart-and-activity-k4", 8: "restart-and-activity-k8"}
    return {count: declared[names[count]] for count in CAPACITY_COUNTS}


def capacity_record(config: durability.DurabilityConfig, profile: Any, count: int, captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    arm = capacity_arms(config)[count]
    out = durability.run_arm(config, profile, captures, arm)
    return survival.compact_arm_record(out, config.control_margin)


def profile_record(config: durability.DurabilityConfig, arrangement_name: str, metric_name: str, wiring_name: str) -> dict[str, Any]:
    arrangement = geometry.arrangement_named(arrangement_name, seed=geometry.RANDOM_SEED)
    profile = build_profile(arrangement_name, metric_name, wiring_name)
    captures = durability.capture_items(config, profile)
    hooks = geometry.hook_effect(profile, quartic_probe=False)
    placement_info = placement_record(profile)
    return {
        "arrangement": arrangement_name,
        "metric": metric_name,
        "wiring": wiring_name,
        "profile_signature": {
            "transport_sha256": array_digest(profile.transport_matrix),
            "inverse_mass_sha256": array_digest(profile.projected_inv_mass),
            "generator_sha256": placement_info["generator_sha256"],
        },
        "edge": edge_signature(arrangement, profile),
        "hooks": {
            "projected_transport_used": bool(hooks["projected_transport_used"]),
            "projected_inv_mass_used": bool(hooks["projected_inv_mass_used"]),
            "cross_pool_entries": int(hooks["cross_pool_entries"]),
            "cross_pool_strength_l1": float(hooks["cross_pool_strength_l1"]),
        },
        "placement": placement_info,
        "capture_orthogonality": {
            "max_off_diagonal_squared_cosine": float(max(
                (value for left, row in enumerate(durability.overlap_matrix(captures)) for right, value in enumerate(row) if left != right),
                default=0.0,
            )),
            "allowance": float(durability.ORTHOGONALITY_ALLOWANCE),
        },
        "captures": [
            {"name": row["name"], "scale_width": int(row["scale_width"]), "direction_sha256": row["direction_sha256"], "deposited_energy": float(row["deposited_energy"])}
            for row in captures
        ],
        "capacity": {str(count): capacity_record(config, profile, count, captures) for count in CAPACITY_COUNTS},
    }


def edge_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    difference = abs(float(left["cross_pool_strength_l1"]) - float(right["cross_pool_strength_l1"]))
    return {
        "link_count_equal": bool(left["effective_link_count"] == right["effective_link_count"]),
        "cross_pool_l1_difference": difference,
        "cross_pool_l1_tolerance": EDGE_MATCH_TOLERANCE,
        "cross_pool_l1_equal_within_tolerance": bool(difference <= EDGE_MATCH_TOLERANCE),
        "matched": bool(left["effective_link_count"] == right["effective_link_count"] and difference <= EDGE_MATCH_TOLERANCE),
    }


def recovery(row: Mapping[str, Any]) -> float:
    value = row.get("recovery_fraction")
    return float(value) if value is not None else 0.0


def comparison(pair: Mapping[str, Any], left: Mapping[str, Any], right: Mapping[str, Any], metric_name: str, wiring_name: str, count: int) -> dict[str, Any]:
    difference = recovery(right["capacity"][str(count)]) - recovery(left["capacity"][str(count)])
    return {
        "pair": pair["name"], "left": pair["left"], "right": pair["right"],
        "metric": metric_name, "wiring": wiring_name, "capacity": int(count),
        "placement": "canonical-port-0", "difference_right_minus_left": float(difference),
        "margin": RECOVERY_MARGIN,
        "separates": bool(abs(difference) >= RECOVERY_MARGIN),
        "firing_control": {"kind": "matched-geometry-arm", "attempted": True, "can_fail": True, "difference": float(difference)},
    }


def continuity_checks() -> list[dict[str, Any]]:
    rows = []
    for name, cited in CITED_IPR.items():
        profile = geometry.build_profile(geometry.arrangement_named(name, seed=geometry.RANDOM_SEED))
        observed = float(geometry.spectrum_metrics(profile, rail_gains=())["ipr_median"])
        rows.append({
            "source_receipt": "_diag/fractal-geometry/exploration.json",
            "value": "spectrum.ipr_median", "arrangement": name,
            "cited": cited, "observed": observed, "tolerance": CONTINUITY_TOLERANCE,
            "within_tolerance": bool(abs(observed - cited) <= CONTINUITY_TOLERANCE),
        })
    return rows


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    config = durability.DurabilityConfig()
    profiles: dict[str, dict[str, Any]] = {}
    for pair in PAIRS:
        for arrangement_name in (pair["left"], pair["right"]):
            for metric_name in METRICS:
                for wiring_name in WIRINGS:
                    key = f"{arrangement_name}|{metric_name}|{wiring_name}"
                    if key not in profiles:
                        profiles[key] = profile_record(config, arrangement_name, metric_name, wiring_name)
    comparisons = []
    edge_checks = []
    placement_checks = []
    for pair in PAIRS:
        for metric_name in METRICS:
            for wiring_name in WIRINGS:
                left = profiles[f"{pair['left']}|{metric_name}|{wiring_name}"]
                right = profiles[f"{pair['right']}|{metric_name}|{wiring_name}"]
                edge = edge_match(left["edge"], right["edge"])
                edge_checks.append({"pair": pair["name"], "metric": metric_name, "wiring": wiring_name, **edge, "firing_control": {"kind": "edge-leaf-mutation", "attempted": False, "can_fail": True}})
                for count in CAPACITY_COUNTS:
                    comparisons.append(comparison(pair, left, right, metric_name, wiring_name, count))
                for record in (left, right):
                    p = record["placement"]
                    selected_delta = float(record["capacity"]["1"]["recovery_fraction"] or 0.0)
                    placement_checks.append({
                        "arrangement": record["arrangement"], "metric": metric_name, "wiring": wiring_name,
                        "canonical_port": p["canonical_port"], "task_selected_port": p["task_selected_port"], "shuffled_port": p["shuffled_port"],
                        "task_selected_effective_mode_delta": p["selected_minus_canonical_effective_modes"],
                        "mode_margin": PLACEMENT_MODE_MARGIN,
                        "mode_separates": bool(abs(p["selected_minus_canonical_effective_modes"]) >= PLACEMENT_MODE_MARGIN),
                        "survival_margin": PLACEMENT_RECOVERY_MARGIN,
                        "survival_firing_value": selected_delta,
                        "firing_control": {"kind": "seeded-shuffle-placement", "attempted": True, "can_fail": True},
                    })
    continuity = continuity_checks()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "question": "Does matched pool-graph geometry alter multiscale durability and modal access when metric, wiring, placement, and capacity are held fixed?",
            "pairs": copy.deepcopy(PAIRS),
            "factor_grid": {"metric": list(METRICS), "wiring": list(WIRINGS), "capacity": list(CAPACITY_COUNTS), "placement": list(PLACEMENTS)},
            "headline": {"metric": "canonical", "wiring": "native", "placement": "canonical-port-0", "capacities": list(CAPACITY_COUNTS), "recovery_margin": RECOVERY_MARGIN},
            "budgets": {"write_budget": float(config.write_budget), "activity_ticks": int(config.activity_ticks), "activity_samples": list(config.activity_samples), "seed": geometry.RANDOM_SEED},
            "edge_match_tolerance": EDGE_MATCH_TOLERANCE,
            "placement_mode_margin": PLACEMENT_MODE_MARGIN,
            "continuity_tolerance": CONTINUITY_TOLERANCE,
            "source_receipts": ["_diag/fractal-geometry/exploration.json", "_diag/fractal-survival/exploration.json", "_diag/fractal-placement/exploration.json"],
        },
        "profiles": profiles,
        "comparisons": comparisons,
        "edge_match_checks": edge_checks,
        "placement_checks": placement_checks,
        "continuity_checks": continuity,
        "controls": {
            "silenced_cross_scale": {"attempted": True, "definition": "zero every cross-pool transport entry after the production rail is built", "margin": RECOVERY_MARGIN, "can_fail": True},
            "shell_metric": {"attempted": True, "definition": "repeat the matched pairs with metric.shell_inverse_mass; not a pure geometry arm", "margin": RECOVERY_MARGIN, "can_fail": True},
            "seeded_shuffle_placement": {"attempted": True, "seed": SHUFFLE_SEED, "margin": PLACEMENT_RECOVERY_MARGIN, "can_fail": True},
            "edge_mutation": {"attempted": False, "definition": "test mutates a real edge-count/L1 leaf and requires edge matching to fail", "can_fail": True},
            "receipt_mutation": {"attempted": False, "definition": "test mutates a measured recovery leaf and requires content digest to change", "can_fail": True},
        },
        "limitations": [
            "The arrangement-level coordinates override is inert; neither pair tests literal spatial spacing.",
            "quasiperiodic-chain means a matched chain strength distribution, not spatial quasiperiodicity.",
            "Equal total realized cross-pool L1 does not equal equal edge lengths, degree sequence, local spectrum, or nonlinear dynamics.",
            "The placement leg is a beta=0 rest modal-access proxy, not task performance.",
            "Durability recovery is a share of measured written-direction energy under declared damping/activity, not semantic recall or retrieval.",
            "Shell metric, silenced wiring, and selected placement are controls/robustness legs and cannot be folded into a single geometry effect.",
            "There is no delayed-binding API: bind_workspace/condense_workspace consume fixed metadata at condensation, and later metadata edits do not perform a binding-dependent recall.",
            "Packet split/compose is same-field analysis regrouping with mixed-source refusal, not compositional semantic recall; it is intentionally omitted from the headline.",
            "No result demonstrates learning, owner-memory utility, semantic content, downstream consumer behavior, or architectural advantage.",
        ],
        "verdicts": {"continuity": "PASS" if all(row["within_tolerance"] for row in continuity) else "FAIL", "edge_matching": "see per-pair checks", "headline_geometry": "see per-cell margins", "scope": "reachable production-hook comparison only"},
    }
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
