"""Independently verify the frozen full-world-model benchmark artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from benchmark_cassi_world_model import (
    BATCH_SIZE,
    EPOCHS,
    HORIZON,
    MODEL_CONFIG,
    TEST_EPISODES,
    TRAIN_EPISODES,
    load_world_model_checkpoint,
)


SCHEMA = "cassi.full-world-model-benchmark.v1"
FAMILIES = ("native", "off-family")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def verify(output_dir: Path) -> tuple[str, list[str]]:
    failures: list[str] = []
    result_path = output_dir / "full-world-model-benchmark.json"
    report_path = output_dir / "FULL-WORLD-MODEL-BENCHMARK-REPORT.md"
    if not result_path.is_file():
        return "FAIL", [f"missing benchmark JSON: {result_path}"]
    if not report_path.is_file():
        failures.append(f"missing benchmark report: {report_path}")
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return "FAIL", [f"benchmark JSON cannot be read: {type(exc).__name__}: {exc}"]
    if payload.get("schema") != SCHEMA:
        failures.append("benchmark schema mismatch")
    if payload.get("model_config") != MODEL_CONFIG.to_dict():
        failures.append("model configuration mismatch")
    if payload.get("overall_verdict") != "SUPPORTS":
        failures.append("overall verdict is not SUPPORTS")
    prereg = Path(payload.get("preregistration", ""))
    expected_prereg = Path(__file__).with_name("FULL-WORLD-MODEL-BENCHMARK-PREREG.md").resolve()
    if prereg.resolve() != expected_prereg or not expected_prereg.is_file():
        failures.append("preregistration path mismatch")
    elif payload.get("preregistration_sha256") != _sha256(expected_prereg):
        failures.append("preregistration digest mismatch")
    script_path = Path(__file__).with_name("benchmark_cassi_world_model.py")
    if payload.get("script_sha256") != _sha256(script_path):
        failures.append("benchmark script digest mismatch")

    families = payload.get("families")
    if not isinstance(families, list) or {item.get("family") for item in families if isinstance(item, dict)} != set(FAMILIES):
        failures.append("benchmark family set mismatch")
        families = []
    for family in families:
        if not isinstance(family, dict):
            failures.append("family record is not an object")
            continue
        name = family.get("family")
        if name not in FAMILIES:
            failures.append(f"unexpected family: {name}")
            continue
        if family.get("verdict") != "SUPPORTS":
            failures.append(f"{name} did not reach SUPPORTS")
        metrics = family.get("metrics")
        if not isinstance(metrics, dict):
            failures.append(f"{name} metrics are missing")
            continue
        for key in (
            "teacher_forced_observation_mse",
            "teacher_forced_reward_mse",
            "open_loop_observation_mse",
            "open_loop_reward_mse",
            "persistence_open_loop_observation_mse",
            "observation_improvement_over_persistence",
            "evaluation_steps_per_second",
            "training_seconds",
            "first_train_total_loss",
            "final_train_total_loss",
            "first_validation_total_loss",
            "final_validation_total_loss",
        ):
            if not _finite(metrics.get(key)):
                failures.append(f"{name} metric is non-finite: {key}")
        if metrics.get("finite") is not True:
            failures.append(f"{name} finite flag is false")
        if metrics.get("checkpoint_roundtrip_max_abs_diff", math.inf) > 1.0e-6:
            failures.append(f"{name} checkpoint round-trip mismatch")
        if metrics.get("episodes_train") != TRAIN_EPISODES or metrics.get("episodes_test") != TEST_EPISODES or metrics.get("horizon") != HORIZON:
            failures.append(f"{name} split or horizon mismatch")
        if metrics.get("observation_improvement_over_persistence", -math.inf) < 0.05:
            failures.append(f"{name} persistence improvement gate failed")
        if metrics.get("peak_memory_bytes") is not None and (not isinstance(metrics["peak_memory_bytes"], int) or metrics["peak_memory_bytes"] < 0):
            failures.append(f"{name} peak-memory metric invalid")

        train_path = output_dir / f"{name}-train.npz"
        test_path = output_dir / f"{name}-test.npz"
        checkpoint_path = output_dir / f"{name}-model.pt"
        for path, key in ((train_path, "train_dataset_sha256"), (test_path, "test_dataset_sha256"), (checkpoint_path, "checkpoint_sha256")):
            if not path.is_file():
                failures.append(f"{name} artifact missing: {path.name}")
            elif metrics.get(key) != _sha256(path):
                failures.append(f"{name} artifact digest mismatch: {path.name}")
        if checkpoint_path.is_file():
            try:
                loaded = load_world_model_checkpoint(checkpoint_path, device="cpu", expected_config=MODEL_CONFIG)
                if loaded.step != EPOCHS:
                    failures.append(f"{name} checkpoint epoch mismatch")
                if loaded.metadata.get("dataset_digest") is None:
                    failures.append(f"{name} checkpoint lacks dataset digest")
            except Exception as exc:
                failures.append(f"{name} checkpoint reload failed: {type(exc).__name__}: {exc}")

    verdict = "FAIL" if failures else "SUPPORTS"
    return verdict, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("_diag/full-world-model-benchmark"))
    parser.add_argument("--require-supports", action="store_true")
    args = parser.parse_args()
    verdict, failures = verify(args.output_dir)
    payload: dict[str, Any] = {"verdict": verdict, "failures": failures}
    print(json.dumps(payload, indent=2))
    if verdict == "FAIL" or (args.require_supports and verdict != "SUPPORTS"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
