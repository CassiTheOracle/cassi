"""Independently verify the multi-seed robustness benchmark artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from cassi_fi_paths import ARTIFACT_DIR, DESIGN_DIR

import numpy as np
import torch

import benchmark_cassi_world_model as base
from benchmark_cassi_world_model_robustness import CASE_SEEDS, GRUControl, NOISE_SIGMA, ROBUSTNESS_SCHEMA
from cassi_world_model import CassiWorldModel, load_world_model_checkpoint


FAMILIES = ("native", "off-family")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: object) -> bool:
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return math.isfinite(float(value))
    return True


def _same(left: float, right: float, tolerance: float = 1.0e-9) -> bool:
    return abs(left - right) <= tolerance


def verify(output_dir: Path) -> tuple[str, list[str]]:
    failures: list[str] = []
    result_path = output_dir / "full-world-model-robustness.json"
    report_path = output_dir / "FULL-WORLD-MODEL-ROBUSTNESS-REPORT.md"
    if not result_path.is_file():
        return "FAIL", [f"missing robustness JSON: {result_path}"]
    if not report_path.is_file():
        failures.append("robustness report is missing")
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return "FAIL", [f"robustness JSON cannot be read: {type(exc).__name__}: {exc}"]
    if payload.get("schema") != ROBUSTNESS_SCHEMA:
        failures.append("robustness schema mismatch")
    if payload.get("noise_sigma") != NOISE_SIGMA:
        failures.append("noise sigma mismatch")
    expected_prereg = (DESIGN_DIR / "FULL-WORLD-MODEL-ROBUSTNESS-PREREG.md").resolve()
    try:
        prereg = Path(payload.get("preregistration", ""))
    except TypeError:
        prereg = Path("")
    if prereg.resolve() != expected_prereg or not expected_prereg.is_file():
        failures.append("robustness preregistration path mismatch")
    elif payload.get("preregistration_sha256") != _sha256(expected_prereg):
        failures.append("robustness preregistration digest mismatch")
    script_path = Path(__file__).with_name("benchmark_cassi_world_model_robustness.py")
    if payload.get("script_sha256") != _sha256(script_path):
        failures.append("robustness harness digest mismatch")
    records = payload.get("records")
    expected_keys = {(family, seed) for family in FAMILIES for seed in CASE_SEEDS}
    actual_keys = {(item.get("family"), item.get("seed")) for item in records} if isinstance(records, list) else set()
    if actual_keys != expected_keys or len(records) != len(expected_keys):
        failures.append("robustness case set mismatch")
        records = []
    if payload.get("mechanical_failures") != []:
        failures.append("benchmark reported mechanical failures")

    full_parameter_count = sum(parameter.numel() for parameter in CassiWorldModel(base.MODEL_CONFIG).parameters())
    gru_parameter_count = GRUControl(base.OBSERVATION_DIM, base.ACTION_DIM, base.REWARD_DIM).parameter_count
    for record in records:
        family = record["family"]
        seed = record["seed"]
        full = record.get("full", {})
        gru = record.get("gru", {})
        if not _finite(record):
            failures.append(f"non-finite record: {family} seed {seed}")
        if full.get("parameter_count") != full_parameter_count:
            failures.append(f"full parameter count mismatch: {family} seed {seed}")
        if gru.get("parameter_count") != gru_parameter_count:
            failures.append(f"GRU parameter count mismatch: {family} seed {seed}")
        for name, metrics in (("full", full), ("gru", gru)):
            if metrics.get("roundtrip_max_abs_diff", math.inf) > 1.0e-6:
                failures.append(f"{name} checkpoint round-trip mismatch: {family} seed {seed}")
            if not isinstance(metrics.get("evaluation_steps_per_second"), (int, float)) or metrics["evaluation_steps_per_second"] <= 0:
                failures.append(f"{name} throughput invalid: {family} seed {seed}")
            if metrics.get("peak_memory_bytes") is not None and (not isinstance(metrics["peak_memory_bytes"], int) or metrics["peak_memory_bytes"] < 0):
                failures.append(f"{name} memory metric invalid: {family} seed {seed}")
        case_dir = output_dir / f"{family}-seed{seed}"
        train_path = case_dir / "train.npz"
        test_path = case_dir / "test.npz"
        full_path = case_dir / "full-model.pt"
        gru_path = case_dir / "gru-model.pt"
        for path, digest_key in ((train_path, "train_dataset_sha256"), (test_path, "test_dataset_sha256"), (full_path, "full_checkpoint_sha256"), (gru_path, "gru_checkpoint_sha256")):
            if not path.is_file():
                failures.append(f"missing artifact: {path}")
            elif record.get(digest_key) != _sha256(path):
                failures.append(f"artifact digest mismatch: {path}")
        if train_path.is_file() and test_path.is_file():
            with np.load(train_path, allow_pickle=False) as train_data, np.load(test_path, allow_pickle=False) as test_data:
                if train_data["observations"].shape[0] != base.TRAIN_EPISODES or test_data["observations"].shape[0] != base.TEST_EPISODES:
                    failures.append(f"episode split shape mismatch: {family} seed {seed}")
                if train_data["observations"].shape[1] != base.HORIZON or test_data["observations"].shape[1] != base.HORIZON:
                    failures.append(f"horizon mismatch: {family} seed {seed}")
        if full_path.is_file():
            try:
                loaded = load_world_model_checkpoint(full_path, device="cpu", expected_config=base.MODEL_CONFIG)
                if loaded.step != base.EPOCHS:
                    failures.append(f"full checkpoint epoch mismatch: {family} seed {seed}")
            except Exception as exc:
                failures.append(f"full checkpoint reload failed: {family} seed {seed}: {type(exc).__name__}: {exc}")
        if gru_path.is_file():
            try:
                checkpoint = torch.load(gru_path, map_location="cpu", weights_only=True)
                if checkpoint.get("schema") != "cassi.robustness.gru-checkpoint.v1" or checkpoint.get("step") != base.EPOCHS:
                    failures.append(f"GRU checkpoint metadata mismatch: {family} seed {seed}")
                restored = GRUControl(base.OBSERVATION_DIM, base.ACTION_DIM, base.REWARD_DIM)
                restored.load_state_dict(checkpoint["state_dict"], strict=True)
            except Exception as exc:
                failures.append(f"GRU checkpoint reload failed: {family} seed {seed}: {type(exc).__name__}: {exc}")

    aggregates = payload.get("aggregates")
    if not isinstance(aggregates, list) or {item.get("family") for item in aggregates} != set(FAMILIES):
        failures.append("aggregate family set mismatch")
    else:
        for aggregate in aggregates:
            family = aggregate["family"]
            selected = [record for record in records if record["family"] == family]
            clean = [float(record["full"]["clean"]["improvement"]) for record in selected]
            noisy = [float(record["full"]["noisy"]["improvement"]) for record in selected]
            full_obs = [float(record["full"]["clean"]["observation_mse"]) for record in selected]
            gru_obs = [float(record["gru"]["clean"]["observation_mse"]) for record in selected]
            expected = {
                "full_clean_improvement_median": statistics.median(clean),
                "full_clean_improvement_worst": min(clean),
                "full_noisy_improvement_median": statistics.median(noisy),
                "full_noisy_improvement_worst": min(noisy),
                "full_clean_observation_mse_median": statistics.median(full_obs),
                "gru_clean_observation_mse_median": statistics.median(gru_obs),
            }
            for key, value in expected.items():
                if not _same(float(aggregate.get(key, math.nan)), value):
                    failures.append(f"aggregate mismatch: {family}.{key}")
            if aggregate.get("clean_verdict") != ("SUPPORTS" if expected["full_clean_improvement_median"] >= 0.05 and expected["full_clean_improvement_worst"] >= 0.0 else "NULL"):
                failures.append(f"clean verdict mismatch: {family}")
            if aggregate.get("noise_verdict") != ("SUPPORTS" if expected["full_noisy_improvement_median"] >= 0.05 and expected["full_noisy_improvement_worst"] >= 0.0 else "NULL"):
                failures.append(f"noise verdict mismatch: {family}")
            if aggregate.get("gru_verdict") != ("SUPPORTS" if expected["full_clean_observation_mse_median"] <= expected["gru_clean_observation_mse_median"] else "NULL"):
                failures.append(f"GRU verdict mismatch: {family}")

    verdict = "FAIL" if failures else str(payload.get("overall_verdict", "NULL"))
    return verdict, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR / "full-world-model-robustness")
    parser.add_argument("--require-supports", action="store_true")
    args = parser.parse_args()
    verdict, failures = verify(args.output_dir)
    print(json.dumps({"verdict": verdict, "failures": failures}, indent=2))
    if verdict == "FAIL" or (args.require_supports and verdict != "SUPPORTS"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
