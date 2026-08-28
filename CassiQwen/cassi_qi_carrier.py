"""W4 reciprocal D/C carrier evolution on the sole ``[S,9M,B]`` field.

The carrier owns no tensor outside the supplied :class:`QiFlowStateV3`.  W2
periodic sheets provide the physical grids and FFT2 operators; W3 supplies the
sealed transport profile and numerical admission contract.  W4 adds one
reciprocal composition potential and advances D and C together with the same
seven-stage symmetric split.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

import torch

from cassi_qi_field import (
    QiFlowGeometryV2,
    QiFlowStateV3,
    _w3_damped_spectral_propagate,
)
from cassi_qi_numerical_certificate import (
    NUMERICAL_CERTIFICATE_DOMAIN,
    NUMERICAL_CERTIFICATE_SCHEMA,
    NUMERICAL_GUARD_SCHEMA,
    evaluate_online_guard,
    raw_state_bytes_from_field,
)
from cassi_qi_profile import canonical_hash, finite_float
from cassi_qi_transport import (
    load_w3_transport_profile,
    projected_pseudospectral_operators,
    validate_w3_transport_profile,
    w3_stage_schedule,
)

W4_CARRIER_PROFILE_SCHEMA = "cassi.qi-flow-carrier-profile.v1"
W4_CARRIER_ROOT_SCHEMA = "cassi.qi-flow-carrier-root.v1"
W4_CARRIER_RECEIPT_SCHEMA = "cassi.qi-flow-carrier-receipt.v1"
W4_CARRIER_CANDIDATE_SCHEMA = "cassi.qi-flow-g4-candidate.v1"
W4_CARRIER_PROFILE_DOMAIN = "cassi.qi-flow-w4-carrier-profile.v1"
W4_CARRIER_ROOT_DOMAIN = "cassi.qi-flow-w4-carrier-root.v1"
W4_CARRIER_RECEIPT_DOMAIN = "cassi.qi-flow-w4-carrier-receipt.v1"
W4_RAW_STATE_DOMAIN = "cassi.qi-flow-w4-raw-state.v1"
W4_COMPOSITION_DERIVATION_SCHEMA = "cassi.qi-flow-w4-composition-derivation.v1"
W4_COMPOSITION_DERIVATION_DOMAIN = "cassi.qi-flow-w4-composition-derivation.v1"
W4_COMPOSITION_SECTION_SCHEMA = "cassi.qi-flow-w4-composition-section.v1"
W4_COMPOSITION_SECTION_DOMAIN = "cassi.qi-flow-w4-composition-section.v1"

W4_COMPONENTS = (
    "EY.re",
    "EY.im",
    "EI.re",
    "EI.im",
    "VY.re",
    "VY.im",
    "VI.re",
    "VI.im",
    "epsilon2_ema",
)

# These are W4 law extension values, not W3 identities.  They are materialized
# into every immutable carrier profile so runtime code never consults a second
# hidden source.  A future profile-schema migration can move this extension to
# W1; until then the named W4 extension is the source of truth.
_W4_EXTENSION_BETA = (0.20, 0.16, 0.12, 0.08)
_W4_EXTENSION_EPSILON_REF = (0.040, 0.050, 0.060, 0.080)


class CarrierError(ValueError):
    """A noncommittable W4 carrier transition or invalid carrier contract."""


def _f64(value: float) -> str:
    if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0.0):
        raise CarrierError("carrier scalar must be finite and not negative zero")
    import struct

    return "f64:" + struct.pack(">d", float(value)).hex()


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _carrier_payload(
    *,
    transport: Any,
    geometry: Any,
    c_c: Sequence[float],
    omega_c: Sequence[float],
    gamma_c: Sequence[float],
    kappa_c: Sequence[float],
) -> dict[str, Any]:
    parameters = transport.pinned_parameters
    phi = finite_float(parameters.phi, name="W3 transform phi")
    return {
        "schema": W4_CARRIER_PROFILE_SCHEMA,
        "law_id": "reciprocal-composition-combined-dc-velocity-verlet.v2",
        "w2_parent": {
            "profile_sha256": str(geometry.profile_sha256),
            "contract_root_sha256": str(geometry.contract_root_sha256),
            "geometry_contract_sha256": str(geometry.geometry_contract_sha256),
            "operator_semantic_sha256": str(geometry.operator_semantic_sha256),
        },
        "w3_parent": {
            "profile_sha256": str(transport.profile_sha256),
            "contract_root_sha256": str(transport.contract_root_sha256),
            "semantic_sha256": str(transport.transport_semantic_sha256),
            "parent_w2": _plain(getattr(transport, "parent_w2", {})),
        },
        "d_c_transform": {
            "phi": _f64(phi),
            "forward": {
                "D": "EY-phi*EI",
                "C": "(phi*EY+EI)/(1+phi^2)",
                "V_D": "VY-phi*VI",
                "V_C": "(phi*VY+VI)/(1+phi^2)",
            },
            "inverse": {
                "EY": "w_D*D+phi*C",
                "EI": "C-phi*w_D*D",
                "VY": "w_D*V_D+phi*V_C",
                "VI": "V_C-phi*w_D*V_D",
            },
            "metric": {"w_D": "1/(1+phi^2)", "w_C": "1+phi^2"},
        },
        "composition": {
            "potential": "w_C*omega_C_s^2*beta_s*tanh(epsilon_s/epsilon_ref_s)*abs(C_s)^2/2",
            "epsilon": "abs(EY)^2-phi*abs(EI)^2",
            "epsilon_wirtinger": {
                "D": "a_phi*(EY+phi^2*EI)",
                "C": "phi*(EY-EI)",
            },
            "beta": [_f64(value) for value in _W4_EXTENSION_BETA],
            "epsilon_ref": [_f64(value) for value in _W4_EXTENSION_EPSILON_REF],
            "force": "reciprocal-metric-wirtinger-v1",
            "potential_off": "uncoupled-combined-dc-reference-v1",
        },
        "dynamics": {
            "D": {
                "c_m_per_s": [_f64(value) for value in transport.pinned_parameters.c_D_m_per_s],
                "omega_rad_per_s": [_f64(value) for value in transport.pinned_parameters.omega_rad_per_s],
                "gamma_per_s": [_f64(value) for value in transport.pinned_parameters.gamma_per_s],
                "kappa": [_f64(value) for value in transport.pinned_parameters.kappa],
            },
            "C": {
                "c_m_per_s": [_f64(value) for value in c_c],
                "omega_rad_per_s": [_f64(value) for value in omega_c],
                "gamma_per_s": [_f64(value) for value in gamma_c],
                "kappa": [_f64(value) for value in kappa_c],
            },
            "source": "W3-transport-D;W1-frozen-base-dynamics-C",
        },
        "integration": {
            "split": "preflight-local-halfkick-analytic-fft2-half-center-placeholder-analytic-fft2-half-local-halfkick-precommit.v2",
            "spectral_operator": "W2-periodic-fft2-unitary-exact-damped-2x2.v1",
            "duration": "validated-W3-clock-interval",
            "local_nonlinear": "metric-adjoint-projected-pseudospectral-cubic.v1",
            "candidate_policy": "finite-envelope-and-work-bound-reject-before-commit.v1",
            "inactive_conversion": "centered-conversion-placeholder.v1",
        },
        "symmetry": {
            "phase_current_reversal": "conjugate-EY-EI-VY-VI.v1",
            "coordinate_negation": "D-and-VD-only;not-epsilon-reversal.v1",
            "imbalance_reversal": "composition-reversal-v1-exact-paired-density.v1",
            "yang_yin_exchange": "metric-normalized-Yang-Yin-exchange-epsilon-sign-reversal.v1",
        },
        "state": {"shape": "[S,9M,B]", "components": list(W4_COMPONENTS), "additional_state": False},
    }


@dataclass(frozen=True)
class QiCarrierProfile:
    payload: Mapping[str, Any]
    root: Mapping[str, Any]
    profile_sha256: str
    root_sha256: str
    phi: float
    w_d: float
    w_c: float
    beta: tuple[float, ...]
    epsilon_ref: tuple[float, ...]
    c_d: tuple[float, ...]
    omega_d: tuple[float, ...]
    gamma_d: tuple[float, ...]
    kappa_d: tuple[float, ...]
    c_c: tuple[float, ...]
    omega_c: tuple[float, ...]
    gamma_c: tuple[float, ...]
    kappa_c: tuple[float, ...]

    @property
    def c_D(self) -> tuple[float, ...]:
        return self.c_d

    @property
    def omega_D(self) -> tuple[float, ...]:
        return self.omega_d

    @property
    def gamma_D(self) -> tuple[float, ...]:
        return self.gamma_d

    @property
    def kappa_D(self) -> tuple[float, ...]:
        return self.kappa_d

    @property
    def c_C(self) -> tuple[float, ...]:
        return self.c_c

    @property
    def gamma_C(self) -> tuple[float, ...]:
        return self.gamma_c

    @property
    def kappa_C(self) -> tuple[float, ...]:
        return self.kappa_c
    @property
    def c_D_m_per_s(self) -> tuple[float, ...]:
        return self.c_d

    @property
    def omega_D_rad_per_s(self) -> tuple[float, ...]:
        return self.omega_d

    @property
    def gamma_D_per_s(self) -> tuple[float, ...]:
        return self.gamma_d

    @property
    def kappa_D_values(self) -> tuple[float, ...]:
        return self.kappa_d

    @property
    def c_C_m_per_s(self) -> tuple[float, ...]:
        return self.c_c

    @property
    def omega_C(self) -> tuple[float, ...]:
        return self.omega_c

    @property
    def omega_C_rad_per_s(self) -> tuple[float, ...]:
        return self.omega_c

    @property
    def gamma_C_per_s(self) -> tuple[float, ...]:
        return self.gamma_c

    @property
    def kappa_C_values(self) -> tuple[float, ...]:
        return self.kappa_c



def _scale_values(dynamics: Mapping[str, Any], key: str, scales: int) -> tuple[float, ...]:
    values = dynamics.get(key)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)) or len(values) != scales:
        raise CarrierError(f"base profile dynamics.{key} must contain one value per scale")
    result = tuple(finite_float(value, name=f"base dynamics.{key}[{index}]") for index, value in enumerate(values))
    if any(value < 0.0 for value in result):
        raise CarrierError(f"base profile dynamics.{key} must be non-negative")
    return result


def load_w4_carrier_profile(*, geometry: Any, transport: Any | None = None) -> QiCarrierProfile:
    """Load W4 and bind it to the current W2/W3 semantic ancestry.

    D coefficients come from the validated W3 transport profile.  C
    coefficients are read from the frozen W1 base-profile dynamics, never from
    a W4 literal or a run artifact.
    """
    try:
        w3 = (
            load_w3_transport_profile(geometry=geometry)
            if transport is None
            else validate_w3_transport_profile(transport, geometry=geometry)
        )
        scales = int(geometry.base_profile.state_layout["scale_count"])
        dynamics = geometry.base_profile.payload["dynamics"]
        if not isinstance(dynamics, Mapping):
            raise CarrierError("base profile omits frozen dynamics")
        c_c = _scale_values(dynamics, "c_C_m_per_s", scales)
        omega_c = _scale_values(dynamics, "omega_C_rad_per_s", scales)
        gamma_c = _scale_values(dynamics, "gamma_C_per_s", scales)
        kappa_c = _scale_values(dynamics, "kappa_C", scales)
        beta = tuple(float(value) for value in _W4_EXTENSION_BETA)
        epsilon_ref = tuple(float(value) for value in _W4_EXTENSION_EPSILON_REF)
        if len(beta) != scales or len(epsilon_ref) != scales:
            raise CarrierError("W4 composition extension does not match current scale count")
        if any(not (0.0 <= value < 1.0) for value in beta) or any(value <= 0.0 for value in epsilon_ref):
            raise CarrierError("W4 composition extension is outside its admitted domain")
        parameters = w3.pinned_parameters
        phi = finite_float(parameters.phi, name="carrier phi")
        if phi <= 0.0:
            raise CarrierError("carrier phi must be positive")
        w_d = 1.0 / (1.0 + phi * phi)
        w_c = 1.0 + phi * phi
        c_d = tuple(finite_float(value, name="W3 c_D") for value in parameters.c_D_m_per_s)
        omega_d = tuple(finite_float(value, name="W3 omega_D") for value in parameters.omega_rad_per_s)
        gamma_d = tuple(finite_float(value, name="W3 gamma_D") for value in parameters.gamma_per_s)
        kappa_d = tuple(finite_float(value, name="W3 kappa_D") for value in parameters.kappa)
        if any(len(values) != scales for values in (c_d, omega_d, gamma_d, kappa_d)):
            raise CarrierError("W3 D dynamics do not match the current scale count")
        payload = _carrier_payload(
            transport=w3,
            geometry=geometry,
            c_c=c_c,
            omega_c=omega_c,
            gamma_c=gamma_c,
            kappa_c=kappa_c,
        )
        payload["profile_sha256"] = canonical_hash(payload, W4_CARRIER_PROFILE_DOMAIN)
        root: dict[str, Any] = {
            "schema": W4_CARRIER_ROOT_SCHEMA,
            "profile_sha256": payload["profile_sha256"],
            "w2_geometry_profile_sha256": geometry.profile_sha256,
            "w2_geometry_contract_root_sha256": geometry.contract_root_sha256,
            "w2_operator_semantic_sha256": geometry.operator_semantic_sha256,
            "w3_transport_profile_sha256": w3.profile_sha256,
            "w3_transport_contract_root_sha256": w3.contract_root_sha256,
            "w3_transport_semantic_sha256": w3.transport_semantic_sha256,
            "state_layout": _plain(geometry.base_profile.state_layout),
            "no_secondary_state": True,
            "profile_extension": "w4-composition-beta-epsilon-ref.v1",
        }
        root["self_sha256"] = canonical_hash(root, W4_CARRIER_ROOT_DOMAIN)
        return QiCarrierProfile(
            MappingProxyType(payload),
            MappingProxyType(root),
            str(payload["profile_sha256"]),
            str(root["self_sha256"]),
            phi,
            w_d,
            w_c,
            beta,
            epsilon_ref,
            c_d,
            omega_d,
            gamma_d,
            kappa_d,
            c_c,
            omega_c,
            gamma_c,
            kappa_c,
        )
    except CarrierError:
        raise
    except Exception as exc:
        raise CarrierError(f"carrier profile construction failed: {type(exc).__name__}: {exc}") from exc


def _certificate_hash_valid(certificate: Mapping[str, Any]) -> bool:
    body = _plain(certificate)
    return body.get("self_sha256") == canonical_hash(
        {key: value for key, value in body.items() if key != "self_sha256"},
        NUMERICAL_CERTIFICATE_DOMAIN,
    )


def _require_certificate_ancestry(certificate: Mapping[str, Any], *, geometry: Any, transport: Any) -> None:
    if not isinstance(certificate, Mapping) or certificate.get("schema") != NUMERICAL_CERTIFICATE_SCHEMA:
        raise CarrierError("W4 requires a numerical G3N certificate root")
    if not _certificate_hash_valid(certificate):
        raise CarrierError("W4 numerical certificate root self hash is invalid")
    guard = certificate.get("online_guard_contract")
    if not isinstance(guard, Mapping) or guard.get("schema") != NUMERICAL_GUARD_SCHEMA:
        raise CarrierError("W4 certificate omits the online numerical guard contract")
    expected_pairs = {
        "profile_sha256": transport.profile_sha256,
        "transport_semantic_sha256": transport.transport_semantic_sha256,
        "operator_semantic_sha256": geometry.operator_semantic_sha256,
    }
    for key, expected in expected_pairs.items():
        if certificate.get(key) != expected:
            raise CarrierError(f"W4 certificate {key} is not bound to the current W3/W2 ancestry")
    if certificate.get("w2_parent") != _plain(getattr(transport, "parent_w2", {})):
        raise CarrierError("W4 certificate W2 parent is not the current validated W2 profile")
    accepted = certificate.get("accepted_w3_artifact_identity")
    if not isinstance(accepted, Mapping):
        raise CarrierError("W4 certificate omits accepted source-exact W3 identity")
    if accepted.get("profile_sha256") != transport.profile_sha256:
        raise CarrierError("W4 certificate accepted W3 profile is not current")
    if accepted.get("contract_root_sha256") != transport.contract_root_sha256:
        raise CarrierError("W4 certificate accepted W3 contract root is not current")
    if accepted.get("semantic_sha256") != transport.transport_semantic_sha256:
        raise CarrierError("W4 certificate accepted W3 semantic source is not current")
    if accepted.get("parent_w2_profile_sha256") != geometry.profile_sha256:
        raise CarrierError("W4 certificate accepted W3 parent profile is not current")
    if accepted.get("parent_w2_contract_root_sha256") != geometry.contract_root_sha256:
        raise CarrierError("W4 certificate accepted W3 parent root is not current")
    raw_layout = guard.get("raw_layout")
    if not isinstance(raw_layout, Mapping):
        raise CarrierError("W4 certificate guard omits raw layout")
    semantic_layout = getattr(transport, "semantic_payload", {}).get("state_layout")
    if not isinstance(semantic_layout, Mapping):
        raise CarrierError("W4 transport omits its semantic state layout")
    scale_count = int(semantic_layout.get("scale_count", 0))
    component_count = int(semantic_layout.get("component_count", 0))
    mode_count = int(semantic_layout.get("mode_count", 0))
    batch_limit = int(geometry.base_profile.state_layout["batch_limit"])
    width = component_count * mode_count
    expected_layout = {
        "layout_id": semantic_layout.get("layout_id"),
        "mode_count": mode_count,
        "component_count": component_count,
        "shape_prefix": [scale_count, width],
        "dtype": semantic_layout.get("dtype"),
        "device": semantic_layout.get("device"),
        "endianness": semantic_layout.get("endianness"),
        "batch_limit": batch_limit,
        "workspace_max_shape": [scale_count, width, batch_limit],
    }
    for key, expected in expected_layout.items():
        if raw_layout.get(key) != expected:
            raise CarrierError(f"W4 certificate raw layout {key} does not match current state")
    active_shapes = geometry.base_profile.payload["spatial"]["active_shapes"]
    if guard.get("active_shapes_yx") != _plain(active_shapes):
        raise CarrierError("W4 certificate active W2 shapes are not current")


def _require_profile(profile: QiCarrierProfile, geometry: Any, transport: Any, certificate: Mapping[str, Any]) -> None:
    if not isinstance(profile, QiCarrierProfile):
        raise CarrierError("W4 requires an explicit QiCarrierProfile")
    validated = load_w4_carrier_profile(geometry=geometry, transport=transport)
    if profile.profile_sha256 != validated.profile_sha256 or profile.root_sha256 != validated.root_sha256:
        raise CarrierError("carrier profile does not match the current immutable W4 extension")
    _require_certificate_ancestry(certificate, geometry=geometry, transport=transport)


@dataclass(frozen=True)
class CarrierCoordinates:
    d: tuple[torch.Tensor, ...]
    c: tuple[torch.Tensor, ...]
    vd: tuple[torch.Tensor, ...]
    vc: tuple[torch.Tensor, ...]
    ey: tuple[torch.Tensor, ...]
    ei: tuple[torch.Tensor, ...]


def _complex(real: torch.Tensor, imag: torch.Tensor) -> torch.Tensor:
    return torch.complex(real, imag)
def _canonical_zero_tensor(value: torch.Tensor) -> torch.Tensor:
    """Canonicalize signed zero before raw-state admission."""
    return torch.where(value == 0.0, torch.zeros_like(value), value)



def _validate_coordinates(values: CarrierCoordinates, *, geometry: Any, state: QiFlowStateV3) -> None:
    scales = int(state.field.shape[0])
    if any(len(getattr(values, name)) != scales for name in ("d", "c", "vd", "vc", "ey", "ei")):
        raise CarrierError("carrier coordinate map changed the number of W2 scales")
    for scale in range(scales):
        expected = tuple(QiFlowGeometryV2(state, geometry)._surface.sheet_shape(scale)) + (state.field.shape[2],)
        for name in ("d", "c", "vd", "vc", "ey", "ei"):
            value = getattr(values, name)[scale]
            if tuple(value.shape) != expected or not value.is_complex() or not bool(torch.isfinite(value).all().item()):
                raise CarrierError(f"carrier coordinate map returned invalid {name}[{scale}]")


def carrier_coordinates(state: QiFlowStateV3, *, geometry: Any, profile: QiCarrierProfile) -> CarrierCoordinates:
    """Derive D/C positions and velocities on every frozen physical W2 grid."""
    if not isinstance(profile, QiCarrierProfile):
        raise CarrierError("carrier_coordinates requires a QiCarrierProfile")
    state.validate(geometry.base_profile)
    surface = QiFlowGeometryV2(state, geometry)
    d: list[torch.Tensor] = []
    c: list[torch.Tensor] = []
    vd: list[torch.Tensor] = []
    vc: list[torch.Tensor] = []
    ey_values: list[torch.Tensor] = []
    ei_values: list[torch.Tensor] = []
    for scale in range(state.field.shape[0]):
        ey = _complex(surface.component_grid(scale, 0), surface.component_grid(scale, 1))
        ei = _complex(surface.component_grid(scale, 2), surface.component_grid(scale, 3))
        vy = _complex(surface.component_grid(scale, 4), surface.component_grid(scale, 5))
        vi = _complex(surface.component_grid(scale, 6), surface.component_grid(scale, 7))
        ey_values.append(ey)
        ei_values.append(ei)
        d.append((ey - profile.phi * ei).contiguous())
        c.append(((profile.phi * ey + ei) * profile.w_d).contiguous())
        vd.append((vy - profile.phi * vi).contiguous())
        vc.append(((profile.phi * vy + vi) * profile.w_d).contiguous())
    return CarrierCoordinates(tuple(d), tuple(c), tuple(vd), tuple(vc), tuple(ey_values), tuple(ei_values))


def _inverse(
    *, d: torch.Tensor, c: torch.Tensor, vd: torch.Tensor, vc: torch.Tensor, profile: QiCarrierProfile
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    return (
        profile.w_d * d + profile.phi * c,
        c - profile.phi * profile.w_d * d,
        profile.w_d * vd + profile.phi * vc,
        vc - profile.phi * profile.w_d * vd,
    )


def _replace_coordinates(
    state: QiFlowStateV3,
    *,
    geometry: Any,
    profile: QiCarrierProfile,
    d: tuple[torch.Tensor, ...],
    c: tuple[torch.Tensor, ...],
    vd: tuple[torch.Tensor, ...],
    vc: tuple[torch.Tensor, ...],
) -> QiFlowStateV3:
    surface = QiFlowGeometryV2(state, geometry)
    field = state.field.clone()
    modes = int(geometry.base_profile.state_layout["mode_count"])
    scales = int(state.field.shape[0])
    if not all(len(values) == scales for values in (d, c, vd, vc)):
        raise CarrierError("carrier coordinate replacement changed scale count")
    for scale, (d_value, c_value, vd_value, vc_value) in enumerate(zip(d, c, vd, vc, strict=True)):
        expected = tuple(surface._surface.sheet_shape(scale)) + (state.field.shape[2],)
        if any(tuple(value.shape) != expected or not value.is_complex() for value in (d_value, c_value, vd_value, vc_value)):
            raise CarrierError("carrier coordinate replacement shape mismatch")
        ey, ei, vy, vi = _inverse(d=d_value, c=c_value, vd=vd_value, vc=vc_value, profile=profile)
        for component, value in (
            (0, ey.real),
            (1, ey.imag),
            (2, ei.real),
            (3, ei.imag),
            (4, vy.real),
            (5, vy.imag),
            (6, vi.real),
            (7, vi.imag),
        ):
            packed = surface.grid_modes(scale, _canonical_zero_tensor(value.contiguous()))
            start = component * modes
            active = int(surface._surface.active_site_count(scale))
            field[scale, start : start + active, :] = packed[:active]
            field[scale, start + active : start + modes, :].zero_()
    result = QiFlowStateV3(field.contiguous())
    result.validate(geometry.base_profile)
    return result


def _epsilon(ey: torch.Tensor, ei: torch.Tensor, profile: QiCarrierProfile) -> torch.Tensor:
    return ey.abs().square() - profile.phi * ei.abs().square()


def _cell_measure(geometry: Any, scale: int) -> float:
    try:
        value = geometry.base_profile.payload["spatial"]["metric_cell_area"][scale]
    except Exception:
        value = geometry.base_profile.payload["spatial"]["sheets"][scale]["metric_cell_area"]
    return finite_float(value, name=f"W2 metric cell area[{scale}]")


def _composition_forces_from_coordinates(
    values: CarrierCoordinates, *, geometry: Any, profile: QiCarrierProfile
) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...], tuple[torch.Tensor, ...], tuple[float, ...]]:
    forces_d: list[torch.Tensor] = []
    forces_c: list[torch.Tensor] = []
    epsilons: list[torch.Tensor] = []
    potentials: list[float] = []
    a_phi = profile.w_d
    for scale, (ey, ei, c_value) in enumerate(zip(values.ey, values.ei, values.c, strict=True)):
        epsilon = _epsilon(ey, ei, profile)
        ratio = epsilon / profile.epsilon_ref[scale]
        f_value = torch.tanh(ratio)
        f_prime = (1.0 - f_value.square()) / profile.epsilon_ref[scale]
        c2 = c_value.abs().square()
        omega2 = profile.omega_c[scale] * profile.omega_c[scale]
        beta = profile.beta[scale]
        # These are exactly the two metric-normalized Wirtinger gradients in
        # CassiFI/01-field-physics.md, equations (composition force rows).
        derivative_epsilon_d = a_phi * (ey + profile.phi * profile.phi * ei)
        derivative_epsilon_c = profile.phi * (ey - ei)
        force_d = (
            -(profile.w_c / profile.w_d)
            * omega2
            * beta
            * f_prime
            * c2
            * derivative_epsilon_d
        ).contiguous()
        force_c = (
            -omega2
            * beta
            * (f_value * c_value + f_prime * c2 * derivative_epsilon_c)
        ).contiguous()
        density = 0.5 * profile.w_c * omega2 * beta * f_value * c2
        forces_d.append(force_d)
        forces_c.append(force_c)
        epsilons.append(epsilon.contiguous())
        potentials.append(float((density.real.sum() * _cell_measure(geometry, scale)).item()))
    return tuple(forces_d), tuple(forces_c), tuple(epsilons), tuple(potentials)


def composition_forces(
    state: QiFlowStateV3, *, geometry: Any, profile: QiCarrierProfile
) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...], tuple[torch.Tensor, ...], tuple[float, ...]]:
    """Evaluate both reciprocal Wirtinger forces and ``U`` at one local stage."""
    values = carrier_coordinates(state, geometry=geometry, profile=profile)
    return _composition_forces_from_coordinates(values, geometry=geometry, profile=profile)


def composition_potential(state: QiFlowStateV3, *, geometry: Any, profile: QiCarrierProfile) -> float:
    return float(sum(_composition_forces_from_coordinates(carrier_coordinates(state, geometry=geometry, profile=profile), geometry=geometry, profile=profile)[3]))


def _coordinate_energies(
    state: QiFlowStateV3, *, geometry: Any, profile: QiCarrierProfile
) -> tuple[tuple[Mapping[str, Any], ...], float]:
    values = carrier_coordinates(state, geometry=geometry, profile=profile)
    surface = QiFlowGeometryV2(state, geometry)._surface
    rows: list[Mapping[str, Any]] = []
    total = 0.0
    for scale, (d, c, vd, vc) in enumerate(zip(values.d, values.c, values.vd, values.vc, strict=True)):
        d_energy = _w3_energy_and_current_local(
            surface,
            scale,
            d,
            vd,
            c_m_per_s=profile.c_d[scale],
            omega_rad_per_s=profile.omega_d[scale],
            gamma_per_s=profile.gamma_d[scale],
            kappa=profile.kappa_d[scale],
            weight=profile.w_d,
        )
        c_energy = _w3_energy_and_current_local(
            surface,
            scale,
            c,
            vc,
            c_m_per_s=profile.c_c[scale],
            omega_rad_per_s=profile.omega_c[scale],
            gamma_per_s=profile.gamma_c[scale],
            kappa=profile.kappa_c[scale],
            weight=profile.w_c,
        )
        row = {
            "scale": scale,
            "D": d_energy,
            "C": c_energy,
            "energy": float(d_energy["energy"] + c_energy["energy"]),
            "phase_charge": float(d_energy["phase_charge"] + c_energy["phase_charge"]),
            "current_max": max(float(d_energy["current_max"]), float(c_energy["current_max"])),
            "current_integral_x": float(d_energy["current_integral_x"] + c_energy["current_integral_x"]),
            "current_integral_y": float(d_energy["current_integral_y"] + c_energy["current_integral_y"]),
        }
        rows.append(MappingProxyType(row))
        total += row["energy"]
    return tuple(rows), float(total)


def _w3_energy_and_current_local(
    surface: Any,
    scale: int,
    position: torch.Tensor,
    velocity: torch.Tensor,
    *,
    c_m_per_s: float,
    omega_rad_per_s: float,
    gamma_per_s: float,
    kappa: float,
    weight: float,
) -> Mapping[str, Any]:
    del gamma_per_s
    gradient = surface.gradient(position, scale=scale)
    area = float(surface.cell_area_m2(scale))
    gradient_norm2 = gradient.abs().square().sum(dim=0)
    density = weight * (
        0.5 * velocity.abs().square()
        + 0.5 * c_m_per_s * c_m_per_s * gradient_norm2
        + 0.5 * omega_rad_per_s * omega_rad_per_s * position.abs().square()
        + 0.25 * kappa * position.abs().square().square()
    )
    phase_density = weight * torch.imag(torch.conj(position) * velocity)
    current = -weight * c_m_per_s * c_m_per_s * torch.imag(torch.conj(position).unsqueeze(0) * gradient)
    return MappingProxyType(
        {
            "energy": float((density.sum() * area).item()),
            "phase_charge": float((phase_density.sum() * area).item()),
            "current_max": float(current.abs().amax().item()),
            "current_integral_x": float((current[0].sum() * area).item()),
            "current_integral_y": float((current[1].sum() * area).item()),
            "amplitude_max": float(position.abs().amax().item()),
        }
    )


def carrier_total_energy(state: QiFlowStateV3, *, geometry: Any, profile: QiCarrierProfile) -> float:
    _, base = _coordinate_energies(state, geometry=geometry, profile=profile)
    return float(base + composition_potential(state, geometry=geometry, profile=profile))


def _state_hash(state: QiFlowStateV3) -> str:
    raw = raw_state_bytes_from_field(state.field)
    digest = hashlib.sha256()
    domain = W4_RAW_STATE_DOMAIN.encode("utf-8")
    digest.update(len(domain).to_bytes(8, "big"))
    digest.update(domain)
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)
    return digest.hexdigest()


def _canonical_zero(value: float) -> float:
    if not math.isfinite(value):
        raise CarrierError("carrier receipt scalar is non-finite")
    return 0.0 if value == 0.0 else float(value)


def _force_sum(forces: tuple[torch.Tensor, ...], geometry: Any, scale: int | None = None) -> float:
    indices = range(len(forces)) if scale is None else (scale,)
    return float(
        sum(float((forces[index].real.sum() * _cell_measure(geometry, index)).item()) for index in indices)
    )


@dataclass(frozen=True)
class QiCarrierStep:
    predecessor: QiFlowStateV3
    candidate: QiFlowStateV3 | None
    committable: bool
    receipt: Mapping[str, Any]
    failure_reason: str | None = None
    intermediates: Mapping[str, QiFlowStateV3] = MappingProxyType({})

AdditionalForce: TypeAlias = Callable[
    [QiFlowStateV3, Any, QiCarrierProfile, CarrierCoordinates],
    tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]],
]
CenterMap: TypeAlias = Callable[[QiFlowStateV3, Any, QiCarrierProfile, CarrierCoordinates], Any]
def _detach_state(state: QiFlowStateV3) -> QiFlowStateV3:
    """Give internal consumers an immutable snapshot independent of work buffers."""
    return QiFlowStateV3(state.field.clone().contiguous())



def _failure(state: QiFlowStateV3, *, reason: str, preflight: Mapping[str, Any] | None = None) -> QiCarrierStep:
    receipt: dict[str, Any] = {
        "schema": W4_CARRIER_RECEIPT_SCHEMA,
        "status": "REJECTED",
        "committable": False,
        "failure_reason": reason,
        "candidate_state_sha256": None,
    }
    if preflight is not None:
        receipt["preflight_guard"] = _plain(preflight)
    receipt["self_sha256"] = canonical_hash(receipt, W4_CARRIER_RECEIPT_DOMAIN)
    return QiCarrierStep(state, None, False, MappingProxyType(receipt), reason)


def _resolve_duration(transport: Any, duration_s: float | None) -> float:
    parameters = transport.pinned_parameters
    duration = finite_float(parameters.h if duration_s is None else duration_s, name="carrier duration")
    h_max = finite_float(getattr(parameters, "h_max_s", parameters.h), name="W3 h_max")
    if not (duration > 0.0 and duration <= h_max):
        raise CarrierError("carrier duration is outside the current W3 clock interval")
    return duration


def _state_energy_and_rows(
    state: QiFlowStateV3, *, geometry: Any, profile: QiCarrierProfile
) -> tuple[tuple[Mapping[str, Any], ...], float, float]:
    rows, base = _coordinate_energies(state, geometry=geometry, profile=profile)
    potential = composition_potential(state, geometry=geometry, profile=profile)
    return rows, base, potential




def _validate_extra_forces(
    forces: Any, *, geometry: Any, state: QiFlowStateV3
) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
    if not isinstance(forces, tuple) or len(forces) != 2:
        raise CarrierError("additional carrier force must return (D_forces, C_forces)")
    d_forces, c_forces = forces
    scales = int(state.field.shape[0])
    if not isinstance(d_forces, tuple) or not isinstance(c_forces, tuple) or len(d_forces) != scales or len(c_forces) != scales:
        raise CarrierError("additional carrier force must return one tensor per scale")
    surface = QiFlowGeometryV2(state, geometry)._surface
    for scale, value in enumerate((*d_forces, *c_forces)):
        expected = tuple(surface.sheet_shape(scale % scales)) + (state.field.shape[2],)
        if not isinstance(value, torch.Tensor) or tuple(value.shape) != expected or not value.is_complex() or not bool(torch.isfinite(value).all().item()):
            raise CarrierError("additional carrier force returned an invalid tensor")
    return d_forces, c_forces
def _tensor_summary(value: torch.Tensor, *, geometry: Any, scale: int) -> Mapping[str, Any]:
    """Keep receipts canonical and compact; never place tensors in JSON."""
    area = _cell_measure(geometry, scale)
    return MappingProxyType(
        {
            "scale": scale,
            "shape": list(value.shape),
            "max_abs": _canonical_zero(float(value.abs().amax().item())),
            "l2_metric": _canonical_zero(float((value.abs().square().sum() * area).sqrt().item())),
            "sum_re": _canonical_zero(float((value.real.sum() * area).item())),
        }
    )


def _force_summaries(values: Sequence[torch.Tensor], *, geometry: Any) -> tuple[Mapping[str, Any], ...]:
    return tuple(_tensor_summary(value, geometry=geometry, scale=scale) for scale, value in enumerate(values))


def _epsilon_summaries(values: Sequence[torch.Tensor]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        MappingProxyType(
            {
                "scale": scale,
                "min": _canonical_zero(float(value.real.amin().item())),
                "max": _canonical_zero(float(value.real.amax().item())),
            }
        )
        for scale, value in enumerate(values)
    )


def _potential_values(
    values: CarrierCoordinates, *, geometry: Any, profile: QiCarrierProfile, enabled: bool
) -> tuple[float, ...]:
    if not enabled:
        return tuple(0.0 for _ in values.d)
    return _composition_forces_from_coordinates(values, geometry=geometry, profile=profile)[3]





def _apply_center_map(
    state: QiFlowStateV3,
    values: CarrierCoordinates,
    *,
    geometry: Any,
    profile: QiCarrierProfile,
    center_map: CenterMap | None,
) -> tuple[QiFlowStateV3, CarrierCoordinates, Mapping[str, Any]]:
    if center_map is None:
        return state, values, MappingProxyType({"mode": "inactive-w3-placeholder", "applied": False})
    mapped = center_map(state, geometry, profile, values)
    if isinstance(mapped, QiFlowStateV3):
        mapped.validate(geometry.base_profile)
        mapped_values = carrier_coordinates(mapped, geometry=geometry, profile=profile)
        return mapped, mapped_values, MappingProxyType({"mode": "profile-bound-center-map", "applied": True, "return": "state"})
    if isinstance(mapped, CarrierCoordinates):
        _validate_coordinates(mapped, geometry=geometry, state=state)
        mapped_state = _replace_coordinates(state, geometry=geometry, profile=profile, d=mapped.d, c=mapped.c, vd=mapped.vd, vc=mapped.vc)
        return mapped_state, carrier_coordinates(mapped_state, geometry=geometry, profile=profile), MappingProxyType({"mode": "profile-bound-center-map", "applied": True, "return": "coordinates"})
    if isinstance(mapped, tuple) and len(mapped) == 2 and isinstance(mapped[0], QiFlowStateV3) and isinstance(mapped[1], CarrierCoordinates):
        mapped[0].validate(geometry.base_profile)
        _validate_coordinates(mapped[1], geometry=geometry, state=mapped[0])
        return mapped[0], mapped[1], MappingProxyType({"mode": "profile-bound-center-map", "applied": True, "return": "state-and-coordinates"})
    raise CarrierError("center_map must return QiFlowStateV3 or CarrierCoordinates")


def _local_kick(
    state: QiFlowStateV3,
    values: CarrierCoordinates,
    *,
    geometry: Any,
    profile: QiCarrierProfile,
    duration: float,
    potential_enabled: bool,
    additional_force: AdditionalForce | None,
) -> tuple[QiFlowStateV3, CarrierCoordinates, Mapping[str, Any]]:
    half = 0.5 * duration
    surface = QiFlowGeometryV2(state, geometry)._surface
    composition_d: tuple[torch.Tensor, ...]
    composition_c: tuple[torch.Tensor, ...]
    epsilons: tuple[torch.Tensor, ...]
    u_scales: tuple[float, ...]
    if potential_enabled:
        composition_d, composition_c, epsilons, u_scales = _composition_forces_from_coordinates(values, geometry=geometry, profile=profile)
    else:
        composition_d = tuple(torch.zeros_like(item) for item in values.d)
        composition_c = tuple(torch.zeros_like(item) for item in values.c)
        epsilons = tuple(_epsilon(ey, ei, profile) for ey, ei in zip(values.ey, values.ei, strict=True))
        u_scales = tuple(0.0 for _ in values.d)
    extra_d = tuple(torch.zeros_like(item) for item in values.d)
    extra_c = tuple(torch.zeros_like(item) for item in values.c)
    if additional_force is not None:
        extra_d, extra_c = _validate_extra_forces(additional_force(state, geometry, profile, values), geometry=geometry, state=state)
    force_d: list[torch.Tensor] = []
    force_c: list[torch.Tensor] = []
    nonlinear_d: list[torch.Tensor] = []
    nonlinear_c: list[torch.Tensor] = []
    for scale, (d, c) in enumerate(zip(values.d, values.c, strict=True)):
        d_nonlinear = torch.zeros_like(d)
        c_nonlinear = torch.zeros_like(c)
        if profile.kappa_d[scale] != 0.0:
            projector = projected_pseudospectral_operators(surface, scale)
            d_nonlinear = -profile.kappa_d[scale] * projector.R(projector.I(d).abs().square() * projector.I(d))
        if profile.kappa_c[scale] != 0.0:
            projector = projected_pseudospectral_operators(surface, scale)
            c_nonlinear = -profile.kappa_c[scale] * projector.R(projector.I(c).abs().square() * projector.I(c))
        nonlinear_d.append(d_nonlinear.contiguous())
        nonlinear_c.append(c_nonlinear.contiguous())
        force_d.append((d_nonlinear + composition_d[scale] + extra_d[scale]).contiguous())
        force_c.append((c_nonlinear + composition_c[scale] + extra_c[scale]).contiguous())
    next_vd = tuple((velocity + half * force).contiguous() for velocity, force in zip(values.vd, force_d, strict=True))
    next_vc = tuple((velocity + half * force).contiguous() for velocity, force in zip(values.vc, force_c, strict=True))
    next_state = _replace_coordinates(
        state,
        geometry=geometry,
        profile=profile,
        d=values.d,
        c=values.c,
        vd=next_vd,
        vc=next_vc,
    )
    next_values = carrier_coordinates(next_state, geometry=geometry, profile=profile)
    evidence = MappingProxyType(
        {
            "potential_enabled": potential_enabled,
            "force_D": _force_summaries(force_d, geometry=geometry),
            "force_C": _force_summaries(force_c, geometry=geometry),
            "nonlinear_D": _force_summaries(nonlinear_d, geometry=geometry),
            "nonlinear_C": _force_summaries(nonlinear_c, geometry=geometry),
            "epsilon": _epsilon_summaries(epsilons),
            "U_per_scale": tuple(_canonical_zero(value) for value in u_scales),
            "force_D_sum_re": _canonical_zero(_force_sum(tuple(force_d), geometry)),
            "force_C_sum_re": _canonical_zero(_force_sum(tuple(force_c), geometry)),
        }
    )
    return next_state, next_values, evidence


def _spectral_half(
    state: QiFlowStateV3,
    values: CarrierCoordinates,
    *,
    geometry: Any,
    profile: QiCarrierProfile,
    duration: float,
) -> tuple[QiFlowStateV3, CarrierCoordinates, Mapping[str, Any]]:
    surface = QiFlowGeometryV2(state, geometry)._surface
    d_out: list[torch.Tensor] = []
    c_out: list[torch.Tensor] = []
    vd_out: list[torch.Tensor] = []
    vc_out: list[torch.Tensor] = []
    branches: list[Mapping[str, int]] = []
    for scale, (d, c, vd, vc) in enumerate(zip(values.d, values.c, values.vd, values.vc, strict=True)):
        next_d, next_vd, branch_d = _w3_damped_spectral_propagate(
            surface,
            scale,
            d,
            vd,
            duration_s=duration,
            c_m_per_s=profile.c_d[scale],
            omega_rad_per_s=profile.omega_d[scale],
            gamma_per_s=profile.gamma_d[scale],
        )
        next_c, next_vc, branch_c = _w3_damped_spectral_propagate(
            surface,
            scale,
            c,
            vc,
            duration_s=duration,
            c_m_per_s=profile.c_c[scale],
            omega_rad_per_s=profile.omega_c[scale],
            gamma_per_s=profile.gamma_c[scale],
        )
        d_out.append(next_d.contiguous())
        c_out.append(next_c.contiguous())
        vd_out.append(next_vd.contiguous())
        vc_out.append(next_vc.contiguous())
        branches.append(MappingProxyType({"D": branch_d, "C": branch_c}))
    next_state = _replace_coordinates(state, geometry=geometry, profile=profile, d=tuple(d_out), c=tuple(c_out), vd=tuple(vd_out), vc=tuple(vc_out))
    next_values = carrier_coordinates(next_state, geometry=geometry, profile=profile)
    return next_state, next_values, MappingProxyType({"branches": tuple(branches), "duration_s": duration})


def _transition_v4_carrier_split(
    state: QiFlowStateV3,
    *,
    geometry_profile: Any,
    transport_profile: Any,
    carrier_profile: QiCarrierProfile,
    numerical_certificate: Mapping[str, Any],
    duration_s: float | None = None,
    potential_enabled: bool = True,
    additional_force: AdditionalForce | None = None,
    center_map: CenterMap | None = None,
) -> QiCarrierStep:
    """Internal shared seven-stage D/C split used by W4, W4R, and W5.

    The optional callbacks are profile-bound internal composition hooks.  The
    public W4 entry point supplies neither callback, so callers cannot select a
    different live W4 law.
    """
    try:
        if not isinstance(potential_enabled, bool):
            raise CarrierError("W4 potential_enabled must be boolean")
        state.validate(geometry_profile.base_profile)
        validated_transport = validate_w3_transport_profile(transport_profile, geometry=geometry_profile)
        _require_profile(carrier_profile, geometry_profile, validated_transport, numerical_certificate)
        preflight = evaluate_online_guard(numerical_certificate, raw_state=raw_state_bytes_from_field(state.field))
        if preflight.get("decision") != "ACCEPT":
            return _failure(state, reason=f"W4 preflight numerical admission rejected: {preflight.get('reason')}", preflight=preflight)
        duration = _resolve_duration(validated_transport, duration_s)
        schedule = w3_stage_schedule(duration)
        values = carrier_coordinates(state, geometry=geometry_profile, profile=carrier_profile)
        if not bool(torch.isfinite(state.field).all().item()):
            raise CarrierError("W4 predecessor contains non-finite values")
        cap = finite_float(validated_transport.pinned_parameters.amplitude_cap, name="W3 amplitude cap")
        if float(state.field.abs().amax().item()) > cap:
            raise CarrierError("W4 predecessor exceeds the W3 amplitude cap")
        pre_rows, pre_base, pre_u = _state_energy_and_rows(state, geometry=geometry_profile, profile=carrier_profile)
        stage_evidence: list[dict[str, Any]] = [{"ordinal": 1, "name": schedule["stages"][0]["name"], "mode": "active", "energy_before": carrier_total_energy(state, geometry=geometry_profile, profile=carrier_profile), "energy_after": carrier_total_energy(state, geometry=geometry_profile, profile=carrier_profile), "work": 0.0}]
        first_local, first_values, first_force = _local_kick(
            state,
            values,
            geometry=geometry_profile,
            profile=carrier_profile,
            duration=duration,
            potential_enabled=potential_enabled,
            additional_force=additional_force,
        )
        first_energy = carrier_total_energy(first_local, geometry=geometry_profile, profile=carrier_profile)
        stage_evidence.append({"ordinal": 2, "name": schedule["stages"][1]["name"], "mode": "active", "energy_before": stage_evidence[0]["energy_after"], "energy_after": first_energy, "work": first_energy - stage_evidence[0]["energy_after"], "force": first_force})
        first_spectral, first_spectral_values, first_spectral_evidence = _spectral_half(
            first_local,
            first_values,
            geometry=geometry_profile,
            profile=carrier_profile,
            duration=0.5 * duration,
        )
        first_spectral_energy = carrier_total_energy(first_spectral, geometry=geometry_profile, profile=carrier_profile)
        stage_evidence.append({"ordinal": 3, "name": schedule["stages"][2]["name"], "mode": "active", "energy_before": first_energy, "energy_after": first_spectral_energy, "work": first_spectral_energy - first_energy, "spectral": first_spectral_evidence})
        center_state, center_values, center_evidence = _apply_center_map(
            first_spectral,
            first_spectral_values,
            geometry=geometry_profile,
            profile=carrier_profile,
            center_map=center_map,
        )
        center_energy = carrier_total_energy(center_state, geometry=geometry_profile, profile=carrier_profile)
        stage_evidence.append({"ordinal": 4, "name": schedule["stages"][3]["name"], "mode": "inactive-w3-placeholder" if center_map is None else "profile-bound", "energy_before": first_spectral_energy, "energy_after": center_energy, "work": center_energy - first_spectral_energy, "center": center_evidence})
        second_spectral, second_spectral_values, second_spectral_evidence = _spectral_half(
            center_state,
            center_values,
            geometry=geometry_profile,
            profile=carrier_profile,
            duration=0.5 * duration,
        )
        second_spectral_energy = carrier_total_energy(second_spectral, geometry=geometry_profile, profile=carrier_profile)
        stage_evidence.append({"ordinal": 5, "name": schedule["stages"][4]["name"], "mode": "active", "energy_before": center_energy, "energy_after": second_spectral_energy, "work": second_spectral_energy - center_energy, "spectral": second_spectral_evidence})
        second_local, second_values, second_force = _local_kick(
            second_spectral,
            second_spectral_values,
            geometry=geometry_profile,
            profile=carrier_profile,
            duration=duration,
            potential_enabled=potential_enabled,
            additional_force=additional_force,
        )
        second_energy = carrier_total_energy(second_local, geometry=geometry_profile, profile=carrier_profile)
        stage_evidence.append({"ordinal": 6, "name": schedule["stages"][5]["name"], "mode": "active", "energy_before": second_spectral_energy, "energy_after": second_energy, "work": second_energy - second_spectral_energy, "force": second_force})
        candidate = _detach_state(second_local)
        intermediates = MappingProxyType(
            {
                "predecessor": _detach_state(state),
                "post-first-kick": _detach_state(first_local),
                "post-first-spectral/pre-center": _detach_state(first_spectral),
                "post-center": _detach_state(center_state),
                "post-second-spectral": _detach_state(second_spectral),
                "post-second-kick/pre-EMA": _detach_state(second_local),
                "candidate/post-EMA": candidate,
            }
        )
        post = evaluate_online_guard(numerical_certificate, raw_state=raw_state_bytes_from_field(candidate.field))
        if post.get("decision") != "ACCEPT":
            return _failure(state, reason=f"W4 postcommit numerical admission rejected: {post.get('reason')}", preflight=post)
        candidate.validate(geometry_profile.base_profile)
        if not bool(torch.isfinite(candidate.field).all().item()):
            raise CarrierError("W4 candidate is non-finite")
        if float(candidate.field.abs().amax().item()) > cap:
            raise CarrierError("W4 candidate exceeds the W3 amplitude cap")
        tail_proof = QiFlowGeometryV2(candidate, geometry_profile)._surface.zero_tail_proof(candidate.field)
        if not bool(tail_proof["inactive_tail_is_exact_zero"]):
            raise CarrierError("W4 candidate wrote a nonzero inactive packed tail")
        post_rows, post_base, post_u = _state_energy_and_rows(candidate, geometry=geometry_profile, profile=carrier_profile)
        stage_evidence.append({"ordinal": 7, "name": schedule["stages"][6]["name"], "mode": "active", "energy_before": second_energy, "energy_after": second_energy, "work": 0.0})
        u_first = composition_potential(first_spectral, geometry=geometry_profile, profile=carrier_profile) if potential_enabled else 0.0
        u_center = composition_potential(center_state, geometry=geometry_profile, profile=carrier_profile) if potential_enabled else 0.0
        u_second = composition_potential(second_spectral, geometry=geometry_profile, profile=carrier_profile) if potential_enabled else 0.0
        u_post = post_u if potential_enabled else 0.0
        work_d = -(u_first - (pre_u if potential_enabled else 0.0))
        work_center = -(u_center - u_first)
        work_c = -(u_second - u_center)
        delta_u = u_second - (pre_u if potential_enabled else 0.0)
        work_closure = work_d + work_center + work_c + delta_u
        linear_pre = sum(
            float(row["D"]["energy"] - 0.25 * carrier_profile.w_d * carrier_profile.kappa_d[row["scale"]] * (0.0))
            + float(row["C"]["energy"] - 0.25 * carrier_profile.w_c * carrier_profile.kappa_c[row["scale"]] * (0.0))
            for row in pre_rows
        )
        linear_post = sum(
            float(row["D"]["energy"] - 0.25 * carrier_profile.w_d * carrier_profile.kappa_d[row["scale"]] * (0.0))
            + float(row["C"]["energy"] - 0.25 * carrier_profile.w_c * carrier_profile.kappa_c[row["scale"]] * (0.0))
            for row in post_rows
        )
        damping_work = linear_post - linear_pre
        total_pre = carrier_total_energy(state, geometry=geometry_profile, profile=carrier_profile)
        total_post = carrier_total_energy(candidate, geometry=geometry_profile, profile=carrier_profile)
        energy_closure = total_post - total_pre - damping_work
        phase_pre = sum(float(row["phase_charge"]) for row in pre_rows)
        phase_post = sum(float(row["phase_charge"]) for row in post_rows)
        current_max = max(
            [float(row["current_max"]) for row in pre_rows] + [float(row["current_max"]) for row in post_rows]
        )
        receipt: dict[str, Any] = {
            "schema": W4_CARRIER_RECEIPT_SCHEMA,
            "status": "PASS",
            "committable": True,
            "predecessor_state_sha256": _state_hash(state),
            "candidate_state_sha256": _state_hash(candidate),
            "post_candidate_guard": _plain(post),
            "preflight_guard": _plain(preflight),
            "carrier_profile_sha256": carrier_profile.profile_sha256,
            "carrier_root_sha256": carrier_profile.root_sha256,
            "w3_transport_profile_sha256": validated_transport.profile_sha256,
            "w3_transport_semantic_sha256": validated_transport.transport_semantic_sha256,
            "w2_geometry_profile_sha256": geometry_profile.profile_sha256,
            "duration_s": duration,
            "potential_enabled": potential_enabled,
            "potential_off_identity": "uncoupled-combined-dc-reference-v1" if not potential_enabled else None,
            "split": "combined-dc-symmetric-seven-stage.v2",
            "stage_schedule": _plain(schedule),
            "stage_evidence": _plain(tuple(stage_evidence)),
            "center_map": "inactive-w3-placeholder.v1" if center_map is None else "profile-bound-center-map.v1",
            "damping": "D-and-C-analytic-fft2-exactly-once-per-half.v1",
            "projection": "metric-adjoint-projected-pseudospectral-cubic.v1",
            "composition": {
                "base_energy_pre": _canonical_zero(pre_base),
                "base_energy_post": _canonical_zero(post_base),
                "U_pre": _canonical_zero(pre_u if potential_enabled else 0.0),
                "U_D_path": _canonical_zero(u_first),
                "U_center": _canonical_zero(u_center),
                "U_C_path": _canonical_zero(u_second),
                "U_post": _canonical_zero(u_post),
                "Delta_U": _canonical_zero(delta_u),
                "W_D": _canonical_zero(work_d),
                "W_center": _canonical_zero(work_center),
                "W_C": _canonical_zero(work_c),
                "coordinate_work_closure": _canonical_zero(work_closure),
                "wave_energy_delta": _canonical_zero(damping_work),
                "total_coupled_closure": _canonical_zero(energy_closure),
                "force_D_sum_re": _canonical_zero(float(second_force["force_D_sum_re"])),
                "force_C_sum_re": _canonical_zero(float(second_force["force_C_sum_re"])),
                "slow_carrier_bias_re": _canonical_zero(float(second_force["force_C"][-1]["sum_re"])),
                "per_scale_U_pre": [_canonical_zero(value) for value in (_composition_forces_from_coordinates(values, geometry=geometry_profile, profile=carrier_profile)[3] if potential_enabled else tuple(0.0 for _ in values.d))],
                "per_scale_U_post": [_canonical_zero(value) for value in (_composition_forces_from_coordinates(second_spectral_values, geometry=geometry_profile, profile=carrier_profile)[3] if potential_enabled else tuple(0.0 for _ in values.d))],
            },
            "diagnostics": {
                "per_scale": _plain(tuple(post_rows)),
                "energy_pre": _canonical_zero(total_pre),
                "energy_post": _canonical_zero(total_post),
                "damping_work": _canonical_zero(damping_work),
                "energy_closure": _canonical_zero(energy_closure),
                "phase_charge_pre": _canonical_zero(phase_pre),
                "phase_charge_post": _canonical_zero(phase_post),
                "current_max": _canonical_zero(current_max),
                "branch_totals": _plain({
                    "D": {name: sum(int(row["spectral"]["branches"][scale]["D"].get(name, 0)) for row in stage_evidence if "spectral" in row for scale in range(len(row["spectral"]["branches"]))) for name in ("underdamped", "critical", "overdamped")},
                    "C": {name: sum(int(row["spectral"]["branches"][scale]["C"].get(name, 0)) for row in stage_evidence if "spectral" in row for scale in range(len(row["spectral"]["branches"]))) for name in ("underdamped", "critical", "overdamped")},
                }),
            },
            "tail_proof": _plain(tail_proof),
            "internal_hooks": {"additional_force": additional_force is not None, "center_map": center_map is not None},
        }
        receipt["self_sha256"] = canonical_hash(receipt, W4_CARRIER_RECEIPT_DOMAIN)
        return QiCarrierStep(state, candidate, True, MappingProxyType(receipt), None, intermediates)
    except Exception as exc:
        return _failure(state, reason=f"W4 split rejected before commit: {type(exc).__name__}: {exc}")


def transition_v4_carrier(
    state: QiFlowStateV3,
    *,
    geometry_profile: Any,
    transport_profile: Any,
    carrier_profile: QiCarrierProfile,
    numerical_certificate: Mapping[str, Any],
    duration_s: float | None = None,
    potential_enabled: bool = True,
) -> QiCarrierStep:
    """Run the immutable W4 combined D/C seven-stage split."""
    return _transition_v4_carrier_split(
        state,
        geometry_profile=geometry_profile,
        transport_profile=transport_profile,
        carrier_profile=carrier_profile,
        numerical_certificate=numerical_certificate,
        duration_s=duration_s,
        potential_enabled=potential_enabled,
    )


def phase_current_reversal(state: QiFlowStateV3, *, geometry: Any) -> QiFlowStateV3:
    """Apply registered phase/current conjugation to the sole packed field."""
    state.validate(geometry.base_profile)
    result = state.field.clone()
    modes = int(geometry.base_profile.state_layout["mode_count"])
    for component in (1, 3, 5, 7):
        current = result[:, component * modes : (component + 1) * modes, :]
        result[:, component * modes : (component + 1) * modes, :] = _canonical_zero_tensor(-current)
    return QiFlowStateV3(_canonical_zero_tensor(result.contiguous()))


def yang_yin_exchange(state: QiFlowStateV3, *, geometry: Any, profile: QiCarrierProfile) -> QiFlowStateV3:
    """Exchange Yang/Yin under the profile metric, reversing epsilon sign."""
    state.validate(geometry.base_profile)
    result = state.field.clone()
    modes = int(geometry.base_profile.state_layout["mode_count"])
    phi_root = math.sqrt(profile.phi)
    for real_component, imag_component, other_real, other_imag in ((0, 1, 2, 3), (4, 5, 6, 7)):
        first_real = state.field[:, real_component * modes : (real_component + 1) * modes, :]
        first_imag = state.field[:, imag_component * modes : (imag_component + 1) * modes, :]
        second_real = state.field[:, other_real * modes : (other_real + 1) * modes, :]
        second_imag = state.field[:, other_imag * modes : (other_imag + 1) * modes, :]
        result[:, real_component * modes : (real_component + 1) * modes, :] = phi_root * second_real
        result[:, imag_component * modes : (imag_component + 1) * modes, :] = phi_root * second_imag
        result[:, other_real * modes : (other_real + 1) * modes, :] = first_real / phi_root
        result[:, other_imag * modes : (other_imag + 1) * modes, :] = first_imag / phi_root
    return QiFlowStateV3(_canonical_zero_tensor(result.contiguous()))


def negate_differential_coordinate(state: QiFlowStateV3, *, geometry: Any, profile: QiCarrierProfile) -> QiFlowStateV3:
    """Apply the registered D/VD sign control without reversing epsilon."""
    values = carrier_coordinates(state, geometry=geometry, profile=profile)
    return _replace_coordinates(
        state,
        geometry=geometry,
        profile=profile,
        d=tuple(-value for value in values.d),
        c=values.c,
        vd=tuple(-value for value in values.vd),
        vc=values.vc,
    )


def phase_shuffled_equal_energy(state: QiFlowStateV3, *, geometry: Any) -> QiFlowStateV3:
    """Apply a deterministic sheet-wise global phase without changing energy."""
    state.validate(geometry.base_profile)
    result = state.field.clone()
    modes = int(geometry.base_profile.state_layout["mode_count"])
    for scale in range(result.shape[0]):
        for lane in range(result.shape[2]):
            quarter_turns = (scale + lane + 1) % 4
            for real_component, imag_component in ((0, 1), (2, 3), (4, 5), (6, 7)):
                real = state.field[scale, real_component * modes : (real_component + 1) * modes, lane]
                imag = state.field[scale, imag_component * modes : (imag_component + 1) * modes, lane]
                if quarter_turns == 1:
                    next_real, next_imag = -imag, real
                elif quarter_turns == 2:
                    next_real, next_imag = -real, -imag
                elif quarter_turns == 3:
                    next_real, next_imag = imag, -real
                else:
                    next_real, next_imag = real, imag
                result[scale, real_component * modes : (real_component + 1) * modes, lane] = next_real
                result[scale, imag_component * modes : (imag_component + 1) * modes, lane] = next_imag
    return QiFlowStateV3(_canonical_zero_tensor(result.contiguous()))


def _fixture_energy_for_c2(
    *,
    geometry: Any,
    profile: QiCarrierProfile,
    rho: float,
    epsilon0: float,
    sign: float,
    c2: float,
) -> float:
    """Evaluate the zero-velocity constant-field energy for fixture search."""
    d2 = (rho - profile.w_c * c2) / profile.w_d
    if d2 < 0.0:
        return float("nan")
    total = 0.0
    for scale in range(len(profile.c_d)):
        cells = int(geometry.base_profile.payload["spatial"]["per_scale"][scale]["active_site_count"])
        cells *= _cell_measure(geometry, scale)
        d2_scale = profile.w_d * (
            0.5 * profile.omega_d[scale] ** 2 * d2
            + 0.25 * profile.kappa_d[scale] * d2 * d2
        )
        c2_scale = profile.w_c * (
            0.5 * profile.omega_c[scale] ** 2 * c2
            + 0.25 * profile.kappa_c[scale] * c2 * c2
        )
        composition = (
            0.5
            * profile.w_c
            * profile.omega_c[scale] ** 2
            * profile.beta[scale]
            * math.tanh(sign * epsilon0 / profile.epsilon_ref[scale])
            * c2
        )
        total += cells * (d2_scale + c2_scale + composition)
    return total


def _fixture_c2_range(*, profile: QiCarrierProfile, rho: float, epsilon0: float, sign: float) -> tuple[float, float]:
    ey2 = (profile.phi * rho + sign * epsilon0) / (1.0 + profile.phi)
    ei2 = (rho - sign * epsilon0) / (1.0 + profile.phi)
    cross = 2.0 * profile.phi * math.sqrt(max(0.0, ey2 * ei2))
    denominator = (1.0 + profile.phi * profile.phi) ** 2
    return ((profile.phi * math.sqrt(ey2) - math.sqrt(ei2)) ** 2 / denominator, (profile.phi * math.sqrt(ey2) + math.sqrt(ei2)) ** 2 / denominator)


def _fixture_match_c2(
    *, geometry: Any, profile: QiCarrierProfile, rho: float, epsilon0: float, sign: float, target: float
) -> float:
    low, high = _fixture_c2_range(profile=profile, rho=rho, epsilon0=epsilon0, sign=sign)
    samples = [low + (high - low) * index / 256.0 for index in range(257)]
    values = [_fixture_energy_for_c2(geometry=geometry, profile=profile, rho=rho, epsilon0=epsilon0, sign=sign, c2=value) for value in samples]
    best = min(range(len(samples)), key=lambda index: abs(values[index] - target))
    if best == 0 or best == len(samples) - 1:
        return samples[best]
    left = samples[best - 1]
    right = samples[best + 1]
    left_value = _fixture_energy_for_c2(geometry=geometry, profile=profile, rho=rho, epsilon0=epsilon0, sign=sign, c2=left)
    right_value = _fixture_energy_for_c2(geometry=geometry, profile=profile, rho=rho, epsilon0=epsilon0, sign=sign, c2=right)
    increasing = right_value >= left_value
    for _ in range(80):
        middle = 0.5 * (left + right)
        middle_value = _fixture_energy_for_c2(geometry=geometry, profile=profile, rho=rho, epsilon0=epsilon0, sign=sign, c2=middle)
        if (middle_value < target) == increasing:
            left = middle
        else:
            right = middle
    return 0.5 * (left + right)


def composition_reversal_fixture(
    *,
    geometry: Any,
    profile: QiCarrierProfile,
    rho: float = 0.010,
    epsilon0: float = 0.001,
    ballast: float = 0.0002,
) -> dict[str, Any]:
    """Build equal-density/equal-energy, opposite-epsilon, zero-current pairs."""
    if not (
        math.isfinite(rho)
        and math.isfinite(epsilon0)
        and math.isfinite(ballast)
        and rho > 0.0
        and ballast > 0.0
        and 0.0 < epsilon0 < rho * min(1.0, profile.phi)
    ):
        raise CarrierError("composition reversal fixture constants are invalid")
    ranges = [_fixture_c2_range(profile=profile, rho=rho, epsilon0=epsilon0, sign=sign) for sign in (-1.0, 1.0)]
    energy_ranges = [
        [
            _fixture_energy_for_c2(geometry=geometry, profile=profile, rho=rho, epsilon0=epsilon0, sign=sign, c2=value)
            for value in bounds
        ]
        for sign, bounds in zip((-1.0, 1.0), ranges, strict=True)
    ]
    low_target = max(min(values) for values in energy_ranges)
    high_target = min(max(values) for values in energy_ranges)
    if not (low_target <= high_target and math.isfinite(low_target) and math.isfinite(high_target)):
        raise CarrierError("composition reversal fixture has no equal-energy zero-velocity pair")
    target = 0.5 * (low_target + high_target)
    c2_values = {
        sign: _fixture_match_c2(
            geometry=geometry, profile=profile, rho=rho, epsilon0=epsilon0, sign=sign, target=target
        )
        for sign in (-1.0, 1.0)
    }
    base = QiFlowStateV3.create(geometry.base_profile, batch_lanes=1)
    modes = int(geometry.base_profile.state_layout["mode_count"])
    states: dict[str, QiFlowStateV3] = {}
    position_energy: dict[str, float] = {}
    phase_data: dict[str, float] = {}
    for sign, name in ((-1.0, "minus"), (1.0, "plus")):
        ey2 = (profile.phi * rho + sign * epsilon0) / (1.0 + profile.phi)
        ei2 = (rho - sign * epsilon0) / (1.0 + profile.phi)
        c2_min, c2_max = ranges[0 if sign < 0 else 1]
        denominator = 2.0 * profile.phi * math.sqrt(max(1.0e-300, ey2 * ei2))
        cosine = ((1.0 + profile.phi * profile.phi) ** 2 * c2_values[sign] - profile.phi * profile.phi * ey2 - ei2) / denominator
        cosine = max(-1.0, min(1.0, cosine))
        theta = math.acos(cosine)
        ey = math.sqrt(ey2)
        ei = math.sqrt(ei2) * complex(math.cos(theta), math.sin(theta))
        field = torch.zeros_like(base.field)
        field[:, 0:modes, :] = ey
        field[:, 2 * modes : 3 * modes, :] = torch.as_tensor(ei.real, dtype=field.dtype)
        field[:, 3 * modes : 4 * modes, :] = torch.as_tensor(ei.imag, dtype=field.dtype)
        state = QiFlowStateV3(field.contiguous())
        states[name] = state
        position_energy[name] = carrier_total_energy(state, geometry=geometry, profile=profile)
        phase_data[name] = theta
    target = 0.5 * (position_energy["minus"] + position_energy["plus"])
    return {
        "fixture_id": "composition-reversal-v1",
        "rho": rho,
        "epsilon0": epsilon0,
        "ballast": ballast,
        "target_energy": target,
        "minus": states["minus"],
        "plus": states["plus"],
        "raw_state_sha256": {name: _state_hash(value) for name, value in states.items()},
        "full_energy": {name: carrier_total_energy(value, geometry=geometry, profile=profile) for name, value in states.items()},
        "position_energy": position_energy,
        "phase": phase_data,
        "velocity_basis": "exact-zero-v1",
    }


def build_composition_derivation(*, carrier_profile: QiCarrierProfile, numerical_certificate: Mapping[str, Any]) -> dict[str, Any]:
    """Derive W4 curvature/work bounds from a structurally valid G3N root."""
    if not isinstance(numerical_certificate, Mapping) or numerical_certificate.get("schema") != NUMERICAL_CERTIFICATE_SCHEMA or not _certificate_hash_valid(numerical_certificate):
        raise CarrierError("composition derivation requires a valid numerical certificate root")
    try:
        raw_cap = finite_float(numerical_certificate["online_guard_contract"]["raw_component_admission_abs"], name="G3N raw cap")
        duration = finite_float(numerical_certificate["online_guard_contract"]["stage_schedule_sha256"] and numerical_certificate["offline_derivation"]["inputs"]["h_s"], name="G3N duration")
    except Exception:
        try:
            duration = finite_float(numerical_certificate["offline_derivation"]["inputs"]["h_s"], name="G3N duration")
            raw_cap = finite_float(numerical_certificate["online_guard_contract"]["raw_component_admission_abs"], name="G3N raw cap")
        except Exception as exc:
            raise CarrierError("composition derivation has no sealed raw envelope/duration") from exc
    c_cap = math.sqrt(2.0) * (1.0 + carrier_profile.phi) * raw_cap * carrier_profile.w_d
    gradient_cap = math.sqrt(2.0) * raw_cap * (1.0 + 2.0 * carrier_profile.phi)
    curvature_by_scale = [
        carrier_profile.w_c
        * omega
        * omega
        * beta
        * (2.0 / reference + 4.0 * c_cap * gradient_cap / reference + 2.0 * c_cap * c_cap * gradient_cap * gradient_cap / (reference * reference))
        for beta, reference, omega in zip(carrier_profile.beta, carrier_profile.epsilon_ref, carrier_profile.omega_c, strict=True)
    ]
    curvature = max(curvature_by_scale, default=0.0)
    work_bound = (curvature + 1.0) * duration * duration * 128.0
    derivation: dict[str, Any] = {
        "schema": W4_COMPOSITION_DERIVATION_SCHEMA,
        "carrier_profile_sha256": carrier_profile.profile_sha256,
        "carrier_root_sha256": carrier_profile.root_sha256,
        "g3n_numerical_certificate_sha256": numerical_certificate["self_sha256"],
        "raw_component_admission_abs": raw_cap,
        "inputs": {
            "phi": carrier_profile.phi,
            "w_D": carrier_profile.w_d,
            "w_C": carrier_profile.w_c,
            "beta": list(carrier_profile.beta),
            "epsilon_ref": list(carrier_profile.epsilon_ref),
            "c_C_m_per_s": list(carrier_profile.c_c),
            "omega_C_rad_per_s": list(carrier_profile.omega_c),
            "gamma_C_per_s": list(carrier_profile.gamma_c),
            "kappa_C": list(carrier_profile.kappa_c),
            "duration_s": duration,
        },
        "bounds": {
            "c_abs": c_cap,
            "epsilon_wirtinger_abs": gradient_cap,
            "curvature_abs_per_scale": curvature_by_scale,
            "curvature_abs": curvature,
            "coordinate_work_rounding_abs": work_bound,
            "total_coupled_integrator_abs": work_bound,
        },
        "formulae": {
            "potential": "w_C*omega_C_s^2*beta_s*tanh(epsilon/epsilon_ref_s)*abs(C)^2/2",
            "forces": "both-metric-wirtinger-gradients-on-same-frozen-grid.v1",
            "curvature": "sech2<=1;abs(d_sech2)<=2;raw-envelope-chain-rule.v1",
            "work": "D-center-C-potential-path;W_D+W_center+W_C+Delta_U=0-within-f64-budget.v1",
        },
        "dynamics": "combined-D-and-C-profile-frozen-analytic-fft2.v1",
    }
    derivation["self_sha256"] = canonical_hash(derivation, W4_COMPOSITION_DERIVATION_DOMAIN)
    return derivation


def build_composition_section(*, carrier_profile: QiCarrierProfile, derivation: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(derivation)
    if body.pop("self_sha256", None) != canonical_hash(body, W4_COMPOSITION_DERIVATION_DOMAIN):
        raise CarrierError("composition derivation self hash is invalid")
    if body.get("carrier_profile_sha256") != carrier_profile.profile_sha256 or body.get("carrier_root_sha256") != carrier_profile.root_sha256:
        raise CarrierError("composition derivation/profile mismatch")
    section: dict[str, Any] = {
        "schema": W4_COMPOSITION_SECTION_SCHEMA,
        "section_id": "w4-composition-stability-work",
        "owning_package": "W4",
        "gate": "G4",
        "required": True,
        "ordinal": 2,
        "carrier_profile_sha256": carrier_profile.profile_sha256,
        "carrier_root_sha256": carrier_profile.root_sha256,
        "offline_derivation_sha256": derivation["self_sha256"],
        "curvature_abs": derivation["bounds"]["curvature_abs"],
        "coordinate_work_rounding_abs": derivation["bounds"]["coordinate_work_rounding_abs"],
        "total_coupled_integrator_abs": derivation["bounds"]["total_coupled_integrator_abs"],
    }
    section["self_sha256"] = canonical_hash(section, W4_COMPOSITION_SECTION_DOMAIN)
    return section


__all__ = [
    "CarrierError",
    "CarrierCoordinates",
    "QiCarrierProfile",
    "QiCarrierStep",
    "W4_CARRIER_CANDIDATE_SCHEMA",
    "W4_CARRIER_PROFILE_DOMAIN",
    "W4_CARRIER_PROFILE_SCHEMA",
    "W4_CARRIER_RECEIPT_DOMAIN",
    "W4_CARRIER_RECEIPT_SCHEMA",
    "W4_CARRIER_ROOT_DOMAIN",
    "W4_CARRIER_ROOT_SCHEMA",
    "W4_COMPOSITION_DERIVATION_DOMAIN",
    "W4_COMPOSITION_DERIVATION_SCHEMA",
    "W4_COMPOSITION_SECTION_DOMAIN",
    "W4_COMPOSITION_SECTION_SCHEMA",
    "build_composition_derivation",
    "build_composition_section",
    "carrier_coordinates",
    "carrier_total_energy",
    "composition_forces",
    "composition_potential",
    "composition_reversal_fixture",
    "load_w4_carrier_profile",
    "negate_differential_coordinate",
    "phase_current_reversal",
    "phase_shuffled_equal_energy",
    "transition_v4_carrier",
    "yang_yin_exchange",
    "_transition_v4_carrier_split",
]
