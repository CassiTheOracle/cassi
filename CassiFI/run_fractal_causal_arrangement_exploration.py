"""Fixed-graph causal arrangement study for the CassiFI resonant field.

This workstream deliberately does not sweep topology.  Leg A measures the
actual ``condense_input``/``advance_transceiver`` path after changing only the
physical ports bound to one logical input/output pair.  Leg B measures the
existing durability and source-off ladder surfaces after changing only the
supported inverse-mass and damping hooks.  There is no active cross-scale arm:
the production profile has no scale-indexed cross-scale API.

All figures are field-level numerical observables.  They are not semantic
recall, task utility, or consumer retrieval claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry
import run_fractal_ladder_exploration as ladder
from cassi_field_transceiver import advance_transceiver, condense_input, reset_transceiver
from cassi_resonant_field import ResonantProfile, initial_workspace

SCHEMA = "cassifi.fractal-causal-arrangement-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-causal-arrangement/exploration.json")
PORT_COUNT = 28
PORTS_PER_POOL = 4
INPUT_ID = "fg:drive-pool-0"
OUTPUT_ID = "fg:read-pool-0"
INPUT_SCAN = (0.0, 0.5, 1.75, 3.5)
RANK = 16
HORIZON_TICKS = 64
INPUT_BOUND = 4.0
COUPLING_ACTIVE = 0.5
AUTHORITY_ALLOWANCE = 1e-12
PLACEMENT_MARGIN_FACTOR = 0.05
INTERACTION_TOLERANCE = 0.01
WRITE_BUDGET = 0.001
ACTIVITY_TICKS = 64
ACTIVITY_SAMPLES = (8, 16, 32, 64)
SOURCE_OFF_HORIZON = 256
SOURCE_OFF_SAMPLE_EVERY = 16
SOURCE_OFF_THRESHOLD_FRACTION = 0.05
METRIC_MARGIN = 0.02
DAMPING_RECOVERY_MARGIN = 0.02
DAMPING_LIFETIME_MARGIN = 16
CONTINUITY_TOLERANCE = 1e-12
RANDOM_SEED = 20260915

# Existing receipt numbers are read, not re-derived from copied constants.  The
# values below are only the selectors' expected labels; the run reads the actual
# receipt and records what it found.
SURVIVAL_RECEIPT = Path("_diag/fractal-survival/exploration.json")
GEOMETRY_RECEIPT = Path("_diag/fractal-geometry/exploration.json")

LEG_A_ARMS = (
    ("T0-canonical-inert", 0, 1, 0.0),
    ("T1-canonical-active", 0, 1, COUPLING_ACTIVE),
    ("T2-controllability-candidate", 23, 1, COUPLING_ACTIVE),
    ("T3-observability-candidate", 0, 20, COUPLING_ACTIVE),
    ("T4-joint-candidate", 23, 20, COUPLING_ACTIVE),
)
LEG_B_METRICS = ("canonical", "mass-only")
LEG_B_DAMPINGS = (0.006, 0.012, 0.024)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def array_digest(value: Any) -> str | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=np.float64)
    return hashlib.sha256(arr.tobytes(order="C")).hexdigest()


def _strip_clock(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(k): _strip_clock(v)
            for k, v in value.items()
            if k not in {"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_sha256"}
        }
    if isinstance(value, list):
        return [_strip_clock(v) for v in value]
    return value


def content_digest(receipt: Mapping[str, Any]) -> str:
    return digest_obj(_strip_clock(receipt))


def _binding(port: int) -> dict[str, Any]:
    port = int(port)
    return {
        "pool": port // PORTS_PER_POOL,
        "port": port,
        "component": "common",
        "binding_id": f"fractal-causal-arrangement:{port}",
    }


def logical_bindings(input_port: int, output_port: int) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Return the two logical bindings and an explicit collision verdict."""
    ports = [int(input_port), int(output_port)]
    valid_range = all(0 <= p < PORT_COUNT for p in ports)
    unique = len(set(ports)) == len(ports)
    bindings = {INPUT_ID: _binding(ports[0]), OUTPUT_ID: _binding(ports[1])}
    result = {
        "physical_ports": ports,
        "port_count": PORT_COUNT,
        "in_range": bool(valid_range),
        "unique": bool(unique),
        "collision": bool(not unique),
        "collision_checked": True,
        "valid": bool(valid_range and unique),
    }
    if not result["valid"]:
        raise ValueError(f"invalid causal arrangement binding: {result}")
    return bindings, result


def _output_value(receipt: Mapping[str, Any]) -> float:
    values = receipt.get("values", {})
    return float(values.get(OUTPUT_ID, 0.0))


def _trajectory(kernel: Mapping[str, Any], *, pulse: float = 1.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    state = reset_transceiver(kernel)
    rows: list[dict[str, Any]] = []
    for tick in range(HORIZON_TICKS):
        value = float(pulse) if tick == 0 else 0.0
        state, receipt = advance_transceiver(
            kernel, state, inputs={INPUT_ID: value}, ticks=1, force_full=False
        )
        rows.append({
            "tick": int(tick + 1),
            "input": value,
            "output": _output_value(receipt),
            "mode": str(receipt["mode"]),
            "status": str(receipt["status"]),
            "resolved": bool(receipt["resolved"]),
            "error_bound": float(receipt["error_bound"]),
            "counts": dict(receipt["counts"]),
        })
    final_state = reset_transceiver(kernel)
    replay: list[float] = []
    for tick in range(HORIZON_TICKS):
        value = float(pulse) if tick == 0 else 0.0
        final_state, receipt = advance_transceiver(
            kernel, final_state, inputs={INPUT_ID: value}, ticks=1, force_full=False
        )
        replay.append(_output_value(receipt))
    primary = [float(row["output"]) for row in rows]
    identity = {
        "primary_digest": digest_obj(primary),
        "replay_digest": digest_obj(replay),
        "identical": bool(primary == replay),
        "reset_initial_digest": digest_obj(reset_transceiver(kernel)),
    }
    return rows, identity


def _authority(kernel: Mapping[str, Any]) -> dict[str, Any]:
    outputs: list[float] = []
    statuses: list[str] = []
    for value in INPUT_SCAN:
        state, receipt = advance_transceiver(
            kernel, reset_transceiver(kernel), inputs={INPUT_ID: float(value)}, ticks=1
        )
        del state
        outputs.append(_output_value(receipt))
        statuses.append(str(receipt["status"]))
    spread = float(max(outputs) - min(outputs)) if outputs else 0.0
    magnitude = float(max((abs(v) for v in outputs), default=0.0))
    relative = float(spread / magnitude) if magnitude else 0.0
    return {
        "input_scan": [float(v) for v in INPUT_SCAN],
        "outputs": outputs,
        "statuses": statuses,
        "spread": spread,
        "output_magnitude": magnitude,
        "relative_authority": relative,
        "allowance": AUTHORITY_ALLOWANCE,
    }


def _leg_a_arm(name: str, input_port: int, output_port: int, coupling: float) -> dict[str, Any]:
    profile = geometry.build_profile(geometry.arrangement_named("helix7"))
    profile = replace(profile, beta=0.0, projected_transport=None, projected_inv_mass=None)
    bindings, collision = logical_bindings(input_port, output_port)
    workspace = initial_workspace(profile)._copy(bindings=bindings)
    kernel, _working, condensation = condense_input(
        workspace,
        input_ids=(INPUT_ID,),
        output_ids=(OUTPUT_ID,),
        diagonal=1.0,
        coupling=float(coupling),
        rank=RANK,
        error_allowance=1e-3,
        input_bound=INPUT_BOUND,
        horizon_ticks=HORIZON_TICKS,
    )
    trajectory, identity = _trajectory(kernel)
    authority = _authority(kernel)
    modes = sorted({str(row["mode"]) for row in trajectory})
    return {
        "name": name,
        "physical_input_port": int(input_port),
        "physical_output_port": int(output_port),
        "logical_input_id": INPUT_ID,
        "logical_output_id": OUTPUT_ID,
        "coupling": float(coupling),
        "diagonal": 1.0,
        "envelope": INPUT_BOUND,
        "rank": RANK,
        "horizon_ticks": HORIZON_TICKS,
        "beta": float(profile.beta),
        "profile_contract": {
            "topology": str(profile.topology),
            "ports_per_pool": int(profile.ports_per_pool),
            "port_count": int(profile.port_count),
            "projected_transport_is_none": profile.projected_transport is None,
        },
        "binding_map": bindings,
        "binding_map_sha256": digest_obj(bindings),
        "collision": collision,
        "input_lift_sha256": array_digest(kernel.get("input_lift")),
        "output_rows_sha256": array_digest(kernel.get("output_rows")),
        "kernel_sha256": str(kernel.get("kernel_sha256", digest_obj(kernel))),
        "condensation": {
            "operation": condensation.get("operation"),
            "status": condensation.get("status"),
            "reason": condensation.get("reason"),
            "mode": condensation.get("mode"),
            "dimensions": condensation.get("dimensions"),
            "error_bound": float(condensation.get("error_bound", 0.0)),
            "resolved": bool(condensation.get("resolved", False)),
        },
        "trajectory": trajectory,
        "reset_replay_identity": identity,
        "modes_observed": modes,
        "reduced_observed": bool("reduced" in modes),
        "full_observed": bool("full" in modes),
        "authority": authority,
    }
def _seeded_shuffle_arm() -> tuple[str, int, int]:
    rng = np.random.default_rng(RANDOM_SEED)
    ports = rng.permutation(PORT_COUNT)
    return "T5-seeded-shuffle-active", int(ports[0]), int(ports[1])

def run_leg_a() -> dict[str, Any]:
    arms = list(LEG_A_ARMS)
    shuffle = _seeded_shuffle_arm()
    arms.append((shuffle[0], shuffle[1], shuffle[2], COUPLING_ACTIVE))
    measured = [_leg_a_arm(*arm) for arm in arms]
    by_name = {row["name"]: row for row in measured}
    t1 = by_name["T1-canonical-active"]
    t0 = by_name["T0-canonical-inert"]
    authority_control = {
        "t0_at_or_below_allowance": bool(t0["authority"]["spread"] <= AUTHORITY_ALLOWANCE),
        "t1_above_allowance": bool(t1["authority"]["spread"] > AUTHORITY_ALLOWANCE),
        "fires": bool(
            t0["authority"]["spread"] <= AUTHORITY_ALLOWANCE
            and t1["authority"]["spread"] > AUTHORITY_ALLOWANCE
        ),
        "margin": AUTHORITY_ALLOWANCE,
    }
    scores = {
        row["name"]: float(np.linalg.norm([float(v["output"]) for v in row["trajectory"]]))
        for row in measured
    }
    canonical_score = scores["T1-canonical-active"]
    controllability_delta = float(scores["T2-controllability-candidate"] - canonical_score)
    observability_delta = float(scores["T3-observability-candidate"] - canonical_score)
    joint_delta = float(scores["T4-joint-candidate"] - canonical_score)
    interaction = float(
        scores["T4-joint-candidate"]
        - scores["T2-controllability-candidate"]
        - scores["T3-observability-candidate"]
        + canonical_score
    )
    comparison_margin = float(PLACEMENT_MARGIN_FACTOR * abs(canonical_score))
    comparison = {
        "canonical_active_score": canonical_score,
        "scores": scores,
        "controllability_delta_vs_T1": controllability_delta,
        "observability_delta_vs_T1": observability_delta,
        "joint_delta_vs_T1": joint_delta,
        "margin": comparison_margin,
        "controllability_separates": bool(abs(controllability_delta) >= comparison_margin),
        "observability_separates": bool(abs(observability_delta) >= comparison_margin),
        "interaction_I": interaction,
        "interaction_tolerance": INTERACTION_TOLERANCE,
        "interaction_within_tolerance": bool(abs(interaction) <= INTERACTION_TOLERANCE),
        "interaction_interpretation_allowed": bool(abs(interaction) <= INTERACTION_TOLERANCE),
    }
    return {
        "question": "Does actual transceiver response change when physical input/output bindings move on one fixed graph?",
        "fixed_graph": {
            "arrangement": "helix7",
            "topology": "meaningful-helix",
            "port_count": PORT_COUNT,
            "ports_per_pool": PORTS_PER_POOL,
            "projected_transport": None,
            "topology_sweep": False,
        },
        "matched_budget": {
            "input_bound": INPUT_BOUND,
            "rank": RANK,
            "horizon_ticks": HORIZON_TICKS,
            "calls": HORIZON_TICKS,
            "pulse": "one unit input at tick 1, zero thereafter",
        },
        "arms": measured,
        "authority_control": authority_control,
        "comparison": comparison,
        "verdict": "PASS" if authority_control["fires"] else "FAIL/NULL",
    }


def _profile(metric: str, damping: float) -> ResonantProfile:
    base = geometry.build_profile(geometry.arrangement_named("helix7"))
    inv = None if metric == "canonical" else geometry.core_shell_inverse_mass(PORTS_PER_POOL)
    return replace(
        base,
        projected_transport=None,
        projected_inv_mass=inv,
        damping=float(damping),
        quiet_damping=16.0,
        beta=0.08,
    )


def _compact_arm(out: Mapping[str, Any], config: durability.DurabilityConfig) -> dict[str, Any]:
    readout = out["readout"]
    cross = dict(readout["cross_item_confusion"])
    off_diag = [
        float(value)
        for written, row in cross.items()
        for read, value in row.items()
        if read != written
    ]
    return {
        "recovery_fraction": readout["recovery_fraction"],
        "per_item_recovery_fraction": dict(readout["own_shares"]),
        "control_share": readout["control_share"],
        "max_off_diagonal_confusion": max(off_diag, default=0.0),
        "total_packet_energy_ratio": readout["total_packet_energy_ratio"],
        "frame_energy_ratio": readout["total_packet_energy_ratio"],
        "activity_dissipated_work": float(out["activity"]["dissipated_work_total"]),
        "activity_positive_heartbeat_work": float(out["activity"]["positive_heartbeat_work_total"]),
        "restart_state_digest_identical": out["restart"].get("state_digest_identical"),
        "restart_page_digest_identical": out["restart"].get("page_digest_identical"),
        "restart_applied": bool(out["restart"].get("applied", False)),
        "activity_ticks": int(config.activity_ticks),
    }


def run_leg_b() -> dict[str, Any]:
    config = durability.DurabilityConfig(
        write_budget=WRITE_BUDGET,
        activity_ticks=ACTIVITY_TICKS,
        activity_samples=ACTIVITY_SAMPLES,
        multi_item_counts=(2, 4, 8),
    )
    rows: list[dict[str, Any]] = []
    for metric in LEG_B_METRICS:
        for damping in LEG_B_DAMPINGS:
            name = f"M{'0' if metric == 'canonical' else '1'}D{damping:.3f}"
            profile = _profile(metric, damping)
            captures = durability.capture_items(config, profile)
            arm = durability.Arm("restart-and-activity-k4", (0, 1, 2, 3), True, True, True)
            control_arm = durability.Arm("no-item-restart-and-activity", (), True, True, True)
            out = durability.run_arm(config, profile, captures, arm)
            control = durability.run_arm(config, profile, captures, control_arm)
            compact = _compact_arm(out, config)
            control_compact = _compact_arm(control, config)
            item = ladder.measured_series_for_item(profile, 0, captures)
            per_item = compact["per_item_recovery_fraction"]
            minimum = float(min(float(v) for v in per_item.values())) if per_item else None
            rows.append({
                "name": name,
                "metric": metric,
                "damping": float(damping),
                "profile": {
                    "topology": str(profile.topology),
                    "port_count": int(profile.port_count),
                    "projected_transport_is_none": profile.projected_transport is None,
                    "projected_inv_mass_is_set": profile.projected_inv_mass is not None,
                    "beta": float(profile.beta),
                    "quiet_damping": float(profile.quiet_damping),
                    "damping": float(profile.damping),
                },
                "write_budget": WRITE_BUDGET,
                "activity_ticks": ACTIVITY_TICKS,
                "activity_samples": list(ACTIVITY_SAMPLES),
                "restart_replay": {
                    "applied": compact["restart_applied"],
                    "state_digest_identical": compact["restart_state_digest_identical"],
                    "page_digest_identical": compact["restart_page_digest_identical"],
                },
                "min_per_item_recovery": minimum,
                "per_item_recovery": per_item,
                "control_share": compact["control_share"],
                "max_off_diagonal_confusion": compact["max_off_diagonal_confusion"],
                "frame_energy_ratio": compact["frame_energy_ratio"],
                "dissipated_work": compact["activity_dissipated_work"],
                "positive_heartbeat_work": compact["activity_positive_heartbeat_work"],
                "no_item_control": {
                    "control_share": control_compact["control_share"],
                    "max_off_diagonal_confusion": control_compact["max_off_diagonal_confusion"],
                    "frame_energy_ratio": control_compact["frame_energy_ratio"],
                    "dissipated_work": control_compact["activity_dissipated_work"],
                },
                "source_off_ladder": {
                    "horizon_ticks": SOURCE_OFF_HORIZON,
                    "sample_every": SOURCE_OFF_SAMPLE_EVERY,
                    "threshold_fraction": SOURCE_OFF_THRESHOLD_FRACTION,
                    "first_crossing_ticks": item["first_crossing_ticks"],
                    "lifetime_ticks": item["lifetime_ticks"],
                    "occupancy": item["occupancy"],
                    "final_alignment": item["final_retention"],
                    "series": item["series"],
                },
            })
    by_name = {row["name"]: row for row in rows}
    mid_default = by_name["M0D0.012"]
    mid_mass = by_name["M1D0.012"]
    low_default = by_name["M0D0.006"]
    high_default = by_name["M0D0.024"]
    low_mass = by_name["M1D0.006"]
    high_mass = by_name["M1D0.024"]
    metric_delta = float(mid_mass["min_per_item_recovery"] - mid_default["min_per_item_recovery"])
    damping_recovery_delta = float(low_default["min_per_item_recovery"] - high_default["min_per_item_recovery"])
    damping_lifetime_delta = abs(float(low_default["source_off_ladder"]["lifetime_ticks"]) - float(high_default["source_off_ladder"]["lifetime_ticks"]))
    interaction = float(
        (high_mass["min_per_item_recovery"] - low_mass["min_per_item_recovery"])
        - (high_default["min_per_item_recovery"] - low_default["min_per_item_recovery"])
    )
    comparisons = {
        "metric_mid_difference": metric_delta,
        "metric_margin": METRIC_MARGIN,
        "metric_separates": bool(abs(metric_delta) >= METRIC_MARGIN),
        "damping_low_minus_high_recovery": damping_recovery_delta,
        "damping_recovery_margin": DAMPING_RECOVERY_MARGIN,
        "damping_recovery_separates": bool(abs(damping_recovery_delta) >= DAMPING_RECOVERY_MARGIN),
        "damping_low_high_lifetime_difference": damping_lifetime_delta,
        "damping_lifetime_margin": DAMPING_LIFETIME_MARGIN,
        "damping_lifetime_separates": bool(damping_lifetime_delta >= DAMPING_LIFETIME_MARGIN),
        "damping_separates": bool(abs(damping_recovery_delta) >= DAMPING_RECOVERY_MARGIN or damping_lifetime_delta >= DAMPING_LIFETIME_MARGIN),
        "interaction_residual": interaction,
        "interaction_tolerance": INTERACTION_TOLERANCE,
        "interaction_within_tolerance": bool(abs(interaction) <= INTERACTION_TOLERANCE),
        "interaction_interpretation_allowed": bool(abs(interaction) <= INTERACTION_TOLERANCE),
    }
    return {
        "question": "Do supported inverse-mass and damping hooks change fixed-graph survival and source-off lifetime?",
        "fixed_graph": {"arrangement": "helix7", "topology": "meaningful-helix", "port_count": PORT_COUNT, "projected_transport": None, "topology_sweep": False},
        "matched_budget": {"write_budget": WRITE_BUDGET, "activity_ticks": ACTIVITY_TICKS, "activity_samples": list(ACTIVITY_SAMPLES), "source_off_horizon": SOURCE_OFF_HORIZON, "source_off_sample_every": SOURCE_OFF_SAMPLE_EVERY, "quiet_damping": 16.0, "beta": 0.08},
        "arms": rows,
        "comparisons": comparisons,
        "verdict": "MEASURED",
    }
def _continuity(leg_b: Mapping[str, Any]) -> dict[str, Any]:
    with SURVIVAL_RECEIPT.open("r", encoding="utf-8") as stream:
        survival = json.load(stream)
    with GEOMETRY_RECEIPT.open("r", encoding="utf-8") as stream:
        geom = json.load(stream)
    expected_recovery = float(survival["scaffold"]["per_profile"]["helix7"]["restart-and-activity-k4"]["recovery_fraction"])
    geom_row = next(row for row in geom["arrangements"] if row["construction"]["name"] == "helix7")
    expected_retention = float(geom_row["retention"]["retention_mean"])
    measured_recovery = float(next(row for row in leg_b["arms"] if row["name"] == "M0D0.012")["min_per_item_recovery"])
    canonical_profile = geometry.build_profile(geometry.arrangement_named("helix7"))
    measured_retention = float(
        geometry.retention_metrics(
            canonical_profile,
            pools=geometry.DEFAULT_IMPULSE_POOLS,
            work=geometry.DEFAULT_IMPULSE_WORK,
            ticks=geometry.DEFAULT_RETENTION_TICKS,
        )["retention_mean"]
    )
    checks = [
        {
            "source": str(SURVIVAL_RECEIPT),
            "selector": "scaffold.per_profile.helix7.restart-and-activity-k4.recovery_fraction",
            "expected": expected_recovery,
            "measured": measured_recovery,
            "difference": float(measured_recovery - expected_recovery),
            "tolerance": CONTINUITY_TOLERANCE,
            "within_tolerance": bool(abs(measured_recovery - expected_recovery) <= CONTINUITY_TOLERANCE),
        },
        {
            "source": str(GEOMETRY_RECEIPT),
            "selector": "arrangements[construction.name=helix7].retention.retention_mean",
            "expected": expected_retention,
            "measured": measured_retention,
            "difference": float(measured_retention - expected_retention),
            "tolerance": CONTINUITY_TOLERANCE,
            "within_tolerance": bool(abs(measured_retention - expected_retention) <= CONTINUITY_TOLERANCE),
        },
    ]
    return {"checks": checks, "all_within_tolerance": all(row["within_tolerance"] for row in checks)}


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    leg_a = run_leg_a()
    leg_b = run_leg_b()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "fixed_graph": "helix7 / meaningful-helix / 28 ports / projected_transport=None",
            "topology_sweep": False,
            "semantic_recall_claim": False,
            "active_cross_scale": {"attempted": False, "verdict": "OUT_OF_SCOPE", "reason": "production has no scale-indexed cross-scale API"},
            "leg_a": {"actual_path": "cassi_field_transceiver.condense_input -> advance_transceiver", "not_modal_proxy": True},
            "leg_b": {"existing_builders": ["run_fractal_durability_exploration", "run_fractal_ladder_exploration"]},
            "margins": {"authority": AUTHORITY_ALLOWANCE, "placement_factor": PLACEMENT_MARGIN_FACTOR, "interaction": INTERACTION_TOLERANCE, "metric": METRIC_MARGIN, "damping_recovery": DAMPING_RECOVERY_MARGIN, "damping_lifetime_ticks": DAMPING_LIFETIME_MARGIN},
        },
        "continuity": _continuity(leg_b),
        "leg_a": leg_a,
        "leg_b": leg_b,
        "limitations": [
            "All figures are field-level numerical response, retention, and readout observables; no semantic recall or task utility claim is made.",
            "The active coupling in Leg A is a declared cross-port input relation, not a field cross-scale coupling.",
            "Physical candidate ports were preselected from the existing modal placement receipt; their causal ranking is not inferred from that proxy.",
            "The finite deterministic horizons and single fixed helix7 graph do not establish generalization to other graphs or consumers.",
            "Interaction is interpreted as additive only when its declared 0.01 tolerance holds; otherwise it is reported as a measured interaction.",
        ],
    }
    body["runtime_seconds"] = float(perf_counter() - started)
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    expected = str(receipt.get("content_digest", ""))
    actual = content_digest(receipt)
    return {"content_digest_matches": bool(expected == actual), "digest": actual}


def can_fail_probes(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Mutate actual measured leaves in memory; both margin predicates must fire."""
    clone = json.loads(canonical_json(receipt))
    original = float(clone["leg_a"]["comparison"]["controllability_delta_vs_T1"])
    margin = float(clone["leg_a"]["comparison"]["margin"])
    clone["leg_a"]["comparison"]["controllability_delta_vs_T1"] = 0.0
    placement_fires = bool(abs(float(clone["leg_a"]["comparison"]["controllability_delta_vs_T1"])) < margin)
    clone["leg_b"]["comparisons"]["metric_mid_difference"] = 0.0
    metric_fires = bool(abs(float(clone["leg_b"]["comparisons"]["metric_mid_difference"])) < float(clone["leg_b"]["comparisons"]["metric_margin"]))
    return {"placement_original": original, "placement_margin": margin, "placement_control_fires": placement_fires, "metric_control_fires": metric_fires}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "content_digest": receipt["content_digest"], "runtime_seconds": receipt["runtime_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
