"""Deterministic associative KV reference for the Cassi Qi multi-scale path.

This pure Torch reference owns no Qwen tensors and has no learned projection,
embedding table, MLP, or neural head. Fixed analytic complex Fourier/address
codes bind keys, values, position, layer, head, and scale. The only adaptive
persistent payload is one canonical Qi field tensor with shape ``[S, 9*M, B]``:
eight real Yang/Yin position/velocity components plus ``epsilon2_ema``. The
exact local ring is ephemeral cache state and is never included in a field-only
checkpoint.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Deque, Mapping, Sequence

import torch
from torch import Tensor


QI_KV_CONFIG_SCHEMA = "cassi.qi-kv.config.v1"
QI_KV_STATE_SCHEMA = "cassi.qi-kv.state.v1"
QI_KV_BINDING_PROFILE_ID = "cassi.qi-kv.four-tag-fourier.v1"
_DEFAULT_PHI = 1.618033988749895
_DEFAULT_PRIMES = (4093, 4099, 4127, 4133)
_CODEBOOK_DESCRIPTOR_VERSION = "cassi.qi-kv.codebook.v1"


class QiKVError(ValueError):
    """Invalid Qi associative-memory configuration, state, or query."""


def _finite(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QiKVError(f"{name} must be a finite real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise QiKVError(f"{name} must be finite")
    return converted


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise QiKVError(f"{name} must be a positive integer")
    return int(value)


def _unit_interval(name: str, value: Any) -> float:
    converted = _finite(name, value)
    if converted < 0.0 or converted > 1.0:
        raise QiKVError(f"{name} must be in [0, 1]")
    return converted


def _positive_finite(name: str, value: Any) -> float:
    converted = _finite(name, value)
    if converted <= 0.0:
        raise QiKVError(f"{name} must be positive")
    return converted


def _integer_index(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise QiKVError(f"{name} must be an integer")
    return int(value)


def _jsonable_config(config: "QiKVConfig") -> dict[str, Any]:
    payload = asdict(config)
    payload["scale_primes"] = list(config.scale_primes)
    return payload


@dataclass(frozen=True)
class QiKVConfig:
    """Fixed controls for a deterministic Qi associative KV memory.

    ``mode_count`` is the Fourier mode count in each scale bank. For a
    matched-budget comparison use :meth:`matched_budget`; an ordinary
    multi-scale configuration with the same ``mode_count`` at every scale is
    the expanded-bank comparison.
    """

    mode: str = "compress"
    local_window: int = 8
    scale_count: int = 4
    head_count: int = 1
    mode_count: int = 64
    key_dim: int = 16
    value_dim: int = 8
    phi: float = _DEFAULT_PHI
    scale_ratio: float | None = None
    dt: float = 0.005
    epsilon_tau: float = _DEFAULT_PHI**-1
    energy_floor: float = 1.0e-6
    read_threshold: float = 0.10
    write_gain: float = 1.0
    field_retention: float = 0.999
    max_field_norm: float = 64.0
    max_value_norm: float = 16.0
    max_epsilon2: float = 64.0
    local_entry_overhead: int = 32
    total_mode_budget: int | None = None
    scale_primes: tuple[int, ...] = _DEFAULT_PRIMES

    def __post_init__(self) -> None:
        if self.mode not in {"assist", "compress", "replace"}:
            raise QiKVError("mode must be one of {'assist', 'compress', 'replace'}")
        local_window = _positive_int("local_window", self.local_window)
        scale_count = _positive_int("scale_count", self.scale_count)
        head_count = _positive_int("head_count", self.head_count)
        mode_count = _positive_int("mode_count", self.mode_count)
        key_dim = _positive_int("key_dim", self.key_dim)
        value_dim = _positive_int("value_dim", self.value_dim)
        local_entry_overhead = _positive_int("local_entry_overhead", self.local_entry_overhead)
        if value_dim > mode_count:
            raise QiKVError("value_dim cannot exceed mode_count")
        try:
            primes = tuple(_positive_int("scale_primes item", int(item)) for item in self.scale_primes)
        except (TypeError, ValueError) as exc:
            raise QiKVError("scale_primes must be a sequence of positive integers") from exc
        if primes != _DEFAULT_PRIMES:
            raise QiKVError("QiKV v1 requires the fixed prime tuple (4093, 4099, 4127, 4133)")
        if scale_count > len(primes):
            raise QiKVError("scale_count exceeds the fixed scale-prime table")
        total_mode_budget = self.total_mode_budget
        if total_mode_budget is not None:
            total_mode_budget = _positive_int("total_mode_budget", total_mode_budget)
            if total_mode_budget % scale_count:
                raise QiKVError("total_mode_budget must be divisible by scale_count")
            mode_count = total_mode_budget // scale_count
            if mode_count < value_dim:
                raise QiKVError("matched total_mode_budget leaves too few modes for value_dim")
        phi = _positive_finite("phi", self.phi)
        scale_ratio = self.scale_ratio
        if scale_ratio is None:
            scale_ratio = phi**3
        scale_ratio = _positive_finite("scale_ratio", scale_ratio)
        dt = _positive_finite("dt", self.dt)
        epsilon_tau = _unit_interval("epsilon_tau", self.epsilon_tau)
        energy_floor = _positive_finite("energy_floor", self.energy_floor)
        read_threshold = _unit_interval("read_threshold", self.read_threshold)
        write_gain = _positive_finite("write_gain", self.write_gain)
        field_retention = _unit_interval("field_retention", self.field_retention)
        max_field_norm = _positive_finite("max_field_norm", self.max_field_norm)
        max_value_norm = _positive_finite("max_value_norm", self.max_value_norm)
        max_epsilon2 = _positive_finite("max_epsilon2", self.max_epsilon2)
        object.__setattr__(self, "local_window", local_window)
        object.__setattr__(self, "scale_count", scale_count)
        object.__setattr__(self, "head_count", head_count)
        object.__setattr__(self, "mode_count", mode_count)
        object.__setattr__(self, "key_dim", key_dim)
        object.__setattr__(self, "value_dim", value_dim)
        object.__setattr__(self, "phi", phi)
        object.__setattr__(self, "scale_ratio", scale_ratio)
        object.__setattr__(self, "dt", dt)
        object.__setattr__(self, "epsilon_tau", epsilon_tau)
        object.__setattr__(self, "energy_floor", energy_floor)
        object.__setattr__(self, "read_threshold", read_threshold)
        object.__setattr__(self, "write_gain", write_gain)
        object.__setattr__(self, "field_retention", field_retention)
        object.__setattr__(self, "max_field_norm", max_field_norm)
        object.__setattr__(self, "max_value_norm", max_value_norm)
        object.__setattr__(self, "max_epsilon2", max_epsilon2)
        object.__setattr__(self, "local_entry_overhead", local_entry_overhead)
        object.__setattr__(self, "total_mode_budget", total_mode_budget)
        object.__setattr__(self, "scale_primes", primes)

    @classmethod
    def matched_budget(cls, total_mode_budget: int, **kwargs: Any) -> "QiKVConfig":
        """Construct a configuration with a fixed total scale-bank budget."""

        total = _positive_int("total_mode_budget", total_mode_budget)
        scale_count = _positive_int("scale_count", int(kwargs.get("scale_count", 1)))
        if total % scale_count:
            raise QiKVError("total_mode_budget must be divisible by scale_count")
        payload = dict(kwargs)
        payload["scale_count"] = scale_count
        payload["mode_count"] = total // scale_count
        payload["total_mode_budget"] = total
        return cls(**payload)

    @property
    def total_modes(self) -> int:
        return self.scale_count * self.mode_count

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(_jsonable_config(self), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable_config(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "QiKVConfig":
        if not isinstance(value, Mapping):
            raise QiKVError("QiKV configuration must be a mapping")
        payload = dict(value)
        unknown = set(payload) - set(cls.__dataclass_fields__)
        if unknown:
            raise QiKVError(f"QiKV configuration has unknown fields: {sorted(unknown)!r}")
        if "scale_primes" in payload:
            try:
                payload["scale_primes"] = tuple(payload["scale_primes"])
            except TypeError as exc:
                raise QiKVError("scale_primes must be a sequence") from exc
        try:
            return cls(**payload)
        except QiKVError:
            raise
        except (TypeError, ValueError) as exc:
            raise QiKVError(f"invalid QiKV configuration: {exc}") from exc


@dataclass(frozen=True)
class QiKVState:
    """Canonical persistent Qi field with shape ``[S, 9*M, B]``."""

    field: Tensor

    def validate(self, config: QiKVConfig, *, device: torch.device | None = None, dtype: torch.dtype | None = None) -> None:
        if not torch.is_tensor(self.field):
            raise QiKVError("QiKV field must be a torch.Tensor")
        expected = (config.scale_count, 9 * config.mode_count)
        if self.field.ndim != 3 or tuple(self.field.shape[:2]) != expected or self.field.shape[2] < 1:
            raise QiKVError(f"QiKV field must have shape [{expected[0]}, {expected[1]}, B] with B >= 1")
        if not self.field.dtype.is_floating_point:
            raise QiKVError("QiKV field must use F32 or F64 real storage")
        if not bool(torch.isfinite(self.field).all().item()):
            raise QiKVError("QiKV field contains non-finite values")
        if device is not None and self.field.device != device:
            raise QiKVError("QiKV field device does not match the requested device")
        if dtype is not None and self.field.dtype != dtype:
            raise QiKVError("QiKV field dtype does not match the requested dtype")

    @property
    def batch_size(self) -> int:
        return int(self.field.shape[2])

    def clone(self) -> "QiKVState":
        return QiKVState(self.field.clone())

    def detach(self) -> "QiKVState":
        return QiKVState(self.field.detach())

    def to(self, device: torch.device | str, *, dtype: torch.dtype | None = None) -> "QiKVState":
        return QiKVState(self.field.to(device=device, dtype=dtype or self.field.dtype))


@dataclass(frozen=True)
class QiKVByteAccounting:
    """Deterministic adaptive and ephemeral memory capacity accounting."""

    field_bytes: int
    local_bytes: int
    total_bytes: int
    field_modes: int
    local_entries: int
    local_entry_bytes: int

    def __getitem__(self, key: str) -> int:
        return int(getattr(self, key))

    def get(self, key: str, default: int | None = None) -> int | None:
        return int(getattr(self, key)) if hasattr(self, key) else default

    def as_dict(self) -> dict[str, int]:
        return {"field_bytes": self.field_bytes, "local_bytes": self.local_bytes, "total_bytes": self.total_bytes, "field_modes": self.field_modes, "local_entries": self.local_entries, "local_entry_bytes": self.local_entry_bytes}


@dataclass(frozen=True)
class QiKVQueryResult:
    """Finite query result and compact Qi read telemetry."""

    value: Tensor
    available: bool
    q: float
    q_max: float
    epsilon2_ema: float
    chi: float
    cross_scale_coherence: float
    read_gate: float
    local_weight: float
    field_weight: float
    memory_bytes: QiKVByteAccounting
    local_available: bool = False
    field_available: bool = False
    exact: bool = False

    @property
    def zero(self) -> bool:
        return not self.available and bool(torch.count_nonzero(self.value).item() == 0)


@dataclass(frozen=True)
class _LocalEntry:
    batch: int
    key_identity: tuple[float, ...]
    value: tuple[float, ...]
    position: int
    layer: int
    head: int


class QiKVMemory:
    """Pure Torch deterministic associative KV memory over the canonical Qi field."""

    def __init__(self, config: QiKVConfig | None = None) -> None:
        self.config = config if config is not None else QiKVConfig()
        if not isinstance(self.config, QiKVConfig):
            raise QiKVError("config must be QiKVConfig")
        self._local_ring: dict[int, Deque[_LocalEntry]] = {}

    @property
    def config_fingerprint(self) -> str:
        return self.config.fingerprint

    @property
    def codebook_descriptor(self) -> dict[str, Any]:
        return {"version": _CODEBOOK_DESCRIPTOR_VERSION, "binding_profile_id": QI_KV_BINDING_PROFILE_ID, "address": "normalized-complex-fft-quadratic-chirp", "value_basis": "fixed-fourier-dft", "scale_primes": list(_DEFAULT_PRIMES), "mode_count": self.config.mode_count, "key_dim": self.config.key_dim, "value_dim": self.config.value_dim}

    @property
    def codebook_fingerprint(self) -> str:
        encoded = json.dumps(self.codebook_descriptor, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def initial_state(self, batch_size: int = 1, *, device: torch.device | str = "cpu", dtype: torch.dtype = torch.float32) -> QiKVState:
        batch = _positive_int("batch_size", batch_size)
        if dtype not in (torch.float32, torch.float64):
            raise QiKVError("dtype must be torch.float32 or torch.float64")
        state = QiKVState(torch.zeros((self.config.scale_count, 9 * self.config.mode_count, batch), device=device, dtype=dtype))
        state.validate(self.config)
        return state

    def reset(self, state: QiKVState | None = None) -> QiKVState:
        """Clear the adaptive field and ephemeral exact ring."""

        self._local_ring.clear()
        if state is None:
            return self.initial_state()
        self._validate_state(state)
        return QiKVState(torch.zeros_like(state.field))

    def reset_local_ring(self) -> None:
        self._local_ring.clear()

    def memory_bytes(self, state: QiKVState | None = None) -> QiKVByteAccounting:
        """Return field and bounded local-ring capacity in bytes."""

        if state is None:
            batch, element_size = 1, torch.tensor([], dtype=torch.float32).element_size()
        else:
            self._validate_state(state)
            batch, element_size = state.batch_size, state.field.element_size()
        field_modes = self.config.total_modes * batch
        field_elements = self.config.scale_count * 9 * self.config.mode_count * batch
        field_bytes = int(field_elements * element_size)
        local_entries = 0 if self.config.mode == "replace" else self.config.local_window * batch
        local_entry_bytes = int(self.config.key_dim * 4 + self.config.value_dim * 4 + 4 * 4 + self.config.local_entry_overhead)
        local_bytes = int(local_entries * local_entry_bytes)
        return QiKVByteAccounting(field_bytes, local_bytes, field_bytes + local_bytes, field_modes, local_entries, local_entry_bytes)

    def deposit(self, state: QiKVState, key: Any, value: Any, position: int, layer: int = 0, head: int = 0, scale: int | None = None, batch: int = 0) -> QiKVState:
        """Deposit into scale zero, then consolidate through gated slower banks."""

        self._validate_state(state)
        position, layer, head, batch = (_integer_index("position", position), _integer_index("layer", layer), _integer_index("head", head), _integer_index("batch", batch))
        if min(position, layer, head, batch) < 0:
            raise QiKVError("position, layer, head, and batch must be non-negative")
        if head >= self.config.head_count or batch >= state.batch_size:
            raise QiKVError("head or batch is outside configuration/state")
        if scale is not None:
            raise QiKVError("QiKV deposits enter scale zero; consolidation owns slower scales")
        real_dtype = state.field.dtype
        key_tensor = self._coerce_key(key, device=state.field.device, dtype=real_dtype)
        value_tensor = self._clip_real_vector(self._coerce_value(value, device=state.field.device, dtype=real_dtype), self.config.max_value_norm)
        target_scale = 0
        updated = state.field.clone()
        bank = updated[target_scale, :, batch]
        old_y, old_i = self._decode_y_i(bank)
        old_d = old_y - self.config.phi * old_i
        binding = self.binding(key_tensor, position, layer=layer, head=head, scale=target_scale, device=state.field.device, dtype=self._complex_dtype(real_dtype))
        encoded = self._encode_value(value_tensor, scale=target_scale, device=state.field.device, dtype=self._complex_dtype(real_dtype))
        payload = binding * encoded * float(self.config.mode_count)
        old_q, _, old_rho, _ = self._bank_metrics(bank)
        write_gate = 1.0 if old_rho < self.config.energy_floor else max(0.0, min(1.0, 1.0 - old_q))
        gain = self.config.write_gain * write_gate
        next_d = self._clip_complex_vector(self.config.field_retention * old_d + gain * payload, self.config.max_field_norm)
        delta_d = next_d - old_d
        next_y, next_i = old_y + 0.5 * delta_d, old_i - 0.5 * delta_d / self.config.phi
        y_dot, i_dot = self._clip_complex_vector(next_y - old_y, self.config.max_field_norm), self._clip_complex_vector(next_i - old_i, self.config.max_field_norm)
        epsilon = self._epsilon_from_y_i(next_y, next_i)
        epsilon2 = (1.0 - self.config.epsilon_tau) * self._epsilon2(bank) + self.config.epsilon_tau * epsilon * epsilon
        updated[target_scale, :, batch] = self._encode_field_bank(next_y, next_i, y_dot, i_dot, epsilon2, real_dtype)
        updated = self._consolidate(updated, batch=batch, key=key_tensor, position=position, layer=layer, head=head, value=value_tensor)
        result = QiKVState(updated)
        result.validate(self.config)
        if self.config.mode == "compress":
            ring = self._local_ring.setdefault(batch, deque(maxlen=self.config.local_window))
            ring.append(_LocalEntry(batch, tuple(float(item) for item in key_tensor.detach().cpu().tolist()), tuple(float(item) for item in value_tensor.detach().cpu().tolist()), position, layer, head))
        return result

    def query(self, state: QiKVState, key: Any, position: int, layer: int = 0, head: int = 0, *, external_local: Any = None, external_full: Any = None, local_candidate: Any = None, full_candidate: Any = None, batch: int = 0) -> QiKVQueryResult:
        """Retrieve with Qi gating and optional assist-mode external candidates."""

        self._validate_state(state)
        position, layer, head, batch = (_integer_index("position", position), _integer_index("layer", layer), _integer_index("head", head), _integer_index("batch", batch))
        if min(position, layer, head, batch) < 0:
            raise QiKVError("position, layer, head, and batch must be non-negative")
        if head >= self.config.head_count or batch >= state.batch_size:
            raise QiKVError("head or batch is outside configuration/state")
        key_tensor = self._coerce_key(key, device=state.field.device, dtype=state.field.dtype)
        local_external = full_external = None
        local_external_weight = full_external_weight = 0.0
        if self.config.mode == "assist":
            local_payload = external_local if external_local is not None else local_candidate
            full_payload = external_full if external_full is not None else full_candidate
            local_external, local_external_weight, _ = self._candidate(local_payload, state)
            full_external, full_external_weight, _ = self._candidate(full_payload, state)
        field_value, field_available, q, q_max, epsilon2, chi, cross, read_gate = self._field_query(state, key_tensor, position, layer, head, batch)
        exact_value: Tensor | None = None
        if self.config.mode == "compress":
            entry = self._find_local(key_tensor, position=position, layer=layer, head=head, batch=batch)
            if entry is not None:
                exact_value = torch.tensor(entry.value, device=state.field.device, dtype=state.field.dtype)
        zero = torch.zeros(self.config.value_dim, device=state.field.device, dtype=state.field.dtype)
        memory = self.memory_bytes(state)
        if self.config.mode == "assist":
            base = full_external if full_external is not None else local_external
            base_weight = full_external_weight if full_external is not None else local_external_weight
            if base is None:
                # Assist never claims to own full attention: without an
                # external candidate the honest result is unavailable/zero.
                return self._result(zero, False, q, q_max, epsilon2, chi, cross, read_gate, 0.0, 0.0, memory)
            output = base + read_gate * field_value if field_available and read_gate >= self.config.read_threshold else base
            return self._result(self._clip_real_vector(output, self.config.max_value_norm), True, q, q_max, epsilon2, chi, cross, read_gate, base_weight, read_gate if field_available else 0.0, memory, local_available=True, field_available=field_available)
        if exact_value is not None:
            return self._result(exact_value, True, q, q_max, epsilon2, chi, cross, read_gate, 1.0, 0.0, memory, local_available=True, field_available=field_available, exact=True)
        if field_available and read_gate >= self.config.read_threshold:
            return self._result(field_value, True, q, q_max, epsilon2, chi, cross, read_gate, 0.0, read_gate, memory, field_available=True)
        return self._result(zero, False, q, q_max, epsilon2, chi, cross, read_gate, 0.0, 0.0, memory)

    def binding(self, key: Any, position: int, *, layer: int = 0, head: int = 0, scale: int = 0, device: torch.device | None = None, dtype: torch.dtype = torch.complex64) -> Tensor:
        """Return a normalized complex binding with five deterministic tags."""

        position, layer, head, scale = (_integer_index("position", position), _integer_index("layer", layer), _integer_index("head", head), _integer_index("scale", scale))
        if min(position, layer, head, scale) < 0 or head >= self.config.head_count or scale >= self.config.scale_count:
            raise QiKVError("binding index is outside configuration")
        if dtype not in (torch.complex64, torch.complex128):
            raise QiKVError("binding dtype must be complex64 or complex128")
        real_dtype = torch.float64 if dtype == torch.complex128 else torch.float32
        key_vector = self._coerce_key(key, device=device, dtype=real_dtype)
        modes = torch.arange(self.config.mode_count, device=device, dtype=real_dtype) + 1.0
        weights = torch.arange(self.config.key_dim, device=device, dtype=real_dtype) + 1.0
        key_seed = torch.sum(key_vector * weights) / float(self.config.key_dim)
        key_phase = 2.0 * math.pi * key_seed * modes / float(_DEFAULT_PRIMES[0])
        key_wave = torch.complex(torch.cos(key_phase), torch.sin(key_phase))
        key_spectrum = torch.fft.fft(key_wave)
        key_code = torch.complex(torch.cos(torch.angle(key_spectrum)), torch.sin(torch.angle(key_spectrum))) / math.sqrt(float(self.config.mode_count))
        result = key_code * self._tag(modes, float(position), float(_DEFAULT_PRIMES[0]), 1.0, dtype) * self._tag(modes, float(layer), float(_DEFAULT_PRIMES[1]), 1.7, dtype) * self._tag(modes, float(head), float(_DEFAULT_PRIMES[2]), 2.3, dtype) * self._scale_code(scale, device=device, dtype=dtype)
        norm = torch.linalg.vector_norm(result).real.clamp_min(torch.finfo(real_dtype).eps)
        return (result / norm).to(dtype=dtype)

    def _field_query(self, state: QiKVState, key: Tensor, position: int, layer: int, head: int, batch: int) -> tuple[Tensor, bool, float, float, float, float, float, float]:
        decoded, q_values, q_max_values, epsilon_values, active = [], [], [], [], []
        for scale in range(self.config.scale_count):
            bank = state.field[scale, :, batch]
            q, q_max, rho, epsilon2 = self._bank_metrics(bank)
            q_values.append(q)
            q_max_values.append(q_max)
            epsilon_values.append(epsilon2)
            if rho < self.config.energy_floor or q <= 0.0:
                decoded.append(torch.zeros(self.config.value_dim, device=bank.device, dtype=state.field.dtype))
                continue
            d = self._decode_d(bank)
            binding = self.binding(key, position, layer=layer, head=head, scale=scale, device=bank.device, dtype=self._complex_dtype(state.field.dtype))
            unbound = d * torch.conj(binding)
            basis = self._value_basis(scale, device=bank.device, dtype=self._complex_dtype(state.field.dtype))
            value = torch.stack([torch.sum(torch.conj(basis[index]) * unbound).real for index in range(self.config.value_dim)])
            gain = self.config.write_gain
            decoded.append(value / max(gain, 1.0e-12))
            active.append(scale)
        if not active:
            zero = torch.zeros(self.config.value_dim, device=state.field.device, dtype=state.field.dtype)
            return zero, False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        q = float(sum(q_values[index] for index in active) / len(active))
        q_max = float(sum(q_max_values[index] for index in active) / len(active))
        epsilon2 = float(sum(epsilon_values[index] for index in active) / len(active))
        chi_values = [q_values[index] / q_max_values[index] if q_max_values[index] > 0.0 else 0.0 for index in active]
        chi = max(0.0, min(1.0, float(sum(chi_values) / len(chi_values))))
        if len(active) == 1:
            cross = 1.0
        else:
            vectors = []
            for index in active:
                norm = float(torch.linalg.vector_norm(decoded[index]).detach().cpu().item())
                if norm > 1.0e-12:
                    vectors.append(decoded[index] / norm)
            if len(vectors) < 2:
                cross = 0.0 if not vectors else 1.0
            else:
                pair_values = []
                for left in range(len(vectors)):
                    for right in range(left + 1, len(vectors)):
                        cosine = float(torch.sum(vectors[left] * vectors[right]).detach().cpu().item())
                        pair_values.append(max(0.0, min(1.0, 0.5 * (cosine + 1.0))))
                cross = float(sum(pair_values) / len(pair_values)) if pair_values else 0.0
        weights = torch.tensor([q_values[index] for index in active], device=state.field.device, dtype=state.field.dtype)
        combined = torch.sum(torch.stack([decoded[index] for index in active]) * weights[:, None], dim=0) / weights.sum().clamp_min(1.0e-12)
        combined = self._clip_real_vector(combined, self.config.max_value_norm)
        read_gate = max(0.0, min(1.0, chi * cross))
        return combined, read_gate >= self.config.read_threshold, q, q_max, epsilon2, chi, cross, read_gate

    def _consolidate(self, field: Tensor, *, batch: int, key: Tensor, position: int, layer: int, head: int, value: Tensor) -> Tensor:
        for target_scale in range(1, self.config.scale_count):
            source_scale = target_scale - 1
            source_bank, target_bank = field[source_scale, :, batch], field[target_scale, :, batch]
            source_q, source_qmax, source_rho, _ = self._bank_metrics(source_bank)
            target_q, _, target_rho, _ = self._bank_metrics(target_bank)
            source_chi = source_q / source_qmax if source_qmax > 0.0 else 0.0
            source_d, target_d = self._decode_d(source_bank), self._decode_d(target_bank)
            source_norm, target_norm = torch.linalg.vector_norm(source_d).real, torch.linalg.vector_norm(target_d).real
            empty_target = target_rho < self.config.energy_floor
            if empty_target:
                phase_agreement, current_gate = 1.0, 1.0
            else:
                phase = torch.sum(torch.conj(source_d) * target_d).imag / (source_norm * target_norm).clamp_min(1.0e-12)
                phase_agreement = max(0.0, min(1.0, 0.5 * (float(phase.detach().cpu().item()) + 1.0)))
                j_scale = torch.mean(torch.imag(torch.conj(source_d) * target_d)).real
                current_gate = max(0.0, min(1.0, float(j_scale.detach().cpu().item()) / (float(source_norm * target_norm) + 1.0e-12)))
            target_open = 1.0 if empty_target else max(0.0, min(1.0, 1.0 - target_q))
            gate = max(0.0, min(1.0, source_chi * phase_agreement * current_gate * target_open))
            if empty_target:
                gate = source_chi
            if source_rho < self.config.energy_floor or source_q <= 0.0 or gate <= 0.0:
                continue
            if key is None:
                transfer = source_d * self._scale_code_ratio(source_scale, target_scale, device=source_d.device, dtype=self._complex_dtype(field.dtype))
            else:
                binding = self.binding(key, position, layer=layer, head=head, scale=target_scale, device=source_d.device, dtype=self._complex_dtype(field.dtype))
                encoded = self._encode_value(value, scale=target_scale, device=source_d.device, dtype=self._complex_dtype(field.dtype))
                transfer = binding * encoded * float(self.config.mode_count)
            target_y, target_i = self._decode_y_i(target_bank)
            old_target_d = target_y - self.config.phi * target_i
            next_d = self._clip_complex_vector(old_target_d + self.config.write_gain * gate * transfer, self.config.max_field_norm)
            delta = next_d - old_target_d
            next_y, next_i = target_y + 0.5 * delta, target_i - 0.5 * delta / self.config.phi
            y_dot, i_dot = self._clip_complex_vector(next_y - target_y, self.config.max_field_norm), self._clip_complex_vector(next_i - target_i, self.config.max_field_norm)
            epsilon2 = (1.0 - self.config.epsilon_tau) * self._epsilon2(target_bank) + self.config.epsilon_tau * self._epsilon_from_y_i(next_y, next_i) ** 2
            field[target_scale, :, batch] = self._encode_field_bank(next_y, next_i, y_dot, i_dot, epsilon2, field.dtype)
        return field

    def _find_local(self, key: Tensor, *, position: int, layer: int, head: int, batch: int) -> _LocalEntry | None:
        identity = tuple(float(item) for item in key.detach().cpu().tolist())
        for entry in reversed(self._local_ring.get(batch, ())):
            if entry.batch != batch or entry.key_identity != identity or entry.layer != layer or entry.head != head:
                continue
            if 0 <= position - entry.position < self.config.local_window:
                return entry
        return None

    def _candidate(self, candidate: Any, state: QiKVState) -> tuple[Tensor | None, float, bool]:
        if candidate is None:
            return None, 0.0, False
        value, weight, available = candidate, 1.0, True
        if isinstance(candidate, Mapping):
            value = candidate.get("value", candidate.get("values"))
            weight = candidate.get("weight", candidate.get("attention_weight", 1.0))
            available = bool(candidate.get("available", True))
        elif isinstance(candidate, (tuple, list)) and len(candidate) == 2 and isinstance(candidate[1], (int, float)):
            value, weight = candidate
        if value is None or not available:
            return None, 0.0, False
        weight = _unit_interval("candidate weight", weight)
        tensor = self._coerce_value(value, device=state.field.device, dtype=state.field.dtype)
        return self._clip_real_vector(tensor, self.config.max_value_norm), weight, True

    def _result(self, value: Tensor, available: bool, q: float, q_max: float, epsilon2: float, chi: float, cross: float, read_gate: float, local_weight: float, field_weight: float, memory: QiKVByteAccounting, *, local_available: bool = False, field_available: bool = False, exact: bool = False) -> QiKVQueryResult:
        value = self._clip_real_vector(value, self.config.max_value_norm)
        if not available:
            value = torch.zeros_like(value)
        telemetry = (q, q_max, epsilon2, chi, cross, read_gate, local_weight, field_weight)
        if not all(math.isfinite(float(item)) for item in telemetry):
            raise QiKVError("query produced non-finite telemetry")
        return QiKVQueryResult(value, bool(available), max(0.0, min(1.0, float(q))), max(0.0, min(1.0, float(q_max))), max(0.0, min(self.config.max_epsilon2, float(epsilon2))), max(0.0, min(1.0, float(chi))), max(0.0, min(1.0, float(cross))), max(0.0, min(1.0, float(read_gate))), max(0.0, min(1.0, float(local_weight))), max(0.0, min(1.0, float(field_weight))), memory, bool(local_available), bool(field_available), bool(exact))

    def _bank_metrics(self, bank: Tensor) -> tuple[float, float, float, float]:
        y, i = self._decode_y_i(bank)
        e_y = float(torch.mean(torch.abs(y) ** 2).real.detach().cpu().item())
        e_i = float(torch.mean(torch.abs(i) ** 2).real.detach().cpu().item())
        rho = e_y + e_i
        epsilon2 = self._epsilon2(bank)
        q_max = rho * rho / (rho * rho + self.config.phi ** -2)
        q = rho * rho / (rho * rho + self.config.phi ** -2 + epsilon2)
        return max(0.0, min(1.0, q)), max(0.0, min(1.0, q_max)), rho, epsilon2

    def _epsilon2(self, bank: Tensor) -> float:
        values = torch.clamp(bank[8 * self.config.mode_count : 9 * self.config.mode_count], min=0.0)
        return max(0.0, min(self.config.max_epsilon2, float(torch.mean(values).detach().cpu().item())))

    def _epsilon_from_y_i(self, y: Tensor, i: Tensor) -> float:
        e_y = torch.mean(torch.abs(y) ** 2).real
        e_i = torch.mean(torch.abs(i) ** 2).real
        return float((e_y - self.config.phi * e_i).detach().cpu().item())

    def _validate_state(self, state: QiKVState) -> None:
        if not isinstance(state, QiKVState):
            raise QiKVError("state must be QiKVState")
        state.validate(self.config)

    @staticmethod
    def _complex_dtype(dtype: torch.dtype) -> torch.dtype:
        if dtype == torch.float64:
            return torch.complex128
        if dtype == torch.float32:
            return torch.complex64
        raise QiKVError("unsupported real field dtype")

    @staticmethod
    def _coerce_key_raw(key: Any, *, device: torch.device | None, dtype: torch.dtype) -> Tensor:
        if torch.is_tensor(key):
            tensor = key.detach().to(device=device, dtype=dtype).flatten()
        elif isinstance(key, (int, float)) and not isinstance(key, bool):
            tensor = torch.tensor([float(key)], device=device, dtype=dtype)
        elif (isinstance(key, Sequence) and not isinstance(key, (str, bytes, bytearray))) or hasattr(key, "__array__"):
            try:
                tensor = torch.as_tensor(key, device=device, dtype=dtype).flatten()
            except (TypeError, ValueError) as exc:
                raise QiKVError("key must be a finite scalar or vector") from exc
        else:
            raise QiKVError("key must be a finite scalar or vector")
        if tensor.numel() == 0 or not bool(torch.isfinite(tensor).all().item()):
            raise QiKVError("key must be non-empty and finite")
        return tensor

    def _coerce_key(self, key: Any, *, device: torch.device | None, dtype: torch.dtype) -> Tensor:
        tensor = self._coerce_key_raw(key, device=device, dtype=dtype)
        if tensor.numel() == self.config.key_dim:
            return tensor
        if tensor.numel() == 1:
            frequencies = torch.arange(self.config.key_dim, device=tensor.device, dtype=dtype) + 1.0
            seed = tensor.reshape(()) * frequencies
            return torch.sin(seed) + 0.5 * torch.cos(seed * 0.61803398875)
        raise QiKVError(f"key vector must have {self.config.key_dim} components")

    def _coerce_value(self, value: Any, *, device: torch.device | None, dtype: torch.dtype) -> Tensor:
        if torch.is_tensor(value):
            tensor = value.detach().to(device=device, dtype=dtype).flatten()
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if self.config.value_dim != 1:
                raise QiKVError("scalar value is only valid when value_dim is one")
            tensor = torch.tensor([float(value)], device=device, dtype=dtype)
        elif (isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))) or hasattr(value, "__array__"):
            try:
                tensor = torch.as_tensor(value, device=device, dtype=dtype).flatten()
            except (TypeError, ValueError) as exc:
                raise QiKVError("value must be a finite vector") from exc
        else:
            raise QiKVError("value must be a finite vector")
        if tensor.numel() != self.config.value_dim:
            raise QiKVError(f"value vector must have {self.config.value_dim} components")
        if not bool(torch.isfinite(tensor).all().item()):
            raise QiKVError("value must be finite")
        return tensor

    @staticmethod
    def _clip_real_vector(value: Tensor, limit: float) -> Tensor:
        norm = torch.linalg.vector_norm(value)
        scale = torch.clamp(torch.as_tensor(limit, device=value.device, dtype=value.dtype) / norm.clamp_min(1.0e-12), max=1.0)
        return value * scale

    @staticmethod
    def _clip_complex_vector(value: Tensor, limit: float) -> Tensor:
        norm = torch.linalg.vector_norm(value).real
        scale = torch.clamp(torch.as_tensor(limit, device=value.device, dtype=norm.dtype) / norm.clamp_min(1.0e-12), max=1.0)
        return value * scale.to(dtype=value.real.dtype)

    def _encode_value(self, value: Tensor, *, scale: int, device: torch.device, dtype: torch.dtype) -> Tensor:
        basis = self._value_basis(scale, device=device, dtype=dtype)
        encoded = torch.zeros(self.config.mode_count, device=device, dtype=dtype)
        for index in range(self.config.value_dim):
            encoded = encoded + value[index].to(dtype=dtype) * basis[index]
        return encoded

    def _value_basis(self, scale: int, *, device: torch.device, dtype: torch.dtype) -> Tensor:
        real_dtype = torch.float64 if dtype == torch.complex128 else torch.float32
        modes = torch.arange(self.config.mode_count, device=device, dtype=real_dtype)
        rows = []
        stride = 0
        for index in range(self.config.value_dim):
            frequency = (index + 1 + stride) % self.config.mode_count
            phase = 2.0 * math.pi * frequency * modes / float(self.config.mode_count)
            rows.append(torch.complex(torch.cos(phase), torch.sin(phase)).to(dtype=dtype) / math.sqrt(float(self.config.mode_count)))
        return torch.stack(rows)

    @staticmethod
    def _tag(modes: Tensor, value: float, prime: float, coefficient: float, dtype: torch.dtype) -> Tensor:
        real_dtype = torch.float64 if dtype == torch.complex128 else torch.float32
        modes = modes.to(dtype=real_dtype)
        phase = 2.0 * math.pi * (value * coefficient * modes / prime + (value + coefficient) * modes * (modes + 1.0) / (prime * prime))
        return torch.complex(torch.cos(phase), torch.sin(phase)).to(dtype=dtype)

    def _scale_code(self, scale: int, *, device: torch.device | None, dtype: torch.dtype) -> Tensor:
        real_dtype = torch.float64 if dtype == torch.complex128 else torch.float32
        modes = torch.arange(self.config.mode_count, device=device, dtype=real_dtype) + 1.0
        prime = float(_DEFAULT_PRIMES[scale])
        phase = 2.0 * math.pi * ((scale + 1.0) * modes * modes / (prime * prime) + modes / prime)
        return torch.complex(torch.cos(phase), torch.sin(phase)).to(dtype=dtype)

    def _scale_code_ratio(self, source: int, target: int, *, device: torch.device, dtype: torch.dtype) -> Tensor:
        return self._scale_code(target, device=device, dtype=dtype) * torch.conj(self._scale_code(source, device=device, dtype=dtype))

    def _decode_y_i(self, bank: Tensor) -> tuple[Tensor, Tensor]:
        m, dtype = self.config.mode_count, self._complex_dtype(bank.dtype)
        y = bank[0 * m : 1 * m].to(dtype) + 1j * bank[1 * m : 2 * m].to(dtype)
        i = bank[2 * m : 3 * m].to(dtype) + 1j * bank[3 * m : 4 * m].to(dtype)
        return y, i

    def _encode_field_bank(self, y: Tensor, i: Tensor, y_dot: Tensor, i_dot: Tensor, epsilon2: float, dtype: torch.dtype) -> Tensor:
        m = self.config.mode_count
        output = torch.zeros(9 * m, device=y.device, dtype=dtype)
        output[0 * m : 1 * m] = y.real.to(dtype)
        output[1 * m : 2 * m] = y.imag.to(dtype)
        output[2 * m : 3 * m] = i.real.to(dtype)
        output[3 * m : 4 * m] = i.imag.to(dtype)
        output[4 * m : 5 * m] = y_dot.real.to(dtype)
        output[5 * m : 6 * m] = y_dot.imag.to(dtype)
        output[6 * m : 7 * m] = i_dot.real.to(dtype)
        output[7 * m : 8 * m] = i_dot.imag.to(dtype)
        output[8 * m : 9 * m] = max(0.0, min(self.config.max_epsilon2, float(epsilon2)))
        return output

    def _decode_d(self, bank: Tensor) -> Tensor:
        y, i = self._decode_y_i(bank)
        return y - self.config.phi * i


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


def save_field_checkpoint(path: Path | str, memory: QiKVMemory, state: QiKVState) -> str:
    """Persist the canonical Qi field and fixed codebook identity, never the local ring."""

    if not isinstance(memory, QiKVMemory):
        raise QiKVError("memory must be QiKVMemory")
    memory._validate_state(state)
    payload = {
        "schema": QI_KV_STATE_SCHEMA,
        "binding_profile_id": QI_KV_BINDING_PROFILE_ID,
        "codebook_profile_id": QI_KV_BINDING_PROFILE_ID,
        "config_schema": QI_KV_CONFIG_SCHEMA,
        "config": memory.config.to_dict(),
        "config_fingerprint": memory.config_fingerprint,
        "binding_descriptor": memory.codebook_descriptor,
        "binding_fingerprint": memory.codebook_fingerprint,
        "codebook_descriptor": memory.codebook_descriptor,
        "codebook_descriptors": (memory.codebook_descriptor,),
        "codebook_fingerprint": memory.codebook_fingerprint,
        "field": state.field.detach().cpu(),
    }
    target = Path(path)
    _atomic_torch_save(payload, target)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def load_field_checkpoint(path: Path | str, memory: QiKVMemory, *, device: torch.device | str = "cpu", dtype: torch.dtype | None = None) -> QiKVState:
    """Restore only a field payload after exact fixed identity validation."""

    if not isinstance(memory, QiKVMemory):
        raise QiKVError("memory must be QiKVMemory")
    target = Path(path)
    if not target.is_file():
        raise QiKVError(f"QiKV checkpoint does not exist: {target}")
    target_device = torch.device(device)
    try:
        payload = torch.load(target, map_location=target_device, weights_only=True)
    except Exception as exc:
        raise QiKVError(f"QiKV checkpoint cannot be loaded: {type(exc).__name__}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != QI_KV_STATE_SCHEMA:
        raise QiKVError("QiKV checkpoint schema mismatch")
    if payload.get("binding_profile_id") != QI_KV_BINDING_PROFILE_ID:
        raise QiKVError("QiKV checkpoint binding identity mismatch")
    if payload.get("config_schema") != QI_KV_CONFIG_SCHEMA:
        raise QiKVError("QiKV checkpoint configuration schema mismatch")
    loaded_config = QiKVConfig.from_dict(payload.get("config", {}))
    if loaded_config != memory.config or payload.get("config_fingerprint") != memory.config_fingerprint:
        raise QiKVError("QiKV checkpoint belongs to a different fixed configuration")
    if payload.get("binding_descriptor") != memory.codebook_descriptor or payload.get("binding_fingerprint") != memory.codebook_fingerprint:
        raise QiKVError("QiKV checkpoint binding/codebook identity mismatch")
    if payload.get("codebook_profile_id") != QI_KV_BINDING_PROFILE_ID:
        raise QiKVError("QiKV checkpoint codebook profile mismatch")
    if payload.get("codebook_descriptor") != memory.codebook_descriptor or payload.get("codebook_descriptors") != (memory.codebook_descriptor,) or payload.get("codebook_fingerprint") != memory.codebook_fingerprint:
        raise QiKVError("QiKV checkpoint codebook identity mismatch")
    field = payload.get("field")
    if not torch.is_tensor(field):
        raise QiKVError("QiKV checkpoint is missing its sole adaptive field tensor")
    target_dtype = dtype or field.dtype
    state = QiKVState(field.to(device=target_device, dtype=target_dtype))
    state.validate(memory.config, device=target_device, dtype=target_dtype)
    # Loading a field-only artifact never restores any ephemeral exact cache.
    memory.reset_local_ring()
    return state


__all__ = ["QI_KV_BINDING_PROFILE_ID", "QI_KV_CONFIG_SCHEMA", "QI_KV_STATE_SCHEMA", "QiKVByteAccounting", "QiKVConfig", "QiKVError", "QiKVMemory", "QiKVQueryResult", "QiKVState", "load_field_checkpoint", "save_field_checkpoint"]
