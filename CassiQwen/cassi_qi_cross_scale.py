"""W6 reciprocal cross-scale Hamiltonian and periodic-current diagnostics.

The module owns only the distributed reciprocal link law.  It deliberately
keeps the state in the existing ``[S,9M,B]`` representation and delegates all
sheet gathering, FFT symbols, cell metrics, and fixed cross-scale maps to
:class:`cassi_qi_geometry.PeriodicSheetGeometry`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import torch

from cassi_qi_geometry import PeriodicSheetGeometry
from cassi_qi_profile import canonical_hash, finite_float


W6_CROSS_SCALE_PROFILE_SCHEMA = "cassi.qi-flow-cross-scale-profile.v1"
W6_CROSS_SCALE_ROOT_SCHEMA = "cassi.qi-flow-cross-scale-root.v1"
W6_CROSS_SCALE_LAW_ID = "distributed-reciprocal-weighted-links.v1"
W6_CROSS_SCALE_PROFILE_DOMAIN = W6_CROSS_SCALE_PROFILE_SCHEMA
W6_CROSS_SCALE_ROOT_DOMAIN = W6_CROSS_SCALE_ROOT_SCHEMA
W6_CROSS_SCALE_LAW_DOMAIN = "cassi.qi-flow-cross-scale-law.v1"
W6_HODGE_SCHEMA = "cassi.qi-flow-hodge-diagnostics.v1"


class CrossScaleError(ValueError):
    """Raised for an invalid immutable W6 law, operator, or diagnostic input."""


QiCrossScaleError = CrossScaleError


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


def _finite(value: Any, *, name: str, positive: bool = False, nonnegative: bool = False) -> float:
    try:
        result = finite_float(value, name=name)
    except Exception as exc:
        raise CrossScaleError(str(exc)) from exc
    if positive and result <= 0.0:
        raise CrossScaleError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise CrossScaleError(f"{name} must be non-negative")
    return result


def _sequence(value: Any, *, name: str, length: int | None = None) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise CrossScaleError(f"{name} must be a finite sequence")
    result = tuple(value)
    if length is not None and len(result) != length:
        raise CrossScaleError(f"{name} must contain exactly {length} entries")
    return result


def _sha_body(value: Mapping[str, Any], domain: str, self_key: str) -> str:
    return canonical_hash({key: _plain(item) for key, item in value.items() if key != self_key}, domain)


def _state_field(state: Any) -> torch.Tensor:
    tensor = getattr(state, "field", state)
    if not torch.is_tensor(tensor):
        raise CrossScaleError("state must be a tensor or QiFlowStateV3")
    if tensor.ndim != 3 or tensor.shape[0] < 1 or tensor.shape[1] < 9 or tensor.shape[1] % 9 != 0 or tensor.shape[2] < 1:
        raise CrossScaleError("state must have shape [S,9M,B]")

    if tensor.device.type != "cpu" or tensor.layout is not torch.strided or not tensor.is_contiguous():
        raise CrossScaleError("state must be a contiguous CPU tensor")
    if tensor.dtype not in (torch.float64, torch.complex128):
        raise CrossScaleError("state must use float64 or complex128 storage")
    if not bool(torch.isfinite(tensor).all().item()):
        raise CrossScaleError("state contains a non-finite value")
    return tensor


def _surface(geometry: Any) -> PeriodicSheetGeometry:
    if isinstance(geometry, PeriodicSheetGeometry):
        return geometry
    candidate = getattr(geometry, "_surface", None)
    if isinstance(candidate, PeriodicSheetGeometry):
        return candidate
    try:
        return PeriodicSheetGeometry(geometry)
    except Exception as exc:
        raise CrossScaleError(f"cannot bind PeriodicSheetGeometry: {type(exc).__name__}: {exc}") from exc


def _geometry_profile(geometry: Any) -> Any:
    surface = _surface(geometry)
    return surface.profile


def _state_scale_check(state: Any, surface: PeriodicSheetGeometry, profile: "QiCrossScaleProfile") -> torch.Tensor:
    tensor = _state_field(state)
    if tensor.shape[0] != profile.scale_count or tensor.shape[0] != surface.profile.scale_count:
        raise CrossScaleError("state, geometry, and cross-scale profile scale counts disagree")
    return tensor


def _complex_pair(real: torch.Tensor, imag: torch.Tensor) -> torch.Tensor:
    if real.is_complex() or imag.is_complex():
        return (real.to(torch.complex128) + 1.0j * imag.to(torch.complex128)).contiguous()
    return torch.complex(real, imag).to(torch.complex128).contiguous()


def _as_complex(value: torch.Tensor) -> torch.Tensor:
    return value.to(torch.complex128) if not value.is_complex() else value.to(torch.complex128)


def _component_grid(tensor: torch.Tensor, surface: PeriodicSheetGeometry, scale: int, component: int) -> torch.Tensor:
    modes = tensor.shape[1] // 9
    start = component * modes
    return surface.modes_to_grid(tensor[scale, start : start + modes].contiguous(), scale=scale)


def _fallback_coordinates(tensor: torch.Tensor, surface: PeriodicSheetGeometry, profile: "QiCrossScaleProfile") -> tuple[tuple[torch.Tensor, ...], ...]:
    d: list[torch.Tensor] = []
    c: list[torch.Tensor] = []
    vd: list[torch.Tensor] = []
    vc: list[torch.Tensor] = []
    for scale in range(profile.scale_count):
        ey = _complex_pair(_component_grid(tensor, surface, scale, 0), _component_grid(tensor, surface, scale, 1))
        ei = _complex_pair(_component_grid(tensor, surface, scale, 2), _component_grid(tensor, surface, scale, 3))
        vy = _complex_pair(_component_grid(tensor, surface, scale, 4), _component_grid(tensor, surface, scale, 5))
        vi = _complex_pair(_component_grid(tensor, surface, scale, 6), _component_grid(tensor, surface, scale, 7))
        d.append((ey - profile.phi * ei).contiguous())
        c.append((profile.w_C * (profile.phi * ey + ei)).contiguous())
        vd.append((vy - profile.phi * vi).contiguous())
        vc.append((profile.w_C * (profile.phi * vy + vi)).contiguous())
    return tuple(d), tuple(c), tuple(vd), tuple(vc)


def _coordinates(
    state: Any,
    surface: PeriodicSheetGeometry,
    profile: "QiCrossScaleProfile",
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...], tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
    tensor = _state_scale_check(state, surface, profile)
    if coords is not None:
        names = ("d", "c", "vd", "vc")
        values: list[Any] = []
        complete = True
        for name in names:
            value = getattr(coords, name, None)
            if value is None and isinstance(coords, Mapping):
                value = coords.get(name, coords.get(name.upper()))
            if value is None:
                complete = False
                break
            values.append(_sequence(value, name=f"coords.{name}", length=profile.scale_count))
        if complete:
            result = tuple(tuple(_as_complex(item) for item in group) for group in values)
            _validate_coordinate_shapes(result, surface, tensor.shape[2])
            return result  # type: ignore[return-value]
    if carrier_profile is not None and hasattr(state, "field"):
        try:
            from cassi_qi_carrier import carrier_coordinates

            mapped = carrier_coordinates(state, geometry=_geometry_profile(surface), profile=carrier_profile)
            result = (
                tuple(_as_complex(value) for value in mapped.d),
                tuple(_as_complex(value) for value in mapped.c),
                tuple(_as_complex(value) for value in mapped.vd),
                tuple(_as_complex(value) for value in mapped.vc),
            )
            _validate_coordinate_shapes(result, surface, tensor.shape[2])
            return result
        except CrossScaleError:
            raise
        except Exception as exc:
            raise CrossScaleError(f"carrier coordinate map failed: {type(exc).__name__}: {exc}") from exc
    result = _fallback_coordinates(tensor, surface, profile)
    _validate_coordinate_shapes(result, surface, tensor.shape[2])
    return result


def _validate_coordinate_shapes(values: tuple[tuple[torch.Tensor, ...], ...], surface: PeriodicSheetGeometry, batch: int) -> None:
    for group in values:
        for scale, value in enumerate(group):
            expected = tuple(surface.sheet_shape(scale)) + (batch,)
            if tuple(value.shape) != expected or value.device.type != "cpu" or not value.is_complex() or not bool(torch.isfinite(value).all().item()):
                raise CrossScaleError(f"coordinate[{scale}] has shape or dtype inconsistent with its active sheet")


def _link_override(adjoint_matrices: Any, link_index: int, source: int, target: int) -> torch.Tensor | None:
    if adjoint_matrices is None:
        return None
    if isinstance(adjoint_matrices, Mapping):
        return adjoint_matrices.get(link_index, adjoint_matrices.get((source, target)))
    values = _sequence(adjoint_matrices, name="adjoint_matrices")
    if link_index >= len(values):
        raise CrossScaleError("adjoint_matrices omits an active link")
    return values[link_index]


def _metric_adjoint(
    surface: PeriodicSheetGeometry,
    profile: "QiCrossScaleProfile",
    source: int,
    target: int,
    link_index: int,
    override: Any | None = None,
) -> torch.Tensor:
    matrix = surface.cross_scale_matrix(source, target).to(torch.complex128)
    expected = surface.cross_scale_adjoint_matrix(source, target).to(torch.complex128)
    candidate = expected if override is None else torch.as_tensor(override, dtype=torch.complex128)
    if candidate.ndim != 2 or tuple(candidate.shape) != tuple(expected.shape):
        raise CrossScaleError(f"P[{source}] adjoint has the wrong shape")
    source_area = float(surface.cell_area_m2(source))
    target_area = float(surface.cell_area_m2(target))
    residual = source_area * candidate - target_area * matrix.conj().T
    bound = profile.tolerance("operator")
    if float(residual.abs().max().item()) > bound:
        raise CrossScaleError(f"P[{source}] weighted metric-adjoint identity failed")
    return candidate.contiguous()

def _apply(matrix: torch.Tensor, values: torch.Tensor, *, target_shape: tuple[int, int]) -> torch.Tensor:
    flat = values.reshape(values.shape[0] * values.shape[1], values.shape[2])
    mapped = matrix @ flat
    return mapped.reshape(*target_shape, values.shape[2]).contiguous()


def _transfer(surface: PeriodicSheetGeometry, values: torch.Tensor, source: int, target: int) -> torch.Tensor:
    matrix = surface.cross_scale_matrix(source, target).to(device=values.device, dtype=torch.complex128)
    return _apply(matrix, _as_complex(values), target_shape=surface.sheet_shape(target))


def _adjoint_transfer(surface: PeriodicSheetGeometry, values: torch.Tensor, source: int, target: int, adjoint: torch.Tensor | None = None) -> torch.Tensor:
    matrix = surface.cross_scale_adjoint_matrix(source, target).to(device=values.device, dtype=torch.complex128) if adjoint is None else adjoint.to(device=values.device, dtype=torch.complex128)
    return _apply(matrix, _as_complex(values), target_shape=surface.sheet_shape(source))


@dataclass(frozen=True, slots=True)
class QiCrossScaleProfile:
    """Immutable, validated materialization of all W6 link physics."""

    scale_count: int = 0
    link_pairs: tuple[tuple[int, int], ...] = ()
    g_D: tuple[float, ...] = ()
    g_C: tuple[float, ...] = ()
    phi: float | None = None
    w_D: float | None = None
    w_C: float | None = None
    c_D: tuple[float, ...] | None = None
    c_C: tuple[float, ...] | None = None
    metric_cell_areas: tuple[float, ...] = ()
    enabled: bool = True
    law_id: str = W6_CROSS_SCALE_LAW_ID
    operator_family: str = "periodic-fft2.v1"
    p_operator_sha256: str = ""
    p_adjoint_sha256: str = ""
    potential_quadrature: str = "positive-cell-metric.v1"
    force_pullback: str = "weighted-adjoint-reciprocal.v1"
    phase_current_sign: str = "positive-fine-to-coarse.v1"
    absent_endpoint_links: str = "exact-zero.v1"
    tolerances: Mapping[str, float] = field(default_factory=dict)
    parent_identities: Mapping[str, Any] = field(default_factory=dict)
    operator_identity: Mapping[str, Any] = field(default_factory=dict)
    active_site_counts: tuple[int, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)
    root: Mapping[str, Any] = field(default_factory=dict)
    profile_sha256: str = ""
    root_sha256: str = ""

    def __post_init__(self) -> None:
        scales = int(self.scale_count)
        if scales <= 0:
            if self.g_D:
                scales = len(self.g_D) + 1
            elif self.g_C:
                scales = len(self.g_C) + 1
            elif self.link_pairs:
                scales = len(self.link_pairs) + 1
            else:
                scales = 1
        if scales < 1:
            raise CrossScaleError("scale_count must be positive")
        pairs = tuple(tuple(pair) for pair in self.link_pairs) if self.link_pairs else tuple((index, index + 1) for index in range(scales - 1))
        if len(pairs) != scales - 1 or any(len(pair) != 2 or pair != (index, index + 1) for index, pair in enumerate(pairs)):
            raise CrossScaleError("link_pairs must enumerate every adjacent scale exactly once")
        g_d = tuple(_finite(item, name=f"g_D[{index}]", positive=True) for index, item in enumerate(_sequence(self.g_D, name="g_D", length=scales - 1)))
        g_c = tuple(_finite(item, name=f"g_C[{index}]", positive=True) for index, item in enumerate(_sequence(self.g_C, name="g_C", length=scales - 1)))
        if self.phi is None:
            raise CrossScaleError("phi is required and must be supplied by the parent physics profile")
        phi = _finite(self.phi, name="phi", positive=True)
        expected_w_d = 1.0 / (1.0 + phi * phi)
        expected_w_c = 1.0 + phi * phi
        w_d = expected_w_d if self.w_D is None else _finite(self.w_D, name="w_D", positive=True)
        w_c = expected_w_c if self.w_C is None else _finite(self.w_C, name="w_C", positive=True)
        if w_d != expected_w_d or w_c != expected_w_c:
            raise CrossScaleError("D/C metric weights do not match the supplied phi")
        if self.c_D is None:
            raise CrossScaleError("c_D is required and must be supplied by the parent physics profile")
        if self.c_C is None:
            raise CrossScaleError("c_C is required and must be supplied by the parent physics profile")
        c_d = tuple(_finite(item, name=f"c_D[{index}]", positive=True) for index, item in enumerate(_sequence(self.c_D, name="c_D", length=scales)))
        c_c = tuple(_finite(item, name=f"c_C[{index}]", positive=True) for index, item in enumerate(_sequence(self.c_C, name="c_C", length=scales)))
        areas = self.metric_cell_areas if self.metric_cell_areas else tuple(1.0 for _ in range(scales))
        metric_areas = tuple(_finite(item, name=f"metric_cell_areas[{index}]", positive=True) for index, item in enumerate(_sequence(areas, name="metric_cell_areas", length=scales)))
        if isinstance(self.enabled, bool) is False:
            raise CrossScaleError("enabled must be boolean")
        tolerance_input = dict(self.tolerances) if isinstance(self.tolerances, Mapping) else {}
        tolerances: dict[str, float] = {}
        for name in ("operator", "energy", "work", "current", "hodge"):
            value = tolerance_input.get(name, tolerance_input.get("numeric", 1.0e-10))
            tolerances[name] = _finite(value, name=f"tolerances.{name}", positive=True)
        parents = _freeze(dict(self.parent_identities)) if isinstance(self.parent_identities, Mapping) else MappingProxyType({})
        operators = _freeze(dict(self.operator_identity)) if isinstance(self.operator_identity, Mapping) else MappingProxyType({})
        active_counts = tuple(int(item) for item in self.active_site_counts)
        if active_counts and (len(active_counts) != scales or any(item < 1 for item in active_counts)):
            raise CrossScaleError("active_site_counts must contain one positive value per scale")
        if not isinstance(self.law_id, str) or not self.law_id:
            raise CrossScaleError("law_id must be a non-empty immutable string")
        body = _plain(self.payload) if isinstance(self.payload, Mapping) else {}
        body.update(
            {
                "schema": W6_CROSS_SCALE_PROFILE_SCHEMA,
                "law_id": self.law_id,
                "enabled": bool(self.enabled),
                "scale_count": scales,
                "link_pairs": [list(pair) for pair in pairs],
                "g_D": list(g_d),
                "g_C": list(g_c),
                "metric": {
                    "phi": phi,
                    "w_D": w_d,
                    "w_C": w_c,
                    "cell_areas": list(metric_areas),
                },
                "operator": {
                    "family": self.operator_family,
                    "p_operator_sha256": self.p_operator_sha256,
                    "p_adjoint_sha256": self.p_adjoint_sha256,
                    **_plain(operators),
                },
                "conventions": {
                    "potential_quadrature": self.potential_quadrature,
                    "force_pullback": self.force_pullback,
                    "phase_current_sign": self.phase_current_sign,
                    "absent_endpoint_links": self.absent_endpoint_links,
                },
                "speeds": {"c_D": list(c_d), "c_C": list(c_c)},
                "active_site_counts": list(active_counts),
                "tolerances": tolerances,
                "parent_identities": _plain(parents),
                "state": {"shape": "[S,9M,B]", "additional_state": False},
            }
        )
        body.pop("profile_sha256", None)
        digest = _sha_body(body, W6_CROSS_SCALE_PROFILE_DOMAIN, "profile_sha256")
        supplied_digest = str(self.profile_sha256) if self.profile_sha256 else ""
        if supplied_digest and supplied_digest != digest:
            raise CrossScaleError("cross-scale profile identity mismatch")
        materialized = dict(body)
        materialized["profile_sha256"] = digest
        root_body = _plain(self.root) if isinstance(self.root, Mapping) else {}
        root_body.update(
            {
                "schema": W6_CROSS_SCALE_ROOT_SCHEMA,
                "law_id": self.law_id,
                "profile_sha256": digest,
                "parent_identities": _plain(parents),
                "state": {"shape": "[S,9M,B]", "additional_state": False},
            }
        )
        root_body.pop("self_sha256", None)
        root_digest = _sha_body(root_body, W6_CROSS_SCALE_ROOT_DOMAIN, "self_sha256")
        supplied_root = str(self.root_sha256) if self.root_sha256 else ""
        if supplied_root and supplied_root != root_digest:
            raise CrossScaleError("cross-scale root identity mismatch")
        root_materialized = dict(root_body)
        root_materialized["self_sha256"] = root_digest
        object.__setattr__(self, "scale_count", scales)
        object.__setattr__(self, "link_pairs", pairs)
        object.__setattr__(self, "g_D", g_d)
        object.__setattr__(self, "g_C", g_c)
        object.__setattr__(self, "phi", phi)
        object.__setattr__(self, "w_D", w_d)
        object.__setattr__(self, "w_C", w_c)
        object.__setattr__(self, "c_D", c_d)
        object.__setattr__(self, "c_C", c_c)
        object.__setattr__(self, "metric_cell_areas", metric_areas)
        object.__setattr__(self, "tolerances", MappingProxyType(tolerances))
        object.__setattr__(self, "parent_identities", parents)
        object.__setattr__(self, "operator_identity", operators)
        object.__setattr__(self, "active_site_counts", active_counts)
        object.__setattr__(self, "payload", _freeze(materialized))
        object.__setattr__(self, "root", _freeze(root_materialized))
        object.__setattr__(self, "profile_sha256", digest)
        object.__setattr__(self, "root_sha256", root_digest)

    @property
    def g_d(self) -> tuple[float, ...]:
        return self.g_D

    @property
    def g_c(self) -> tuple[float, ...]:
        return self.g_C

    @property
    def parents(self) -> Mapping[str, Any]:
        return self.parent_identities

    @property
    def p_sha256(self) -> str:
        return self.p_operator_sha256

    @property
    def g_D_per_s2(self) -> tuple[float, ...]:
        return self.g_D

    @property
    def g_C_per_s2(self) -> tuple[float, ...]:
        return self.g_C

    @classmethod
    def from_geometry(cls, geometry: Any, **kwargs: Any) -> "QiCrossScaleProfile":
        return load_w6_cross_scale_profile(geometry=geometry, **kwargs)

    def tolerance(self, name: str) -> float:
        try:
            return float(self.tolerances[name])
        except (KeyError, TypeError, ValueError) as exc:
            raise CrossScaleError(f"unknown W6 tolerance {name!r}") from exc

    @property
    def operator_tolerance(self) -> float:
        return self.tolerance("operator")

    @property
    def energy_tolerance(self) -> float:
        return self.tolerance("energy")

    @property
    def work_tolerance(self) -> float:
        return self.tolerance("work")

    @property
    def current_tolerance(self) -> float:
        return self.tolerance("current")

    def __hash__(self) -> int:
        return hash((self.profile_sha256, self.root_sha256))

    def with_enabled(self, enabled: bool) -> "QiCrossScaleProfile":
        if not isinstance(enabled, bool):
            raise CrossScaleError("enabled must be boolean")
        return replace(self, enabled=enabled, profile_sha256="", root_sha256="")

    def validate(self, geometry: Any | None = None) -> "QiCrossScaleProfile":
        if geometry is not None:
            _validate_profile_geometry(self, _surface(geometry))
        return self



def _validate_profile_geometry(profile: QiCrossScaleProfile, surface: PeriodicSheetGeometry) -> None:

    if profile.scale_count != surface.profile.scale_count:
        raise CrossScaleError("cross-scale profile does not cover every geometry scale")
    bound_geometry = profile.parent_identities.get("geometry_profile_sha256")
    if bound_geometry is not None and bound_geometry != surface.profile.profile_sha256:
        raise CrossScaleError("cross-scale profile geometry parent identity mismatch")
    if profile.p_operator_sha256 and profile.p_operator_sha256 != getattr(surface.profile, "operator_semantic_sha256", profile.p_operator_sha256):
        # W2 exposes the semantic identity separately; a supplied empty identity
        # is intentionally allowed for analytic/manual profiles.
        raise CrossScaleError("cross-scale profile P operator identity mismatch")
    if profile.metric_cell_areas and bound_geometry is not None:
        for scale, area in enumerate(profile.metric_cell_areas):
            if area != float(surface.cell_area_m2(scale)):
                raise CrossScaleError("cross-scale profile metric cell area mismatch")


def _operator_rows(surface: PeriodicSheetGeometry, scales: int, tolerance: float) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for index in range(scales - 1):
        source, target = index, index + 1
        matrix = surface.cross_scale_matrix(source, target)
        singular = torch.linalg.svdvals(matrix)
        threshold = tolerance * max(float(singular.max().item()) if singular.numel() else 1.0, 1.0)
        rank = int((singular > threshold).sum().item())
        rows.append(
            MappingProxyType(
                {
                    "source_scale": source,
                    "target_scale": target,
                    "shape": tuple(int(item) for item in matrix.shape),
                    "singular_values": tuple(float(item) for item in singular.tolist()),
                    "effective_rank": rank,
                    "nullity": int(matrix.shape[1] - rank),
                    "nullspace": "right-kernel",
                    "metric_adjoint": True,
                }
            )
        )
    return tuple(rows)


def _profile_from_geometry(
    geometry: Any,
    *,
    carrier_profile: Any | None = None,
    parent_identities: Mapping[str, Any] | None = None,
    enabled: bool | None = None,
    g_D: Sequence[Any] | None = None,
    g_C: Sequence[Any] | None = None,
    tolerances: Mapping[str, Any] | None = None,
) -> QiCrossScaleProfile:
    surface = _surface(geometry)
    base = getattr(surface.profile, "base_profile", None)
    payload = getattr(base, "payload", {}) if base is not None else {}
    if not isinstance(payload, Mapping):
        raise CrossScaleError("geometry profile has no parent physics payload")
    coupling = payload.get("scale_coupling", {})
    if not isinstance(coupling, Mapping):
        raise CrossScaleError("parent profile omits scale_coupling")
    scales = int(surface.profile.scale_count)
    raw_g_d = coupling.get("g_D_per_s2") if g_D is None else g_D
    raw_g_c = coupling.get("g_C_per_s2") if g_C is None else g_C
    if raw_g_d is None or raw_g_c is None:
        raise CrossScaleError("cross-scale profile requires positive g_D and g_C for every link")
    dynamics = payload.get("dynamics", {})
    if not isinstance(dynamics, Mapping):
        dynamics = {}
    transform = dynamics.get("coordinate_transform", {})
    if not isinstance(transform, Mapping):
        transform = {}
    phi_value = getattr(carrier_profile, "phi", None)
    if phi_value is None:
        phi_value = transform.get("phi")
    if phi_value is None:
        raise CrossScaleError("cross-scale profile requires the parent phi identity")
    phi = _finite(phi_value, name="phi", positive=True)
    def _scale_values(name: str, carrier_name: str) -> tuple[float, ...]:
        values = getattr(carrier_profile, carrier_name, None) if carrier_profile is not None else None
        if values is None:
            values = dynamics.get(name)
        if values is None:
            raise CrossScaleError(f"{name} is required and must be supplied by the parent physics profile")
        return tuple(_finite(item, name=f"{name}[{index}]", positive=True) for index, item in enumerate(_sequence(values, name=name, length=scales)))
    parent: dict[str, Any] = {
        "geometry_profile_sha256": getattr(surface.profile, "profile_sha256", ""),
        "geometry_contract_root_sha256": getattr(surface.profile, "contract_root_sha256", ""),
        "operator_semantic_sha256": getattr(surface.profile, "operator_semantic_sha256", ""),
    }
    if carrier_profile is not None:
        for field_name, key in (("profile_sha256", "carrier_profile_sha256"), ("root_sha256", "carrier_root_sha256")):
            value = getattr(carrier_profile, field_name, None)
            if value is not None:
                parent[key] = value
    if parent_identities is not None:
        if not isinstance(parent_identities, Mapping):
            raise CrossScaleError("parent_identities must be a mapping")
        parent.update(_plain(parent_identities))
    numeric_tolerance = None
    envelope = dynamics.get("stability_envelope")
    if isinstance(envelope, Mapping):
        numeric_tolerance = envelope.get("numerical_uncertainty_abs")
    if numeric_tolerance is None:
        numeric_tolerance = dynamics.get("candidate_numerical_tolerance")
    if numeric_tolerance is None:
        numeric_tolerance = 1.0e-10
    tol = dict(tolerances or {})
    for name in ("operator", "energy", "work", "current", "hodge"):
        tol.setdefault(name, numeric_tolerance)
        tol[name] = _finite(tol[name], name=f"tolerances.{name}", positive=True)
    operator_rows = _operator_rows(surface, scales, tol["operator"])
    return QiCrossScaleProfile(
        scale_count=scales,
        link_pairs=tuple((index, index + 1) for index in range(scales - 1)),
        g_D=tuple(_finite(item, name=f"g_D[{index}]", positive=True) for index, item in enumerate(_sequence(raw_g_d, name="g_D", length=scales - 1))),
        g_C=tuple(_finite(item, name=f"g_C[{index}]", positive=True) for index, item in enumerate(_sequence(raw_g_c, name="g_C", length=scales - 1))),
        phi=phi,
        c_D=_scale_values("c_D_m_per_s", "c_D"),
        c_C=_scale_values("c_C_m_per_s", "c_C"),
        metric_cell_areas=tuple(float(surface.cell_area_m2(scale)) for scale in range(scales)),
        enabled=bool(coupling.get("enabled", True) if enabled is None else enabled),
        law_id=str(coupling.get("law_id", W6_CROSS_SCALE_LAW_ID)),
        operator_family=str(payload.get("spatial", {}).get("operator_family", "periodic-fft2.v1")) if isinstance(payload.get("spatial", {}), Mapping) else "periodic-fft2.v1",
        p_operator_sha256=str(coupling.get("p_operator_sha256", "")),
        p_adjoint_sha256=str(coupling.get("p_adjoint_sha256", "")),
        potential_quadrature=str(coupling.get("potential_quadrature", "positive-cell-metric.v1")),
        force_pullback=str(coupling.get("force_pullback", "weighted-adjoint-reciprocal.v1")),
        phase_current_sign=str(coupling.get("phase_current_sign", "positive-fine-to-coarse.v1")),
        absent_endpoint_links=str(coupling.get("absent_endpoint_links", "exact-zero.v1")),
        tolerances=tol,
        parent_identities=parent,
        active_site_counts=tuple(int(surface.active_site_count(scale)) for scale in range(scales)),
        operator_identity={"link_pairs": tuple((index, index + 1) for index in range(scales - 1)), "links": operator_rows},
    )


def load_w6_cross_scale_profile(
    geometry_profile: Any | None = None,
    *,
    geometry: Any | None = None,
    carrier_profile: Any | None = None,
    parent_identities: Mapping[str, Any] | None = None,
    enabled: bool | None = None,
    g_D: Sequence[Any] | None = None,
    g_C: Sequence[Any] | None = None,
    tolerances: Mapping[str, Any] | None = None,
) -> QiCrossScaleProfile:
    """Materialize W6 from the supplied validated W2/carrier parent profiles."""
    target = geometry_profile if geometry_profile is not None else geometry
    if target is None:
        raise CrossScaleError("geometry_profile is required")
    return _profile_from_geometry(
        target,
        carrier_profile=carrier_profile,
        parent_identities=parent_identities,
        enabled=enabled,
        g_D=g_D,
        g_C=g_C,
        tolerances=tolerances,
    )


load_cross_scale_profile = load_w6_cross_scale_profile


def validate_w6_cross_scale_profile(profile_or_payload: QiCrossScaleProfile | Mapping[str, Any], *, geometry: Any | None = None) -> QiCrossScaleProfile:
    if isinstance(profile_or_payload, QiCrossScaleProfile):
        profile = profile_or_payload
    elif isinstance(profile_or_payload, Mapping):
        serialized = dict(profile_or_payload)
        root = serialized.pop("root", {})
        if root is None:
            root = {}
        if not isinstance(root, Mapping):
            raise CrossScaleError("root must be a mapping")
        root_sha256 = serialized.pop("root_sha256", None)
        if root_sha256 is None:
            root_sha256 = root.get("self_sha256", serialized.pop("self_sha256", ""))
        operator_identity = serialized.pop("operator_identity", None)
        metric = serialized.get("metric", {})
        operator = serialized.get("operator", {})
        conventions = serialized.get("conventions", {})
        speeds = serialized.get("speeds", {})
        if not isinstance(metric, Mapping) or not isinstance(operator, Mapping) or not isinstance(conventions, Mapping) or not isinstance(speeds, Mapping):
            raise CrossScaleError("serialized cross-scale profile sections must be mappings")
        nested_operator_identity = {
            key: value
            for key, value in operator.items()
            if key not in {"family", "p_operator_sha256", "p_adjoint_sha256"}
        }
        if operator_identity is None:
            operator_identity = nested_operator_identity
        else:
            if not isinstance(operator_identity, Mapping):
                raise CrossScaleError("operator_identity must be a mapping")
            merged_operator_identity = dict(nested_operator_identity)
            merged_operator_identity.update(_plain(operator_identity))
            operator_identity = merged_operator_identity
        profile = QiCrossScaleProfile(
            scale_count=int(serialized.get("scale_count", 0)),
            link_pairs=tuple(tuple(pair) for pair in serialized.get("link_pairs", ())),
            g_D=tuple(serialized.get("g_D", ())),
            g_C=tuple(serialized.get("g_C", ())),
            phi=_finite(metric.get("phi"), name="metric.phi", positive=True),
            w_D=metric.get("w_D"),
            w_C=metric.get("w_C"),
            c_D=tuple(speeds.get("c_D", ())),
            c_C=tuple(speeds.get("c_C", ())),
            metric_cell_areas=tuple(metric.get("cell_areas", ())),
            enabled=bool(serialized.get("enabled", True)),
            law_id=str(serialized.get("law_id", W6_CROSS_SCALE_LAW_ID)),
            operator_family=str(operator.get("family", "periodic-fft2.v1")),
            p_operator_sha256=str(operator.get("p_operator_sha256", "")),
            p_adjoint_sha256=str(operator.get("p_adjoint_sha256", "")),
            potential_quadrature=str(conventions.get("potential_quadrature", "positive-cell-metric.v1")),
            force_pullback=str(conventions.get("force_pullback", "weighted-adjoint-reciprocal.v1")),
            phase_current_sign=str(conventions.get("phase_current_sign", "positive-fine-to-coarse.v1")),
            absent_endpoint_links=str(conventions.get("absent_endpoint_links", "exact-zero.v1")),
            tolerances=serialized.get("tolerances", {}),
            parent_identities=serialized.get("parent_identities", {}),
            operator_identity=operator_identity,
            active_site_counts=tuple(serialized.get("active_site_counts", ())),
            payload=serialized,
            root=root,
            profile_sha256=str(serialized.get("profile_sha256", "")),
            root_sha256=str(root_sha256 or ""),
        )
    else:
        raise CrossScaleError("profile must be QiCrossScaleProfile or mapping")
    if geometry is not None:
        _validate_profile_geometry(profile, _surface(geometry))
    return profile


@dataclass(frozen=True, slots=True)
class QiHodgeResult:
    scale: int
    coordinate: str
    current: torch.Tensor
    longitudinal: torch.Tensor
    transverse: torch.Tensor
    harmonic: torch.Tensor
    current_spectrum: torch.Tensor
    longitudinal_spectrum: torch.Tensor
    transverse_spectrum: torch.Tensor
    harmonic_spectrum: torch.Tensor
    nullspace_mask: torch.Tensor
    reconstruction_residual: torch.Tensor
    metric_longitudinal_transverse: torch.Tensor
    divergence: torch.Tensor
    curl: torch.Tensor
    longitudinal_divergence: torch.Tensor
    transverse_curl: torch.Tensor
    flux: torch.Tensor
    circulation: torch.Tensor
    zero_mode: torch.Tensor
    nullspace_dimension: int
    inactive_tail_zero: bool = True

    def __getitem__(self, key: str) -> Any:
        aliases = {"L": "longitudinal", "T": "transverse", "H": "harmonic", "reconstruction": "reconstruction_residual", "orthogonality": "metric_longitudinal_transverse"}
        return getattr(self, aliases.get(key, key))

    def as_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "schema": W6_HODGE_SCHEMA,
                "scale": self.scale,
                "coordinate": self.coordinate,
                "L": self.longitudinal,
                "T": self.transverse,
                "H": self.harmonic,
                "reconstruction_residual": self.reconstruction_residual,
                "metric_longitudinal_transverse": self.metric_longitudinal_transverse,
                "divergence": self.divergence,
                "curl": self.curl,
                "flux": self.flux,
                "circulation": self.circulation,
                "zero_mode": self.zero_mode,
                "nullspace_dimension": self.nullspace_dimension,
                "inactive_tail_zero": self.inactive_tail_zero,
            }
        )
@dataclass(frozen=True, slots=True)
class QiCrossScaleLaw:
    """Immutable conservative-law bundle consumed by W5's private split."""

    profile: QiCrossScaleProfile
    law_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, QiCrossScaleProfile):
            raise CrossScaleError("QiCrossScaleLaw requires a QiCrossScaleProfile")
        object.__setattr__(self, "law_id", self.profile.law_id)

    @property
    def enabled(self) -> bool:
        return self.profile.enabled

    def with_enabled(self, enabled: bool) -> "QiCrossScaleLaw":
        return QiCrossScaleLaw(self.profile.with_enabled(enabled))

    @classmethod
    def bind(cls, profile: QiCrossScaleProfile) -> "QiCrossScaleLaw":
        return cls(validate_w6_cross_scale_profile(profile))

    @classmethod
    def from_profile(cls, profile: QiCrossScaleProfile) -> "QiCrossScaleLaw":
        return cls.bind(profile)

    def energy(
        self,
        state: Any,
        geometry: Any | None = None,
        carrier_profile: Any | None = None,
        coords: Any | None = None,
        **kwargs: Any,
    ) -> torch.Tensor:
        geometry = geometry if geometry is not None else kwargs.get("geometry_profile")
        if geometry is None:
            raise CrossScaleError("cross-scale energy requires geometry")
        return cross_scale_energy(state, geometry=geometry, profile=self.profile, carrier_profile=carrier_profile, coords=coords)

    def energy_per_batch(self, state: Any, geometry: Any, carrier_profile: Any | None = None, coords: Any | None = None) -> torch.Tensor:
        return cross_scale_energy_per_batch(state, geometry=geometry, profile=self.profile, carrier_profile=carrier_profile, coords=coords)

    def additional_force(self, state: Any, geometry: Any, carrier_profile: Any | None = None, coords: Any | None = None) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
        return cross_scale_forces(state, geometry=geometry, profile=self.profile, carrier_profile=carrier_profile, coords=coords)


    def euclidean_forces(self, state: Any, geometry: Any, carrier_profile: Any | None = None, coords: Any | None = None) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
        return cross_scale_euclidean_forces(state, geometry=geometry, profile=self.profile, carrier_profile=carrier_profile, coords=coords)
    def link_forces(self, state: Any, geometry: Any, carrier_profile: Any | None = None, coords: Any | None = None, *, adjoint_matrices: Any | None = None) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
        return cross_scale_forces(state, geometry=geometry, profile=self.profile, carrier_profile=carrier_profile, coords=coords, adjoint_matrices=adjoint_matrices)

    def link_energy_rows(self, state: Any, geometry: Any, carrier_profile: Any | None = None, coords: Any | None = None) -> tuple[Mapping[str, Any], ...]:
        return cross_scale_link_energy_rows(state, geometry=geometry, profile=self.profile, carrier_profile=carrier_profile, coords=coords)

    def work_rows(self, predecessor: Any, candidate: Any, geometry: Any, duration_s: float, carrier_profile: Any | None = None) -> tuple[Mapping[str, Any], ...]:
        return cross_scale_work_rows(predecessor, candidate, geometry=geometry, duration_s=duration_s, profile=self.profile, carrier_profile=carrier_profile)

    def phase_current(self, state: Any, geometry: Any, coordinate: str = "D", carrier_profile: Any | None = None, coords: Any | None = None) -> tuple[torch.Tensor, ...]:
        return cross_scale_phase_current(state, geometry=geometry, profile=self.profile, coordinate=coordinate, carrier_profile=carrier_profile, coords=coords)

    def phase_charge(self, state: Any, geometry: Any, coordinate: str = "D", carrier_profile: Any | None = None, coords: Any | None = None) -> tuple[torch.Tensor, ...]:
        return phase_charges(state, geometry=geometry, profile=self.profile, coordinate=coordinate, carrier_profile=carrier_profile, coords=coords)

    def continuity(self, predecessor: Any, candidate: Any, geometry: Any, duration_s: float, coordinate: str = "D", carrier_profile: Any | None = None) -> Mapping[str, Any]:
        return cross_scale_continuity(predecessor, candidate, geometry=geometry, duration_s=duration_s, profile=self.profile, coordinate=coordinate, carrier_profile=carrier_profile)

    def spatial_current(self, state: Any, geometry: Any, coordinate: str = "D", carrier_profile: Any | None = None, coords: Any | None = None) -> tuple[torch.Tensor, ...]:
        return spatial_currents(state, geometry=geometry, profile=self.profile, coordinate=coordinate, carrier_profile=carrier_profile, coords=coords)

    def hodge(self, state: Any, geometry: Any, coordinate: str = "D", carrier_profile: Any | None = None, coords: Any | None = None, *, derivative_symbols: Any | None = None) -> tuple[QiHodgeResult, ...]:
        return hodge_diagnostics(state, geometry=geometry, profile=self.profile, coordinate=coordinate, carrier_profile=carrier_profile, coords=coords, derivative_symbols=derivative_symbols)

    def diagnostics(self, state: Any, geometry: Any, carrier_profile: Any | None = None, coords: Any | None = None) -> Mapping[str, Any]:
        return cross_scale_diagnostics(state, geometry=geometry, profile=self.profile, carrier_profile=carrier_profile, coords=coords)


def build_w6_cross_scale_law(profile: QiCrossScaleProfile) -> QiCrossScaleLaw:
    return QiCrossScaleLaw(validate_w6_cross_scale_profile(profile))


def load_w6_cross_scale_law(
    geometry_profile: Any | None = None,
    *,
    geometry: Any | None = None,
    cross_scale_profile: QiCrossScaleProfile | None = None,
    carrier_profile: Any | None = None,
    **kwargs: Any,
) -> QiCrossScaleLaw:
    profile = cross_scale_profile or load_w6_cross_scale_profile(geometry_profile, geometry=geometry, carrier_profile=carrier_profile, **kwargs)
    return build_w6_cross_scale_law(profile)


build_cross_scale_law = build_w6_cross_scale_law
load_cross_scale_law = load_w6_cross_scale_law


def _coordinate_pair(coordinate: str, values: tuple[tuple[torch.Tensor, ...], ...]) -> tuple[torch.Tensor, ...]:
    if not isinstance(coordinate, str) or coordinate.upper() not in {"D", "C"}:
        raise CrossScaleError("coordinate must be D or C")
    return values[0] if coordinate.upper() == "D" else values[1]


def _velocity_pair(coordinate: str, values: tuple[tuple[torch.Tensor, ...], ...]) -> tuple[torch.Tensor, ...]:
    return values[2] if coordinate.upper() == "D" else values[3]


def _link_energy_values(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
    surface = _surface(geometry)
    _validate_profile_geometry(profile, surface)
    values = _coordinates(state, surface, profile, carrier_profile, coords)
    d_values, c_values = values[0], values[1]
    result_d: list[torch.Tensor] = []
    result_c: list[torch.Tensor] = []
    for index, (source, target) in enumerate(profile.link_pairs):
        d_delta = d_values[target] - _transfer(surface, d_values[source], source, target)
        c_delta = c_values[target] - _transfer(surface, c_values[source], source, target)
        if profile.enabled:
            ed = 0.5 * profile.w_D * profile.g_D[index] * surface.weighted_inner(d_delta, d_delta, scale=target).real
            ec = 0.5 * profile.w_C * profile.g_C[index] * surface.weighted_inner(c_delta, c_delta, scale=target).real
        else:
            ed = d_delta.real.sum(dim=(0, 1)) * 0.0
            ec = c_delta.real.sum(dim=(0, 1)) * 0.0
        result_d.append(ed.contiguous())
        result_c.append(ec.contiguous())
    return tuple(result_d), tuple(result_c)


def cross_scale_energy_per_batch(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> torch.Tensor:
    energies_d, energies_c = _link_energy_values(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords)
    if not energies_d:
        return _state_field(state).new_zeros((_state_field(state).shape[2],), dtype=torch.float64)
    return torch.stack(tuple(energies_d) + tuple(energies_c), dim=0).sum(dim=0)


def cross_scale_energy(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> torch.Tensor:
    """Return total link potential as a differentiable scalar tensor."""
    return cross_scale_energy_per_batch(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords).sum()


def cross_scale_link_energy_rows(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> tuple[Mapping[str, Any], ...]:
    energies_d, energies_c = _link_energy_values(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords)
    rows: list[Mapping[str, Any]] = []
    for index, (source, target) in enumerate(profile.link_pairs):
        row = {
            "link_index": index,
            "source_scale": source,
            "target_scale": target,
            "g_D": profile.g_D[index],
            "g_C": profile.g_C[index],
            "energy_D": energies_d[index],
            "energy_C": energies_c[index],
            "energy": energies_d[index] + energies_c[index],
            "link_energy_D": energies_d[index],
            "link_energy_C": energies_c[index],
        }
        rows.append(MappingProxyType(row))
    return tuple(rows)


def cross_scale_link_energy(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    coordinate: str | None = None,
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> Any:
    rows = cross_scale_link_energy_rows(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords)
    if coordinate is None:
        return rows
    label = coordinate.upper()
    if label not in {"D", "C"}:
        raise CrossScaleError("coordinate must be D or C")
    return tuple(row[f"energy_{label}"] for row in rows)


def _force_values(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    carrier_profile: Any | None = None,
    coords: Any | None = None,
    adjoint_matrices: Any | None = None,
) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
    surface = _surface(geometry)
    _validate_profile_geometry(profile, surface)
    values = _coordinates(state, surface, profile, carrier_profile, coords)
    d_values, c_values = values[0], values[1]
    d_forces = [torch.zeros_like(value) for value in d_values]
    c_forces = [torch.zeros_like(value) for value in c_values]
    if not profile.enabled:
        return tuple(d_forces), tuple(c_forces)
    for index, (source, target) in enumerate(profile.link_pairs):
        override = _link_override(adjoint_matrices, index, source, target)
        p_dagger = _metric_adjoint(surface, profile, source, target, index, override)
        d_delta = d_values[target] - _transfer(surface, d_values[source], source, target)
        c_delta = c_values[target] - _transfer(surface, c_values[source], source, target)
        d_forces[source] = d_forces[source] + profile.g_D[index] * _adjoint_transfer(surface, d_delta, source, target, p_dagger)
        d_forces[target] = d_forces[target] - profile.g_D[index] * d_delta
        c_forces[source] = c_forces[source] + profile.g_C[index] * _adjoint_transfer(surface, c_delta, source, target, p_dagger)
        c_forces[target] = c_forces[target] - profile.g_C[index] * c_delta
    return tuple(value.contiguous() for value in d_forces), tuple(value.contiguous() for value in c_forces)


def cross_scale_forces(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    carrier_profile: Any | None = None,
    coords: Any | None = None,
    adjoint_matrices: Any | None = None,
) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
    """Return all reciprocal D/C link forces, scattered only over active sheets."""
    return _force_values(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords, adjoint_matrices=adjoint_matrices)


link_forces = cross_scale_forces
additional_force = cross_scale_forces


def cross_scale_euclidean_forces(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...]]:
    """Return ``-dE/dZ`` in Euclidean coordinates.

    ``additional_force`` is the metric-normalized Hamiltonian acceleration
    required by W5 (``g P^† Delta`` and ``-g Delta``).  The weighted energy
    has Euclidean negative gradient ``w_Z * additional_force``; exposing it
    separately keeps the force and autograd conventions explicit.
    """
    d_forces, c_forces = cross_scale_forces(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords)
    return tuple(profile.w_D * value for value in d_forces), tuple(profile.w_C * value for value in c_forces)


metric_normalized_forces = cross_scale_forces


def _force_work(displacement: torch.Tensor, force: torch.Tensor, *, surface: PeriodicSheetGeometry, scale: int, weight: float) -> torch.Tensor:
    return (weight * surface.weighted_inner(displacement, force, scale=scale).real).contiguous()


def cross_scale_work_rows(
    predecessor: Any,
    candidate: Any,
    *,
    geometry: Any,
    duration_s: float,
    profile: QiCrossScaleProfile,
    carrier_profile: Any | None = None,
) -> tuple[Mapping[str, Any], ...]:
    duration = _finite(duration_s, name="duration_s", positive=True)
    surface = _surface(geometry)
    pre_values = _coordinates(predecessor, surface, profile, carrier_profile)
    post_values = _coordinates(candidate, surface, profile, carrier_profile)
    pre_forces = _force_values(predecessor, geometry=surface, profile=profile, carrier_profile=carrier_profile)[0:2]
    post_forces = _force_values(candidate, geometry=surface, profile=profile, carrier_profile=carrier_profile)[0:2]
    pre_energies = _link_energy_values(predecessor, geometry=surface, profile=profile, carrier_profile=carrier_profile)
    post_energies = _link_energy_values(candidate, geometry=surface, profile=profile, carrier_profile=carrier_profile)
    rows: list[Mapping[str, Any]] = []
    for index, (source, target) in enumerate(profile.link_pairs):
        row: dict[str, Any] = {"link_index": index, "source_scale": source, "target_scale": target}
        for label, weight, value_index in (("D", profile.w_D, 0), ("C", profile.w_C, 1)):
            pre_pair = pre_values[value_index]
            post_pair = post_values[value_index]
            pre_force_pair = pre_forces[value_index]
            post_force_pair = post_forces[value_index]
            source_displacement = post_pair[source] - pre_pair[source]
            target_displacement = post_pair[target] - pre_pair[target]
            source_force = 0.5 * (pre_force_pair[source] + post_force_pair[source])
            target_force = 0.5 * (pre_force_pair[target] + post_force_pair[target])
            source_work = _force_work(source_displacement, source_force, surface=surface, scale=source, weight=weight)
            target_work = _force_work(target_displacement, target_force, surface=surface, scale=target, weight=weight)
            link_delta = post_energies[value_index][index] - pre_energies[value_index][index]
            closure = source_work + target_work + link_delta
            row[f"W_link_{label}_source"] = source_work

            row[f"W_link_{label}_target"] = target_work
            row[f"W_link_{label}"] = source_work + target_work
            row[f"P_link_{label}_source"] = source_work / duration
            row[f"P_link_{label}_target"] = target_work / duration
            row[f"Delta_E_link_{label}"] = link_delta
            row[f"link_work_closure_{label}"] = closure
            row[label] = MappingProxyType(
                {
                    "source_work": source_work,
                    "target_work": target_work,
                    "link_work": source_work + target_work,
                    "source_power": source_work / duration,
                    "target_power": target_work / duration,
                    "delta_energy": link_delta,
                    "closure": closure,
                }
            )
        rows.append(MappingProxyType(row))
    return tuple(rows)


work_rows = cross_scale_work_rows


def phase_charges(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    coordinate: str = "D",
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> tuple[torch.Tensor, ...]:
    surface = _surface(geometry)
    values = _coordinates(state, surface, profile, carrier_profile, coords)
    positions = _coordinate_pair(coordinate, values)
    velocities = _velocity_pair(coordinate, values)
    weight = profile.w_D if coordinate.upper() == "D" else profile.w_C
    result: list[torch.Tensor] = []
    for scale, (position, velocity) in enumerate(zip(positions, velocities, strict=True)):
        density = weight * (position.conj() * velocity).imag
        ones = torch.ones_like(density)
        result.append(surface.weighted_inner(ones, density, scale=scale).real.contiguous())
    return tuple(result)


phase_charge = phase_charges


def cross_scale_phase_current(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    coordinate: str = "D",
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> tuple[torch.Tensor, ...]:
    surface = _surface(geometry)
    values = _coordinates(state, surface, profile, carrier_profile, coords)
    positions = _coordinate_pair(coordinate, values)
    weight = profile.w_D if coordinate.upper() == "D" else profile.w_C
    result: list[torch.Tensor] = []
    if not profile.enabled:
        return tuple(position.real.sum(dim=(0, 1)) * 0.0 for position in positions[:-1])
    for index, (source, target) in enumerate(profile.link_pairs):
        delta = positions[target] - _transfer(surface, positions[source], source, target)
        mapped = _transfer(surface, positions[source], source, target)
        inner = surface.weighted_inner(mapped, delta, scale=target)
        result.append((-weight * (profile.g_D[index] if coordinate.upper() == "D" else profile.g_C[index]) * inner.imag).contiguous())
    return tuple(result)


phase_current = cross_scale_phase_current


def cross_scale_continuity(
    predecessor: Any,
    candidate: Any,
    *,
    geometry: Any,
    duration_s: float,
    profile: QiCrossScaleProfile,
    coordinate: str = "D",
    carrier_profile: Any | None = None,
    residuals: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    duration = _finite(duration_s, name="duration_s", positive=True)
    surface = _surface(geometry)
    pre_values = _coordinates(predecessor, surface, profile, carrier_profile)
    post_values = _coordinates(candidate, surface, profile, carrier_profile)
    pre_q = phase_charges(predecessor, geometry=surface, profile=profile, coordinate=coordinate, carrier_profile=carrier_profile)
    post_q = phase_charges(candidate, geometry=surface, profile=profile, coordinate=coordinate, carrier_profile=carrier_profile)
    pre_j = spatial_currents(predecessor, geometry=surface, profile=profile, coordinate=coordinate, carrier_profile=carrier_profile)
    post_j = spatial_currents(candidate, geometry=surface, profile=profile, coordinate=coordinate, carrier_profile=carrier_profile)
    pre_k = cross_scale_phase_current(predecessor, geometry=surface, profile=profile, coordinate=coordinate, carrier_profile=carrier_profile)
    post_k = cross_scale_phase_current(candidate, geometry=surface, profile=profile, coordinate=coordinate, carrier_profile=carrier_profile)
    mid_k = tuple(0.5 * (a + b) for a, b in zip(pre_k, post_k, strict=True))
    rows: list[Mapping[str, Any]] = []
    outgoing: list[torch.Tensor] = []
    incoming: list[torch.Tensor] = []
    zero_k = torch.zeros_like(pre_q[0])
    rhs_names = ("boundary", "remap", "composition", "conversion", "residual", "retention", "port", "damping", "numeric")
    for scale in range(profile.scale_count):
        active = surface.sheet_shape(scale)
        area = float(surface.cell_area_m2(scale))
        divergence_pre = surface.divergence(pre_j[scale], scale=scale).real
        divergence_post = surface.divergence(post_j[scale], scale=scale).real
        flux = 0.5 * area * (divergence_pre.sum(dim=(0, 1)) + divergence_post.sum(dim=(0, 1)))
        out = mid_k[scale] if scale < profile.scale_count - 1 else zero_k
        inc = mid_k[scale - 1] if scale > 0 else zero_k
        outgoing.append(out)
        incoming.append(inc)
        lhs = (post_q[scale] - pre_q[scale]) / duration + flux + out - inc
        terms: dict[str, torch.Tensor] = {}
        for name in rhs_names:
            value = residuals.get(name, 0.0) if isinstance(residuals, Mapping) else 0.0
            if torch.is_tensor(value):
                terms[name] = value.to(dtype=lhs.dtype)
            else:
                terms[name] = torch.full_like(lhs, float(value))
        rhs = sum(terms.values(), torch.zeros_like(lhs))
        row = {
            "scale": scale,
            "coordinate": coordinate.upper(),
            "Q_pre": pre_q[scale],
            "Q_post": post_q[scale],
            "dQ_dt": (post_q[scale] - pre_q[scale]) / duration,
            "Phi_spatial": flux,
            "K_out": out,
            "K_in": inc,
            "lhs": lhs,
            "rhs_terms": MappingProxyType(terms),
            "rhs": rhs,
            "residual": lhs - rhs,
            "endpoint_outgoing_exact_zero": scale == profile.scale_count - 1,
            "endpoint_incoming_exact_zero": scale == 0,
            "active_shape": active,
        }
        rows.append(MappingProxyType(row))
    internal_cancellation = sum(outgoing, torch.zeros_like(outgoing[0])) - sum(incoming, torch.zeros_like(incoming[0])) if outgoing else torch.zeros(0, dtype=torch.float64)
    return MappingProxyType(
        {
            "schema": "cassi.qi-flow-space-scale-continuity.v1",
            "coordinate": coordinate.upper(),
            "duration_s": duration,
            "per_scale": tuple(rows),
            "K_outgoing": tuple(outgoing),
            "K_incoming": tuple(incoming),
            "internal_K_cancellation": internal_cancellation,
            "summed_lhs": sum((row["lhs"] for row in rows), torch.zeros_like(outgoing[0])) if rows else torch.zeros(0, dtype=torch.float64),
            "summed_rhs": sum((row["rhs"] for row in rows), torch.zeros_like(outgoing[0])) if rows else torch.zeros(0, dtype=torch.float64),
        }
    )


continuity = cross_scale_continuity


def _speed(profile: QiCrossScaleProfile, coordinate: str, scale: int, carrier_profile: Any | None) -> float:
    values = profile.c_D if coordinate.upper() == "D" else profile.c_C
    if carrier_profile is not None:
        candidate = getattr(carrier_profile, "c_D" if coordinate.upper() == "D" else "c_C", None)
        if candidate is not None:
            values = tuple(float(item) for item in candidate)
    return _finite(values[scale], name=f"c_{coordinate}[{scale}]", positive=True)


def spatial_currents(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    coordinate: str = "D",
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> tuple[torch.Tensor, ...]:
    surface = _surface(geometry)
    values = _coordinates(state, surface, profile, carrier_profile, coords)
    positions = _coordinate_pair(coordinate, values)
    weight = profile.w_D if coordinate.upper() == "D" else profile.w_C
    result: list[torch.Tensor] = []
    for scale, position in enumerate(positions):
        gradient = surface.gradient(position, scale=scale)
        speed2 = _speed(profile, coordinate, scale, carrier_profile) ** 2
        result.append((-weight * speed2 * (position.conj().unsqueeze(0) * gradient).imag).contiguous())
    return tuple(result)


spatial_current = spatial_currents


def _derivative_symbols(surface: PeriodicSheetGeometry, scale: int, override: Any | None) -> tuple[torch.Tensor, torch.Tensor]:
    ky, kx = surface.angular_wavenumber_axes(scale)
    expected_kx = kx.to(torch.float64)
    expected_ky = ky.to(torch.float64)
    if override is None:
        return expected_kx, expected_ky
    if isinstance(override, Mapping):
        candidate_kx = override.get("kx")
        candidate_ky = override.get("ky")
    elif isinstance(override, Sequence) and not isinstance(override, (str, bytes, bytearray)) and len(override) == 2:
        candidate_kx, candidate_ky = override
    else:
        raise CrossScaleError("derivative_symbols must provide kx and ky")
    if candidate_kx is None or candidate_ky is None:
        raise CrossScaleError("derivative_symbols must provide both kx and ky")
    candidate_kx = torch.as_tensor(candidate_kx, dtype=torch.float64)
    candidate_ky = torch.as_tensor(candidate_ky, dtype=torch.float64)
    if tuple(candidate_kx.shape) != tuple(expected_kx.shape) or tuple(candidate_ky.shape) != tuple(expected_ky.shape) or not torch.equal(candidate_kx, expected_kx) or not torch.equal(candidate_ky, expected_ky):
        raise CrossScaleError("Hodge derivative symbol does not match periodic-FFT2 profile")
    return expected_kx, expected_ky


def hodge_decompose(
    current: torch.Tensor,
    *,
    geometry: Any,
    scale: int,
    coordinate: str = "D",
    derivative_symbols: Any | None = None,
) -> QiHodgeResult:
    surface = _surface(geometry)
    try:
        current = current if torch.is_tensor(current) else torch.as_tensor(current)
        expected = (2, *surface.sheet_shape(scale), current.shape[-1] if current.ndim else 0)
    except Exception as exc:
        raise CrossScaleError("Hodge current is not a tensor") from exc
    if current.ndim != 4 or tuple(current.shape[:3]) != expected[:3] or current.device.type != "cpu" or current.dtype not in (torch.float64, torch.complex128) or not current.is_contiguous():
        raise CrossScaleError("Hodge current must have shape [2,Ny,Nx,B] on contiguous CPU float64/complex128")
    if not bool(torch.isfinite(current).all().item()):
        raise CrossScaleError("Hodge current is non-finite")
    kx, ky = _derivative_symbols(surface, scale, derivative_symbols)
    spectrum = surface.fft2(current, scale=scale)
    # Keep vector, spatial, and batch axes explicit to avoid broadcasting a
    # wavenumber into the batch dimension.
    dx = 1.0j * kx[None, None, :, None].to(torch.complex128)
    dy = 1.0j * ky[None, :, None, None].to(torch.complex128)
    denominator = dx.conj() * dx + dy.conj() * dy
    nullspace = denominator[0, :, :, 0].abs() == 0.0
    mask = nullspace[None, :, :, None]
    harmonic_spectrum = torch.where(mask, spectrum, torch.zeros_like(spectrum))
    numerator = dx.conj() * spectrum[0].unsqueeze(0) + dy.conj() * spectrum[1].unsqueeze(0)
    coefficient = torch.where(mask, torch.zeros_like(numerator), numerator / denominator)
    longitudinal_spectrum = torch.cat((dx * coefficient, dy * coefficient), dim=0).contiguous()
    longitudinal_spectrum = torch.where(mask, torch.zeros_like(longitudinal_spectrum), longitudinal_spectrum)
    transverse_spectrum = (spectrum - longitudinal_spectrum - harmonic_spectrum).contiguous()
    longitudinal = surface.ifft2(longitudinal_spectrum, scale=scale).contiguous()
    transverse = surface.ifft2(transverse_spectrum, scale=scale).contiguous()
    harmonic = surface.ifft2(harmonic_spectrum, scale=scale).contiguous()
    reconstruction = (longitudinal + transverse + harmonic - current).contiguous()
    div = surface.divergence(current, scale=scale)
    curl = surface.curl(current, scale=scale)
    l_div = surface.divergence(longitudinal, scale=scale)
    t_curl = surface.curl(transverse, scale=scale)
    orthogonality = surface.weighted_inner(longitudinal, transverse, scale=scale)
    area = float(surface.cell_area_m2(scale))
    flux = (area * div.sum(dim=(0, 1))).contiguous()
    circulation = (area * curl.sum(dim=(0, 1))).contiguous()
    zero_y = int((surface.frequency_axes(scale)[0] == 0).nonzero(as_tuple=False)[0].item())
    zero_x = int((surface.frequency_axes(scale)[1] == 0).nonzero(as_tuple=False)[0].item())
    zero_mode = harmonic_spectrum[:, zero_y, zero_x, :].contiguous()
    return QiHodgeResult(
        scale=scale,
        coordinate=coordinate.upper(),
        current=current,
        longitudinal=longitudinal,
        transverse=transverse,
        harmonic=harmonic,
        current_spectrum=spectrum,
        longitudinal_spectrum=longitudinal_spectrum,
        transverse_spectrum=transverse_spectrum,
        harmonic_spectrum=harmonic_spectrum,
        nullspace_mask=nullspace,
        reconstruction_residual=reconstruction,
        metric_longitudinal_transverse=orthogonality,
        divergence=div,
        curl=curl,
        longitudinal_divergence=l_div,
        transverse_curl=t_curl,
        flux=flux,
        circulation=circulation,
        zero_mode=zero_mode,
        nullspace_dimension=int(nullspace.count_nonzero().item()),
        inactive_tail_zero=True,
    )


def hodge_diagnostics(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    coordinate: str = "D",
    carrier_profile: Any | None = None,
    coords: Any | None = None,
    derivative_symbols: Any | None = None,
) -> tuple[QiHodgeResult, ...]:
    currents = spatial_currents(state, geometry=geometry, profile=profile, coordinate=coordinate, carrier_profile=carrier_profile, coords=coords)
    if isinstance(derivative_symbols, Sequence) and not isinstance(derivative_symbols, (str, bytes, bytearray)) and len(derivative_symbols) == profile.scale_count:
        symbols = tuple(derivative_symbols)
    else:
        symbols = tuple(derivative_symbols for _ in range(profile.scale_count))
    return tuple(hodge_decompose(current, geometry=geometry, scale=scale, coordinate=coordinate, derivative_symbols=symbols[scale]) for scale, current in enumerate(currents))


hodge = hodge_diagnostics


def phase_current_reversal(state: Any, *, geometry: Any | None = None) -> Any:
    tensor = _state_field(state)
    result = tensor.clone()
    modes = tensor.shape[1] // 9
    for component in (1, 3, 5, 7):
        result[:, component * modes : (component + 1) * modes, :].mul_(-1.0)
    if hasattr(state, "field"):
        return type(state)(result.contiguous())
    return result.contiguous()


reverse_phase_current = phase_current_reversal


def phase_shuffled_equal_energy(state: Any, *, geometry: Any | None = None) -> Any:
    tensor = _state_field(state)
    result = tensor.clone()
    modes = tensor.shape[1] // 9
    signs = torch.ones((modes,), dtype=result.real.dtype)
    signs[1::2] = -1.0
    for component in range(8):
        result[:, component * modes : (component + 1) * modes, :].mul_(signs.view(1, modes, 1))
    if hasattr(state, "field"):
        return type(state)(result.contiguous())
    return result.contiguous()


def source_target_swap(row: Mapping[str, Any]) -> Mapping[str, Any]:
    """Relabel one already-computed directed link row without changing physics."""
    if not isinstance(row, Mapping):
        raise CrossScaleError("source_target_swap requires a link row mapping")
    result = dict(row)
    source = row.get("source_scale")
    target = row.get("target_scale")
    result["source_scale"], result["target_scale"] = target, source
    for name in ("K", "K_out", "K_in"):
        if name in result and torch.is_tensor(result[name]):
            result[name] = -result[name]
    for label in ("D", "C"):
        nested = row.get(label)
        if isinstance(nested, Mapping):
            swapped = dict(nested)
            for first, second in (("source_work", "target_work"), ("source_power", "target_power")):
                if first in nested or second in nested:
                    swapped[first], swapped[second] = nested.get(second), nested.get(first)
            result[label] = MappingProxyType(swapped)
    return MappingProxyType(result)


def wrong_metric_adjoint(geometry: Any, source_scale: int, target_scale: int) -> torch.Tensor:
    """Return a deliberately unweighted/perturbed adjoint for rejection controls."""
    surface = _surface(geometry)
    return (surface.cross_scale_matrix(source_scale, target_scale).conj().T * 1.125).contiguous()


def reject_wrong_metric_adjoint(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    coordinate: str = "D",
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> None:
    bad = tuple(wrong_metric_adjoint(geometry, source, target) for source, target in profile.link_pairs)
    cross_scale_forces(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords, adjoint_matrices=bad)
    raise CrossScaleError("wrong metric adjoint was not rejected")


def active_subspace_impulse(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    link_index: int = 0,
    coordinate: str = "D",
    target_pattern: torch.Tensor | None = None,
) -> Mapping[str, Any]:
    surface = _surface(geometry)
    if link_index < 0 or link_index >= len(profile.link_pairs):
        raise CrossScaleError("link_index is outside the adjacent-link set")
    source, target = profile.link_pairs[link_index]
    values = _coordinates(state, surface, profile)
    target_values = _coordinate_pair(coordinate, values)[target]
    if target_pattern is None:
        target_active = torch.zeros_like(target_values)
        target_active.view(-1, target_active.shape[-1])[0].fill_(1.0)
    else:
        target_active = _as_complex(target_pattern)
        if tuple(target_active.shape) != tuple(target_values.shape):
            raise CrossScaleError("target_pattern shape does not match the target active sheet")
    source_active = _adjoint_transfer(surface, target_active, source, target)
    return MappingProxyType(
        {
            "link_index": link_index,
            "source_scale": source,
            "target_scale": target,
            "coordinate": coordinate.upper(),
            "target": target_active,
            "source": source_active,
            "retained_subspace_impulse": _transfer(surface, source_active, source, target),
        }
    )


def known_nullspace(geometry: Any, source_scale: int, target_scale: int, *, tolerance: float | None = None) -> Mapping[str, Any]:
    surface = _surface(geometry)
    matrix = surface.cross_scale_matrix(source_scale, target_scale)
    singular = torch.linalg.svdvals(matrix)
    tol = float(tolerance if tolerance is not None else torch.finfo(torch.float64).eps * max(matrix.shape) * float(singular.max().item() if singular.numel() else 1.0))
    rank = int((singular > tol).sum().item())
    _, _, vh = torch.linalg.svd(matrix)
    kernel = vh[rank:].conj().T.contiguous()
    return MappingProxyType({"source_scale": source_scale, "target_scale": target_scale, "rank": rank, "nullity": int(matrix.shape[1] - rank), "singular_values": singular, "kernel_basis": kernel, "tolerance": tol})


def frozen_scale(state: Any, *, geometry: Any | None = None) -> Any:
    """Return an out-of-place zero-velocity control state."""
    tensor = _state_field(state)
    result = tensor.clone()
    modes = tensor.shape[1] // 9
    result[:, 4 * modes : 8 * modes, :].zero_()
    if hasattr(state, "field"):
        return type(state)(result.contiguous())
    return result.contiguous()


def frozen_scale_diagnostics(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    duration_s: float,
    carrier_profile: Any | None = None,
) -> Mapping[str, Any]:
    control = frozen_scale(state, geometry=geometry)
    return MappingProxyType(
        {
            "state": control,
            "phase_charge_D": phase_charges(control, geometry=geometry, profile=profile, coordinate="D", carrier_profile=carrier_profile),
            "phase_charge_C": phase_charges(control, geometry=geometry, profile=profile, coordinate="C", carrier_profile=carrier_profile),
            "continuity_D": cross_scale_continuity(control, control, geometry=geometry, duration_s=duration_s, profile=profile, coordinate="D", carrier_profile=carrier_profile),
            "continuity_C": cross_scale_continuity(control, control, geometry=geometry, duration_s=duration_s, profile=profile, coordinate="C", carrier_profile=carrier_profile),
        }
    )


def link_off(profile_or_law: QiCrossScaleProfile | QiCrossScaleLaw) -> QiCrossScaleLaw:
    law = profile_or_law if isinstance(profile_or_law, QiCrossScaleLaw) else QiCrossScaleLaw(profile_or_law)
    return law.with_enabled(False)


def cross_scale_diagnostics(
    state: Any,
    *,
    geometry: Any,
    profile: QiCrossScaleProfile,
    carrier_profile: Any | None = None,
    coords: Any | None = None,
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            "schema": "cassi.qi-flow-space-scale-diagnostics.v1",
            "profile_sha256": profile.profile_sha256,
            "law_id": profile.law_id,
            "energy": cross_scale_energy(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords),
            "energy_per_batch": cross_scale_energy_per_batch(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords),
            "link_rows": cross_scale_link_energy_rows(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords),
            "forces": cross_scale_forces(state, geometry=geometry, profile=profile, carrier_profile=carrier_profile, coords=coords),
            "phase_charge_D": phase_charges(state, geometry=geometry, profile=profile, coordinate="D", carrier_profile=carrier_profile, coords=coords),
            "phase_charge_C": phase_charges(state, geometry=geometry, profile=profile, coordinate="C", carrier_profile=carrier_profile, coords=coords),
            "phase_current_D": cross_scale_phase_current(state, geometry=geometry, profile=profile, coordinate="D", carrier_profile=carrier_profile, coords=coords),
            "phase_current_C": cross_scale_phase_current(state, geometry=geometry, profile=profile, coordinate="C", carrier_profile=carrier_profile, coords=coords),
            "spatial_current_D": spatial_currents(state, geometry=geometry, profile=profile, coordinate="D", carrier_profile=carrier_profile, coords=coords),
            "spatial_current_C": spatial_currents(state, geometry=geometry, profile=profile, coordinate="C", carrier_profile=carrier_profile, coords=coords),
            "hodge_D": hodge_diagnostics(state, geometry=geometry, profile=profile, coordinate="D", carrier_profile=carrier_profile, coords=coords),
            "hodge_C": hodge_diagnostics(state, geometry=geometry, profile=profile, coordinate="C", carrier_profile=carrier_profile, coords=coords),
        }
    )


def _transition_w6_split(
    state: Any,
    *,
    geometry_profile: Any,
    transport_profile: Any,
    carrier_profile: Any,
    topology_profile: Any,
    conversion_profile: Any,
    numerical_certificate: Mapping[str, Any],
    cross_scale_law: QiCrossScaleLaw,
    duration_s: float | None = None,
    conversion_enabled: bool = True,
    epsilon_ema_enabled: bool = True,
    source: Any | None = None,
) -> Any:
    """Private W6 integration hook; W5 owns the actual split and EMA once."""
    if not isinstance(cross_scale_law, QiCrossScaleLaw):
        raise CrossScaleError("private W6 split requires one QiCrossScaleLaw")
    bound_surface = _surface(geometry_profile)
    geometry_identity = getattr(bound_surface.profile, "profile_sha256", getattr(geometry_profile, "profile_sha256", None))
    if cross_scale_law.profile.parent_identities.get("geometry_profile_sha256") not in (None, geometry_identity):
        raise CrossScaleError("W6 law is bound to a different geometry profile")
    from cassi_qi_conversion import _transition_w5_split

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
        extra_conservative_law=cross_scale_law,
    )


def transition_w6_integrated(
    state: Any,
    *,
    geometry_profile: Any,
    transport_profile: Any,
    carrier_profile: Any,
    topology_profile: Any,
    conversion_profile: Any,
    numerical_certificate: Mapping[str, Any],
    cross_scale_profile: QiCrossScaleProfile,
    duration_s: float | None = None,
    conversion_enabled: bool = True,
    epsilon_ema_enabled: bool = True,
    source: Any | None = None,
) -> Any:
    """Bind one frozen W6 profile/law and delegate evolution to W5 exactly once."""
    profile = validate_w6_cross_scale_profile(cross_scale_profile, geometry=geometry_profile)
    law = QiCrossScaleLaw(profile)
    return _transition_w6_split(
        state,
        geometry_profile=geometry_profile,
        transport_profile=transport_profile,
        carrier_profile=carrier_profile,
        topology_profile=topology_profile,
        conversion_profile=conversion_profile,
        numerical_certificate=numerical_certificate,
        cross_scale_law=law,
        duration_s=duration_s,
        conversion_enabled=conversion_enabled,
        epsilon_ema_enabled=epsilon_ema_enabled,
        source=source,
    )


transition_w6 = transition_w6_integrated


__all__ = [
    "W6_CROSS_SCALE_PROFILE_SCHEMA",
    "W6_CROSS_SCALE_ROOT_SCHEMA",
    "W6_CROSS_SCALE_LAW_ID",
    "W6_CROSS_SCALE_PROFILE_DOMAIN",
    "W6_CROSS_SCALE_ROOT_DOMAIN",
    "W6_CROSS_SCALE_LAW_DOMAIN",
    "W6_HODGE_SCHEMA",
    "CrossScaleError",
    "QiCrossScaleError",
    "QiCrossScaleProfile",
    "QiCrossScaleLaw",
    "QiHodgeResult",
    "load_w6_cross_scale_profile",
    "load_cross_scale_profile",
    "validate_w6_cross_scale_profile",
    "build_w6_cross_scale_law",
    "build_cross_scale_law",
    "load_w6_cross_scale_law",
    "load_cross_scale_law",
    "cross_scale_energy",
    "cross_scale_energy_per_batch",
    "cross_scale_link_energy_rows",
    "cross_scale_link_energy",
    "cross_scale_forces",
    "cross_scale_euclidean_forces",
    "metric_normalized_forces",
    "link_forces",
    "additional_force",
    "cross_scale_work_rows",
    "work_rows",
    "phase_charges",
    "phase_charge",
    "cross_scale_phase_current",
    "phase_current",
    "cross_scale_continuity",
    "continuity",
    "spatial_currents",
    "spatial_current",
    "hodge_decompose",
    "hodge_diagnostics",
    "hodge",
    "phase_current_reversal",
    "reverse_phase_current",
    "phase_shuffled_equal_energy",
    "source_target_swap",
    "wrong_metric_adjoint",
    "reject_wrong_metric_adjoint",
    "active_subspace_impulse",
    "known_nullspace",
    "frozen_scale",
    "frozen_scale_diagnostics",
    "link_off",
    "cross_scale_diagnostics",
    "transition_w6_integrated",
    "transition_w6",
]
