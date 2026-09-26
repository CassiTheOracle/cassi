"""Three-arm arrangement recall matrix through the shipped consumer path.

This workstream is intentionally separate from the earlier two-arm receipt.  It
imports that runner's arrangement measurement and can-fail probe, and imports
all geometry and consumer builders rather than reproducing either implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_arrangement_recall_exploration as prior
import run_fractal_geometry_exploration as geometry
import run_memory_consumer_path as consumer
from cassi_field_atlas import canonical_json_bytes

SCHEMA = "cassifi.fractal-arrangement-recall-matrix.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-arrangement-recall-matrix/exploration.json")
SEED = prior.SEED
MAX_RUNTIME_SECONDS = prior.MAX_RUNTIME_SECONDS
CONTINUITY_TOLERANCE = prior.CONTINUITY_TOLERANCE
# These are the timing and digest leaves excluded from the content digest.  The
# declaration is also emitted inside every receipt so a re-reader can reproduce
# the rule without relying on an implementation detail.
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_digest", "receipt_sha256"})
ARRANGEMENTS = (
    ("current-meaningful-helix", "helix7"),
    ("nested-core-shell-loops", "nested-core-shell"),
    ("nested-paired-loops", "recursive-paired-loops"),
)
CONTROL_NAMES = ("silenced", "no_memory", "mismatch", "policy_mutated")
CONSUMER_ARM_NAMES = (
    "A-memory-used",
    "B-identity-control-read-suppressed",
    "C-no-memory",
    "D-mismatch-control",
    "C-firing-control-policy-mutated",
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


def _profile(arrangement_name: str) -> Any:
    # Reuse the geometry runner's canonical named builder.  No matrix-local
    # geometry or topology implementation is introduced here.
    return geometry.build_profile(
        geometry.arrangement_named(arrangement_name, seed=SEED),
        ports_per_pool=geometry.DEFAULT_PORTS_PER_POOL,
    )

def _owner_inspection(arrangement_name: str) -> dict[str, Any]:
    """Exercise the canonical owner inspection + JSON normalization boundary."""
    profile = _profile(arrangement_name)
    owner, home = consumer.open_owner(profile, prefix="arrangement-matrix-inspection-")
    try:
        try:
            report = owner.inspect_resonance()
            encoded = canonical_json_bytes(report)
            decoded = json.loads(encoded.decode("utf-8"))
            edge_powers = decoded.get("edge_powers", [])
            return {
                "status": "MEASURED",
                "canonical_json": True,
                "edge_power_count": len(edge_powers),
                "first_edge_source_type": type(edge_powers[0]["source"]).__name__ if edge_powers else None,
                "first_edge_destination_type": type(edge_powers[0]["destination"]).__name__ if edge_powers else None,
                "report_sha256": hashlib.sha256(encoded).hexdigest(),
            }
        except Exception as error:
            # Preserve an owner-serialization blocker as a blocker; never turn
            # it into a negative dynamics result or substitute another path.
            return {
                "status": "BLOCKED",
                "canonical_json": False,
                "error_type": type(error).__name__,
                "error": str(error),
                "reason": "canonical owner inspection/JSON normalization blocked this arrangement",
            }
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def _continuity() -> list[dict[str, Any]]:
    source = Path("_diag/fractal-geometry/exploration.json")
    cited = json.loads(source.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for _, arrangement_name in ARRANGEMENTS:
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
                "source_receipt": str(source).replace("\\", "/"),
                "selector": f"arrangements[construction.name={arrangement_name}].spectrum.ipr_median",
                "cited": cited_value,
                "observed": observed_value,
                "difference": difference,
                "tolerance": CONTINUITY_TOLERANCE,
                "within_tolerance": bool(abs(difference) <= CONTINUITY_TOLERANCE),
            }
        )
    return rows


def _blocked_control_bookkeeping(arm: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "attempted": bool(arm.get("controls", {}).get(name, {}).get("attempted", False)),
            "status": arm.get("controls", {}).get(name, {}).get("status", "BLOCKED"),
        }
        for name in CONTROL_NAMES
    }

def _measure_arm(
    spec: tuple[str, str],
    config: consumer.MemoryConsumerConfig,
) -> dict[str, Any]:
    label, arrangement_name = spec
    # The prior runner owns the complete real consumer/control sequence,
    # including exact blocker preservation and no-surrogate behavior.
    arm = prior._measure_arrangement(label, arrangement_name, config)
    arm["owner_inspection"] = _owner_inspection(arrangement_name)
    return arm


def _submit_arms(pool: ProcessPoolExecutor, config: consumer.MemoryConsumerConfig) -> list[Any]:
    return [pool.submit(_measure_arm, spec, config) for spec in ARRANGEMENTS]


def _collect_arms(futures: Sequence[Any]) -> list[dict[str, Any]]:
    # The declared tuple order is retained even though workers finish freely.
    return [future.result() for future in futures]


def _assemble_body(
    arms: list[dict[str, Any]],
    config: consumer.MemoryConsumerConfig,
) -> dict[str, Any]:
    can_fail = {arm["label"]: prior._can_fail_probe(arm, config) for arm in arms}
    return {
        "schema": SCHEMA,
        "declared": {
            "question": "Does the same field-owned task-grounded consumer path differ across the current meaningful helix, nested core-shell loops, and recursive/nested paired loops?",
            "seed": SEED,
            "arrangements": [{"label": label, "builder_name": name} for label, name in ARRANGEMENTS],
            "consumer_builder": "run_memory_consumer_path.consumer_episode",
            "consumer_measurement_import": "run_fractal_arrangement_recall_exploration._measure_arrangement",
            "task": "carry the remembered target direction forward",
            "candidate_directions": [config.target_spec.name, config.mismatch_spec.name, config.fallback_spec.name],
            "target_item_index": int(config.target_item_index),
            "mismatch_item_index": int(config.mismatch_item_index),
            "fallback_item_index": int(config.fallback_item_index),
            "write_budget": float(config.write_budget),
            "act_budget": float(config.act_budget),
            "hold_horizon_ticks": int(config.hold_horizon_ticks),
            "observation_surface": prior.durability.READ_FRAME_PATH,
            "controls": list(CONTROL_NAMES),
            "consumer_arms": list(CONSUMER_ARM_NAMES),
            "margins": {"pursuit": float(config.pursuit_margin), "continuity": CONTINUITY_TOLERANCE},
            "timing_stripping": {
                "clock_leaf_keys": sorted(TIMING_KEYS),
                "derived_clock_keys": [],
                "rule": "content_digest hashes canonical JSON after these timing/digest leaves are stripped recursively",
            },
            "canonical_owner_inspection": "cassi_field_atlas.canonical_json_bytes(FieldIntelligenceOwner.inspect_resonance())",
        },
        "arms": arms,
        "control_statuses": {arm["label"]: _blocked_control_bookkeeping(arm) for arm in arms},
        "can_fail_controls": can_fail,
        "continuity_checks": _continuity(),
        "limitations": [
            "These are field-level numeric cue-to-controller-action observables only; no semantic recall, usefulness, or generalization claim is made.",
            "All three arrangements use one matched MemoryConsumerConfig and the shipped consumer path; no surrogate is used for a blocked arm.",
            "A finite 16-tick hold and one fixed target/mismatch/fallback set do not cover other tasks, horizons, or candidate directions.",
            "A blocked recursive-paired-loops arm is an integration blocker, not a negative dynamics result.",
        ],
        "verdict": "MEASURED_WITH_INTEGRATION_BLOCKER" if any(arm["status"] == "BLOCKED" for arm in arms) else "MEASURED",
        "self_check": {
            "performed": True,
            "rule": "receipt content_digest must equal content_digest(receipt) after the declared timing leaves are stripped",
        },
    }


def _measure_body() -> dict[str, Any]:
    config = consumer.MemoryConsumerConfig(owner_home_prefix="arrangement-recall-matrix-")
    with ProcessPoolExecutor(max_workers=len(ARRANGEMENTS)) as pool:
        arms = _collect_arms(_submit_arms(pool, config))
    return _assemble_body(arms, config)


def _measure_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    """Run both complete three-arm builds concurrently in one six-worker pool."""
    config = consumer.MemoryConsumerConfig(owner_home_prefix="arrangement-recall-matrix-")
    with ProcessPoolExecutor(max_workers=len(ARRANGEMENTS) * 2) as pool:
        first_futures = _submit_arms(pool, config)
        rebuilt_futures = _submit_arms(pool, config)
        first_arms = _collect_arms(first_futures)
        rebuilt_arms = _collect_arms(rebuilt_futures)
    return _assemble_body(first_arms, config), _assemble_body(rebuilt_arms, config)


def _deterministic_rebuild(
    body: Mapping[str, Any],
    rebuilt: Mapping[str, Any],
) -> dict[str, Any]:
    first_digest = content_digest(body)
    rebuilt_digest = content_digest(rebuilt)
    with tempfile.TemporaryDirectory(prefix="arrangement-recall-matrix-") as directory:
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
    body, rebuilt = _measure_pair()
    body["deterministic_rebuild"] = _deterministic_rebuild(body, rebuilt)
    body["elapsed_seconds"] = float(time.perf_counter() - started)
    if body["elapsed_seconds"] >= MAX_RUNTIME_SECONDS:
        raise TimeoutError(f"arrangement recall matrix exceeded {MAX_RUNTIME_SECONDS:g} seconds")
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
    if not verify_receipt(receipt)["content_digest_matches"]:
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
