"""W5/G5 engineering Yang↔Yin exchange and density-assisted flux on the sole field."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Any, Mapping

import torch

from cassi_qi_carrier import W4_G3N_NUMERICAL_CERTIFICATE_SHA256, W4_RAW_STATE_DOMAIN, transition_v4_carrier
from cassi_qi_field import QiFlowStateV3
from cassi_qi_geometry import PeriodicSheetGeometry
from cassi_qi_numerical_certificate import (
    NUMERICAL_CERTIFICATE_DOMAIN,
    evaluate_online_guard,
    raw_state_bytes_from_field,
    transition_v3_transport_guarded,
)
from cassi_qi_profile import canonical_hash, finite_float
from cassi_qi_topology import (
    W4R_G4_PARENT_EXTENSION,
    W4R_G4_PARENT_PROFILE,
    W4R_G4_PARENT_ROOT,
    W4R_G4_PARENT_RUN,
    topology_diagnostics,
    transition_w4r_topology,
)

W5_EXCHANGE_PROFILE_SCHEMA = "cassi.qi-flow-w5-exchange-profile.v1"
W5_EXCHANGE_ROOT_SCHEMA = "cassi.qi-flow-w5-exchange-root.v1"
W5_EXCHANGE_RECEIPT_SCHEMA = "cassi.qi-flow-w5-exchange-receipt.v1"
W5_INTEGRATED_RECEIPT_SCHEMA = "cassi.qi-flow-w5-integrated-receipt.v1"
W5_EXCHANGE_PROFILE_DOMAIN = W5_EXCHANGE_PROFILE_SCHEMA
W5_EXCHANGE_ROOT_DOMAIN = W5_EXCHANGE_ROOT_SCHEMA
W5_EXCHANGE_RECEIPT_DOMAIN = W5_EXCHANGE_RECEIPT_SCHEMA
W5_INTEGRATED_RECEIPT_DOMAIN = W5_INTEGRATED_RECEIPT_SCHEMA
W5_RAW_DOMAIN = "cassi.qi-flow-w5-raw-state.v1"
W5_LAW_DOMAIN = "cassi.qi-flow-w5-integrated-exchange-flux-law.v1"

W5_PARENT_W4R_RUN = "bf5c141a22f30e9b20bb0cefcebf4cb7d0989dc91ae24baa11511f544604530e"
W5_PARENT_W4R_PROFILE = "838a21ab6bab7f10898fa0bba9f786450141e4f46af0f075ddebb0108b323f22"
W5_PARENT_W4R_ROOT = "6c8f932e34b38394202c4f9ef685c0edd45efc5b05137d218673de42f28eb525"
W5_PARENT_W4R_EXTENSION = "2d9b98645ef11c2c4a5378fc93397bb24b6c1c9a6996946d4ba13083a2592a0e"
W5_PARENT_W4R_CANDIDATE = "467a7ac93b0699afcd45ea16c98f921c4402ee80cd95120a66d2fc8639148335"


class ExchangeError(ValueError):
    pass


def _f64(value: float) -> str:
    import struct

    if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0.0):
        raise ExchangeError("exchange scalar is not canonical finite float64")
    return "f64:" + struct.pack(">d", value).hex()


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _raw_hash(state: QiFlowStateV3) -> str:
    raw = raw_state_bytes_from_field(state.field)
    domain = W5_RAW_DOMAIN.encode("utf-8")
    return hashlib.sha256(
        len(domain).to_bytes(8, "big") + domain + len(raw).to_bytes(8, "big") + raw
    ).hexdigest()

def _w4_raw_hash(state: QiFlowStateV3) -> str:
    raw = raw_state_bytes_from_field(state.field)
    domain = W4_RAW_STATE_DOMAIN.encode("utf-8")
    return hashlib.sha256(
        len(domain).to_bytes(8, "big") + domain + len(raw).to_bytes(8, "big") + raw
    ).hexdigest()


def _payload(*, geometry: Any) -> dict[str, Any]:
    surface = PeriodicSheetGeometry(geometry)
    x_spacing = finite_float(surface.operator_metadata()["spacings_m"][2], name="W2 x spacing")
    law = {
        "law_id": "w5-engineering-phase-current-exchange-flux.v1",
        "density_equations": "dEY=-Gamma*dt-divergence(F)*dt;dEI=+Gamma*dt+divergence(F)*dt",
        "gamma": "gamma_rate*(EY_density*EI_density/(EY_density+EI_density))*(phase_gain*sin(thetaI-thetaY)+current_gain*Lx*(dthetaY_dx-dthetaI_dx))",
        "flux": "F=flux_diffusivity*(EY_density*EI_density/(EY_density+EI_density))*(grad(thetaY)-grad(thetaI))",
        "current": "Im(conj(E)*grad(E)) with W2 centered-periodic [z,y,x] operator",
        "field_realization": "phase-preserving density rescale of EY/EI only; velocities and epsilon2_ema unchanged",
        "no_additive_phase_source": True,
        "no_damping": True,
        "no_projection": True,
        "no_clipping_or_bounding": True,
        "no_new_persistent_state": True,
    }
    law_sha256 = canonical_hash(law, W5_LAW_DOMAIN)
    return {
        "schema": W5_EXCHANGE_PROFILE_SCHEMA,
        "engineering_status": "candidate;W5V-forward-domain-certification-not-claimed",
        "w4r_parent_run_id": W5_PARENT_W4R_RUN,
        "w4r_topology_profile_sha256": W5_PARENT_W4R_PROFILE,
        "w4r_topology_root_sha256": W5_PARENT_W4R_ROOT,
        "w4r_certificate_extension_sha256": W5_PARENT_W4R_EXTENSION,
        "w4r_candidate_sha256": W5_PARENT_W4R_CANDIDATE,
        "g3n_numerical_certificate_sha256": W4_G3N_NUMERICAL_CERTIFICATE_SHA256,
        "canonical_lanes": {
            "yang_position": ["EY.re", "EY.im"],
            "yin_position": ["EI.re", "EI.im"],
            "unchanged": ["VY.re", "VY.im", "VI.re", "VI.im", "epsilon2_ema"],
        },
        "split_schedule": [
            "W3N-guarded-transport",
            "W4-corrected-carrier-with-its-guarded-W3-parent",
            "W4R-topological-retention",
            "W5-phase-current-exchange-and-flux",
        ],
        "law": law,
        "w2_operator": {
            "schema": "cassi.qi-flow-geometry-operators.w2",
            "axis_order": ["z", "y", "x"],
            "spacings_m": list(surface.operator_metadata()["spacings_m"]),
            "gradient": "centered-periodic-roll",
            "divergence": "sum-axis-first-derivatives",
        },
        "law_sha256": law_sha256,
        "parameters": {
            "duration_s": _f64(1.0e-5),
            "gamma_rate_s_inv": _f64(40.0),
            "phase_gain": _f64(1.0),
            "current_gain": _f64(0.25),
            "current_reference_length_m": _f64(x_spacing),
            "flux_diffusivity_m2_s": _f64(1.0e-3),
            "density_floor": _f64(1.0e-12),
        },
        "admission": {
            "strict_positive_target_densities": True,
            "post_exchange_numerical_guard": True,
            "requires_w4r_valid_topology_before_exchange": True,
            "requires_w4r_valid_topology_after_exchange": True,
            "source_byte_budget": 0,
        },
    }


@dataclass(frozen=True)
class QiExchangeProfile:
    payload: Mapping[str, Any]
    root: Mapping[str, Any]
    profile_sha256: str
    root_sha256: str
    law_sha256: str
    duration: float
    gamma_rate: float
    phase_gain: float
    current_gain: float
    current_reference_length: float
    flux_diffusivity: float
    density_floor: float

@dataclass(frozen=True)
class QiExchangeStep:
    predecessor: QiFlowStateV3
    candidate: QiFlowStateV3 | None
    committable: bool
    receipt: Mapping[str, Any]
    failure_reason: str | None = None


@dataclass(frozen=True)
class QiIntegratedExchangeStep:
    predecessor: QiFlowStateV3
    candidate: QiFlowStateV3 | None
    committable: bool
    receipt: Mapping[str, Any]
    failure_reason: str | None = None
    stage_candidates: Mapping[str, QiFlowStateV3] | None = None


def load_w5_exchange_profile(*, geometry: Any) -> QiExchangeProfile:
    payload = _payload(geometry=geometry)
    values = payload["parameters"]
    duration = finite_float(values["duration_s"], name="exchange duration")
    gamma_rate = finite_float(values["gamma_rate_s_inv"], name="exchange gamma rate")
    phase_gain = finite_float(values["phase_gain"], name="exchange phase gain")
    current_gain = finite_float(values["current_gain"], name="exchange current gain")
    current_length = finite_float(values["current_reference_length_m"], name="exchange current length")
    flux = finite_float(values["flux_diffusivity_m2_s"], name="exchange flux diffusivity")
    density_floor = finite_float(values["density_floor"], name="exchange density floor")
    if not (
        duration > 0.0
        and gamma_rate >= 0.0
        and phase_gain > 0.0
        and current_gain >= 0.0
        and current_length > 0.0
        and flux >= 0.0
        and density_floor > 0.0
    ):
        raise ExchangeError("invalid W5 exchange profile parameters")
    base = geometry.base_profile.state_layout
    if int(base["scale_count"]) != 4 or int(base["mode_count"]) != 32 or int(base["component_count"]) != 9:
        raise ExchangeError("W5 requires the frozen W2 [4,9*32,B] sole-field layout")
    payload["w2_geometry_profile_sha256"] = geometry.profile_sha256
    payload["profile_sha256"] = canonical_hash(payload, W5_EXCHANGE_PROFILE_DOMAIN)
    root = {
        "schema": W5_EXCHANGE_ROOT_SCHEMA,
        "profile_sha256": payload["profile_sha256"],
        "law_sha256": payload["law_sha256"],
        "w2_geometry_profile_sha256": geometry.profile_sha256,
        "w4r_parent_run_id": W5_PARENT_W4R_RUN,
        "w4r_topology_profile_sha256": W5_PARENT_W4R_PROFILE,
        "w4r_topology_root_sha256": W5_PARENT_W4R_ROOT,
        "w4r_certificate_extension_sha256": W5_PARENT_W4R_EXTENSION,
        "w4r_candidate_sha256": W5_PARENT_W4R_CANDIDATE,
        "state_layout": _plain(base),
        "persistent_state_added": False,
        "w5v_forward_domain_certificate": None,
    }
    root["self_sha256"] = canonical_hash(root, W5_EXCHANGE_ROOT_DOMAIN)
    return QiExchangeProfile(
        MappingProxyType(payload),
        MappingProxyType(root),
        payload["profile_sha256"],
        root["self_sha256"],
        payload["law_sha256"],
        duration,
        gamma_rate,
        phase_gain,
        current_gain,
        current_length,
        flux,
        density_floor,
    )


def _verify_profile(profile: QiExchangeProfile, geometry: Any, certificate: Mapping[str, Any]) -> None:
    expected = load_w5_exchange_profile(geometry=geometry)
    if not isinstance(profile, QiExchangeProfile) or profile.profile_sha256 != expected.profile_sha256 or profile.root_sha256 != expected.root_sha256:
        raise ExchangeError("W5 profile/root mismatch")
    if profile.law_sha256 != expected.law_sha256:
        raise ExchangeError("W5 law hash mismatch")
    if certificate.get("self_sha256") != W4_G3N_NUMERICAL_CERTIFICATE_SHA256:
        raise ExchangeError("W5 requires the frozen final G3N numerical certificate")
    certificate_body = dict(certificate)
    if certificate_body.pop("self_sha256", None) != canonical_hash(certificate_body, NUMERICAL_CERTIFICATE_DOMAIN):
        raise ExchangeError("W5 numerical certificate identity mismatch")


def _fail_exchange(state: QiFlowStateV3, reason: str) -> QiExchangeStep:
    receipt = {
        "schema": W5_EXCHANGE_RECEIPT_SCHEMA,
        "status": "REJECTED",
        "committable": False,
        "predecessor_state_sha256": _raw_hash(state),
        "candidate_state_sha256": None,
        "failure_reason": reason,
    }
    receipt["self_sha256"] = canonical_hash(receipt, W5_EXCHANGE_RECEIPT_DOMAIN)
    return QiExchangeStep(state, None, False, MappingProxyType(receipt), reason)


def _empty_ledger(*, scale: int, n_y: torch.Tensor, n_i: torch.Tensor) -> dict[str, Any]:
    total = n_y + n_i
    return {
        "scale": scale,
        "yang_density_pre": float(n_y.sum().item()),
        "yin_density_pre": float(n_i.sum().item()),
        "total_density_pre": float(total.sum().item()),
        "gamma_raw_integral": 0.0,
        "gamma_raw_l1": 0.0,
        "local_yang_delta": 0.0,
        "local_yang_delta_l1": 0.0,
        "local_yin_delta": 0.0,
        "local_yin_delta_l1": 0.0,
        "flux_yang_delta": 0.0,
        "flux_yang_delta_l1": 0.0,
        "flux_yin_delta": 0.0,
        "flux_yin_delta_l1": 0.0,
        "integrated_divergence": 0.0,
        "divergence_l1": 0.0,
        "source_work_proxy": 0.0,
        "position_density_work": 0.0,
        "total_density_post": float(total.sum().item()),
        "total_density_closure": 0.0,
        "realized_total_density_delta": 0.0,
    }


def _exchange_map(
    state: QiFlowStateV3,
    *,
    geometry: Any,
    profile: QiExchangeProfile,
    conversion_enabled: bool,
    flux_enabled: bool,
) -> tuple[QiFlowStateV3, list[dict[str, Any]]]:
    """Apply only W5's phase-preserving density map; no guard or projection is hidden here."""
    if not isinstance(conversion_enabled, bool) or not isinstance(flux_enabled, bool):
        raise ExchangeError("W5 term selections must be booleans")
    if not conversion_enabled and not flux_enabled:
        return QiFlowStateV3(state.field.clone().contiguous()), []
    modes = int(geometry.base_profile.state_layout["mode_count"])
    surface = PeriodicSheetGeometry(geometry)
    field = state.field.clone()
    ledgers: list[dict[str, Any]] = []
    for scale in range(int(geometry.base_profile.state_layout["scale_count"])):
        yang = torch.complex(
            surface.modes_to_grid(field[scale, 0:modes, :]),
            surface.modes_to_grid(field[scale, modes:2 * modes, :]),
        )
        yin = torch.complex(
            surface.modes_to_grid(field[scale, 2 * modes:3 * modes, :]),
            surface.modes_to_grid(field[scale, 3 * modes:4 * modes, :]),
        )
        n_y, n_i = yang.abs().square(), yin.abs().square()
        if not bool(torch.isfinite(n_y).all().item()) or not bool(torch.isfinite(n_i).all().item()):
            raise ExchangeError("W5 nonfinite position density")
        if not bool((n_y > profile.density_floor).all().item()) or not bool((n_i > profile.density_floor).all().item()):
            raise ExchangeError("W5 position density violates strict pre-map floor")
        if not conversion_enabled and not flux_enabled:
            ledgers.append(_empty_ledger(scale=scale, n_y=n_y, n_i=n_i))
            continue
        grad_yang = torch.complex(
            surface.gradient(yang.real.contiguous()),
            surface.gradient(yang.imag.contiguous()),
        )
        grad_yin = torch.complex(
            surface.gradient(yin.real.contiguous()),
            surface.gradient(yin.imag.contiguous()),
        )
        current_yang = torch.imag(torch.conj(yang).unsqueeze(0) * grad_yang)
        current_yin = torch.imag(torch.conj(yin).unsqueeze(0) * grad_yin)
        n_total = n_y + n_i
        density_assist = n_y * n_i / n_total
        phase_drive = torch.imag(torch.conj(yang) * yin) / torch.sqrt(n_y * n_i)
        relative_phase_gradient = current_yang / n_y.unsqueeze(0) - current_yin / n_i.unsqueeze(0)
        current_drive = profile.current_reference_length * relative_phase_gradient[2]
        gamma = (
            profile.gamma_rate
            * density_assist
            * (profile.phase_gain * phase_drive + profile.current_gain * current_drive)
            if conversion_enabled
            else torch.zeros_like(n_y)
        )
        flux = (
            profile.flux_diffusivity * density_assist.unsqueeze(0) * relative_phase_gradient
            if flux_enabled
            else torch.zeros_like(relative_phase_gradient)
        )
        divergence = surface.divergence(flux.contiguous())
        local_yang = -profile.duration * gamma
        local_yin = profile.duration * gamma
        flux_yang = -profile.duration * divergence
        flux_yin = profile.duration * divergence
        target_y, target_i = n_y + local_yang + flux_yang, n_i + local_yin + flux_yin
        if not bool(torch.isfinite(target_y).all().item()) or not bool(torch.isfinite(target_i).all().item()):
            raise ExchangeError("W5 target density is nonfinite")
        if not bool((target_y > profile.density_floor).all().item()) or not bool((target_i > profile.density_floor).all().item()):
            raise ExchangeError("W5 target density violates strict floor before commit")
        yang_next = yang * torch.sqrt(target_y / n_y)
        yin_next = yin * torch.sqrt(target_i / n_i)
        field[scale, 0:modes, :] = surface.grid_to_modes(yang_next.real.contiguous())
        field[scale, modes:2 * modes, :] = surface.grid_to_modes(yang_next.imag.contiguous())
        field[scale, 2 * modes:3 * modes, :] = surface.grid_to_modes(yin_next.real.contiguous())
        field[scale, 3 * modes:4 * modes, :] = surface.grid_to_modes(yin_next.imag.contiguous())
        pre_total = float(n_total.sum().item())
        post_total = float((yang_next.abs().square() + yin_next.abs().square()).sum().item())
        ledgers.append(
            {
                "scale": scale,
                "yang_density_pre": float(n_y.sum().item()),
                "yin_density_pre": float(n_i.sum().item()),
                "total_density_pre": pre_total,
                "gamma_raw_integral": float(gamma.sum().item()),
                "local_yang_delta": float(local_yang.sum().item()),
                "local_yin_delta": float(local_yin.sum().item()),
                "flux_yang_delta": float(flux_yang.sum().item()),
                "flux_yin_delta": float(flux_yin.sum().item()),
                "integrated_divergence": float(divergence.sum().item()),
                "source_work_proxy": float((profile.duration * gamma * phase_drive).sum().item()),
                "position_density_work": 0.5 * (post_total - pre_total),
                "total_density_post": post_total,
                "gamma_raw_l1": float(gamma.abs().sum().item()),
                "local_yang_delta_l1": float(local_yang.abs().sum().item()),
                "local_yin_delta_l1": float(local_yin.abs().sum().item()),
                "flux_yang_delta_l1": float(flux_yang.abs().sum().item()),
                "flux_yin_delta_l1": float(flux_yin.abs().sum().item()),
                "divergence_l1": float(divergence.abs().sum().item()),
                "total_density_closure": float((local_yang + local_yin + flux_yang + flux_yin).sum().item()),
                "realized_total_density_delta": post_total - pre_total,
            }
        )
    candidate = QiFlowStateV3(field.contiguous())
    candidate.validate(geometry.base_profile)
    return candidate, ledgers


def _aggregate(ledgers: list[Mapping[str, Any]]) -> dict[str, float]:
    keys = (
        "gamma_raw_integral",
        "gamma_raw_l1",
        "local_yang_delta",
        "local_yang_delta_l1",
        "local_yin_delta",
        "local_yin_delta_l1",
        "flux_yang_delta",
        "flux_yang_delta_l1",
        "flux_yin_delta",
        "flux_yin_delta_l1",
        "integrated_divergence",
        "divergence_l1",
        "source_work_proxy",
        "position_density_work",
        "total_density_closure",
        "realized_total_density_delta",
    )
    return {key: float(sum(float(ledger[key]) for ledger in ledgers)) for key in keys}


def transition_w5_exchange(
    state: QiFlowStateV3,
    *,
    geometry_profile: Any,
    exchange_profile: QiExchangeProfile,
    numerical_certificate: Mapping[str, Any],
    conversion_enabled: bool = True,
    flux_enabled: bool = True,
) -> QiExchangeStep:
    """W5 sole-field local conversion plus W2-periodic density-assisted flux."""
    try:
        _verify_profile(exchange_profile, geometry_profile, numerical_certificate)
    except Exception as exc:
        return _fail_exchange(state, f"W5 profile/certificate rejection: {type(exc).__name__}: {exc}")
    try:
        if not conversion_enabled and not flux_enabled:
            candidate = QiFlowStateV3(state.field.clone().contiguous())
            ledgers = [_empty_ledger(
                scale=scale,
                n_y=state.field[scale, 0:int(geometry_profile.base_profile.state_layout["mode_count"]), :].square()
                + state.field[scale, int(geometry_profile.base_profile.state_layout["mode_count"]):2 * int(geometry_profile.base_profile.state_layout["mode_count"]), :].square(),
                n_i=state.field[scale, 2 * int(geometry_profile.base_profile.state_layout["mode_count"]):3 * int(geometry_profile.base_profile.state_layout["mode_count"]), :].square()
                + state.field[scale, 3 * int(geometry_profile.base_profile.state_layout["mode_count"]):4 * int(geometry_profile.base_profile.state_layout["mode_count"]), :].square(),
            ) for scale in range(int(geometry_profile.base_profile.state_layout["scale_count"]))]
        else:
            candidate, ledgers = _exchange_map(
                state,
                geometry=geometry_profile,
                profile=exchange_profile,
                conversion_enabled=conversion_enabled,
                flux_enabled=flux_enabled,
            )
        guard = evaluate_online_guard(
            numerical_certificate,
            raw_state=raw_state_bytes_from_field(candidate.field),
        )
        if guard["decision"] != "ACCEPT":
            return _fail_exchange(state, f"W5 candidate numerical admission rejected: {guard['reason']}")
        aggregate = _aggregate(ledgers)
        closure_bound = 1.0e-12 * max(1.0, sum(abs(item["total_density_pre"]) for item in ledgers))
        if abs(aggregate["total_density_closure"]) > closure_bound:
            return _fail_exchange(state, "W5 density equation closure violated before commit")
        receipt = {
            "schema": W5_EXCHANGE_RECEIPT_SCHEMA,
            "status": "PASS",
            "committable": True,
            "predecessor_state_sha256": _raw_hash(state),
            "candidate_state_sha256": _raw_hash(candidate),
            "law_sha256": exchange_profile.law_sha256,
            "profile_sha256": exchange_profile.profile_sha256,
            "root_sha256": exchange_profile.root_sha256,
            "conversion_enabled": conversion_enabled,
            "flux_enabled": flux_enabled,
            "map": {
                "phase_source": "none",
                "damping": "none",
                "projection": "none",
                "clipping": "none",
                "bounds": "none;strict-density-admission-rejects-before-commit",
                "persistent_state_added": False,
                "epsilon2_ema_mutated": False,
            },
            "numerical_guard": _plain(guard),
            "per_scale_work_source_ledger": ledgers,
            "continuity": {
                "aggregate": aggregate,
                "equation_closure_bound": closure_bound,
                "periodic_operator": "W2-centered-periodic-divergence-[z,y,x]",
            },
        }
        receipt["self_sha256"] = canonical_hash(receipt, W5_EXCHANGE_RECEIPT_DOMAIN)
        return QiExchangeStep(state, candidate, True, MappingProxyType(receipt))
    except Exception as exc:
        return _fail_exchange(state, f"W5 exchange/flux rejection: {type(exc).__name__}: {exc}")


def _integrated_failure(state: QiFlowStateV3, *, reason: str, stages: Mapping[str, Any]) -> QiIntegratedExchangeStep:
    receipt = {
        "schema": W5_INTEGRATED_RECEIPT_SCHEMA,
        "status": "REJECTED",
        "committable": False,
        "predecessor_state_sha256": _raw_hash(state),
        "candidate_state_sha256": None,
        "failure_reason": reason,
        "stages": _plain(stages),
    }
    receipt["self_sha256"] = canonical_hash(receipt, W5_INTEGRATED_RECEIPT_DOMAIN)
    return QiIntegratedExchangeStep(state, None, False, MappingProxyType(receipt), reason)


def _stage_record(*, name: str, predecessor: QiFlowStateV3, candidate: QiFlowStateV3, receipt: Mapping[str, Any], structural_projection: str) -> dict[str, Any]:
    return {
        "name": name,
        "direct_parent_state_sha256": _raw_hash(predecessor),
        "candidate_state_sha256": _raw_hash(candidate),
        "structural_projection": structural_projection,
        "receipt": _plain(receipt),
    }


def transition_w5_integrated(
    state: QiFlowStateV3,
    *,
    geometry_profile: Any,
    transport_profile: Any,
    carrier_profile: Any,
    topology_profile: Any,
    exchange_profile: QiExchangeProfile,
    numerical_certificate: Mapping[str, Any],
    source: Any = None,
    conversion_enabled: bool = True,
    flux_enabled: bool = True,
) -> QiIntegratedExchangeStep:
    """Declare and execute W3N → corrected W4 → W4R → W5 exactly once each."""
    try:
        _verify_profile(exchange_profile, geometry_profile, numerical_certificate)
    except Exception as exc:
        return _integrated_failure(state, reason=f"W5 profile/certificate rejection: {type(exc).__name__}: {exc}", stages={})
    stages: dict[str, Any] = {}
    guarded = transition_v3_transport_guarded(
        state,
        geometry_profile=geometry_profile,
        transport_profile=transport_profile,
        certificate=numerical_certificate,
        source=source,
    )
    if not guarded.committable or guarded.candidate is None:
        stages["w3_guarded_transport"] = {"receipt": _plain(guarded.receipt or {}), "candidate_exposed": False}
        return _integrated_failure(state, reason=f"W5 W3 guarded transport rejected: {guarded.failure_reason}", stages=stages)
    stages["w3_guarded_transport"] = _stage_record(
        name="W3N-guarded-transport",
        predecessor=state,
        candidate=guarded.candidate,
        receipt=guarded.receipt or {},
        structural_projection="none",
    )
    carrier = transition_v4_carrier(
        state,
        geometry_profile=geometry_profile,
        transport_profile=transport_profile,
        carrier_profile=carrier_profile,
        numerical_certificate=numerical_certificate,
    )
    if not carrier.committable or carrier.candidate is None:
        stages["w4_corrected_carrier"] = {"receipt": _plain(carrier.receipt), "candidate_exposed": False}
        return _integrated_failure(state, reason=f"W5 W4 carrier rejected: {carrier.failure_reason}", stages=stages)
    if raw_state_bytes_from_field(carrier.predecessor.field) != raw_state_bytes_from_field(state.field):
        return _integrated_failure(state, reason="W5 W4 carrier predecessor does not match W5 predecessor", stages=stages)
    w4_guarded_raw = carrier.receipt.get("guarded_w3_candidate_state_sha256")
    if w4_guarded_raw != _w4_raw_hash(guarded.candidate):
        return _integrated_failure(
            state,
            reason="W5 W4 guarded parent does not equal the declared W3 candidate",
            stages=stages,
        )
    stages["w4_corrected_carrier"] = _stage_record(
        name="W4-corrected-carrier",
        predecessor=guarded.candidate,
        candidate=carrier.candidate,
        receipt=carrier.receipt,
        structural_projection=str(carrier.receipt.get("projection", "none")),
    )
    stages["w4_corrected_carrier"]["guarded_w3_candidate_state_sha256"] = w4_guarded_raw
    topology = transition_w4r_topology(
        carrier.candidate,
        geometry_profile=geometry_profile,
        topology_profile=topology_profile,
        numerical_certificate=numerical_certificate,
        decision_bearing=True,
    )
    if not topology.committable or topology.candidate is None:
        stages["w4r_hamiltonian_topology"] = {"receipt": _plain(topology.receipt), "candidate_exposed": False}
        return _integrated_failure(state, reason=f"W5 W4R topology rejected: {topology.failure_reason}", stages=stages)
    stages["w4r_hamiltonian_topology"] = _stage_record(
        name="W4R-topological-retention-hamiltonian",
        predecessor=carrier.candidate,
        candidate=topology.candidate,
        receipt=topology.receipt,
        structural_projection="none",
    )
    exchange = transition_w5_exchange(
        topology.candidate,
        geometry_profile=geometry_profile,
        exchange_profile=exchange_profile,
        numerical_certificate=numerical_certificate,
        conversion_enabled=conversion_enabled,
        flux_enabled=flux_enabled,
    )
    if not exchange.committable or exchange.candidate is None:
        stages["w5_exchange_flux"] = {"receipt": _plain(exchange.receipt), "candidate_exposed": False}
        return _integrated_failure(state, reason=f"W5 exchange/flux rejected: {exchange.failure_reason}", stages=stages)
    post_topology = topology_diagnostics(exchange.candidate, geometry=geometry_profile, profile=topology_profile)
    if post_topology["status"] != "VALID":
        return _integrated_failure(state, reason="W5 exchange invalidated decision-bearing W4R topology", stages=stages)
    stages["w5_exchange_flux"] = _stage_record(
        name="W5-phase-current-exchange-flux",
        predecessor=topology.candidate,
        candidate=exchange.candidate,
        receipt=exchange.receipt,
        structural_projection="none",
    )
    receipt = {
        "schema": W5_INTEGRATED_RECEIPT_SCHEMA,
        "status": "PASS",
        "committable": True,
        "predecessor_state_sha256": _raw_hash(state),
        "candidate_state_sha256": _raw_hash(exchange.candidate),
        "schedule": list(exchange_profile.payload["split_schedule"]),
        "direct_parent_chain": [
            "W5-predecessor",
            "W3N-guarded-transport",
            "W4-corrected-carrier",
            "W4R-topological-retention-hamiltonian",
            "W5-phase-current-exchange-flux",
        ],
        "stages": stages,
        "post_exchange_topology": post_topology,
        "structural_projections": {
            "w3_guarded_transport": "none",
            "w4_corrected_carrier": str(carrier.receipt.get("projection", "none")),
            "w4r_hamiltonian_topology": "none",
            "w5_exchange_flux": "none",
        },
        "w5v_forward_domain_certificate": None,
    }
    receipt["self_sha256"] = canonical_hash(receipt, W5_INTEGRATED_RECEIPT_DOMAIN)
    return QiIntegratedExchangeStep(
        state,
        exchange.candidate,
        True,
        MappingProxyType(receipt),
        stage_candidates=MappingProxyType(
            {
                "w3_guarded_transport": guarded.candidate,
                "w4_corrected_carrier": carrier.candidate,
                "w4r_hamiltonian_topology": topology.candidate,
                "w5_exchange_flux": exchange.candidate,
            }
        ),
    )
__all__ = [
    "ExchangeError",
    "QiExchangeProfile",
    "QiExchangeStep",
    "QiIntegratedExchangeStep",
    "W5_EXCHANGE_PROFILE_DOMAIN",
    "W5_EXCHANGE_ROOT_DOMAIN",
    "W5_EXCHANGE_RECEIPT_DOMAIN",
    "W5_INTEGRATED_RECEIPT_DOMAIN",
    "W5_LAW_DOMAIN",
    "W5_PARENT_W4R_RUN",
    "W5_PARENT_W4R_PROFILE",
    "W5_PARENT_W4R_ROOT",
    "W5_PARENT_W4R_EXTENSION",
    "W5_PARENT_W4R_CANDIDATE",
    "load_w5_exchange_profile",
    "transition_w5_exchange",
    "transition_w5_integrated",
    "_exchange_map",
]
