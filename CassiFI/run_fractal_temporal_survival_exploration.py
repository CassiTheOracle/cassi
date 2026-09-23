"""Measure temporal survival of a localized LL write on one live field page.

The probe writes one LL packet mode, advances with the canonical source disabled,
and reads both the LL child coefficients and the L level-zero parent summary at a
fixed schedule.  A fourth arm applies one signed, bounded LL impulse at the
correction tick.  The correction is a second live-field write, not packet
restoration or semantic memory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np

import cassi_resonant_field as field
import run_fractal_geometry_exploration as geometry
import run_fractal_localized_projection_exploration as localized
import run_fractal_memory_exploration as memory

SCHEMA = "cassifi.fractal-temporal-survival-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-temporal-survival/exploration.json")
LOCALIZED_RECEIPT = Path("_diag/fractal-localized-projection/exploration.json")
SEED = 20260917
PARENT_PATH = "L"
FINE_PATH = "LL"
SIBLING_PATH = "LR"
FLOW_SIGNAL = (1.0, 0.0)
CORRECTION_FLOW_SIGNAL = (-1.0, 0.0)
DRIVE_BUDGET = 1e-3
CORRECTION_BUDGET = 5e-4
SAMPLE_TICKS = (0, 1, 2, 4, 8, 16, 32, 64)
CORRECTION_TICK = 8
ALIGNMENT_THRESHOLD_FRACTION = 0.05
FINE_REACH_MARGIN = 1e-12
PROJECTION_SEPARATION_MARGIN = 1e-8
TEMPORAL_CHILD_OCCUPANCY_MARGIN = 0.05
TEMPORAL_PARENT_OCCUPANCY_MARGIN = 0.05
CORRECTION_CHILD_DELTA_MARGIN = 1e-12
CORRECTION_ACCEPTANCE_MARGIN = 1.0
SOURCE_OFF_MARGIN = 1.0
CONTINUITY_TOLERANCE = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_sha256"})

BOUNDARY = (
    "Canonical-field numerical measurements only. A packet is a disposable view "
    "of one live field page; parent summaries are recomputed projections and the "
    "child correction is a second live-field impulse. No persistent parent/child "
    "state, semantic hierarchy, semantic recall, consumer retrieval, task utility, "
    "or architectural advantage is claimed."
)
LIMITATIONS = [
    "Source-off survival measures residue in one fixed canonical field page, not a stored memory item.",
    "analyze_helical_packet returns a disposable localized view; split_helical_packet and compose_helical_packets do not write or restore live state.",
    "The L level-zero value is a Haar block-average projection of the live LL/LR support, not a persistent parent summary.",
    "The child-only correction is supported only as a second apply_helical_packet_impulse(path='LL') call with a signed flow signal; no public packet writeback API exists.",
    "All comparisons are field observables. Temporal decay or retention does not establish semantic memory, recall, or hierarchy.",
]


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_timing(item)
            for key, item in value.items()
            if key not in TIMING_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_strip_timing(item) for item in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(_strip_timing(value)).encode("utf-8")).hexdigest()


def page_sha256(workspace: Any) -> str:
    return hashlib.sha256(workspace.page_bytes).hexdigest()


def _profile() -> field.ResonantProfile:
    # Reuse the canonical geometry builder; localized remains the continuity builder.
    return geometry.build_profile(
        geometry.arrangement_named("helix7", seed=SEED),
        ports_per_pool=localized.PORTS_PER_POOL,
    )


def _zero_advance() -> dict[str, Any]:
    return {
        "source_enabled": False,
        "positive_heartbeat_work": 0.0,
        "dissipated_work": 0.0,
        "residual_work": 0.0,
        "balance_defect": 0.0,
        "maximum_residual_norm": 0.0,
        "nonlinear_iterations": 0,
        "operator_applications": 0,
    }


def _packet_values(workspace: Any) -> tuple[np.ndarray, np.ndarray]:
    parent = field.analyze_helical_packet(workspace, path=PARENT_PATH)
    child = field.analyze_helical_packet(workspace, path=FINE_PATH)
    parent_zero = np.asarray(parent["coefficients"], dtype=np.float64)[0].copy()
    child_coefficients = np.asarray(child["coefficients"], dtype=np.float64).reshape(-1).copy()
    return child_coefficients, parent_zero


def _capture(workspace: Any, tick: int, phase: str, advance: Mapping[str, Any]) -> dict[str, Any]:
    child, parent = _packet_values(workspace)
    return {
        "tick": int(tick),
        "phase": phase,
        "field_ticks": int(workspace.field_ticks),
        "source_enabled": bool(advance["source_enabled"]),
        "positive_heartbeat_work": float(advance["positive_heartbeat_work"]),
        "dissipated_work": float(advance["dissipated_work"]),
        "residual_work": float(advance["residual_work"]),
        "balance_defect": float(advance["balance_defect"]),
        "maximum_residual_norm": float(advance["maximum_residual_norm"]),
        "nonlinear_iterations": int(advance["nonlinear_iterations"]),
        "operator_applications": int(advance["operator_applications"]),
        "state_sha256": workspace.state_sha256,
        "page_sha256": page_sha256(workspace),
        "child_coefficients": child.tolist(),
        "parent_level_zero_projection": parent.tolist(),
        "child_norm": float(np.linalg.norm(child)),
        "parent_summary_norm": float(np.linalg.norm(parent)),
        "finite": bool(np.isfinite(child).all() and np.isfinite(parent).all()),
    }


def _impulse_record(impulse: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: impulse[key]
        for key in (
            "schema", "accepted", "event_kind", "basis_sha256", "path", "component",
            "support", "mode", "flow_signal", "requested_work", "applied_work",
            "impulse_amount", "balance_defect", "energy_roundoff_allowance",
            "source_state_sha256", "state_sha256",
        )
    }


def _apply_impulse(
    workspace: Any,
    *,
    path: str,
    signal: Sequence[float],
    budget: float,
) -> tuple[Any, dict[str, Any]]:
    return field.apply_helical_packet_impulse(
        workspace,
        path=path,
        component="scale",
        flow_signal=signal,
        work_budget=budget,
        evidence_tick=workspace.evidence_tick,
        event_kind=memory.EVENT_KIND,
    )


def _run_arm(profile: field.ResonantProfile, name: str, write_path: str | None, correction: bool = False) -> dict[str, Any]:
    workspace = field.initial_workspace(profile)
    write_impulse = None
    if write_path is not None:
        workspace, write_impulse = _apply_impulse(
            workspace, path=write_path, signal=FLOW_SIGNAL, budget=DRIVE_BUDGET
        )
    samples: list[dict[str, Any]] = []
    previous = 0
    correction_impulse = None
    correction_pre = None
    correction_post = None
    for tick in SAMPLE_TICKS:
        tick = int(tick)
        if tick < previous:
            raise RuntimeError("sample ticks must be ordered")
        if tick == previous:
            advance = _zero_advance()
        else:
            workspace, advance = field.advance_workspace(
                workspace, ticks=tick - previous, demand=0.0, source_enabled=False
            )
        previous = tick
        if correction and tick == CORRECTION_TICK:
            correction_pre = _capture(workspace, tick, "pre-correction", advance)
            workspace, correction_impulse = _apply_impulse(
                workspace,
                path=FINE_PATH,
                signal=CORRECTION_FLOW_SIGNAL,
                budget=CORRECTION_BUDGET,
            )
            correction_post = _capture(workspace, tick, "post-correction", _zero_advance())
            samples.append(correction_post)
        else:
            samples.append(_capture(workspace, tick, "post-advance", advance))
    return {
        "arm": name,
        "write_path": write_path,
        "correction": bool(correction),
        "component": "scale" if write_path is not None else None,
        "flow_signal": list(FLOW_SIGNAL) if write_path is not None else None,
        "requested_work": 0.0 if write_impulse is None else float(write_impulse["requested_work"]),
        "applied_work": 0.0 if write_impulse is None else float(write_impulse["applied_work"]),
        "write_impulse": None if write_impulse is None else _impulse_record(write_impulse),
        "correction_impulse": None if correction_impulse is None else _impulse_record(correction_impulse),
        "correction_pre": correction_pre,
        "correction_post": correction_post,
        "samples": samples,
        "state_sha256": workspace.state_sha256,
        "page_sha256": page_sha256(workspace),
    }


def _post_sample_map(arm: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {int(row["tick"]): row for row in arm["samples"] if row["phase"] == "post-advance" or row["phase"] == "post-correction"}


def _vector(row: Mapping[str, Any], key: str) -> np.ndarray:
    return np.asarray(row[key], dtype=np.float64)


def _trajectory(arm: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    values = _post_sample_map(arm)
    base_values = _post_sample_map(baseline)
    initial = values[0]
    base_initial = base_values[0]
    child_delta0 = _vector(initial, "child_coefficients") - _vector(base_initial, "child_coefficients")
    parent_delta0 = _vector(initial, "parent_level_zero_projection") - _vector(base_initial, "parent_level_zero_projection")
    child_denominator = float(child_delta0 @ child_delta0)
    parent_denominator = float(parent_delta0 @ parent_delta0)
    rows: list[dict[str, Any]] = []
    for tick in SAMPLE_TICKS:
        tick = int(tick)
        row = values[tick]
        base = base_values[tick]
        child_delta = _vector(row, "child_coefficients") - _vector(base, "child_coefficients")
        parent_delta = _vector(row, "parent_level_zero_projection") - _vector(base, "parent_level_zero_projection")
        child_alignment = float(child_delta @ child_delta0 / child_denominator) if child_denominator else 0.0
        parent_alignment = float(parent_delta @ parent_delta0 / parent_denominator) if parent_denominator else 0.0
        rows.append({
            "tick": tick,
            "phase": row["phase"],
            "child_delta_norm": float(np.linalg.norm(child_delta)),
            "parent_delta_norm": float(np.linalg.norm(parent_delta)),
            "child_alignment": child_alignment,
            "parent_alignment": parent_alignment,
            "child_above_threshold": bool(abs(child_alignment) >= ALIGNMENT_THRESHOLD_FRACTION),
            "parent_above_threshold": bool(abs(parent_alignment) >= ALIGNMENT_THRESHOLD_FRACTION),
        })
    child_above = [row["child_above_threshold"] for row in rows]
    parent_above = [row["parent_above_threshold"] for row in rows]
    child_crossing = next((row["tick"] for row in rows if not row["child_above_threshold"]), None)
    parent_crossing = next((row["tick"] for row in rows if not row["parent_above_threshold"]), None)
    return {
        "initial_child_delta_norm": float(np.linalg.norm(child_delta0)),
        "initial_parent_delta_norm": float(np.linalg.norm(parent_delta0)),
        "alignment_threshold_fraction": ALIGNMENT_THRESHOLD_FRACTION,
        "samples": rows,
        "child_first_crossing_tick": child_crossing,
        "parent_first_crossing_tick": parent_crossing,
        "child_occupancy_fraction": float(sum(child_above) / len(child_above)),
        "parent_occupancy_fraction": float(sum(parent_above) / len(parent_above)),
        "child_return_window_count": int(sum(child_above[index] and not child_above[index - 1] for index in range(1, len(child_above)))),
        "parent_return_window_count": int(sum(parent_above[index] and not parent_above[index - 1] for index in range(1, len(parent_above)))),
    }


def _comparison(
    identifier: str,
    quantity: float,
    quantity_name: str,
    predicate: str,
    margin: float,
    holds: bool,
    mutation: str,
    mutated_quantity: float,
    holds_after: bool,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "quantity": float(quantity),
        "quantity_name": quantity_name,
        "predicate": predicate,
        "margin": float(margin),
        "holds": bool(holds),
        "firing_control": {
            "attempted": True,
            "mutation": mutation,
            "mutated_quantity": float(mutated_quantity),
            "holds_after": bool(holds_after),
            "can_fail": bool(not holds_after),
        },
    }


def _comparisons(arms: Mapping[str, Mapping[str, Any]], trajectories: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    no_write = arms["no-write-source-off"]
    fine = arms["fine-LL-source-off"]
    sibling = arms["fine-LR-source-off"]
    fine_initial = _post_sample_map(fine)[0]
    no_initial = _post_sample_map(no_write)[0]
    sibling_initial = _post_sample_map(sibling)[0]
    child_reach = float(np.linalg.norm(_vector(fine_initial, "child_coefficients") - _vector(no_initial, "child_coefficients")))
    projection_separation = float(np.linalg.norm(_vector(fine_initial, "parent_level_zero_projection") - _vector(sibling_initial, "parent_level_zero_projection")))
    fine_trajectory = trajectories["fine-LL-source-off"]
    correction = arms["fine-LL-child-correction"]
    correction_pre = correction["correction_pre"]
    correction_post = correction["correction_post"]
    correction_child_delta = float(np.linalg.norm(_vector(correction_post, "child_coefficients") - _vector(correction_pre, "child_coefficients")))
    correction_accepted = 1.0 if correction["correction_impulse"]["accepted"] and correction["correction_impulse"]["path"] == FINE_PATH else 0.0
    source_off_rows = [row for arm in arms.values() for row in arm["samples"]]
    source_off_ok = 1.0 if all(not row["source_enabled"] and row["positive_heartbeat_work"] == 0.0 for row in source_off_rows) else 0.0
    return [
        _comparison("fine_child_reaches", child_reach, "||child(LL write)-child(no-write)||2", "quantity > margin", FINE_REACH_MARGIN, child_reach > FINE_REACH_MARGIN, "replace LL child delta with no-write delta", 0.0, 0.0 > FINE_REACH_MARGIN),
        _comparison("coarse_projection_separates_LL_from_LR", projection_separation, "||level0(L,LL)-level0(L,LR)||2", "quantity > margin", PROJECTION_SEPARATION_MARGIN, projection_separation > PROJECTION_SEPARATION_MARGIN, "replace LL parent summary with LR parent summary", 0.0, 0.0 > PROJECTION_SEPARATION_MARGIN),
        _comparison("child_temporal_survival", fine_trajectory["child_occupancy_fraction"], "fraction of LL samples above child alignment threshold", "quantity > margin", TEMPORAL_CHILD_OCCUPANCY_MARGIN, fine_trajectory["child_occupancy_fraction"] > TEMPORAL_CHILD_OCCUPANCY_MARGIN, "silence the initial LL write", 0.0, 0.0 > TEMPORAL_CHILD_OCCUPANCY_MARGIN),
        _comparison("parent_summary_temporal_survival", fine_trajectory["parent_occupancy_fraction"], "fraction of L summary samples above parent alignment threshold", "quantity > margin", TEMPORAL_PARENT_OCCUPANCY_MARGIN, fine_trajectory["parent_occupancy_fraction"] > TEMPORAL_PARENT_OCCUPANCY_MARGIN, "silence the initial LL write", 0.0, 0.0 > TEMPORAL_PARENT_OCCUPANCY_MARGIN),
        _comparison("child_only_correction_changes_child", correction_child_delta, "||child(post-correction)-child(pre-correction)||2", "quantity > margin", CORRECTION_CHILD_DELTA_MARGIN, correction_child_delta > CORRECTION_CHILD_DELTA_MARGIN, "replace post-correction child with pre-correction child", 0.0, 0.0 > CORRECTION_CHILD_DELTA_MARGIN),
        _comparison("child_correction_api_accepts_LL", correction_accepted, "accepted LL correction impulse", "quantity >= margin", CORRECTION_ACCEPTANCE_MARGIN, correction_accepted >= CORRECTION_ACCEPTANCE_MARGIN, "mutate correction accepted/path to false/non-LL", 0.0, 0.0 >= CORRECTION_ACCEPTANCE_MARGIN),
        _comparison("source_off_is_observed", source_off_ok, "all sampled advances report source off and zero heartbeat work", "quantity >= margin", SOURCE_OFF_MARGIN, source_off_ok >= SOURCE_OFF_MARGIN, "enable source or heartbeat in one sampled row", 0.0, 0.0 >= SOURCE_OFF_MARGIN),
    ]


def continuity_checks() -> list[dict[str, Any]]:
    root = Path(__file__).resolve().parent
    with (root / LOCALIZED_RECEIPT).open("r", encoding="utf-8") as stream:
        prior = json.load(stream)
    profile = _profile()
    no_write = localized._write_arm(profile, "no-write", None)
    fine = localized._write_arm(profile, "fine-LL", FINE_PATH)
    sibling = localized._write_arm(profile, "fine-LR", SIBLING_PATH)
    measured_child = float(np.linalg.norm(np.asarray(fine["views"]["fine_child"]["coefficients"], dtype=np.float64) - np.asarray(no_write["views"]["fine_child"]["coefficients"], dtype=np.float64)))
    measured_parent = float(np.linalg.norm(np.asarray(fine["views"]["parent_level_zero_projection"], dtype=np.float64) - np.asarray(sibling["views"]["parent_level_zero_projection"], dtype=np.float64)))
    expected_child = float(next(row["quantity"] for row in prior["comparisons"] if row["id"] == "fine_child_reaches"))
    expected_parent = float(next(row["quantity"] for row in prior["comparisons"] if row["id"] == "coarse_projection_separates_LL_from_LR"))
    return [
        {
            "source": str(LOCALIZED_RECEIPT),
            "selector": "comparisons[id=fine_child_reaches].quantity",
            "expected": expected_child,
            "measured": measured_child,
            "difference": measured_child - expected_child,
            "tolerance": CONTINUITY_TOLERANCE,
            "within_tolerance": abs(measured_child - expected_child) <= CONTINUITY_TOLERANCE,
        },
        {
            "source": str(LOCALIZED_RECEIPT),
            "selector": "comparisons[id=coarse_projection_separates_LL_from_LR].quantity",
            "expected": expected_parent,
            "measured": measured_parent,
            "difference": measured_parent - expected_parent,
            "tolerance": CONTINUITY_TOLERANCE,
            "within_tolerance": abs(measured_parent - expected_parent) <= CONTINUITY_TOLERANCE,
        },
    ]


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    profile = _profile()
    arms = {
        "no-write-source-off": _run_arm(profile, "no-write-source-off", None),
        "fine-LL-source-off": _run_arm(profile, "fine-LL-source-off", FINE_PATH),
        "fine-LR-source-off": _run_arm(profile, "fine-LR-source-off", SIBLING_PATH),
        "fine-LL-child-correction": _run_arm(profile, "fine-LL-child-correction", FINE_PATH, correction=True),
    }
    trajectories = {
        name: _trajectory(arm, arms["no-write-source-off"])
        for name, arm in arms.items()
        if name in {"fine-LL-source-off", "fine-LL-child-correction"}
    }
    comparisons = _comparisons(arms, trajectories)
    continuity = continuity_checks()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "question": "After a localized LL write with source off, how long do child coefficients and the recomputed L parent summary remain aligned, and can a second LL-only correction change the live child?",
            "probe_kind": "temporal localized packet survival and live-child correction probe",
            "seed": SEED,
            "semantic_recall_claim": False,
            "field_persistence_claim": False,
            "profile": profile.as_dict(),
            "packet_paths": {"parent": PARENT_PATH, "fine_child": FINE_PATH, "sibling_null": SIBLING_PATH},
            "schedule": {"sample_ticks": list(SAMPLE_TICKS), "correction_tick": CORRECTION_TICK, "source_enabled": False, "demand": 0.0},
            "drive": {"component": "scale", "flow_signal": list(FLOW_SIGNAL), "work_budget": DRIVE_BUDGET, "event_kind": memory.EVENT_KIND},
            "correction": {"path": FINE_PATH, "flow_signal": list(CORRECTION_FLOW_SIGNAL), "work_budget": CORRECTION_BUDGET, "supported_by": "apply_helical_packet_impulse"},
            "margins": {
                "fine_child_reach": FINE_REACH_MARGIN,
                "coarse_projection_separation": PROJECTION_SEPARATION_MARGIN,
                "temporal_child_occupancy": TEMPORAL_CHILD_OCCUPANCY_MARGIN,
                "temporal_parent_occupancy": TEMPORAL_PARENT_OCCUPANCY_MARGIN,
                "correction_child_delta": CORRECTION_CHILD_DELTA_MARGIN,
                "correction_acceptance": CORRECTION_ACCEPTANCE_MARGIN,
                "source_off": SOURCE_OFF_MARGIN,
                "alignment_threshold_fraction": ALIGNMENT_THRESHOLD_FRACTION,
                "continuity": CONTINUITY_TOLERANCE,
            },
            "api_surface": ["initial_workspace", "apply_helical_packet_impulse", "advance_workspace", "analyze_helical_packet"],
        },
        "arms": arms,
        "trajectories": trajectories,
        "comparisons": comparisons,
        "continuity": continuity,
        "continuity_verdict": "PASS" if all(row["within_tolerance"] for row in continuity) else "FAIL",
        "controls": {
            "firing": [{"comparison": row["id"], **row["firing_control"]} for row in comparisons],
            "all_attempted": all(row["firing_control"]["attempted"] for row in comparisons),
            "all_can_fail": all(row["firing_control"]["can_fail"] for row in comparisons),
            "all_flip": all(not row["firing_control"]["holds_after"] for row in comparisons),
        },
        "limitations": LIMITATIONS,
        "boundary": BOUNDARY,
        "verdict": (
            "MEASURED_FIELD_TEMPORAL_SURVIVAL_NO_PERSISTENT_PARENT_CHILD_MEMORY"
            if all(row["holds"] for row in comparisons[2:5])
            else "MEASURED_NO_FIELD_TEMPORAL_SURVIVAL_OR_PERSISTENT_PARENT_CHILD_MEMORY"
        ),
    }
    body["runtime_seconds"] = float(perf_counter() - started)
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    actual = content_digest(receipt)
    return {"content_digest_matches": actual == receipt.get("content_digest"), "digest": actual}


def can_fail_probes(receipt: Mapping[str, Any]) -> dict[str, Any]:
    rows = receipt.get("comparisons", [])
    controls = receipt.get("controls", {}).get("firing", [])
    return {
        "comparison_count": len(rows),
        "control_count": len(controls),
        "all_attempted": bool(controls) and all(row.get("attempted") for row in controls),
        "all_can_fail": bool(controls) and all(row.get("can_fail") for row in controls),
        "all_flip": bool(controls) and all(not row.get("holds_after") for row in controls),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_jsonable(receipt), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "content_digest": receipt["content_digest"], "runtime_seconds": receipt["runtime_seconds"], "verdict": receipt["verdict"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
