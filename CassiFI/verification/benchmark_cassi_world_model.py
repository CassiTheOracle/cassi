"""Run the frozen full field-native world-model performance benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from cassi_fi_paths import ARTIFACT_DIR, DESIGN_DIR
from typing import Any

import numpy as np
import torch

from cassi_modal_torch import CassiModalConfig, cassi_modal_forward_parallel, native_mode_params
from cassi_world_model import CassiTrajectoryBatch, CassiWorldModelConfig, CassiWorldModelLossConfig, load_world_model_checkpoint
from train_cassi_world_model import train


GENERATOR_SEED = 20260822
TRAINING_SEED = 20260823
EVALUATION_SEED = 20260824
EPISODES = 96
TRAIN_EPISODES = 72
TEST_EPISODES = 24
HORIZON = 32
OBSERVATION_DIM = 6
ACTION_DIM = 2
REWARD_DIM = 1
MODE_COUNT = 4
PREFIX = 16
EPOCHS = 30
BATCH_SIZE = 16
LEARNING_RATE = 0.003
WEIGHT_DECAY = 0.0001
VALIDATION_FRACTION = 0.2
GRADIENT_CLIP_NORM = 100.0

MODAL_CONFIG = CassiModalConfig(
    retained_weight=0.9,
    phi=1.61803398875,
    dt=0.005,
    omega2=20.0,
    coupling=1.0,
    steps_per_layer=1,
)
MODEL_CONFIG = CassiWorldModelConfig(
    observation_dim=OBSERVATION_DIM,
    action_dim=ACTION_DIM,
    reward_dim=REWARD_DIM,
    mode_count=MODE_COUNT,
    latent_dim=8,
    model_dim=64,
    hidden_dim=64,
    mlp_layers=1,
    min_std=0.05,
    max_std=1.5,
    modal=MODAL_CONFIG,
)
LOSS_CONFIG = CassiWorldModelLossConfig(
    observation_weight=1.0,
    reward_weight=0.5,
    continuation_weight=0.25,
    kl_weight=0.1,
    kl_balance=0.8,
    free_nats=0.1,
)


class BenchmarkError(RuntimeError):
    """A mechanical benchmark failure."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _normalize_rows(matrix: TensorLike) -> TensorLike:
    norms = torch.linalg.vector_norm(matrix, dim=1, keepdim=True).clamp_min(1.0e-8)
    return matrix / norms


TensorLike = torch.Tensor


def _native_family(seed: int) -> CassiTrajectoryBatch:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    actions = torch.randn(EPISODES, HORIZON, ACTION_DIM, generator=generator) * 0.35
    field = torch.zeros(8 * MODE_COUNT, EPISODES, dtype=torch.float32)
    modes = native_mode_params(MODE_COUNT, dtype=torch.float32)
    observation_matrix = _normalize_rows(torch.randn(OBSERVATION_DIM, 8 * MODE_COUNT, generator=generator))
    correction_matrix = _normalize_rows(torch.randn(OBSERVATION_DIM, 2 * MODE_COUNT, generator=generator))
    action_matrix = torch.randn(ACTION_DIM, 2 * MODE_COUNT, generator=generator) * 0.25
    observations: list[torch.Tensor] = []
    rewards: list[torch.Tensor] = []
    for step in range(HORIZON):
        deposit = actions[:, step] @ action_matrix
        layer_modes = deposit.transpose(0, 1).unsqueeze(1).unsqueeze(-1)
        modal = cassi_modal_forward_parallel(layer_modes, field, modes, MODAL_CONFIG)
        field = modal.state
        correction = modal.correction[:, :, 0].transpose(0, 1)
        observation = torch.tanh(field.transpose(0, 1) @ observation_matrix.T + correction @ correction_matrix.T)
        reward = (-0.2 * observation.square().mean(dim=1, keepdim=True) + 0.05 * actions[:, step].sum(dim=1, keepdim=True))
        observations.append(observation)
        rewards.append(reward)
    return CassiTrajectoryBatch(
        observations=torch.stack(observations, dim=1),
        actions=actions,
        rewards=torch.stack(rewards, dim=1),
        continues=torch.ones(EPISODES, HORIZON),
        valid=torch.ones(EPISODES, HORIZON, dtype=torch.bool),
        resets=torch.cat((torch.ones(EPISODES, 1, dtype=torch.bool), torch.zeros(EPISODES, HORIZON - 1, dtype=torch.bool)), dim=1),
    )


def _off_family(seed: int) -> CassiTrajectoryBatch:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    actions = torch.randn(EPISODES, HORIZON, ACTION_DIM, generator=generator) * 0.35
    state = torch.zeros(EPISODES, 4)
    observation_matrix = _normalize_rows(torch.randn(OBSERVATION_DIM, 4, generator=generator))
    observations: list[torch.Tensor] = []
    rewards: list[torch.Tensor] = []
    for step in range(HORIZON):
        action = actions[:, step]
        x0, x1, x2, x3 = state.unbind(dim=1)
        next_state = torch.stack(
            (
                0.92 * x0 + 0.18 * x1 + 0.12 * torch.tanh(action[:, 0]),
                0.85 * x1 - 0.22 * x0 + 0.10 * action[:, 1],
                0.95 * x2 + 0.15 * torch.sin(x0) + 0.10 * action[:, 0],
                0.88 * x3 + 0.20 * torch.tanh(x2),
            ),
            dim=1,
        )
        state = next_state
        observation = torch.tanh(state @ observation_matrix.T)
        reward = -0.1 * state.square().mean(dim=1, keepdim=True) + 0.03 * action.square().sum(dim=1, keepdim=True)
        observations.append(observation)
        rewards.append(reward)
    return CassiTrajectoryBatch(
        observations=torch.stack(observations, dim=1),
        actions=actions,
        rewards=torch.stack(rewards, dim=1),
        continues=torch.ones(EPISODES, HORIZON),
        valid=torch.ones(EPISODES, HORIZON, dtype=torch.bool),
        resets=torch.cat((torch.ones(EPISODES, 1, dtype=torch.bool), torch.zeros(EPISODES, HORIZON - 1, dtype=torch.bool)), dim=1),
    )


def _write_batch(path: Path, batch: CassiTrajectoryBatch, indices: slice) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        observations=batch.observations[indices].numpy().astype(np.float32),
        actions=batch.actions[indices].numpy().astype(np.float32),
        rewards=batch.rewards[indices].numpy().astype(np.float32),
        continues=batch.continues[indices].numpy().astype(np.float32),
        valid=batch.valid[indices].numpy(),
        resets=batch.resets[indices].numpy(),
    )


def _masked_mse(prediction: torch.Tensor, target: torch.Tensor, valid: torch.Tensor) -> float:
    values = (prediction - target).square().mean(dim=-1)
    return float(values[valid].mean().item())


def _masked_accuracy(logits: torch.Tensor, target: torch.Tensor, valid: torch.Tensor) -> float:
    predicted = (torch.sigmoid(logits) >= 0.5).to(target.dtype)
    return float((predicted[valid] == target[valid]).float().mean().item())


def _evaluate(
    model: torch.nn.Module,
    test: CassiTrajectoryBatch,
    train: CassiTrajectoryBatch,
    device: torch.device,
    checkpoint: Path,
) -> dict[str, Any]:
    model.eval()
    test_device = test.to(device=device, dtype=torch.float32)
    train_device = train.to(device=device, dtype=torch.float32)
    with torch.no_grad():
        _sync(device)
        start = time.perf_counter()
        teacher = model.observe(test_device, sample=False)
        _sync(device)
        elapsed = time.perf_counter() - start
        prefix_batch = CassiTrajectoryBatch(
            observations=test_device.observations[:, :PREFIX],
            actions=test_device.actions[:, :PREFIX],
            rewards=test_device.rewards[:, :PREFIX],
            continues=test_device.continues[:, :PREFIX],
            valid=test_device.valid[:, :PREFIX],
            resets=test_device.resets[:, :PREFIX],
        )
        prefix = model.observe(prefix_batch, sample=False)
        suffix_actions = test_device.actions[:, PREFIX:]
        suffix_valid = test_device.valid[:, PREFIX:]
        suffix_resets = test_device.resets[:, PREFIX:]
        imagined = model.imagine(suffix_actions, prefix.final_state.detach(), valid=suffix_valid, resets=suffix_resets, sample=False)
        _sync(device)
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
            _ = model.observe(test_device, sample=False)
            _sync(device)
            peak_memory = int(torch.cuda.max_memory_allocated(device))
        else:
            peak_memory = None
        persistence = test_device.observations[:, PREFIX - 1:PREFIX].expand(-1, HORIZON - PREFIX, -1)
        train_reward_mean = train_device.rewards.mean(dim=(0, 1), keepdim=True)
        roundtrip = load_world_model_checkpoint(checkpoint, device=device, expected_config=MODEL_CONFIG).model.eval()
        roundtrip_output = roundtrip.observe(test_device, sample=False)
        roundtrip_max_diff = float((roundtrip_output.observation_mean - teacher.observation_mean).abs().max().item())
    return {
        "teacher_forced_observation_mse": _masked_mse(teacher.observation_mean, test_device.observations, test_device.valid),
        "teacher_forced_reward_mse": _masked_mse(teacher.reward_mean, test_device.rewards, test_device.valid),
        "teacher_forced_continuation_accuracy": _masked_accuracy(teacher.continue_logits, test_device.continues, test_device.valid),
        "open_loop_observation_mse": _masked_mse(imagined.observation_mean, test_device.observations[:, PREFIX:], suffix_valid),
        "open_loop_reward_mse": _masked_mse(imagined.reward_mean, test_device.rewards[:, PREFIX:], suffix_valid),
        "open_loop_continuation_accuracy": _masked_accuracy(imagined.continue_logits, test_device.continues[:, PREFIX:], suffix_valid),
        "persistence_open_loop_observation_mse": _masked_mse(persistence, test_device.observations[:, PREFIX:], suffix_valid),
        "persistence_open_loop_reward_mse": _masked_mse(train_reward_mean.expand_as(test_device.rewards[:, PREFIX:]), test_device.rewards[:, PREFIX:], suffix_valid),
        "observation_improvement_over_persistence": 1.0 - _masked_mse(imagined.observation_mean, test_device.observations[:, PREFIX:], suffix_valid) / _masked_mse(persistence, test_device.observations[:, PREFIX:], suffix_valid),
        "evaluation_steps_per_second": float(test_device.batch_size * test_device.horizon / max(elapsed, 1.0e-9)),
        "peak_memory_bytes": peak_memory,
        "checkpoint_roundtrip_max_abs_diff": roundtrip_max_diff,
        "finite": all(math.isfinite(float(value)) for key, value in {
            "teacher_forced_observation_mse": _masked_mse(teacher.observation_mean, test_device.observations, test_device.valid),
            "teacher_forced_reward_mse": _masked_mse(teacher.reward_mean, test_device.rewards, test_device.valid),
            "open_loop_observation_mse": _masked_mse(imagined.observation_mean, test_device.observations[:, PREFIX:], suffix_valid),
            "open_loop_reward_mse": _masked_mse(imagined.reward_mean, test_device.rewards[:, PREFIX:], suffix_valid),
        }.items()),
    }


def _family_result(name: str, full_batch: CassiTrajectoryBatch, root: Path, device: torch.device) -> dict[str, Any]:
    train_batch = full_batch.index_select(torch.arange(TRAIN_EPISODES, dtype=torch.int64))
    test_batch = full_batch.index_select(torch.arange(TRAIN_EPISODES, EPISODES, dtype=torch.int64))
    train_path = root / f"{name}-train.npz"
    test_path = root / f"{name}-test.npz"
    checkpoint_path = root / f"{name}-model.pt"
    _write_batch(train_path, full_batch, slice(0, TRAIN_EPISODES))
    _write_batch(test_path, full_batch, slice(TRAIN_EPISODES, EPISODES))
    started = time.perf_counter()
    summary = train(
        train_path,
        checkpoint_path,
        OBSERVATION_DIM,
        ACTION_DIM,
        REWARD_DIM,
        model_config=MODEL_CONFIG,
        loss_config=LOSS_CONFIG,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        learning_rate=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
        seed=TRAINING_SEED,
        device=device,
        validation_fraction=VALIDATION_FRACTION,
        gradient_clip_norm=GRADIENT_CLIP_NORM,
    )
    training_seconds = time.perf_counter() - started
    loaded = load_world_model_checkpoint(checkpoint_path, device=device, expected_config=MODEL_CONFIG)
    metrics = _evaluate(loaded.model, test_batch, train_batch, device, checkpoint_path)
    history = loaded.metadata.get("epoch_receipts", [])
    first_train_total = history[0]["train"].get("total") if history else None
    final_train_total = history[-1]["train"].get("total") if history else None
    first_validation_total = history[0]["validation"].get("total") if history and history[0].get("validation", {}).get("available") else None
    final_validation_total = history[-1]["validation"].get("total") if history and history[-1].get("validation", {}).get("available") else None
    metrics.update({
        "training_seconds": training_seconds,
        "first_train_total_loss": first_train_total,
        "final_train_total_loss": final_train_total,
        "first_validation_total_loss": first_validation_total,
        "final_validation_total_loss": final_validation_total,
        "train_dataset_sha256": _sha256(train_path),
        "test_dataset_sha256": _sha256(test_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "episodes_train": TRAIN_EPISODES,
        "episodes_test": TEST_EPISODES,
        "horizon": HORIZON,
    })
    return {"family": name, "summary": summary, "metrics": metrics}


def _verdict(result: dict[str, Any]) -> tuple[str, list[str]]:
    metrics = result["metrics"]
    failures: list[str] = []
    for key in ("teacher_forced_observation_mse", "teacher_forced_reward_mse", "open_loop_observation_mse", "open_loop_reward_mse", "persistence_open_loop_observation_mse", "checkpoint_roundtrip_max_abs_diff"):
        value = metrics.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            failures.append(f"{result['family']}: non-finite {key}")
    if metrics.get("checkpoint_roundtrip_max_abs_diff", 1.0) > 1.0e-6:
        failures.append(f"{result['family']}: checkpoint round-trip changed predictions")
    improvement = metrics.get("observation_improvement_over_persistence", float("nan"))
    if not math.isfinite(float(improvement)):
        failures.append(f"{result['family']}: non-finite persistence improvement")
    if failures:
        return "FAIL", failures
    return ("SUPPORTS", ["open-loop observation MSE improves over persistence by at least five percent"]) if improvement >= 0.05 else ("NULL", ["mechanical checks pass but the five-percent persistence gate is not reached"])


def _render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Full field-native world-model benchmark report",
        "",
        f"- Overall verdict: **{payload['overall_verdict']}**",
        f"- Device: `{payload['device']}`",
        f"- Generator seed: `{GENERATOR_SEED}`",
        f"- Training seed: `{TRAINING_SEED}`",
        f"- Evaluation seed: `{EVALUATION_SEED}`",
        "",
        "| Family | Verdict | Teacher obs MSE | Open-loop obs MSE | Persistence obs MSE | Improvement | Train seconds | Steps/sec |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    table_rows: list[str] = []
    detail_lines: list[str] = []
    for result in payload["families"]:
        metrics = result["metrics"]
        table_rows.append(
            f"| `{result['family']}` | **{result['verdict']}** | {metrics['teacher_forced_observation_mse']:.8g} | "
            f"{metrics['open_loop_observation_mse']:.8g} | {metrics['persistence_open_loop_observation_mse']:.8g} | "
            f"{metrics['observation_improvement_over_persistence']:.3%} | {metrics['training_seconds']:.3f} | "
            f"{metrics['evaluation_steps_per_second']:.1f} |"
        )
        detail_lines.extend(["", f"### {result['family']}", "", "```json", json.dumps(metrics, indent=2, sort_keys=True), "```"])
        if result["reasons"]:
            detail_lines.extend(["", *[f"- {reason}" for reason in result["reasons"]]])
    lines.extend(table_rows)
    lines.extend(detail_lines)
    lines.extend(["", "This benchmark is an offline trajectory test. It is not a language, multimodal, Qwen, live-authority, or OS-G7 adoption result.", ""])
    return "\n".join(lines)


def run(output_dir: Path, device_name: str | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    device = torch.device(device_name or ("cuda" if torch.cuda.is_available() else "cpu"))
    if device.type == "cuda":
        torch.cuda.manual_seed_all(TRAINING_SEED)
    torch.manual_seed(EVALUATION_SEED)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(EVALUATION_SEED)
    native = _native_family(GENERATOR_SEED)
    off_family = _off_family(GENERATOR_SEED + 1)
    results: list[dict[str, Any]] = []
    for name, batch in (("native", native), ("off-family", off_family)):
        result = _family_result(name, batch, output_dir, device)
        verdict, reasons = _verdict(result)
        result["verdict"] = verdict
        result["reasons"] = reasons
        results.append(result)
    if any(result["verdict"] == "FAIL" for result in results):
        overall = "FAIL"
    elif results[0]["verdict"] == "SUPPORTS" and results[1]["verdict"] == "SUPPORTS":
        overall = "SUPPORTS"
    elif results[0]["verdict"] == "SUPPORTS":
        overall = "EMERGES"
    else:
        overall = "DOES NOT EMERGE"
    payload = {
        "schema": "cassi.full-world-model-benchmark.v1",
        "preregistration": str(DESIGN_DIR / "FULL-WORLD-MODEL-BENCHMARK-PREREG.md"),
        "preregistration_sha256": _sha256(DESIGN_DIR / "FULL-WORLD-MODEL-BENCHMARK-PREREG.md"),
        "script_sha256": _sha256(Path(__file__)),
        "device": str(device),
        "model_config": MODEL_CONFIG.to_dict(),
        "loss_config": LOSS_CONFIG.to_dict(),
        "families": results,
        "overall_verdict": overall,
    }
    (output_dir / "full-world-model-benchmark.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "FULL-WORLD-MODEL-BENCHMARK-REPORT.md").write_text(_render_report(payload), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR / "full-world-model-benchmark")
    parser.add_argument("--device", default=None)
    parser.add_argument("--require-supports", action="store_true")
    args = parser.parse_args()
    try:
        payload = run(args.output_dir, args.device)
    except Exception as exc:
        print(json.dumps({"verdict": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 1
    print(json.dumps({"verdict": payload["overall_verdict"], "families": [{"family": item["family"], "verdict": item["verdict"], "metrics": item["metrics"]} for item in payload["families"]]}, indent=2, sort_keys=True))
    if payload["overall_verdict"] == "FAIL":
        return 1
    if args.require_supports and payload["overall_verdict"] != "SUPPORTS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
