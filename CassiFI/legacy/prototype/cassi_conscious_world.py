"""Read-only counterfactual world simulation for the conscious Qi field.

This bridge supplies bounded counterfactual predictions to the conscious-field
branch API.  A learned world model is neither an identity model nor a source of
truth: only a separately bound observed consequence can reconcile a branch.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Final

import torch
from torch import Tensor

from cassi_conscious_field import (
    CassiConsciousBranch,
    CassiConsciousField,
    CassiConsciousFieldError,
    ConsciousReconciliation,
    tensor_wave_sha256,
)
from cassi_conscious_protocol import (
    ActorClass,
    CassiExperienceEvent,
    EventKind,
    RealityStatus,
    create_event,
    validate_event,
)
from cassi_qi_field import QiFieldState
from cassi_world_model import (
    CassiTrajectoryBatch,
    CassiWorldModel,
    CassiWorldModelError,
    CassiWorldModelOutput,
    CassiWorldModelState,
)


CONSCIOUS_WORLD_PROJECTION_SCHEMA: Final[str] = "cassi.conscious-world.consequence-dft.v1"
CONSCIOUS_FIELD_FUTURE_PROJECTION_SCHEMA: Final[str] = (
    "cassi.field-organism.shadow-future-dft.v1"
)
MAX_ACTION_HORIZON: Final[int] = 64
MAX_BATCH_SIZE: Final[int] = 1
_HEX_DIGITS: Final[frozenset[str]] = frozenset("0123456789abcdef")


class CassiConsciousWorldError(ValueError):
    """Raised when read-only world-to-conscious simulation is invalid."""


def _require_bounded_positive_int(name: str, value: int, hard_maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value > hard_maximum
    ):
        raise CassiConsciousWorldError(
            f"{name} must be a positive integer no greater than {hard_maximum}"
        )
    return value


def _require_sha256(name: str, value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _HEX_DIGITS for character in value)
    ):
        raise CassiConsciousWorldError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _tensor_sha256(tensor: Tensor) -> str:
    if not torch.is_tensor(tensor):
        raise CassiConsciousWorldError("tensor hash input must be a tensor")
    if not tensor.dtype.is_floating_point or not bool(torch.isfinite(tensor).all()):
        raise CassiConsciousWorldError("tensor hash input must be finite floating point")
    metadata = f"{tuple(tensor.shape)}|{tensor.dtype}".encode("ascii")
    values = tensor.detach().contiguous().cpu().numpy().tobytes()
    return hashlib.sha256(metadata + values).hexdigest()


@dataclass(frozen=True)
class CassiConsciousWorldSummary:
    """Finite aggregate for one simulated uncertainty channel."""

    mean: float
    maximum: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in (self.mean, self.maximum)):
            raise CassiConsciousWorldError("uncertainty summary must be finite")

    def canonical_payload(self) -> dict[str, float]:
        return {"mean": self.mean, "max": self.maximum}


@dataclass(frozen=True)
class CassiConsciousWorldUncertainty:
    """Immutable simulation uncertainty receipt."""

    observation_std: CassiConsciousWorldSummary
    reward_std: CassiConsciousWorldSummary
    prior_std: CassiConsciousWorldSummary

    def canonical_payload(self) -> dict[str, dict[str, float]]:
        return {
            "observation_std": self.observation_std.canonical_payload(),
            "reward_std": self.reward_std.canonical_payload(),
            "prior_std": self.prior_std.canonical_payload(),
        }


def _finite_summary(name: str, values: Tensor) -> CassiConsciousWorldSummary:
    if not torch.is_tensor(values) or not values.dtype.is_floating_point:
        raise CassiConsciousWorldError(f"{name} must be floating point")
    if not bool(torch.isfinite(values).all()):
        raise CassiConsciousWorldError(f"{name} must be finite")
    return CassiConsciousWorldSummary(
        mean=float(values.mean().detach().cpu()),
        maximum=float(values.max().detach().cpu()),
    )


@dataclass(frozen=True)
class CassiConsciousWorldResult:
    """One immutable counterfactual proposal and its detached model receipt.

    ``imagined_world_state`` is a prior-root branch result only. It MUST NOT
    replace the live world state: live state advances exclusively through
    :meth:`CassiConsciousWorldBridge.observe_actual` after observation.
    """

    event: CassiExperienceEvent
    wave: Tensor
    output: CassiWorldModelOutput
    imagined_world_state: CassiWorldModelState
    branch: CassiConsciousBranch
    uncertainty: CassiConsciousWorldUncertainty


@dataclass(frozen=True)
class CassiFieldImaginationResult:
    """One field-owned shadow future projected into an isolated Qi branch."""

    event: CassiExperienceEvent
    wave: Tensor
    actions: Tensor
    future: Tensor
    candidate_index: int
    branch: CassiConsciousBranch


class CassiConsciousWorldBridge:
    """Project deterministic world-model consequences into conscious branches.

    The bridge has no trainable parameters and never invokes backward or an
    optimizer.  It does not mutate the input world state, model parameters, or
    canonical Qi state.
    """

    def __init__(
        self,
        model: CassiWorldModel,
        model_checkpoint_sha256: str,
        conscious_field: CassiConsciousField,
        *,
        max_action_horizon: int = MAX_ACTION_HORIZON,
        max_batch_size: int = MAX_BATCH_SIZE,
    ) -> None:
        if not isinstance(model, CassiWorldModel):
            raise CassiConsciousWorldError("model must be a CassiWorldModel")
        if not isinstance(conscious_field, CassiConsciousField):
            raise CassiConsciousWorldError("conscious_field must be a CassiConsciousField")
        self.max_action_horizon = _require_bounded_positive_int(
            "max_action_horizon",
            max_action_horizon,
            MAX_ACTION_HORIZON,
        )
        self.max_batch_size = _require_bounded_positive_int(
            "max_batch_size",
            max_batch_size,
            MAX_BATCH_SIZE,
        )
        self.model = model
        self.model_checkpoint_sha256 = _require_sha256(
            "model_checkpoint_sha256",
            model_checkpoint_sha256,
        )
        self.conscious_field = conscious_field

    @staticmethod
    def _require_sequence(sequence: int) -> int:
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise CassiConsciousWorldError("sequence must be a non-negative integer")
        return sequence

    @staticmethod
    def _require_source_id(source_id: str) -> str:
        if (
            not isinstance(source_id, str)
            or not source_id
            or len(source_id) > 256
            or not source_id.isascii()
        ):
            raise CassiConsciousWorldError(
                "source_id must be a nonempty bounded ASCII string"
            )
        return source_id

    def _validate_root_state(self, root_state: QiFieldState) -> None:
        # The public gate performs the core owner/shape/device/dtype validation.
        self.conscious_field.access_gate(root_state)
        if root_state.batch_size != 1:
            raise CassiConsciousWorldError("conscious root state must have one lane")

    def _validate_world_state(self, world_state: CassiWorldModelState) -> None:
        if not isinstance(world_state, CassiWorldModelState):
            raise CassiConsciousWorldError("world_state must be a CassiWorldModelState")
        if not all(
            torch.is_tensor(value)
            for value in (world_state.field, world_state.stochastic, world_state.step)
        ):
            raise CassiConsciousWorldError("world_state tensors are invalid")
        if not bool(torch.isfinite(world_state.field).all()) or not bool(
            torch.isfinite(world_state.stochastic).all()
        ):
            raise CassiConsciousWorldError("world_state must be finite")
        reference = next(self.model.parameters())
        try:
            world_state.validate(
                self.model.config,
                device=reference.device,
                dtype=reference.dtype,
            )
        except (CassiWorldModelError, AttributeError, RuntimeError, TypeError, ValueError) as exc:
            raise CassiConsciousWorldError(str(exc)) from exc
        if world_state.batch_size < 1 or world_state.batch_size > self.max_batch_size:
            raise CassiConsciousWorldError(
                f"world_state batch size exceeds configured maximum {self.max_batch_size}"
            )
        if world_state.batch_size != 1:
            raise CassiConsciousWorldError("world_state must have one lane")

    def _validate_actions(self, actions: Tensor) -> None:
        if not torch.is_tensor(actions) or not actions.dtype.is_floating_point:
            raise CassiConsciousWorldError("actions must be a floating point tensor")
        if actions.ndim != 3:
            raise CassiConsciousWorldError("actions must have shape [B, T, action_dim]")
        batch_size, horizon, action_dim = (int(size) for size in actions.shape)
        if batch_size < 1 or batch_size > self.max_batch_size:
            raise CassiConsciousWorldError(
                f"actions batch size exceeds configured maximum {self.max_batch_size}"
            )
        if horizon < 1 or horizon > self.max_action_horizon:
            raise CassiConsciousWorldError(
                f"actions horizon exceeds configured maximum {self.max_action_horizon}"
            )
        if action_dim != self.model.config.action_dim:
            raise CassiConsciousWorldError("actions have an invalid action feature width")
        if not bool(torch.isfinite(actions).all()):
            raise CassiConsciousWorldError("actions must be finite")
        reference = next(self.model.parameters())
        if actions.dtype != reference.dtype or actions.device != reference.device:
            raise CassiConsciousWorldError("actions must match the model device and dtype")

    def _validate_consequence(
        self,
        observations: Tensor,
        rewards: Tensor,
        continues: Tensor,
    ) -> None:
        values = (observations, rewards, continues)
        if not all(torch.is_tensor(value) and value.dtype.is_floating_point for value in values):
            raise CassiConsciousWorldError("consequences must be floating point tensors")
        if observations.ndim != 3 or rewards.ndim != 3 or continues.ndim != 2:
            raise CassiConsciousWorldError(
                "consequences must have shapes [B, T, feature] and [B, T]"
            )
        batch_size, horizon, observation_dim = (int(size) for size in observations.shape)
        reward_batch, reward_horizon, reward_dim = (int(size) for size in rewards.shape)
        continue_batch, continue_horizon = (int(size) for size in continues.shape)
        if batch_size < 1 or batch_size > self.max_batch_size:
            raise CassiConsciousWorldError(
                f"consequence batch size exceeds configured maximum {self.max_batch_size}"
            )
        if horizon < 1 or horizon > self.max_action_horizon:
            raise CassiConsciousWorldError(
                f"consequence horizon exceeds configured maximum {self.max_action_horizon}"
            )
        if (
            reward_batch != batch_size
            or continue_batch != batch_size
            or reward_horizon != horizon
            or continue_horizon != horizon
        ):
            raise CassiConsciousWorldError(
                "observation, reward, and continuation lengths must match"
            )
        if observation_dim != self.model.config.observation_dim:
            raise CassiConsciousWorldError("observations have an invalid feature width")
        if reward_dim != self.model.config.reward_dim:
            raise CassiConsciousWorldError("rewards have an invalid feature width")
        if not all(bool(torch.isfinite(value).all()) for value in values):
            raise CassiConsciousWorldError("consequences must be finite")
        reference = next(self.model.parameters())
        if any(value.dtype != reference.dtype for value in values):
            raise CassiConsciousWorldError("consequences must use the model dtype")
        if any(value.device != reference.device for value in values):
            raise CassiConsciousWorldError("consequences must use the model device")
        if bool(torch.any(continues < 0.0)) or bool(torch.any(continues > 1.0)):
            raise CassiConsciousWorldError("continues must be in [0, 1]")

    @staticmethod
    def _detach_clone_state(state: CassiWorldModelState) -> CassiWorldModelState:
        return CassiWorldModelState(
            field=state.field.detach().clone(),
            stochastic=state.stochastic.detach().clone(),
            step=state.step.detach().clone(),
        )

    def _validate_model_output(
        self,
        output: CassiWorldModelOutput,
        *,
        batch_size: int,
        horizon: int,
        require_posterior: bool,
    ) -> None:
        if not isinstance(output, CassiWorldModelOutput):
            raise CassiConsciousWorldError("learned world model returned an invalid output")
        reference = next(self.model.parameters())
        config = self.model.config

        def require_tensor(name: str, value: object, shape: tuple[int, ...]) -> None:
            if not torch.is_tensor(value) or not value.dtype.is_floating_point:
                raise CassiConsciousWorldError(f"world-model output {name} must be floating point")
            if tuple(value.shape) != shape:
                raise CassiConsciousWorldError(
                    f"world-model output {name} has an invalid shape"
                )
            if value.dtype != reference.dtype or value.device != reference.device:
                raise CassiConsciousWorldError(
                    f"world-model output {name} must match the model device and dtype"
                )
            if not bool(torch.isfinite(value).all()):
                raise CassiConsciousWorldError(
                    f"world-model output {name} must be finite"
                )

        require_tensor(
            "observation_mean",
            output.observation_mean,
            (batch_size, horizon, config.observation_dim),
        )
        require_tensor(
            "observation_log_std",
            output.observation_log_std,
            (batch_size, horizon, config.observation_dim),
        )
        require_tensor(
            "reward_mean",
            output.reward_mean,
            (batch_size, horizon, config.reward_dim),
        )
        require_tensor(
            "reward_log_std",
            output.reward_log_std,
            (batch_size, horizon, config.reward_dim),
        )
        require_tensor("continue_logits", output.continue_logits, (batch_size, horizon))
        require_tensor(
            "prior_mean",
            output.prior_mean,
            (batch_size, horizon, config.latent_dim),
        )
        require_tensor(
            "prior_log_std",
            output.prior_log_std,
            (batch_size, horizon, config.latent_dim),
        )
        require_tensor(
            "field_correction",
            output.field_correction,
            (batch_size, horizon, 2 * config.mode_count),
        )
        require_tensor(
            "features",
            output.features,
            (batch_size, horizon, config.model_dim + config.latent_dim),
        )

        posterior = (output.posterior_mean, output.posterior_log_std)
        if require_posterior and any(value is None for value in posterior):
            raise CassiConsciousWorldError(
                "observed world-model output must include posterior tensors"
            )
        if not require_posterior and any(value is not None for value in posterior):
            raise CassiConsciousWorldError(
                "imagined world-model output must not include posterior tensors"
            )
        if all(value is not None for value in posterior):
            require_tensor(
                "posterior_mean",
                output.posterior_mean,
                (batch_size, horizon, config.latent_dim),
            )
            require_tensor(
                "posterior_log_std",
                output.posterior_log_std,
                (batch_size, horizon, config.latent_dim),
            )

        if not isinstance(output.final_state, CassiWorldModelState):
            raise CassiConsciousWorldError(
                "world-model output final_state is invalid"
            )
        if not all(
            torch.is_tensor(value)
            for value in (
                output.final_state.field,
                output.final_state.stochastic,
                output.final_state.step,
            )
        ):
            raise CassiConsciousWorldError(
                "world-model output final_state tensors are invalid"
            )
        try:
            output.final_state.validate(
                config,
                device=reference.device,
                dtype=reference.dtype,
            )
        except (CassiWorldModelError, AttributeError, RuntimeError, TypeError, ValueError) as exc:
            raise CassiConsciousWorldError(
                f"world-model output final_state is invalid: {exc}"
            ) from exc
        if output.final_state.batch_size != batch_size:
            raise CassiConsciousWorldError(
                "world-model output final_state batch size does not match the request"
            )

    def _project_values(self, values: Tensor, root_state: QiFieldState) -> Tensor:
        self._validate_root_state(root_state)
        if (
            not torch.is_tensor(values)
            or not values.dtype.is_floating_point
            or values.numel() < 1
            or not bool(torch.isfinite(values).all().item())
        ):
            raise CassiConsciousWorldError(
                "projection values must be a nonempty finite floating tensor"
            )
        flattened = values.detach().reshape(-1).to(
            device=root_state.field.device,
            dtype=root_state.field.dtype,
        )
        count = int(flattened.numel())
        mode_count = self.conscious_field.controller.config.wave_mode_count
        modes = torch.arange(
            1,
            mode_count + 1,
            device=flattened.device,
            dtype=flattened.dtype,
        )
        positions = torch.arange(
            1,
            count + 1,
            device=flattened.device,
            dtype=flattened.dtype,
        )
        angles = (
            (2.0 * math.pi / count)
            * modes.unsqueeze(1)
            * positions.unsqueeze(0)
        )
        scale = math.sqrt(count)
        real = torch.cos(angles).matmul(flattened) / scale
        imaginary = torch.sin(angles).matmul(flattened) / scale
        wave = torch.stack((real, imaginary), dim=-1).unsqueeze(0)
        magnitude = torch.linalg.vector_norm(wave, dim=-1, keepdim=True)
        maximum = self.conscious_field.config.maximum_wave_magnitude
        wave = wave * torch.clamp(
            maximum / torch.clamp_min(magnitude, 1.0e-12),
            max=1.0,
        )
        return self.conscious_field.boundary.validate_wave(
            wave.contiguous(),
            root_state,
        )
    def project_actual_consequence(
        self,
        observations: Tensor,
        rewards: Tensor,
        continues: Tensor,
        root_state: QiFieldState,
    ) -> Tensor:
        """Map consequence values through a fixed normalized complex DFT.

        Flatten the aligned ``[observation, reward, continuation]`` value row.
        For wave mode ``m`` and flattened value ``x_j``, the real and imaginary
        lanes are respectively ``sum_j x_j cos(2π(m+1)(j+1)/N)/sqrt(N)`` and
        ``sum_j x_j sin(2π(m+1)(j+1)/N)/sqrt(N)``.  This is parameter-free and
        deterministic; per-mode magnitudes are then bounded by the configured
        conscious boundary magnitude.
        """
        self._validate_root_state(root_state)
        self._validate_consequence(observations, rewards, continues)
        values = torch.cat(
            (observations, rewards, continues.unsqueeze(-1)),
            dim=-1,
        )
        return self._project_values(values, root_state)


    def imagine_field_consequence(
        self,
        intent: CassiExperienceEvent,
        actions: Tensor,
        future: Tensor,
        root_state: QiFieldState,
        *,
        candidate_index: int,
        sequence: int,
        imagination_steps: int,
    ) -> CassiFieldImaginationResult:
        """Project one canonical ``m_hat`` trajectory without invoking Qwen or RSSM."""

        validate_event(intent)
        if (
            intent.kind is not EventKind.ACTION_INTENT
            or intent.reality_status is not RealityStatus.AGENT_INTENT
            or intent.actor is not ActorClass.LOCAL_AGENT
        ):
            raise CassiConsciousWorldError("intent must be a local ACTION_INTENT")
        sequence = self._require_sequence(sequence)
        if (
            isinstance(candidate_index, bool)
            or not isinstance(candidate_index, int)
            or candidate_index < 0
        ):
            raise CassiConsciousWorldError(
                "candidate_index must be a non-negative integer"
            )
        if (
            isinstance(imagination_steps, bool)
            or not isinstance(imagination_steps, int)
            or imagination_steps < 1
        ):
            raise CassiConsciousWorldError(
                "imagination_steps must be a positive integer"
            )
        self._validate_actions(actions)
        self._validate_root_state(root_state)
        if (
            not torch.is_tensor(future)
            or future.ndim != 2
            or future.shape[0] < 1
            or future.shape[1] < 2
            or future.device != root_state.field.device
            or future.dtype != root_state.field.dtype
            or not bool(torch.isfinite(future).all().item())
        ):
            raise CassiConsciousWorldError(
                "field future must be finite root-device/dtype [T,M] with T >= 1 and M >= 2"
            )
        owned_actions = actions.detach().clone()
        owned_future = future.detach().clone()
        wave = self._project_values(
            torch.cat((owned_actions.reshape(-1), owned_future.reshape(-1))),
            root_state,
        )
        future_sha256 = _tensor_sha256(owned_future)
        payload = json.dumps(
            {
                "action_sha256": _tensor_sha256(owned_actions),
                "candidate_index": candidate_index,
                "field_future_sha256": future_sha256,
                "future_shape": list(owned_future.shape),
                "projection_schema": CONSCIOUS_FIELD_FUTURE_PROJECTION_SCHEMA,
            },
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        event = create_event(
            sequence=sequence,
            kind=EventKind.IMAGINATION,
            reality_status=RealityStatus.HYPOTHESIS,
            actor=ActorClass.LOCAL_AGENT,
            payload=payload,
            source_id=f"cassi-field-organism:{future_sha256}",
            parent_event_id=intent.event_id,
            boundary_wave_sha256=tensor_wave_sha256(wave),
        )
        branch = self.conscious_field.begin_imagination(
            root_state,
            event,
            root_event_id=intent.event_id,
            steps=imagination_steps,
            proposal_wave=wave,
        )
        return CassiFieldImaginationResult(
            event=event,
            wave=wave.detach().clone(),
            actions=owned_actions,
            future=owned_future,
            candidate_index=candidate_index,
            branch=branch,
        )

    def imagine_consequence(
        self,
        intent: CassiExperienceEvent,
        actions: Tensor,
        world_state: CassiWorldModelState,
        root_state: QiFieldState,
        *,
        sequence: int,
        imagination_steps: int,
    ) -> CassiConsciousWorldResult:
        """Create a bounded hypothesis branch from a deterministic simulation."""
        validate_event(intent)
        if (
            intent.kind is not EventKind.ACTION_INTENT
            or intent.reality_status is not RealityStatus.AGENT_INTENT
            or intent.actor is not ActorClass.LOCAL_AGENT
        ):
            raise CassiConsciousWorldError("intent must be a local ACTION_INTENT")
        sequence = self._require_sequence(sequence)
        if (
            isinstance(imagination_steps, bool)
            or not isinstance(imagination_steps, int)
            or imagination_steps < 1
        ):
            raise CassiConsciousWorldError("imagination_steps must be a positive integer")
        self._validate_actions(actions)
        self._validate_world_state(world_state)
        self._validate_root_state(root_state)
        batch_size = int(actions.shape[0])
        horizon = int(actions.shape[1])
        model_actions = actions.detach().clone()
        model_world_state = self._detach_clone_state(world_state)
        with torch.no_grad():
            raw_output = self.model.imagine(
                model_actions,
                model_world_state,
                sample=False,
            )
            self._validate_model_output(
                raw_output,
                batch_size=batch_size,
                horizon=horizon,
                require_posterior=False,
            )
            output = self._detach_output(raw_output)
            self._validate_model_output(
                output,
                batch_size=batch_size,
                horizon=horizon,
                require_posterior=False,
            )
            continues = torch.sigmoid(output.continue_logits)
            wave = self.project_actual_consequence(
                output.observation_mean,
                output.reward_mean,
                continues,
                root_state,
            )
            uncertainty = CassiConsciousWorldUncertainty(
                observation_std=_finite_summary(
                    "observation_log_std",
                    torch.exp(output.observation_log_std),
                ),
                reward_std=_finite_summary(
                    "reward_log_std",
                    torch.exp(output.reward_log_std),
                ),
                prior_std=_finite_summary(
                    "prior_log_std",
                    torch.exp(output.prior_log_std),
                ),
            )
            payload = json.dumps(
                {
                    "action_sha256": _tensor_sha256(actions),
                    "consequence_sha256": _tensor_sha256(
                        torch.cat(
                            (
                                output.observation_mean,
                                output.reward_mean,
                                continues.unsqueeze(-1),
                            ),
                            dim=-1,
                        )
                    ),
                    "dimensions": {
                        "action": self.model.config.action_dim,
                        "observation": self.model.config.observation_dim,
                        "reward": self.model.config.reward_dim,
                    },
                    "horizon": horizon,
                    "model_checkpoint_sha256": self.model_checkpoint_sha256,
                    "model_config_fingerprint": self.model.config_fingerprint,
                    "projection_schema": CONSCIOUS_WORLD_PROJECTION_SCHEMA,
                    "uncertainty": uncertainty.canonical_payload(),
                },
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            event = create_event(
                sequence=sequence,
                kind=EventKind.IMAGINATION,
                reality_status=RealityStatus.HYPOTHESIS,
                actor=ActorClass.LOCAL_AGENT,
                payload=payload,
                source_id=f"cassi-conscious-world:{self.model_checkpoint_sha256}",
                parent_event_id=intent.event_id,
                boundary_wave_sha256=tensor_wave_sha256(wave),
            )
            branch = self.conscious_field.begin_imagination(
                root_state,
                event,
                root_event_id=intent.event_id,
                steps=imagination_steps,
                proposal_wave=wave,
            )
        return CassiConsciousWorldResult(
            event=event,
            wave=wave.detach().clone(),
            output=output,
            imagined_world_state=output.final_state.detach().clone(),
            branch=branch,
            uncertainty=uncertainty,
        )

    def create_observed_consequence_event(
        self,
        intent: CassiExperienceEvent,
        observations: Tensor,
        rewards: Tensor,
        continues: Tensor,
        root_state: QiFieldState,
        *,
        sequence: int,
        source_id: str,
    ) -> tuple[CassiExperienceEvent, Tensor]:
        """Bind externally observed action evidence to a local acted intent."""
        validate_event(intent)
        if (
            intent.kind is not EventKind.ACTION_INTENT
            or intent.reality_status is not RealityStatus.AGENT_INTENT
            or intent.actor is not ActorClass.LOCAL_AGENT
        ):
            raise CassiConsciousWorldError("intent must be a local ACTION_INTENT")
        sequence = self._require_sequence(sequence)
        source_id = self._require_source_id(source_id)
        wave = self.project_actual_consequence(observations, rewards, continues, root_state)
        payload = json.dumps(
            {
                "consequence_sha256": _tensor_sha256(
                    torch.cat(
                        (observations, rewards, continues.unsqueeze(-1)),
                        dim=-1,
                    )
                ),
                "horizon": int(observations.shape[1]),
                "model_checkpoint_sha256": self.model_checkpoint_sha256,
                "model_config_fingerprint": self.model.config_fingerprint,
                "projection_schema": CONSCIOUS_WORLD_PROJECTION_SCHEMA,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        event = create_event(
            sequence=sequence,
            kind=EventKind.ACTION_OUTCOME,
            reality_status=RealityStatus.OBSERVED_REALITY,
            actor=ActorClass.ENVIRONMENT,
            payload=payload,
            source_id=source_id,
            parent_event_id=intent.event_id,
            boundary_wave_sha256=tensor_wave_sha256(wave),
        )
        return event, wave

    def reconcile_consequence(
        self,
        root_state: QiFieldState,
        branch: CassiConsciousBranch,
        actual_event: CassiExperienceEvent,
        actual_wave: Tensor,
    ) -> ConsciousReconciliation:
        """Reconcile only the supplied evidence against a prior branch."""
        return self.conscious_field.reconcile_branch(
            root_state,
            branch,
            actual_event,
            actual_wave=actual_wave,
        )

    def observe_actual(
        self,
        observations: Tensor,
        actions: Tensor,
        rewards: Tensor,
        continues: Tensor,
        prior_world_state: CassiWorldModelState,
    ) -> CassiWorldModelState:
        """Advance only the live prior state with newly observed consequences."""

        self._validate_actions(actions)
        self._validate_consequence(observations, rewards, continues)
        self._validate_world_state(prior_world_state)
        if actions.shape[0] != observations.shape[0]:
            raise CassiConsciousWorldError(
                "action and consequence batch sizes must match"
            )
        if actions.shape[1] != observations.shape[1]:
            raise CassiConsciousWorldError(
                "action and consequence horizons must match"
            )
        batch_size = int(actions.shape[0])
        horizon = int(actions.shape[1])
        model_observations = observations.detach().clone()
        model_actions = actions.detach().clone()
        model_rewards = rewards.detach().clone()
        model_continues = continues.detach().clone()
        valid = torch.ones(
            (batch_size, horizon),
            device=actions.device,
            dtype=torch.bool,
        )
        resets = torch.zeros_like(valid)
        batch = CassiTrajectoryBatch(
            model_observations,
            model_actions,
            model_rewards,
            model_continues,
            valid,
            resets,
        )
        model_world_state = self._detach_clone_state(prior_world_state)
        with torch.no_grad():
            raw_output = self.model.observe(
                batch,
                model_world_state,
                sample=False,
            )
            self._validate_model_output(
                raw_output,
                batch_size=batch_size,
                horizon=horizon,
                require_posterior=True,
            )
        returned_state = self._detach_clone_state(raw_output.final_state)
        self._validate_world_state(returned_state)
        return returned_state

    @staticmethod
    def _detach_output(output: CassiWorldModelOutput) -> CassiWorldModelOutput:
        return CassiWorldModelOutput(
            observation_mean=output.observation_mean.detach().clone(),
            observation_log_std=output.observation_log_std.detach().clone(),
            reward_mean=output.reward_mean.detach().clone(),
            reward_log_std=output.reward_log_std.detach().clone(),
            continue_logits=output.continue_logits.detach().clone(),
            prior_mean=output.prior_mean.detach().clone(),
            prior_log_std=output.prior_log_std.detach().clone(),
            posterior_mean=None,
            posterior_log_std=None,
            field_correction=output.field_correction.detach().clone(),
            features=output.features.detach().clone(),
            final_state=output.final_state.detach().clone(),
        )


__all__ = [
    "CONSCIOUS_FIELD_FUTURE_PROJECTION_SCHEMA",
    "CONSCIOUS_WORLD_PROJECTION_SCHEMA",
    "MAX_ACTION_HORIZON",
    "MAX_BATCH_SIZE",
    "CassiConsciousWorldBridge",
    "CassiConsciousWorldError",
    "CassiConsciousWorldResult",
    "CassiFieldImaginationResult",
]
