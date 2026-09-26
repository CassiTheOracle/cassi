from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import io
import json
import math
import os
from pathlib import Path
import struct
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import torch

from cassi_qi_field import QiFieldError, QiFieldState


_MAGIC = b"CASSI-BILATERAL-COUNTERFLOW\x00\x01"
_HEADER = struct.Struct(">Q")
_DIGEST_BYTES = hashlib.sha256().digest_size
_MAX_PAYLOAD_BYTES = 16 * 1024 * 1024
_ALLOWED_DTYPES = (torch.float32, torch.float64)
_Ablation = Literal[
    "counterflow",
    "uncoupled",
    "swapped",
    "same_up",
    "same_down",
    "single_stream",
    "constant",
    "reversed",
    "fixed_phase",
]


@dataclass(frozen=True)
class BilateralCounterflowConfig:
    scale_count: int = 7
    slot_count: int = 4
    features_per_species: int = 2
    max_basins: int = 8
    plan_beam_width: int = 16
    initial_plan_beam_width: int = 2
    exact_segment_limit: int = 64
    bidirectional_lookahead_limit: int = 4096
    beam_entropy_expand_threshold: float = 0.55
    ambiguity_entropy_threshold: float = 0.90
    breath_steps: int = 16
    max_breaths: int = 4
    occupancy_floor: float = 0.5
    max_amplitude: float = 16.0
    base_beta: float = 4.0
    relaxation_rate: float = 0.65
    scale_gain: float = 0.8
    cross_gain: float = 0.35
    boundary_gain: float = 0.8
    ridge: float = 1.0e-4
    merge_residual: float = 0.08
    separate_residual: float = 0.25
    operator_norm_cap: float = 4.0
    action_residual_tolerance: float = 0.16
    constraint_tolerance: float = 0.12
    trajectory_tolerance: float = 0.04
    margin_floor: float = 1.0e-3
    score_tie_tolerance: float = 1.0e-4
    stable_plan_steps: int = 3
    ablation: _Ablation = "counterflow"

    def __post_init__(self) -> None:
        if self.scale_count != 7:
            raise QiFieldError("bilateral counterflow requires seven scales")
        if not 2 <= self.slot_count <= 8 or self.features_per_species != 2:
            raise QiFieldError(
                "bilateral counterflow requires two to eight slots and two features per species"
            )
        if self.max_basins < 2:
            raise QiFieldError("max_basins must be at least two")
        if self.breath_steps < 4 or self.breath_steps % 2:
            raise QiFieldError("breath_steps must be an even integer of at least four")
        if self.max_breaths < 1:
            raise QiFieldError("max_breaths must be positive")
        if not 1 <= self.plan_beam_width <= 256:
            raise QiFieldError("plan_beam_width must be in [1, 256]")
        if not 1 <= self.initial_plan_beam_width <= 256:
            raise QiFieldError("initial_plan_beam_width must be in [1, 256]")
        if self.exact_segment_limit < 1:
            raise QiFieldError("exact_segment_limit must be positive")
        if self.bidirectional_lookahead_limit < self.plan_beam_width:
            raise QiFieldError(
                "bidirectional_lookahead_limit must be at least plan_beam_width"
            )
        positive = {
            "occupancy_floor": self.occupancy_floor,
            "max_amplitude": self.max_amplitude,
            "base_beta": self.base_beta,
            "relaxation_rate": self.relaxation_rate,
            "scale_gain": self.scale_gain,
            "ridge": self.ridge,
            "operator_norm_cap": self.operator_norm_cap,
            "action_residual_tolerance": self.action_residual_tolerance,
            "constraint_tolerance": self.constraint_tolerance,
            "trajectory_tolerance": self.trajectory_tolerance,
            "margin_floor": self.margin_floor,
            "score_tie_tolerance": self.score_tie_tolerance,
            "beam_entropy_expand_threshold": self.beam_entropy_expand_threshold,
            "ambiguity_entropy_threshold": self.ambiguity_entropy_threshold,
        }
        for name, value in positive.items():
            if not math.isfinite(value) or value <= 0.0:
                raise QiFieldError(f"{name} must be finite and positive")
        for name, value in {"cross_gain": self.cross_gain, "boundary_gain": self.boundary_gain}.items():
            if not math.isfinite(value) or value < 0.0:
                raise QiFieldError(f"{name} must be finite and non-negative")
        if not 0.0 < self.merge_residual < self.separate_residual:
            raise QiFieldError("merge_residual must be positive and below separate_residual")
        if not 0.0 < self.relaxation_rate <= 1.0:
            raise QiFieldError("relaxation_rate must be in (0, 1]")
        if not 1 <= self.stable_plan_steps <= self.breath_steps // 2:
            raise QiFieldError("stable_plan_steps is outside the contraction window")
        if self.beam_entropy_expand_threshold > 1.0:
            raise QiFieldError("beam_entropy_expand_threshold must be at most one")
        if self.ambiguity_entropy_threshold > 1.0:
            raise QiFieldError("ambiguity_entropy_threshold must be at most one")
        if self.ablation not in {
            "counterflow",
            "uncoupled",
            "swapped",
            "same_up",
            "same_down",
            "single_stream",
            "constant",
            "reversed",
            "fixed_phase",
        }:
            raise QiFieldError(f"unsupported counterflow ablation: {self.ablation}")

    @property
    def lane_width(self) -> int:
        return self.slot_count * self.features_per_species

    @property
    def latent_dim(self) -> int:
        return 2 * self.features_per_species

    @property
    def matrix_width(self) -> int:
        return self.latent_dim * self.latent_dim


    @property
    def basin_metadata_width(self) -> int:
        return 2 + 2 * (self.slot_count - 1)

    @property
    def basin_width(self) -> int:
        return self.matrix_width + self.basin_metadata_width
    @property
    def up_modes(self) -> slice:
        return slice(0, self.lane_width)

    @property
    def down_modes(self) -> slice:
        return slice(self.lane_width, 2 * self.lane_width)

    @property
    def constraint_modes(self) -> slice:
        return slice(2 * self.lane_width, 3 * self.lane_width)

    @property
    def basin_start(self) -> int:
        return 3 * self.lane_width

    @property
    def basin_end(self) -> int:
        return self.basin_start + self.max_basins * self.basin_width

    @property
    def metadata_start(self) -> int:
        return self.basin_end

    @property
    def mode_count(self) -> int:
        needed = self.metadata_start + self.slot_count + 4
        return ((needed + 7) // 8) * 8

    @property
    def max_refinement_steps(self) -> int:
        return self.breath_steps * self.max_breaths

    def fingerprint(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class BasinReceipt:
    decision: Literal["create", "reinforce", "separate", "abstain", "capacity"]
    basin_id: int | None
    best_residual: float
    best_similarity: float
    occupied_before: int
    occupied_after: int
    support_before: int
    support_after: int
    dispersion_after: float
    field_sha256: str


@dataclass(frozen=True)
class TransitionPrediction:
    status: Literal["predicted", "ambiguous", "no_transition_data"]
    basin_id: int | None
    value: tuple[complex, ...] | None
    score: float | None
    cycle_residual: float | None
    support: int
    dispersion: float
    margin: float | None
    field_sha256: str

@dataclass(frozen=True)
class MacroReceipt:
    decision: Literal["create", "reinforce", "capacity"]
    basin_id: int | None
    constituents: tuple[int, ...]
    constituent_generations: tuple[int, ...]
    occupied_before: int
    occupied_after: int
    support_before: int
    support_after: int
    field_sha256: str



@dataclass(frozen=True)
class BreathGains:
    phase: Literal["expansion", "contraction"]
    ascending: float
    descending: float
    cross: float
    boundary: float
    beta: float
    constraint: float
    momentum: float


@dataclass(frozen=True)
class CounterflowTelemetry:
    refinement_step: int
    active_slot_count: int
    cycle_index: int
    phase_step: int
    phase: str
    ascending_gain: float
    descending_gain: float
    cross_gain: float
    boundary_gain: float
    beta: float
    constraint_gain: float
    occupied_basin_count: int
    eligible_basin_count_at_breath_start: int
    currently_above_support_floor: int
    support_threshold_crossing_count: int
    candidate_entropy: float
    normalized_candidate_entropy: float
    effective_candidate_count: float
    beam_survivor_count: int
    evaluated_plan_extensions: int
    beam_plan_entropy: float
    beam_effective_plan_count: float
    normalized_beam_plan_entropy: float
    beam_widths: tuple[int, ...]
    search_mode: Literal["exact", "adaptive", "bidirectional"]
    meeting_residual: float
    terminal_plan_margin: float
    best_plan_residual: float
    valid_plan_count: int
    winning_basins: tuple[int, ...]
    basin_margins: tuple[float, ...]
    action_residuals: tuple[float, ...]
    cycle_residuals: tuple[float, ...]
    action_valid: bool
    constraint_residual: float
    trajectory_delta: float
    energy: float
    crown_residual: float
    root_residual: float
    common_mode_energy: float
    relative_mode_energy: float
    relative_mode_ratio: float
    ascending_scale_energy: tuple[float, ...]
    descending_scale_energy: tuple[float, ...]
    ascending_directed_response: float
    descending_directed_response: float
    stable_plan_steps: int
    status: Literal["active", "settled", "ambiguous", "exhausted"]
    clamp_count: int
    max_amplitude: float
    basin_region_sha256: str
    field_sha256: str


@dataclass(frozen=True)
class CounterflowStep:
    state: QiFieldState
    telemetry: CounterflowTelemetry


@dataclass(frozen=True)
class _PlanSearch:
    forward: torch.Tensor
    backward: torch.Tensor
    survivor_count: int
    evaluated_extensions: int
    entropy: float
    normalized_entropy: float
    widths: tuple[int, ...]
    mode: Literal["exact", "adaptive", "bidirectional"]
    meeting_residual: float
    best_plan: tuple[int, ...]
    terminal_margin: float
    best_residual: float
    valid_plan_count: int
    ambiguous: bool


class BilateralCounterflowController:
    """One Qi field with Y/I × ascending/descending views and shared learned basins."""

    _STEP_OFFSET = 0
    _STATUS_OFFSET = 1
    _STABLE_OFFSET = 2
    _PLAN_OFFSET = 3
    _ACTIVE_SLOTS_AFTER_ELIGIBILITY = 1
    _IDLE = 0
    _ACTIVE = 1
    _SETTLED = 2
    _EXHAUSTED = 3
    _AMBIGUOUS = 4
    _MAX_EXACT_INTEGER = (1 << 24) - 1

    def __init__(self, config: BilateralCounterflowConfig | None = None) -> None:
        self.config = config or BilateralCounterflowConfig()


    @property
    def _eligible_mask_offset(self) -> int:
        return self._PLAN_OFFSET + self.config.slot_count - 1

    @property
    def _active_slots_offset(self) -> int:
        return self._eligible_mask_offset + self._ACTIVE_SLOTS_AFTER_ELIGIBILITY

    def initial_state(
        self,
        *,
        device: str | torch.device = "cpu",
        dtype: torch.dtype = torch.float32,
    ) -> QiFieldState:
        if dtype not in _ALLOWED_DTYPES:
            raise QiFieldError("bilateral counterflow supports float32 or float64")
        field = torch.zeros(
            (self.config.scale_count, 9 * self.config.mode_count, 1),
            device=device,
            dtype=dtype,
        )
        state = QiFieldState(field=field)
        self.validate_state(state)
        return state

    def _packed(self, state: QiFieldState) -> torch.Tensor:
        expected = (self.config.scale_count, 9 * self.config.mode_count, 1)
        if tuple(state.field.shape) != expected:
            raise QiFieldError(
                f"counterflow field shape mismatch: expected {expected}, got {tuple(state.field.shape)}"
            )
        return state.field.reshape(self.config.scale_count, 9, self.config.mode_count, 1)

    @staticmethod
    def _require_zero(name: str, value: torch.Tensor) -> None:
        if value.numel() and torch.count_nonzero(value).item() != 0:
            raise QiFieldError(f"{name} must remain exactly zero")

    @staticmethod
    def _require_integer(name: str, value: float, minimum: int, maximum: int) -> int:
        if not math.isfinite(value) or value != float(round(value)):
            raise QiFieldError(f"{name} must be a finite exact integer")
        integer = int(value)
        if integer < minimum or integer > maximum:
            raise QiFieldError(f"{name} must be in [{minimum}, {maximum}]")
        return integer

    def _metadata(
        self,
        packed: torch.Tensor,
    ) -> tuple[int, int, int, tuple[int, ...], int]:
        c = self.config
        start = c.metadata_start
        step = self._require_integer(
            "refinement_step", float(packed[0, 8, start + self._STEP_OFFSET, 0].item()), 0, c.max_refinement_steps
        )
        status = self._require_integer(
            "thought_status", float(packed[0, 8, start + self._STATUS_OFFSET, 0].item()), 0, 4
        )
        stable = self._require_integer(
            "stable_plan_steps",
            float(packed[0, 8, start + self._STABLE_OFFSET, 0].item()),
            0,
            c.breath_steps,
        )
        plan_values = packed[
            0,
            8,
            start + self._PLAN_OFFSET : start + self._PLAN_OFFSET + c.slot_count - 1,
            0,
        ].tolist()
        plan = tuple(
            self._require_integer(f"plan_id[{index}]", value, 0, c.max_basins)
            for index, value in enumerate(plan_values)
        )
        active_slots = self._require_integer(
            "active_slot_count",
            float(packed[0, 8, start + self._active_slots_offset, 0].item()),
            0,
            c.slot_count,
        )
        return step, status, stable, plan, active_slots

    def validate_state(self, state: QiFieldState) -> None:
        field = state.field
        if field.dtype not in _ALLOWED_DTYPES:
            raise QiFieldError("counterflow field dtype must be float32 or float64")
        if field.layout != torch.strided or not field.is_contiguous():
            raise QiFieldError("counterflow field must be dense, strided, and contiguous")
        packed = self._packed(state)
        if not torch.isfinite(packed).all().item():
            raise QiFieldError("counterflow field must be finite")
        dynamic_components = packed[:, :8, : self.config.basin_start, :]
        if float(dynamic_components.abs().amax().item()) > self.config.max_amplitude:
            raise QiFieldError("counterflow dynamics exceed max_amplitude")

        c = self.config
        constraint = c.constraint_modes
        basin = slice(c.basin_start, c.basin_end)
        metadata = slice(c.metadata_start, c.mode_count)
        basin_components = packed[0, :8, basin, :]
        if float(basin_components.abs().amax().item()) > c.max_amplitude**2:
            raise QiFieldError("counterflow basin moments exceed the bounded input energy")

        self._require_zero("constraint mask imaginary components", packed[0, 5:8:2, constraint, :])
        self._require_zero("constraint summaries", packed[0, 8, constraint, :])
        self._require_zero("non-root constraints", packed[1:, :, constraint, :])
        self._require_zero("non-root basin memory", packed[1:, :, basin, :])
        self._require_zero("metadata components", packed[0, :8, metadata, :])
        self._require_zero("non-root metadata", packed[1:, :, metadata, :])

        mask = torch.cat((packed[0, 4, constraint, 0], packed[0, 6, constraint, 0]))
        if ((mask < 0.0) | (mask > 1.0)).any().item():
            raise QiFieldError("constraint mask must remain in [0, 1]")

        support = self._basin_support(packed)
        if (support < 0).any().item():
            raise QiFieldError("basin support must be non-negative")
        generations: list[int] = []
        macros: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
        for basin_index, basin_support in enumerate(support.tolist()):
            modes = self._basin_slice(basin_index)
            basin_metadata = self._basin_metadata_slice(basin_index)
            self._require_zero(
                f"basin metadata components {basin_index}",
                packed[0, :8, basin_metadata, :],
            )
            generation = self._require_integer(
                f"basin_generation[{basin_index}]",
                packed[0, 8, basin_metadata.start, 0].item(),
                0,
                self._MAX_EXACT_INTEGER,
            )
            macro_length = self._require_integer(
                f"macro_length[{basin_index}]",
                packed[0, 8, basin_metadata.start + 1, 0].item(),
                0,
                c.slot_count - 1,
            )
            edge_capacity = c.slot_count - 1
            encoded_ids = tuple(
                self._require_integer(
                    f"macro_basin[{basin_index},{edge}]",
                    packed[0, 8, basin_metadata.start + 2 + edge, 0].item(),
                    0,
                    c.max_basins,
                )
                for edge in range(edge_capacity)
            )
            encoded_generations = tuple(
                self._require_integer(
                    f"macro_generation[{basin_index},{edge}]",
                    packed[
                        0,
                        8,
                        basin_metadata.start + 2 + edge_capacity + edge,
                        0,
                    ].item(),
                    0,
                    self._MAX_EXACT_INTEGER,
                )
                for edge in range(edge_capacity)
            )
            generations.append(generation)
            if basin_support < c.occupancy_floor:
                if basin_support != 0.0:
                    raise QiFieldError("unoccupied basin support must be exactly zero")
                self._require_zero(
                    f"unoccupied basin {basin_index}",
                    packed[0, :8, modes, :],
                )
                self._require_zero(
                    f"unoccupied basin moment metadata {basin_index}",
                    packed[0, 8, modes, :],
                )
                if macro_length or any(encoded_ids) or any(encoded_generations):
                    raise QiFieldError("unoccupied basin macro metadata must be zero")
                continue
            self._require_integer(
                f"basin_support[{basin_index}]",
                basin_support,
                1,
                self._MAX_EXACT_INTEGER,
            )
            dispersion = float(packed[0, 8, modes.start + 1, 0].item())
            if not math.isfinite(dispersion) or dispersion < 0.0:
                raise QiFieldError("basin dispersion must be finite and non-negative")
            if generation < 1:
                raise QiFieldError("occupied basin generation must be positive")
            if macro_length == 1:
                raise QiFieldError("a macro must contain at least two constituent basins")
            if macro_length == 0:
                if any(encoded_ids) or any(encoded_generations):
                    raise QiFieldError("primitive basin macro metadata must be zero")
            else:
                if any(value == 0 for value in encoded_ids[:macro_length]):
                    raise QiFieldError("macro constituent basin IDs must be populated")
                if any(value == 0 for value in encoded_generations[:macro_length]):
                    raise QiFieldError("macro constituent generations must be populated")
                if any(encoded_ids[macro_length:]) or any(encoded_generations[macro_length:]):
                    raise QiFieldError("inactive macro metadata must be zero")
                constituents = tuple(value - 1 for value in encoded_ids[:macro_length])
                if basin_index in constituents:
                    raise QiFieldError("a macro cannot contain itself")
                macros.append(
                    (
                        basin_index,
                        constituents,
                        encoded_generations[:macro_length],
                    )
                )

        current_mask = sum(
            1 << index
            for index, basin_support in enumerate(support.tolist())
            if basin_support >= c.occupancy_floor
        )
        for _, constituents, constituent_generations in macros:
            for constituent, generation in zip(
                constituents,
                constituent_generations,
                strict=True,
            ):
                if not current_mask & (1 << constituent):
                    raise QiFieldError("macro references an unoccupied constituent basin")
                if generations[constituent] != generation:
                    raise QiFieldError("macro references a stale constituent generation")

        step, status, stable, plan, active_slots = self._metadata(packed)
        eligible_mask = self._require_integer(
            "eligible_basin_mask",
            packed[0, 8, c.metadata_start + self._eligible_mask_offset, 0].item(),
            0,
            (1 << c.max_basins) - 1,
        )
        if any(value and support[value - 1].item() < c.occupancy_floor for value in plan):
            raise QiFieldError("thought plan references an unoccupied basin")
        if status == self._IDLE and (
            step != 0 or stable != 0 or any(plan) or eligible_mask != 0 or active_slots != 0
        ):
            raise QiFieldError("idle thought metadata must be reset")
        if status != self._IDLE and (
            eligible_mask == 0 or eligible_mask & ~current_mask
        ):
            raise QiFieldError("eligible basin set changed after the thought started")
        if status != self._IDLE and any(
            value and not eligible_mask & (1 << (value - 1))
            for value in plan
        ):
            raise QiFieldError("thought plan references an ineligible basin")
        if status != self._IDLE and not 2 <= active_slots <= c.slot_count:
            raise QiFieldError("active_slot_count is outside the configured trajectory")
        if status != self._IDLE and any(plan[active_slots - 1 :]):
            raise QiFieldError("inactive plan slots must remain exactly zero")
        if status != self._IDLE:
            inactive_offset = active_slots * c.features_per_species
            for name, modes in (
                ("ascending trajectory", c.up_modes),
                ("descending trajectory", c.down_modes),
                ("constraints", c.constraint_modes),
            ):
                inactive_modes = slice(modes.start + inactive_offset, modes.stop)
                self._require_zero(f"inactive {name} slots", packed[:, :, inactive_modes, :])
        if status == self._ACTIVE and step >= c.max_refinement_steps:
            raise QiFieldError("active thought exhausted its refinement budget")
        if status == self._EXHAUSTED and step != c.max_refinement_steps:
            raise QiFieldError("exhausted thought must end at max_refinement_steps")
        if status == self._AMBIGUOUS and step != c.max_refinement_steps:
            raise QiFieldError("ambiguous thought must end at max_refinement_steps")

        unused = slice(c.metadata_start + self._active_slots_offset + 1, c.mode_count)
        self._require_zero("unused layout cells", packed[0, 8, unused, :])

    @staticmethod
    def _tensor_sha256(tensor: torch.Tensor) -> str:
        if tensor.layout != torch.strided or not tensor.is_contiguous():
            raise QiFieldError("cannot hash a non-contiguous counterflow field")
        raw = tensor.detach().to(device="cpu").contiguous().view(torch.uint8).numpy().tobytes()
        return hashlib.sha256(raw).hexdigest()

    def _basin_region_sha256(self, packed: torch.Tensor) -> str:
        region = packed[0, :, self.config.basin_start : self.config.basin_end, :].contiguous()
        return self._tensor_sha256(region)

    @staticmethod
    def _complex(packed: torch.Tensor, real: int, imag: int, modes: slice) -> torch.Tensor:
        return torch.complex(packed[:, real, modes, 0], packed[:, imag, modes, 0])

    def _lane(self, packed: torch.Tensor, modes: slice, *, velocity: bool = False) -> torch.Tensor:
        offset = 4 if velocity else 0
        yang = self._complex(packed, offset, offset + 1, modes).reshape(
            self.config.scale_count, self.config.slot_count, self.config.features_per_species
        )
        yin = self._complex(packed, offset + 2, offset + 3, modes).reshape(
            self.config.scale_count, self.config.slot_count, self.config.features_per_species
        )
        return torch.cat((yang, yin), dim=-1)

    def _write_lane(
        self,
        packed: torch.Tensor,
        modes: slice,
        position: torch.Tensor,
        velocity: torch.Tensor,
    ) -> None:
        c = self.config
        yang, yin = position.split(c.features_per_species, dim=-1)
        vyang, vyin = velocity.split(c.features_per_species, dim=-1)
        values = (yang, yin, vyang, vyin)
        for component, value in zip((0, 2, 4, 6), values, strict=True):
            flat = value.reshape(c.scale_count, c.lane_width)
            packed[:, component, modes, 0] = flat.real
            packed[:, component + 1, modes, 0] = flat.imag
        energy = position.abs().square().reshape(
            c.scale_count, c.slot_count, 2, c.features_per_species
        ).mean(dim=2)
        packed[:, 8, modes, 0] = energy.reshape(c.scale_count, c.lane_width)

    def _constraint(self, packed: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        c = self.config
        modes = c.constraint_modes
        yang = torch.complex(packed[0, 0, modes, 0], packed[0, 1, modes, 0]).reshape(
            c.slot_count, c.features_per_species
        )
        yin = torch.complex(packed[0, 2, modes, 0], packed[0, 3, modes, 0]).reshape(
            c.slot_count, c.features_per_species
        )
        yang_mask = packed[0, 4, modes, 0].reshape(c.slot_count, c.features_per_species)
        yin_mask = packed[0, 6, modes, 0].reshape(c.slot_count, c.features_per_species)
        return torch.cat((yang, yin), dim=-1), torch.cat((yang_mask, yin_mask), dim=-1)

    def _coerce_mask(
        self,
        value: torch.Tensor | Sequence[float],
        state: QiFieldState,
        *,
        allow_empty: bool = False,
    ) -> torch.Tensor:
        tensor = torch.as_tensor(value, device=state.field.device, dtype=state.field.dtype)
        if tensor.shape != (self.config.latent_dim,):
            raise QiFieldError(f"constraint mask must have shape ({self.config.latent_dim},)")
        if not torch.isfinite(tensor).all().item():
            raise QiFieldError("constraint mask must be finite")
        if ((tensor < 0.0) | (tensor > 1.0)).any().item():
            raise QiFieldError("constraint mask must be in [0, 1]")
        if not allow_empty and torch.count_nonzero(tensor).item() == 0:
            raise QiFieldError("constraint mask must select at least one latent component")
        return tensor

    def _coerce_latent(self, value: torch.Tensor | Sequence[complex | float], state: QiFieldState) -> torch.Tensor:
        complex_dtype = torch.complex64 if state.field.dtype == torch.float32 else torch.complex128
        tensor = torch.as_tensor(value, device=state.field.device, dtype=complex_dtype)
        if tensor.shape != (self.config.latent_dim,):
            raise QiFieldError(f"latent state must have shape ({self.config.latent_dim},)")
        if not torch.isfinite(tensor.real).all().item() or not torch.isfinite(tensor.imag).all().item():
            raise QiFieldError("latent state must be finite")
        if float(tensor.abs().amax().item()) > self.config.max_amplitude:
            raise QiFieldError("latent state exceeds max_amplitude")
        return tensor

    def _coerce_examples(
        self,
        value: torch.Tensor | Sequence[Sequence[complex | float]],
        state: QiFieldState,
    ) -> torch.Tensor:
        complex_dtype = torch.complex64 if state.field.dtype == torch.float32 else torch.complex128
        tensor = torch.as_tensor(value, device=state.field.device, dtype=complex_dtype)
        if tensor.ndim != 2 or tensor.shape[1] != self.config.latent_dim:
            raise QiFieldError(f"transition examples must have shape [N, {self.config.latent_dim}]")
        if tensor.shape[0] < 1:
            raise QiFieldError("transition examples must contain at least one pair")
        if not torch.isfinite(tensor.real).all().item() or not torch.isfinite(tensor.imag).all().item():
            raise QiFieldError("transition examples must be finite")
        if float(tensor.abs().amax().item()) > self.config.max_amplitude:
            raise QiFieldError("transition examples exceed max_amplitude")
        return tensor

    def _basin_storage_slice(self, basin_id: int) -> slice:
        if not 0 <= basin_id < self.config.max_basins:
            raise QiFieldError("basin_id is outside the configured capacity")
        start = self.config.basin_start + basin_id * self.config.basin_width
        return slice(start, start + self.config.basin_width)

    def _basin_slice(self, basin_id: int) -> slice:
        storage = self._basin_storage_slice(basin_id)
        return slice(storage.start, storage.start + self.config.matrix_width)

    def _basin_metadata_slice(self, basin_id: int) -> slice:
        storage = self._basin_storage_slice(basin_id)
        return slice(storage.start + self.config.matrix_width, storage.stop)

    def _basin_support(self, packed: torch.Tensor) -> torch.Tensor:
        c = self.config
        return packed[0, 8, c.basin_start : c.basin_end : c.basin_width, 0]

    def _basin_generation(self, packed: torch.Tensor, basin_id: int) -> int:
        modes = self._basin_metadata_slice(basin_id)
        return int(round(float(packed[0, 8, modes.start, 0].item())))

    def _macro_definition(
        self,
        packed: torch.Tensor,
        basin_id: int,
    ) -> tuple[tuple[int, ...], tuple[int, ...]]:
        modes = self._basin_metadata_slice(basin_id)
        edge_capacity = self.config.slot_count - 1
        length = int(round(float(packed[0, 8, modes.start + 1, 0].item())))
        constituents = tuple(
            int(round(float(value))) - 1
            for value in packed[
                0,
                8,
                modes.start + 2 : modes.start + 2 + length,
                0,
            ].tolist()
        )
        generations = tuple(
            int(round(float(value)))
            for value in packed[
                0,
                8,
                modes.start + 2 + edge_capacity : modes.start + 2 + edge_capacity + length,
                0,
            ].tolist()
        )
        return constituents, generations

    def _write_macro_metadata(
        self,
        packed: torch.Tensor,
        basin_id: int,
        generation: int,
        constituents: Sequence[int] = (),
        constituent_generations: Sequence[int] = (),
    ) -> None:
        if len(constituents) != len(constituent_generations):
            raise QiFieldError("macro constituents and generations must have equal length")
        modes = self._basin_metadata_slice(basin_id)
        edge_capacity = self.config.slot_count - 1
        packed[0, 8, modes, 0] = 0.0
        packed[0, 8, modes.start, 0] = float(generation)
        packed[0, 8, modes.start + 1, 0] = float(len(constituents))
        if constituents:
            packed[
                0,
                8,
                modes.start + 2 : modes.start + 2 + len(constituents),
                0,
            ] = torch.tensor(
                [value + 1 for value in constituents],
                device=packed.device,
                dtype=packed.dtype,
            )
            generation_start = modes.start + 2 + edge_capacity
            packed[
                0,
                8,
                generation_start : generation_start + len(constituent_generations),
                0,
            ] = torch.tensor(
                constituent_generations,
                device=packed.device,
                dtype=packed.dtype,
            )

    def _read_moments(
        self,
        packed: torch.Tensor,
        basin_id: int,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, int, float]:
        modes = self._basin_slice(basin_id)
        c = self.config
        matrices = tuple(
            torch.complex(
                packed[0, component, modes, 0],
                packed[0, component + 1, modes, 0],
            ).reshape(c.latent_dim, c.latent_dim)
            for component in (0, 2, 4, 6)
        )
        support = int(round(float(packed[0, 8, modes.start, 0].item())))
        dispersion = float(packed[0, 8, modes.start + 1, 0].item())
        forward_cross, forward_gram, backward_cross, backward_gram = matrices
        return (
            forward_cross,
            forward_gram,
            backward_cross,
            backward_gram,
            support,
            dispersion,
        )

    def _write_moments(
        self,
        packed: torch.Tensor,
        basin_id: int,
        forward_cross: torch.Tensor,
        forward_gram: torch.Tensor,
        backward_cross: torch.Tensor,
        backward_gram: torch.Tensor,
        support: int,
        dispersion: float,
    ) -> None:
        modes = self._basin_slice(basin_id)
        for component, matrix in zip(
            (0, 2, 4, 6),
            (forward_cross, forward_gram, backward_cross, backward_gram),
            strict=True,
        ):
            packed[0, component, modes, 0] = matrix.reshape(-1).real
            packed[0, component + 1, modes, 0] = matrix.reshape(-1).imag
        packed[0, 8, modes, 0] = 0.0
        packed[0, 8, modes.start, 0] = float(support)
        packed[0, 8, modes.start + 1, 0] = float(dispersion)

    def _operator_from_moments(self, cross: torch.Tensor, gram: torch.Tensor) -> torch.Tensor:
        eye = torch.eye(self.config.latent_dim, device=cross.device, dtype=cross.dtype)
        operator = cross @ torch.linalg.inv(gram + self.config.ridge * eye)
        norm = torch.linalg.matrix_norm(operator)
        if not torch.isfinite(norm).item():
            raise QiFieldError("learned basin operator is not finite")
        if float(norm.item()) > self.config.operator_norm_cap:
            operator = operator * (self.config.operator_norm_cap / norm)
        return operator

    def _operators(
        self,
        packed: torch.Tensor,
        basin_ids: Sequence[int] | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, tuple[int, ...]]:
        support = self._basin_support(packed)
        occupied = tuple(
            index
            for index, value in enumerate(support.tolist())
            if math.isfinite(value) and value >= self.config.occupancy_floor
        )
        if basin_ids is not None:
            requested = tuple(basin_ids)
            if len(set(requested)) != len(requested) or any(
                value not in occupied for value in requested
            ):
                raise QiFieldError("eligible basins must be distinct occupied basin IDs")
            occupied = requested
        if not occupied:
            complex_dtype = torch.complex64 if packed.dtype == torch.float32 else torch.complex128
            empty = torch.empty(
                (0, self.config.latent_dim, self.config.latent_dim),
                device=packed.device,
                dtype=complex_dtype,
            )
            return empty, empty, occupied
        moments = [self._read_moments(packed, index) for index in occupied]
        operators = torch.stack(
            [self._operator_from_moments(value[0], value[1]) for value in moments]
        )
        backward_operators = torch.stack(
            [self._operator_from_moments(value[2], value[3]) for value in moments]
        )
        if self.config.ablation == "fixed_phase":
            phases = torch.arange(
                1,
                len(occupied) + 1,
                device=packed.device,
                dtype=packed.dtype,
            )
            phases = 2.0 * math.pi * phases / float(self.config.max_basins + 1)
            diagonals = torch.exp(
                1j
                * phases[:, None]
                * torch.arange(1, self.config.latent_dim + 1, device=packed.device)
            )
            operators = torch.diag_embed(diagonals.to(dtype=operators.dtype))
            backward_operators = torch.diag_embed(
                diagonals.conj().to(dtype=operators.dtype)
            )
        return operators, backward_operators, occupied

    def predict_transition(
        self,
        state: QiFieldState,
        current: torch.Tensor | Sequence[complex | float],
        *,
        eligible_basins: Sequence[int] | None = None,
    ) -> TransitionPrediction:
        """Apply the best field-resident operator without observing an outcome."""
        self.validate_state(state)
        packed = self._packed(state)
        _, status, _, _, _ = self._metadata(packed)
        if status != self._IDLE:
            raise QiFieldError("transition prediction requires an idle field")
        value = self._coerce_latent(current, state)
        operators, backward_operators, occupied = self._operators(
            packed,
            eligible_basins,
        )
        if not occupied:
            return TransitionPrediction(
                status="no_transition_data",
                basin_id=None,
                value=None,
                score=None,
                cycle_residual=None,
                support=0,
                dispersion=0.0,
                margin=None,
                field_sha256=self._tensor_sha256(state.field),
            )

        candidates: list[tuple[float, int, torch.Tensor, float, int, float]] = []
        for basin_id, operator, backward in zip(
            occupied,
            operators,
            backward_operators,
            strict=True,
        ):
            predicted = operator @ value
            reconstructed = backward @ predicted
            cycle_residual = float(
                self._relative_residual(reconstructed, value).item()
            )
            *_, support, dispersion = self._read_moments(packed, basin_id)
            score = cycle_residual + dispersion / float(max(1, support))
            candidates.append(
                (score, basin_id, predicted, cycle_residual, support, dispersion)
            )
        candidates.sort(key=lambda item: (item[0], item[1]))
        best = candidates[0]
        margin = None if len(candidates) == 1 else candidates[1][0] - best[0]
        if margin is not None and margin <= self.config.margin_floor:
            return TransitionPrediction(
                status="ambiguous",
                basin_id=None,
                value=None,
                score=best[0],
                cycle_residual=best[3],
                support=best[4],
                dispersion=best[5],
                margin=margin,
                field_sha256=self._tensor_sha256(state.field),
            )
        return TransitionPrediction(
            status="predicted",
            basin_id=best[1],
            value=tuple(complex(component) for component in best[2].tolist()),
            score=best[0],
            cycle_residual=best[3],
            support=best[4],
            dispersion=best[5],
            margin=margin,
            field_sha256=self._tensor_sha256(state.field),
        )

    @staticmethod
    def _relative_residual(predicted: torch.Tensor, expected: torch.Tensor) -> torch.Tensor:
        numerator = (predicted - expected).abs().square().mean(dim=-1).sqrt()
        denominator = expected.abs().square().mean(dim=-1).sqrt().clamp_min(torch.finfo(expected.real.dtype).eps)
        return numerator / denominator

    @staticmethod
    def _operator_similarity(first: torch.Tensor, second: torch.Tensor) -> float:
        numerator = (first.conj() * second).sum().real
        denominator = torch.linalg.matrix_norm(first) * torch.linalg.matrix_norm(second)
        if denominator.item() == 0.0:
            return 0.0
        return float((numerator / denominator).item())

    def observe_transitions(
        self,
        state: QiFieldState,
        before: torch.Tensor | Sequence[Sequence[complex | float]],
        after: torch.Tensor | Sequence[Sequence[complex | float]],
    ) -> tuple[QiFieldState, BasinReceipt]:
        self.validate_state(state)
        packed = self._packed(state)
        _, status, _, _, _ = self._metadata(packed)
        if status != self._IDLE:
            raise QiFieldError("persistent basins may change only while no thought is active")
        x = self._coerce_examples(before, state)
        y = self._coerce_examples(after, state)
        if x.shape != y.shape:
            raise QiFieldError("before and after transition batches must have the same shape")
        forward_gram = torch.einsum("ni,nj->ij", x, x.conj()) / float(x.shape[0])
        forward_cross = torch.einsum("ni,nj->ij", y, x.conj()) / float(x.shape[0])
        backward_gram = torch.einsum("ni,nj->ij", y, y.conj()) / float(y.shape[0])
        backward_cross = torch.einsum("ni,nj->ij", x, y.conj()) / float(y.shape[0])
        candidate = self._operator_from_moments(forward_cross, forward_gram)

        operators, _, occupied = self._operators(packed)
        residuals: list[float] = []
        similarities: list[float] = []
        for operator in operators:
            predicted = torch.einsum("ij,nj->ni", operator, x)
            residuals.append(float(self._relative_residual(predicted, y).mean().item()))
            similarities.append(self._operator_similarity(candidate, operator))
        best_position = min(range(len(residuals)), key=residuals.__getitem__) if residuals else None
        best_residual = residuals[best_position] if best_position is not None else math.inf
        best_similarity = similarities[best_position] if best_position is not None else 0.0
        if best_position is None:
            best_support, best_dispersion = 0, 0.0
        else:
            *_, best_support, best_dispersion = self._read_moments(
                packed,
                occupied[best_position],
            )
        decision: Literal["create", "reinforce", "separate", "abstain", "capacity"]
        basin_id: int | None

        if best_position is not None and best_residual <= self.config.merge_residual:
            decision = "reinforce"
            basin_id = occupied[best_position]
        elif best_position is not None and best_residual < self.config.separate_residual:
            return state, BasinReceipt(
                decision="abstain",
                basin_id=None,
                best_residual=best_residual,
                best_similarity=best_similarity,
                occupied_before=len(occupied),
                occupied_after=len(occupied),
                support_before=best_support,
                support_after=best_support,
                dispersion_after=best_dispersion,
                field_sha256=self._tensor_sha256(state.field),
            )
        else:
            free = next((index for index in range(self.config.max_basins) if index not in occupied), None)
            if free is None:
                return state, BasinReceipt(
                    decision="capacity",
                    basin_id=None,
                    best_residual=best_residual,
                    best_similarity=best_similarity,
                    occupied_before=len(occupied),
                    occupied_after=len(occupied),
                    support_before=best_support,
                    support_after=best_support,
                    dispersion_after=best_dispersion,
                    field_sha256=self._tensor_sha256(state.field),
                )
            decision = "create" if not occupied else "separate"
            basin_id = free

        result = QiFieldState(field=state.field.clone())
        target = self._packed(result)
        sample_count = int(x.shape[0])
        candidate_error = float(
            self._relative_residual(
                torch.einsum("ij,nj->ni", candidate, x),
                y,
            ).mean().item()
        )
        support_before = best_support if decision == "reinforce" else 0
        if decision == "reinforce":
            (
                old_forward_cross,
                old_forward_gram,
                old_backward_cross,
                old_backward_gram,
                old_support,
                old_dispersion,
            ) = self._read_moments(target, basin_id)
            support = old_support + sample_count
            forward_cross = (
                old_support * old_forward_cross + sample_count * forward_cross
            ) / float(support)
            forward_gram = (
                old_support * old_forward_gram + sample_count * forward_gram
            ) / float(support)
            backward_cross = (
                old_support * old_backward_cross + sample_count * backward_cross
            ) / float(support)
            backward_gram = (
                old_support * old_backward_gram + sample_count * backward_gram
            ) / float(support)
            dispersion = (
                old_support * old_dispersion + sample_count * candidate_error
            ) / float(support)
        else:
            support = sample_count
            dispersion = candidate_error
            generation = self._basin_generation(target, basin_id)
            self._write_macro_metadata(
                target,
                basin_id,
                generation if generation > 0 else 1,
            )
        if support > self._MAX_EXACT_INTEGER:
            raise QiFieldError("basin support exceeds exact field integer capacity")
        self._write_moments(
            target,
            basin_id,
            forward_cross,
            forward_gram,
            backward_cross,
            backward_gram,
            support,
            dispersion,
        )
        self.validate_state(result)
        return result, BasinReceipt(
            decision=decision,
            basin_id=basin_id,
            best_residual=best_residual,
            best_similarity=best_similarity,
            occupied_before=len(occupied),
            occupied_after=len(occupied) + int(decision != "reinforce"),
            support_before=support_before,
            support_after=support,
            dispersion_after=dispersion,
            field_sha256=self._tensor_sha256(result.field),
        )

    def clear_basin(self, state: QiFieldState, basin_id: int) -> QiFieldState:
        self.validate_state(state)
        packed = self._packed(state)
        _, status, _, _, _ = self._metadata(packed)
        if status != self._IDLE:
            raise QiFieldError("a basin may be cleared only while no thought is active")
        modes = self._basin_slice(basin_id)
        if packed[0, 8, modes.start, 0].item() < self.config.occupancy_floor:
            raise QiFieldError("cannot clear an unoccupied basin")

        support = self._basin_support(packed)
        occupied = tuple(
            index
            for index, value in enumerate(support.tolist())
            if value >= self.config.occupancy_floor
        )
        invalidated = {basin_id}
        changed = True
        while changed:
            changed = False
            for candidate in occupied:
                if candidate in invalidated:
                    continue
                constituents, _ = self._macro_definition(packed, candidate)
                if any(value in invalidated for value in constituents):
                    invalidated.add(candidate)
                    changed = True

        result = QiFieldState(field=state.field.clone())
        target = self._packed(result)
        for candidate in sorted(invalidated):
            generation = self._basin_generation(target, candidate)
            if generation >= self._MAX_EXACT_INTEGER:
                raise QiFieldError("basin generation exceeds exact field integer capacity")
            target[0, :, self._basin_storage_slice(candidate), :] = 0.0
            self._write_macro_metadata(target, candidate, generation + 1)
        self.validate_state(result)
        return result

    def reset_thought(self, state: QiFieldState) -> QiFieldState:
        self.validate_state(state)
        result = QiFieldState(field=state.field.clone())
        packed = self._packed(result)
        packed[:, :, : self.config.basin_start, :] = 0.0
        packed[:, :, self.config.metadata_start :, :] = 0.0
        self.validate_state(result)
        return result

    def consolidate_plan(self, state: QiFieldState) -> tuple[QiFieldState, MacroReceipt]:
        self.validate_state(state)
        packed = self._packed(state)
        _, status, _, encoded_plan, active_slots = self._metadata(packed)
        if status != self._SETTLED:
            raise QiFieldError("a macro may consolidate only from a settled thought")
        constituents = tuple(value - 1 for value in encoded_plan[: active_slots - 1])
        if len(constituents) < 2 or any(value < 0 for value in constituents):
            raise QiFieldError("a macro requires a settled multi-edge plan")

        operators, backward_operators, occupied = self._operators(packed)
        position = {basin_id: index for index, basin_id in enumerate(occupied)}
        constituent_generations = tuple(
            self._basin_generation(packed, basin_id) for basin_id in constituents
        )
        existing = next(
            (
                basin_id
                for basin_id in occupied
                if self._macro_definition(packed, basin_id)
                == (constituents, constituent_generations)
            ),
            None,
        )
        free: int | None = None
        if existing is None:
            free = next(
                (
                    basin_id
                    for basin_id in range(self.config.max_basins)
                    if basin_id not in occupied
                ),
                None,
            )
            if free is None:
                return state, MacroReceipt(
                    decision="capacity",
                    basin_id=None,
                    constituents=constituents,
                    constituent_generations=constituent_generations,
                    occupied_before=len(occupied),
                    occupied_after=len(occupied),
                    support_before=0,
                    support_after=0,
                    field_sha256=self._tensor_sha256(state.field),
                )

        result = self.reset_thought(state)
        target = self._packed(result)
        if existing is not None:
            (
                forward_cross,
                forward_gram,
                backward_cross,
                backward_gram,
                support_before,
                dispersion,
            ) = self._read_moments(target, existing)
            support = support_before + 1
            if support > self._MAX_EXACT_INTEGER:
                raise QiFieldError("basin support exceeds exact field integer capacity")
            self._write_moments(
                target,
                existing,
                forward_cross,
                forward_gram,
                backward_cross,
                backward_gram,
                support,
                dispersion,
            )
            basin_id = existing
            decision: Literal["create", "reinforce", "capacity"] = "reinforce"
        else:
            assert free is not None
            complex_dtype = (
                torch.complex64 if state.field.dtype == torch.float32 else torch.complex128
            )
            identity = torch.eye(
                self.config.latent_dim,
                device=state.field.device,
                dtype=complex_dtype,
            )
            forward = identity
            backward = identity
            for constituent in constituents:
                forward = operators[position[constituent]] @ forward
                backward = backward @ backward_operators[position[constituent]]
            regularized_identity = (1.0 + self.config.ridge) * identity
            generation = self._basin_generation(target, free)
            generation = generation if generation > 0 else 1
            self._write_moments(
                target,
                free,
                forward @ regularized_identity,
                identity,
                backward @ regularized_identity,
                identity,
                1,
                0.0,
            )
            self._write_macro_metadata(
                target,
                free,
                generation,
                constituents,
                constituent_generations,
            )
            basin_id = free
            support_before = 0
            support = 1
            decision = "create"
        self.validate_state(result)
        return result, MacroReceipt(
            decision=decision,
            basin_id=basin_id,
            constituents=constituents,
            constituent_generations=constituent_generations,
            occupied_before=len(occupied),
            occupied_after=len(occupied) + int(decision == "create"),
            support_before=support_before,
            support_after=support,
            field_sha256=self._tensor_sha256(result.field),
        )

    def consolidate_outcome(
        self,
        state: QiFieldState,
        before: torch.Tensor | Sequence[Sequence[complex | float]],
        after: torch.Tensor | Sequence[Sequence[complex | float]],
    ) -> tuple[QiFieldState, BasinReceipt]:
        self.validate_state(state)
        _, status, _, _, _ = self._metadata(self._packed(state))
        if status not in (self._SETTLED, self._EXHAUSTED, self._AMBIGUOUS):
            raise QiFieldError("an outcome may consolidate only after a thought closes")
        return self.observe_transitions(self.reset_thought(state), before, after)

    def start_thought(
        self,
        state: QiFieldState,
        start: torch.Tensor | Sequence[complex | float],
        goal: torch.Tensor | Sequence[complex | float],
        *,
        active_slots: int | None = None,
        goal_mask: torch.Tensor | Sequence[float] | None = None,
        constraints: Mapping[
            int,
            tuple[
                torch.Tensor | Sequence[complex | float],
                torch.Tensor | Sequence[float],
            ],
        ]
        | None = None,
        eligible_basins: Sequence[int] | None = None,
    ) -> QiFieldState:
        self.validate_state(state)
        packed = self._packed(state)
        _, status, _, _, _ = self._metadata(packed)
        if status != self._IDLE:
            raise QiFieldError("reset the previous thought before starting another")
        _, _, occupied = self._operators(packed)
        if not occupied:
            raise QiFieldError("cannot start a thought without learned basins")
        if eligible_basins is None:
            selected_basins = occupied
        else:
            if isinstance(eligible_basins, (str, bytes)) or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in eligible_basins
            ):
                raise QiFieldError("eligible_basins must contain basin IDs")
            selected_basins = tuple(eligible_basins)
            if not selected_basins:
                raise QiFieldError("eligible_basins must select at least one basin")
            _, _, selected_basins = self._operators(packed, selected_basins)

        c = self.config
        slots = c.slot_count if active_slots is None else active_slots
        if not isinstance(slots, int) or not 2 <= slots <= c.slot_count:
            raise QiFieldError(f"active_slots must be an integer in [2, {c.slot_count}]")
        if constraints is not None and not isinstance(constraints, Mapping):
            raise QiFieldError("constraints must map intermediate slot indices to value-mask pairs")

        start_value = self._coerce_latent(start, state)
        goal_value = self._coerce_latent(goal, state)
        goal_weight = (
            torch.ones(c.latent_dim, device=state.field.device, dtype=state.field.dtype)
            if goal_mask is None
            else self._coerce_mask(goal_mask, state)
        )
        constraint = torch.zeros(
            (c.slot_count, c.latent_dim),
            device=state.field.device,
            dtype=start_value.dtype,
        )
        constraint_mask = torch.zeros(
            (c.slot_count, c.latent_dim),
            device=state.field.device,
            dtype=state.field.dtype,
        )
        constraint[0] = start_value
        constraint_mask[0] = 1.0
        goal_slot = slots - 1
        constraint[goal_slot] = torch.where(
            goal_weight > 0.0,
            goal_value,
            torch.zeros_like(goal_value),
        )
        constraint_mask[goal_slot] = goal_weight
        for slot, pair in (() if constraints is None else constraints.items()):
            if isinstance(slot, bool) or not isinstance(slot, int) or not 1 <= slot < goal_slot:
                raise QiFieldError("constraint slots must be intermediate active-slot indices")
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise QiFieldError("each intermediate constraint must be a value-mask pair")
            value = self._coerce_latent(pair[0], state)
            weight = self._coerce_mask(pair[1], state)
            constraint[slot] = torch.where(weight > 0.0, value, torch.zeros_like(value))
            constraint_mask[slot] = weight

        result = QiFieldState(field=state.field.clone())
        target = self._packed(result)
        target[:, :, : c.basin_start, :] = 0.0
        target[:, :, c.metadata_start :, :] = 0.0
        yang, yin = constraint.split(c.features_per_species, dim=-1)
        yang_mask, yin_mask = constraint_mask.split(c.features_per_species, dim=-1)
        modes = c.constraint_modes
        target[0, 0, modes, 0] = yang.reshape(-1).real
        target[0, 1, modes, 0] = yang.reshape(-1).imag
        target[0, 2, modes, 0] = yin.reshape(-1).real
        target[0, 3, modes, 0] = yin.reshape(-1).imag
        target[0, 4, modes, 0] = yang_mask.reshape(-1)
        target[0, 6, modes, 0] = yin_mask.reshape(-1)

        up = torch.zeros(
            (c.scale_count, c.slot_count, c.latent_dim),
            device=state.field.device,
            dtype=start_value.dtype,
        )
        down = torch.zeros_like(up)
        up[0, 0] = start_value
        down[-1, goal_slot] = constraint[goal_slot]
        zero_velocity = torch.zeros_like(up)
        self._write_lane(target, c.up_modes, up, zero_velocity)
        self._write_lane(target, c.down_modes, down, zero_velocity)
        target[0, 8, c.metadata_start + self._STATUS_OFFSET, 0] = float(self._ACTIVE)
        target[
            0,
            8,
            c.metadata_start + self._eligible_mask_offset,
            0,
        ] = float(sum(1 << basin_id for basin_id in selected_basins))
        target[0, 8, c.metadata_start + self._active_slots_offset, 0] = float(slots)
        self.validate_state(result)
        return result

    def directional_matrices(
        self,
        *,
        device: str | torch.device = "cpu",
        dtype: torch.dtype = torch.float64,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        up = torch.zeros((self.config.scale_count, self.config.scale_count), device=device, dtype=dtype)
        index = torch.arange(self.config.scale_count - 1, device=device)
        up[index + 1, index] = 1.0
        return up, up.T.contiguous()

    def directional_impulse_trace(
        self,
        direction: Literal["up", "down"],
        *,
        steps: int | None = None,
        dtype: torch.dtype = torch.float64,
    ) -> torch.Tensor:
        if direction not in ("up", "down"):
            raise QiFieldError("direction must be 'up' or 'down'")
        up, down = self.directional_matrices(dtype=dtype)
        matrix = up if direction == "up" else down
        value = torch.zeros(self.config.scale_count, dtype=dtype)
        value[0 if direction == "up" else -1] = 1.0
        trace = [value.clone()]
        for _ in range(self.config.scale_count - 1 if steps is None else steps):
            value = matrix @ value
            trace.append(value.clone())
        return torch.stack(trace)


    def _gain_phase_step(self, step: int) -> int:
        phase_step = step % self.config.breath_steps
        if self.config.ablation == "reversed":
            phase_step = (phase_step + self.config.breath_steps // 2) % self.config.breath_steps
        return phase_step

    def _breath_gains(self, step: int) -> BreathGains:
        c = self.config
        phase_step = self._gain_phase_step(step)
        if c.ablation == "constant":
            return BreathGains("expansion" if phase_step < c.breath_steps // 2 else "contraction", 1.0, 1.0, c.cross_gain, c.boundary_gain, c.base_beta, 1.0, 0.25)
        if phase_step < c.breath_steps // 2:
            turn = phase_step == c.breath_steps // 2 - 1
            return BreathGains("expansion", 1.0, 0.25, c.cross_gain * (1.0 if turn else 0.5), c.boundary_gain * (1.0 if turn else 0.5), c.base_beta / 4.0, 0.25, 0.45)
        progress = (phase_step - c.breath_steps // 2) / float(c.breath_steps // 2 - 1)
        turn = phase_step == c.breath_steps // 2
        return BreathGains(
            "contraction",
            0.25,
            1.0,
            c.cross_gain * (1.0 if turn else 0.5),
            c.boundary_gain * (1.0 if turn else 0.5),
            c.base_beta * (1.0 + 3.0 * progress),
            0.25 + 3.75 * progress,
            0.45 - 0.30 * progress,
        )

    def _directions(self) -> tuple[Literal["up", "down"], Literal["up", "down"]]:
        mode = self.config.ablation
        if mode == "swapped":
            return "down", "up"
        if mode == "same_up":
            return "up", "up"
        if mode == "same_down":
            return "down", "down"
        return "up", "down"

    def _operator_completion(
        self,
        trajectory: torch.Tensor,
        operators: torch.Tensor,
        backward_operators: torch.Tensor,
        beta: float,
        active_slots: int,
    ) -> torch.Tensor:
        edge_count = active_slots - 1
        current = trajectory[:, :edge_count]
        following = trajectory[:, 1:active_slots]
        forward = torch.einsum("bij,sej->sebi", operators, current)
        backward = torch.einsum("bij,sej->sebi", backward_operators, following)
        residual = 0.5 * (
            (forward - following[:, :, None, :]).abs().square().mean(dim=-1)
            + (backward - current[:, :, None, :]).abs().square().mean(dim=-1)
        )
        weights = torch.softmax(-beta * residual, dim=-1).to(dtype=forward.dtype)
        target = torch.zeros_like(trajectory)
        target[:, 1:active_slots] += torch.einsum("seb,sebi->sei", weights, forward)
        target[:, :edge_count] += torch.einsum("seb,sebi->sei", weights, backward)
        count = torch.zeros(
            (self.config.slot_count, 1),
            device=trajectory.device,
            dtype=trajectory.real.dtype,
        )
        count[:edge_count] += 1.0
        count[1:active_slots] += 1.0
        return target / count.clamp_min(1.0)

    @staticmethod
    def _masked_residual(
        predicted: torch.Tensor,
        expected: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        weight = mask.to(dtype=predicted.real.dtype)
        count = weight.sum().clamp_min(1.0)
        difference = ((predicted - expected).abs().square() * weight).sum(dim=-1).div(count).sqrt()
        predicted_scale = (predicted.abs().square() * weight).sum(dim=-1).div(count).sqrt()
        expected_scale = (expected.abs().square() * weight).sum(dim=-1).div(count).sqrt()
        reference = (0.5 * (predicted_scale + expected_scale)).clamp_min(
            torch.finfo(predicted.real.dtype).eps
        )
        return difference / reference

    def _adaptive_beam_width(
        self,
        costs: torch.Tensor,
        beta: float,
    ) -> tuple[int, float, float]:
        count = costs.numel()
        weights = torch.softmax(-beta * (costs - costs.min()).square(), dim=0)
        entropy = -(weights * weights.clamp_min(torch.finfo(weights.dtype).eps).log()).sum()
        normalized = (
            float((entropy / math.log(count)).item())
            if count > 1
            else 0.0
        )
        ceiling = min(self.config.plan_beam_width, count)
        keep = min(self.config.initial_plan_beam_width, ceiling)
        while keep < ceiling and normalized > self.config.beam_entropy_expand_threshold:
            keep = min(2 * keep, ceiling)
        return keep, float(entropy.item()), normalized

    def _backward_anchor_states(
        self,
        target: torch.Tensor,
        backward_operators: torch.Tensor,
        steps: int,
    ) -> torch.Tensor:
        states = target.unsqueeze(0)
        basin_count = backward_operators.shape[0]
        for _ in range(steps):
            states = torch.einsum("bij,nj->nbi", backward_operators, states).reshape(
                states.shape[0] * basin_count,
                self.config.latent_dim,
            )
            if states.shape[0] > self.config.bidirectional_lookahead_limit:
                states = states[: self.config.bidirectional_lookahead_limit]
        return states

    def _global_plan_completion(
        self,
        constraint: torch.Tensor,
        constraint_mask: torch.Tensor,
        active_slots: int,
        operators: torch.Tensor,
        backward_operators: torch.Tensor,
        occupied: tuple[int, ...],
        beta: float,
    ) -> _PlanSearch:
        basin_count = operators.shape[0]
        trajectories = torch.zeros(
            (1, self.config.slot_count, self.config.latent_dim),
            device=operators.device,
            dtype=operators.dtype,
        )
        trajectories[:, 0] = constraint[0]
        states = constraint[0].unsqueeze(0)
        path_costs = torch.zeros(1, device=operators.device, dtype=operators.real.dtype)
        plans = torch.empty((1, 0), device=operators.device, dtype=torch.long)
        evaluated_extensions = 0
        widths: list[int] = []
        last_anchor = 0
        pruned = False
        used_bidirectional = False
        meeting_residuals: list[float] = []
        backward_cache: dict[tuple[int, int], torch.Tensor] = {}
        full_anchors = tuple(
            slot
            for slot in range(1, active_slots)
            if torch.count_nonzero(constraint_mask[slot]).item() == self.config.latent_dim
        )

        for edge in range(active_slots - 1):
            current_slot = edge + 1
            beam_count = states.shape[0]
            expanded_states = torch.einsum("bij,nj->nbi", operators, states).reshape(
                beam_count * basin_count,
                self.config.latent_dim,
            )
            expanded_path_costs = path_costs.repeat_interleave(basin_count)
            basin_ids = torch.arange(basin_count, device=operators.device).repeat(beam_count)
            expanded_plans = torch.cat(
                (plans.repeat_interleave(basin_count, dim=0), basin_ids[:, None]),
                dim=1,
            )
            expanded_trajectories = trajectories.repeat_interleave(basin_count, dim=0)
            expanded_trajectories[:, current_slot] = expanded_states
            constrained = torch.count_nonzero(constraint_mask[current_slot]).item() > 0
            if constrained:
                expanded_path_costs = expanded_path_costs + self._masked_residual(
                    expanded_states,
                    constraint[current_slot],
                    constraint_mask[current_slot],
                )
            evaluated_extensions += expanded_states.shape[0]

            # Meeting disagreement selects prefixes; only observed constraints calibrate terminal validity.
            selection_costs = expanded_path_costs
            future_anchor = next(
                (slot for slot in full_anchors if slot > current_slot),
                None,
            )
            if future_anchor is not None:
                remaining = future_anchor - current_slot
                key = (future_anchor, remaining)
                backward_states = backward_cache.get(key)
                if backward_states is None:
                    backward_states = self._backward_anchor_states(
                        constraint[future_anchor],
                        backward_operators,
                        remaining,
                    )
                    backward_cache[key] = backward_states
                meeting = self._masked_residual(
                    expanded_states[:, None, :],
                    backward_states[None, :, :],
                    torch.ones(
                        self.config.latent_dim,
                        device=operators.device,
                        dtype=operators.real.dtype,
                    ),
                ).min(dim=1).values
                selection_costs = expanded_path_costs + meeting
                meeting_residuals.append(float(meeting.min().item()))
                used_bidirectional = True

            segment_paths = basin_count ** (current_slot - last_anchor)
            should_prune = constrained or segment_paths > self.config.exact_segment_limit
            if should_prune and expanded_states.shape[0] > self.config.plan_beam_width:
                keep, _, _ = self._adaptive_beam_width(selection_costs, beta)
                order = torch.argsort(selection_costs, stable=True)[:keep]
                pruned = True
            else:
                order = torch.argsort(selection_costs, stable=True)
            states = expanded_states[order]
            path_costs = expanded_path_costs[order]
            plans = expanded_plans[order]
            trajectories = expanded_trajectories[order]
            widths.append(states.shape[0])
            if constrained:
                last_anchor = current_slot

        if states.shape[0] > self.config.plan_beam_width:
            keep, _, _ = self._adaptive_beam_width(path_costs, beta)
            order = torch.argsort(path_costs, stable=True)[:keep]
            states = states[order]
            path_costs = path_costs[order]
            plans = plans[order]
            trajectories = trajectories[order]
            widths[-1] = keep
            pruned = True

        backward = torch.zeros_like(trajectories)
        backward[:, active_slots - 1] = trajectories[:, active_slots - 1]
        for edge in range(active_slots - 2, -1, -1):
            selected_backward = backward_operators[plans[:, edge]]
            backward[:, edge] = torch.einsum(
                "pij,pj->pi",
                selected_backward,
                backward[:, edge + 1],
            )
        weights = torch.softmax(-beta * path_costs.square(), dim=0)
        entropy = -(weights * weights.clamp_min(torch.finfo(weights.dtype).eps).log()).sum()
        normalized_entropy = (
            float((entropy / math.log(weights.numel())).item())
            if weights.numel() > 1
            else 0.0
        )
        ordered = torch.argsort(path_costs, stable=True)
        best = int(ordered[0].item())
        terminal_margin = (
            float((path_costs[ordered[1]] - path_costs[ordered[0]]).item())
            if ordered.numel() > 1
            else math.inf
        )
        best_residual = float(path_costs[ordered[0]].item())
        constrained_slots = int(
            torch.count_nonzero(
                constraint_mask[1:active_slots].sum(dim=-1) > 0.0
            ).item()
        )
        valid_limit = self.config.constraint_tolerance * max(1, constrained_slots)
        valid_plan_count = int(
            torch.count_nonzero(path_costs <= valid_limit).item()
        )
        tied = int(
            torch.count_nonzero(
                path_costs <= path_costs[ordered[0]] + self.config.score_tie_tolerance
            ).item()
        )
        ambiguous = valid_plan_count > 1 and (
            tied > 1
            or (
                normalized_entropy >= self.config.ambiguity_entropy_threshold
                and terminal_margin < self.config.margin_floor
            )
        )
        complex_weights = weights.to(dtype=operators.dtype)
        mode: Literal["exact", "adaptive", "bidirectional"]
        if used_bidirectional:
            mode = "bidirectional"
        elif pruned:
            mode = "adaptive"
        else:
            mode = "exact"
        forward_mean = torch.einsum("p,pij->ij", complex_weights, trajectories)
        backward_mean = torch.einsum("p,pij->ij", complex_weights, backward)
        anchor_weight = constraint_mask.to(dtype=operators.dtype)
        anchored_forward = (
            (1.0 - anchor_weight) * forward_mean + anchor_weight * constraint
        )
        anchored_backward = (
            (1.0 - anchor_weight) * backward_mean + anchor_weight * constraint
        )
        return _PlanSearch(
            forward=anchored_forward,
            backward=anchored_backward,
            survivor_count=trajectories.shape[0],
            evaluated_extensions=evaluated_extensions,
            entropy=float(entropy.item()),
            normalized_entropy=normalized_entropy,
            widths=tuple(widths),
            mode=mode,
            meeting_residual=min(meeting_residuals, default=0.0),
            best_plan=tuple(occupied[int(value)] for value in plans[best].tolist()),
            terminal_margin=terminal_margin,
            best_residual=best_residual,
            valid_plan_count=valid_plan_count,
            ambiguous=ambiguous,
        )

    @staticmethod
    def _directed_alignment(value: torch.Tensor, transported: torch.Tensor) -> float:
        numerator = (value.conj() * transported).sum().real
        denominator = value.abs().square().sum().sqrt() * transported.abs().square().sum().sqrt()
        if denominator.item() == 0.0:
            return 0.0
        return float((numerator / denominator).item())

    @staticmethod
    def _mix(current: torch.Tensor, proposed: torch.Tensor, gain: float) -> torch.Tensor:
        return (current + gain * proposed) / (1.0 + gain)

    def _bounded(self, value: torch.Tensor) -> tuple[torch.Tensor, int]:
        magnitude = value.abs()
        mask = magnitude > self.config.max_amplitude
        scale = torch.where(mask, self.config.max_amplitude / magnitude.clamp_min(torch.finfo(value.real.dtype).eps), 1.0)
        return value * scale, int(mask.sum().item())

    def _plan_diagnostics(
        self,
        trajectory: torch.Tensor,
        operators: torch.Tensor,
        backward_operators: torch.Tensor,
        occupied: tuple[int, ...],
        beta: float,
        active_slots: int,
        selected_plan: tuple[int, ...] | None = None,
    ) -> tuple[
        tuple[int, ...],
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
        torch.Tensor,
    ]:
        if selected_plan is not None and (
            len(selected_plan) != active_slots - 1
            or any(value not in occupied for value in selected_plan)
        ):
            raise QiFieldError("selected global plan is outside the eligible basin set")
        position = {basin_id: index for index, basin_id in enumerate(occupied)}
        plan: list[int] = []
        margins: list[float] = []
        residuals_out: list[float] = []
        cycles: list[float] = []
        weights_all: list[torch.Tensor] = []
        for edge in range(active_slots - 1):
            candidates = torch.einsum("bij,j->bi", operators, trajectory[edge])
            residuals = self._masked_residual(
                candidates,
                trajectory[edge + 1],
                torch.ones_like(trajectory[edge + 1].real),
            )
            scores = -beta * residuals.square()
            weights = torch.softmax(scores, dim=0)
            winner = (
                int(torch.argmax(scores).item())
                if selected_plan is None
                else position[selected_plan[edge]]
            )
            plan.append(occupied[winner])
            residuals_out.append(float(residuals[winner].item()))
            cycled = backward_operators[winner] @ candidates[winner]
            cycles.append(
                float(
                    self._masked_residual(
                        cycled,
                        trajectory[edge],
                        torch.ones_like(trajectory[edge].real),
                    ).item()
                )
            )
            if len(occupied) == 1:
                margins.append(math.inf)
            else:
                competitors = torch.cat((scores[:winner], scores[winner + 1 :]))
                margins.append(float((scores[winner] - competitors.max()).item()))
            weights_all.append(weights)
        return (
            tuple(plan),
            tuple(margins),
            tuple(residuals_out),
            tuple(cycles),
            torch.stack(weights_all),
        )

    def refine_once(self, state: QiFieldState) -> CounterflowStep:
        self.validate_state(state)
        source = self._packed(state)
        step, status, stable_before, prior_plan_encoded, active_slots = self._metadata(source)
        if status != self._ACTIVE:
            raise QiFieldError("refine_once requires an active thought")
        eligible_mask = int(
            round(
                float(
                    source[
                        0,
                        8,
                        self.config.metadata_start + self._eligible_mask_offset,
                        0,
                    ].item()
                )
            )
        )
        eligible_ids = tuple(
            basin_id
            for basin_id in range(self.config.max_basins)
            if eligible_mask & (1 << basin_id)
        )
        operators, backward_operators, occupied = self._operators(source, eligible_ids)
        if not occupied:
            raise QiFieldError("active thought lost every eligible basin")
        gains = self._breath_gains(step)
        up = self._lane(source, self.config.up_modes)
        down = self._lane(source, self.config.down_modes)
        v_up = self._lane(source, self.config.up_modes, velocity=True)
        v_down = self._lane(source, self.config.down_modes, velocity=True)
        constraint, constraint_mask = self._constraint(source)
        memory_hash = self._basin_region_sha256(source)

        plan_up = self._operator_completion(
            up, operators, backward_operators, gains.beta, active_slots
        )
        plan_down = self._operator_completion(
            down, operators, backward_operators, gains.beta, active_slots
        )
        search = self._global_plan_completion(
            constraint,
            constraint_mask,
            active_slots,
            operators,
            backward_operators,
            occupied,
            gains.beta,
        )
        if gains.phase == "contraction" and self.config.ablation != "constant":
            plan_up[0] = search.forward
            plan_down[-1] = search.backward
        else:
            plan_up[0] = self._mix(plan_up[0], search.forward, gains.constraint)
            plan_down[-1] = self._mix(plan_down[-1], search.backward, gains.constraint)
        matrix_up, matrix_down = self.directional_matrices(device=state.field.device, dtype=state.field.dtype)
        matrix_up = matrix_up.to(dtype=up.dtype)
        matrix_down = matrix_down.to(dtype=down.dtype)
        up_direction, down_direction = self._directions()
        up_matrix = matrix_up if up_direction == "up" else matrix_down
        down_matrix = matrix_up if down_direction == "up" else matrix_down
        scale_up = torch.einsum("ts,sij->tij", up_matrix, up)
        scale_down = torch.einsum("ts,sij->tij", down_matrix, down)
        if up_direction == "up":
            scale_up[0] = up[0]
        else:
            scale_up[-1] = up[-1]
        if down_direction == "down":
            scale_down[-1] = down[-1]
        else:
            scale_down[0] = down[0]
        if gains.phase == "contraction" and self.config.ablation != "constant":
            phase_step = self._gain_phase_step(step)
            distance = min(
                self.config.scale_count - 1,
                2 * (phase_step - self.config.breath_steps // 2),
            )
            front_up = torch.zeros(self.config.scale_count, device=up.device, dtype=up.dtype)
            front_down = torch.zeros_like(front_up)
            front_up[0] = 1.0
            front_down[-1] = 1.0
            reached_up = front_up.abs() > 0.0
            reached_down = front_down.abs() > 0.0
            for _ in range(distance):
                front_up = up_matrix @ front_up
                front_down = down_matrix @ front_down
                reached_up |= front_up.abs() > 0.0
                reached_down |= front_down.abs() > 0.0
            plan_up[reached_up] = search.forward
            plan_down[reached_down] = search.backward

        if self.config.ablation == "single_stream":
            shared = 0.5 * (up + down)
            symmetric = 0.5 * (matrix_up + matrix_down)
            scale_shared = torch.einsum("ts,sij->tij", symmetric, shared)
            plan_shared = 0.5 * (plan_up + plan_down)
            target_up = target_down = self._mix(plan_shared, scale_shared, self.config.scale_gain)
        else:
            target_up = self._mix(plan_up, scale_up, self.config.scale_gain * gains.ascending)
            target_down = self._mix(plan_down, scale_down, self.config.scale_gain * gains.descending)

        cross_gain = 0.0 if self.config.ablation == "uncoupled" else gains.cross
        boundary_gain = 0.0 if self.config.ablation == "uncoupled" else gains.boundary
        if cross_gain:
            agreement = 0.5 * (up + down)
            target_up = self._mix(target_up, agreement, cross_gain)
            target_down = self._mix(target_down, agreement, cross_gain)
        if boundary_gain:
            crown = 0.5 * (up[-1] + down[-1])
            root = 0.5 * (up[0] + down[0])
            target_up[-1] = self._mix(target_up[-1], crown, boundary_gain)
            target_down[-1] = self._mix(target_down[-1], crown, boundary_gain)
            target_up[0] = self._mix(target_up[0], root, boundary_gain)
            target_down[0] = self._mix(target_down[0], root, boundary_gain)

        constrained = constraint_mask.bool()
        target_up[0] = torch.where(
            constrained,
            self._mix(target_up[0], constraint, gains.constraint),
            target_up[0],
        )
        target_down[-1] = torch.where(
            constrained,
            self._mix(target_down[-1], constraint, gains.constraint),
            target_down[-1],
        )

        new_v_up = gains.momentum * v_up + self.config.relaxation_rate * (target_up - up)
        new_v_down = gains.momentum * v_down + self.config.relaxation_rate * (target_down - down)
        new_up, clamps_up = self._bounded(up + new_v_up)
        new_down, clamps_down = self._bounded(down + new_v_down)
        new_v_up, clamps_vu = self._bounded(new_v_up)
        new_v_down, clamps_vd = self._bounded(new_v_down)
        clamp_count = clamps_up + clamps_down + clamps_vu + clamps_vd

        result = QiFieldState(field=state.field.clone())
        target = self._packed(result)
        self._write_lane(target, self.config.up_modes, new_up, new_v_up)
        self._write_lane(target, self.config.down_modes, new_down, new_v_down)
        if self._basin_region_sha256(target) != memory_hash:
            raise QiFieldError("provisional refinement mutated persistent basin memory")
        plan, margins, action_residuals, cycle_residuals, weights = self._plan_diagnostics(
            new_down[0], operators, backward_operators, occupied, gains.beta, active_slots, search.best_plan
        )
        action_valid = all(value <= self.config.action_residual_tolerance for value in action_residuals) and all(
            value >= self.config.margin_floor for value in margins
        )
        prior_plan = tuple(value - 1 for value in prior_plan_encoded[: active_slots - 1])
        stable = stable_before + 1 if action_valid and prior_plan == plan else (1 if action_valid else 0)
        step_after = step + 1

        active = slice(0, active_slots)
        constraint_residual = float(
            self._masked_residual(
                new_down[0, active].reshape(1, -1),
                constraint[active].reshape(-1),
                constraint_mask[active].reshape(-1),
            )[0].item()
        )
        change = (new_down[0, active] - down[0, active]).abs().square().mean().sqrt()
        old_scale = down[0, active].abs().square().mean().sqrt()
        new_scale = new_down[0, active].abs().square().mean().sqrt()
        reference = torch.maximum(old_scale, new_scale).clamp_min(torch.finfo(state.field.dtype).eps)
        delta = float((change / reference).item())
        phase_is_contraction = gains.phase == "contraction"
        empty_turn = step_after % self.config.breath_steps == 0
        settled = (
            phase_is_contraction
            and empty_turn
            and action_valid
            and stable >= self.config.stable_plan_steps
            and constraint_residual <= self.config.constraint_tolerance
            and delta <= self.config.trajectory_tolerance
            and not search.ambiguous
        )
        if settled:
            next_status = self._SETTLED
        elif step_after >= self.config.max_refinement_steps:
            next_status = self._AMBIGUOUS if search.ambiguous else self._EXHAUSTED
            step_after = self.config.max_refinement_steps
        else:
            next_status = self._ACTIVE

        meta = self.config.metadata_start
        target[0, 8, meta + self._STEP_OFFSET, 0] = float(step_after)
        target[0, 8, meta + self._STATUS_OFFSET, 0] = float(next_status)
        target[0, 8, meta + self._STABLE_OFFSET, 0] = float(min(stable, self.config.breath_steps))
        target[0, 8, meta + self._PLAN_OFFSET : meta + self._PLAN_OFFSET + len(plan), 0] = torch.tensor(
            [value + 1 for value in plan], device=state.field.device, dtype=state.field.dtype
        )

        entropy_per_edge = -(weights * weights.clamp_min(torch.finfo(weights.dtype).eps).log()).sum(dim=1)
        candidate_entropy = float(entropy_per_edge.mean().item())
        normalized_entropy = candidate_entropy / math.log(len(occupied)) if len(occupied) > 1 else 0.0
        transition_energy = sum(value * value for value in action_residuals) / len(action_residuals)
        crown_residual = float(
            (new_up[-1, active] - new_down[-1, active]).abs().square().mean().sqrt().item()
        )
        root_residual = float(
            (new_up[0, active] - new_down[0, active]).abs().square().mean().sqrt().item()
        )
        common = (new_up[:, active] + new_down[:, active]) / math.sqrt(2.0)
        relative = (new_up[:, active] - new_down[:, active]) / math.sqrt(2.0)
        common_energy = float(common.abs().square().mean().item())
        relative_energy = float(relative.abs().square().mean().item())
        relative_ratio = relative_energy / max(
            common_energy,
            torch.finfo(state.field.dtype).eps,
        )
        energy = constraint_residual**2 + transition_energy + crown_residual**2 + root_residual**2
        ascending_energy = tuple(
            float(value) for value in new_up[:, active].abs().square().mean(dim=(1, 2)).tolist()
        )
        descending_energy = tuple(
            float(value) for value in new_down[:, active].abs().square().mean(dim=(1, 2)).tolist()
        )
        ascending_response = self._directed_alignment(new_up[:, active], scale_up[:, active])
        descending_response = self._directed_alignment(new_down[:, active], scale_down[:, active])
        current_support = self._basin_support(target)
        currently_occupied = int((current_support >= self.config.occupancy_floor).sum().item())
        previous_support = self._basin_support(source)
        support_crossings = int(
            (
                (current_support >= self.config.occupancy_floor)
                != (previous_support >= self.config.occupancy_floor)
            ).sum().item()
        )
        max_amplitude = max(
            float(new_up.abs().amax().item()),
            float(new_down.abs().amax().item()),
            float(new_v_up.abs().amax().item()),
            float(new_v_down.abs().amax().item()),
        )
        self.validate_state(result)
        telemetry = CounterflowTelemetry(
            active_slot_count=active_slots,
            refinement_step=step_after,
            cycle_index=(step_after - 1) // self.config.breath_steps,
            phase_step=(step_after - 1) % self.config.breath_steps,
            phase=gains.phase,
            ascending_gain=gains.ascending,
            descending_gain=gains.descending,
            cross_gain=cross_gain,
            boundary_gain=boundary_gain,
            beta=gains.beta,
            constraint_gain=gains.constraint,
            occupied_basin_count=currently_occupied,
            eligible_basin_count_at_breath_start=len(occupied),
            currently_above_support_floor=currently_occupied,
            support_threshold_crossing_count=support_crossings,
            candidate_entropy=candidate_entropy,
            normalized_candidate_entropy=normalized_entropy,
            effective_candidate_count=math.exp(candidate_entropy),
            beam_survivor_count=search.survivor_count,
            evaluated_plan_extensions=search.evaluated_extensions,
            beam_plan_entropy=search.entropy,
            beam_effective_plan_count=math.exp(search.entropy),
            normalized_beam_plan_entropy=search.normalized_entropy,
            beam_widths=search.widths,
            search_mode=search.mode,
            meeting_residual=search.meeting_residual,
            terminal_plan_margin=search.terminal_margin,
            best_plan_residual=search.best_residual,
            valid_plan_count=search.valid_plan_count,
            winning_basins=plan,
            basin_margins=margins,
            action_residuals=action_residuals,
            cycle_residuals=cycle_residuals,
            action_valid=action_valid,
            constraint_residual=constraint_residual,
            trajectory_delta=delta,
            energy=energy,
            crown_residual=crown_residual,
            root_residual=root_residual,
            common_mode_energy=common_energy,
            relative_mode_energy=relative_energy,
            relative_mode_ratio=relative_ratio,
            ascending_scale_energy=ascending_energy,
            descending_scale_energy=descending_energy,
            ascending_directed_response=ascending_response,
            descending_directed_response=descending_response,
            stable_plan_steps=stable,
            status=(
                "settled"
                if next_status == self._SETTLED
                else "ambiguous"
                if next_status == self._AMBIGUOUS
                else "exhausted"
                if next_status == self._EXHAUSTED
                else "active"
            ),
            clamp_count=clamp_count,
            max_amplitude=max_amplitude,
            basin_region_sha256=memory_hash,
            field_sha256=self._tensor_sha256(result.field),
        )
        return CounterflowStep(result, telemetry)

    def run_until_closed(self, state: QiFieldState) -> tuple[QiFieldState, tuple[CounterflowTelemetry, ...]]:
        telemetry: list[CounterflowTelemetry] = []
        current = state
        while self._metadata(self._packed(current))[1] == self._ACTIVE:
            step = self.refine_once(current)
            current = step.state
            telemetry.append(step.telemetry)
        return current, tuple(telemetry)

    def dump_state_bytes(self, state: QiFieldState) -> bytes:
        self.validate_state(state)
        field = state.field.detach().to(device="cpu").contiguous()
        payload = {
            "schema": 1,
            "config": asdict(self.config),
            "config_sha256": self.config.fingerprint(),
            "field": field,
            "field_sha256": self._tensor_sha256(field),
        }
        buffer = io.BytesIO()
        torch.save(payload, buffer)
        encoded = buffer.getvalue()
        if len(encoded) > _MAX_PAYLOAD_BYTES:
            raise QiFieldError("counterflow checkpoint exceeds the payload limit")
        return _MAGIC + _HEADER.pack(len(encoded)) + hashlib.sha256(encoded).digest() + encoded

    def load_state_bytes(
        self,
        data: bytes | bytearray | memoryview,
        *,
        device: str | torch.device = "cpu",
    ) -> QiFieldState:
        raw = bytes(data)
        header_size = len(_MAGIC) + _HEADER.size + _DIGEST_BYTES
        if len(raw) < header_size or not raw.startswith(_MAGIC):
            raise QiFieldError("invalid bilateral counterflow checkpoint frame")
        offset = len(_MAGIC)
        (payload_size,) = _HEADER.unpack(raw[offset : offset + _HEADER.size])
        if payload_size > _MAX_PAYLOAD_BYTES or len(raw) != header_size + payload_size:
            raise QiFieldError("invalid bilateral counterflow checkpoint length")
        digest_start = offset + _HEADER.size
        digest = raw[digest_start : digest_start + _DIGEST_BYTES]
        payload_bytes = raw[header_size:]
        if not hmac.compare_digest(digest, hashlib.sha256(payload_bytes).digest()):
            raise QiFieldError("bilateral counterflow checkpoint digest mismatch")
        try:
            payload: Any = torch.load(io.BytesIO(payload_bytes), map_location="cpu", weights_only=True)
        except Exception as exc:
            raise QiFieldError("could not decode bilateral counterflow checkpoint") from exc
        if not isinstance(payload, dict) or set(payload) != {
            "schema",
            "config",
            "config_sha256",
            "field",
            "field_sha256",
        }:
            raise QiFieldError("invalid bilateral counterflow checkpoint payload")
        if payload["schema"] != 1 or payload["config"] != asdict(self.config):
            raise QiFieldError("incompatible bilateral counterflow checkpoint configuration")
        if payload["config_sha256"] != self.config.fingerprint():
            raise QiFieldError("counterflow configuration fingerprint mismatch")
        field = payload["field"]
        if not isinstance(field, torch.Tensor) or field.dtype not in _ALLOWED_DTYPES:
            raise QiFieldError("counterflow checkpoint field is invalid")
        if field.layout != torch.strided or not field.is_contiguous():
            raise QiFieldError("counterflow checkpoint field must be dense and contiguous")
        if payload["field_sha256"] != self._tensor_sha256(field):
            raise QiFieldError("counterflow checkpoint field checksum mismatch")
        state = QiFieldState(field=field.to(device=device).contiguous())
        self.validate_state(state)
        return state

    def save_state(self, path: str | Path, state: QiFieldState) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = self.dump_state_bytes(state)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=f".{destination.name}.", delete=False) as handle:
                temporary = handle.name
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)

    def load_state(
        self,
        path: str | Path,
        *,
        device: str | torch.device = "cpu",
    ) -> QiFieldState:
        return self.load_state_bytes(Path(path).read_bytes(), device=device)
