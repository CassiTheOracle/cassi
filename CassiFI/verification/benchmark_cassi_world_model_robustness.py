"""Run the frozen multi-seed, GRU-control, and noisy-prefix benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from cassi_fi_paths import ARTIFACT_DIR, DESIGN_DIR
from typing import NamedTuple

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as F

import benchmark_cassi_world_model as base
from cassi_world_model import CassiTrajectoryBatch, load_world_model_checkpoint


CASE_SEEDS = (20260822, 20260832, 20260842)
NOISE_SIGMA = 0.05
PREFIX = base.PREFIX
ROBUSTNESS_SCHEMA = "cassi.full-world-model-robustness.v1"


class GRUState(NamedTuple):
    hidden: Tensor
    previous_observation: Tensor


class GRUOutput(NamedTuple):
    observation_mean: Tensor
    reward_mean: Tensor
    continue_logits: Tensor
    final_state: GRUState


class GRUControl(nn.Module):
    """Generic recurrent control with the same trajectory timing contract."""

    def __init__(self, observation_dim: int, action_dim: int, reward_dim: int, hidden_dim: int = 32) -> None:
        super().__init__()
        self.observation_dim = observation_dim
        self.action_dim = action_dim
        self.reward_dim = reward_dim
        self.hidden_dim = hidden_dim
        # Explicit GRU equations avoid the MIOpen RNN kernel path, which is
        # currently incompatible with this Windows ROCm toolchain's HIPRTC.
        self.recurrent_input = nn.Linear(observation_dim + action_dim, 3 * hidden_dim)
        self.recurrent_hidden = nn.Linear(hidden_dim, 3 * hidden_dim, bias=False)
        self.observation_head = nn.Linear(hidden_dim, observation_dim)
        self.reward_head = nn.Linear(hidden_dim, reward_dim)
        self.continuation_head = nn.Linear(hidden_dim, 1)

    @property
    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def initial_state(self, batch_size: int, device: torch.device, dtype: torch.dtype) -> GRUState:
        return GRUState(
            hidden=torch.zeros(batch_size, self.hidden_dim, device=device, dtype=dtype),
            previous_observation=torch.zeros(batch_size, self.observation_dim, device=device, dtype=dtype),
        )

    def _step(
        self,
        action: Tensor,
        state: GRUState,
        valid: Tensor,
        reset: Tensor,
        teacher_observation: Tensor | None,
    ) -> tuple[Tensor, Tensor, Tensor, GRUState]:
        reset = reset & valid
        hidden = torch.where(reset[:, None], torch.zeros_like(state.hidden), state.hidden)
        previous = torch.where(reset[:, None], torch.zeros_like(state.previous_observation), state.previous_observation)
        recurrent_input = torch.cat((previous, action), dim=-1)
        input_reset, input_update, input_candidate = self.recurrent_input(recurrent_input).chunk(3, dim=-1)
        hidden_reset, hidden_update, hidden_candidate = self.recurrent_hidden(hidden).chunk(3, dim=-1)
        reset_gate = torch.sigmoid(input_reset + hidden_reset)
        update_gate = torch.sigmoid(input_update + hidden_update)
        candidate = torch.tanh(input_candidate + reset_gate * hidden_candidate)
        candidate = (1.0 - update_gate) * candidate + update_gate * hidden
        hidden = torch.where(valid[:, None], candidate, hidden)
        observation = self.observation_head(hidden)
        reward = self.reward_head(hidden)
        continuation = self.continuation_head(hidden).squeeze(-1)
        observation = torch.where(valid[:, None], observation, torch.zeros_like(observation))
        reward = torch.where(valid[:, None], reward, torch.zeros_like(reward))
        continuation = torch.where(valid, continuation, torch.zeros_like(continuation))
        next_previous = teacher_observation if teacher_observation is not None else observation
        next_previous = torch.where(valid[:, None], next_previous, previous)
        return observation, reward, continuation, GRUState(hidden, next_previous)

    def teacher(self, batch: CassiTrajectoryBatch) -> GRUOutput:
        state = self.initial_state(batch.batch_size, batch.observations.device, batch.observations.dtype)
        observations: list[Tensor] = []
        rewards: list[Tensor] = []
        continuations: list[Tensor] = []
        for step in range(batch.horizon):
            observation, reward, continuation, state = self._step(
                batch.actions[:, step], state, batch.valid[:, step], batch.resets[:, step], batch.observations[:, step]
            )
            observations.append(observation)
            rewards.append(reward)
            continuations.append(continuation)
        return GRUOutput(torch.stack(observations, 1), torch.stack(rewards, 1), torch.stack(continuations, 1), state)

    def imagine(self, actions: Tensor, state: GRUState, valid: Tensor, resets: Tensor) -> GRUOutput:
        observations: list[Tensor] = []
        rewards: list[Tensor] = []
        continuations: list[Tensor] = []
        for step in range(actions.shape[1]):
            observation, reward, continuation, state = self._step(
                actions[:, step], state, valid[:, step], resets[:, step], None
            )
            observations.append(observation)
            rewards.append(reward)
            continuations.append(continuation)
        return GRUOutput(torch.stack(observations, 1), torch.stack(rewards, 1), torch.stack(continuations, 1), state)


def _masked_mean(value: Tensor, valid: Tensor) -> Tensor:
    return value[valid].mean()


def _gru_loss(output: GRUOutput, batch: CassiTrajectoryBatch) -> Tensor:
    observation = _masked_mean((output.observation_mean - batch.observations).square().mean(-1), batch.valid)
    reward = _masked_mean((output.reward_mean - batch.rewards).square().mean(-1), batch.valid)
    continuation = _masked_mean(F.binary_cross_entropy_with_logits(output.continue_logits, batch.continues, reduction="none"), batch.valid)
    return observation + 0.5 * reward + 0.25 * continuation


def _train_gru(batch: CassiTrajectoryBatch, seed: int, device: torch.device) -> tuple[GRUControl, dict[str, float], float]:
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    model = GRUControl(base.OBSERVATION_DIM, base.ACTION_DIM, base.REWARD_DIM).to(device=device, dtype=torch.float32)
    optimizer = torch.optim.AdamW(model.parameters(), lr=base.LEARNING_RATE, weight_decay=base.WEIGHT_DECAY)
    started = time.perf_counter()
    first_loss = None
    final_loss = None
    train_device = batch.to(device=device, dtype=torch.float32)
    generator = torch.Generator(device="cpu").manual_seed(seed)
    for epoch in range(base.EPOCHS):
        model.train()
        indices = torch.randperm(train_device.batch_size, generator=generator)
        total = 0.0
        count = 0
        for start in range(0, train_device.batch_size, base.BATCH_SIZE):
            selected = indices[start:start + base.BATCH_SIZE]
            mini = train_device.index_select(selected.to(device=train_device.observations.device))
            optimizer.zero_grad(set_to_none=True)
            loss = _gru_loss(model.teacher(mini), mini)
            if not bool(torch.isfinite(loss).item()):
                raise RuntimeError("GRU control loss became non-finite")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), base.GRADIENT_CLIP_NORM)
            optimizer.step()
            total += float(loss.detach().item())
            count += 1
        epoch_loss = total / max(count, 1)
        first_loss = epoch_loss if first_loss is None else first_loss
        final_loss = epoch_loss
    return model.eval(), {"first_train_loss": float(first_loss), "final_train_loss": float(final_loss)}, time.perf_counter() - started


def _open_loop(model: GRUControl, batch: CassiTrajectoryBatch, device: torch.device, noise: bool, seed: int) -> dict[str, float]:
    target = batch.to(device=device, dtype=torch.float32)
    prefix_observation = target.observations[:, :PREFIX]
    if noise:
        generator = torch.Generator(device=device.type).manual_seed(seed)
        prefix_observation = prefix_observation + NOISE_SIGMA * torch.randn(prefix_observation.shape, generator=generator, device=device)
    prefix = CassiTrajectoryBatch(prefix_observation, target.actions[:, :PREFIX], target.rewards[:, :PREFIX], target.continues[:, :PREFIX], target.valid[:, :PREFIX], target.resets[:, :PREFIX])
    prefix_output = model.teacher(prefix)
    suffix = model.imagine(target.actions[:, PREFIX:], prefix_output.final_state, target.valid[:, PREFIX:], target.resets[:, PREFIX:])
    expected_observations = target.observations[:, PREFIX:]
    expected_rewards = target.rewards[:, PREFIX:]
    valid = target.valid[:, PREFIX:]
    persistence = prefix_observation[:, -1:, :].expand_as(expected_observations)
    return {
        "observation_mse": float((suffix.observation_mean[valid] - expected_observations[valid]).square().mean().item()),
        "reward_mse": float((suffix.reward_mean[valid] - expected_rewards[valid]).square().mean().item()),
        "persistence_observation_mse": float((persistence[valid] - expected_observations[valid]).square().mean().item()),
        "continuation_accuracy": float(((torch.sigmoid(suffix.continue_logits[valid]) >= 0.5) == target.continues[:, PREFIX:][valid]).float().mean().item()),
        "improvement": float(1.0 - ((suffix.observation_mean[valid] - expected_observations[valid]).square().mean() / (persistence[valid] - expected_observations[valid]).square().mean()).item()),
    }


def _evaluate_gru(model: GRUControl, batch: CassiTrajectoryBatch, device: torch.device, seed: int) -> dict[str, object]:
    target = batch.to(device=device, dtype=torch.float32)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    base._sync(device)
    started = time.perf_counter()
    with torch.no_grad():
        clean = _open_loop(model, batch, device, False, seed)
        noisy = _open_loop(model, batch, device, True, seed + 1000)
        teacher = model.teacher(target)
    base._sync(device)
    elapsed = time.perf_counter() - started
    teacher_obs_mse = float((teacher.observation_mean[target.valid] - target.observations[target.valid]).square().mean().item())
    return {
        "teacher_observation_mse": teacher_obs_mse,
        "clean": clean,
        "noisy": noisy,
        "evaluation_steps_per_second": float(target.batch_size * target.horizon / max(elapsed, 1.0e-9)),
        "peak_memory_bytes": int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None,
    }



def _evaluate_full(model: torch.nn.Module, batch: CassiTrajectoryBatch, device: torch.device, checkpoint: Path, seed: int) -> dict[str, object]:
    target = batch.to(device=device, dtype=torch.float32)
    model.eval()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    base._sync(device)
    started = time.perf_counter()
    with torch.no_grad():
        teacher = model.observe(target, sample=False)
        clean = _full_open_loop(model, target, device, False, seed)
        noisy = _full_open_loop(model, target, device, True, seed + 1000)
        roundtrip = load_world_model_checkpoint(checkpoint, device=device, expected_config=base.MODEL_CONFIG).model.eval()
        roundtrip_output = roundtrip.observe(target, sample=False)
    base._sync(device)
    elapsed = time.perf_counter() - started
    teacher_obs_mse = float((teacher.observation_mean[target.valid] - target.observations[target.valid]).square().mean().item())
    roundtrip_diff = float((roundtrip_output.observation_mean - teacher.observation_mean).abs().max().item())
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    return {
        "parameter_count": parameter_count,
        "teacher_observation_mse": teacher_obs_mse,
        "clean": clean,
        "noisy": noisy,
        "roundtrip_max_abs_diff": roundtrip_diff,
        "evaluation_steps_per_second": float(target.batch_size * target.horizon / max(elapsed, 1.0e-9)),
        "peak_memory_bytes": int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None,
    }


def _full_open_loop(model: torch.nn.Module, target: CassiTrajectoryBatch, device: torch.device, noise: bool, seed: int) -> dict[str, float]:
    prefix_observation = target.observations[:, :PREFIX]
    if noise:
        generator = torch.Generator(device=device.type).manual_seed(seed)
        prefix_observation = prefix_observation + NOISE_SIGMA * torch.randn(prefix_observation.shape, generator=generator, device=device)
    prefix = CassiTrajectoryBatch(prefix_observation, target.actions[:, :PREFIX], target.rewards[:, :PREFIX], target.continues[:, :PREFIX], target.valid[:, :PREFIX], target.resets[:, :PREFIX])
    prefix_output = model.observe(prefix, sample=False)
    suffix = model.imagine(target.actions[:, PREFIX:], prefix_output.final_state.detach(), valid=target.valid[:, PREFIX:], resets=target.resets[:, PREFIX:], sample=False)
    expected_observations = target.observations[:, PREFIX:]
    expected_rewards = target.rewards[:, PREFIX:]
    valid = target.valid[:, PREFIX:]
    persistence = prefix_observation[:, -1:, :].expand_as(expected_observations)
    model_error = (suffix.observation_mean[valid] - expected_observations[valid]).square().mean()
    persistence_error = (persistence[valid] - expected_observations[valid]).square().mean()
    return {
        "observation_mse": float(model_error.item()),
        "reward_mse": float((suffix.reward_mean[valid] - expected_rewards[valid]).square().mean().item()),
        "persistence_observation_mse": float(persistence_error.item()),
        "continuation_accuracy": float(((torch.sigmoid(suffix.continue_logits[valid]) >= 0.5) == target.continues[:, PREFIX:][valid]).float().mean().item()),
        "improvement": float(1.0 - (model_error / persistence_error).item()),
    }


def _finite(value: object) -> bool:
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return math.isfinite(float(value))
    return True


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def _gru_roundtrip_diff(model: GRUControl, checkpoint: Path, batch: CassiTrajectoryBatch, device: torch.device) -> float:
    payload = torch.load(checkpoint, map_location=device, weights_only=True)
    if payload.get("schema") != "cassi.robustness.gru-checkpoint.v1" or payload.get("step") != base.EPOCHS:
        raise RuntimeError("GRU checkpoint metadata mismatch")
    if payload.get("parameter_count") != model.parameter_count:
        raise RuntimeError("GRU checkpoint parameter count mismatch")
    restored = GRUControl(base.OBSERVATION_DIM, base.ACTION_DIM, base.REWARD_DIM).to(device=device, dtype=torch.float32)
    restored.load_state_dict(payload["state_dict"], strict=True)
    target = batch.to(device=device, dtype=torch.float32)
    with torch.no_grad():
        original = model.teacher(target)
        replayed = restored.teacher(target)
    return float((original.observation_mean - replayed.observation_mean).abs().max().item())



def _run_case(family: str, seed: int, output_dir: Path, device: torch.device) -> dict[str, object]:
    full_batch = base._native_family(seed) if family == "native" else base._off_family(seed)
    train_batch = full_batch.index_select(torch.arange(base.TRAIN_EPISODES, dtype=torch.int64))
    test_batch = full_batch.index_select(torch.arange(base.TRAIN_EPISODES, base.EPISODES, dtype=torch.int64))
    case_dir = output_dir / f"{family}-seed{seed}"
    case_dir.mkdir(parents=True, exist_ok=True)
    train_path = case_dir / "train.npz"
    test_path = case_dir / "test.npz"
    full_checkpoint_path = case_dir / "full-model.pt"
    gru_checkpoint_path = case_dir / "gru-model.pt"
    base._write_batch(train_path, full_batch, slice(0, base.TRAIN_EPISODES))
    base._write_batch(test_path, full_batch, slice(base.TRAIN_EPISODES, base.EPISODES))
    train_started = time.perf_counter()
    base.train(train_path, full_checkpoint_path, base.OBSERVATION_DIM, base.ACTION_DIM, base.REWARD_DIM, model_config=base.MODEL_CONFIG, loss_config=base.LOSS_CONFIG, epochs=base.EPOCHS, batch_size=base.BATCH_SIZE, learning_rate=base.LEARNING_RATE, weight_decay=base.WEIGHT_DECAY, seed=seed + 1, device=device, validation_fraction=base.VALIDATION_FRACTION, gradient_clip_norm=base.GRADIENT_CLIP_NORM)
    full_training_seconds = time.perf_counter() - train_started
    full_checkpoint = load_world_model_checkpoint(full_checkpoint_path, device=device, expected_config=base.MODEL_CONFIG)
    full_metrics = _evaluate_full(full_checkpoint.model, test_batch, device, full_checkpoint_path, seed + 2)
    gru_train_started = time.perf_counter()
    gru_model, gru_train_metrics, gru_training_seconds = _train_gru(train_batch, seed + 1, device)
    torch.save({"schema": "cassi.robustness.gru-checkpoint.v1", "state_dict": gru_model.state_dict(), "parameter_count": gru_model.parameter_count, "step": base.EPOCHS}, gru_checkpoint_path)
    gru_metrics = _evaluate_gru(gru_model, test_batch, device, seed + 2)
    gru_roundtrip_diff = _gru_roundtrip_diff(gru_model, gru_checkpoint_path, test_batch, device)
    return {
        "family": family,
        "seed": seed,
        "full": full_metrics,
        "gru": {
            **gru_metrics,
            **gru_train_metrics,
            "parameter_count": gru_model.parameter_count,
            "training_seconds": gru_training_seconds,
            "roundtrip_max_abs_diff": gru_roundtrip_diff,
        },
        "full_training_seconds": full_training_seconds,
        "train_dataset_sha256": _sha256(train_path),
        "test_dataset_sha256": _sha256(test_path),
        "full_checkpoint_sha256": _sha256(full_checkpoint_path),
        "gru_checkpoint_sha256": _sha256(gru_checkpoint_path),
        "full_checkpoint": str(full_checkpoint_path),
        "gru_checkpoint": str(gru_checkpoint_path),
    }


def _aggregate(records: list[dict[str, object]], family: str) -> dict[str, object]:
    selected = [record for record in records if record["family"] == family]
    full_clean = [float(record["full"]["clean"]["improvement"]) for record in selected]  # type: ignore[index]
    full_noisy = [float(record["full"]["noisy"]["improvement"]) for record in selected]  # type: ignore[index]
    full_obs = [float(record["full"]["clean"]["observation_mse"]) for record in selected]  # type: ignore[index]
    gru_obs = [float(record["gru"]["clean"]["observation_mse"]) for record in selected]  # type: ignore[index]
    clean_supports = statistics.median(full_clean) >= 0.05 and min(full_clean) >= 0.0
    noisy_supports = statistics.median(full_noisy) >= 0.05 and min(full_noisy) >= 0.0
    gru_supports = statistics.median(full_obs) <= statistics.median(gru_obs)
    return {
        "family": family,
        "full_clean_improvement_median": statistics.median(full_clean),
        "full_clean_improvement_worst": min(full_clean),
        "full_noisy_improvement_median": statistics.median(full_noisy),
        "full_noisy_improvement_worst": min(full_noisy),
        "full_clean_observation_mse_median": statistics.median(full_obs),
        "gru_clean_observation_mse_median": statistics.median(gru_obs),
        "clean_verdict": "SUPPORTS" if clean_supports else "NULL",
        "noise_verdict": "SUPPORTS" if noisy_supports else "NULL",
        "gru_verdict": "SUPPORTS" if gru_supports else "NULL",
    }


def _render_report(payload: dict[str, object]) -> str:
    lines = [
        "# Full field-native world-model robustness report",
        "",
        f"- Overall verdict: **{payload['overall_verdict']}**",
        f"- Device: `{payload['device']}`",
        f"- Noise sigma: `{NOISE_SIGMA}`",
        "",
        "| Family | Clean gate | Noise gate | GRU median gate | Full clean improvement median | Worst seed | Noisy median |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for aggregate in payload["aggregates"]:  # type: ignore[union-attr]
        lines.append(f"| `{aggregate['family']}` | **{aggregate['clean_verdict']}** | **{aggregate['noise_verdict']}** | **{aggregate['gru_verdict']}** | {aggregate['full_clean_improvement_median']:.3%} | {aggregate['full_clean_improvement_worst']:.3%} | {aggregate['full_noisy_improvement_median']:.3%} |")
    lines.extend(["", "## Per-case results", "", "```json", json.dumps(payload["records"], indent=2, sort_keys=True), "```", "", "This is an offline synthetic robustness board, not a language, multimodal, Qwen, live-authority, or OS-G7 result.", ""])
    return "\n".join(lines)


def run(output_dir: Path, device_name: str | None = None) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    device = torch.device(device_name or ("cuda" if torch.cuda.is_available() else "cpu"))
    records = [_run_case(family, seed, output_dir, device) for family in ("native", "off-family") for seed in CASE_SEEDS]
    aggregates = [_aggregate(records, family) for family in ("native", "off-family")]
    mechanical_failures = []
    for record in records:
        if not _finite(record):
            mechanical_failures.append(f"non-finite record: {record['family']} seed {record['seed']}")
        if float(record["full"]["roundtrip_max_abs_diff"]) > 1.0e-6:  # type: ignore[index]
            mechanical_failures.append(f"full checkpoint round-trip mismatch: {record['family']} seed {record['seed']}")
    clean_all = all(item["clean_verdict"] == "SUPPORTS" for item in aggregates)
    noise_all = all(item["noise_verdict"] == "SUPPORTS" for item in aggregates)
    gru_all = all(item["gru_verdict"] == "SUPPORTS" for item in aggregates)
    overall = "FAIL" if mechanical_failures else ("SUPPORTS" if clean_all and noise_all and gru_all else ("EMERGES" if clean_all else "NULL"))
    payload: dict[str, object] = {
        "schema": ROBUSTNESS_SCHEMA,
        "preregistration": str(DESIGN_DIR / "FULL-WORLD-MODEL-ROBUSTNESS-PREREG.md"),
        "preregistration_sha256": _sha256(DESIGN_DIR / "FULL-WORLD-MODEL-ROBUSTNESS-PREREG.md"),
        "script_sha256": _sha256(Path(__file__)),
        "device": str(device),
        "noise_sigma": NOISE_SIGMA,
        "records": records,
        "aggregates": aggregates,
        "mechanical_failures": mechanical_failures,
        "overall_verdict": overall,
    }
    (output_dir / "full-world-model-robustness.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "FULL-WORLD-MODEL-ROBUSTNESS-REPORT.md").write_text(_render_report(payload), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR / "full-world-model-robustness")
    parser.add_argument("--device", default=None)
    parser.add_argument("--require-supports", action="store_true")
    args = parser.parse_args()
    try:
        payload = run(args.output_dir, args.device)
    except Exception as exc:
        print(json.dumps({"verdict": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 1
    print(json.dumps({"verdict": payload["overall_verdict"], "aggregates": payload["aggregates"], "mechanical_failures": payload["mechanical_failures"]}, indent=2, sort_keys=True))
    if payload["overall_verdict"] == "FAIL" or (args.require_supports and payload["overall_verdict"] != "SUPPORTS"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
