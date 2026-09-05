"""Executable reference for a headless, single-field Cassi intelligence.

The only adaptive persistent value in this architecture is one native-layout
Yang/Yin field tensor with shape ``[8 * M, B]``.  Perception is a fixed boundary
wave, prediction is a phase-conjugate resonance measurement, and learning is a
bounded correction written into slow modes of the same field.  There are no
learned parameters, embeddings, neural-network layers, optimizer state, or
auxiliary recurrent memories.

This module is intentionally isolated from the current production world model.
It defines the field-only contract that a later native GGML/Vulkan operator can
implement without changing the verified v2 provider path.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor

from cassi_modal_torch import native_mode_params


FIELD_CONFIG_SCHEMA = "cassi.field-intelligence.config.v1"
FIELD_STATE_SCHEMA = "cassi.field-intelligence.state.v1"
FIELD_LAYOUT_ID = "cassi.field-intelligence.native-linear-x-fast.v1"
FIELD_OPERATOR_PROFILE_ID = "cassi.field-intelligence.phase-conjugate.v1"
BOUNDARY_PROFILE_ID = "cassi.boundary.quadratic-chirp.v1"
TEXT_BYTE_COUNT = 256


class CassiFieldIntelligenceError(ValueError):
    """Invalid field configuration, state, boundary event, or artifact."""


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CassiFieldIntelligenceError(f"{name} must be a positive integer")
    return value


def _finite(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CassiFieldIntelligenceError(f"{name} must be a finite real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise CassiFieldIntelligenceError(f"{name} must be finite")
    return converted


def _unit_interval(name: str, value: Any) -> float:
    converted = _finite(name, value)
    if converted < 0.0 or converted > 1.0:
        raise CassiFieldIntelligenceError(f"{name} must be in [0, 1]")
    return converted


def _positive_finite(name: str, value: Any) -> float:
    converted = _finite(name, value)
    if converted <= 0.0:
        raise CassiFieldIntelligenceError(f"{name} must be positive")
    return converted


@dataclass(frozen=True)
class CassiFieldIntelligenceConfig:
    """Fixed physical and boundary controls for one field intelligence."""

    mode_count: int = 512
    alphabet_size: int = 260
    grid_n: int = 32
    phi: float = 1.618033988749895
    dt: float = 0.005
    fast_omega2: float = 20.0
    slow_omega2: float = 0.05
    fast_damping: float = 0.5
    slow_damping: float = 0.01
    nonlinear_gain: float = 0.002
    settle_steps: int = 1
    sense_retention: float = 0.0
    sense_velocity_retention: float = 0.0
    fast_retention: float = 0.05
    slow_retention: float = 0.9995
    plasticity_gain: float = 0.2
    plasticity_momentum: float = 0.0
    consolidation_steps: int = 1
    flux_velocity_scale: float = 0.05
    max_mode_amplitude: float = 8.0
    max_mean_energy: float = 32.0
    emission_floor: float = 1.0e-6
    correction_epsilon: float = 1.0e-6

    def __post_init__(self) -> None:
        mode_count = _positive_int("mode_count", self.mode_count)
        alphabet_size = _positive_int("alphabet_size", self.alphabet_size)
        grid_n = _positive_int("grid_n", self.grid_n)
        settle_steps = _positive_int("settle_steps", self.settle_steps)
        consolidation_steps = _positive_int("consolidation_steps", self.consolidation_steps)
        if mode_count < 4 or mode_count % 2:
            raise CassiFieldIntelligenceError("mode_count must be even and at least four")
        if mode_count > grid_n ** 3:
            raise CassiFieldIntelligenceError("mode_count cannot exceed grid_n ** 3")
        if alphabet_size > 65_536:
            raise CassiFieldIntelligenceError("alphabet_size is unreasonably large")
        object.__setattr__(self, "mode_count", mode_count)
        object.__setattr__(self, "alphabet_size", alphabet_size)
        object.__setattr__(self, "grid_n", grid_n)
        object.__setattr__(self, "settle_steps", settle_steps)
        object.__setattr__(self, "consolidation_steps", consolidation_steps)

        for name in (
            "phi",
            "dt",
            "fast_omega2",
            "slow_omega2",
            "fast_damping",
            "slow_damping",
            "max_mode_amplitude",
            "max_mean_energy",
            "emission_floor",
            "correction_epsilon",
        ):
            object.__setattr__(self, name, _positive_finite(name, getattr(self, name)))
        for name in (
            "sense_retention",
            "sense_velocity_retention",
            "fast_retention",
            "slow_retention",
            "plasticity_momentum",
        ):
            object.__setattr__(self, name, _unit_interval(name, getattr(self, name)))
        for name in ("nonlinear_gain", "plasticity_gain", "flux_velocity_scale"):
            value = _finite(name, getattr(self, name))
            if value < 0.0:
                raise CassiFieldIntelligenceError(f"{name} must be non-negative")
            object.__setattr__(self, name, value)
        if self.dt * math.sqrt(max(self.fast_omega2, self.slow_omega2)) >= 1.4:
            raise CassiFieldIntelligenceError("dt and omega2 violate the conservative stability bound")

    @property
    def slow_mode_count(self) -> int:
        return self.mode_count // 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CassiFieldIntelligenceConfig":
        if not isinstance(value, Mapping):
            raise CassiFieldIntelligenceError("field configuration must be a mapping")
        expected = set(cls.__dataclass_fields__)
        payload = dict(value)
        unknown = set(payload) - expected
        if unknown:
            raise CassiFieldIntelligenceError(f"field configuration has unknown fields: {sorted(unknown)!r}")
        try:
            return cls(**payload)
        except CassiFieldIntelligenceError:
            raise
        except (TypeError, ValueError) as exc:
            raise CassiFieldIntelligenceError(f"invalid field configuration: {exc}") from exc

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CassiFieldState:
    """The sole adaptive persistent object: one native-layout field tensor."""

    field: Tensor

    @property
    def batch_size(self) -> int:
        if self.field.ndim != 2:
            raise CassiFieldIntelligenceError("field state must be a matrix")
        return int(self.field.shape[1])

    def validate(
        self,
        config: CassiFieldIntelligenceConfig,
        *,
        device: torch.device | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        if not torch.is_tensor(self.field):
            raise CassiFieldIntelligenceError("field must be a torch.Tensor")
        if self.field.ndim != 2 or self.field.shape[0] != 8 * config.mode_count or self.field.shape[1] < 1:
            raise CassiFieldIntelligenceError(
                f"field must have shape [8 * {config.mode_count}, B] with B >= 1"
            )
        if not self.field.dtype.is_floating_point:
            raise CassiFieldIntelligenceError("field must have a floating dtype")
        if device is not None and self.field.device != device:
            raise CassiFieldIntelligenceError("field device does not match the requested device")
        if dtype is not None and self.field.dtype != dtype:
            raise CassiFieldIntelligenceError("field dtype does not match the requested dtype")
        if not bool(torch.isfinite(self.field).all().item()):
            raise CassiFieldIntelligenceError("field contains non-finite values")

    def clone(self) -> "CassiFieldState":
        return CassiFieldState(self.field.clone())

    def detach(self) -> "CassiFieldState":
        return CassiFieldState(self.field.detach())

    def to(
        self,
        device: torch.device | str,
        *,
        dtype: torch.dtype | None = None,
    ) -> "CassiFieldState":
        return CassiFieldState(self.field.to(device=device, dtype=dtype or self.field.dtype))


@dataclass(frozen=True)
class CassiFieldEmission:
    """Ephemeral boundary measurement; it is never part of persistent state."""

    symbols: Tensor
    available: Tensor
    scores: Tensor
    flux: Tensor
    margin: Tensor
    uncertainty: Tensor
    wave: Tensor


@dataclass(frozen=True)
class CassiFieldCycle:
    """One sense/predict/correct/consolidate event result."""

    state: CassiFieldState
    emission: CassiFieldEmission
    correction_energy: Tensor


@dataclass(frozen=True)
class CassiFieldImagination:
    """Autonomous emitted events and the final single field state."""

    state: CassiFieldState
    emissions: tuple[CassiFieldEmission, ...]


class CassiBoundaryAlphabet:
    """Fixed procedural event waves; no learned embedding table exists."""

    def __init__(self, alphabet_size: int, wave_modes: int) -> None:
        self.alphabet_size = _positive_int("alphabet_size", alphabet_size)
        self.wave_modes = _positive_int("wave_modes", wave_modes)
        descriptor = (
            f"{BOUNDARY_PROFILE_ID}:{self.alphabet_size}:"
            f"{self.wave_modes}:prime=4093:"
            "phase=((symbol+1)*(position+1)^2+(symbol+1)^2*(position+1)) mod prime"
        ).encode("utf-8")
        self._fingerprint = hashlib.sha256(descriptor).hexdigest()

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    def codes(self, *, device: torch.device, dtype: torch.dtype) -> Tensor:
        if not dtype.is_floating_point:
            raise CassiFieldIntelligenceError("boundary codes require a floating dtype")
        symbol = torch.arange(
            self.alphabet_size, device=device, dtype=torch.int64
        ).reshape(self.alphabet_size, 1) + 1
        position = torch.arange(
            self.wave_modes, device=device, dtype=torch.int64
        ).reshape(1, self.wave_modes) + 1
        prime = 4093
        phase_index = torch.remainder(
            symbol * position.square() + symbol.square() * position,
            prime,
        )
        phase = (
            2.0
            * math.pi
            * phase_index.to(dtype=dtype)
            / float(prime)
        )
        return torch.stack((torch.cos(phase), torch.sin(phase)), dim=-1)

    def validate_symbols(self, symbols: Tensor, *, batch_size: int, device: torch.device) -> Tensor:
        if not torch.is_tensor(symbols):
            raise CassiFieldIntelligenceError("symbols must be a torch.Tensor")
        if symbols.shape != (batch_size,):
            raise CassiFieldIntelligenceError("symbols must have shape [B]")
        if symbols.dtype not in (torch.int32, torch.int64):
            raise CassiFieldIntelligenceError("symbols must use int32 or int64")
        if symbols.device != device:
            raise CassiFieldIntelligenceError("symbols and field must share a device")
        if bool(torch.any(symbols < 0).item()) or bool(torch.any(symbols >= self.alphabet_size).item()):
            raise CassiFieldIntelligenceError("symbols contain an event outside the boundary alphabet")
        return symbols.to(dtype=torch.int64)

    def encode(
        self,
        symbols: Tensor,
        *,
        batch_size: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Tensor:
        ids = self.validate_symbols(symbols, batch_size=batch_size, device=device)
        return self.codes(device=device, dtype=dtype).index_select(0, ids)

    def resonance_scores(self, waves: Tensor) -> Tensor:
        if not torch.is_tensor(waves) or waves.ndim != 3:
            raise CassiFieldIntelligenceError("boundary waves must have shape [B, W, 2]")
        if waves.shape[1:] != (self.wave_modes, 2) or waves.shape[0] < 1:
            raise CassiFieldIntelligenceError("boundary wave shape does not match the alphabet")
        if not waves.dtype.is_floating_point or not bool(torch.isfinite(waves).all().item()):
            raise CassiFieldIntelligenceError("boundary waves must be finite floating tensors")
        codes = self.codes(device=waves.device, dtype=waves.dtype)
        # Re(conj(code) * wave), averaged over the fixed probe surface.
        return torch.einsum("bwc,awc->ba", waves, codes) / float(self.wave_modes)

    @staticmethod
    def bytes_to_symbols(data: bytes, *, device: torch.device | str = "cpu") -> Tensor:
        if not isinstance(data, bytes):
            raise CassiFieldIntelligenceError("text boundary input must be bytes")
        return torch.tensor(list(data), dtype=torch.int64, device=device)

    @staticmethod
    def symbols_to_bytes(symbols: Sequence[int]) -> bytes:
        values = [int(value) for value in symbols]
        if any(value < 0 or value >= TEXT_BYTE_COUNT for value in values):
            raise CassiFieldIntelligenceError("only byte symbols 0..255 can be decoded as text")
        return bytes(values)


class CassiFieldIntelligence:
    """Parameter-free controller for one adaptive Yang/Yin field."""

    def __init__(self, config: CassiFieldIntelligenceConfig = CassiFieldIntelligenceConfig()) -> None:
        if not isinstance(config, CassiFieldIntelligenceConfig):
            raise CassiFieldIntelligenceError("config must be a CassiFieldIntelligenceConfig")
        self.config = config
        self.alphabet = CassiBoundaryAlphabet(config.alphabet_size, config.slow_mode_count)
        symbols = native_mode_params(
            config.mode_count,
            grid_n=config.grid_n,
            dtype=torch.float64,
            device="cpu",
        ).tolist()
        ordered = sorted(range(config.mode_count), key=lambda index: (abs(float(symbols[index])), index))
        self.slow_indices = tuple(ordered[: config.slow_mode_count])
        slow_set = set(self.slow_indices)
        self.fast_indices = tuple(index for index in range(config.mode_count) if index not in slow_set)
        self.mode_symbols = tuple(float(value) for value in symbols)
        if len(self.fast_indices) != config.slow_mode_count:
            raise CassiFieldIntelligenceError("fast and slow mode partitions must have equal size")

    @property
    def config_fingerprint(self) -> str:
        return self.config.fingerprint

    @property
    def boundary_fingerprint(self) -> str:
        return self.alphabet.fingerprint

    def initial_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str = "cpu",
        dtype: torch.dtype = torch.float32,
    ) -> CassiFieldState:
        batch_size = _positive_int("batch_size", batch_size)
        if not dtype.is_floating_point:
            raise CassiFieldIntelligenceError("field state requires a floating dtype")
        state = CassiFieldState(
            torch.zeros(
                8 * self.config.mode_count,
                batch_size,
                device=torch.device(device),
                dtype=dtype,
            )
        )
        state.validate(self.config)
        return state

    def _validate_state(self, state: CassiFieldState) -> None:
        if not isinstance(state, CassiFieldState):
            raise CassiFieldIntelligenceError("state must be a CassiFieldState")
        state.validate(self.config)

    def _unpack(self, state: CassiFieldState) -> tuple[Tensor, ...]:
        self._validate_state(state)
        unpacked = state.field.transpose(0, 1).reshape(state.batch_size, self.config.mode_count, 8)
        return tuple(unpacked.unbind(dim=-1))

    @staticmethod
    def _pack(components: Sequence[Tensor]) -> CassiFieldState:
        if len(components) != 8:
            raise CassiFieldIntelligenceError("a native field requires eight components")
        batch_size, mode_count = components[0].shape
        if any(component.shape != (batch_size, mode_count) for component in components):
            raise CassiFieldIntelligenceError("native field components must share [B, M]")
        packed = torch.stack(tuple(components), dim=-1).reshape(batch_size, 8 * mode_count).transpose(0, 1).contiguous()
        return CassiFieldState(packed)

    def _index(self, values: tuple[int, ...], device: torch.device) -> Tensor:
        return torch.tensor(values, dtype=torch.int64, device=device)

    def _fixed_mode_values(self, reference: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        symbols = torch.tensor(self.mode_symbols, device=reference.device, dtype=reference.dtype).reshape(1, -1)
        slow_index = self._index(self.slow_indices, reference.device)
        omega2 = torch.full_like(symbols, self.config.fast_omega2)
        damping = torch.full_like(symbols, self.config.fast_damping)
        omega2.index_fill_(1, slow_index, self.config.slow_omega2)
        damping.index_fill_(1, slow_index, self.config.slow_damping)
        return symbols, omega2, damping

    @staticmethod
    def _complex_multiply(
        left_re: Tensor,
        left_im: Tensor,
        right_re: Tensor,
        right_im: Tensor,
    ) -> tuple[Tensor, Tensor]:
        return (
            left_re * right_re - left_im * right_im,
            left_re * right_im + left_im * right_re,
        )

    @staticmethod
    def _complex_conjugate_multiply(
        left_re: Tensor,
        left_im: Tensor,
        right_re: Tensor,
        right_im: Tensor,
    ) -> tuple[Tensor, Tensor]:
        return (
            left_re * right_re + left_im * right_im,
            left_re * right_im - left_im * right_re,
        )

    @staticmethod
    def _radial_bound(real: Tensor, imag: Tensor, maximum: float) -> tuple[Tensor, Tensor]:
        magnitude = torch.sqrt(real.square() + imag.square() + torch.finfo(real.dtype).eps)
        scale = torch.clamp(torch.as_tensor(maximum, device=real.device, dtype=real.dtype) / magnitude, max=1.0)
        return real * scale, imag * scale

    def _energy_bound(self, components: tuple[Tensor, ...]) -> tuple[Tensor, ...]:
        energy = sum(component.square() for component in components).mean(dim=1)
        scale = torch.sqrt(
            torch.clamp(
                torch.as_tensor(
                    self.config.max_mean_energy,
                    device=energy.device,
                    dtype=energy.dtype,
                )
                / torch.clamp_min(energy, torch.finfo(energy.dtype).eps),
                max=1.0,
            )
        ).reshape(-1, 1)
        return tuple(component * scale for component in components)

    def _bounded_state(self, components: tuple[Tensor, ...]) -> CassiFieldState:
        bounded: list[Tensor] = []
        for offset in range(0, 8, 2):
            real, imag = self._radial_bound(
                components[offset], components[offset + 1], self.config.max_mode_amplitude
            )
            bounded.extend((real, imag))
        result = self._pack(self._energy_bound(tuple(bounded)))
        result.validate(self.config)
        return result

    def component_energy(self, state: CassiFieldState) -> Tensor:
        components = self._unpack(state)
        return sum(component.square() for component in components).mean(dim=1)

    def free_energy(self, state: CassiFieldState) -> Tensor:
        ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im = self._unpack(state)
        symbols, omega2, _ = self._fixed_mode_values(ey_re)
        d_re = ey_re - self.config.phi * ei_re
        d_im = ey_im - self.config.phi * ei_im
        kinetic = vy_re.square() + vy_im.square() + vi_re.square() + vi_im.square()
        gradient = -symbols * (
            ey_re.square() + ey_im.square() + ei_re.square() + ei_im.square()
        )
        coupling = omega2 * (d_re.square() + d_im.square())
        nonlinear = 0.5 * self.config.nonlinear_gain * (
            d_re.square() + d_im.square()
        ).square()
        return (0.5 * kinetic + 0.5 * gradient + 0.5 * coupling + nonlinear).mean(dim=1)

    def _apply_differential_delta(
        self,
        first_re: Tensor,
        first_im: Tensor,
        second_re: Tensor,
        second_im: Tensor,
        delta_re: Tensor,
        delta_im: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        denominator = 1.0 + self.config.phi ** 2
        return (
            first_re + delta_re / denominator,
            first_im + delta_im / denominator,
            second_re - self.config.phi * delta_re / denominator,
            second_im - self.config.phi * delta_im / denominator,
        )

    def sense(self, state: CassiFieldState, symbols: Tensor) -> CassiFieldState:
        """Deposit fixed event waves into fast differential Yang/Yin modes."""

        components = list(self._unpack(state))
        ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im = components
        encoded = self.alphabet.encode(
            symbols,
            batch_size=state.batch_size,
            device=state.field.device,
            dtype=state.field.dtype,
        )
        fast_index = self._index(self.fast_indices, state.field.device)
        d_re = ey_re - self.config.phi * ei_re
        d_im = ey_im - self.config.phi * ei_im
        old_fast_re = d_re.index_select(1, fast_index)
        old_fast_im = d_im.index_select(1, fast_index)
        desired_re = self.config.sense_retention * old_fast_re + (1.0 - self.config.sense_retention) * encoded[:, :, 0]
        desired_im = self.config.sense_retention * old_fast_im + (1.0 - self.config.sense_retention) * encoded[:, :, 1]
        delta_re = torch.zeros_like(d_re).index_copy(1, fast_index, desired_re - old_fast_re)
        delta_im = torch.zeros_like(d_im).index_copy(1, fast_index, desired_im - old_fast_im)
        ey_re, ey_im, ei_re, ei_im = self._apply_differential_delta(
            ey_re, ey_im, ei_re, ei_im, delta_re, delta_im
        )

        vd_re = vy_re - self.config.phi * vi_re
        vd_im = vy_im - self.config.phi * vi_im
        old_vd_re = vd_re.index_select(1, fast_index)
        old_vd_im = vd_im.index_select(1, fast_index)
        velocity_delta_re = torch.zeros_like(vd_re).index_copy(
            1, fast_index, (self.config.sense_velocity_retention - 1.0) * old_vd_re
        )
        velocity_delta_im = torch.zeros_like(vd_im).index_copy(
            1, fast_index, (self.config.sense_velocity_retention - 1.0) * old_vd_im
        )
        vy_re, vy_im, vi_re, vi_im = self._apply_differential_delta(
            vy_re, vy_im, vi_re, vi_im, velocity_delta_re, velocity_delta_im
        )
        return self._bounded_state((ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im))

    def evolve(self, state: CassiFieldState, *, steps: int | None = None) -> CassiFieldState:
        """Advance the bounded two-fluid field with fixed native-mode physics."""

        count = self.config.settle_steps if steps is None else _positive_int("steps", steps)
        ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im = self._unpack(state)
        symbols, omega2, damping = self._fixed_mode_values(ey_re)
        damping_factor = torch.exp(-damping * self.config.dt)
        denominator = 1.0 + self.config.phi ** 2
        for _ in range(count):
            d_re = ey_re - self.config.phi * ei_re
            d_im = ey_im - self.config.phi * ei_im
            magnitude2 = d_re.square() + d_im.square()
            nonlinear_re = -self.config.nonlinear_gain * magnitude2 * d_re
            nonlinear_im = -self.config.nonlinear_gain * magnitude2 * d_im
            acc_y_re = (symbols - omega2) * ey_re + omega2 * self.config.phi * ei_re + nonlinear_re / denominator
            acc_y_im = (symbols - omega2) * ey_im + omega2 * self.config.phi * ei_im + nonlinear_im / denominator
            acc_i_re = symbols * ei_re + omega2 * d_re - self.config.phi * nonlinear_re / denominator
            acc_i_im = symbols * ei_im + omega2 * d_im - self.config.phi * nonlinear_im / denominator
            vy_re = damping_factor * vy_re + self.config.dt * acc_y_re
            vy_im = damping_factor * vy_im + self.config.dt * acc_y_im
            vi_re = damping_factor * vi_re + self.config.dt * acc_i_re
            vi_im = damping_factor * vi_im + self.config.dt * acc_i_im
            ey_re = ey_re + self.config.dt * vy_re
            ey_im = ey_im + self.config.dt * vy_im
            ei_re = ei_re + self.config.dt * vi_re
            ei_im = ei_im + self.config.dt * vi_im
            bounded = self._bounded_state(
                (ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im)
            )
            ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im = self._unpack(bounded)
        return self._pack((ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im))

    def prediction_wave(self, state: CassiFieldState) -> Tensor:
        """Measure phase-conjugate fast/slow wave mixing at the output boundary."""

        ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im = self._unpack(state)
        fast_index = self._index(self.fast_indices, state.field.device)
        slow_index = self._index(self.slow_indices, state.field.device)
        d_re = ey_re - self.config.phi * ei_re
        d_im = ey_im - self.config.phi * ei_im
        vd_re = vy_re - self.config.phi * vi_re
        vd_im = vy_im - self.config.phi * vi_im
        flux_re = d_re + self.config.flux_velocity_scale * vd_re
        flux_im = d_im + self.config.flux_velocity_scale * vd_im
        query_re = flux_re.index_select(1, fast_index)
        query_im = -flux_im.index_select(1, fast_index)  # native phase conjugation
        magnitude = torch.sqrt(
            query_re.square() + query_im.square() + self.config.correction_epsilon
        )
        active = magnitude >= self.config.emission_floor
        query_re = torch.where(active, query_re / magnitude, torch.zeros_like(query_re))
        query_im = torch.where(active, query_im / magnitude, torch.zeros_like(query_im))
        memory_re = flux_re.index_select(1, slow_index)
        memory_im = flux_im.index_select(1, slow_index)
        response_re, response_im = self._complex_multiply(
            query_re, query_im, memory_re, memory_im
        )
        return torch.stack((response_re, response_im), dim=-1)

    def emit(self, state: CassiFieldState) -> CassiFieldEmission:
        """Decode the fixed boundary resonance without logits or softmax."""

        wave = self.prediction_wave(state)
        scores = self.alphabet.resonance_scores(wave)
        flux = torch.sqrt(torch.mean(wave.square().sum(dim=-1), dim=1))
        available = flux >= self.config.emission_floor
        symbols = torch.argmax(scores, dim=1).to(dtype=torch.int64)
        symbols = torch.where(available, symbols, torch.full_like(symbols, -1))
        if self.config.alphabet_size == 1:
            top_value = scores[:, 0]
            second_value = torch.zeros_like(top_value)
        else:
            top_two = torch.topk(scores, k=2, dim=1, largest=True, sorted=True).values
            top_value, second_value = top_two[:, 0], top_two[:, 1]
        margin = top_value - second_value
        certainty = torch.clamp(
            margin / torch.clamp_min(torch.abs(top_value), self.config.correction_epsilon),
            min=0.0,
            max=1.0,
        )
        uncertainty = torch.where(available, 1.0 - certainty, torch.ones_like(certainty))
        return CassiFieldEmission(symbols, available, scores, flux, margin, uncertainty, wave)

    def correct(self, state: CassiFieldState, target_symbols: Tensor) -> tuple[CassiFieldState, Tensor]:
        """Write phase-conjugate prediction mismatch into slow modes of this field."""

        components = list(self._unpack(state))
        ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im = components
        target = self.alphabet.encode(
            target_symbols,
            batch_size=state.batch_size,
            device=state.field.device,
            dtype=state.field.dtype,
        )
        response = self.prediction_wave(state)
        error_re = target[:, :, 0] - response[:, :, 0]
        error_im = target[:, :, 1] - response[:, :, 1]

        fast_index = self._index(self.fast_indices, state.field.device)
        slow_index = self._index(self.slow_indices, state.field.device)
        d_re = ey_re - self.config.phi * ei_re
        d_im = ey_im - self.config.phi * ei_im
        query_re = d_re.index_select(1, fast_index)
        query_im = -d_im.index_select(1, fast_index)
        magnitude = torch.sqrt(
            query_re.square() + query_im.square() + self.config.correction_epsilon
        )
        query_re = query_re / magnitude
        query_im = query_im / magnitude
        drive_re, drive_im = self._complex_conjugate_multiply(
            query_re, query_im, error_re, error_im
        )
        denominator = query_re.square() + query_im.square() + self.config.correction_epsilon
        drive_re = self.config.plasticity_gain * drive_re / denominator
        drive_im = self.config.plasticity_gain * drive_im / denominator

        vd_re = vy_re - self.config.phi * vi_re
        vd_im = vy_im - self.config.phi * vi_im
        old_memory_re = d_re.index_select(1, slow_index)
        old_memory_im = d_im.index_select(1, slow_index)
        old_velocity_re = vd_re.index_select(1, slow_index)
        old_velocity_im = vd_im.index_select(1, slow_index)
        new_velocity_re = self.config.plasticity_momentum * old_velocity_re + drive_re
        new_velocity_im = self.config.plasticity_momentum * old_velocity_im + drive_im
        desired_memory_re = self.config.slow_retention * old_memory_re + new_velocity_re
        desired_memory_im = self.config.slow_retention * old_memory_im + new_velocity_im

        delta_memory_re = torch.zeros_like(d_re).index_copy(
            1, slow_index, desired_memory_re - old_memory_re
        )
        delta_memory_im = torch.zeros_like(d_im).index_copy(
            1, slow_index, desired_memory_im - old_memory_im
        )
        ey_re, ey_im, ei_re, ei_im = self._apply_differential_delta(
            ey_re, ey_im, ei_re, ei_im, delta_memory_re, delta_memory_im
        )
        delta_velocity_re = torch.zeros_like(vd_re).index_copy(
            1, slow_index, new_velocity_re - old_velocity_re
        )
        delta_velocity_im = torch.zeros_like(vd_im).index_copy(
            1, slow_index, new_velocity_im - old_velocity_im
        )
        vy_re, vy_im, vi_re, vi_im = self._apply_differential_delta(
            vy_re, vy_im, vi_re, vi_im, delta_velocity_re, delta_velocity_im
        )
        correction_energy = torch.mean(drive_re.square() + drive_im.square(), dim=1)
        result = self._bounded_state(
            (ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im)
        )
        return result, correction_energy

    def consolidate(self, state: CassiFieldState) -> CassiFieldState:
        """Damp transient fast modes while retaining slow condensate modes."""

        ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im = self._unpack(state)
        fast_index = self._index(self.fast_indices, state.field.device)
        slow_index = self._index(self.slow_indices, state.field.device)
        d_re = ey_re - self.config.phi * ei_re
        d_im = ey_im - self.config.phi * ei_im
        vd_re = vy_re - self.config.phi * vi_re
        vd_im = vy_im - self.config.phi * vi_im

        desired_d_re = d_re.clone()
        desired_d_im = d_im.clone()
        desired_vd_re = vd_re.clone()
        desired_vd_im = vd_im.clone()
        desired_d_re.index_copy_(1, fast_index, self.config.fast_retention * d_re.index_select(1, fast_index))
        desired_d_im.index_copy_(1, fast_index, self.config.fast_retention * d_im.index_select(1, fast_index))
        desired_d_re.index_copy_(1, slow_index, self.config.slow_retention * d_re.index_select(1, slow_index))
        desired_d_im.index_copy_(1, slow_index, self.config.slow_retention * d_im.index_select(1, slow_index))
        desired_vd_re.index_copy_(1, fast_index, self.config.fast_retention * vd_re.index_select(1, fast_index))
        desired_vd_im.index_copy_(1, fast_index, self.config.fast_retention * vd_im.index_select(1, fast_index))
        desired_vd_re.index_copy_(1, slow_index, self.config.plasticity_momentum * vd_re.index_select(1, slow_index))
        desired_vd_im.index_copy_(1, slow_index, self.config.plasticity_momentum * vd_im.index_select(1, slow_index))

        ey_re, ey_im, ei_re, ei_im = self._apply_differential_delta(
            ey_re, ey_im, ei_re, ei_im, desired_d_re - d_re, desired_d_im - d_im
        )
        vy_re, vy_im, vi_re, vi_im = self._apply_differential_delta(
            vy_re, vy_im, vi_re, vi_im, desired_vd_re - vd_re, desired_vd_im - vd_im
        )
        bounded = self._bounded_state(
            (ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im)
        )
        return self.evolve(bounded, steps=self.config.consolidation_steps)

    def cycle(
        self,
        state: CassiFieldState,
        current_symbols: Tensor,
        *,
        target_symbols: Tensor | None = None,
        learn: bool = True,
    ) -> CassiFieldCycle:
        """Run one complete field event without creating auxiliary model state."""

        sensed = self.sense(state, current_symbols)
        settled = self.evolve(sensed)
        emission = self.emit(settled)
        correction_energy = torch.zeros(
            state.batch_size, device=state.field.device, dtype=state.field.dtype
        )
        corrected = settled
        if target_symbols is not None and learn:
            corrected, correction_energy = self.correct(settled, target_symbols)
        consolidated = self.consolidate(corrected)
        return CassiFieldCycle(consolidated, emission, correction_energy)

    def reset(self, state: CassiFieldState, *, preserve_memory: bool) -> CassiFieldState:
        """Clear transients, optionally retaining slow modes of the same field."""

        self._validate_state(state)
        if not preserve_memory:
            return self.initial_state(
                state.batch_size, device=state.field.device, dtype=state.field.dtype
            )
        ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im = self._unpack(state)
        fast_index = self._index(self.fast_indices, state.field.device)
        d_re = ey_re - self.config.phi * ei_re
        d_im = ey_im - self.config.phi * ei_im
        vd_re = vy_re - self.config.phi * vi_re
        vd_im = vy_im - self.config.phi * vi_im
        zero_d_re = torch.zeros_like(d_re).index_copy(1, fast_index, -d_re.index_select(1, fast_index))
        zero_d_im = torch.zeros_like(d_im).index_copy(1, fast_index, -d_im.index_select(1, fast_index))
        zero_vd_re = torch.zeros_like(vd_re).index_copy(1, fast_index, -vd_re.index_select(1, fast_index))
        zero_vd_im = torch.zeros_like(vd_im).index_copy(1, fast_index, -vd_im.index_select(1, fast_index))
        ey_re, ey_im, ei_re, ei_im = self._apply_differential_delta(
            ey_re, ey_im, ei_re, ei_im, zero_d_re, zero_d_im
        )
        vy_re, vy_im, vi_re, vi_im = self._apply_differential_delta(
            vy_re, vy_im, vi_re, vi_im, zero_vd_re, zero_vd_im
        )
        return self._bounded_state(
            (ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im)
        )

    def imagine(self, state: CassiFieldState, *, steps: int) -> CassiFieldImagination:
        """Run autonomous field emission/reinjection with no external model or cache."""

        count = _positive_int("steps", steps)
        current = state
        emissions: list[CassiFieldEmission] = []
        for _ in range(count):
            settled = self.evolve(current)
            emission = self.emit(settled)
            if not bool(torch.all(emission.available).item()):
                break
            emissions.append(emission)
            current = self.sense(settled, emission.symbols)
            current = self.consolidate(current)
        return CassiFieldImagination(current, tuple(emissions))


def _atomic_torch_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    handle.close()
    try:
        torch.save(payload, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def save_field_state(
    path: Path | str,
    intelligence: CassiFieldIntelligence,
    state: CassiFieldState,
) -> str:
    """Persist exactly one adaptive tensor plus fixed contract identity."""

    if not isinstance(intelligence, CassiFieldIntelligence):
        raise CassiFieldIntelligenceError("intelligence must be a CassiFieldIntelligence")
    intelligence._validate_state(state)
    payload = {
        "schema": FIELD_STATE_SCHEMA,
        "layout_id": FIELD_LAYOUT_ID,
        "operator_profile_id": FIELD_OPERATOR_PROFILE_ID,
        "config_schema": FIELD_CONFIG_SCHEMA,
        "config": intelligence.config.to_dict(),
        "config_fingerprint": intelligence.config_fingerprint,
        "boundary_profile_id": BOUNDARY_PROFILE_ID,
        "boundary_fingerprint": intelligence.boundary_fingerprint,
        "field": state.field.detach().cpu(),
    }
    target = Path(path)
    _atomic_torch_save(payload, target)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def load_field_state(
    path: Path | str,
    intelligence: CassiFieldIntelligence,
    *,
    device: torch.device | str = "cpu",
    dtype: torch.dtype | None = None,
) -> CassiFieldState:
    """Load a field only when every fixed operator/transducer identity matches."""

    if not isinstance(intelligence, CassiFieldIntelligence):
        raise CassiFieldIntelligenceError("intelligence must be a CassiFieldIntelligence")
    target = Path(path)
    if not target.is_file():
        raise CassiFieldIntelligenceError(f"field-state artifact does not exist: {target}")
    target_device = torch.device(device)
    try:
        payload = torch.load(target, map_location=target_device, weights_only=True)
    except Exception as exc:
        raise CassiFieldIntelligenceError(
            f"field-state artifact cannot be loaded: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema") != FIELD_STATE_SCHEMA:
        raise CassiFieldIntelligenceError("field-state schema mismatch")
    if payload.get("layout_id") != FIELD_LAYOUT_ID or payload.get("operator_profile_id") != FIELD_OPERATOR_PROFILE_ID:
        raise CassiFieldIntelligenceError("field-state native operator identity mismatch")
    if payload.get("config_schema") != FIELD_CONFIG_SCHEMA:
        raise CassiFieldIntelligenceError("field-state configuration schema mismatch")
    loaded_config = CassiFieldIntelligenceConfig.from_dict(payload.get("config", {}))
    if loaded_config != intelligence.config or payload.get("config_fingerprint") != intelligence.config_fingerprint:
        raise CassiFieldIntelligenceError("field state belongs to a different fixed configuration")
    if payload.get("boundary_profile_id") != BOUNDARY_PROFILE_ID or payload.get("boundary_fingerprint") != intelligence.boundary_fingerprint:
        raise CassiFieldIntelligenceError("field state belongs to a different boundary transducer")
    field = payload.get("field")
    if not torch.is_tensor(field):
        raise CassiFieldIntelligenceError("field-state artifact is missing its sole adaptive tensor")
    target_dtype = dtype or field.dtype
    state = CassiFieldState(field.to(device=target_device, dtype=target_dtype))
    state.validate(intelligence.config, device=target_device, dtype=target_dtype)
    return state


__all__ = [
    "BOUNDARY_PROFILE_ID",
    "FIELD_CONFIG_SCHEMA",
    "FIELD_LAYOUT_ID",
    "FIELD_OPERATOR_PROFILE_ID",
    "FIELD_STATE_SCHEMA",
    "TEXT_BYTE_COUNT",
    "CassiBoundaryAlphabet",
    "CassiFieldCycle",
    "CassiFieldEmission",
    "CassiFieldImagination",
    "CassiFieldIntelligence",
    "CassiFieldIntelligenceConfig",
    "CassiFieldIntelligenceError",
    "CassiFieldState",
    "load_field_state",
    "save_field_state",
]
