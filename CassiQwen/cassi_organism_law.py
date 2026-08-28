"""Constrained causal update law for the canonical Cassi field organism.

The implementation instantiates the extended product-state equation as one
ordered successor operation over :class:`CassiOrganismState`.  The arena is the
only adaptive owner.  All receipts, teacher vectors, scratch futures, and
intermediate projections are transient.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Final, Mapping, Sequence

import torch
from torch import Tensor

_MAX_CAUSAL_SCALAR: Final[float] = 1.0e6
_MAX_RESOURCE_CREDIT: Final[float] = 1.0e12

from cassi_field_language import FIELD_TEXT_CODEC_SCHEMA
from cassi_organism import (
    ACTION_BAND_OFFSET,
    ACTION_COMMITMENT_OFFSET,
    ACTION_FITNESS_OFFSET,
    ACTION_INFORMATION_OFFSET,
    ACTION_MASS_OFFSET,
    ACTION_PREDICTED_COST_OFFSET,
    ACTION_SCORE_OFFSET,
    ACTION_VIABILITY_OFFSET,
    CassiOrganismConfig,
    CassiOrganismError,
    CassiOrganismState,
    organism_state_sha256,
    qi_state_from_organism,
    successor_organism_state,
)
from cassi_qi_field import QiBalanceConversion, QiFieldController

TEACHER_WEAVE_SCHEMA: Final[str] = "cassi.organism.teacher-weave.v1"
ORGANISM_STEP_RECEIPT_SCHEMA: Final[str] = "cassi.organism.step-receipt.v2"
_MAX_EXACT_FLOAT32_INTEGER: Final[int] = 1 << 24
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")


class CassiOrganismLawError(ValueError):
    """Invalid organism input, teacher weave, resource ledger, or update."""

class CassiResourceExhaustedError(CassiOrganismLawError):
    """A causal step could not pay the field work required for a symbol."""



def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _HEX for char in value):
        raise CassiOrganismLawError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _finite_real(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CassiOrganismLawError(f"{name} must be a finite real number")
    result = float(value)
    if (
        not math.isfinite(result)
        or (minimum is not None and result < minimum)
        or (maximum is not None and result > maximum)
    ):
        bounds: list[str] = ["finite"]
        if minimum is not None:
            bounds.append(f"at least {minimum}")
        if maximum is not None:
            bounds.append(f"at most {maximum}")
        raise CassiOrganismLawError(f"{name} must be {' and '.join(bounds)}")
    return result


def _tensor_bytes(value: Tensor) -> bytes:
    return value.detach().to(device="cpu", dtype=torch.float32).contiguous().numpy().tobytes()


def _resample_vector(value: Tensor, width: int) -> Tensor:
    """Deterministically linearly resample one flat vector without parameters."""

    source = value.reshape(-1)
    if width <= 0:
        raise CassiOrganismLawError("resample width must be positive")
    if source.numel() == 0:
        return torch.zeros(width, dtype=value.dtype, device=value.device)
    if source.numel() == width:
        return source.clone()
    if source.numel() == 1:
        return source.expand(width).clone()
    positions = torch.linspace(0.0, float(source.numel() - 1), width, dtype=value.dtype, device=value.device)
    lower = positions.floor().to(torch.int64)
    upper = torch.clamp(lower + 1, max=source.numel() - 1)
    fraction = positions - lower.to(value.dtype)
    return source.index_select(0, lower) * (1.0 - fraction) + source.index_select(0, upper) * fraction


def _simplex(value: Tensor) -> Tensor:
    result = torch.clamp(value, min=0.0)
    total = result.sum()
    if not bool(torch.isfinite(total).item()) or float(total.item()) <= torch.finfo(result.dtype).tiny:
        return torch.full_like(result, 1.0 / result.numel())
    return result / total

def _qi_diagnostics(qi: Tensor, phi: float) -> tuple[Tensor, Tensor]:
    """Derive q and Yang-minus-phi-Yin from the current Qi tensor."""

    yang = qi[:, :2, :].square().sum(dim=1)
    yin = qi[:, 2:4, :].square().sum(dim=1)
    epsilon = yang - phi * yin
    rho2 = qi[:, :4, :].square().sum(dim=1).square()
    q = rho2 / (
        rho2 + phi**-2 + epsilon.square()
    ).clamp_min(torch.finfo(qi.dtype).tiny)
    return q, epsilon


def _capture_digest(
    layers: Sequence[Tensor],
    *,
    source_model_sha256: str,
    source_runtime_sha256: str,
    token_index: int,
) -> str:
    hasher = hashlib.sha256()
    header = json.dumps(
        {
            "schema": TEACHER_WEAVE_SCHEMA,
            "source_model_sha256": source_model_sha256,
            "source_runtime_sha256": source_runtime_sha256,
            "token_index": token_index,
            "layer_count": len(layers),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    hasher.update(header)
    for index, layer in enumerate(layers):
        raw = _tensor_bytes(layer)
        hasher.update(index.to_bytes(4, "little", signed=False))
        hasher.update(len(raw).to_bytes(8, "little", signed=False))
        hasher.update(raw)
    return hasher.hexdigest()


@dataclass(frozen=True)
class CassiAllLayerTeacherWeave:
    """One source-labelled, frozen, stop-gradient all-layer Qwen observation."""

    source_model_sha256: str
    source_runtime_sha256: str
    token_index: int
    layer_vectors: tuple[Tensor, ...]
    capture_sha256: str

    @classmethod
    def from_layers(
        cls,
        layers: Sequence[Tensor],
        *,
        source_model_sha256: str,
        source_runtime_sha256: str,
        token_index: int,
    ) -> "CassiAllLayerTeacherWeave":
        _require_digest("teacher model hash", source_model_sha256)
        _require_digest("teacher runtime hash", source_runtime_sha256)
        if isinstance(token_index, bool) or not isinstance(token_index, int) or token_index < 0:
            raise CassiOrganismLawError("teacher token_index must be a nonnegative integer")
        if len(layers) < 1 or len(layers) > 1024:
            raise CassiOrganismLawError("teacher layer count exceeds its bounded geometry")
        copied: list[Tensor] = []
        for index, layer in enumerate(layers):
            if (
                not torch.is_tensor(layer)
                or not layer.dtype.is_floating_point
                or layer.ndim != 1
                or layer.numel() < 1
                or layer.numel() > 65536
            ):
                raise CassiOrganismLawError(
                    f"teacher layer {index} must be a bounded nonempty floating vector"
                )
            if not bool(torch.isfinite(layer).all().item()):
                raise CassiOrganismLawError(f"teacher layer {index} contains non-finite values")
            if float(layer.detach().abs().max().item()) > torch.finfo(torch.float32).max:
                raise CassiOrganismLawError(
                    f"teacher layer {index} exceeds finite float32 transport"
                )
            copied.append(layer.detach().to(device="cpu", dtype=torch.float32).contiguous().clone())
        values = tuple(copied)
        return cls(
            source_model_sha256=source_model_sha256,
            source_runtime_sha256=source_runtime_sha256,
            token_index=token_index,
            layer_vectors=values,
            capture_sha256=_capture_digest(
                values,
                source_model_sha256=source_model_sha256,
                source_runtime_sha256=source_runtime_sha256,
                token_index=token_index,
            ),
        )

    def validate(self, config: CassiOrganismConfig) -> None:
        _require_digest("teacher model hash", self.source_model_sha256)
        _require_digest("teacher runtime hash", self.source_runtime_sha256)
        _require_digest("teacher capture hash", self.capture_sha256)
        if isinstance(self.token_index, bool) or not isinstance(self.token_index, int) or self.token_index < 0:
            raise CassiOrganismLawError("teacher token_index must be a nonnegative integer")
        if len(self.layer_vectors) != config.teacher_layer_count:
            raise CassiOrganismLawError(
                f"teacher weave must contain every layer 0..{config.teacher_layer_count - 1} exactly once"
            )
        widths = {int(layer.numel()) for layer in self.layer_vectors if torch.is_tensor(layer)}
        if widths != {config.teacher_layer_width} or any(
            not torch.is_tensor(layer)
            or layer.ndim != 1
            or layer.dtype is not torch.float32
            or layer.device.type != "cpu"
            or layer.requires_grad
            or not bool(torch.isfinite(layer).all().item())
            for layer in self.layer_vectors
        ):
            raise CassiOrganismLawError(
                "teacher layers must match the configured width as detached finite CPU float32 vectors"
            )
        actual = _capture_digest(
            self.layer_vectors,
            source_model_sha256=self.source_model_sha256,
            source_runtime_sha256=self.source_runtime_sha256,
            token_index=self.token_index,
        )
        if actual != self.capture_sha256:
            raise CassiOrganismLawError("teacher capture hash mismatch")


@dataclass(frozen=True)
class CassiOrganismInput:
    """One bounded causal input; teacher/candidate tensors remain transient."""

    observation: Tensor | None = None
    boundary_symbol: int | None = None
    reward: float | None = None
    resource_credit: float = 0.0
    unexpectedness: float | None = None
    event_sha256: str | None = None
    teacher: CassiAllLayerTeacherWeave | None = None
    candidate_actions: Tensor | None = None
    metadata: bytes | bytearray | memoryview | Mapping[str, Any] | None = None


@dataclass(frozen=True)
class CassiResourceLedger:
    reserve_before: float
    external_credit_received: float
    external_credit_stored: float
    overflow_exported: float
    passive_dissipation: float
    field_work: float
    history_work: float
    model_work: float
    shadow_work: float
    action_work: float
    attention_work: float
    plasticity_work: float
    reserve_after: float
    closure_residual: float

    @property
    def total_work(self) -> float:
        return (
            self.field_work
            + self.history_work
            + self.model_work
            + self.shadow_work
            + self.action_work
            + self.attention_work
            + self.plasticity_work
        )


@dataclass(frozen=True)
class CassiTeacherWeaveReceipt:
    consumed: bool
    source_model_sha256: str | None
    source_runtime_sha256: str | None
    capture_sha256: str | None
    token_index: int | None
    layer_indices: tuple[int, ...]
    layer_sha256: tuple[str, ...]
    layer_l2: tuple[float, ...]
    raw_teacher_persisted: bool = False


@dataclass(frozen=True)
class CassiActionPopulationReceipt:
    evaluated_candidates: tuple[int, ...]
    computed_shadow_steps: int
    winner: int
    committed_candidate: int | None
    mass_before: tuple[float, ...]
    mass_after: tuple[float, ...]
    fitness: tuple[float, ...]


@dataclass(frozen=True)
class CassiLearningReceipt:
    prediction_error: float
    outcome_error: float | None
    surprise: float
    holdout_loss_before: float
    holdout_loss_after: float
    maturity_before: float
    maturity_after: float
    proposed_delta_linf: float
    applied_delta_linf: float
    accepted: bool
    reason: str


@dataclass(frozen=True)
class CassiOrganismStepReceipt:
    schema: str
    prior_state_sha256: str
    successor_state_sha256: str
    event_sha256: str | None
    boundary_schema: str
    boundary_symbol: int | None
    language_step_before: int
    language_step_after: int
    boundary_wave_sha256: str | None
    world_step: int
    boundary_before: tuple[float, ...]
    boundary_after: tuple[float, ...]
    attention_sum_before: float
    attention_sum_after: float
    density_conservation_residual: float
    imbalance_l1_before: float
    imbalance_l1_after: float
    ledger: CassiResourceLedger
    action_population: CassiActionPopulationReceipt
    learning: CassiLearningReceipt
    teacher: CassiTeacherWeaveReceipt

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True).encode("utf-8")


@dataclass(frozen=True)
class CassiOrganismStep:
    state: CassiOrganismState
    action: Tensor | None
    receipt: CassiOrganismStepReceipt


class CassiFieldOrganism:
    """One deterministic single-writer causal cycle over the product state."""

    def __init__(self, controller: QiFieldController, config: CassiOrganismConfig) -> None:
        if not isinstance(controller, QiFieldController) or not isinstance(config, CassiOrganismConfig):
            raise CassiOrganismLawError("controller and organism configuration are required")
        if controller.config.fingerprint != config.qi_config_fingerprint:
            raise CassiOrganismLawError("organism and Qi controller configuration mismatch")
        self.controller = controller
        self.config = config

    def _input(
        self,
        value: CassiOrganismInput,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> tuple[Tensor | None, int | None, float | None, float, float | None, Tensor | None]:
        if not isinstance(value, CassiOrganismInput):
            raise CassiOrganismLawError("step input must be CassiOrganismInput")
        observation: Tensor | None = None
        boundary_symbol: int | None = None
        if value.boundary_symbol is not None:
            if isinstance(value.boundary_symbol, bool) or not isinstance(value.boundary_symbol, int):
                raise CassiOrganismLawError("boundary_symbol must be an integer")
            if value.observation is not None:
                raise CassiOrganismLawError(
                    "boundary_symbol cannot be combined with an arbitrary observation"
                )
            if not 0 <= value.boundary_symbol < self.config.qi_alphabet_size:
                raise CassiOrganismLawError(
                    "boundary_symbol must be within the configured byte alphabet"
                )
            boundary_symbol = value.boundary_symbol
        if value.observation is not None:
            if not torch.is_tensor(value.observation) or not value.observation.dtype.is_floating_point:
                raise CassiOrganismLawError("observation must be a floating tensor")
            observation = value.observation.detach().to(device=device, dtype=dtype).reshape(-1)
            if (
                observation.numel() != self.config.world_observation_dim
                or not bool(torch.isfinite(observation).all().item())
                or bool(torch.any(observation.abs() > _MAX_CAUSAL_SCALAR).item())
            ):
                raise CassiOrganismLawError(
                    f"observation must contain {self.config.world_observation_dim} finite bounded values"
                )
        reward = (
            None
            if value.reward is None
            else _finite_real(
                "reward",
                value.reward,
                minimum=-_MAX_CAUSAL_SCALAR,
                maximum=_MAX_CAUSAL_SCALAR,
            )
        )
        credit = _finite_real(
            "resource_credit",
            value.resource_credit,
            minimum=0.0,
            maximum=_MAX_RESOURCE_CREDIT,
        )
        unexpected = (
            None
            if value.unexpectedness is None
            else _finite_real(
                "unexpectedness",
                value.unexpectedness,
                minimum=0.0,
                maximum=_MAX_CAUSAL_SCALAR,
            )
        )
        if value.event_sha256 is not None:
            _require_digest("event hash", value.event_sha256)
        if value.teacher is not None:
            value.teacher.validate(self.config)
        candidates: Tensor | None = None
        if value.candidate_actions is not None:
            candidate_actions = value.candidate_actions
            if (
                not torch.is_tensor(candidate_actions)
                or not candidate_actions.dtype.is_floating_point
                or candidate_actions.ndim != 3
                or int(candidate_actions.shape[0]) < 1
                or int(candidate_actions.shape[0]) > self.config.action_population_capacity
                or tuple(candidate_actions.shape[1:])
                != (self.config.action_horizon, self.config.world_action_dim)
            ):
                raise CassiOrganismLawError(
                    "candidate_actions must be finite [N,action_horizon,action_dim] "
                    "with 1 <= N <= action_population_capacity"
                )
            candidates = (
                candidate_actions.detach()
                .to(device=device, dtype=dtype)
                .contiguous()
                .clone()
            )
            if not bool(torch.isfinite(candidates).all().item()):
                raise CassiOrganismLawError(
                    "candidate_actions contains non-finite values"
                )
            if bool(torch.any((candidates < -1.0) | (candidates > 1.0)).item()):
                raise CassiOrganismLawError(
                    "candidate_actions must stay in [-1, 1]"
                )
        return observation, boundary_symbol, reward, credit, unexpected, candidates

    def _boundary_wave(
        self,
        symbol: int,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Tensor:
        """Return one fixed scale-zero chirp without retaining a boundary tensor."""

        codebook = self.controller.codebook(0, device=device, dtype=dtype)
        return codebook[symbol : symbol + 1].detach().contiguous()

    def _teacher_projection(
        self,
        teacher: CassiAllLayerTeacherWeave | None,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> tuple[Tensor, Tensor, CassiTeacherWeaveReceipt]:
        y_projection = torch.zeros(self.config.scale_count * 8, device=device, dtype=dtype)
        eligibility_projection = torch.zeros(self.config.theta_width, device=device, dtype=dtype)
        if teacher is None:
            return y_projection, eligibility_projection, CassiTeacherWeaveReceipt(
                False, None, None, None, None, (), (), ()
            )
        teacher.validate(self.config)
        layer_hashes: list[str] = []
        layer_norms: list[float] = []
        count = len(teacher.layer_vectors)
        for index, cpu_layer in enumerate(teacher.layer_vectors):
            raw = _tensor_bytes(cpu_layer)
            layer_hashes.append(_digest_bytes(raw))
            norm64 = torch.linalg.vector_norm(cpu_layer.to(torch.float64))
            norm = float(norm64.item())
            layer_norms.append(norm)
            rms64 = torch.sqrt(
                cpu_layer.to(torch.float64).square().mean()
            ).clamp_min(torch.finfo(torch.float64).eps)
            normalized = torch.tanh(
                cpu_layer.to(torch.float64) / rms64
            ).to(device=device, dtype=dtype)
            phase_weight = 1.0 + 0.25 * math.cos(
                2.0 * math.pi * (index + 0.5) / count
            )
            y_projection.add_(
                _resample_vector(normalized, y_projection.numel()),
                alpha=phase_weight / count,
            )
            eligibility_projection.add_(
                _resample_vector(normalized, eligibility_projection.numel()), alpha=phase_weight / count
            )
        return (
            torch.tanh(y_projection),
            torch.tanh(eligibility_projection),
            CassiTeacherWeaveReceipt(
                consumed=True,
                source_model_sha256=teacher.source_model_sha256,
                source_runtime_sha256=teacher.source_runtime_sha256,
                capture_sha256=teacher.capture_sha256,
                token_index=teacher.token_index,
                layer_indices=tuple(range(count)),
                layer_sha256=tuple(layer_hashes),
                layer_l2=tuple(layer_norms),
            ),
        )

    @staticmethod
    def _debit(reserve: Tensor, requested: float, *, partial: bool = False) -> float:
        if requested <= 0.0:
            return 0.0
        available = float(reserve.sum(dtype=torch.float64).item())
        if available <= 0.0 or (not partial and available + 1.0e-12 < requested):
            return 0.0
        target = min(requested, available) if partial else requested
        before = float(reserve.sum(dtype=torch.float64).item())
        reserve.mul_(max(0.0, 1.0 - target / available))
        after = float(reserve.sum(dtype=torch.float64).item())
        return max(0.0, before - after)

    def _sensation(self, qi: Tensor, observation: Tensor | None, teacher_y: Tensor) -> Tensor:
        intrinsic = qi[:, :8, :].mean(dim=2)
        result = intrinsic
        if observation is not None:
            result = result + 0.5 * _resample_vector(observation, result.numel()).reshape_as(result)
        result = result + 0.25 * teacher_y.reshape_as(result)
        return torch.tanh(result)

    def _unexpectedness(self, state: CassiOrganismState, observation: Tensor | None) -> tuple[float, Tensor]:
        if observation is None:
            return 0.0, torch.zeros(self.config.world_observation_dim, device=state.device, dtype=state.dtype)
        predicted = _resample_vector(
            state._sector_view("m")[: self.config.world_field_width],
            self.config.world_observation_dim,
        )
        observation64 = observation.to(torch.float64)
        predicted64 = predicted.to(torch.float64)
        difference64 = observation64 - predicted64
        observation_rms = torch.sqrt(observation64.square().mean())
        difference_rms = torch.sqrt(difference64.square().mean())
        denominator = 1.0 + float(observation_rms.item())
        normalized_error = torch.tanh(
            difference64 / denominator
        ).to(dtype=state.dtype)
        return float(difference_rms.item()) / denominator, normalized_error

    def _uncertainty(
        self,
        state: CassiOrganismState,
        model_error: Tensor,
        teacher: CassiTeacherWeaveReceipt,
        *,
        funded: bool,
    ) -> Tensor:
        """Update bounded prediction and teacher uncertainty statistics."""

        sigma = state._sector_view("Sigma")
        if not funded:
            return sigma.clone()
        target = torch.zeros_like(sigma)
        target[0] = torch.sqrt(model_error.square().mean())
        latent_stop = 1 + self.config.world_latent_dim
        target[1:latent_stop] = _resample_vector(model_error.abs(), self.config.world_latent_dim)
        if teacher.consumed:
            norms = torch.tensor(
                teacher.layer_l2,
                device=target.device,
                dtype=torch.float64,
            )
            norms = torch.log1p(norms)
            norms = norms / norms.max().clamp_min(1.0)
            target[latent_stop:] = norms.to(dtype=target.dtype)
        return torch.clamp(0.9 * sigma + 0.1 * target, min=0.0, max=10.0)

    def _history_record(
        self,
        *,
        y: Tensor,
        q: Tensor,
        epsilon: Tensor,
        boundary: Tensor,
        reserve: Tensor,
        unexpectedness: float,
        reward: float | None,
        predicted_reward: float,
        teacher_consumed: bool,
        winner: int,
        world_step: int,
    ) -> Tensor:
        """Encode one bounded, single-epoch consequence row."""

        record = torch.zeros(self.config.history_width, device=y.device, dtype=y.dtype)
        values = (
            world_step / float(_MAX_EXACT_FLOAT32_INTEGER),
            float(y.mean().item()),
            math.tanh(float(q.mean().item())),
            math.tanh(float(epsilon.mean().item())),
            float(boundary.mean().item()),
            float((reserve / self.config.law.reserve_capacity).mean().item()),
            float((boundary * reserve / self.config.law.reserve_capacity).mean().item()),
            0.0 if winner < 0 else winner / float(max(1, self.config.action_population_capacity - 1)),
            0.0 if reward is None else reward,
            math.tanh(unexpectedness),
            predicted_reward,
            1.0 if teacher_consumed else 0.0,
        )
        width = min(len(values), record.numel())
        record[:width] = torch.tensor(
            values[:width],
            device=record.device,
            dtype=record.dtype,
        )
        return record

    def _model_target(
        self,
        *,
        state: CassiOrganismState,
        y: Tensor,
        observation: Tensor | None,
        error: Tensor,
        reward: float | None,
        prior: Tensor,
        world_step: int,
    ) -> Tensor:
        """Build one observed-consequence target from sensation and history."""

        target = prior.clone()
        sensed = (
            y.reshape(-1)
            if observation is None
            else torch.cat((y.reshape(-1), observation))
        )
        target[: self.config.world_field_width] = torch.tanh(
            _resample_vector(
                sensed,
                self.config.world_field_width,
            )
        )
        history_context = state._sector_view("h")[: min(4, self.config.history_capacity)].reshape(-1)
        latent_source = torch.cat((error, y.reshape(-1).abs(), history_context))
        target[
            self.config.world_field_width : self.config.world_field_width
            + self.config.world_latent_dim
        ] = torch.tanh(
            _resample_vector(latent_source, self.config.world_latent_dim)
        )
        if reward is not None:
            target[0] = reward
        target[-1] = float(world_step)
        return target

    def _shadow_population(
        self,
        *,
        state: CassiOrganismState,
        model: Tensor,
        reserve: Tensor,
        boundary: Tensor,
        unexpectedness: float,
        work: dict[str, float],
        candidate_actions: Tensor | None,
        shadow_attention: float,
        action_attention: float,
    ) -> tuple[Tensor, Tensor, Tensor, CassiActionPopulationReceipt, Tensor | None]:
        """Advance only complete funded shadow branches and retain every other fitness."""

        config, law = self.config, self.config.law
        original_population = state._sector_view("p")
        population = original_population.clone()
        old_actions = original_population[:, : config.action_width].reshape(
            config.action_population_capacity,
            config.action_horizon,
            config.world_action_dim,
        )
        actions = population[:, : config.action_width].reshape(
            config.action_population_capacity,
            config.action_horizon,
            config.world_action_dim,
        )
        fitness = population[:, config.action_width + ACTION_FITNESS_OFFSET]
        scores = population[:, config.action_width + ACTION_SCORE_OFFSET]
        old_mass = population[:, config.action_width + ACTION_MASS_OFFSET].clone()
        old_commitment = population[
            :, config.action_width + ACTION_COMMITMENT_OFFSET
        ].clone()
        bands = population[:, config.action_width + ACTION_BAND_OFFSET]
        predicted_cost = population[
            :, config.action_width + ACTION_PREDICTED_COST_OFFSET
        ]
        information = population[
            :, config.action_width + ACTION_INFORMATION_OFFSET
        ]
        futures = state._sector_view("m_hat").clone()
        external_count = (
            0 if candidate_actions is None else int(candidate_actions.shape[0])
        )
        active_count = (
            config.action_population_capacity
            if candidate_actions is None
            else external_count
        )

        if candidate_actions is not None:
            changed = torch.any(
                old_actions[:external_count] != candidate_actions,
                dim=(1, 2),
            )
            actions[:external_count].copy_(candidate_actions)
            actions[external_count:].zero_()
            invalidated = torch.zeros(
                config.action_population_capacity,
                device=state.device,
                dtype=torch.bool,
            )
            invalidated[:external_count] = changed
            invalidated[external_count:] = True
            fitness[invalidated] = -1.0
            scores[invalidated] = 0.0
            old_commitment[invalidated] = 0.0
            bands[invalidated] = -1.0
            information[invalidated] = 0.0
            predicted_cost[invalidated] = 0.0
            futures[invalidated].zero_()
            active_mass = old_mass[:external_count]
            old_mass.zero_()
            old_mass[:external_count] = _simplex(active_mass)

        predicted_cost[:active_count] = actions[:active_count].square().mean(
            dim=(1, 2)
        )
        initial_valid = bands >= 0.0
        if candidate_actions is None:
            band_count = math.ceil(
                config.action_population_capacity / config.shadow_branches
            )
            band = int(model[-1].item()) % band_count
            start = band * config.shadow_branches
            band_values = list(
                range(
                    start,
                    min(
                        start + config.shadow_branches,
                        config.action_population_capacity,
                    ),
                )
            )
            committed_values = [
                int(candidate)
                for candidate in torch.nonzero(
                    old_commitment >= law.commitment_threshold,
                    as_tuple=False,
                ).reshape(-1).tolist()
            ]
            ordered = committed_values + [
                candidate
                for candidate in band_values
                if candidate not in committed_values
            ]
        else:
            band = 0
            committed_values = [
                int(candidate)
                for candidate in torch.nonzero(
                    old_commitment[:external_count] >= law.commitment_threshold,
                    as_tuple=False,
                ).reshape(-1).tolist()
            ]
            ordered = committed_values + [
                candidate
                for candidate in range(external_count)
                if candidate not in committed_values
            ]
        shadow_attention = min(1.0, max(0.0, shadow_attention))
        action_attention = min(1.0, max(0.0, action_attention))
        branch_budget = (
            0
            if shadow_attention <= 0.0
            else max(
                1,
                len(committed_values),
                math.ceil(len(ordered) * shadow_attention),
            )
        )
        planned = tuple(ordered[:branch_budget])

        evaluated: list[int] = []
        theta_drive = _resample_vector(
            state._sector_view("Theta"), config.model_width - 1
        )
        world_step = int(model[-1].item())
        branch_cost = law.shadow_step_cost * config.shadow_steps
        for candidate in planned:
            paid = self._debit(reserve, branch_cost)
            if branch_cost > 0.0 and paid <= 0.0:
                continue
            work["shadow"] += paid
            current = model.clone()
            current[:-1] = torch.tanh(current[:-1])
            if bool(initial_valid[candidate].item()):
                prior_future = futures[candidate, -1, :-1]
                current[:-1] = torch.tanh(
                    0.9 * current[:-1] + 0.1 * prior_future
                )
            prior_imagination = state._sector_view("u_hat")
            for future_step in range(config.shadow_steps):
                action = actions[
                    candidate, future_step % config.action_horizon
                ]
                inertial_action = (
                    (1.0 - 0.25 * action_attention) * action
                    + 0.25
                    * action_attention
                    * prior_imagination[future_step % config.action_horizon]
                )
                action_effect = _resample_vector(
                    inertial_action, config.model_width - 1
                )
                core = current[:-1]
                current[:-1] = torch.tanh(
                    (1.0 - law.shadow_rate) * core
                    + law.shadow_rate * action_attention * action_effect
                    + 0.025 * torch.tanh(theta_drive)
                )
                current[-1] = float(
                    min(
                        _MAX_EXACT_FLOAT32_INTEGER,
                        world_step + future_step + 1,
                    )
                )
                futures[candidate, future_step].copy_(current)
            final = futures[candidate, -1]
            bounded_origin = torch.tanh(model[:-1])
            displacement = torch.tanh(
                (final[:-1] - bounded_origin).abs().mean()
            )
            information[candidate] = displacement
            current_viability = torch.clamp(
                boundary * reserve / law.reserve_capacity,
                min=0.0,
                max=1.0,
            )
            fitness[candidate] = torch.tanh(
                final[0]
                + 0.25 * current_viability.mean()
                + 0.1 * action_attention * displacement
                - 0.2 * predicted_cost[candidate]
                - 0.1 * unexpectedness
            )
            bands[candidate] = float(band)
            evaluated.append(candidate)

        if not evaluated:
            original_mass = original_population[
                :, config.action_width + ACTION_MASS_OFFSET
            ]
            original_fitness = original_population[
                :, config.action_width + ACTION_FITNESS_OFFSET
            ]
            winner = -1
            return (
                original_population.clone(),
                state._sector_view("m_hat").clone(),
                state._sector_view("u_hat").clone(),
                CassiActionPopulationReceipt(
                    evaluated_candidates=(),
                    computed_shadow_steps=0,
                    winner=winner,
                    committed_candidate=None,
                    mass_before=tuple(
                        float(value) for value in original_mass.tolist()
                    ),
                    mass_after=tuple(
                        float(value) for value in original_mass.tolist()
                    ),
                    fitness=tuple(
                        float(value) for value in original_fitness.tolist()
                    ),
                ),
                None,
            )

        active_mask = torch.arange(
            config.action_population_capacity,
            device=state.device,
        ) < active_count
        valid = active_mask & (bands >= 0.0)
        valid_indices = torch.nonzero(valid, as_tuple=False).reshape(-1)
        newly_valid = valid & ~initial_valid
        mass_seed = old_mass.clone()
        mass_seed[~valid] = 0.0
        mass_seed[newly_valid] = torch.maximum(
            mass_seed[newly_valid],
            torch.full_like(
                mass_seed[newly_valid],
                1.0 / config.action_population_capacity,
            ),
        )
        active_mass = _simplex(mass_seed[valid_indices])
        active_fitness = fitness[valid_indices]
        mean_fitness = torch.sum(active_mass * active_fitness)
        laplacian = (
            torch.roll(active_mass, 1)
            + torch.roll(active_mass, -1)
            - 2.0 * active_mass
        )
        evolved_mass = _simplex(
            active_mass
            + law.time_step
            * (
                law.population_diffusion * laplacian
                + law.population_selection_rate
                * active_mass
                * (active_fitness - mean_fitness)
            )
        )
        mass = torch.zeros_like(old_mass)
        mass[valid_indices] = evolved_mass
        fresh_indices = torch.tensor(
            evaluated,
            device=state.device,
            dtype=torch.long,
        )
        fresh_fitness = fitness[fresh_indices]
        fresh_mass = mass[fresh_indices]
        winner_position = int(
            torch.argmax(fresh_fitness + 1.0e-4 * fresh_mass).item()
        )
        winner = int(fresh_indices[winner_position].item())
        active_scores = torch.softmax(active_fitness, dim=0)
        fresh_scores = torch.softmax(fresh_fitness, dim=0)
        confidence = float(
            (
                fresh_scores[winner_position] * fresh_indices.numel()
            ).clamp(max=1.0).item()
        )
        commitment = torch.clamp(
            old_commitment - law.time_step * law.release_threshold,
            min=0.0,
            max=1.0,
        )
        commitment[~valid] = 0.0
        commitment[winner] = torch.clamp(
            old_commitment[winner]
            + law.time_step * action_attention * confidence,
            min=0.0,
            max=1.0,
        )
        previously_committed = fresh_indices[
            old_commitment[fresh_indices] >= law.commitment_threshold
        ]
        committed: int | None = None
        if action_attention > 0.0 and previously_committed.numel():
            previous_position = torch.argmax(
                old_commitment[previously_committed]
            )
            candidate = int(previously_committed[previous_position].item())
            if float(commitment[candidate].item()) >= law.release_threshold:
                committed = candidate
        if (
            action_attention > 0.0
            and committed is None
            and float(commitment[winner].item()) >= law.commitment_threshold
        ):
            committed = winner

        scores.zero_()
        scores[valid_indices] = active_scores
        population[:, config.action_width + ACTION_FITNESS_OFFSET].copy_(
            fitness
        )
        population[:, config.action_width + ACTION_SCORE_OFFSET].copy_(scores)
        population[:, config.action_width + ACTION_MASS_OFFSET].copy_(mass)
        population[
            :, config.action_width + ACTION_COMMITMENT_OFFSET
        ].copy_(commitment)
        population[
            :, config.action_width + ACTION_PREDICTED_COST_OFFSET
        ].copy_(predicted_cost)
        population[
            :, config.action_width + ACTION_INFORMATION_OFFSET
        ].copy_(information)
        imagined_action = torch.sum(
            mass.reshape(-1, 1, 1) * actions,
            dim=0,
        )
        enacted: Tensor | None = None
        if committed is not None:
            candidate_action = actions[committed].clone()
            requested = action_attention * law.action_step_cost * (
                1.0 + float(candidate_action.abs().mean().item())
            )
            paid = self._debit(reserve, requested, partial=True)
            work["action"] += paid
            if requested <= 0.0 or paid > 0.0:
                fraction = (
                    1.0
                    if requested <= 0.0
                    else min(1.0, paid / requested)
                )
                enacted = candidate_action * fraction
            else:
                committed = None
        receipt = CassiActionPopulationReceipt(
            evaluated_candidates=tuple(evaluated),
            computed_shadow_steps=len(evaluated) * config.shadow_steps,
            winner=winner,
            committed_candidate=committed,
            mass_before=tuple(float(value) for value in old_mass.tolist()),
            mass_after=tuple(float(value) for value in mass.tolist()),
            fitness=tuple(float(value) for value in fitness.tolist()),
        )
        return population, futures, imagined_action, receipt, enacted

    def _attention(self, state: CassiOrganismState, y: Tensor, model_error: Tensor, population: Tensor) -> Tensor:
        law = self.config.law
        fitness = population[:, self.config.action_width + ACTION_FITNESS_OFFSET]
        eligibility = state._sector_view("e_Theta")
        prior = state._sector_view("g")
        utilities = _resample_vector(
            torch.cat((y.abs().reshape(-1), model_error.abs().reshape(-1), fitness.abs(), eligibility.abs())),
            self.config.attention_slots,
        )
        utilities = torch.tanh(utilities - utilities.mean())
        laplacian = torch.roll(prior, 1) + torch.roll(prior, -1) - 2.0 * prior
        mean_utility = torch.sum(prior * utilities)
        successor = prior + law.time_step * (
            law.attention_diffusion * laplacian
            + law.attention_selection_rate * prior * (utilities - mean_utility)
        )
        return _simplex(successor)

    def _attention_allocations(self, attention: Tensor) -> dict[str, float]:
        """Partition the conserved simplex into causal work allocations."""

        names = ("field", "history", "model", "shadow", "action", "attention", "plasticity")
        chunks = torch.tensor_split(attention, len(names))
        allocations = {
            name: float(chunk.sum(dtype=torch.float64).item())
            for name, chunk in zip(names, chunks, strict=True)
        }
        total = sum(allocations.values())
        if not math.isfinite(total) or abs(total - 1.0) > 1.0e-5:
            raise CassiOrganismLawError("attention allocations do not conserve the simplex")
        return allocations

    def _learn(
        self,
        *,
        state: CassiOrganismState,
        y: Tensor,
        model: Tensor,
        teacher_feature: Tensor,
        prediction_error: float,
        outcome_error: float | None,
        unexpectedness: float,
        funded: bool,
        attention: float,
        world_step: int,
    ) -> tuple[Tensor, Tensor, CassiLearningReceipt]:
        law = self.config.law
        feature = torch.tanh(
            _resample_vector(torch.cat((y.reshape(-1), model[:-1], teacher_feature)), self.config.theta_width)
        )
        surprise = max(unexpectedness, prediction_error, 0.0 if outcome_error is None else abs(outcome_error))
        prior_eligibility = state._sector_view("e_Theta")
        prior_theta = state._sector_view("Theta")
        attention = min(1.0, max(0.0, attention))
        eligibility = torch.clamp(
            law.eligibility_decay * prior_eligibility
            + attention * law.eligibility_rate * surprise * feature,
            min=-1.0,
            max=1.0,
        )
        theta = prior_theta.clone()
        coefficient_width = max(1, self.config.theta_width - 2)
        target = torch.tanh(_resample_vector(y.reshape(-1), coefficient_width))
        constitutive_feature = feature[:coefficient_width]
        current = theta[:coefficient_width]
        current_prediction = torch.tanh(current) * constitutive_feature
        signal = prediction_error if outcome_error is None else prediction_error + outcome_error
        rate = law.theta_prediction_rate if outcome_error is None else law.theta_outcome_rate
        delta = attention * rate * signal * eligibility[:coefficient_width]
        delta = delta - attention * law.theta_homeostasis * current
        delta = torch.clamp(delta, min=-law.theta_step_bound, max=law.theta_step_bound)
        proposed = torch.clamp(
            current + delta,
            min=-law.theta_absolute_bound,
            max=law.theta_absolute_bound,
        )
        holdout = torch.arange(coefficient_width, device=theta.device) % 2 != world_step % 2
        if not bool(torch.any(holdout).item()):
            holdout = torch.ones(coefficient_width, dtype=torch.bool, device=theta.device)
        before_loss = float((current_prediction[holdout] - target[holdout]).square().mean().item())
        after_prediction = torch.tanh(proposed) * constitutive_feature
        after_loss = float((after_prediction[holdout] - target[holdout]).square().mean().item())
        if not funded or attention <= 0.0:
            maturity = (
                float(prior_theta[self.config.theta_width - 2 + (world_step % 2)].item())
                if self.config.theta_width >= 2
                else 0.0
            )
            return prior_eligibility.clone(), prior_theta.clone(), CassiLearningReceipt(
                prediction_error=prediction_error,
                outcome_error=outcome_error,
                surprise=surprise,
                holdout_loss_before=before_loss,
                holdout_loss_after=after_loss,
                maturity_before=maturity,
                maturity_after=maturity,
                proposed_delta_linf=float(delta.abs().max().item()),
                applied_delta_linf=0.0,
                accepted=False,
                reason="attention-gated" if funded else "resource-gated",
            )
        maturity_slot = self.config.theta_width - 2 + (world_step % 2)
        maturity_before = float(theta[maturity_slot].item()) if self.config.theta_width >= 2 else 0.0
        improves = after_loss <= before_loss + 1.0e-9
        maturity_after = (
            min(1.0, maturity_before + 0.25 * attention)
            if improves
            else max(0.0, maturity_before - 0.5 * attention)
        )
        accepted = surprise >= law.unexpected_threshold and improves and maturity_after >= 0.5
        if accepted:
            theta[:coefficient_width].copy_(proposed)
        if self.config.theta_width >= 2:
            theta[maturity_slot] = maturity_after
        applied = float((theta[:coefficient_width] - current).abs().max().item())
        reason = "accepted"
        if not funded:
            reason = "resource-gated"
        elif attention <= 0.0:
            reason = "attention-gated"
        elif surprise < law.unexpected_threshold:
            reason = "surprise-below-threshold"
        elif not improves:
            reason = "holdout-regression"
        elif maturity_after < 0.5:
            reason = "maturation-incomplete"
        return eligibility, theta, CassiLearningReceipt(
            prediction_error=prediction_error,
            outcome_error=outcome_error,
            surprise=surprise,
            holdout_loss_before=before_loss,
            holdout_loss_after=after_loss,
            maturity_before=maturity_before,
            maturity_after=maturity_after,
            proposed_delta_linf=float(delta.abs().max().item()),
            applied_delta_linf=applied,
            accepted=accepted,
            reason=reason,
        )

    @torch.no_grad()
    def step(self, state: CassiOrganismState, value: CassiOrganismInput = CassiOrganismInput()) -> CassiOrganismStep:
        """Advance every live sector once and return one immutable successor."""

        if not isinstance(state, CassiOrganismState):
            raise CassiOrganismLawError("state must be a CassiOrganismState")
        try:
            state.validate(self.config)
        except CassiOrganismError as error:
            raise CassiOrganismLawError(f"organism state is invalid: {error}") from error
        device, dtype = state.device, state.dtype
        (
            observation,
            boundary_symbol,
            reward,
            credit_received,
            supplied_unexpected,
            candidate_actions,
        ) = self._input(value, device=device, dtype=dtype)
        # Keep the legacy receipt ordinal on the existing canonical world clock;
        # no language-sector clock or other adaptive state is retained.
        language_step_before = int(state._sector_view("m")[-1].item())
        language_step_after = language_step_before
        boundary_wave_sha256: str | None = None
        if boundary_symbol is not None:
            if language_step_before >= _MAX_EXACT_FLOAT32_INTEGER:
                raise CassiOrganismLawError(
                    "boundary_symbol cannot advance an exhausted exact language clock"
                )
            language_step_after += 1
        teacher_y, teacher_feature, teacher_receipt = self._teacher_projection(value.teacher, device=device, dtype=dtype)
        prior_sha = organism_state_sha256(state, self.config)
        law = self.config.law
        reserve = state._sector_view("a").clone()
        reserve_before = float(reserve.sum(dtype=torch.float64).item())
        capacity = torch.clamp(law.reserve_capacity - reserve, min=0.0)
        capacity_total = float(capacity.sum(dtype=torch.float64).item())
        requested_store = min(credit_received, capacity_total)
        if requested_store > 0.0:
            reserve.add_(capacity * (requested_store / capacity_total))
            reserve.clamp_(max=law.reserve_capacity)
        accepted_credit = max(
            0.0,
            float(reserve.sum(dtype=torch.float64).item()) - reserve_before,
        )
        overflow = max(0.0, credit_received - accepted_credit)
        passive = self._debit(
            reserve,
            law.passive_dissipation * law.time_step * float(state._sector_view("b").sum().item()),
            partial=True,
        )
        work = {name: 0.0 for name in ("field", "history", "model", "shadow", "action", "attention", "plasticity")}
        attention_allocations = self._attention_allocations(state._sector_view("g"))
        allocation_widths = {
            name: int(chunk.numel())
            for name, chunk in zip(
                attention_allocations,
                torch.tensor_split(state._sector_view("g"), len(attention_allocations)),
                strict=True,
            )
        }
        attention_strength = {
            name: min(
                1.0,
                mass * self.config.attention_slots / allocation_widths[name],
            )
            for name, mass in attention_allocations.items()
        }

        qi_state = qi_state_from_organism(state, self.config)
        conversion: QiBalanceConversion | None = None
        requested = law.field_step_cost * attention_allocations["field"]
        paid = self._debit(reserve, requested)
        field_funded = attention_strength["field"] > 0.0 and (
            requested <= 0.0 or paid > 0.0
        )
        if boundary_symbol is not None:
            if not field_funded:
                raise CassiResourceExhaustedError(
                    "resource_exhausted: boundary symbol requires a funded field cycle"
                )
            boundary_wave = self._boundary_wave(
                boundary_symbol,
                device=device,
                dtype=dtype,
            )
            boundary_wave_sha256 = _digest_bytes(_tensor_bytes(boundary_wave))
            qi_state = self.controller.sense_symbols(
                qi_state,
                (boundary_symbol,),
                source_trust=1.0,
            )
            observation = _resample_vector(
                boundary_wave.reshape(-1),
                self.config.world_observation_dim,
            )
        if field_funded:
            work["field"] += paid
            evolved = self.controller.evolve(qi_state, steps=1)
            conversion = self.controller.convert_balance(
                evolved,
                rate=law.conversion_rate,
                time_step=law.time_step,
            )
            qi_state = conversion.state
        qi_tensor = qi_state.field.reshape(self.config.scale_count, 9, self.config.qi_mode_count)
        evolved_q, evolved_epsilon = _qi_diagnostics(
            qi_tensor,
            self.config.qi_phi,
        )
        measured_unexpected, model_error = self._unexpectedness(state, observation)
        unexpectedness = measured_unexpected if supplied_unexpected is None else max(measured_unexpected, supplied_unexpected)
        if field_funded:
            y = self._sensation(qi_tensor, observation, teacher_y)
            self_signal = evolved_q.mean(dim=1)
            prior_boundary = state._sector_view("b")
            boundary = torch.clamp(
                prior_boundary
                + attention_strength["field"]
                * law.time_step
                * (
                    law.boundary_self_rate * (self_signal - prior_boundary)
                    - law.boundary_world_rate * unexpectedness * prior_boundary
                    - law.boundary_unexpected_rate * unexpectedness
                ),
                min=0.0,
                max=1.0,
            )
        else:
            y = state._sector_view("y").clone()
            boundary = state._sector_view("b").clone()
        viability = torch.clamp(boundary * reserve / law.reserve_capacity, min=0.0, max=1.0)
        current_model = state._sector_view("m")
        world_step = int(current_model[-1].item())
        next_world_step = min(_MAX_EXACT_FLOAT32_INTEGER, world_step + 1)
        predicted_reward = float(current_model[0].item())
        reward_signal = None if reward is None else math.tanh(reward)
        prediction_error = measured_unexpected
        outcome_error = (
            None
            if reward_signal is None
            else reward_signal - predicted_reward
        )

        model = current_model.clone()
        requested = law.model_step_cost * attention_allocations["model"]
        paid = self._debit(reserve, requested)
        model_funded = attention_strength["model"] > 0.0 and (
            requested <= 0.0 or paid > 0.0
        )
        if model_funded:
            work["model"] += paid
            model_target = self._model_target(
                state=state,
                y=y,
                observation=observation,
                error=model_error,
                reward=reward_signal,
                prior=current_model,
                world_step=next_world_step,
            )
            theta_rate = min(
                1.0,
                attention_strength["model"]
                * law.model_rate
                * (1.0 + 0.25 * math.tanh(float(state._sector_view("Theta")[0].item())))
                / (1.0 + float(state._sector_view("Sigma")[0].item())),
            )
            model[:-1] = (1.0 - theta_rate) * current_model[:-1] + theta_rate * model_target[:-1]
            model[-1] = float(next_world_step)
        else:
            next_world_step = world_step
        uncertainty = self._uncertainty(
            state,
            model_error,
            teacher_receipt,
            funded=model_funded,
        )

        population, futures, imagined_action, action_receipt, enacted = self._shadow_population(
            state=state,
            model=model,
            reserve=reserve,
            boundary=boundary,
            unexpectedness=unexpectedness,
            work=work,
            candidate_actions=candidate_actions,
            shadow_attention=attention_strength["shadow"],
            action_attention=attention_strength["action"],
        )
        if action_receipt.computed_shadow_steps == 0:
            u = state._sector_view("u").clone()
            u_hat = state._sector_view("u_hat").clone()
        else:
            u = torch.zeros_like(state._sector_view("u")) if enacted is None else enacted
            u_hat = imagined_action

        history = state._sector_view("h").clone()
        requested = law.history_write_cost * attention_allocations["history"]
        paid = self._debit(reserve, requested)
        history_funded = attention_strength["history"] > 0.0 and (
            requested <= 0.0 or paid > 0.0
        )
        if history_funded:
            work["history"] += paid
            proposal = history.clone()
            if proposal.shape[0] > 1:
                proposal[1:] = law.history_decay * proposal[:-1].clone()
            proposal[0] = self._history_record(
                y=y,
                q=evolved_q,
                epsilon=evolved_epsilon,
                boundary=boundary,
                reserve=reserve,
                unexpectedness=unexpectedness,
                reward=reward_signal,
                predicted_reward=predicted_reward,
                teacher_consumed=teacher_receipt.consumed,
                winner=action_receipt.winner,
                world_step=next_world_step,
            )
            history = (
                (1.0 - attention_strength["history"]) * history
                + attention_strength["history"] * proposal
            )

        requested = law.attention_step_cost * attention_allocations["attention"]
        paid = self._debit(reserve, requested)
        attention_funded = attention_strength["attention"] > 0.0 and (
            requested <= 0.0 or paid > 0.0
        )
        if attention_funded:
            work["attention"] += paid
            proposed_attention = self._attention(state, y, model_error, population)
            attention = _simplex(
                (1.0 - attention_strength["attention"]) * state._sector_view("g")
                + attention_strength["attention"] * proposed_attention
            )
        else:
            attention = state._sector_view("g").clone()

        plasticity_requested = (
            law.plasticity_step_cost * attention_allocations["plasticity"]
        )
        plasticity_paid = self._debit(reserve, plasticity_requested)
        plasticity_funded = attention_strength["plasticity"] > 0.0 and (
            plasticity_requested <= 0.0 or plasticity_paid > 0.0
        )
        if plasticity_funded:
            work["plasticity"] += plasticity_paid
        eligibility, theta, learning = self._learn(
            state=state,
            y=y,
            model=model,
            teacher_feature=teacher_feature,
            prediction_error=prediction_error,
            outcome_error=outcome_error,
            unexpectedness=unexpectedness,
            funded=plasticity_funded,
            attention=attention_strength["plasticity"],
            world_step=next_world_step,
        )
        viability = torch.clamp(boundary * reserve / law.reserve_capacity, min=0.0, max=1.0)
        population[
            :, self.config.action_width + ACTION_VIABILITY_OFFSET
        ].fill_(float(viability.mean().item()))
        successor_sectors = {
            "qi": qi_tensor,
            "b": boundary,
            "a": reserve,
            "z": viability,
            "y": y,
            "u": u,
            "u_hat": u_hat,
            "h": history,
            "m": model,
            "m_hat": futures,
            "p": population,
            "g": attention,
            "e_Theta": eligibility,
            "Theta": theta,
            "Sigma": uncertainty,
        }
        try:
            successor = successor_organism_state(
                state,
                self.config,
                sectors=successor_sectors,
                metadata=state.metadata if value.metadata is None else value.metadata,
            )
        except CassiOrganismError as error:
            raise CassiOrganismLawError(f"organism successor violates its product-state contract: {error}") from error
        reserve_after = float(reserve.sum(dtype=torch.float64).item())
        total_work = sum(work.values())
        closure = reserve_after - (reserve_before + accepted_credit - passive - total_work)
        ledger = CassiResourceLedger(
            reserve_before=reserve_before,
            external_credit_received=credit_received,
            external_credit_stored=accepted_credit,
            overflow_exported=overflow,
            passive_dissipation=passive,
            field_work=work["field"],
            history_work=work["history"],
            model_work=work["model"],
            shadow_work=work["shadow"],
            action_work=work["action"],
            attention_work=work["attention"],
            plasticity_work=work["plasticity"],
            reserve_after=reserve_after,
            closure_residual=closure,
        )
        if abs(closure) > 5.0e-5:
            raise CassiOrganismLawError(f"resource ledger does not close: residual={closure}")
        density_residual = 0.0
        imbalance_before = float(state.epsilon.abs().sum().item())
        imbalance_after = float(successor.epsilon.abs().sum().item())
        if conversion is not None:
            density_residual = float((conversion.density_after - conversion.density_before).abs().max().item())
            imbalance_before = float(conversion.imbalance_l1_before.sum().item())
            imbalance_after = float(conversion.imbalance_l1_after.sum().item())
        receipt = CassiOrganismStepReceipt(
            schema=ORGANISM_STEP_RECEIPT_SCHEMA,
            prior_state_sha256=prior_sha,
            successor_state_sha256=organism_state_sha256(successor, self.config),
            event_sha256=value.event_sha256,
            boundary_schema=FIELD_TEXT_CODEC_SCHEMA,
            boundary_symbol=boundary_symbol,
            language_step_before=language_step_before,
            language_step_after=language_step_after,
            boundary_wave_sha256=boundary_wave_sha256,
            world_step=next_world_step,
            boundary_before=tuple(float(item) for item in state._sector_view("b").tolist()),
            boundary_after=tuple(float(item) for item in boundary.tolist()),
            attention_sum_before=float(state._sector_view("g").sum().item()),
            attention_sum_after=float(attention.sum().item()),
            density_conservation_residual=density_residual,
            imbalance_l1_before=imbalance_before,
            imbalance_l1_after=imbalance_after,
            ledger=ledger,
            action_population=action_receipt,
            learning=learning,
            teacher=teacher_receipt,
        )
        return CassiOrganismStep(
            state=successor,
            action=None if enacted is None else enacted.unsqueeze(0).detach().clone(),
            receipt=receipt,
        )

    def finalize_step(
        self,
        step: CassiOrganismStep,
        *,
        event_sha256: str,
        metadata: bytes | bytearray | memoryview | Mapping[str, Any] | None = None,
    ) -> CassiOrganismStep:
        """Bind a prepared adaptive successor to its immutable event and metadata."""

        if not isinstance(step, CassiOrganismStep):
            raise CassiOrganismLawError("finalized value must be a CassiOrganismStep")
        _require_digest("event hash", event_sha256)
        if step.receipt.event_sha256 not in (None, event_sha256):
            raise CassiOrganismLawError("organism step is already bound to a different event")
        try:
            state = (
                step.state
                if metadata is None
                else successor_organism_state(step.state, self.config, metadata=metadata)
            )
        except CassiOrganismError as error:
            raise CassiOrganismLawError(f"organism step metadata is invalid: {error}") from error
        receipt = replace(
            step.receipt,
            event_sha256=event_sha256,
            successor_state_sha256=organism_state_sha256(state, self.config),
        )
        return CassiOrganismStep(
            state=state,
            action=None if step.action is None else step.action.detach().clone(),
            receipt=receipt,
        )


__all__ = [
    "ORGANISM_STEP_RECEIPT_SCHEMA",
    "TEACHER_WEAVE_SCHEMA",
    "CassiActionPopulationReceipt",
    "CassiAllLayerTeacherWeave",
    "CassiFieldOrganism",
    "CassiLearningReceipt",
    "CassiOrganismInput",
    "CassiOrganismLawError",
    "CassiOrganismStep",
    "CassiOrganismStepReceipt",
    "CassiResourceExhaustedError",
    "CassiResourceLedger",
    "CassiTeacherWeaveReceipt",
]
