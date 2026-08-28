"""Canonical deterministic Qi multi-scale field reference.

The controller in this module is a field-only reference for the Qi upgrade. Its
only adaptive value is :class:`QiFieldState.field`, packed as ``[S, 9*M, B]``.
Per scale the first eight mode planes are Yang/Yin position and velocity
real/imaginary components and the ninth plane is ``epsilon2_ema``. Codebooks,
mode profiles, and all gates are fixed procedural data; there are no learned
parameters, embedding tables, or auxiliary adaptive memories.

Scale zero is the fastest/finest bank. Increasing scale index is slower and is
positive +z for the declared fast-to-slow current
``j_scale = Im(conj(D_s) * D_{s+1})``. Cross-scale measurements first undo each
bank's fixed boundary-bin permutation, so they compare a shared coordinate
rather than unrelated raw mode indices.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field as dataclass_field
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor
QI_COMPONENT_ORDER = (
    "Y_re",
    "Y_im",
    "I_re",
    "I_im",
    "VY_re",
    "VY_im",
    "VI_re",
    "VI_im",
    "epsilon2_ema",
)
QI_SCALE_ORIENTATION = "scale0=fastest-fine; increasing-index=slower-positive-z"


QI_FIELD_CONFIG_SCHEMA = "cassi.qi.field-config.v2"
QI_FIELD_STATE_SCHEMA = "cassi.qi.field-state.v2"
QI_FIELD_LAYOUT_ID = "cassi.qi.native-linear-scale-component-mode.v2"
QI_FIELD_OPERATOR_PROFILE_ID = "cassi.qi.multi-scale-de-resonant.v2"
QI_CODEBOOK_PROFILE_ID = "cassi.qi.scale-prime-quadratic-chirp.v2"
QI_OLD_FIELD_STATE_SCHEMA = "cassi.field-intelligence.state.v1"

_DEFAULT_PHI = 1.618033988749895
_DEFAULT_PRIMES = (4093, 4099, 4127, 4133)
# (quadratic symbol coefficient, linear symbol coefficient, quadratic position
# coefficient, linear position coefficient). Distinct permutations below are
# part of the fixed codebook identity, not adaptive state.
_SCALE_COEFFICIENTS = (
    (1, 1, 1, 3),
    (3, 5, 7, 11),
    (5, 9, 11, 17),
    (7, 13, 17, 23),
)
_SCALE_PERMUTATIONS = ((1, 0), (5, 1), (7, 3), (11, 5))
_MAX_QI_FIELD_STATE_BYTES = 64 * 1024 * 1024


class QiFieldError(ValueError):
    """Invalid Qi configuration, state, boundary input, or artifact."""


CassiQiFieldError = QiFieldError


def _coerce_state_bytes(payload: bytes | bytearray | memoryview) -> bytes:
    """Validate and own one bounded serialized Qi field-state payload."""

    if isinstance(payload, bool) or not isinstance(payload, (bytes, bytearray, memoryview)):
        raise QiFieldError("Qi field-state payload must be bytes, bytearray, or memoryview")
    try:
        size = payload.nbytes if isinstance(payload, memoryview) else len(payload)
    except (TypeError, ValueError) as exc:
        raise QiFieldError("Qi field-state payload size cannot be read") from exc
    if size < 1:
        raise QiFieldError("Qi field-state payload must be nonempty")
    if size > _MAX_QI_FIELD_STATE_BYTES:
        raise QiFieldError(
            f"Qi field-state payload exceeds the {_MAX_QI_FIELD_STATE_BYTES}-byte limit"
        )
    try:
        owned = bytes(payload)
    except Exception as exc:
        raise QiFieldError(f"Qi field-state payload cannot be copied: {type(exc).__name__}: {exc}") from exc
    if not owned:
        raise QiFieldError("Qi field-state payload must be nonempty")
    if len(owned) > _MAX_QI_FIELD_STATE_BYTES:
        raise QiFieldError(
            f"Qi field-state payload exceeds the {_MAX_QI_FIELD_STATE_BYTES}-byte limit"
        )
    return owned


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise QiFieldError(f"{name} must be a positive integer")
    return value


def _finite(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QiFieldError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise QiFieldError(f"{name} must be finite")
    return result


def _positive_finite(name: str, value: Any) -> float:
    result = _finite(name, value)
    if result <= 0.0:
        raise QiFieldError(f"{name} must be positive")
    return result


def _unit_interval(name: str, value: Any) -> float:
    result = _finite(name, value)
    if result < 0.0 or result > 1.0:
        raise QiFieldError(f"{name} must be in [0, 1]")
    return result


def _nonnegative(name: str, value: Any) -> float:
    result = _finite(name, value)
    if result < 0.0:
        raise QiFieldError(f"{name} must be non-negative")
    return result


def _floating_dtype(dtype: torch.dtype) -> None:
    if dtype not in (torch.float32, torch.float64):
        raise QiFieldError("Qi field state requires torch.float32 or torch.float64")


@dataclass(frozen=True)
class QiFieldPhysicsConfig:
    """Plain fixed data for the bounded Yang/Yin differential dynamics."""

    dt: float = 0.005
    fast_omega2: float = 20.0
    slow_omega2: float = 0.05
    fast_damping: float = 0.5
    slow_damping: float = 0.01
    nonlinear_gain: float = 0.002
    max_mode_amplitude: float = 8.0
    max_mean_energy: float = 32.0
    correction_epsilon: float = 1.0e-6
    velocity_weight: float = 0.05

    def __post_init__(self) -> None:
        for name in (
            "dt",
            "fast_omega2",
            "slow_omega2",
            "fast_damping",
            "slow_damping",
            "max_mode_amplitude",
            "max_mean_energy",
            "correction_epsilon",
        ):
            object.__setattr__(self, name, _positive_finite(name, getattr(self, name)))
        for name in ("nonlinear_gain", "velocity_weight"):
            object.__setattr__(self, name, _nonnegative(name, getattr(self, name)))
        if self.dt * math.sqrt(max(self.fast_omega2, self.slow_omega2)) >= 1.4:
            raise QiFieldError("physics dt and fast_omega2 violate the conservative stability bound")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "QiFieldPhysicsConfig":
        if not isinstance(value, Mapping):
            raise QiFieldError("physics configuration must be a mapping")
        expected = set(cls.__dataclass_fields__)
        payload = dict(value)
        unknown = set(payload) - expected
        if unknown:
            raise QiFieldError(f"physics configuration has unknown fields: {sorted(unknown)!r}")
        try:
            return cls(**payload)
        except QiFieldError:
            raise
        except (TypeError, ValueError) as exc:
            raise QiFieldError(f"invalid physics configuration: {exc}") from exc


@dataclass(frozen=True)
class QiFieldConfig:
    """Fixed controller and codebook controls.

    ``scale_ratio`` is derived from ``phi`` when omitted, so changing ``phi``
    cannot silently retain an identity from the default scale ladder. The
    nested ``physics`` object is plain fixed data and is included in the
    checkpoint fingerprint.
    """

    scale_count: int = 4
    mode_count: int = 512
    alphabet_size: int = 260
    phi: float = _DEFAULT_PHI
    scale_ratio: float | None = None
    primes: tuple[int, ...] = _DEFAULT_PRIMES
    energy_floor: float = 1.0e-6
    read_floor: float = 0.05
    read_threshold: float | None = None
    emission_floor: float = 1.0e-6
    epsilon_tau: float = _DEFAULT_PHI**-1
    epsilon_clip: float = 64.0
    sense_gain: float = 1.0
    correction_gain: float = 0.5
    consolidation_gain: float = 0.25
    write_trust_floor: float = 0.25
    settle_steps: int = 1
    consolidation_steps: int = 1
    physics: QiFieldPhysicsConfig = dataclass_field(default_factory=QiFieldPhysicsConfig)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scale_count", _positive_int("scale_count", self.scale_count))
        object.__setattr__(self, "mode_count", _positive_int("mode_count", self.mode_count))
        object.__setattr__(self, "alphabet_size", _positive_int("alphabet_size", self.alphabet_size))
        object.__setattr__(self, "settle_steps", _positive_int("settle_steps", self.settle_steps))
        object.__setattr__(self, "consolidation_steps", _positive_int("consolidation_steps", self.consolidation_steps))
        if self.mode_count < 4 or self.mode_count % 2:
            raise QiFieldError("mode_count must be even and at least four")
        if self.scale_count > len(_DEFAULT_PRIMES):
            raise QiFieldError("scale_count is limited to the declared fixed prime tuple")
        if self.alphabet_size > 65_536:
            raise QiFieldError("alphabet_size is unreasonably large")
        object.__setattr__(self, "phi", _positive_finite("phi", self.phi))
        ratio = self.phi**3 if self.scale_ratio is None else _positive_finite("scale_ratio", self.scale_ratio)
        if ratio <= 1.0:
            raise QiFieldError("scale_ratio must be greater than one")
        object.__setattr__(self, "scale_ratio", ratio)

        primes = tuple(int(value) for value in self.primes)
        # The declared four-prime identity is the default ladder. Smaller
        # reference controllers use its fixed prefix; custom ladders must
        # still bind exactly one explicit prime to every scale.
        if len(primes) != self.scale_count:
            if primes == _DEFAULT_PRIMES and self.scale_count < len(primes):
                primes = primes[: self.scale_count]
            else:
                raise QiFieldError("primes must contain exactly one distinct fixed prime for every scale")
        if any(value < 3 for value in primes) or len(set(primes)) != len(primes):
            raise QiFieldError("primes must be distinct integers greater than two")
        object.__setattr__(self, "primes", primes)

        for name in ("energy_floor", "read_floor", "emission_floor", "epsilon_clip"):
            object.__setattr__(self, name, _positive_finite(name, getattr(self, name)))
        threshold = self.read_floor if self.read_threshold is None else _positive_finite("read_threshold", self.read_threshold)
        object.__setattr__(self, "read_threshold", threshold)
        for name in ("epsilon_tau", "sense_gain", "correction_gain", "consolidation_gain", "write_trust_floor"):
            object.__setattr__(self, name, _unit_interval(name, getattr(self, name)))
        if isinstance(self.physics, Mapping):
            object.__setattr__(self, "physics", QiFieldPhysicsConfig.from_dict(self.physics))
        elif not isinstance(self.physics, QiFieldPhysicsConfig):
            raise QiFieldError("physics must be a QiFieldPhysicsConfig")

    @property
    def wave_mode_count(self) -> int:
        return self.mode_count // 2

    @property
    def base(self) -> QiFieldPhysicsConfig:
        return self.physics

    @property
    def base_physics(self) -> QiFieldPhysicsConfig:
        return self.physics

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "QiFieldConfig":
        if not isinstance(value, Mapping):
            raise QiFieldError("Qi field configuration must be a mapping")
        expected = set(cls.__dataclass_fields__)
        payload = dict(value)
        unknown = set(payload) - expected
        if unknown:
            raise QiFieldError(f"Qi field configuration has unknown fields: {sorted(unknown)!r}")
        if "primes" in payload:
            payload["primes"] = tuple(payload["primes"])
        if "physics" in payload and isinstance(payload["physics"], Mapping):
            payload["physics"] = QiFieldPhysicsConfig.from_dict(payload["physics"])
        try:
            return cls(**payload)
        except QiFieldError:
            raise
        except (TypeError, ValueError) as exc:
            raise QiFieldError(f"invalid Qi field configuration: {exc}") from exc

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class QiFieldState:
    """The sole adaptive Qi value, with shape ``[S, 9*M, B]``."""

    field: Tensor

    @property
    def batch_size(self) -> int:
        if self.field.ndim != 3:
            raise QiFieldError("Qi field state must have three dimensions")
        return int(self.field.shape[2])

    def validate(
        self,
        config: QiFieldConfig,
        *,
        device: torch.device | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        if not torch.is_tensor(self.field):
            raise QiFieldError("field must be a torch.Tensor")
        expected = (config.scale_count, 9 * config.mode_count)
        if self.field.ndim != 3 or tuple(self.field.shape[:2]) != expected or self.field.shape[2] < 1:
            raise QiFieldError(
                f"field must have shape [{config.scale_count}, 9 * {config.mode_count}, B] with B >= 1"
            )
        _floating_dtype(self.field.dtype)
        if device is not None and self.field.device != device:
            raise QiFieldError("field device does not match the requested device")
        if dtype is not None and self.field.dtype != dtype:
            raise QiFieldError("field dtype does not match the requested dtype")
        if not bool(torch.isfinite(self.field).all().item()):
            raise QiFieldError("field contains non-finite values")

    def clone(self) -> "QiFieldState":
        return QiFieldState(self.field.clone())

    def detach(self) -> "QiFieldState":
        return QiFieldState(self.field.detach())

    def to(self, device: torch.device | str, *, dtype: torch.dtype | None = None) -> "QiFieldState":
        return QiFieldState(self.field.to(device=device, dtype=dtype or self.field.dtype))


@dataclass(frozen=True)
class QiFieldDiagnostics:
    """Compact finite per-scale diagnostics."""

    rho: Tensor
    epsilon: Tensor
    epsilon2_ema: Tensor
    q: Tensor
    q_max: Tensor
    chi: Tensor
    available: Tensor
    j_temporal: Tensor
    j_scale: Tensor
    cross_scale_coherence: Tensor
    read_gate: Tensor
    write_gate: Tensor
    consolidation_gate: Tensor
    source_trust: Tensor

    @property
    def q_coherence(self) -> Tensor:
        return self.q

    @property
    def read_gate_any(self) -> Tensor:
        return self.read_gate.max(dim=0).values if self.read_gate.shape[0] else self.source_trust.new_zeros(self.source_trust.shape)

    @property
    def write_gate_any(self) -> Tensor:
        return self.write_gate.max(dim=0).values if self.write_gate.shape[0] else self.source_trust.new_zeros(self.source_trust.shape)


@dataclass(frozen=True)
class QiFieldReadout:
    """A query-dependent phase-conjugate read from the fixed boundary."""

    symbols: Tensor
    available: Tensor
    scores: Tensor
    wave: Tensor
    flux: Tensor
    margin: Tensor
    uncertainty: Tensor
    q: Tensor
    q_max: Tensor
    chi: Tensor
    cross_scale_coherence: Tensor
    read_gate: Tensor
    contribution_weights: Tensor

    @property
    def symbol(self) -> Tensor:
        return self.symbols

    @property
    def q_coherence(self) -> Tensor:
        return self.q


@dataclass(frozen=True)
class QiSenseResult:
    state: QiFieldState
    write_gate: Tensor
    source_trust: Tensor


@dataclass(frozen=True)
class QiFieldCycle:
    state: QiFieldState
    emission: QiFieldReadout
    correction_energy: Tensor


@dataclass(frozen=True)
class QiBalanceConversion:
    """Projected rank-one Yang/Yin conversion and its conservation receipt."""

    state: QiFieldState
    density_before: Tensor
    density_after: Tensor
    imbalance_l1_before: Tensor
    imbalance_l1_after: Tensor
    transferred_density: Tensor
    clipped_modes: int

@dataclass(frozen=True)
class QiConsolidationResult:
    state: QiFieldState
    consolidation_gate: Tensor


class QiFieldController:
    """Parameter-free deterministic multi-scale Qi controller."""

    def __init__(self, config: QiFieldConfig | None = None) -> None:
        if config is None:
            config = QiFieldConfig()
        if not isinstance(config, QiFieldConfig):
            raise QiFieldError("config must be a QiFieldConfig")
        self.config = config
        self._mode_profile = tuple(1.0 + 0.25 * (index / max(1, config.mode_count - 1)) for index in range(config.mode_count))
        self._codebook_descriptors = tuple(self._make_codebook_descriptor(scale) for scale in range(config.scale_count))
        self._codebook_cache: dict[tuple[int, torch.device, torch.dtype], Tensor] = {}
        descriptor = json.dumps(self._codebook_descriptors, separators=(",", ":"), sort_keys=False).encode("utf-8")
        self._codebook_fingerprint = hashlib.sha256(descriptor).hexdigest()

    @property
    def config_fingerprint(self) -> str:
        return self.config.fingerprint

    @property
    def codebook_fingerprint(self) -> str:
        return self._codebook_fingerprint

    @property
    def boundary_fingerprint(self) -> str:
        return self._codebook_fingerprint

    @property
    def codebook_descriptors(self) -> tuple[dict[str, Any], ...]:
        return self._codebook_descriptors

    @property
    def scale_count(self) -> int:
        return self.config.scale_count

    @property
    def mode_count(self) -> int:
        return self.config.mode_count

    @property
    def wave_mode_count(self) -> int:
        return self.config.wave_mode_count

    def _make_codebook_descriptor(self, scale: int) -> dict[str, Any]:
        coefficients = _SCALE_COEFFICIENTS[scale % len(_SCALE_COEFFICIENTS)]
        permutation = _SCALE_PERMUTATIONS[scale % len(_SCALE_PERMUTATIONS)]
        return {
            "profile": QI_CODEBOOK_PROFILE_ID,
            "scale": scale,
            "prime": int(self.config.primes[scale]),
            "coefficients": list(coefficients),
            "permutation": list(permutation),
            "phase_denominator": int(self.config.primes[scale]),
            "wave_modes": self.config.wave_mode_count,
        }

    def _validate_state(self, state: QiFieldState) -> None:
        if not isinstance(state, QiFieldState):
            raise QiFieldError("state must be a QiFieldState")
        state.validate(self.config)

    def initial_state(self, batch_size: int, *, device: torch.device | str = "cpu", dtype: torch.dtype = torch.float32) -> QiFieldState:
        batch_size = _positive_int("batch_size", batch_size)
        _floating_dtype(dtype)
        state = QiFieldState(torch.zeros(self.config.scale_count, 9 * self.config.mode_count, batch_size, device=torch.device(device), dtype=dtype))
        state.validate(self.config)
        return state

    def _parts(self, state: QiFieldState) -> tuple[Tensor, ...]:
        self._validate_state(state)
        packed = state.field.reshape(self.config.scale_count, 9, self.config.mode_count, state.batch_size)
        return tuple(packed[:, index] for index in range(9))

    def _pack(self, parts: Sequence[Tensor]) -> QiFieldState:
        if len(parts) != 9:
            raise QiFieldError("a Qi field requires eight position/velocity planes and epsilon2_ema")
        shape = parts[0].shape
        if len(shape) != 3 or shape[:2] != (self.config.scale_count, self.config.mode_count) or shape[2] < 1:
            raise QiFieldError("Qi field components must have shape [S, M, B]")
        if any(component.shape != shape for component in parts):
            raise QiFieldError("Qi field components must share [S, M, B]")
        packed = torch.stack(tuple(parts), dim=1).reshape(self.config.scale_count, 9 * self.config.mode_count, shape[2])
        result = QiFieldState(packed.contiguous())
        result.validate(self.config)
        return result

    def _permutation_indices(self, scale: int, *, device: torch.device) -> Tensor:
        """Raw active-bin -> shared boundary-bin coordinate permutation."""

        width = self.config.wave_mode_count
        perm_a, perm_b = _SCALE_PERMUTATIONS[scale % len(_SCALE_PERMUTATIONS)]
        positions = torch.arange(width, device=device, dtype=torch.int64)
        return torch.remainder(positions * perm_a + perm_b, width)

    def _align_active(self, values: Tensor, scale: int) -> Tensor:
        """Undo the fixed scale permutation into shared boundary coordinates."""

        width = self.config.wave_mode_count
        if values.shape[0] != width:
            raise QiFieldError("active-bin tensor has the wrong wave width")
        aligned = torch.zeros_like(values)
        aligned.index_copy_(0, self._permutation_indices(scale, device=values.device), values)
        return aligned

    def _unalign_active(self, values: Tensor, scale: int) -> Tensor:
        """Map shared boundary coordinates into a scale's raw active bins."""

        width = self.config.wave_mode_count
        if values.shape[0] != width:
            raise QiFieldError("aligned-bin tensor has the wrong wave width")
        # _align_active performs aligned[perm[i]] = raw[i], so its exact
        # inverse is raw[i] = aligned[perm[i]] (a gather, not another scatter).
        return values.index_select(0, self._permutation_indices(scale, device=values.device))

    def codebook(self, scale: int, *, device: torch.device | str = "cpu", dtype: torch.dtype = torch.float32) -> Tensor:
        """Return one immutable fixed ``[alphabet, W, 2]`` real/imag codebook.

        Codebooks are procedural constants, not adaptive state.  Cache each
        device/dtype realization so symbol-by-symbol field cycles do not
        repeatedly reconstruct the same chirps.
        """

        if isinstance(scale, bool) or not isinstance(scale, int) or scale < 0 or scale >= self.config.scale_count:
            raise QiFieldError("scale is outside the configured codebook bank")
        _floating_dtype(dtype)
        target_device = torch.device(device)
        cache_key = (scale, target_device, dtype)
        cached = self._codebook_cache.get(cache_key)
        if cached is not None:
            return cached
        width = self.config.wave_mode_count
        symbol = torch.arange(self.config.alphabet_size, device=target_device, dtype=torch.int64).reshape(-1, 1) + 1
        position = torch.arange(width, device=target_device, dtype=torch.int64).reshape(1, -1) + 1
        coefficients = _SCALE_COEFFICIENTS[scale % len(_SCALE_COEFFICIENTS)]
        perm_a, perm_b = _SCALE_PERMUTATIONS[scale % len(_SCALE_PERMUTATIONS)]
        permuted = torch.remainder(position * perm_a + perm_b, width) + 1
        c_symbol2, c_symbol, c_position2, c_position = coefficients
        prime = int(self.config.primes[scale])
        phase_index = torch.remainder(c_symbol2 * symbol.square() * permuted + c_symbol * symbol * permuted.square() + c_position2 * permuted.square() + c_position * symbol, prime)
        phase = 2.0 * math.pi * phase_index.to(dtype=dtype) / float(prime)
        value = torch.stack((torch.cos(phase), torch.sin(phase)), dim=-1)
        self._codebook_cache[cache_key] = value
        return value

    def codebooks(self, *, device: torch.device | str = "cpu", dtype: torch.dtype = torch.float32) -> Tensor:
        """Return all fixed codebooks as ``[S, alphabet, W, 2]``."""

        return torch.stack(tuple(self.codebook(scale, device=device, dtype=dtype) for scale in range(self.config.scale_count)), dim=0)

    scale_codebook = codebook

    def _index_symbols(self, symbols: Tensor | Sequence[int], *, batch_size: int, device: torch.device) -> Tensor:
        if not torch.is_tensor(symbols):
            symbols = torch.as_tensor(symbols, device=device)
        if symbols.ndim != 1 or symbols.shape[0] != batch_size:
            raise QiFieldError("symbols must have shape [B]")
        if symbols.dtype not in (torch.int32, torch.int64):
            raise QiFieldError("symbols must use int32 or int64")
        symbols = symbols.to(device=device, dtype=torch.int64)
        if bool(torch.any(symbols < 0).item()) or bool(torch.any(symbols >= self.config.alphabet_size).item()):
            raise QiFieldError("symbols contain an event outside the configured alphabet")
        return symbols

    def _source_values(self, value: Tensor | float | int | Sequence[float] | None, *, batch_size: int, device: torch.device, dtype: torch.dtype) -> Tensor:
        if value is None:
            return torch.ones(batch_size, device=device, dtype=dtype)
        if not torch.is_tensor(value):
            value = torch.as_tensor(value, device=device, dtype=dtype)
        else:
            value = value.to(device=device, dtype=dtype)
        if value.ndim == 0:
            value = value.expand(batch_size)
        if value.shape != (batch_size,):
            raise QiFieldError("structured_source/source_trust must have shape [B]")
        if not bool(torch.isfinite(value).all().item()):
            raise QiFieldError("source trust must be finite")
        return torch.clamp(value, min=0.0, max=1.0)

    def _bounded_parts(self, parts: Sequence[Tensor]) -> tuple[Tensor, ...]:
        bounded = [component for component in parts]
        maximum = self.config.physics.max_mode_amplitude
        eps = torch.finfo(parts[0].dtype).eps
        for offset in (0, 2, 4, 6):
            real, imag = bounded[offset], bounded[offset + 1]
            magnitude = torch.sqrt(real.square() + imag.square() + eps)
            factor = torch.clamp(torch.as_tensor(maximum, device=real.device, dtype=real.dtype) / magnitude, max=1.0)
            bounded[offset] = real * factor
            bounded[offset + 1] = imag * factor
        energy = sum(component.square() for component in bounded[:8]).mean(dim=1)
        energy_factor = torch.sqrt(torch.clamp(torch.as_tensor(self.config.physics.max_mean_energy, device=energy.device, dtype=energy.dtype) / torch.clamp_min(energy, eps), max=1.0)).unsqueeze(1)
        bounded[:8] = [component * energy_factor for component in bounded[:8]]
        bounded[8] = torch.clamp(bounded[8], min=0.0, max=self.config.epsilon_clip)
        return tuple(bounded)

    def _bounded_state(self, parts: Sequence[Tensor]) -> QiFieldState:
        return self._pack(self._bounded_parts(parts))

    def _apply_differential_delta(
        self,
        parts: list[Tensor],
        delta_re: Tensor,
        delta_im: Tensor,
        *,
        scale: int | None = None,
        active_width: int | None = None,
        velocity: bool = False,
    ) -> None:
        denominator = 1.0 + self.config.phi**2
        offset = 4 if velocity else 0
        if scale is None:
            parts[offset] = parts[offset] + delta_re / denominator
            parts[offset + 1] = parts[offset + 1] + delta_im / denominator
            parts[offset + 2] = parts[offset + 2] - self.config.phi * delta_re / denominator
            parts[offset + 3] = parts[offset + 3] - self.config.phi * delta_im / denominator
            return
        if active_width is None:
            parts[offset][scale] = parts[offset][scale] + delta_re / denominator
            parts[offset + 1][scale] = parts[offset + 1][scale] + delta_im / denominator
            parts[offset + 2][scale] = parts[offset + 2][scale] - self.config.phi * delta_re / denominator
            parts[offset + 3][scale] = parts[offset + 3][scale] - self.config.phi * delta_im / denominator
            return
        parts[offset][scale, :active_width] = parts[offset][scale, :active_width] + delta_re / denominator
        parts[offset + 1][scale, :active_width] = parts[offset + 1][scale, :active_width] + delta_im / denominator
        parts[offset + 2][scale, :active_width] = parts[offset + 2][scale, :active_width] - self.config.phi * delta_re / denominator
        parts[offset + 3][scale, :active_width] = parts[offset + 3][scale, :active_width] - self.config.phi * delta_im / denominator

    def _demodulate_bank(
        self,
        d_re: Tensor,
        d_im: Tensor,
        scale: int,
    ) -> tuple[Tensor, Tensor, Tensor]:
        """Project one raw active bank into common symbol coordinates.

        The projection is a fixed phase-conjugate correlation against the
        scale-specific chirp.  It is not a learned head: the output is a
        complex coefficient per fixed symbol, plus the source RMS used for
        bounded reconstruction.
        """

        width = self.config.wave_mode_count
        eps = torch.finfo(d_re.dtype).eps
        raw_re = d_re[:width]
        raw_im = d_im[:width]
        signal_rms = torch.sqrt((raw_re.square() + raw_im.square()).mean(dim=0) + eps)
        normalized_re = raw_re / signal_rms.unsqueeze(0)
        normalized_im = raw_im / signal_rms.unsqueeze(0)
        codes = self.codebook(scale, device=d_re.device, dtype=d_re.dtype)
        code_re = codes[:, :, 0]
        code_im = codes[:, :, 1]
        coefficient_re = (
            torch.einsum("aw,wb->ab", code_re, normalized_re)
            + torch.einsum("aw,wb->ab", code_im, normalized_im)
        ) / float(width)
        coefficient_im = (
            torch.einsum("aw,wb->ab", code_re, normalized_im)
            - torch.einsum("aw,wb->ab", code_im, normalized_re)
        ) / float(width)
        return coefficient_re, coefficient_im, signal_rms

    def _demodulate_active(
        self,
        d_re: Tensor,
        d_im: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor]:
        coefficients_re = []
        coefficients_im = []
        signal_rms = []
        for scale in range(self.config.scale_count):
            coefficient_re, coefficient_im, bank_rms = self._demodulate_bank(
                d_re[scale],
                d_im[scale],
                scale,
            )
            coefficients_re.append(coefficient_re)
            coefficients_im.append(coefficient_im)
            signal_rms.append(bank_rms)
        return (
            torch.stack(tuple(coefficients_re), dim=0),
            torch.stack(tuple(coefficients_im), dim=0),
            torch.stack(tuple(signal_rms), dim=0),
        )

    def _metrics_raw(self, state: QiFieldState) -> dict[str, Tensor]:
        y_re, y_im, i_re, i_im, vy_re, vy_im, vi_re, vi_im, epsilon2 = self._parts(state)
        phi = self.config.phi
        eps = torch.finfo(state.field.dtype).eps
        # Canonical quantities: E_Y=|Psi_Y|^2, E_I=|Psi_I|^2,
        # rho=E_Y+E_I, epsilon=E_Y-phi*E_I. D below is a separate
        # differential coordinate for dynamics/readout/current diagnostics.
        y_energy_mode = y_re.square() + y_im.square()
        i_energy_mode = i_re.square() + i_im.square()
        y_energy = y_energy_mode.mean(dim=1)
        i_energy = i_energy_mode.mean(dim=1)
        rho = torch.clamp(y_energy + i_energy, min=0.0)
        epsilon = (y_energy_mode - phi * i_energy_mode).mean(dim=1)
        epsilon2_mean = torch.clamp(epsilon2, min=0.0, max=self.config.epsilon_clip).mean(dim=1)
        rho2 = rho.square()
        inv_phi2 = phi ** -2
        q_max = rho2 / (rho2 + inv_phi2)
        q = rho2 / (rho2 + inv_phi2 + epsilon2_mean)
        q = torch.minimum(torch.clamp(q, min=0.0, max=1.0), q_max)
        available = rho > self.config.energy_floor
        chi = torch.where(available & (q_max > eps), q / torch.clamp_min(q_max, eps), torch.zeros_like(q))
        chi = torch.clamp(chi, min=0.0, max=1.0)

        d_re = y_re - phi * i_re
        d_im = y_im - phi * i_im
        vd_re = vy_re - phi * vi_re
        vd_im = vy_im - phi * vi_im
        d_energy = (d_re.square() + d_im.square()).mean(dim=1)
        j_temporal = (d_re * vd_im - d_im * vd_re).mean(dim=1)

        # Cross-scale comparisons use true fixed-codebook demodulation into
        # common symbol IDs. Raw-mode permutation alone is not a valid
        # cross-scale coordinate because every scale has a different chirp.
        demod_re, demod_im, signal_rms = self._demodulate_active(d_re, d_im)
        decoded_symbols = torch.argmax(demod_re, dim=1)
        top_re = demod_re.gather(1, decoded_symbols.unsqueeze(1))
        top_im = demod_im.gather(1, decoded_symbols.unsqueeze(1))
        # A one-symbol binding is the shared resonance coordinate. Keeping
        # only the declared top binding prevents off-symbol chirp leakage
        # from masquerading as cross-scale coherence.
        binding_re = torch.zeros_like(demod_re).scatter_(1, decoded_symbols.unsqueeze(1), top_re)
        binding_im = torch.zeros_like(demod_im).scatter_(1, decoded_symbols.unsqueeze(1), top_im)
        binding_energy = (binding_re.square() + binding_im.square()).sum(dim=1)
        demod_energy = (demod_re.square() + demod_im.square()).sum(dim=1)
        if self.config.scale_count > 1:
            inner_re = (
                binding_re[:-1] * binding_re[1:] + binding_im[:-1] * binding_im[1:]
            ).sum(dim=1)
            inner_im = (
                binding_re[:-1] * binding_im[1:] - binding_im[:-1] * binding_re[1:]
            ).sum(dim=1)
            pair_denominator = torch.sqrt(
                torch.clamp_min(binding_energy[:-1] * binding_energy[1:], eps)
            )
            pair_valid = pair_denominator > math.sqrt(eps)
            same_symbol = decoded_symbols[:-1] == decoded_symbols[1:]
            pair_phase = torch.where(
                pair_valid & same_symbol,
                torch.clamp(
                    inner_re / torch.clamp_min(pair_denominator, eps),
                    min=-1.0,
                    max=1.0,
                ),
                torch.where(
                    pair_valid,
                    torch.full_like(inner_re, -1.0),
                    torch.ones_like(inner_re),
                ),
            )
            j_scale = torch.where(pair_valid, inner_im, torch.zeros_like(inner_im))
            pair_agreement = torch.clamp(
                0.5 * (pair_phase + 1.0),
                min=0.0,
                max=1.0,
            )
            pair_available = available[:-1] & available[1:]
            pair_sum = (
                pair_agreement * pair_available.to(dtype=pair_agreement.dtype)
            ).sum(dim=0)
            pair_count = pair_available.to(dtype=pair_agreement.dtype).sum(dim=0)
            consensus = torch.where(
                pair_count > 0.0,
                pair_sum / torch.clamp_min(pair_count, 1.0),
                torch.ones_like(pair_sum),
            )
            target_empty = ~available[1:]
            consolidation_phase = torch.where(
                target_empty,
                torch.ones_like(pair_agreement),
                pair_agreement,
            )
            current_ok = (
                j_scale >= -self.config.physics.correction_epsilon
            ).to(dtype=pair_agreement.dtype)
            source_factor = available[:-1].to(dtype=pair_agreement.dtype) * chi[:-1]
            target_open = 1.0 - q[1:]
            consolidation_gate = (
                source_factor
                * consolidation_phase
                * current_ok
                * target_open
                * self.config.consolidation_gain
            )
        else:
            j_scale = state.field.new_zeros((0, state.batch_size))
            consolidation_gate = state.field.new_zeros((0, state.batch_size))
            consensus = torch.ones(
                state.batch_size,
                device=state.field.device,
                dtype=state.field.dtype,
            )

        cross_scale = torch.where(
            available,
            consensus.unsqueeze(0).expand(self.config.scale_count, -1),
            torch.zeros_like(rho),
        )
        read_gate = torch.clamp(chi * cross_scale, min=0.0, max=1.0)
        return {
            "rho": rho,
            "epsilon": epsilon,
            "epsilon2_ema": epsilon2_mean,
            "q": q,
            "q_max": q_max,
            "chi": chi,
            "available": available,
            "j_temporal": j_temporal,
            "j_scale": j_scale,
            "cross_scale_coherence": cross_scale,
            "consensus": consensus,
            "read_gate": read_gate,
            "consolidation_gate": consolidation_gate,
            "d_re": d_re,
            "d_im": d_im,
            "vd_re": vd_re,
            "vd_im": vd_im,
            "d_energy": d_energy,
            "demod_re": demod_re,
            "demod_im": demod_im,
            "demod_energy": demod_energy,
            "decoded_symbols": decoded_symbols,
            "signal_rms": signal_rms,
        }

    def diagnostics(self, state: QiFieldState, *, structured_source: Tensor | float | int | Sequence[float] | None = None, source_trust: Tensor | float | int | Sequence[float] | None = None) -> QiFieldDiagnostics:
        self._validate_state(state)
        if structured_source is not None and source_trust is not None:
            raise QiFieldError("provide structured_source or source_trust, not both")
        source = self._source_values(structured_source if structured_source is not None else source_trust, batch_size=state.batch_size, device=state.field.device, dtype=state.field.dtype)
        metrics = self._metrics_raw(state)
        trust_ok = source >= self.config.write_trust_floor
        gate0 = source * (1.0 - metrics["q"][0])
        gate0 = torch.where(~metrics["available"][0] & trust_ok, source, gate0)
        gate0 = torch.where(trust_ok, gate0, torch.zeros_like(gate0))
        write_gate = torch.zeros_like(metrics["read_gate"])
        write_gate[0] = torch.clamp(gate0, min=0.0, max=1.0)
        return QiFieldDiagnostics(metrics["rho"], metrics["epsilon"], metrics["epsilon2_ema"], metrics["q"], metrics["q_max"], metrics["chi"], metrics["available"], metrics["j_temporal"], metrics["j_scale"], metrics["cross_scale_coherence"], metrics["read_gate"], write_gate, metrics["consolidation_gate"], source)

    def _write_wave(self, state: QiFieldState, wave: Tensor, source: Tensor, *, return_result: bool) -> QiFieldState | QiSenseResult:
        self._validate_state(state)
        if wave.shape != (state.batch_size, self.config.wave_mode_count, 2):
            raise QiFieldError("boundary wave must have shape [B, M/2, 2]")
        if not wave.dtype.is_floating_point or not bool(torch.isfinite(wave).all().item()):
            raise QiFieldError("boundary wave must be finite and floating point")
        wave = wave.to(device=state.field.device, dtype=state.field.dtype)
        metrics = self._metrics_raw(state)
        trust_ok = source >= self.config.write_trust_floor
        gate = source * (1.0 - metrics["q"][0])
        gate = torch.where(~metrics["available"][0] & trust_ok, source, gate)
        gate = torch.where(trust_ok, gate, torch.zeros_like(gate))
        gain = self.config.sense_gain * torch.clamp(gate, min=0.0, max=1.0)
        parts = [component.clone() for component in self._parts(state)]
        width = self.config.wave_mode_count
        current_re = parts[0][0, :width] - self.config.phi * parts[2][0, :width]
        current_im = parts[1][0, :width] - self.config.phi * parts[3][0, :width]
        desired_re = wave[:, :, 0].transpose(0, 1)
        desired_im = wave[:, :, 1].transpose(0, 1)
        gain_modes = gain.reshape(1, -1)
        delta_re = gain_modes * (desired_re - current_re)
        delta_im = gain_modes * (desired_im - current_im)
        self._apply_differential_delta(parts, delta_re, delta_im, scale=0, active_width=width)
        velocity_gain = gain.reshape(1, -1)
        for offset in (4, 5, 6, 7):
            parts[offset][0, :width] = parts[offset][0, :width] * (1.0 - velocity_gain)
        result = self._bounded_state(parts)
        if return_result:
            return QiSenseResult(result, gate, source)
        return result

    def sense_symbols(self, state: QiFieldState, symbols: Tensor | Sequence[int], *, structured_source: Tensor | float | int | Sequence[float] | None = None, source_trust: Tensor | float | int | Sequence[float] | None = None, return_result: bool = False) -> QiFieldState | QiSenseResult:
        """Deposit a fixed symbol wave into scale zero through the write gate."""

        self._validate_state(state)
        if structured_source is not None and source_trust is not None:
            raise QiFieldError("provide structured_source or source_trust, not both")
        ids = self._index_symbols(symbols, batch_size=state.batch_size, device=state.field.device)
        source = self._source_values(1.0 if structured_source is None and source_trust is None else (structured_source if structured_source is not None else source_trust), batch_size=state.batch_size, device=state.field.device, dtype=state.field.dtype)
        wave = self.codebook(0, device=state.field.device, dtype=state.field.dtype).index_select(0, ids)
        return self._write_wave(state, wave, source, return_result=return_result)

    @staticmethod
    def _wave_shape(wave: Tensor, *, batch_size: int, mode_count: int) -> Tensor:
        if not torch.is_tensor(wave):
            raise QiFieldError("boundary wave must be a torch.Tensor")
        if wave.ndim == 2 and tuple(wave.shape) == (batch_size, 2 * mode_count):
            wave = wave.reshape(batch_size, mode_count, 2)
        if wave.ndim != 3 or tuple(wave.shape) != (batch_size, mode_count, 2):
            raise QiFieldError("boundary wave must have shape [B, M/2, 2] or [B, M]")
        return wave

    def _resonance_scores(self, wave: Tensor, *, scale: int) -> Tensor:
        codes = self.codebook(scale, device=wave.device, dtype=wave.dtype)
        return torch.einsum("bmc,amc->ba", wave, codes) / float(self.config.wave_mode_count)

    def sense_wave(self, state: QiFieldState, wave: Tensor, *, structured_source: Tensor | float | int | Sequence[float] | None = None, source_trust: Tensor | float | int | Sequence[float] | None = None, return_result: bool = False) -> QiFieldState | QiSenseResult:
        """Deposit exactly a ``[B, M/2, 2]`` teacher/boundary wave into scale zero."""

        self._validate_state(state)
        if structured_source is not None and source_trust is not None:
            raise QiFieldError("provide structured_source or source_trust, not both")
        wave = self._wave_shape(wave, batch_size=state.batch_size, mode_count=self.config.wave_mode_count)
        if not wave.dtype.is_floating_point or not bool(torch.isfinite(wave).all().item()):
            raise QiFieldError("boundary wave must be finite and floating point")
        wave = wave.to(device=state.field.device, dtype=state.field.dtype)
        if structured_source is None and source_trust is None:
            raw_scores = self._resonance_scores(wave, scale=0)
            # A random wave's largest fixed-chirp correlation is not a
            # structured source. Subtract a deterministic finite-alphabet
            # noise floor before applying the trust floor.
            noise_floor = min(0.9, 2.0 / math.sqrt(float(self.config.wave_mode_count)))
            source = torch.clamp(
                (raw_scores.amax(dim=1) - noise_floor) / max(1.0 - noise_floor, 1.0e-6),
                min=0.0,
                max=1.0,
            )
        else:
            source = self._source_values(
                structured_source if structured_source is not None else source_trust,
                batch_size=state.batch_size,
                device=state.field.device,
                dtype=state.field.dtype,
            )
        return self._write_wave(state, wave, source, return_result=return_result)

    def evolve(self, state: QiFieldState, *, steps: int | None = None) -> QiFieldState:
        """Advance all banks with bounded differential Yang/Yin dynamics."""

        self._validate_state(state)
        count = self.config.settle_steps if steps is None else _positive_int("steps", steps)
        parts = [component.clone() for component in self._parts(state)]
        dt = self.config.physics.dt
        phi = self.config.phi
        mode_profile = torch.tensor(self._mode_profile, device=state.field.device, dtype=state.field.dtype).reshape(1, -1, 1)
        scale_indices = torch.arange(self.config.scale_count, device=state.field.device, dtype=state.field.dtype).reshape(-1, 1, 1)
        scale_decay = torch.pow(torch.as_tensor(self.config.scale_ratio, device=state.field.device, dtype=state.field.dtype), -0.5 * scale_indices)
        omega2 = torch.clamp(self.config.physics.fast_omega2 * scale_decay * mode_profile, min=self.config.physics.slow_omega2)
        damping = torch.clamp(self.config.physics.fast_damping * scale_decay, min=self.config.physics.slow_damping)
        damping_factor = torch.exp(-damping * dt)
        for _ in range(count):
            d_re = parts[0] - phi * parts[2]
            d_im = parts[1] - phi * parts[3]
            vd_re = parts[4] - phi * parts[6]
            vd_im = parts[5] - phi * parts[7]
            magnitude2 = d_re.square() + d_im.square()
            nonlinear = self.config.physics.nonlinear_gain * magnitude2
            new_vd_re = damping_factor * vd_re + dt * (-omega2 * d_re - nonlinear * d_re)
            new_vd_im = damping_factor * vd_im + dt * (-omega2 * d_im - nonlinear * d_im)
            new_d_re = d_re + dt * new_vd_re
            new_d_im = d_im + dt * new_vd_im
            self._apply_differential_delta(parts, new_d_re - d_re, new_d_im - d_im)
            self._apply_differential_delta(parts, new_vd_re - vd_re, new_vd_im - vd_im, velocity=True)
            y_energy_mode = parts[0].square() + parts[1].square()
            i_energy_mode = parts[2].square() + parts[3].square()
            epsilon_target = (y_energy_mode - phi * i_energy_mode).square()
            # Canonical IIR: bar_eps2_t = (1-tau)*old + tau*epsilon^2.
            parts[8] = (1.0 - self.config.epsilon_tau) * parts[8] + self.config.epsilon_tau * epsilon_target
            parts = list(self._bounded_parts(parts))
        return self._pack(parts)

    def convert_balance(
        self,
        state: QiFieldState,
        *,
        rate: float,
        time_step: float,
    ) -> QiBalanceConversion:
        """Apply the positivity-projected rank-one Yang/Yin conversion law.

        The update transfers density between the position sectors without
        changing their modewise total:
        ``delta = dt * rate * (1 - q) * epsilon``. Projection onto
        ``[-E_I, E_Y]`` is the normal-cone term that keeps both densities
        nonnegative.
        """

        self._validate_state(state)
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(float(rate)) or float(rate) < 0.0:
            raise QiFieldError("conversion rate must be a finite nonnegative real number")
        if isinstance(time_step, bool) or not isinstance(time_step, (int, float)) or not math.isfinite(float(time_step)) or float(time_step) <= 0.0:
            raise QiFieldError("conversion time_step must be a finite positive real number")
        parts = [component.clone() for component in self._parts(state)]
        yang_energy = parts[0].square() + parts[1].square()
        yin_energy = parts[2].square() + parts[3].square()
        density = yang_energy + yin_energy
        imbalance = yang_energy - self.config.phi * yin_energy
        density2 = density.square()
        q = density2 / (
            density2 + self.config.phi**-2 + imbalance.square()
        ).clamp_min(torch.finfo(state.field.dtype).tiny)
        unconstrained = float(time_step) * float(rate) * (1.0 - q) * imbalance
        equilibrium_transfer = imbalance / (1.0 + self.config.phi)
        transfer = torch.sign(unconstrained) * torch.minimum(
            unconstrained.abs(),
            equilibrium_transfer.abs(),
        )
        tiny = torch.finfo(state.field.dtype).tiny
        amplitude2 = self.config.physics.max_mode_amplitude**2

        def phase_energy_capacity(
            real: Tensor,
            imag: Tensor,
            own_energy: Tensor,
            fallback_real: Tensor,
            fallback_imag: Tensor,
            fallback_energy: Tensor,
        ) -> Tensor:
            has_own_phase = own_energy > tiny
            source_real = torch.where(has_own_phase, real, fallback_real)
            source_imag = torch.where(has_own_phase, imag, fallback_imag)
            source_energy = torch.where(has_own_phase, own_energy, fallback_energy)
            peak2 = torch.maximum(source_real.square(), source_imag.square())
            directional_capacity = (
                amplitude2 * source_energy / peak2.clamp_min(tiny)
            )
            return torch.where(
                source_energy > tiny,
                directional_capacity,
                torch.full_like(source_energy, amplitude2),
            )

        yang_capacity = phase_energy_capacity(
            parts[0], parts[1], yang_energy, parts[2], parts[3], yin_energy
        )
        yin_capacity = phase_energy_capacity(
            parts[2], parts[3], yin_energy, parts[0], parts[1], yang_energy
        )
        lower = torch.maximum(-yin_energy, yang_energy - yang_capacity)
        upper = torch.minimum(yang_energy, yin_capacity - yin_energy)
        transfer = torch.minimum(torch.maximum(transfer, lower), upper)
        next_yang = torch.clamp(yang_energy - transfer, min=0.0)
        next_yin = torch.clamp(yin_energy + transfer, min=0.0)
        tiny = torch.finfo(state.field.dtype).tiny

        def rescale(
            real: Tensor,
            imag: Tensor,
            old_energy: Tensor,
            next_energy: Tensor,
            fallback_real: Tensor,
            fallback_imag: Tensor,
            fallback_energy: Tensor,
        ) -> tuple[Tensor, Tensor]:
            own_factor = torch.sqrt(next_energy / old_energy.clamp_min(tiny))
            fallback_factor = torch.sqrt(next_energy / fallback_energy.clamp_min(tiny))
            has_own_phase = old_energy > tiny
            return (
                torch.where(has_own_phase, real * own_factor, fallback_real * fallback_factor),
                torch.where(has_own_phase, imag * own_factor, fallback_imag * fallback_factor),
            )

        old_yang_real, old_yang_imag = parts[0], parts[1]
        old_yin_real, old_yin_imag = parts[2], parts[3]
        parts[0], parts[1] = rescale(
            old_yang_real, old_yang_imag, yang_energy, next_yang, old_yin_real, old_yin_imag, yin_energy
        )
        parts[2], parts[3] = rescale(
            old_yin_real, old_yin_imag, yin_energy, next_yin, old_yang_real, old_yang_imag, yang_energy
        )
        next_imbalance = next_yang - self.config.phi * next_yin
        parts[8] = torch.clamp(
            (1.0 - self.config.epsilon_tau) * parts[8]
            + self.config.epsilon_tau * next_imbalance.square(),
            min=0.0,
            max=self.config.epsilon_clip,
        )
        result = self._pack(parts)
        result_parts = self._parts(result)
        density_after_mode = (
            result_parts[0].square()
            + result_parts[1].square()
            + result_parts[2].square()
            + result_parts[3].square()
        )
        next_imbalance_actual = (
            result_parts[0].square()
            + result_parts[1].square()
            - self.config.phi * (result_parts[2].square() + result_parts[3].square())
        )
        batch_dims = (0, 1)
        return QiBalanceConversion(
            state=result,
            density_before=density.sum(dim=batch_dims),
            density_after=density_after_mode.sum(dim=batch_dims),
            imbalance_l1_before=imbalance.abs().sum(dim=batch_dims),
            imbalance_l1_after=next_imbalance_actual.abs().sum(dim=batch_dims),
            transferred_density=transfer.abs().sum(dim=batch_dims),
            clipped_modes=int(torch.count_nonzero(unconstrained != transfer).item()),
        )

    def _read(self, state: QiFieldState) -> QiFieldReadout:
        self._validate_state(state)
        metrics = self._metrics_raw(state)
        eps = torch.finfo(state.field.dtype).eps
        available = metrics["available"]
        raw_weight = metrics["rho"] * available.to(dtype=state.field.dtype)
        weight_sum = raw_weight.sum(dim=0)
        weights = raw_weight / torch.clamp_min(weight_sum, eps)
        weighted_gate = (weights * metrics["read_gate"]).sum(dim=0)
        pass_gate = weighted_gate >= self.config.read_threshold
        contribution_weights = torch.where(
            pass_gate.unsqueeze(0),
            weights,
            torch.zeros_like(weights),
        )

        # Aggregate demodulated coefficients in common symbol coordinates,
        # then reconstruct the returned wave through the fixed scale-zero
        # codebook. This keeps the readout boundary representation stable
        # despite each bank's distinct prime/chirp codebook.
        shared_re = (
            contribution_weights.unsqueeze(1) * metrics["demod_re"]
        ).sum(dim=0)
        shared_im = (
            contribution_weights.unsqueeze(1) * metrics["demod_im"]
        ).sum(dim=0)
        code0 = self.codebook(0, device=state.field.device, dtype=state.field.dtype)
        code0_re = code0[:, :, 0]
        code0_im = code0[:, :, 1]
        wave_re = (
            torch.einsum("ab,aw->wb", shared_re, code0_re)
            - torch.einsum("ab,aw->wb", shared_im, code0_im)
        )
        wave_im = (
            torch.einsum("ab,aw->wb", shared_re, code0_im)
            + torch.einsum("ab,aw->wb", shared_im, code0_re)
        )
        wave = torch.stack((wave_re, wave_im), dim=-1).permute(1, 0, 2)
        scores = shared_re.transpose(0, 1)
        flux = torch.sqrt(torch.clamp_min(wave.square().sum(dim=-1).mean(dim=1), 0.0))
        available_read = pass_gate & (flux >= self.config.emission_floor)
        wave = torch.where(available_read[:, None, None], wave, torch.zeros_like(wave))
        scores = torch.where(available_read[:, None], scores, torch.zeros_like(scores))
        if self.config.alphabet_size == 1:
            top_value, second_value = scores[:, 0], torch.zeros_like(scores[:, 0])
        else:
            top_two = torch.topk(scores, k=2, dim=1, largest=True, sorted=True).values
            top_value, second_value = top_two[:, 0], top_two[:, 1]
        margin = top_value - second_value
        certainty = torch.clamp(
            margin / torch.clamp_min(
                torch.abs(top_value),
                self.config.physics.correction_epsilon,
            ),
            min=0.0,
            max=1.0,
        )
        uncertainty = torch.where(available_read, 1.0 - certainty, torch.ones_like(certainty))
        symbols = torch.argmax(scores, dim=1).to(dtype=torch.int64)
        symbols = torch.where(available_read, symbols, torch.full_like(symbols, -1))
        q = (weights * metrics["q"]).sum(dim=0)
        q_max = (weights * metrics["q_max"]).sum(dim=0)
        chi = (weights * metrics["chi"]).sum(dim=0)
        return QiFieldReadout(
            symbols,
            available_read,
            scores,
            wave,
            flux,
            margin,
            uncertainty,
            q,
            q_max,
            chi,
            metrics["consensus"],
            weighted_gate,
            contribution_weights,
        )

    def emit(self, state: QiFieldState) -> QiFieldReadout:
        """Emit a symbol only when the normalized multi-scale read gate passes."""

        return self._read(state)

    def correct_wave(
        self,
        state: QiFieldState,
        target_wave: Tensor,
        *,
        correction_gain: float = 1.0,
    ) -> tuple[QiFieldState, Tensor]:
        """Apply a bounded target-wave mismatch write to scale zero.

        ``correction_gain`` is an additional bounded multiplier over the
        controller's fixed ``config.correction_gain``. A value of one keeps
        the symbol-correction path exactly unchanged.
        """

        self._validate_state(state)
        wave = self._wave_shape(
            target_wave,
            batch_size=state.batch_size,
            mode_count=self.config.wave_mode_count,
        )
        if not wave.dtype.is_floating_point or not bool(torch.isfinite(wave).all().item()):
            raise QiFieldError("target wave must be finite and floating point")
        gain_value = _unit_interval("correction_gain", correction_gain)
        wave = wave.to(device=state.field.device, dtype=state.field.dtype)
        readout = self._read(state)
        error_re = wave[:, :, 0] - readout.wave[:, :, 0]
        error_im = wave[:, :, 1] - readout.wave[:, :, 1]
        metrics = self._metrics_raw(state)
        trust = torch.ones(state.batch_size, device=state.field.device, dtype=state.field.dtype)
        gate = torch.where(~metrics["available"][0], trust, 1.0 - metrics["q"][0])
        gain = self.config.correction_gain * torch.clamp(gate, min=0.0, max=1.0)
        if gain_value != 1.0:
            gain = gain * gain_value
        parts = [component.clone() for component in self._parts(state)]
        delta_re = gain.reshape(1, -1) * error_re.transpose(0, 1)
        delta_im = gain.reshape(1, -1) * error_im.transpose(0, 1)
        self._apply_differential_delta(parts, delta_re, delta_im, scale=0, active_width=self.config.wave_mode_count)
        correction_energy = (error_re.square() + error_im.square()).mean(dim=1) * gain.square()
        return self._bounded_state(parts), correction_energy

    def correct(self, state: QiFieldState, target_symbols: Tensor | Sequence[int]) -> tuple[QiFieldState, Tensor]:
        """Apply a bounded target mismatch write to scale zero."""

        self._validate_state(state)
        ids = self._index_symbols(target_symbols, batch_size=state.batch_size, device=state.field.device)
        codes = self.codebook(0, device=state.field.device, dtype=state.field.dtype).index_select(0, ids)
        return self.correct_wave(state, codes, correction_gain=1.0)

    def consolidate(self, state: QiFieldState, *, return_result: bool = False) -> QiFieldState | QiConsolidationResult:
        """Consolidate by source demodulation and target-code reconstruction.

        Raw D modes are never copied between banks: distinct prime/chirp
        codebooks would make that content decode as an unrelated symbol.
        Instead the source bank is demodulated into shared symbol IDs, its
        strongest fixed symbol is bound into the target bank's codebook, and
        only that bounded target wave is written.
        """

        self._validate_state(state)
        if self.config.scale_count == 1:
            empty_gate = state.field.new_zeros((0, state.batch_size))
            return QiConsolidationResult(state, empty_gate) if return_result else state
        metrics = self._metrics_raw(state)
        parts = [component.clone() for component in self._parts(state)]
        scale_factor = self.config.scale_ratio ** -0.5
        width = self.config.wave_mode_count
        for scale in range(self.config.scale_count - 1):
            gate = metrics["consolidation_gate"][scale]
            source_re = parts[0][scale, :width] - self.config.phi * parts[2][scale, :width]
            source_im = parts[1][scale, :width] - self.config.phi * parts[3][scale, :width]
            source_coeff_re, source_coeff_im, source_rms = self._demodulate_bank(
                source_re,
                source_im,
                scale,
            )
            source_symbol = torch.argmax(source_coeff_re, dim=0)
            source_top_re = source_coeff_re.gather(
                0, source_symbol.unsqueeze(0)
            ).squeeze(0)
            source_top_im = source_coeff_im.gather(
                0, source_symbol.unsqueeze(0)
            ).squeeze(0)
            target_codes = self.codebook(
                scale + 1,
                device=state.field.device,
                dtype=state.field.dtype,
            ).index_select(0, source_symbol)
            target_code_re = target_codes[:, :, 0].transpose(0, 1)
            target_code_im = target_codes[:, :, 1].transpose(0, 1)
            desired_re = (
                source_top_re.unsqueeze(0) * target_code_re
                - source_top_im.unsqueeze(0) * target_code_im
            ) * (source_rms.unsqueeze(0) * scale_factor)
            desired_im = (
                source_top_re.unsqueeze(0) * target_code_im
                + source_top_im.unsqueeze(0) * target_code_re
            ) * (source_rms.unsqueeze(0) * scale_factor)
            target_re = parts[0][scale + 1, :width] - self.config.phi * parts[2][scale + 1, :width]
            target_im = parts[1][scale + 1, :width] - self.config.phi * parts[3][scale + 1, :width]
            gain = gate.reshape(1, -1)
            delta_re = gain * (desired_re - target_re)
            delta_im = gain * (desired_im - target_im)
            self._apply_differential_delta(
                parts,
                delta_re,
                delta_im,
                scale=scale + 1,
                active_width=width,
            )
            target_v_re = parts[4][scale + 1, :width] - self.config.phi * parts[6][scale + 1, :width]
            target_v_im = parts[5][scale + 1, :width] - self.config.phi * parts[7][scale + 1, :width]
            self._apply_differential_delta(
                parts,
                -gain * target_v_re,
                -gain * target_v_im,
                scale=scale + 1,
                active_width=width,
                velocity=True,
            )
            parts[8][scale + 1] = parts[8][scale + 1] + gain * (
                parts[8][scale] - parts[8][scale + 1]
            )
        result = self._bounded_state(parts)
        if return_result:
            return QiConsolidationResult(result, metrics["consolidation_gate"])
        return result

    def cycle(self, state: QiFieldState, current_symbols: Tensor | Sequence[int] | None = None, *, current_wave: Tensor | None = None, target_symbols: Tensor | Sequence[int] | None = None, learn: bool = True) -> QiFieldCycle:
        """Run sense, evolve, emit, optional correction, and consolidation."""

        if current_symbols is not None and current_wave is not None:
            raise QiFieldError("provide current_symbols or current_wave, not both")
        if current_wave is not None:
            sensed = self.sense_wave(state, current_wave)
        elif current_symbols is not None:
            sensed = self.sense_symbols(state, current_symbols)
        else:
            raise QiFieldError("cycle requires current_symbols or current_wave")
        settled = self.evolve(sensed)
        emission = self.emit(settled)
        correction_energy = torch.zeros(state.batch_size, device=state.field.device, dtype=state.field.dtype)
        corrected = settled
        if target_symbols is not None and learn:
            corrected, correction_energy = self.correct(settled, target_symbols)
        consolidated = self.consolidate(corrected)
        return QiFieldCycle(consolidated, emission, correction_energy)

    def reset(self, state: QiFieldState, *, preserve_memory: bool = False) -> QiFieldState:
        """Reset all state or clear transient scale zero while retaining slow positions."""

        self._validate_state(state)
        if not preserve_memory:
            return self.initial_state(state.batch_size, device=state.field.device, dtype=state.field.dtype)
        parts = [component.clone() for component in self._parts(state)]
        # Scale zero is transient: clear all positions, velocities, and EMA.
        for offset in range(9):
            parts[offset][0].zero_()
        # Every bank's velocity is transient; slower positional condensates and
        # their epsilon2 EMA remain in the same sole adaptive tensor.
        for offset in (4, 5, 6, 7):
            parts[offset].zero_()
        return self._bounded_state(parts)

    @staticmethod
    def _atomic_bytes_save(payload: bytes, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        )
        temporary = Path(handle.name)
        try:
            with handle:
                handle.write(payload)
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def dump_state_bytes(self, state: QiFieldState) -> bytes:
        """Serialize one exact v2 state to a bounded, detached byte artifact."""

        self._validate_state(state)
        payload = {
            "schema": QI_FIELD_STATE_SCHEMA,
            "layout_id": QI_FIELD_LAYOUT_ID,
            "operator_profile_id": QI_FIELD_OPERATOR_PROFILE_ID,
            "config_schema": QI_FIELD_CONFIG_SCHEMA,
            "config": self.config.to_dict(),
            "config_fingerprint": self.config_fingerprint,
            "codebook_profile_id": QI_CODEBOOK_PROFILE_ID,
            "codebook_descriptors": self.codebook_descriptors,
            "codebook_fingerprint": self.codebook_fingerprint,
            "field": state.field.detach().cpu(),
        }
        stream = io.BytesIO()
        try:
            torch.save(payload, stream)
        except Exception as exc:
            raise QiFieldError(
                f"Qi field-state artifact cannot be serialized: {type(exc).__name__}: {exc}"
            ) from exc
        serialized = stream.getvalue()
        if not serialized:
            raise QiFieldError("Qi field-state payload must be nonempty")
        if len(serialized) > _MAX_QI_FIELD_STATE_BYTES:
            raise QiFieldError(
                f"Qi field-state payload exceeds the {_MAX_QI_FIELD_STATE_BYTES}-byte limit"
            )
        return serialized

    def _decode_state_payload(
        self,
        payload: Any,
        *,
        target_device: torch.device,
        dtype: torch.dtype | None,
    ) -> QiFieldState:
        if not isinstance(payload, dict) or payload.get("schema") != QI_FIELD_STATE_SCHEMA:
            if isinstance(payload, dict) and payload.get("schema") == QI_OLD_FIELD_STATE_SCHEMA:
                raise QiFieldError("old v1 field-state identity is rejected; no implicit conversion is permitted")
            raise QiFieldError("Qi field-state schema mismatch")
        if payload.get("layout_id") != QI_FIELD_LAYOUT_ID or payload.get("operator_profile_id") != QI_FIELD_OPERATOR_PROFILE_ID:
            raise QiFieldError("Qi field-state native operator identity mismatch")
        if payload.get("config_schema") != QI_FIELD_CONFIG_SCHEMA:
            raise QiFieldError("Qi field-state configuration schema mismatch")
        if payload.get("codebook_profile_id") != QI_CODEBOOK_PROFILE_ID:
            raise QiFieldError("Qi field-state codebook profile mismatch")
        loaded_config = QiFieldConfig.from_dict(payload.get("config", {}))
        if loaded_config != self.config or payload.get("config_fingerprint") != self.config_fingerprint:
            raise QiFieldError("Qi field state belongs to a different fixed configuration")
        if payload.get("codebook_descriptors") != self.codebook_descriptors or payload.get("codebook_fingerprint") != self.codebook_fingerprint:
            raise QiFieldError("Qi field state belongs to a different fixed codebook identity")
        field = payload.get("field")
        if not torch.is_tensor(field):
            raise QiFieldError("Qi field-state artifact is missing its sole adaptive tensor")
        target_dtype = dtype or field.dtype
        _floating_dtype(target_dtype)
        try:
            owned_field = field.detach().to(device=target_device, dtype=target_dtype).clone()
            result = QiFieldState(owned_field)
            result.validate(self.config, device=target_device, dtype=target_dtype)
        except QiFieldError:
            raise
        except Exception as exc:
            raise QiFieldError(
                f"Qi field-state tensor cannot be restored: {type(exc).__name__}: {exc}"
            ) from exc
        return result

    def load_state_bytes(
        self,
        payload: bytes | bytearray | memoryview,
        *,
        device: torch.device | str | None = "cpu",
        dtype: torch.dtype | None = None,
    ) -> QiFieldState:
        """Load and validate one exact v2 state from bounded bytes."""

        serialized = _coerce_state_bytes(payload)
        try:
            target_device = torch.device("cpu" if device is None else device)
        except Exception as exc:
            raise QiFieldError(f"invalid Qi field-state device: {exc}") from exc
        try:
            loaded = torch.load(
                io.BytesIO(serialized),
                map_location=target_device,
                weights_only=True,
            )
        except Exception as exc:
            raise QiFieldError(
                f"Qi field-state artifact cannot be loaded: {type(exc).__name__}: {exc}"
            ) from exc
        return self._decode_state_payload(
            loaded,
            target_device=target_device,
            dtype=dtype,
        )

    def save(self, path: Path | str | QiFieldState, state: QiFieldState | Path | str | None = None) -> str:
        """Save one exact v2 state and its fixed codebook/config identity."""

        if isinstance(path, QiFieldState):
            if state is None:
                raise QiFieldError("save(state, path) requires a path")
            path, state = state, path
        if not isinstance(state, QiFieldState):
            raise QiFieldError("save requires a QiFieldState")
        target = Path(path)
        serialized = self.dump_state_bytes(state)
        self._atomic_bytes_save(serialized, target)
        return hashlib.sha256(serialized).hexdigest()

    def load(self, path: Path | str, *, device: torch.device | str | None = "cpu", dtype: torch.dtype | None = None) -> QiFieldState:
        """Load only an exact v2 state; old or wrong identities are rejected."""

        target = Path(path)
        if not target.is_file():
            raise QiFieldError(f"Qi field-state artifact does not exist: {target}")
        with target.open("rb") as handle:
            serialized = handle.read(_MAX_QI_FIELD_STATE_BYTES + 1)
        return self.load_state_bytes(serialized, device=device, dtype=dtype)


def save_qi_field_state(path: Path | str, controller: QiFieldController, state: QiFieldState) -> str:
    if not isinstance(controller, QiFieldController):
        raise QiFieldError("controller must be a QiFieldController")
    return controller.save(path, state)


def load_qi_field_state(path: Path | str, controller: QiFieldController, *, device: torch.device | str = "cpu", dtype: torch.dtype | None = None) -> QiFieldState:
    if not isinstance(controller, QiFieldController):
        raise QiFieldError("controller must be a QiFieldController")
    return controller.load(path, device=device, dtype=dtype)


__all__ = [
    "QI_CODEBOOK_PROFILE_ID", "QI_FIELD_CONFIG_SCHEMA", "QI_FIELD_LAYOUT_ID",
    "QI_FIELD_OPERATOR_PROFILE_ID", "QI_FIELD_STATE_SCHEMA", "QiBalanceConversion",
    "QiConsolidationResult", "QiFieldConfig", "QiFieldController", "QiFieldCycle", "QiFieldDiagnostics",
    "QiFieldError", "QiFieldPhysicsConfig", "QiFieldReadout", "QiFieldState",
    "QiSenseResult", "CassiQiFieldError", "load_qi_field_state", "save_qi_field_state",
]
