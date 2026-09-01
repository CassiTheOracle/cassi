"""CassiFI W14A CPU/Torch backend contract.

The backend owns device selection, deterministic controls, bounded preflight,
canonical state copies, and receipts.  Field evolution remains in
``cassi_qi_field``; this module never reimplements the field law.
"""

from __future__ import annotations

import hashlib
import math
import platform
import time
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, Sequence

import torch

from cassi_qi_field import (
    QiFieldState,
    QiFlowStateV3,
    dump_v3_state_bytes,
    load_v3_state_bytes,
    transition_v3_transport,
)
from cassi_qi_profile import QiFlowProfile, canonical_hash, finite_float, validate_profile


RUNTIME_CONFIG_SCHEMA = "cassi.qi-flow-runtime-config.v1"
BACKEND_IDENTITY_SCHEMA = "cassi.qi-flow-backend-identity.v1"
BACKEND_CAPABILITY_SCHEMA = "cassi.qi-flow-backend-capability.v1"
BACKEND_CAPACITY_SCHEMA = "cassi.qi-flow-backend-capacity.v1"
BACKEND_MEMORY_SCHEMA = "cassi.qi-flow-backend-memory.v1"
BACKEND_OPERATOR_SCHEMA = "cassi.qi-flow-backend-operator.v1"
BACKEND_PROBE_SCHEMA = "cassi.qi-flow-backend-probe.v1"
FIXED_OPERATOR_ID = "fixed-affine-scale-v1"
ADVANCE_OPERATOR_ID = "backend-additive-advance-v1"
FIXED_OPERATOR_SCALE = 0.5
_ZERO_SHA256 = "0" * 64
PARITY_TERM_ORDER = ("current", "momentum", "work", "topology", "receipt", "state")
_PARITY_TERM_ORDER = PARITY_TERM_ORDER
_PARITY_TERM_SET = frozenset(_PARITY_TERM_ORDER)
_TOLERANCE_KEYS = frozenset({"scalar", "field", "current", "work", "decision"})
_RUNTIME_CONFIG_KEYS = frozenset(
    {
        "schema",
        "profile_path",
        "device",
        "dtype",
        "cpu_threads",
        "interop_threads",
        "deterministic_algorithms",
        "same_backend_exact_replay",
        "cross_backend_tolerances",
        "max_sessions",
        "max_batch",
        "max_candidates",
        "max_packet_bytes",
        "max_queue_events",
        "latency_budget",
        "working_memory_budget",
        "config_sha256",
    }
)


class QiBackendError(RuntimeError):
    """Base class for fail-closed backend errors."""


class QiBackendConfigurationError(QiBackendError, ValueError):
    """The explicit profile/config/device contract is inconsistent."""


class QiBackendUnavailable(QiBackendError):
    """The explicitly requested device or adapter is unavailable."""


class QiBackendCapacityError(QiBackendError, ValueError):
    """A declared memory, batch, or candidate bound rejects the request."""


class QiBackendSerializationError(QiBackendError, ValueError):
    """Canonical state serialization or restore failed."""


class QiBackendExecutionError(QiBackendError):
    """An operator or transaction failed without a semantic fallback."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


def _sha(payload: Mapping[str, Any], domain: str) -> str:
    try:
        return str(canonical_hash(_plain(payload), domain))
    except Exception as exc:
        raise QiBackendConfigurationError(
            f"canonical backend identity failed: {type(exc).__name__}: {exc}"
        ) from exc


def _require_int(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise QiBackendConfigurationError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _require_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise QiBackendConfigurationError(f"{name} must be a boolean")
    return bool(value)


def _dtype(value: Any) -> tuple[torch.dtype, str]:
    if value is torch.float32 or value == torch.float32 or value == "float32":
        return torch.float32, "float32"
    if value is torch.float64 or value == torch.float64 or value == "float64":
        return torch.float64, "float64"
    raise QiBackendConfigurationError("dtype must be float32 or float64")


def _device(value: Any) -> tuple[torch.device, str]:
    if isinstance(value, torch.device):
        selected = value
    elif isinstance(value, str):
        raw = value.strip().lower()
        if raw == "rocm":
            raw = "cuda"
        try:
            selected = torch.device(raw)
        except Exception as exc:
            raise QiBackendConfigurationError(f"invalid backend device {value!r}") from exc
    else:
        raise QiBackendConfigurationError("device must be cpu, cuda, or rocm")
    if selected.type not in {"cpu", "cuda"}:
        raise QiBackendConfigurationError("only cpu and Torch cuda/ROCm devices are supported")
    if selected.type == "cpu":
        return torch.device("cpu"), "cpu"
    index = 0 if selected.index is None else int(selected.index)
    if index < 0:
        raise QiBackendConfigurationError("cuda device index must be nonnegative")
    return torch.device("cuda", index), f"cuda:{index}"


def _profile_device(profile: QiFlowProfile) -> str:
    try:
        value = profile.payload["backend_contract"]["device"]
    except Exception as exc:
        raise QiBackendConfigurationError("profile backend device is missing") from exc
    if value not in {"cpu", "cuda"}:
        raise QiBackendConfigurationError("profile backend device must be cpu or cuda")
    return str(value)


def _profile_dtype(profile: QiFlowProfile) -> str:
    try:
        field_value = profile.payload["field"]["dtype"]
        backend_value = profile.payload["backend_contract"]["dtype"]
    except Exception as exc:
        raise QiBackendConfigurationError("profile dtype is missing") from exc
    if field_value != backend_value or field_value not in {"float32", "float64"}:
        raise QiBackendConfigurationError("profile field/backend dtype contract is inconsistent")
    return str(field_value)


def _profile_layout(profile: QiFlowProfile) -> tuple[int, int, tuple[int, ...], int]:
    try:
        field = profile.payload["field"]
        scales = _require_int(field["scale_count"], "profile scale_count", 1)
        modes = _require_int(field["mode_count"], "profile mode_count", 1)
        components = _require_int(field["component_count"], "profile component_count", 1)
        sites = tuple(field["active_site_counts"])
        batch_limit = _require_int(field["batch_limit"], "profile batch_limit", 1)
    except QiBackendConfigurationError:
        raise
    except Exception as exc:
        raise QiBackendConfigurationError("profile field layout is incomplete") from exc
    if components != 9:
        raise QiBackendConfigurationError("backend requires the [S,9M,B] state layout")
    if len(sites) != scales or any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in sites):
        raise QiBackendConfigurationError("profile active_site_counts is invalid")
    return scales, components * modes, tuple(int(item) for item in sites), batch_limit


def _profile_capacity(profile: QiFlowProfile) -> dict[str, int]:
    try:
        source = profile.payload["capacity"]
        result = {
            key: _require_int(source[key], f"profile capacity {key}")
            for key in (
                "max_state_bytes",
                "max_checkpoint_bytes",
                "max_receipt_bytes",
                "max_active_sites",
                "max_batch_lanes",
            )
        }
    except QiBackendConfigurationError:
        raise
    except Exception as exc:
        raise QiBackendConfigurationError("profile capacity is incomplete") from exc
    try:
        result["max_candidates"] = _require_int(profile.payload["action"]["max_candidates"], "profile max_candidates")
    except Exception:
        result["max_candidates"] = 8
    return result


def _interval(value: Any, name: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or set(value) != {"lower", "upper"}:
        raise QiBackendConfigurationError(f"{name} must contain exactly lower and upper")
    result: dict[str, str] = {}
    for bound in ("lower", "upper"):
        raw = value[bound]
        if not isinstance(raw, str) or ":" not in raw:
            raise QiBackendConfigurationError(f"{name}.{bound} must be finite_bits")
        prefix, bits = raw.split(":", 1)
        expected = 8 if prefix == "f32" else 16 if prefix == "f64" else 0
        if expected == 0 or len(bits) != expected:
            raise QiBackendConfigurationError(f"{name}.{bound} must be a finite f32/f64 bit string")
        try:
            integer = int(bits, 16)
        except ValueError as exc:
            raise QiBackendConfigurationError(f"{name}.{bound} has invalid hexadecimal bits") from exc
        exponent_mask = 0x7F800000 if prefix == "f32" else 0x7FF0000000000000
        if integer & exponent_mask == exponent_mask:
            raise QiBackendConfigurationError(f"{name}.{bound} must be finite")
        result[bound] = raw
    return MappingProxyType(result)


def _zero_tolerances() -> Mapping[str, Mapping[str, str]]:
    zero = {"lower": "f64:0000000000000000", "upper": "f64:0000000000000000"}
    return MappingProxyType({key: MappingProxyType(dict(zero)) for key in _TOLERANCE_KEYS})


@dataclass(frozen=True, slots=True)
class QiRuntimeConfig:
    """The exact process-local v1 runtime configuration."""

    schema: str = RUNTIME_CONFIG_SCHEMA
    profile_path: str = "explicit-profile"
    device: str = "cpu"
    dtype: str | torch.dtype = "float64"
    cpu_threads: int = 0
    interop_threads: int = 0
    deterministic_algorithms: bool = True
    same_backend_exact_replay: bool = True
    cross_backend_tolerances: Mapping[str, Mapping[str, str]] = _zero_tolerances()
    max_sessions: int = 1
    max_batch: int = 4
    max_candidates: int = 8
    max_packet_bytes: int = 65536
    max_queue_events: int = 1024
    latency_budget: Mapping[str, int] = MappingProxyType({"n": 0, "d": 1})
    working_memory_budget: int = 1 << 20

    def __post_init__(self) -> None:
        if self.schema != RUNTIME_CONFIG_SCHEMA:
            raise QiBackendConfigurationError("runtime config schema is not v1")
        if not isinstance(self.profile_path, str) or not 1 <= len(self.profile_path) <= 2048:
            raise QiBackendConfigurationError("profile_path must be a bounded nonempty string")
        device_obj, _ = _device(self.device)
        object.__setattr__(self, "device", device_obj.type)
        _, dtype_name = _dtype(self.dtype)
        object.__setattr__(self, "dtype", dtype_name)
        for name in (
            "cpu_threads",
            "interop_threads",
            "max_sessions",
            "max_batch",
            "max_candidates",
            "max_packet_bytes",
            "max_queue_events",
            "working_memory_budget",
        ):
            object.__setattr__(self, name, _require_int(getattr(self, name), name))
        object.__setattr__(self, "deterministic_algorithms", _require_bool(self.deterministic_algorithms, "deterministic_algorithms"))
        object.__setattr__(self, "same_backend_exact_replay", _require_bool(self.same_backend_exact_replay, "same_backend_exact_replay"))
        if not isinstance(self.cross_backend_tolerances, Mapping) or set(self.cross_backend_tolerances) != _TOLERANCE_KEYS:
            raise QiBackendConfigurationError("cross_backend_tolerances keys are not exact")
        object.__setattr__(
            self,
            "cross_backend_tolerances",
            MappingProxyType({key: _interval(self.cross_backend_tolerances[key], f"cross_backend_tolerances.{key}") for key in sorted(_TOLERANCE_KEYS)}),
        )
        if not isinstance(self.latency_budget, Mapping) or set(self.latency_budget) != {"n", "d"}:
            raise QiBackendConfigurationError("latency_budget keys are not exact")
        object.__setattr__(
            self,
            "latency_budget",
            MappingProxyType({"n": _require_int(self.latency_budget["n"], "latency_budget.n"), "d": _require_int(self.latency_budget["d"], "latency_budget.d", 1)}),
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "profile_path": self.profile_path,
            "device": self.device,
            "dtype": str(self.dtype),
            "cpu_threads": self.cpu_threads,
            "interop_threads": self.interop_threads,
            "deterministic_algorithms": self.deterministic_algorithms,
            "same_backend_exact_replay": self.same_backend_exact_replay,
            "cross_backend_tolerances": _plain(self.cross_backend_tolerances),
            "max_sessions": self.max_sessions,
            "max_batch": self.max_batch,
            "max_candidates": self.max_candidates,
            "max_packet_bytes": self.max_packet_bytes,
            "max_queue_events": self.max_queue_events,
            "latency_budget": _plain(self.latency_budget),
            "working_memory_budget": self.working_memory_budget,
        }
        payload["config_sha256"] = _sha(payload, RUNTIME_CONFIG_SCHEMA)
        return payload

    @property
    def config_sha256(self) -> str:
        return str(self.to_payload()["config_sha256"])

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QiRuntimeConfig":
        if not isinstance(payload, Mapping) or set(payload) != _RUNTIME_CONFIG_KEYS:
            raise QiBackendConfigurationError("runtime config fields are not exact")
        supplied = payload["config_sha256"]
        if not isinstance(supplied, str) or len(supplied) != 64 or any(char not in "0123456789abcdef" for char in supplied):
            raise QiBackendConfigurationError("config_sha256 is not a lowercase sha256")
        unsigned = {key: _plain(payload[key]) for key in _RUNTIME_CONFIG_KEYS if key != "config_sha256"}
        if supplied != _sha(unsigned, RUNTIME_CONFIG_SCHEMA):
            raise QiBackendConfigurationError("runtime config hash mismatch")
        return cls(**{key: payload[key] for key in _RUNTIME_CONFIG_KEYS if key != "config_sha256"})


@dataclass(frozen=True, slots=True)
class QiCapacityProfile:
    """Versioned bounded limits used by preflight."""

    max_state_bytes: int
    max_checkpoint_bytes: int
    max_receipt_bytes: int
    max_active_sites: int
    max_batch_lanes: int
    max_candidates: int
    working_memory_budget: int

    def __post_init__(self) -> None:
        for name in (
            "max_state_bytes",
            "max_checkpoint_bytes",
            "max_receipt_bytes",
            "max_active_sites",
            "max_batch_lanes",
            "max_candidates",
            "working_memory_budget",
        ):
            object.__setattr__(self, name, _require_int(getattr(self, name), name))

    @classmethod
    def from_profile(cls, profile: QiFlowProfile, *, working_memory_budget: int | None = None, max_batch_lanes: int | None = None, max_candidates: int | None = None) -> "QiCapacityProfile":
        values = _profile_capacity(profile)
        return cls(
            max_state_bytes=values["max_state_bytes"],
            max_checkpoint_bytes=values["max_checkpoint_bytes"],
            max_receipt_bytes=values["max_receipt_bytes"],
            max_active_sites=values["max_active_sites"],
            max_batch_lanes=values["max_batch_lanes"] if max_batch_lanes is None else _require_int(max_batch_lanes, "max_batch_lanes"),
            max_candidates=values["max_candidates"] if max_candidates is None else _require_int(max_candidates, "max_candidates"),
            working_memory_budget=values["max_state_bytes"] if working_memory_budget is None else _require_int(working_memory_budget, "working_memory_budget"),
        )

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "schema": BACKEND_CAPACITY_SCHEMA,
            "max_state_bytes": self.max_state_bytes,
            "max_checkpoint_bytes": self.max_checkpoint_bytes,
            "max_receipt_bytes": self.max_receipt_bytes,
            "max_active_sites": self.max_active_sites,
            "max_batch_lanes": self.max_batch_lanes,
            "max_candidates": self.max_candidates,
            "working_memory_budget": self.working_memory_budget,
        }
        payload["capacity_sha256"] = _sha(payload, BACKEND_CAPACITY_SCHEMA)
        return payload

    @property
    def capacity_sha256(self) -> str:
        return str(self.to_payload()["capacity_sha256"])


@dataclass(frozen=True, slots=True)
class QiMemoryPreflight:
    batch: int
    candidates: int
    scalar_bytes: int
    state_bytes: int
    candidate_bytes: int
    coordinate_bytes: int
    prepared_bytes: int
    required_bytes: int
    working_memory_budget: int

    @property
    def peak_working_bytes(self) -> int:
        return self.required_bytes


def preflight_memory(
    profile: QiFlowProfile,
    batch: int,
    candidates: int,
    *,
    dtype: str | torch.dtype | None = None,
    capacity: QiCapacityProfile | None = None,
) -> QiMemoryPreflight:
    try:
        selected = validate_profile(profile)
    except Exception as exc:
        raise QiBackendConfigurationError("preflight requires a validated profile") from exc
    lanes = _require_int(batch, "batch", 1)
    branches = _require_int(candidates, "candidates", 1)
    scalar_dtype, dtype_name = _dtype(_profile_dtype(selected) if dtype is None else dtype)
    del scalar_dtype
    scalar_bytes = 4 if dtype_name == "float32" else 8
    scales, packed_width, sites, profile_batch_limit = _profile_layout(selected)
    limits = capacity or QiCapacityProfile.from_profile(selected)
    if lanes > profile_batch_limit or lanes > limits.max_batch_lanes:
        raise QiBackendCapacityError("batch exceeds the profile/backend batch limit")
    if branches > limits.max_candidates:
        raise QiBackendCapacityError("candidate count exceeds the profile/backend candidate limit")
    if sum(sites) > limits.max_active_sites:
        raise QiBackendCapacityError("active-site count exceeds the backend capacity limit")
    state_bytes = scales * packed_width * lanes * scalar_bytes
    candidate_bytes = state_bytes * branches
    coordinate_bytes = 8 * lanes * scalar_bytes * sum(sites)
    # The fixed probe has one immutable scalar coefficient; field-law caches
    # are supplied by the owning W6/W7 operators and are not invented here.
    prepared_bytes = scalar_bytes
    required = state_bytes + candidate_bytes + coordinate_bytes + prepared_bytes
    if state_bytes > limits.max_state_bytes:
        raise QiBackendCapacityError("state exceeds max_state_bytes")
    if required > limits.working_memory_budget:
        raise QiBackendCapacityError("preflight exceeds working_memory_budget")
    return QiMemoryPreflight(lanes, branches, scalar_bytes, state_bytes, candidate_bytes, coordinate_bytes, prepared_bytes, required, limits.working_memory_budget)


@dataclass(frozen=True, slots=True)
class QiBackendCapabilities:
    """Immutable result of the explicit capability probe."""

    available: bool
    device: str
    device_type: str
    device_index: int | None
    device_name: str
    pci_identity: str | None
    torch_version: str
    rocm_version: str | None
    supports_float32: bool
    supports_float64: bool
    deterministic_algorithms: bool
    probe_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "available", _require_bool(self.available, "capability.available"))
        if self.device_type not in {"cpu", "cuda"}:
            raise QiBackendConfigurationError("capability.device_type must be cpu/cuda")
        if not isinstance(self.device_name, str) or not self.device_name:
            raise QiBackendConfigurationError("capability.device_name must be nonempty")
        if self.device_index is not None:
            object.__setattr__(self, "device_index", _require_int(self.device_index, "capability.device_index"))
        object.__setattr__(self, "supports_float32", _require_bool(self.supports_float32, "capability.supports_float32"))
        object.__setattr__(self, "supports_float64", _require_bool(self.supports_float64, "capability.supports_float64"))
        object.__setattr__(self, "deterministic_algorithms", _require_bool(self.deterministic_algorithms, "capability.deterministic_algorithms"))

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": BACKEND_CAPABILITY_SCHEMA,
            "available": self.available,
            "device": self.device,
            "device_type": self.device_type,
            "device_index": self.device_index,
            "device_name": self.device_name,
            "pci_identity": self.pci_identity,
            "torch_version": self.torch_version,
            "rocm_version": self.rocm_version,
            "supports_float32": self.supports_float32,
            "supports_float64": self.supports_float64,
            "deterministic_algorithms": self.deterministic_algorithms,
            "probe_id": self.probe_id,
        }
        payload["capability_sha256"] = _sha(payload, BACKEND_CAPABILITY_SCHEMA)
        return payload

    @property
    def capability_sha256(self) -> str:
        return str(self.to_payload()["capability_sha256"])

    @classmethod
    def from_probe(cls, device: torch.device, result: Any, *, deterministic_algorithms: bool) -> "QiBackendCapabilities":
        if isinstance(result, cls):
            return result
        if isinstance(result, bool):
            result = {"available": result}
        if not isinstance(result, Mapping):
            raise QiBackendConfigurationError("capability probe must return QiBackendCapabilities, mapping, or bool")
        available = result.get("available", False)
        index = device.index if device.type == "cuda" else None
        defaults = {
            "device": str(device),
            "device_type": device.type,
            "device_index": index,
            "device_name": platform.processor() or device.type,
            "pci_identity": None,
            "torch_version": str(torch.__version__),
            "rocm_version": getattr(torch.version, "hip", None),
            "supports_float32": bool(available),
            "supports_float64": device.type == "cpu" or bool(available),
            "deterministic_algorithms": deterministic_algorithms,
            "probe_id": "injected-capability-probe-v1",
        }
        defaults.update({key: result[key] for key in defaults if key in result})
        defaults["available"] = bool(available)
        return cls(**defaults)


def default_capability_probe(device: torch.device) -> QiBackendCapabilities:
    if device.type == "cpu":
        return QiBackendCapabilities(True, "cpu", "cpu", None, platform.processor() or "cpu", None, str(torch.__version__), getattr(torch.version, "hip", None), True, True, True, "torch-capability-probe-v1")
    try:
        index = 0 if device.index is None else int(device.index)
        available = bool(torch.cuda.is_available()) and index < int(torch.cuda.device_count())
        name = str(torch.cuda.get_device_name(index)) if available else "unavailable"
        pci = None
        if available:
            try:
                pci = str(torch.cuda.get_device_properties(index).pci_bus_id)
            except Exception:
                pci = None
        return QiBackendCapabilities(available, str(device), "cuda", index, name, pci, str(torch.__version__), getattr(torch.version, "hip", None), available, available, True, "torch-capability-probe-v1")
    except Exception as exc:
        raise QiBackendUnavailable(f"GPU capability probe failed: {type(exc).__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True)
class QiBackendIdentity:
    backend: str
    adapter: str
    device: str
    device_type: str
    device_index: int | None
    device_name: str
    pci_identity: str | None
    torch_version: str
    rocm_version: str | None
    dtype: str
    seed: int
    deterministic_algorithms: bool
    same_backend_exact_replay: bool
    cpu_threads: int
    interop_threads: int
    fft_identity: str
    prepared_operator_sha256: str
    fallback_count: int
    synchronization_policy: str
    profile_sha256: str
    capability_sha256: str

    def __post_init__(self) -> None:
        if self.backend != "torch" or self.device_type not in {"cpu", "cuda"}:
            raise QiBackendConfigurationError("backend identity is not Torch CPU/cuda")
        _, dtype_name = _dtype(self.dtype)
        object.__setattr__(self, "dtype", dtype_name)
        object.__setattr__(self, "seed", _require_int(self.seed, "seed"))
        object.__setattr__(self, "fallback_count", _require_int(self.fallback_count, "fallback_count"))
        if self.fallback_count != 0:
            raise QiBackendConfigurationError("backend fallback count must be zero")

    def _unsigned(self) -> dict[str, Any]:
        return {
            "schema": BACKEND_IDENTITY_SCHEMA,
            "backend": self.backend,
            "adapter": self.adapter,
            "device": self.device,
            "device_type": self.device_type,
            "device_index": self.device_index,
            "device_name": self.device_name,
            "pci_identity": self.pci_identity,
            "torch_version": self.torch_version,
            "rocm_version": self.rocm_version,
            "dtype": self.dtype,
            "seed": self.seed,
            "deterministic_algorithms": self.deterministic_algorithms,
            "same_backend_exact_replay": self.same_backend_exact_replay,
            "cpu_threads": self.cpu_threads,
            "interop_threads": self.interop_threads,
            "fft_identity": self.fft_identity,
            "prepared_operator_sha256": self.prepared_operator_sha256,
            "fallback_count": self.fallback_count,
            "synchronization_policy": self.synchronization_policy,
            "profile_sha256": self.profile_sha256,
            "capability_sha256": self.capability_sha256,
        }

    @property
    def content_sha256(self) -> str:
        return _sha(self._unsigned(), BACKEND_IDENTITY_SCHEMA)

    def to_payload(self) -> dict[str, Any]:
        payload = self._unsigned()
        payload["identity_sha256"] = self.content_sha256
        return payload


@dataclass(frozen=True, slots=True)
class QiPreparedOperators:
    """Immutable handle for one profile/backend/dtype/batch operator cache."""

    profile_sha256: str
    device: str
    dtype: str
    batch: int
    operator_id: str
    operator_sha256: str
    allocation_bytes: int
    operator_cache_sha256: str = ""
    backend_identity_sha256: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.profile_sha256, str) or len(self.profile_sha256) != 64 or any(char not in "0123456789abcdef" for char in self.profile_sha256):
            raise QiBackendConfigurationError("prepared profile identity is invalid")
        if not isinstance(self.device, str) or not self.device:
            raise QiBackendConfigurationError("prepared device identity is invalid")
        if not isinstance(self.operator_id, str) or not self.operator_id:
            raise QiBackendConfigurationError("prepared operator identity is invalid")
        _, dtype_name = _dtype(self.dtype)
        object.__setattr__(self, "dtype", dtype_name)
        object.__setattr__(self, "batch", _require_int(self.batch, "prepared batch", 1))
        object.__setattr__(self, "allocation_bytes", _require_int(self.allocation_bytes, "prepared allocation_bytes"))
        for name in ("operator_sha256", "operator_cache_sha256", "backend_identity_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise QiBackendConfigurationError(f"prepared {name} is invalid")

    def _unsigned(self) -> dict[str, Any]:
        return {
            "schema": BACKEND_OPERATOR_SCHEMA,
            "profile_sha256": self.profile_sha256,
            "device": self.device,
            "dtype": self.dtype,
            "batch": self.batch,
            "operator_id": self.operator_id,
            "operator_sha256": self.operator_sha256,
            "allocation_bytes": self.allocation_bytes,
            "operator_cache_sha256": self.operator_cache_sha256,
            "backend_identity_sha256": self.backend_identity_sha256,
        }

    @property
    def prepared_sha256(self) -> str:
        return _sha(self._unsigned(), BACKEND_OPERATOR_SCHEMA)

    def to_payload(self) -> dict[str, Any]:
        payload = self._unsigned()
        payload["prepared_sha256"] = self.prepared_sha256
        return payload


@dataclass(frozen=True, slots=True)
class QiDriveBundle:
    """Immutable transaction input supplied by the flow layer."""

    delta: torch.Tensor | float | int | None = None
    transaction_id: str = "transaction-0"
    duration_s: float | None = None
    source: Any | None = None
    operator: Callable[[torch.Tensor], torch.Tensor] | None = None
    geometry_profile: Any | None = None
    transport_profile: Any | None = None
    profile: QiFlowProfile | None = None
    prepared: QiPreparedOperators | None = None

    def __post_init__(self) -> None:
        if torch.is_tensor(self.delta):
            if self.delta.requires_grad or self.delta.grad is not None:
                raise QiBackendConfigurationError("drive tensor cannot carry autograd state")
            object.__setattr__(self, "delta", self.delta.detach().clone().contiguous())
        elif self.delta is not None and (isinstance(self.delta, bool) or not isinstance(self.delta, (int, float))):
            raise QiBackendConfigurationError("drive delta must be a scalar or tensor")
        if not isinstance(self.transaction_id, str) or not self.transaction_id:
            raise QiBackendConfigurationError("transaction_id must be nonempty")
        if self.duration_s is not None and (not isinstance(self.duration_s, (int, float)) or not math.isfinite(float(self.duration_s)) or float(self.duration_s) < 0):
            raise QiBackendConfigurationError("duration_s must be finite and nonnegative")
        if self.operator is not None and not callable(self.operator):
            raise QiBackendConfigurationError("drive operator must be callable")
        if self.prepared is not None and not isinstance(self.prepared, QiPreparedOperators):
            raise QiBackendConfigurationError("prepared must be QiPreparedOperators")




@dataclass(frozen=True, slots=True)
class QiFlowStep:
    predecessor: QiFlowStateV3
    candidate: QiFlowStateV3 | None
    committable: bool
    transaction_id: str
    operator_id: str
    receipt: Mapping[str, Any]
    diagnostics: Any | None = None
    ledger: Any | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "committable", _require_bool(self.committable, "step.committable"))
        object.__setattr__(self, "receipt", _freeze(self.receipt))
        if self.committable and self.candidate is None:
            raise QiBackendExecutionError("committable step has no candidate")
        if self.committable and self.failure_reason is not None:
            raise QiBackendExecutionError("committable step has a failure reason")

    @property
    def step_sha256(self) -> str:
        return _sha(_plain(self.receipt), "cassi.qi-flow-backend-step")


@dataclass(frozen=True, slots=True)
class QiCandidateBatch:
    predecessor: QiFlowStateV3
    candidates: tuple[QiFlowStateV3, ...]
    transaction_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "transaction_ids", tuple(self.transaction_ids))
        if not self.candidates or len(self.candidates) != len(self.transaction_ids):
            raise QiBackendExecutionError("candidate batch cardinality is invalid")


@dataclass(frozen=True, slots=True)
class QiBackendMemoryReceipt:
    device: str
    dtype: str
    state_bytes: int
    peak_working_bytes: int
    allocated_bytes: int
    reserved_bytes: int
    allocation_count: int
    copy_count: int
    synchronization_count: int
    op_count: int
    wall_time_ns: int
    measurement: str
    prepared_cache_entries: int = 0
    prepared_cache_hits: int = 0
    prepared_cache_misses: int = 0

    def __post_init__(self) -> None:
        _, dtype_name = _dtype(self.dtype)
        object.__setattr__(self, "dtype", dtype_name)
        for name in (
            "state_bytes",
            "peak_working_bytes",
            "allocated_bytes",
            "reserved_bytes",
            "allocation_count",
            "copy_count",
            "synchronization_count",
            "op_count",
            "wall_time_ns",
            "prepared_cache_entries",
            "prepared_cache_hits",
            "prepared_cache_misses",
        ):
            object.__setattr__(self, name, _require_int(getattr(self, name), name))

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "schema": BACKEND_MEMORY_SCHEMA,
            "device": self.device,
            "dtype": self.dtype,
            "state_bytes": self.state_bytes,
            "peak_working_bytes": self.peak_working_bytes,
            "allocated_bytes": self.allocated_bytes,
            "reserved_bytes": self.reserved_bytes,
            "allocation_count": self.allocation_count,
            "copy_count": self.copy_count,
            "synchronization_count": self.synchronization_count,
            "op_count": self.op_count,
            "wall_time_ns": self.wall_time_ns,
            "measurement": self.measurement,
            "prepared_cache_entries": self.prepared_cache_entries,
            "prepared_cache_hits": self.prepared_cache_hits,
            "prepared_cache_misses": self.prepared_cache_misses,
        }
        payload["receipt_sha256"] = _sha(payload, BACKEND_MEMORY_SCHEMA)
        return payload


@dataclass(frozen=True, slots=True)
class QiProbeReceipt:
    backend_identity_sha256: str
    capability_sha256: str
    profile_sha256: str
    operator_id: str
    operator_sha256: str
    executed: bool
    parity_status: str
    value_interval: tuple[float, float]
    state_hashes: Mapping[str, str]
    memory_high_water_bytes: int
    op_count: int
    wall_time_ns: int
    allocations: int
    copies: int
    synchronizations: int
    prepared_sha256: str | None = None
    operator_cache_sha256: str | None = None

    def __post_init__(self) -> None:
        for name in ("backend_identity_sha256", "capability_sha256", "profile_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise QiBackendConfigurationError(f"probe {name} is invalid")
        if self.parity_status not in {"NOT_RUN", "PASS", "FAIL", "ABSTAIN"}:
            raise QiBackendConfigurationError("probe parity status is invalid")
        if len(self.value_interval) != 2 or any(not math.isfinite(float(item)) for item in self.value_interval) or self.value_interval[0] > self.value_interval[1]:
            raise QiBackendConfigurationError("probe value interval is invalid")
        object.__setattr__(self, "state_hashes", _freeze(self.state_hashes))
        for name in ("memory_high_water_bytes", "op_count", "wall_time_ns", "allocations", "copies", "synchronizations"):
            object.__setattr__(self, name, _require_int(getattr(self, name), name))
        if not self.executed and self.parity_status != "NOT_RUN":
            raise QiBackendConfigurationError("unexecuted probe cannot claim parity")
        for name in ("prepared_sha256", "operator_cache_sha256"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or len(value) != 64):
                raise QiBackendConfigurationError(f"probe {name} is invalid")

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "schema": BACKEND_PROBE_SCHEMA,
            "backend_identity_sha256": self.backend_identity_sha256,
            "capability_sha256": self.capability_sha256,
            "profile_sha256": self.profile_sha256,
            "operator_id": self.operator_id,
            "operator_sha256": self.operator_sha256,
            "executed": self.executed,
            "parity_status": self.parity_status,
            "value_interval": list(self.value_interval),
            "state_hashes": _plain(self.state_hashes),
            "memory_high_water_bytes": self.memory_high_water_bytes,
            "op_count": self.op_count,
            "wall_time_ns": self.wall_time_ns,
            "allocations": self.allocations,
            "copies": self.copies,
            "synchronizations": self.synchronizations,
            "prepared_sha256": self.prepared_sha256,
            "operator_cache_sha256": self.operator_cache_sha256,
        }
        payload["receipt_sha256"] = _sha(payload, BACKEND_PROBE_SCHEMA)
        return payload


def _operator_cache_identity(
    profile: QiFlowProfile,
    *,
    device: str,
    dtype: str,
    batch: int,
    operator_id: str,
    operator_sha256: str,
    backend_identity_sha256: str,
) -> str:
    """Bind a prepared cache entry to the frozen W6B semantic roots."""

    semantic = getattr(profile, "semantic_subhashes", {})
    payload = {
        "schema": BACKEND_OPERATOR_SCHEMA,
        "profile_sha256": profile.profile_sha256,
        "state_contract_sha256": str(semantic.get("state_contract_sha256", "")),
        "backend_capacity_sha256": str(semantic.get("backend_capacity_sha256", "")),
        "backend_sha256": profile.backend_sha256,
        "device": device,
        "dtype": dtype,
        "batch": batch,
        "operator_id": operator_id,
        "operator_sha256": operator_sha256,
        "backend_identity_sha256": backend_identity_sha256,
    }
    if not payload["state_contract_sha256"] or not payload["backend_capacity_sha256"]:
        raise QiBackendConfigurationError("profile semantic roots are required for operator-cache identity")
    return _sha(payload, BACKEND_OPERATOR_SCHEMA)


def _profile_number(profile: QiFlowProfile, *path: str) -> float:
    try:
        value: Any = profile.payload
        for key in path:
            value = value[key]
        number = float(finite_float(value, name=".".join(path)))
    except Exception as exc:
        raise QiBackendConfigurationError(f"profile guard {'.'.join(path)} is not finite") from exc
    if not math.isfinite(number) or number <= 0.0:
        raise QiBackendConfigurationError(f"profile guard {'.'.join(path)} must be positive")
    return number


@dataclass(frozen=True, slots=True)
class QiParityGuardBands:
    """Profile-derived term tolerances, optionally widened from measurements."""

    profile_sha256: str
    terms: Mapping[str, float]
    strict_safety_margin: float
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.profile_sha256, str) or len(self.profile_sha256) != 64:
            raise QiBackendConfigurationError("parity guard profile identity is invalid")
        if set(self.terms) != _PARITY_TERM_SET:
            raise QiBackendConfigurationError("parity guard term keys are not exact")
        normalized: dict[str, float] = {}
        for key in _PARITY_TERM_ORDER:
            value = float(self.terms[key])
            if not math.isfinite(value) or value <= 0.0:
                raise QiBackendConfigurationError(f"parity guard {key} must be positive and finite")
            normalized[key] = value
        object.__setattr__(self, "terms", MappingProxyType(normalized))
        margin = float(self.strict_safety_margin)
        if not math.isfinite(margin) or not 0.0 < margin < 1.0:
            raise QiBackendConfigurationError("parity strict safety margin must lie in (0,1)")
        object.__setattr__(self, "strict_safety_margin", margin)
        if not isinstance(self.source, str) or not self.source:
            raise QiBackendConfigurationError("parity guard source is required")

    @classmethod
    def from_profile(
        cls,
        profile: QiFlowProfile,
        *,
        measured_errors: Mapping[str, float] | None = None,
    ) -> "QiParityGuardBands":
        selected = validate_profile(profile)
        numerical = _profile_number(selected, "dynamics", "stability_envelope", "numerical_uncertainty_abs")
        candidate = _profile_number(selected, "dynamics", "candidate_numerical_tolerance")
        topology = _profile_number(selected, "retention", "barrier_uncertainty_guard")
        conversion = _profile_number(selected, "conversion", "numerical_zero_guard")
        safety = _profile_number(selected, "dynamics", "stability_envelope", "strict_safety_margin")
        base = {
            "current": max(numerical, candidate),
            "momentum": max(numerical, candidate),
            "work": max(numerical, candidate),
            "topology": max(numerical, topology),
            "receipt": max(numerical, conversion),
            "state": max(numerical, candidate),
        }
        source = "profile-derived-v1"
        if measured_errors is not None:
            if set(measured_errors) != _PARITY_TERM_SET:
                raise QiBackendConfigurationError("measured parity errors must name every required term")
            for key in _PARITY_TERM_ORDER:
                error = float(measured_errors[key])
                if not math.isfinite(error) or error < 0.0:
                    raise QiBackendConfigurationError(f"measured parity error {key} is invalid")
                base[key] = max(base[key], error * (1.0 + safety))
            source = "measured-and-profile-derived-v1"
        return cls(selected.profile_sha256, base, safety, source)

    @property
    def guard_sha256(self) -> str:
        return _sha(
            {
                "schema": BACKEND_PROBE_SCHEMA,
                "profile_sha256": self.profile_sha256,
                "terms": _plain(self.terms),
                "strict_safety_margin": self.strict_safety_margin,
                "source": self.source,
            },
            BACKEND_PROBE_SCHEMA,
        )

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "schema": BACKEND_PROBE_SCHEMA,
            "profile_sha256": self.profile_sha256,
            "terms": _plain(self.terms),
            "strict_safety_margin": self.strict_safety_margin,
            "source": self.source,
        }
        payload["guard_sha256"] = self.guard_sha256
        return payload
@dataclass(frozen=True, slots=True)
class QiParityTerm:
    name: str
    reference_sha256: str
    candidate_sha256: str
    max_abs_error: float | None
    tolerance: float
    safe_tolerance: float
    compared_values: int
    mismatch_count: int
    status: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise QiBackendConfigurationError("parity term name is required")
        for name in ("reference_sha256", "candidate_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise QiBackendConfigurationError(f"parity term {name} is invalid")
        for name in ("tolerance", "safe_tolerance"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise QiBackendConfigurationError(f"parity term {name} is invalid")
            object.__setattr__(self, name, value)
        if self.max_abs_error is not None:
            value = float(self.max_abs_error)
            if not math.isfinite(value) or value < 0.0:
                raise QiBackendConfigurationError("parity term max_abs_error is invalid")
            object.__setattr__(self, "max_abs_error", value)
        object.__setattr__(self, "compared_values", _require_int(self.compared_values, "parity compared_values"))
        object.__setattr__(self, "mismatch_count", _require_int(self.mismatch_count, "parity mismatch_count"))
        if self.status not in {"NOT_RUN", "PASS", "FAIL", "ABSTAIN"}:
            raise QiBackendConfigurationError("parity term status is invalid")
        if self.status == "NOT_RUN" and self.max_abs_error is not None:
            raise QiBackendConfigurationError("unexecuted parity term cannot report an error")

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "reference_sha256": self.reference_sha256,
            "candidate_sha256": self.candidate_sha256,
            "max_abs_error": self.max_abs_error,
            "tolerance": self.tolerance,
            "safe_tolerance": self.safe_tolerance,
            "compared_values": self.compared_values,
            "mismatch_count": self.mismatch_count,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class QiParityReceipt:
    oracle_profile_sha256: str
    candidate_profile_sha256: str
    oracle_backend_identity_sha256: str
    candidate_backend_identity_sha256: str
    oracle_dtype: str
    candidate_dtype: str
    candidate_device: str
    executed: bool
    parity_status: str
    guard_sha256: str
    terms: tuple[QiParityTerm, ...]
    prepared_sha256: str | None = None
    candidate_prepared_sha256: str | None = None
    counter_delta: Mapping[str, int] = MappingProxyType({})

    def __post_init__(self) -> None:
        for name in (
            "oracle_profile_sha256",
            "candidate_profile_sha256",
            "oracle_backend_identity_sha256",
            "candidate_backend_identity_sha256",
            "guard_sha256",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise QiBackendConfigurationError(f"parity receipt {name} is invalid")
        _, oracle_dtype = _dtype(self.oracle_dtype)
        _, candidate_dtype = _dtype(self.candidate_dtype)
        object.__setattr__(self, "oracle_dtype", oracle_dtype)
        object.__setattr__(self, "candidate_dtype", candidate_dtype)
        object.__setattr__(self, "terms", tuple(self.terms))
        if tuple(term.name for term in self.terms) != _PARITY_TERM_ORDER:
            raise QiBackendConfigurationError("parity receipt terms are not in canonical order")
        if self.parity_status not in {"NOT_RUN", "PASS", "FAIL", "ABSTAIN"}:
            raise QiBackendConfigurationError("parity receipt status is invalid")
        if not self.executed and self.parity_status != "NOT_RUN":
            raise QiBackendConfigurationError("unexecuted parity receipt cannot claim a result")
        if self.prepared_sha256 is not None and (not isinstance(self.prepared_sha256, str) or len(self.prepared_sha256) != 64):
            raise QiBackendConfigurationError("oracle prepared identity is invalid")
        if self.candidate_prepared_sha256 is not None and (not isinstance(self.candidate_prepared_sha256, str) or len(self.candidate_prepared_sha256) != 64):
            raise QiBackendConfigurationError("candidate prepared identity is invalid")
        if not isinstance(self.counter_delta, Mapping):
            raise QiBackendConfigurationError("parity counter delta must be a mapping")
        object.__setattr__(
            self,
            "counter_delta",
            MappingProxyType({str(key): _require_int(value, f"counter_delta.{key}") for key, value in self.counter_delta.items()}),
        )

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "schema": BACKEND_PROBE_SCHEMA,
            "oracle_profile_sha256": self.oracle_profile_sha256,
            "candidate_profile_sha256": self.candidate_profile_sha256,
            "oracle_backend_identity_sha256": self.oracle_backend_identity_sha256,
            "candidate_backend_identity_sha256": self.candidate_backend_identity_sha256,
            "oracle_dtype": self.oracle_dtype,
            "candidate_dtype": self.candidate_dtype,
            "candidate_device": self.candidate_device,
            "executed": self.executed,
            "parity_status": self.parity_status,
            "guard_sha256": self.guard_sha256,
            "terms": [term.to_payload() for term in self.terms],
            "prepared_sha256": self.prepared_sha256,
            "candidate_prepared_sha256": self.candidate_prepared_sha256,
            "counter_delta": _plain(self.counter_delta),
        }
        payload["receipt_sha256"] = _sha(payload, BACKEND_PROBE_SCHEMA)
        return payload


@dataclass(frozen=True, slots=True)
class QiCandidateTrajectoryReceipt:
    profile_sha256: str
    executed: bool
    parity_status: str
    guard_sha256: str
    branches: tuple[QiParityTerm, ...]
    candidate_count: int

    def __post_init__(self) -> None:
        for name in ("profile_sha256", "guard_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise QiBackendConfigurationError(f"trajectory receipt {name} is invalid")
        object.__setattr__(self, "branches", tuple(self.branches))
        object.__setattr__(self, "candidate_count", _require_int(self.candidate_count, "candidate_count", 1))
        if len(self.branches) != self.candidate_count:
            raise QiBackendConfigurationError("trajectory receipt branch count is inconsistent")
        if self.parity_status not in {"NOT_RUN", "PASS", "FAIL", "ABSTAIN"}:
            raise QiBackendConfigurationError("trajectory receipt status is invalid")
        if not self.executed and self.parity_status != "NOT_RUN":
            raise QiBackendConfigurationError("unexecuted trajectory receipt cannot claim a result")

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "schema": BACKEND_PROBE_SCHEMA,
            "profile_sha256": self.profile_sha256,
            "executed": self.executed,
            "parity_status": self.parity_status,
            "guard_sha256": self.guard_sha256,
            "candidate_count": self.candidate_count,
            "branches": [branch.to_payload() for branch in self.branches],
        }
        payload["receipt_sha256"] = _sha(payload, BACKEND_PROBE_SCHEMA)
        return payload


def _parity_leaf_map(value: Any, path: str = "$") -> dict[str, tuple[str, Any]]:
    if isinstance(value, QiFlowStateV3):
        return _parity_leaf_map(value.field, path)
    if isinstance(value, QiFieldState):
        return _parity_leaf_map(value.field, path)
    if hasattr(value, "to_payload") and callable(value.to_payload):
        return _parity_leaf_map(value.to_payload(), path)
    if torch.is_tensor(value):
        if value.requires_grad or value.grad is not None:
            raise QiBackendConfigurationError(f"parity tensor {path} carries autograd state")
        if value.ndim == 0:
            flat = [value.detach().item()]
        else:
            flat = value.detach().contiguous().reshape(-1).to(device="cpu").tolist()
        result: dict[str, tuple[str, Any]] = {
            f"{path}/shape": ("exact", tuple(int(item) for item in value.shape)),
        }
        for index, item in enumerate(flat):
            number = float(item)
            if not math.isfinite(number):
                raise QiBackendExecutionError(f"parity tensor {path} contains a nonfinite value")
            result[f"{path}/value/{index}"] = ("numeric", number)
        return result
    if isinstance(value, Mapping):
        result = {}
        for key in sorted(value, key=lambda item: str(item).encode("utf-8")):
            result.update(_parity_leaf_map(value[key], f"{path}/{key}"))
        return result
    if isinstance(value, (tuple, list)):
        result = {}
        for index, item in enumerate(value):
            result.update(_parity_leaf_map(item, f"{path}/{index}"))
        return result
    if isinstance(value, bool):
        return {path: ("exact", value)}
    if isinstance(value, int):
        return {path: ("integer", int(value))}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise QiBackendExecutionError(f"parity value {path} is nonfinite")
        return {path: ("numeric", float(value))}
    if value is None or isinstance(value, str):
        return {path: ("exact", value)}
    if isinstance(value, bytes):
        return {path: ("exact", value.hex())}
    raise QiBackendConfigurationError(f"unsupported parity value at {path}: {type(value).__name__}")

def _parity_digest(leaves: Mapping[str, tuple[str, Any]]) -> str:
    return _sha({"leaves": {key: [kind, value] for key, (kind, value) in sorted(leaves.items())}}, BACKEND_PROBE_SCHEMA)


def _compare_leaves(
    reference: Mapping[str, tuple[str, Any]],
    candidate: Mapping[str, tuple[str, Any]],
    *,
    tolerance: float,
    safe_tolerance: float,
) -> tuple[float, int, int, str]:
    if set(reference) != set(candidate):
        return math.inf, 0, 1, "FAIL"
    maximum = 0.0
    compared = 0
    mismatches = 0
    for key in sorted(reference):
        ref_kind, ref_value = reference[key]
        cand_kind, cand_value = candidate[key]
        if ref_kind in {"integer", "exact"} or cand_kind in {"integer", "exact"}:
            if ref_kind != cand_kind or ref_value != cand_value:
                mismatches += 1
            continue
        if ref_kind != "numeric" or cand_kind != "numeric":
            mismatches += 1
            continue
        difference = abs(float(ref_value) - float(cand_value))
        maximum = max(maximum, difference)
        compared += 1
        if difference > tolerance:
            mismatches += 1
    if mismatches:
        return maximum, compared, mismatches, "FAIL"
    if maximum > safe_tolerance:
        return maximum, compared, 0, "ABSTAIN"
    return maximum, compared, 0, "PASS"


def _backend_metric_snapshot(backend: Any) -> dict[str, int]:
    metrics = getattr(backend, "_metrics", {})
    return {
        str(key): int(value)
        for key, value in metrics.items()
        if isinstance(value, int) and not isinstance(value, bool)
    }


def _validate_parity_backend(backend: Any, *, oracle: bool) -> None:
    try:
        device = backend.device
        dtype = backend.dtype
        identity = backend.identity
        capabilities = backend.capabilities
    except Exception as exc:
        raise QiBackendConfigurationError("parity requires a TorchFlowBackend") from exc
    if oracle and (device.type != "cpu" or dtype is not torch.float64):
        raise QiBackendConfigurationError("oracle backend must be CPU float64")
    if not oracle and (device.type not in {"cpu", "cuda"} or dtype is not torch.float32):
        raise QiBackendConfigurationError("candidate backend must be CPU or ROCm float32")
    if not bool(capabilities.available) or int(identity.fallback_count) != 0:
        raise QiBackendUnavailable("parity backend is unavailable or reports fallback")
    if not oracle and device.type == "cuda" and not capabilities.rocm_version:
        raise QiBackendConfigurationError("cuda parity candidate must identify ROCm explicitly")


def _parity_status(terms: Sequence[QiParityTerm], *, executed: bool) -> str:
    if not executed:
        return "NOT_RUN"
    statuses = {term.status for term in terms}
    if "FAIL" in statuses:
        return "FAIL"
    if "ABSTAIN" in statuses:
        return "ABSTAIN"
    return "PASS"


def compare_termwise_parity(
    profile: QiFlowProfile,
    oracle_backend: Any,
    candidate_backend: Any,
    oracle_terms: Mapping[str, Any],
    candidate_terms: Mapping[str, Any],
    *,
    guard_bands: QiParityGuardBands | None = None,
    executed: bool = False,
    oracle_prepared: QiPreparedOperators | None = None,
    candidate_prepared: QiPreparedOperators | None = None,
) -> QiParityReceipt:
    """Compare f64-oracle/f32 candidate terms without changing either backend."""

    selected = validate_profile(profile)
    bands = guard_bands or QiParityGuardBands.from_profile(selected)
    if bands.profile_sha256 != selected.profile_sha256:
        raise QiBackendConfigurationError("parity guard profile identity does not match oracle profile")
    if set(oracle_terms) != _PARITY_TERM_SET or set(candidate_terms) != _PARITY_TERM_SET:
        raise QiBackendConfigurationError("parity terms must be exactly current/momentum/work/topology/receipt/state")
    _validate_parity_backend(oracle_backend, oracle=True)
    _validate_parity_backend(candidate_backend, oracle=False)
    if oracle_backend.profile.profile_sha256 != selected.profile_sha256:
        raise QiBackendConfigurationError("oracle backend profile does not match parity profile")
    if oracle_prepared is not None:
        oracle_backend._validate_prepared(oracle_prepared, int(oracle_prepared.batch))
    if candidate_prepared is not None:
        candidate_backend._validate_prepared(candidate_prepared, int(candidate_prepared.batch))
    before = _backend_metric_snapshot(oracle_backend)
    before.update({f"candidate_{key}": value for key, value in _backend_metric_snapshot(candidate_backend).items()})
    if executed and (oracle_prepared is None or candidate_prepared is None):
        raise QiBackendConfigurationError("executed parity requires both prepared backend handles")
    if executed:
        oracle_backend.synchronize()
        candidate_backend.synchronize()
    terms: list[QiParityTerm] = []
    for name in _PARITY_TERM_ORDER:
        reference_leaves = _parity_leaf_map(oracle_terms[name], f"${name}")
        candidate_leaves = _parity_leaf_map(candidate_terms[name], f"${name}")
        reference_hash = _parity_digest(reference_leaves)
        candidate_hash = _parity_digest(candidate_leaves)
        tolerance = bands.terms[name]
        safe_tolerance = tolerance * (1.0 - bands.strict_safety_margin)
        if executed:
            maximum, compared, mismatches, status = _compare_leaves(
                reference_leaves,
                candidate_leaves,
                tolerance=tolerance,
                safe_tolerance=safe_tolerance,
            )
        else:
            maximum, compared, mismatches, status = None, 0, 0, "NOT_RUN"
        terms.append(QiParityTerm(name, reference_hash, candidate_hash, maximum, tolerance, safe_tolerance, compared, mismatches, status))
    after = _backend_metric_snapshot(oracle_backend)
    after.update({f"candidate_{key}": value for key, value in _backend_metric_snapshot(candidate_backend).items()})
    counter_delta = {key: after.get(key, 0) - before.get(key, 0) for key in sorted(set(before) | set(after))}
    return QiParityReceipt(
        oracle_profile_sha256=selected.profile_sha256,
        candidate_profile_sha256=candidate_backend.profile.profile_sha256,
        oracle_backend_identity_sha256=oracle_backend.identity.content_sha256,
        candidate_backend_identity_sha256=candidate_backend.identity.content_sha256,
        oracle_dtype=str(oracle_backend.dtype).removeprefix("torch."),
        candidate_dtype=str(candidate_backend.dtype).removeprefix("torch."),
        candidate_device=str(candidate_backend.device),
        executed=executed,
        parity_status=_parity_status(terms, executed=executed),
        guard_sha256=bands.guard_sha256,
        terms=tuple(terms),
        prepared_sha256=None if oracle_prepared is None else oracle_prepared.prepared_sha256,
        candidate_prepared_sha256=None if candidate_prepared is None else candidate_prepared.prepared_sha256,
        counter_delta=counter_delta,
    )


def compare_candidate_trajectories(
    profile: QiFlowProfile,
    batched_candidates: Sequence[Any],
    independent_candidates: Sequence[Any],
    *,
    guard_bands: QiParityGuardBands | None = None,
    executed: bool = False,
) -> QiCandidateTrajectoryReceipt:
    """Compare batched branches with separately executed candidate trajectories."""

    selected = validate_profile(profile)
    bands = guard_bands or QiParityGuardBands.from_profile(selected)
    if bands.profile_sha256 != selected.profile_sha256:
        raise QiBackendConfigurationError("trajectory guard profile identity does not match profile")
    if not batched_candidates or len(batched_candidates) != len(independent_candidates):
        raise QiBackendConfigurationError("batched and independent candidate counts must match and be nonzero")
    branches: list[QiParityTerm] = []
    for index, (batched, independent) in enumerate(zip(batched_candidates, independent_candidates)):
        batched_leaves = _parity_leaf_map(batched, f"$candidate/{index}")
        independent_leaves = _parity_leaf_map(independent, f"$candidate/{index}")
        tolerance = bands.terms["state"]
        safe_tolerance = tolerance * (1.0 - bands.strict_safety_margin)
        if executed:
            maximum, compared, mismatches, status = _compare_leaves(
                batched_leaves,
                independent_leaves,
                tolerance=tolerance,
                safe_tolerance=safe_tolerance,
            )
        else:
            maximum, compared, mismatches, status = None, 0, 0, "NOT_RUN"
        branches.append(
            QiParityTerm(
                f"candidate-{index}",
                _parity_digest(batched_leaves),
                _parity_digest(independent_leaves),
                maximum,
                tolerance,
                safe_tolerance,
                compared,
                mismatches,
                status,
            )
        )
    return QiCandidateTrajectoryReceipt(
        profile_sha256=selected.profile_sha256,
        executed=executed,
        parity_status=_parity_status(branches, executed=executed),
        guard_sha256=bands.guard_sha256,
        branches=tuple(branches),
        candidate_count=len(branches),
    )
class QiFlowBackend(Protocol):
    identity: QiBackendIdentity

    def prepare(self, profile: QiFlowProfile, batch: int, *, operator_id: str = ADVANCE_OPERATOR_ID, operator_sha256: str | None = None) -> QiPreparedOperators: ...

    def execute_advance(self, state: QiFieldState, drive: QiDriveBundle) -> QiFlowStep: ...

    def fork(self, state: QiFieldState, count: int) -> QiCandidateBatch: ...

    def serialize_state(self, state: QiFieldState) -> bytes: ...

    def synchronize(self) -> None: ...

    def memory_receipt(self) -> QiBackendMemoryReceipt: ...


class TorchFlowBackend:
    """One backend semantics for CPU and explicitly requested Torch cuda/ROCm."""

    def __init__(
        self,
        profile: QiFlowProfile,
        *,
        device: torch.device | str,
        dtype: torch.dtype | str,
        seed: int = 0,
        config: QiRuntimeConfig | None = None,
        capability_probe: Callable[[torch.device], Any] | None = None,
        capacity: QiCapacityProfile | None = None,
    ) -> None:
        try:
            self.profile = validate_profile(profile)
        except Exception as exc:
            raise QiBackendConfigurationError("selected profile is invalid") from exc
        self._device, self._device_name = _device(device)
        self._torch_dtype, self._dtype_name = _dtype(dtype)
        self.seed = _require_int(seed, "seed")
        if config is None:
            config = QiRuntimeConfig(device=self._device.type, dtype=self._dtype_name, working_memory_budget=1 << 20)
        if not isinstance(config, QiRuntimeConfig):
            raise QiBackendConfigurationError("config must be QiRuntimeConfig")
        if config.device != self._device.type or config.dtype != self._dtype_name:
            raise QiBackendConfigurationError("runtime config device/dtype does not match explicit backend selection")
        self.config = config
        probe = default_capability_probe if capability_probe is None else capability_probe
        try:
            result = probe(self._device)
        except QiBackendUnavailable:
            raise
        except Exception as exc:
            raise QiBackendUnavailable(f"capability probe failed: {type(exc).__name__}: {exc}") from exc
        self.capabilities = QiBackendCapabilities.from_probe(self._device, result, deterministic_algorithms=config.deterministic_algorithms)
        if not self.capabilities.available:
            raise QiBackendUnavailable(f"requested device {self._device} is unavailable; CPU fallback is forbidden")
        if self.capabilities.device_type != self._device.type or (self._device.type == "cuda" and self.capabilities.device_index != self._device.index):
            raise QiBackendUnavailable("capability probe identified a different device")
        if self.capabilities.device_type == "cuda" and self.capabilities.device != str(self._device):
            raise QiBackendUnavailable("capability probe device identity does not match request")
        if self._torch_dtype is torch.float32 and not self.capabilities.supports_float32:
            raise QiBackendUnavailable("requested float32 capability is unavailable")
        if self._torch_dtype is torch.float64 and not self.capabilities.supports_float64:
            raise QiBackendUnavailable("requested float64 capability is unavailable")
        declared_device = _profile_device(self.profile)
        declared_dtype = _profile_dtype(self.profile)
        if declared_device != self._device.type:
            raise QiBackendConfigurationError("explicit device does not match profile-declared device")
        if declared_dtype != self._dtype_name:
            raise QiBackendConfigurationError("explicit dtype does not match profile-declared dtype")
        if capacity is None:
            capacity = QiCapacityProfile.from_profile(self.profile, working_memory_budget=config.working_memory_budget, max_batch_lanes=min(config.max_batch, _profile_capacity(self.profile)["max_batch_lanes"]), max_candidates=min(config.max_candidates, _profile_capacity(self.profile)["max_candidates"]))
        if not isinstance(capacity, QiCapacityProfile):
            raise QiBackendConfigurationError("capacity must be QiCapacityProfile")
        self.capacity = capacity
        self._operator_sha256 = _sha(
            {
                "schema": BACKEND_OPERATOR_SCHEMA,
                "operator_id": FIXED_OPERATOR_ID,
                "semantics": "output = predecessor * fixed_scale",
                "fixed_scale": "f64:3fe0000000000000",
                "state_layout": "[S,9M,B]",
                "random_apis": False,
                "device_dependent_rounding": False,
            },
            BACKEND_OPERATOR_SCHEMA,
        )
        self._advance_operator_sha256 = _sha(
            {
                "schema": BACKEND_OPERATOR_SCHEMA,
                "operator_id": ADVANCE_OPERATOR_ID,
                "semantics": "output = predecessor + explicit_delta_or_identity",
                "state_layout": "[S,9M,B]",
                "random_apis": False,
                "device_dependent_rounding": False,
            },
            BACKEND_OPERATOR_SCHEMA,
        )
        self._metrics = {
            name: 0
            for name in (
                "state_bytes",
                "peak",
                "allocated",
                "reserved",
                "allocations",
                "copies",
                "synchronizations",
                "op_count",
                "wall_time_ns",
                "prepared_cache_hits",
                "prepared_cache_misses",
            )
        }
        self._configure_determinism()
        self.identity = QiBackendIdentity(
            backend="torch",
            adapter="torch-rocm" if self._device.type == "cuda" and self.capabilities.rocm_version else ("torch-cuda" if self._device.type == "cuda" else "torch-cpu-reference"),
            device=self._device_name,
            device_type=self._device.type,
            device_index=self._device.index,
            device_name=self.capabilities.device_name,
            pci_identity=self.capabilities.pci_identity,
            torch_version=self.capabilities.torch_version,
            rocm_version=self.capabilities.rocm_version,
            dtype=self._dtype_name,
            seed=self.seed,
            deterministic_algorithms=config.deterministic_algorithms,
            same_backend_exact_replay=config.same_backend_exact_replay,
            cpu_threads=config.cpu_threads,
            interop_threads=config.interop_threads,
            fft_identity="torch.fft.orthonormal-registered-replay-v1",
            prepared_operator_sha256=self._operator_sha256,
            fallback_count=0,
            synchronization_policy="explicit-before-observation-v1",
            profile_sha256=self.profile.profile_sha256,
            capability_sha256=self.capabilities.capability_sha256,
        )
        self._prepared_cache: dict[str, QiPreparedOperators] = {}
        self._prepared_cache_limit = max(1, min(self.config.max_batch, self.capacity.max_batch_lanes))

    @property
    def device(self) -> torch.device:
        return self._device

    @property
    def dtype(self) -> torch.dtype:
        return self._torch_dtype

    @property
    def operator_sha256(self) -> str:
        return self._operator_sha256

    @property
    def identity_receipt(self) -> dict[str, Any]:
        return self.identity.to_payload()

    @property
    def capability_receipt(self) -> dict[str, Any]:
        return self.capabilities.to_payload()
    @property
    def prepared_cache(self) -> tuple[QiPreparedOperators, ...]:
        """Return immutable handles currently held by the bounded cache."""

        return tuple(self._prepared_cache.values())

    def _configure_determinism(self) -> None:
        try:
            if self.config.cpu_threads:
                torch.set_num_threads(self.config.cpu_threads)
            if self.config.interop_threads:
                torch.set_num_interop_threads(self.config.interop_threads)
            if self.config.deterministic_algorithms:
                torch.use_deterministic_algorithms(True)
                if hasattr(torch.backends, "cudnn"):
                    torch.backends.cudnn.deterministic = True
                    torch.backends.cudnn.benchmark = False
                    torch.backends.cudnn.allow_tf32 = False
                if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
                    torch.backends.cuda.matmul.allow_tf32 = False
        except Exception as exc:
            raise QiBackendConfigurationError(f"deterministic Torch controls failed: {type(exc).__name__}: {exc}") from exc

    def prepare(
        self,
        profile: QiFlowProfile,
        batch: int,
        *,
        operator_id: str = ADVANCE_OPERATOR_ID,
        operator_sha256: str | None = None,
    ) -> QiPreparedOperators:
        selected = self._resolve_profile(profile)
        preflight = preflight_memory(selected, batch, 1, dtype=self._torch_dtype, capacity=self.capacity)
        if not isinstance(operator_id, str) or not operator_id:
            raise QiBackendConfigurationError("prepared operator_id must be nonempty")
        if operator_sha256 is None:
            if operator_id == FIXED_OPERATOR_ID:
                selected_operator_sha = self._operator_sha256
            elif operator_id == ADVANCE_OPERATOR_ID:
                selected_operator_sha = self._advance_operator_sha256
            else:
                raise QiBackendConfigurationError("custom prepared operators require an explicit operator_sha256")
        else:
            selected_operator_sha = operator_sha256
        if not isinstance(selected_operator_sha, str) or len(selected_operator_sha) != 64 or any(char not in "0123456789abcdef" for char in selected_operator_sha):
            raise QiBackendConfigurationError("prepared operator_sha256 must be lowercase sha256")
        cache_identity = _operator_cache_identity(
            selected,
            device=self._device_name,
            dtype=self._dtype_name,
            batch=preflight.batch,
            operator_id=operator_id,
            operator_sha256=selected_operator_sha,
            backend_identity_sha256=self.identity.content_sha256,
        )
        cached = self._prepared_cache.get(cache_identity)
        if cached is not None:
            self._metrics["prepared_cache_hits"] += 1
            return cached
        self._metrics["prepared_cache_misses"] += 1
        if len(self._prepared_cache) >= self._prepared_cache_limit:
            raise QiBackendCapacityError("prepared operator cache capacity is exhausted")
        prepared = QiPreparedOperators(
            selected.profile_sha256,
            self._device_name,
            self._dtype_name,
            preflight.batch,
            operator_id,
            selected_operator_sha,
            preflight.prepared_bytes,
            cache_identity,
            self.identity.content_sha256,
        )
        self._prepared_cache[cache_identity] = prepared
        self._metrics["allocations"] += 1
        self._metrics["peak"] = max(self._metrics["peak"], preflight.required_bytes)
        self._metrics["allocated"] = max(self._metrics["allocated"], preflight.required_bytes)
        self._metrics["reserved"] = max(self._metrics["reserved"], preflight.required_bytes)
        return prepared

    def initial_state(self, batch: int = 1) -> QiFlowStateV3:
        preflight = preflight_memory(self.profile, batch, 1, dtype=self._torch_dtype, capacity=self.capacity)
        try:
            state = QiFlowStateV3.create(self.profile, batch_lanes=batch, device=self._device)
        except Exception as exc:
            raise QiBackendExecutionError(f"initial state allocation failed: {type(exc).__name__}: {exc}") from exc
        self._metrics["state_bytes"] = max(self._metrics["state_bytes"], preflight.state_bytes)
        self._metrics["peak"] = max(self._metrics["peak"], preflight.required_bytes)
        self._metrics["allocated"] = max(self._metrics["allocated"], preflight.required_bytes)
        self._metrics["reserved"] = max(self._metrics["reserved"], preflight.required_bytes)
        self._metrics["allocations"] += 1
        return state

    def _resolve_profile(self, profile: QiFlowProfile) -> QiFlowProfile:
        try:
            selected = validate_profile(profile)
        except Exception as exc:
            raise QiBackendConfigurationError("selected profile is invalid") from exc
        if selected.profile_sha256 != self.profile.profile_sha256:
            raise QiBackendConfigurationError("backend profile identity changed")
        return selected
    def _validate_prepared(self, prepared: QiPreparedOperators, batch: int) -> QiPreparedOperators:
        if not isinstance(prepared, QiPreparedOperators):
            raise QiBackendConfigurationError("execute_advance requires QiPreparedOperators")
        if (
            prepared.profile_sha256 != self.profile.profile_sha256
            or prepared.device != self._device_name
            or prepared.dtype != self._dtype_name
            or prepared.batch != batch
            or prepared.backend_identity_sha256 != self.identity.content_sha256
        ):
            raise QiBackendConfigurationError("prepared operator handle does not match backend/profile/batch")
        expected_cache = _operator_cache_identity(
            self.profile,
            device=self._device_name,
            dtype=self._dtype_name,
            batch=batch,
            operator_id=prepared.operator_id,
            operator_sha256=prepared.operator_sha256,
            backend_identity_sha256=self.identity.content_sha256,
        )
        if expected_cache != prepared.operator_cache_sha256:
            raise QiBackendConfigurationError("prepared operator cache identity mismatch")
        cached = self._prepared_cache.get(prepared.operator_cache_sha256)
        if cached is None or cached.prepared_sha256 != prepared.prepared_sha256:
            raise QiBackendConfigurationError("prepared operator handle is not live in the bounded cache")
        return prepared

    def _required_operator_id(self, drive: QiDriveBundle) -> str:
        if drive.geometry_profile is not None or drive.transport_profile is not None:
            return "w3-transport-v1"
        if drive.operator is not None:
            return "explicit-operator-v1"
        return ADVANCE_OPERATOR_ID

    def _state(self, state: QiFieldState | QiFlowStateV3) -> QiFlowStateV3:
        try:
            selected = state if isinstance(state, QiFlowStateV3) else QiFlowStateV3.from_field(self.profile, state)
            selected.validate(self.profile, device=self._device)
            return selected
        except Exception as exc:
            raise QiBackendConfigurationError(f"state device/dtype/layout mismatch: {type(exc).__name__}: {exc}") from exc

    def _account(self, preflight: QiMemoryPreflight, *, allocations: int, copies: int, operations: int, elapsed_ns: int) -> None:
        self._metrics["state_bytes"] = max(self._metrics["state_bytes"], preflight.state_bytes)
        self._metrics["peak"] = max(self._metrics["peak"], preflight.required_bytes)
        self._metrics["allocated"] = max(self._metrics["allocated"], preflight.required_bytes)
        self._metrics["reserved"] = max(self._metrics["reserved"], preflight.required_bytes)
        self._metrics["allocations"] += allocations
        self._metrics["copies"] += copies
        self._metrics["op_count"] += operations
        self._metrics["wall_time_ns"] += elapsed_ns

    def execute_advance(self, state: QiFieldState | QiFlowStateV3, drive: QiDriveBundle) -> QiFlowStep:
        if not isinstance(drive, QiDriveBundle):
            raise QiBackendConfigurationError("execute_advance requires QiDriveBundle")
        if drive.prepared is None:
            raise QiBackendConfigurationError("execute_advance requires an explicit prepared operator handle")
        predecessor = self._state(state)
        batch = int(predecessor.field.shape[2])
        prepared = self._validate_prepared(drive.prepared, batch)
        required_operator_id = self._required_operator_id(drive)
        if prepared.operator_id != required_operator_id:
            raise QiBackendConfigurationError("prepared operator handle is for a different operator")
        preflight = preflight_memory(self.profile, batch, 1, dtype=self._torch_dtype, capacity=self.capacity)
        self.synchronize()
        start = time.perf_counter_ns()
        try:
            if (drive.geometry_profile is None) != (drive.transport_profile is None):
                raise QiBackendExecutionError("geometry_profile and transport_profile must be supplied together")
            if drive.geometry_profile is not None:
                raw = transition_v3_transport(predecessor, geometry_profile=drive.geometry_profile, transport_profile=drive.transport_profile, duration_s=drive.duration_s, source=drive.source)
                candidate = raw.candidate
                if candidate is not None:
                    candidate.validate(self.profile, device=self._device)
                operator_id = "w3-transport-v1"
                committable = bool(raw.committable and candidate is not None)
                failure_reason = raw.failure_reason
                diagnostics = raw.diagnostics
                ledger = raw.ledger
                raw_receipt = _plain(raw.receipt)
            else:
                if drive.operator is not None:
                    output = drive.operator(predecessor.field)
                elif drive.delta is None:
                    output = predecessor.field.clone()
                elif torch.is_tensor(drive.delta):
                    if drive.delta.device != self._device or drive.delta.dtype is not self._torch_dtype:
                        raise QiBackendConfigurationError("drive tensor device/dtype does not match backend")
                    if drive.delta.ndim not in {0, predecessor.field.ndim} or (drive.delta.ndim == predecessor.field.ndim and tuple(drive.delta.shape) != tuple(predecessor.field.shape)):
                        raise QiBackendConfigurationError("drive tensor shape does not match [S,9M,B]")
                    output = torch.add(predecessor.field, drive.delta)
                else:
                    if not math.isfinite(float(drive.delta)):
                        raise QiBackendConfigurationError("drive scalar must be finite")
                    output = torch.add(predecessor.field, torch.tensor(float(drive.delta), dtype=self._torch_dtype, device=self._device))
                if not torch.is_tensor(output) or output.requires_grad or output.grad is not None:
                    raise QiBackendExecutionError("operator must return a detached tensor")
                if output.device != self._device or output.dtype is not self._torch_dtype or tuple(output.shape) != tuple(predecessor.field.shape):
                    raise QiBackendExecutionError("operator changed device, dtype, or [S,9M,B] shape")
                candidate = QiFlowStateV3.from_field(self.profile, output.contiguous())
                operator_id = ADVANCE_OPERATOR_ID if drive.operator is None else "explicit-operator-v1"
                committable = True
                failure_reason = None
                diagnostics = None
                ledger = None
                raw_receipt = {}
            self.synchronize()
            elapsed = time.perf_counter_ns() - start
            predecessor_hash = predecessor.state_sha256(self.profile)
            candidate_hash = None if candidate is None else candidate.state_sha256(self.profile)
            receipt = {
                "schema": "cassi.qi-flow-backend-step.v1",
                "status": "COMMITTED" if committable else "REJECTED",
                "transaction_id": drive.transaction_id,
                "operator_id": operator_id,
                "predecessor_state_sha256": predecessor_hash,
                "candidate_state_sha256": candidate_hash,
                "backend_identity_sha256": self.identity.content_sha256,
                "operator_sha256": prepared.operator_sha256,
                "prepared_sha256": prepared.prepared_sha256,
                "operator_cache_sha256": prepared.operator_cache_sha256,
                "wall_time_ns": elapsed,
                "op_count": 1,
                "raw_operator_receipt": raw_receipt,
                "failure_reason": failure_reason,
            }
            self._account(preflight, allocations=1 if candidate is not None else 0, copies=1, operations=1, elapsed_ns=elapsed)
            return QiFlowStep(predecessor, candidate, committable, drive.transaction_id, operator_id, receipt, diagnostics, ledger, failure_reason)
        except QiBackendError:
            raise
        except Exception as exc:
            raise QiBackendExecutionError(f"operator execution failed: {type(exc).__name__}: {exc}") from exc

    def fork(self, state: QiFieldState | QiFlowStateV3, count: int) -> QiCandidateBatch:
        predecessor = self._state(state)
        branches = _require_int(count, "count", 1)
        batch = int(predecessor.field.shape[2])
        preflight = preflight_memory(self.profile, batch, branches, dtype=self._torch_dtype, capacity=self.capacity)
        self.synchronize()
        start = time.perf_counter_ns()
        try:
            states = tuple(QiFlowStateV3.from_field(self.profile, predecessor.field.clone().contiguous()) for _ in range(branches))
        except Exception as exc:
            raise QiBackendExecutionError(f"candidate fork failed: {type(exc).__name__}: {exc}") from exc
        elapsed = time.perf_counter_ns() - start
        self.synchronize()
        self._account(preflight, allocations=branches, copies=branches, operations=0, elapsed_ns=elapsed)
        return QiCandidateBatch(predecessor, states, tuple(f"fork-{index}" for index in range(branches)))
    def serialize_state(self, state: QiFieldState | QiFlowStateV3) -> bytes:
        owned = self._state(state)
        self.synchronize()
        raw_bytes = int(owned.field.numel() * owned.field.element_size())
        if raw_bytes + 16384 > self.capacity.max_checkpoint_bytes or raw_bytes + 16384 > self.capacity.working_memory_budget:
            raise QiBackendCapacityError("checkpoint exceeds declared memory bounds before serialization")
        try:
            payload = dump_v3_state_bytes(owned, self.profile)
        except Exception as exc:
            raise QiBackendSerializationError(f"canonical v3 serialization failed: {type(exc).__name__}: {exc}") from exc
        if len(payload) > self.capacity.max_checkpoint_bytes:
            raise QiBackendCapacityError("checkpoint exceeds max_checkpoint_bytes")
        self.synchronize()
        self._metrics["copies"] += 1
        return bytes(payload)

    def deserialize_state(self, payload: bytes) -> QiFlowStateV3:
        if not isinstance(payload, bytes):
            raise QiBackendSerializationError("restore requires canonical bytes")
        if len(payload) > self.capacity.max_checkpoint_bytes:
            raise QiBackendCapacityError("checkpoint exceeds max_checkpoint_bytes")
        self.synchronize()
        try:
            restored = load_v3_state_bytes(payload, self.profile, device=self._device, dtype=self._torch_dtype)
            restored.validate(self.profile, device=self._device)
        except Exception as exc:
            raise QiBackendSerializationError(f"canonical v3 restore failed: {type(exc).__name__}: {exc}") from exc
        self.synchronize()
        self._metrics["allocations"] += 1
        self._metrics["copies"] += 1
        return restored

    def synchronize(self) -> None:
        if self._device.type == "cuda":
            try:
                torch.cuda.synchronize(self._device)
            except Exception as exc:
                raise QiBackendExecutionError(f"device synchronization failed: {type(exc).__name__}: {exc}") from exc
        self._metrics["synchronizations"] += 1

    def memory_receipt(self) -> QiBackendMemoryReceipt:
        self.synchronize()
        allocated = self._metrics["allocated"]
        reserved = self._metrics["reserved"]
        peak = self._metrics["peak"]
        measurement = "declared-upper-bound"
        if self._device.type == "cuda":
            try:
                allocated = max(allocated, int(torch.cuda.memory_allocated(self._device)))
                reserved = max(reserved, int(torch.cuda.memory_reserved(self._device)))
                peak = max(peak, int(torch.cuda.max_memory_allocated(self._device)))
                measurement = "torch-device-observation"
            except Exception as exc:
                raise QiBackendExecutionError(f"device memory observation failed: {type(exc).__name__}: {exc}") from exc
        return QiBackendMemoryReceipt(
            self._device_name,
            self._dtype_name,
            self._metrics["state_bytes"],
            peak,
            allocated,
            reserved,
            self._metrics["allocations"],
            self._metrics["copies"],
            self._metrics["synchronizations"],
            self._metrics["op_count"],
            self._metrics["wall_time_ns"],
            measurement,
            len(self._prepared_cache),
            self._metrics["prepared_cache_hits"],
            self._metrics["prepared_cache_misses"],
        )

    def fixed_operator_probe(
        self,
        state: QiFlowStateV3 | QiFieldState,
        *,
        prepared: QiPreparedOperators | None = None,
    ) -> QiProbeReceipt:
        selected = self._state(state)
        batch = int(selected.field.shape[2])
        if prepared is None:
            raise QiBackendConfigurationError("fixed operator probe requires an explicit prepared operator handle")
        self._validate_prepared(prepared, batch)
        if prepared.operator_id != FIXED_OPERATOR_ID:
            raise QiBackendConfigurationError("fixed operator probe received a different operator handle")
        preflight = preflight_memory(self.profile, batch, 1, dtype=self._torch_dtype, capacity=self.capacity)
        self.synchronize()
        before_alloc = self._metrics["allocations"]
        before_copy = self._metrics["copies"]
        before_sync = self._metrics["synchronizations"]
        start = time.perf_counter_ns()
        output = fixed_operator_probe(selected.field)
        self.synchronize()
        elapsed = time.perf_counter_ns() - start
        result = QiFlowStateV3.from_field(self.profile, output)
        value_interval = (float(output.amin().item()), float(output.amax().item()))
        if not all(math.isfinite(value) for value in value_interval):
            raise QiBackendExecutionError("fixed operator produced a nonfinite interval")
        self._account(preflight, allocations=1, copies=0, operations=1, elapsed_ns=elapsed)
        return QiProbeReceipt(
            backend_identity_sha256=self.identity.content_sha256,
            capability_sha256=self.capabilities.capability_sha256,
            profile_sha256=self.profile.profile_sha256,
            operator_id=prepared.operator_id,
            operator_sha256=prepared.operator_sha256,
            executed=True,
            parity_status="NOT_RUN",
            value_interval=value_interval,
            state_hashes={"input": selected.state_sha256(self.profile), "output": result.state_sha256(self.profile)},
            memory_high_water_bytes=self._metrics["peak"],
            op_count=1,
            wall_time_ns=elapsed,
            allocations=self._metrics["allocations"] - before_alloc,
            copies=self._metrics["copies"] - before_copy,
            synchronizations=self._metrics["synchronizations"] - before_sync,
            prepared_sha256=prepared.prepared_sha256,
            operator_cache_sha256=prepared.operator_cache_sha256,
        )

    def backend_receipt(self, *, probe: QiProbeReceipt | None = None, step: QiFlowStep | None = None) -> dict[str, Any]:
        if probe is None and step is None:
            raise QiBackendExecutionError("backend receipt requires an executed probe or step")
        if probe is not None and not probe.executed:
            raise QiBackendExecutionError("backend receipt cannot consume an unexecuted probe")
        if step is not None:
            accepted_step = step.step_sha256
            operator = {
                "deterministic": self.config.same_backend_exact_replay,
                "input_sha256": step.predecessor.state_sha256(self.profile),
                "operator_id": step.operator_id,
                "output_sha256": _ZERO_SHA256 if step.candidate is None else step.candidate.state_sha256(self.profile),
                "status": "PASS" if step.committable else "FAIL",
            }
        else:
            assert probe is not None
            accepted_step = str(probe.state_hashes["output"])
            operator = {
                "deterministic": probe.executed,
                "input_sha256": str(probe.state_hashes["input"]),
                "operator_id": probe.operator_id,
                "output_sha256": str(probe.state_hashes["output"]),
                "status": "PASS",
            }
        memory = self.memory_receipt()
        ledger = _sha({"transaction": "backend", "step": accepted_step}, "cassi.qi-flow-backend-ledger")
        toolchain = _sha({"torch_version": self.identity.torch_version, "rocm_version": self.identity.rocm_version, "adapter": self.identity.adapter}, "cassi.qi-flow-backend-toolchain")
        try:
            from cassi_qi_receipts import build_receipt
            return build_receipt(
                "cassi.qi-flow-backend-receipt.v1",
                profile=self.profile,
                accepted_ledger_sha256=ledger,
                accepted_step_sha256=accepted_step,
                backend_contract_sha256=self.profile.backend_sha256,
                determinism_result="MEASURED",
                device_fingerprint_sha256=self.capabilities.capability_sha256,
                operator_results=[operator],
                outcome="PASS" if operator["status"] == "PASS" else "FAIL",
                receipt_kind="runtime",
                resource_observation={"peak_working_bytes": memory.peak_working_bytes, "raw_bytes": memory.state_bytes, "state_bytes": memory.state_bytes},
                toolchain_sha256=toolchain,
            )
        except Exception as exc:
            raise QiBackendExecutionError(f"backend receipt construction failed: {type(exc).__name__}: {exc}") from exc


def fixed_operator_probe(value: torch.Tensor) -> torch.Tensor:
    """A fixed backend-only scale operator; it is not a Cassi field-law term."""

    if not torch.is_tensor(value) or value.requires_grad or value.grad is not None or value.ndim != 3 or not value.is_contiguous() or value.dtype not in {torch.float32, torch.float64}:
        raise QiBackendConfigurationError("fixed operator requires detached contiguous [S,9M,B] float tensor")
    with torch.no_grad():
        result = torch.mul(value, FIXED_OPERATOR_SCALE)
    if result.device != value.device or result.dtype is not value.dtype or tuple(result.shape) != tuple(value.shape):
        raise QiBackendExecutionError("fixed operator changed tensor identity")
    return result.contiguous()




__all__ = [
    "RUNTIME_CONFIG_SCHEMA",
    "BACKEND_IDENTITY_SCHEMA",
    "BACKEND_CAPABILITY_SCHEMA",
    "BACKEND_CAPACITY_SCHEMA",
    "BACKEND_MEMORY_SCHEMA",
    "BACKEND_OPERATOR_SCHEMA",
    "BACKEND_PROBE_SCHEMA",
    "PARITY_TERM_ORDER",
    "ADVANCE_OPERATOR_ID",
    "FIXED_OPERATOR_ID",
    "QiBackendError",
    "QiBackendConfigurationError",
    "QiBackendUnavailable",
    "QiBackendCapacityError",
    "QiBackendSerializationError",
    "QiBackendExecutionError",
    "QiRuntimeConfig",
    "QiCapacityProfile",
    "QiMemoryPreflight",
    "preflight_memory",
    "QiBackendCapabilities",
    "default_capability_probe",
    "QiBackendIdentity",
    "QiPreparedOperators",
    "QiDriveBundle",
    "QiFlowStep",
    "QiCandidateBatch",
    "QiBackendMemoryReceipt",
    "QiProbeReceipt",
    "QiParityGuardBands",
    "QiParityTerm",
    "QiParityReceipt",
    "QiCandidateTrajectoryReceipt",
    "compare_termwise_parity",
    "compare_candidate_trajectories",
    "QiFlowBackend",
    "TorchFlowBackend",
    "fixed_operator_probe",

]
