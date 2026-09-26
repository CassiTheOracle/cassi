"""Integrated W5 frozen-Q conversion on the single v3 field.

The module owns only the conversion law.  W4 supplies the one seven-stage
carrier split; W5 installs one center map into that split and performs one
coordinate-duration EMA after the accepted field step.  Coordinate duration
is ground truth; tau_F and chi_F are derived candidate process ages, and
endpoint inversion is reported separately from their direct frozen-Q values.
No artifact lookup or persistent conversion state is performed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import inspect
import math
import struct
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import torch

from cassi_qi_bootstrap import finite_float
from cassi_qi_carrier import (
    CarrierCoordinates,
    carrier_coordinates,
    carrier_total_energy,
    _replace_coordinates,
    _transition_v4_carrier_split,
)
from cassi_qi_field import QiFlowGeometryV2, QiFlowStateV3
from cassi_qi_profile import canonical_hash
from cassi_qi_topology import (
    QiTopologyProfile,
    QiTopologicalRetentionLaw,
    topology_diagnostics,
)


W5_CONVERSION_PROFILE_SCHEMA = "cassi.qi-flow-conversion-profile.v1"
W5_CONVERSION_ROOT_SCHEMA = "cassi.qi-flow-w5-conversion-root.v1"
W5_CONVERSION_RECEIPT_SCHEMA = "cassi.qi-flow-w5-conversion-receipt.v1"
W5_INTEGRATED_RECEIPT_SCHEMA = "cassi.qi-flow-w5-integrated-receipt.v1"
W5_LAW_DOMAIN = "cassi.qi-flow-frozen-q-map.v1"
W5_PROFILE_DOMAIN = W5_CONVERSION_PROFILE_SCHEMA
W5_ROOT_DOMAIN = W5_CONVERSION_ROOT_SCHEMA
W5_CONVERSION_RECEIPT_DOMAIN = W5_CONVERSION_RECEIPT_SCHEMA
W5_INTEGRATED_RECEIPT_DOMAIN = W5_INTEGRATED_RECEIPT_SCHEMA
W5_RAW_DOMAIN = "cassi.qi-flow-w5-raw-state.v1"


class ConversionError(ValueError):
    """Raised when a W5 profile, map, or guarded commit is inadmissible."""



class _WorkRejected(ConversionError):
    """Internal signal preserving a rejected conversion-work witness."""

@dataclass(frozen=True)
class QiConversionProfile:
    payload: Mapping[str, Any]
    root: Mapping[str, Any]
    profile_sha256: str
    root_sha256: str
    law_sha256: str
    phi: float
    lambda_rate: float
    rho_ref: float
    h_min: float
    h_max: float
    runtime_durations: tuple[float, ...]
    epsilon_memory_time: float
    epsilon_prog_min: float
    rho_max: float
    epsilon2_ema_max: float
    component_abs_max: float
    density_tolerance: float
    work_tolerance: float
    energy_uncertainty: float

    @property
    def schema(self) -> str:
        return W5_CONVERSION_PROFILE_SCHEMA

    @property
    def law_id(self) -> str:
        return W5_LAW_DOMAIN

    @property
    def parent_identities(self) -> Mapping[str, Any]:
        value = self.payload.get("parent_identities", self.payload.get("parents", {}))
        return value if isinstance(value, Mapping) else MappingProxyType({})


@dataclass(frozen=True)
class QiConversionStep:
    """Pure-map result used by private replay/proof helpers, never committed."""

    predecessor: QiFlowStateV3
    candidate: QiFlowStateV3 | None
    committable: bool
    receipt: Mapping[str, Any]
    failure_reason: str | None = None


@dataclass(frozen=True)
class QiIntegratedConversionStep:
    predecessor: QiFlowStateV3
    candidate: QiFlowStateV3 | None
    committable: bool
    receipt: Mapping[str, Any]
    failure_reason: str | None = None
    intermediates: Mapping[str, QiFlowStateV3] = MappingProxyType({})


# ---------------------------------------------------------------------------
# Small identity/encoding helpers.  They consume supplied immutable profiles;
# none of these helpers reads a file or knows a parent artifact identity.


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _sha256(value: Any, domain: str) -> str:
    return str(canonical_hash(_plain(value), domain))


def _state_hash(state: QiFlowStateV3) -> str:
    if not isinstance(state, QiFlowStateV3):
        raise ConversionError("state must be QiFlowStateV3")
    raw = state.field.detach().contiguous().cpu().numpy().tobytes(order="C")
    digest = hashlib.sha256()
    encoded = W5_RAW_DOMAIN.encode("utf-8")
    digest.update(len(encoded).to_bytes(8, "big"))
    digest.update(encoded)
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)
    return digest.hexdigest()


def _raw_state_descriptor(state: QiFlowStateV3, *, geometry: Any, role: str) -> Mapping[str, Any]:
    if not isinstance(state, QiFlowStateV3):
        raise ConversionError("center-map witness state must be QiFlowStateV3")
    geometry = _geometry_profile(geometry)
    layout = getattr(geometry.base_profile, "state_layout", None)
    if not isinstance(layout, Mapping):
        raise ConversionError("center-map witness requires the immutable state layout")
    raw = state.field.detach().contiguous().cpu().numpy().astype("<f8", copy=False).tobytes(order="C")
    return MappingProxyType({
        "role": role,
        "raw_domain": W5_RAW_DOMAIN,
        "domain": W5_RAW_DOMAIN,
        "dtype": "<f8",
        "byte_order": "little",
        "shape": [int(value) for value in state.field.shape],
        "layout_id": str(layout["layout_id"]),
        "state_layout": {
            "scale_count": int(layout["scale_count"]),
            "mode_count": int(layout["mode_count"]),
            "component_count": int(layout["component_count"]),
            "shape": [int(value) for value in state.field.shape],
        },
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "raw_sha256": _state_hash(state),
    })


_INTERMEDIATE_KEYS = (
    "predecessor",
    "post_first_kick",
    "post_first_spectral_pre_center",
    "post_center_conversion",
    "post_second_spectral",
    "post_second_kick_pre_ema",
    "candidate_post_ema",
)

_CARRIER_INTERMEDIATE_KEYS = {
    "predecessor": "predecessor",
    "post_first_kick": "post-first-kick",
    "post_first_spectral_pre_center": "post-first-spectral/pre-center",
    "post_center_conversion": "post-center",
    "post_second_spectral": "post-second-spectral",
    "post_second_kick_pre_ema": "post-second-kick/pre-EMA",
}


def _detached_state(state: QiFlowStateV3) -> QiFlowStateV3:
    return QiFlowStateV3(state.field.detach().contiguous().clone())


def _detached_intermediates(carrier_step: Any, predecessor: QiFlowStateV3, candidate: QiFlowStateV3) -> Mapping[str, QiFlowStateV3]:
    del predecessor
    raw = getattr(carrier_step, "intermediates", None)
    if not isinstance(raw, Mapping):
        raise ConversionError("carrier split did not expose detached stage intermediates")
    missing = [key for key, raw_key in _CARRIER_INTERMEDIATE_KEYS.items() if raw_key not in raw]
    if missing:
        raise ConversionError(f"carrier split intermediates missing: {','.join(missing)}")
    values: dict[str, QiFlowStateV3] = {}
    for key, raw_key in _CARRIER_INTERMEDIATE_KEYS.items():
        value = raw[raw_key]
        if not isinstance(value, QiFlowStateV3):
            raise ConversionError(f"carrier intermediate {key} is not QiFlowStateV3")
        values[key] = _detached_state(value)
    values["candidate_post_ema"] = _detached_state(candidate)
    return MappingProxyType(values)


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _f64(value: Any, *, name: str, positive: bool = False, nonnegative: bool = False) -> float:
    try:
        result = float(finite_float(value, name=name))
    except Exception as exc:
        raise ConversionError(f"{name} must be a finite scalar") from exc
    if not math.isfinite(result) or (result == 0.0 and math.copysign(1.0, result) < 0.0):
        raise ConversionError(f"{name} must be finite f64 and not negative zero")
    if positive and result <= 0.0:
        raise ConversionError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise ConversionError(f"{name} must be non-negative")
    return result


def _f64_tag(value: float) -> str:
    result = _f64(value, name="f64")
    return "f64:" + struct.pack(">d", result).hex()


def _decode_scalar(value: Any, *, name: str) -> float:
    if isinstance(value, str) and value.startswith("f64:"):
        try:
            if len(value) != 20:
                raise ValueError("invalid f64 tag")
            result = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
        except Exception as exc:
            raise ConversionError(f"{name} has an invalid f64 tag") from exc
        return _f64(result, name=name)
    if isinstance(value, Mapping) and "numerator" in value and "denominator" in value:
        try:
            result = float(Fraction(int(value["numerator"]), int(value["denominator"])))
        except Exception as exc:
            raise ConversionError(f"{name} has an invalid rational") from exc
        return _f64(result, name=name)
    return _f64(value, name=name)


def _geometry_profile(value: Any) -> Any:
    if hasattr(value, "base_profile") and hasattr(value, "active_shapes"):
        return value
    nested = getattr(value, "geometry_profile", None)
    if nested is not None and hasattr(nested, "base_profile"):
        return nested
    raise ConversionError("W5 requires a validated W2 geometry profile")


def _base_payload(geometry: Any) -> Mapping[str, Any]:
    profile = _geometry_profile(geometry).base_profile
    payload = getattr(profile, "payload", None)
    if not isinstance(payload, Mapping):
        raise ConversionError("W2 geometry has no immutable base profile payload")
    return payload


def _source_identity(value: Any, *names: str) -> str | None:
    for name in names or ("profile_sha256", "root_sha256", "contract_root_sha256", "self_sha256"):
        candidate = getattr(value, name, None)
        if _is_sha256(candidate):
            return str(candidate)
    payload = getattr(value, "payload", None)
    if isinstance(payload, Mapping):
        for name in names or ("profile_sha256", "root_sha256", "contract_root_sha256", "self_sha256"):
            candidate = payload.get(name)
            if _is_sha256(candidate):
                return str(candidate)
    if isinstance(value, Mapping):
        for name in names or ("profile_sha256", "root_sha256", "contract_root_sha256", "self_sha256"):
            candidate = value.get(name)
            if _is_sha256(candidate):
                return str(candidate)
    return None


def _parent_identities(
    geometry: Any,
    *,
    transport_profile: Any | None,
    carrier_profile: Any | None,
    topology_profile: Any | None,
    supplied: Mapping[str, Any] | None,
) -> dict[str, Any]:
    geometry = _geometry_profile(geometry)
    values: dict[str, Any] = {
        "w2_profile_sha256": _source_identity(geometry),
        "w2_contract_root_sha256": _source_identity(getattr(geometry, "contract_root", None)),
        "w2_geometry_contract_sha256": _source_identity(geometry, "geometry_contract_sha256"),
        "w2_operator_semantic_sha256": _source_identity(geometry, "operator_semantic_sha256"),
        "w3_transport_profile_sha256": _source_identity(transport_profile),
        "w3_transport_root_sha256": _source_identity(transport_profile, "root_sha256", "contract_root_sha256"),
        "w3_transport_semantic_sha256": _source_identity(transport_profile, "transport_semantic_sha256"),
        "w4_carrier_profile_sha256": _source_identity(carrier_profile),
        "w4_carrier_root_sha256": _source_identity(carrier_profile, "root_sha256"),
        "w4r_topology_profile_sha256": _source_identity(topology_profile),
        "w4r_topology_root_sha256": _source_identity(topology_profile, "root_sha256"),
    }
    if topology_profile is not None:
        nested = getattr(topology_profile, "parent_identities", None)
        if isinstance(nested, Mapping):
            for key, value in nested.items():
                values.setdefault(str(key), _plain(value))
    if supplied is not None:
        if not isinstance(supplied, Mapping):
            raise ConversionError("parent_identities must be a mapping")
        for key, value in supplied.items():
            if value is not None and not isinstance(value, str):
                raise ConversionError(f"parent identity {key!r} must be a string or null")
            if isinstance(value, str) and not _is_sha256(value):
                raise ConversionError(f"parent identity {key!r} is not a lowercase sha256")
            values[str(key)] = value
    return values


def _profile_number(value: Any, *, name: str, default: float) -> float:
    try:
        return _decode_scalar(value, name=name)
    except ConversionError:
        return _f64(default, name=name)


def _clock_bounds(geometry: Any, transport_profile: Any | None) -> tuple[float, float, Mapping[str, Any], Mapping[str, Any]]:
    base = _base_payload(geometry)
    clock = base.get("execution", {}).get("clock", base.get("dynamics", {}).get("clock", {}))
    if not isinstance(clock, Mapping):
        clock = {}
    h_min_obj = clock.get("h_min", {"numerator": 1, "denominator": 1000})
    h_max_obj = clock.get("h_max", {"numerator": 1, "denominator": 100})
    h_min = _decode_scalar(h_min_obj, name="h_min")
    h_max = _decode_scalar(h_max_obj, name="h_max")
    if transport_profile is not None:
        for name, attr in (("h_min", "h_min_s"), ("h_max", "h_max_s")):
            candidate = getattr(transport_profile, attr, None)
            if candidate is None:
                candidate = getattr(transport_profile, name, None)
            if candidate is not None:
                if name == "h_min":
                    h_min = _f64(candidate, name=name)
                else:
                    h_max = _f64(candidate, name=name)
    if not (0.0 < h_min <= h_max):
        raise ConversionError("registered clock interval is invalid")
    return h_min, h_max, _f64_tag(h_min), _f64_tag(h_max)


def _coordinate_phi(geometry: Any, carrier_profile: Any | None, topology_profile: Any | None) -> float:
    if carrier_profile is not None and getattr(carrier_profile, "phi", None) is not None:
        phi = _f64(carrier_profile.phi, name="phi", positive=True)
    elif topology_profile is not None and getattr(topology_profile, "phi", None) is not None:
        phi = _f64(topology_profile.phi, name="phi", positive=True)
    else:
        transform = _base_payload(geometry).get("dynamics", {}).get("coordinate_transform", {})
        if not isinstance(transform, Mapping) or transform.get("phi") is None:
            raise ConversionError("coordinate transform phi is absent from supplied W1 profile")
        phi = _decode_scalar(transform["phi"], name="phi")
    if topology_profile is not None and getattr(topology_profile, "phi", None) is not None:
        if not math.isclose(phi, _f64(topology_profile.phi, name="topology phi", positive=True), rel_tol=0.0, abs_tol=0.0):
            raise ConversionError("carrier/topology phi values disagree")
    return phi


def _state_layout(geometry: Any) -> Mapping[str, Any]:
    layout = getattr(_geometry_profile(geometry).base_profile, "state_layout", None)
    if not isinstance(layout, Mapping):
        payload = _base_payload(geometry)
        layout = payload.get("field", {}).get("state_layout", payload.get("state_layout"))
    if not isinstance(layout, Mapping):
        raise ConversionError("W2 profile has no state layout")
    required = ("scale_count", "mode_count", "component_count", "layout_id")
    if any(key not in layout for key in required):
        raise ConversionError("state layout is incomplete")
    if int(layout["component_count"]) != 9:
        raise ConversionError("W5 requires exactly nine components per scale")
    return MappingProxyType({str(key): _plain(value) for key, value in layout.items()})


def _profile_payload(
    geometry: Any,
    *,
    transport_profile: Any | None,
    carrier_profile: Any | None,
    topology_profile: Any | None,
    parent_identities: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    base = _base_payload(geometry)
    conversion = base.get("conversion", {})
    dynamics = base.get("dynamics", {})
    bounds = base.get("field", {}).get("state_bounds", {})
    if not isinstance(conversion, Mapping):
        conversion = {}
    if not isinstance(dynamics, Mapping):
        dynamics = {}
    if not isinstance(bounds, Mapping):
        bounds = {}
    phi = _coordinate_phi(geometry, carrier_profile, topology_profile)
    h_min, h_max, h_min_obj, h_max_obj = _clock_bounds(geometry, transport_profile)
    h_min_fraction = Fraction(str(h_min))
    h_max_fraction = Fraction(str(h_max))
    h_min_rational = {"numerator": int(h_min_fraction.numerator), "denominator": int(h_min_fraction.denominator)}
    h_max_rational = {"numerator": int(h_max_fraction.numerator), "denominator": int(h_max_fraction.denominator)}
    lambda_rate = _profile_number(conversion.get("lambda_per_s"), name="lambda_per_s", default=40.0)
    memory_time = _profile_number(conversion.get("epsilon_memory_time_s"), name="epsilon_memory_time_s", default=1.0)
    if lambda_rate < 0.0 or memory_time <= 0.0:
        raise ConversionError("conversion rate/memory time is invalid")
    rho_ref = 1.0
    rho_max = 0.25
    ema_max = _profile_number(bounds.get("epsilon2_ema_max"), name="epsilon2_ema_max", default=0.5)
    component_max_value = bounds.get("component_abs_max", [0.5])
    if isinstance(component_max_value, (tuple, list)) and component_max_value:
        component_max = max(_decode_scalar(item, name="component_abs_max") for item in component_max_value)
    else:
        component_max = _profile_number(component_max_value, name="component_abs_max", default=0.5)
    numerical_zero = _profile_number(conversion.get("numerical_zero_guard"), name="numerical_zero_guard", default=1.0e-9)
    uncertainty = _profile_number(
        dynamics.get("stability_envelope", {}).get("numerical_uncertainty_abs")
        if isinstance(dynamics.get("stability_envelope"), Mapping)
        else None,
        name="energy_uncertainty",
        default=1.0e-10,
    )
    work_tolerance = max(5.0e-10, uncertainty)
    epsilon_prog_min = 1.0e-6
    law = {
        "law_id": W5_LAW_DOMAIN,
        "normalization": "rho=|E_Y|^2+|E_I|^2; epsilon=|E_Y|^2-phi|E_I|^2",
        "frozen_q": "rho_bar^2/(rho_bar^2+phi^-2+m_epsilon2)",
        "alpha": "exp(-(1+phi)*lambda*(1-Q)*h)",
        "transfer": "T=epsilon*(1-alpha)/(1+phi)",
        "density_map": "rho_next=rho; epsilon_next=alpha*epsilon",
        "epsilon_evaluation": "factored-magnitude-difference.v1",
        "phase_rule": "own-phase; empty-target-inherits-other-sector; double-empty-remains-zero.v1",
        "ema": "m_next=(1-tau)m+tau*epsilon_next^2",
        "tau": "1-exp(-h/epsilon_memory_time)",
        "q_evaluations_per_conversion": 1,
        "conversion_maps_per_interval": 1,
        "ema_updates_per_interval": 1,
        "velocity_mutation": "none",
        "projection": "none",
        "clipping": "none",
        "repair": "none",
        "persistent_state_added": False,
    }
    law_sha = _sha256(law, W5_LAW_DOMAIN)
    stage_schedule = [
        "w3n-guarded-transport",
        "w4-corrected-carrier-seven-stage-split",
        "w4r-topological-force-in-both-carrier-kicks",
        "w5-frozen-q-position-conversion-at-carrier-center",
        "w5-single-post-step-epsilon2-ema",
    ]
    layout = _state_layout(geometry)
    payload: dict[str, Any] = {
        "schema": W5_CONVERSION_PROFILE_SCHEMA,
        "law_id": W5_LAW_DOMAIN,
        "law_sha256": law_sha,
        "law": law,
        "phi": _f64_tag(phi),
        "lambda_rate": _f64_tag(lambda_rate),
        "rho_ref": _f64_tag(rho_ref),
        "epsilon_memory_time_s": _f64_tag(memory_time),
        "epsilon_prog_min": _f64_tag(epsilon_prog_min),
        "clock": {
            "runtime_exact_rationals": [h_min_rational, h_max_rational],
            "h_min": h_min_obj,
            "h_max": h_max_obj,
            "runtime_membership": "reduced-positive-rational-closed-interval.v1",
        },
        "state_layout": layout,
        "split_schedule": stage_schedule,
        "parent_identities": _plain(parent_identities),
        "parents": _plain(parent_identities),
        "support": {
            "D_conv": {
                "closed": True,
                "rho_ref_positive": True,
                "position_density": {"EY_min": 0.0, "EI_min": 0.0, "EY_plus_EI_max": rho_max},
                "epsilon2_ema": [0.0, ema_max],
                "component_abs_max": component_max,
                "duration_s": [h_min_obj, h_max_obj],
                "frozen_before_observation": True,
            },
            "A_accepted": {
                "finite_only": True,
                "nonnegative_sector_densities": True,
                "density_sum_at_most": rho_max,
                "epsilon2_ema_at_most": ema_max,
                "component_abs_at_most": component_max,
                "density_conservation_abs": work_tolerance,
                "work_closure_abs": work_tolerance,
            },
        },
        "partition": {
            "D_prog": "abs(epsilon)>=epsilon_prog_min",
            "D_neutral": "abs(epsilon)<epsilon_prog_min",
            "balanced": "epsilon==0",
            "exact_zero": "EY==EI==epsilon2_ema==0",
        },
        "margins": {
            "Delta_T_min": _f64_tag(1.0e-12),
            "Delta_T_neutral": _f64_tag(1.0e-9),
            "U_T_max": _f64_tag(1.0e-12),
            "forward_density_floor": _f64_tag(0.0),
            "ema_upper_slack_min": _f64_tag(5.0e-7),
            "Delta_conversion": _f64_tag(numerical_zero),
            "U_conversion": _f64_tag(uncertainty),
        },
        "energy": {
            "mode": "dissipative-v1",
            "hamiltonian": "carrier_total_energy+topological_retention_energy+extra_conservative_energy",
            "classification": "W+U<-Delta=>Q=-W; |W|+U<=Delta=>signed-numerical-zero; otherwise-reject",
            "link_accounting": "one-complete-hamiltonian-evaluation; no-duplicate-composition-or-topology",
        },
        "numerical_zero_guard": _f64_tag(numerical_zero),
        "q_evaluation_count": 1,
        "conversion_count": 1,
        "ema_update_count": 1,
        "additional_state": False,
        "no_extra_persistent_state": True,
    }
    support_d_conv = {
        "closed": True,
        "rho_ref_positive": True,
        "runtime_exact_rationals": [h_min_rational, h_max_rational],
        "epsilon2_ema": {"min": _f64_tag(0.0), "max": _f64_tag(ema_max)},
        "component_abs_max": _f64_tag(component_max),
        "duration_s": [h_min_obj, h_max_obj],
        "phase_branches": ["yang-own-phase", "yin-own-phase", "empty-yang-inherits-yin", "empty-yin-inherits-yang", "double-empty"],
        "frozen_before_observation": True,
    }
    accepted_a = {
        "finite_only": True,
        "nonnegative_sector_densities": True,
        "density_sum_at_most": _f64_tag(rho_max),
        "epsilon2_ema_at_most": _f64_tag(ema_max),
        "component_abs_at_most": _f64_tag(component_max),
        "density_conservation_abs": _f64_tag(work_tolerance),
        "work_closure_abs": _f64_tag(work_tolerance),
    }
    payload["D_conv"] = support_d_conv
    payload["A_accepted"] = accepted_a
    payload["support"] = {"D_conv": support_d_conv, "A_accepted": accepted_a}
    cover_semantics = {
        "cell_definition": "D_nu=D_conv intersect predicate(cell_id)",
        "unspecified_coordinates": "full frozen D_conv support subject only to cell predicate",
        "coordinates_covered": ["EY", "EI", "epsilon2_ema", "rho_ref", "phi", "lambda_rate", "phase_branch", "scale", "mode", "batch", "duration_s"],
        "boundary_values": "exact tagged-f64 profile values",
        "interior": "relative interior within D_conv",
        "overlap_policy": "shared boundaries and named lower-dimensional controls only",
    }
    exact_cover = [
        {"cell_id": "C00-exact-zero", "epsilon_interval": [_f64_tag(0.0), _f64_tag(0.0)], "epsilon2_ema_interval": [_f64_tag(0.0), _f64_tag(0.0)], "predicate": "EY==EI==epsilon2_ema==0"},
        {"cell_id": "C01-balanced-memory-zero", "epsilon_interval": [_f64_tag(0.0), _f64_tag(0.0)], "epsilon2_ema_interval": [_f64_tag(0.0), _f64_tag(0.0)], "predicate": "epsilon==0 and epsilon2_ema==0"},
        {"cell_id": "C02-balanced-memory-positive", "epsilon_interval": [_f64_tag(0.0), _f64_tag(0.0)], "epsilon2_ema_interval": [_f64_tag(0.0), _f64_tag(ema_max)], "predicate": "epsilon==0 and epsilon2_ema>0"},
        {"cell_id": "C03-neutral-positive", "epsilon_interval": [_f64_tag(0.0), _f64_tag(epsilon_prog_min)], "epsilon2_ema_interval": [_f64_tag(0.0), _f64_tag(ema_max)], "predicate": "0<epsilon<epsilon_prog_min"},
        {"cell_id": "C04-neutral-negative", "epsilon_interval": [_f64_tag(-epsilon_prog_min), _f64_tag(0.0)], "epsilon2_ema_interval": [_f64_tag(0.0), _f64_tag(ema_max)], "predicate": "-epsilon_prog_min<epsilon<0"},
        {"cell_id": "C05-progress-positive", "epsilon_interval": [_f64_tag(epsilon_prog_min), _f64_tag(rho_max)], "epsilon2_ema_interval": [_f64_tag(0.0), _f64_tag(ema_max)], "predicate": "epsilon>=epsilon_prog_min"},
        {"cell_id": "C06-progress-negative", "epsilon_interval": [_f64_tag(-phi * rho_max), _f64_tag(-epsilon_prog_min)], "epsilon2_ema_interval": [_f64_tag(0.0), _f64_tag(ema_max)], "predicate": "epsilon<=-epsilon_prog_min"},
    ]
    rich_cover = []
    for ordinal, row in enumerate(exact_cover):
        rich_cover.append({
            **row,
            "order": ordinal,
            "D_conv": _plain(support_d_conv),
            "A_accepted": _plain(accepted_a),
            "registered_margins": {"Delta_T_min": _f64_tag(1.0e-12), "Delta_T_neutral": _f64_tag(1.0e-9), "U_T_max": _f64_tag(1.0e-12)},
            "analytic_operation_count_upper": 128,
        })
    payload["cover"] = {"cells": rich_cover, "semantics": cover_semantics, "endpoint_semantics": "closed-exact-rational.v1"}
    payload["complete_domain_cover"] = {"cells": exact_cover, "semantics": cover_semantics}
    payload["complete_domain_cover_semantics"] = cover_semantics
    registered_margins = dict(payload["margins"])
    registered_margins["analytic_operation_count_upper"] = 128
    payload["margins"] = registered_margins
    payload["registered_margins"] = registered_margins
    payload["parameters"] = {
        "epsilon_memory_time_candidates_s": [_f64_tag(1.0), _f64_tag(0.5), _f64_tag(2.0), _f64_tag(0.25)],
        "epsilon_memory_time_s": _f64_tag(memory_time),
        "epsilon_prog_min": _f64_tag(epsilon_prog_min),
        "epsilon_memory_time_selection_order": "listed-order-first-all-cell-pass",
    }
    payload["profile_sha256"] = _sha256(payload, W5_PROFILE_DOMAIN)
    root = {
        "schema": W5_CONVERSION_ROOT_SCHEMA,
        "law_id": W5_LAW_DOMAIN,
        "profile_sha256": payload["profile_sha256"],
        "law_sha256": law_sha,
        "parent_identities": _plain(parent_identities),
        "state_layout": layout,
        "split_schedule": stage_schedule,
        "additional_state": False,
    }
    root["self_sha256"] = _sha256(root, W5_ROOT_DOMAIN)
    values = {
        "phi": phi,
        "lambda_rate": lambda_rate,
        "rho_ref": rho_ref,
        "h_min": h_min,
        "h_max": h_max,
        "epsilon_memory_time": memory_time,
        "epsilon_prog_min": epsilon_prog_min,
        "rho_max": rho_max,
        "epsilon2_ema_max": ema_max,
        "component_abs_max": component_max,
        "density_tolerance": work_tolerance,
        "work_tolerance": work_tolerance,
        "energy_uncertainty": uncertainty,
    }
    return payload, root, values


def load_w5_conversion_profile(
    geometry_profile: Any | None = None,
    *,
    geometry: Any | None = None,
    transport_profile: Any | None = None,
    carrier_profile: Any | None = None,
    topology_profile: Any | None = None,
    parent_identities: Mapping[str, Any] | None = None,
) -> QiConversionProfile:
    """Build an immutable W5 law from supplied validated profile objects."""
    if geometry_profile is None:
        geometry_profile = geometry
    if geometry_profile is None:
        raise ConversionError("geometry_profile is required")
    geometry_profile = _geometry_profile(geometry_profile)
    parents = _parent_identities(
        geometry_profile,
        transport_profile=transport_profile,
        carrier_profile=carrier_profile,
        topology_profile=topology_profile,
        supplied=parent_identities,
    )
    payload, root, values = _profile_payload(
        geometry_profile,
        transport_profile=transport_profile,
        carrier_profile=carrier_profile,
        topology_profile=topology_profile,
        parent_identities=parents,
    )
    runtime = (values["h_min"], values["h_max"])
    return QiConversionProfile(
        MappingProxyType(payload),
        MappingProxyType(root),
        str(payload["profile_sha256"]),
        str(root["self_sha256"]),
        str(payload["law_sha256"]),
        values["phi"],
        values["lambda_rate"],
        values["rho_ref"],
        values["h_min"],
        values["h_max"],
        runtime,
        values["epsilon_memory_time"],
        values["epsilon_prog_min"],
        values["rho_max"],
        values["epsilon2_ema_max"],
        values["component_abs_max"],
        values["density_tolerance"],
        values["work_tolerance"],
        values["energy_uncertainty"],
    )


def _verify_profile(
    profile: QiConversionProfile,
    geometry: Any,
    *,
    transport_profile: Any | None = None,
    carrier_profile: Any | None = None,
    topology_profile: Any | None = None,
) -> None:
    if not isinstance(profile, QiConversionProfile):
        raise ConversionError("conversion_profile must be QiConversionProfile")
    geometry = _geometry_profile(geometry)
    payload = dict(profile.payload)
    payload.pop("profile_sha256", None)
    if _sha256(payload, W5_PROFILE_DOMAIN) != profile.profile_sha256:
        raise ConversionError("conversion profile identity mismatch")
    root = dict(profile.root)
    root.pop("self_sha256", None)
    if _sha256(root, W5_ROOT_DOMAIN) != profile.root_sha256:
        raise ConversionError("conversion root identity mismatch")
    law = payload.get("law")
    if not isinstance(law, Mapping) or _sha256(law, W5_LAW_DOMAIN) != profile.law_sha256:
        raise ConversionError("conversion law identity mismatch")
    if payload.get("law_id") != W5_LAW_DOMAIN or law.get("law_id") != W5_LAW_DOMAIN:
        raise ConversionError("unsupported W5 conversion law")
    layout = payload.get("state_layout")
    if _plain(layout) != _plain(_state_layout(geometry)):
        raise ConversionError("conversion profile state layout disagrees with geometry")
    if payload.get("additional_state") is not False or payload.get("no_extra_persistent_state") is not True:
        raise ConversionError("W5 conversion may not add persistent state")
    current = _parent_identities(
        geometry,
        transport_profile=transport_profile,
        carrier_profile=carrier_profile,
        topology_profile=topology_profile,
        supplied=None,
    )
    bound = profile.parent_identities
    for key, now in current.items():
        before = bound.get(key)
        if _is_sha256(before) and _is_sha256(now) and before != now:
            raise ConversionError(f"conversion profile parent {key} disagrees with supplied profile")
    if not (profile.phi > 0.0 and profile.rho_ref > 0.0 and profile.epsilon_memory_time > 0.0 and profile.h_min > 0.0 and profile.h_min <= profile.h_max):
        raise ConversionError("conversion profile scalar guards are invalid")


def _duration_rational(duration: float) -> Mapping[str, Any]:
    try:
        fraction = Fraction(str(duration))
    except Exception as exc:
        raise ConversionError("duration_s is not an exact decimal/rational f64") from exc
    if fraction <= 0:
        raise ConversionError("duration_s must be positive")
    return MappingProxyType({"numerator": int(fraction.numerator), "denominator": int(fraction.denominator)})


def _decimal_fraction(value: Any, *, name: str) -> Fraction:
    try:
        finite = _f64(value, name=name, positive=True)
        return Fraction(str(finite))
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"{name} is not an exact decimal/rational f64") from exc


def _rational_fraction(value: Any, *, name: str) -> Fraction:
    if not isinstance(value, Mapping):
        raise ConversionError(f"{name} must be an exact rational mapping")
    numerator = value.get("numerator")
    denominator = value.get("denominator")
    if isinstance(numerator, bool) or not isinstance(numerator, int) or isinstance(denominator, bool) or not isinstance(denominator, int):
        raise ConversionError(f"{name} must contain integer numerator and denominator")
    if denominator <= 0:
        raise ConversionError(f"{name} denominator must be positive")
    result = Fraction(numerator, denominator)
    if result <= 0:
        raise ConversionError(f"{name} must be positive")
    return result


def _declared_fraction(value: Any, *, name: str) -> Fraction:
    if isinstance(value, Mapping) and "numerator" in value and "denominator" in value:
        return _rational_fraction(value, name=name)
    return _decimal_fraction(value, name=name)


def _profile_runtime_bounds(profile: QiConversionProfile) -> tuple[Fraction, Fraction]:
    payload = profile.payload
    clock = payload.get("clock") if isinstance(payload, Mapping) else None
    expected_membership = "reduced-positive-rational-closed-interval.v1"
    if not isinstance(clock, Mapping) or clock.get("runtime_membership") != expected_membership:
        raise ConversionError("conversion profile does not declare the exact rational runtime clock")
    endpoint_values = clock.get("runtime_exact_rationals")
    if not isinstance(endpoint_values, (tuple, list)) or len(endpoint_values) != 2:
        raise ConversionError("conversion profile runtime clock endpoints are missing")
    registered = tuple(
        _rational_fraction(value, name=f"runtime_exact_rationals[{index}]")
        for index, value in enumerate(endpoint_values)
    )
    profile_bounds = (
        _decimal_fraction(profile.h_min, name="profile h_min"),
        _decimal_fraction(profile.h_max, name="profile h_max"),
    )
    clock_bounds = (
        _declared_fraction(clock.get("h_min"), name="clock h_min"),
        _declared_fraction(clock.get("h_max"), name="clock h_max"),
    )
    runtime_values = profile.runtime_durations
    if not isinstance(runtime_values, (tuple, list)) or len(runtime_values) != 2:
        raise ConversionError("conversion profile runtime duration bounds are missing")
    runtime_bounds = tuple(
        _decimal_fraction(value, name=f"runtime_durations[{index}]")
        for index, value in enumerate(runtime_values)
    )
    if registered[0] > registered[1] or profile_bounds != registered or clock_bounds != registered or runtime_bounds != registered:
        raise ConversionError("conversion profile runtime duration identities disagree")
    return registered


def _resolve_duration(profile: QiConversionProfile, duration_s: float | None) -> tuple[float, Mapping[str, Any]]:
    runtime_min, runtime_max = _profile_runtime_bounds(profile)
    duration = profile.h_min if duration_s is None else _f64(duration_s, name="duration_s", positive=True)
    duration_fraction = _decimal_fraction(duration, name="duration_s")
    if duration_fraction < runtime_min or duration_fraction > runtime_max:
        raise ConversionError("duration_s lies outside the closed registered rational clock interval")
    rational = _duration_rational(duration)
    resolved_fraction = _rational_fraction(rational, name="duration_s")
    if resolved_fraction != duration_fraction or float(resolved_fraction) != duration:
        raise ConversionError("duration_s is not exactly representable as its registered rational")
    return duration, rational


def derive_epsilon_tau(profile: QiConversionProfile, duration_s: float) -> float:
    if not isinstance(profile, QiConversionProfile):
        raise ConversionError("derive_epsilon_tau requires QiConversionProfile")
    duration, _ = _resolve_duration(profile, duration_s)
    result = -math.expm1(-duration / profile.epsilon_memory_time)
    if not (0.0 <= result < 1.0) or not math.isfinite(result):
        raise ConversionError("derived epsilon EMA coefficient is invalid")
    return 0.0 if result == 0.0 else result


# ---------------------------------------------------------------------------
# Frozen-Q center map and post-step EMA.


def _component_grid(surface: QiFlowGeometryV2, scale: int, component: int) -> torch.Tensor:
    return surface.component_grid(scale, component)


def _phase_rescale(
    own: torch.Tensor,
    other: torch.Tensor,
    own_density: torch.Tensor,
    other_density: torch.Tensor,
    target_density: torch.Tensor,
) -> torch.Tensor:
    """Preserve own phase, or inherit donor phase for an empty sector."""
    result = torch.zeros_like(own)
    own_mask = own_density > 0.0
    donor_mask = (~own_mask) & (other_density > 0.0)
    if bool(own_mask.any().item()):
        result[own_mask] = own[own_mask] * torch.sqrt(target_density[own_mask] / own_density[own_mask])
    if bool(donor_mask.any().item()):
        result[donor_mask] = other[donor_mask] * torch.sqrt(target_density[donor_mask] / other_density[donor_mask])
    if not bool(torch.isfinite(result).all().item()):
        raise ConversionError("phase-preserving frozen-Q rescale is nonfinite")
    return result.contiguous()


def _map_row(
    scale: int,
    q: torch.Tensor,
    alpha: torch.Tensor,
    epsilon: torch.Tensor,
    transfer: torch.Tensor,
    rho: torch.Tensor,
    next_y: torch.Tensor,
    next_i: torch.Tensor,
    branches: Mapping[str, int],
) -> Mapping[str, Any]:
    reconstructed = next_y.square().abs() + next_i.square().abs()
    return MappingProxyType({
        "scale": scale,
        "q_min": float(q.amin().item()),
        "q_max": float(q.amax().item()),
        "alpha_min": float(alpha.amin().item()),
        "alpha_max": float(alpha.amax().item()),
        "epsilon_min": float(epsilon.amin().item()),
        "epsilon_max": float(epsilon.amax().item()),
        "transfer_min": float(transfer.amin().item()),
        "transfer_max": float(transfer.amax().item()),
        "transfer_l1": float(transfer.abs().sum().item()),
        "signed_progress_min": float((torch.sign(epsilon) * transfer).amin().item()),
        "density_pre": float(rho.sum().item()),
        "density_post_analytic": float((rho).sum().item()),
        "density_post_reconstructed": float(reconstructed.sum().item()),
        "density_map_closure_abs": float(((next_y.square().abs() + next_i.square().abs()) - rho).abs().amax().item()),
        "density_closure_abs": float(((next_y.square().abs() + next_i.square().abs()) - rho).abs().amax().item()),
        "balanced_count": int(torch.count_nonzero(epsilon == 0.0).item()),
        "zero_count": int(branches.get("double-empty", 0)),
        "phase_branches": dict(branches),
    })


def _clock_aggregate(values: torch.Tensor, *, name: str) -> dict[str, float]:
    if values.numel() == 0 or not bool(torch.isfinite(values).all().item()):
        raise ConversionError(f"{name} process-clock values are nonfinite or empty")
    return {
        "min": float(values.amin().item()),
        "max": float(values.amax().item()),
        "mean": float(values.mean().item()),
    }


def _process_clock_row(
    *,
    scale: int,
    q: torch.Tensor,
    alpha: torch.Tensor,
    epsilon: torch.Tensor,
    next_y: torch.Tensor,
    next_i: torch.Tensor,
    duration: float,
    lambda_rate: float,
    phi: float,
    epsilon_guard: float,
) -> Mapping[str, Any]:
    """Record derived conversion age without adding state to the field."""
    tau_values = (1.0 - q) * duration
    chi_values = tau_values * lambda_rate
    next_epsilon = (next_y.abs().square() - phi * next_i.abs().square()).contiguous()
    if not bool(torch.isfinite(next_epsilon).all().item()):
        raise ConversionError("successor epsilon is nonfinite in process-clock witness")
    if not bool(torch.isfinite(alpha).all().item()) or not bool((alpha > 0.0).all().item()):
        raise ConversionError("conversion alpha is invalid in process-clock witness")
    q_summary = _clock_aggregate(q, name=f"scale {scale} q")
    tau_summary = _clock_aggregate(tau_values, name=f"scale {scale} Delta tau_F")
    chi_summary = _clock_aggregate(chi_values, name=f"scale {scale} Delta chi_F")
    alpha_summary = _clock_aggregate(alpha, name=f"scale {scale} alpha")
    epsilon_abs = epsilon.abs()
    next_epsilon_abs = next_epsilon.abs()
    endpoint_mask = (
        (epsilon_abs > epsilon_guard)
        & (next_epsilon_abs > epsilon_guard)
        & (epsilon * next_epsilon > 0.0)
    )
    resolved_count = int(torch.count_nonzero(endpoint_mask).item())
    sample_count = int(q.numel())
    unresolved_count = sample_count - resolved_count
    endpoint_alpha: dict[str, float] | None = None
    tau_endpoint: dict[str, float] | None = None
    chi_endpoint: dict[str, float] | None = None
    alpha_closure_abs = 0.0
    tau_closure_abs: float | None = None
    chi_closure_abs: float | None = None
    if resolved_count:
        endpoint_alpha_values = next_epsilon_abs[endpoint_mask] / epsilon_abs[endpoint_mask]
        if not bool(torch.isfinite(endpoint_alpha_values).all().item()) or not bool((endpoint_alpha_values > 0.0).all().item()):
            raise ConversionError("endpoint alpha is invalid in process-clock witness")
        endpoint_alpha = _clock_aggregate(endpoint_alpha_values, name=f"scale {scale} endpoint alpha")
        endpoint_chi_values = -torch.log(endpoint_alpha_values) / (1.0 + phi)
        if not bool(torch.isfinite(endpoint_chi_values).all().item()):
            raise ConversionError("endpoint conversion exposure is nonfinite")
        chi_endpoint = _clock_aggregate(endpoint_chi_values, name=f"scale {scale} endpoint chi_F")
        alpha_closure_abs = float((endpoint_alpha_values - alpha[endpoint_mask]).abs().amax().item())
        chi_closure_abs = float((endpoint_chi_values - chi_values[endpoint_mask]).abs().amax().item())
        if lambda_rate > 0.0:
            endpoint_tau_values = endpoint_chi_values / lambda_rate
            tau_endpoint = _clock_aggregate(endpoint_tau_values, name=f"scale {scale} endpoint tau_F")
            tau_closure_abs = float((endpoint_tau_values - tau_values[endpoint_mask]).abs().amax().item())
    reasons: list[str] = []
    if lambda_rate == 0.0:
        reasons.append("lambda=0: endpoint inversion to tau_F is undefined; direct Delta tau_F remains defined")
    if unresolved_count:
        reasons.append("epsilon≈0 or successor epsilon≈0: endpoint quotient/log is unobservable")
    return {
        "scale": scale,
        "sample_count": sample_count,
        "q": q_summary,
        "lambda_rate": lambda_rate,
        "delta_tau_F": tau_summary,
        "delta_chi_F": chi_summary,
        "tau_F_defined": True,
        "chi_F_defined": True,
        "tau_F_expected": tau_summary,
        "chi_F_expected": chi_summary,
        "tau_F_endpoint": tau_endpoint,
        "chi_F_endpoint": chi_endpoint,
        "alpha_expected": alpha_summary,
        "alpha_endpoint": endpoint_alpha,
        "alpha_closure_abs": alpha_closure_abs,
        "tau_F_closure_abs": tau_closure_abs,
        "chi_F_closure_abs": chi_closure_abs,
        "endpoint_observable": bool(resolved_count),
        "tau_F_endpoint_observable": bool(lambda_rate > 0.0 and resolved_count),
        "chi_F_endpoint_observable": bool(resolved_count),
        "epsilon_pre_nonzero_count": int(torch.count_nonzero(epsilon_abs > epsilon_guard).item()),
        "epsilon_post_nonzero_count": int(torch.count_nonzero(next_epsilon_abs > epsilon_guard).item()),
        "endpoint_resolved_count": resolved_count,
        "endpoint_unresolved_count": unresolved_count,
        "endpoint_degeneracy": bool(unresolved_count),
        "degeneracy_reasons": reasons,
    }


def _frozen_q_map(
    state: QiFlowStateV3,
    *,
    geometry: Any,
    profile: QiConversionProfile,
    carrier_profile: Any,
    duration_s: float,
    lambda_rate: float | None = None,
    process_rows: list[Mapping[str, Any]] | None = None,
) -> tuple[QiFlowStateV3, tuple[Mapping[str, Any], ...], Mapping[str, int]]:
    """Apply exactly one frozen-Q position map without changing velocities/EMA."""
    geometry = _geometry_profile(geometry)
    _verify_profile(profile, geometry)
    state.validate(geometry.base_profile)
    duration, _ = _resolve_duration(profile, duration_s)
    if not bool(torch.isfinite(state.field).all().item()):
        raise ConversionError("W5 predecessor contains nonfinite values")
    if carrier_profile is None:
        raise ConversionError("frozen-Q map requires a carrier profile")
    values = carrier_coordinates(state, geometry=geometry, profile=carrier_profile)
    surface = QiFlowGeometryV2(state, geometry)
    mapped_d: list[torch.Tensor] = []
    mapped_c: list[torch.Tensor] = []
    branches_total = {"yang-own-phase": 0, "yin-own-phase": 0, "empty-yang-inherits-yin": 0, "empty-yin-inherits-yang": 0, "double-empty": 0}
    rows: list[Mapping[str, Any]] = []
    rate = profile.lambda_rate if lambda_rate is None else _f64(lambda_rate, name="lambda_rate", nonnegative=True)
    for scale, (yang, yin) in enumerate(zip(values.ey, values.ei, strict=True)):
        yang_density = yang.abs().square()
        yin_density = yin.abs().square()
        rho = yang_density + yin_density
        epsilon = (yang.abs() - math.sqrt(profile.phi) * yin.abs()) * (yang.abs() + math.sqrt(profile.phi) * yin.abs())
        ema = _component_grid(surface, scale, 8)
        if not bool(torch.isfinite(rho).all().item()) or not bool(torch.isfinite(epsilon).all().item()):
            raise ConversionError("W5 density/epsilon is nonfinite")
        if not bool(((yang_density >= 0.0) & (yin_density >= 0.0) & (rho <= profile.rho_max)).all().item()):
            raise ConversionError("W5 predecessor lies outside closed density support")
        if not bool(((ema >= 0.0) & (ema <= profile.epsilon2_ema_max)).all().item()):
            raise ConversionError("W5 predecessor lies outside closed EMA support")
        rho_bar = rho / profile.rho_ref
        ema_bar = ema / (profile.rho_ref * profile.rho_ref)
        denominator = rho_bar.square() + profile.phi ** -2 + ema_bar
        q = rho_bar.square() / denominator
        if not bool(torch.isfinite(q).all().item()) or not bool(((q >= 0.0) & (q < 1.0)).all().item()):
            raise ConversionError("W5 frozen Q is outside [0,1)")
        alpha = torch.exp(-(1.0 + profile.phi) * rate * (1.0 - q) * duration)
        transfer = epsilon * (1.0 - alpha) / (1.0 + profile.phi)
        next_y_density = yang_density - transfer
        next_i_density = yin_density + transfer
        if not bool(torch.isfinite(transfer).all().item()) or not bool(((next_y_density >= 0.0) & (next_i_density >= 0.0)).all().item()):
            raise ConversionError("W5 frozen-Q law left the nonnegative density cone")
        if not bool((next_y_density + next_i_density <= profile.rho_max).all().item()):
            raise ConversionError("W5 frozen-Q law left the accepted density support")
        own_y = yang_density > 0.0
        own_i = yin_density > 0.0
        branches = {
            "yang-own-phase": int(torch.count_nonzero(own_y).item()),
            "yin-own-phase": int(torch.count_nonzero(own_i).item()),
            "empty-yang-inherits-yin": int(torch.count_nonzero((~own_y) & own_i).item()),
            "empty-yin-inherits-yang": int(torch.count_nonzero(own_y & (~own_i)).item()),
            "double-empty": int(torch.count_nonzero((~own_y) & (~own_i)).item()),
        }
        for key, value in branches.items():
            branches_total[key] += value
        next_y = _phase_rescale(yang, yin, yang_density, yin_density, next_y_density)
        next_i = _phase_rescale(yin, yang, yin_density, yang_density, next_i_density)
        mapped_d_value = next_y - profile.phi * next_i
        mapped_c_value = (profile.phi * next_y + next_i) * (1.0 / (1.0 + profile.phi * profile.phi))
        mapped_d.append(mapped_d_value.contiguous())
        mapped_c.append(mapped_c_value.contiguous())
        rows.append(_map_row(scale, q, alpha, epsilon, transfer, rho, next_y, next_i, branches))
        if process_rows is not None:
            process_rows.append(
                _process_clock_row(
                    scale=scale,
                    q=q,
                    alpha=alpha,
                    epsilon=epsilon,
                    next_y=next_y,
                    next_i=next_i,
                    duration=duration,
                    lambda_rate=rate,
                    phi=profile.phi,
                    epsilon_guard=profile.epsilon_prog_min,
                )
            )
    if rate == 0.0:

        mapped = QiFlowStateV3(state.field.detach().contiguous().clone())
    else:
        mapped = _replace_coordinates(
            state,
            geometry=geometry,
            profile=carrier_profile,
            d=tuple(mapped_d),
            c=tuple(mapped_c),
            vd=values.vd,
            vc=values.vc,
        )
    mapped.validate(geometry.base_profile)
    return mapped, tuple(rows), MappingProxyType(branches_total)
def _clock_rows_aggregate(
    rows: Sequence[Mapping[str, Any]],
    field: str,
) -> dict[str, float] | None:
    summaries = [row.get(field) for row in rows]
    if not summaries:
        return None
    if any(not isinstance(summary, Mapping) for summary in summaries):
        return None
    typed = [summary for summary in summaries if isinstance(summary, Mapping)]
    if len(typed) != len(summaries):
        return None
    counts = [int(row.get("sample_count", 0)) for row in rows]
    if any(count <= 0 for count in counts):
        return None
    return {
        "min": min(float(summary["min"]) for summary in typed),
        "max": max(float(summary["max"]) for summary in typed),
        "mean": math.fsum(float(summary["mean"]) * count for summary, count in zip(typed, counts, strict=True)) / sum(counts),
    }


def _process_clock_receipt(
    rows: Sequence[Mapping[str, Any]],
    conversion_rows: Sequence[Mapping[str, Any]],
    *,
    duration: float,
    duration_rational: Mapping[str, Any],
    lambda_rate: float,
    epsilon_guard: float,
) -> Mapping[str, Any]:
    """Aggregate one derived process clock over the frozen-Q conversion rows."""
    if len(rows) != len(conversion_rows) or not rows:
        raise ConversionError("process-clock rows do not cover conversion rows exactly")
    q_summary = _clock_rows_aggregate(rows, "q")
    delta_tau = _clock_rows_aggregate(rows, "delta_tau_F")
    delta_chi = _clock_rows_aggregate(rows, "delta_chi_F")
    if q_summary is None or delta_tau is None or delta_chi is None:
        raise ConversionError("process-clock aggregate is incomplete")
    unresolved = sum(int(row["endpoint_unresolved_count"]) for row in rows)
    resolved = sum(int(row["endpoint_resolved_count"]) for row in rows)
    closure_values = [
        float(value)
        for row in rows
        for value in (row.get("alpha_closure_abs"), row.get("tau_F_closure_abs"), row.get("chi_F_closure_abs"))
        if value is not None
    ]
    if not closure_values or not all(math.isfinite(value) for value in closure_values):
        raise ConversionError("process-clock closure is not finite")
    reasons: list[str] = []
    for row in rows:
        for reason in row.get("degeneracy_reasons", ()):
            if reason not in reasons:
                reasons.append(str(reason))
    process_clock: dict[str, Any] = {
        "schema": "cassi.qi-flow-process-clock.v1",
        "coordinate_duration_s": duration,
        "coordinate_duration_rational": _plain(duration_rational),
        "coordinate_time_ground_truth": True,
        "lambda_rate": lambda_rate,
        "lambda_rate_bounds": {"min": lambda_rate, "max": lambda_rate},
        "q_bounds": {"min": q_summary["min"], "max": q_summary["max"], "mean": q_summary["mean"]},
        "delta_tau_F": delta_tau,
        "delta_chi_F": delta_chi,
        "tau_F_defined": True,
        "chi_F_defined": True,
        "evaluation_count": len(rows),
        "conversion_row_count": len(conversion_rows),
        "one_process_age_evaluation_per_conversion_row": True,
        "normalization": "d tau_F=(1-Q) dt; Delta tau_F=(1-Q) h; Delta chi_F=lambda*Delta tau_F",
        "normalization_provenance": {
            "law_id": W5_LAW_DOMAIN,
            "coordinate_time": "dt",
            "source": "single frozen-Q conversion map",
            "epsilon_guard": epsilon_guard,
        },
        "rows": _plain(rows),
        "endpoint_observable": bool(resolved),
        "endpoint_degenerate": bool(unresolved),
        "lambda_zero": lambda_rate == 0.0,
        "epsilon_near_zero": bool(unresolved),
        "observability": {
            "delta_tau_F": True,
            "delta_chi_F": True,
            "endpoint_alpha": bool(resolved),
            "endpoint_tau_F": bool(lambda_rate > 0.0 and resolved),
            "endpoint_chi_F": bool(resolved),
        },
        "degeneracy_reasons": reasons,
        "resolved_endpoint_count": resolved,
        "unresolved_endpoint_count": unresolved,
        "closure_abs": max(closure_values),
        "closure_finite": True,
    }
    return process_clock



def _epsilon_sample(state: QiFlowStateV3, *, geometry: Any, profile: QiConversionProfile, carrier_profile: Any) -> tuple[torch.Tensor, ...]:
    surface = QiFlowGeometryV2(state, _geometry_profile(geometry))
    coords = carrier_coordinates(state, geometry=geometry, profile=carrier_profile)
    return tuple((yang.abs().square() - profile.phi * yin.abs().square()).square().contiguous() for yang, yin in zip(coords.ey, coords.ei, strict=True))


def _update_ema_once(
    state: QiFlowStateV3,
    *,
    geometry: Any,
    profile: QiConversionProfile,
    carrier_profile: Any,
    duration_s: float,
    enabled: bool,
) -> tuple[QiFlowStateV3, float, tuple[Mapping[str, Any], ...]]:
    if not isinstance(enabled, bool):
        raise ConversionError("epsilon_ema_enabled must be boolean")
    duration, _ = _resolve_duration(profile, duration_s)
    tau = derive_epsilon_tau(profile, duration) if enabled else 0.0
    geometry = _geometry_profile(geometry)
    surface = QiFlowGeometryV2(state, geometry)
    samples = _epsilon_sample(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile)
    candidate_field = state.field.clone()
    modes = int(geometry.base_profile.state_layout["mode_count"])
    rows: list[Mapping[str, Any]] = []
    for scale, sample in enumerate(samples):
        old = surface.component_grid(scale, 8)
        next_ema = old if tau == 0.0 else (1.0 - tau) * old + tau * sample
        if not bool(torch.isfinite(next_ema).all().item()) or not bool(((next_ema >= 0.0) & (next_ema <= profile.epsilon2_ema_max)).all().item()):
            raise ConversionError("W5 epsilon2 EMA update left the accepted domain")
        packed = surface.grid_modes(scale, next_ema.contiguous())
        candidate_field[scale, 8 * modes : 9 * modes, :] = packed
        rows.append(MappingProxyType({
            "scale": scale,
            "pre_min": float(old.amin().item()),
            "pre_max": float(old.amax().item()),
            "sample_min": float(sample.amin().item()),
            "sample_max": float(sample.amax().item()),
            "post_min": float(next_ema.amin().item()),
            "post_max": float(next_ema.amax().item()),
            "enabled": enabled,
        }))
    candidate = QiFlowStateV3(candidate_field.contiguous())
    candidate.validate(geometry.base_profile)
    return candidate, tau, tuple(rows)


# ---------------------------------------------------------------------------
# Full Hamiltonian/work ledger and integrated guarded transition.


def _call_energy(
    law: Any,
    state: QiFlowStateV3,
    *,
    geometry: Any,
    carrier_profile: Any,
    topology_profile: Any,
) -> float:
    energy = getattr(law, "energy", None)
    if not callable(energy):
        raise ConversionError("extra conservative law must provide energy")
    try:
        parameters = inspect.signature(energy).parameters
    except (TypeError, ValueError) as exc:
        raise ConversionError("extra conservative law energy signature is unavailable") from exc
    kwargs: dict[str, Any] = {}
    supplied = {
        "geometry": geometry,
        "geometry_profile": geometry,
        "carrier_profile": carrier_profile,
        "topology_profile": topology_profile,
    }
    accepts_var_kw = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    for key, value in supplied.items():
        if accepts_var_kw or key in parameters:
            kwargs[key] = value
    try:
        result = energy(state, **kwargs)
    except TypeError as exc:
        raise ConversionError(f"extra conservative law energy call failed: {exc}") from exc
    if isinstance(result, torch.Tensor):
        if result.ndim != 0:
            raise ConversionError("extra conservative energy must be a finite scalar")
        result = result.detach().item()
    result = _f64(result, name="extra conservative energy")
    return result


def _complete_hamiltonian(
    state: QiFlowStateV3,
    *,
    geometry: Any,
    carrier_profile: Any,
    topology_law: QiTopologicalRetentionLaw,
    topology_profile: QiTopologyProfile,
    extra_conservative_law: Any | None,
) -> Mapping[str, Any]:
    carrier = _f64(carrier_total_energy(state, geometry=geometry, profile=carrier_profile), name="carrier Hamiltonian")
    topology = _f64(topology_law.potential(state), name="topological Hamiltonian", nonnegative=True)
    extra = 0.0 if extra_conservative_law is None else _call_energy(
        extra_conservative_law,
        state,
        geometry=geometry,
        carrier_profile=carrier_profile,
        topology_profile=topology_profile,
    )
    total = _f64(carrier + topology + extra, name="complete Hamiltonian")
    return MappingProxyType({
        "carrier": carrier,
        "topological": topology,
        "extra_conservative": extra,
        "link_energy": extra,
        "total": total,
    })


def _energy_components(
    state: QiFlowStateV3,
    *,
    geometry: Any,
    carrier_profile: Any,
    topology_profile: QiTopologyProfile,
) -> Mapping[str, Any]:
    """Compute the complete Hamiltonian without advancing state."""
    geometry = _geometry_profile(geometry)
    topology_law = QiTopologicalRetentionLaw.bind(topology_profile, geometry)
    return _complete_hamiltonian(
        state,
        geometry=geometry,
        carrier_profile=carrier_profile,
        topology_law=topology_law,
        topology_profile=topology_profile,
        extra_conservative_law=None,
    )


def _work_interval(work: float, *, profile: QiConversionProfile) -> Mapping[str, float]:
    work_value = _f64(work, name="conversion work")
    uncertainty = max(profile.energy_uncertainty, profile.work_tolerance)
    delta = _profile_number(profile.payload.get("margins", {}).get("Delta_conversion"), name="Delta_conversion", default=1.0e-9)
    lower = work_value - uncertainty
    upper = work_value + uncertainty
    return MappingProxyType({
        "W_conversion": work_value,
        "U_conversion": uncertainty,
        "Delta_conversion": delta,
        "interval_lower": lower,
        "interval_upper": upper,
    })


def _work_rejection_witness(work: float, *, profile: QiConversionProfile, reason: str) -> Mapping[str, Any]:
    interval = dict(_work_interval(work, profile=profile))
    interval.update({
        "classification": "resolved-positive" if interval["interval_lower"] > interval["Delta_conversion"] else "source-ambiguous",
        "Q_conversion": None,
        "sink": False,
        "accepted": False,
        "rejection_reason": reason,
    })
    return MappingProxyType(interval)


def _classify_work(work: float, *, profile: QiConversionProfile) -> Mapping[str, Any]:
    common = dict(_work_interval(work, profile=profile))
    lower = common["interval_lower"]
    upper = common["interval_upper"]
    delta = common["Delta_conversion"]
    if lower > delta:
        raise ConversionError("conversion positive work is resolved and inadmissible")
    if upper < -delta:
        common.update({"classification": "resolved-dissipation", "Q_conversion": -common["W_conversion"], "sink": True})
        return MappingProxyType(common)
    if lower >= -delta and upper <= delta:
        common.update({"classification": "numerical-zero", "Q_conversion": 0.0, "sink": False})
        return MappingProxyType(common)
    raise ConversionError("conversion work is source-ambiguous under the registered uncertainty interval")


def _integrated_failure(state: QiFlowStateV3, reason: str, *, stage: str = "preflight", details: Mapping[str, Any] | None = None) -> QiIntegratedConversionStep:
    receipt: dict[str, Any] = {
        "schema": W5_INTEGRATED_RECEIPT_SCHEMA,
        "status": "REJECTED",
        "committable": False,
        "stage": stage,
        "failure_reason": reason,
        "predecessor_state_sha256": _state_hash(state),
        "candidate_state_sha256": None,
        "additional_state": False,
    }
    if details:
        receipt.update(_plain(details))
    receipt["self_sha256"] = _sha256(receipt, W5_INTEGRATED_RECEIPT_DOMAIN)
    return QiIntegratedConversionStep(state, None, False, MappingProxyType(receipt), reason)


def _work_rejection_details(
    holder: Mapping[str, Any],
    *,
    conversion_profile: QiConversionProfile,
    duration: float,
    duration_rational: Mapping[str, Any],
    source_provenance: Mapping[str, Any] | None,
    carrier_receipt: Any = None,
) -> Mapping[str, Any]:
    """Build evidence for a rejected map without exposing an attempted candidate."""
    work_witness = holder.get("work_classification")
    before = holder.get("energy_before")
    after = holder.get("energy_after")
    if not isinstance(work_witness, Mapping) or not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise ConversionError("rejected conversion has no complete energy/work witness")
    delta = {
        str(key): float(after[key]) - float(before[key])
        for key in before
        if key in after
    }
    work = float(work_witness["W_conversion"])
    center_delta = float(after["total"]) - float(before["total"])
    energy = {
        "hamiltonian_before": _plain(before),
        "hamiltonian_after": _plain(after),
        "center_hamiltonian_before": _plain(before),
        "center_hamiltonian_after": _plain(after),
        "pre": _plain(before),
        "post": _plain(after),
        "delta": delta,
        "W_conversion": work,
        "U_conversion": float(work_witness["U_conversion"]),
        "Delta_conversion": float(work_witness["Delta_conversion"]),
        "work_interval_lower": float(work_witness["interval_lower"]),
        "work_interval_upper": float(work_witness["interval_upper"]),
        "Q_conversion": None,
        "work_classification": work_witness["classification"],
        "sink_recorded": False,
        "conversion_work_closure_abs": abs(center_delta - work),
        "full_step_hamiltonian_delta": delta.get("total", center_delta),
        "complete_component_recomputation": True,
        "candidate_state_sha256": None,
    }
    center_witness = holder.get("center_map_witness")
    if not isinstance(center_witness, Mapping):
        raise ConversionError("rejected conversion has no center-map raw witness descriptor")
    details: dict[str, Any] = {
        "duration_s": duration,
        "duration_rational": _plain(duration_rational),
        "profile_sha256": conversion_profile.profile_sha256,
        "root_sha256": conversion_profile.root_sha256,
        "law_sha256": conversion_profile.law_sha256,
        "parent_identities": _plain(conversion_profile.parent_identities),
        "source_provenance": source_provenance,
        "energy": energy,
        "work_witness": _plain(work_witness),
        "work_rejection_witness": {
            "energy": energy,
            "work": _plain(work_witness),
            "attempted_center_map_witness": _plain(center_witness),
            "candidate_state_sha256": None,
        },
        "attempted_center_map_witness": _plain(center_witness),
        "center_calls": holder.get("center_calls"),
        "force_calls": holder.get("force_calls"),
    }
    if carrier_receipt is not None:
        details["carrier_split_receipt"] = _plain(carrier_receipt)
    return MappingProxyType(details)


def _validate_extra_law(law: Any | None) -> str | None:
    if law is None:
        return None
    law_id = getattr(law, "law_id", None)
    additional_force = getattr(law, "additional_force", None)
    energy = getattr(law, "energy", None)
    if not isinstance(law_id, str) or not law_id.strip() or not callable(additional_force) or not callable(energy):
        raise ConversionError("extra_conservative_law requires immutable law_id, additional_force, and energy")
    return law_id


def _sum_forces(
    left: tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]],
    right: tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]],
) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
    if len(left) != 2 or len(right) != 2 or len(left[0]) != len(right[0]) or len(left[1]) != len(right[1]):
        raise ConversionError("combined conservative force scale count mismatch")
    return (
        tuple((a + b).contiguous() for a, b in zip(left[0], right[0], strict=True)),
        tuple((a + b).contiguous() for a, b in zip(left[1], right[1], strict=True)),
    )


def _transition_w5_split(
    state: QiFlowStateV3,
    *,
    geometry_profile: Any,
    transport_profile: Any,
    carrier_profile: Any,
    topology_profile: QiTopologyProfile,
    conversion_profile: QiConversionProfile,
    numerical_certificate: Mapping[str, Any],
    duration_s: float | None = None,
    conversion_enabled: bool = True,
    epsilon_ema_enabled: bool = True,
    source: Mapping[str, Any] | None = None,
    extra_conservative_law: Any | None = None,
) -> QiIntegratedConversionStep:
    """Run the sole integrated W5 path: carrier split + center map + one EMA."""
    try:
        if source is not None and not isinstance(source, Mapping):
            raise ConversionError("source provenance must be a mapping")
        source_provenance = None if source is None else {
            "source": _plain(source),
            "source_sha256": _sha256(source, "cassi.qi-flow-w5-source-provenance.v1"),
        }
        if not isinstance(conversion_enabled, bool) or not isinstance(epsilon_ema_enabled, bool):
            raise ConversionError("conversion_enabled and epsilon_ema_enabled must be boolean")
        geometry = _geometry_profile(geometry_profile)
        _verify_profile(
            conversion_profile,
            geometry,
            transport_profile=transport_profile,
            carrier_profile=carrier_profile,
            topology_profile=topology_profile,
        )
        if not isinstance(topology_profile, QiTopologyProfile):
            raise ConversionError("topology_profile must be QiTopologyProfile")
        if not isinstance(numerical_certificate, Mapping):
            raise ConversionError("numerical_certificate is required")
        state.validate(geometry.base_profile)
        duration, duration_rational = _resolve_duration(conversion_profile, duration_s)
        extra_law_id = _validate_extra_law(extra_conservative_law)
        topology_law = QiTopologicalRetentionLaw.bind(topology_profile, geometry)
        topology_pre = topology_law.diagnostics(state)
        if topology_pre.get("status") != "VALID":
            raise ConversionError(f"topology preflight is not valid: {topology_pre.get('reason', 'unknown')}")
    except Exception as exc:
        return _integrated_failure(state, f"W5 profile/preflight rejection: {type(exc).__name__}: {exc}")

    holder: dict[str, Any] = {"center_calls": 0, "force_calls": 0, "map_rows": None, "process_rows": None, "branches": None, "work": None, "energy_before": None, "energy_after": None, "work_classification": None, "work_rejection": None, "center_map_witness": None}
    map_rate = conversion_profile.lambda_rate if conversion_enabled else 0.0

    def center_map(current: QiFlowStateV3, geometry_value: Any, carrier: Any, coordinates: CarrierCoordinates) -> CarrierCoordinates:
        del coordinates
        holder["center_calls"] += 1
        if holder["center_calls"] != 1:
            raise ConversionError("W5 center conversion map invoked more than once")
        before = _complete_hamiltonian(
            current,
            geometry=geometry_value,
            carrier_profile=carrier,
            topology_law=topology_law,
            topology_profile=topology_profile,
            extra_conservative_law=extra_conservative_law,
        )
        process_rows: list[Mapping[str, Any]] = []
        mapped, rows, branches = _frozen_q_map(
            current,
            geometry=geometry_value,
            profile=conversion_profile,
            carrier_profile=carrier,
            duration_s=duration,
            lambda_rate=map_rate,
            process_rows=process_rows,
        )
        holder["process_rows"] = tuple(process_rows)
        after = _complete_hamiltonian(
            mapped,
            geometry=geometry_value,
            carrier_profile=carrier,
            topology_law=topology_law,
            topology_profile=topology_profile,
            extra_conservative_law=extra_conservative_law,
        )
        input_descriptor = _raw_state_descriptor(current, geometry=geometry_value, role="center-map-input")
        output_descriptor = _raw_state_descriptor(mapped, geometry=geometry_value, role="center-map-output")
        center_map_witness = {
            "input_state_sha256": input_descriptor["raw_sha256"],
            "output_state_sha256": output_descriptor["raw_sha256"],
            "raw_domain": W5_RAW_DOMAIN,
            "layout": input_descriptor["state_layout"],
            "layout_id": input_descriptor["layout_id"],
            "shape": input_descriptor["shape"],
            "dtype": input_descriptor["dtype"],
            "input": input_descriptor,
            "output": output_descriptor,
            "duration_s": duration,
            "duration_rational": _plain(duration_rational),
            "lambda_rate": map_rate,
            "tau": 0.0,
            "candidate_state_sha256": None,
        }
        work = float(after["total"]) - float(before["total"])
        try:
            classification = _classify_work(work, profile=conversion_profile)
            rejection = None
        except ConversionError as exc:
            rejection = str(exc)
            classification = _work_rejection_witness(work, profile=conversion_profile, reason=rejection)
            holder.update({"map_rows": rows, "branches": branches, "work": work, "energy_before": before, "energy_after": after, "work_classification": classification, "work_rejection": rejection, "center_map_witness": center_map_witness})
            raise _WorkRejected(rejection) from exc
        holder.update({"map_rows": rows, "branches": branches, "work": work, "energy_before": before, "energy_after": after, "work_classification": classification, "work_rejection": rejection, "center_map_witness": center_map_witness})
        return carrier_coordinates(mapped, geometry=geometry_value, profile=carrier)

    def combined_force(current: QiFlowStateV3, geometry_value: Any, carrier: Any, coordinates: CarrierCoordinates) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
        holder["force_calls"] += 1
        topology_force = topology_law.additional_force(current, geometry_value, carrier, coordinates)
        if extra_conservative_law is None:
            return topology_force
        extra_force = extra_conservative_law.additional_force(current, geometry_value, carrier, coordinates)
        if not isinstance(extra_force, tuple) or len(extra_force) != 2:
            raise ConversionError("extra conservative force must return (D_forces,C_forces)")
        return _sum_forces(topology_force, extra_force)

    try:
        carrier_step = _transition_v4_carrier_split(
            state,
            geometry_profile=geometry,
            transport_profile=transport_profile,
            carrier_profile=carrier_profile,
            numerical_certificate=numerical_certificate,
            duration_s=duration,
            potential_enabled=True,
            additional_force=combined_force,
            center_map=center_map,
        )
    except _WorkRejected as exc:
        try:
            details = _work_rejection_details(
                holder,
                conversion_profile=conversion_profile,
                duration=duration,
                duration_rational=duration_rational,
                source_provenance=source_provenance,
            )
        except Exception as witness_exc:
            return _integrated_failure(state, f"W5 conversion work rejected: {exc}; witness failed: {type(witness_exc).__name__}: {witness_exc}", stage="work-ledger")
        return _integrated_failure(state, f"W5 conversion work rejected: {exc}", stage="work-ledger", details=details)
    except Exception as exc:
        if holder["work_rejection"] is not None:
            try:
                details = _work_rejection_details(
                    holder,
                    conversion_profile=conversion_profile,
                    duration=duration,
                    duration_rational=duration_rational,
                    source_provenance=source_provenance,
                )
            except Exception as witness_exc:
                return _integrated_failure(state, f"W5 conversion work rejected: {holder['work_rejection']}; witness failed: {type(witness_exc).__name__}: {witness_exc}", stage="work-ledger")
            return _integrated_failure(state, f"W5 conversion work rejected: {holder['work_rejection']}", stage="work-ledger", details=details)
        return _integrated_failure(state, f"W5 carrier split failed closed: {type(exc).__name__}: {exc}", stage="carrier-split")
    if holder["work_rejection"] is not None:
        try:
            details = _work_rejection_details(
                holder,
                conversion_profile=conversion_profile,
                duration=duration,
                duration_rational=duration_rational,
                source_provenance=source_provenance,
                carrier_receipt=getattr(carrier_step, "receipt", None),
            )
        except Exception as witness_exc:
            return _integrated_failure(state, f"W5 conversion work rejected: {holder['work_rejection']}; witness failed: {type(witness_exc).__name__}: {witness_exc}", stage="work-ledger")
        return _integrated_failure(state, f"W5 conversion work rejected: {holder['work_rejection']}", stage="work-ledger", details=details)
    if not getattr(carrier_step, "committable", False) or getattr(carrier_step, "candidate", None) is None:
        return _integrated_failure(
            state,
            f"W5 carrier split rejected: {getattr(carrier_step, 'failure_reason', 'unknown')}",
            stage="carrier-split",
            details={"carrier_split_receipt": getattr(carrier_step, "receipt", None)},
        )
    if holder["center_calls"] != 1 or holder["force_calls"] != 2 or holder["map_rows"] is None or holder["work_classification"] is None:
        return _integrated_failure(state, "W5 center/force hooks did not execute exactly once/twice", stage="center-map", details={"carrier_split_receipt": getattr(carrier_step, "receipt", None), "center_calls": holder["center_calls"], "force_calls": holder["force_calls"]})
    candidate_before_ema = carrier_step.candidate
    try:
        topology_post = topology_law.diagnostics(candidate_before_ema)
        if topology_post.get("status") != "VALID":
            raise ConversionError(f"topology postflight is not valid: {topology_post.get('reason', 'unknown')}")
        candidate, tau, ema_rows = _update_ema_once(
            candidate_before_ema,
            geometry=geometry,
            profile=conversion_profile,
            carrier_profile=carrier_profile,
            duration_s=duration,
            enabled=epsilon_ema_enabled,
        )
        candidate.validate(geometry.base_profile)
        step_before = _complete_hamiltonian(
            state,
            geometry=geometry,
            carrier_profile=carrier_profile,
            topology_law=topology_law,
            topology_profile=topology_profile,
            extra_conservative_law=extra_conservative_law,
        )
        step_after = _complete_hamiltonian(
            candidate,
            geometry=geometry,
            carrier_profile=carrier_profile,
            topology_law=topology_law,
            topology_profile=topology_profile,
            extra_conservative_law=extra_conservative_law,
        )
        intermediates = _detached_intermediates(carrier_step, state, candidate)
    except Exception as exc:
        return _integrated_failure(state, f"W5 postflight/EMA rejected: {type(exc).__name__}: {exc}", stage="postflight", details={"carrier_split_receipt": getattr(carrier_step, "receipt", None)})

    carrier_receipt = getattr(carrier_step, "receipt", MappingProxyType({}))
    carrier_schedule = carrier_receipt.get("stage_schedule") if isinstance(carrier_receipt, Mapping) else None
    if not isinstance(carrier_schedule, Mapping):
        return _integrated_failure(state, "W5 carrier receipt omitted the real stage schedule", stage="receipt", details={"carrier_split_receipt": _plain(carrier_receipt), "source_provenance": source_provenance})
    schedule_rows = carrier_schedule.get("stages")
    if not isinstance(schedule_rows, (tuple, list)) or len(schedule_rows) != 7:
        return _integrated_failure(state, "W5 carrier receipt has an invalid seven-stage schedule", stage="receipt", details={"carrier_split_receipt": _plain(carrier_receipt), "source_provenance": source_provenance})
    carrier_names = [str(row.get("name", "")) for row in schedule_rows if isinstance(row, Mapping)]
    if len(carrier_names) != 7 or any(not name for name in carrier_names):
        return _integrated_failure(state, "W5 carrier receipt has malformed stage names", stage="receipt", details={"carrier_split_receipt": _plain(carrier_receipt), "source_provenance": source_provenance})
    if carrier_names[3] != "centered_conversion_placeholder" or carrier_receipt.get("center_map") != "profile-bound-center-map.v1":
        return _integrated_failure(state, "W5 carrier receipt does not prove the centered map placement", stage="receipt", details={"carrier_split_receipt": _plain(carrier_receipt), "source_provenance": source_provenance})
    carrier_names[3] = "w5_frozen_q_position_conversion"
    stage_order = tuple(carrier_names + ["w5_single_post_step_epsilon2_ema"])
    center_pre = holder["energy_before"]
    center_post = holder["energy_after"]
    work_classification = holder["work_classification"]
    density_rows = tuple(holder["map_rows"])
    process_rows = tuple(holder["process_rows"] or ())
    density_closure = max((float(row.get("density_closure_abs", 0.0)) for row in density_rows), default=0.0)
    try:
        process_clock = _process_clock_receipt(
            process_rows,
            density_rows,
            duration=duration,
            duration_rational=duration_rational,
            lambda_rate=map_rate,
            epsilon_guard=conversion_profile.epsilon_prog_min,
        )
    except Exception as exc:
        return _integrated_failure(state, f"W5 process-clock receipt failed closed: {type(exc).__name__}: {exc}", stage="receipt")
    full_work_closure = float(center_post["total"]) - float(center_pre["total"]) - float(work_classification["W_conversion"])
    receipt: dict[str, Any] = {
        "schema": W5_INTEGRATED_RECEIPT_SCHEMA,
        "status": "PASS",
        "committable": True,
        "process_clock": _plain(process_clock),
        "transition_kind": "integrated-w5-centered-frozen-q",
        "stage_order": stage_order,
        "duration_s": duration,
        "duration_rational": _plain(duration_rational),
        "predecessor_state_sha256": _state_hash(state),
        "candidate_state_sha256": _state_hash(candidate),
        "profile_sha256": conversion_profile.profile_sha256,
        "root_sha256": conversion_profile.root_sha256,
        "law_sha256": conversion_profile.law_sha256,
        "parent_identities": _plain(conversion_profile.parent_identities),
        "source_provenance": source_provenance,
        "carrier_split_receipt": _plain(carrier_receipt),
        "topology": {
            "law_id": topology_profile.law_id,
            "profile_sha256": topology_profile.profile_sha256,
            "pre_diagnostics": _plain(topology_pre),
            "post_diagnostics": _plain(topology_post),
            "force_evaluations": holder["force_calls"],
            "force_in_both_conservative_half_kicks": holder["force_calls"] == 2,
        },
        "conversion": {
            "law_id": W5_LAW_DOMAIN,
            "enabled": conversion_enabled,
            "lambda_rate": map_rate,
            "q_evaluations": 1,
            "conversion_maps": 1,
            "center_map_invocations": holder["center_calls"],
            "phase_branches": _plain(holder["branches"]),
            "rows": _plain(density_rows),
            "density_closure_abs": density_closure,
            "velocities_unchanged_by_map": True,
        },
        "ema": {
            "enabled": epsilon_ema_enabled,
            "invocations": 1,
            "updates": 1 if epsilon_ema_enabled else 0,
            "tau": tau,
            "rows": _plain(ema_rows),
            "post_step_only": True,
            "joint_off": not conversion_enabled and not epsilon_ema_enabled,
            "joint_off_identity": (
                {
                    "baseline": "w4r-carrier-split-candidate",
                    "baseline_state_sha256": _state_hash(candidate_before_ema),
                    "candidate_state_sha256": _state_hash(candidate),
                    "equal": _state_hash(candidate_before_ema) == _state_hash(candidate),
                }
                if not conversion_enabled and not epsilon_ema_enabled
                else None
            ),
        },
        "energy": {
            "hamiltonian_before": _plain(step_before),
            "hamiltonian_after": _plain(step_after),
            "center_hamiltonian_before": _plain(center_pre),
            "center_hamiltonian_after": _plain(center_post),
            "W_conversion": float(work_classification["W_conversion"]),
            "U_conversion": float(work_classification["U_conversion"]),
            "Delta_conversion": float(work_classification["Delta_conversion"]),
            "work_interval_lower": float(work_classification["interval_lower"]),
            "work_interval_upper": float(work_classification["interval_upper"]),
            "Q_conversion": float(work_classification["Q_conversion"]),
            "work_classification": work_classification["classification"],
            "sink_recorded": bool(work_classification["sink"]),
            "conversion_work_closure_abs": abs(full_work_closure),
            "full_step_hamiltonian_delta": float(step_after["total"]) - float(step_before["total"]),
            "extra_conservative_law_id": extra_law_id,
            "duplicate_composition_or_topology_accounting": False,
        },
        "guards": {
            "density_nonnegative": True,
            "density_conservation_abs": density_closure,
            "work_closed": math.isfinite(full_work_closure) and abs(full_work_closure) <= conversion_profile.work_tolerance,
            "no_projection": True,
            "no_clipping": True,
            "no_repair": True,
            "no_extra_persistent_state": True,
        },
        "intermediate_stage_names": list(_INTERMEDIATE_KEYS),
        "intermediate_state_sha256": {key: _state_hash(value) for key, value in intermediates.items()},
        "extra_conservative_law_id": extra_law_id,
        "additional_state": False,
    }
    if not receipt["guards"]["work_closed"]:
        return _integrated_failure(state, "W5 conversion work closure exceeded registered uncertainty", stage="ledger", details=receipt)
    try:
        validate_w5_schedule_receipt(receipt)
    except ConversionError as exc:
        return _integrated_failure(state, f"W5 schedule receipt rejected: {exc}", stage="receipt", details=receipt)
    receipt["self_sha256"] = _sha256(receipt, W5_INTEGRATED_RECEIPT_DOMAIN)
    return QiIntegratedConversionStep(state, candidate, True, MappingProxyType(receipt), None, intermediates)


def _clock_summary_for_receipt(value: Any, *, name: str, allow_none: bool = False) -> dict[str, float] | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, Mapping) or set(value) != {"min", "max", "mean"}:
        raise ConversionError(f"{name} must be a min/max/mean mapping")
    result: dict[str, float] = {}
    for key in ("min", "max", "mean"):
        if isinstance(value[key], bool):
            raise ConversionError(f"{name}.{key} must be a finite scalar")
        result[key] = _f64(value[key], name=f"{name}.{key}")
    if result["min"] > result["max"] or not result["min"] <= result["mean"] <= result["max"]:
        raise ConversionError(f"{name} aggregate bounds are inconsistent")
    return result


def _clock_close(left: float, right: float, *, name: str) -> None:
    if not math.isclose(left, right, rel_tol=2.0e-12, abs_tol=2.0e-12):
        raise ConversionError(f"{name} disagrees with its process-clock witness")


def _validate_process_clock_receipt(
    receipt: Mapping[str, Any],
    conversion_row: Mapping[str, Any],
) -> None:
    process = receipt.get("process_clock")
    if not isinstance(process, Mapping):
        raise ConversionError("W5 receipt is missing process_clock")
    if process.get("schema") != "cassi.qi-flow-process-clock.v1":
        raise ConversionError("W5 process_clock schema is invalid")
    duration = _f64(receipt.get("duration_s"), name="duration_s", positive=True)
    if process.get("coordinate_duration_rational") != receipt.get("duration_rational"):
        raise ConversionError("W5 process_clock duration rational disagrees with receipt")
    _clock_close(_f64(process.get("coordinate_duration_s"), name="process_clock.coordinate_duration_s"), duration, name="process_clock.coordinate_duration_s")
    if process.get("coordinate_time_ground_truth") is not True:
        raise ConversionError("W5 process_clock must preserve coordinate time as ground truth")
    if process.get("normalization") != "d tau_F=(1-Q) dt; Delta tau_F=(1-Q) h; Delta chi_F=lambda*Delta tau_F":
        raise ConversionError("W5 process_clock normalization is invalid")
    provenance = process.get("normalization_provenance")
    if not isinstance(provenance, Mapping) or provenance.get("law_id") != W5_LAW_DOMAIN or provenance.get("coordinate_time") != "dt" or provenance.get("source") != "single frozen-Q conversion map":
        raise ConversionError("W5 process_clock normalization provenance is invalid")
    epsilon_guard = _f64(provenance.get("epsilon_guard"), name="process_clock epsilon_guard", nonnegative=True)
    del epsilon_guard
    rate = _f64(conversion_row.get("lambda_rate"), name="conversion.lambda_rate", nonnegative=True)
    _clock_close(_f64(process.get("lambda_rate"), name="process_clock.lambda_rate", nonnegative=True), rate, name="process_clock.lambda_rate")
    rate_bounds = process.get("lambda_rate_bounds")
    if not isinstance(rate_bounds, Mapping):
        raise ConversionError("W5 process_clock lambda-rate bounds are missing")
    _clock_close(_f64(rate_bounds.get("min"), name="process_clock.lambda_rate_bounds.min", nonnegative=True), rate, name="process_clock.lambda_rate_bounds.min")
    _clock_close(_f64(rate_bounds.get("max"), name="process_clock.lambda_rate_bounds.max", nonnegative=True), rate, name="process_clock.lambda_rate_bounds.max")
    conversion_rows = conversion_row.get("rows")
    rows = process.get("rows")
    if not isinstance(conversion_rows, (tuple, list)) or not isinstance(rows, (tuple, list)) or not conversion_rows or len(rows) != len(conversion_rows):
        raise ConversionError("W5 process_clock rows do not cover conversion rows exactly")
    if process.get("conversion_row_count") != len(conversion_rows) or process.get("evaluation_count") != len(rows) or process.get("one_process_age_evaluation_per_conversion_row") is not True:
        raise ConversionError("W5 process_clock evaluation count is not one per conversion row")
    row_keys = {
        "scale", "sample_count", "q", "lambda_rate", "delta_tau_F", "delta_chi_F",
        "tau_F_defined", "chi_F_defined", "tau_F_expected", "chi_F_expected",
        "tau_F_endpoint", "chi_F_endpoint", "alpha_expected", "alpha_endpoint",
        "alpha_closure_abs", "tau_F_closure_abs", "chi_F_closure_abs",
        "endpoint_observable", "tau_F_endpoint_observable", "chi_F_endpoint_observable",
        "epsilon_pre_nonzero_count", "epsilon_post_nonzero_count",
        "endpoint_resolved_count", "endpoint_unresolved_count", "endpoint_degeneracy",
        "degeneracy_reasons",
    }
    parsed_rows: list[dict[str, Any]] = []
    for index, (row, conversion_scale) in enumerate(zip(rows, conversion_rows, strict=True)):
        if not isinstance(row, Mapping) or set(row) != row_keys or not isinstance(conversion_scale, Mapping):
            raise ConversionError(f"W5 process_clock row {index} is malformed")
        if row.get("scale") != conversion_scale.get("scale"):
            raise ConversionError(f"W5 process_clock row {index} scale mismatch")
        sample_count = row.get("sample_count")
        if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count <= 0:
            raise ConversionError(f"W5 process_clock row {index} sample count is invalid")
        q = _clock_summary_for_receipt(row.get("q"), name=f"process_clock.rows[{index}].q")
        assert q is not None
        _clock_close(q["min"], _f64(conversion_scale.get("q_min"), name=f"conversion.rows[{index}].q_min"), name=f"process_clock.rows[{index}].q.min")
        _clock_close(q["max"], _f64(conversion_scale.get("q_max"), name=f"conversion.rows[{index}].q_max"), name=f"process_clock.rows[{index}].q.max")
        if q["min"] < 0.0 or q["max"] >= 1.0:
            raise ConversionError(f"W5 process_clock row {index} Q bounds are invalid")
        row_rate = _f64(row.get("lambda_rate"), name=f"process_clock.rows[{index}].lambda_rate", nonnegative=True)
        _clock_close(row_rate, rate, name=f"process_clock.rows[{index}].lambda_rate")
        tau = _clock_summary_for_receipt(row.get("delta_tau_F"), name=f"process_clock.rows[{index}].delta_tau_F")
        chi = _clock_summary_for_receipt(row.get("delta_chi_F"), name=f"process_clock.rows[{index}].delta_chi_F")
        tau_expected = _clock_summary_for_receipt(row.get("tau_F_expected"), name=f"process_clock.rows[{index}].tau_F_expected")
        chi_expected = _clock_summary_for_receipt(row.get("chi_F_expected"), name=f"process_clock.rows[{index}].chi_F_expected")
        if tau is None or chi is None or tau_expected is None or chi_expected is None or row.get("tau_F_defined") is not True:
            raise ConversionError(f"W5 process_clock row {index} omits defined conversion age or exposure")
        expected_tau_min = (1.0 - q["max"]) * duration
        expected_tau_max = (1.0 - q["min"]) * duration
        _clock_close(tau["min"], expected_tau_min, name=f"process_clock.rows[{index}].delta_tau_F.min")
        _clock_close(tau["max"], expected_tau_max, name=f"process_clock.rows[{index}].delta_tau_F.max")
        _clock_close(tau["mean"], (1.0 - q["mean"]) * duration, name=f"process_clock.rows[{index}].delta_tau_F.mean")
        for key in ("min", "max", "mean"):
            _clock_close(tau[key], tau_expected[key], name=f"process_clock.rows[{index}].tau_F_expected.{key}")
        if row.get("chi_F_defined") is not True:
            raise ConversionError(f"W5 process_clock row {index} conversion exposure is inconsistent")
        for key in ("min", "max", "mean"):
            _clock_close(chi[key], chi_expected[key], name=f"process_clock.rows[{index}].chi_F_expected.{key}")
            _clock_close(chi[key], tau[key] * rate, name=f"process_clock.rows[{index}].delta_chi_F.{key}")
        alpha = _clock_summary_for_receipt(row.get("alpha_expected"), name=f"process_clock.rows[{index}].alpha_expected")
        assert alpha is not None
        _clock_close(alpha["min"], _f64(conversion_scale.get("alpha_min"), name=f"conversion.rows[{index}].alpha_min"), name=f"process_clock.rows[{index}].alpha.min")
        _clock_close(alpha["max"], _f64(conversion_scale.get("alpha_max"), name=f"conversion.rows[{index}].alpha_max"), name=f"process_clock.rows[{index}].alpha.max")
        tau_endpoint = _clock_summary_for_receipt(row.get("tau_F_endpoint"), name=f"process_clock.rows[{index}].tau_F_endpoint", allow_none=True)
        chi_endpoint = _clock_summary_for_receipt(row.get("chi_F_endpoint"), name=f"process_clock.rows[{index}].chi_F_endpoint", allow_none=True)
        alpha_endpoint = _clock_summary_for_receipt(row.get("alpha_endpoint"), name=f"process_clock.rows[{index}].alpha_endpoint", allow_none=True)
        for key in ("alpha_closure_abs", "tau_F_closure_abs", "chi_F_closure_abs"):
            value = row.get(key)
            if value is not None:
                _f64(value, name=f"process_clock.rows[{index}].{key}", nonnegative=True)
        counts = []
        for key in ("epsilon_pre_nonzero_count", "epsilon_post_nonzero_count", "endpoint_resolved_count", "endpoint_unresolved_count"):
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ConversionError(f"W5 process_clock row {index} {key} is invalid")
            counts.append(value)
        resolved, unresolved = counts[-2:]
        if (tau_endpoint is not None) != (rate > 0.0 and resolved > 0):
            raise ConversionError(f"W5 process_clock row {index} tau_F endpoint presence is inconsistent")
        if (chi_endpoint is not None) != (resolved > 0) or (alpha_endpoint is not None) != (resolved > 0):
            raise ConversionError(f"W5 process_clock row {index} endpoint witness presence is inconsistent")
        closure_presence = (
            row.get("alpha_closure_abs") is not None,
            row.get("tau_F_closure_abs") is not None,
            row.get("chi_F_closure_abs") is not None,
        )
        if closure_presence != (True, rate > 0.0 and resolved > 0, resolved > 0):
            raise ConversionError(f"W5 process_clock row {index} endpoint closure presence is inconsistent")
        if resolved + unresolved != sample_count or row.get("endpoint_observable") is not (resolved > 0) or row.get("endpoint_degeneracy") is not (unresolved > 0):
            raise ConversionError(f"W5 process_clock row {index} endpoint counts are inconsistent")
        if row.get("tau_F_endpoint_observable") is not (rate > 0.0 and resolved > 0) or row.get("chi_F_endpoint_observable") is not (resolved > 0):
            raise ConversionError(f"W5 process_clock row {index} endpoint observability is inconsistent")
        if row.get("tau_F_endpoint") is not None and rate == 0.0:
            raise ConversionError(f"W5 process_clock row {index} infers tau_F at lambda=0")
        reasons = row.get("degeneracy_reasons")
        if not isinstance(reasons, list) or any(not isinstance(reason, str) or not reason for reason in reasons):
            raise ConversionError(f"W5 process_clock row {index} degeneracy reasons are malformed")
        if rate == 0.0 and not any(reason.startswith("lambda=0:") for reason in reasons):
            raise ConversionError(f"W5 process_clock row {index} omits lambda=0 degeneracy")
        if unresolved and not any("epsilon" in reason for reason in reasons):
            raise ConversionError(f"W5 process_clock row {index} omits epsilon degeneracy")
        parsed_rows.append({
            "sample_count": sample_count,
            "q": q,
            "delta_tau_F": tau,
            "delta_chi_F": chi,
            "alpha": alpha,
            "row": row,
        })

    def aggregate(field: str, *, allow_none: bool = False) -> dict[str, float] | None:
        summaries = [item[field] for item in parsed_rows]
        if allow_none and all(summary is None for summary in summaries):
            return None
        if any(summary is None for summary in summaries):
            raise ConversionError(f"W5 process_clock aggregate {field} is incomplete")
        typed = [summary for summary in summaries if summary is not None]
        total = sum(item["sample_count"] for item in parsed_rows)
        return {
            "min": min(summary["min"] for summary in typed),
            "max": max(summary["max"] for summary in typed),
            "mean": math.fsum(summary["mean"] * item["sample_count"] for summary, item in zip(typed, parsed_rows, strict=True)) / total,
        }

    q_bounds = _clock_summary_for_receipt(process.get("q_bounds"), name="process_clock.q_bounds")
    delta_tau = _clock_summary_for_receipt(process.get("delta_tau_F"), name="process_clock.delta_tau_F")
    delta_chi = _clock_summary_for_receipt(process.get("delta_chi_F"), name="process_clock.delta_chi_F")
    for actual, expected, name in (
        (q_bounds, aggregate("q"), "process_clock.q_bounds"),
        (delta_tau, aggregate("delta_tau_F"), "process_clock.delta_tau_F"),
        (delta_chi, aggregate("delta_chi_F"), "process_clock.delta_chi_F"),
    ):
        if (actual is None) != (expected is None):
            raise ConversionError(f"{name} aggregate presence is inconsistent")
        if actual is not None and expected is not None:
            for key in ("min", "max", "mean"):
                _clock_close(actual[key], expected[key], name=f"{name}.{key}")
    unresolved_total = sum(item["row"]["endpoint_unresolved_count"] for item in parsed_rows)
    resolved_total = sum(item["row"]["endpoint_resolved_count"] for item in parsed_rows)
    if process.get("resolved_endpoint_count") != resolved_total or process.get("unresolved_endpoint_count") != unresolved_total:
        raise ConversionError("W5 process_clock endpoint counts are inconsistent")
    if process.get("lambda_zero") is not (rate == 0.0) or process.get("tau_F_defined") is not True or process.get("chi_F_defined") is not True:
        raise ConversionError("W5 process_clock rate observability flags are inconsistent")
    if process.get("endpoint_observable") is not (resolved_total > 0) or process.get("endpoint_degenerate") is not (unresolved_total > 0) or process.get("epsilon_near_zero") is not (unresolved_total > 0):
        raise ConversionError("W5 process_clock endpoint flags are inconsistent")
    observability = process.get("observability")
    expected_observability = {
        "delta_tau_F": True,
        "delta_chi_F": True,
        "endpoint_alpha": resolved_total > 0,
        "endpoint_tau_F": rate > 0.0 and resolved_total > 0,
        "endpoint_chi_F": resolved_total > 0,
    }
    if not isinstance(observability, Mapping) or observability != expected_observability:
        raise ConversionError("W5 process_clock observability flags are inconsistent")
    if not isinstance(process.get("degeneracy_reasons"), list):
        raise ConversionError("W5 process_clock degeneracy reasons are malformed")
    if rate == 0.0 and not any(str(reason).startswith("lambda=0:") for reason in process["degeneracy_reasons"]):
        raise ConversionError("W5 process_clock omits lambda=0 degeneracy")
    if unresolved_total and not any("epsilon" in str(reason) for reason in process["degeneracy_reasons"]):
        raise ConversionError("W5 process_clock omits epsilon degeneracy")
    closure_abs = _f64(process.get("closure_abs"), name="process_clock.closure_abs", nonnegative=True)
    if process.get("closure_finite") is not True or not math.isfinite(closure_abs):
        raise ConversionError("W5 process_clock closure is not finite")
    closure_values = [
        _f64(item["row"][key], name=f"process_clock.rows[{index}].{key}", nonnegative=True)
        for index, item in enumerate(parsed_rows)
        for key in ("alpha_closure_abs", "tau_F_closure_abs", "chi_F_closure_abs")
        if item["row"].get(key) is not None
    ]
    if not closure_values or not math.isclose(closure_abs, max(closure_values), rel_tol=2.0e-12, abs_tol=2.0e-12):
        raise ConversionError("W5 process_clock closure aggregate is inconsistent")


def validate_w5_schedule_receipt(receipt: Mapping[str, Any]) -> bool:
    """Validate W5 placement/counters without committing any field state."""
    if not isinstance(receipt, Mapping):
        raise ConversionError("W5 schedule receipt must be a mapping")
    carrier = receipt.get("carrier_split_receipt")
    if not isinstance(carrier, Mapping):
        raise ConversionError("W5 receipt is missing carrier_split_receipt")
    schedule = carrier.get("stage_schedule")
    if not isinstance(schedule, Mapping):
        raise ConversionError("W5 receipt is missing the carrier stage schedule")
    stages = schedule.get("stages")
    if not isinstance(stages, (tuple, list)) or len(stages) != 7:
        raise ConversionError("W5 carrier schedule must contain exactly seven stages")
    names = [row.get("name") for row in stages if isinstance(row, Mapping)]
    if len(names) != 7 or any(not isinstance(name, str) or not name for name in names):
        raise ConversionError("W5 carrier schedule has malformed stage names")
    if names.count("centered_conversion_placeholder") != 1 or names[3] != "centered_conversion_placeholder":
        raise ConversionError("W5 carrier schedule must contain one centered conversion marker")
    if carrier.get("center_map") != "profile-bound-center-map.v1":
        raise ConversionError("W5 carrier schedule is not center-map bound")
    stage_order = receipt.get("stage_order")
    if not isinstance(stage_order, (tuple, list)) or stage_order.count("w5_frozen_q_position_conversion") != 1 or stage_order.count("w5_single_post_step_epsilon2_ema") != 1:
        raise ConversionError("W5 stage order has duplicate or missing conversion/EMA stage")
    conversion_row = receipt.get("conversion")
    topology_row = receipt.get("topology")
    ema_row = receipt.get("ema")
    if not isinstance(conversion_row, Mapping) or conversion_row.get("q_evaluations") != 1 or conversion_row.get("conversion_maps") != 1 or conversion_row.get("center_map_invocations") != 1:
        raise ConversionError("W5 conversion counters are not exactly one")
    if not isinstance(topology_row, Mapping) or topology_row.get("force_evaluations") != 2:
        raise ConversionError("W5 topology/combined-force counter is not exactly two")
    if not isinstance(ema_row, Mapping) or ema_row.get("invocations") != 1 or ema_row.get("updates") != (1 if ema_row.get("enabled") else 0):
        raise ConversionError("W5 EMA counters do not match its toggle")
    if not isinstance(conversion_row, Mapping):
        raise ConversionError("W5 conversion row is missing")
    _validate_process_clock_receipt(receipt, conversion_row)
    return True


def transition_w5_integrated(
    state: QiFlowStateV3,
    *,
    geometry_profile: Any,
    transport_profile: Any,
    carrier_profile: Any,
    topology_profile: QiTopologyProfile,
    conversion_profile: QiConversionProfile,
    numerical_certificate: Mapping[str, Any],
    duration_s: float | None = None,
    conversion_enabled: bool = True,
    epsilon_ema_enabled: bool = True,
    source: Mapping[str, Any] | None = None,
    extra_conservative_law: Any | None = None,
) -> QiIntegratedConversionStep:
    """Public W5 transition; all timed evolution routes through one split."""
    return _transition_w5_split(
        state,
        geometry_profile=geometry_profile,
        transport_profile=transport_profile,
        carrier_profile=carrier_profile,
        topology_profile=topology_profile,
        conversion_profile=conversion_profile,
        numerical_certificate=numerical_certificate,
        duration_s=duration_s,
        conversion_enabled=conversion_enabled,
        epsilon_ema_enabled=epsilon_ema_enabled,
        source=source,
        extra_conservative_law=extra_conservative_law,
    )


__all__ = [
    "W5_CONVERSION_PROFILE_SCHEMA",
    "W5_CONVERSION_ROOT_SCHEMA",
    "W5_CONVERSION_RECEIPT_SCHEMA",
    "W5_INTEGRATED_RECEIPT_SCHEMA",
    "W5_LAW_DOMAIN",
    "W5_RAW_DOMAIN",
    "ConversionError",
    "QiConversionProfile",
    "QiConversionStep",
    "QiIntegratedConversionStep",
    "load_w5_conversion_profile",
    "derive_epsilon_tau",
    "transition_w5_integrated",
    "validate_w5_schedule_receipt",
]
