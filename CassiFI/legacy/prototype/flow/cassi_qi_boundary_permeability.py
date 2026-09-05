"""W7P passive field-owned sensory permeability and openness evidence."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import torch

from cassi_qi_profile import canonical_hash
from cassi_qi_scattering import QiInterval, QiPortDescriptor, QiScatteringReceipt, build_qi_scattering_receipt

PERMEABILITY_PROFILE_SCHEMA = "cassi.qi-flow-boundary-permeability-profile.v1"
PERMEABILITY_DESCRIPTOR_SCHEMA = "cassi.qi-flow-boundary-permeability-descriptor.v1"
PERMEABILITY_ADMISSION_SCHEMA = "cassi.qi-flow-permeability-admission.v1"
PERMEABILITY_OPERATOR_SCHEMA = "cassi.qi-flow-permeability-operator.v1"
REQUIRED_OPENNESS_CONTROLS = (
    "state_gate_frozen",
    "matched_energy_phase_current_reversal",
    "field_frozen",
    "gate_off_diagnostic",
    "shuffled_probe_order",
    "finite_repeated_probe",
)
SENSORY_OPENNESS_SCHEMA = "cassi.qi-flow-sensory-openness.v1"


class QiPermeabilityError(ValueError):
    """Invalid immutable profile, field observation, packet, or work ledger."""


PermeabilityError = QiPermeabilityError


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise QiPermeabilityError(f"{name} must be a non-empty UTF-8 string")
    return value


def _digest(name: str, value: Any) -> str:
    result = _text(name, value)
    if len(result) != 64 or result.lower() != result or any(ch not in "0123456789abcdef" for ch in result):
        raise QiPermeabilityError(f"{name} must be a lowercase SHA-256 digest")
    return result


def _finite(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QiPermeabilityError(f"{name} must be a finite real")
    result = float(value)
    if not math.isfinite(result) or (result == 0.0 and math.copysign(1.0, result) < 0):
        raise QiPermeabilityError(f"{name} must be finite and not negative zero")
    return result


def _nonnegative(name: str, value: Any) -> float:
    result = _finite(name, value)
    if result < 0.0:
        raise QiPermeabilityError(f"{name} must be non-negative")
    return result


def _positive(name: str, value: Any) -> float:
    result = _finite(name, value)
    if result <= 0.0:
        raise QiPermeabilityError(f"{name} must be positive")
    return result


def _integer(name: str, value: Any, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise QiPermeabilityError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _vector(name: str, values: Sequence[Any], *, positive: bool = False) -> tuple[float, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise QiPermeabilityError(f"{name} must be a vector")
    result = tuple(_finite(name, value) for value in values)
    if not result or positive and any(value <= 0.0 for value in result):
        raise QiPermeabilityError(f"{name} is empty or outside its domain")
    return result


def _complex_vector(name: str, values: Sequence[Any]) -> tuple[complex, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise QiPermeabilityError(f"{name} must be a vector")
    try:
        result = tuple(complex(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise QiPermeabilityError(f"{name} is not complex-valued") from exc
    if not result or any(not math.isfinite(value.real) or not math.isfinite(value.imag) for value in result):
        raise QiPermeabilityError(f"{name} must contain finite values")
    return result


def _state_field(state: Any) -> torch.Tensor:
    field = getattr(state, "field", state)
    if not isinstance(field, torch.Tensor) or field.numel() == 0 or not torch.is_complex(field) or not bool(torch.isfinite(field).all().item()):
        raise QiPermeabilityError("state must expose a non-empty finite complex tensor")
    return field


def _state_hash(state: Any, profile: Any | None = None) -> str:
    if hasattr(state, "state_sha256") and profile is not None:
        try:
            result = str(state.state_sha256(profile))
            return _digest("state_sha256", result)
        except Exception as exc:
            raise QiPermeabilityError(f"state identity failed: {exc}") from exc
    field = _state_field(state).detach().contiguous().cpu()
    raw = field.numpy().tobytes(order="C")
    return canonical_hash({"dtype": str(field.dtype), "shape": list(field.shape), "raw_sha256": hashlib.sha256(raw).hexdigest()}, "cassi.qi-flow-permeability-state.v1")


def _interval(value: Any, name: str) -> QiInterval:
    try:
        result = value if isinstance(value, QiInterval) else QiInterval.exact(value)
    except Exception as exc:
        raise QiPermeabilityError(f"{name} is not a valid interval") from exc
    if not result.resolved or not math.isfinite(result.lower) or not math.isfinite(result.upper) or result.lower < 0.0:
        raise QiPermeabilityError(f"{name} must be a resolved finite non-negative interval")
    return result


def _ratio(numerator: QiInterval, denominator: QiInterval, name: str) -> QiInterval:
    if not numerator.resolved or not denominator.resolved or denominator.lower <= 0.0:
        raise QiPermeabilityError(f"{name} has an unresolved or non-positive incident denominator")
    return QiInterval(numerator.lower / denominator.upper, numerator.upper / denominator.lower)


def _close(left: float, right: float, tol: float = 2.0e-10) -> bool:
    return abs(left - right) <= tol * max(1.0, abs(left), abs(right))


@dataclass(frozen=True, slots=True)
class QiBoundaryPermeabilityDescriptor:
    """Fixed characteristic basis, metric, scale, orientation, and port operator."""

    port_id: str
    interface_id: str
    scale: int
    orientation: int
    component: int
    port: Any
    characteristic_basis: tuple[complex, ...]
    metric: tuple[float, ...]
    geometry_sha256: str
    operator_sha256: str
    metric_sha256: str
    descriptor_sha256: str

    @classmethod
    def create(cls, *, port_id: str, scale: int, component: int, port: Any, characteristic_basis: Sequence[complex], metric: Sequence[float], orientation: int = 1, interface_id: str | None = None, geometry_sha256: str = "", operator_sha256: str = "", metric_sha256: str = "") -> "QiBoundaryPermeabilityDescriptor":
        name = _text("port_id", port_id)
        if isinstance(port, QiPortDescriptor) or not hasattr(port, "observe") or not hasattr(port, "inject"):
            raise QiPermeabilityError("descriptor requires a fixed linear observe/inject port")
        scale_i, component_i = _integer("scale", scale), _integer("component", component)
        if orientation not in {-1, 1}:
            raise QiPermeabilityError("orientation must be -1 or +1")
        basis, weights = _complex_vector("characteristic_basis", characteristic_basis), _vector("metric", metric, positive=True)
        if len(basis) != len(weights) or len(basis) != int(port.source_dimension):
            raise QiPermeabilityError("basis, metric, and port source dimensions disagree")
        norm = sum(weight * (value.real * value.real + value.imag * value.imag) for weight, value in zip(weights, basis, strict=True))
        if not math.isfinite(norm) or not _close(norm, 1.0):
            raise QiPermeabilityError("characteristic basis must have metric norm one")
        interface = _text("interface_id", interface_id or f"sensory:{name}:scale:{scale_i}")
        def optional_digest(label: str, value: str) -> str:
            return "" if value == "" else _digest(label, value)
        geometry, operator, metric_id = optional_digest("geometry_sha256", geometry_sha256), optional_digest("operator_sha256", operator_sha256), optional_digest("metric_sha256", metric_sha256)
        body = {"schema": PERMEABILITY_DESCRIPTOR_SCHEMA, "port_id": name, "interface_id": interface, "scale": scale_i, "orientation": int(orientation), "component": component_i, "port_descriptor_sha256": str(getattr(port, "descriptor_sha256", "")), "characteristic_basis": [[value.real, value.imag] for value in basis], "metric": list(weights), "geometry_sha256": geometry, "operator_sha256": operator, "metric_sha256": metric_id}
        return cls(name, interface, scale_i, int(orientation), component_i, port, basis, weights, geometry, operator, metric_id, canonical_hash(body, PERMEABILITY_DESCRIPTOR_SCHEMA))

    @property
    def source_dimension(self) -> int:
        return len(self.characteristic_basis)

    @property
    def field_dimension(self) -> int:
        return int(self.port.field_dimension)

    def basis_tensor(self, *, device: torch.device | str = "cpu") -> torch.Tensor:
        return torch.tensor(self.characteristic_basis, dtype=torch.complex128, device=device)

    def metric_tensor(self, *, device: torch.device | str = "cpu") -> torch.Tensor:
        return torch.tensor(self.metric, dtype=torch.float64, device=device)

    def payload(self) -> dict[str, Any]:
        return {"schema": PERMEABILITY_DESCRIPTOR_SCHEMA, "port_id": self.port_id, "interface_id": self.interface_id, "scale": self.scale, "orientation": self.orientation, "component": self.component, "port_descriptor_sha256": str(getattr(self.port, "descriptor_sha256", "")), "characteristic_basis": [[value.real, value.imag] for value in self.characteristic_basis], "metric": list(self.metric), "geometry_sha256": self.geometry_sha256, "operator_sha256": self.operator_sha256, "metric_sha256": self.metric_sha256, "descriptor_sha256": self.descriptor_sha256}

    def scattering_port(self, profile_sha256: str) -> QiPortDescriptor:
        profile = _digest("profile_sha256", profile_sha256)
        return QiPortDescriptor(self.port_id, self.interface_id, "external", None, None, self.orientation, "temporal-full-rank", profile, self.operator_sha256 or canonical_hash(self.payload(), PERMEABILITY_OPERATOR_SCHEMA), self.metric_sha256 or canonical_hash({"metric": list(self.metric)}, "cassi.qi-flow-permeability-metric.v1"), profile)


@dataclass(frozen=True, slots=True)
class QiGateResult:
    value: float
    signal: float
    signal_norm: float
    interval: QiInterval
    state_sha256: str

    def payload(self) -> dict[str, Any]:
        return {"value": self.value, "signal": self.signal, "signal_norm": self.signal_norm, "interval": self.interval.payload(), "state_sha256": self.state_sha256}


@dataclass(frozen=True, slots=True)
class QiPowerFractions:
    gate: float
    transmitted: float
    reflected: float
    absorbed: float

    def __post_init__(self) -> None:
        for name in ("gate", "transmitted", "reflected", "absorbed"):
            _finite(name, getattr(self, name))
        values = (self.transmitted, self.reflected, self.absorbed)
        if any(value < 0.0 or value > 1.0 for value in values) or not _close(sum(values), 1.0, 2.0e-12):
            raise QiPermeabilityError("power fractions must be nonnegative, bounded, and close")

    def payload(self) -> dict[str, float]:
        return {"gate": self.gate, "transmitted": self.transmitted, "reflected": self.reflected, "absorbed": self.absorbed}


@dataclass(frozen=True, slots=True)
class QiPermeabilityScatter:
    incident_amplitude: complex
    reflected_amplitude: complex
    transmitted_amplitude: complex
    fractions: QiPowerFractions
    W_incident: QiInterval
    W_reflected: QiInterval
    W_transmitted: QiInterval
    W_absorbed: QiInterval
    closure_residual: QiInterval
    closure_bound: float
    gate_samples: tuple[QiGateResult, ...]
    phases: tuple[float, float]
    replay_identity_sha256: str

    @property
    def W_admitted(self) -> QiInterval:
        return self.W_transmitted

    def payload(self) -> dict[str, Any]:
        return {"incident_amplitude": [self.incident_amplitude.real, self.incident_amplitude.imag], "reflected_amplitude": [self.reflected_amplitude.real, self.reflected_amplitude.imag], "transmitted_amplitude": [self.transmitted_amplitude.real, self.transmitted_amplitude.imag], "fractions": self.fractions.payload(), "W_incident": self.W_incident.payload(), "W_reflected": self.W_reflected.payload(), "W_transmitted": self.W_transmitted.payload(), "W_absorbed": self.W_absorbed.payload(), "closure_residual": self.closure_residual.payload(), "closure_bound": self.closure_bound, "gate_samples": [sample.payload() for sample in self.gate_samples], "phases": list(self.phases), "replay_identity_sha256": self.replay_identity_sha256}


@dataclass(frozen=True, slots=True)
class QiBoundaryPermeabilityProfile:
    descriptor: QiBoundaryPermeabilityDescriptor
    kappa_min: float
    kappa_max: float
    bias: float
    slope: float
    s_ref: float
    eta_trans_min: float
    eta_trans_max: float
    eta_abs_min: float
    eta_abs_max: float
    phase_reflected: float
    phase_transmitted: float
    incident_weight: float
    admitted_work_min: float
    admitted_work_max: float
    reflected_work_min: float
    reflected_work_max: float
    absorbed_work_min: float
    absorbed_work_max: float
    source_work_max: float
    scatter_bound: float
    observable_norm_max: float
    quadrature_identity: str
    refinement_identity: str
    work_units: str
    openness_min: float
    recovery_min: float
    openness_reference: float
    recovery_horizon: float
    recovery_work_min: float
    profile_sha256: str

    @classmethod
    def create(cls, *, descriptor: QiBoundaryPermeabilityDescriptor, **kwargs: Any) -> "QiBoundaryPermeabilityProfile":
        if not isinstance(descriptor, QiBoundaryPermeabilityDescriptor):
            raise QiPermeabilityError("profile requires an immutable permeability descriptor")
        defaults = {"kappa_min": 0.0, "kappa_max": 1.0, "bias": 0.0, "slope": 1.0, "s_ref": 1.0, "eta_trans_min": 0.05, "eta_trans_max": 0.80, "eta_abs_min": 0.05, "eta_abs_max": 0.10, "phase_reflected": math.pi, "phase_transmitted": 0.0, "incident_weight": 1.0, "admitted_work_min": 0.0, "admitted_work_max": 1.0e12, "reflected_work_min": 0.0, "reflected_work_max": 1.0e12, "absorbed_work_min": 0.0, "absorbed_work_max": 1.0e12, "source_work_max": 1.0e12, "scatter_bound": 1.0e-12, "observable_norm_max": 1.0e12, "quadrature_identity": "direct-positive-duration-v1", "refinement_identity": "exact-scalar-gate-v1", "work_units": "joule-equivalent", "openness_min": 1.0e-9, "recovery_min": 1.0e-9, "openness_reference": 1.0, "recovery_horizon": 1.0, "recovery_work_min": 0.0}
        unknown = set(kwargs) - set(defaults)
        if unknown:
            raise QiPermeabilityError(f"unknown profile fields: {sorted(unknown)!r}")
        defaults.update(kwargs)
        positive_fields = {"s_ref", "incident_weight", "observable_norm_max", "openness_min", "recovery_min", "openness_reference", "recovery_horizon"}
        nonnegative_fields = {"kappa_min", "kappa_max", "eta_trans_min", "eta_trans_max", "eta_abs_min", "eta_abs_max", "admitted_work_min", "admitted_work_max", "reflected_work_min", "reflected_work_max", "absorbed_work_min", "absorbed_work_max", "source_work_max", "scatter_bound", "recovery_work_min"}
        values = {name: (_positive(name, value) if name in positive_fields else _nonnegative(name, value) if name in nonnegative_fields else _finite(name, value)) for name, value in defaults.items() if name not in {"quadrature_identity", "refinement_identity", "work_units"}}
        for name in ("quadrature_identity", "refinement_identity", "work_units"):
            values[name] = _text(name, defaults[name])
        if values["kappa_min"] > values["kappa_max"] or values["kappa_max"] > 1.0 or values["slope"] == 0.0:
            raise QiPermeabilityError("gate bounds/slope are invalid")
        if any(values[lo] > values[hi] or values[hi] > 1.0 for lo, hi in (("eta_trans_min", "eta_trans_max"), ("eta_abs_min", "eta_abs_max"))):
            raise QiPermeabilityError("power fraction bounds are invalid")
        if values["eta_trans_max"] + values["eta_abs_max"] > 1.0:
            raise QiPermeabilityError("maximum transmitted and absorbed fractions exceed one")
        if any(values[lo] > values[hi] for lo, hi in (("admitted_work_min", "admitted_work_max"), ("reflected_work_min", "reflected_work_max"), ("absorbed_work_min", "absorbed_work_max"))):
            raise QiPermeabilityError("work bounds are reversed")
        if values["admitted_work_max"] > values["source_work_max"]:
            raise QiPermeabilityError("admitted work maximum exceeds source budget")
        body = {"schema": PERMEABILITY_PROFILE_SCHEMA, "descriptor": descriptor.payload(), **values, "operator_schema": PERMEABILITY_OPERATOR_SCHEMA, "state_observable": "metric-normalized-current-field-v1", "fraction_mapping": "linear-gate-v1", "scattering": "fixed-phase-complex-amplitude-v1"}
        digest = canonical_hash(body, PERMEABILITY_PROFILE_SCHEMA)
        ordered_names = ("kappa_min", "kappa_max", "bias", "slope", "s_ref", "eta_trans_min", "eta_trans_max", "eta_abs_min", "eta_abs_max", "phase_reflected", "phase_transmitted", "incident_weight", "admitted_work_min", "admitted_work_max", "reflected_work_min", "reflected_work_max", "absorbed_work_min", "absorbed_work_max", "source_work_max", "scatter_bound", "observable_norm_max", "quadrature_identity", "refinement_identity", "work_units", "openness_min", "recovery_min", "openness_reference", "recovery_horizon", "recovery_work_min")
        return cls(descriptor, *(values[name] for name in ordered_names), digest)

    @classmethod
    def from_descriptor(cls, descriptor: QiBoundaryPermeabilityDescriptor, **kwargs: Any) -> "QiBoundaryPermeabilityProfile":
        return cls.create(descriptor=descriptor, **kwargs)

    @property
    def port_id(self) -> str:
        return self.descriptor.port_id

    @property
    def scale(self) -> int:
        return self.descriptor.scale

    @property
    def orientation(self) -> int:
        return self.descriptor.orientation

    @property
    def operator_sha256(self) -> str:
        return self.descriptor.operator_sha256 or canonical_hash(self.descriptor.payload(), PERMEABILITY_OPERATOR_SCHEMA)

    @property
    def geometry_sha256(self) -> str:
        return self.descriptor.geometry_sha256

    @property
    def metric_sha256(self) -> str:
        return self.descriptor.metric_sha256

    @property
    def reflected_fraction_bounds(self) -> tuple[float, float]:
        return max(0.0, 1.0 - self.eta_trans_max - self.eta_abs_max), min(1.0, 1.0 - self.eta_trans_min - self.eta_abs_min)

    def payload(self) -> dict[str, Any]:
        return {"schema": PERMEABILITY_PROFILE_SCHEMA, "descriptor": self.descriptor.payload(), "kappa_bounds": [self.kappa_min, self.kappa_max], "gate": {"bias": self.bias, "slope": self.slope, "s_ref": self.s_ref, "observable": "metric-normalized-current-field-v1"}, "power_fraction_bounds": {"transmitted": [self.eta_trans_min, self.eta_trans_max], "absorbed": [self.eta_abs_min, self.eta_abs_max], "reflected": list(self.reflected_fraction_bounds)}, "phases": {"reflected": self.phase_reflected, "transmitted": self.phase_transmitted}, "incident_weight": self.incident_weight, "work_bounds": {"admitted": [self.admitted_work_min, self.admitted_work_max], "reflected": [self.reflected_work_min, self.reflected_work_max], "absorbed": [self.absorbed_work_min, self.absorbed_work_max], "source_work_max": self.source_work_max, "scatter_bound": self.scatter_bound}, "observable_norm_max": self.observable_norm_max, "quadrature_identity": self.quadrature_identity, "refinement_identity": self.refinement_identity, "work_units": self.work_units, "fixture_thresholds": {"openness_min": self.openness_min, "recovery_min": self.recovery_min, "openness_reference": self.openness_reference, "recovery_horizon": self.recovery_horizon, "recovery_work_min": self.recovery_work_min}, "operator_schema": PERMEABILITY_OPERATOR_SCHEMA, "fraction_mapping": "linear-gate-v1", "scattering": "fixed-phase-complex-amplitude-v1", "profile_sha256": self.profile_sha256}

    def _component(self, state: Any, lane: int) -> torch.Tensor:
        field = _state_field(state)
        lane_i = _integer("lane", lane)
        if field.ndim == 1:
            if lane_i != 0 or field.shape[0] != self.descriptor.field_dimension:
                raise QiPermeabilityError("field vector shape disagrees with port")
            return field
        if field.ndim != 3 or self.scale >= field.shape[0] or lane_i >= field.shape[2]:
            raise QiPermeabilityError("QiFlowStateV3 field must contain the declared scale/lane")
        mode_count = field.shape[1] // 9
        if field.shape[1] % 9 or mode_count != self.descriptor.field_dimension or self.descriptor.component >= 9:
            raise QiPermeabilityError("field layout does not match descriptor component")
        return field[self.scale, self.descriptor.component * mode_count : (self.descriptor.component + 1) * mode_count, lane_i]

    def derive_gate(self, state: Any, *, lane: int = 0, profile: Any | None = None) -> QiGateResult:
        observed = self.descriptor.port.observe(self._component(state, lane))
        metric, basis = self.descriptor.metric_tensor(device=observed.device), self.descriptor.basis_tensor(device=observed.device)
        norm = float(torch.sqrt(torch.sum(metric * torch.abs(observed).square())).detach().cpu().item())
        if not math.isfinite(norm) or norm > self.observable_norm_max:
            raise QiPermeabilityError("current field is outside the certified observable domain")
        signal = float((torch.sum(torch.conj(basis) * metric * observed).real / (self.s_ref + norm)).detach().cpu().item())
        if not math.isfinite(signal) or signal < -1.0 - 2.0e-10 or signal > 1.0 + 2.0e-10:
            raise QiPermeabilityError("current field observable left [-1,1]")
        if signal < -1.0:
            signal = -1.0
        elif signal > 1.0:
            signal = 1.0
        value = self.kappa_min + (self.kappa_max - self.kappa_min) * (1.0 + math.tanh(self.bias + self.slope * signal)) / 2.0
        if not math.isfinite(value) or not self.kappa_min <= value <= self.kappa_max:
            raise QiPermeabilityError("gate interval is not enclosed by the declared bounds")
        return QiGateResult(value, signal, norm, QiInterval.exact(value), _state_hash(state, profile))

    def power_fractions(self, gate: float | QiGateResult) -> QiPowerFractions:
        value = gate.value if isinstance(gate, QiGateResult) else _finite("gate", gate)
        if not self.kappa_min <= value <= self.kappa_max:
            raise QiPermeabilityError("gate lies outside profile bounds")
        transmitted = self.eta_trans_min + (self.eta_trans_max - self.eta_trans_min) * value
        absorbed = self.eta_abs_min + (self.eta_abs_max - self.eta_abs_min) * value
        reflected = 1.0 - transmitted - absorbed
        if min(transmitted, reflected, absorbed) < -2.0e-12 or max(transmitted, reflected, absorbed) > 1.0 + 2.0e-12:
            raise QiPermeabilityError("derived fractions leave [0,1]")
        return QiPowerFractions(value, transmitted, reflected, absorbed)

    def scatter(self, incident_amplitude: complex, *, duration: float, state: Any, state_samples: Sequence[Any] | None = None, state_gate_mode: str = "live", lane: int = 0, profile: Any | None = None) -> QiPermeabilityScatter:
        try:
            amplitude = complex(incident_amplitude)
        except (TypeError, ValueError) as exc:
            raise QiPermeabilityError("incident amplitude must be complex") from exc
        if not math.isfinite(amplitude.real) or not math.isfinite(amplitude.imag):
            raise QiPermeabilityError("incident amplitude must be finite")
        span = _positive("duration", duration)
        if state_gate_mode not in {"live", "frozen"}:
            raise QiPermeabilityError("state_gate_mode must be live or frozen")
        samples = tuple(state_samples) if state_samples is not None else (state,)
        if not samples:
            raise QiPermeabilityError("state_samples cannot be empty")
        if state_gate_mode == "frozen":
            samples = (samples[0],) * len(samples)
        gates = tuple(self.derive_gate(item, lane=lane, profile=profile) for item in samples)
        fractions = tuple(self.power_fractions(gate) for gate in gates)
        each = span / len(gates)
        incident_power = self.incident_weight * (amplitude.real * amplitude.real + amplitude.imag * amplitude.imag) / 2.0
        W_inc, W_trans = incident_power * span, sum(incident_power * value.transmitted * each for value in fractions)
        W_ref, W_abs = sum(incident_power * value.reflected * each for value in fractions), sum(incident_power * value.absorbed * each for value in fractions)
        residual_value = W_inc - W_trans - W_ref - W_abs
        if abs(residual_value) > self.scatter_bound:
            raise QiPermeabilityError("scattering work closure exceeds fixed enclosure")
        representative = fractions[-1]
        ref_phase, trans_phase = self.orientation * self.phase_reflected, self.orientation * self.phase_transmitted
        reflected, transmitted = amplitude * math.sqrt(representative.reflected) * complex(math.cos(ref_phase), math.sin(ref_phase)), amplitude * math.sqrt(representative.transmitted) * complex(math.cos(trans_phase), math.sin(trans_phase))
        incident, reflected_work, transmitted_work, absorbed_work = QiInterval.exact(W_inc), QiInterval.exact(W_ref), QiInterval.exact(W_trans), QiInterval.exact(W_abs)
        residual = QiInterval.exact(residual_value)
        replay = canonical_hash({"schema": PERMEABILITY_ADMISSION_SCHEMA, "descriptor_sha256": self.descriptor.descriptor_sha256, "profile_sha256": self.profile_sha256, "incident_amplitude": [amplitude.real, amplitude.imag], "duration": span, "state_gate_mode": state_gate_mode, "gates": [gate.payload() for gate in gates], "work": {"incident": incident.payload(), "reflected": reflected_work.payload(), "transmitted": transmitted_work.payload(), "absorbed": absorbed_work.payload(), "residual": residual.payload()}}, PERMEABILITY_ADMISSION_SCHEMA)
        return QiPermeabilityScatter(amplitude, reflected, transmitted, representative, incident, reflected_work, transmitted_work, absorbed_work, residual, self.scatter_bound, gates, (ref_phase, trans_phase), replay)

    def _check_work(self, scatter: QiPermeabilityScatter) -> None:
        if scatter.W_incident.lower <= 0.0:
            raise QiPermeabilityError("ZERO_INCIDENT_WORK")
        if scatter.W_incident.upper > self.source_work_max:
            raise QiPermeabilityError("incident work exceeds source budget")
        for name, value, lower, upper in (("admitted", scatter.W_admitted, self.admitted_work_min, self.admitted_work_max), ("reflected", scatter.W_reflected, self.reflected_work_min, self.reflected_work_max), ("absorbed", scatter.W_absorbed, self.absorbed_work_min, self.absorbed_work_max)):
            if value.lower < lower or value.upper > upper:
                raise QiPermeabilityError(f"{name} work lies outside declared bounds")

    def _successor(self, predecessor: Any, candidate: torch.Tensor, profile: Any | None) -> Any:
        if type(predecessor).__name__ == "QiFlowStateV3" and hasattr(type(predecessor), "from_field"):
            if profile is None:
                raise QiPermeabilityError("QiFlowStateV3 admission requires its explicit profile")
            try:
                return type(predecessor).from_field(profile, candidate)
            except Exception as exc:
                raise QiPermeabilityError(f"successor state failed validation: {exc}") from exc
        return candidate

    def admit_scratch(self, predecessor: Any, *, incident_amplitude: complex, duration: float, scratch_successor: Any | None = None, state_samples: Sequence[Any] | None = None, state_gate_mode: str = "live", lane: int = 0, source_cursor: Any = None, profile: Any | None = None, step: int = 0, head_sha256: str | None = None, incoming_trajectory_sha256: str | None = None, stage_id: str = "sensory-ingress", tick_interval: float | None = None) -> "QiPermeabilityAdmission":
        before = _state_hash(predecessor, profile)
        try:
            _state_field(predecessor)
            candidate_input = predecessor if scratch_successor is None else scratch_successor
            _state_field(candidate_input)
            scatter = self.scatter(incident_amplitude, duration=duration, state=candidate_input, state_samples=state_samples, state_gate_mode=state_gate_mode, lane=lane, profile=profile)
            self._check_work(scatter)
            if scatter.W_admitted.lower <= 0.0:
                raise QiPermeabilityError("ZERO_ADMITTED_WORK")
            candidate = _state_field(candidate_input).detach().clone()
            injected = self.descriptor.port.inject(self.descriptor.basis_tensor(device=candidate.device) * scatter.transmitted_amplitude)
            if candidate.ndim == 1:
                if candidate.shape != injected.shape:
                    raise QiPermeabilityError("candidate vector shape disagrees with injected source")
                candidate = candidate + injected * duration
            else:
                mode_count = candidate.shape[1] // 9
                if candidate.shape[1] % 9 or mode_count != injected.shape[0] or self.scale >= candidate.shape[0] or lane >= candidate.shape[2]:
                    raise QiPermeabilityError("candidate layout disagrees with descriptor")
                start = self.descriptor.component * mode_count
                candidate[self.scale, start : start + mode_count, lane] += injected * duration
            successor = self._successor(predecessor, candidate, profile)
            after = _state_hash(successor, profile)
            port = self.descriptor.scattering_port(self.profile_sha256)
            receipt = build_qi_scattering_receipt(
                port=port,
                step=_integer("step", step),
                head_sha256=_digest("head_sha256", head_sha256 or canonical_hash({"before": before, "step": step}, "cassi.qi-flow-permeability-head.v1")),
                incoming_trajectory_sha256=_digest("incoming_trajectory_sha256", incoming_trajectory_sha256 or scatter.replay_identity_sha256),
                stage_id=_text("stage_id", stage_id),
                tick_interval=QiInterval.exact(tick_interval if tick_interval is not None else duration),
                profile_sha256=self.profile_sha256,
                operator_sha256=self.operator_sha256,
                metric_sha256=self.metric_sha256 or port.metric_sha256,
                active_rank=self.descriptor.source_dimension,
                nullspace_sha256=canonical_hash({"dimension": self.descriptor.field_dimension, "active": self.descriptor.source_dimension}, "cassi.qi-flow-permeability-nullspace.v1"),
                pre_state_sha256=before,
                post_state_sha256=after,
                work_rows={"W_incident": scatter.W_incident, "W_reflected": scatter.W_reflected, "W_transmitted": scatter.W_transmitted, "W_absorbed": scatter.W_absorbed},
                closure_bound=self.scatter_bound,
                permeability_profile_sha256=self.profile_sha256,
                replay_identity_sha256=scatter.replay_identity_sha256,
            )
            identity = canonical_hash({"accepted": True, "before": before, "after": after, "receipt": receipt.self_sha256}, PERMEABILITY_ADMISSION_SCHEMA)
            return QiPermeabilityAdmission(True, before, after, source_cursor, source_cursor, successor, scatter, receipt, None, identity)
        except (QiPermeabilityError, ValueError, TypeError) as exc:
            identity = canonical_hash({"accepted": False, "state": before, "reason": str(exc)}, PERMEABILITY_ADMISSION_SCHEMA)
            return QiPermeabilityAdmission(False, before, before, source_cursor, source_cursor, predecessor, None, None, str(exc), identity)


@dataclass(frozen=True, slots=True)
class QiPermeabilityAdmission:
    accepted: bool
    predecessor_state_sha256: str
    successor_state_sha256: str
    source_cursor_before: Any
    source_cursor_after: Any
    state: Any
    scattering: QiPermeabilityScatter | None
    scattering_receipt: QiScatteringReceipt | None
    failure_reason: str | None
    self_sha256: str

    @property
    def successor(self) -> Any:
        return self.state

    def payload(self) -> dict[str, Any]:
        return {"schema": PERMEABILITY_ADMISSION_SCHEMA, "accepted": self.accepted, "predecessor_state_sha256": self.predecessor_state_sha256, "successor_state_sha256": self.successor_state_sha256, "source_cursor_before": self.source_cursor_before, "source_cursor_after": self.source_cursor_after, "scattering_receipt_sha256": self.scattering_receipt.self_sha256 if self.scattering_receipt else None, "failure_reason": self.failure_reason, "self_sha256": self.self_sha256}


@dataclass(frozen=True, slots=True)
class QiSensoryOpennessReceipt:
    port_id: str
    scale: int
    profile_sha256: str
    descriptor_sha256: str
    pre_state_sha256: str
    post_state_sha256: str
    incident_pre: QiInterval
    admitted_pre: QiInterval
    reflected_pre: QiInterval
    absorbed_pre: QiInterval
    incident_post: QiInterval
    admitted_post: QiInterval
    reflected_post: QiInterval
    absorbed_post: QiInterval
    openness_pre: QiInterval
    openness_post: QiInterval
    openness_reference: float
    recovery: QiInterval
    recovery_horizon: float
    recovery_work: QiInterval
    downstream_return_sha256: tuple[str, ...]
    fixture_thresholds: Mapping[str, float]
    controls: tuple[str, ...]
    self_sha256: str

    @classmethod
    def create(cls, *, profile: QiBoundaryPermeabilityProfile, pre_state: Any, post_state: Any, pre_scatter: QiPermeabilityScatter, post_scatter: QiPermeabilityScatter, source_free_horizon: float, recovery_work: QiInterval | float, downstream_return_sha256: Sequence[str] = (), controls: Sequence[str] = (), state_profile: Any | None = None) -> "QiSensoryOpennessReceipt":
        horizon = _positive("source_free_horizon", source_free_horizon)
        if horizon < profile.recovery_horizon:
            raise QiPermeabilityError("source-free horizon is shorter than profile recovery horizon")
        recovery_interval = _interval(recovery_work, "recovery_work")
        if recovery_interval.lower < profile.recovery_work_min:
            raise QiPermeabilityError("recovery work is below its declared bound")
        pre_o, post_o = _ratio(pre_scatter.W_admitted, pre_scatter.W_incident, "pre openness"), _ratio(post_scatter.W_admitted, post_scatter.W_incident, "post openness")
        recovery = _ratio(post_o, QiInterval.exact(max(profile.openness_reference, pre_o.upper)), "recovery")
        if post_o.lower < profile.openness_min or recovery.lower < profile.recovery_min:
            raise QiPermeabilityError("openness/recovery is below fixed thresholds")
        control_names = tuple(_text("control", value) for value in controls)
        if not set(REQUIRED_OPENNESS_CONTROLS).issubset(control_names):
            raise QiPermeabilityError("openness receipt is missing a required control")
        downstream = tuple(_digest("downstream_return_sha256", value) for value in downstream_return_sha256)
        pre_hash, post_hash = _state_hash(pre_state, state_profile), _state_hash(post_state, state_profile)
        thresholds = {"openness_min": profile.openness_min, "recovery_min": profile.recovery_min, "openness_reference": profile.openness_reference, "recovery_horizon": profile.recovery_horizon, "recovery_work_min": profile.recovery_work_min}
        body = {"schema": SENSORY_OPENNESS_SCHEMA, "port_id": profile.port_id, "scale": profile.scale, "profile_sha256": profile.profile_sha256, "descriptor_sha256": profile.descriptor.descriptor_sha256, "pre_state_sha256": pre_hash, "post_state_sha256": post_hash, "incident_pre": pre_scatter.W_incident.payload(), "admitted_pre": pre_scatter.W_admitted.payload(), "reflected_pre": pre_scatter.W_reflected.payload(), "absorbed_pre": pre_scatter.W_absorbed.payload(), "incident_post": post_scatter.W_incident.payload(), "admitted_post": post_scatter.W_admitted.payload(), "reflected_post": post_scatter.W_reflected.payload(), "absorbed_post": post_scatter.W_absorbed.payload(), "openness_pre": pre_o.payload(), "openness_post": post_o.payload(), "openness_reference": profile.openness_reference, "recovery": recovery.payload(), "recovery_horizon": horizon, "recovery_work": recovery_interval.payload(), "downstream_return_sha256": list(downstream), "fixture_thresholds": thresholds, "controls": list(control_names)}
        return cls(profile.port_id, profile.scale, profile.profile_sha256, profile.descriptor.descriptor_sha256, pre_hash, post_hash, pre_scatter.W_incident, pre_scatter.W_admitted, pre_scatter.W_reflected, pre_scatter.W_absorbed, post_scatter.W_incident, post_scatter.W_admitted, post_scatter.W_reflected, post_scatter.W_absorbed, pre_o, post_o, profile.openness_reference, recovery, horizon, recovery_interval, downstream, MappingProxyType(thresholds), control_names, canonical_hash(body, SENSORY_OPENNESS_SCHEMA))

    def payload(self) -> dict[str, Any]:
        return {"schema": SENSORY_OPENNESS_SCHEMA, "port_id": self.port_id, "scale": self.scale, "profile_sha256": self.profile_sha256, "descriptor_sha256": self.descriptor_sha256, "pre_state_sha256": self.pre_state_sha256, "post_state_sha256": self.post_state_sha256, "incident_pre": self.incident_pre.payload(), "admitted_pre": self.admitted_pre.payload(), "reflected_pre": self.reflected_pre.payload(), "absorbed_pre": self.absorbed_pre.payload(), "incident_post": self.incident_post.payload(), "admitted_post": self.admitted_post.payload(), "reflected_post": self.reflected_post.payload(), "absorbed_post": self.absorbed_post.payload(), "openness_pre": self.openness_pre.payload(), "openness_post": self.openness_post.payload(), "openness_reference": self.openness_reference, "recovery": self.recovery.payload(), "recovery_horizon": self.recovery_horizon, "recovery_work": self.recovery_work.payload(), "downstream_return_sha256": list(self.downstream_return_sha256), "fixture_thresholds": dict(self.fixture_thresholds), "controls": list(self.controls), "self_sha256": self.self_sha256}


def build_sensory_openness_receipt(**kwargs: Any) -> QiSensoryOpennessReceipt:
    return QiSensoryOpennessReceipt.create(**kwargs)


def validate_sensory_openness_receipt(receipt: QiSensoryOpennessReceipt) -> None:
    if not isinstance(receipt, QiSensoryOpennessReceipt):
        raise QiPermeabilityError("invalid sensory openness receipt type")
    body = receipt.payload()
    supplied = body.pop("self_sha256")
    if supplied != canonical_hash(body, SENSORY_OPENNESS_SCHEMA):
        raise QiPermeabilityError("sensory openness receipt self hash mismatch")
    if receipt.incident_pre.lower <= 0.0 or receipt.incident_post.lower <= 0.0:
        raise QiPermeabilityError("openness receipt incident work is non-positive")


def validate_permeability_profile(profile: QiBoundaryPermeabilityProfile) -> None:
    if not isinstance(profile, QiBoundaryPermeabilityProfile):
        raise QiPermeabilityError("invalid permeability profile type")
    names = ("kappa_min", "kappa_max", "bias", "slope", "s_ref", "eta_trans_min", "eta_trans_max", "eta_abs_min", "eta_abs_max", "phase_reflected", "phase_transmitted", "incident_weight", "admitted_work_min", "admitted_work_max", "reflected_work_min", "reflected_work_max", "absorbed_work_min", "absorbed_work_max", "source_work_max", "scatter_bound", "observable_norm_max", "quadrature_identity", "refinement_identity", "work_units", "openness_min", "recovery_min", "openness_reference", "recovery_horizon", "recovery_work_min")
    body = {"schema": PERMEABILITY_PROFILE_SCHEMA, "descriptor": profile.descriptor.payload(), **{name: getattr(profile, name) for name in names}, "operator_schema": PERMEABILITY_OPERATOR_SCHEMA, "state_observable": "metric-normalized-current-field-v1", "fraction_mapping": "linear-gate-v1", "scattering": "fixed-phase-complex-amplitude-v1"}
    if profile.profile_sha256 != canonical_hash(body, PERMEABILITY_PROFILE_SCHEMA):
        raise QiPermeabilityError("permeability profile self hash mismatch")


QiWorkInterval = QiInterval

__all__ = ["PERMEABILITY_PROFILE_SCHEMA", "PERMEABILITY_DESCRIPTOR_SCHEMA", "PERMEABILITY_ADMISSION_SCHEMA", "PERMEABILITY_OPERATOR_SCHEMA", "SENSORY_OPENNESS_SCHEMA", "REQUIRED_OPENNESS_CONTROLS", "QiPermeabilityError", "PermeabilityError", "QiBoundaryPermeabilityDescriptor", "QiGateResult", "QiPowerFractions", "QiPermeabilityScatter", "QiBoundaryPermeabilityProfile", "QiPermeabilityAdmission", "QiSensoryOpennessReceipt", "QiWorkInterval", "build_sensory_openness_receipt", "validate_sensory_openness_receipt", "validate_permeability_profile"]
