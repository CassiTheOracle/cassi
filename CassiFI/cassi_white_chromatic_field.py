"""Global-white, seven-channel chromatic Qi field and read-only projection."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Sequence

import torch
from torch import Tensor

from cassi_prismatic_field import (
    PHI,
    HeartbeatReceipt,
    PrismaticFieldConfig,
    PrismaticFieldController,
    PrismaticReadout,
    PrismaticTick,
)
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldError, QiFieldState

WHITE_CHROMATIC_LAYOUT_PROFILE_ID = "cassi.qi-white-chromatic-shared-coordinate.v1"
WHITE_CHROMATIC_OPERATOR_PROFILE_ID = "cassi.qi-white-chromatic-heartbeat.v1"
WHITE_CHROMATIC_PROJECTION_PROFILE_ID = "cassi.qi-white-chromatic-projection.v1"
WHITE_CHROMATIC_CHANNEL_NAMES = (
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "indigo",
    "violet",
)
_CHANNEL_COUNT = len(WHITE_CHROMATIC_CHANNEL_NAMES)
_DENOMINATOR = 1.0 + PHI * PHI


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise QiFieldError(f"{name} must be a positive integer")
    return value


def _positive_finite(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QiFieldError(f"{name} must be a finite positive real number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise QiFieldError(f"{name} must be a finite positive real number")
    return result


@dataclass(frozen=True)
class WhiteChromaticFieldConfig:
    """Frozen geometry and energy budget for the L30 side-by-side operator."""

    mode_count: int
    alphabet_size: int = 260
    dt: float = 0.05
    base_omega2: float = 1.0
    base_damping: float = 0.2
    nonlinear_gain: float = 0.002
    coupling_omega2: float = 0.05
    epsilon_tau: float = 0.05
    heartbeat_carrier_energy: float = 0.5
    field_energy_budget: float = 1.0
    readout_energy_floor: float = 1.0e-8
    max_mode_amplitude: float = 8.0
    max_mean_energy: float = 4.0

    def __post_init__(self) -> None:
        mode_count = _positive_int("mode_count", self.mode_count)
        alphabet_size = _positive_int("alphabet_size", self.alphabet_size)
        if mode_count % 2:
            raise QiFieldError("mode_count must be even")
        if mode_count // 2 < alphabet_size:
            raise QiFieldError("mode_count // 2 must cover alphabet_size")
        object.__setattr__(self, "mode_count", mode_count)
        object.__setattr__(self, "alphabet_size", alphabet_size)
        for name in (
            "dt",
            "base_omega2",
            "base_damping",
            "nonlinear_gain",
            "coupling_omega2",
            "epsilon_tau",
            "heartbeat_carrier_energy",
            "field_energy_budget",
            "readout_energy_floor",
            "max_mode_amplitude",
            "max_mean_energy",
        ):
            object.__setattr__(self, name, _positive_finite(name, getattr(self, name)))
        if self.dt > 0.1:
            raise QiFieldError("dt must be in (0, 0.1]")
        if self.epsilon_tau > 1.0:
            raise QiFieldError("epsilon_tau must be in (0, 1]")
        if self.heartbeat_carrier_energy >= self.field_energy_budget:
            raise QiFieldError("heartbeat_carrier_energy must be below field_energy_budget")
        if self.max_mean_energy < self.field_energy_budget:
            raise QiFieldError("max_mean_energy must cover field_energy_budget")

    @property
    def bank_count(self) -> int:
        return _CHANNEL_COUNT

    @property
    def wave_mode_count(self) -> int:
        return self.mode_count // 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": WHITE_CHROMATIC_LAYOUT_PROFILE_ID,
                "operator_profile_id": WHITE_CHROMATIC_OPERATOR_PROFILE_ID,
                "projection_profile_id": WHITE_CHROMATIC_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @property
    def fingerprint(self) -> str:
        source = QiFieldController(
            QiFieldConfig(
                scale_count=1,
                mode_count=self.mode_count,
                alphabet_size=self.alphabet_size,
                primes=(4093,),
                settle_steps=1,
            )
        )
        return self.fingerprint_with(source.codebook_fingerprint)


@dataclass(frozen=True)
class WhiteChromaticHeartbeatReceipt(HeartbeatReceipt):
    total_energy_before: Tensor
    total_energy_after: Tensor
    dissipated_energy: Tensor


@dataclass(frozen=True)
class WhiteChromaticReadout(PrismaticReadout):

    @property
    def active_channel_count(self) -> Tensor:
        return self.active_bank_count


@dataclass(frozen=True)
class PsychedelicProjection:
    rgb: Tensor
    common_intensity: Tensor
    channel_intensity: Tensor
    side: int


@dataclass(frozen=True)
class WhiteChromaticTick(PrismaticTick):
    heartbeat: WhiteChromaticHeartbeatReceipt
    readout: WhiteChromaticReadout

    @property
    def dissipated_energy(self) -> Tensor:
        return self.heartbeat.dissipated_energy


class WhiteChromaticFieldController(PrismaticFieldController):
    """Field-owned white carrier refracted through seven chromatic channels."""

    def __init__(self, config: WhiteChromaticFieldConfig) -> None:
        if not isinstance(config, WhiteChromaticFieldConfig):
            raise QiFieldError("config must be a WhiteChromaticFieldConfig")
        base = PrismaticFieldConfig(
            bank_timescales=(1.0,) * _CHANNEL_COUNT,
            mode_count=config.mode_count,
            alphabet_size=config.alphabet_size,
            dt=config.dt,
            base_omega2=config.base_omega2,
            base_damping=config.base_damping,
            nonlinear_gain=config.nonlinear_gain,
            coupling_omega2=config.coupling_omega2,
            epsilon_tau=config.epsilon_tau,
            heartbeat_target_energy=config.heartbeat_carrier_energy,
            readout_energy_floor=config.readout_energy_floor,
            max_mode_amplitude=config.max_mode_amplitude,
            max_mean_energy=config.max_mean_energy,
        )
        super().__init__(base)
        self.config = config
        self._config_fingerprint = config.fingerprint_with(
            self._codebook_source.codebook_fingerprint
        )
        self._constant_cache = {}

    @property
    def bank_names(self) -> tuple[str, ...]:
        return WHITE_CHROMATIC_CHANNEL_NAMES

    @property
    def channel_names(self) -> tuple[str, ...]:
        return WHITE_CHROMATIC_CHANNEL_NAMES

    def codebook(
        self,
        scale: int = 0,
        *,
        device: torch.device | str = "cpu",
        dtype: torch.dtype = torch.float32,
    ) -> Tensor:
        if scale != 0:
            raise QiFieldError("white-chromatic field has one immutable codebook scale")
        return self._codebook_source.codebook(scale, device=device, dtype=dtype)

    def _constants(self, state: QiFieldState) -> dict[str, Tensor]:
        key = (state.field.device, state.field.dtype)
        cached = self._constant_cache.get(key)
        if cached is not None:
            return cached
        device, dtype = key
        width = self.config.wave_mode_count
        progress = torch.arange(width, device=device, dtype=dtype) / float(
            max(width - 1, 1)
        )
        timescale = torch.pow(
            torch.full((width,), PHI, device=device, dtype=dtype), 6.0 * progress
        ).reshape(1, width, 1)
        white = torch.full(
            (_CHANNEL_COUNT,), 1.0 / math.sqrt(_CHANNEL_COUNT), device=device, dtype=dtype
        )
        angle = 2.0 * math.pi * torch.arange(
            _CHANNEL_COUNT, device=device, dtype=dtype
        ) / float(_CHANNEL_COUNT)
        channel_phase = torch.complex(torch.cos(angle), torch.sin(angle))
        rgb = torch.tensor(
            (
                (1.0, 0.0, 0.0),
                (1.0, 0.35, 0.0),
                (1.0, 1.0, 0.0),
                (0.0, 1.0, 0.2),
                (0.0, 0.25, 1.0),
                (0.25, 0.0, 0.75),
                (0.65, 0.0, 1.0),
            ),
            device=device,
            dtype=dtype,
        )
        inverse_tau2 = timescale.square().reciprocal()
        cached = {
            "timescale": timescale,
            "omega2": self.config.base_omega2 * inverse_tau2,
            "damping_decay": torch.exp(
                -self.config.base_damping * self.config.dt / timescale
            ),
            "nonlinear": self.config.nonlinear_gain * inverse_tau2,
            "epsilon_alpha": 1.0
            - torch.pow(
                torch.full_like(timescale, 1.0 - self.config.epsilon_tau),
                timescale.reciprocal(),
            ),
            "edge_weight": (
                self.config.coupling_omega2
                * inverse_tau2.expand(_CHANNEL_COUNT - 1, -1, -1)
            ),
            "source_weights": white.square(),
            "white": white,
            "channel_phase": channel_phase,
            "rgb": rgb,
        }
        self._constant_cache[key] = cached
        return cached

    def _total_energy_unchecked(self, state: QiFieldState) -> Tensor:
        # Per-channel Yang/Yin plane energy already contains the C/D denominator;
        # this channel mean is the preregistered 1/7 aggregate.
        return self._dynamic_energy_unchecked(state).mean(dim=0)

    def dynamic_energy(self, state: QiFieldState) -> Tensor:
        self._validate_state(state)
        return self._total_energy_unchecked(state)

    def _carrier_projection(
        self, common: Tensor, common_velocity: Tensor, white: Tensor
    ) -> tuple[Tensor, Tensor]:
        return (
            (white[:, None, None] * common).sum(dim=0),
            (white[:, None, None] * common_velocity).sum(dim=0),
        )

    def _carrier_energy_from(
        self, common: Tensor, common_velocity: Tensor, white: Tensor
    ) -> Tensor:
        carrier, carrier_velocity = self._carrier_projection(
            common, common_velocity, white
        )
        return (
            carrier.abs().square() + carrier_velocity.abs().square()
        ).mean(dim=0) / (_CHANNEL_COUNT * _DENOMINATOR)

    def carrier_energy(self, state: QiFieldState) -> Tensor:
        self._validate_state(state)
        common, _, common_velocity, _ = self._active_coordinates(state)
        return self._carrier_energy_from(
            common, common_velocity, self._constants(state)["white"]
        )

    def _heartbeat_unchecked(
        self, state: QiFieldState
    ) -> tuple[QiFieldState, WhiteChromaticHeartbeatReceipt]:
        constants = self._constants(state)
        white = constants["white"]
        common, differential, common_velocity, differential_velocity = (
            self._active_coordinates(state)
        )
        total_before = self._total_energy_unchecked(state)
        carrier, carrier_velocity = self._carrier_projection(
            common, common_velocity, white
        )
        carrier_before = (
            carrier.abs().square() + carrier_velocity.abs().square()
        ).mean(dim=0) / (_CHANNEL_COUNT * _DENOMINATOR)
        white_shape = white[:, None, None]
        common_complement = common - white_shape * carrier[None]
        velocity_complement = (
            common_velocity - white_shape * carrier_velocity[None]
        )
        complement_energy = torch.clamp_min(total_before - carrier_before, 0.0)
        complement_budget = (
            self.config.field_energy_budget - self.config.heartbeat_carrier_energy
        )
        complement_scale = torch.where(
            complement_energy > complement_budget,
            torch.sqrt(
                complement_budget / torch.clamp_min(complement_energy, 1.0e-30)
            ),
            torch.ones_like(complement_energy),
        ).reshape(1, 1, -1)
        common_complement = common_complement * complement_scale
        velocity_complement = velocity_complement * complement_scale
        differential = differential * complement_scale
        differential_velocity = differential_velocity * complement_scale

        zero_carrier = carrier_before <= torch.finfo(state.field.dtype).eps
        if bool(zero_carrier.any().item()):
            mask = zero_carrier.reshape(1, -1)
            carrier = torch.where(mask, torch.ones_like(carrier), carrier)
            carrier_velocity = torch.where(
                mask, torch.zeros_like(carrier_velocity), carrier_velocity
            )
        seeded_energy = (
            carrier.abs().square() + carrier_velocity.abs().square()
        ).mean(dim=0) / (_CHANNEL_COUNT * _DENOMINATOR)
        carrier_scale = torch.sqrt(
            self.config.heartbeat_carrier_energy
            / torch.clamp_min(seeded_energy, 1.0e-30)
        ).reshape(1, -1)
        carrier = carrier * carrier_scale
        carrier_velocity = carrier_velocity * carrier_scale
        common = common_complement + white_shape * carrier[None]
        common_velocity = velocity_complement + white_shape * carrier_velocity[None]
        result = self._replace_coordinates(
            state,
            common,
            differential,
            common_velocity,
            differential_velocity,
        )
        result, clamp_count = self._bound(result)
        total_after = self._total_energy_unchecked(result)
        after_common, _, after_velocity, _ = self._active_coordinates(result)
        carrier_after = self._carrier_energy_from(
            after_common, after_velocity, white
        )
        change = total_after - total_before
        return result, WhiteChromaticHeartbeatReceipt(
            source_weights=constants["source_weights"].clone(),
            source_energy_before=carrier_before,
            source_energy_after=carrier_after,
            total_energy_before=total_before,
            total_energy_after=total_after,
            injected_energy=torch.clamp_min(change, 0.0),
            dissipated_energy=torch.clamp_min(-change, 0.0),
            clamp_count=clamp_count,
        )

    def heartbeat(
        self, state: QiFieldState
    ) -> tuple[QiFieldState, WhiteChromaticHeartbeatReceipt]:
        self._validate_state(state)
        return self._heartbeat_unchecked(state)

    def _modulate_unchecked(
        self,
        state: QiFieldState,
        symbols: Tensor | Sequence[int],
        source_trust: float | Tensor,
    ) -> tuple[QiFieldState, Tensor, int]:
        symbol_ids = self._symbol_tensor(symbols, state)
        trust = self._trust_tensor(source_trust, state)
        before = self._total_energy_unchecked(state)
        common, differential, common_velocity, differential_velocity = (
            self._active_coordinates(state)
        )
        constants = self._constants(state)
        white = constants["white"]
        phase_parts = self._codebook_source.codebook(
            0, device=state.field.device, dtype=state.field.dtype
        ).index_select(0, symbol_ids)
        phase = torch.complex(phase_parts[..., 0], phase_parts[..., 1]).transpose(0, 1)
        direction = (
            constants["channel_phase"][:, None, None]
            * phase[None]
            / math.sqrt(_CHANNEL_COUNT)
        )
        carrier, carrier_velocity = self._carrier_projection(
            common, common_velocity, white
        )
        chromatic = torch.sum(direction.conj() * differential, dim=0)
        chromatic_velocity = torch.sum(
            direction.conj() * differential_velocity, dim=0
        )
        alpha = (0.5 * math.pi * trust).reshape(1, -1)
        cosine, sine = torch.cos(alpha), torch.sin(alpha)
        new_chromatic = cosine * chromatic + sine * carrier
        new_carrier = cosine * carrier - sine * chromatic
        new_chromatic_velocity = (
            cosine * chromatic_velocity + sine * carrier_velocity
        )
        new_carrier_velocity = (
            cosine * carrier_velocity - sine * chromatic_velocity
        )
        common = common + white[:, None, None] * (new_carrier - carrier)[None]
        differential = differential + direction * (new_chromatic - chromatic)[None]
        common_velocity = common_velocity + white[:, None, None] * (
            new_carrier_velocity - carrier_velocity
        )[None]
        differential_velocity = differential_velocity + direction * (
            new_chromatic_velocity - chromatic_velocity
        )[None]
        result = self._replace_coordinates(
            state,
            common,
            differential,
            common_velocity,
            differential_velocity,
        )
        result, clamp_count = self._bound(result)
        after = self._total_energy_unchecked(result)
        denominator = torch.clamp_min(before.abs(), torch.finfo(before.dtype).eps)
        drift = torch.where(
            (before == 0.0) & (after == 0.0),
            torch.zeros_like(before),
            (after - before) / denominator,
        )
        return result, drift, clamp_count

    def modulate_symbols(
        self,
        state: QiFieldState,
        symbols: Tensor | Sequence[int],
        *,
        source_trust: float | Tensor = 1.0,
        trust: float | Tensor | None = None,
    ) -> tuple[QiFieldState, Tensor]:
        self._validate_state(state)
        if trust is not None:
            if not isinstance(source_trust, (int, float)) or float(source_trust) != 1.0:
                raise QiFieldError("use either source_trust or trust, not both")
            source_trust = trust
        result, drift, _ = self._modulate_unchecked(state, symbols, source_trust)
        return result, drift

    def evolve(self, state: QiFieldState, *, steps: int = 1) -> QiFieldState:
        self._validate_state(state)
        steps = _positive_int("steps", steps)
        result, _ = self._evolve_unchecked(state, steps)
        return result

    def _white_readout_unchecked(
        self,
        state: QiFieldState,
        allowed_symbols: Sequence[int] | None,
    ) -> WhiteChromaticReadout:
        _, differential, _, _ = self._active_coordinates(state)
        phase_parts = self._codebook_source.codebook(
            0, device=state.field.device, dtype=state.field.dtype
        )
        codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
        coefficients = torch.einsum(
            "aw,swb->sab", codebook.conj(), differential
        ) / float(self.config.wave_mode_count)
        aligned = (
            self._constants(state)["channel_phase"].conj()[:, None, None]
            * coefficients
        )
        global_coefficients = aligned.sum(dim=0) / math.sqrt(_CHANNEL_COUNT)
        scores = global_coefficients.abs().square().transpose(0, 1)
        bank_scores = coefficients.abs().square().permute(0, 2, 1)
        differential_rms = torch.sqrt(differential.abs().square().mean(dim=1))
        bank_energy = differential_rms.square()
        active = differential_rms >= self.config.readout_energy_floor
        active_bank_count = active.sum(dim=0)
        total_differential = differential.abs().square().mean(dim=(0, 1))
        available = (
            (total_differential >= self.config.readout_energy_floor)
            & (active_bank_count >= 2)
        )
        allowed = self._allowed_symbols(allowed_symbols)
        if allowed is None:
            symbols = torch.argmax(scores, dim=1)
        else:
            allowed = allowed.to(device=state.field.device)
            local = torch.argmax(scores.index_select(1, allowed), dim=1)
            symbols = allowed.index_select(0, local)
        contributions = aligned.permute(0, 2, 1)
        winning = aligned.permute(2, 0, 1).gather(
            2,
            symbols[:, None, None].expand(state.batch_size, _CHANNEL_COUNT, 1),
        )[:, :, 0]
        coherence = winning.sum(dim=1).abs().square() / (
            active_bank_count.to(dtype=state.field.dtype)
            * winning.abs().square().sum(dim=1)
            + 1.0e-12
        )
        coherence = torch.where(available, coherence, torch.zeros_like(coherence))
        return WhiteChromaticReadout(
            bank_scores=bank_scores,
            scores=scores,
            symbols=symbols,
            available=available,
            contributions=contributions,
            differential_rms=differential_rms,
            bank_energy=bank_energy,
            active_bank_count=active_bank_count,
            white_coherence=coherence,
        )

    def white_readout(
        self,
        state: QiFieldState,
        *,
        allowed_symbols: Sequence[int] | None = None,
    ) -> WhiteChromaticReadout:
        self._validate_state(state)
        return self._white_readout_unchecked(state, allowed_symbols)

    def psychedelic_projection(
        self, state: QiFieldState, *, max_side: int = 32
    ) -> PsychedelicProjection:
        self._validate_state(state)
        max_side = _positive_int("max_side", max_side)
        side = min(max_side, math.isqrt(self.config.wave_mode_count))
        if side < 2:
            raise QiFieldError("projection side must be at least 2")
        common, differential, _, _ = self._active_coordinates(state)
        white = self._constants(state)["white"]
        carrier = (white[:, None, None] * common).sum(dim=0)
        count = side * side
        indices = torch.div(
            torch.arange(count, device=state.field.device) * self.config.wave_mode_count,
            count,
            rounding_mode="floor",
        )
        common_spectrum = carrier.index_select(0, indices).transpose(0, 1).reshape(
            state.batch_size, side, side
        )
        channel_spectrum = differential.index_select(1, indices).permute(
            2, 0, 1
        ).reshape(state.batch_size, _CHANNEL_COUNT, side, side)
        common_wave = torch.fft.ifft2(common_spectrum, norm="ortho")
        channel_wave = torch.fft.ifft2(channel_spectrum, norm="ortho")
        common_intensity = common_wave.abs().square()
        by_batch = channel_wave.real.square()
        raw = common_intensity[:, None] + torch.einsum(
            "sc,bshw->bchw", self._constants(state)["rgb"], by_batch
        )
        rgb = raw / (1.0 + raw)
        return PsychedelicProjection(
            rgb=rgb,
            common_intensity=common_intensity,
            channel_intensity=by_batch.permute(1, 0, 2, 3),
            side=side,
        )

    def tick(
        self,
        state: QiFieldState,
        current_symbols: Tensor | Sequence[int] | None = None,
        *,
        symbols: Tensor | Sequence[int] | None = None,
        steps: int = 8,
        source_trust: float | Tensor = 1.0,
        trust: float | Tensor | None = None,
    ) -> WhiteChromaticTick:
        self._validate_state(state)
        steps = _positive_int("steps", steps)
        if symbols is not None:
            if current_symbols is not None:
                raise QiFieldError("use either current_symbols or symbols, not both")
            current_symbols = symbols
        if trust is not None:
            if not isinstance(source_trust, (int, float)) or float(source_trust) != 1.0:
                raise QiFieldError("use either source_trust or trust, not both")
            source_trust = trust
        current, heartbeat = self._heartbeat_unchecked(state)
        input_clamps = 0
        if current_symbols is None:
            drift = state.field.new_zeros(state.batch_size)
        else:
            current, drift, input_clamps = self._modulate_unchecked(
                current, current_symbols, source_trust
            )
        current, evolve_clamps = self._evolve_unchecked(current, steps)
        readout = self._white_readout_unchecked(current, None)
        return WhiteChromaticTick(
            state=current,
            heartbeat=heartbeat,
            input_energy_drift=drift,
            readout=readout,
            bank_energy=self._dynamic_energy_unchecked(current),
            hamiltonian=self._hamiltonian_unchecked(current),
            clamp_count=heartbeat.clamp_count + input_clamps + evolve_clamps,
        )


__all__ = [
    "PsychedelicProjection",
    "WHITE_CHROMATIC_CHANNEL_NAMES",
    "WHITE_CHROMATIC_LAYOUT_PROFILE_ID",
    "WHITE_CHROMATIC_OPERATOR_PROFILE_ID",
    "WHITE_CHROMATIC_PROJECTION_PROFILE_ID",
    "WhiteChromaticFieldConfig",
    "WhiteChromaticFieldController",
    "WhiteChromaticHeartbeatReceipt",
    "WhiteChromaticReadout",
    "WhiteChromaticTick",
]
