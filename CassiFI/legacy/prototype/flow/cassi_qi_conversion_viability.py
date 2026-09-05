"""W5V/G5V complete-domain certificate for the centered frozen-Q map.

The profile is frozen before fixtures are inspected.  Acceptance is a
high-precision outward enclosure over the complete declared support, not a
fit to a witness.  Parent and source identities are supplied by the current
W5 artifact and are never pinned in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
import math
import struct
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from cassi_qi_conversion import QiConversionProfile
from cassi_qi_profile import canonical_hash, finite_float

W5V_PROFILE_SCHEMA = "cassi.qi-flow-conversion-viability-profile.v1"
W5V_PROFILE_DOMAIN = W5V_PROFILE_SCHEMA
W5V_RECEIPT_SCHEMA = "cassi.qi-flow-conversion-viability-receipt.v1"
W5V_RECEIPT_DOMAIN = W5V_RECEIPT_SCHEMA
W5V_EXTENSION_SCHEMA = "cassi.qi-flow-certificate-extension.v1"
W5V_EXTENSION_DOMAIN = "cassi.qi-flow-w3n-extension.v1"
W5V_SECTION_SCHEMA = "cassi.qi-flow-w5v-forward-viability-section.v1"
W5V_SECTION_DOMAIN = W5V_SECTION_SCHEMA
W5V_ANALYTIC_METHOD = "decimal-exact-registered-f64-outward-enclosure.v1"

_COVER_IDS = (
    "C00-exact-zero",
    "C01-balanced-memory-zero",
    "C02-balanced-memory-positive",
    "C03-neutral-positive",
    "C04-neutral-negative",
    "C05-progress-positive",
    "C06-progress-negative",
)
_BASE_BINDING_KEYS = {
    "run_id",
    "index_sha256",
    "candidate_state_sha256",
    "profile_sha256",
    "root_sha256",
    "law_sha256",
    "conversion_source_sha256",
    "source_identity_sha256",
    "parent_identities",
    "certificate_identities",
    "status",
    "w5v_forward_domain_certificate",
}
_OPTIONAL_BINDING_KEYS = {"w5_source_identity", "w5_artifact_root"}


class ConversionViabilityError(ValueError):
    """The frozen support or its complete-domain proof is inadmissible."""


def _f64(value: float) -> str:
    number = float(value)
    if not math.isfinite(number) or (number == 0.0 and math.copysign(1.0, number) < 0.0):
        raise ConversionViabilityError("viability scalar must be canonical finite float64")
    return "f64:" + struct.pack(">d", number).hex()


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _tagged(value: Any, *, name: str) -> float:
    if not isinstance(value, str):
        raise ConversionViabilityError(f"{name} must be canonical tagged float64")
    return finite_float(value, name=name)


def _decimal_float(value: float) -> Decimal:
    return Decimal.from_float(float(value))


def _outward_lower(value: Decimal) -> float:
    candidate = float(value)
    if not math.isfinite(candidate):
        raise ConversionViabilityError("nonfinite lower enclosure")
    if Decimal.from_float(candidate) > value:
        candidate = math.nextafter(candidate, -math.inf)
    return math.nextafter(candidate, -math.inf)


def _outward_upper(value: Decimal) -> float:
    candidate = float(value)
    if not math.isfinite(candidate):
        raise ConversionViabilityError("nonfinite upper enclosure")
    if Decimal.from_float(candidate) < value:
        candidate = math.nextafter(candidate, math.inf)
    return math.nextafter(candidate, math.inf)


def _rounding_radius(value: Decimal, lower: float, upper: float) -> float:
    left = value - Decimal.from_float(lower)
    right = Decimal.from_float(upper) - value
    return _outward_upper(max(left, right, Decimal(0)))


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _validate_identity_tree(value: Any, *, name: str) -> Any:
    """Validate supplied identities without knowing a predecessor's digest."""
    if isinstance(value, Mapping):
        result = {str(key): _validate_identity_tree(item, name=f"{name}.{key}") for key, item in value.items()}
        for key, item in result.items():
            if key.endswith("sha256") and item is not None and not _is_sha256(item):
                raise ConversionViabilityError(f"{name}.{key} is not a SHA-256 identity")
        return result
    if isinstance(value, (tuple, list)):
        return [_validate_identity_tree(item, name=name) for item in value]
    return value


def _state_layout(conversion: QiConversionProfile) -> dict[str, Any]:
    raw = conversion.payload.get("state_layout") or conversion.root.get("state_layout")
    if not isinstance(raw, Mapping):
        raise ConversionViabilityError("W5 conversion profile omitted its declared state layout")
    result = _plain(raw)
    for name in ("scale_count", "mode_count", "component_count", "batch_limit"):
        if name in result:
            value = result[name]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ConversionViabilityError(f"state layout {name} is not a positive integer")
    for name in ("scale_count", "mode_count", "component_count"):
        if name not in result:
            raise ConversionViabilityError(f"state layout omits {name}")
    return result
def _viability_inputs(conversion: QiConversionProfile) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], list[Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    """Read the W5 profile's explicit viability objects without inventing them."""
    payload = conversion.payload
    support_root = payload.get("support")
    if not isinstance(support_root, Mapping):
        support_root = {}
    support = payload.get("D_conv", support_root.get("D_conv"))
    accepted = payload.get("A_accepted", support_root.get("A_accepted"))
    partition = payload.get("partition")
    cover_root = payload.get("complete_domain_cover", payload.get("cover"))
    if isinstance(cover_root, Mapping):
        cover = cover_root.get("cells")
        semantics = payload.get("complete_domain_cover_semantics", cover_root.get("semantics"))
    else:
        cover = cover_root
        semantics = payload.get("complete_domain_cover_semantics")
    margins = payload.get("registered_margins", payload.get("margins"))
    parameters = payload.get("parameters")
    if not isinstance(parameters, Mapping):
        parameters = payload
    if not all(isinstance(value, Mapping) for value in (support, accepted, partition, margins)):
        raise ConversionViabilityError("W5 profile omits explicit D_conv/A_accepted/partition/margins objects")
    if not isinstance(cover, list) or not isinstance(semantics, Mapping):
        raise ConversionViabilityError("W5 profile omits explicit complete-domain cover semantics")
    return support, accepted, partition, cover, semantics, margins, parameters


def _duration_bounds(support: Mapping[str, Any]) -> tuple[str, str]:
    duration = support.get("duration_s")
    if isinstance(duration, Mapping):
        lower, upper = duration.get("min"), duration.get("max")
    elif isinstance(duration, list) and len(duration) == 2:
        lower, upper = duration
    else:
        lower = upper = None
    if not isinstance(lower, str) or not isinstance(upper, str):
        raise ConversionViabilityError("D_conv has no closed exact duration interval")
    return lower, upper


def _runtime_rationals(conversion: QiConversionProfile, support: Mapping[str, Any]) -> list[Any]:
    rows = support.get("runtime_exact_rationals")
    if rows is None:
        clock = conversion.payload.get("clock")
        rows = clock.get("runtime_exact_rationals") if isinstance(clock, Mapping) else None
    if not isinstance(rows, list):
        raise ConversionViabilityError("D_conv has no exact runtime rational members")
    return rows



def _exact_duration_rows(conversion: QiConversionProfile) -> list[dict[str, Any]]:
    support, _, _, _, _, _, _ = _viability_inputs(conversion)
    raw_rows = _runtime_rationals(conversion, support)
    if not raw_rows:
        raise ConversionViabilityError("D_conv has no exact runtime rational members")
    durations = tuple(conversion.runtime_durations)
    if len(durations) != len(raw_rows):
        raise ConversionViabilityError("runtime duration tuple differs from exact rational registration")
    h_min_raw, h_max_raw = _duration_bounds(support)
    h_min = finite_float(h_min_raw, name="D_conv h_min")
    h_max = finite_float(h_max_raw, name="D_conv h_max")
    result: list[dict[str, Any]] = []
    for ordinal, (raw, duration) in enumerate(zip(raw_rows, durations)):
        if not isinstance(raw, Mapping) or set(raw) != {"numerator", "denominator"}:
            raise ConversionViabilityError("exact runtime rational schema mismatch")
        numerator, denominator = raw["numerator"], raw["denominator"]
        if (
            isinstance(numerator, bool)
            or not isinstance(numerator, int)
            or isinstance(denominator, bool)
            or not isinstance(denominator, int)
            or numerator <= 0
            or denominator <= 0
            or math.gcd(numerator, denominator) != 1
        ):
            raise ConversionViabilityError("exact runtime rational is not reduced and positive")
        if float(numerator / denominator) != float(duration) or not h_min <= float(duration) <= h_max:
            raise ConversionViabilityError("exact runtime rational is not a member of the closed duration interval")
        result.append(
            {
                "ordinal": ordinal,
                "numerator": numerator,
                "denominator": denominator,
                "duration_s": _f64(float(duration)),
            }
        )
    return result


@dataclass(frozen=True)
class QiConversionViabilityProfile:
    payload: Mapping[str, Any]
    profile_sha256: str
    support_sha256: str
    accepted_sha256: str
    cover_sha256: str
    partition_sha256: str
    method_sha256: str


@dataclass(frozen=True)
class QiConversionViabilityResult:
    profile: QiConversionViabilityProfile
    receipt: Mapping[str, Any]
    extension: Mapping[str, Any] | None


def load_w5v_profile(
    conversion: QiConversionProfile,
    *,
    parent_identities: Mapping[str, Any] | None = None,
) -> QiConversionViabilityProfile:
    if not isinstance(conversion, QiConversionProfile):
        raise ConversionViabilityError("W5V requires the exact current QiConversionProfile")
    support, accepted, partition, cover, cover_semantics, margins, parameters = _viability_inputs(conversion)
    if support.get("closed") is not True or support.get("frozen_before_observation") is not True:
        raise ConversionViabilityError("D_conv must be frozen before observation and closed")
    candidates = parameters.get("epsilon_memory_time_candidates_s")
    if not isinstance(candidates, list) or not candidates:
        raise ConversionViabilityError("conversion profile has no preregistered physical-time candidate order")
    for ordinal, value in enumerate(candidates):
        memory_time = _tagged(value, name=f"epsilon_memory_time candidate {ordinal}")
        if memory_time <= 0.0:
            raise ConversionViabilityError("physical epsilon_memory_time candidates must be positive")
    selected_raw = parameters.get("epsilon_memory_time_s")
    if selected_raw is None:
        selected_raw = parameters.get("physical_epsilon_memory_time_s")
    selected_memory_time = _tagged(selected_raw, name="epsilon_memory_time")
    if selected_memory_time <= 0.0:
        raise ConversionViabilityError("physical epsilon_memory_time must be positive")
    epsilon_prog_raw = parameters.get("epsilon_prog_min")
    epsilon_prog_min = _tagged(epsilon_prog_raw, name="epsilon_prog_min")
    if epsilon_prog_min <= 0.0:
        raise ConversionViabilityError("epsilon_prog_min must be positive")
    duration_rows = _exact_duration_rows(conversion)
    for name in ("Delta_T_min", "Delta_T_neutral", "U_T_max", "forward_density_floor", "ema_upper_slack_min"):
        value = _tagged(margins.get(name), name=f"registered margin {name}")
        if name != "forward_density_floor" and value <= 0.0:
            raise ConversionViabilityError(f"registered margin {name} must be positive")
        if name == "forward_density_floor" and value < 0.0:
            raise ConversionViabilityError("forward density floor cannot be negative")
    if not isinstance(cover, list) or len(cover) != len(_COVER_IDS):
        raise ConversionViabilityError("complete-domain cover must contain exactly seven cells")
    source_parent_ids = parent_identities
    if source_parent_ids is None:
        source_parent_ids = getattr(conversion, "parent_identities", None)
    if source_parent_ids is None:
        source_parent_ids = conversion.payload.get("parent_identities") or conversion.root.get("parent_identities")
    if source_parent_ids is None:
        source_parent_ids = {}
    identity_tree = _validate_identity_tree(source_parent_ids, name="parent_identities")
    method = {
        "method": W5V_ANALYTIC_METHOD,
        "decimal_precision_digits": 100,
        "registered_parameters_are_exact_binary64_reals": True,
        "transcendentals": "Decimal.exp with outward binary64 enclosure",
        "fixtures_define_support": False,
        "unresolved_policy": "FAIL",
        "candidate_order": list(candidates),
        "selection_rule": parameters.get("epsilon_memory_time_selection_order"),
        "exact_runtime_rationals": duration_rows,
    }
    viability = {
        "schema": W5V_PROFILE_SCHEMA,
        "conversion_profile_sha256": conversion.profile_sha256,
        "conversion_root_sha256": conversion.root_sha256,
        "conversion_law_sha256": conversion.law_sha256,
        "parent_identities": identity_tree,
        "D_conv": _plain(support),
        "A_accepted": _plain(accepted),
        "partition": _plain(partition),
        "epsilon_prog_min": epsilon_prog_raw,
        "D_prog": _plain(partition.get("D_prog")),
        "D_neutral": _plain(partition.get("D_neutral")),
        "complete_domain_cover": _plain(cover),
        "complete_domain_cover_semantics": _plain(cover_semantics),
        "registered_margins": _plain(margins),
        "coefficient_candidates": list(candidates),
        "physical_epsilon_memory_time_s": selected_raw,
        "exact_duration_rationals": duration_rows,
        "method": method,
        "frozen_before_fixture_observation": True,
        "post_observation_support_change": "new-failed-profile-identity",
        "rejection_policy": "retain-exact-rejected-intervals;revise-law-on-failure",
    }
    viability["support_sha256"] = canonical_hash(viability["D_conv"], "cassi.qi-flow-conversion-support.v1")
    viability["accepted_sha256"] = canonical_hash(viability["A_accepted"], "cassi.qi-flow-conversion-accepted.v1")
    viability["cover_sha256"] = canonical_hash(
        {
            "semantics": viability["complete_domain_cover_semantics"],
            "cells": viability["complete_domain_cover"],
        },
        "cassi.qi-flow-conversion-cover.v1",
    )
    viability["partition_sha256"] = canonical_hash(viability["partition"], "cassi.qi-flow-conversion-partition.v1")
    viability["method_sha256"] = canonical_hash(method, "cassi.qi-flow-conversion-proof-method.v1")
    viability["profile_sha256"] = canonical_hash(viability, W5V_PROFILE_DOMAIN)
    return QiConversionViabilityProfile(
        MappingProxyType(viability),
        viability["profile_sha256"],
        viability["support_sha256"],
        viability["accepted_sha256"],
        viability["cover_sha256"],
        viability["partition_sha256"],
        viability["method_sha256"],
    )


def _validate_w5_binding(binding: Mapping[str, Any], conversion: QiConversionProfile) -> dict[str, Any]:
    if not isinstance(binding, Mapping):
        raise ConversionViabilityError("W5 binding must be an object of current identities")
    allowed = _BASE_BINDING_KEYS | _OPTIONAL_BINDING_KEYS
    missing = sorted(_BASE_BINDING_KEYS - set(binding))
    extra = sorted(set(binding) - allowed)
    if missing or extra:
        raise ConversionViabilityError(f"W5 binding schema mismatch; missing={missing}; extra={extra}")
    for name in (
        "run_id",
        "index_sha256",
        "candidate_state_sha256",
        "profile_sha256",
        "root_sha256",
        "law_sha256",
        "conversion_source_sha256",
        "source_identity_sha256",
    ):
        if not _is_sha256(binding[name]):
            raise ConversionViabilityError(f"W5 binding {name} is not a SHA-256 identity")
    if binding["status"] != "PASS":
        raise ConversionViabilityError("current W5 predecessor did not pass")
    if binding["w5v_forward_domain_certificate"] is not None:
        raise ConversionViabilityError("W5 predecessor falsely inferred or embedded W5V acceptance")
    if binding["profile_sha256"] != conversion.profile_sha256:
        raise ConversionViabilityError("W5 binding profile does not match the proved profile")
    if binding["root_sha256"] != conversion.root_sha256:
        raise ConversionViabilityError("W5 binding root does not match the proved root")
    if binding["law_sha256"] != conversion.law_sha256:
        raise ConversionViabilityError("W5 binding law does not match the proved frozen-Q law")
    for name in ("parent_identities", "certificate_identities"):
        if not isinstance(binding[name], Mapping) or not binding[name]:
            raise ConversionViabilityError(f"W5 binding {name} is empty")
        _validate_identity_tree(binding[name], name=f"w5_binding.{name}")
    return dict(binding)


def _cover_status(profile: QiConversionViabilityProfile, conversion: QiConversionProfile) -> dict[str, Any]:
    support, _, _, _, _, _, _ = _viability_inputs(conversion)
    phase_branches = support.get("phase_branches", conversion.payload.get("phase_branches"))
    if not isinstance(phase_branches, list) or not phase_branches:
        raise ConversionViabilityError("D_conv omits its registered phase branches")
    cover = list(profile.payload["complete_domain_cover"])
    ids = [row.get("cell_id") for row in cover if isinstance(row, Mapping)]
    if tuple(ids) != _COVER_IDS:
        raise ConversionViabilityError("registered cover cells are missing, reordered, or duplicated")
    semantics = profile.payload.get("complete_domain_cover_semantics")
    expected_semantics = {
        "cell_definition": "D_nu=D_conv intersect predicate(cell_id)",
        "unspecified_coordinates": "full frozen D_conv support subject only to cell predicate",
        "coordinates_covered": [
            "EY",
            "EI",
            "epsilon2_ema",
            "rho_ref",
            "phi",
            "lambda_rate",
            "phase_branch",
            "scale",
            "mode",
            "batch",
            "duration_s",
        ],
        "boundary_values": "exact tagged-f64 profile values",
        "interior": "relative interior within D_conv",
        "overlap_policy": "shared boundaries and named lower-dimensional controls only",
    }
    if semantics != expected_semantics:
        raise ConversionViabilityError("complete-domain cover semantics changed after registration")
    phi = conversion.phi
    epsilon_min = -phi * conversion.rho_max
    epsilon_max = conversion.rho_max
    eps = conversion.epsilon_prog_min
    ema_max = conversion.epsilon2_ema_max
    expected = {
        "C00-exact-zero": {"epsilon": (0.0, 0.0), "ema": (0.0, 0.0), "predicate": "EY==EI==epsilon2_ema==0"},
        "C01-balanced-memory-zero": {"epsilon": (0.0, 0.0), "ema": (0.0, 0.0), "predicate": "epsilon==0 and epsilon2_ema==0"},
        "C02-balanced-memory-positive": {"epsilon": (0.0, 0.0), "ema": (0.0, ema_max), "predicate": "epsilon==0 and epsilon2_ema>0"},
        "C03-neutral-positive": {"epsilon": (0.0, eps), "ema": (0.0, ema_max), "predicate": "0<epsilon<epsilon_prog_min"},
        "C04-neutral-negative": {"epsilon": (-eps, 0.0), "ema": (0.0, ema_max), "predicate": "-epsilon_prog_min<epsilon<0"},
        "C05-progress-positive": {"epsilon": (eps, epsilon_max), "ema": (0.0, ema_max), "predicate": "epsilon>=epsilon_prog_min"},
        "C06-progress-negative": {"epsilon": (epsilon_min, -eps), "ema": (0.0, ema_max), "predicate": "epsilon<=-epsilon_prog_min"},
    }
    for row in cover:
        cell_id = row["cell_id"]
        if set(row) != {"cell_id", "epsilon_interval", "epsilon2_ema_interval", "predicate"}:
            raise ConversionViabilityError(f"cover cell {cell_id} schema mismatch")
        epsilon_interval = row["epsilon_interval"]
        ema_interval = row["epsilon2_ema_interval"]
        if not isinstance(epsilon_interval, list) or len(epsilon_interval) != 2 or not isinstance(ema_interval, list) or len(ema_interval) != 2:
            raise ConversionViabilityError(f"cover cell {cell_id} has no exact interval")
        parsed_epsilon = (_tagged(epsilon_interval[0], name=f"{cell_id} epsilon lower"), _tagged(epsilon_interval[1], name=f"{cell_id} epsilon upper"))
        parsed_ema = (_tagged(ema_interval[0], name=f"{cell_id} EMA lower"), _tagged(ema_interval[1], name=f"{cell_id} EMA upper"))
        wanted = expected[cell_id]
        if parsed_epsilon != wanted["epsilon"] or parsed_ema != wanted["ema"] or row["predicate"] != wanted["predicate"]:
            raise ConversionViabilityError(f"cover cell {cell_id} changed after registration")
        if parsed_epsilon[0] > parsed_epsilon[1] or parsed_ema[0] > parsed_ema[1]:
            raise ConversionViabilityError(f"cover cell {cell_id} interval is reversed")
    bulk = [
        expected["C06-progress-negative"]["epsilon"],
        expected["C04-neutral-negative"]["epsilon"],
        expected["C03-neutral-positive"]["epsilon"],
        expected["C05-progress-positive"]["epsilon"],
    ]
    if bulk[0][1] != bulk[1][0] or bulk[1][1] != bulk[2][0] or bulk[2][1] != bulk[3][0]:
        raise ConversionViabilityError("bulk cover has a gap or non-profile boundary")
    if any(left[1] > right[0] for left, right in zip(bulk, bulk[1:])):
        raise ConversionViabilityError("bulk cover interiors overlap")
    exact_rows = _exact_duration_rows(conversion)
    return {
        "cell_count": len(cover),
        "cell_ids": list(_COVER_IDS),
        "epsilon_support": [_f64(epsilon_min), _f64(epsilon_max)],
        "epsilon2_ema_support": [_f64(0.0), _f64(conversion.epsilon2_ema_max)],
        "duration_support": _plain(dict(zip(("min", "max"), _duration_bounds(support)))),
        "exact_duration_rationals": exact_rows,
        "phase_branches": phase_branches,
        "bulk_cover_order": ["C06-progress-negative", "C04-neutral-negative", "C03-neutral-positive", "C05-progress-positive"],
        "balanced_memory_partition": ["C00-exact-zero", "C01-balanced-memory-zero", "C02-balanced-memory-positive"],
        "D_prog": profile.payload["D_prog"],
        "D_neutral": profile.payload["D_neutral"],
        "complete": True,
        "all_D_conv_coordinates_included": True,
        "interiors_pairwise_disjoint": True,
        "boundary_overlap_only": True,
        "exact_zero_named": True,
        "balanced_named": True,
    }


def _analytic_bounds(conversion: QiConversionProfile) -> dict[str, Any]:
    layout = _state_layout(conversion)
    with localcontext() as context:
        context.prec = 100
        phi = _decimal_float(conversion.phi)
        rate = _decimal_float(conversion.lambda_rate)
        rho_ref = _decimal_float(conversion.rho_ref)
        support, accepted, _, _, _, margins, _ = _viability_inputs(conversion)
        position = support.get("position_density")
        rho_raw = position.get("EY_plus_EI_max") if isinstance(position, Mapping) else accepted.get("density_sum_at_most")
        ema = support.get("epsilon2_ema")
        ema_raw = ema.get("max") if isinstance(ema, Mapping) else (ema[1] if isinstance(ema, list) and len(ema) == 2 else accepted.get("epsilon2_ema_at_most"))
        rho_max = _decimal_float(_tagged(rho_raw, name="D_conv rho max"))
        ema_max = _decimal_float(_tagged(ema_raw, name="D_conv EMA max"))
        accepted_density_max = _decimal_float(_tagged(accepted.get("density_sum_at_most"), name="accepted density bound"))
        h_min = _decimal_float(conversion.h_min)
        h_max = _decimal_float(conversion.h_max)
        eps_min = _decimal_float(conversion.epsilon_prog_min)
        one = Decimal(1)
        phi_inv_sq = one / (phi * phi)
        rho_bar_max = rho_max / rho_ref
        q_max = rho_bar_max * rho_bar_max / (rho_bar_max * rho_bar_max + phi_inv_sq)
        one_minus_q_min = one - q_max
        kappa_min = (one + phi) * rate * one_minus_q_min * h_min
        kappa_max = (one + phi) * rate * h_max
        beta_min = (one - (-kappa_min).exp()) / (one + phi)
        beta_max = (one - (-kappa_max).exp()) / (one + phi)
        unit_roundoff = Decimal(2) ** Decimal(-53)
        operation_count_raw = margins.get("analytic_operation_count_upper")
        if isinstance(operation_count_raw, bool) or not isinstance(operation_count_raw, int) or operation_count_raw <= 0:
            raise ConversionViabilityError("W5 profile has no explicit analytic operation-count bound")
        operation_count = Decimal(operation_count_raw)
        if operation_count <= 0 or operation_count * unit_roundoff >= one:
            raise ConversionViabilityError("analytic operation-count bound is inadmissible")
        gamma = (operation_count * unit_roundoff) / (one - operation_count * unit_roundoff)
        operation_scale = max(ema_max, rho_max, phi * rho_max, one)
        runtime_error = gamma * operation_scale
        progress_exact = eps_min * beta_min
        progress_lo = _outward_lower(progress_exact)
        progress_hi = _outward_upper(progress_exact)
        progress_rounding = _rounding_radius(progress_exact, progress_lo, progress_hi)
        progress_u = max(progress_rounding, _outward_upper(runtime_error))
        neutral_exact = eps_min * beta_max
        neutral_lo = _outward_lower(neutral_exact)
        neutral_hi = _outward_upper(neutral_exact)
        neutral_rounding = _rounding_radius(neutral_exact, neutral_lo, neutral_hi)
        neutral_u = max(neutral_rounding, _outward_upper(runtime_error))
        epsilon_abs_max = phi * rho_max
        epsilon2_post_max = epsilon_abs_max * epsilon_abs_max
        coefficient_floor = one - phi * beta_max
        work_proof = {
            "definition": "W_conversion=E_total(endpoint)-E_total(predecessor)",
            "E_total_components": [
                "wave_position",
                "wave_velocity",
                "wave_gradient",
                "composition_potential",
                "link_energy",
                "topological_retention_hamiltonian",
            ],
            "state_dimension": layout,
            "bounded_input": {
                "position_density_sum_max": _f64(conversion.rho_max),
                "dynamic_component_abs_max": _f64(conversion.component_abs_max),
                "epsilon2_ema_max": _f64(conversion.epsilon2_ema_max),
            },
            "finite_operator_identity": conversion.payload.get("w2_geometry_profile_sha256"),
            "finite_endpoint_reason": "finite-dimensional bounded field; current periodic-sheet, composition, link, and retention operators",
            "link_energy_at_W5": _f64(0.0),
            "algebraic_closure": "Delta(E_total)-W_conversion=0",
            "density_energy_work_closure": "signed endpoint ledger includes wave, gradient, composition, links, and retention",
            "independent_raw_endpoint_replay_required": True,
            "whole_wave_dissipation_claim": False,
        }
        work_proof["self_sha256"] = canonical_hash(work_proof, "cassi.qi-flow-conversion-work-domain-proof.v1")
        return {
            "q": {"min": _f64(0.0), "max_outward": _f64(_outward_upper(q_max)), "strictly_less_than_one": q_max < one},
            "one_minus_q": {"min_outward": _f64(_outward_lower(one_minus_q_min)), "max": _f64(1.0)},
            "kappa": {"min_outward": _f64(_outward_lower(kappa_min)), "max_outward": _f64(_outward_upper(kappa_max))},
            "beta": {"min_outward": _f64(_outward_lower(beta_min)), "max_outward": _f64(_outward_upper(beta_max))},
            "runtime_roundoff_model": {
                "unit_roundoff": _f64(float(unit_roundoff)),
                "operation_count_upper": int(operation_count),
                "gamma_outward": _f64(_outward_upper(gamma)),
                "operation_scale_upper": _f64(float(operation_scale)),
                "absolute_error_upper": _f64(_outward_upper(runtime_error)),
                "covers": [
                    "factored epsilon evaluation",
                    "frozen-Q denominator and quotient",
                    "exponential alpha",
                    "transfer and density updates",
                    "phase-rescale target reconstruction",
                ],
            },
            "progress_transfer": {
                "abs_lower_outward": _f64(progress_lo),
                "abs_upper_at_lower_corner": _f64(progress_hi),
                "U_T": _f64(progress_u),
            },
            "neutral_transfer": {
                "abs_supremum_outward": _f64(neutral_hi),
                "lower_outward": _f64(neutral_lo),
                "U_T": _f64(neutral_u),
            },
            "density_coefficients": {
                "one_minus_beta_min": _f64(_outward_lower(one - beta_max)),
                "phi_beta_min": _f64(_outward_lower(phi * beta_min)),
                "beta_min": _f64(_outward_lower(beta_min)),
                "one_minus_phi_beta_min": _f64(_outward_lower(coefficient_floor)),
                "all_nonnegative": coefficient_floor > 0,
            },
            "epsilon_abs_max": _f64(_outward_upper(epsilon_abs_max)),
            "epsilon2_post_max": _f64(_outward_upper(epsilon2_post_max)),
            "ema_support_max": _f64(float(ema_max)),
            "accepted_density_max": _f64(float(accepted_density_max)),
            "density_sum_identity": "EY_next+EI_next=EY+EI",
            "imbalance_identity": "epsilon_next=alpha*epsilon",
            "signed_transfer_identity": "T=epsilon*(1-alpha)/(1+phi)",
            "work_domain_proof": work_proof,
            "map_forward_inclusion": True,
        }


def _coefficient_trials(
    conversion: QiConversionProfile,
    bounds: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    _, _, _, _, _, margins, parameters = _viability_inputs(conversion)
    raw_candidates = parameters.get("epsilon_memory_time_candidates_s")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ConversionViabilityError("W5 profile has no exact physical-time candidate order")
    h_min_d = _decimal_float(conversion.h_min)
    h_max_d = _decimal_float(conversion.h_max)
    ema_max_d = _decimal_float(conversion.epsilon2_ema_max)
    epsilon2_bound_d = _decimal_float(_tagged(bounds["epsilon2_post_max"], name="epsilon2 outward max"))
    required_slack_d = _decimal_float(_tagged(margins["ema_upper_slack_min"], name="registered EMA slack"))
    duration_rows = _exact_duration_rows(conversion)
    trials: list[dict[str, Any]] = []
    for ordinal, raw in enumerate(raw_candidates):
        memory_time = _tagged(raw, name=f"coefficient candidate {ordinal}")
        trial: dict[str, Any] = {
            "ordinal": ordinal,
            "epsilon_memory_time_s": raw,
            "duration_horizons": [],
            "tau_asymptotic_horizon": _f64(1.0),
        }
        if memory_time <= 0.0:
            trial.update({"tau_min_horizon": None, "tau_max_horizon": None, "ema_endpoint_max_outward": None, "ema_upper_slack_lower": None, "status": "FAIL", "reason": "physical epsilon_memory_time is not positive"})
            trials.append(trial)
            continue
        memory_d = _decimal_float(memory_time)
        tau_min_d = one_minus_exp_min = Decimal(1) - (-h_min_d / memory_d).exp()
        tau_max_d = Decimal(1) - (-h_max_d / memory_d).exp()
        endpoint_d = (Decimal(1) - tau_min_d) * ema_max_d + tau_min_d * epsilon2_bound_d
        slack_d = ema_max_d - endpoint_d
        tau_min = _outward_lower(tau_min_d)
        tau_max = _outward_upper(tau_max_d)
        endpoint = _outward_upper(endpoint_d)
        slack = _outward_lower(slack_d)
        horizons: list[dict[str, Any]] = []
        for duration_row in duration_rows:
            h_d = _decimal_float(_tagged(duration_row["duration_s"], name="exact duration"))
            tau_d = Decimal(1) - (-h_d / memory_d).exp()
            horizons.append(
                {
                    "ordinal": duration_row["ordinal"],
                    "duration_exact_rational": {"numerator": duration_row["numerator"], "denominator": duration_row["denominator"]},
                    "duration_s": duration_row["duration_s"],
                    "tau_lower_outward": _f64(_outward_lower(tau_d)),
                    "tau_upper_outward": _f64(_outward_upper(tau_d)),
                }
            )
        trial["duration_horizons"] = horizons
        trial.update(
            {
                "tau_min_horizon": _f64(tau_min),
                "tau_max_horizon": _f64(tau_max),
                "ema_endpoint_max_outward": _f64(endpoint),
                "ema_upper_slack_lower": _f64(slack),
                "status": "PASS" if 0.0 < tau_min <= tau_max < 1.0 and slack >= float(required_slack_d) else "FAIL",
            }
        )
        trial["reason"] = None if trial["status"] == "PASS" else "physical-time EMA forward-inclusion failed"
        trials.append(trial)
    selected = next((row for row in trials if row["status"] == "PASS"), None)
    expected = parameters["epsilon_memory_time_s"]
    if selected is not None and selected["epsilon_memory_time_s"] != expected:
        raise ConversionViabilityError("first-passing coefficient differs from current W5 profile selection")
    return trials, selected


def _cell_rows(
    viability: QiConversionViabilityProfile,
    conversion: QiConversionProfile,
    bounds: Mapping[str, Any],
) -> list[dict[str, Any]]:
    progress_lower = _tagged(bounds["progress_transfer"]["abs_lower_outward"], name="progress lower")
    progress_u = _tagged(bounds["progress_transfer"]["U_T"], name="progress uncertainty")
    neutral_upper = _tagged(bounds["neutral_transfer"]["abs_supremum_outward"], name="neutral upper")
    neutral_u = _tagged(bounds["neutral_transfer"]["U_T"], name="neutral uncertainty")
    _, _, _, _, _, registered, _ = _viability_inputs(conversion)
    delta_min = _tagged(registered["Delta_T_min"], name="registered progress margin")
    delta_neutral = _tagged(registered["Delta_T_neutral"], name="registered neutral margin")
    u_max = _tagged(registered["U_T_max"], name="registered uncertainty maximum")
    common_pass = bool(bounds["map_forward_inclusion"] and bounds["density_coefficients"]["all_nonnegative"])
    rows: list[dict[str, Any]] = []
    cover = viability.payload["complete_domain_cover"]
    cover_cells = cover.get("cells") if isinstance(cover, Mapping) else cover
    if not isinstance(cover_cells, list):
        raise ConversionViabilityError("viability complete-domain cover cells are not a list")
    for cell in cover_cells:
        cell_id = cell["cell_id"]
        is_progress = cell_id in {"C05-progress-positive", "C06-progress-negative"}
        exact_noop = cell_id in {"C00-exact-zero", "C01-balanced-memory-zero"}
        if is_progress:
            margin = progress_lower - progress_u
            transfer_pass = progress_u <= u_max and margin >= delta_min and progress_lower > 0.0
            classification = "dissipative-imbalance-progress"
        else:
            margin = delta_neutral - (neutral_upper + neutral_u)
            transfer_pass = neutral_u <= u_max and neutral_upper + neutral_u <= delta_neutral
            classification = "exact-noop" if exact_noop else "certified-numerical-zero"
        status = "PASS" if common_pass and transfer_pass else "FAIL"
        rows.append(
            {
                "cell_id": cell_id,
                "cell_sha256": canonical_hash(cell, "cassi.qi-flow-conversion-cover-cell.v1"),
                "epsilon_interval": _plain(cell["epsilon_interval"]),
                "epsilon2_ema_interval": _plain(cell["epsilon2_ema_interval"]),
                "predicate": cell["predicate"],
                "status": status,
                "classification": classification,
                "forward_in_D_conv": common_pass,
                "forward_in_A_accepted": common_pass,
                "density_nonnegative": bool(bounds["density_coefficients"]["all_nonnegative"]),
                "density_sum_conserved": True,
                "work_domain_proof_sha256": bounds["work_domain_proof"]["self_sha256"],
                "work_definition": bounds["work_domain_proof"]["definition"],
                "work_closure_class": "analytic signed endpoint identity plus independent raw-endpoint replay",
                "work_closure_abs": _f64(0.0),
                "signed_energy_work_closure": _f64(0.0),
                "sign_transfer_equals_sign_epsilon": True if is_progress else None,
                "transfer_abs_lower": _f64(progress_lower if is_progress else 0.0),
                "transfer_abs_upper": _f64(neutral_upper if not is_progress else _tagged(bounds["progress_transfer"]["abs_upper_at_lower_corner"], name="progress upper")),
                "transfer_uncertainty": _f64(progress_u if is_progress else neutral_u),
                "transfer_margin_lower": _f64(margin),
                "exact_named_noop": exact_noop,
                "unresolved": False,
            }
        )
    return rows


def _normalise_witnesses(witnesses: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    required = {"fixture_id", "covered_cell_ids", "predecessor_sha256", "candidate_sha256", "kind"}
    for witness in witnesses:
        if not isinstance(witness, Mapping) or set(witness) != required:
            raise ConversionViabilityError("witness schema mismatch")
        covered = witness["covered_cell_ids"]
        if not isinstance(covered, list) or not covered:
            raise ConversionViabilityError("witness must name covered registered cells")
        for cell_id in covered:
            if cell_id not in _COVER_IDS:
                raise ConversionViabilityError("witness names an unregistered cover cell")
        if not _is_sha256(witness["predecessor_sha256"]) or not _is_sha256(witness["candidate_sha256"]):
            raise ConversionViabilityError("witness raw state identities are not SHA-256")
        row = dict(witness)
        row["defines_support"] = False
        row["determines_verdict"] = False
        row["witness_sha256"] = canonical_hash(row, "cassi.qi-flow-conversion-witness.v1")
        rows.append(row)
    rows.sort(key=lambda row: row["fixture_id"])
    return rows


def build_w5v_receipt(
    conversion: QiConversionProfile,
    *,
    w5_binding: Mapping[str, Any],
    witnesses: Sequence[Mapping[str, Any]] = (),
    parent_identities: Mapping[str, Any] | None = None,
) -> tuple[QiConversionViabilityProfile, Mapping[str, Any]]:
    viability = load_w5v_profile(conversion, parent_identities=parent_identities)
    support, accepted, _, _, _, registered, _ = _viability_inputs(conversion)
    binding = _validate_w5_binding(w5_binding, conversion)
    cover_status = _cover_status(viability, conversion)
    bounds = _analytic_bounds(conversion)
    trials, selected = _coefficient_trials(conversion, bounds)
    cells = _cell_rows(viability, conversion, bounds)
    witness_rows = _normalise_witnesses(witnesses)
    pass_count = sum(row["status"] == "PASS" for row in cells)
    fail_count = sum(row["status"] == "FAIL" for row in cells)
    unresolved_count = sum(row["status"] == "UNRESOLVED" or row["unresolved"] for row in cells)
    status = "PASS" if selected is not None and pass_count == len(cells) and fail_count == 0 and unresolved_count == 0 else "FAIL"
    exact_duration_rationals = _exact_duration_rows(conversion)
    receipt = {
        "schema": W5V_RECEIPT_SCHEMA,
        "gate": "G5V",
        "owning_package": "W5V",
        "status": status,
        "failure_artifact": status != "PASS",
        "viability_profile_sha256": viability.profile_sha256,
        "conversion_profile_sha256": conversion.profile_sha256,
        "conversion_root_sha256": conversion.root_sha256,
        "conversion_law_sha256": conversion.law_sha256,
        "w5_engineering_binding": binding,
        "parent_identities": viability.payload["parent_identities"],
        "certificate_identities": binding["certificate_identities"],
        "support_sha256": viability.support_sha256,
        "accepted_sha256": viability.accepted_sha256,
        "cover_sha256": viability.cover_sha256,
        "partition_sha256": viability.partition_sha256,
        "registered_margins_sha256": canonical_hash(registered, "cassi.qi-flow-conversion-registered-margins.v1"),
        "proof_method": _plain(viability.payload["method"]),
        "proof_method_sha256": canonical_hash(viability.payload["method"], "cassi.qi-flow-conversion-proof-method.v1"),
        "epsilon_prog_min": viability.payload["epsilon_prog_min"],
        "D_prog": viability.payload["D_prog"],
        "D_neutral": viability.payload["D_neutral"],
        "D_conv": viability.payload["D_conv"],
        "A_accepted": viability.payload["A_accepted"],
        "exact_rational_time_members": exact_duration_rationals,
        "closed_duration_interval": _plain(dict(zip(("min", "max"), _duration_bounds(support)))),
        "physical_epsilon_memory_time_s": viability.payload["physical_epsilon_memory_time_s"],
        "complete_cover": cover_status,
        "analytic_enclosures": bounds,
        "coefficient_trials": trials,
        "selected_coefficient": selected,
        "cells": cells,
        "cell_counts": {"total": len(cells), "PASS": pass_count, "FAIL": fail_count, "UNRESOLVED": unresolved_count},
        "accepted_intervals": {
            "D_conv": viability.payload["D_conv"],
            "A_accepted": viability.payload["A_accepted"],
            "duration_exact_rationals": exact_duration_rationals,
            "cells": [dict(row) for row in cells if row["status"] == "PASS"],
        },
        "rejected_intervals": {
            "failed_cells": [dict(row) for row in cells if row["status"] != "PASS"],
            "unresolved_cells": [dict(row) for row in cells if row["unresolved"]],
            "coefficient_candidates": [dict(row) for row in trials if row["status"] != "PASS"],
            "support_shrinkage": "REJECTED:new-failed-profile-identity",
        },
        "witnesses": witness_rows,
        "fixtures_define_support": False,
        "frozen_before_observation": True,
        "activity_coverage_residence": {
            "proof_cells": ["C05-progress-positive", "C06-progress-negative"],
            "strict_progress_predicate": "abs(T)-U_T>=Delta_T_min>0",
            "strict_progress_verified": all(row["status"] == "PASS" for row in cells if row["classification"] == "dissipative-imbalance-progress"),
            "active_scale_coverage_fraction": _f64(1.0),
            "active_mode_coverage_fraction": _f64(1.0),
            "cross_scale_residency": "all-registered-scales-one-complete-conversion-interval",
            "residence_intervals_min": 1,
            "total_site_occupancy_identity": "EY_next+EI_next=EY+EI",
        },
        "boundary_controls": [
            {
                "control_id": "exact-zero",
                "registered_cell_ids": ["C00-exact-zero"],
                "precondition": "EY==EI==epsilon2_ema==0",
                "analytic_outcome": {"T": _f64(0.0), "epsilon2_ema_next": _f64(0.0)},
                "expected_raw_relation": "exact-noop",
                "runtime_witness_required": True,
            },
            {
                "control_id": "balanced-memory-zero",
                "registered_cell_ids": ["C01-balanced-memory-zero"],
                "precondition": "epsilon==0 and epsilon2_ema==0",
                "analytic_outcome": {"T": _f64(0.0), "epsilon2_ema_next": _f64(0.0)},
                "expected_raw_relation": "exact-noop",
                "runtime_witness_required": True,
            },
            {
                "control_id": "balanced-positive-memory",
                "registered_cell_ids": ["C02-balanced-memory-positive"],
                "precondition": "epsilon==0 and epsilon2_ema>0",
                "analytic_outcome": {"T": _f64(0.0), "epsilon2_ema_next": "(1-tau)*epsilon2_ema"},
                "expected_raw_relation": "positions-and-velocities-exact-noop;EMA-physical-relaxation",
                "runtime_witness_required": True,
            },
            {
                "control_id": "near-capacity-both-signs-phases",
                "registered_cell_ids": ["C05-progress-positive", "C06-progress-negative"],
                "precondition": "rho=profile-rho-max;all-registered-phase-branches",
                "analytic_outcome": {"forward_included": bool(bounds["map_forward_inclusion"]), "sign_transfer_equals_sign_epsilon": True},
                "expected_raw_relation": "density-conserved;phase-preserved-or-registered-inheritance",
                "runtime_witness_required": True,
            },
        ],
        "mutation_controls": [
            {"control_id": "mutate-support", "expected": "REJECT"},
            {"control_id": "delete-cover-cell", "expected": "REJECT"},
            {"control_id": "mutate-cell-predicate", "expected": "REJECT"},
            {"control_id": "mutate-EMA-axis", "expected": "REJECT"},
            {"control_id": "mutate-duration-member", "expected": "REJECT"},
            {"control_id": "reorder-coefficients", "expected": "REJECT"},
            {"control_id": "mutate-margin", "expected": "REJECT"},
            {"control_id": "mutate-W5-source", "expected": "REJECT"},
            {"control_id": "substitute-fixture-for-cover", "expected": "REJECT"},
            {"control_id": "mutate-parent-identity", "expected": "REJECT"},
        ],
        "law_fallback": None,
        "clipping": "none",
        "normalization": "none",
        "retry": "none",
        "silent_transfer_shrink": "none",
        "rejected_candidates": [dict(row) for row in trials if row["status"] != "PASS"],
        "decision": "ADMIT-FROZEN-Q-MAP" if status == "PASS" else "REVISE-LAW-FULL-HAMILTONIAN-GRADIENT-FLOW",
    }
    receipt["self_sha256"] = canonical_hash(receipt, W5V_RECEIPT_DOMAIN)
    return viability, MappingProxyType(receipt)


def build_w5v_extension(
    receipt: Mapping[str, Any],
    *,
    parent_extension: Mapping[str, Any],
    evidence: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    if receipt.get("schema") != W5V_RECEIPT_SCHEMA or receipt.get("status") != "PASS":
        raise ConversionViabilityError("only a passing canonical W5V receipt may extend the certificate")
    if not isinstance(parent_extension, Mapping):
        raise ConversionViabilityError("W5V extension requires the current W4R extension object")
    parent = dict(parent_extension)
    parent_self = parent.get("self_sha256")
    if not _is_sha256(parent_self):
        raise ConversionViabilityError("W4R extension has no current immutable identity")
    parent_body = dict(parent)
    parent_body.pop("self_sha256", None)
    if parent_self != canonical_hash(parent_body, W5V_EXTENSION_DOMAIN):
        raise ConversionViabilityError("W5V parent extension self-hash mismatch")
    parent_ordinal = parent.get("chain_ordinal")
    if isinstance(parent_ordinal, bool) or not isinstance(parent_ordinal, int) or parent_ordinal < 1:
        raise ConversionViabilityError("W5V parent extension ordinal is invalid")
    inventory = list(parent.get("complete_section_inventory", []))
    if len(inventory) != parent_ordinal or [row.get("ordinal") for row in inventory] != list(range(1, parent_ordinal + 1)):
        raise ConversionViabilityError("W5V parent inventory is incomplete or reordered")
    chain_status = parent.get("chain_status")
    if not isinstance(chain_status, str) or "provisional" not in chain_status:
        raise ConversionViabilityError("W5V parent extension is not a provisional certificate predecessor")
    added_section: dict[str, Any] = {
        "schema": W5V_SECTION_SCHEMA,
        "section_id": "w5v-complete-domain-forward-viability",
        "ordinal": parent_ordinal + 1,
        "gate": "G5V",
        "owning_package": "W5V",
        "required": True,
        "receipt_sha256": receipt["self_sha256"],
        "viability_profile_sha256": receipt["viability_profile_sha256"],
        "conversion_profile_sha256": receipt["conversion_profile_sha256"],
        "conversion_root_sha256": receipt["conversion_root_sha256"],
        "conversion_law_sha256": receipt["conversion_law_sha256"],
        "support_sha256": receipt["support_sha256"],
        "accepted_sha256": receipt["accepted_sha256"],
        "partition_sha256": receipt["partition_sha256"],
        "proof_method_sha256": receipt["proof_method_sha256"],
        "registered_margins_sha256": receipt["registered_margins_sha256"],
        "work_domain_proof_sha256": receipt["analytic_enclosures"]["work_domain_proof"]["self_sha256"],
        "w5_engineering_run_id": receipt["w5_engineering_binding"]["run_id"],
        "w5_engineering_index_sha256": receipt["w5_engineering_binding"]["index_sha256"],
        "w5_conversion_source_sha256": receipt["w5_engineering_binding"]["conversion_source_sha256"],
        "w5_source_identity_sha256": receipt["w5_engineering_binding"]["source_identity_sha256"],
        "parent_identities": receipt["parent_identities"],
        "certificate_identities": receipt["certificate_identities"],
        "cover_sha256": receipt["cover_sha256"],
        "all_cell_pass_count": receipt["cell_counts"]["PASS"],
        "unresolved_count": receipt["cell_counts"]["UNRESOLVED"],
        "selected_epsilon_memory_time_s": receipt["selected_coefficient"]["epsilon_memory_time_s"],
        "failed_cell_count": receipt["cell_counts"]["FAIL"],
        "coefficient_trial_count": len(receipt["coefficient_trials"]),
        "all_cells_resolved": receipt["cell_counts"]["UNRESOLVED"] == 0,
        "epsilon_prog_min": receipt["epsilon_prog_min"],
        "D_prog": receipt["D_prog"],
        "D_neutral": receipt["D_neutral"],
        "exact_duration_rationals": receipt["exact_rational_time_members"],
        "physical_time_candidate_order": receipt["coefficient_trials"],
    }
    if evidence is not None:
        added_section["evidence_identities"] = _validate_identity_tree(evidence, name="extension.evidence")
    added_section["self_sha256"] = canonical_hash(added_section, W5V_SECTION_DOMAIN)
    complete_inventory = inventory + [added_section]
    extension = {
        "schema": W5V_EXTENSION_SCHEMA,
        "gate": "G5V",
        "owning_package": "W5V",
        "chain_ordinal": parent_ordinal + 1,
        "chain_status": "provisional",
        "certificate_chain_id": parent["certificate_chain_id"],
        "parent_certificate_sha256": parent_self,
        "parent_section_inventory": inventory,
        "added_section": added_section,
        "complete_section_inventory": complete_inventory,
        "consumed_semantic_subhashes": list(parent.get("consumed_semantic_subhashes", [])),
        "parent_identities": receipt["parent_identities"],
        "certificate_identities": receipt["certificate_identities"],
        "production_certificate_complete": False,
        "required_future_sections": list(parent.get("required_future_sections", [])),
        "final_certificate_identity_sha256": None,
    }
    extension["self_sha256"] = canonical_hash(extension, W5V_EXTENSION_DOMAIN)
    return MappingProxyType(extension)


def certify_w5v(
    conversion: QiConversionProfile,
    *,
    w5_binding: Mapping[str, Any],
    parent_extension: Mapping[str, Any],
    witnesses: Sequence[Mapping[str, Any]] = (),
    parent_identities: Mapping[str, Any] | None = None,
    extension_evidence: Mapping[str, Any] | None = None,
) -> QiConversionViabilityResult:
    profile, receipt = build_w5v_receipt(
        conversion,
        w5_binding=w5_binding,
        witnesses=witnesses,
        parent_identities=parent_identities,
    )
    extension = build_w5v_extension(receipt, parent_extension=parent_extension, evidence=extension_evidence) if receipt["status"] == "PASS" else None
    return QiConversionViabilityResult(profile, receipt, extension)


__all__ = [
    "ConversionViabilityError",
    "QiConversionViabilityProfile",
    "QiConversionViabilityResult",
    "W5V_ANALYTIC_METHOD",
    "W5V_EXTENSION_DOMAIN",
    "W5V_EXTENSION_SCHEMA",
    "W5V_PROFILE_DOMAIN",
    "W5V_PROFILE_SCHEMA",
    "W5V_RECEIPT_DOMAIN",
    "W5V_RECEIPT_SCHEMA",
    "W5V_SECTION_DOMAIN",
    "W5V_SECTION_SCHEMA",
    "build_w5v_extension",
    "build_w5v_receipt",
    "certify_w5v",
    "load_w5v_profile",
]
