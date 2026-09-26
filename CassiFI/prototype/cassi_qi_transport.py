"""W3 transport contract bound to the current W2 periodic FFT2 geometry.

This module owns only immutable W3 transport metadata and the small wrapper used
by the field transition.  Spatial arrays and all Fourier work remain owned by
:mod:`cassi_qi_geometry`; this layer never copies that implementation.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import torch
from torch import Tensor

from cassi_qi_geometry import (
    PeriodicSheetGeometry,
    W2GeometryProfile,
    load_w2_geometry_profile,
    validate_w2_geometry_profile,
)
from cassi_qi_profile import (
    PROFILE_DEFAULTS,
    PROFILE_MISMATCH,
    canonical_hash,
    canonical_json_bytes,
    canonical_json_loads,
    finite_float,
)


# Wire/schema identities retained for downstream receipt code.  None of these
# identities carries a run directory or an artifact snapshot.
W3_SCHEMA_REGISTRY_SCHEMA = "cassi.qi-flow-schema-registry.w3"
W3_CONTRACT_ROOT_SCHEMA = "cassi.qi-flow-contract-root.w3"
W3_PROFILE_SCHEMA = "cassi.qi-flow-transport-profile.w3"
W3_TRANSPORT_SEMANTIC_SCHEMA = "cassi.qi-flow-steering-transport.w3"
W3_PARENT_LINK_SCHEMA = "cassi.qi-flow-parent-link.w3"
W3_SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-source-identity.w3"
W3_G3_CANDIDATE_SCHEMA = "cassi.qi-flow-g3-transport-candidate.v1"
W3_GATE_STATUS_SCHEMA = "cassi.qi-flow-gate-status.v1"
W3_RUN_INDEX_SCHEMA = "cassi.qi-flow-run-index.v1"
W3_ARTIFACT_DOMAIN = "cassi.qi-flow-w3-artifact.v1"
W3_CONTRACT_ROOT_ID = "qi-flow-steering-transport-w3-development-v1"
W3_STAGE_SCHEDULE_SCHEMA = "cassi.qi-flow-g3-stage-schedule.v1"
W3_RAW_STATE_SCHEMA = "cassi.qi-flow-g3-raw-state.v1"
W3_DIRECT_IDENTITY_RECEIPT_SCHEMA = "cassi.qi-flow-g3-identity-receipt.v1"
W3_DIAGNOSTICS_SCHEMA = "cassi.qi-flow-g3-transport-diagnostics.v1"
W3_SIMPLE_DIAGNOSTICS_SCHEMA = "cassi.qi-flow-g3-simple-diagnostics.v1"
W3_SOURCE_REQUEST_SCHEMA = "cassi.qi-flow-g3-source-request.v1"
W3_REPLAY_SCHEMA = "cassi.qi-flow-g3-replay.v1"
W3_REFINEMENT_SCHEMA = "cassi.qi-flow-g3-refinement.v1"
W3_LONG_HORIZON_SCHEMA = "cassi.qi-flow-g3-long-horizon.v1"
W3_FAILURE_RECEIPT_SCHEMA = "cassi.qi-flow-g3-failure-receipt.v1"
W3_WORKSPACE_BOUNDS_SCHEMA = "cassi.qi-flow-g3-workspace-bounds.v1"
W3_STABILITY_BOUNDS_SCHEMA = "cassi.qi-flow-g3-stability-bounds.v1"
W3_RAW_STATE_DOMAIN = "cassi.qi-flow-w3-raw-state.v1"
W3_PARENT_IDENTITY_DOMAIN = "cassi.qi-flow-w3-parent-identity.v1"


def _f64(value: float) -> str:
    value = float(value)
    if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0.0):
        raise PROFILE_MISMATCH("W3 transport forbids non-finite or negative-zero parameters")
    return "f64:" + struct.pack(">d", value).hex()


def _rational_seconds(value: Any, *, name: str) -> float:
    if not isinstance(value, Mapping) or set(value) != {"numerator", "denominator"}:
        raise PROFILE_MISMATCH(f"{name} must be an exact rational object")
    numerator = value["numerator"]
    denominator = value["denominator"]
    if (
        isinstance(numerator, bool)
        or isinstance(denominator, bool)
        or not isinstance(numerator, int)
        or not isinstance(denominator, int)
        or numerator < 0
        or denominator <= 0
        or math.gcd(numerator, denominator) != 1
    ):
        raise PROFILE_MISMATCH(f"{name} is not reduced positive rational time")
    return float(numerator) / float(denominator)


# Importing the validated W2 profile once gives scalar constants to callers,
# while every constructed profile still revalidates and derives its own parent.
_CURRENT_W2 = load_w2_geometry_profile()
_CURRENT_W2_CONTRACT = _CURRENT_W2.payload["geometry_contract"]
_CURRENT_W2_STORAGE = _CURRENT_W2_CONTRACT["storage"]
_FIELD_DEFAULTS = PROFILE_DEFAULTS["field"]
_DYNAMIC_DEFAULTS = PROFILE_DEFAULTS["dynamics"]
_CLOCK_DEFAULTS = _DYNAMIC_DEFAULTS["clock"]

W3_SCALE_COUNT = int(_CURRENT_W2.scale_count)
W3_COMPONENT_COUNT = int(_FIELD_DEFAULTS["component_count"])
W3_MODE_COUNT = int(_FIELD_DEFAULTS["mode_count"])
W3_DTYPE = str(_FIELD_DEFAULTS["dtype"])
W3_DEVICE = str(_CURRENT_W2_STORAGE.get("backend", "cpu"))
W3_LAYOUT_ID = "[S,9M,B]"
W3_ZERO = _f64(0.0)
W3_H_MIN_S = _f64(_rational_seconds(_CLOCK_DEFAULTS["h_min"], name="dynamics.clock.h_min"))
W3_H_MAX_S = _f64(_rational_seconds(_CLOCK_DEFAULTS["h_max"], name="dynamics.clock.h_max"))
# W3_H_S is the release step retained by the field transition.
W3_H_S = W3_H_MIN_S
W3_HALF_H_S = _f64(0.5 * finite_float(W3_H_S, name="W3 h"))
W3_PHI = str(_DYNAMIC_DEFAULTS["coordinate_transform"]["phi"])
W3_RHO_FLOOR = str(_DYNAMIC_DEFAULTS["rho_floor"])
W3_AMPLITUDE_CAP = str(_DYNAMIC_DEFAULTS["candidate_amplitude_cap"])
W3_CANDIDATE_TOLERANCE = str(_DYNAMIC_DEFAULTS["candidate_numerical_tolerance"])
W3_C_D_M_PER_S = tuple(str(value) for value in _DYNAMIC_DEFAULTS["c_D_m_per_s"])
W3_OMEGA_RAD_PER_S = tuple(str(value) for value in _DYNAMIC_DEFAULTS["omega_D_rad_per_s"])
W3_GAMMA_PER_S = tuple(str(value) for value in _DYNAMIC_DEFAULTS["gamma_D_per_s"])
W3_KAPPA = tuple(str(value) for value in _DYNAMIC_DEFAULTS["kappa_D"])
W3_MAX_SOURCE_BYTES = 0
W3_WORKSPACE_BYTE_CAP = max(
    (
        int(value)
        for key, value in _CURRENT_W2_CONTRACT.get("workspace", {}).items()
        if key.endswith("_bytes") and isinstance(value, int) and not isinstance(value, bool)
    ),
    default=0,
)
W3_REQUIRED_SOURCE_PATHS = (
    "cassi-qi-flow-development.json",
    "cassi_qi_field.py",
    "cassi_qi_geometry.py",
    "cassi_qi_profile.py",
    "cassi_qi_transport.py",
    "run_cassi_qi_flow.py",
    "verify_cassi_qi_flow.py",
)
W3_MUTATION_CONTROLS = frozenset(
    {
        "candidate_out_of_place",
        "fail_before_commit",
        "finite_only",
        "amplitude_cap_enforced",
        "no_clipping",
        "no_tanh",
        "no_threshold",
        "no_adaptive_dt",
        "no_fallback",
        "predecessor_unchanged",
        "source_nonempty_rejected",
        "source_oversized_rejected",
        "source_nonfinite_rejected",
        "raw_state_reseal_rejected",
        "diagnostic_reseal_rejected",
        "stage_order_reseal_rejected",
        "operator_semantic_reseal_rejected",
        "parent_identity_tamper_rejected",
    }
)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _canonical_object(value: Any, *, name: str) -> dict[str, Any]:
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        try:
            decoded = canonical_json_loads(raw)
        except Exception as exc:
            raise PROFILE_MISMATCH(f"{name} must be canonical JSON") from exc
        if not isinstance(decoded, Mapping) or canonical_json_bytes(decoded) != raw:
            raise PROFILE_MISMATCH(f"{name} is not exact canonical object framing")
        return _plain(decoded)
    if not isinstance(value, Mapping):
        raise PROFILE_MISMATCH(f"{name} must be a mapping or canonical JSON bytes")
    try:
        candidate = _plain(value)
        encoded = canonical_json_bytes(candidate)
        decoded = canonical_json_loads(encoded)
    except Exception as exc:
        raise PROFILE_MISMATCH(f"{name} is not canonical JSON material") from exc
    if not isinstance(decoded, Mapping) or canonical_json_bytes(decoded) != encoded:
        raise PROFILE_MISMATCH(f"{name} has invalid canonical object framing")
    return _plain(decoded)


def _canonical_equal(left: Any, right: Any, *, name: str) -> None:
    try:
        if canonical_json_bytes(left) != canonical_json_bytes(right):
            raise PROFILE_MISMATCH(f"{name} does not match immutable transport material")
    except PROFILE_MISMATCH:
        raise
    except Exception as exc:
        raise PROFILE_MISMATCH(f"{name} is not canonical JSON material") from exc


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _w2_parent_record(geometry: W2GeometryProfile) -> dict[str, Any]:
    return {
        "schema": W3_PARENT_LINK_SCHEMA,
        "kind": "validated-current-w2-profile",
        "family": str(geometry.payload["geometry_contract"].get("family", "periodic-fft2.v1")),
        "profile_sha256": geometry.profile_sha256,
        "contract_root_sha256": geometry.contract_root_sha256,
        "geometry_contract_sha256": geometry.geometry_contract_sha256,
        "operator_semantic_sha256": geometry.operator_semantic_sha256,
    }


# This is identity-only and is intentionally derived from the live validated
# W2 object; it contains no run id, path, index digest, or generated artifact.
W2_PARENT_RECORD = MappingProxyType(_w2_parent_record(_CURRENT_W2))


def _scale_geometry_rows(geometry: W2GeometryProfile) -> list[dict[str, Any]]:
    contract = geometry.payload.get("geometry_contract")
    if not isinstance(contract, Mapping):
        raise PROFILE_MISMATCH("current W2 profile omits geometry_contract")
    sheets = contract.get("per_scale_sheets")
    if not isinstance(sheets, (list, tuple)) or len(sheets) != geometry.scale_count:
        raise PROFILE_MISMATCH("current W2 profile does not bind every scale sheet")
    rows: list[dict[str, Any]] = []
    for scale, sheet in enumerate(sheets):
        if not isinstance(sheet, Mapping):
            raise PROFILE_MISMATCH(f"W2 scale {scale} sheet is not an object")
        rectangle = sheet.get("active_rectangle")
        if not isinstance(rectangle, Mapping) or not isinstance(
            rectangle.get("shape_yx"), (list, tuple)
        ):
            raise PROFILE_MISMATCH(f"W2 scale {scale} omits its active 2D shape")
        shape = rectangle["shape_yx"]
        if len(shape) != 2 or any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in shape):
            raise PROFILE_MISMATCH(f"W2 scale {scale} active shape is not a positive 2D rectangle")
        if sheet.get("scale") != scale:
            raise PROFILE_MISMATCH("W2 scale sheets are not ordered")
        rows.append(
            {
                "scale": scale,
                "shape_yx": list(shape),
                "active_site_count": int(sheet["active_site_count"]),
                "spacing_m": _plain(sheet["spacing_m"]),
                "extent_m": _plain(sheet["extent_m"]),
                "cell_area_m2": sheet["cell_area_m2"],
                "signed_frequency_y": list(sheet["signed_frequency_y"]),
                "signed_frequency_x": list(sheet["signed_frequency_x"]),
                "oversampling": _plain(sheet["oversampling"]),
                "laplacian_symbol": "-(kx^2+ky^2)",
                "k2_symbol": "kx^2+ky^2",
            }
        )
    return rows


def _geometry_semantics(geometry: W2GeometryProfile) -> dict[str, Any]:
    contract = geometry.payload["geometry_contract"]
    return {
        "family": contract.get("family", "periodic-fft2.v1"),
        "profile_sha256": geometry.profile_sha256,
        "contract_root_sha256": geometry.contract_root_sha256,
        "geometry_contract_sha256": geometry.geometry_contract_sha256,
        "operator_semantic_sha256": geometry.operator_semantic_sha256,
        "storage": _plain(contract["storage"]),
        "axes": _plain(contract["axes"]),
        "boundary_condition": contract["boundary_condition"],
        "per_scale": _scale_geometry_rows(geometry),
        "fft2": {
            "normalization": contract["fft2"]["normalization"],
            "transform_axes": contract["fft2"]["transform_axes"],
            "signed_frequency_convention": contract["fft2"]["signed_frequency_convention"],
            "angular_wavenumber": contract["fft2"]["angular_wavenumber"],
        },
        "metric": _plain(contract["metric"]),
        "oversampling": _plain(contract["oversampling"]),
        "refinement": _plain(contract["refinement"]),
    }


def _dynamics_semantics() -> dict[str, Any]:
    dynamics = _DYNAMIC_DEFAULTS
    return {
        "h_min_s": W3_H_MIN_S,
        "h_max_s": W3_H_MAX_S,
        "c_D_m_per_s": list(W3_C_D_M_PER_S),
        "omega_D_rad_per_s": list(W3_OMEGA_RAD_PER_S),
        "gamma_D_per_s": list(W3_GAMMA_PER_S),
        "kappa_D": list(W3_KAPPA),
        # Explicit short names are useful to schema consumers; the pinned
        # dataclass below retains the established attribute names as well.
        "c_D": list(W3_C_D_M_PER_S),
        "omega_D": list(W3_OMEGA_RAD_PER_S),
        "gamma_D": list(W3_GAMMA_PER_S),
        "kappa_D": list(W3_KAPPA),
        "phi": W3_PHI,
        "rho_floor": W3_RHO_FLOOR,
        "candidate_amplitude_cap": W3_AMPLITUDE_CAP,
        "candidate_numerical_tolerance": W3_CANDIDATE_TOLERANCE,
        "finite_only": True,
        "source_budget_bytes": W3_MAX_SOURCE_BYTES,
        "coordinate_transform": _plain(dynamics["coordinate_transform"]),
        "spectral_symbol": "-(kx^2+ky^2)",
        "linear_mode": "analytic-2x2-damped-oscillator",
        "branches": ["underdamped", "critical", "overdamped"],
        "branch_evaluation": "exactly-once-per-spectral-half-step",
    }


def _base_stage_rows() -> tuple[dict[str, Any], ...]:
    return (
        {
            "ordinal": 1,
            "name": "preflight",
            "duration_s": W3_ZERO,
            "reads": ["predecessor_raw", "source_request"],
            "writes": ["preflight_receipt"],
            "dependencies": [],
            "mode": "active",
        },
        {
            "ordinal": 2,
            "name": "first_local_force_velocity_half_kick",
            "duration_s": W3_HALF_H_S,
            "reads": ["D_0", "V_D_0"],
            "writes": ["V_D_1"],
            "dependencies": ["preflight"],
            "mode": "active",
        },
        {
            "ordinal": 3,
            "name": "first_analytic_damped_spectral_half_propagation",
            "duration_s": W3_HALF_H_S,
            "reads": ["D_0", "V_D_1"],
            "writes": ["D_2", "V_D_2"],
            "dependencies": ["first_local_force_velocity_half_kick"],
            "mode": "active",
        },
        {
            "ordinal": 4,
            "name": "centered_conversion_placeholder",
            "duration_s": W3_H_S,
            "reads": ["D_2", "V_D_2"],
            "writes": ["conversion_placeholder"],
            "dependencies": ["first_analytic_damped_spectral_half_propagation"],
            "mode": "inactive-w3",
        },
        {
            "ordinal": 5,
            "name": "second_analytic_damped_spectral_half_propagation",
            "duration_s": W3_HALF_H_S,
            "reads": ["D_2", "V_D_2"],
            "writes": ["D_3", "V_D_3"],
            "dependencies": ["centered_conversion_placeholder"],
            "mode": "active",
        },
        {
            "ordinal": 6,
            "name": "second_local_force_velocity_half_kick",
            "duration_s": W3_HALF_H_S,
            "reads": ["D_3", "V_D_3"],
            "writes": ["V_D_4"],
            "dependencies": ["second_analytic_damped_spectral_half_propagation"],
            "mode": "active",
        },
        {
            "ordinal": 7,
            "name": "precommit",
            "duration_s": W3_ZERO,
            "reads": ["D_3", "V_D_4"],
            "writes": ["candidate_raw", "diagnostics", "commit_decision"],
            "dependencies": ["second_local_force_velocity_half_kick"],
            "mode": "active",
        },
    )


W3_G3_STAGE_ROWS = tuple(_freeze(row) for row in _base_stage_rows())


def w3_stage_schedule(duration_s: float | str) -> dict[str, Any]:
    """Return the canonical seven-row split schedule for ``duration_s``.

    The release step is the current W1 clock lower bound.  Refinement scales
    only logical durations; stage order, dependencies, and read/write slices
    remain immutable.
    """

    try:
        duration = finite_float(duration_s, name="W3 duration_s")
        h_min = finite_float(W3_H_S, name="W3 release step")
        h_max = finite_float(W3_H_MAX_S, name="W3 maximum step")
    except Exception as exc:
        raise PROFILE_MISMATCH(f"invalid W3 duration: {exc}") from exc
    if duration < 0.0 or duration > h_max:
        raise PROFILE_MISMATCH("W3 duration is outside the current W1 clock interval")
    scale = 0.0 if h_min == 0.0 else duration / h_min
    stages: list[dict[str, Any]] = []
    for row in _base_stage_rows():
        base_duration = finite_float(row["duration_s"], name=f"stage {row['ordinal']} duration")
        stage = dict(row)
        stage["duration_s"] = _f64(base_duration * scale)
        stage["reads"] = list(row["reads"])
        stage["writes"] = list(row["writes"])
        stage["dependencies"] = list(row["dependencies"])
        stages.append(stage)
    return {
        "schema": W3_STAGE_SCHEDULE_SCHEMA,
        "h_s": _f64(duration),
        "substeps": len(stages),
        "stages": stages,
    }


W3_G3_STAGE_SCHEDULE = _freeze(w3_stage_schedule(W3_H_S))


def w3_transport_semantic_map(
    geometry_profile: W2GeometryProfile | None = None,
    *,
    geometry: W2GeometryProfile | None = None,
) -> dict[str, Any]:
    """Return transport semantics bound to the validated current W2 profile."""

    if geometry_profile is not None and geometry is not None and geometry_profile is not geometry:
        raise PROFILE_MISMATCH("geometry_profile and geometry identify different W2 profiles")
    selected = geometry_profile if geometry_profile is not None else geometry
    bound = authenticate_sealed_w2_parent(selected)
    parent = _w2_parent_record(bound)
    semantic = {
        "schema": W3_TRANSPORT_SEMANTIC_SCHEMA,
        "family": "periodic-fft2.v1",
        "parent_w2": parent,
        "geometry": _geometry_semantics(bound),
        "dynamics": _dynamics_semantics(),
        "state_layout": {
            "layout_id": W3_LAYOUT_ID,
            "scale_count": W3_SCALE_COUNT,
            "component_count": W3_COMPONENT_COUNT,
            "mode_count": W3_MODE_COUNT,
            "component_lanes": [
                "EY.re",
                "EY.im",
                "EI.re",
                "EI.im",
                "VY.re",
                "VY.im",
                "VI.re",
                "VI.im",
                "epsilon",
            ],
            "dtype": W3_DTYPE,
            "device": W3_DEVICE,
            "endianness": "little",
        },
        "d_vd_transform": {
            "phi": W3_PHI,
            "w_D": "1/(1+phi^2)",
            "D": "EY-phi*EI",
            "C": "(phi*EY+EI)/(1+phi^2)",
            "V_D": "VY-phi*VI",
            "V_C": "(phi*VY+VI)/(1+phi^2)",
            "inverse": "EY=w_D*D+phi*C;EI=C-phi*w_D*D;VY=w_D*V_D+phi*V_C;VI=V_C-phi*w_D*V_D",
            "epsilon": "byte-identical",
        },
        "operator": {
            "geometry_api": "PeriodicSheetGeometry",
            "spatial_operator_family": "periodic-fft2.v1",
            "transform": "unitary-fft2",
            "transform_axes": "(y,x)",
            "laplacian": "F^-1[-(kx^2+ky^2)]F",
            "laplacian_symbol": "-(kx^2+ky^2)",
            "frequency_policy": "complete-signed-frequency-per-scale",
            "damping": "analytic-2x2-damped-oscillator-exactly-once",
            "branches": ["underdamped", "critical", "overdamped"],
        },
        "dealias": {
            "helper": "metric-adjoint-projected-pseudospectral-cubic",
            "per_scale": [
                {
                    "scale": row["scale"],
                    "shape_yx": row["shape_yx"],
                    "oversampling": row["oversampling"],
                    "alpha": "sqrt(Nplus/N)",
                    "injection": "complete-signed-frequency",
                    "restriction": "metric-adjoint",
                    "projector": "I_s R_s",
                }
                for row in _scale_geometry_rows(bound)
            ],
            "roundtrip": "required",
        },
        "inactive_terms": {
            "centered_conversion": "inactive-w3-placeholder",
            "w4": "unavailable",
            "w5": "unavailable",
            "advection": "unavailable",
            "source": "source-free",
        },
        "workspace": {
            "byte_cap": W3_WORKSPACE_BYTE_CAP,
            "accounting": "prepared-w2-operators-plus-bounded-stage-temporaries.v1",
            "unbounded_allocation": "forbidden",
        },
        "execution_contract": {
            "candidate_out_of_place": True,
            "fail_before_commit": True,
            "clip": "forbidden",
            "tanh": "forbidden",
            "threshold": "forbidden",
            "adaptive_dt": "forbidden",
            "fallback": "forbidden",
            "stage_order": [row["name"] for row in _base_stage_rows()],
            "stage_schedule_sha256": canonical_hash(W3_G3_STAGE_SCHEDULE, W3_STAGE_SCHEDULE_SCHEMA),
        },
    }
    return semantic


def _registry() -> dict[str, Any]:
    entries = {
        W3_CONTRACT_ROOT_SCHEMA: (65_536, ()),
        W3_G3_CANDIDATE_SCHEMA: (1_048_576, ("profile_sha256", "contract_root_sha256", "semantic_sha256", "geometry_contract_sha256", "operator_semantic_sha256")),
        W3_GATE_STATUS_SCHEMA: (65_536, ("profile_sha256", "contract_root_sha256", "semantic_sha256")),
        W3_TRANSPORT_SEMANTIC_SCHEMA: (131_072, ("geometry_contract_sha256", "operator_semantic_sha256")),
        W3_PROFILE_SCHEMA: (262_144, ("geometry_profile_sha256", "geometry_contract_sha256", "operator_semantic_sha256", "semantic_sha256")),
        W3_PARENT_LINK_SCHEMA: (65_536, ()),
        W3_SOURCE_IDENTITY_SCHEMA: (65_536, ()),
        W3_SCHEMA_REGISTRY_SCHEMA: (65_536, ()),
        W3_RUN_INDEX_SCHEMA: (1_048_576, ()),
    }
    return {
        "schema": W3_SCHEMA_REGISTRY_SCHEMA,
        "entries": [
            {"schema": schema, "max_bytes": limit, "semantic_parents": list(parents)}
            for schema, (limit, parents) in sorted(entries.items())
        ],
    }


def _parameters(semantic: Mapping[str, Any]) -> "W3PinnedParameters":
    dynamics = semantic["dynamics"]
    return W3PinnedParameters(
        phi=finite_float(semantic["d_vd_transform"]["phi"], name="W3 phi"),
        h=finite_float(dynamics["h_min_s"], name="W3 h"),
        substeps=int(W3_G3_STAGE_SCHEDULE["substeps"]),
        amplitude_cap=finite_float(dynamics["candidate_amplitude_cap"], name="W3 cap"),
        finite_only=bool(dynamics["finite_only"]),
        rho_floor=finite_float(dynamics["rho_floor"], name="W3 rho floor"),
        c_D_m_per_s=tuple(finite_float(item, name="W3 c_D") for item in dynamics["c_D_m_per_s"]),
        omega_rad_per_s=tuple(finite_float(item, name="W3 omega_D") for item in dynamics["omega_D_rad_per_s"]),
        gamma_per_s=tuple(finite_float(item, name="W3 gamma_D") for item in dynamics["gamma_D_per_s"]),
        kappa=tuple(finite_float(item, name="W3 kappa_D") for item in dynamics["kappa_D"]),
        max_source_budget=float(dynamics["source_budget_bytes"]),
        candidate_numerical_tolerance=finite_float(dynamics["candidate_numerical_tolerance"], name="W3 tolerance"),
        h_min_s=finite_float(dynamics["h_min_s"], name="W3 h_min"),
        h_max_s=finite_float(dynamics["h_max_s"], name="W3 h_max"),
    )


@dataclass(frozen=True)
class W3PinnedParameters:
    phi: float
    h: float
    substeps: int
    amplitude_cap: float
    finite_only: bool
    rho_floor: float
    c_D_m_per_s: tuple[float, ...]
    omega_rad_per_s: tuple[float, ...]
    gamma_per_s: tuple[float, ...]
    kappa: tuple[float, ...]
    max_source_budget: float
    candidate_numerical_tolerance: float
    h_min_s: float
    h_max_s: float

    @property
    def c_D(self) -> tuple[float, ...]:
        return self.c_D_m_per_s

    @property
    def omega_D(self) -> tuple[float, ...]:
        return self.omega_rad_per_s

    @property
    def gamma_D(self) -> tuple[float, ...]:
        return self.gamma_per_s

    @property
    def kappa_D(self) -> tuple[float, ...]:
        return self.kappa


@dataclass(frozen=True)
class W3TransportProfile:
    payload: Mapping[str, Any]
    root_payload: Mapping[str, Any]
    semantic_payload: Mapping[str, Any]
    registry_payload: Mapping[str, Any]
    pinned_parameters: W3PinnedParameters
    parent_w2: Mapping[str, Any]
    base_geometry: W2GeometryProfile

    @property
    def profile_sha256(self) -> str:
        return str(self.payload["profile_sha256"])

    @property
    def contract_root_sha256(self) -> str:
        return str(self.payload["contract_root_sha256"])

    @property
    def transport_semantic_sha256(self) -> str:
        return str(self.payload["semantic_sha256"])

    @classmethod
    def load(
        cls,
        payload_or_bytes: "W3TransportProfile | Mapping[str, Any] | bytes",
        *,
        geometry_profile: W2GeometryProfile | None = None,
        base_profile: Any | None = None,
        geometry: W2GeometryProfile | None = None,
    ) -> "W3TransportProfile":
        return validate_w3_transport_profile(
            payload_or_bytes,
            geometry_profile=geometry_profile,
            base_profile=base_profile,
            geometry=geometry,
        )

    def validate(
        self,
        *,
        geometry_profile: W2GeometryProfile | None = None,
        base_profile: Any | None = None,
        geometry: W2GeometryProfile | None = None,
    ) -> "W3TransportProfile":
        return validate_w3_transport_profile(
            self,
            geometry_profile=geometry_profile,
            base_profile=base_profile,
            geometry=geometry,
        )


def authenticate_sealed_w2_parent(
    geometry_profile: W2GeometryProfile | None = None,
    *,
    base_profile: Any | None = None,
    geometry: W2GeometryProfile | None = None,
) -> W2GeometryProfile:
    if geometry_profile is not None and geometry is not None and geometry_profile is not geometry:
        raise PROFILE_MISMATCH("geometry_profile and geometry identify different W2 profiles")
    selected = geometry_profile if geometry_profile is not None else geometry
    try:
        return (
            load_w2_geometry_profile(base_profile=base_profile)
            if selected is None
            else validate_w2_geometry_profile(selected, base_profile=base_profile)
        )
    except PROFILE_MISMATCH:
        raise
    except Exception as exc:
        raise PROFILE_MISMATCH(f"current W2 profile validation failed: {type(exc).__name__}: {exc}") from exc


def build_w3_transport_profile(
    base_profile: Any | None = None,
    geometry_profile: W2GeometryProfile | None = None,
    *,
    geometry: W2GeometryProfile | None = None,
) -> W3TransportProfile:
    bound = authenticate_sealed_w2_parent(
        geometry_profile,
        base_profile=base_profile,
        geometry=geometry,
    )
    parent = _w2_parent_record(bound)
    semantic = w3_transport_semantic_map(bound)
    semantic_sha256 = canonical_hash(semantic, W3_TRANSPORT_SEMANTIC_SCHEMA)
    registry = _registry()
    registry_sha256 = canonical_hash(registry, W3_SCHEMA_REGISTRY_SCHEMA)
    root: dict[str, Any] = {
        "schema": W3_CONTRACT_ROOT_SCHEMA,
        "contract_root_id": W3_CONTRACT_ROOT_ID,
        "parent_w2": parent,
        "geometry": {
            "profile_sha256": bound.profile_sha256,
            "contract_root_sha256": bound.contract_root_sha256,
            "geometry_contract_sha256": bound.geometry_contract_sha256,
            "operator_semantic_sha256": bound.operator_semantic_sha256,
        },
        "schema_registry": {"schema": W3_SCHEMA_REGISTRY_SCHEMA, "sha256": registry_sha256},
        "transport_semantic": {"schema": W3_TRANSPORT_SEMANTIC_SCHEMA, "sha256": semantic_sha256},
    }
    root["self_sha256"] = canonical_hash(root, W3_CONTRACT_ROOT_SCHEMA)
    profile: dict[str, Any] = {
        "schema": W3_PROFILE_SCHEMA,
        "contract_root_id": W3_CONTRACT_ROOT_ID,
        "parent_w2": parent,
        "base_geometry_profile_sha256": bound.profile_sha256,
        "base_geometry_contract_root_sha256": bound.contract_root_sha256,
        "geometry_profile_sha256": bound.profile_sha256,
        "geometry_contract_sha256": bound.geometry_contract_sha256,
        "operator_semantic_sha256": bound.operator_semantic_sha256,
        "schema_registry": registry,
        "schema_registry_sha256": registry_sha256,
        "semantic": semantic,
        "semantic_sha256": semantic_sha256,
        "contract_root": root,
        "contract_root_sha256": root["self_sha256"],
    }
    profile["profile_sha256"] = canonical_hash(profile, W3_PROFILE_SCHEMA)
    pinned = _parameters(semantic)
    frozen_profile = _freeze(profile)
    frozen_root = _freeze(root)
    frozen_semantic = _freeze(semantic)
    frozen_registry = _freeze(registry)
    return W3TransportProfile(
        frozen_profile,
        frozen_root,
        frozen_semantic,
        frozen_registry,
        pinned,
        _freeze(parent),
        bound,
    )


def load_w3_transport_profile(
    base_profile: Any | None = None,
    geometry_profile: W2GeometryProfile | None = None,
    *,
    geometry: W2GeometryProfile | None = None,
) -> W3TransportProfile:
    return build_w3_transport_profile(
        base_profile=base_profile,
        geometry_profile=geometry_profile,
        geometry=geometry,
    )


def validate_w3_transport_profile(
    payload_or_bytes: W3TransportProfile | Mapping[str, Any] | bytes | bytearray | memoryview,
    *,
    geometry_profile: W2GeometryProfile | None = None,
    base_profile: Any | None = None,
    geometry: W2GeometryProfile | None = None,
) -> W3TransportProfile:
    bound = authenticate_sealed_w2_parent(
        geometry_profile,
        base_profile=base_profile,
        geometry=geometry,
    )
    expected = build_w3_transport_profile(base_profile=bound.base_profile, geometry_profile=bound)
    if isinstance(payload_or_bytes, W3TransportProfile):
        supplied = _canonical_object(payload_or_bytes.payload, name="W3 profile payload")
    else:
        supplied = _canonical_object(payload_or_bytes, name="W3 profile payload")
    _canonical_equal(supplied, expected.payload, name="W3 profile")
    for name, value in (
        ("profile_sha256", supplied.get("profile_sha256")),
        ("contract_root_sha256", supplied.get("contract_root_sha256")),
        ("geometry_profile_sha256", supplied.get("geometry_profile_sha256")),
        ("geometry_contract_sha256", supplied.get("geometry_contract_sha256")),
        ("operator_semantic_sha256", supplied.get("operator_semantic_sha256")),
        ("semantic_sha256", supplied.get("semantic_sha256")),
        ("schema_registry_sha256", supplied.get("schema_registry_sha256")),
    ):
        if not _is_sha256(value):
            raise PROFILE_MISMATCH(f"{name} must be a lowercase SHA-256 digest")
    root = _canonical_object(supplied.get("contract_root"), name="W3 contract root")
    _canonical_equal(root, expected.root_payload, name="W3 contract root")
    semantic = _canonical_object(supplied.get("semantic"), name="W3 semantic payload")
    _canonical_equal(semantic, expected.semantic_payload, name="W3 semantic payload")
    if isinstance(payload_or_bytes, W3TransportProfile):
        if (
            payload_or_bytes.base_geometry.profile_sha256 != bound.profile_sha256
            or payload_or_bytes.base_geometry.contract_root_sha256 != bound.contract_root_sha256
        ):
            raise PROFILE_MISMATCH("W3 profile object binds a different W2 geometry")
    return expected


class ProjectedPseudospectralOperators:
    """Per-scale W2 interpolation, restriction, and metric projector."""

    __slots__ = ("geometry", "scale", "shape", "oversampled_shape", "alpha")

    def __init__(self, geometry: PeriodicSheetGeometry, scale: int) -> None:
        if not isinstance(geometry, PeriodicSheetGeometry):
            raise PROFILE_MISMATCH("projected operators require a PeriodicSheetGeometry instance")
        try:
            scale_i = int(scale)
            if isinstance(scale, bool) or scale_i != scale:
                raise ValueError("scale must be an integer")
            shape = tuple(int(value) for value in geometry.sheet_shape(scale_i))
            sheet = geometry.profile.payload["geometry_contract"]["per_scale_sheets"][scale_i]
            factors = tuple(int(value) for value in sheet["oversampling"]["factors_yx"])
        except Exception as exc:
            raise PROFILE_MISMATCH(f"invalid W2 projected-operator scale: {exc}") from exc
        if len(shape) != 2 or len(factors) != 2 or any(value < 1 for value in factors):
            raise PROFILE_MISMATCH("W2 projected operators require a positive 2D scale and factors")
        self.geometry = geometry
        self.scale = scale_i
        self.shape = shape
        self.oversampled_shape = (shape[0] * factors[0], shape[1] * factors[1])
        self.alpha = math.sqrt(float(math.prod(self.oversampled_shape)) / float(math.prod(shape)))

    def I(self, value: Tensor) -> Tensor:
        return self.geometry.interpolate_oversampled(value, scale=self.scale)

    def R(self, value: Tensor) -> Tensor:
        return self.geometry.restrict_oversampled(value, scale=self.scale)

    def P(self, value: Tensor) -> Tensor:
        return self.geometry.oversampled_projector(value, scale=self.scale)

    def interpolate(self, value: Tensor) -> Tensor:
        return self.I(value)

    def restrict(self, value: Tensor) -> Tensor:
        return self.R(value)

    def projector(self, value: Tensor) -> Tensor:
        return self.P(value)

    def I_adjoint(self, value: Tensor) -> Tensor:
        return self.R(value)

    def R_adjoint(self, value: Tensor) -> Tensor:
        return self.I(value)

    def P_adjoint(self, value: Tensor) -> Tensor:
        return self.P(value)


def projected_pseudospectral_operators(
    geometry: PeriodicSheetGeometry,
    scale: int,
) -> ProjectedPseudospectralOperators:
    return ProjectedPseudospectralOperators(geometry, scale)


__all__ = [
    "ProjectedPseudospectralOperators",
    "W2_PARENT_RECORD",
    "W3PinnedParameters",
    "W3TransportProfile",
    "W3_AMPLITUDE_CAP",
    "W3_ARTIFACT_DOMAIN",
    "W3_CANDIDATE_TOLERANCE",
    "W3_C_D_M_PER_S",
    "W3_COMPONENT_COUNT",
    "W3_CONTRACT_ROOT_ID",
    "W3_CONTRACT_ROOT_SCHEMA",
    "W3_DEVICE",
    "W3_DIAGNOSTICS_SCHEMA",
    "W3_DIRECT_IDENTITY_RECEIPT_SCHEMA",
    "W3_DTYPE",
    "W3_FAILURE_RECEIPT_SCHEMA",
    "W3_G3_CANDIDATE_SCHEMA",
    "W3_G3_STAGE_ROWS",
    "W3_G3_STAGE_SCHEDULE",
    "W3_GAMMA_PER_S",
    "W3_GATE_STATUS_SCHEMA",
    "W3_H_MAX_S",
    "W3_H_MIN_S",
    "W3_H_S",
    "W3_HALF_H_S",
    "W3_KAPPA",
    "W3_LAYOUT_ID",
    "W3_LONG_HORIZON_SCHEMA",
    "W3_MAX_SOURCE_BYTES",
    "W3_MODE_COUNT",
    "W3_MUTATION_CONTROLS",
    "W3_OMEGA_RAD_PER_S",
    "W3_PARENT_IDENTITY_DOMAIN",
    "W3_PARENT_LINK_SCHEMA",
    "W3_PROFILE_SCHEMA",
    "W3_RAW_STATE_DOMAIN",
    "W3_RAW_STATE_SCHEMA",
    "W3_REFINEMENT_SCHEMA",
    "W3_REPLAY_SCHEMA",
    "W3_REQUIRED_SOURCE_PATHS",
    "W3_RHO_FLOOR",
    "W3_RUN_INDEX_SCHEMA",
    "W3_SCALE_COUNT",
    "W3_SCHEMA_REGISTRY_SCHEMA",
    "W3_SIMPLE_DIAGNOSTICS_SCHEMA",
    "W3_SOURCE_IDENTITY_SCHEMA",
    "W3_SOURCE_REQUEST_SCHEMA",
    "W3_STABILITY_BOUNDS_SCHEMA",
    "W3_STAGE_SCHEDULE_SCHEMA",
    "W3_TRANSPORT_SEMANTIC_SCHEMA",
    "W3_WORKSPACE_BOUNDS_SCHEMA",
    "W3_WORKSPACE_BYTE_CAP",
    "W3_ZERO",
    "authenticate_sealed_w2_parent",
    "build_w3_transport_profile",
    "load_w3_transport_profile",
    "projected_pseudospectral_operators",
    "validate_w3_transport_profile",
    "w3_stage_schedule",
    "w3_transport_semantic_map",
]
