"""Conscious-field orchestration over the canonical deterministic Qi field.

This module is a functional control layer, not a phenomenological claim.  The
Qi field remains the sole adaptive state.  Events provide immutable provenance;
explicit tensor waves are accepted only when the event carries the exact hash
of the tensor bytes that the caller supplied.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Sequence

import torch
from torch import Tensor

from cassi_conscious_protocol import (
    ActorClass,
    BranchStatus,
    CassiContradictionReceipt,
    CassiExperienceEvent,
    CassiPredictionReceipt,
    EventKind,
    RealityStatus,
    create_event,
    validate_event,
)
from cassi_qi_field import QiFieldController, QiFieldError, QiFieldReadout, QiFieldState


_EVENT_KIND_LANES = {event_kind: index + 1 for index, event_kind in enumerate(EventKind)}
_REALITY_STATUS_LANES = {
    reality_status: index + 1
    for index, reality_status in enumerate(RealityStatus)
}
_ACTOR_CLASS_LANES = {
    actor_class: index + 1
    for index, actor_class in enumerate(ActorClass)
}

CONSCIOUS_FIELD_PROFILE_ID = "cassi.conscious-field.qi-v2.v2"
BOUNDARY_PROFILE_ID = "cassi.conscious-boundary.byte-positional.v2"
INTEROCEPTIVE_LAYOUT_ID = "cassi.conscious.interoception.seven-vector.v1"


class CassiConsciousFieldError(ValueError):
    """Raised when a conscious-field state, event, or branch is invalid."""


class AccessLevel(str, Enum):
    """Public readout access levels."""

    ACCESSIBLE = "accessible"
    LOCAL_ONLY = "local_only"
    ABSTAIN = "abstain"
    UNCERTAIN = "uncertain"
    CONTRADICTED = "contradicted"


class MetacognitiveState(str, Enum):
    """Finite metacognitive classification derived from field readout."""

    ACCESSIBLE = "accessible"
    LOCAL_ONLY = "local_only"
    ABSTAIN = "abstain"
    UNCERTAIN = "uncertain"
    CONTRADICTED = "contradicted"


def _unit_interval(value: float) -> float:
    """Return a finite scalar clipped to the unit interval."""

    if not math.isfinite(value):
        raise CassiConsciousFieldError("non-finite conscious-field value")
    return max(0.0, min(1.0, float(value)))


def tensor_wave_sha256(wave: Tensor) -> str:
    """Hash the exact detached tensor bytes used at an explicit wave boundary.

    The hash intentionally covers tensor storage bytes, but not an assertion
    about the event source.  Callers should create the event with this value
    before passing the same wave to ``perceive``, ``begin_imagination``,
    ``receive_report``, or reconciliation APIs.
    """

    if not torch.is_tensor(wave):
        raise CassiConsciousFieldError("tensor wave must be a torch.Tensor")
    return hashlib.sha256(wave.detach().contiguous().cpu().numpy().tobytes()).hexdigest()


def _field_sha256(state: QiFieldState) -> str:
    """Hash the sole adaptive field tensor in a Qi state."""

    return tensor_wave_sha256(state.field)


def _require_exact_int(name: str, value: object, *, minimum: int | None = None) -> int:
    """Validate an integer without accepting Python booleans."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise CassiConsciousFieldError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise CassiConsciousFieldError(f"{name} must be at least {minimum}")
    return value


def _validate_optional_digest(name: str, value: object) -> str:
    """Validate an optional lower-case SHA-256 digest for field-owned values."""

    if not isinstance(value, str):
        raise CassiConsciousFieldError(f"{name} must be a string digest")
    if value == "":
        return value
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise CassiConsciousFieldError(f"{name} must be a lower-case SHA-256 digest")
    return value


@dataclass(frozen=True)
class ProvenancePolicy:
    """Fixed trust multipliers for event reality statuses."""

    observed_trust: float = 1.0
    reported_evidence_trust: float = 0.6
    local_intent_trust: float = 0.85
    hypothesis_trust: float = 0.45
    recall_trust: float = 0.35
    deliberation_trust: float = 0.3
    teacher_trust: float = 0.4
    contradiction_trust: float = 0.8

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise CassiConsciousFieldError(f"invalid {field_name}")

    def trust_for(self, event: CassiExperienceEvent) -> float:
        """Return the fixed trust multiplier for a validated event."""

        validate_event(event)
        trust_by_status = {
            RealityStatus.OBSERVED_REALITY: self.observed_trust,
            RealityStatus.REPORTED_EVIDENCE: self.reported_evidence_trust,
            RealityStatus.AGENT_INTENT: self.local_intent_trust,
            RealityStatus.HYPOTHESIS: self.hypothesis_trust,
            RealityStatus.DERIVED_RECALL: self.recall_trust,
            RealityStatus.DERIVED_DELIBERATION: self.deliberation_trust,
            RealityStatus.EXTERNAL_PROPOSAL: self.teacher_trust,
            RealityStatus.CONTRADICTION_FACT: self.contradiction_trust,
        }
        return trust_by_status[event.reality_status]


@dataclass(frozen=True)
class ConsciousFieldConfig:
    """Thresholds and fixed controls for the single-lane orchestrator."""

    provenance: ProvenancePolicy = ProvenancePolicy()
    access_threshold: float = 0.12
    minimum_access_scales: int = 2
    minimum_cross_scale_coherence: float = 0.55
    maximum_access_uncertainty: float = 0.9
    metadata_amplitude: float = 0.08
    maximum_correction_gain: float = 0.45
    contradiction_gain: float = 0.18
    recurrence_floor: float = 0.1
    maximum_wave_magnitude: float = 1.0
    boundary_chunk_size: int = 128
    maximum_action_candidates: int = 32
    maximum_imagination_steps: int = 64

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, ProvenancePolicy):
            raise CassiConsciousFieldError("provenance must be a ProvenancePolicy")
        _require_exact_int("minimum_access_scales", self.minimum_access_scales, minimum=1)
        _require_exact_int("boundary_chunk_size", self.boundary_chunk_size, minimum=1)
        if _require_exact_int(
            "maximum_action_candidates",
            self.maximum_action_candidates,
            minimum=1,
        ) > 32:
            raise CassiConsciousFieldError("maximum_action_candidates exceeds hard limit")
        if _require_exact_int(
            "maximum_imagination_steps",
            self.maximum_imagination_steps,
            minimum=1,
        ) > 64:
            raise CassiConsciousFieldError("maximum_imagination_steps exceeds hard limit")
        bounded_fields = (
            "access_threshold",
            "minimum_cross_scale_coherence",
            "maximum_access_uncertainty",
            "metadata_amplitude",
            "maximum_correction_gain",
            "contradiction_gain",
            "recurrence_floor",
            "maximum_wave_magnitude",
        )
        for field_name in bounded_fields:
            value = getattr(self, field_name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
                or (field_name == "maximum_wave_magnitude" and value == 0.0)
            ):
                raise CassiConsciousFieldError(f"invalid {field_name}")


@dataclass(frozen=True)
class SelfCondensate:
    """Bounded structural summary of the current Qi state."""

    fast_differential: float
    slow_differential: float
    velocity_organization: float
    epsilon_stability: float
    cross_scale_coherence: float
    scale_current: float
    continuity: float
    structural_strength: float
    fingerprint: str


@dataclass(frozen=True)
class ConsciousAccess:
    """Access decision and the readout metrics supporting it."""

    level: AccessLevel
    granted: bool
    participating_scales: int
    cross_scale_coherence: float
    uncertainty: float
    reason: str


@dataclass(frozen=True)
class InteroceptiveValueReadout:
    """Seven-dimensional bounded value readout used for candidate scoring."""

    energy_safety: float
    coherence: float
    access: float
    contradiction_pressure: float
    slow_continuity: float
    controllability_evidence: float
    uncertainty: float

    @property
    def vector(self) -> tuple[float, ...]:
        """Return values in the stable interoceptive layout order."""

        return (
            self.energy_safety,
            self.coherence,
            self.access,
            self.contradiction_pressure,
            self.slow_continuity,
            self.controllability_evidence,
            self.uncertainty,
        )


@dataclass(frozen=True)
class MetacognitiveReadout:
    """Classification, confidence metrics, and optional source status."""

    state: MetacognitiveState
    access: ConsciousAccess
    margin: float
    uncertainty: float
    source_status: RealityStatus | None
    residual_energy: float


@dataclass(frozen=True)
class EligibilityReadout:
    """Per-scale eligibility for a local action-intent event."""

    per_scale: tuple[float, ...]
    salience: float
    reliability: float
    self_relevance: float
    recurrence: float


@dataclass(frozen=True)
class AgencyReadout:
    """Bounded agency attribution, never a causal-proof claim."""

    supported: bool
    evidence: float
    reason: str


@dataclass(frozen=True)
class ConsciousTransition:
    """State and readouts produced by one committed event."""

    state: QiFieldState
    event: CassiExperienceEvent
    input_wave: Tensor
    emission: QiFieldReadout
    self_condensate: SelfCondensate
    access: ConsciousAccess
    correction_energy: float
    applied_correction_gain: float


@dataclass(frozen=True)
class CassiConsciousBranch:
    """Open imagination state with a complete prediction receipt."""

    branch_id: str
    root_field_sha256: str
    root_event_id: str
    proposal_event: CassiExperienceEvent
    state: QiFieldState
    branch_state_sha256: str
    proposal_wave: Tensor
    predicted_wave: Tensor
    receipt: CassiPredictionReceipt
    steps: int
    status: BranchStatus = BranchStatus.OPEN


@dataclass(frozen=True)
class CassiRecallResult:
    """Readout from a strictly typed derived-recall event."""

    event: CassiExperienceEvent
    symbol: int
    available: bool
    access: ConsciousAccess
    uncertainty: float


@dataclass(frozen=True)
class CassiActionProposal:
    """Selected candidate action and its authenticated imagination branch."""

    intent: CassiExperienceEvent
    access: ConsciousAccess
    branch: CassiConsciousBranch
    value: InteroceptiveValueReadout
    score: float
    candidate_index: int
    inert: bool = True


@dataclass(frozen=True)
class CassiCommitmentProposal:
    """One inert locally owned commitment selected from fixed safe candidates."""

    event: CassiExperienceEvent
    access: ConsciousAccess
    value: InteroceptiveValueReadout
    score: float
    candidate_index: int


@dataclass(frozen=True)
class ConsciousReconciliation:
    """Observed transition and branch comparison result."""

    state: QiFieldState
    actual: ConsciousTransition
    contradiction: CassiContradictionReceipt
    contradiction_event: CassiExperienceEvent | None
    branch_status: BranchStatus
    semantic_trace_energy: float


class CassiConsciousBoundary:
    """Deterministic byte/metadata transducer at the Qi field boundary."""

    def __init__(self, controller: QiFieldController, config: ConsciousFieldConfig) -> None:
        if not isinstance(controller, QiFieldController):
            raise CassiConsciousFieldError("controller must be a QiFieldController")
        if not isinstance(config, ConsciousFieldConfig):
            raise CassiConsciousFieldError("config must be a ConsciousFieldConfig")
        if controller.config.alphabet_size < 260:
            raise CassiConsciousFieldError("alphabet must be >=260")
        self.controller = controller
        self.config = config

    def validate_wave(self, wave: Tensor, state: QiFieldState) -> Tensor:
        """Validate an explicit ``[1, wave_modes, 2]`` tensor at state precision."""

        if not torch.is_tensor(wave) or tuple(wave.shape) != (
            1,
            self.controller.config.wave_mode_count,
            2,
        ):
            raise CassiConsciousFieldError("wave must be exact [1,W,2]")
        if (
            not wave.dtype.is_floating_point
            or wave.dtype != state.field.dtype
            or wave.device != state.field.device
            or not bool(torch.isfinite(wave).all())
        ):
            raise CassiConsciousFieldError("wave must be finite and root device/dtype exact")
        magnitude = float(torch.linalg.vector_norm(wave, dim=-1).amax())
        if magnitude > self.config.maximum_wave_magnitude + 1.0e-6:
            raise CassiConsciousFieldError("wave magnitude exceeds bound")
        return wave.contiguous()

    def _bound(self, wave: Tensor) -> Tensor:
        """Apply the configured per-mode vector-magnitude bound."""

        if not torch.is_tensor(wave) or not bool(torch.isfinite(wave).all()):
            raise CassiConsciousFieldError("non-finite boundary")
        magnitude = torch.linalg.vector_norm(wave, dim=-1, keepdim=True)
        epsilon = torch.finfo(wave.dtype).eps
        scale = torch.clamp(
            self.config.maximum_wave_magnitude / torch.clamp_min(magnitude, epsilon),
            max=1.0,
        )
        return (wave * scale).contiguous()

    def encode(self, event: CassiExperienceEvent, state: QiFieldState) -> Tensor:
        """Encode event bytes and fixed metadata into a bounded boundary wave."""

        validate_event(event)
        width = self.controller.config.wave_mode_count
        device = state.field.device
        dtype = state.field.dtype
        codebook = self.controller.codebook(0, device=device, dtype=dtype)
        coefficients = torch.zeros((256, width, 2), device=device, dtype=dtype)
        modes = torch.arange(width, device=device, dtype=dtype)[None, :] + 1

        for start_index in range(0, len(event.payload), self.config.boundary_chunk_size):
            payload_slice = event.payload[start_index : start_index + self.config.boundary_chunk_size]
            values = torch.tensor(list(payload_slice), device=device, dtype=torch.long)
            positions = torch.arange(
                start_index,
                start_index + len(values),
                device=device,
                dtype=dtype,
            )[:, None] + 1
            phase = 2.0 * math.pi * (
                positions * modes.square() + positions.square() * modes
            ) / 4093.0
            coefficients.index_add_(
                0,
                values,
                torch.stack((torch.cos(phase), torch.sin(phase)), dim=-1),
            )

        coefficient_real = coefficients[..., 0]
        coefficient_imaginary = coefficients[..., 1]
        codebook_real = codebook[:256, :, 0]
        codebook_imaginary = codebook[:256, :, 1]
        wave_real = (
            coefficient_real * codebook_real
            - coefficient_imaginary * codebook_imaginary
        ).sum(dim=0)
        wave_imaginary = (
            coefficient_real * codebook_imaginary
            + coefficient_imaginary * codebook_real
        ).sum(dim=0)
        boundary_wave = torch.stack((wave_real, wave_imaginary), dim=-1)
        if event.payload:
            boundary_wave = boundary_wave / math.sqrt(len(event.payload))

        first_mode = modes[0]
        metadata_values = (
            _EVENT_KIND_LANES[event.kind],
            _REALITY_STATUS_LANES[event.reality_status],
            _ACTOR_CLASS_LANES[event.actor],
            int(
                hashlib.sha256(
                    (event.branch_id or event.parent_event_id or event.source_id).encode()
                ).hexdigest()[:12],
                16,
            ),
        )
        for lane_index, metadata_value in enumerate(metadata_values):
            phase = 2.0 * math.pi * (
                float(metadata_value) * first_mode
                + (lane_index + 1) * first_mode.square()
            ) / 4099.0
            rotation_real = torch.cos(phase)
            rotation_imaginary = torch.sin(phase)
            metadata_real = codebook[256 + lane_index, :, 0]
            metadata_imaginary = codebook[256 + lane_index, :, 1]
            boundary_wave[:, 0] += self.config.metadata_amplitude * (
                metadata_real * rotation_real - metadata_imaginary * rotation_imaginary
            )
            boundary_wave[:, 1] += self.config.metadata_amplitude * (
                metadata_real * rotation_imaginary + metadata_imaginary * rotation_real
            )
        return self._bound(boundary_wave.unsqueeze(0))


class CassiConsciousField:
    """Single-lane conscious-field controller over one canonical Qi state."""

    def __init__(
        self,
        controller: QiFieldController,
        config: ConsciousFieldConfig | None = None,
    ) -> None:
        if not isinstance(controller, QiFieldController):
            raise CassiConsciousFieldError("controller must be a QiFieldController")
        resolved_config = ConsciousFieldConfig() if config is None else config
        if not isinstance(resolved_config, ConsciousFieldConfig):
            raise CassiConsciousFieldError("config must be a ConsciousFieldConfig")
        if controller.config.alphabet_size < 260:
            raise CassiConsciousFieldError("alphabet must be >=260")
        if config is None and controller.config.scale_count < resolved_config.minimum_access_scales:
            resolved_config = replace(
                resolved_config,
                minimum_access_scales=controller.config.scale_count,
            )
        if resolved_config.minimum_access_scales > controller.config.scale_count:
            raise CassiConsciousFieldError("minimum_access_scales exceeds scale_count")
        self.controller = controller
        self.config = resolved_config
        self.boundary = CassiConsciousBoundary(controller, resolved_config)

    def initial_state(
        self,
        batch_size: int = 1,
        *,
        device: torch.device | str = "cpu",
        dtype: torch.dtype = torch.float32,
    ) -> QiFieldState:
        """Create the single owner state; batch sizes other than one are rejected."""

        _require_exact_int("batch_size", batch_size, minimum=1)
        if batch_size != 1:
            raise CassiConsciousFieldError("single-lane owner requires batch_size == 1")
        try:
            state = self.controller.initial_state(1, device=device, dtype=dtype)
        except QiFieldError as exc:
            raise CassiConsciousFieldError(str(exc)) from exc
        return state

    def _state(self, state: QiFieldState) -> QiFieldState:
        """Validate owner, shape, device, dtype, and finite-value invariants."""

        if not isinstance(state, QiFieldState):
            raise CassiConsciousFieldError("QiFieldState required")
        if state.batch_size != 1:
            raise CassiConsciousFieldError("single-lane owner rejects multi-lane state")
        try:
            self.controller._validate_state(state)
        except QiFieldError as exc:
            raise CassiConsciousFieldError(str(exc)) from exc
        return state

    def _require_event_shape(
        self,
        event: CassiExperienceEvent,
        *,
        kind: EventKind,
        reality_status: RealityStatus,
        actor: ActorClass,
        message: str,
    ) -> None:
        """Require an exact event kind/status/actor contract."""

        if (
            event.kind is not kind
            or event.reality_status is not reality_status
            or event.actor is not actor
        ):
            raise CassiConsciousFieldError(message)

    def _direct(self, event: CassiExperienceEvent) -> bool:
        """Return whether an event is an observed direct perception/outcome."""

        return (
            event.reality_status is RealityStatus.OBSERVED_REALITY
            and event.kind in {EventKind.PERCEPTION, EventKind.ACTION_OUTCOME}
        )

    def _corrective(self, event: CassiExperienceEvent) -> bool:
        """Return whether an event is allowed to correct the field."""

        return self._direct(event) or (
            event.kind is EventKind.EXTERNAL_REPORT
            and event.reality_status is RealityStatus.REPORTED_EVIDENCE
        )

    def _resolve_boundary_wave(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
        explicit_wave: Tensor | None,
        *,
        boundary_name: str,
    ) -> Tensor:
        """Encode bytes or verify an explicit wave's event-boundary binding."""

        if explicit_wave is None:
            if event.boundary_wave_sha256:
                raise CassiConsciousFieldError(
                    f"{boundary_name} event boundary hash requires an explicit wave"
                )
            return self.boundary.encode(event, state)
        wave = self.boundary.validate_wave(explicit_wave, state)
        if not event.boundary_wave_sha256:
            raise CassiConsciousFieldError(
                f"{boundary_name} explicit wave requires event boundary_wave_sha256"
            )
        expected_digest = tensor_wave_sha256(wave)
        if event.boundary_wave_sha256 != expected_digest:
            raise CassiConsciousFieldError(
                f"{boundary_name} wave is not bound by event boundary_wave_sha256"
            )
        return wave

    def _access_from_readout(
        self,
        state: QiFieldState,
        readout: QiFieldReadout,
    ) -> ConsciousAccess:
        """Convert a Qi readout into the conservative public access gate."""

        participating_scales = int((readout.contribution_weights[:, 0] > 1.0e-7).sum().item())
        cross_scale_coherence = _unit_interval(float(readout.cross_scale_coherence[0].item()))
        uncertainty = _unit_interval(float(readout.uncertainty[0].item()))
        if not bool(readout.available[0].item()):
            return ConsciousAccess(
                AccessLevel.ABSTAIN,
                False,
                participating_scales,
                cross_scale_coherence,
                uncertainty,
                "field/readout unavailable",
            )
        if (
            participating_scales < self.config.minimum_access_scales
            or cross_scale_coherence < self.config.minimum_cross_scale_coherence
        ):
            return ConsciousAccess(
                AccessLevel.LOCAL_ONLY,
                False,
                participating_scales,
                cross_scale_coherence,
                uncertainty,
                "insufficient cross-scale participation",
            )
        if (
            uncertainty > self.config.maximum_access_uncertainty
            or float(readout.read_gate[0].item()) < self.config.access_threshold
        ):
            return ConsciousAccess(
                AccessLevel.LOCAL_ONLY,
                False,
                participating_scales,
                cross_scale_coherence,
                uncertainty,
                "uncertain or weak read gate",
            )
        return ConsciousAccess(
            AccessLevel.ACCESSIBLE,
            True,
            participating_scales,
            cross_scale_coherence,
            uncertainty,
            "cross-scale access granted",
        )

    def access_gate(self, state: QiFieldState) -> ConsciousAccess:
        """Return the conservative access decision for a validated state."""

        validated_state = self._state(state)
        return self._access_from_readout(
            validated_state,
            self.controller.emit(validated_state),
        )

    def structural_self(
        self,
        state: QiFieldState,
        prior_state: QiFieldState | None = None,
    ) -> SelfCondensate:
        """Read bounded Yang/Yin differential, epsilon, current, and continuity."""

        validated_state = self._state(state)
        if prior_state is not None:
            self._state(prior_state)
            if prior_state.field.shape != validated_state.field.shape:
                raise CassiConsciousFieldError("prior state shape mismatch")

        packed = validated_state.field.reshape(
            self.controller.config.scale_count,
            9,
            self.controller.config.mode_count,
            1,
        )
        phi = self.controller.config.phi
        differential_real = packed[:, 0] - phi * packed[:, 2]
        differential_imaginary = packed[:, 1] - phi * packed[:, 3]
        velocity_real = packed[:, 4] - phi * packed[:, 6]
        velocity_imaginary = packed[:, 5] - phi * packed[:, 7]
        differential_amplitudes = torch.sqrt(
            (differential_real.square() + differential_imaginary.square()).mean(
                dim=(1, 2)
            )
        )
        velocity_amplitude = torch.sqrt(
            (velocity_real.square() + velocity_imaginary.square()).mean()
        )
        epsilon_energy = torch.clamp(packed[:, 8], min=0.0).mean()
        diagnostics = self.controller.diagnostics(validated_state)
        cross_scale_coherence = _unit_interval(
            float(diagnostics.cross_scale_coherence.mean().item())
        )
        if prior_state is None:
            continuity = 1.0
        else:
            prior_norm = float(torch.linalg.vector_norm(prior_state.field).item())
            delta_norm = float(
                torch.linalg.vector_norm(validated_state.field - prior_state.field).item()
            )
            continuity = _unit_interval(1.0 - delta_norm / (prior_norm + 1.0))

        fast_differential = _unit_interval(float(differential_amplitudes[0].item()))
        slow_differential = _unit_interval(float(differential_amplitudes[-1].item()))
        velocity_organization = _unit_interval(float(velocity_amplitude.item()))
        epsilon_stability = _unit_interval(1.0 / (1.0 + float(epsilon_energy.item())))
        scale_current = (
            _unit_interval(0.5 + 0.5 * float(diagnostics.j_scale.mean().item()))
            if diagnostics.j_scale.numel()
            else 0.0
        )
        structural_strength = _unit_interval(
            slow_differential
            / (1.0 + slow_differential)
            * cross_scale_coherence
            / (1.0 + float(epsilon_energy.item()))
        )
        fingerprint = hashlib.sha256(
            validated_state.field.detach().contiguous().cpu().numpy().tobytes()
            + bytes.fromhex(self.controller.config_fingerprint)
        ).hexdigest()
        return SelfCondensate(
            fast_differential=fast_differential,
            slow_differential=slow_differential,
            velocity_organization=velocity_organization,
            epsilon_stability=epsilon_stability,
            cross_scale_coherence=cross_scale_coherence,
            scale_current=scale_current,
            continuity=continuity,
            structural_strength=structural_strength,
            fingerprint=fingerprint,
        )

    def interoception(
        self,
        state: QiFieldState,
        *,
        prior_state: QiFieldState | None = None,
        contradiction_energy: float = 0.0,
        agency: AgencyReadout | None = None,
    ) -> InteroceptiveValueReadout:
        """Return bounded state value used by deterministic candidate scoring."""

        if (
            isinstance(contradiction_energy, bool)
            or not isinstance(contradiction_energy, (int, float))
            or not math.isfinite(contradiction_energy)
            or contradiction_energy < 0.0
        ):
            raise CassiConsciousFieldError("invalid contradiction energy")
        validated_state = self._state(state)
        condensate = self.structural_self(validated_state, prior_state)
        readout = self.controller.emit(validated_state)
        access = self._access_from_readout(validated_state, readout)
        field_energy = float(
            validated_state.field[:, : 8 * self.controller.config.mode_count].square().mean().item()
        )
        return InteroceptiveValueReadout(
            energy_safety=_unit_interval(
                1.0 - field_energy / self.controller.config.physics.max_mean_energy
            ),
            coherence=condensate.cross_scale_coherence,
            access=float(access.granted),
            contradiction_pressure=_unit_interval(
                float(contradiction_energy) / (1.0 + float(contradiction_energy))
            ),
            slow_continuity=condensate.continuity,
            controllability_evidence=0.0 if agency is None else _unit_interval(agency.evidence),
            uncertainty=_unit_interval(float(readout.uncertainty[0].item())),
        )

    def metacognition(
        self,
        state: QiFieldState,
        *,
        event: CassiExperienceEvent | None = None,
        residual_energy: float = 0.0,
    ) -> MetacognitiveReadout:
        """Classify access, abstention, or contradiction from finite readouts."""

        if (
            isinstance(residual_energy, bool)
            or not isinstance(residual_energy, (int, float))
            or not math.isfinite(residual_energy)
            or residual_energy < 0.0
        ):
            raise CassiConsciousFieldError("residual energy invalid")
        validated_state = self._state(state)
        if event is not None:
            validate_event(event)
        readout = self.controller.emit(validated_state)
        access = self._access_from_readout(validated_state, readout)
        if residual_energy > 0.0:
            metacognitive_state = MetacognitiveState.CONTRADICTED
        elif access.granted:
            metacognitive_state = MetacognitiveState.ACCESSIBLE
        elif access.level is AccessLevel.LOCAL_ONLY and access.uncertainty > self.config.maximum_access_uncertainty:
            metacognitive_state = MetacognitiveState.UNCERTAIN
        elif access.level is AccessLevel.LOCAL_ONLY:
            metacognitive_state = MetacognitiveState.LOCAL_ONLY
        else:
            metacognitive_state = MetacognitiveState.ABSTAIN
        return MetacognitiveReadout(
            state=metacognitive_state,
            access=access,
            margin=float(readout.margin[0].item()),
            uncertainty=_unit_interval(float(readout.uncertainty[0].item())),
            source_status=None if event is None else event.reality_status,
            residual_energy=float(residual_energy),
        )

    def eligibility(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
    ) -> EligibilityReadout:
        """Compute eligibility only for an exact local action-intent event."""

        validated_state = self._state(state)
        validate_event(event)
        self._require_event_shape(
            event,
            kind=EventKind.ACTION_INTENT,
            reality_status=RealityStatus.AGENT_INTENT,
            actor=ActorClass.LOCAL_AGENT,
            message="eligibility requires a local action-intent event",
        )
        if event.boundary_wave_sha256:
            raise CassiConsciousFieldError("eligibility does not accept an explicit wave")
        diagnostics = self.controller.diagnostics(validated_state)
        condensate = self.structural_self(validated_state)
        trust = self.config.provenance.trust_for(event)
        per_scale = tuple(
            _unit_interval(
                self.controller.config.scale_ratio ** (-0.5 * scale_index)
                * trust
                * float(diagnostics.q[scale_index, 0].item())
                * float(diagnostics.chi[scale_index, 0].item())
                * (0.25 + 0.75 * condensate.cross_scale_coherence)
            )
            for scale_index in range(self.controller.config.scale_count)
        )
        salience = _unit_interval(
            float(diagnostics.rho[0, 0].item())
            / (1.0 + float(diagnostics.rho[0, 0].item()))
        )
        recurrence = _unit_interval(
            self.config.recurrence_floor
            + (1.0 - self.config.recurrence_floor) * condensate.structural_strength
        )
        return EligibilityReadout(
            per_scale=per_scale,
            salience=salience,
            reliability=trust,
            self_relevance=condensate.structural_strength,
            recurrence=recurrence,
        )

    def _selective_gain(self, state: QiFieldState, event: CassiExperienceEvent) -> float:
        """Compute bounded selective correction gain from field diagnostics."""

        diagnostics = self.controller.diagnostics(state)
        condensate = self.structural_self(state)
        salience = _unit_interval(
            float(diagnostics.rho[0, 0].item())
            / (1.0 + float(diagnostics.rho[0, 0].item()))
        )
        relevance = max(condensate.structural_strength, 0.05)
        recurrence = _unit_interval(
            self.config.recurrence_floor
            + (1.0 - self.config.recurrence_floor) * condensate.structural_strength
        )
        trust = self.config.provenance.trust_for(event)
        return min(
            self.config.maximum_correction_gain,
            0.05 * trust + 0.4 * salience * trust * relevance * recurrence,
        )

    def _commit(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
        corrective: bool,
        explicit_wave: Tensor | None = None,
        *,
        boundary_name: str = "event",
    ) -> ConsciousTransition:
        """Apply one event, optionally with an authenticated explicit wave."""

        validated_state = self._state(state)
        validate_event(event)
        if corrective != self._corrective(event):
            raise CassiConsciousFieldError("reality correction invariant")
        boundary_wave = self._resolve_boundary_wave(
            validated_state,
            event,
            explicit_wave,
            boundary_name=boundary_name,
        )
        try:
            evolved_state = self.controller.evolve(
                self.controller.sense_wave(
                    validated_state,
                    boundary_wave,
                    structured_source=self.config.provenance.trust_for(event),
                )
            )
        except QiFieldError as exc:
            raise CassiConsciousFieldError(str(exc)) from exc

        correction_energy = 0.0
        applied_gain = 0.0
        if corrective:
            applied_gain = self._selective_gain(evolved_state, event)
            try:
                evolved_state, energy = self.controller.correct_wave(
                    evolved_state,
                    boundary_wave,
                    correction_gain=applied_gain,
                )
            except QiFieldError as exc:
                raise CassiConsciousFieldError(str(exc)) from exc
            correction_energy = float(energy.mean().item())
        evolved_state = self.controller.consolidate(evolved_state)
        emission = self.controller.emit(evolved_state)
        return ConsciousTransition(
            state=evolved_state,
            event=event,
            input_wave=boundary_wave.detach().clone(),
            emission=emission,
            self_condensate=self.structural_self(evolved_state, validated_state),
            access=self._access_from_readout(evolved_state, emission),
            correction_energy=correction_energy,
            applied_correction_gain=applied_gain,
        )

    def perceive(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
        *,
        observation_wave: Tensor | None = None,
    ) -> ConsciousTransition:
        """Apply a direct observed perception or action outcome."""

        validate_event(event)
        if not self._direct(event):
            raise CassiConsciousFieldError("perceive requires direct observed perception/outcome")
        return self._commit(
            state,
            event,
            True,
            observation_wave,
            boundary_name="observation",
        )

    def receive_report(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
        *,
        report_wave: Tensor | None = None,
    ) -> ConsciousTransition:
        """Apply externally reported evidence with selective lower trust."""

        validate_event(event)
        if event.kind is not EventKind.EXTERNAL_REPORT or event.reality_status is not RealityStatus.REPORTED_EVIDENCE:
            raise CassiConsciousFieldError("reported evidence required")
        if event.actor not in {ActorClass.EXTERNAL_AGENT, ActorClass.TEACHER}:
            raise CassiConsciousFieldError("reported evidence requires an external actor")
        return self._commit(
            state,
            event,
            True,
            report_wave,
            boundary_name="report",
        )

    def commit_action_intent(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
    ) -> ConsciousTransition:
        """Commit a local action intent without corrective gain."""

        validate_event(event)
        self._require_event_shape(
            event,
            kind=EventKind.ACTION_INTENT,
            reality_status=RealityStatus.AGENT_INTENT,
            actor=ActorClass.LOCAL_AGENT,
            message="local action intent required",
        )
        return self._commit(state, event, False)

    def commit_commitment(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
    ) -> ConsciousTransition:
        """Commit a local non-corrective commitment event."""

        validate_event(event)
        self._require_event_shape(
            event,
            kind=EventKind.COMMITMENT,
            reality_status=RealityStatus.AGENT_INTENT,
            actor=ActorClass.LOCAL_AGENT,
            message="local commitment required",
        )
        return self._commit(state, event, False)

    def _branch_id(
        self,
        root_field_sha256: str,
        proposal_event: CassiExperienceEvent,
        root_event_id: str,
        proposal_wave: Tensor,
        steps: int,
        branch_state_sha256: str,
    ) -> str:
        """Derive a stable branch identity from all branch inputs."""

        material = (
            f"{root_field_sha256}:{proposal_event.event_id}:{root_event_id}:"
            f"{tensor_wave_sha256(proposal_wave)}:{steps}:{branch_state_sha256}"
        )
        return hashlib.sha256(material.encode("ascii")).hexdigest()

    def _integrity(self, root: QiFieldState, branch: CassiConsciousBranch) -> None:
        """Recompute and verify every open-branch digest and prediction field."""

        validated_root = self._state(root)
        if not isinstance(branch, CassiConsciousBranch) or not isinstance(branch.receipt, CassiPredictionReceipt):
            raise CassiConsciousFieldError("branch/receipt required")
        branch_state = self._state(branch.state)
        if branch_state.field.device != validated_root.field.device or branch_state.field.dtype != validated_root.field.dtype:
            raise CassiConsciousFieldError("branch state device/dtype mismatch")
        validate_event(branch.proposal_event)
        self.boundary.validate_wave(branch.proposal_wave, validated_root)
        self.boundary.validate_wave(branch.predicted_wave, validated_root)
        branch_root_event_id = _validate_optional_digest("root_event_id", branch.root_event_id)
        validated_steps = _require_exact_int("branch.steps", branch.steps, minimum=1)
        if (
            not isinstance(branch.status, BranchStatus)
            or branch.status is not BranchStatus.OPEN
            or _field_sha256(validated_root) != branch.root_field_sha256
            or _field_sha256(branch_state) != branch.branch_state_sha256
            or branch.receipt.root_field_sha256 != branch.root_field_sha256
            or branch.receipt.root_event_id != branch_root_event_id
            or branch.receipt.proposal_event_sha256 != branch.proposal_event.event_id
            or branch.receipt.proposal_wave_sha256 != tensor_wave_sha256(branch.proposal_wave)
            or branch.receipt.readout_sha256 != tensor_wave_sha256(branch.predicted_wave)
            or branch.receipt.imagination_steps != validated_steps
            or branch.receipt.branch_id != branch.branch_id
            or branch.branch_id
            != self._branch_id(
                branch.root_field_sha256,
                branch.proposal_event,
                branch_root_event_id,
                branch.proposal_wave,
                validated_steps,
                branch.branch_state_sha256,
            )
        ):
            raise CassiConsciousFieldError("branch integrity failure")
        if branch.proposal_event.boundary_wave_sha256 and branch.proposal_event.boundary_wave_sha256 != tensor_wave_sha256(branch.proposal_wave):
            raise CassiConsciousFieldError("proposal event boundary binding failure")

        emission = self.controller.emit(branch_state)
        expected_prediction = self.boundary._bound(emission.wave.detach().clone())
        expected_symbol = int(emission.symbols[0].item())
        expected_access = self._access_from_readout(branch_state, emission).granted
        if not torch.equal(branch.predicted_wave, expected_prediction):
            raise CassiConsciousFieldError("branch predicted wave mismatch")
        if branch.receipt.predicted_symbol != expected_symbol:
            raise CassiConsciousFieldError("branch predicted symbol mismatch")
        if branch.receipt.access_granted != expected_access:
            raise CassiConsciousFieldError("branch access receipt mismatch")

    def begin_imagination(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
        *,
        root_event_id: str = "",
        steps: int = 1,
        proposal_wave: Tensor | None = None,
    ) -> CassiConsciousBranch:
        """Open an isolated imagination branch from a single root state."""

        validated_steps = _require_exact_int("steps", steps, minimum=1)
        if validated_steps > self.config.maximum_imagination_steps:
            raise CassiConsciousFieldError("steps exceeds maximum_imagination_steps")
        validated_state = self._state(state)
        validate_event(event)
        validated_root_event_id = _validate_optional_digest("root_event_id", root_event_id)
        if event.kind not in {
            EventKind.ACTION_INTENT,
            EventKind.COMMITMENT,
            EventKind.IMAGINATION,
            EventKind.TEACHER_PROPOSAL,
        }:
            raise CassiConsciousFieldError("invalid imagination event kind")
        if proposal_wave is not None and event.reality_status not in {
            RealityStatus.HYPOTHESIS,
            RealityStatus.EXTERNAL_PROPOSAL,
        }:
            raise CassiConsciousFieldError("explicit proposal wave not legal")
        selected_wave = self._resolve_boundary_wave(
            validated_state,
            event,
            proposal_wave,
            boundary_name="proposal",
        )
        root_field_sha256 = _field_sha256(validated_state)
        try:
            branch_state = self.controller.evolve(
                self.controller.sense_wave(
                    validated_state.clone(),
                    selected_wave,
                    structured_source=self.config.provenance.trust_for(event),
                ),
                steps=validated_steps,
            )
        except QiFieldError as exc:
            raise CassiConsciousFieldError(str(exc)) from exc
        branch_state_sha256 = _field_sha256(branch_state)
        branch_id = self._branch_id(
            root_field_sha256,
            event,
            validated_root_event_id,
            selected_wave,
            validated_steps,
            branch_state_sha256,
        )
        emission = self.controller.emit(branch_state)
        predicted_wave = self.boundary._bound(emission.wave.detach().clone())
        access_granted = self._access_from_readout(branch_state, emission).granted
        receipt = CassiPredictionReceipt(
            branch_id=branch_id,
            root_field_sha256=root_field_sha256,
            root_event_id=validated_root_event_id,
            proposal_event_sha256=event.event_id,
            proposal_wave_sha256=tensor_wave_sha256(selected_wave),
            imagination_steps=validated_steps,
            predicted_symbol=int(emission.symbols[0].item()),
            readout_sha256=tensor_wave_sha256(predicted_wave),
            access_granted=access_granted,
        )
        return CassiConsciousBranch(
            branch_id=branch_id,
            root_field_sha256=root_field_sha256,
            root_event_id=validated_root_event_id,
            proposal_event=event,
            state=branch_state,
            branch_state_sha256=branch_state_sha256,
            proposal_wave=selected_wave.detach().clone(),
            predicted_wave=predicted_wave,
            receipt=receipt,
            steps=validated_steps,
        )

    def accept_teacher_proposal(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
        **kwargs: object,
    ) -> CassiConsciousBranch:
        """Open a branch only for an external teacher proposal event."""

        validate_event(event)
        if event.kind is not EventKind.TEACHER_PROPOSAL or event.reality_status is not RealityStatus.EXTERNAL_PROPOSAL:
            raise CassiConsciousFieldError("teacher proposal required")
        if event.actor not in {ActorClass.TEACHER, ActorClass.EXTERNAL_AGENT}:
            raise CassiConsciousFieldError("teacher proposal requires external actor")
        return self.begin_imagination(state, event, **kwargs)

    def reconcile_branch(
        self,
        root: QiFieldState,
        branch: CassiConsciousBranch,
        actual_event: CassiExperienceEvent,
        *,
        actual_wave: Tensor | None = None,
    ) -> ConsciousReconciliation:
        """Compare an open prediction with an observed event and close it."""

        validated_root = self._state(root)
        self._integrity(validated_root, branch)
        validate_event(actual_event)
        if not self._corrective(actual_event):
            raise CassiConsciousFieldError("invalid reconciliation evidence")
        if branch.root_event_id and actual_event.parent_event_id != branch.root_event_id:
            raise CassiConsciousFieldError("invalid reconciliation evidence")
        selected_wave = self._resolve_boundary_wave(
            validated_root,
            actual_event,
            actual_wave,
            boundary_name="observation",
        )
        actual_transition = self._commit(
            validated_root,
            actual_event,
            True,
            selected_wave,
            boundary_name="observation",
        )
        residual = selected_wave - branch.predicted_wave
        matched = bool(
            torch.allclose(
                selected_wave,
                branch.predicted_wave,
                rtol=0.0,
                atol=1.0e-6,
            )
        )
        reconciliation_state = actual_transition.state
        semantic_trace_energy = 0.0
        contradiction_event: CassiExperienceEvent | None = None
        if not matched:
            contradiction_event = create_event(
                sequence=_require_exact_int(
                    "contradiction sequence",
                    actual_event.sequence + 1,
                    minimum=0,
                ),
                kind=EventKind.CONTRADICTION,
                reality_status=RealityStatus.CONTRADICTION_FACT,
                actor=ActorClass.LOCAL_AGENT,
                payload=bytes.fromhex(tensor_wave_sha256(branch.predicted_wave))
                + bytes.fromhex(tensor_wave_sha256(selected_wave)),
                source_id="cassi-conscious-field",
                parent_event_id=actual_event.event_id,
                branch_id=branch.branch_id,
            )
            contradiction_wave = self.boundary._bound(
                residual
                + self.config.metadata_amplitude
                * self.boundary.encode(contradiction_event, reconciliation_state)
            )
            try:
                corrected_state = self.controller.evolve(
                    self.controller.sense_wave(
                        reconciliation_state,
                        contradiction_wave,
                        structured_source=self.config.provenance.trust_for(contradiction_event),
                    )
                )
                reconciliation_state, energy = self.controller.correct_wave(
                    corrected_state,
                    contradiction_wave,
                    correction_gain=self.config.contradiction_gain,
                )
            except QiFieldError as exc:
                raise CassiConsciousFieldError(str(exc)) from exc
            reconciliation_state = self.controller.consolidate(reconciliation_state)
            semantic_trace_energy = float(energy.mean().item())
        contradiction_receipt = CassiContradictionReceipt(
            branch_id=branch.branch_id,
            proposal_event_sha256=branch.proposal_event.event_id,
            actual_event_sha256=actual_event.event_id,
            proposal_wave_sha256=tensor_wave_sha256(branch.proposal_wave),
            predicted_wave_sha256=tensor_wave_sha256(branch.predicted_wave),
            actual_wave_sha256=tensor_wave_sha256(selected_wave),
            residual_sha256=tensor_wave_sha256(residual),
            matched=matched,
        )
        return ConsciousReconciliation(
            state=reconciliation_state,
            actual=actual_transition,
            contradiction=contradiction_receipt,
            contradiction_event=contradiction_event,
            branch_status=BranchStatus.CONFIRMED if matched else BranchStatus.CONTRADICTED,
            semantic_trace_energy=semantic_trace_energy,
        )

    def recall(
        self,
        state: QiFieldState,
        query: CassiExperienceEvent,
    ) -> CassiRecallResult:
        """Read a derived recall event; perception events are rejected exactly."""

        validated_state = self._state(state)
        validate_event(query)
        self._require_event_shape(
            query,
            kind=EventKind.RECALL,
            reality_status=RealityStatus.DERIVED_RECALL,
            actor=ActorClass.LOCAL_AGENT,
            message="recall requires a local derived-recall event",
        )
        query_wave = self._resolve_boundary_wave(
            validated_state,
            query,
            None,
            boundary_name="recall",
        )
        try:
            trial_state = self.controller.evolve(
                self.controller.sense_wave(
                    validated_state.clone(),
                    query_wave,
                    structured_source=self.config.provenance.trust_for(query),
                )
            )
        except QiFieldError as exc:
            raise CassiConsciousFieldError(str(exc)) from exc
        readout = self.controller.emit(trial_state)
        return CassiRecallResult(
            event=query,
            symbol=int(readout.symbols[0].item()),
            available=bool(readout.available[0].item()),
            access=self._access_from_readout(trial_state, readout),
            uncertainty=float(readout.uncertainty[0].item()),
        )

    def commit_recall(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
        recall_wave: Tensor | None = None,
    ) -> ConsciousTransition:
        """Commit one selected local derived recall through the normal field path."""

        validated_state = self._state(state)
        validate_event(event)
        self._require_event_shape(
            event,
            kind=EventKind.RECALL,
            reality_status=RealityStatus.DERIVED_RECALL,
            actor=ActorClass.LOCAL_AGENT,
            message="recall commit requires a local derived-recall event",
        )
        return self._commit(
            validated_state,
            event,
            False,
            recall_wave,
            boundary_name="recall",
        )

    def commit_deliberation(
        self,
        state: QiFieldState,
        event: CassiExperienceEvent,
    ) -> ConsciousTransition:
        """Commit one internal derived deliberation through the canonical path."""

        validate_event(event)
        self._require_event_shape(
            event,
            kind=EventKind.DELIBERATION,
            reality_status=RealityStatus.DERIVED_DELIBERATION,
            actor=ActorClass.LOCAL_AGENT,
            message="local derived deliberation required",
        )
        if not event.branch_id:
            raise CassiConsciousFieldError("deliberation requires a nonempty branch_id")
        if event.boundary_wave_sha256:
            raise CassiConsciousFieldError("deliberation does not accept an explicit wave")
        return self._commit(state, event, False, boundary_name="deliberation")

    @staticmethod
    def _candidate_score(value: InteroceptiveValueReadout) -> float:
        """Shared bounded score for inert local candidate selection."""

        return (
            value.energy_safety
            + value.coherence
            + value.access
            + value.slow_continuity
            + 1.0
            - value.uncertainty
        ) / 5.0

    def propose_commitment(
        self,
        state: QiFieldState,
        candidates: Sequence[bytes],
        *,
        sequence: int,
        parent_event_id: str = "",
        source_id: str = "cassi-conscious-field",
    ) -> CassiCommitmentProposal | None:
        """Select an inert local commitment from caller-supplied safe payloads."""

        if len(candidates) > self.config.maximum_action_candidates:
            raise CassiConsciousFieldError(
                "candidate count exceeds maximum_action_candidates"
            )
        validated_state = self._state(state)
        access = self.access_gate(validated_state)
        if not access.granted:
            return None
        if not candidates or any(not isinstance(candidate, bytes) or not candidate for candidate in candidates):
            raise CassiConsciousFieldError("nonempty byte candidates required")
        value = self.interoception(validated_state, prior_state=validated_state)
        score = self._candidate_score(value)
        proposals = [
            (
                event.event_id,
                candidate_index,
                event,
            )
            for candidate_index, payload in enumerate(candidates)
            for event in (
                create_event(
                    sequence=sequence,
                    kind=EventKind.COMMITMENT,
                    reality_status=RealityStatus.AGENT_INTENT,
                    actor=ActorClass.LOCAL_AGENT,
                    payload=payload,
                    source_id=source_id,
                    parent_event_id=parent_event_id,
                ),
            )
        ]
        _, candidate_index, event = min(proposals)
        return CassiCommitmentProposal(event, access, value, score, candidate_index)

    def propose_action(
        self,
        state: QiFieldState,
        candidates: Sequence[bytes],
        *,
        sequence: int,
        parent_event_id: str = "",
        source_id: str = "cassi-conscious-field",
    ) -> CassiActionProposal | None:
        """Score all candidates deterministically and select the best branch."""

        if len(candidates) > self.config.maximum_action_candidates:
            raise CassiConsciousFieldError(
                "candidate count exceeds maximum_action_candidates"
            )
        validated_state = self._state(state)
        access = self.access_gate(validated_state)
        if not access.granted:
            return None
        if not candidates or any(not isinstance(candidate, bytes) for candidate in candidates):
            raise CassiConsciousFieldError("byte candidates required")

        scored_candidates: list[tuple[float, str, int, CassiExperienceEvent, CassiConsciousBranch, InteroceptiveValueReadout]] = []
        for candidate_index, candidate_payload in enumerate(candidates):
            intent_event = create_event(
                sequence=sequence,
                kind=EventKind.ACTION_INTENT,
                reality_status=RealityStatus.AGENT_INTENT,
                actor=ActorClass.LOCAL_AGENT,
                payload=candidate_payload,
                source_id=source_id,
                parent_event_id=parent_event_id,
            )
            branch = self.begin_imagination(validated_state, intent_event)
            value = self.interoception(branch.state, prior_state=validated_state)
            score = self._candidate_score(value)
            scored_candidates.append(
                (-score, intent_event.event_id, candidate_index, intent_event, branch, value)
            )

        negative_score, _, candidate_index, intent_event, branch, value = min(
            scored_candidates,
            key=lambda candidate: (candidate[0], candidate[1]),
        )
        return CassiActionProposal(
            intent=intent_event,
            access=access,
            branch=branch,
            value=value,
            score=-negative_score,
            candidate_index=candidate_index,
            inert=True,
        )

    def agency_attribution(
        self,
        intent: CassiExperienceEvent,
        outcome: CassiExperienceEvent,
        branch: CassiConsciousBranch,
        root: QiFieldState,
        *,
        outcome_wave: Tensor | None = None,
    ) -> AgencyReadout:
        """Return bounded linked evidence for a local intent/outcome pair."""

        validate_event(intent)
        validate_event(outcome)
        if (
            intent.kind is not EventKind.ACTION_INTENT
            or intent.reality_status is not RealityStatus.AGENT_INTENT
            or intent.actor is not ActorClass.LOCAL_AGENT
        ):
            return AgencyReadout(False, 0.0, "missing linked local intent")
        if (
            outcome.kind is not EventKind.ACTION_OUTCOME
            or not self._direct(outcome)
            or outcome.parent_event_id != intent.event_id
        ):
            return AgencyReadout(False, 0.0, "missing linked observed outcome")
        validated_root = self._state(root)
        self._integrity(validated_root, branch)
        access = self.access_gate(validated_root)
        if branch.root_event_id != intent.event_id or not access.granted:
            return AgencyReadout(False, 0.0, "insufficient linked access")
        selected_wave = self._resolve_boundary_wave(
            validated_root,
            outcome,
            outcome_wave,
            boundary_name="outcome",
        )
        residual = float((selected_wave - branch.predicted_wave).square().mean().item())
        evidence = _unit_interval(
            1.0
            / (1.0 + residual)
            * access.cross_scale_coherence
            * (1.0 - access.uncertainty)
        )
        return AgencyReadout(
            supported=evidence > 0.0,
            evidence=evidence,
            reason="bounded causal evidence, not causal proof",
        )


__all__ = [
    "AccessLevel",
    "AgencyReadout",
    "BOUNDARY_PROFILE_ID",
    "CassiActionProposal",
    "CassiCommitmentProposal",
    "CassiConsciousBoundary",
    "CassiConsciousBranch",
    "CassiConsciousField",
    "CassiConsciousFieldError",
    "CassiRecallResult",
    "CONSCIOUS_FIELD_PROFILE_ID",
    "ConsciousAccess",
    "ConsciousFieldConfig",
    "ConsciousReconciliation",
    "ConsciousTransition",
    "EligibilityReadout",
    "INTEROCEPTIVE_LAYOUT_ID",
    "InteroceptiveValueReadout",
    "MetacognitiveReadout",
    "MetacognitiveState",
    "ProvenancePolicy",
    "SelfCondensate",
    "tensor_wave_sha256",
]
