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
import struct
import sys
import tempfile
import warnings
from dataclasses import asdict, dataclass, field as dataclass_field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor

from cassi_qi_profile import (
    CanonicalCodecError,
    PROFILE_MISMATCH,
    PROFILE_SCHEMA,
    PROJECTION_REGISTRY,
    QiFlowProfile,
    _projection_value,
    canonical_hash,
    canonical_json_bytes,
    canonical_json_loads,
    finite_float,
    validate_contract_root,
    validate_profile,
)

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



# The legacy v2 codec above remains isolated for historical callers.  New
# profile-governed state is deliberately a separate, v3-only surface: it never
# probes a default profile, never converts a legacy payload, and never places
# controller caches or derived diagnostics into its raw state.
QI_FLOW_STATE_V3_SCHEMA = "cassi.qi-flow-state.v3"
QI_FLOW_STATE_V3_TENSOR_DOMAIN = "cassi.qi-flow-state-tensor.v3"
_QI_FLOW_STATE_V3_MAGIC = b"CASSI-QI-FLOW-STATE-V3\x00"
_QI_FLOW_STATE_V3_ENDIANNESS = "little"
_QI_FLOW_STATE_V3_MAX_HEADER_BYTES = 64 * 1024
_QI_FLOW_STATE_V3_HEADER_FIELDS = frozenset(
    {
        "schema",
        "layout_id",
        "profile_sha256",
        "contract_root_sha256",
        "state_contract_sha256",
        "execution_schedule_sha256",
        "topology_sha256",
        "source_identity_sha256",
        "backend",
        "dtype",
        "shape",
        "raw_byte_count",
        "source_raw_sha256",
        "state_sha256",
        "self_sha256",
    }
)


@dataclass(frozen=True)
class _QiFlowV3StateContract:
    """Validated fixed interpretation data for one v3 raw state."""

    layout_id: str
    profile_sha256: str
    contract_root_sha256: str
    state_contract_sha256: str
    execution_schedule_sha256: str
    topology_sha256: str
    source_identity_sha256: str
    shape_prefix: tuple[int, int]
    mode_count: int
    fixed_batch_lanes: int | None
    active_shapes: tuple[tuple[int, int], ...]
    active_site_counts: tuple[int, ...]
    component_abs_max: tuple[float, ...]
    complex_amplitude_max: tuple[float, ...]
    density_max: float
    epsilon2_ema_max: float
    inactive_tail_value: float
    dtype: torch.dtype
    dtype_name: str
    backend: str
    max_batch_lanes: int
    max_raw_bytes: int

def _v3_profile_mismatch(message: str) -> None:
    """Raise the profile layer's mismatch signal without accepting a fallback."""

    if isinstance(PROFILE_MISMATCH, type) and issubclass(PROFILE_MISMATCH, BaseException):
        raise PROFILE_MISMATCH(message)
    if isinstance(PROFILE_MISMATCH, BaseException):
        raise PROFILE_MISMATCH
    raise QiFieldError(f"{PROFILE_MISMATCH}: {message}")


def _v3_is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _v3_digest(value: Any, name: str) -> str:
    if not _v3_is_sha256(value):
        _v3_profile_mismatch(f"{name} must be a lowercase 64-hex SHA-256 digest")
    return value


def _v3_positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _v3_profile_mismatch(f"{name} must be a positive integer")
    return value

def _v3_tagged_positive_scalar(value: Any, name: str) -> float:
    if not isinstance(value, str) or not value.startswith(("f32:", "f64:")):
        _v3_profile_mismatch(f"{name} must be a tagged f32/f64 finite scalar")
    try:
        result = finite_float(value, name=name)
    except Exception as exc:
        _v3_profile_mismatch(f"{name} is invalid: {type(exc).__name__}: {exc}")
    if result <= 0.0:
        _v3_profile_mismatch(f"{name} must be strictly positive")
    return result


def _v3_tagged_positive_vector(value: Any, name: str, count: int) -> tuple[float, ...]:
    if not isinstance(value, (tuple, list)) or len(value) != count:
        _v3_profile_mismatch(f"{name} must contain exactly {count} tagged finite scalars")
    return tuple(
        _v3_tagged_positive_scalar(item, f"{name}[{index}]")
        for index, item in enumerate(value)
    )


def _v3_tagged_positive_zero(value: Any, name: str) -> float:
    if not isinstance(value, str) or not value.startswith(("f32:", "f64:")):
        _v3_profile_mismatch(f"{name} must be a tagged +0 scalar")
    try:
        result = finite_float(value, name=name)
    except Exception as exc:
        _v3_profile_mismatch(f"{name} is invalid: {type(exc).__name__}: {exc}")
    if result != 0.0 or math.copysign(1.0, result) < 0.0:
        _v3_profile_mismatch(f"{name} must be tagged positive zero")
    return result


def _v3_active_shapes(
    value: Any,
    *,
    name: str,
    scale_count: int,
    mode_count: int,
) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, (tuple, list)) or len(value) != scale_count:
        _v3_profile_mismatch(f"{name} must contain one [height,width] shape for every scale")
    shapes: list[tuple[int, int]] = []
    for scale, shape in enumerate(value):
        if not isinstance(shape, (tuple, list)) or len(shape) != 2:
            _v3_profile_mismatch(f"{name}[{scale}] must be a [height,width] shape")
        height = _v3_positive_int(shape[0], f"{name}[{scale}][0]")
        width = _v3_positive_int(shape[1], f"{name}[{scale}][1]")
        if height * width > mode_count:
            _v3_profile_mismatch(f"{name}[{scale}] exceeds declared mode storage")
        shapes.append((height, width))
    return tuple(shapes)


def _v3_active_site_counts(
    value: Any,
    *,
    name: str,
    active_shapes: tuple[tuple[int, int], ...],
) -> tuple[int, ...]:
    if not isinstance(value, (tuple, list)) or len(value) != len(active_shapes):
        _v3_profile_mismatch(f"{name} must contain one active-site count for every scale")
    counts = tuple(
        _v3_positive_int(item, f"{name}[{scale}]")
        for scale, item in enumerate(value)
    )
    expected = tuple(height * width for height, width in active_shapes)
    if counts != expected:
        _v3_profile_mismatch(f"{name} must exactly match the declared active shapes")
    return counts


def _v3_state_bounds(value: Any) -> tuple[tuple[float, ...], tuple[float, ...], float, float, float]:
    expected = {
        "component_abs_max",
        "complex_amplitude_max",
        "density_max",
        "epsilon2_ema_max",
        "inactive_tail_value",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        _v3_profile_mismatch("field.state_bounds must contain exactly the declared v3 state bounds")
    component_abs_max = _v3_tagged_positive_vector(
        value["component_abs_max"],
        "field.state_bounds.component_abs_max",
        9,
    )
    complex_amplitude_max = _v3_tagged_positive_vector(
        value["complex_amplitude_max"],
        "field.state_bounds.complex_amplitude_max",
        4,
    )
    density_max = _v3_tagged_positive_scalar(
        value["density_max"],
        "field.state_bounds.density_max",
    )
    epsilon2_ema_max = _v3_tagged_positive_scalar(
        value["epsilon2_ema_max"],
        "field.state_bounds.epsilon2_ema_max",
    )
    inactive_tail_value = _v3_tagged_positive_zero(
        value["inactive_tail_value"],
        "field.state_bounds.inactive_tail_value",
    )
    return (
        component_abs_max,
        complex_amplitude_max,
        density_max,
        epsilon2_ema_max,
        inactive_tail_value,
    )


def _v3_require_little_endian() -> None:
    if sys.byteorder != _QI_FLOW_STATE_V3_ENDIANNESS:
        _v3_profile_mismatch("v3 little-endian raw state is unsupported on this host")


def _v3_raw_values(raw: bytes, dtype_name: str) -> memoryview:
    _v3_require_little_endian()
    try:
        return memoryview(raw).cast("f" if dtype_name == "float32" else "d")
    except (TypeError, ValueError) as exc:
        _v3_profile_mismatch(f"v3 raw field cannot be decoded: {type(exc).__name__}: {exc}")


def _v3_scalar_is_positive_zero(value: float) -> bool:
    return value == 0.0 and math.copysign(1.0, value) > 0.0


def _v3_root_self_sha256(root: Any) -> Any:
    if isinstance(root, Mapping):
        return root.get("self_sha256")
    return getattr(root, "self_sha256", getattr(root, "sha256", None))


def _v3_state_semantic_sha256(profile: QiFlowProfile) -> str:
    """Read the registered state semantic parent without inventing a fallback."""

    values = getattr(profile, "semantic_subhashes", None)
    candidate: Any = None
    if isinstance(values, Mapping):
        candidate = values.get("state_contract_sha256")
        if isinstance(candidate, Mapping):
            candidate = candidate.get("sha256")
    elif isinstance(values, (tuple, list)):
        for item in values:
            if isinstance(item, Mapping) and item.get("name") == "state_contract_sha256":
                candidate = item.get("sha256")
                break
            if isinstance(item, tuple) and len(item) == 2 and item[0] == "state_contract_sha256":
                candidate = item[1]
                break
            if getattr(item, "name", None) == "state_contract_sha256":
                candidate = getattr(item, "sha256", None)
                break
    return _v3_digest(candidate, "semantic_subhashes.state_contract_sha256")


def _v3_payload_semantic_sha256(payload: Mapping[str, Any], name: str) -> str:
    rows = payload.get("semantic_subhashes")
    if not isinstance(rows, (tuple, list)):
        _v3_profile_mismatch("profile payload semantic_subhashes must be an ordered list")
    matches = [
        row.get("sha256")
        for row in rows
        if isinstance(row, Mapping) and row.get("name") == name
    ]
    if len(matches) != 1:
        _v3_profile_mismatch(f"profile payload must contain exactly one {name} semantic digest")
    return _v3_digest(matches[0], f"profile.payload.semantic_subhashes.{name}")


def _v3_recomputed_state_contract_sha256(payload: Mapping[str, Any]) -> str:
    projections = PROJECTION_REGISTRY.get("projections")
    if not isinstance(projections, (tuple, list)):
        _v3_profile_mismatch("projection registry must publish an ordered projection list")
    rows = [
        row
        for row in projections
        if isinstance(row, Mapping) and row.get("name") == "state_contract_sha256"
    ]
    if len(rows) != 1:
        _v3_profile_mismatch("projection registry must publish exactly one state contract")
    pointers = rows[0].get("pointers")
    if not isinstance(pointers, (tuple, list)) or not all(
        isinstance(pointer, str) for pointer in pointers
    ):
        _v3_profile_mismatch("state-contract projection pointers must be an ordered string list")
    try:
        projection = _projection_value(payload, pointers)
        digest = canonical_hash(
            {"projection": "state_contract_sha256", **projection},
            "cassi.qi-flow.projection.state_contract_sha256",
        )
    except Exception as exc:
        _v3_profile_mismatch(
            f"state-contract projection cannot be reconstructed: {type(exc).__name__}: {exc}"
        )
    return _v3_digest(digest, "recomputed state_contract_sha256")


def _v3_dtype(value: Any, name: str) -> tuple[torch.dtype, str]:
    if value == "float32":
        return torch.float32, "float32"
    if value == "float64":
        return torch.float64, "float64"
    _v3_profile_mismatch(f"{name} must declare float32 or float64")
    raise AssertionError("unreachable")


def _v3_profile_contract(profile: QiFlowProfile) -> _QiFlowV3StateContract:
    """Authenticate direct field/spatial profile data before interpreting a state."""

    if not isinstance(profile, QiFlowProfile):
        _v3_profile_mismatch("v3 state requires an explicit QiFlowProfile")
    payload = getattr(profile, "payload", None)
    if not isinstance(payload, Mapping):
        _v3_profile_mismatch("profile payload must be an immutable mapping")
    profile_payload = dict(payload)
    try:
        validated_profile = validate_profile(profile)
        if canonical_json_bytes(profile_payload) != canonical_json_bytes(
            dict(validated_profile.payload)
        ):
            _v3_profile_mismatch("profile payload differs from its verified materialization")
    except Exception as exc:
        _v3_profile_mismatch(
            f"profile payload validation failed: {type(exc).__name__}: {exc}"
        )

    profile_sha256 = _v3_digest(
        getattr(profile, "profile_sha256", None),
        "profile.profile_sha256",
    )
    if _v3_digest(
        profile_payload.get("profile_sha256"),
        "profile.payload.profile_sha256",
    ) != profile_sha256:
        _v3_profile_mismatch("profile object digest disagrees with its payload")
    profile_hash_payload = dict(profile_payload)
    profile_hash_payload.pop("profile_sha256", None)
    try:
        expected_profile_sha256 = canonical_hash(profile_hash_payload, PROFILE_SCHEMA)
    except Exception as exc:
        _v3_profile_mismatch(
            f"profile identity cannot be reconstructed: {type(exc).__name__}: {exc}"
        )
    if profile_sha256 != expected_profile_sha256:
        _v3_profile_mismatch("profile digest does not match the supplied payload")

    root = getattr(profile, "contract_root", None)
    if root is None:
        _v3_profile_mismatch("profile is missing its contract root")
    try:
        validated_root = validate_contract_root(root)
    except Exception as exc:
        _v3_profile_mismatch(
            f"contract root validation failed: {type(exc).__name__}: {exc}"
        )
    contract_root_sha256 = _v3_digest(
        getattr(profile, "contract_root_sha256", None),
        "profile.contract_root_sha256",
    )
    if (
        _v3_digest(
            profile_payload.get("contract_root_sha256"),
            "profile.payload.contract_root_sha256",
        )
        != contract_root_sha256
    ):
        _v3_profile_mismatch("profile payload root digest disagrees with its contract root")
    root_self_sha256 = _v3_digest(
        _v3_root_self_sha256(validated_root),
        "contract_root.self_sha256",
    )
    if root_self_sha256 != contract_root_sha256:
        _v3_profile_mismatch("profile contract-root digest does not match the validated root")

    state_contract_sha256 = _v3_payload_semantic_sha256(
        profile_payload,
        "state_contract_sha256",
    )
    if _v3_state_semantic_sha256(profile) != state_contract_sha256:
        _v3_profile_mismatch("profile state-contract digest disagrees with the semantic registry")
    if (
        _v3_digest(
            getattr(profile, "state_contract_sha256", None),
            "profile.state_contract_sha256",
        )
        != state_contract_sha256
    ):
        _v3_profile_mismatch("profile state-contract property disagrees with its payload")
    if _v3_recomputed_state_contract_sha256(profile_payload) != state_contract_sha256:
        _v3_profile_mismatch(
            "profile state-contract digest does not match the authenticated projection"
        )

    try:
        execution_payload = profile_payload["execution"]
        if not isinstance(execution_payload, Mapping):
            _v3_profile_mismatch("profile.execution must be a mapping")
        execution_schedule_sha256 = _v3_digest(
            getattr(profile, "execution_schedule_sha256", None),
            "profile.execution_schedule_sha256",
        )
        schedule_payload = execution_payload["schedule"]
        if not isinstance(schedule_payload, Mapping):
            _v3_profile_mismatch("profile.execution.schedule must be a mapping")
        schedule_body = dict(schedule_payload)
        schedule_self_sha256 = _v3_digest(
            schedule_body.pop("self_sha256", None),
            "profile.execution.schedule.self_sha256",
        )
        expected_execution_schedule_sha256 = canonical_hash(
            schedule_body,
            schedule_payload["schema"],
        )
        if (
            execution_schedule_sha256 != schedule_self_sha256
            or schedule_self_sha256 != expected_execution_schedule_sha256
        ):
            _v3_profile_mismatch(
                "profile execution-schedule digest does not match the authenticated payload"
            )

        scale_geometry_payload = profile_payload["scale_geometry"]
        if not isinstance(scale_geometry_payload, Mapping):
            _v3_profile_mismatch("profile.scale_geometry must be a mapping")
        spatial_payload = profile_payload["spatial"]
        if not isinstance(spatial_payload, Mapping):
            _v3_profile_mismatch("profile.spatial must be a mapping")
        topology_sha256 = _v3_digest(
            getattr(profile, "topology_sha256", None),
            "profile.topology_sha256",
        )
        expected_topology_sha256 = canonical_hash(
            {
                "spatial": spatial_payload,
                "scale_geometry": scale_geometry_payload["state_operator"],
            },
            "cassi.qi-flow.topology",
        )
        if topology_sha256 != expected_topology_sha256:
            _v3_profile_mismatch(
                "profile topology digest does not match the authenticated payload"
            )

        source_identity = execution_payload["source_identity"]
        if not isinstance(source_identity, Mapping):
            _v3_profile_mismatch("profile.execution.source_identity must be a mapping")
        source_body = dict(source_identity)
        source_self_sha256 = _v3_digest(
            source_body.pop("self_sha256", None),
            "profile.execution.source_identity.self_sha256",
        )
        if source_self_sha256 != canonical_hash(
            source_body,
            source_body["schema"],
        ):
            _v3_profile_mismatch("profile source identity is not self-consistent")
        source_identity_sha256 = _v3_digest(
            getattr(profile, "source_identity_sha256", None),
            "profile.source_identity_sha256",
        )
        if (
            _v3_digest(
                execution_payload["source_identity_sha256"],
                "profile.execution.source_identity_sha256",
            )
            != source_identity_sha256
            or source_identity_sha256 != source_self_sha256
        ):
            _v3_profile_mismatch(
                "profile source-identity digest does not match the authenticated payload"
            )
    except KeyError as exc:
        _v3_profile_mismatch(f"profile is missing {exc.args[0]!r}")
    except CanonicalCodecError as exc:
        _v3_profile_mismatch(f"profile identity cannot be reconstructed: {exc}")
    except Exception as exc:
        _v3_profile_mismatch(
            f"profile identity cannot be reconstructed: {type(exc).__name__}: {exc}"
        )

    field_payload = profile_payload.get("field")
    backend_payload = profile_payload.get("backend_contract")
    if not isinstance(field_payload, Mapping):
        _v3_profile_mismatch("profile.field must be a mapping")
    if not isinstance(backend_payload, Mapping):
        _v3_profile_mismatch("profile.backend_contract must be a mapping")
    try:
        scale_count = _v3_positive_int(field_payload["scale_count"], "field.scale_count")
        mode_count = _v3_positive_int(field_payload["mode_count"], "field.mode_count")
        component_count = _v3_positive_int(
            field_payload["component_count"],
            "field.component_count",
        )
        layout_id = field_payload["layout_id"]
        dtype, dtype_name = _v3_dtype(field_payload["dtype"], "field.dtype")
        byte_order = field_payload["byte_order"]
        backend = backend_payload["device"]
        max_batch_lanes = _v3_positive_int(field_payload["batch_limit"], "field.batch_limit")
        raw_limit = _v3_positive_int(
            field_payload["state_byte_limit"],
            "field.state_byte_limit",
        )
        active_shapes = _v3_active_shapes(
            field_payload["active_shapes"],
            name="field.active_shapes",
            scale_count=scale_count,
            mode_count=mode_count,
        )
        active_site_counts = _v3_active_site_counts(
            field_payload["active_site_counts"],
            name="field.active_site_counts",
            active_shapes=active_shapes,
        )
        bounds_value = field_payload["state_bounds"]
    except KeyError as exc:
        _v3_profile_mismatch(f"profile.field is missing {exc.args[0]!r}")

    if component_count != 9:
        _v3_profile_mismatch("v3 field layout must declare exactly nine packed components")
    if not isinstance(layout_id, str) or not layout_id:
        _v3_profile_mismatch("field.layout_id must be a nonempty string")
    if byte_order != _QI_FLOW_STATE_V3_ENDIANNESS:
        _v3_profile_mismatch("field.byte_order must declare fixed little-endian v3 storage")
    if not isinstance(backend, str) or not backend:
        _v3_profile_mismatch("backend_contract.device must be a nonempty backend string")
    try:
        declared_backend = torch.device(backend)
    except Exception as exc:
        _v3_profile_mismatch(
            f"backend_contract.device is invalid: {type(exc).__name__}: {exc}"
        )
    if declared_backend.type != backend:
        _v3_profile_mismatch(
            "backend_contract.device must name a backend type without an implicit device"
        )
    if field_payload.get("component_order") != list(QI_COMPONENT_ORDER):
        _v3_profile_mismatch("field.component_order must match the packed v3 component order")

    spatial_active_shapes = _v3_active_shapes(
        spatial_payload.get("active_shapes"),
        name="profile.spatial.active_shapes",
        scale_count=scale_count,
        mode_count=mode_count,
    )
    if active_shapes != spatial_active_shapes:
        _v3_profile_mismatch("field active shapes disagree with profile.spatial")
    if spatial_payload.get("gather_scatter") != "active-prefix-zero-tail.v1":
        _v3_profile_mismatch("profile.spatial must declare active-prefix zero-tail storage")
    per_scale = spatial_payload.get("per_scale")
    if not isinstance(per_scale, (tuple, list)) or len(per_scale) != scale_count:
        _v3_profile_mismatch("profile.spatial.per_scale must contain every active sheet")
    expected_tail_counts = tuple(mode_count - count for count in active_site_counts)
    for scale, (shape, active_count, sheet) in enumerate(
        zip(
            active_shapes,
            active_site_counts,
            per_scale,
            strict=True,
        )
    ):
        if not isinstance(sheet, Mapping):
            _v3_profile_mismatch(f"profile.spatial.per_scale[{scale}] must be a mapping")
        if (
            sheet.get("scale_index") != scale
            or sheet.get("active_shape") != list(shape)
            or sheet.get("active_site_count") != active_count
            or sheet.get("storage_mode_count") != mode_count
        ):
            _v3_profile_mismatch(
                f"profile.spatial.per_scale[{scale}] disagrees with direct field storage"
            )

    state_operator = scale_geometry_payload.get("state_operator")
    capacity = scale_geometry_payload.get("capacity")
    if not isinstance(state_operator, Mapping) or not isinstance(capacity, Mapping):
        _v3_profile_mismatch(
            "profile.scale_geometry must publish state_operator and capacity mappings"
        )
    if (
        state_operator.get("active_ranks") != list(active_site_counts)
        or state_operator.get("nullspace_dimensions") != list(expected_tail_counts)
    ):
        _v3_profile_mismatch("profile state operator disagrees with direct field capacity")
    bytes_per_value = 4 if dtype is torch.float32 else 8
    active_state_bytes = (
        sum(active_site_counts)
        * component_count
        * max_batch_lanes
        * bytes_per_value
    )
    padded_state_bytes = (
        sum(expected_tail_counts)
        * component_count
        * max_batch_lanes
        * bytes_per_value
    )
    if (
        capacity.get("active_sites") != list(active_site_counts)
        or capacity.get("padded_sites") != list(expected_tail_counts)
        or capacity.get("active_state_bytes_at_batch_limit") != active_state_bytes
        or capacity.get("padded_state_bytes_at_batch_limit") != padded_state_bytes
    ):
        _v3_profile_mismatch("profile capacity disagrees with direct field storage")
    (
        component_abs_max,
        complex_amplitude_max,
        density_max,
        epsilon2_ema_max,
        inactive_tail_value,
    ) = _v3_state_bounds(bounds_value)

    full_state_bytes = (
        scale_count * component_count * mode_count * max_batch_lanes * bytes_per_value
    )
    maximum_raw_bytes = (
        _MAX_QI_FIELD_STATE_BYTES
        - len(_QI_FLOW_STATE_V3_MAGIC)
        - 8
        - _QI_FLOW_STATE_V3_MAX_HEADER_BYTES
    )
    if raw_limit > maximum_raw_bytes:
        _v3_profile_mismatch("field.state_byte_limit exceeds the v3 byte budget")
    if full_state_bytes > raw_limit:
        _v3_profile_mismatch(
            "field.state_byte_limit cannot hold the declared padded state at batch limit"
        )
    return _QiFlowV3StateContract(
        layout_id=layout_id,
        profile_sha256=profile_sha256,
        contract_root_sha256=contract_root_sha256,
        state_contract_sha256=state_contract_sha256,
        execution_schedule_sha256=execution_schedule_sha256,
        topology_sha256=topology_sha256,
        source_identity_sha256=source_identity_sha256,
        shape_prefix=(scale_count, component_count * mode_count),
        mode_count=mode_count,
        fixed_batch_lanes=None,
        active_shapes=active_shapes,
        active_site_counts=active_site_counts,
        component_abs_max=component_abs_max,
        complex_amplitude_max=complex_amplitude_max,
        density_max=density_max,
        epsilon2_ema_max=epsilon2_ema_max,
        inactive_tail_value=inactive_tail_value,
        dtype=dtype,
        dtype_name=dtype_name,
        backend=backend,
        max_batch_lanes=max_batch_lanes,
        max_raw_bytes=raw_limit,
    )


def _v3_target_device(
    contract: _QiFlowV3StateContract,
    requested: torch.device | str | None,
) -> torch.device:
    try:
        target = torch.device(contract.backend if requested is None else requested)
    except Exception as exc:
        _v3_profile_mismatch(f"requested v3 state device is invalid: {type(exc).__name__}: {exc}")
    if target.type != contract.backend:
        _v3_profile_mismatch(
            f"requested backend {target.type!r} does not match declared backend {contract.backend!r}"
        )
    return target


def _v3_raw_byte_count(
    contract: _QiFlowV3StateContract,
    batch_lanes: int,
) -> int:
    lanes = _v3_positive_int(batch_lanes, "batch_lanes")
    if contract.fixed_batch_lanes is not None and lanes != contract.fixed_batch_lanes:
        _v3_profile_mismatch(
            f"v3 field has {lanes} B lanes, not the declared {contract.fixed_batch_lanes}-lane shape"
        )
    if lanes > contract.max_batch_lanes:
        _v3_profile_mismatch(
            f"v3 field has {lanes} B lanes, above the declared {contract.max_batch_lanes}-lane limit"
        )
    count = contract.shape_prefix[0] * contract.shape_prefix[1] * lanes
    bytes_per_value = 4 if contract.dtype is torch.float32 else 8
    byte_count = count * bytes_per_value
    if byte_count < 1 or byte_count > contract.max_raw_bytes:
        _v3_profile_mismatch(
            f"v3 raw state requires {byte_count} bytes, outside the declared {contract.max_raw_bytes}-byte budget"
        )
    return byte_count


def _v3_validate_tensor_values(
    field: Tensor,
    contract: _QiFlowV3StateContract,
) -> None:
    try:
        packed = field.reshape(
            contract.shape_prefix[0],
            9,
            contract.mode_count,
            int(field.shape[2]),
        )
        finite = bool(torch.isfinite(packed).all().item())
    except Exception as exc:
        _v3_profile_mismatch(
            f"v3 field finiteness cannot be checked: {type(exc).__name__}: {exc}"
        )
    if not finite:
        _v3_profile_mismatch("v3 field contains a non-finite value")

    for scale, active_sites in enumerate(contract.active_site_counts):
        active = packed[scale, :, :active_sites, :]
        for component, cap in enumerate(contract.component_abs_max):
            if bool(torch.any(torch.abs(active[component]) > cap).item()):
                _v3_profile_mismatch(
                    f"v3 field component {component} exceeds its declared bound at scale {scale}"
                )
        epsilon2_ema = active[8]
        if bool(torch.any(epsilon2_ema < 0.0).item()) or bool(
            torch.any(torch.signbit(epsilon2_ema)).item()
        ):
            _v3_profile_mismatch("v3 field epsilon2_ema must be nonnegative")
        if bool(torch.any(epsilon2_ema > contract.epsilon2_ema_max).item()):
            _v3_profile_mismatch("v3 field epsilon2_ema exceeds its declared bound")
        for pair, cap in enumerate(contract.complex_amplitude_max):
            real = active[2 * pair]
            imaginary = active[2 * pair + 1]
            if bool(torch.any(real.square() + imaginary.square() > cap * cap).item()):
                _v3_profile_mismatch(
                    f"v3 field complex component {pair} exceeds its declared amplitude bound at scale {scale}"
                )
        density = active[:8].square().sum(dim=0)
        if bool(torch.any(density > contract.density_max).item()):
            _v3_profile_mismatch(
                f"v3 field density exceeds its declared bound at scale {scale}"
            )
        if active_sites < contract.mode_count:
            tail = packed[scale, :, active_sites:, :]
            if bool(torch.any(tail != contract.inactive_tail_value).item()) or bool(
                torch.any(torch.signbit(tail)).item()
            ):
                _v3_profile_mismatch(
                    f"v3 field inactive tail is not exact positive zero at scale {scale}"
                )


def _v3_validate_tensor(
    field: Any,
    contract: _QiFlowV3StateContract,
    *,
    device: torch.device | None = None,
    check_finite: bool = True,
) -> None:
    if not torch.is_tensor(field):
        _v3_profile_mismatch("v3 state must own its sole field as a torch.Tensor")
    if field.requires_grad or field.grad is not None:
        _v3_profile_mismatch("v3 state cannot carry a gradient tensor or autograd state")
    if field.ndim != 3:
        _v3_profile_mismatch("v3 field must have shape [S,9M,B]")
    if tuple(field.shape[:2]) != contract.shape_prefix:
        _v3_profile_mismatch("v3 field shape does not match the profile layout")
    batch_lanes = int(field.shape[2])
    if batch_lanes < 1:
        _v3_profile_mismatch("v3 field must have at least one B lane")
    if field.dtype is not contract.dtype:
        _v3_profile_mismatch("v3 field dtype does not match the profile layout")
    if field.device.type != contract.backend:
        _v3_profile_mismatch("v3 field backend does not match the profile layout")
    if device is not None and field.device != device:
        _v3_profile_mismatch("v3 field device does not match the requested device")
    if not field.is_contiguous():
        _v3_profile_mismatch("v3 field must be contiguous in [S,9M,B] order")
    _v3_raw_byte_count(contract, batch_lanes)
    if check_finite:
        _v3_validate_tensor_values(field, contract)


def _v3_little_endian_raw_bytes(
    field: Tensor,
    contract: _QiFlowV3StateContract,
) -> bytes:
    _v3_require_little_endian()
    try:
        raw = field.detach().to(device="cpu").numpy().tobytes(order="C")
    except Exception as exc:
        raise QiFieldError(
            f"v3 raw field bytes cannot be materialized: {type(exc).__name__}: {exc}"
        ) from exc
    expected = _v3_raw_byte_count(contract, int(field.shape[2]))
    if len(raw) != expected:
        _v3_profile_mismatch("v3 raw field byte count does not match its declared layout")
    _v3_validate_raw_state(
        raw,
        contract,
        (int(field.shape[0]), int(field.shape[1]), int(field.shape[2])),
    )
    return raw


def _v3_frame(value: bytes) -> bytes:
    return struct.pack(">Q", len(value)) + value


def _v3_tensor_sha256(
    raw: bytes,
    *,
    dtype_name: str,
    shape: tuple[int, int, int],
    state_contract_sha256: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(_v3_frame(QI_FLOW_STATE_V3_TENSOR_DOMAIN.encode("utf-8")))
    digest.update(_v3_frame(state_contract_sha256.encode("ascii")))
    digest.update(_v3_frame(dtype_name.encode("ascii")))
    digest.update(struct.pack(">I", len(shape)))
    for dimension in shape:
        digest.update(struct.pack(">Q", dimension))
    digest.update(struct.pack(">Q", len(raw)))
    digest.update(raw)
    return digest.hexdigest()


def _v3_validate_raw_state(
    raw: bytes,
    contract: _QiFlowV3StateContract,
    shape: tuple[int, int, int],
) -> None:
    """Validate every fixed-LE scalar before any tensor storage is allocated."""

    batch_lanes = _v3_positive_int(shape[2], "v3 raw batch_lanes")
    expected_bytes = _v3_raw_byte_count(contract, batch_lanes)
    if len(raw) != expected_bytes:
        _v3_profile_mismatch("v3 raw field byte count does not match its declared layout")
    values = _v3_raw_values(raw, contract.dtype_name)
    expected_values = contract.shape_prefix[0] * 9 * contract.mode_count * batch_lanes
    if len(values) != expected_values:
        _v3_profile_mismatch("v3 raw field scalar count does not match its declared layout")

    plane_stride = contract.mode_count * batch_lanes
    scale_stride = 9 * plane_stride
    for scale, active_sites in enumerate(contract.active_site_counts):
        scale_base = scale * scale_stride
        for mode in range(contract.mode_count):
            mode_base = scale_base + mode * batch_lanes
            active = mode < active_sites
            for lane in range(batch_lanes):
                for component, cap in enumerate(contract.component_abs_max):
                    value = float(values[mode_base + component * plane_stride + lane])
                    if not math.isfinite(value):
                        _v3_profile_mismatch("v3 raw field contains a non-finite value")
                    if not active:
                        if (
                            value != contract.inactive_tail_value
                            or not _v3_scalar_is_positive_zero(value)
                        ):
                            _v3_profile_mismatch(
                                f"v3 raw field inactive tail is not exact positive zero at scale {scale}"
                            )
                    elif abs(value) > cap:
                        _v3_profile_mismatch(
                            f"v3 raw field component {component} exceeds its declared bound at scale {scale}"
                        )
                if not active:
                    continue

                epsilon2_ema = float(values[mode_base + 8 * plane_stride + lane])
                if epsilon2_ema < 0.0 or not (
                    epsilon2_ema != 0.0 or _v3_scalar_is_positive_zero(epsilon2_ema)
                ):
                    _v3_profile_mismatch("v3 raw field epsilon2_ema must be nonnegative")
                if epsilon2_ema > contract.epsilon2_ema_max:
                    _v3_profile_mismatch("v3 raw field epsilon2_ema exceeds its declared bound")
                for pair, cap in enumerate(contract.complex_amplitude_max):
                    real = float(values[mode_base + (2 * pair) * plane_stride + lane])
                    imaginary = float(
                        values[mode_base + (2 * pair + 1) * plane_stride + lane]
                    )
                    if real * real + imaginary * imaginary > cap * cap:
                        _v3_profile_mismatch(
                            f"v3 raw field complex component {pair} exceeds its declared amplitude bound at scale {scale}"
                        )
                density = math.fsum(
                    float(values[mode_base + component * plane_stride + lane]) ** 2
                    for component in range(8)
                )
                if density > contract.density_max:
                    _v3_profile_mismatch(
                        f"v3 raw field density exceeds its declared bound at scale {scale}"
                    )


@dataclass(frozen=True)
class QiFlowStateV3:
    """One profile-governed adaptive raw tensor and no secondary state object."""

    field: Tensor

    @classmethod
    def create(
        cls,
        profile: QiFlowProfile,
        *,
        batch_lanes: int,
        device: torch.device | str | None = None,
    ) -> "QiFlowStateV3":
        contract = _v3_profile_contract(profile)
        lanes = _v3_positive_int(batch_lanes, "batch_lanes")
        _v3_raw_byte_count(contract, lanes)
        target_device = _v3_target_device(contract, device)
        try:
            field = torch.zeros(
                contract.shape_prefix[0],
                contract.shape_prefix[1],
                lanes,
                dtype=contract.dtype,
                device=target_device,
            )
        except Exception as exc:
            raise QiFieldError(
                f"v3 field allocation failed: {type(exc).__name__}: {exc}"
            ) from exc
        _v3_validate_tensor(field, contract, device=target_device)
        return cls(field)

    @classmethod
    def from_field(
        cls,
        profile: QiFlowProfile,
        field: Tensor | QiFieldState,
    ) -> "QiFlowStateV3":
        tensor = field.field if isinstance(field, QiFieldState) else field
        contract = _v3_profile_contract(profile)
        _v3_validate_tensor(tensor, contract)
        return cls(tensor)

    def validate(
        self,
        profile: QiFlowProfile,
        *,
        device: torch.device | str | None = None,
    ) -> None:
        contract = _v3_profile_contract(profile)
        target = _v3_target_device(contract, device) if device is not None else None
        _v3_validate_tensor(self.field, contract, device=target)

    def to_qi_field_state(self) -> QiFieldState:
        """Expose the same sole tensor to the existing fixed physics controller."""

        return QiFieldState(self.field)

    def identity_metadata(self, profile: QiFlowProfile) -> dict[str, Any]:
        return v3_state_identity(self, profile)

    def state_sha256(self, profile: QiFlowProfile) -> str:
        return str(v3_state_identity(self, profile)["state_sha256"])

    def dump_bytes(self, profile: QiFlowProfile) -> bytes:
        return dump_v3_state_bytes(self, profile)


def _v3_identity_from_raw(
    field: Tensor,
    contract: _QiFlowV3StateContract,
    raw: bytes,
) -> dict[str, Any]:
    """Build raw-state identity after a caller has performed field validation."""

    shape = (
        int(field.shape[0]),
        int(field.shape[1]),
        int(field.shape[2]),
    )
    source_raw_sha256 = hashlib.sha256(raw).hexdigest()
    state_sha256 = _v3_tensor_sha256(
        raw,
        dtype_name=contract.dtype_name,
        shape=shape,
        state_contract_sha256=contract.state_contract_sha256,
    )
    return {
        "layout_id": contract.layout_id,
        "profile_sha256": contract.profile_sha256,
        "contract_root_sha256": contract.contract_root_sha256,
        "state_contract_sha256": contract.state_contract_sha256,
        "execution_schedule_sha256": contract.execution_schedule_sha256,
        "topology_sha256": contract.topology_sha256,
        "source_identity_sha256": contract.source_identity_sha256,
        "backend": contract.backend,
        "dtype": contract.dtype_name,
        "shape": list(shape),
        "raw_byte_count": len(raw),
        "source_raw_sha256": source_raw_sha256,
        "state_sha256": state_sha256,
    }


def v3_state_identity(state: QiFlowStateV3, profile: QiFlowProfile) -> dict[str, Any]:
    """Return the complete v3 raw-state identity, derived from one tensor."""

    if not isinstance(state, QiFlowStateV3):
        _v3_profile_mismatch("v3 state identity requires a QiFlowStateV3")
    contract = _v3_profile_contract(profile)
    _v3_validate_tensor(state.field, contract)
    raw = _v3_little_endian_raw_bytes(state.field, contract)
    return _v3_identity_from_raw(state.field, contract, raw)


def _v3_encode_state(
    state: QiFlowStateV3,
    profile: QiFlowProfile,
) -> tuple[bytes, dict[str, Any]]:
    contract = _v3_profile_contract(profile)
    _v3_validate_tensor(state.field, contract)
    raw = _v3_little_endian_raw_bytes(state.field, contract)
    metadata = _v3_identity_from_raw(state.field, contract, raw)
    header: dict[str, Any] = {"schema": QI_FLOW_STATE_V3_SCHEMA, **metadata}
    try:
        self_sha256 = canonical_hash(header, QI_FLOW_STATE_V3_SCHEMA)
        header["self_sha256"] = _v3_digest(self_sha256, "v3 checkpoint self_sha256")
        header_bytes = canonical_json_bytes(header)
    except CanonicalCodecError as exc:
        raise QiFieldError(f"v3 checkpoint header is not canonical: {exc}") from exc
    except Exception as exc:
        raise QiFieldError(
            f"v3 checkpoint header cannot be encoded: {type(exc).__name__}: {exc}"
        ) from exc
    if len(header_bytes) < 1 or len(header_bytes) > _QI_FLOW_STATE_V3_MAX_HEADER_BYTES:
        raise QiFieldError("v3 checkpoint header is outside its bounded byte budget")
    serialized = _QI_FLOW_STATE_V3_MAGIC + struct.pack(">Q", len(header_bytes)) + header_bytes + raw
    if len(serialized) > _MAX_QI_FIELD_STATE_BYTES:
        raise QiFieldError(
            f"v3 checkpoint exceeds the {_MAX_QI_FIELD_STATE_BYTES}-byte total byte budget"
        )
    return serialized, header


def dump_v3_state_bytes(state: QiFlowStateV3, profile: QiFlowProfile) -> bytes:
    """Encode one v3-only raw state with a canonical header and raw LE tensor."""

    serialized, _ = _v3_encode_state(state, profile)
    return serialized


def _v3_checkpoint_header(
    serialized: bytes,
    contract: _QiFlowV3StateContract,
) -> tuple[dict[str, Any], bytes, torch.device]:
    _v3_require_little_endian()
    minimum_size = len(_QI_FLOW_STATE_V3_MAGIC) + 8
    if len(serialized) < minimum_size:
        _v3_profile_mismatch("v3 checkpoint is truncated before its canonical header")
    if not serialized.startswith(_QI_FLOW_STATE_V3_MAGIC):
        _v3_profile_mismatch("v3 checkpoint rejects legacy, unknown, or malformed schema framing")
    header_size = struct.unpack(">Q", serialized[len(_QI_FLOW_STATE_V3_MAGIC):minimum_size])[0]
    if header_size < 2 or header_size > _QI_FLOW_STATE_V3_MAX_HEADER_BYTES:
        _v3_profile_mismatch("v3 checkpoint canonical header size is invalid")
    header_end = minimum_size + header_size
    if header_end > len(serialized):
        _v3_profile_mismatch("v3 checkpoint is truncated in its canonical header")
    header_bytes = serialized[minimum_size:header_end]
    raw = serialized[header_end:]
    try:
        header = canonical_json_loads(header_bytes)
        if canonical_json_bytes(header) != header_bytes:
            _v3_profile_mismatch("v3 checkpoint header is not exact canonical JSON")
    except CanonicalCodecError as exc:
        _v3_profile_mismatch(f"v3 checkpoint canonical header is invalid: {exc}")
    except Exception as exc:
        _v3_profile_mismatch(
            f"v3 checkpoint canonical header cannot be decoded: {type(exc).__name__}: {exc}"
        )
    if not isinstance(header, dict):
        _v3_profile_mismatch("v3 checkpoint header must be an object")
    if set(header) != _QI_FLOW_STATE_V3_HEADER_FIELDS:
        _v3_profile_mismatch(
            "v3 checkpoint must contain exactly one raw tensor identity and no extra adaptive map or tensor"
        )
    if header.get("schema") != QI_FLOW_STATE_V3_SCHEMA:
        _v3_profile_mismatch("v3 checkpoint schema is not cassi.qi-flow-state.v3")

    expected_identities = {
        "layout_id": contract.layout_id,
        "profile_sha256": contract.profile_sha256,
        "contract_root_sha256": contract.contract_root_sha256,
        "state_contract_sha256": contract.state_contract_sha256,
        "execution_schedule_sha256": contract.execution_schedule_sha256,
        "topology_sha256": contract.topology_sha256,
        "source_identity_sha256": contract.source_identity_sha256,
        "backend": contract.backend,
        "dtype": contract.dtype_name,
    }
    for name, expected in expected_identities.items():
        value = header.get(name)
        if value != expected:
            _v3_profile_mismatch(f"v3 checkpoint {name} does not match the explicit profile")

    shape_value = header.get("shape")
    if (
        not isinstance(shape_value, list)
        or len(shape_value) != 3
        or any(isinstance(value, bool) or not isinstance(value, int) for value in shape_value)
        or shape_value[0] != contract.shape_prefix[0]
        or shape_value[1] != contract.shape_prefix[1]
        or shape_value[2] < 1
    ):
        _v3_profile_mismatch("v3 checkpoint shape is incompatible with the profile layout")
    shape = (shape_value[0], shape_value[1], shape_value[2])
    expected_raw_bytes = _v3_raw_byte_count(contract, shape[2])
    raw_byte_count = header.get("raw_byte_count")
    if (
        isinstance(raw_byte_count, bool)
        or not isinstance(raw_byte_count, int)
        or raw_byte_count != expected_raw_bytes
        or raw_byte_count != len(raw)
    ):
        _v3_profile_mismatch("v3 checkpoint raw byte count is truncated or inconsistent")

    source_raw_sha256 = _v3_digest(header.get("source_raw_sha256"), "v3 checkpoint source_raw_sha256")
    if hashlib.sha256(raw).hexdigest() != source_raw_sha256:
        _v3_profile_mismatch("v3 checkpoint source raw digest mismatch")
    state_sha256 = _v3_digest(header.get("state_sha256"), "v3 checkpoint state_sha256")
    if state_sha256 != _v3_tensor_sha256(
        raw,
        dtype_name=contract.dtype_name,
        shape=shape,
        state_contract_sha256=contract.state_contract_sha256,
    ):
        _v3_profile_mismatch("v3 checkpoint state digest mismatch")
    supplied_self_sha256 = _v3_digest(header.get("self_sha256"), "v3 checkpoint self_sha256")
    self_payload = dict(header)
    del self_payload["self_sha256"]
    try:
        expected_self_sha256 = canonical_hash(self_payload, QI_FLOW_STATE_V3_SCHEMA)
    except CanonicalCodecError as exc:
        _v3_profile_mismatch(f"v3 checkpoint self-hash payload is invalid: {exc}")
    except Exception as exc:
        _v3_profile_mismatch(
            f"v3 checkpoint self-hash cannot be reconstructed: {type(exc).__name__}: {exc}"
        )
    if supplied_self_sha256 != expected_self_sha256:
        _v3_profile_mismatch("v3 checkpoint self digest mismatch")
    _v3_validate_raw_state(raw, contract, shape)
    return header, raw, torch.device(contract.backend)


def load_v3_state_bytes(
    payload: bytes | bytearray | memoryview,
    profile: QiFlowProfile,
    *,
    device: torch.device | str | None = None,
    dtype: torch.dtype | None = None,
) -> QiFlowStateV3:
    """Load one exact v3 state only after all header/raw checks pass."""

    contract = _v3_profile_contract(profile)
    target_device = _v3_target_device(contract, device)
    if dtype is not None and dtype is not contract.dtype:
        _v3_profile_mismatch("v3 checkpoint dtype conversion is forbidden")
    try:
        serialized = _coerce_state_bytes(payload)
    except QiFieldError as exc:
        _v3_profile_mismatch(f"v3 checkpoint bytes are invalid: {exc}")
    header, raw, declared_device = _v3_checkpoint_header(serialized, contract)
    if declared_device.type != target_device.type:
        _v3_profile_mismatch("v3 checkpoint backend does not match the requested backend")
    element_count = int(header["shape"][0]) * int(header["shape"][1]) * int(header["shape"][2])
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="The given buffer is not writable", category=UserWarning)
            raw_view = torch.frombuffer(raw, dtype=contract.dtype, count=element_count)
        if target_device.type == "cpu":
            owned_field = raw_view.clone()
        else:
            owned_field = raw_view.to(device=target_device)
        owned_field = owned_field.reshape(tuple(header["shape"])).contiguous()
        _v3_validate_tensor(
            owned_field,
            contract,
            device=target_device,
            check_finite=False,
        )
    except Exception as exc:
        _v3_profile_mismatch(
            f"v3 checkpoint tensor cannot be restored after validation: {type(exc).__name__}: {exc}"
        )
    return QiFlowStateV3(owned_field)


def _atomic_v3_bytes_save(payload: bytes, path: Path) -> None:
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


def save_v3_checkpoint(
    path: Path | str,
    state: QiFlowStateV3,
    profile: QiFlowProfile,
) -> str:
    """Atomically persist one explicit-profile v3 state and return its state hash."""

    serialized, header = _v3_encode_state(state, profile)
    _atomic_v3_bytes_save(serialized, Path(path))
    return str(header["state_sha256"])


def load_v3_checkpoint(
    path: Path | str,
    profile: QiFlowProfile,
    *,
    device: torch.device | str | None = None,
    dtype: torch.dtype | None = None,
) -> QiFlowStateV3:
    """Load a v3-only checkpoint; v1/v2 artifacts have no acceptance path."""

    target = Path(path)
    if not target.is_file():
        _v3_profile_mismatch(f"v3 checkpoint does not exist: {target}")
    maximum = _MAX_QI_FIELD_STATE_BYTES + len(_QI_FLOW_STATE_V3_MAGIC) + 8
    try:
        with target.open("rb") as handle:
            payload = handle.read(maximum + 1)
    except OSError as exc:
        _v3_profile_mismatch(f"v3 checkpoint cannot be read: {type(exc).__name__}: {exc}")
    return load_v3_state_bytes(payload, profile, device=device, dtype=dtype)


QI_FLOW_GEOMETRY_V2_SCHEMA = "cassi.qi-flow-field-geometry.v2"


def _w2_geometry_surface(
    state: QiFlowStateV3,
    geometry_profile: Any,
) -> Any:
    """Authenticate a W2 geometry binding before exposing the sole raw tensor."""

    try:
        from cassi_qi_geometry import (
            PeriodicSheetGeometry,
            W2GeometryProfile,
            validate_w2_geometry_profile,
        )
    except Exception as exc:
        _v3_profile_mismatch(
            f"W2 geometry surface is unavailable: {type(exc).__name__}: {exc}"
        )
    if not isinstance(state, QiFlowStateV3):
        _v3_profile_mismatch("W2 geometry requires one QiFlowStateV3")
    if not isinstance(geometry_profile, W2GeometryProfile):
        _v3_profile_mismatch("W2 geometry requires an explicit W2GeometryProfile")
    try:
        validated = validate_w2_geometry_profile(geometry_profile)
    except Exception as exc:
        _v3_profile_mismatch(
            f"W2 geometry profile validation failed: {type(exc).__name__}: {exc}"
        )
    if validated is False:
        _v3_profile_mismatch("W2 geometry profile validation failed")
    base_profile = getattr(geometry_profile, "base_profile", None)
    if not isinstance(base_profile, QiFlowProfile):
        _v3_profile_mismatch("W2 geometry profile is missing its explicit W1 base profile")
    state.validate(base_profile)
    try:
        surface = PeriodicSheetGeometry(geometry_profile)
        metadata = surface.operator_metadata()
    except Exception as exc:
        _v3_profile_mismatch(
            f"W2 geometry surface construction failed: {type(exc).__name__}: {exc}"
        )
    if (
        metadata.get("geometry_profile_sha256")
        != getattr(geometry_profile, "profile_sha256", None)
        or metadata.get("geometry_contract_root_sha256")
        != getattr(geometry_profile, "contract_root_sha256", None)
        or metadata.get("operator_semantic_sha256")
        != getattr(geometry_profile, "operator_semantic_sha256", None)
    ):
        _v3_profile_mismatch("W2 geometry semantic linkage does not match its profile")
    return surface


@dataclass(frozen=True)
class QiFlowGeometryV2:
    """Read-only ragged 2-D W2 view of the sole ``[S,9M,B]`` raw tensor."""

    state: QiFlowStateV3
    geometry_profile: Any
    _surface: Any = dataclass_field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_surface",
            _w2_geometry_surface(self.state, self.geometry_profile),
        )

    def _component_modes(self, scale: int, component: int) -> Tensor:
        if isinstance(scale, bool) or not isinstance(scale, int) or scale < 0 or scale >= self.state.field.shape[0]:
            _v3_profile_mismatch("W2 geometry scale index is outside the fixed state layout")
        if isinstance(component, bool) or not isinstance(component, int) or component < 0 or component >= 9:
            _v3_profile_mismatch("W2 geometry component index must be one of the nine packed components")
        mode_count = int(self.geometry_profile.base_profile.state_layout["mode_count"])
        start = component * mode_count
        modes = self.state.field[scale, start : start + mode_count, :]
        if tuple(modes.shape) != (mode_count, int(self.state.field.shape[2])):
            _v3_profile_mismatch("W2 geometry component slice does not preserve frozen [M,B] lane order")
        return modes

    def component_modes(self, scale: int, component: int) -> Tensor:
        """Return the exact ``[M,B]`` component view without copying."""

        return self._component_modes(scale, component)

    def component_grid(self, scale: int, component: int) -> Tensor:
        """Gather one component's active prefix as ``[Ny,Nx,B]``."""

        return self._surface.modes_to_grid(
            self._component_modes(scale, component).contiguous(),
            scale=scale,
        )

    def grid_modes(self, scale: int, grid: Tensor) -> Tensor:
        """Scatter a scale's active grid to packed ``[M,B]`` with zero tail."""

        return self._surface.grid_to_modes(grid, scale=scale)

    def gradient(self, scale: int, component: int) -> Tensor:
        return self._surface.gradient(self.component_grid(scale, component), scale=scale)

    def laplacian(self, scale: int, component: int) -> Tensor:
        return self._surface.laplacian(self.component_grid(scale, component), scale=scale)

    def laplacian_identity(self, scale: int, component: int) -> Mapping[str, Tensor]:
        grid = self.component_grid(scale, component)
        laplacian = self._surface.laplacian(grid, scale=scale)
        divergence_gradient = self._surface.divergence(
            self._surface.gradient(grid, scale=scale),
            scale=scale,
        )
        return MappingProxyType(
            {
                "laplacian": laplacian,
                "divergence_gradient": divergence_gradient,
                "identity_residual": laplacian - divergence_gradient,
            }
        )

    def vector_grid(self, scale: int, components: Sequence[int] = (0, 1)) -> Tensor:
        if (
            not isinstance(components, Sequence)
            or isinstance(components, (str, bytes))
            or len(components) != 2
            or any(isinstance(component, bool) or not isinstance(component, int) for component in components)
            or len(set(components)) != 2
        ):
            _v3_profile_mismatch("W2 vector geometry requires two distinct packed components in [x,y] order")
        return torch.stack([self.component_grid(scale, component) for component in components], dim=0).contiguous()

    def divergence(self, scale: int, components: Sequence[int] = (0, 1)) -> Tensor:
        return self._surface.divergence(self.vector_grid(scale, components), scale=scale)

    def curl(self, scale: int, components: Sequence[int] = (0, 1)) -> Tensor:
        return self._surface.curl(self.vector_grid(scale, components), scale=scale)

    def cross_scale_transfer(self, component: int, *, source_scale: int, target_scale: int) -> Tensor:
        mapped = self._surface.cross_scale_transfer(
            self._component_modes(source_scale, component).contiguous(),
            source_scale=source_scale,
            target_scale=target_scale,
        )
        return self._surface.modes_to_grid(mapped, scale=target_scale)

    def remap_epsilon2_ema(self, *, source_scale: int, target_scale: int) -> Any:
        return self._surface.remap_epsilon2_ema(
            self._component_modes(source_scale, 8).contiguous(),
            source_scale=source_scale,
            target_scale=target_scale,
        )

    def operator_metadata(self) -> Mapping[str, Any]:
        return MappingProxyType(dict(self._surface.operator_metadata()))


def bind_v3_geometry(
    state: QiFlowStateV3,
    geometry_profile: Any,
) -> QiFlowGeometryV2:
    """Bind a validated W2 periodic-sheet contract without evolving W3 dynamics."""

    return QiFlowGeometryV2(state, geometry_profile)


QI_FLOW_TRANSPORT_W3_SCHEMA = "cassi.qi-flow-field-transport.v3"



class QiFlowTransportRejected(QiFieldError):
    """A W3 candidate was rejected without mutating its predecessor."""


@dataclass(frozen=True)
class QiFlowDiagnosticsW3:
    """W3 diagnostics measured with the literal W2 periodic FFT2 operators."""

    per_scale: tuple[Mapping[str, Any], ...]
    pre_energy: float
    post_energy: float
    damping_work: float
    damping_charge: float
    transport_closure: float
    phase_charge_before: float
    phase_charge_after: float
    phase_charge_expected: float
    phase_continuity_residual: float
    current_max: float
    amplitude_max: float
    inactive_tail_nonzero: int


@dataclass(frozen=True)
class QiFlowLedgerW3:
    """The immutable W3 split-stage ledger for one candidate."""

    stage_schedule_sha256: str
    stages: tuple[Mapping[str, Any], ...]
    local_work: float
    damping_work: float
    source_work: float
    conversion_work: float
    numerical_residual: float


@dataclass(frozen=True)
class QiFlowStepW3:
    """One W3 candidate and its receipt; rejection never exposes a candidate."""

    predecessor: QiFlowStateV3
    candidate: QiFlowStateV3 | None
    committable: bool
    diagnostics: QiFlowDiagnosticsW3 | None
    ledger: QiFlowLedgerW3 | None
    receipt: Mapping[str, Any]
    failure_reason: str | None = None


def _w3_transport_context(
    state: QiFlowStateV3,
    geometry_profile: Any,
    transport_profile: Any,
) -> tuple[QiFlowGeometryV2, Mapping[str, Any], Mapping[str, Any], Any]:
    """Authenticate the current W1/W2/W3 lineage before making a candidate."""

    try:
        from cassi_qi_transport import (
            W3TransportProfile,
            validate_w3_transport_profile,
        )
    except Exception as exc:
        _v3_profile_mismatch(
            f"W3 transport profile support is unavailable: {type(exc).__name__}: {exc}"
        )
    if not isinstance(transport_profile, W3TransportProfile):
        _v3_profile_mismatch("W3 transport requires an explicit W3TransportProfile")
    try:
        validated = validate_w3_transport_profile(
            transport_profile,
            geometry_profile=geometry_profile,
        )
    except Exception as exc:
        _v3_profile_mismatch(
            f"W3 transport profile validation failed: {type(exc).__name__}: {exc}"
        )
    if validated is False:
        _v3_profile_mismatch("W3 transport profile validation failed")
    geometry = bind_v3_geometry(state, geometry_profile)
    bound_geometry = getattr(transport_profile, "base_geometry", None)
    if (
        getattr(bound_geometry, "profile_sha256", None) != geometry_profile.profile_sha256
        or getattr(bound_geometry, "contract_root_sha256", None)
        != geometry_profile.contract_root_sha256
    ):
        _v3_profile_mismatch("W3 transport profile does not bind the supplied W2 geometry")
    payload = transport_profile.payload
    semantic = payload.get("semantic")
    if not isinstance(semantic, Mapping):
        _v3_profile_mismatch("W3 transport profile omits its immutable semantic contract")
    parameters = transport_profile.pinned_parameters
    if not bool(getattr(parameters, "finite_only", False)):
        _v3_profile_mismatch("W3 transport profile must reject non-finite candidates")
    return geometry, payload, semantic, parameters


def _w3_complex_component(
    geometry: QiFlowGeometryV2,
    scale: int,
    real_component: int,
) -> Tensor:
    return torch.complex(
        geometry.component_grid(scale, real_component),
        geometry.component_grid(scale, real_component + 1),
    ).contiguous()


def _w3_literal_k2(
    surface: Any,
    scale: int,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> Tensor:
    ky, kx = surface.angular_wavenumber_axes(scale)
    return (
        ky.to(device=device, dtype=dtype)[:, None].square()
        + kx.to(device=device, dtype=dtype)[None, :].square()
    ).reshape(-1, 1)


def _w3_damped_spectral_propagate(
    surface: Any,
    scale: int,
    position: Tensor,
    velocity: Tensor,
    *,
    duration_s: float,
    c_m_per_s: float,
    omega_rad_per_s: float,
    gamma_per_s: float,
) -> tuple[Tensor, Tensor, Mapping[str, int]]:
    """Apply the exact analytic 2x2 damped oscillator once to every FFT2 mode."""

    if duration_s < 0.0 or not math.isfinite(duration_s):
        _v3_profile_mismatch("W3 spectral duration must be finite and non-negative")
    if duration_s == 0.0:
        return (
            position.clone(),
            velocity.clone(),
            MappingProxyType({"underdamped": 0, "critical": 0, "overdamped": 0}),
        )
    ny, nx = surface.sheet_shape(scale)
    active = int(surface.active_site_count(scale))
    position_modes = surface.fft2(position, scale=scale)
    velocity_modes = surface.fft2(velocity, scale=scale)
    q0 = position_modes.reshape(active, position.shape[-1])
    v0 = velocity_modes.reshape(active, velocity.shape[-1])
    real_dtype = q0.real.dtype
    k2 = _w3_literal_k2(
        surface,
        scale,
        device=q0.device,
        dtype=real_dtype,
    )
    lam = c_m_per_s * c_m_per_s * k2 + omega_rad_per_s * omega_rad_per_s
    alpha = 0.5 * gamma_per_s
    discriminant = lam - alpha * alpha
    tolerance = (
        64.0
        * torch.finfo(real_dtype).eps
        * torch.maximum(lam.abs(), torch.full_like(lam, max(1.0, alpha * alpha)))
    )
    under = (discriminant > tolerance).reshape(-1)
    over = (discriminant < -tolerance).reshape(-1)
    critical = ~(under | over)
    q1 = torch.empty_like(q0)
    v1 = torch.empty_like(v0)
    decay = math.exp(-alpha * duration_s)

    if bool(under.any().item()):
        d = discriminant[under].sqrt()
        cosine = torch.cos(d * duration_s)
        sine_over = torch.sin(d * duration_s) / d
        q = q0[under]
        v = v0[under]
        lam_u = lam[under]
        q1[under] = decay * (cosine * q + sine_over * (v + alpha * q))
        v1[under] = decay * (
            cosine * v - sine_over * (alpha * v + lam_u * q)
        )
    if bool(over.any().item()):
        d = (-discriminant[over]).sqrt()
        cosine = torch.cosh(d * duration_s)
        sine_over = torch.sinh(d * duration_s) / d
        q = q0[over]
        v = v0[over]
        lam_o = lam[over]
        q1[over] = decay * (cosine * q + sine_over * (v + alpha * q))
        v1[over] = decay * (
            cosine * v - sine_over * (alpha * v + lam_o * q)
        )
    if bool(critical.any().item()):
        q = q0[critical]
        v = v0[critical]
        lam_c = lam[critical]
        q1[critical] = decay * (q + duration_s * (v + alpha * q))
        v1[critical] = decay * (
            v - duration_s * (alpha * v + lam_c * q)
        )

    next_position = surface.ifft2(
        q1.reshape(ny, nx, position.shape[-1]).contiguous(),
        scale=scale,
    )
    next_velocity = surface.ifft2(
        v1.reshape(ny, nx, velocity.shape[-1]).contiguous(),
        scale=scale,
    )
    branches = MappingProxyType(
        {
            "underdamped": int(under.sum().item()),
            "critical": int(critical.sum().item()),
            "overdamped": int(over.sum().item()),
        }
    )
    return next_position.contiguous(), next_velocity.contiguous(), branches


def _w3_energy_and_current(
    surface: Any,
    scale: int,
    position: Tensor,
    velocity: Tensor,
    *,
    c_m_per_s: float,
    omega_rad_per_s: float,
    kappa: float,
    weight_d: float,
) -> Mapping[str, Any]:
    """Measure the normative D-coordinate Hamiltonian, charge, and current."""

    gradient = surface.gradient(position, scale=scale)
    area = float(surface.cell_area_m2(scale))
    gradient_norm2 = gradient.abs().square().sum(dim=0)
    density = weight_d * (
        0.5 * velocity.abs().square()
        + 0.5 * c_m_per_s * c_m_per_s * gradient_norm2
        + 0.5 * omega_rad_per_s * omega_rad_per_s * position.abs().square()
        + 0.25 * kappa * position.abs().square().square()
    )
    phase_density = weight_d * torch.imag(torch.conj(position) * velocity)
    current = (
        -weight_d
        * c_m_per_s
        * c_m_per_s
        * torch.imag(torch.conj(position).unsqueeze(0) * gradient)
    )
    energy_flux = (
        -weight_d
        * c_m_per_s
        * c_m_per_s
        * torch.real(torch.conj(velocity).unsqueeze(0) * gradient)
    )
    return MappingProxyType(
        {
            "energy": float((density.sum() * area).item()),
            "phase_charge": float((phase_density.sum() * area).item()),
            "current_max": float(current.abs().amax().item()),
            "current_integral_x": float((current[0].sum() * area).item()),
            "current_integral_y": float((current[1].sum() * area).item()),
            "energy_flux_max": float(energy_flux.abs().amax().item()),
            "amplitude_max": float(position.abs().amax().item()),
        }
    )


def _w3_schedule(
    duration_s: float,
) -> tuple[tuple[Mapping[str, Any], ...], str]:
    try:
        from cassi_qi_transport import W3_STAGE_SCHEDULE_SCHEMA, w3_stage_schedule

        payload = w3_stage_schedule(duration_s)
    except Exception as exc:
        _v3_profile_mismatch(
            f"W3 stage schedule cannot be derived: {type(exc).__name__}: {exc}"
        )
    stages = tuple(MappingProxyType(dict(row)) for row in payload["stages"])
    return stages, canonical_hash(payload, W3_STAGE_SCHEDULE_SCHEMA)


def _w3_failure_step(
    predecessor: QiFlowStateV3,
    *,
    reason: str,
    parents: Mapping[str, Any],
) -> QiFlowStepW3:
    receipt = MappingProxyType(
        {
            "schema": QI_FLOW_TRANSPORT_W3_SCHEMA,
            "status": "REJECTED",
            "parents": MappingProxyType(dict(parents)),
            "failure_reason": reason,
            "committable": False,
        }
    )
    return QiFlowStepW3(
        predecessor=predecessor,
        candidate=None,
        committable=False,
        diagnostics=None,
        ledger=None,
        receipt=receipt,
        failure_reason=reason,
    )


def _w3_write_component(
    candidate: Tensor,
    surface: Any,
    *,
    scale: int,
    component: int,
    values: Tensor,
) -> None:
    mode_count = int(candidate.shape[1] // 9)
    active = int(surface.active_site_count(scale))
    start = component * mode_count
    candidate[scale, start : start + mode_count].zero_()
    candidate[scale, start : start + active].copy_(
        values.reshape(active, values.shape[-1])
    )


def transition_v3_transport(
    state: QiFlowStateV3,
    *,
    geometry_profile: Any,
    transport_profile: Any,
    duration_s: float | None = None,
    source: Any | None = None,
) -> QiFlowStepW3:
    """Advance the W3 D field with a symmetric local/spectral FFT2 split."""

    if source is not None:
        return _w3_failure_step(
            state,
            reason="W3 is source-free; any source admission is rejected",
            parents=MappingProxyType({}),
        )
    geometry, profile_payload, semantic, parameters = _w3_transport_context(
        state,
        geometry_profile,
        transport_profile,
    )
    try:
        predecessor_identity = v3_state_identity(state, geometry_profile.base_profile)
    except Exception as exc:
        return _w3_failure_step(
            state,
            reason=f"W3 predecessor identity failed: {type(exc).__name__}: {exc}",
            parents=MappingProxyType({}),
        )
    parents = MappingProxyType(
        {
            "predecessor_state_sha256": predecessor_identity["state_sha256"],
            "transport_profile_sha256": profile_payload["profile_sha256"],
            "transport_contract_root_sha256": profile_payload[
                "contract_root_sha256"
            ],
            "transport_semantic_sha256": profile_payload["semantic_sha256"],
            "geometry_profile_sha256": geometry_profile.profile_sha256,
            "geometry_contract_root_sha256": geometry_profile.contract_root_sha256,
            "geometry_contract_sha256": geometry_profile.geometry_contract_sha256,
            "operator_semantic_sha256": geometry_profile.operator_semantic_sha256,
        }
    )
    inactive_terms = semantic.get("inactive_terms")
    if not isinstance(inactive_terms, Mapping) or not all(
        bool(value) for value in inactive_terms.values()
    ):
        return _w3_failure_step(
            state,
            reason="W3 transport profile violates fixed finite-only inactive-term semantics",
            parents=parents,
        )
    field = state.field
    if not bool(torch.isfinite(field).all().item()):
        return _w3_failure_step(
            state,
            reason="W3 predecessor contains non-finite values",
            parents=parents,
        )
    step_duration = float(parameters.h if duration_s is None else duration_s)
    h_max = float(getattr(parameters, "h_max_s", parameters.h))
    if (
        not math.isfinite(step_duration)
        or step_duration < 0.0
        or step_duration > h_max
    ):
        return _w3_failure_step(
            state,
            reason="W3 duration is outside the declared refinement interval",
            parents=parents,
        )
    if float(field.abs().amax().item()) > float(parameters.amplitude_cap):
        return _w3_failure_step(
            state,
            reason="W3 predecessor exceeds the amplitude cap",
            parents=parents,
        )

    surface = geometry._surface
    half_duration = 0.5 * step_duration
    phi = finite_float(parameters.phi, name="authenticated W3 phi")
    weight_d = 1.0 / (1.0 + phi * phi)
    candidate_field = field.clone()
    per_scale: list[Mapping[str, Any]] = []
    stage_totals = [
        {"energy_before": 0.0, "energy_after": 0.0, "work": 0.0}
        for _ in range(7)
    ]
    pre_energy = 0.0
    post_energy = 0.0
    damping_work = 0.0
    local_work = 0.0
    damping_charge = 0.0
    phase_before = 0.0
    phase_after = 0.0
    phase_expected = 0.0
    current_max = 0.0
    branch_totals = {"underdamped": 0, "critical": 0, "overdamped": 0}

    for scale in range(int(field.shape[0])):
        yang = _w3_complex_component(geometry, scale, 0)
        yin = _w3_complex_component(geometry, scale, 2)
        velocity_yang = _w3_complex_component(geometry, scale, 4)
        velocity_yin = _w3_complex_component(geometry, scale, 6)
        differential = yang - phi * yin
        coherence = (phi * yang + yin) * weight_d
        differential_velocity = velocity_yang - phi * velocity_yin
        coherence_velocity = (phi * velocity_yang + velocity_yin) * weight_d
        c_value = float(parameters.c_D_m_per_s[scale])
        omega_value = float(parameters.omega_rad_per_s[scale])
        gamma_value = float(parameters.gamma_per_s[scale])
        kappa_value = float(parameters.kappa[scale])

        before = _w3_energy_and_current(
            surface,
            scale,
            differential,
            differential_velocity,
            c_m_per_s=c_value,
            omega_rad_per_s=omega_value,
            kappa=kappa_value,
            weight_d=weight_d,
        )
        projector = None
        first_velocity = differential_velocity
        if kappa_value != 0.0 and half_duration != 0.0:
            try:
                from cassi_qi_transport import projected_pseudospectral_operators

                projector = projected_pseudospectral_operators(surface, scale)
                oversampled = projector.I(differential)
                force = -kappa_value * projector.R(
                    oversampled.abs().square() * oversampled
                )
                first_velocity = differential_velocity + half_duration * force
            except Exception as exc:
                return _w3_failure_step(
                    state,
                    reason=f"W3 first local half-kick failed: {type(exc).__name__}: {exc}",
                    parents=parents,
                )
        after_first_local = _w3_energy_and_current(
            surface,
            scale,
            differential,
            first_velocity,
            c_m_per_s=c_value,
            omega_rad_per_s=omega_value,
            kappa=kappa_value,
            weight_d=weight_d,
        )
        first_position, first_spectral_velocity, first_branches = (
            _w3_damped_spectral_propagate(
                surface,
                scale,
                differential,
                first_velocity,
                duration_s=half_duration,
                c_m_per_s=c_value,
                omega_rad_per_s=omega_value,
                gamma_per_s=gamma_value,
            )
        )
        after_first_spectral = _w3_energy_and_current(
            surface,
            scale,
            first_position,
            first_spectral_velocity,
            c_m_per_s=c_value,
            omega_rad_per_s=omega_value,
            kappa=kappa_value,
            weight_d=weight_d,
        )
        first_linear_before = _w3_energy_and_current(
            surface,
            scale,
            differential,
            first_velocity,
            c_m_per_s=c_value,
            omega_rad_per_s=omega_value,
            kappa=0.0,
            weight_d=weight_d,
        )
        first_linear_after = _w3_energy_and_current(
            surface,
            scale,
            first_position,
            first_spectral_velocity,
            c_m_per_s=c_value,
            omega_rad_per_s=omega_value,
            kappa=0.0,
            weight_d=weight_d,
        )
        first_damping_work = float(first_linear_after["energy"]) - float(
            first_linear_before["energy"]
        )
        second_position, second_spectral_velocity, second_branches = (
            _w3_damped_spectral_propagate(
                surface,
                scale,
                first_position,
                first_spectral_velocity,
                duration_s=half_duration,
                c_m_per_s=c_value,
                omega_rad_per_s=omega_value,
                gamma_per_s=gamma_value,
            )
        )
        after_second_spectral = _w3_energy_and_current(
            surface,
            scale,
            second_position,
            second_spectral_velocity,
            c_m_per_s=c_value,
            omega_rad_per_s=omega_value,
            kappa=kappa_value,
            weight_d=weight_d,
        )
        second_linear_before = _w3_energy_and_current(
            surface,
            scale,
            first_position,
            first_spectral_velocity,
            c_m_per_s=c_value,
            omega_rad_per_s=omega_value,
            kappa=0.0,
            weight_d=weight_d,
        )
        second_linear_after = _w3_energy_and_current(
            surface,
            scale,
            second_position,
            second_spectral_velocity,
            c_m_per_s=c_value,
            omega_rad_per_s=omega_value,
            kappa=0.0,
            weight_d=weight_d,
        )
        second_damping_work = float(second_linear_after["energy"]) - float(
            second_linear_before["energy"]
        )
        next_velocity = second_spectral_velocity
        if kappa_value != 0.0 and half_duration != 0.0:
            assert projector is not None
            oversampled = projector.I(second_position)
            force = -kappa_value * projector.R(
                oversampled.abs().square() * oversampled
            )
            next_velocity = second_spectral_velocity + half_duration * force
        after = _w3_energy_and_current(
            surface,
            scale,
            second_position,
            next_velocity,
            c_m_per_s=c_value,
            omega_rad_per_s=omega_value,
            kappa=kappa_value,
            weight_d=weight_d,
        )

        next_yang = weight_d * second_position + phi * coherence
        next_yin = coherence - phi * weight_d * second_position
        next_velocity_yang = weight_d * next_velocity + phi * coherence_velocity
        next_velocity_yin = coherence_velocity - phi * weight_d * next_velocity
        for component, value in (
            (0, next_yang.real),
            (1, next_yang.imag),
            (2, next_yin.real),
            (3, next_yin.imag),
            (4, next_velocity_yang.real),
            (5, next_velocity_yang.imag),
            (6, next_velocity_yin.real),
            (7, next_velocity_yin.imag),
        ):
            _w3_write_component(
                candidate_field,
                surface,
                scale=scale,
                component=component,
                values=value.contiguous(),
            )

        first_local_work = float(after_first_local["energy"]) - float(
            before["energy"]
        )
        second_local_work = float(after["energy"]) - float(
            after_second_spectral["energy"]
        )
        scale_damping_work = first_damping_work + second_damping_work
        expected_charge = math.exp(-gamma_value * step_duration) * float(
            before["phase_charge"]
        )
        charge_residual = float(after["phase_charge"]) - expected_charge
        energy_residual = (
            float(after["energy"]) - float(before["energy"]) - scale_damping_work
        )
        for key in branch_totals:
            branch_totals[key] += int(first_branches[key]) + int(
                second_branches[key]
            )
        pre_energy += float(before["energy"])
        post_energy += float(after["energy"])
        damping_work += scale_damping_work
        local_work += first_local_work + second_local_work
        phase_before += float(before["phase_charge"])
        phase_after += float(after["phase_charge"])
        phase_expected += expected_charge
        damping_charge += (
            float(after_first_spectral["phase_charge"])
            - float(after_first_local["phase_charge"])
            + float(after_second_spectral["phase_charge"])
            - float(after_first_spectral["phase_charge"])
        )
        current_max = max(
            current_max,
            float(before["current_max"]),
            float(after["current_max"]),
        )
        stage_states = (
            (before, before, 0.0),
            (before, after_first_local, first_local_work),
            (after_first_local, after_first_spectral, first_damping_work),
            (after_first_spectral, after_first_spectral, 0.0),
            (after_first_spectral, after_second_spectral, second_damping_work),
            (after_second_spectral, after, second_local_work),
            (after, after, 0.0),
        )
        for aggregate, (stage_before, stage_after, work) in zip(
            stage_totals, stage_states
        ):
            aggregate["energy_before"] += float(stage_before["energy"])
            aggregate["energy_after"] += float(stage_after["energy"])
            aggregate["work"] += float(work)
        per_scale.append(
            MappingProxyType(
                {
                    "scale": scale,
                    "sheet_shape": list(surface.sheet_shape(scale)),
                    "active_site_count": int(surface.active_site_count(scale)),
                    "cell_area_m2": float(surface.cell_area_m2(scale)),
                    "energy_before": float(before["energy"]),
                    "energy_after": float(after["energy"]),
                    "damping_work": scale_damping_work,
                    "local_split_work": first_local_work + second_local_work,
                    "energy_closure_residual": energy_residual,
                    "phase_charge_before": float(before["phase_charge"]),
                    "phase_charge_after": float(after["phase_charge"]),
                    "phase_charge_expected": expected_charge,
                    "phase_continuity_residual": charge_residual,
                    "current_max": max(
                        float(before["current_max"]),
                        float(after["current_max"]),
                    ),
                    "amplitude_max": float(after["amplitude_max"]),
                }
            )
        )

    if not bool(torch.isfinite(candidate_field).all().item()):
        return _w3_failure_step(
            state,
            reason="W3 candidate is non-finite",
            parents=parents,
        )
    candidate_amplitude = float(candidate_field.abs().amax().item())
    if candidate_amplitude > float(parameters.amplitude_cap):
        return _w3_failure_step(
            state,
            reason="W3 candidate exceeds the amplitude cap",
            parents=parents,
        )
    tail_proof = surface.zero_tail_proof(candidate_field)
    if not bool(tail_proof["inactive_tail_is_exact_zero"]):
        return _w3_failure_step(
            state,
            reason="W3 candidate wrote a nonzero inactive packed tail",
            parents=parents,
        )
    inactive_nonzero = sum(
        int(row["inactive_nonzero"]) for row in tail_proof["per_scale"]
    )
    candidate = QiFlowStateV3(candidate_field.contiguous())
    try:
        candidate.validate(geometry_profile.base_profile)
    except Exception as exc:
        return _w3_failure_step(
            state,
            reason=f"W3 candidate violates the W1 state contract: {type(exc).__name__}: {exc}",
            parents=parents,
        )
    schedule_stages, schedule_sha256 = _w3_schedule(step_duration)
    ledger_stages = tuple(
        MappingProxyType(
            {
                **dict(schedule),
                "energy_before": stage["energy_before"],
                "energy_after": stage["energy_after"],
                "work": stage["work"],
            }
        )
        for schedule, stage in zip(schedule_stages, stage_totals)
    )
    closure = post_energy - pre_energy - damping_work
    phase_residual = phase_after - phase_expected
    diagnostics = QiFlowDiagnosticsW3(
        per_scale=tuple(per_scale),
        pre_energy=pre_energy,
        post_energy=post_energy,
        damping_work=damping_work,
        damping_charge=damping_charge,
        transport_closure=closure,
        phase_charge_before=phase_before,
        phase_charge_after=phase_after,
        phase_charge_expected=phase_expected,
        phase_continuity_residual=phase_residual,
        current_max=current_max,
        amplitude_max=candidate_amplitude,
        inactive_tail_nonzero=inactive_nonzero,
    )
    ledger = QiFlowLedgerW3(
        stage_schedule_sha256=schedule_sha256,
        stages=ledger_stages,
        local_work=local_work,
        damping_work=damping_work,
        source_work=0.0,
        conversion_work=0.0,
        numerical_residual=closure,
    )
    candidate_identity = v3_state_identity(candidate, geometry_profile.base_profile)
    receipt = MappingProxyType(
        {
            "schema": QI_FLOW_TRANSPORT_W3_SCHEMA,
            "status": "PASS",
            "parents": parents,
            "candidate_state_sha256": candidate_identity["state_sha256"],
            "stage_schedule_sha256": schedule_sha256,
            "inactive_terms": semantic["inactive_terms"],
            "damping_applied_once": True,
            "spectral_branch_counts": MappingProxyType(branch_totals),
            "conversion_stage": "centered-inactive-until-W5",
            "source_admission": False,
            "predecessor_state_retained": True,
            "committable": True,
        }
    )
    return QiFlowStepW3(
        predecessor=state,
        candidate=candidate,
        committable=True,
        diagnostics=diagnostics,
        ledger=ledger,
        receipt=receipt,
    )
__all__ = [
    "QI_CODEBOOK_PROFILE_ID",
    "QI_FIELD_CONFIG_SCHEMA",
    "QI_FIELD_LAYOUT_ID",
    "QI_FIELD_OPERATOR_PROFILE_ID",
    "QI_FIELD_STATE_SCHEMA",
    "QI_FLOW_STATE_V3_SCHEMA",
    "QI_FLOW_GEOMETRY_V2_SCHEMA",
    "QI_FLOW_TRANSPORT_W3_SCHEMA",
    "QI_FLOW_STATE_V3_TENSOR_DOMAIN",
    "CassiQiFieldError",
    "QiBalanceConversion",
    "QiConsolidationResult",
    "QiFieldConfig",
    "QiFieldController",
    "QiFieldCycle",
    "QiFieldDiagnostics",
    "QiFieldError",
    "QiFieldPhysicsConfig",
    "QiFieldReadout",
    "QiFieldState",
    "QiFlowStateV3",
    "QiFlowGeometryV2",
    "QiFlowDiagnosticsW3",
    "QiFlowLedgerW3",
    "QiFlowStepW3",
    "QiFlowTransportRejected",
    "QiSenseResult",
    "dump_v3_state_bytes",
    "load_qi_field_state",
    "load_v3_checkpoint",
    "load_v3_state_bytes",
    "save_qi_field_state",
    "save_v3_checkpoint",
    "bind_v3_geometry",
    "transition_v3_transport",
    "v3_state_identity",
]
