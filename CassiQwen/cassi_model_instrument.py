"""Fixed model-instrument boundary for CassiFI-owned cognition.

This module contains no adaptive state.  It validates model/native identity,
capabilities, bounded numeric observations, and the nonlearned publication
journal needed to pair a CassiFI owner transition with native trial state.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import struct
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

IDENTITY_SCHEMA = "cassi.model-instrument-identity.v1"
CAPABILITY_SCHEMA = "cassi.model-instrument-capabilities.v1"
ENVELOPE_SCHEMA = "cassi.model-numeric-envelope.v1"
TRANSACTION_SCHEMA = "cassi.coupled-transaction.v1"
NATIVE_RESULT_SCHEMA = "cassi.qwen-native-instrument-result.v1"
# Declared by the runtime: `cassi-qwen.cpp` sets n_ctx = 256 for coupled mode.
NATIVE_CONTEXT_TOKENS = 256
_MAX_ENVELOPE_ELEMENTS = 1_048_576


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


# The field coupling is a declared, auditable choice: each entry names one
# `cassi-qwen` option whose value decides what the instrument computes.
COUPLING_OPTIONS: Mapping[str, tuple[str, type]] = {
    "displacement": ("--displacement", int),
    "injection_scale": ("--injection-scale", float),
    "energy_floor": ("--energy-floor", float),
    "read_floor": ("--read-floor", float),
}
_DISPLACEMENT_LEVELS = frozenset({0, 3, 4, 5, 6})
DEFAULT_NATIVE_COUPLING: Mapping[str, float] = {
    "displacement": 0.0,
    "injection_scale": 1.0,
    "energy_floor": 1.0e-6,
    "read_floor": 0.05,
}

def _float32(value: Any) -> float:
    """Round a number through the runtime's own precision (``float`` = f32)."""

    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def normalize_coupling(coupling: Mapping[str, Any] | None) -> dict[str, float]:
    """Validate and canonicalize a field coupling declaration."""

    if coupling is None:
        return {}
    if not isinstance(coupling, Mapping):
        raise ValueError("coupling must be a mapping of coupling option to value")
    normalized: dict[str, float] = {}
    for key, raw in coupling.items():
        if key not in COUPLING_OPTIONS:
            raise ValueError(f"unknown coupling option: {key}")
        _, kind = COUPLING_OPTIONS[key]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"coupling option {key} must be numeric")
        value = kind(raw)
        if not math.isfinite(value):
            raise ValueError(f"coupling option {key} must be finite")
        if kind is int and value not in _DISPLACEMENT_LEVELS:
            raise ValueError("coupling option displacement must be one of 0, 3, 4, 5, 6")
        if kind is float and value < 0.0:
            raise ValueError(f"coupling option {key} must not be negative")
        normalized[key] = float(value)
    return normalized


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{name} must be a nonempty bounded string")
    return value


def _digest(value: Any, name: str) -> str:
    text = _identifier(value, name)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return text


@dataclass(frozen=True, slots=True)
class ModelInstrumentIdentity:
    adapter_id: str
    adapter_version: str
    model_sha256: str
    architecture: str
    quantization: str
    tokenizer_sha256: str
    runtime_sha256: str
    hook_sha256: str
    arithmetic_profile: str
    context_policy: str
    backend: str
    coupling: Mapping[str, Any] | None = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("adapter_id", "adapter_version", "architecture", "quantization", "arithmetic_profile", "context_policy", "backend"):
            _identifier(getattr(self, name), name)
        for name in ("model_sha256", "tokenizer_sha256", "runtime_sha256", "hook_sha256"):
            _digest(getattr(self, name), name)
        # The field coupling decides what the instrument computes, so it belongs
        # to the identity a continuation has to match.
        object.__setattr__(self, "coupling", normalize_coupling(self.coupling))

    @property
    def fingerprint(self) -> str:
        return _sha256_bytes(_canonical(self.as_dict()))

    def as_dict(self) -> dict[str, Any]:
        return {"schema": IDENTITY_SCHEMA, **asdict(self)}


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    profile: str
    structured_requests: bool
    activation_observation_sites: tuple[str, ...]
    intervention_sites: tuple[str, ...]
    trial_state: str
    selective_operations: tuple[str, ...]
    emission_owner: str
    native_persistence: str
    partial_acceptance: bool
    cancellation: bool
    max_elements: int = _MAX_ENVELOPE_ELEMENTS
    lm_head_owner: str = "none"
    sampler_owner: str = "none"
    logit_owner: str = "none"

    def __post_init__(self) -> None:
        _identifier(self.profile, "profile")
        if self.trial_state not in {
            "exact-context",
            "exact-field-state",
            "exact-snapshot",
            "deterministic-replay",
            "none",
        }:
            raise ValueError("trial_state is invalid")
        if self.native_persistence not in {
            "exact",
            "field-state",
            "deterministic-replay",
            "none",
        }:
            raise ValueError("native_persistence is invalid")
        if self.emission_owner not in {"field", "model", "structured-service", "none"}:
            raise ValueError("emission_owner is invalid")
        if self.lm_head_owner not in {"field", "model", "none"}:
            raise ValueError("lm_head_owner is invalid")
        if self.sampler_owner not in {"field", "native-llama", "none"}:
            raise ValueError("sampler_owner is invalid")
        if self.logit_owner not in {"field", "model", "none"}:
            raise ValueError("logit_owner is invalid")
        if isinstance(self.max_elements, bool) or not 1 <= self.max_elements <= _MAX_ENVELOPE_ELEMENTS:
            raise ValueError("max_elements is out of bounds")
        for values, label in ((self.activation_observation_sites, "observation site"), (self.intervention_sites, "intervention site"), (self.selective_operations, "selective operation")):
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate {label}")
            for value in values:
                _identifier(value, label)

    def supports(self, capability: str, *, site: str | None = None) -> bool:
        if capability == "structured-request":
            return self.structured_requests
        if capability == "activation-observation":
            return site in self.activation_observation_sites
        if capability == "latent-intervention":
            return site in self.intervention_sites
        if capability == "partial-acceptance":
            return self.partial_acceptance
        if capability == "cancellation":
            return self.cancellation
        if capability == "exact-native-resume":
            return (
                self.trial_state in {"exact-context", "exact-snapshot"}
                and self.native_persistence == "exact"
            )
        if capability == "exact-field-state":
            return (
                self.trial_state == "exact-field-state"
                and self.native_persistence == "exact"
            )
        if capability == "field-owned-emission":
            return self.emission_owner == "field"
        return capability in self.selective_operations

    def require(self, capability: str, *, site: str | None = None) -> None:
        if not self.supports(capability, site=site):
            detail = capability if site is None else f"{capability}:{site}"
            raise UnsupportedCapability(detail, self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": CAPABILITY_SCHEMA,
            "profile": self.profile,
            "structured_requests": self.structured_requests,
            "activation_observation_sites": list(self.activation_observation_sites),
            "intervention_sites": list(self.intervention_sites),
            "trial_state": self.trial_state,
            "selective_operations": list(self.selective_operations),
            "emission_owner": self.emission_owner,
            "lm_head_owner": self.lm_head_owner,
            "sampler_owner": self.sampler_owner,
            "logit_owner": self.logit_owner,
            "native_persistence": self.native_persistence,
            "partial_acceptance": self.partial_acceptance,
            "cancellation": self.cancellation,
            "max_elements": self.max_elements,
        }



class UnsupportedCapability(RuntimeError):
    def __init__(self, capability: str, capabilities: Mapping[str, Any]) -> None:
        self.capability = capability
        self.capabilities = dict(capabilities)
        super().__init__(f"unsupported adapter capability: {capability}")

    def result(self) -> dict[str, Any]:
        return {
            "schema": "cassi.model-instrument-unsupported.v1",
            "status": "unsupported-adapter-capability",
            "required_capability": self.capability,
            "capabilities": self.capabilities,
        }


@dataclass(frozen=True, slots=True)
class NumericEnvelope:
    routing: Mapping[str, Any]
    meaning: Mapping[str, Any]
    shape: tuple[int, ...]
    dtype: str
    endianness: str
    order: str
    payload_b64: str
    payload_bytes: int
    payload_sha256: str
    finite: bool
    normalization: Mapping[str, Any]
    magnitude_l2: float
    state_dependency: Mapping[str, Any]
    work: Mapping[str, Any]
    trust: Mapping[str, Any]

    @classmethod
    def from_f32(
        cls,
        values: Sequence[float],
        *,
        shape: Sequence[int],
        routing: Mapping[str, Any],
        meaning: Mapping[str, Any],
        state_dependency: Mapping[str, Any],
        work: Mapping[str, Any],
        trust: Mapping[str, Any],
        normalization: Mapping[str, Any] | None = None,
        max_elements: int = _MAX_ENVELOPE_ELEMENTS,
    ) -> "NumericEnvelope":
        dimensions = tuple(shape)
        if not dimensions or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in dimensions):
            raise ValueError("numeric envelope shape must contain positive integers")
        count = math.prod(dimensions)
        if count != len(values) or count > max_elements:
            raise ValueError("numeric envelope shape/payload product is invalid")
        numbers = tuple(float(value) for value in values)
        finite = all(math.isfinite(value) for value in numbers)
        payload = struct.pack(f"<{count}f", *numbers)
        packed_numbers = struct.unpack(f"<{count}f", payload)
        magnitude = (
            math.sqrt(math.fsum(value * value for value in packed_numbers))
            if finite
            else math.inf
        )
        envelope = cls(
            routing=dict(routing),
            meaning=dict(meaning),
            shape=dimensions,
            dtype="float32",
            endianness="little",
            order="C",
            payload_b64=base64.b64encode(payload).decode("ascii"),
            payload_bytes=len(payload),
            payload_sha256=_sha256_bytes(payload),
            finite=finite,
            normalization=dict(normalization or {"kind": "none", "magnitude_retained": True}),
            magnitude_l2=magnitude,
            state_dependency=dict(state_dependency),
            work=dict(work),
            trust=dict(trust),
        )
        envelope.validate(max_elements=max_elements)
        return envelope

    @classmethod
    def from_f32_file(cls, path: Path, **kwargs: Any) -> "NumericEnvelope":
        source = Path(path)
        byte_length = source.stat().st_size
        max_elements = int(kwargs.get("max_elements", _MAX_ENVELOPE_ELEMENTS))
        if byte_length % 4:
            raise ValueError("float32 observation byte length is not divisible by four")
        if byte_length // 4 > max_elements:
            raise ValueError("float32 observation exceeds its allocation before read")
        shape = kwargs.get("shape")
        if not isinstance(shape, Sequence) or math.prod(shape) * 4 != byte_length:
            raise ValueError("float32 observation shape does not match its file")
        raw = source.read_bytes()
        values = struct.unpack(f"<{len(raw) // 4}f", raw)
        return cls.from_f32(values, **kwargs)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "NumericEnvelope":
        if value.get("schema") != ENVELOPE_SCHEMA:
            raise ValueError("numeric envelope schema is unsupported")
        envelope = cls(
            routing=dict(value["routing"]), meaning=dict(value["meaning"]),
            shape=tuple(value["numeric_payload"]["shape"]),
            dtype=value["numeric_payload"]["dtype"],
            endianness=value["numeric_payload"]["endianness"],
            order=value["numeric_payload"]["order"],
            payload_b64=value["numeric_payload"]["payload_b64"],
            payload_bytes=value["numeric_payload"]["payload_bytes"],
            payload_sha256=value["numeric_payload"]["payload_sha256"],
            finite=value["numeric_payload"]["finite"],
            normalization=dict(value["numeric_payload"]["normalization"]),
            magnitude_l2=value["numeric_payload"]["magnitude_l2"],
            state_dependency=dict(value["state_dependency"]), work=dict(value["work"]), trust=dict(value["trust"]),
        )
        envelope.validate()
        return envelope

    def validate(self, *, max_elements: int = _MAX_ENVELOPE_ELEMENTS, allow_nonfinite_fault: bool = True) -> bytes:
        required_routing = {"principal", "session", "episode", "operation", "sequence", "producer_identity"}
        if not required_routing.issubset(self.routing):
            raise ValueError("numeric envelope routing identity is incomplete")
        required_meaning = {"kind", "site", "frame", "semantic_question", "epistemic_attribution"}
        if not required_meaning.issubset(self.meaning):
            raise ValueError("numeric envelope meaning is incomplete")
        required_state = {"field_predecessor", "adapter_identity", "profile", "catalog_identity"}
        if not required_state.issubset(self.state_dependency):
            raise ValueError("numeric envelope state dependency is incomplete")
        required_work = {"maximum", "consumed", "status", "disposition", "continuation_id"}
        if not required_work.issubset(self.work):
            raise ValueError("numeric envelope work identity is incomplete")
        if not {"evidence_scope", "access_scope", "required_capability"}.issubset(self.trust):
            raise ValueError("numeric envelope trust boundary is incomplete")
        if self.dtype != "float32" or self.endianness != "little" or self.order != "C":
            raise ValueError("numeric envelope arithmetic layout is unsupported")
        count = math.prod(self.shape)
        if not self.shape or count > max_elements or self.payload_bytes != 4 * count:
            raise ValueError("numeric envelope allocation is invalid")
        try:
            payload = base64.b64decode(self.payload_b64, validate=True)
        except Exception as exc:
            raise ValueError("numeric envelope payload is not canonical base64") from exc
        if len(payload) != self.payload_bytes or _sha256_bytes(payload) != self.payload_sha256:
            raise ValueError("numeric envelope payload digest or length mismatch")
        unpacked = struct.unpack(f"<{count}f", payload)
        measured_finite = all(math.isfinite(value) for value in unpacked)
        if measured_finite != self.finite:
            raise ValueError("numeric envelope finite flag is false")
        if not measured_finite and not allow_nonfinite_fault:
            raise ValueError("nonfinite fault evidence cannot enter numeric evolution")
        measured_magnitude = (
            math.sqrt(math.fsum(value * value for value in unpacked))
            if measured_finite
            else math.inf
        )
        if (
            measured_finite
            and (
                not math.isfinite(self.magnitude_l2)
                or not math.isclose(
                    self.magnitude_l2,
                    measured_magnitude,
                    rel_tol=1.0e-15,
                    abs_tol=0.0,
                )
            )
        ):
            raise ValueError("numeric envelope magnitude is invalid")
        return payload

    def as_dict(self) -> dict[str, Any]:
        strides: list[int] = []
        stride = 4
        for dimension in reversed(self.shape):
            strides.append(stride)
            stride *= dimension
        strides.reverse()
        return {
            "schema": ENVELOPE_SCHEMA,
            "routing": dict(self.routing), "meaning": dict(self.meaning),
            "numeric_payload": {
                "shape": list(self.shape), "strides": strides, "dtype": self.dtype,
                "endianness": self.endianness, "order": self.order,
                "finite": self.finite, "normalization": dict(self.normalization),
                "magnitude_l2": self.magnitude_l2, "payload_bytes": self.payload_bytes,
                "payload_sha256": self.payload_sha256, "payload_b64": self.payload_b64,
                "buffer_lifetime": "immutable-envelope",
            },
            "state_dependency": dict(self.state_dependency), "work": dict(self.work), "trust": dict(self.trust),
        }


class CoupledTransactionJournal:
    """Durable nonlearned reservation and publication decisions.

    One canonical file per operation avoids an independent semantic clock.  The
    CassiFI owner operation remains the learned-state publication; this journal
    records only reservation, native trial lineage, and recovery disposition.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, operation_id: str) -> Path:
        return self.root / f"{hashlib.sha256(_identifier(operation_id, 'operation_id').encode()).hexdigest()}.json"

    def _read(self, operation_id: str) -> dict[str, Any]:
        path = self._path(operation_id)
        if not path.is_file():
            raise KeyError(operation_id)
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema") != TRANSACTION_SCHEMA or value.get("operation_id") != operation_id:
            raise RuntimeError("coupled transaction identity is corrupt")
        return value

    def _write(self, value: Mapping[str, Any]) -> dict[str, Any]:
        path = self._path(str(value["operation_id"]))
        staged = path.with_suffix(f".tmp-{os.getpid()}")
        payload = _canonical(dict(value))
        with staged.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, path)
        return dict(value)

    def reserve(self, *, operation_id: str, routing: Mapping[str, Any], identity: ModelInstrumentIdentity, field_predecessor: str, native_predecessor: Mapping[str, Any] | None, reservation: Mapping[str, int], continuation_class: str) -> Mapping[str, Any]:
        if continuation_class not in {"exact-pair", "field-only", "native-continuation-unavailable"}:
            raise ValueError("continuation class is invalid")
        normalized_reservation = {str(name): int(amount) for name, amount in reservation.items()}
        if not normalized_reservation or any(amount < 0 for amount in normalized_reservation.values()):
            raise ValueError("transaction reservation is invalid")
        value = {
            "schema": TRANSACTION_SCHEMA, "operation_id": operation_id, "status": "reserved",
            "routing": dict(routing), "adapter_identity": identity.as_dict(),
            "adapter_identity_sha256": identity.fingerprint, "field_predecessor": _digest(field_predecessor, "field_predecessor"),
            "native_predecessor": None if native_predecessor is None else dict(native_predecessor),
            "reservation": normalized_reservation, "measured_work": {"lower": 0, "upper": sum(normalized_reservation.values()), "exact": False},
            "continuation_class": continuation_class, "preparation": None, "trial": None, "publication_intent": None,
            "field_successor": None, "native_successor": None, "delivery": None,
        }
        path = self._path(operation_id)
        if path.is_file():
            existing = self._read(operation_id)
            replay_keys = (
                "routing",
                "adapter_identity",
                "adapter_identity_sha256",
                "field_predecessor",
                "native_predecessor",
                "reservation",
                "continuation_class",
            )
            if all(existing.get(key) == value.get(key) for key in replay_keys):
                return existing
            raise RuntimeError("coupled transaction operation conflicts")
        return self._write(value)

    @staticmethod
    def _counters(values: Mapping[str, Any], label: str) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for name, amount in values.items():
            key = _identifier(name, f"{label} name")
            if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                raise ValueError(f"{label} must be nonnegative integers")
            normalized[key] = amount
        return normalized

    def stage(
        self,
        operation_id: str,
        *,
        trial: Mapping[str, Any],
        measured_lower: int,
        measured_upper: int,
        exact: bool,
        work: Mapping[str, int] | None = None,
        timings: Mapping[str, int] | None = None,
        native_predecessor: Mapping[str, Any] | None = None,
        preparation: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        value = self._read(operation_id)
        if value["status"] not in {"reserved", "staged"}:
            raise RuntimeError("coupled transaction cannot stage from current state")
        if measured_lower < 0 or measured_upper < measured_lower or measured_upper > sum(value["reservation"].values()):
            raise ValueError("measured work interval exceeds reservation")
        if native_predecessor is not None:
            value["native_predecessor"] = dict(native_predecessor)
        if preparation is not None:
            value["preparation"] = dict(preparation)
        value.update(
            status="staged",
            trial=dict(trial),
            measured_work={"lower": measured_lower, "upper": measured_upper, "exact": bool(exact)},
            work=None if work is None else self._counters(work, "measured work counter"),
            timings=None if timings is None else self._counters(timings, "measured phase timing"),
        )
        return self._write(value)

    def seal(self, operation_id: str, *, field_successor: str, native_successor: Mapping[str, Any] | None, delivery: Mapping[str, Any], admission: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        value = self._read(operation_id)
        if value["status"] not in {"staged", "sealed"}:
            raise RuntimeError("coupled transaction cannot seal from current state")
        intent = {
            "field_successor": _digest(field_successor, "field_successor"),
            "native_successor": None if native_successor is None else dict(native_successor),
            "delivery": dict(delivery),
            "admission": None if admission is None else dict(admission),
        }
        if value["status"] == "sealed" and value["publication_intent"] != intent:
            raise RuntimeError("coupled publication intent conflicts")
        value.update(status="sealed", publication_intent=intent)
        return self._write(value)

    def commit(self, operation_id: str) -> Mapping[str, Any]:
        value = self._read(operation_id)
        if value["status"] == "committed":
            return value
        if value["status"] != "sealed":
            raise RuntimeError("coupled transaction has no sealed publication intent")
        intent = value["publication_intent"]
        value.update(
            status="committed",
            field_successor=intent["field_successor"],
            native_successor=intent["native_successor"],
            delivery=intent["delivery"],
            admission=intent.get("admission"),
        )
        return self._write(value)

    def reject(self, operation_id: str, *, reason: str, cancelled: bool = False) -> Mapping[str, Any]:
        value = self._read(operation_id)
        if value["status"] == "committed":
            raise RuntimeError("committed coupled transaction cannot be rejected")
        value.update(status="cancelled" if cancelled else "rejected", rejection_reason=_identifier(reason, "reason"))
        return self._write(value)

    @staticmethod
    def _artifact_matches(descriptor: Any) -> bool:
        if not isinstance(descriptor, Mapping):
            return False
        path_value = descriptor.get("path")
        expected_sha = descriptor.get("sha256")
        expected_bytes = descriptor.get("bytes")
        if (
            not isinstance(path_value, str)
            or not path_value
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
            or isinstance(expected_bytes, bool)
            or not isinstance(expected_bytes, int)
            or expected_bytes < 0
        ):
            return False
        try:
            path = Path(path_value)
            return (
                path.is_file()
                and path.stat().st_size == expected_bytes
                and sha256_path(path) == expected_sha
            )
        except (OSError, ValueError):
            return False

    @classmethod
    def _preparation_is_intact(cls, transaction: Mapping[str, Any]) -> bool:
        preparation = transaction.get("preparation")
        if preparation is None:
            # Older journal entries predate preparation provenance.  Keep their
            # existing recovery semantics; new native entries always stage it.
            return True
        if not isinstance(preparation, Mapping):
            return False
        original_seed = preparation.get("original_seed")
        state = preparation.get("state")
        if not cls._artifact_matches(original_seed) or not cls._artifact_matches(state):
            return False
        predecessor = transaction.get("native_predecessor")
        if not isinstance(predecessor, Mapping) or (
            predecessor.get("path") != state.get("path")
            or predecessor.get("sha256") != state.get("sha256")
        ):
            return False
        sources = preparation.get("sources")
        if not isinstance(sources, list) or not sources:
            return False
        return all(cls._artifact_matches(source) for source in sources)

    def recover(self, operation_id: str, *, field_root: str) -> Mapping[str, Any]:
        value = self._read(operation_id)
        status = value["status"]
        if status in {"reserved", "staged"}:
            return {"status": "unaccepted-trial", "charge": value["reservation"], "continuation": "discard-or-explicit-retry", "transaction": value}
        if status == "sealed":
            return {"status": "publication-reconciliation-required", "charge": value["measured_work"], "continuation": value["continuation_class"], "transaction": value}
        if status == "committed":
            exact_field = value["field_successor"] == field_root
            native = value.get("native_successor")
            exact_native = True
            if native is not None and native.get("path"):
                path = Path(native["path"])
                exact_native = path.is_file() and sha256_path(path) == native.get("sha256")
                context = native.get("native_context")
                if exact_native and context is not None:
                    # A paired continuation needs the native context, so a
                    # missing or altered snapshot is not an exact pair.
                    snapshot = Path(context["path"])
                    exact_native = (
                        snapshot.is_file()
                        and sha256_path(snapshot) == context.get("sha256")
                    )
            if exact_native:
                exact_native = self._preparation_is_intact(value)
            return {
                "status": "exact-pair" if exact_field and exact_native else "native-continuation-unavailable" if exact_field else "field-root-mismatch",
                "delivery": value.get("delivery"), "transaction": value,
                "adapter_identity_sha256": value.get("adapter_identity_sha256"),
            }
        return {"status": status, "transaction": value}

    def publication_status(self, operation_id: str) -> Mapping[str, Any]:
        """Report whether this transaction's semantic payload may be recalled.

        The journal is the durable commit authority.  A paired semantic
        admission is eligible only while its transaction is committed, so an
        interrupted trial cannot be recalled as accepted knowledge.
        """
        operation_id = _identifier(operation_id, "operation_id")
        try:
            value = self._read(operation_id)
        except KeyError:
            return {
                "operation_id": operation_id,
                "status": "missing",
                "eligible": False,
                "reason": "transaction-missing",
                "admission": None,
                "continuation_class": None,
            }
        status = str(value.get("status"))
        if status == "committed":
            if self._preparation_is_intact(value):
                eligible, reason = True, "committed"
            else:
                eligible, reason = False, "preparation-artifact-unavailable"
        elif status == "sealed":
            eligible, reason = False, "publication-reconciliation-required"
        elif status in {"reserved", "staged"}:
            eligible, reason = False, "unaccepted-trial"
        else:
            eligible, reason = False, status
        measured = value.get("measured_work") or {}
        charged = (
            value.get("reservation")
            if int(measured.get("lower", 0) or 0) == 0
            else measured
        )
        return {
            "operation_id": operation_id,
            "status": status,
            "eligible": eligible,
            "reason": reason,
            "admission": value.get("admission"),
            "continuation_class": value.get("continuation_class"),
            "charge": charged,
        }

    def unsettled(self) -> tuple[Mapping[str, Any], ...]:
        """List every transaction that still requires an operator decision."""
        rows: list[Mapping[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (
                value.get("schema") != TRANSACTION_SCHEMA
                or not isinstance(value.get("operation_id"), str)
                or value.get("status") in {"committed", "rejected", "cancelled"}
            ):
                continue
            measured = value.get("measured_work") or {}
            rows.append(
                {
                    "operation_id": value["operation_id"],
                    "status": value.get("status"),
                    "continuation_class": value.get("continuation_class"),
                    "admission": value.get("admission"),
                    "field_successor": value.get("field_successor"),
                    "charge": value.get("reservation")
                    if int(measured.get("lower", 0) or 0) == 0
                    else measured,
                }
            )
        return tuple(rows)


class LatentQwenInstrument:
    """Identified Qwen residual capture and Qi intervention harness.

    The harness exposes observations and an isolated Qi trial, but not a
    resumable native KV/model context.  Its continuation class is therefore
    explicitly unavailable after the process exits.
    """

    def __init__(
        self,
        *,
        executable: Path,
        model: Path,
        state: Path,
        backend: str,
        layer_count: int,
        embedding_width: int,
    ) -> None:
        self.executable = Path(executable).resolve()
        self.model = Path(model).resolve()
        self.state = Path(state).resolve()
        for path in (self.executable, self.model, self.state):
            if not path.is_file():
                raise FileNotFoundError(path)
        if backend not in {"cpu", "gpu"}:
            raise ValueError("backend must be cpu or gpu")
        if layer_count < 1 or embedding_width < 1:
            raise ValueError("latent model dimensions must be positive")
        self.backend = backend
        self.layer_count = layer_count
        self.embedding_width = embedding_width
        model_sha = sha256_path(self.model)
        hook = (
            Path(__file__).resolve().parent
            / "native/llama.cpp/tests/test-cassi-qi-latent.cpp"
        )
        self.identity = ModelInstrumentIdentity(
            adapter_id="cassi-qwen-latent",
            adapter_version="1",
            model_sha256=model_sha,
            architecture="qwen3.5",
            quantization="declared-by-gguf",
            tokenizer_sha256=hashlib.sha256(
                f"embedded-gguf-tokenizer:{model_sha}".encode("ascii")
            ).hexdigest(),
            runtime_sha256=sha256_path(self.executable),
            hook_sha256=sha256_path(hook),
            arithmetic_profile="native-f32-backend-dependent",
            context_policy="single-sequence-bounded-prompt",
            backend=backend,
        )

    def capabilities(self, field_layer: int) -> AdapterCapabilities:
        if not 0 <= field_layer < self.layer_count:
            raise ValueError("field layer is outside the declared model")
        observation_sites = tuple(
            f"qwen35.block.{layer}.input"
            for layer in range(field_layer, self.layer_count)
        )
        return AdapterCapabilities(
            profile="latent-instrument",
            structured_requests=False,
            activation_observation_sites=observation_sites,
            intervention_sites=(f"qwen35.block.{field_layer}.input",),
            trial_state="none",
            selective_operations=("qwen-forward", "qi-field-intervention"),
            emission_owner="model",
            native_persistence="none",
            partial_acceptance=False,
            cancellation=False,
            max_elements=max(self.embedding_width, 1),
        )

    def execute(
        self,
        *,
        prompt: str,
        field_layer: int,
        field_steps: int,
        alpha: float,
        generate_tokens: int,
        trial_dir: Path,
        routing: Mapping[str, Any],
        field_predecessor: str,
        catalog_identity: str,
        reset_each_token: bool = False,
        phase_shuffle_after_prompt: bool = False,
    ) -> Mapping[str, Any]:
        capabilities = self.capabilities(field_layer)
        if field_steps < 0 or field_steps > 1_000_000:
            raise ValueError("field steps are outside the bounded range")
        if not math.isfinite(alpha) or alpha < 0.0:
            raise ValueError("intervention alpha must be finite and nonnegative")
        if generate_tokens < 0 or generate_tokens > 256:
            raise ValueError("generated token count is outside the bounded range")
        if field_steps:
            capabilities.require(
                "latent-intervention",
                site=f"qwen35.block.{field_layer}.input",
            )
        trial_dir = Path(trial_dir).resolve()
        trial_dir.mkdir(parents=True, exist_ok=False)
        prompt_path = trial_dir / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        command = [
            str(self.executable),
            str(self.model),
            str(self.state),
            self.backend,
            str(prompt_path),
            str(field_layer),
            str(field_steps),
            repr(alpha),
            str(generate_tokens),
            str(trial_dir),
            "1" if reset_each_token else "0",
            "1" if phase_shuffle_after_prompt else "0",
        ]
        started = time.perf_counter_ns()
        completed = subprocess.run(
            command,
            cwd=self.executable.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=600,
            check=False,
        )
        elapsed_ns = time.perf_counter_ns() - started
        if completed.returncode != 0:
            raise RuntimeError(
                f"latent Qwen instrument failed ({completed.returncode}): "
                f"{completed.stderr.strip()}"
            )
        if not completed.stdout.strip():
            raise RuntimeError("latent Qwen instrument omitted its receipt")
        receipt = json.loads(completed.stdout)
        if (
            receipt.get("schema") != "cassi.qi.latent.v1"
            or receipt.get("verdict") != "PASS"
            or receipt.get("layer") != field_layer
            or receipt.get("steps") != field_steps
        ):
            raise RuntimeError("latent Qwen instrument receipt is incompatible")
        if len(receipt.get("captured_layers", [])) != (
            self.layer_count - field_layer
        ):
            raise RuntimeError("latent Qwen capture layer closure is incomplete")
        dependency = {
            "field_predecessor": _digest(
                field_predecessor, "field_predecessor"
            ),
            "native_predecessor": {
                "state_path": str(self.state),
                "state_sha256": sha256_path(self.state),
            },
            "adapter_identity": self.identity.fingerprint,
            "model_identity": self.identity.model_sha256,
            "profile": capabilities.profile,
            "catalog_identity": _digest(
                catalog_identity, "catalog_identity"
            ),
            "read_versions": [],
            "write_versions": [],
        }
        envelopes: list[dict[str, Any]] = []
        for capture in receipt["captured_layers"]:
            layer = int(capture["layer"])
            site = f"qwen35.block.{layer}.input"
            capabilities.require("activation-observation", site=site)
            path = Path(str(capture["path"]))
            if not path.is_absolute():
                path = (self.executable.parent / path).resolve()
            envelope = NumericEnvelope.from_f32_file(
                path,
                shape=(1, self.embedding_width),
                routing={
                    **dict(routing),
                    "producer_identity": self.identity.fingerprint,
                    "measurement_id": (
                        f"{routing.get('operation')}:{site}:last-prompt-position"
                    ),
                    "trial_ancestry": list(
                        routing.get("trial_ancestry", [])
                    ),
                    "accepted_prefix": int(
                        routing.get("accepted_prefix", 0)
                    ),
                },
                meaning={
                    "kind": "activation-observation",
                    "site": site,
                    "frame": (
                        f"qwen35-residual-input-f32-width-"
                        f"{self.embedding_width}"
                    ),
                    "semantic_question": dict(
                        routing.get("semantic_question", {})
                    ),
                    "epistemic_attribution": (
                        "identified-model-computation"
                    ),
                    "position": "last-prompt-token",
                },
                state_dependency=dependency,
                work={
                    "maximum": field_steps + generate_tokens + 1,
                    "consumed": field_steps + len(
                        receipt.get("generation_token_ids", [])
                    ) + 1,
                    "status": "complete",
                    "disposition": "staged",
                    "continuation_id": (
                        f"{routing.get('operation')}:{site}:complete"
                    ),
                },
                trust={
                    "evidence_scope": routing.get("principal"),
                    "access_scope": routing.get(
                        "access_scope", "activation-opt-in"
                    ),
                    "required_capability": "activation-observation",
                },
                max_elements=capabilities.max_elements,
            )
            envelopes.append(envelope.as_dict())
        state_path = trial_dir / "state-after.f32"
        state_successor = None
        if state_path.is_file():
            state_successor = {
                "path": str(state_path),
                "sha256": sha256_path(state_path),
                "bytes": state_path.stat().st_size,
                "semantics": "qi-field-trial-not-native-kv-context",
            }
        return {
            "schema": "cassi.qwen-latent-instrument-result.v1",
            "status": "staged",
            "identity": self.identity.as_dict(),
            "identity_sha256": self.identity.fingerprint,
            "capabilities": capabilities.as_dict(),
            "receipt": receipt,
            "measurements": envelopes,
            "state_successor": state_successor,
            "continuation_class": "native-continuation-unavailable",
            "elapsed_ns": elapsed_ns,
            "ownership": {
                "output_owner": "model",
                "field_intervention_executed": field_steps > 0,
                "native_graph_nodes": receipt.get("graph_nodes"),
                "native_layers_skipped": 0,
                "silent_fallback": False,
            },
        }


DIFFERENTIAL_STATE_SCHEMA = "cassi.qwen-differential-field-state.v1"


def _read_state_floats(path: Path) -> list[float]:
    raw = Path(path).read_bytes()
    if len(raw) == 0:
        raise RuntimeError(f"state is an empty f32 buffer: {path}")
    if len(raw) % 4:
        raise RuntimeError(f"state is not an integral little-endian f32 buffer: {path}")
    try:
        values = list(struct.unpack(f"<{len(raw) // 4}f", raw))
    except struct.error as exc:
        raise RuntimeError(f"state is not a readable little-endian f32 buffer: {path}") from exc
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"state contains non-finite f32 data: {path}")
    return values


def differential_field_state(
    *,
    instrument: "QwenNativeInstrument",
    frame: str,
    reference: str,
    trial_dir: Path,
    output: Path,
) -> Mapping[str, Any]:
    """Build an experimental numerical contrast between two field seeds.

    This is raw elementwise subtraction of two nonlinear field trajectories.
    It is not proof that semantics, memory, or a value has been isolated.  The
    caller must retain both source prompts and source states as provenance.
    """

    for label, prompt in (("frame", frame), ("reference", reference)):
        if not isinstance(prompt, str) or not prompt:
            raise ValueError(f"{label} prompt must be nonempty")
    if frame == reference:
        raise ValueError("a differential state needs two different prompts")
    root = Path(trial_dir).resolve()
    root.mkdir(parents=True, exist_ok=False)
    destination = Path(output).resolve()
    if not destination.parent.is_dir():
        raise FileNotFoundError(destination.parent)
    if destination.exists():
        raise FileExistsError(f"differential output already exists: {destination}")
    original_seed = {
        "path": str(instrument.state),
        "sha256": sha256_path(instrument.state),
        "bytes": instrument.state.stat().st_size,
    }
    if destination == instrument.state.resolve():
        raise ValueError("differential output must not overwrite the instrument seed")
    expected_sources = {
        (root / "frame" / "state-after.f32").resolve(),
        (root / "reference" / "state-after.f32").resolve(),
    }
    if destination in expected_sources:
        raise ValueError("differential output must not overwrite a source state")
    seed_elements = len(_read_state_floats(instrument.state))

    seeded: dict[str, Path] = {}
    digests: dict[str, str] = {}
    seed_receipts: list[Mapping[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    for role, prompt in (("frame", frame), ("reference", reference)):
        outcome = instrument.execute(
            mode="field",
            prompt=prompt,
            tokens=1,
            trial_dir=root / role,
        )
        seed_receipts.append(outcome["receipt"])
        source = Path(outcome["state_successor"]["path"]).resolve()
        seeded[role] = source
        digests[role] = str(outcome["state_successor"]["sha256"])
        source_stat = source.stat()
        source_rows.append(
            {
                "role": role,
                "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
                "prompt_bytes": len(prompt.encode("utf-8")),
                "prompt_tokens": int(outcome["receipt"].get("prompt_tokens", 0)),
                "path": str(source),
                "sha256": digests[role],
                "bytes": source_stat.st_size,
            }
        )
    frame_values = _read_state_floats(seeded["frame"])
    reference_values = _read_state_floats(seeded["reference"])
    if len(frame_values) != seed_elements or len(reference_values) != seed_elements:
        raise RuntimeError("field seed preparation changed the original state shape")
    difference = [a - b for a, b in zip(frame_values, reference_values)]
    if not all(math.isfinite(value) for value in difference):
        raise RuntimeError("differential subtraction produced non-finite f32 data")
    try:
        packed = struct.pack(f"<{len(difference)}f", *difference)
    except (OverflowError, struct.error) as exc:
        raise RuntimeError("differential subtraction is incompatible with f32") from exc
    packed_values = struct.unpack(f"<{len(difference)}f", packed)
    if not all(math.isfinite(value) for value in packed_values):
        raise RuntimeError("differential subtraction is incompatible with f32")
    with destination.open("xb") as stream:
        stream.write(packed)
        stream.flush()
        os.fsync(stream.fileno())

    def amplitude(values: Sequence[float]) -> float:
        return max((abs(value) for value in values), default=0.0)

    def norm(values: Sequence[float]) -> float:
        return math.sqrt(math.fsum(value * value for value in values))

    frame_norm = norm(frame_values)
    difference_norm = norm(difference)
    if not math.isfinite(frame_norm) or not math.isfinite(difference_norm):
        raise RuntimeError("differential state norm is non-finite")
    return {
        "schema": DIFFERENTIAL_STATE_SCHEMA,
        "instrument_identity_sha256": instrument.identity.fingerprint,
        "effective_coupling": dict(instrument.coupling),
        "composition_method": "float32-elementwise-subtraction-experimental-contrast",
        "original_seed": original_seed,
        "state": {
            "path": str(destination),
            "sha256": sha256_path(destination),
            "bytes": destination.stat().st_size,
            "elements": len(difference),
        },
        "sources": source_rows,
        "difference": {
            "max_amplitude": amplitude(difference),
            "norm_fraction": 0.0 if frame_norm == 0.0 else difference_norm / frame_norm,
        },
        "preparation_work": {
            "field_seed_runs": len(source_rows),
            "field_seed_forward_passes": sum(
                int(receipt.get("qwen_forward_passes", 0))
                for receipt in seed_receipts
            ),
            "field_seed_steps": sum(
                int(receipt["prompt_tokens"]) + int(receipt["generated_tokens"])
                for receipt in seed_receipts
            ),
            "field_seed_logits_read": sum(
                int(receipt["field_logits_read"]) for receipt in seed_receipts
            ),
        },
    }


class QwenNativeInstrument:
    """Actual ``cassi-qwen`` executable as a fixed model instrument."""

    def __init__(self, *, executable: Path, model: Path, state: Path, backend: str, architecture: str = "qwen3.5", quantization: str = "declared-by-gguf", native_context: bool = True, coupling: Mapping[str, Any] | None = None) -> None:
        self.executable = Path(executable).resolve()
        self.model = Path(model).resolve()
        self.state = Path(state).resolve()
        for path in (self.executable, self.model, self.state):
            if not path.is_file():
                raise FileNotFoundError(path)
        if backend not in {"cpu", "gpu"}:
            raise ValueError("backend must be cpu or gpu")
        self.native_context = bool(native_context)
        source = Path(__file__).resolve().parent / "native/llama.cpp/examples/cassi-qwen/cassi-qwen.cpp"
        hook_sha = sha256_path(source)
        model_sha = sha256_path(self.model)
        tokenizer_sha = hashlib.sha256(
            f"embedded-gguf-tokenizer:{model_sha}".encode("ascii")
        ).hexdigest()
        effective_coupling = dict(DEFAULT_NATIVE_COUPLING)
        if coupling is not None:
            effective_coupling.update(dict(coupling))
        self.identity = ModelInstrumentIdentity(
            adapter_id="cassi-qwen-native", adapter_version="1", model_sha256=model_sha,
            architecture=architecture, quantization=quantization, tokenizer_sha256=tokenizer_sha,
            runtime_sha256=sha256_path(self.executable), hook_sha256=hook_sha,
            arithmetic_profile="native-f32-backend-dependent",
            context_policy=(
                "single-sequence-nctx-256-full-context-snapshot"
                if self.native_context
                else "single-sequence-nctx-256-field-state-only"
            ),
            backend=backend,
            coupling=effective_coupling,
        )
        self.backend = backend
        self.coupling: Mapping[str, float] = self.identity.coupling or {}

    def capabilities(self, mode: str) -> AdapterCapabilities:
        if mode not in {"coupled", "field"}:
            raise ValueError("native Qwen mode is invalid")
        # Field mode never builds a llama context: the Qi field state is the
        # complete trial state.  Coupled mode owns a native context, so it is
        # exactly resumable only when the full context snapshot is captured.
        displacement = int(self.coupling.get("displacement", 0))
        if mode == "field":
            trial_state, persistence = "exact-field-state", "exact"
            lm_head_owner, logit_owner, sampler_owner = "none", "field", "field"
        elif self.native_context:
            trial_state, persistence = "exact-context", "exact"
            lm_head_owner = "field" if displacement >= 6 else "model"
            logit_owner = lm_head_owner
            sampler_owner = "native-llama"
        else:
            trial_state, persistence = "none", "field-state"
            lm_head_owner = "field" if displacement >= 6 else "model"
            logit_owner = lm_head_owner
            sampler_owner = "native-llama"
        return AdapterCapabilities(
            profile="latent-instrument" if mode == "coupled" else "standalone-field",
            structured_requests=False, activation_observation_sites=(), intervention_sites=(),
            trial_state=trial_state,
            selective_operations=("field-step", "vocabulary-read") if mode == "field" else ("qwen-forward", "field-step"),
            emission_owner="field" if mode == "field" or displacement >= 6 else "model",
            native_persistence=persistence,
            partial_acceptance=False, cancellation=False,
            lm_head_owner=lm_head_owner,
            sampler_owner=sampler_owner,
            logit_owner=logit_owner,
        )

    def continuation_class(self, mode: str) -> str:
        """Name what kind of continuation this mode can actually restore."""
        capabilities = self.capabilities(mode)
        if mode == "field":
            return "field-only"
        if capabilities.supports("exact-native-resume"):
            return "exact-pair"
        return "native-continuation-unavailable"

    def prompt_token_room(self, mode: str, tokens: int) -> int | None:
        """Tokens a frame may occupy so this trial's generation still fits.

        Coupled mode decodes the frame and the generated tokens into one fixed
        context, so the frame's room shrinks as the requested generation grows.
        Field mode keeps no context: the frame's only cost is field stepping.
        """

        if mode not in {"coupled", "field"}:
            raise ValueError("native Qwen mode is invalid")
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 1:
            raise ValueError("tokens must be a positive integer")
        if mode == "field":
            return None
        room = NATIVE_CONTEXT_TOKENS - tokens
        if room < 1:
            raise ValueError(
                f"requested generation of {tokens} tokens leaves no room in the "
                f"{NATIVE_CONTEXT_TOKENS}-token emitter context"
            )
        return room

    def count_prompt_tokens(self, prompt: str) -> int:
        """Measure how many tokens this runtime's own tokenizer assigns to a prompt."""

        if not isinstance(prompt, str) or not prompt:
            raise ValueError("prompt must be nonempty")
        completed = subprocess.run(
            [str(self.executable), "--model", str(self.model), "--mode", "count", "--prompt", prompt],
            cwd=self.executable.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=300,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"native Qwen tokenizer failed ({completed.returncode}): {completed.stderr.strip()}"
            )
        lines = completed.stdout.splitlines()
        if not lines:
            raise RuntimeError("native Qwen tokenizer omitted its receipt")
        receipt = json.loads(lines[-1])
        if (
            receipt.get("schema") != "cassi.qi.native-runtime.v1"
            or receipt.get("verdict") != "PASS"
            or receipt.get("mode") != "count"
        ):
            raise RuntimeError("native Qwen tokenizer receipt is incompatible")
        tokens = receipt.get("prompt_tokens")
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            raise RuntimeError("native Qwen tokenizer reported no token count")
        return tokens

    def _check_observed_ownership(
        self,
        receipt: Mapping[str, Any],
        capabilities: AdapterCapabilities,
    ) -> None:
        """Reject receipts whose ownership or work counters are not auditable."""

        for name in ("lm_head_owner", "sampler_owner", "logit_owner"):
            observed = receipt.get(name)
            expected = getattr(capabilities, name)
            if observed != expected:
                raise RuntimeError(
                    f"native Qwen receipt {name} {observed!r} does not match "
                    f"instrument {expected!r}"
                )
        for name in (
            "qwen_forward_passes",
            "model_logits_read",
            "field_logits_read",
            "lm_head_rows_computed",
            "lm_head_rows_skipped",
            "sampler_steps",
        ):
            observed = receipt.get(name)
            if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
                raise RuntimeError(
                    f"native Qwen receipt counter {name} is not a nonnegative integer"
                )

    def _check_observed_coupling(self, receipt: Mapping[str, Any], mode: str) -> None:
        """Reject any receipt whose field coupling is not the declared one.

        The declared coupling is part of the identity; the receipt reports what
        the runtime actually ran.  A quiet disagreement between the two would
        make every downstream measurement describe the wrong trial.  Field mode
        builds no transformer forward, so a coupling there is reported only if
        the runtime chooses to.
        """

        for name, (_, kind) in COUPLING_OPTIONS.items():
            if name not in receipt:
                if mode == "coupled":
                    raise RuntimeError(f"native Qwen receipt omits coupling option {name}")
                continue
            observed = receipt[name]
            if isinstance(observed, bool) or not isinstance(observed, (int, float)):
                raise RuntimeError(f"native Qwen receipt coupling option {name} is not numeric")
            declared = self.coupling.get(name)
            if declared is None:
                continue
            if kind is int:
                if int(observed) != int(declared):
                    raise RuntimeError(
                        f"native Qwen ran displacement {int(observed)}, instrument declared {int(declared)}"
                    )
            elif _float32(observed) != _float32(declared):
                raise RuntimeError(
                    f"native Qwen ran {name} {_float32(observed)!r}, instrument declared {_float32(declared)!r}"
                )

    def execute(
        self,
        *,
        mode: str,
        prompt: str,
        tokens: int,
        trial_dir: Path,
        field_layer: int = -1,
        context_in: Path | None = None,
        state_in: Path | None = None,
    ) -> Mapping[str, Any]:
        capabilities = self.capabilities(mode)
        if isinstance(tokens, bool) or not 1 <= tokens <= 256:
            raise ValueError("tokens must be in [1, 256]")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("prompt must be nonempty")
        source_state = self.state if state_in is None else Path(state_in).resolve()
        if not source_state.is_file():
            raise FileNotFoundError(source_state)
        state_predecessor = {
            "path": str(source_state),
            "sha256": sha256_path(source_state),
            "bytes": source_state.stat().st_size,
            "kind": "native-field-state-seed",
        }
        trial_dir = Path(trial_dir).resolve()
        trial_dir.mkdir(parents=True, exist_ok=False)
        state_after = trial_dir / "state-after.f32"
        context_after = trial_dir / "context-after.bin"
        command = [str(self.executable), "--model", str(self.model), "--state", str(source_state), "--out-state", str(state_after), "--mode", mode, "--prompt", prompt, "--tokens", str(tokens), "--gpu-layers", "99" if self.backend == "gpu" else "0", "--field-layer", str(field_layer)]
        for name, value in sorted(self.coupling.items()):
            option, kind = COUPLING_OPTIONS[name]
            command += [option, str(int(value)) if kind is int else repr(float(value))]
        resume = mode == "coupled" and self.native_context
        if resume:
            command += ["--out-context", str(context_after)]
        if context_in is not None:
            if not resume:
                raise UnsupportedCapability("exact-native-resume", capabilities.as_dict())
            source_context = Path(context_in).resolve()
            if not source_context.is_file():
                raise FileNotFoundError(source_context)
            command += ["--in-context", str(source_context)]
        started = time.perf_counter_ns()
        completed = subprocess.run(command, cwd=self.executable.parent, capture_output=True, text=True, encoding="utf-8", errors="strict", timeout=600, check=False)
        elapsed_ns = time.perf_counter_ns() - started
        if completed.returncode != 0:
            raise RuntimeError(f"native Qwen instrument failed ({completed.returncode}): {completed.stderr.strip()}")
        lines = completed.stdout.splitlines()
        if len(lines) < 2:
            raise RuntimeError("native Qwen instrument omitted its receipt")
        receipt = json.loads(lines[-1])
        if receipt.get("schema") != "cassi.qi.native-runtime.v1" or receipt.get("verdict") != "PASS" or receipt.get("mode") != mode:
            raise RuntimeError("native Qwen instrument receipt is incompatible")
        if not state_after.is_file():
            raise RuntimeError("native Qwen instrument omitted trial state")
        if resume and not context_after.is_file():
            raise RuntimeError("native Qwen instrument omitted its native context snapshot")
        output = "\n".join(lines[:-1])
        if len(output.encode("utf-8")) != receipt.get("output_bytes"):
            raise RuntimeError("native Qwen output byte count is inconsistent")
        self._check_observed_ownership(receipt, capabilities)
        self._check_observed_coupling(receipt, mode)
        native_context = (
            {
                "path": str(context_after),
                "sha256": sha256_path(context_after),
                "bytes": context_after.stat().st_size,
                "restored_bytes": int(receipt.get("context_restored_bytes", 0)),
                "decoded_tokens": int(receipt.get("decoded_tokens", 0)),
                "prompt_tokens": int(receipt.get("prompt_tokens", 0)),
            }
            if resume
            else None
        )
        ownership = {
            "output_owner": capabilities.emission_owner,
            "lm_head_owner": capabilities.lm_head_owner,
            "sampler_owner": capabilities.sampler_owner,
            "logit_owner": capabilities.logit_owner,
            "qwen_forward_passes": int(receipt.get("qwen_forward_passes", 0)),
            "model_logits_read": int(receipt.get("model_logits_read", 0) or 0),
            "field_logits_read": int(receipt.get("field_logits_read", 0) or 0),
            "lm_head_rows_computed": int(receipt.get("lm_head_rows_computed", 0) or 0),
            "lm_head_rows_skipped": int(receipt.get("lm_head_rows_skipped", 0) or 0),
            "sampler_steps": int(receipt.get("sampler_steps", 0) or 0),
            "qwen_tensor_bytes_loaded": receipt.get("qwen_tensor_bytes_loaded"),
            "native_dynamic_state_bytes_removed": 0,
            "native_state_bytes_committed": state_after.stat().st_size,
            "native_context_bytes_committed": 0 if native_context is None else native_context["bytes"],
            "native_ops_skipped": "full-transformer-forward" if mode == "field" else 0,
            "silent_native_fallback": False,
        }
        state_successor = {
            "path": str(state_after),
            "sha256": sha256_path(state_after),
            "bytes": state_after.stat().st_size,
            "kind": "qi-field-state" if native_context is None else "qi-field-state-and-native-context",
            "native_context": native_context,
            "native_predecessor": state_predecessor,
            "instrument_identity_sha256": self.identity.fingerprint,
            "effective_coupling": dict(self.coupling),
        }
        return {
            "schema": NATIVE_RESULT_SCHEMA, "status": "staged", "mode": mode,
            "identity": self.identity.as_dict(), "identity_sha256": self.identity.fingerprint,
            "capabilities": capabilities.as_dict(), "output": output, "receipt": receipt,
            "state_predecessor": state_predecessor,
            "state_successor": state_successor,
            "continuation_class": self.continuation_class(mode),
            "elapsed_ns": elapsed_ns, "ownership": ownership,
        }
