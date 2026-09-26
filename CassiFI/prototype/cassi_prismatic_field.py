"""Side-by-side phi-prismatic Qi field with heartbeat-only energy injection."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Sequence

import torch
from torch import Tensor

from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldError, QiFieldState

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PRISMATIC_LAYOUT_PROFILE_ID = "cassi.qi-prismatic-shared-coordinate.v1"
PRISMATIC_OPERATOR_PROFILE_ID = "cassi.qi-prismatic-heartbeat.v1"
PRISMATIC_BANK_NAMES = (
    "root",
    "sacral",
    "solar",
    "heart",
    "throat",
    "brow",
    "crown",
)


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
class PrismaticFieldConfig:
    """Fixed geometry and dynamics for one experimental prismatic field."""

    bank_timescales: tuple[float, ...]
    mode_count: int
    alphabet_size: int = 260
    dt: float = 0.05
    base_omega2: float = 1.0
    base_damping: float = 0.2
    nonlinear_gain: float = 0.002
    coupling_omega2: float = 0.25
    epsilon_tau: float = 0.05
    heartbeat_target_energy: float = 1.0
    readout_energy_floor: float = 1.0e-8
    max_mode_amplitude: float = 8.0
    max_mean_energy: float = 32.0

    def __post_init__(self) -> None:
        try:
            timescales = tuple(_positive_finite("bank_timescale", value) for value in self.bank_timescales)
        except TypeError as exc:
            raise QiFieldError("bank_timescales must be a finite sequence") from exc
        if len(timescales) < 2:
            raise QiFieldError("bank_timescales must contain at least two banks")
        object.__setattr__(self, "bank_timescales", timescales)

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
            "heartbeat_target_energy",
            "readout_energy_floor",
            "max_mode_amplitude",
            "max_mean_energy",
        ):
            object.__setattr__(self, name, _positive_finite(name, getattr(self, name)))
        if self.dt > 0.1:
            raise QiFieldError("dt must be in (0, 0.1]")
        if self.epsilon_tau > 1.0:
            raise QiFieldError("epsilon_tau must be in (0, 1]")

    @property
    def bank_count(self) -> int:
        return len(self.bank_timescales)

    @property
    def wave_mode_count(self) -> int:
        return self.mode_count // 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        payload = {
            "layout_profile_id": PRISMATIC_LAYOUT_PROFILE_ID,
            "operator_profile_id": PRISMATIC_OPERATOR_PROFILE_ID,
            "shared_codebook_fingerprint": codebook_fingerprint,
            "config": self.to_dict(),
        }
        encoded = json.dumps(
            payload,
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
class HeartbeatReceipt:
    """Per-batch accounting for one central heartbeat."""

    source_weights: Tensor
    source_energy_before: Tensor
    source_energy_after: Tensor
    injected_energy: Tensor
    clamp_count: int


@dataclass(frozen=True)
class PrismaticReadout:
    """Read-only coherent crown/white synthesis."""

    bank_scores: Tensor
    scores: Tensor
    symbols: Tensor
    available: Tensor
    contributions: Tensor
    differential_rms: Tensor
    bank_energy: Tensor
    active_bank_count: Tensor
    white_coherence: Tensor


@dataclass(frozen=True)
class PrismaticTick:
    """One heartbeat, optional modulation, evolution, and white readout."""

    state: QiFieldState
    heartbeat: HeartbeatReceipt
    input_energy_drift: Tensor
    readout: PrismaticReadout
    bank_energy: Tensor
    hamiltonian: Tensor
    clamp_count: int

    @property
    def injected_energy(self) -> Tensor:
        return self.heartbeat.injected_energy


class PrismaticFieldController:
    """Deterministic shared-coordinate field whose sole source is its heartbeat."""

    def __init__(self, config: PrismaticFieldConfig) -> None:
        if not isinstance(config, PrismaticFieldConfig):
            raise QiFieldError("config must be a PrismaticFieldConfig")
        self.config = config
        self._codebook_source = QiFieldController(
            QiFieldConfig(
                scale_count=1,
                mode_count=config.mode_count,
                alphabet_size=config.alphabet_size,
                primes=(4093,),
                settle_steps=1,
            )
        )
        self._config_fingerprint = config.fingerprint_with(
            self._codebook_source.codebook_fingerprint
        )
        self._constant_cache: dict[
            tuple[torch.device, torch.dtype], dict[str, Tensor]
        ] = {}

    @property
    def config_fingerprint(self) -> str:
        return self._config_fingerprint

    @property
    def codebook_fingerprint(self) -> str:
        return self._codebook_source.codebook_fingerprint

    @property
    def bank_names(self) -> tuple[str, ...]:
        if self.config.bank_count == len(PRISMATIC_BANK_NAMES):
            return PRISMATIC_BANK_NAMES
        return tuple(f"bank-{index}" for index in range(self.config.bank_count))

    def new_state(
        self,
        batch_size: int = 1,
        *,
        device: torch.device | str = "cpu",
        dtype: torch.dtype = torch.float32,
    ) -> QiFieldState:
        batch_size = _positive_int("batch_size", batch_size)
        if dtype not in (torch.float32, torch.float64):
            raise QiFieldError("prismatic field requires torch.float32 or torch.float64")
        return QiFieldState(
            torch.zeros(
                self.config.bank_count,
                9 * self.config.mode_count,
                batch_size,
                device=torch.device(device),
                dtype=dtype,
            )
        )

    def _validate_state(self, state: QiFieldState) -> None:
        if not isinstance(state, QiFieldState) or not torch.is_tensor(state.field):
            raise QiFieldError("state must be a QiFieldState")
        expected = (self.config.bank_count, 9 * self.config.mode_count)
        if (
            state.field.ndim != 3
            or tuple(state.field.shape[:2]) != expected
            or state.field.shape[2] < 1
        ):
            raise QiFieldError(
                f"field must have shape [{self.config.bank_count}, "
                f"9 * {self.config.mode_count}, B] with B >= 1"
            )
        if state.field.dtype not in (torch.float32, torch.float64):
            raise QiFieldError("prismatic field requires torch.float32 or torch.float64")
        if not bool(torch.isfinite(state.field).all().item()):
            raise QiFieldError("field contains non-finite values")
        packed = state.field.reshape(
            self.config.bank_count, 9, self.config.mode_count, state.batch_size
        )
        if bool(torch.count_nonzero(packed[:, :, self.config.wave_mode_count :]).item()):
            raise QiFieldError("inactive prismatic modes must remain exactly zero")

    def _parts(self, state: QiFieldState) -> tuple[Tensor, ...]:
        packed = state.field.reshape(
            self.config.bank_count, 9, self.config.mode_count, state.batch_size
        )
        return tuple(packed[:, index] for index in range(9))

    def _pack(self, parts: Sequence[Tensor]) -> QiFieldState:
        packed = torch.stack(tuple(parts), dim=1).reshape(
            self.config.bank_count, 9 * self.config.mode_count, parts[0].shape[-1]
        )
        return QiFieldState(packed.contiguous())

    def _constants(self, state: QiFieldState) -> dict[str, Tensor]:
        key = (state.field.device, state.field.dtype)
        cached = self._constant_cache.get(key)
        if cached is not None:
            return cached
        device, dtype = key
        width = self.config.wave_mode_count
        tau = torch.tensor(
            self.config.bank_timescales, device=device, dtype=dtype
        ).reshape(-1, 1, 1)
        mode_profile = (
            1.0
            + 0.25
            * torch.arange(width, device=device, dtype=dtype)
            / float(max(width - 1, 1))
        ).reshape(1, width, 1)
        source_weights = torch.zeros(
            self.config.bank_count, device=device, dtype=dtype
        )
        middle = self.config.bank_count // 2
        if self.config.bank_count % 2:
            source_weights[middle] = 1.0
        else:
            source_weights[middle - 1 : middle + 1] = 0.5
        cached = {
            "omega2": self.config.base_omega2 * mode_profile / tau.square(),
            "damping_decay": torch.exp(
                -self.config.base_damping * self.config.dt / tau
            ),
            "nonlinear": torch.full_like(mode_profile, self.config.nonlinear_gain)
            / tau.square(),
            "epsilon_alpha": 1.0
            - torch.pow(
                torch.full_like(tau, 1.0 - self.config.epsilon_tau),
                1.0 / tau,
            ),
            "edge_weight": self.config.coupling_omega2
            / (tau[:-1] * tau[1:]),
            "source_weights": source_weights,
        }
        self._constant_cache[key] = cached
        return cached

    def _active_coordinates(
        self, state: QiFieldState
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        width = self.config.wave_mode_count
        y_re, y_im, i_re, i_im, vy_re, vy_im, vi_re, vi_im, _ = self._parts(
            state
        )
        y = torch.complex(y_re[:, :width], y_im[:, :width])
        i = torch.complex(i_re[:, :width], i_im[:, :width])
        vy = torch.complex(vy_re[:, :width], vy_im[:, :width])
        vi = torch.complex(vi_re[:, :width], vi_im[:, :width])
        return PHI * y + i, y - PHI * i, PHI * vy + vi, vy - PHI * vi

    def _replace_coordinates(
        self,
        state: QiFieldState,
        common: Tensor,
        differential: Tensor,
        common_velocity: Tensor,
        differential_velocity: Tensor,
        *,
        epsilon: Tensor | None = None,
    ) -> QiFieldState:
        width = self.config.wave_mode_count
        denominator = 1.0 + PHI * PHI
        y = (differential + PHI * common) / denominator
        i = (common - PHI * differential) / denominator
        vy = (differential_velocity + PHI * common_velocity) / denominator
        vi = (common_velocity - PHI * differential_velocity) / denominator
        parts = [component.clone() for component in self._parts(state)]
        replacements = (y.real, y.imag, i.real, i.imag, vy.real, vy.imag, vi.real, vi.imag)
        for index, value in enumerate(replacements):
            parts[index][:, :width] = value
            parts[index][:, width:] = 0.0
        if epsilon is not None:
            parts[8][:, :width] = epsilon
        parts[8][:, width:] = 0.0
        return self._pack(parts)

    def _bound(self, state: QiFieldState) -> tuple[QiFieldState, int]:
        packed = state.field.reshape(
            self.config.bank_count, 9, self.config.mode_count, state.batch_size
        ).clone()
        width = self.config.wave_mode_count
        active = packed[:, :8, :width]
        clamped = active.clamp(
            min=-self.config.max_mode_amplitude,
            max=self.config.max_mode_amplitude,
        )
        clamp_count = int(torch.count_nonzero(active != clamped).item())
        packed[:, :8, :width] = clamped
        energy = clamped.square().sum(dim=1).mean(dim=1)
        excessive = energy > self.config.max_mean_energy
        factor = torch.where(
            excessive,
            torch.sqrt(
                self.config.max_mean_energy / torch.clamp_min(energy, 1.0e-30)
            ),
            torch.ones_like(energy),
        )
        packed[:, :8, :width] *= factor[:, None, None, :]
        clamp_count += int(torch.count_nonzero(excessive).item())

        epsilon = packed[:, 8, :width]
        bounded_epsilon = epsilon.clamp(
            min=0.0, max=self.config.max_mode_amplitude**4
        )
        clamp_count += int(torch.count_nonzero(epsilon != bounded_epsilon).item())
        packed[:, 8, :width] = bounded_epsilon
        packed[:, :, width:] = 0.0
        return QiFieldState(
            packed.reshape(
                self.config.bank_count,
                9 * self.config.mode_count,
                state.batch_size,
            ).contiguous()
        ), clamp_count

    def _dynamic_energy_unchecked(self, state: QiFieldState) -> Tensor:
        width = self.config.wave_mode_count
        packed = state.field.reshape(
            self.config.bank_count, 9, self.config.mode_count, state.batch_size
        )
        return packed[:, :8, :width].square().sum(dim=1).mean(dim=1)

    def dynamic_energy(self, state: QiFieldState) -> Tensor:
        self._validate_state(state)
        return self._dynamic_energy_unchecked(state)

    def _heartbeat_unchecked(
        self, state: QiFieldState
    ) -> tuple[QiFieldState, HeartbeatReceipt]:
        constants = self._constants(state)
        weights = constants["source_weights"]
        before_by_bank = self._dynamic_energy_unchecked(state)
        before = (before_by_bank * weights[:, None]).sum(dim=0)
        needs_energy = before < self.config.heartbeat_target_energy
        common, differential, common_velocity, differential_velocity = (
            self._active_coordinates(state)
        )
        source_mask = weights > 0.0
        zero_source = needs_energy & (before <= torch.finfo(state.field.dtype).eps)
        if bool(zero_source.any().item()):
            seed = zero_source.reshape(1, 1, -1)
            common[source_mask] = torch.where(
                seed,
                torch.ones_like(common[source_mask]),
                common[source_mask],
            )
            differential[source_mask] = torch.where(
                seed,
                torch.zeros_like(differential[source_mask]),
                differential[source_mask],
            )
            common_velocity[source_mask] = torch.where(
                seed,
                torch.zeros_like(common_velocity[source_mask]),
                common_velocity[source_mask],
            )
            differential_velocity[source_mask] = torch.where(
                seed,
                torch.zeros_like(differential_velocity[source_mask]),
                differential_velocity[source_mask],
            )

        coordinate_energy = (
            common.abs().square()
            + differential.abs().square()
            + common_velocity.abs().square()
            + differential_velocity.abs().square()
        ).mean(dim=1) / (1.0 + PHI * PHI)
        seeded_energy = (coordinate_energy * weights[:, None]).sum(dim=0)
        scale = torch.where(
            needs_energy,
            torch.sqrt(
                self.config.heartbeat_target_energy
                / torch.clamp_min(seeded_energy, 1.0e-30)
            ),
            torch.ones_like(seeded_energy),
        )
        source_scale = torch.where(
            source_mask[:, None], scale[None, :], torch.ones_like(scale)[None, :]
        )[:, None, :]
        common = common * source_scale
        differential = differential * source_scale
        common_velocity = common_velocity * source_scale
        differential_velocity = differential_velocity * source_scale
        result = self._replace_coordinates(
            state,
            common,
            differential,
            common_velocity,
            differential_velocity,
        )
        result, clamp_count = self._bound(result)
        after_by_bank = self._dynamic_energy_unchecked(result)
        after = (after_by_bank * weights[:, None]).sum(dim=0)
        return result, HeartbeatReceipt(
            source_weights=weights.clone(),
            source_energy_before=before,
            source_energy_after=after,
            injected_energy=after - before,
            clamp_count=clamp_count,
        )

    def heartbeat(
        self, state: QiFieldState
    ) -> tuple[QiFieldState, HeartbeatReceipt]:
        self._validate_state(state)
        return self._heartbeat_unchecked(state)

    def _symbol_tensor(
        self, symbols: Tensor | Sequence[int], state: QiFieldState
    ) -> Tensor:
        if torch.is_tensor(symbols):
            if symbols.dtype not in (
                torch.int8,
                torch.int16,
                torch.int32,
                torch.int64,
                torch.uint8,
            ):
                raise QiFieldError("symbols must use an integer dtype")
            result = symbols.to(device=state.field.device, dtype=torch.int64)
        else:
            try:
                values = tuple(symbols)
            except TypeError as exc:
                raise QiFieldError("symbols must be a one-dimensional sequence") from exc
            if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
                raise QiFieldError("symbols must contain integers")
            result = torch.tensor(values, device=state.field.device, dtype=torch.int64)
        if result.ndim != 1 or result.numel() != state.batch_size:
            raise QiFieldError("symbols must have shape [B]")
        if bool(((result < 0) | (result >= self.config.alphabet_size)).any().item()):
            raise QiFieldError("symbol is outside the configured alphabet")
        return result

    def _trust_tensor(
        self, source_trust: float | Tensor, state: QiFieldState
    ) -> Tensor:
        if torch.is_tensor(source_trust):
            trust = source_trust.to(
                device=state.field.device, dtype=state.field.dtype
            )
        elif isinstance(source_trust, bool) or not isinstance(
            source_trust, (int, float)
        ):
            raise QiFieldError("source_trust must be a finite real scalar or tensor")
        else:
            trust = torch.tensor(
                float(source_trust), device=state.field.device, dtype=state.field.dtype
            )
        if trust.ndim == 0:
            trust = trust.expand(state.batch_size)
        if trust.ndim != 1 or trust.numel() != state.batch_size:
            raise QiFieldError("source_trust must be scalar or have shape [B]")
        if not bool(torch.isfinite(trust).all().item()) or bool(
            ((trust < 0.0) | (trust > 1.0)).any().item()
        ):
            raise QiFieldError("source_trust must be finite and in [0, 1]")
        return trust

    def _modulate_unchecked(
        self,
        state: QiFieldState,
        symbols: Tensor | Sequence[int],
        source_trust: float | Tensor,
    ) -> tuple[QiFieldState, Tensor, int]:
        symbol_ids = self._symbol_tensor(symbols, state)
        trust = self._trust_tensor(source_trust, state)
        before = self._dynamic_energy_unchecked(state)[0]
        common, differential, common_velocity, differential_velocity = (
            self._active_coordinates(state)
        )
        codebook = self._codebook_source.codebook(
            0, device=state.field.device, dtype=state.field.dtype
        ).index_select(0, symbol_ids)
        phase = torch.complex(codebook[..., 0], codebook[..., 1]).transpose(0, 1)
        alpha = (0.5 * math.pi * trust).reshape(1, -1)
        cosine, sine = torch.cos(alpha), torch.sin(alpha)

        root_d = cosine * differential[0] + sine * phase * common[0]
        root_c = cosine * common[0] - sine * phase.conj() * differential[0]
        root_vd = (
            cosine * differential_velocity[0]
            + sine * phase * common_velocity[0]
        )
        root_vc = (
            cosine * common_velocity[0]
            - sine * phase.conj() * differential_velocity[0]
        )
        common = common.clone()
        differential = differential.clone()
        common_velocity = common_velocity.clone()
        differential_velocity = differential_velocity.clone()
        common[0], differential[0] = root_c, root_d
        common_velocity[0], differential_velocity[0] = root_vc, root_vd
        result = self._replace_coordinates(
            state,
            common,
            differential,
            common_velocity,
            differential_velocity,
        )
        result, clamp_count = self._bound(result)
        after = self._dynamic_energy_unchecked(result)[0]
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
    ) -> tuple[QiFieldState, Tensor]:
        self._validate_state(state)
        result, drift, _ = self._modulate_unchecked(state, symbols, source_trust)
        return result, drift

    @staticmethod
    def _coupling_force(position: Tensor, edge_weight: Tensor) -> Tensor:
        force = torch.zeros_like(position)
        delta = position[1:] - position[:-1]
        edge_force = edge_weight * delta
        force[:-1] += edge_force
        force[1:] -= edge_force
        return force

    def _evolve_unchecked(
        self, state: QiFieldState, steps: int
    ) -> tuple[QiFieldState, int]:
        constants = self._constants(state)
        clamp_count = 0
        current = state
        for _ in range(steps):
            common, differential, common_velocity, differential_velocity = (
                self._active_coordinates(current)
            )
            radius2 = common.abs().square() + differential.abs().square()
            common_force = self._coupling_force(
                common, constants["edge_weight"]
            )
            differential_force = self._coupling_force(
                differential, constants["edge_weight"]
            )
            common_velocity = (
                constants["damping_decay"] * common_velocity
                + self.config.dt
                * (
                    -constants["omega2"] * common
                    - constants["nonlinear"] * radius2 * common
                    + common_force
                )
            )
            differential_velocity = (
                constants["damping_decay"] * differential_velocity
                + self.config.dt
                * (
                    -constants["omega2"] * differential
                    - constants["nonlinear"] * radius2 * differential
                    + differential_force
                )
            )
            common = common + self.config.dt * common_velocity
            differential = differential + self.config.dt * differential_velocity
            denominator = 1.0 + PHI * PHI
            y = (differential + PHI * common) / denominator
            i = (common - PHI * differential) / denominator
            epsilon_target = (y.abs().square() - PHI * i.abs().square()).square()
            epsilon = self._parts(current)[8][:, : self.config.wave_mode_count]
            epsilon = epsilon + constants["epsilon_alpha"] * (
                epsilon_target - epsilon
            )
            current = self._replace_coordinates(
                current,
                common,
                differential,
                common_velocity,
                differential_velocity,
                epsilon=epsilon,
            )
            current, step_clamps = self._bound(current)
            clamp_count += step_clamps
        return current, clamp_count

    def evolve(self, state: QiFieldState, *, steps: int = 1) -> QiFieldState:
        self._validate_state(state)
        steps = _positive_int("steps", steps)
        result, _ = self._evolve_unchecked(state, steps)
        return result

    def _hamiltonian_unchecked(self, state: QiFieldState) -> Tensor:
        constants = self._constants(state)
        common, differential, common_velocity, differential_velocity = (
            self._active_coordinates(state)
        )
        radius2 = common.abs().square() + differential.abs().square()
        local = (
            0.5
            * (
                common_velocity.abs().square()
                + differential_velocity.abs().square()
            )
            + 0.5 * constants["omega2"] * radius2
            + 0.25 * constants["nonlinear"] * radius2.square()
        ) / (1.0 + PHI * PHI)
        edge = (
            0.5
            * constants["edge_weight"]
            * (
                (common[1:] - common[:-1]).abs().square()
                + (differential[1:] - differential[:-1]).abs().square()
            )
        ) / (1.0 + PHI * PHI)
        return local.mean(dim=1).sum(dim=0) + edge.mean(dim=1).sum(dim=0)

    def _allowed_symbols(self, allowed_symbols: Sequence[int] | None) -> Tensor | None:
        if allowed_symbols is None:
            return None
        values = tuple(allowed_symbols)
        if not values:
            raise QiFieldError("allowed_symbols must not be empty")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise QiFieldError("allowed_symbols must contain integers")
        if min(values) < 0 or max(values) >= self.config.alphabet_size:
            raise QiFieldError("allowed symbol is outside the configured alphabet")
        return torch.tensor(sorted(set(values)), dtype=torch.int64)

    def _white_readout_unchecked(
        self,
        state: QiFieldState,
        allowed_symbols: Sequence[int] | None,
    ) -> PrismaticReadout:
        common, differential, _, _ = self._active_coordinates(state)
        del common
        bank_energy = self._dynamic_energy_unchecked(state)
        differential_rms = torch.sqrt(differential.abs().square().mean(dim=1))
        codebook_parts = self._codebook_source.codebook(
            0, device=state.field.device, dtype=state.field.dtype
        )
        codebook = torch.complex(codebook_parts[..., 0], codebook_parts[..., 1])
        coefficients = torch.einsum(
            "aw,swb->sab", codebook.conj(), differential
        ) / float(self.config.wave_mode_count)
        coefficients = coefficients / torch.clamp_min(
            differential_rms[:, None, :], torch.finfo(state.field.dtype).eps
        )
        active = bank_energy >= self.config.readout_energy_floor
        contributions = torch.where(
            active[:, None, :], coefficients, torch.zeros_like(coefficients)
        )
        white = contributions.sum(dim=0)
        scores = white.abs().square().transpose(0, 1)
        bank_scores = contributions.abs().square().permute(0, 2, 1)

        allowed = self._allowed_symbols(allowed_symbols)
        if allowed is None:
            symbols = torch.argmax(scores, dim=1)
        else:
            allowed = allowed.to(device=state.field.device)
            local = torch.argmax(scores.index_select(1, allowed), dim=1)
            symbols = allowed.index_select(0, local)
        active_bank_count = active.sum(dim=0)
        available = (
            (bank_energy[-1] >= self.config.readout_energy_floor)
            & (active_bank_count >= 2)
        )
        winning = contributions.permute(2, 0, 1).gather(
            2,
            symbols[:, None, None].expand(
                state.batch_size, self.config.bank_count, 1
            ),
        )[:, :, 0]
        winning_score = scores.gather(1, symbols[:, None])[:, 0]
        coherence = winning_score / (
            active_bank_count.to(dtype=state.field.dtype)
            * winning.abs().square().sum(dim=1)
            + 1.0e-12
        )
        coherence = torch.where(available, coherence, torch.zeros_like(coherence))
        return PrismaticReadout(
            bank_scores=bank_scores,
            scores=scores,
            symbols=symbols,
            available=available,
            contributions=contributions.permute(0, 2, 1),
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
    ) -> PrismaticReadout:
        self._validate_state(state)
        return self._white_readout_unchecked(state, allowed_symbols)

    def tick(
        self,
        state: QiFieldState,
        current_symbols: Tensor | Sequence[int] | None = None,
        *,
        steps: int = 16,
    ) -> PrismaticTick:
        self._validate_state(state)
        steps = _positive_int("steps", steps)
        current, heartbeat = self._heartbeat_unchecked(state)
        input_clamps = 0
        if current_symbols is None:
            drift = state.field.new_zeros(state.batch_size)
        else:
            current, drift, input_clamps = self._modulate_unchecked(
                current, current_symbols, 1.0
            )
        current, evolve_clamps = self._evolve_unchecked(current, steps)
        energy = self._dynamic_energy_unchecked(current)
        readout = self._white_readout_unchecked(current, None)
        return PrismaticTick(
            state=current,
            heartbeat=heartbeat,
            input_energy_drift=drift,
            readout=readout,
            bank_energy=energy,
            hamiltonian=self._hamiltonian_unchecked(current),
            clamp_count=heartbeat.clamp_count + input_clamps + evolve_clamps,
        )


__all__ = [
    "HeartbeatReceipt",
    "PHI",
    "PRISMATIC_BANK_NAMES",
    "PRISMATIC_LAYOUT_PROFILE_ID",
    "PRISMATIC_OPERATOR_PROFILE_ID",
    "PrismaticFieldConfig",
    "PrismaticFieldController",
    "PrismaticReadout",
    "PrismaticTick",
]
