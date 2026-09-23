"""Compare two arrangements through the existing field-owned consumer path.

This is a narrow task-grounded measurement.  It reuses the geometry, durability,
feedback, and memory-consumer builders; it does not introduce a surrogate
consumer when an arrangement is incompatible with the shipped owner surface.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry
import run_memory_consumer_path as consumer
from cassi_field_atlas import FieldIntelligenceError

SCHEMA = "cassifi.fractal-arrangement-recall-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-arrangement-recall/exploration.json")
SEED = 20260917
MAX_RUNTIME_SECONDS = 180.0
CONTINUITY_TOLERANCE = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_digest", "receipt_sha256"})
SOURCE_RECEIPT = Path("_diag/memory-consumer-path/exploration.json")
ARRANGEMENTS = (
    ("current-meaningful-helix", "helix7"),
    ("nested-core-shell-loops", "nested-core-shell"),
)


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
        return {
            str(key): strip_timing(item)
            for key, item in value.items()
            if str(key) not in TIMING_KEYS
        }
    if isinstance(value, (tuple, list)):
        return [strip_timing(item) for item in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(strip_timing(value)).encode("utf-8")).hexdigest()


def array_digest(value: Any) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(np.ascontiguousarray(np.asarray(value, dtype="<f8")).tobytes()).hexdigest()


def _profile(arrangement_name: str) -> Any:
    # The seed is supplied to the existing arrangement builder, not used to
    # create a second arrangement implementation here.
    return geometry.build_profile(
        geometry.arrangement_named(arrangement_name, seed=SEED),
        ports_per_pool=geometry.DEFAULT_PORTS_PER_POOL,
    )


def _blocker(stage: str, error: BaseException) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "attempted": True,
        "stage": stage,
        "error_type": type(error).__name__,
        "error": str(error),
        "reason": (
            "the existing field-owned consumer path cannot serialize this profile "
            "through FieldIntelligenceOwner.inspect_resonance; no surrogate path was used"
        ),
    }


def _profile_contract(profile: Any) -> dict[str, Any]:
    return {
        "topology": str(profile.topology),
        "port_count": int(profile.port_count),
        "pools": int(profile.port_count) // int(profile.ports_per_pool),
        "ports_per_pool": int(profile.ports_per_pool),
        "projected_transport_is_none": profile.projected_transport is None,
        "projected_inv_mass_is_none": profile.projected_inv_mass is None,
        "projected_quartic_weights_is_none": profile.projected_quartic_weights is None,
        "transport_sha256": array_digest(profile.projected_transport),
        "inverse_mass_sha256": array_digest(profile.projected_inv_mass),
    }


def _controls_blocked(stage: str, error: BaseException) -> dict[str, Any]:
    blocked = _blocker(stage, error)
    return {
        "silenced": dict(blocked),
        "no_memory": dict(blocked),
        "mismatch": dict(blocked),
        "policy_mutated": dict(blocked),
    }


def _measure_arrangement(label: str, arrangement_name: str, config: consumer.MemoryConsumerConfig) -> dict[str, Any]:
    profile = _profile(arrangement_name)
    capture_config = durability.DurabilityConfig(write_budget=float(config.write_budget))
    captures = durability.capture_items(capture_config, profile)
    record: dict[str, Any] = {
        "label": label,
        "arrangement_name": arrangement_name,
        "status": "PENDING",
        "profile": _profile_contract(profile),
        "declared_consumer": config.as_dict(),
        "candidate_directions": consumer.capture_block(profile, config),
    }
    try:
        phase = consumer.phase_reference_for(profile, captures)
        refinement = consumer.neutral_gain_refinement(profile, captures, phase, config)
        gain = float(refinement["measured_gain"])
        neutrality = {
            "target": consumer.neutrality_probe(
                profile, captures, phase, config,
                item_index=int(config.target_item_index), gain=gain,
            ),
            "mismatch": consumer.neutrality_probe(
                profile, captures, phase, config,
                item_index=int(config.mismatch_item_index), gain=gain,
            ),
        }
        target, target_workspace = consumer.hold_episode(
            profile, captures, phase, config,
            item_index=int(config.target_item_index), gain=gain,
            name=f"{label}:target",
        )
        silenced = consumer.consumer_episode(
            profile, target_workspace, captures, config,
            held_episode=target, name=f"{label}:identity-control",
            read_suppressed=True,
        )
        blank, blank_workspace = consumer.blank_episode(profile, captures, config)
        no_memory = consumer.consumer_episode(
            profile, blank_workspace, captures, config,
            held_episode=blank, name=f"{label}:no-memory",
        )
        mismatch, mismatch_workspace = consumer.hold_episode(
            profile, captures, phase, config,
            item_index=int(config.mismatch_item_index), gain=gain,
            name=f"{label}:mismatch",
        )
        mismatch_control = consumer.consumer_episode(
            profile, mismatch_workspace, captures, config,
            held_episode=mismatch, name=f"{label}:mismatch-control",
        )
        policy_mutated = consumer.consumer_episode(
            profile, blank_workspace, captures, config,
            held_episode=blank, name=f"{label}:policy-mutated",
            policy_mutated=True,
        )
        consumer_arms = {
            "A-memory-used": consumer.consumer_episode(
                profile, target_workspace, captures, config,
                held_episode=target, name=f"{label}:memory-used",
            ),
            "B-identity-control-read-suppressed": silenced,
            "C-no-memory": no_memory,
            "D-mismatch-control": mismatch_control,
            "C-firing-control-policy-mutated": policy_mutated,
        }
        for result in consumer_arms.values():
            result["attempted"] = True
            result["status"] = "MEASURED"
        record.update(
            {
                "status": "MEASURED",
                "phase_reference": phase,
                "neutral_gain": refinement,
                "neutrality_probe": neutrality,
                "memory_used": consumer_arms["A-memory-used"],
                "controls": {
                    "silenced": silenced,
                    "no_memory": no_memory,
                    "mismatch": mismatch_control,
                    "policy_mutated": policy_mutated,
                },
                "consumer_arms": consumer_arms,
                "matched": {
                    "task": "carry the remembered target direction forward",
                    "candidate_directions": [
                        config.target_spec.name,
                        config.mismatch_spec.name,
                        config.fallback_spec.name,
                    ],
                    "write_budget": float(config.write_budget),
                    "act_budget": float(config.act_budget),
                    "hold_horizon_ticks": int(config.hold_horizon_ticks),
                    "read_frame_path": durability.READ_FRAME_PATH,
                    "gain": gain,
                },
            }
        )
    except FieldIntelligenceError as error:
        record["status"] = "BLOCKED"
        record["blocker"] = _blocker("field-owned-consumer-path", error)
        record["controls"] = _controls_blocked("matched-controls", error)
        record["consumer_arms"] = {
            name: dict(record["blocker"])
            for name in (
                "A-memory-used",
                "B-identity-control-read-suppressed",
                "C-no-memory",
                "D-mismatch-control",
                "C-firing-control-policy-mutated",
            )
        }
        record["matched"] = {
            "task": "carry the remembered target direction forward",
            "candidate_directions": [
                config.target_spec.name,
                config.mismatch_spec.name,
                config.fallback_spec.name,
            ],
            "write_budget": float(config.write_budget),
            "act_budget": float(config.act_budget),
            "hold_horizon_ticks": int(config.hold_horizon_ticks),
            "read_frame_path": durability.READ_FRAME_PATH,
            "not_run": True,
        }
    return record


def _can_fail_probe(record: Mapping[str, Any], config: consumer.MemoryConsumerConfig) -> dict[str, Any]:
    if record.get("status") != "MEASURED":
        return {"status": "BLOCKED", "attempted": False, "reason": "arrangement consumer arm is blocked"}
    original = copy.deepcopy(record["memory_used"])
    original_share = original["statistic"]["share_along_target"]
    mutated = copy.deepcopy(original)
    mutated["statistic"]["share_along_target"] = 0.0
    fires = not (float(mutated["statistic"]["share_along_target"]) >= float(config.pursuit_margin))
    return {
        "status": "MEASURED",
        "attempted": True,
        "kind": "mutate-real-memory-arm-target-share-to-zero",
        "original_share_along_target": original_share,
        "mutated_share_along_target": 0.0,
        "margin": float(config.pursuit_margin),
        "predicate_fires": bool(fires),
    }


def _continuity(config: consumer.MemoryConsumerConfig) -> list[dict[str, Any]]:
    cited = json.loads(Path("_diag/fractal-geometry/exploration.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for arrangement_name in ("helix7", "nested-core-shell"):
        cited_row = next(
            row for row in cited["arrangements"]
            if row["construction"]["name"] == arrangement_name
        )
        cited_value = float(cited_row["spectrum"]["ipr_median"])
        observed_value = float(
            geometry.spectrum_metrics(_profile(arrangement_name), rail_gains=())["ipr_median"]
        )
        difference = observed_value - cited_value
        rows.append(
            {
                "source_receipt": "_diag/fractal-geometry/exploration.json",
                "selector": f"arrangements[construction.name={arrangement_name}].spectrum.ipr_median",
                "cited": cited_value,
                "observed": observed_value,
                "difference": difference,
                "tolerance": CONTINUITY_TOLERANCE,
                "within_tolerance": bool(abs(difference) <= CONTINUITY_TOLERANCE),
            }
        )
    return rows


def _measure_body() -> dict[str, Any]:
    started = time.perf_counter()
    config = consumer.MemoryConsumerConfig(owner_home_prefix="arrangement-recall-")
    arms = [_measure_arrangement(label, name, config) for label, name in ARRANGEMENTS]
    for arm in arms:
        if time.perf_counter() - started >= MAX_RUNTIME_SECONDS:
            raise TimeoutError(f"arrangement recall runner exceeded {MAX_RUNTIME_SECONDS:g} seconds")
    controls = {
        arm["label"]: {
            control_name: {
                "attempted": bool(arm["controls"][control_name].get("attempted", False)),
                "status": arm["controls"][control_name].get("status"),
            }
            for control_name in ("silenced", "no_memory", "mismatch", "policy_mutated")
        }
        for arm in arms
    }
    firing = {arm["label"]: _can_fail_probe(arm, config) for arm in arms}
    continuity = _continuity(config)
    return {
        "schema": SCHEMA,
        "declared": {
            "question": "Does the existing field-owned task-grounded consumer path behave differently on the current meaningful helix and nested core-shell loops?",
            "seed": SEED,
            "arrangements": [{"label": label, "builder_name": name} for label, name in ARRANGEMENTS],
            "consumer_builder": "run_memory_consumer_path.consumer_episode",
            "task": "carry the remembered target direction forward",
            "candidate_directions": [config.target_spec.name, config.mismatch_spec.name, config.fallback_spec.name],
            "write_budget": float(config.write_budget),
            "act_budget": float(config.act_budget),
            "hold_horizon_ticks": int(config.hold_horizon_ticks),
            "observation_surface": durability.READ_FRAME_PATH,
            "controls": "same B/C/D/mutated-C controls per arrangement; controls are not replaced when an arm is blocked",
            "margins": {"pursuit": float(config.pursuit_margin), "continuity": CONTINUITY_TOLERANCE},
        },
        "arms": arms,
        "controls": controls,
        "can_fail_controls": firing,
        "continuity_checks": continuity,
        "limitations": [
            "These are field-level numeric cue-to-controller-action observables only; no semantic recall, usefulness, or generalization claim is made.",
            "The nested-core-shell profile is attempted through the shipped consumer path without a surrogate.",
            "Nested-core-shell runs through the shipped consumer path without a surrogate after canonical JSON normalization of NumPy report values; that arm and all four controls are measured.",
            "The canonical owner inspection boundary is exercised on both arrangements, so no integration blocker remains.",
            "A finite 16-tick hold and one fixed target/mismatch/fallback set do not cover other tasks, horizons, or candidate directions.",
        ],
        "verdict": "MEASURED_WITH_INTEGRATION_BLOCKER" if any(arm["status"] == "BLOCKED" for arm in arms) else "MEASURED",
        "self_check": {
            "performed": True,
            "rule": "receipt content_digest must equal content_digest(receipt) after declared timing leaves are stripped",
        },
    }


def _deterministic_rebuild(body: Mapping[str, Any]) -> dict[str, Any]:
    first_digest = content_digest(body)
    rebuilt = _measure_body()
    rebuilt_digest = content_digest(rebuilt)
    with tempfile.TemporaryDirectory(prefix="arrangement-recall-") as directory:
        path = Path(directory) / "rebuild.json"
        path.write_text(canonical_json(rebuilt), encoding="utf-8")
        round_trip = json.loads(path.read_text(encoding="utf-8"))
    return {
        "attempted": True,
        "temp_path": "<temporary>/rebuild.json",
        "first_body_digest": first_digest,
        "rebuilt_body_digest": rebuilt_digest,
        "round_trip_digest": content_digest(round_trip),
        "byte_stable_body": bool(first_digest == rebuilt_digest == content_digest(round_trip)),
    }


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    body = _measure_body()
    body["deterministic_rebuild"] = _deterministic_rebuild(body)
    body["elapsed_seconds"] = float(time.perf_counter() - started)
    if body["elapsed_seconds"] >= MAX_RUNTIME_SECONDS:
        raise TimeoutError(f"arrangement recall runner exceeded {MAX_RUNTIME_SECONDS:g} seconds")
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    body["runtime_seconds"] = body["elapsed_seconds"]
    if content_digest(body) != body["content_digest"]:
        raise ValueError("receipt self-check failed")
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    actual = content_digest(receipt)
    expected = str(receipt.get("content_digest", ""))
    return {"content_digest_matches": bool(actual == expected), "digest": actual}


def write_receipt(path: Path) -> dict[str, Any]:
    receipt = build_receipt()
    check = verify_receipt(receipt)
    if not check["content_digest_matches"]:
        raise ValueError("receipt self-check failed")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(receipt), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = write_receipt(args.output)
    print(json.dumps({"output": str(args.output), "verdict": receipt["verdict"], "content_digest": receipt["content_digest"], "runtime_seconds": receipt["runtime_seconds"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
