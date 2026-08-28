"""W4R topological-retention law on the validated W2 periodic FFT2 sheet.

The production law is deliberately small: one smooth bounded potential on the
weighted D/C coordinates, an analytic metric-gradient pullback, and one
conservative callback for the combined W4 split.  Every topology observable is
recomputed from the sole ``[S,9M,B]`` tensor; no winding cache or adaptive
state is kept here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import torch

from cassi_qi_bootstrap import finite_float
from cassi_qi_field import QiFlowGeometryV2, QiFlowStateV3
from cassi_qi_geometry import (
    ey_ei_to_d_c,
    d_c_to_ey_ei,
    vy_vi_to_vd_vc,
    vd_vc_to_vy_vi,
)
from cassi_qi_profile import canonical_hash, load_development_profile


W4R_PROFILE_SCHEMA = "cassi.qi-flow-w4r-topology-profile.v1"
W4R_ROOT_SCHEMA = "cassi.qi-flow-w4r-topology-root.v1"
W4R_RECEIPT_SCHEMA = "cassi.qi-flow-w4r-topology-receipt.v1"
W4R_DERIVATION_SCHEMA = "cassi.qi-flow-w4r-topology-derivation.v1"
W4R_SECTION_SCHEMA = "cassi.qi-flow-w4r-topology-section.v1"
W4R_PROFILE_DOMAIN = "cassi.qi-flow-w4r-topology-profile.v1"
W4R_ROOT_DOMAIN = "cassi.qi-flow-w4r-topology-root.v1"
W4R_RECEIPT_DOMAIN = "cassi.qi-flow-w4r-topology-receipt.v1"
W4R_DERIVATION_DOMAIN = "cassi.qi-flow-w4r-topology-derivation.v1"
W4R_CODEBOOK_DOMAIN = "cassi.qi-flow-w4r-topology-codebook.v1"
W4R_BARRIER_DOMAIN = "cassi.qi-flow-w4r-topology-barrier.v1"
W4R_STATE_DOMAIN = "cassi.qi-flow-w4r-topology-state.v1"
W4R_F64_DOMAIN = "cassi.qi-flow-w4r-f64.v1"


class TopologyError(ValueError):
    """Raised when a W4R profile, state, or identity is not admissible."""


class TopologyTransitionRejected(TopologyError):
    """Raised only by direct primitives; guarded transitions return a step."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _f64_tag(value: float, *, name: str) -> str:
    result = float(value)
    if not math.isfinite(result) or (result == 0.0 and math.copysign(1.0, result) < 0.0):
        raise TopologyError(f"{name} must be finite f64 and not negative zero")
    return "f64:" + struct.pack(">d", result).hex()


def _f64(value: Any, *, name: str, positive: bool = False, nonnegative: bool = False) -> float:
    try:
        result = float(finite_float(value, name=name))
    except Exception as exc:
        raise TopologyError(f"{name} is not a finite scalar") from exc
    if not math.isfinite(result) or (result == 0.0 and math.copysign(1.0, result) < 0.0):
        raise TopologyError(f"{name} must be finite f64 and not negative zero")
    if positive and result <= 0.0:
        raise TopologyError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise TopologyError(f"{name} must be non-negative")
    return result


def _sha256(value: Any, domain: str) -> str:
    return str(canonical_hash(_plain(value), domain))
def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _identity_hash(value: Mapping[str, Any], domain: str, field: str) -> str:
    body = dict(value)
    body.pop(field, None)
    return _sha256(body, domain)


def _state_hash(state: QiFlowStateV3) -> str:
    if not isinstance(state, QiFlowStateV3):
        raise TopologyError("topology state must be QiFlowStateV3")
    raw = state.field.detach().contiguous().cpu().numpy().tobytes(order="C")
    digest = hashlib.sha256()
    encoded = W4R_STATE_DOMAIN.encode("utf-8")
    digest.update(len(encoded).to_bytes(8, "big"))
    digest.update(encoded)
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)
    return digest.hexdigest()


def _geometry_profile(geometry: Any) -> Any:
    if hasattr(geometry, "base_profile") and hasattr(geometry, "active_shapes"):
        return geometry
    nested = getattr(geometry, "geometry_profile", None)
    if nested is not None and hasattr(nested, "base_profile"):
        return nested
    nested = getattr(geometry, "profile", None)
    if nested is not None and hasattr(nested, "base_profile"):
        return nested
    raise TopologyError("W4R requires a validated W2 geometry profile")


def _base_profile(geometry: Any) -> Any:
    return _geometry_profile(geometry).base_profile


def _active_shapes(geometry: Any) -> tuple[tuple[int, int], ...]:
    geometry = _geometry_profile(geometry)
    value = getattr(geometry, "active_shapes", None)
    if value is None:
        payload = getattr(geometry, "payload", {})
        contract = payload.get("geometry_contract", payload.get("field", {}))
        value = contract.get("active_shapes", contract.get("active_shapes_yx"))
    if not isinstance(value, (tuple, list)) or not value:
        raise TopologyError("W2 geometry has no active per-scale shapes")
    result: list[tuple[int, int]] = []
    for index, shape in enumerate(value):
        if not isinstance(shape, (tuple, list)) or len(shape) != 2:
            raise TopologyError(f"scale {index} shape is not [Ny,Nx]")
        ny = int(shape[0]); nx = int(shape[1])
        if ny < 2 or nx < 2:
            raise TopologyError("periodic topology sheets require at least 2x2 sites")
        result.append((ny, nx))
    return tuple(result)


def _scale_count(geometry: Any) -> int:
    shapes = _active_shapes(geometry)
    layout = _base_profile(geometry).state_layout
    declared = int(layout["scale_count"])
    if declared != len(shapes):
        raise TopologyError("W2 scale count disagrees with active shape registry")
    return declared


def _mode_count(geometry: Any) -> int:
    try:
        return int(_base_profile(geometry).state_layout["mode_count"])
    except Exception as exc:
        raise TopologyError("W2 profile has no mode count") from exc


def _metric_cell_area(geometry: Any, scale: int) -> float:
    geometry = _geometry_profile(geometry)
    try:
        value = geometry.base_profile.payload["spatial"]["metric_cell_area"][scale]
    except Exception as exc:
        raise TopologyError(f"missing W2 metric for scale {scale}") from exc
    return _f64(value, name=f"metric cell area {scale}", positive=True)


def _coordinate_transform(geometry: Any) -> tuple[float, float, float]:
    payload = getattr(_base_profile(geometry), "payload", {})
    transform = payload.get("dynamics", {}).get("coordinate_transform", {})
    phi_value = transform.get("phi")
    if phi_value is None:
        # W2/G3 descendants carry the authenticated value in their parent map.
        phi_value = payload.get("dynamics", {}).get("phi")
    if phi_value is None:
        phi_value = payload.get("parent_w1", {}).get("dynamics", {}).get("coordinate_transform", {}).get("phi")
    if phi_value is None:
        raise TopologyError("coordinate transform phi is absent from the authenticated W1 profile")
    phi = _f64(phi_value, name="phi")
    w_d = 1.0 / (1.0 + phi * phi)
    w_c = 1.0 + phi * phi
    if not (w_d > 0.0 and w_c > 0.0 and math.isfinite(w_d) and math.isfinite(w_c)):
        raise TopologyError("D/C metric weights are not positive finite f64 values")
    return phi, w_d, w_c


def _retention_payload(geometry: Any) -> Mapping[str, Any]:
    retention = getattr(_base_profile(geometry), "payload", {}).get("retention")
    if not isinstance(retention, Mapping):
        raise TopologyError("W1 profile has no retention payload")
    return retention


def _canonical_edges(shape: tuple[int, int]) -> tuple[dict[str, Any], ...]:
    ny, nx = shape
    rows: list[dict[str, Any]] = []
    ordinal = 0
    for y in range(ny):
        for x in range(nx):
            source = y * nx + x
            rows.append({
                "ordinal": ordinal,
                "axis": "x",
                "source": [y, x],
                "target": [y, (x + 1) % nx],
                "weight": 1.0,
            })
            ordinal += 1
            rows.append({
                "ordinal": ordinal,
                "axis": "y",
                "source": [y, x],
                "target": [(y + 1) % ny, x],
                "weight": 1.0,
            })
            ordinal += 1
    return tuple(rows)


def _edge_registry_for_shape(geometry: Any, shape: tuple[int, int]) -> tuple[dict[str, Any], ...]:
    retention = _retention_payload(geometry)
    candidate = retention.get("edge_registry", retention.get("edges"))
    if not isinstance(candidate, Mapping):
        raise TopologyError("W2 retention profile has no registered oriented edge registry")
    registry = {str(key): _plain(value) for key, value in candidate.items()}
    declared_hash = registry.pop("self_sha256", None)
    schema = registry.get("schema")
    if schema != "cassi.qi-flow-oriented-edge-registry.v1":
        raise TopologyError("edge registry schema is not the frozen oriented registry")
    computed_hash = _sha256(registry, str(schema))
    if not _is_sha256(declared_hash) or declared_hash != computed_hash:
        raise TopologyError("edge registry self identity is invalid")
    if retention.get("edge_registry_sha256") != computed_hash:
        raise TopologyError("retention edge-registry identity mismatch")
    candidate = registry.get("edges")
    rows: list[dict[str, Any]] = []
    if isinstance(candidate, (tuple, list)):
        ny, nx = shape
        for ordinal, row in enumerate(candidate):
            if not isinstance(row, Mapping):
                raise TopologyError("edge registry row is not a mapping")
            axis = str(row.get("axis", ""))
            source_raw = row.get("source", row.get("source_yx"))
            target_raw = row.get("target", row.get("target_yx"))
            if axis not in {"x", "y"}:
                raise TopologyError("edge registry row has invalid axis")
            if isinstance(source_raw, int) and isinstance(target_raw, int):
                y, x = divmod(int(source_raw), nx)
                ty, tx = divmod(int(target_raw), nx)
            elif isinstance(source_raw, (tuple, list)) and isinstance(target_raw, (tuple, list)) and len(source_raw) == 2 and len(target_raw) == 2:
                y, x = int(source_raw[0]), int(source_raw[1])
                ty, tx = int(target_raw[0]), int(target_raw[1])
            else:
                raise TopologyError("edge registry row has invalid oriented endpoints")
            if not (0 <= y < ny and 0 <= x < nx):
                raise TopologyError("edge registry source is outside the sheet")
            expected = (y, (x + 1) % nx) if axis == "x" else ((y + 1) % ny, x)
            if (ty, tx) != expected:
                raise TopologyError("edge registry is not the exact +x/+y periodic W2 registry")
            rows.append({
                "ordinal": ordinal,
                "axis": axis,
                "source": [y, x],
                "target": [ty, tx],
                "weight": _f64(row.get("weight", 1.0), name=f"edge {ordinal} weight", positive=True),
            })
    else:
        raise TopologyError("W2 retention profile has no registered oriented edge registry")
    expected = _canonical_edges(shape)
    if len(rows) != len(expected):
        raise TopologyError("edge registry count does not match the dynamic periodic sheet")
    seen: set[tuple[int, str, int, int]] = set()
    for row in rows:
        y, x = row["source"]
        key = (int(y) * shape[1] + int(x), row["axis"], int(row["target"][0]), int(row["target"][1]))
        if key in seen:
            raise TopologyError("oriented edge appears more than once")
        seen.add(key)
    return tuple(rows)


def _cycle_registry_for_shape(geometry: Any, shape: tuple[int, int]) -> Mapping[str, Any]:
    retention = _retention_payload(geometry)
    candidate = retention.get("cycle_registry", retention.get("cycles"))
    if not isinstance(candidate, Mapping):
        raise TopologyError("W2 retention profile has no registered cycle/plaquette registry")
    registry = {str(key): _plain(value) for key, value in candidate.items()}
    declared_hash = registry.pop("self_sha256", None)
    schema = registry.get("schema")
    if schema != "cassi.qi-flow-torus-cycle-plaquette-registry.v1":
        raise TopologyError("cycle registry schema is not the frozen torus registry")
    computed_hash = _sha256(registry, str(schema))
    if not _is_sha256(declared_hash) or declared_hash != computed_hash:
        raise TopologyError("cycle registry self identity is invalid")
    if retention.get("cycle_registry_sha256") != computed_hash:
        raise TopologyError("retention cycle-registry identity mismatch")
    ny, nx = shape
    expected_x = [[y * nx + x for x in range(nx)] for y in range(ny)]
    expected_y = [[y * nx + x for y in range(ny)] for x in range(nx)]
    expected_plaquettes = [y * nx + x for y in range(ny) for x in range(nx)]
    if (
        registry.get("sheet_shape") != [ny, nx]
        or registry.get("x_cycles") != expected_x
        or registry.get("y_cycles") != expected_y
        or registry.get("plaquette_origins") != expected_plaquettes
        or registry.get("orientation") != "counterclockwise-+x-+y.v1"
    ):
        raise TopologyError("cycle registry is not the complete oriented periodic torus")
    return MappingProxyType({**registry, "self_sha256": computed_hash})


def _source_identity(value: Any) -> str | None:
    for name in ("profile_sha256", "root_sha256", "contract_root_sha256", "self_sha256"):
        candidate = getattr(value, name, None)
        if _is_sha256(candidate):
            return str(candidate)
    if isinstance(value, Mapping):
        for name in ("profile_sha256", "root_sha256", "contract_root_sha256", "self_sha256"):
            candidate = value.get(name)
            if _is_sha256(candidate):
                return str(candidate)
    return None


def _w2_parent_identities(geometry: Any) -> dict[str, Any]:
    geometry = _geometry_profile(geometry)
    payload = getattr(geometry, "payload", {})
    root = getattr(geometry, "contract_root", {})
    return {
        "w2_profile_sha256": _source_identity(geometry),
        "w2_contract_root_sha256": _source_identity(root) or getattr(geometry, "contract_root_sha256", None),
        "w2_geometry_contract_sha256": getattr(geometry, "geometry_contract_sha256", payload.get("geometry_contract_sha256")),
        "w2_operator_semantic_sha256": getattr(geometry, "operator_semantic_sha256", payload.get("operator_semantic_sha256")),
        "family": payload.get("family", "periodic-fft2.v1"),
    }


def _certificate_identities(certificate: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(certificate, Mapping):
        return {}
    return {
        "g3n_certificate_sha256": certificate.get("self_sha256"),
        "g3n_profile_sha256": certificate.get("profile_sha256"),
        "g3n_contract_root_sha256": certificate.get("contract_root_sha256"),
        "g3n_transport_semantic_sha256": certificate.get("transport_semantic_sha256"),
    }


def _codebook_payload(shape: tuple[int, int], edges: Sequence[Mapping[str, Any]], cycles: Mapping[str, Any], *, a: float, b: float) -> dict[str, Any]:
    return {
        "schema": "cassi.qi-flow-w4r-topology-codebook.v1",
        "law_id": "topological-v1",
        "sheet_shape_yx": list(shape),
        "edge_registry": [_plain(row) for row in edges],
        "cycle_registry": _plain(cycles),
        "weighted_rotation": {"a_topo": _f64_tag(a, name="a_topo"), "b_topo": _f64_tag(b, name="b_topo")},
        "sector_vector": "(n_x[row], n_y[column], p[row,column])",
        "edge_count_policy": "each-oriented-edge-exactly-once.v1",
    }


def _barrier_payload(*, E: float, lambda_core: float, rho_ring: float, rho_topo: float, delta_h_min: float, radial_min: float) -> dict[str, Any]:
    return {
        "schema": "cassi.qi-flow-w4r-barrier-certificate.v1",
        "law_id": "topological-v1",
        "potential": "E_topo*(lambda_ph*U_phase+lambda_core*U_core)",
        "core": "((|psi|^2-rho_ring^2)/(|psi|^2+rho_ring^2))^2",
        "smooth_radius": "sqrt(|psi|^2+r_core^2)",
        "rho_ring": _f64_tag(rho_ring, name="rho_ring"),
        "rho_topo": _f64_tag(rho_topo, name="rho_topo"),
        "radial_curvature_min": _f64_tag(radial_min, name="radial_curvature_min"),
        "Delta_H_topo_min": _f64_tag(delta_h_min, name="Delta_H_topo_min"),
        "potential_upper_bound": _f64_tag(E * (2.0 * 1.0 + lambda_core), name="potential_upper_bound"),
        "guard_policy": "reject-before-commit.v1",
    }


@dataclass(frozen=True)
class QiTopologyProfile:
    payload: Mapping[str, Any]
    root: Mapping[str, Any]
    profile_sha256: str
    root_sha256: str
    mode: str
    slow_scale: int
    a_topo: float
    b_topo: float
    phi: float
    w_d: float
    w_c: float
    E_topo: float
    lambda_ph: float
    lambda_core: float
    r_core: float
    rho_ring: float
    rho_topo: float
    delta_topo: float
    delta_topo_int: float
    delta_h_min: float
    radial_curvature_min: float
    duration: float
    edge_registry: tuple[Mapping[str, Any], ...]
    cycle_registry: Mapping[str, Any]
    metric_diagonal: tuple[float, ...] | None
    topology_codebook_sha256: str | None
    barrier_certificate_sha256: str | None
    reset_operator_sha256: str
    parent_identities: Mapping[str, Any]

    @property
    def schema(self) -> str:
        return W4R_PROFILE_SCHEMA

    @property
    def law_id(self) -> str:
        return "topological-v1" if self.mode == "topological-v1" else "fading-v1"


@dataclass(frozen=True)
class QiTopologicalRetentionLaw:
    """Immutable W4R law and its bound W2 geometry."""

    profile: QiTopologyProfile
    geometry: Any

    @classmethod
    def bind(cls, profile: QiTopologyProfile, geometry: Any) -> "QiTopologicalRetentionLaw":
        return cls(profile, _geometry_profile(geometry))

    def potential(self, state: QiFlowStateV3) -> float:
        return topological_potential(state, geometry=self.geometry, profile=self.profile)

    def force(self, state: QiFlowStateV3) -> Mapping[str, tuple[torch.Tensor, ...]]:
        return topological_force(state, geometry=self.geometry, profile=self.profile)

    def diagnostics(self, state: QiFlowStateV3) -> Mapping[str, Any]:
        return topology_diagnostics(state, geometry=self.geometry, profile=self.profile)
    def transition_w4r_topology(
        self,
        state: QiFlowStateV3,
        *,
        numerical_certificate: Mapping[str, Any],
        transport_profile: Any | None = None,
        carrier_profile: Any | None = None,
        duration_s: float | None = None,
        potential_enabled: bool = True,
        transition_kind: str = "timed",
        reset_authorization: Mapping[str, Any] | None = None,
    ) -> "QiW4RStep":
        return transition_w4r_topology(
            state,
            geometry_profile=self.geometry,
            topology_profile=self.profile,
            numerical_certificate=numerical_certificate,
            transport_profile=transport_profile,
            carrier_profile=carrier_profile,
            duration_s=duration_s,
            potential_enabled=potential_enabled,
            transition_kind=transition_kind,
            reset_authorization=reset_authorization,
        )

    def additional_force(
        self,
        state: QiFlowStateV3,
        geometry: Any,
        carrier_profile: Any,
        coordinates: Any,
    ) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
        """Carrier-split callback: one force evaluation at each local kick."""
        del carrier_profile
        return _force_callback(self.profile, state, geometry, coordinates)

    @staticmethod
    def identity_center_map(state: QiFlowStateV3, geometry: Any, carrier_profile: Any, coordinates: Any) -> Any:
        del state, geometry, carrier_profile
        return coordinates


# The callback descriptor is useful to W5 without exposing mutable law state.
def make_topological_force_callback(profile: QiTopologyProfile, geometry: Any) -> Callable[..., tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]]:
    law = QiTopologicalRetentionLaw.bind(profile, geometry)
    return law.additional_force


def _profile_float(retention: Mapping[str, Any], names: Sequence[str], default: float, *, positive: bool = False, nonnegative: bool = False) -> float:
    for name in names:
        if name in retention:
            return _f64(retention[name], name=name, positive=positive, nonnegative=nonnegative)
    return _f64(default, name=names[0], positive=positive, nonnegative=nonnegative)


def load_w4r_topology_profile(
    *,
    geometry: Any,
    mode: str = "topological-v1",
    carrier_profile: Any | None = None,
    numerical_certificate: Mapping[str, Any] | None = None,
) -> QiTopologyProfile:
    """Derive a frozen topological extension from current W2/W1 material."""
    geometry = _geometry_profile(geometry)
    if mode not in {"topological-v1", "fading-v1"}:
        raise TopologyError("W4R mode must be topological-v1 or explicit fading-v1 comparator")
    shapes = _active_shapes(geometry)
    slow_scale = len(shapes) - 1
    shape = shapes[slow_scale]
    edges = _edge_registry_for_shape(geometry, shape)
    cycles = _cycle_registry_for_shape(geometry, shape)
    phi, w_d, w_c = _coordinate_transform(geometry)
    retention = _retention_payload(geometry)
    E = _profile_float(retention, ("E_topo", "topological_energy_scale", "E"), 0.01, positive=True)
    lambda_ph = _profile_float(retention, ("lambda_ph", "phase_weight", "lambda_phase"), 0.5, nonnegative=True)
    lambda_core = _profile_float(retention, ("lambda_core", "core_weight"), 0.5, nonnegative=True)
    r_core = _profile_float(retention, ("r_core", "core_radius"), 0.01, positive=True)
    rho_ring = _profile_float(retention, ("rho_ring", "ring_amplitude"), 0.1, positive=True)
    rho_topo = _profile_float(retention, ("rho_topo", "rho_floor", "topological_amplitude_floor"), max(rho_ring * 0.2, 1.0e-6), positive=True)
    delta_topo = _profile_float(retention, ("delta_topo_rad", "delta_topo", "phase_branch_margin"), 0.05, positive=True)
    delta_topo_int = _profile_float(retention, ("delta_topo_int", "integer_margin"), 0.25, positive=True)
    delta_h_min = _profile_float(retention, ("Delta_H_topo_min", "delta_h_min", "barrier_min"), E * lambda_core * 0.25, positive=True)
    radial_min = _profile_float(retention, ("radial_curvature_min", "radial_curvature_bound"), E * lambda_core / max(rho_ring * rho_ring, 1.0e-30), positive=True)
    duration = _profile_float(retention, ("duration", "h_s", "h"), 0.01, positive=True)
    if not (0.0 <= rho_topo < rho_ring and 0.0 < delta_topo < math.pi and 0.0 < delta_topo_int < 0.5):
        raise TopologyError("topological guard thresholds are inconsistent")
    a = 0.0
    b = 1.0
    codebook = _codebook_payload(shape, edges, cycles, a=a, b=b)
    barrier = _barrier_payload(E=E, lambda_core=lambda_core, rho_ring=rho_ring, rho_topo=rho_topo, delta_h_min=delta_h_min, radial_min=radial_min)
    reset_body = {
        "operator_id": "authenticated-topological-retention-reset.v1",
        "target": "psi_topo=rho_ring*exp(i*theta0);V_psi=0",
        "preserve": ["chi_topo", "V_chi_topo"],
    }
    derived_codebook = _sha256(codebook, W4R_CODEBOOK_DOMAIN)
    derived_barrier = _sha256(barrier, W4R_BARRIER_DOMAIN)
    derived_reset = _sha256(reset_body, "cassi.qi-flow.retention-reset-operator.v1")
    configured_codebook = retention.get("topology_codebook_sha256")
    configured_barrier = retention.get("barrier_certificate_sha256")
    configured_reset = retention.get("reset_operator_sha256")
    if configured_codebook is not None and (not _is_sha256(configured_codebook) or str(configured_codebook) != derived_codebook):
        raise TopologyError("registered topology codebook identity disagrees with derived W4R law")
    if configured_barrier is not None and (not _is_sha256(configured_barrier) or str(configured_barrier) != derived_barrier):
        raise TopologyError("registered barrier identity disagrees with derived W4R law")
    if configured_reset is not None and (not _is_sha256(configured_reset) or str(configured_reset) != derived_reset):
        raise TopologyError("registered reset identity disagrees with the frozen reset operator")
    topology_codebook_sha256 = derived_codebook
    barrier_certificate_sha256 = derived_barrier
    reset_operator_sha256 = derived_reset
    metric_values: tuple[float, ...] | None = None
    metric_payload = retention.get("metric_diagonal")
    if isinstance(metric_payload, (tuple, list)):
        metric_values = tuple(_f64(value, name="metric diagonal", positive=True) for value in metric_payload)
        if len(metric_values) != shape[0] * shape[1]:
            raise TopologyError("retention metric diagonal has the wrong dynamic site count")
    parents = _w2_parent_identities(geometry)
    parents.update({
        "carrier_profile_sha256": _source_identity(carrier_profile),
        **_certificate_identities(numerical_certificate),
    })
    payload: dict[str, Any] = {
        "schema": W4R_PROFILE_SCHEMA,
        "law_id": "topological-v1" if mode == "topological-v1" else "fading-v1",
        "mode": mode,
        "slow_scale": slow_scale,
        "active_shape_yx": list(shape),
        "active_shapes_yx": [list(item) for item in shapes],
        "weighted_rotation": {"a_topo": _f64_tag(a, name="a_topo"), "b_topo": _f64_tag(b, name="b_topo")},
        "d_c_transform": {"phi": _f64_tag(phi, name="phi"), "w_D": _f64_tag(w_d, name="w_D"), "w_C": _f64_tag(w_c, name="w_c")},
        "potential": {
            "E_topo": _f64_tag(E, name="E_topo"),
            "lambda_ph": _f64_tag(lambda_ph, name="lambda_ph"),
            "lambda_core": _f64_tag(lambda_core, name="lambda_core"),
            "r_core": _f64_tag(r_core, name="r_core"),
            "rho_ring": _f64_tag(rho_ring, name="rho_ring"),
            "rho_topo": _f64_tag(rho_topo, name="rho_topo"),
        },
        "guards": {
            "delta_topo": _f64_tag(delta_topo, name="delta_topo"),
            "delta_topo_int": _f64_tag(delta_topo_int, name="delta_topo_int"),
            "radial_curvature_min": _f64_tag(radial_min, name="radial_curvature_min"),
            "Delta_H_topo_min": _f64_tag(delta_h_min, name="Delta_H_topo_min"),
        },
        "integration": {
            "duration": _f64_tag(duration, name="duration"),
            "split": "combined-w4-dc-symmetric-seven-stage.v1",
            "topology_kick": "symmetric-kdk-force-in-both-local-half-kicks.v1",
        },
        "edge_registry": [_plain(row) for row in edges],
        "cycle_registry": _plain(cycles),
        "metric_diagonal": [_f64_tag(value, name="metric diagonal") for value in metric_values] if metric_values is not None else None,
        "topology_codebook_sha256": topology_codebook_sha256,
        "barrier_certificate_sha256": barrier_certificate_sha256,
        "reset_operator_sha256": reset_operator_sha256,
        "parents": _plain(parents),
        "additional_state": False,
    }
    payload["profile_sha256"] = _identity_hash(payload, W4R_PROFILE_DOMAIN, "profile_sha256")
    root: dict[str, Any] = {
        "schema": W4R_ROOT_SCHEMA,
        "law_id": payload["law_id"],
        "profile_sha256": payload["profile_sha256"],
        "parents": _plain(parents),
        "topology_codebook_sha256": topology_codebook_sha256,
        "barrier_certificate_sha256": barrier_certificate_sha256,
        "reset_operator_sha256": reset_operator_sha256,
        "shape_yx": list(shape),
    }
    root["self_sha256"] = _identity_hash(root, W4R_ROOT_DOMAIN, "self_sha256")
    return QiTopologyProfile(
        MappingProxyType(payload), MappingProxyType(root), str(payload["profile_sha256"]), str(root["self_sha256"]), mode, slow_scale, a, b, phi, w_d, w_c, E, lambda_ph, lambda_core, r_core, rho_ring, rho_topo, delta_topo, delta_topo_int, delta_h_min, radial_min, duration, tuple(MappingProxyType(dict(row)) for row in edges), MappingProxyType(dict(cycles)), metric_values, topology_codebook_sha256, barrier_certificate_sha256, reset_operator_sha256, MappingProxyType(parents)
    )


def _validate_profile(profile: QiTopologyProfile, geometry: Any) -> None:
    if not isinstance(profile, QiTopologyProfile):
        raise TopologyError("topology_profile must be QiTopologyProfile")
    geometry = _geometry_profile(geometry)
    if profile.mode not in {"topological-v1", "fading-v1"}:
        raise TopologyError("unknown W4R mode")
    if profile.slow_scale != _scale_count(geometry) - 1:
        raise TopologyError("topology slow scale is not the current slow W2 scale")
    shape = _active_shapes(geometry)[profile.slow_scale]
    if tuple(profile.payload.get("active_shape_yx", ())) != shape:
        raise TopologyError("profile shape is not bound to current W2 geometry")
    if profile.a_topo != 0.0 or profile.b_topo != 1.0:
        raise TopologyError("production rotation must be weighted a=0,b=1")
    if profile.mode == "topological-v1" and (not _is_sha256(profile.topology_codebook_sha256) or not _is_sha256(profile.barrier_certificate_sha256)):
        raise TopologyError("topological-v1 requires concrete codebook and barrier identities")
    if _identity_hash(dict(profile.root), W4R_ROOT_DOMAIN, "self_sha256") != profile.root_sha256:
        raise TopologyError("topology root identity mismatch")
    payload = dict(profile.payload)
    if _identity_hash(payload, W4R_PROFILE_DOMAIN, "profile_sha256") != profile.profile_sha256:
        raise TopologyError("topology profile identity mismatch")
    current = _w2_parent_identities(geometry)
    for key in ("w2_profile_sha256", "w2_contract_root_sha256", "w2_geometry_contract_sha256", "w2_operator_semantic_sha256"):
        bound = profile.parent_identities.get(key)
        now = current.get(key)
        if _is_sha256(bound) and _is_sha256(now) and bound != now:
            raise TopologyError(f"topology profile {key} disagrees with current W2 geometry")
    expected_edges = _edge_registry_for_shape(geometry, shape)
    if _plain(profile.edge_registry) != _plain(expected_edges):
        raise TopologyError("topology profile edge registry disagrees with current W2 geometry")


def _surface(state: QiFlowStateV3, geometry: Any) -> QiFlowGeometryV2:
    geometry = _geometry_profile(geometry)
    if not isinstance(state, QiFlowStateV3):
        raise TopologyError("topology requires one QiFlowStateV3")
    try:
        state.validate(geometry.base_profile)
        return QiFlowGeometryV2(state, geometry)
    except Exception as exc:
        raise TopologyError(f"invalid W2-bound QiFlowStateV3: {type(exc).__name__}: {exc}") from exc


def _coordinates_from_state(state: QiFlowStateV3, geometry: Any, scale: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    surface = _surface(state, geometry)
    ey = torch.complex(surface.component_grid(scale, 0), surface.component_grid(scale, 1))
    ei = torch.complex(surface.component_grid(scale, 2), surface.component_grid(scale, 3))
    vy = torch.complex(surface.component_grid(scale, 4), surface.component_grid(scale, 5))
    vi = torch.complex(surface.component_grid(scale, 6), surface.component_grid(scale, 7))
    phi, w_d, _ = _coordinate_transform(geometry)
    d, c = ey - phi * ei, (phi * ey + ei) * w_d
    vd, vc = vy - phi * vi, (phi * vy + vi) * w_d
    return d.contiguous(), c.contiguous(), vd.contiguous(), vc.contiguous()


def _coordinates_from_carrier(coordinates: Any, geometry: Any, scale: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor] | None:
    if coordinates is None:
        return None
    names = ("d", "c", "vd", "vc")
    if not all(hasattr(coordinates, name) for name in names):
        return None
    try:
        values = tuple(getattr(coordinates, name)[scale] for name in names)
    except Exception:
        return None
    if all(isinstance(value, torch.Tensor) and value.is_complex() and value.dtype == torch.complex128 for value in values):
        return tuple(value.contiguous() for value in values)  # type: ignore[return-value]
    return None


def _rotated(d: torch.Tensor, c: torch.Tensor, vd: torch.Tensor | None, vc: torch.Tensor | None, profile: QiTopologyProfile) -> tuple[torch.Tensor, ...]:
    sd = math.sqrt(profile.w_d)
    sc = math.sqrt(profile.w_c)
    psi = profile.a_topo * sd * d + profile.b_topo * sc * c
    chi = -profile.b_topo * sd * d + profile.a_topo * sc * c
    if vd is None or vc is None:
        return psi.contiguous(), chi.contiguous()
    vpsi = profile.a_topo * sd * vd + profile.b_topo * sc * vc
    vchi = -profile.b_topo * sd * vd + profile.a_topo * sc * vc
    return psi.contiguous(), chi.contiguous(), vpsi.contiguous(), vchi.contiguous()


def _metric_vector(profile: QiTopologyProfile, geometry: Any, shape: tuple[int, int], *, device: torch.device) -> torch.Tensor:
    count = shape[0] * shape[1]
    if profile.metric_diagonal is not None:
        values = profile.metric_diagonal
    else:
        values = tuple(_metric_cell_area(geometry, profile.slow_scale) for _ in range(count))
    if len(values) != count:
        raise TopologyError("metric diagonal does not match dynamic topology sheet")
    return torch.tensor(values, dtype=torch.float64, device=device).reshape(shape).contiguous()


def _edge_indices(profile: QiTopologyProfile, shape: tuple[int, int], *, device: torch.device) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    sources: list[int] = []
    targets: list[int] = []
    weights: list[float] = []
    ny, nx = shape
    for row in profile.edge_registry:
        y, x = row["source"]; ty, tx = row["target"]
        sources.append(int(y) * nx + int(x)); targets.append(int(ty) * nx + int(tx)); weights.append(_f64(row["weight"], name="edge weight", positive=True))
    if len(sources) != 2 * ny * nx:
        raise TopologyError("edge registry does not contain exactly one +x/+y edge per site")
    return torch.tensor(sources, dtype=torch.long, device=device), torch.tensor(targets, dtype=torch.long, device=device), torch.tensor(weights, dtype=torch.float64, device=device)


def _smooth_phase(psi: torch.Tensor, profile: QiTopologyProfile) -> torch.Tensor:
    q = psi.real.square() + psi.imag.square()
    return psi / torch.sqrt(q + profile.r_core * profile.r_core)


def _potential_tensor(psi: torch.Tensor, *, geometry: Any, profile: QiTopologyProfile) -> torch.Tensor:
    shape = tuple(int(value) for value in psi.shape[:2])
    flat = psi.reshape(shape[0] * shape[1], psi.shape[-1])
    metric = _metric_vector(profile, geometry, shape, device=psi.device).reshape(-1, 1)
    source, target, edge_weight = _edge_indices(profile, shape, device=psi.device)
    smooth = _smooth_phase(psi, profile).reshape_as(flat)
    phase = (1.0 - (smooth[source].conj() * smooth[target]).real)
    # Metric-normalised phase energy counts each oriented edge exactly once.
    edge_norm = edge_weight.sum()
    if not (float(edge_norm.item()) > 0.0 and math.isfinite(float(edge_norm.item()))):
        raise TopologyError("topology edge weights have no positive normalisation")
    phase_energy = (edge_weight.reshape(-1, 1) * phase).sum(dim=0) / edge_norm
    q = flat.real.square() + flat.imag.square()
    rho2 = profile.rho_ring * profile.rho_ring
    core = ((q - rho2) / (q + rho2)).square()
    core_energy = (metric * core).sum(dim=0) / metric.sum()
    return (profile.E_topo * (profile.lambda_ph * phase_energy + profile.lambda_core * core_energy)).contiguous()


def topological_potential(state: QiFlowStateV3, *, geometry: Any, profile: QiTopologyProfile) -> float:
    """Return the exact f64 sum of U_topo over all batch lanes."""
    _validate_profile(profile, geometry)
    if profile.mode == "fading-v1":
        return 0.0
    d, c, _, _ = _coordinates_from_state(state, geometry, profile.slow_scale)
    psi, _ = _rotated(d, c, None, None, profile)
    values = _potential_tensor(psi, geometry=geometry, profile=profile)
    result = float(values.sum().item())
    if not math.isfinite(result):
        raise TopologyError("topological potential is non-finite")
    return 0.0 if result == 0.0 else result


def _force_for_coordinates(psi: torch.Tensor, *, geometry: Any, profile: QiTopologyProfile) -> torch.Tensor:
    shape = tuple(int(value) for value in psi.shape[:2])
    flat = psi.reshape(shape[0] * shape[1], psi.shape[-1])
    metric = _metric_vector(profile, geometry, shape, device=psi.device).reshape(-1, 1)
    source, target, edge_weight = _edge_indices(profile, shape, device=psi.device)
    q = flat.real.square() + flat.imag.square()
    radius = torch.sqrt(q + profile.r_core * profile.r_core)
    smooth = flat / radius
    gradient = torch.zeros_like(flat)
    for edge in range(int(source.numel())):
        i = int(source[edge].item()); j = int(target[edge].item()); weight = edge_weight[edge]
        ri3 = radius[i].square() * radius[i]
        rj3 = radius[j].square() * radius[j]
        term_i = ((q[i] + 2.0 * profile.r_core * profile.r_core) * smooth[j] - flat[i].square() * smooth[j].conj()) / (4.0 * ri3)
        term_j = ((q[j] + 2.0 * profile.r_core * profile.r_core) * smooth[i] - flat[j].square() * smooth[i].conj()) / (4.0 * rj3)
        gradient[i] = gradient[i] - weight * term_i / edge_weight.sum()
        gradient[j] = gradient[j] - weight * term_j / edge_weight.sum()
    rho2 = profile.rho_ring * profile.rho_ring
    core_derivative = 4.0 * rho2 * (q - rho2) / (q + rho2).pow(3)
    gradient = profile.E_topo * (profile.lambda_ph * gradient + profile.lambda_core * metric * core_derivative * flat / metric.sum())
    metric_gradient = gradient / metric
    # Wirtinger pullback through weighted orthogonal D/C -> psi/chi rotation.
    force_psi = metric_gradient
    fd = (-2.0 * profile.a_topo * force_psi / math.sqrt(profile.w_d)).reshape(shape[0], shape[1], -1)
    fc = (-2.0 * profile.b_topo * force_psi / math.sqrt(profile.w_c)).reshape(shape[0], shape[1], -1)
    return fd.contiguous(), fc.contiguous()


def topological_force(state: QiFlowStateV3, *, geometry: Any, profile: QiTopologyProfile) -> Mapping[str, tuple[torch.Tensor, ...]]:
    """Return metric-gradient forces for every scale, with only slow scale active."""
    _validate_profile(profile, geometry)
    geometry = _geometry_profile(geometry)
    scale_count = _scale_count(geometry)
    d_forces: list[torch.Tensor] = []
    c_forces: list[torch.Tensor] = []
    for scale, shape in enumerate(_active_shapes(geometry)):
        if scale != profile.slow_scale or profile.mode == "fading-v1":
            d, c, _, _ = _coordinates_from_state(state, geometry, scale)
            d_forces.append(torch.zeros_like(d)); c_forces.append(torch.zeros_like(c))
            continue
        d, c, _, _ = _coordinates_from_state(state, geometry, scale)
        psi, _ = _rotated(d, c, None, None, profile)
        fd, fc = _force_for_coordinates(psi, geometry=geometry, profile=profile)
        d_forces.append(fd); c_forces.append(fc)
    if len(d_forces) != scale_count:
        raise TopologyError("force scale count mismatch")
    return MappingProxyType({"D": tuple(d_forces), "C": tuple(c_forces), "d": tuple(d_forces), "c": tuple(c_forces)})


def _phase_edge_arrays(psi: torch.Tensor, profile: QiTopologyProfile) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    shape = (int(psi.shape[0]), int(psi.shape[1]))
    ny, nx = shape
    phase = torch.zeros((ny, nx, psi.shape[-1]), dtype=torch.float64, device=psi.device)
    dx = torch.zeros_like(phase); dy = torch.zeros_like(phase)
    for row in profile.edge_registry:
        y, x = row["source"]; ty, tx = row["target"]
        delta = torch.angle(psi[y, x].conj() * psi[ty, tx])
        phase[y, x] = delta
        if row["axis"] == "x":
            dx[y, x] = delta
        else:
            dy[y, x] = delta
    plaquette = dx + torch.roll(dy, shifts=-1, dims=1) - torch.roll(dx, shifts=-1, dims=0) - dy
    return dx, dy, plaquette


def _nested(values: torch.Tensor, *, integer: bool = False) -> Any:
    detached = values.detach().cpu()
    if values.ndim == 0:
        value = detached.item()
        return int(value) if integer else (0.0 if float(value) == 0.0 else float(value))
    if values.ndim == 1:
        result = []
        for value in detached:
            scalar = value.item()
            result.append(int(scalar) if integer else (0.0 if float(scalar) == 0.0 else float(scalar)))
        return result
    return [_nested(value, integer=integer) for value in detached]


def _sector_vectors(dx: torch.Tensor, dy: torch.Tensor, plaquette: torch.Tensor, profile: QiTopologyProfile) -> tuple[list[dict[str, Any]], torch.Tensor, torch.Tensor, torch.Tensor]:
    twopi = 2.0 * math.pi
    nx_raw = dx.sum(dim=1) / twopi  # [Ny,B]
    ny_raw = dy.sum(dim=0) / twopi  # [Nx,B]
    p_raw = plaquette / twopi
    nx_round = torch.round(nx_raw); ny_round = torch.round(ny_raw); p_round = torch.round(p_raw)
    vectors: list[dict[str, Any]] = []
    batch = int(dx.shape[-1])
    for lane in range(batch):
        vectors.append({"n_x": [int(v) for v in nx_round[:, lane].detach().cpu().tolist()], "n_y": [int(v) for v in ny_round[:, lane].detach().cpu().tolist()], "p": [[int(v) for v in row] for row in p_round[:, :, lane].detach().cpu().tolist()]})
    return vectors, nx_raw, ny_raw, p_raw


def topology_diagnostics(state: QiFlowStateV3, *, geometry: Any, profile: QiTopologyProfile) -> Mapping[str, Any]:
    """Derive amplitude, branch, integer, cycle, plaquette, and torus guards."""
    _validate_profile(profile, geometry)
    geometry = _geometry_profile(geometry)
    d, c, vd, vc = _coordinates_from_state(state, geometry, profile.slow_scale)
    psi, chi, vpsi, vchi = _rotated(d, c, vd, vc, profile)
    amplitude = torch.sqrt(psi.real.square() + psi.imag.square())
    amplitude_min = float(amplitude.min().item())
    batch = int(psi.shape[-1])
    valid_amplitude = amplitude >= profile.rho_topo
    valid_by_lane = valid_amplitude.reshape(-1, batch).all(dim=0)
    base: dict[str, Any] = {
        "schema": "cassi.qi-flow-w4r-topology-diagnostics.v1",
        "status": "INVALID",
        "mode": profile.mode,
        "law_id": profile.law_id,
        "slow_scale": profile.slow_scale,
        "shape_yx": [int(psi.shape[0]), int(psi.shape[1])],
        "batch_lanes": batch,
        "amplitude_min": 0.0 if amplitude_min == 0.0 else amplitude_min,
        "amplitude_floor": profile.rho_topo,
        "amplitude_margin": amplitude_min - profile.rho_topo,
        "phase_interval_radius": 0.0,
        "branch_margin_min": None,
        "integer_margin_min": None,
        "valid_by_lane": [bool(v) for v in valid_by_lane.detach().cpu().tolist()],
        "sector_vector": [None for _ in range(batch)],
        "cycle_x": None,
        "cycle_y": None,
        "plaquette": None,
        "torus_algebra": None,
        "reason": "amplitude-floor",
        "potential": 0.0,
        "phase_current": _nested((psi.conj() * vpsi).imag.sum(dim=(0, 1))),
        "chi_current": _nested((chi.conj() * vchi).imag.sum(dim=(0, 1))),
    }
    if not bool(valid_amplitude.all().item()):
        base["valid_by_lane"] = [bool(v) for v in valid_by_lane.detach().cpu().tolist()]
        return MappingProxyType(base)
    dx, dy, plaquette = _phase_edge_arrays(psi, profile)
    branch_margin = math.pi - torch.maximum(dx.abs(), dy.abs())
    branch_valid = branch_margin >= profile.delta_topo
    vectors, nx_raw, ny_raw, p_raw = _sector_vectors(dx, dy, plaquette, profile)
    nx_error = (nx_raw - torch.round(nx_raw)).abs()
    ny_error = (ny_raw - torch.round(ny_raw)).abs()
    p_error = (p_raw - torch.round(p_raw)).abs()
    nx_integer_valid = nx_error <= profile.delta_topo_int
    ny_integer_valid = ny_error <= profile.delta_topo_int
    p_integer_valid = p_error <= profile.delta_topo_int
    # Exact torus identities are checked on the unrounded vector and then on
    # the accepted integer vector; no sector is inferred from one scalar sum.
    algebra_x = nx_raw[:-1] - nx_raw[1:] - p_raw.sum(dim=1)[:-1]
    algebra_y = ny_raw[1:] - ny_raw[:-1] - p_raw.sum(dim=0)[:-1]
    algebra_total = p_raw.sum(dim=(0, 1))
    algebra_error = torch.zeros((batch,), dtype=torch.float64, device=psi.device)
    if algebra_x.numel(): algebra_error = torch.maximum(algebra_error, algebra_x.abs().reshape(-1, batch).max(dim=0).values)
    if algebra_y.numel(): algebra_error = torch.maximum(algebra_error, algebra_y.abs().reshape(-1, batch).max(dim=0).values)
    algebra_error = torch.maximum(algebra_error, algebra_total.abs())
    algebra_valid = algebra_error <= max(profile.delta_topo_int * 8.0, 1.0e-12)
    edge_valid_by_lane = branch_valid.reshape(-1, batch).all(dim=0)
    integer_valid_by_lane = (
        nx_integer_valid.all(dim=0)
        & ny_integer_valid.all(dim=0)
        & p_integer_valid.reshape(-1, batch).all(dim=0)
    )
    valid_by_lane = edge_valid_by_lane & integer_valid_by_lane & algebra_valid
    branch_min = float(branch_margin.min().item())
    integer_error_max = torch.maximum(
        torch.maximum(nx_error.max(dim=0).values, ny_error.max(dim=0).values),
        p_error.reshape(-1, batch).max(dim=0).values,
    )
    integer_min = float((profile.delta_topo_int - integer_error_max).min().item())
    base.update({
        "status": "VALID" if bool(valid_by_lane.all().item()) else "INVALID",
        "reason": "ok" if bool(valid_by_lane.all().item()) else ("branch-cut" if not bool(edge_valid_by_lane.all().item()) else ("integer-guard" if not bool(integer_valid_by_lane.all().item()) else "torus-algebra")),
        "valid_by_lane": [bool(v) for v in valid_by_lane.detach().cpu().tolist()],
        "branch_margin_min": 0.0 if branch_min == 0.0 else branch_min,
        "integer_margin_min": 0.0 if integer_min == 0.0 else integer_min,
        "cycle_x": _nested(nx_raw),
        "cycle_y": _nested(ny_raw),
        "plaquette": _nested(p_raw),
        "sector_vector": vectors,
        "torus_algebra": {"residual_max": _nested(algebra_error), "valid": [bool(v) for v in algebra_valid.detach().cpu().tolist()]},
        "phase_x": _nested(dx),
        "phase_y": _nested(dy),
        "potential": topological_potential(state, geometry=geometry, profile=profile) if profile.mode == "topological-v1" else 0.0,
        "edge_count": len(profile.edge_registry),
        "edge_weight_sum": float(sum(_f64(row["weight"], name="edge weight") for row in profile.edge_registry)),
    })
    # Sector identity remains the complete cycle/plaquette vector above.
    base["current_x"] = _nested((psi.conj() * vpsi).imag.sum(dim=0))
    base["current_y"] = _nested((chi.conj() * vchi).imag.sum(dim=0))
    base["vortex_density"] = _nested(p_raw)
    return MappingProxyType(base)


def radial_curvature(profile: QiTopologyProfile, radius: float | None = None) -> float:
    """Analytic second radial derivative of the smooth core term."""
    radius = profile.rho_ring if radius is None else _f64(radius, name="radius", nonnegative=True)
    q = radius * radius
    R = profile.rho_ring * profile.rho_ring
    value = 8.0 * R * (-3.0 * q * q + 8.0 * R * q - R * R) / (q + R) ** 4
    return profile.E_topo * profile.lambda_core * value


def radial_curvature_bound(*, geometry: Any, profile: QiTopologyProfile) -> Mapping[str, Any]:
    _validate_profile(profile, geometry)
    at_ring = radial_curvature(profile, profile.rho_ring)
    return MappingProxyType({"schema": "cassi.qi-flow-w4r-radial-curvature.v1", "radius": profile.rho_ring, "value": at_ring, "lower": profile.radial_curvature_min, "valid": bool(at_ring >= profile.radial_curvature_min)})


def barrier_bounds(*, geometry: Any, profile: QiTopologyProfile, state: QiFlowStateV3 | None = None) -> Mapping[str, Any]:
    _validate_profile(profile, geometry)
    upper = profile.E_topo * (2.0 * profile.lambda_ph + profile.lambda_core)
    lower = profile.delta_h_min
    result: dict[str, Any] = {"schema": "cassi.qi-flow-w4r-barrier-bounds.v1", "lower": lower, "upper": upper, "Delta_H_topo_min": lower, "potential_upper_bound": upper, "rho_ring": profile.rho_ring, "rho_topo": profile.rho_topo, "codebook_sha256": profile.topology_codebook_sha256, "barrier_certificate_sha256": profile.barrier_certificate_sha256, "reset_operator_sha256": profile.reset_operator_sha256}
    if state is not None:
        result["pre_potential"] = topological_potential(state, geometry=geometry, profile=profile)
    return MappingProxyType(result)


def _replace_coordinates(state: QiFlowStateV3, *, geometry: Any, profile: QiTopologyProfile, d: torch.Tensor, c: torch.Tensor, vd: torch.Tensor, vc: torch.Tensor) -> QiFlowStateV3:
    geometry = _geometry_profile(geometry)
    surface = _surface(state, geometry)
    phi, w_d, _ = _coordinate_transform(geometry)
    ey, ei = w_d * d + phi * c, c - phi * w_d * d
    vy, vi = w_d * vd + phi * vc, vc - phi * w_d * vd
    field = state.field.clone()
    values = (ey.real, ey.imag, ei.real, ei.imag, vy.real, vy.imag, vi.real, vi.imag)
    for component, value in enumerate(values):
        field[profile.slow_scale, component * _mode_count(geometry):(component + 1) * _mode_count(geometry), :] = surface.grid_modes(profile.slow_scale, value.contiguous())
    candidate = QiFlowStateV3(field.contiguous())
    candidate.validate(geometry.base_profile)
    return candidate


def _hamiltonian_map(state: QiFlowStateV3, *, geometry: Any, profile: QiTopologyProfile, duration_s: float | None = None) -> QiFlowStateV3:
    """Pure topology KDK helper; production W4R uses the carrier split hook."""
    _validate_profile(profile, geometry)
    if profile.mode == "fading-v1":
        return state
    duration = profile.duration if duration_s is None else _f64(duration_s, name="topology duration", positive=True)
    d, c, vd, vc = _coordinates_from_state(state, geometry, profile.slow_scale)
    force0 = topological_force(state, geometry=geometry, profile=profile)
    fd0, fc0 = force0["D"][profile.slow_scale], force0["C"][profile.slow_scale]
    half = 0.5 * duration
    vd_half = vd + half * fd0; vc_half = vc + half * fc0
    d_end = d + duration * vd_half; c_end = c + duration * vc_half
    midpoint = _replace_coordinates(state, geometry=geometry, profile=profile, d=d_end, c=c_end, vd=vd_half, vc=vc_half)
    force1 = topological_force(midpoint, geometry=geometry, profile=profile)
    vd_end = vd_half + half * force1["D"][profile.slow_scale]; vc_end = vc_half + half * force1["C"][profile.slow_scale]
    return _replace_coordinates(midpoint, geometry=geometry, profile=profile, d=d_end, c=c_end, vd=vd_end, vc=vc_end)


def _force_callback(profile: QiTopologyProfile, state: QiFlowStateV3, geometry: Any, coordinates: Any = None) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
    geometry = _geometry_profile(geometry)
    _validate_profile(profile, geometry)
    shapes = _active_shapes(geometry)
    d_forces: list[torch.Tensor] = []; c_forces: list[torch.Tensor] = []
    for scale, shape in enumerate(shapes):
        values = _coordinates_from_carrier(coordinates, geometry, scale)
        if values is None:
            d, c, _, _ = _coordinates_from_state(state, geometry, scale)
        else:
            d, c, _, _ = values
        if scale != profile.slow_scale or profile.mode == "fading-v1":
            d_forces.append(torch.zeros_like(d)); c_forces.append(torch.zeros_like(c)); continue
        psi, _ = _rotated(d, c, None, None, profile)
        fd, fc = _force_for_coordinates(psi, geometry=geometry, profile=profile)
        d_forces.append(fd); c_forces.append(fc)
    return tuple(d_forces), tuple(c_forces)


@dataclass(frozen=True)
class QiW4RStep:
    predecessor: QiFlowStateV3
    candidate: QiFlowStateV3 | None
    committable: bool
    receipt: Mapping[str, Any]
    failure_reason: str | None = None


def _failure(state: QiFlowStateV3, reason: str, *, stage: str = "preflight") -> QiW4RStep:
    receipt: dict[str, Any] = {"schema": W4R_RECEIPT_SCHEMA, "status": "REJECTED", "committable": False, "stage": stage, "failure_reason": reason, "candidate_state_sha256": None}
    receipt["self_sha256"] = _sha256(receipt, W4R_RECEIPT_DOMAIN)
    return QiW4RStep(state, None, False, MappingProxyType(receipt), reason)


def _validate_numerical_certificate(certificate: Mapping[str, Any], geometry: Any) -> Mapping[str, Any]:
    if not isinstance(certificate, Mapping):
        raise TopologyError("G3N numerical certificate is required")
    if certificate.get("schema") != "cassi.qi-flow-numerical-certificate.v1":
        raise TopologyError("unsupported G3N certificate schema")
    self_hash = certificate.get("self_sha256")
    if not _is_sha256(self_hash):
        raise TopologyError("G3N certificate has no self identity")
    body = dict(certificate); body.pop("self_sha256", None)
    if _sha256(body, "cassi.qi-flow-numerical-certificate.v1") != self_hash:
        raise TopologyError("G3N certificate self identity mismatch")
    geometry = _geometry_profile(geometry)
    current = _w2_parent_identities(geometry)
    parent = certificate.get("w2_parent")
    if not isinstance(parent, Mapping):
        accepted = certificate.get("accepted_w3_artifact_identity", {})
        parent = {"profile_sha256": accepted.get("parent_w2_profile_sha256"), "contract_root_sha256": accepted.get("parent_w2_contract_root_sha256"), "geometry_contract_sha256": certificate.get("w2_geometry_contract_sha256"), "operator_semantic_sha256": certificate.get("w2_operator_semantic_sha256")}
    checks = {"profile_sha256": current.get("w2_profile_sha256"), "contract_root_sha256": current.get("w2_contract_root_sha256"), "geometry_contract_sha256": current.get("w2_geometry_contract_sha256"), "operator_semantic_sha256": current.get("w2_operator_semantic_sha256")}
    for key, expected in checks.items():
        actual = parent.get(key)
        if _is_sha256(expected) and _is_sha256(actual) and actual != expected:
            raise TopologyError(f"G3N certificate W2 ancestry mismatch at {key}")
    guard = certificate.get("online_guard_contract")
    if not isinstance(guard, Mapping) or guard.get("schema") != "cassi.qi-flow-numerical-guard.v1":
        raise TopologyError("G3N certificate has no online guard contract")
    shapes = [list(shape) for shape in _active_shapes(geometry)]
    if guard.get("active_shapes_yx") not in (None, shapes):
        raise TopologyError("G3N guard shape registry disagrees with current W2 geometry")
    return MappingProxyType(dict(certificate))


def _reset_authorized(reset_authorization: Mapping[str, Any] | None, predecessor_hash: str) -> str:
    if not isinstance(reset_authorization, Mapping) or reset_authorization.get("authorized") is not True:
        raise TopologyError("retention reset requires explicit authorized=true")
    if reset_authorization.get("predecessor_state_sha256") != predecessor_hash:
        raise TopologyError("reset authorization predecessor does not match state")
    reason = reset_authorization.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise TopologyError("reset authorization requires a non-empty reason")
    return _sha256(dict(reset_authorization), "cassi.qi-flow-w4r-reset-authorization.v1")


def _reset_candidate(state: QiFlowStateV3, *, geometry: Any, profile: QiTopologyProfile) -> QiFlowStateV3:
    d, c, vd, vc = _coordinates_from_state(state, geometry, profile.slow_scale)
    psi, chi, _, vchi = _rotated(d, c, vd, vc, profile)
    theta = torch.zeros_like(psi.real)
    psi_reset = profile.rho_ring * torch.complex(torch.cos(theta), torch.sin(theta))
    # Invert the weighted orthogonal rotation.  Production a=0,b=1 gives
    # c=psi/sqrt(w_C), d=-chi/sqrt(w_D), and remains valid for future weights.
    sd = math.sqrt(profile.w_d); sc = math.sqrt(profile.w_c)
    d_reset = (profile.a_topo * psi_reset - profile.b_topo * chi) / sd
    c_reset = (profile.b_topo * psi_reset + profile.a_topo * chi) / sc
    vd_reset = (-profile.b_topo * vchi) / sd
    vc_reset = (profile.a_topo * vchi) / sc
    return _replace_coordinates(state, geometry=geometry, profile=profile, d=d_reset, c=c_reset, vd=vd_reset, vc=vc_reset)


def _topology_receipt(
    predecessor: QiFlowStateV3,
    candidate: QiFlowStateV3,
    *,
    geometry: Any,
    profile: QiTopologyProfile,
    pre: Mapping[str, Any],
    post: Mapping[str, Any],
    numerical_certificate: Mapping[str, Any],
    carrier_receipt: Mapping[str, Any] | None,
    transition_kind: str,
    reset_identity: str | None = None,
) -> Mapping[str, Any]:
    pre_vectors = pre.get("sector_vector")
    post_vectors = post.get("sector_vector")
    same = pre_vectors == post_vectors
    if same:
        sector_event = "same-sector"
    else:
        sector_event = "phase-slip"
    receipt: dict[str, Any] = {
        "schema": W4R_RECEIPT_SCHEMA,
        "status": "PASS",
        "committable": True,
        "transition_kind": transition_kind,
        "sector_event": "reset" if transition_kind == "retention_reset" else sector_event,
        "predecessor_state_sha256": _state_hash(predecessor),
        "candidate_state_sha256": _state_hash(candidate),
        "profile_sha256": profile.profile_sha256,
        "root_sha256": profile.root_sha256,
        "topology_codebook_sha256": profile.topology_codebook_sha256,
        "barrier_certificate_sha256": profile.barrier_certificate_sha256,
        "reset_operator_sha256": profile.reset_operator_sha256,
        "g3n_certificate_sha256": numerical_certificate.get("self_sha256"),
        "pre_sector_vector": _plain(pre_vectors),
        "post_sector_vector": _plain(post_vectors),
        "pre_potential": pre.get("potential", 0.0),
        "post_potential": post.get("potential", 0.0),
        "delta_potential": float(post.get("potential", 0.0)) - float(pre.get("potential", 0.0)),
        "radial_curvature": _plain(radial_curvature_bound(geometry=geometry, profile=profile)),
        "barrier_bounds": _plain(barrier_bounds(geometry=geometry, profile=profile)),
        "pre_diagnostics": _plain(pre),
        "post_diagnostics": _plain(post),
        "carrier_split_receipt": _plain(carrier_receipt) if carrier_receipt is not None else None,
        "reset_authorization_sha256": reset_identity,
        "additional_state": False,
    }
    receipt["self_sha256"] = _sha256(receipt, W4R_RECEIPT_DOMAIN)
    return MappingProxyType(receipt)


def _transition_w4r_split(
    state: QiFlowStateV3,
    *,
    geometry_profile: Any,
    transport_profile: Any,
    carrier_profile: Any,
    topology_profile: QiTopologyProfile,
    numerical_certificate: Mapping[str, Any],
    duration_s: float | None = None,
    potential_enabled: bool = True,
    center_map: Callable[..., Any] | None = None,
) -> QiW4RStep:
    """Bind the W4R force into carrier's one seven-stage split.

    This private entry is the only timed path.  If the carrier split hook is
    absent or rejects the callback contract, the state is rejected before any
    topology-only fallback can mutate it.
    """
    try:
        geometry_profile = _geometry_profile(geometry_profile)
        _validate_profile(topology_profile, geometry_profile)
        _surface(state, geometry_profile)
        certificate = _validate_numerical_certificate(numerical_certificate, geometry_profile)
        if not isinstance(potential_enabled, bool):
            raise TopologyError("potential_enabled must be boolean")
        pre = topology_diagnostics(state, geometry=geometry_profile, profile=topology_profile)
        if pre["status"] != "VALID":
            return _failure(state, f"topology invalid preflight: {pre.get('reason', 'unknown')}")
        from cassi_qi_carrier import _transition_v4_carrier_split
    except Exception as exc:
        return _failure(state, f"W4R profile/certificate rejection: {type(exc).__name__}: {exc}")
    law = QiTopologicalRetentionLaw.bind(topology_profile, geometry_profile)
    additional_force = law.additional_force if potential_enabled else (lambda current, geometry, profile, coordinates: _zero_forces(current, geometry))
    mapper = law.identity_center_map if center_map is None else center_map
    try:
        carrier_step = _transition_v4_carrier_split(
            state,
            geometry_profile=geometry_profile,
            transport_profile=transport_profile,
            carrier_profile=carrier_profile,
            numerical_certificate=certificate,
            duration_s=duration_s,
            potential_enabled=True,
            additional_force=additional_force,
            center_map=mapper,
        )
    except Exception as exc:
        return _failure(state, f"W4R combined carrier split unavailable: {type(exc).__name__}: {exc}")
    if not getattr(carrier_step, "committable", False) or getattr(carrier_step, "candidate", None) is None:
        return _failure(state, f"W4R carrier split rejected: {getattr(carrier_step, 'failure_reason', 'unknown')}", stage="carrier-split")
    candidate = carrier_step.candidate
    try:
        post = topology_diagnostics(candidate, geometry=geometry_profile, profile=topology_profile)
    except Exception as exc:
        return _failure(state, f"W4R post-split diagnostics failed: {type(exc).__name__}: {exc}", stage="postflight")
    if post["status"] != "VALID":
        return _failure(state, f"W4R topology invalid after combined split: {post.get('reason', 'unknown')}", stage="postflight")
    receipt = _topology_receipt(state, candidate, geometry=geometry_profile, profile=topology_profile, pre=pre, post=post, numerical_certificate=certificate, carrier_receipt=getattr(carrier_step, "receipt", None), transition_kind="timed")
    return QiW4RStep(state, candidate, True, receipt)


def _zero_forces(state: QiFlowStateV3, geometry: Any) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
    geometry = _geometry_profile(geometry)
    values_d: list[torch.Tensor] = []; values_c: list[torch.Tensor] = []
    for scale in range(_scale_count(geometry)):
        d, c, _, _ = _coordinates_from_state(state, geometry, scale)
        values_d.append(torch.zeros_like(d)); values_c.append(torch.zeros_like(c))
    return tuple(values_d), tuple(values_c)


def _retention_reset_transition(
    state: QiFlowStateV3,
    *,
    geometry_profile: Any,
    topology_profile: QiTopologyProfile,
    numerical_certificate: Mapping[str, Any],
    reset_authorization: Mapping[str, Any] | None,
) -> QiW4RStep:
    try:
        geometry_profile = _geometry_profile(geometry_profile)
        _validate_profile(topology_profile, geometry_profile)
        certificate = _validate_numerical_certificate(numerical_certificate, geometry_profile)
        pre = topology_diagnostics(state, geometry=geometry_profile, profile=topology_profile)
        if pre["status"] != "VALID":
            return _failure(state, f"topology invalid before reset: {pre.get('reason', 'unknown')}")
        auth_id = _reset_authorized(reset_authorization, _state_hash(state))
        candidate = _reset_candidate(state, geometry=geometry_profile, profile=topology_profile)
        post = topology_diagnostics(candidate, geometry=geometry_profile, profile=topology_profile)
        if post["status"] != "VALID":
            return _failure(state, f"reset candidate violates topology guards: {post.get('reason', 'unknown')}", stage="precommit")
        receipt = _topology_receipt(state, candidate, geometry=geometry_profile, profile=topology_profile, pre=pre, post=post, numerical_certificate=certificate, carrier_receipt=None, transition_kind="retention_reset", reset_identity=auth_id)
        return QiW4RStep(state, candidate, True, receipt)
    except Exception as exc:
        return _failure(state, f"W4R reset rejected: {type(exc).__name__}: {exc}")


def transition_w4r_topology(
    state: QiFlowStateV3,
    *,
    geometry_profile: Any,
    topology_profile: QiTopologyProfile,
    numerical_certificate: Mapping[str, Any],
    transport_profile: Any | None = None,
    carrier_profile: Any | None = None,
    duration_s: float | None = None,
    potential_enabled: bool = True,
    transition_kind: str = "timed",
    reset_authorization: Mapping[str, Any] | None = None,
) -> QiW4RStep:
    """Public guarded W4R transition; timed evolution always uses carrier split."""
    if transition_kind == "retention_reset":
        return _retention_reset_transition(state, geometry_profile=geometry_profile, topology_profile=topology_profile, numerical_certificate=numerical_certificate, reset_authorization=reset_authorization)
    if transition_kind != "timed":
        return _failure(state, "unknown W4R transition kind")
    if transport_profile is None or carrier_profile is None:
        return _failure(state, "timed W4R transition requires explicit W3 transport and W4 carrier profiles")
    return _transition_w4r_split(state, geometry_profile=geometry_profile, transport_profile=transport_profile, carrier_profile=carrier_profile, topology_profile=topology_profile, numerical_certificate=numerical_certificate, duration_s=duration_s, potential_enabled=potential_enabled)


def build_w4r_derivation(*, profile: QiTopologyProfile, certificate: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if not isinstance(profile, QiTopologyProfile):
        raise TopologyError("derivation requires QiTopologyProfile")
    barrier = _barrier_payload(E=profile.E_topo, lambda_core=profile.lambda_core, rho_ring=profile.rho_ring, rho_topo=profile.rho_topo, delta_h_min=profile.delta_h_min, radial_min=profile.radial_curvature_min)
    payload: dict[str, Any] = {
        "schema": W4R_DERIVATION_SCHEMA,
        "law_id": profile.law_id,
        "profile_sha256": profile.profile_sha256,
        "root_sha256": profile.root_sha256,
        "equations": {
            "weighted_rotation": "psi=a_topo*sqrt(w_D)*D+b_topo*sqrt(w_C)*C; chi=-b_topo*sqrt(w_D)*D+a_topo*sqrt(w_C)*C",
            "smooth_phase": "hat_psi=psi/sqrt(|psi|^2+r_core^2)",
            "potential": "U_topo=E_topo*(lambda_ph*mean_edges(1-Re(hat_psi_i^*hat_psi_j))+lambda_core*mean_W(((|psi|^2-rho_ring^2)/(|psi|^2+rho_ring^2))^2))",
            "force": "F_Z=-2/w_Z*W^{-1}*partial_{Z*}U after weighted orthogonal pullback",
            "integrator": "same two local half-kicks as combined W4 carrier split; no separate topology step",
        },
        "edge_registry": [_plain(row) for row in profile.edge_registry],
        "cycle_registry": _plain(profile.cycle_registry),
        "bounds": {"radial_curvature": _plain(radial_curvature_bound(geometry=_DERIVATION_GEOMETRY, profile=profile)) if _DERIVATION_GEOMETRY is not None else {"lower": profile.radial_curvature_min}, "barrier": barrier},
        "topology_codebook_sha256": profile.topology_codebook_sha256,
        "barrier_certificate_sha256": profile.barrier_certificate_sha256,
        "reset_operator_sha256": profile.reset_operator_sha256,
        "g3n_certificate_sha256": certificate.get("self_sha256") if isinstance(certificate, Mapping) else None,
        "additional_state": False,
    }
    payload["self_sha256"] = _sha256(payload, W4R_DERIVATION_DOMAIN)
    return MappingProxyType(payload)


# Derivations can be built without geometry; bounds still carry profile values.
_DERIVATION_GEOMETRY: Any | None = None


def build_w4r_section(*, profile: QiTopologyProfile, derivation: Mapping[str, Any]) -> Mapping[str, Any]:
    if derivation.get("profile_sha256") != profile.profile_sha256:
        raise TopologyError("W4R section/derivation profile mismatch")
    section = {
        "schema": W4R_SECTION_SCHEMA,
        "gate": "G4R",
        "profile_sha256": profile.profile_sha256,
        "derivation_sha256": derivation.get("self_sha256"),
        "subsections": [
            "topological-retention-reciprocal-hamiltonian",
            "symmetric-kick-drift-kick-map",
            "phase-safe-periodic-topology",
            "online-admission-bounds",
        ],
        "identities": {"topology_codebook_sha256": profile.topology_codebook_sha256, "barrier_certificate_sha256": profile.barrier_certificate_sha256, "reset_operator_sha256": profile.reset_operator_sha256},
    }
    section["self_sha256"] = _sha256(section, W4R_SECTION_SCHEMA)
    return MappingProxyType(section)


def make_topology_fixture(*, geometry: Any, kind: str = "vortex", batch_lanes: int = 1) -> QiFlowStateV3:
    """Construct deterministic ring/sector fixtures from the dynamic W2 shape."""
    geometry = _geometry_profile(geometry)
    if isinstance(batch_lanes, bool) or int(batch_lanes) <= 0:
        raise TopologyError("fixture batch_lanes must be positive")
    lanes = int(batch_lanes)
    base = _base_profile(geometry)
    state = QiFlowStateV3.create(base, batch_lanes=lanes)
    profile = load_w4r_topology_profile(geometry=geometry)
    surface = QiFlowGeometryV2(state, geometry)
    ny, nx = _active_shapes(geometry)[profile.slow_scale]
    x = torch.arange(nx, dtype=torch.float64).reshape(1, nx, 1)
    allowed = {"zero", "near-zero", "ring", "plane-wave", "vortex", "anti-vortex", "phase-scramble"}
    if kind not in allowed:
        raise TopologyError(f"unknown topology fixture kind {kind!r}")
    if kind == "zero":
        amplitude = torch.zeros((ny, nx, lanes), dtype=torch.float64)
    elif kind == "near-zero":
        amplitude = torch.full((ny, nx, lanes), profile.rho_topo * 0.25, dtype=torch.float64)
    else:
        amplitude = torch.full((ny, nx, lanes), profile.rho_ring, dtype=torch.float64)
    winding_x = -1.0 if kind == "anti-vortex" else (1.0 if kind == "vortex" else 0.0)
    phase = 2.0 * math.pi * winding_x * x / nx
    if kind == "phase-scramble":
        phase = torch.zeros((ny, nx, lanes), dtype=torch.float64)
        phase[0, 0, :] = math.pi
    psi = torch.complex(amplitude * torch.cos(phase), amplitude * torch.sin(phase))
    c = psi / math.sqrt(profile.w_c)
    d = torch.zeros_like(c)
    vc = 0.05j * c
    vd = torch.zeros_like(d)
    phi, w_d, _ = _coordinate_transform(geometry)
    ey, ei = w_d * d + phi * c, c - phi * w_d * d
    vy, vi = w_d * vd + phi * vc, vc - phi * w_d * vd
    values = (ey.real, ey.imag, ei.real, ei.imag, vy.real, vy.imag, vi.real, vi.imag)
    field = state.field.clone()
    modes = _mode_count(geometry)
    for component, value in enumerate(values):
        field[profile.slow_scale, component * modes:(component + 1) * modes, :] = surface.grid_modes(profile.slow_scale, value.contiguous())
    candidate = QiFlowStateV3(field.contiguous())
    candidate.validate(base)
    return candidate


def topological_retention_hamiltonian(state: QiFlowStateV3, *, geometry: Any, profile: QiTopologyProfile) -> float:
    return topological_potential(state, geometry=geometry, profile=profile)




__all__ = [
    "W4R_PROFILE_SCHEMA",
    "W4R_ROOT_SCHEMA",
    "W4R_RECEIPT_SCHEMA",
    "W4R_DERIVATION_SCHEMA",
    "W4R_SECTION_SCHEMA",
    "TopologyError",
    "TopologyTransitionRejected",
    "QiTopologyProfile",
    "QiTopologicalRetentionLaw",
    "QiW4RStep",
    "load_w4r_topology_profile",
    "topological_potential",
    "topological_force",
    "topological_retention_hamiltonian",
    "topology_diagnostics",
    "transition_w4r_topology",
    "radial_curvature",
    "radial_curvature_bound",
    "barrier_bounds",
    "make_topological_force_callback",
    "build_w4r_derivation",
    "build_w4r_section",
    "make_topology_fixture",
]
