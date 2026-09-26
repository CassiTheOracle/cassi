"""Production field-native stochastic world model for Cassi.

The model uses the differentiable native-parity Cassi modal recurrence as its
persistent deterministic state transition.  A learned stochastic latent carries
uncertainty around that field state.  During observation, an encoder supplies a
posterior; during imagination, only the learned prior and proposed actions are
available.

Trajectory timing is explicit: ``actions[:, t]`` is the action leading into
``observations[:, t]``.  A true ``resets[:, t]`` clears state before that
transition.  A false ``valid[:, t]`` preserves state and excludes that step from
all losses.
"""

from __future__ import annotations

from io import BytesIO

import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, NamedTuple

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from cassi_modal_torch import (
    MODE_LAYOUT_ID,
    OPERATOR_PROFILE_ID,
    CassiModalConfig,
    cassi_modal_forward_parallel,
    native_mode_params,
)


MODEL_CONFIG_SCHEMA = "cassi.world-model.config.v1"
MODEL_CHECKPOINT_SCHEMA = "cassi.world-model.checkpoint.v1"
RUNTIME_STATE_SCHEMA = "cassi.world-model.runtime-state.v1"
MAX_RUNTIME_STATE_BYTES = 64 * 1024 * 1024



class CassiWorldModelError(ValueError):
    """Invalid model configuration, trajectory, state, or persisted artifact."""


def _positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CassiWorldModelError(f"{name} must be a positive integer")


def _finite_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise CassiWorldModelError(f"{name} must be positive and finite")


def _finite_nonnegative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise CassiWorldModelError(f"{name} must be non-negative and finite")


@dataclass(frozen=True)
class CassiWorldModelConfig:
    """Architecture and native recurrence identity for one world model."""

    observation_dim: int
    action_dim: int
    reward_dim: int = 1
    mode_count: int = 32
    latent_dim: int = 64
    model_dim: int = 256
    hidden_dim: int = 256
    mlp_layers: int = 2
    min_std: float = 0.05
    max_std: float = 2.0
    modal: CassiModalConfig = field(default_factory=CassiModalConfig)

    def __post_init__(self) -> None:
        for name in (
            "observation_dim",
            "action_dim",
            "reward_dim",
            "mode_count",
            "latent_dim",
            "model_dim",
            "hidden_dim",
            "mlp_layers",
        ):
            _positive_int(name, getattr(self, name))
        _finite_positive("min_std", self.min_std)
        _finite_positive("max_std", self.max_std)
        if self.max_std < self.min_std:
            raise CassiWorldModelError("max_std must be greater than or equal to min_std")
        if not isinstance(self.modal, CassiModalConfig):
            raise CassiWorldModelError("modal must be a CassiModalConfig")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CassiWorldModelConfig":
        if not isinstance(value, Mapping):
            raise CassiWorldModelError("model configuration must be a mapping")
        payload = dict(value)
        modal_value = payload.pop("modal", None)
        if modal_value is None:
            modal = CassiModalConfig()
        elif isinstance(modal_value, Mapping):
            try:
                modal = CassiModalConfig(**dict(modal_value))
            except (TypeError, ValueError) as exc:
                raise CassiWorldModelError(f"invalid modal configuration: {exc}") from exc
        else:
            raise CassiWorldModelError("modal configuration must be a mapping")
        try:
            return cls(modal=modal, **payload)
        except (TypeError, ValueError) as exc:
            raise CassiWorldModelError(f"invalid world-model configuration: {exc}") from exc

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CassiWorldModelLossConfig:
    """Weights and KL controls for world-model optimization."""

    observation_weight: float = 1.0
    reward_weight: float = 1.0
    continuation_weight: float = 1.0
    kl_weight: float = 1.0
    kl_balance: float = 0.8
    free_nats: float = 1.0

    def __post_init__(self) -> None:
        for name in ("observation_weight", "reward_weight", "continuation_weight", "kl_weight", "free_nats"):
            _finite_nonnegative(name, getattr(self, name))
        if not math.isfinite(self.kl_balance) or not 0.0 <= self.kl_balance <= 1.0:
            raise CassiWorldModelError("kl_balance must be finite and in [0, 1]")

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CassiWorldModelLossConfig":
        if not isinstance(value, Mapping):
            raise CassiWorldModelError("loss configuration must be a mapping")
        try:
            return cls(**dict(value))
        except (TypeError, ValueError) as exc:
            raise CassiWorldModelError(f"invalid loss configuration: {exc}") from exc


@dataclass(frozen=True)
class CassiTrajectoryBatch:
    """A padded batch of aligned world trajectories."""

    observations: Tensor
    actions: Tensor
    rewards: Tensor
    continues: Tensor
    valid: Tensor
    resets: Tensor

    @property
    def batch_size(self) -> int:
        return int(self.observations.shape[0])

    @property
    def horizon(self) -> int:
        return int(self.observations.shape[1])

    def validate(self, config: CassiWorldModelConfig) -> None:
        if self.observations.ndim != 3 or self.observations.shape[2] != config.observation_dim:
            raise CassiWorldModelError("observations must have shape [B, T, observation_dim]")
        batch_size, horizon, _ = self.observations.shape
        if batch_size < 1 or horizon < 1:
            raise CassiWorldModelError("trajectory batches require B >= 1 and T >= 1")
        if self.actions.shape != (batch_size, horizon, config.action_dim):
            raise CassiWorldModelError("actions must have shape [B, T, action_dim]")
        if self.rewards.shape != (batch_size, horizon, config.reward_dim):
            raise CassiWorldModelError("rewards must have shape [B, T, reward_dim]")
        if self.continues.shape != (batch_size, horizon):
            raise CassiWorldModelError("continues must have shape [B, T]")
        if self.valid.shape != (batch_size, horizon) or self.resets.shape != (batch_size, horizon):
            raise CassiWorldModelError("valid and resets must have shape [B, T]")
        if self.valid.dtype != torch.bool or self.resets.dtype != torch.bool:
            raise CassiWorldModelError("valid and resets must be boolean tensors")

        floating = (self.observations, self.actions, self.rewards, self.continues)
        if not self.observations.dtype.is_floating_point:
            raise CassiWorldModelError("trajectory values must use a floating dtype")
        if any(tensor.dtype != self.observations.dtype for tensor in floating):
            raise CassiWorldModelError("all trajectory values must share one floating dtype")
        device = self.observations.device
        if any(tensor.device != device for tensor in (*floating, self.valid, self.resets)):
            raise CassiWorldModelError("all trajectory tensors must share one device")
        if not all(bool(torch.isfinite(tensor).all().item()) for tensor in floating):
            raise CassiWorldModelError("trajectory values must be finite")
        if bool(torch.any(self.continues < 0.0).item()) or bool(torch.any(self.continues > 1.0).item()):
            raise CassiWorldModelError("continues must be in [0, 1]")
        if bool(torch.any(self.resets & ~self.valid).item()):
            raise CassiWorldModelError("a reset cannot occur on an invalid time step")
        if not bool(torch.any(self.valid).item()):
            raise CassiWorldModelError("trajectory batch has no valid time steps")

    def to(self, device: torch.device | str, *, dtype: torch.dtype | None = None) -> "CassiTrajectoryBatch":
        target_dtype = dtype or self.observations.dtype
        return CassiTrajectoryBatch(
            observations=self.observations.to(device=device, dtype=target_dtype),
            actions=self.actions.to(device=device, dtype=target_dtype),
            rewards=self.rewards.to(device=device, dtype=target_dtype),
            continues=self.continues.to(device=device, dtype=target_dtype),
            valid=self.valid.to(device=device),
            resets=self.resets.to(device=device),
        )

    def index_select(self, indices: Tensor) -> "CassiTrajectoryBatch":
        if indices.ndim != 1 or indices.dtype != torch.int64:
            raise CassiWorldModelError("trajectory indices must be a one-dimensional int64 tensor")
        return CassiTrajectoryBatch(
            observations=self.observations.index_select(0, indices),
            actions=self.actions.index_select(0, indices),
            rewards=self.rewards.index_select(0, indices),
            continues=self.continues.index_select(0, indices),
            valid=self.valid.index_select(0, indices),
            resets=self.resets.index_select(0, indices),
        )


@dataclass(frozen=True)
class CassiWorldModelState:
    """Persistent per-sequence field and stochastic state."""

    field: Tensor
    stochastic: Tensor
    step: Tensor

    @property
    def batch_size(self) -> int:
        return int(self.stochastic.shape[0])

    def validate(self, config: CassiWorldModelConfig, *, device: torch.device | None = None, dtype: torch.dtype | None = None) -> None:
        if self.field.ndim != 2 or self.field.shape[0] != 8 * config.mode_count:
            raise CassiWorldModelError("field state must have shape [8*M, B]")
        batch_size = self.field.shape[1]
        if self.stochastic.shape != (batch_size, config.latent_dim):
            raise CassiWorldModelError("stochastic state must have shape [B, latent_dim]")
        if self.step.shape != (batch_size,) or self.step.dtype != torch.int64:
            raise CassiWorldModelError("step state must have shape [B] and dtype int64")
        if not self.field.dtype.is_floating_point or self.stochastic.dtype != self.field.dtype:
            raise CassiWorldModelError("field and stochastic state must share one floating dtype")
        if self.field.device != self.stochastic.device or self.field.device != self.step.device:
            raise CassiWorldModelError("all state tensors must share one device")
        if device is not None and self.field.device != device:
            raise CassiWorldModelError("state device does not match the model")
        if dtype is not None and self.field.dtype != dtype:
            raise CassiWorldModelError("state dtype does not match the model")
        if not bool(torch.isfinite(self.field).all().item()) or not bool(torch.isfinite(self.stochastic).all().item()):
            raise CassiWorldModelError("world-model state must be finite")
        if bool(torch.any(self.step < 0).item()):
            raise CassiWorldModelError("world-model step counters cannot be negative")

    def detach(self) -> "CassiWorldModelState":
        return CassiWorldModelState(self.field.detach(), self.stochastic.detach(), self.step.detach())

    def clone(self) -> "CassiWorldModelState":
        return CassiWorldModelState(self.field.clone(), self.stochastic.clone(), self.step.clone())


@dataclass(frozen=True)
class CassiWorldModelStep:
    observation_mean: Tensor
    observation_log_std: Tensor
    reward_mean: Tensor
    reward_log_std: Tensor
    continue_logits: Tensor
    prior_mean: Tensor
    prior_log_std: Tensor
    posterior_mean: Tensor | None
    posterior_log_std: Tensor | None
    field_correction: Tensor
    features: Tensor
    state: CassiWorldModelState


@dataclass(frozen=True)
class CassiWorldModelOutput:
    observation_mean: Tensor
    observation_log_std: Tensor
    reward_mean: Tensor
    reward_log_std: Tensor
    continue_logits: Tensor
    prior_mean: Tensor
    prior_log_std: Tensor
    posterior_mean: Tensor | None
    posterior_log_std: Tensor | None
    field_correction: Tensor
    features: Tensor
    final_state: CassiWorldModelState


class CassiWorldModelLoss(NamedTuple):
    total: Tensor
    observation_nll: Tensor
    reward_nll: Tensor
    continuation_bce: Tensor
    kl: Tensor
    observation_mse: Tensor
    reward_mse: Tensor

    def detached_metrics(self) -> dict[str, float]:
        return {name: float(value.detach().cpu().item()) for name, value in self._asdict().items()}


def _mlp(input_dim: int, output_dim: int, hidden_dim: int, layers: int) -> nn.Sequential:
    modules: list[nn.Module] = []
    current = input_dim
    for _ in range(layers):
        modules.extend((nn.Linear(current, hidden_dim), nn.SiLU()))
        current = hidden_dim
    modules.append(nn.Linear(current, output_dim))
    return nn.Sequential(*modules)


class CassiWorldModel(nn.Module):
    """Field-native recurrent state-space model with observe and imagine paths."""

    def __init__(self, config: CassiWorldModelConfig) -> None:
        super().__init__()
        self.config = config
        mode_count = config.mode_count
        latent_dim = config.latent_dim
        model_dim = config.model_dim

        self.observation_encoder = nn.Sequential(
            nn.LayerNorm(config.observation_dim),
            _mlp(config.observation_dim, model_dim, config.hidden_dim, config.mlp_layers),
        )
        self.transition_projector = _mlp(
            latent_dim + config.action_dim,
            2 * mode_count,
            config.hidden_dim,
            config.mlp_layers,
        )
        self.field_feature_projector = nn.Sequential(
            nn.LayerNorm(10 * mode_count),
            _mlp(10 * mode_count, model_dim, config.hidden_dim, config.mlp_layers),
        )
        self.prior = _mlp(
            model_dim + config.action_dim,
            2 * latent_dim,
            config.hidden_dim,
            config.mlp_layers,
        )
        self.posterior = _mlp(
            model_dim + model_dim,
            2 * latent_dim,
            config.hidden_dim,
            config.mlp_layers,
        )
        feature_dim = model_dim + latent_dim
        self.observation_head = _mlp(
            feature_dim,
            2 * config.observation_dim,
            config.hidden_dim,
            config.mlp_layers,
        )
        self.reward_head = _mlp(
            feature_dim,
            2 * config.reward_dim,
            config.hidden_dim,
            config.mlp_layers,
        )
        self.continuation_head = _mlp(feature_dim, 1, config.hidden_dim, config.mlp_layers)
        self.register_buffer("mode_params", native_mode_params(mode_count, dtype=torch.float32), persistent=True)

    @property
    def config_fingerprint(self) -> str:
        return self.config.fingerprint

    @property
    def feature_dim(self) -> int:
        return self.config.model_dim + self.config.latent_dim

    def _reference(self) -> Tensor:
        return next(self.parameters())

    def initial_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> CassiWorldModelState:
        _positive_int("batch_size", batch_size)
        reference = self._reference()
        target_device = torch.device(device) if device is not None else reference.device
        target_dtype = dtype or reference.dtype
        if not target_dtype.is_floating_point:
            raise CassiWorldModelError("world-model state requires a floating dtype")
        return CassiWorldModelState(
            field=torch.zeros(8 * self.config.mode_count, batch_size, device=target_device, dtype=target_dtype),
            stochastic=torch.zeros(batch_size, self.config.latent_dim, device=target_device, dtype=target_dtype),
            step=torch.zeros(batch_size, device=target_device, dtype=torch.int64),
        )

    def _validate_step_inputs(
        self,
        action: Tensor,
        state: CassiWorldModelState,
        valid: Tensor,
        reset: Tensor,
        observation: Tensor | None,
    ) -> None:
        reference = self._reference()
        state.validate(self.config, device=reference.device, dtype=reference.dtype)
        batch_size = state.batch_size
        if action.shape != (batch_size, self.config.action_dim):
            raise CassiWorldModelError("step action must have shape [B, action_dim]")
        if observation is not None and observation.shape != (batch_size, self.config.observation_dim):
            raise CassiWorldModelError("step observation must have shape [B, observation_dim]")
        if valid.shape != (batch_size,) or reset.shape != (batch_size,):
            raise CassiWorldModelError("step valid and reset masks must have shape [B]")
        if valid.dtype != torch.bool or reset.dtype != torch.bool:
            raise CassiWorldModelError("step valid and reset masks must be boolean")
        tensors = (action, valid, reset) if observation is None else (action, observation, valid, reset)
        if any(tensor.device != reference.device for tensor in tensors):
            raise CassiWorldModelError("step inputs must be on the model device")
        values = (action,) if observation is None else (action, observation)
        if any(tensor.dtype != reference.dtype for tensor in values):
            raise CassiWorldModelError("step values must use the model dtype")
        if not all(bool(torch.isfinite(tensor).all().item()) for tensor in values):
            raise CassiWorldModelError("step values must be finite")
        if bool(torch.any(reset & ~valid).item()):
            raise CassiWorldModelError("a reset cannot occur on an invalid step")

    def _distribution_stats(self, raw: Tensor) -> tuple[Tensor, Tensor]:
        mean, scale = raw.chunk(2, dim=-1)
        min_log_std = math.log(self.config.min_std)
        max_log_std = math.log(self.config.max_std)
        log_std = min_log_std + torch.sigmoid(scale) * (max_log_std - min_log_std)
        return mean, log_std

    @staticmethod
    def _sample(mean: Tensor, log_std: Tensor, sample: bool) -> Tensor:
        if not sample:
            return mean
        return mean + torch.exp(log_std) * torch.randn_like(mean)

    @staticmethod
    def _masked_rows(candidate: Tensor, previous: Tensor, active: Tensor) -> Tensor:
        mask = active.reshape(active.shape[0], *([1] * (candidate.ndim - 1)))
        return torch.where(mask, candidate, previous)

    def _transition(
        self,
        action: Tensor,
        state: CassiWorldModelState,
        valid: Tensor,
        reset: Tensor,
    ) -> tuple[Tensor, Tensor, CassiWorldModelState]:
        active_reset = valid & reset
        reset_columns = active_reset.reshape(1, state.batch_size)
        reset_rows = active_reset.reshape(state.batch_size, 1)
        field_before = torch.where(reset_columns, torch.zeros_like(state.field), state.field)
        stochastic_before = torch.where(reset_rows, torch.zeros_like(state.stochastic), state.stochastic)
        step_before = torch.where(active_reset, torch.zeros_like(state.step), state.step)

        modal_deposit = self.transition_projector(torch.cat((stochastic_before, action), dim=-1))
        modal_deposit = torch.where(valid.reshape(state.batch_size, 1), modal_deposit, torch.zeros_like(modal_deposit))
        layer_modes = modal_deposit.transpose(0, 1).unsqueeze(1).unsqueeze(-1)
        modal = cassi_modal_forward_parallel(
            layer_modes,
            field_before,
            self.mode_params,
            self.config.modal,
        )
        candidate_field = modal.state
        field_after = torch.where(valid.reshape(1, state.batch_size), candidate_field, field_before)
        correction = modal.correction[:, :, 0].transpose(0, 1)
        correction = torch.where(valid.reshape(state.batch_size, 1), correction, torch.zeros_like(correction))
        field_features = self.field_feature_projector(
            torch.cat((correction, field_after.transpose(0, 1)), dim=-1)
        )
        field_features = torch.where(valid.reshape(state.batch_size, 1), field_features, torch.zeros_like(field_features))
        transitioned = CassiWorldModelState(
            field=field_after,
            stochastic=stochastic_before,
            step=step_before + valid.to(torch.int64),
        )
        return correction, field_features, transitioned

    def _decode(self, features: Tensor, valid: Tensor) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor]:
        observation_mean, observation_log_std = self._distribution_stats(self.observation_head(features))
        reward_mean, reward_log_std = self._distribution_stats(self.reward_head(features))
        continue_logits = self.continuation_head(features).squeeze(-1)
        row_mask = valid.reshape(valid.shape[0], 1)
        observation_mean = torch.where(row_mask, observation_mean, torch.zeros_like(observation_mean))
        observation_log_std = torch.where(row_mask, observation_log_std, torch.zeros_like(observation_log_std))
        reward_mean = torch.where(row_mask, reward_mean, torch.zeros_like(reward_mean))
        reward_log_std = torch.where(row_mask, reward_log_std, torch.zeros_like(reward_log_std))
        continue_logits = torch.where(valid, continue_logits, torch.zeros_like(continue_logits))
        return observation_mean, observation_log_std, reward_mean, reward_log_std, continue_logits

    def observe_step(
        self,
        observation: Tensor,
        action: Tensor,
        state: CassiWorldModelState,
        *,
        valid: Tensor | None = None,
        reset: Tensor | None = None,
        sample: bool | None = None,
    ) -> CassiWorldModelStep:
        batch_size = state.batch_size
        valid = valid if valid is not None else torch.ones(batch_size, dtype=torch.bool, device=state.field.device)
        reset = reset if reset is not None else torch.zeros(batch_size, dtype=torch.bool, device=state.field.device)
        self._validate_step_inputs(action, state, valid, reset, observation)
        correction, field_features, transitioned = self._transition(action, state, valid, reset)

        prior_mean, prior_log_std = self._distribution_stats(self.prior(torch.cat((field_features, action), dim=-1)))
        observation_features = self.observation_encoder(observation)
        posterior_mean, posterior_log_std = self._distribution_stats(
            self.posterior(torch.cat((field_features, observation_features), dim=-1))
        )
        should_sample = self.training if sample is None else sample
        candidate_stochastic = self._sample(posterior_mean, posterior_log_std, should_sample)
        stochastic = self._masked_rows(candidate_stochastic, transitioned.stochastic, valid)
        features = torch.cat((field_features, stochastic), dim=-1)
        features = torch.where(valid.reshape(batch_size, 1), features, torch.zeros_like(features))
        decoded = self._decode(features, valid)
        next_state = CassiWorldModelState(transitioned.field, stochastic, transitioned.step)
        return CassiWorldModelStep(
            observation_mean=decoded[0],
            observation_log_std=decoded[1],
            reward_mean=decoded[2],
            reward_log_std=decoded[3],
            continue_logits=decoded[4],
            prior_mean=torch.where(valid.reshape(batch_size, 1), prior_mean, torch.zeros_like(prior_mean)),
            prior_log_std=torch.where(valid.reshape(batch_size, 1), prior_log_std, torch.zeros_like(prior_log_std)),
            posterior_mean=torch.where(valid.reshape(batch_size, 1), posterior_mean, torch.zeros_like(posterior_mean)),
            posterior_log_std=torch.where(valid.reshape(batch_size, 1), posterior_log_std, torch.zeros_like(posterior_log_std)),
            field_correction=correction,
            features=features,
            state=next_state,
        )

    def imagine_step(
        self,
        action: Tensor,
        state: CassiWorldModelState,
        *,
        valid: Tensor | None = None,
        reset: Tensor | None = None,
        sample: bool = False,
    ) -> CassiWorldModelStep:
        batch_size = state.batch_size
        valid = valid if valid is not None else torch.ones(batch_size, dtype=torch.bool, device=state.field.device)
        reset = reset if reset is not None else torch.zeros(batch_size, dtype=torch.bool, device=state.field.device)
        self._validate_step_inputs(action, state, valid, reset, None)
        correction, field_features, transitioned = self._transition(action, state, valid, reset)
        prior_mean, prior_log_std = self._distribution_stats(self.prior(torch.cat((field_features, action), dim=-1)))
        candidate_stochastic = self._sample(prior_mean, prior_log_std, sample)
        stochastic = self._masked_rows(candidate_stochastic, transitioned.stochastic, valid)
        features = torch.cat((field_features, stochastic), dim=-1)
        features = torch.where(valid.reshape(batch_size, 1), features, torch.zeros_like(features))
        decoded = self._decode(features, valid)
        next_state = CassiWorldModelState(transitioned.field, stochastic, transitioned.step)
        return CassiWorldModelStep(
            observation_mean=decoded[0],
            observation_log_std=decoded[1],
            reward_mean=decoded[2],
            reward_log_std=decoded[3],
            continue_logits=decoded[4],
            prior_mean=torch.where(valid.reshape(batch_size, 1), prior_mean, torch.zeros_like(prior_mean)),
            prior_log_std=torch.where(valid.reshape(batch_size, 1), prior_log_std, torch.zeros_like(prior_log_std)),
            posterior_mean=None,
            posterior_log_std=None,
            field_correction=correction,
            features=features,
            state=next_state,
        )

    @staticmethod
    def _stack_steps(steps: list[CassiWorldModelStep], *, posterior: bool) -> CassiWorldModelOutput:
        if not steps:
            raise CassiWorldModelError("cannot stack an empty world-model trajectory")

        def stack(name: str) -> Tensor:
            return torch.stack([getattr(step, name) for step in steps], dim=1)

        posterior_mean = None
        posterior_log_std = None
        if posterior:
            posterior_mean = torch.stack([step.posterior_mean for step in steps], dim=1)  # type: ignore[arg-type]
            posterior_log_std = torch.stack([step.posterior_log_std for step in steps], dim=1)  # type: ignore[arg-type]
        return CassiWorldModelOutput(
            observation_mean=stack("observation_mean"),
            observation_log_std=stack("observation_log_std"),
            reward_mean=stack("reward_mean"),
            reward_log_std=stack("reward_log_std"),
            continue_logits=stack("continue_logits"),
            prior_mean=stack("prior_mean"),
            prior_log_std=stack("prior_log_std"),
            posterior_mean=posterior_mean,
            posterior_log_std=posterior_log_std,
            field_correction=stack("field_correction"),
            features=stack("features"),
            final_state=steps[-1].state,
        )

    def observe(
        self,
        batch: CassiTrajectoryBatch,
        initial_state: CassiWorldModelState | None = None,
        *,
        sample: bool | None = None,
    ) -> CassiWorldModelOutput:
        batch.validate(self.config)
        reference = self._reference()
        if batch.observations.device != reference.device or batch.observations.dtype != reference.dtype:
            raise CassiWorldModelError("trajectory batch must use the model device and dtype")
        state = initial_state or self.initial_state(batch.batch_size)
        state.validate(self.config, device=reference.device, dtype=reference.dtype)
        if state.batch_size != batch.batch_size:
            raise CassiWorldModelError("initial state batch size does not match the trajectory batch")
        steps: list[CassiWorldModelStep] = []
        for time in range(batch.horizon):
            step = self.observe_step(
                batch.observations[:, time],
                batch.actions[:, time],
                state,
                valid=batch.valid[:, time],
                reset=batch.resets[:, time],
                sample=sample,
            )
            steps.append(step)
            state = step.state
        return self._stack_steps(steps, posterior=True)

    def imagine(
        self,
        actions: Tensor,
        initial_state: CassiWorldModelState,
        *,
        valid: Tensor | None = None,
        resets: Tensor | None = None,
        sample: bool = False,
    ) -> CassiWorldModelOutput:
        if actions.ndim != 3 or actions.shape[2] != self.config.action_dim:
            raise CassiWorldModelError("imagination actions must have shape [B, T, action_dim]")
        batch_size, horizon, _ = actions.shape
        if horizon < 1:
            raise CassiWorldModelError("imagination requires at least one step")
        valid = valid if valid is not None else torch.ones(batch_size, horizon, dtype=torch.bool, device=actions.device)
        resets = resets if resets is not None else torch.zeros(batch_size, horizon, dtype=torch.bool, device=actions.device)
        if valid.shape != (batch_size, horizon) or resets.shape != (batch_size, horizon):
            raise CassiWorldModelError("imagination masks must have shape [B, T]")
        state = initial_state
        if state.batch_size != batch_size:
            raise CassiWorldModelError("initial state batch size does not match imagination actions")
        steps: list[CassiWorldModelStep] = []
        for time in range(horizon):
            step = self.imagine_step(
                actions[:, time],
                state,
                valid=valid[:, time],
                reset=resets[:, time],
                sample=sample,
            )
            steps.append(step)
            state = step.state
        return self._stack_steps(steps, posterior=False)


def _masked_mean(values: Tensor, valid: Tensor) -> Tensor:
    if values.shape[:2] != valid.shape:
        raise CassiWorldModelError("loss values and valid mask do not share [B, T]")
    mask = valid.to(values.dtype)
    return torch.sum(values * mask) / torch.clamp_min(torch.sum(mask), 1.0)


def _normal_nll(target: Tensor, mean: Tensor, log_std: Tensor) -> Tensor:
    return (0.5 * ((target - mean) * torch.exp(-log_std)).square() + log_std + 0.5 * math.log(2.0 * math.pi)).sum(dim=-1)


def _normal_kl(q_mean: Tensor, q_log_std: Tensor, p_mean: Tensor, p_log_std: Tensor) -> Tensor:
    variance_ratio = torch.exp(2.0 * (q_log_std - p_log_std))
    mean_term = (q_mean - p_mean).square() * torch.exp(-2.0 * p_log_std)
    return (p_log_std - q_log_std + 0.5 * (variance_ratio + mean_term - 1.0)).sum(dim=-1)


def compute_world_model_loss(
    batch: CassiTrajectoryBatch,
    output: CassiWorldModelOutput,
    config: CassiWorldModelLossConfig = CassiWorldModelLossConfig(),
) -> CassiWorldModelLoss:
    if output.posterior_mean is None or output.posterior_log_std is None:
        raise CassiWorldModelError("world-model loss requires an observed posterior trajectory")
    expected_observation = batch.observations.shape
    expected_reward = batch.rewards.shape
    if output.observation_mean.shape != expected_observation or output.observation_log_std.shape != expected_observation:
        raise CassiWorldModelError("observation prediction shape does not match the trajectory batch")
    if output.reward_mean.shape != expected_reward or output.reward_log_std.shape != expected_reward:
        raise CassiWorldModelError("reward prediction shape does not match the trajectory batch")
    if output.continue_logits.shape != batch.continues.shape:
        raise CassiWorldModelError("continuation prediction shape does not match the trajectory batch")

    observation_nll = _masked_mean(
        _normal_nll(batch.observations, output.observation_mean, output.observation_log_std),
        batch.valid,
    )
    reward_nll = _masked_mean(
        _normal_nll(batch.rewards, output.reward_mean, output.reward_log_std),
        batch.valid,
    )
    continuation_bce = _masked_mean(
        F.binary_cross_entropy_with_logits(output.continue_logits, batch.continues, reduction="none"),
        batch.valid,
    )
    dynamic_kl = _normal_kl(
        output.posterior_mean.detach(),
        output.posterior_log_std.detach(),
        output.prior_mean,
        output.prior_log_std,
    )
    representation_kl = _normal_kl(
        output.posterior_mean,
        output.posterior_log_std,
        output.prior_mean.detach(),
        output.prior_log_std.detach(),
    )
    dynamic_kl = torch.clamp_min(dynamic_kl, config.free_nats)
    representation_kl = torch.clamp_min(representation_kl, config.free_nats)
    kl = _masked_mean(
        config.kl_balance * dynamic_kl + (1.0 - config.kl_balance) * representation_kl,
        batch.valid,
    )
    observation_mse = _masked_mean((batch.observations - output.observation_mean).square().mean(dim=-1), batch.valid)
    reward_mse = _masked_mean((batch.rewards - output.reward_mean).square().mean(dim=-1), batch.valid)
    total = (
        config.observation_weight * observation_nll
        + config.reward_weight * reward_nll
        + config.continuation_weight * continuation_bce
        + config.kl_weight * kl
    )
    if not bool(torch.isfinite(total).item()):
        raise CassiWorldModelError("world-model loss is non-finite")
    return CassiWorldModelLoss(total, observation_nll, reward_nll, continuation_bce, kl, observation_mse, reward_mse)


@dataclass(frozen=True)
class CassiWorldModelCheckpoint:
    model: CassiWorldModel
    optimizer_state: dict[str, Any] | None
    step: int
    metadata: dict[str, Any]


def _json_safe_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    value = {} if metadata is None else dict(metadata)
    try:
        encoded = json.dumps(value, allow_nan=False, sort_keys=True)
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise CassiWorldModelError(f"checkpoint metadata must be finite JSON data: {exc}") from exc
    if not isinstance(decoded, dict):
        raise CassiWorldModelError("checkpoint metadata must encode a JSON object")
    return decoded


def _atomic_torch_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False)
    temporary = Path(handle.name)
    handle.close()
    try:
        torch.save(payload, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _finite_state_dict(state_dict: Mapping[str, Any]) -> bool:
    return bool(state_dict) and all(
        torch.is_tensor(value) and (not value.dtype.is_floating_point or bool(torch.isfinite(value).all().item()))
        for value in state_dict.values()
    )


def save_world_model_checkpoint(
    path: Path | str,
    model: CassiWorldModel,
    *,
    optimizer: torch.optim.Optimizer | None = None,
    step: int = 0,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    if isinstance(step, bool) or not isinstance(step, int) or step < 0:
        raise CassiWorldModelError("checkpoint step must be a non-negative integer")
    model_state = model.state_dict()
    if not _finite_state_dict(model_state):
        raise CassiWorldModelError("model contains a non-finite or invalid state tensor")
    payload = {
        "schema": MODEL_CHECKPOINT_SCHEMA,
        "mode_layout_id": MODE_LAYOUT_ID,
        "operator_profile_id": OPERATOR_PROFILE_ID,
        "config": model.config.to_dict(),
        "config_fingerprint": model.config_fingerprint,
        "model_state": model_state,
        "optimizer_state": optimizer.state_dict() if optimizer is not None else None,
        "step": step,
        "metadata": _json_safe_metadata(metadata),
    }
    target = Path(path)
    _atomic_torch_save(payload, target)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def load_world_model_checkpoint(
    path: Path | str,
    *,
    device: torch.device | str = "cpu",
    expected_config: CassiWorldModelConfig | None = None,
) -> CassiWorldModelCheckpoint:
    target = Path(path)
    if not target.is_file():
        raise CassiWorldModelError(f"world-model checkpoint does not exist: {target}")
    try:
        payload = torch.load(target, map_location=torch.device(device), weights_only=True)
    except Exception as exc:
        raise CassiWorldModelError(f"world-model checkpoint cannot be loaded: {type(exc).__name__}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != MODEL_CHECKPOINT_SCHEMA:
        raise CassiWorldModelError("world-model checkpoint schema mismatch")
    if payload.get("mode_layout_id") != MODE_LAYOUT_ID or payload.get("operator_profile_id") != OPERATOR_PROFILE_ID:
        raise CassiWorldModelError("world-model checkpoint operator identity mismatch")
    config = CassiWorldModelConfig.from_dict(payload.get("config", {}))
    if payload.get("config_fingerprint") != config.fingerprint:
        raise CassiWorldModelError("world-model checkpoint configuration fingerprint mismatch")
    if expected_config is not None and config != expected_config:
        raise CassiWorldModelError("world-model checkpoint configuration is incompatible")
    model_state = payload.get("model_state")
    if not isinstance(model_state, dict) or not _finite_state_dict(model_state):
        raise CassiWorldModelError("world-model checkpoint contains invalid model state")
    model = CassiWorldModel(config).to(device=torch.device(device))
    try:
        model.load_state_dict(model_state, strict=True)
    except (RuntimeError, ValueError) as exc:
        raise CassiWorldModelError(f"world-model checkpoint state mismatch: {exc}") from exc
    step = payload.get("step")
    if isinstance(step, bool) or not isinstance(step, int) or step < 0:
        raise CassiWorldModelError("world-model checkpoint step is invalid")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise CassiWorldModelError("world-model checkpoint metadata is invalid")
    optimizer_state = payload.get("optimizer_state")
    if optimizer_state is not None and not isinstance(optimizer_state, dict):
        raise CassiWorldModelError("world-model checkpoint optimizer state is invalid")
    return CassiWorldModelCheckpoint(model, optimizer_state, step, metadata)


def _validate_runtime_state_bytes(payload: object) -> bytes:
    if isinstance(payload, bool) or not isinstance(payload, bytes):
        raise CassiWorldModelError("world-model runtime-state payload must be bytes")
    if not payload:
        raise CassiWorldModelError("world-model runtime-state payload must be non-empty")
    if len(payload) > MAX_RUNTIME_STATE_BYTES:
        raise CassiWorldModelError(
            f"world-model runtime-state payload exceeds {MAX_RUNTIME_STATE_BYTES} bytes"
        )
    return payload


def _owned_cpu_tensor(value: Tensor) -> Tensor:
    return value.detach().to(device="cpu").clone()


def dump_world_model_state_bytes(model: CassiWorldModel, state: CassiWorldModelState) -> bytes:
    reference = model._reference()
    state.validate(model.config, device=reference.device, dtype=reference.dtype)
    payload = {
        "schema": RUNTIME_STATE_SCHEMA,
        "mode_layout_id": MODE_LAYOUT_ID,
        "operator_profile_id": OPERATOR_PROFILE_ID,
        "config_fingerprint": model.config_fingerprint,
        "batch_size": state.batch_size,
        "field": _owned_cpu_tensor(state.field),
        "stochastic": _owned_cpu_tensor(state.stochastic),
        "step": _owned_cpu_tensor(state.step),
    }
    try:
        with BytesIO() as stream:
            torch.save(payload, stream)
            encoded = stream.getvalue()
    except Exception as exc:
        raise CassiWorldModelError(
            f"world-model runtime state cannot be serialized: {type(exc).__name__}: {exc}"
        ) from exc
    return _validate_runtime_state_bytes(encoded)


def load_world_model_state_bytes(
    payload: bytes,
    model: CassiWorldModel,
    *,
    device: torch.device | str | None = None,
) -> CassiWorldModelState:
    encoded = _validate_runtime_state_bytes(payload)
    reference = model._reference()
    target_device = torch.device(device) if device is not None else reference.device
    if target_device != reference.device:
        raise CassiWorldModelError("runtime state target device must match the model device")
    try:
        with BytesIO(encoded) as stream:
            decoded = torch.load(stream, map_location=target_device, weights_only=True)
    except Exception as exc:
        raise CassiWorldModelError(
            f"world-model runtime state cannot be loaded: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(decoded, dict) or decoded.get("schema") != RUNTIME_STATE_SCHEMA:
        raise CassiWorldModelError("world-model runtime-state schema mismatch")
    if decoded.get("mode_layout_id") != MODE_LAYOUT_ID or decoded.get("operator_profile_id") != OPERATOR_PROFILE_ID:
        raise CassiWorldModelError("world-model runtime-state operator identity mismatch")
    if decoded.get("config_fingerprint") != model.config_fingerprint:
        raise CassiWorldModelError("world-model runtime state belongs to an incompatible model")
    batch_size = decoded.get("batch_size")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise CassiWorldModelError("world-model runtime-state batch size is invalid")
    field_value = decoded.get("field")
    stochastic_value = decoded.get("stochastic")
    step_value = decoded.get("step")
    if not all(torch.is_tensor(value) for value in (field_value, stochastic_value, step_value)):
        raise CassiWorldModelError("world-model runtime state is missing tensors")
    try:
        state = CassiWorldModelState(
            field=field_value.to(device=target_device, dtype=reference.dtype).detach().clone(),
            stochastic=stochastic_value.to(device=target_device, dtype=reference.dtype).detach().clone(),
            step=step_value.to(device=target_device, dtype=torch.int64).detach().clone(),
        )
        state.validate(model.config, device=target_device, dtype=reference.dtype)
    except CassiWorldModelError:
        raise
    except Exception as exc:
        raise CassiWorldModelError(f"world-model runtime state tensors are invalid: {exc}") from exc
    if state.batch_size != batch_size:
        raise CassiWorldModelError("world-model runtime-state batch size does not match its tensors")
    return state


def _atomic_bytes_save(payload: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False)
    temporary = Path(handle.name)
    handle.close()
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def save_world_model_state(path: Path | str, model: CassiWorldModel, state: CassiWorldModelState) -> str:
    encoded = dump_world_model_state_bytes(model, state)
    target = Path(path)
    _atomic_bytes_save(encoded, target)
    return hashlib.sha256(encoded).hexdigest()


def load_world_model_state(
    path: Path | str,
    model: CassiWorldModel,
    *,
    device: torch.device | str | None = None,
) -> CassiWorldModelState:
    target = Path(path)
    if not target.is_file():
        raise CassiWorldModelError(f"world-model runtime state does not exist: {target}")
    with target.open("rb") as handle:
        encoded = handle.read(MAX_RUNTIME_STATE_BYTES + 1)
    return load_world_model_state_bytes(encoded, model, device=device)


__all__ = [
    "MAX_RUNTIME_STATE_BYTES",
    "MODEL_CHECKPOINT_SCHEMA",
    "MODEL_CONFIG_SCHEMA",
    "RUNTIME_STATE_SCHEMA",
    "CassiTrajectoryBatch",
    "CassiWorldModel",
    "CassiWorldModelCheckpoint",
    "CassiWorldModelConfig",
    "CassiWorldModelError",
    "CassiWorldModelLoss",
    "CassiWorldModelLossConfig",
    "CassiWorldModelOutput",
    "CassiWorldModelState",
    "CassiWorldModelStep",
    "compute_world_model_loss",
    "dump_world_model_state_bytes",
    "load_world_model_checkpoint",
    "load_world_model_state",
    "load_world_model_state_bytes",
    "save_world_model_checkpoint",
    "save_world_model_state",
]
