"""Deterministic L28 field-world-model board.

The board is intentionally synthetic and narrow: it tests whether a trainable
projector/readout around the fixed native-parity Cassi recurrence identifies a
held-out deterministic dynamical family.  It is not a language-quality or
agent-quality benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import torch
from torch import Tensor, nn

from cassi_fi_paths import ARTIFACT_DIR, DESIGN_DIR

from cassi_modal_torch import (
    MODE_LAYOUT_ID,
    OPERATOR_PROFILE_ID,
    CassiModalConfig,
    cassi_modal_forward,
    cassi_modal_forward_parallel,
    native_mode_params,
)


BOARD_SCHEMA = "cassi.l28.field-world-model.v1"
GENERATOR_SEED = 20260822
TRAINING_SEED = 20260823
OPTIMIZATION_SEED = 20260824
OPTIMIZER_UPDATES = 400
OPTIMIZER_LR = 0.03
OPTIMIZER_WEIGHT_DECAY = 0.0001
TRAIN_EPISODES = tuple(range(0, 48))
VALIDATION_EPISODES = tuple(range(48, 64))
TEST_EPISODES = tuple(range(64, 80))


@dataclass(frozen=True)
class WorldSpec:
    observation_dim: int = 6
    target_dim: int = 3
    horizon: int = 24
    mode_count: int = 8
    layer_count: int = 1
    sequence_count: int = 1

    @property
    def state_dim(self) -> int:
        return 8 * self.mode_count


@dataclass(frozen=True)
class Episode:
    seed: int
    observations: Tensor
    targets: Tensor


@dataclass(frozen=True)
class WorldConstants:
    projector: Tensor
    readout: Tensor
    bias: Tensor
    mode_params: Tensor
    fingerprint: str


class FieldWorldModel(nn.Module):
    def __init__(self, spec: WorldSpec, config: CassiModalConfig) -> None:
        super().__init__()
        self.spec = spec
        self.config = config
        self.projector = nn.Linear(spec.observation_dim, 2 * spec.mode_count)
        self.readout = nn.Linear(2 * spec.mode_count, spec.target_dim)

    def _layer_modes(self, observations: Tensor) -> Tensor:
        # observations is [T, observation_dim]; native modal input is [2*M, L, T].
        projected = self.projector(observations)
        return projected.transpose(0, 1).reshape(2 * self.spec.mode_count, 1, observations.shape[0])

    def forward_batch(self, observations: Tensor, initial_state: Tensor | None = None) -> tuple[Tensor, Tensor]:
        if observations.ndim != 3 or observations.shape[2] != self.spec.observation_dim:
            raise ValueError("observations must have shape [B, T, observation_dim]")
        batch_size, horizon, _ = observations.shape
        projected = self.projector(observations.reshape(batch_size * horizon, -1))
        # Parallel path keeps token-major sequence routing but loops only over
        # temporal steps, not over every flattened token.
        layer_modes = projected.reshape(batch_size, horizon, -1).permute(2, 0, 1).unsqueeze(1)
        if initial_state is None:
            initial_state = observations.new_zeros(self.spec.state_dim, batch_size)
        if initial_state.shape != (self.spec.state_dim, batch_size):
            raise ValueError("initial_state must have shape [8*M, B]")
        output = cassi_modal_forward_parallel(
            layer_modes,
            initial_state,
            self._mode_params(observations),
            self.config,
        )
        correction = output.correction.permute(1, 2, 0)
        return self.readout(correction), output.state

    def forward(self, observations: Tensor, initial_state: Tensor | None = None) -> tuple[Tensor, Tensor]:
        if observations.ndim != 2 or observations.shape[1] != self.spec.observation_dim:
            raise ValueError("observations must have shape [T, observation_dim]")
        if initial_state is not None and initial_state.shape != (self.spec.state_dim, 1):
            raise ValueError("initial_state must have shape [8*M, 1]")
        predictions, state = self.forward_batch(observations.unsqueeze(0), initial_state)
        return predictions[0], state

    def _mode_params(self, reference: Tensor) -> Tensor:
        return native_mode_params(
            self.spec.mode_count,
            dtype=reference.dtype,
            device=reference.device,
        )

    def reset_prediction(self, observations: Tensor) -> Tensor:
        predictions: list[Tensor] = []
        state = observations.new_zeros(self.spec.state_dim, 1)
        for event in observations:
            one = event.reshape(1, -1)
            modes = self._layer_modes(one)
            output = cassi_modal_forward(
                modes,
                state.new_zeros(state.shape),
                self._mode_params(observations),
                torch.zeros(1, dtype=torch.int64, device=observations.device),
                self.config,
            )
            predictions.append(self.readout(output.correction[:, 0].reshape(1, -1)).reshape(-1))
        return torch.stack(predictions)


class StatelessWorldModel(nn.Module):
    def __init__(self, spec: WorldSpec) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(spec.observation_dim, 12),
            nn.Tanh(),
            nn.Linear(12, spec.target_dim),
        )

    def forward(self, observations: Tensor) -> Tensor:
        return self.net(observations)


class GRUWorldModel(nn.Module):
    def __init__(self, spec: WorldSpec) -> None:
        super().__init__()
        self.gru = nn.GRU(spec.observation_dim, 4, batch_first=True)
        self.readout = nn.Linear(4, spec.target_dim)

    def forward(self, observations: Tensor) -> Tensor:
        if observations.ndim == 2:
            sequence, _ = self.gru(observations.unsqueeze(0))
            return self.readout(sequence.squeeze(0))
        if observations.ndim == 3:
            sequence, _ = self.gru(observations)
            return self.readout(sequence)
        raise ValueError("observations must have shape [T, D] or [B, T, D]")

def _seeded_generator(seed: int) -> torch.Generator:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    return generator


def make_world_constants(spec: WorldSpec, seed: int = GENERATOR_SEED) -> WorldConstants:
    generator = _seeded_generator(seed)
    projector = torch.randn(2 * spec.mode_count, spec.observation_dim, generator=generator, dtype=torch.float32) * 0.55
    readout = torch.randn(spec.target_dim, 2 * spec.mode_count, generator=generator, dtype=torch.float32) * 0.42
    bias = torch.randn(spec.target_dim, generator=generator, dtype=torch.float32) * 0.03
    mode_params = native_mode_params(spec.mode_count, dtype=torch.float32)
    digest = hashlib.sha256()
    for tensor in (projector, readout, bias, mode_params):
        digest.update(tensor.numpy().tobytes())
    return WorldConstants(projector, readout, bias, mode_params, digest.hexdigest())


def _episode_observations(seed: int, spec: WorldSpec) -> Tensor:
    generator = _seeded_generator(GENERATOR_SEED + 7919 * (seed + 1))
    observations = torch.randn(spec.horizon, spec.observation_dim, generator=generator, dtype=torch.float32)
    # The first two channels carry smooth event-time structure; the remaining
    # channels stay stochastic so the task is not a one-dimensional lookup.
    time = torch.arange(spec.horizon, dtype=torch.float32)
    observations[:, 0] += 0.35 * torch.sin(time * 0.37 + seed * 0.11)
    observations[:, 1] += 0.25 * torch.cos(time * 0.19 - seed * 0.07)
    return observations


def generate_episode(seed: int, spec: WorldSpec, world: WorldConstants) -> Episode:
    observations = _episode_observations(seed, spec)
    layer_modes = torch.einsum("md,td->mt", world.projector, observations).reshape(2 * spec.mode_count, 1, spec.horizon)
    state = torch.zeros(spec.state_dim, 1, dtype=torch.float32)
    output = cassi_modal_forward(
        layer_modes,
        state,
        world.mode_params,
        torch.zeros(spec.horizon, dtype=torch.int64),
        CassiModalConfig(),
    )
    targets = output.correction.transpose(0, 1) @ world.readout.T + world.bias
    return Episode(seed, observations, targets)


def make_dataset(spec: WorldSpec = WorldSpec()) -> tuple[WorldConstants, dict[int, Episode]]:
    world = make_world_constants(spec)
    episodes = {seed: generate_episode(seed, spec, world) for seed in range(80)}
    return world, episodes

def parameter_count(module: nn.Module) -> int:
    return sum(parameter.numel() for parameter in module.parameters())


def _mse(predictions: Iterable[Tensor], targets: Iterable[Tensor]) -> float:
    values = [torch.mean((prediction - target) ** 2).item() for prediction, target in zip(predictions, targets)]
    return float(np.mean(values))


def _train_field(episodes: list[Episode], spec: WorldSpec, config: CassiModalConfig) -> FieldWorldModel:
    model = FieldWorldModel(spec, config)
    observations = torch.stack([episode.observations for episode in episodes])
    targets = torch.stack([episode.targets for episode in episodes])
    optimizer = torch.optim.AdamW(model.parameters(), lr=OPTIMIZER_LR, weight_decay=OPTIMIZER_WEIGHT_DECAY)
    for _ in range(OPTIMIZER_UPDATES):
        optimizer.zero_grad(set_to_none=True)
        prediction, _ = model.forward_batch(observations)
        loss = torch.mean((prediction - targets) ** 2)
        loss.backward()
        optimizer.step()
    return model


def _train_stateless(episodes: list[Episode], spec: WorldSpec) -> StatelessWorldModel:
    model = StatelessWorldModel(spec)
    observations = torch.stack([episode.observations for episode in episodes])
    targets = torch.stack([episode.targets for episode in episodes])
    optimizer = torch.optim.AdamW(model.parameters(), lr=OPTIMIZER_LR, weight_decay=OPTIMIZER_WEIGHT_DECAY)
    for _ in range(OPTIMIZER_UPDATES):
        optimizer.zero_grad(set_to_none=True)
        loss = torch.mean((model(observations) - targets) ** 2)
        loss.backward()
        optimizer.step()
    return model


def _train_gru(episodes: list[Episode], spec: WorldSpec) -> GRUWorldModel:
    model = GRUWorldModel(spec)
    observations = torch.stack([episode.observations for episode in episodes])
    targets = torch.stack([episode.targets for episode in episodes])
    optimizer = torch.optim.AdamW(model.parameters(), lr=OPTIMIZER_LR, weight_decay=OPTIMIZER_WEIGHT_DECAY)
    for _ in range(OPTIMIZER_UPDATES):
        optimizer.zero_grad(set_to_none=True)
        loss = torch.mean((model(observations) - targets) ** 2)
        loss.backward()
        optimizer.step()
    return model


def _digest_state(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def _field_predictions(model: FieldWorldModel, episodes: list[Episode], mode: str) -> list[Tensor]:
    with torch.no_grad():
        if mode == "field":
            return [model(ep.observations)[0] for ep in episodes]
        if mode == "reset":
            return [model.reset_prediction(ep.observations) for ep in episodes]
        if mode != "shuffled":
            raise ValueError(f"unknown field prediction mode: {mode}")

        batch = torch.stack([ep.observations for ep in episodes])
        batch_size, horizon, _ = batch.shape
        state = batch.new_zeros(model.spec.state_dim, batch_size)
        outputs: list[Tensor] = []
        sequence_ids = torch.arange(batch_size, dtype=torch.int64)
        for time in range(horizon):
            projected = model.projector(batch[:, time, :]).transpose(0, 1).unsqueeze(1)
            output = cassi_modal_forward(
                projected,
                state,
                model._mode_params(batch),
                sequence_ids,
                model.config,
            )
            outputs.append(model.readout(output.correction.transpose(0, 1)))
            state = output.state[:, torch.arange(batch_size - 1, -1, -1)]
        return [torch.stack([outputs[time][batch_index] for time in range(horizon)]) for batch_index in range(batch_size)]


def _model_predictions(model: nn.Module, episodes: list[Episode]) -> list[Tensor]:
    with torch.no_grad():
        if isinstance(model, FieldWorldModel):
            return _field_predictions(model, episodes, "field")
        return [model(ep.observations) for ep in episodes]


def _metrics(model: nn.Module, episodes: list[Episode]) -> float:
    return _mse(_model_predictions(model, episodes), (ep.targets for ep in episodes))


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _data_bounds(episodes: Iterable[Episode]) -> tuple[float, float, bool]:
    max_observation = 0.0
    max_target = 0.0
    finite = True
    for episode in episodes:
        max_observation = max(max_observation, float(episode.observations.abs().max()))
        max_target = max(max_target, float(episode.targets.abs().max()))
        finite = finite and bool(torch.isfinite(episode.observations).all().item())
        finite = finite and bool(torch.isfinite(episode.targets).all().item())
    return max_observation, max_target, finite


def _trajectory_bounds(model: FieldWorldModel, episodes: list[Episode]) -> tuple[float, float, bool]:
    max_state = 0.0
    max_power = 0.0
    finite = True
    with torch.no_grad():
        for episode in episodes:
            _, state = model(episode.observations)
            max_state = max(max_state, float(state.abs().max()))
            ey_re, ey_im, ei_re, ei_im = state[0::8], state[1::8], state[2::8], state[3::8]
            max_power = max(max_power, float((ey_re.square() + ey_im.square() + ei_re.square() + ei_im.square()).max()))
            finite = finite and bool(torch.isfinite(state).all().item())
    return max_state, max_power, finite


def _write_checkpoint(
    path: Path,
    model: FieldWorldModel,
    spec: WorldSpec,
    world: WorldConstants,
    manifest_sha256: str,
) -> str:
    payload = {
        "schema": "cassi.l28.field-checkpoint.v1",
        "mode_layout_id": MODE_LAYOUT_ID,
        "operator_profile_id": OPERATOR_PROFILE_ID,
        "world_fingerprint": world.fingerprint,
        "manifest_sha256": manifest_sha256,
        "spec": asdict(spec),
        "config": asdict(model.config),
        "parameter_count": parameter_count(model),
        "model_state": model.state_dict(),
    }
    torch.save(payload, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def train_board(out_dir: Path) -> dict:
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(TRAINING_SEED)
    spec = WorldSpec()
    config = CassiModalConfig()
    world, episodes = make_dataset(spec)
    train = [episodes[seed] for seed in TRAIN_EPISODES]
    validation = [episodes[seed] for seed in VALIDATION_EPISODES]
    test = [episodes[seed] for seed in TEST_EPISODES]

    # TRAINING_SEED records the deterministic execution environment. The
    # independently named optimization seed controls every learner's
    # initialization so the duplicate run is an exact replay.
    torch.manual_seed(OPTIMIZATION_SEED)
    field = _train_field(train, spec, config)
    torch.manual_seed(OPTIMIZATION_SEED + 1)
    stateless = _train_stateless(train, spec)
    torch.manual_seed(OPTIMIZATION_SEED + 2)
    gru = _train_gru(train, spec)

    arms = {
        "field": {
            "parameters": parameter_count(field),
            "train_mse": _metrics(field, train),
            "validation_mse": _metrics(field, validation),
            "test_mse": _metrics(field, test),
        },
        "stateless": {
            "parameters": parameter_count(stateless),
            "train_mse": _metrics(stateless, train),
            "validation_mse": _metrics(stateless, validation),
            "test_mse": _metrics(stateless, test),
        },
        "gru": {
            "parameters": parameter_count(gru),
            "train_mse": _metrics(gru, train),
            "validation_mse": _metrics(gru, validation),
            "test_mse": _metrics(gru, test),
        },
    }
    reset_test = _field_predictions(field, test, "reset")
    shuffled_test = _field_predictions(field, test, "shuffled")
    arms["field-reset"] = {
        "parameters": parameter_count(field),
        "test_mse": _mse(reset_test, (ep.targets for ep in test)),
    }
    arms["field-shuffled"] = {
        "parameters": parameter_count(field),
        "test_mse": _mse(shuffled_test, (ep.targets for ep in test)),
    }

    state_episodes = train + test
    max_state, max_power, finite = _trajectory_bounds(field, state_episodes)
    max_observation, max_target, data_finite = _data_bounds(episodes.values())
    out_dir.mkdir(parents=True, exist_ok=True)

    code_digests = {
        "field_world_model.py": _file_sha256(Path(__file__)),
        "cassi_modal_torch.py": _file_sha256(Path(__file__).with_name("cassi_modal_torch.py")),
        "L28-FIELD-WORLD-MODEL-PREREG.md": _file_sha256(
            DESIGN_DIR / "L28-FIELD-WORLD-MODEL-PREREG.md"
        ),
    }
    manifest = {
        "schema": "cassi.l28.field-manifest.v1",
        "board_schema": BOARD_SCHEMA,
        "generator_seed": GENERATOR_SEED,
        "training_seed": TRAINING_SEED,
        "optimization_seed": OPTIMIZATION_SEED,
        "optimizer": {
            "updates": OPTIMIZER_UPDATES,
            "learning_rate": OPTIMIZER_LR,
            "weight_decay": OPTIMIZER_WEIGHT_DECAY,
        },
        "mode_layout_id": MODE_LAYOUT_ID,
        "operator_profile_id": OPERATOR_PROFILE_ID,
        "config": asdict(config),
        "spec": asdict(spec),
        "world_fingerprint": world.fingerprint,
        "splits": {
            "train": list(TRAIN_EPISODES),
            "validation": list(VALIDATION_EPISODES),
            "test": list(TEST_EPISODES),
        },
        "code_digests": code_digests,
    }
    manifest_path = out_dir / "l28-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha256 = _file_sha256(manifest_path)

    checkpoint_path = out_dir / "l28-field.pt"
    checkpoint_sha256 = _write_checkpoint(checkpoint_path, field, spec, world, manifest_sha256)

    # A duplicate primary training run is a deterministic state-digest check,
    # not an additional hyperparameter search or candidate selection pass.
    torch.manual_seed(OPTIMIZATION_SEED)
    duplicate = _train_field(train, spec, config)
    primary_digest = _digest_state(field)
    duplicate_digest = _digest_state(duplicate)
    board = {
        "schema": BOARD_SCHEMA,
        "status": "COMPLETE",
        "generator_seed": GENERATOR_SEED,
        "training_seed": TRAINING_SEED,
        "optimization_seed": OPTIMIZATION_SEED,
        "optimizer": {
            "updates": OPTIMIZER_UPDATES,
            "learning_rate": OPTIMIZER_LR,
            "weight_decay": OPTIMIZER_WEIGHT_DECAY,
        },
        "mode_layout_id": MODE_LAYOUT_ID,
        "operator_profile_id": OPERATOR_PROFILE_ID,
        "config": asdict(config),
        "spec": asdict(spec),
        "world_fingerprint": world.fingerprint,
        "splits": {
            "train": list(TRAIN_EPISODES),
            "validation": list(VALIDATION_EPISODES),
            "test": list(TEST_EPISODES),
        },
        "parameter_counts": {name: data["parameters"] for name, data in arms.items()},
        "arms": arms,
        "code_digests": code_digests,
        "manifest": {"path": str(manifest_path), "sha256": manifest_sha256},
        "mechanical": {
            "finite": finite,
            "data_finite": data_finite,
            "max_abs_observation": max_observation,
            "max_abs_target": max_target,
            "data_bound": 100.0,
            "max_abs_state": max_state,
            "max_state_power": max_power,
            "state_bound": 100.0,
            "primary_state_digest": primary_digest,
            "duplicate_state_digest": duplicate_digest,
            "duplicate_match": primary_digest == duplicate_digest,
            "test_seed_overlap": bool(set(TRAIN_EPISODES) & set(TEST_EPISODES)),
            "trajectory_episodes": {"train": len(train), "test": len(test)},
        },
        "checkpoint": {"path": str(checkpoint_path), "sha256": checkpoint_sha256},
    }
    board_path = out_dir / "l28-board.json"
    board_path.write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    return board


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ARTIFACT_DIR / "l28-field-world-model")
    args = parser.parse_args()
    board = train_board(args.out_dir)
    print(json.dumps({"board": str(args.out_dir / "l28-board.json"), "field_test_mse": board["arms"]["field"]["test_mse"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
