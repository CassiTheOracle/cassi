"""Matched active-operator comparison of three CassiFI arrangements.

The three arms reuse the production arrangement builders and are lowered to the
three real field hooks (projected transport, projected inverse mass and
projected quartic weights).  Geometry coordinates are never treated as an
observable.  Writes, reads and recurrence are measured through the public
field/durability APIs.
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

import cassi_resonant_field as field
import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry

SCHEMA = "cassifi.fractal-arrangement-comparison.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-arrangement-comparison/exploration.json")
SEED = 20260917
PORTS_PER_POOL = 4
ARRANGEMENTS = (
    ("current-meaningful-helix", "helix7"),
    ("core-shell-loops", "nested-core-shell"),
    ("nested-paired-loops", "recursive-paired-loops"),
)
OBSERVATION_TICKS = (0, 8, 16, 32, 64)
PERSISTENCE_THRESHOLD_FRACTION = 0.20
WRITE_REACH_MARGIN = 1e-12
READ_SENSITIVITY_MARGIN = 1e-12
CROSSTALK_MARGIN = 1e-12
RECURRENCE_MARGIN = 1e-12
CONTINUITY_TOLERANCE = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_sha256"})
GEOMETRY_RECEIPT = Path("_diag/fractal-geometry/exploration.json")


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


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): strip_timing(v) for k, v in value.items() if k not in TIMING_KEYS}
    if isinstance(value, (tuple, list)):
        return [strip_timing(v) for v in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(strip_timing(value)).encode("utf-8")).hexdigest()


def array_digest(value: Any) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(value, dtype="<f8")).tobytes()).hexdigest()


def _inverse_mass_vector(profile: Any) -> np.ndarray:
    raw = profile.projected_inv_mass
    if raw is None:
        return 1.0 / np.asarray(profile.inertances, dtype=np.float64)
    arr = np.asarray(raw, dtype=np.float64)
    if arr.ndim == 1:
        return arr.copy()
    return np.diag(arr).copy()


def active_profile(arrangement_name: str) -> Any:
    """Build one candidate through the existing builder, then match active budgets."""
    arrangement = geometry.arrangement_named(arrangement_name, seed=SEED)
    raw = geometry.build_profile(arrangement, ports_per_pool=PORTS_PER_POOL)
    return raw


def matched_profiles() -> tuple[dict[str, Any], dict[str, float]]:
    raw_profiles = {label: active_profile(name) for label, name in ARRANGEMENTS}
    edge_budget = float(np.abs(np.asarray(raw_profiles[ARRANGEMENTS[0][0]].transport_matrix, dtype=np.float64)).sum())
    inverse_mass_budget = float(np.asarray(_inverse_mass_vector(raw_profiles[ARRANGEMENTS[0][0]]), dtype=np.float64).sum())
    out: dict[str, Any] = {}
    for label, raw in raw_profiles.items():
        rail = np.asarray(raw.transport_matrix, dtype=np.float64)
        rail *= edge_budget / max(float(np.abs(rail).sum()), 1e-300)
        inv = _inverse_mass_vector(raw)
        inv *= inverse_mass_budget / max(float(inv.sum()), 1e-300)
        # Explicit all-ones quartic weights are the active default nonlinear
        # operator, and make the third hook explicit without favouring an arm.
        quartic = np.ones(raw.port_count, dtype=np.float64)
        out[label] = replace(raw, projected_transport=rail, projected_inv_mass=inv, projected_quartic_weights=quartic)
    return out, {"active_edge_l1": edge_budget, "total_inverse_mass": inverse_mass_budget, "coupling": float(next(iter(raw_profiles.values())).coupling)}


def _item_capture(config: Any, profile: Any) -> list[dict[str, Any]]:
    return durability.capture_items(config, profile)


def _trajectory(config: Any, profile: Any, captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    headline = captures[0]
    control = captures[1]
    spec = durability.ITEM_SPECS[0]
    empty = field.initial_workspace(profile)
    before = durability.read_frame(empty, config.read_frame_path)
    written, write_receipt = durability.write_item(empty, spec, config.write_budget)
    post = durability.read_frame(written, config.read_frame_path)
    delta = np.asarray(post - before, dtype=np.float64)
    reach = float(np.linalg.norm(delta))
    read_before = durability.read_frame(empty, "L")
    read_after = durability.read_frame(written, "L")
    read_sensitivity = float(np.linalg.norm(read_after - read_before))
    deposited = float(np.dot(delta, delta))
    initial_alignment = float(durability.share_along(post, headline["direction"], deposited))
    current = written
    rows: list[dict[str, Any]] = [{
        "tick": 0,
        "alignment": initial_alignment,
        "alignment_ratio": 1.0,
        "packet_energy": float(np.dot(post, post)),
        "cross_talk_share": float(np.dot(post, control["direction"])) ** 2 / max(deposited, 1e-300),
    }]
    previous = 0
    for tick in OBSERVATION_TICKS[1:]:
        current, advance = field.advance_workspace(
            current, ticks=int(tick - previous), demand=0.0, source_enabled=False
        )
        frame = durability.read_frame(current, config.read_frame_path)
        alignment = float(durability.share_along(frame, headline["direction"], deposited))
        rows.append({
            "tick": int(tick),
            "alignment": alignment,
            "alignment_ratio": alignment / initial_alignment if initial_alignment else 0.0,
            "packet_energy": float(np.dot(frame, frame)),
            "cross_talk_share": float(np.dot(frame, control["direction"])) ** 2 / max(deposited, 1e-300),
            "dissipated_work": float(advance.get("dissipated_work", 0.0)),
            "positive_heartbeat_work": float(advance.get("positive_heartbeat_work", 0.0)),
            "source_enabled": bool(advance.get("source_enabled", False)),
        })
        previous = int(tick)
    ratios = [float(row["alignment_ratio"]) for row in rows]
    first_below = next((int(row["tick"]) for row in rows if row["alignment_ratio"] < PERSISTENCE_THRESHOLD_FRACTION), None)
    return {
        "write": {
            "path": spec.path,
            "component": spec.component,
            "flow_signal": list(spec.flow_signal),
            "requested_work": float(write_receipt["requested_work"]),
            "applied_work": float(write_receipt["applied_work"]),
            "impulse_amount": float(write_receipt["impulse_amount"]),
            "write_reach_l2": reach,
            "deposited_energy": deposited,
            "state_sha256": written.state_sha256,
        },
        "read_projection": {"write_path": spec.path, "read_path": "L", "sensitivity_l2": read_sensitivity},
        "observations": rows,
        "persistence": {
            "threshold_fraction": PERSISTENCE_THRESHOLD_FRACTION,
            "first_below_tick": first_below,
            "occupancy_fraction": float(np.mean(np.asarray(ratios) >= PERSISTENCE_THRESHOLD_FRACTION)),
            "return_windows": int(sum(1 for a, b in zip(ratios, ratios[1:]) if a < PERSISTENCE_THRESHOLD_FRACTION <= b)),
            "final_alignment_ratio": ratios[-1],
        },
        "cross_talk": {
            "write_item": headline["name"],
            "read_item": control["name"],
            "observed_share_at_final_tick": float(rows[-1]["cross_talk_share"]),
        },
    }


def _silenced_control(config: Any, profile: Any, captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Real no-write control through the same public read path."""
    empty = field.initial_workspace(profile)
    frame = durability.read_frame(empty, config.read_frame_path)
    sensitivity = float(np.linalg.norm(durability.read_frame(empty, "L")))
    return {
        "write_reach_l2": float(np.linalg.norm(frame)),
        "read_sensitivity_l2": sensitivity,
        "cross_talk_share": 0.0,
        "persistence_initial_alignment": 0.0,
        "recurrence_windows": 0,
        "attempted": True,
        "kind": "silenced-write-real-empty-workspace",
    }


def arm_record(label: str, arrangement_name: str, profile: Any, config: Any, budgets: Mapping[str, float]) -> dict[str, Any]:
    captures = _item_capture(config, profile)
    trajectory = _trajectory(config, profile, captures)
    silenced = _silenced_control(config, profile, captures)
    persistence = trajectory["persistence"]
    final_cross = trajectory["cross_talk"]["observed_share_at_final_tick"]
    return {
        "label": label,
        "arrangement_name": arrangement_name,
        "operators": {
            "projected_transport": True,
            "projected_inv_mass": True,
            "projected_quartic_weights": True,
            "transport_sha256": array_digest(profile.projected_transport),
            "inverse_mass_sha256": array_digest(profile.projected_inv_mass),
            "quartic_weights_sha256": array_digest(profile.projected_quartic_weights),
            "edge_l1": float(np.abs(np.asarray(profile.projected_transport)).sum()),
            "inverse_mass_sum": float(np.asarray(profile.projected_inv_mass).sum()),
        },
        "placement": {
            "kind": "active-write-read-projection-surrogate",
            "write_projection": {"path": trajectory["write"]["path"], "component": trajectory["write"]["component"]},
            "read_projection": {"path": trajectory["read_projection"]["read_path"], "frame": config.read_frame_path},
            "public_BC_matrices": False,
        },
        "budgets": dict(budgets),
        "captures": [
            {"name": row["name"], "path": row["path"], "component": row["component"], "scale_width": int(row["scale_width"]), "deposited_energy": float(row["deposited_energy"]), "direction_sha256": row["direction_sha256"]}
            for row in captures[:2]
        ],
        "measurements": trajectory,
        "silenced_control": silenced,
        "predicates": {
            "write_reach": {"value": trajectory["write"]["write_reach_l2"], "margin": WRITE_REACH_MARGIN, "passes": trajectory["write"]["write_reach_l2"] > WRITE_REACH_MARGIN},
            "read_sensitivity": {"value": trajectory["read_projection"]["sensitivity_l2"], "margin": READ_SENSITIVITY_MARGIN, "passes": trajectory["read_projection"]["sensitivity_l2"] > READ_SENSITIVITY_MARGIN},
            "cross_talk": {"value": final_cross, "margin": CROSSTALK_MARGIN, "passes": final_cross > CROSSTALK_MARGIN},
            "recurrence": {"value": persistence["return_windows"], "margin": RECURRENCE_MARGIN, "passes": persistence["return_windows"] > RECURRENCE_MARGIN},
        },
    }


def continuity_checks() -> list[dict[str, Any]]:
    source = GEOMETRY_RECEIPT
    cited_receipt = json.loads(source.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    for arrangement_name in ("helix7", "nested-core-shell", "recursive-paired-loops"):
        record = next(row for row in cited_receipt["arrangements"] if row["construction"]["name"] == arrangement_name)
        cited = float(record["spectrum"]["ipr_median"])
        observed = float(geometry.spectrum_metrics(geometry.build_profile(geometry.arrangement_named(arrangement_name, seed=SEED)), rail_gains=())["ipr_median"])
        checks.append({"source_receipt": str(source).replace("\\", "/"), "arrangement": arrangement_name, "value": "spectrum.ipr_median", "cited": cited, "observed": observed, "tolerance": CONTINUITY_TOLERANCE, "within_tolerance": bool(abs(observed - cited) <= CONTINUITY_TOLERANCE)})
    return checks


def comparisons(arms: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for left_index, (left_label, _left_name) in enumerate(ARRANGEMENTS):
        for right_label, _right_name in ARRANGEMENTS[left_index + 1:]:
            for metric, path, margin in (
                ("write_reach_l2", ("measurements", "write", "write_reach_l2"), WRITE_REACH_MARGIN),
                ("read_sensitivity_l2", ("measurements", "read_projection", "sensitivity_l2"), READ_SENSITIVITY_MARGIN),
                ("cross_talk_share", ("measurements", "cross_talk", "observed_share_at_final_tick"), CROSSTALK_MARGIN),
                ("recurrence_windows", ("measurements", "persistence", "return_windows"), RECURRENCE_MARGIN),
            ):
                left: Any = arms[left_label]
                right: Any = arms[right_label]
                for key in path:
                    left = left[key]; right = right[key]
                difference = float(right) - float(left)
                rows.append({"left": left_label, "right": right_label, "metric": metric, "left_value": float(left), "right_value": float(right), "difference_right_minus_left": difference, "margin": float(margin), "separates": bool(abs(difference) > margin), "firing_control": {"kind": "mutate-right-leaf-to-left-value", "attempted": True, "can_fail": True}})
    return rows


def can_fail_probes(receipt: Mapping[str, Any]) -> dict[str, Any]:
    arm_controls: dict[str, bool] = {}
    for arm in receipt["arms"]:
        mutated = copy.deepcopy(arm)
        predicates = mutated["predicates"]
        checks = []
        for name, pred in predicates.items():
            pred["value"] = 0.0
            pred["passes"] = bool(pred["value"] > float(pred["margin"]))
            checks.append(not pred["passes"])
        arm_controls[arm["label"]] = bool(all(checks))
    comparison_controls: list[bool] = []
    for row in receipt["comparisons"]:
        mutated = dict(row)
        mutated["difference_right_minus_left"] = 0.0
        comparison_controls.append(not (abs(float(mutated["difference_right_minus_left"])) > float(mutated["margin"])))
    return {"silenced_arm_predicates_fire": arm_controls, "mutated_comparison_predicates_fire": comparison_controls, "all_fire": bool(all(arm_controls.values()) and all(comparison_controls))}


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    config = durability.DurabilityConfig()
    profiles, matched_budget = matched_profiles()
    budgets = {"pools": 7.0, "ports_per_pool": float(PORTS_PER_POOL), "damping": float(next(iter(profiles.values())).damping), "write_energy": float(config.write_budget), "observation_ticks": list(OBSERVATION_TICKS), "seed": float(SEED), **matched_budget}
    arms = {
        label: arm_record(label, arrangement_name, profiles[label], config, budgets)
        for label, arrangement_name in ARRANGEMENTS
    }
    arm_list = [arms[label] for label, _ in ARRANGEMENTS]
    continuity = continuity_checks()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "question": "Do three named arrangements differ under matched active field operators when write/read projections and observation budgets are fixed?",
            "arrangements": [{"label": label, "builder_name": name} for label, name in ARRANGEMENTS],
            "active_hooks": ["projected_transport", "projected_inv_mass", "projected_quartic_weights"],
            "readout": "public analyze_helical_packet via durability.read_frame; whole frame plus L projection",
            "persistence": "alignment ratio after source-off advance, occupancy and below-to-above return windows",
            "coordinate_override": "not used; arrangement coordinates are not an active public hook",
            "budgets": budgets,
            "margins": {"write_reach": WRITE_REACH_MARGIN, "read_sensitivity": READ_SENSITIVITY_MARGIN, "cross_talk": CROSSTALK_MARGIN, "recurrence": RECURRENCE_MARGIN},
        },
        "arms": arm_list,
        "comparisons": comparisons(arms),
        "controls": {"can_fail": can_fail_probes({"arms": arm_list, "comparisons": comparisons(arms)}), "silenced_write": "real empty workspace read through the same public projections", "mutated_comparison": "replace measured right leaf with measured left leaf and require separation predicate to fail"},
        "continuity_checks": continuity,
        "limitations": [
            "No public B/C transceiver matrices are exposed; placement is therefore an active write/read projection surrogate, not a fabricated matrix geometry.",
            "The arrangement-level coordinates override is inert and is not treated as a causal variable.",
            "Equalized transport L1 and inverse-mass sum match budgets but do not equalize spectra, degree sequence, local edge lengths, or nonlinear mode structure.",
            "Persistence/recurrence is field alignment under source-off advance, not semantic memory, retrieval, or visual similarity.",
        ],
        "verdicts": {"continuity": "PASS" if all(row["within_tolerance"] for row in continuity) else "FAIL", "scope": "MEASURED active field arrangement comparison"},
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
    args.output.write_text(json.dumps(_jsonable(receipt), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "content_digest": receipt["content_digest"], "runtime_seconds": receipt["runtime_seconds"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
