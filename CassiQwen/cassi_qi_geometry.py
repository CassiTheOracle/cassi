"""Immutable W2/G2 ``periodic-fft2.v1`` geometry and spectral operators.

Each temporal scale owns one complete x-fastest/y-major periodic rectangle
inside its packed ``[S,9M,B]`` storage slice.  Active shapes, spacings, metrics,
signed frequencies, and inactive zero tails come from the current W1 profile;
no spatial operator treats the packed tail as part of a sheet.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import torch

from cassi_qi_profile import (
    PROFILE_DEFAULTS,
    PROFILE_MISMATCH,
    QiFlowProfile,
    canonical_hash,
    canonical_json_bytes,
    canonical_json_loads,
    finite_float,
    load_development_profile,
    validate_contract_root,
)


W2_FAMILY = "periodic-fft2.v1"
W2_CONTRACT_ROOT_SCHEMA = "cassi.qi-flow-contract-root.w2.periodic-fft2.v1"
W2_PROFILE_SCHEMA = "cassi.qi-flow-geometry-profile.w2.periodic-fft2.v1"
W2_GEOMETRY_CONTRACT_SCHEMA = "cassi.qi-flow-periodic-fft2.v1"
W2_OPERATOR_SEMANTIC_SCHEMA = "cassi.qi-flow-periodic-fft2-operators.v1"
W2_PARENT_LINK_SCHEMA = "cassi.qi-flow-parent-link.w2.periodic-fft2.v1"
W2_SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-source-identity.w2.periodic-fft2.v1"
W2_G2_CANDIDATE_SCHEMA = "cassi.qi-flow-g2-periodic-fft2-candidate.v1"
W2_GATE_STATUS_SCHEMA = "cassi.qi-flow-g2-periodic-fft2-status.v1"
W2_RUN_INDEX_SCHEMA = "cassi.qi-flow-w2-periodic-fft2-run-index.v1"
W2_SCHEMA_REGISTRY_SCHEMA = "cassi.qi-flow-schema-registry.w2.periodic-fft2.v1"
W2_RUN_DOMAIN = "cassi.qi-flow-w2-periodic-fft2-artifact.v1"

W2_CONTRACT_ROOT_HASH_DOMAIN = W2_CONTRACT_ROOT_SCHEMA
W2_PROFILE_HASH_DOMAIN = W2_PROFILE_SCHEMA
W2_GEOMETRY_CONTRACT_HASH_DOMAIN = W2_GEOMETRY_CONTRACT_SCHEMA
W2_OPERATOR_SEMANTIC_HASH_DOMAIN = W2_OPERATOR_SEMANTIC_SCHEMA
W2_SCHEMA_REGISTRY_HASH_DOMAIN = W2_SCHEMA_REGISTRY_SCHEMA

SCALE_COUNT = int(PROFILE_DEFAULTS["field"]["scale_count"])
COMPONENT_COUNT = int(PROFILE_DEFAULTS["field"]["component_count"])
MODE_COUNT = int(PROFILE_DEFAULTS["field"]["mode_count"])
STATE_WIDTH = COMPONENT_COUNT * MODE_COUNT
MAX_BATCH_LANES = int(PROFILE_DEFAULTS["field"]["batch_limit"])
AXIS_ORDER = ("y", "x")
VECTOR_ORDER = ("x", "y")
ACTIVE_SHAPES = tuple(
    tuple(int(value) for value in shape)
    for shape in PROFILE_DEFAULTS["spatial"]["active_shapes"]
)
ACTIVE_SITE_COUNTS = tuple(ny * nx for ny, nx in ACTIVE_SHAPES)
SHEET_SPACINGS_M = tuple(
    (
        finite_float(sheet["spacing_m"]["dy"], name=f"spatial.per_scale[{scale}].dy"),
        finite_float(sheet["spacing_m"]["dx"], name=f"spatial.per_scale[{scale}].dx"),
    )
    for scale, sheet in enumerate(PROFILE_DEFAULTS["spatial"]["per_scale"])
)
SHEET_EXTENTS_M = tuple(
    (
        finite_float(sheet["extent_m"]["L_y"], name=f"spatial.per_scale[{scale}].L_y"),
        finite_float(sheet["extent_m"]["L_x"], name=f"spatial.per_scale[{scale}].L_x"),
    )
    for scale, sheet in enumerate(PROFILE_DEFAULTS["spatial"]["per_scale"])
)
SHEET_CELL_AREAS_M2 = tuple(
    finite_float(sheet["metric_cell_area"], name=f"spatial.metric_cell_area[{scale}]")
    for scale, sheet in enumerate(PROFILE_DEFAULTS["spatial"]["per_scale"])
)
SIGNED_FREQUENCIES_Y = tuple(
    tuple(int(value) for value in sheet["signed_frequency_bins"]["y"])
    for sheet in PROFILE_DEFAULTS["spatial"]["per_scale"]
)
SIGNED_FREQUENCIES_X = tuple(
    tuple(int(value) for value in sheet["signed_frequency_bins"]["x"])
    for sheet in PROFILE_DEFAULTS["spatial"]["per_scale"]
)
OVERSAMPLING_FACTORS = tuple(
    tuple(int(value) for value in sheet["oversampling"]["factors"])
    for sheet in PROFILE_DEFAULTS["spatial"]["per_scale"]
)
MAX_REFINEMENT_FACTORS = (4, 4)
W2_WORKSPACE_BYTE_CAP = 524_288
W2_NUMERIC_TOLERANCE_VALUE = 1.0e-10
W2_NUMERIC_TOLERANCE = "f64:3ddb7cdfd9d7bdbb"


class VerificationError(ValueError):
    """A tensor or immutable material value violates the W2 release contract."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _f64_tag(value: float) -> str:
    if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0.0):
        raise ValueError("release scalars must be finite non-negative-zero f64 values")
    return "f64:" + struct.pack(">d", float(value)).hex()


def _finite_f64_tag(value: Any, *, name: str) -> float:
    if (
        not isinstance(value, str)
        or not value.startswith("f64:")
        or len(value) != 20
        or any(character not in "0123456789abcdef" for character in value[4:])
    ):
        raise PROFILE_MISMATCH(f"{name} must be a canonical finite f64 tag")
    try:
        result = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
    except (ValueError, struct.error) as exc:
        raise PROFILE_MISMATCH(f"{name} has an invalid f64 payload") from exc
    if not math.isfinite(result) or (result == 0.0 and math.copysign(1.0, result) < 0.0):
        raise PROFILE_MISMATCH(f"{name} is not finite canonical f64")
    return result


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _signed_indices(count: int) -> tuple[int, ...]:
    if count < 2:
        raise ValueError("periodic-fft2.v1 requires at least two sites per axis")
    positive_stop = (count - 1) // 2 + 1
    return tuple(range(positive_stop)) + tuple(range(positive_stop - count, 0))


_ORIGIN_TAGS = (_f64_tag(0.0), _f64_tag(0.0))
_SHEET_SPACING_TAGS = tuple(
    tuple(PROFILE_DEFAULTS["spatial"]["per_scale"][scale]["spacing_m"][axis] for axis in ("dy", "dx"))
    for scale in range(SCALE_COUNT)
)
_SHEET_EXTENT_TAGS = tuple(
    tuple(PROFILE_DEFAULTS["spatial"]["per_scale"][scale]["extent_m"][axis] for axis in ("L_y", "L_x"))
    for scale in range(SCALE_COUNT)
)
_SHEET_CELL_AREA_TAGS = tuple(PROFILE_DEFAULTS["spatial"]["metric_cell_area"])
_PHI_TAG = _f64_tag((1.0 + math.sqrt(5.0)) / 2.0)
_WD_TAG = _f64_tag(1.0 / (1.0 + ((1.0 + math.sqrt(5.0)) / 2.0) ** 2))
_WC_TAG = _f64_tag(1.0 + ((1.0 + math.sqrt(5.0)) / 2.0) ** 2)
COORDINATE_ORIGIN_M = (0.0, 0.0)
PHI = _finite_f64_tag(_PHI_TAG, name="phi")
W_D = _finite_f64_tag(_WD_TAG, name="w_D")
W_C = _finite_f64_tag(_WC_TAG, name="w_C")
BODY_FRAME_TRANSLATION_M = (0.0, 0.0)
BODY_FRAME_ROTATION_QUARTER_TURNS = 0
G2_TRANSLATION_PROBE_M = SHEET_SPACINGS_M[0]
G2_ROTATION_PROBE_QUARTER_TURNS = 2
_BODY_FRAME_TRANSLATION_TAGS = tuple(_f64_tag(value) for value in BODY_FRAME_TRANSLATION_M)
_G2_TRANSLATION_PROBE_TAGS = tuple(_f64_tag(value) for value in G2_TRANSLATION_PROBE_M)


def _workspace_raw() -> dict[str, Any]:
    complex_bytes = 16
    base = sum(ACTIVE_SITE_COUNTS) * MAX_BATCH_LANES
    over = sum(
        count * factors[0] * factors[1]
        for count, factors in zip(ACTIVE_SITE_COUNTS, OVERSAMPLING_FACTORS)
    ) * MAX_BATCH_LANES
    maximum = (
        sum(ACTIVE_SITE_COUNTS)
        * MAX_REFINEMENT_FACTORS[0]
        * MAX_REFINEMENT_FACTORS[1]
        * MAX_BATCH_LANES
    )
    return {
        "byte_cap": W2_WORKSPACE_BYTE_CAP,
        "dtype": "complex128",
        "batch_lanes": MAX_BATCH_LANES,
        "active_site_counts": list(ACTIVE_SITE_COUNTS),
        "base_scalar_peak_bytes": base * complex_bytes * 3,
        "base_vector_peak_bytes": base * complex_bytes * 6,
        "oversampled_scalar_peak_bytes": (base + 2 * over) * complex_bytes,
        "max_refinement_scalar_peak_bytes": (base + 2 * maximum) * complex_bytes,
        "max_refinement_vector_peak_bytes": (2 * base + 3 * maximum) * complex_bytes,
        "max_refinement_factors_yx": list(MAX_REFINEMENT_FACTORS),
    }


_WORKSPACE_RAW = _workspace_raw()
if max(value for key, value in _WORKSPACE_RAW.items() if key.endswith("_bytes")) > W2_WORKSPACE_BYTE_CAP:
    raise RuntimeError("W2 workspace accounting is inconsistent")


def _cross_scale_pairs_raw() -> list[dict[str, Any]]:
    return [
        {
            "source_scale": source,
            "target_scale": target,
            "P": f"identity-N{ACTIVE_SITE_COUNTS[source]}",
            "P_adjoint": f"W_source^-1 P^H W_target=identity-N{ACTIVE_SITE_COUNTS[source]}",
        }
        for source in range(SCALE_COUNT)
        for target in range(SCALE_COUNT)
    ]


def _sheet_raw(scale: int) -> dict[str, Any]:
    ny, nx = ACTIVE_SHAPES[scale]
    active_count = ACTIVE_SITE_COUNTS[scale]
    factors_y, factors_x = OVERSAMPLING_FACTORS[scale]
    return {
        "scale": scale,
        "temporal_rank": "full",
        "active_rectangle": {
            "origin_yx": [0, 0],
            "shape_yx": [ny, nx],
            "exclusive_stop_yx": [ny, nx],
        },
        "active_site_count": active_count,
        "active_flat_indices": list(range(active_count)),
        "flat_mode_formula": "m=y*Nx+x",
        "component_offsets": [component * MODE_COUNT for component in range(COMPONENT_COUNT)],
        "gather": {
            "source": "state[s,c*M:(c+1)*M,b]",
            "target": "active[y,x,b]",
            "order": "x-fastest/y-major",
        },
        "scatter": {
            "source": "active[y,x,b]",
            "target": "state[s,c*M:(c+1)*M,b]",
            "order": "x-fastest/y-major",
        },
        "inactive_tail_proof": {
            "physical_slots": MODE_COUNT,
            "active_slots": active_count,
            "tail_interval": [active_count, MODE_COUNT],
            "inactive_slots": MODE_COUNT - active_count,
            "property": "inactive-tail-is-exact-zero",
        },
        "origin_m": list(_ORIGIN_TAGS),
        "extent_m": list(_SHEET_EXTENT_TAGS[scale]),
        "spacing_m": list(_SHEET_SPACING_TAGS[scale]),
        "cell_area_m2": _SHEET_CELL_AREA_TAGS[scale],
        "signed_frequency_y": list(SIGNED_FREQUENCIES_Y[scale]),
        "signed_frequency_x": list(SIGNED_FREQUENCIES_X[scale]),
        "oversampling": {
            "factors_yx": [factors_y, factors_x],
            "shape_yx": [ny * factors_y, nx * factors_x],
            "fine_cell_area_m2": _f64_tag(
                SHEET_CELL_AREAS_M2[scale] / float(factors_y * factors_x)
            ),
        },
    }


def _geometry_contract_raw() -> dict[str, Any]:
    return {
        "schema": W2_GEOMETRY_CONTRACT_SCHEMA,
        "family": W2_FAMILY,
        "storage": {
            "shape": "[S,9M,B]",
            "scale_count": SCALE_COUNT,
            "component_count": COMPONENT_COUNT,
            "mode_count": MODE_COUNT,
            "component_stride": MODE_COUNT,
            "state_width": STATE_WIDTH,
            "batch_limit": MAX_BATCH_LANES,
            "active_site_order": "x-fastest/y-major",
            "inactive_tail": "exact-zero",
        },
        "axes": {
            "sheet_axis_order": list(AXIS_ORDER),
            "vector_component_order": list(VECTOR_ORDER),
            "body_frame_handedness": "right-handed-x-y",
        },
        "boundary_condition": "periodic",
        "coordinate": {
            "units": "m",
            "coordinate_formula": "(y,x)=(origin_y+y*dy,origin_x+x*dx)",
            "per_scale": True,
        },
        "per_scale_sheets": [_sheet_raw(scale) for scale in range(SCALE_COUNT)],
        "cross_scale": {
            "temporal_rank": "full",
            "operator": "identity-low-pass.v1",
            "pairs": _cross_scale_pairs_raw(),
        },
        "fft2": {
            "normalization": "ortho",
            "forward_sign": "exp(-2*pi*i*(ky*y/Ny+kx*x/Nx))",
            "inverse_sign": "exp(+2*pi*i*(ky*y/Ny+kx*x/Nx))",
            "transform_axes": "(y,x)",
            "flattening": "m=y*Nx+x",
            "signed_frequency_convention": "[0,...,floor((N-1)/2),...,negative]",
            "literal_signed_nyquist": "negative",
            "angular_wavenumber": "k=2*pi*n/L",
        },
        "metric": {
            "base": "W_s=dx_s*dy_s*I",
            "inner_product": "sum(conj(left)*right)*dx_s*dy_s",
            "gradient_divergence_adjoint": "grad^*=-div",
            "laplacian_adjoint": "laplacian^*=laplacian",
        },
        "coordinate_translation": {
            "phi": _PHI_TAG,
            "position": "D=EY-phi*EI; C=(phi*EY+EI)/(1+phi^2)",
            "position_inverse": "EY=wD*D+phi*C; EI=C-phi*wD*D",
            "velocity": "V_D=VY-phi*VI; V_C=(phi*VY+VI)/(1+phi^2)",
            "velocity_inverse": "VY=wD*V_D+phi*V_C; VI=V_C-phi*wD*V_D",
            "w_D": _WD_TAG,
            "w_C": _WC_TAG,
            "metric_identity": "|EY|^2+|EI|^2=wD*|D|^2+wC*|C|^2",
        },
        "spatial_transforms": {
            "release_body_frame": {
                "translation_m": list(_BODY_FRAME_TRANSLATION_TAGS),
                "rotation_quarter_turns": BODY_FRAME_ROTATION_QUARTER_TURNS,
                "rotation_matrix_xy": [[1, 0], [0, 1]],
            },
            "translation": {
                "action": "(T_delta f)(y,x)=f(y-delta_y,x-delta_x)",
                "fourier_phase": "exp(-i*(ky*delta_y+kx*delta_x))",
                "periodicity": "translation modulo (L_y,L_x)",
            },
            "rotation": {
                "supported_quarter_turns": [0, 2],
                "half_turn_action": "(R_pi f)(y,x)=f((-y) mod N_y,(-x) mod N_x)",
                "half_turn_vector_action": "(R_pi v)(y,x)=-v((-y) mod N_y,(-x) mod N_x)",
            },
            "g2_probes": {
                "translation_m": list(_G2_TRANSLATION_PROBE_TAGS),
                "rotation_quarter_turns": G2_ROTATION_PROBE_QUARTER_TURNS,
                "purpose": "nonidentity-oracle-only-not-release-body-pose",
            },
        },
        "epsilon2_ema": {
            "component": 8,
            "dtype": "float64",
            "constraint": "nonnegative",
            "remap": "positive-conservative-overlap.v1",
            "mass": "sum(epsilon2_ema_s)*dx_s*dy_s",
        },
        "oversampling": {
            "injection": "F_f^-1 sqrt(q) J F_s",
            "restriction": "F_s^-1 (1/sqrt(q)) J^H F_f",
            "projector": "I_s R_s=F_f^-1 J J^H F_f",
            "metric_relation": "R_s=W_s^-1 I_s^H W_f",
        },
        "refinement": {
            "kind": "complete-frequency-injection",
            "factor_domain": "integer factors 2..4 on each sheet axis",
            "injection_scale": "sqrt(ry*rx)",
            "weighted_inverse_scale": "1/sqrt(ry*rx)",
            "complete_frequency_map": "signed coarse n maps to fine FFT bin n mod N_f",
        },
        "workspace": dict(_WORKSPACE_RAW),
    }


W2_GEOMETRY_CONTRACT = _freeze(_geometry_contract_raw())
W2_GEOMETRY_CONTRACT_SHA256 = canonical_hash(_geometry_contract_raw(), W2_GEOMETRY_CONTRACT_HASH_DOMAIN)

_SCHEMA_REGISTRY_ENTRIES: Mapping[str, tuple[int, tuple[str, ...]]] = MappingProxyType({
    W2_CONTRACT_ROOT_SCHEMA: (65_536, ()),
    W2_G2_CANDIDATE_SCHEMA: (524_288, ("geometry_contract_sha256", "operator_semantic_sha256", "source_identity_sha256")),
    W2_GATE_STATUS_SCHEMA: (65_536, ("candidate_sha256",)),
    W2_GEOMETRY_CONTRACT_SCHEMA: (131_072, ()),
    W2_OPERATOR_SEMANTIC_SCHEMA: (131_072, ("geometry_contract_sha256",)),
    W2_PARENT_LINK_SCHEMA: (65_536, ()),
    W2_PROFILE_SCHEMA: (262_144, ("geometry_contract_sha256", "operator_semantic_sha256", "contract_root_sha256")),
    W2_RUN_INDEX_SCHEMA: (1_048_576, ()),
    W2_SOURCE_IDENTITY_SCHEMA: (131_072, ()),
})


def _schema_registry_raw() -> dict[str, Any]:
    return {"schema": W2_SCHEMA_REGISTRY_SCHEMA, "family": W2_FAMILY, "entries": [{"schema": schema, "max_bytes": limit, "semantic_parents": list(parents)} for schema, (limit, parents) in sorted(_SCHEMA_REGISTRY_ENTRIES.items())]}


W2_SCHEMA_REGISTRY = _freeze(_schema_registry_raw())
W2_SCHEMA_REGISTRY_SHA256 = canonical_hash(_schema_registry_raw(), W2_SCHEMA_REGISTRY_HASH_DOMAIN)
W2_CONTRACT_ROOT_ID = "qi-flow-geometry-w2-periodic-fft2-v1"


def _canonical_equal(left: Any, right: Any, *, name: str) -> None:
    try:
        same = canonical_json_bytes(left) == canonical_json_bytes(right)
    except Exception as exc:
        raise PROFILE_MISMATCH(f"{name} is not canonical: {type(exc).__name__}: {exc}") from exc
    if not same:
        raise PROFILE_MISMATCH(f"{name} does not match immutable W2 material")


def _parse_payload(value: Any, *, name: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        result = _plain(value)
    elif isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        try:
            result = canonical_json_loads(raw)
        except Exception as exc:
            raise PROFILE_MISMATCH(f"{name} is not canonical JSON") from exc
        if not isinstance(result, Mapping) or canonical_json_bytes(result) != raw:
            raise PROFILE_MISMATCH(f"{name} is not exact canonical object framing")
        result = _plain(result)
    else:
        raise PROFILE_MISMATCH(f"{name} must be mapping or canonical JSON bytes")
    if not isinstance(result, dict):
        raise PROFILE_MISMATCH(f"{name} must be an object")
    return result


def _development_profile_path() -> Path:
    return Path(__file__).with_name("cassi-qi-flow-development.json")


def _validate_w1_layout(base: QiFlowProfile) -> None:
    """Require W1 to preserve the sole state storage while W2 owns sheet laws.

    The full current W1 payload/root is compared in :func:`_validate_base_profile`
    and then bound into the W2 parent link.  This deliberately avoids duplicating
    a second, stale W1 geometry schema here: W2's immutable contract is the
    authoritative declaration of every physical sheet, transform, metric, and
    FFT2 convention.
    """

    layout = _plain(base.state_layout)
    expected = {
        "scale_count": SCALE_COUNT,
        "mode_count": MODE_COUNT,
        "component_count": COMPONENT_COUNT,
        "shape": [SCALE_COUNT, STATE_WIDTH, None],
        "dtype": "float64",
        "layout_id": "cassi.qi-flow-state-layout.v3",
        "batch_limit": MAX_BATCH_LANES,
        "backend": "cpu",
    }
    for key, wanted in expected.items():
        if layout.get(key) != wanted:
            raise PROFILE_MISMATCH(f"W1 state layout {key} does not satisfy W2 storage")
    spatial = _plain(base.payload.get("spatial"))
    if not isinstance(spatial, dict):
        raise PROFILE_MISMATCH("W1 spatial profile is absent")
    sheets = spatial.get("per_scale")
    if not isinstance(sheets, list) or len(sheets) != SCALE_COUNT:
        raise PROFILE_MISMATCH("W1 must bind all four temporal-full-rank scales")
    for scale, sheet in enumerate(sheets):
        if not isinstance(sheet, dict) or sheet.get("scale_index") != scale:
            raise PROFILE_MISMATCH("W1 scale sheet index is not complete and ordered")
    if not isinstance(_plain(base.payload.get("scale_geometry", {})).get("state_operator"), dict):
        raise PROFILE_MISMATCH("W1 cross-scale state operator is absent")
    if not isinstance(_plain(base.payload.get("dynamics", {})).get("coordinate_transform"), dict):
        raise PROFILE_MISMATCH("W1 coordinate transform is absent")


def _validate_base_profile(base_profile: QiFlowProfile | None) -> QiFlowProfile:
    try:
        expected = load_development_profile(_development_profile_path())
    except Exception as exc:
        raise PROFILE_MISMATCH(f"cannot load current W1 profile: {type(exc).__name__}: {exc}") from exc
    candidate = expected if base_profile is None else base_profile
    if not isinstance(candidate, QiFlowProfile):
        raise PROFILE_MISMATCH("W2 geometry requires QiFlowProfile W1 material")
    try:
        candidate_root = validate_contract_root(candidate.contract_root)
        expected_root = validate_contract_root(expected.contract_root)
        _canonical_equal(candidate.payload, expected.payload, name="W1 profile payload")
        _canonical_equal(candidate_root.payload, expected_root.payload, name="W1 contract root")
        _canonical_equal(candidate.state_layout, expected.state_layout, name="W1 state layout")
    except PROFILE_MISMATCH:
        raise
    except Exception as exc:
        raise PROFILE_MISMATCH(f"W1 validation failed: {type(exc).__name__}: {exc}") from exc
    if candidate.profile_sha256 != expected.profile_sha256 or candidate.contract_root_sha256 != expected.contract_root_sha256 or candidate_root.sha256 != expected.contract_root_sha256:
        raise PROFILE_MISMATCH("W1 identity properties disagree with current material")
    _validate_w1_layout(candidate)
    return candidate


def _w1_parent_raw(base: QiFlowProfile) -> dict[str, Any]:
    layout = _plain(base.state_layout)
    spatial = _plain(base.payload["spatial"])
    return {"schema": W2_PARENT_LINK_SCHEMA, "kind": "validated-current-w1-profile", "profile_sha256": base.profile_sha256, "contract_root_sha256": base.contract_root_sha256, "state_layout_sha256": canonical_hash(layout, W2_PARENT_LINK_SCHEMA + ".state-layout"), "spatial_contract_sha256": canonical_hash(spatial, W2_PARENT_LINK_SCHEMA + ".spatial"), "state_layout": layout, "spatial": spatial}


def _operator_semantic_raw(parent_w1: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": W2_OPERATOR_SEMANTIC_SCHEMA,
        "family": W2_FAMILY,
        "parent_w1": _plain(parent_w1),
        "geometry_contract": _geometry_contract_raw(),
        "geometry_contract_sha256": W2_GEOMETRY_CONTRACT_SHA256,
        "scalar_dtype": "float64-or-complex128",
        "device": "cpu",
        "layout": "dense-contiguous-strided",
        "fft2": "torch.fft.fft2/ifft2(norm='ortho',dim=(y,x))",
        "gradient": "F^-1 (i*kx,i*ky) F",
        "divergence": "F^-1 i*(kx*vx+ky*vy) F",
        "laplacian": "F^-1 (-(kx^2+ky^2)) F",
        "curl": "F^-1 i*(kx*vy-ky*vx) F",
        "adjoints": {
            "gradient": "gradient_adjoint=-divergence",
            "divergence": "divergence_adjoint=-gradient",
            "laplacian": "laplacian_adjoint=laplacian",
        },
        "cross_scale": "identity P and metric P_adjoint",
        "coordinate_translation": "exact D/C weighted coordinate",
        "spatial_transforms": "fixed body-frame translation/rotation plus nonidentity G2 probes",
        "epsilon2_ema": "positive mass-conservative identity remap",
        "oversampling": "complete-frequency weighted I_s/R_s",
        "refinement": "complete signed-frequency injection only",
    }


def _contract_root_raw(parent_w1: Mapping[str, Any], operator_sha256: str) -> dict[str, Any]:
    root = {"schema": W2_CONTRACT_ROOT_SCHEMA, "family": W2_FAMILY, "contract_root_id": W2_CONTRACT_ROOT_ID, "parent_w1": _plain(parent_w1), "schema_registry": {"schema": W2_SCHEMA_REGISTRY_SCHEMA, "sha256": W2_SCHEMA_REGISTRY_SHA256}, "geometry_contract": {"schema": W2_GEOMETRY_CONTRACT_SCHEMA, "sha256": W2_GEOMETRY_CONTRACT_SHA256}, "operator_semantic": {"schema": W2_OPERATOR_SEMANTIC_SCHEMA, "sha256": operator_sha256}}
    root["self_sha256"] = canonical_hash(root, W2_CONTRACT_ROOT_HASH_DOMAIN)
    return root


def _profile_payload_raw(parent_w1: Mapping[str, Any], operator: Mapping[str, Any], operator_sha256: str, root: Mapping[str, Any]) -> dict[str, Any]:
    payload = {"schema": W2_PROFILE_SCHEMA, "family": W2_FAMILY, "parent_w1": _plain(parent_w1), "base_profile_sha256": str(parent_w1["profile_sha256"]), "base_contract_root_sha256": str(parent_w1["contract_root_sha256"]), "schema_registry": _schema_registry_raw(), "schema_registry_sha256": W2_SCHEMA_REGISTRY_SHA256, "geometry_contract": _geometry_contract_raw(), "geometry_contract_sha256": W2_GEOMETRY_CONTRACT_SHA256, "operator_semantic": _plain(operator), "operator_semantic_sha256": operator_sha256, "contract_root": _plain(root), "contract_root_sha256": str(root["self_sha256"])}
    payload["profile_sha256"] = canonical_hash(payload, W2_PROFILE_HASH_DOMAIN)
    return payload


def _expected_material(base: QiFlowProfile) -> tuple[dict[str, Any], dict[str, Any]]:
    parent = _w1_parent_raw(base)
    operator = _operator_semantic_raw(parent)
    operator_hash = canonical_hash(operator, W2_OPERATOR_SEMANTIC_HASH_DOMAIN)
    root = _contract_root_raw(parent, operator_hash)
    return _profile_payload_raw(parent, operator, operator_hash, root), root


@dataclass(frozen=True)
class W2GeometryProfile:
    """A strictly validated immutable descendant of current W1 material."""

    payload: Mapping[str, Any]
    contract_root: Mapping[str, Any]
    profile_sha256: str
    contract_root_sha256: str
    geometry_contract_sha256: str
    operator_semantic_sha256: str
    base_profile: QiFlowProfile
    active_shapes: tuple[tuple[int, int], ...]
    active_site_counts: tuple[int, ...]
    scale_count: int

    @property
    def schema_registry(self) -> Mapping[str, Any]:
        return W2_SCHEMA_REGISTRY

    @property
    def parent_w1(self) -> Mapping[str, Any]:
        return self.payload["parent_w1"]


def load_w2_geometry_profile(*, base_profile: QiFlowProfile | None = None) -> W2GeometryProfile:
    base = _validate_base_profile(base_profile)
    payload, root = _expected_material(base)
    profile = W2GeometryProfile(
        _freeze(payload),
        _freeze(root),
        str(payload["profile_sha256"]),
        str(root["self_sha256"]),
        W2_GEOMETRY_CONTRACT_SHA256,
        str(payload["operator_semantic_sha256"]),
        base,
        ACTIVE_SHAPES,
        ACTIVE_SITE_COUNTS,
        SCALE_COUNT,
    )
    return validate_w2_geometry_profile(profile)


def validate_w2_geometry_profile(profile_or_payload: W2GeometryProfile | Mapping[str, Any] | bytes | bytearray | memoryview, *, contract_root: Mapping[str, Any] | bytes | bytearray | memoryview | None = None, base_profile: QiFlowProfile | None = None) -> W2GeometryProfile:
    if isinstance(profile_or_payload, W2GeometryProfile):
        original = profile_or_payload
        payload = _parse_payload(original.payload, name="W2 profile")
        root = _parse_payload(original.contract_root, name="W2 contract root")
        if contract_root is not None:
            _canonical_equal(_parse_payload(contract_root, name="supplied W2 contract root"), root, name="supplied W2 contract root")
        base = _validate_base_profile(original.base_profile if base_profile is None else base_profile)
    else:
        original = None
        payload = _parse_payload(profile_or_payload, name="W2 profile")
        root = _parse_payload(contract_root, name="W2 contract root") if contract_root is not None else _parse_payload(payload.get("contract_root"), name="embedded W2 contract root")
        base = _validate_base_profile(base_profile)
    expected_payload, expected_root = _expected_material(base)
    _canonical_equal(payload, expected_payload, name="W2 profile")
    _canonical_equal(root, expected_root, name="W2 contract root")
    for name, value in (("profile_sha256", payload.get("profile_sha256")), ("contract_root_sha256", payload.get("contract_root_sha256")), ("geometry_contract_sha256", payload.get("geometry_contract_sha256")), ("operator_semantic_sha256", payload.get("operator_semantic_sha256")), ("contract_root.self_sha256", root.get("self_sha256")), ("parent_w1.profile_sha256", payload.get("parent_w1", {}).get("profile_sha256")), ("parent_w1.contract_root_sha256", payload.get("parent_w1", {}).get("contract_root_sha256"))):
        if not _is_sha256(value):
            raise PROFILE_MISMATCH(f"{name} must be a lowercase SHA-256 digest")
    if original is not None and (
        original.profile_sha256 != payload["profile_sha256"]
        or original.contract_root_sha256 != root["self_sha256"]
        or original.geometry_contract_sha256 != payload["geometry_contract_sha256"]
        or original.operator_semantic_sha256 != payload["operator_semantic_sha256"]
        or original.active_shapes != ACTIVE_SHAPES
        or original.active_site_counts != ACTIVE_SITE_COUNTS
        or original.scale_count != SCALE_COUNT
    ):
        raise PROFILE_MISMATCH("W2GeometryProfile attributes disagree with immutable material")
    return W2GeometryProfile(
        _freeze(payload),
        _freeze(root),
        str(payload["profile_sha256"]),
        str(root["self_sha256"]),
        str(payload["geometry_contract_sha256"]),
        str(payload["operator_semantic_sha256"]),
        base,
        ACTIVE_SHAPES,
        ACTIVE_SITE_COUNTS,
        SCALE_COUNT,
    )


def _index(value: Any, *, name: str, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value >= upper:
        raise VerificationError(f"{name} must be an integer in [0,{upper})")
    return value


def flat_mode_index(y: int, x: int, *, scale: int) -> int:
    """Return one scale's x-fastest/y-major packed site index."""

    scale_i = _index(scale, name="scale", upper=SCALE_COUNT)
    ny, nx = ACTIVE_SHAPES[scale_i]
    return _index(y, name="y", upper=ny) * nx + _index(x, name="x", upper=nx)


def unflatten_mode_index(m: int, *, scale: int) -> tuple[int, int]:
    """Invert :func:`flat_mode_index` for one active scale sheet."""

    scale_i = _index(scale, name="scale", upper=SCALE_COUNT)
    return divmod(_index(m, name="m", upper=ACTIVE_SITE_COUNTS[scale_i]), ACTIVE_SHAPES[scale_i][1])


def _conversion_tensor(value: Any, *, name: str) -> torch.Tensor:
    if not torch.is_tensor(value) or value.device.type != "cpu" or value.dtype not in (torch.float64, torch.complex128) or value.layout is not torch.strided or not value.is_contiguous() or not bool(torch.isfinite(value).all().item()):
        raise VerificationError(f"{name} must be a finite contiguous CPU float64 or complex128 tensor")
    return value


def _conversion_pair(left: Any, right: Any, *, names: tuple[str, str]) -> tuple[torch.Tensor, torch.Tensor]:
    left_tensor, right_tensor = _conversion_tensor(left, name=names[0]), _conversion_tensor(right, name=names[1])
    if left_tensor.shape != right_tensor.shape or left_tensor.dtype != right_tensor.dtype:
        raise VerificationError(f"{names[0]} and {names[1]} must have identical shape and dtype")
    return left_tensor, right_tensor


def ey_ei_to_d_c(ey: torch.Tensor, ei: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Map position fields ``EY/EI`` to the exact ``D/C`` coordinate."""

    ey_tensor, ei_tensor = _conversion_pair(ey, ei, names=("EY", "EI"))
    return ey_tensor - PHI * ei_tensor, (PHI * ey_tensor + ei_tensor) * W_D


def d_c_to_ey_ei(d: torch.Tensor, c: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Invert :func:`ey_ei_to_d_c` without an orthonormal substitution."""

    d_tensor, c_tensor = _conversion_pair(d, c, names=("D", "C"))
    return W_D * d_tensor + PHI * c_tensor, c_tensor - PHI * W_D * d_tensor


def vy_vi_to_vd_vc(vy: torch.Tensor, vi: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Map velocity fields ``VY/VI`` to the exact ``V_D/V_C`` coordinate."""

    vy_tensor, vi_tensor = _conversion_pair(vy, vi, names=("VY", "VI"))
    return vy_tensor - PHI * vi_tensor, (PHI * vy_tensor + vi_tensor) * W_D


def vd_vc_to_vy_vi(vd: torch.Tensor, vc: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Invert :func:`vy_vi_to_vd_vc` exactly."""

    vd_tensor, vc_tensor = _conversion_pair(vd, vc, names=("V_D", "V_C"))
    return W_D * vd_tensor + PHI * vc_tensor, vc_tensor - PHI * W_D * vd_tensor


def d_c_weighted_energy(d: torch.Tensor, c: torch.Tensor) -> torch.Tensor:
    """Return ``wD*|D|^2+wC*|C|^2`` for the declared coordinate metric."""

    d_tensor, c_tensor = _conversion_pair(d, c, names=("D", "C"))
    return W_D * d_tensor.abs().square() + W_C * c_tensor.abs().square()


@dataclass(frozen=True)
class Epsilon2RemapReceipt:
    """A positivity and physical-mass receipt for one scalar cross-scale remap."""

    values: torch.Tensor
    source_scale: int
    target_scale: int
    source_mass: torch.Tensor
    target_mass: torch.Tensor
    source_minimum: torch.Tensor
    target_minimum: torch.Tensor


class PeriodicSheetGeometry:
    """Ragged per-scale FFT2 geometry over packed ``[S,9M,B]`` storage."""

    __slots__ = (
        "_profile",
        "_batch_limit",
        "_frequency_y",
        "_frequency_x",
        "_wavenumber_y",
        "_wavenumber_x",
        "_fft_matrices",
        "_ifft_matrices",
    )

    def __init__(self, profile: W2GeometryProfile | None = None, *, batch_limit: int = MAX_BATCH_LANES) -> None:
        self._profile = validate_w2_geometry_profile(profile or load_w2_geometry_profile())
        self._batch_limit = _index(batch_limit - 1, name="batch_limit-1", upper=MAX_BATCH_LANES) + 1
        self._frequency_y = tuple(torch.tensor(values, dtype=torch.int64) for values in SIGNED_FREQUENCIES_Y)
        self._frequency_x = tuple(torch.tensor(values, dtype=torch.int64) for values in SIGNED_FREQUENCIES_X)
        self._wavenumber_y = tuple(
            (2.0 * math.pi / extent[0]) * frequency.to(torch.float64)
            for extent, frequency in zip(SHEET_EXTENTS_M, self._frequency_y)
        )
        self._wavenumber_x = tuple(
            (2.0 * math.pi / extent[1]) * frequency.to(torch.float64)
            for extent, frequency in zip(SHEET_EXTENTS_M, self._frequency_x)
        )
        self._fft_matrices: list[torch.Tensor | None] = [None] * SCALE_COUNT
        self._ifft_matrices: list[torch.Tensor | None] = [None] * SCALE_COUNT

    @property
    def profile(self) -> W2GeometryProfile:
        return self._profile

    @property
    def batch_limit(self) -> int:
        return self._batch_limit

    def bind_v3_geometry(self, base_profile: QiFlowProfile) -> "PeriodicSheetGeometry":
        validated = load_w2_geometry_profile(base_profile=base_profile)
        if validated.profile_sha256 != self._profile.profile_sha256:
            raise VerificationError("W2 geometry cannot bind a different W1 profile")
        return self

    @staticmethod
    def _scale(scale: int) -> int:
        return _index(scale, name="scale", upper=SCALE_COUNT)

    def sheet_shape(self, scale: int) -> tuple[int, int]:
        return ACTIVE_SHAPES[self._scale(scale)]

    def active_site_count(self, scale: int) -> int:
        return ACTIVE_SITE_COUNTS[self._scale(scale)]

    def spacing_m(self, scale: int) -> tuple[float, float]:
        return SHEET_SPACINGS_M[self._scale(scale)]

    def extent_m(self, scale: int) -> tuple[float, float]:
        return SHEET_EXTENTS_M[self._scale(scale)]

    def cell_area_m2(self, scale: int) -> float:
        return SHEET_CELL_AREAS_M2[self._scale(scale)]

    def _tensor(self, value: Any, *, name: str, dtypes: tuple[torch.dtype, ...] = (torch.float64, torch.complex128)) -> torch.Tensor:
        if (
            not torch.is_tensor(value)
            or value.device.type != "cpu"
            or value.dtype not in dtypes
            or value.layout is not torch.strided
            or not value.is_contiguous()
            or not bool(torch.isfinite(value).all().item())
        ):
            names = "/".join(str(dtype).removeprefix("torch.") for dtype in dtypes)
            raise VerificationError(f"{name} must be a finite contiguous CPU {names} tensor")
        return value

    def _batch(self, value: torch.Tensor, *, name: str) -> int:
        batch = int(value.shape[-1])
        if batch < 1 or batch > self._batch_limit:
            raise VerificationError(f"{name} batch must be in [1,{self._batch_limit}]")
        return batch

    def _packed(self, value: Any, *, scale: int, name: str, require_zero_tail: bool = True, dtypes: tuple[torch.dtype, ...] = (torch.float64, torch.complex128)) -> torch.Tensor:
        scale_i = self._scale(scale)
        tensor = self._tensor(value, name=name, dtypes=dtypes)
        if tensor.ndim != 2 or tensor.shape[0] != MODE_COUNT:
            raise VerificationError(f"{name} must have shape [{MODE_COUNT},B]")
        self._batch(tensor, name=name)
        active = ACTIVE_SITE_COUNTS[scale_i]
        if require_zero_tail and active < MODE_COUNT and bool(torch.count_nonzero(tensor[active:]).item()):
            raise VerificationError(f"{name} inactive tail must be exact zero")
        return tensor

    def _grid(self, value: Any, *, scale: int, name: str, factors: tuple[int, int] = (1, 1)) -> torch.Tensor:
        scale_i = self._scale(scale)
        tensor = self._tensor(value, name=name)
        ny, nx = ACTIVE_SHAPES[scale_i]
        expected = (ny * factors[0], nx * factors[1])
        if tensor.ndim != 3 or tuple(tensor.shape[:2]) != expected:
            raise VerificationError(f"{name} must have shape [{expected[0]},{expected[1]},B]")
        self._batch(tensor, name=name)
        return tensor

    def _vector(self, value: Any, *, scale: int, name: str, factors: tuple[int, int] = (1, 1)) -> torch.Tensor:
        scale_i = self._scale(scale)
        tensor = self._tensor(value, name=name)
        ny, nx = ACTIVE_SHAPES[scale_i]
        expected = (2, ny * factors[0], nx * factors[1])
        if tensor.ndim != 4 or tuple(tensor.shape[:3]) != expected:
            raise VerificationError(f"{name} must have shape [2,{expected[1]},{expected[2]},B] in [x,y] order")
        self._batch(tensor, name=name)
        return tensor

    def _grid_or_vector(self, value: Any, *, scale: int, name: str, factors: tuple[int, int] = (1, 1)) -> torch.Tensor:
        tensor = self._tensor(value, name=name)
        if tensor.ndim == 3:
            return self._grid(tensor, scale=scale, name=name, factors=factors)
        return self._vector(tensor, scale=scale, name=name, factors=factors)

    def modes_to_grid(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        scale_i = self._scale(scale)
        packed = self._packed(values, scale=scale_i, name="packed modes")
        ny, nx = ACTIVE_SHAPES[scale_i]
        return packed[: ACTIVE_SITE_COUNTS[scale_i]].view(ny, nx, packed.shape[-1])

    def grid_to_modes(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        scale_i = self._scale(scale)
        grid = self._grid(values, scale=scale_i, name="active grid")
        flat = grid.view(ACTIVE_SITE_COUNTS[scale_i], grid.shape[-1])
        if ACTIVE_SITE_COUNTS[scale_i] == MODE_COUNT:
            return flat
        packed = torch.zeros((MODE_COUNT, grid.shape[-1]), dtype=grid.dtype)
        packed[: ACTIVE_SITE_COUNTS[scale_i]].copy_(flat)
        return packed

    def active_site_indices(self, scale: int) -> torch.Tensor:
        return torch.arange(self.active_site_count(scale), dtype=torch.int64)

    def component_offset(self, component: int) -> int:
        return _index(component, name="component", upper=COMPONENT_COUNT) * MODE_COUNT

    def gather_active(self, state: torch.Tensor, *, scale: int, component: int) -> torch.Tensor:
        scale_i = self._scale(scale)
        component_i = _index(component, name="component", upper=COMPONENT_COUNT)
        tensor = self._tensor(state, name="state")
        if tensor.ndim != 3 or tuple(tensor.shape[:2]) != (SCALE_COUNT, STATE_WIDTH):
            raise VerificationError(f"state must have shape [{SCALE_COUNT},{STATE_WIDTH},B]")
        self._batch(tensor, name="state")
        start = component_i * MODE_COUNT
        return self.modes_to_grid(tensor[scale_i, start : start + MODE_COUNT].contiguous(), scale=scale_i)

    def scatter_active(self, active: torch.Tensor, *, scale: int, component: int, state: torch.Tensor | None = None) -> torch.Tensor:
        scale_i = self._scale(scale)
        component_i = _index(component, name="component", upper=COMPONENT_COUNT)
        grid = self._grid(active, scale=scale_i, name="active grid")
        if state is None:
            output = torch.zeros((SCALE_COUNT, STATE_WIDTH, grid.shape[-1]), dtype=grid.dtype)
        else:
            source = self._tensor(state, name="state")
            if source.ndim != 3 or tuple(source.shape[:2]) != (SCALE_COUNT, STATE_WIDTH) or source.shape[-1] != grid.shape[-1]:
                raise VerificationError(f"state must have shape [{SCALE_COUNT},{STATE_WIDTH},{grid.shape[-1]}]")
            output = source.clone()
        start = component_i * MODE_COUNT
        output[scale_i, start : start + MODE_COUNT].zero_()
        output[scale_i, start : start + ACTIVE_SITE_COUNTS[scale_i]].copy_(
            grid.view(ACTIVE_SITE_COUNTS[scale_i], grid.shape[-1])
        )
        return output

    def zero_tail_proof(self, state: torch.Tensor) -> dict[str, Any]:
        tensor = self._tensor(state, name="state")
        if tensor.ndim != 3 or tuple(tensor.shape[:2]) != (SCALE_COUNT, STATE_WIDTH):
            raise VerificationError(f"state must have shape [{SCALE_COUNT},{STATE_WIDTH},B]")
        rows: list[dict[str, Any]] = []
        all_zero = True
        for scale, active in enumerate(ACTIVE_SITE_COUNTS):
            inactive = 0
            for component in range(COMPONENT_COUNT):
                start = component * MODE_COUNT + active
                stop = (component + 1) * MODE_COUNT
                if start < stop:
                    inactive += int(torch.count_nonzero(tensor[scale, start:stop]).item())
            rows.append({"scale": scale, "active_slots": active, "inactive_slots": MODE_COUNT - active, "inactive_nonzero": inactive})
            all_zero = all_zero and inactive == 0
        return {"inactive_tail_is_exact_zero": all_zero, "per_scale": rows}

    def coordinate_axes(self, scale: int) -> tuple[torch.Tensor, torch.Tensor]:
        scale_i = self._scale(scale)
        ny, nx = ACTIVE_SHAPES[scale_i]
        dy, dx = SHEET_SPACINGS_M[scale_i]
        return torch.arange(ny, dtype=torch.float64) * dy, torch.arange(nx, dtype=torch.float64) * dx

    def coordinate_mesh(self, scale: int) -> tuple[torch.Tensor, torch.Tensor]:
        y, x = self.coordinate_axes(scale)
        return torch.meshgrid(y, x, indexing="ij")

    def frequency_axes(self, scale: int) -> tuple[torch.Tensor, torch.Tensor]:
        scale_i = self._scale(scale)
        return self._frequency_y[scale_i].clone(), self._frequency_x[scale_i].clone()

    def angular_wavenumber_axes(self, scale: int) -> tuple[torch.Tensor, torch.Tensor]:
        scale_i = self._scale(scale)
        return self._wavenumber_y[scale_i].clone(), self._wavenumber_x[scale_i].clone()

    def _fft(self, values: torch.Tensor) -> torch.Tensor:
        return torch.fft.fft2(values, dim=(-3, -2), norm="ortho")

    def _ifft(self, values: torch.Tensor) -> torch.Tensor:
        return torch.fft.ifft2(values, dim=(-3, -2), norm="ortho")

    def fft2(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        return self._fft(self._grid_or_vector(values, scale=scale, name="FFT2 input"))

    def ifft2(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        return self._ifft(self._grid_or_vector(values, scale=scale, name="IFFT2 input"))

    def _fft_matrix_for_scale(self, scale: int) -> tuple[torch.Tensor, torch.Tensor]:
        scale_i = self._scale(scale)
        if self._fft_matrices[scale_i] is None:
            ny, nx = ACTIVE_SHAPES[scale_i]
            y = torch.arange(ny, dtype=torch.float64)
            x = torch.arange(nx, dtype=torch.float64)
            fy = self._frequency_y[scale_i].to(torch.float64)
            fx = self._frequency_x[scale_i].to(torch.float64)
            matrix_y = torch.exp((-2.0j * math.pi / ny) * fy[:, None] * y[None, :]) / math.sqrt(ny)
            matrix_x = torch.exp((-2.0j * math.pi / nx) * fx[:, None] * x[None, :]) / math.sqrt(nx)
            matrix = torch.kron(matrix_y, matrix_x).to(torch.complex128).contiguous()
            self._fft_matrices[scale_i] = matrix
            self._ifft_matrices[scale_i] = matrix.conj().T.contiguous()
        return self._fft_matrices[scale_i], self._ifft_matrices[scale_i]  # type: ignore[return-value]

    def fft2_matrix(self, scale: int) -> torch.Tensor:
        return self._fft_matrix_for_scale(scale)[0].clone()

    def ifft2_matrix(self, scale: int) -> torch.Tensor:
        return self._fft_matrix_for_scale(scale)[1].clone()

    def _symbols(self, scale: int) -> tuple[torch.Tensor, torch.Tensor]:
        scale_i = self._scale(scale)
        return (
            self._wavenumber_y[scale_i][:, None].to(torch.complex128),
            self._wavenumber_x[scale_i][None, :].to(torch.complex128),
        )

    def _apply_symbol(self, values: torch.Tensor, symbol: torch.Tensor, *, scale: int, name: str) -> torch.Tensor:
        grid = self._grid(values, scale=scale, name=name)
        spectrum = self._fft(grid)
        return self._ifft((spectrum * symbol[..., None]).contiguous())

    def derivative_y(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        ky, _ = self._symbols(scale)
        return self._apply_symbol(values, 1.0j * ky, scale=scale, name="derivative_y input")

    def derivative_x(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        _, kx = self._symbols(scale)
        return self._apply_symbol(values, 1.0j * kx, scale=scale, name="derivative_x input")

    def gradient(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        grid = self._grid(values, scale=scale, name="gradient input")
        return torch.stack((self.derivative_x(grid, scale=scale), self.derivative_y(grid, scale=scale)), dim=0).contiguous()

    def divergence(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        vector = self._vector(values, scale=scale, name="divergence input")
        return (self.derivative_x(vector[0].contiguous(), scale=scale) + self.derivative_y(vector[1].contiguous(), scale=scale)).contiguous()

    def curl(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        vector = self._vector(values, scale=scale, name="curl input")
        return (self.derivative_x(vector[1].contiguous(), scale=scale) - self.derivative_y(vector[0].contiguous(), scale=scale)).contiguous()

    def laplacian(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        ky, kx = self._symbols(scale)
        return self._apply_symbol(values, -(ky.square() + kx.square()), scale=scale, name="laplacian input")

    def negative_laplacian(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        return -self.laplacian(values, scale=scale)

    def metric_weights(self, scale: int, *, refinement: tuple[int, int] = (1, 1)) -> torch.Tensor:
        scale_i = self._scale(scale)
        factors = self._refinement(refinement, allow_identity=True)
        ny, nx = ACTIVE_SHAPES[scale_i]
        return torch.full(
            (ny * factors[0], nx * factors[1]),
            SHEET_CELL_AREAS_M2[scale_i] / float(factors[0] * factors[1]),
            dtype=torch.float64,
        )

    def metric_matrix(self, scale: int) -> torch.Tensor:
        scale_i = self._scale(scale)
        return torch.eye(ACTIVE_SITE_COUNTS[scale_i], dtype=torch.complex128) * SHEET_CELL_AREAS_M2[scale_i]

    def weighted_inner(self, left: torch.Tensor, right: torch.Tensor, *, scale: int, refinement: tuple[int, int] = (1, 1)) -> torch.Tensor:
        factors = self._refinement(refinement, allow_identity=True)
        a = self._grid_or_vector(left, scale=scale, name="inner-product left", factors=factors)
        b = self._grid_or_vector(right, scale=scale, name="inner-product right", factors=factors)
        if a.shape != b.shape:
            raise VerificationError("weighted inner-product operands must have identical shapes")
        area = SHEET_CELL_AREAS_M2[self._scale(scale)] / float(factors[0] * factors[1])
        return torch.sum(a.conj() * b, dim=tuple(range(a.ndim - 1))) * area

    def spectral_translate(self, values: torch.Tensor, *, scale: int, delta_m: tuple[float, float]) -> torch.Tensor:
        grid = self._grid_or_vector(values, scale=scale, name="translation input")
        if len(delta_m) != 2 or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in delta_m):
            raise VerificationError("delta_m must contain two finite physical displacements in [y,x] order")
        ky, kx = self._symbols(scale)
        phase = torch.exp((-1.0j) * (ky * float(delta_m[0]) + kx * float(delta_m[1])))
        return self._ifft((self._fft(grid) * phase[..., None]).contiguous())

    def rotate_quarter_turns(self, values: torch.Tensor, *, scale: int, quarter_turns: int) -> torch.Tensor:
        tensor = self._grid_or_vector(values, scale=scale, name="rotation input")
        if isinstance(quarter_turns, bool) or not isinstance(quarter_turns, int) or quarter_turns % 4 not in (0, 2):
            raise VerificationError("periodic-fft2.v1 supports only 0 or 2 quarter turns")
        if quarter_turns % 4 == 0:
            return tensor.clone()
        rotated = torch.roll(torch.flip(tensor, dims=(-3, -2)), shifts=(1, 1), dims=(-3, -2))
        return (-rotated if tensor.ndim == 4 else rotated).contiguous()

    def body_frame_translate(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        return self.spectral_translate(values, scale=scale, delta_m=BODY_FRAME_TRANSLATION_M)

    def body_frame_rotate(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        return self.rotate_quarter_turns(values, scale=scale, quarter_turns=BODY_FRAME_ROTATION_QUARTER_TURNS)

    def cross_scale_matrix(self, source_scale: int, target_scale: int) -> torch.Tensor:
        source = self._scale(source_scale)
        target = self._scale(target_scale)
        if SHEET_EXTENTS_M[source] != SHEET_EXTENTS_M[target]:
            raise VerificationError("cross-scale FFT transfer requires matching periodic extents")
        if ACTIVE_SHAPES[source] == ACTIVE_SHAPES[target]:
            return torch.eye(ACTIVE_SITE_COUNTS[source], dtype=torch.complex128)
        source_fft, _ = self._fft_matrix_for_scale(source)
        _, target_ifft = self._fft_matrix_for_scale(target)
        target_pairs = {
            (ny, nx): row
            for row, (ny, nx) in enumerate(
                (pair for y in SIGNED_FREQUENCIES_Y[target] for pair in ((y, x) for x in SIGNED_FREQUENCIES_X[target]))
            )
        }
        injection = torch.zeros((ACTIVE_SITE_COUNTS[target], ACTIVE_SITE_COUNTS[source]), dtype=torch.complex128)
        for source_row, pair in enumerate(
            (pair for y in SIGNED_FREQUENCIES_Y[source] for pair in ((y, x) for x in SIGNED_FREQUENCIES_X[source]))
        ):
            target_row = target_pairs.get(pair)
            if target_row is not None:
                injection[target_row, source_row] = math.sqrt(ACTIVE_SITE_COUNTS[target] / ACTIVE_SITE_COUNTS[source])
        return (target_ifft @ injection @ source_fft).contiguous()

    def cross_scale_adjoint_matrix(self, source_scale: int, target_scale: int) -> torch.Tensor:
        source = self._scale(source_scale)
        target = self._scale(target_scale)
        return (
            self.cross_scale_matrix(source, target).conj().T
            * (SHEET_CELL_AREAS_M2[target] / SHEET_CELL_AREAS_M2[source])
        ).contiguous()

    def cross_scale_transfer(self, values: torch.Tensor, *, source_scale: int, target_scale: int) -> torch.Tensor:
        source = self._scale(source_scale)
        target = self._scale(target_scale)
        packed = self._packed(values, scale=source, name="cross-scale source")
        active = packed[: ACTIVE_SITE_COUNTS[source]]
        if ACTIVE_SHAPES[source] == ACTIVE_SHAPES[target]:
            mapped = active
        else:
            mapped_complex = self.cross_scale_matrix(source, target) @ active.to(torch.complex128)
            if packed.dtype == torch.float64:
                if float(mapped_complex.imag.abs().max().item()) > W2_NUMERIC_TOLERANCE_VALUE:
                    raise VerificationError("real cross-scale transfer produced a complex residual")
                mapped = mapped_complex.real.contiguous()
            else:
                mapped = mapped_complex
        ny, nx = ACTIVE_SHAPES[target]
        return self.grid_to_modes(mapped.view(ny, nx, packed.shape[-1]).contiguous(), scale=target)

    def cross_scale_adjoint(self, values: torch.Tensor, *, source_scale: int, target_scale: int) -> torch.Tensor:
        source = self._scale(source_scale)
        target = self._scale(target_scale)
        packed = self._packed(values, scale=target, name="cross-scale adjoint source")
        active = packed[: ACTIVE_SITE_COUNTS[target]]
        if ACTIVE_SHAPES[source] == ACTIVE_SHAPES[target] and SHEET_CELL_AREAS_M2[source] == SHEET_CELL_AREAS_M2[target]:
            mapped = active
        else:
            mapped_complex = self.cross_scale_adjoint_matrix(source, target) @ active.to(torch.complex128)
            if packed.dtype == torch.float64:
                if float(mapped_complex.imag.abs().max().item()) > W2_NUMERIC_TOLERANCE_VALUE:
                    raise VerificationError("real cross-scale adjoint produced a complex residual")
                mapped = mapped_complex.real.contiguous()
            else:
                mapped = mapped_complex
        ny, nx = ACTIVE_SHAPES[source]
        return self.grid_to_modes(mapped.view(ny, nx, packed.shape[-1]).contiguous(), scale=source)

    @staticmethod
    def _axis_overlap_matrix(source_count: int, target_count: int, extent: float) -> torch.Tensor:
        source_width = extent / source_count
        target_width = extent / target_count
        matrix = torch.zeros((target_count, source_count), dtype=torch.float64)
        for target in range(target_count):
            target_start = target * target_width
            target_stop = target_start + target_width
            for source in range(source_count):
                source_start = source * source_width
                source_stop = source_start + source_width
                overlap = max(0.0, min(target_stop, source_stop) - max(target_start, source_start))
                if overlap:
                    matrix[target, source] = overlap / target_width
        return matrix

    def positive_remap_matrix(self, source_scale: int, target_scale: int) -> torch.Tensor:
        source = self._scale(source_scale)
        target = self._scale(target_scale)
        if SHEET_EXTENTS_M[source] != SHEET_EXTENTS_M[target]:
            raise VerificationError("positive conservative remap requires matching periodic extents")
        source_y, source_x = ACTIVE_SHAPES[source]
        target_y, target_x = ACTIVE_SHAPES[target]
        weight_y = self._axis_overlap_matrix(source_y, target_y, SHEET_EXTENTS_M[source][0])
        weight_x = self._axis_overlap_matrix(source_x, target_x, SHEET_EXTENTS_M[source][1])
        return torch.kron(weight_y, weight_x).contiguous()

    def remap_epsilon2_ema(self, epsilon2_ema: torch.Tensor, *, source_scale: int, target_scale: int) -> Epsilon2RemapReceipt:
        source = self._scale(source_scale)
        target = self._scale(target_scale)
        values = self._packed(epsilon2_ema, scale=source, name="epsilon2_ema", dtypes=(torch.float64,))
        active_source = values[: ACTIVE_SITE_COUNTS[source]]
        if bool(torch.any(active_source < 0.0).item()):
            raise VerificationError("epsilon2_ema must be nonnegative")
        mapped_active = self.positive_remap_matrix(source, target) @ active_source
        target_y, target_x = ACTIVE_SHAPES[target]
        mapped = self.grid_to_modes(
            mapped_active.view(target_y, target_x, values.shape[-1]).contiguous(),
            scale=target,
        )
        source_mass = torch.sum(active_source, dim=0) * SHEET_CELL_AREAS_M2[source]
        target_mass = torch.sum(mapped_active, dim=0) * SHEET_CELL_AREAS_M2[target]
        return Epsilon2RemapReceipt(
            mapped,
            source,
            target,
            source_mass,
            target_mass,
            torch.min(active_source),
            torch.min(mapped_active),
        )

    @staticmethod
    def _refinement(factors: tuple[int, int], *, allow_identity: bool = False) -> tuple[int, int]:
        if (
            not isinstance(factors, tuple)
            or len(factors) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in factors)
            or any(value < (1 if allow_identity else 2) or value > MAX_REFINEMENT_FACTORS[index] for index, value in enumerate(factors))
        ):
            low = 1 if allow_identity else 2
            raise VerificationError(f"refinement factors must be integers in [{low},4]")
        return factors

    def _inject_spectrum(self, spectrum: torch.Tensor, *, scale: int, factors: tuple[int, int]) -> torch.Tensor:
        scale_i = self._scale(scale)
        ny, nx = ACTIVE_SHAPES[scale_i]
        fine_y, fine_x = ny * factors[0], nx * factors[1]
        fine = torch.zeros((*spectrum.shape[:-3], fine_y, fine_x, spectrum.shape[-1]), dtype=torch.complex128)
        for y, signed_y in enumerate(SIGNED_FREQUENCIES_Y[scale_i]):
            for x, signed_x in enumerate(SIGNED_FREQUENCIES_X[scale_i]):
                fine[..., signed_y % fine_y, signed_x % fine_x, :] = spectrum[..., y, x, :]
        return fine

    def _restrict_spectrum(self, fine: torch.Tensor, *, scale: int, factors: tuple[int, int]) -> torch.Tensor:
        scale_i = self._scale(scale)
        ny, nx = ACTIVE_SHAPES[scale_i]
        fine_y, fine_x = ny * factors[0], nx * factors[1]
        coarse = torch.empty((*fine.shape[:-3], ny, nx, fine.shape[-1]), dtype=torch.complex128)
        for y, signed_y in enumerate(SIGNED_FREQUENCIES_Y[scale_i]):
            for x, signed_x in enumerate(SIGNED_FREQUENCIES_X[scale_i]):
                coarse[..., y, x, :] = fine[..., signed_y % fine_y, signed_x % fine_x, :]
        return coarse

    def refinement_inject(self, values: torch.Tensor, *, scale: int, factors: tuple[int, int]) -> torch.Tensor:
        factors = self._refinement(factors)
        grid = self._grid_or_vector(values, scale=scale, name="refinement source")
        spectrum = self._inject_spectrum(self._fft(grid), scale=scale, factors=factors)
        return self._ifft((spectrum * math.sqrt(float(factors[0] * factors[1]))).contiguous())

    def refinement_restrict(self, values: torch.Tensor, *, scale: int, factors: tuple[int, int]) -> torch.Tensor:
        factors = self._refinement(factors)
        fine = self._grid_or_vector(values, scale=scale, name="refinement target", factors=factors)
        restricted = self._restrict_spectrum(self._fft(fine), scale=scale, factors=factors)
        return self._ifft((restricted / math.sqrt(float(factors[0] * factors[1]))).contiguous())

    def refinement_projector(self, values: torch.Tensor, *, scale: int, factors: tuple[int, int]) -> torch.Tensor:
        factors = self._refinement(factors)
        return self.refinement_inject(
            self.refinement_restrict(values, scale=scale, factors=factors),
            scale=scale,
            factors=factors,
        )

    def interpolate_oversampled(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        scale_i = self._scale(scale)
        return self.refinement_inject(values, scale=scale_i, factors=OVERSAMPLING_FACTORS[scale_i])

    def restrict_oversampled(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        scale_i = self._scale(scale)
        return self.refinement_restrict(values, scale=scale_i, factors=OVERSAMPLING_FACTORS[scale_i])

    def oversampled_projector(self, values: torch.Tensor, *, scale: int) -> torch.Tensor:
        scale_i = self._scale(scale)
        return self.refinement_projector(values, scale=scale_i, factors=OVERSAMPLING_FACTORS[scale_i])

    def workspace_report(self) -> dict[str, Any]:
        return dict(_WORKSPACE_RAW)

    def operator_metadata(self) -> dict[str, Any]:
        return {
            "family": W2_FAMILY,
            "geometry_profile_sha256": self._profile.profile_sha256,
            "geometry_contract_root_sha256": self._profile.contract_root_sha256,
            "geometry_contract_sha256": self._profile.geometry_contract_sha256,
            "operator_semantic_sha256": self._profile.operator_semantic_sha256,
            "parent_w1": _plain(self._profile.parent_w1),
            "active_shapes_yx": [list(shape) for shape in ACTIVE_SHAPES],
            "active_site_counts": list(ACTIVE_SITE_COUNTS),
            "mode_count": MODE_COUNT,
            "scale_count": SCALE_COUNT,
            "state_shape": "[S,9M,B]",
            "axis_order": list(AXIS_ORDER),
            "vector_order": list(VECTOR_ORDER),
            "per_scale_sheets": _plain(W2_GEOMETRY_CONTRACT["per_scale_sheets"]),
            "coordinate": _plain(W2_GEOMETRY_CONTRACT["coordinate"]),
            "fft2": _plain(W2_GEOMETRY_CONTRACT["fft2"]),
            "metric": _plain(W2_GEOMETRY_CONTRACT["metric"]),
            "cross_scale": _plain(W2_GEOMETRY_CONTRACT["cross_scale"]),
            "coordinate_translation": _plain(W2_GEOMETRY_CONTRACT["coordinate_translation"]),
            "spatial_transforms": _plain(W2_GEOMETRY_CONTRACT["spatial_transforms"]),
            "epsilon2_ema": _plain(W2_GEOMETRY_CONTRACT["epsilon2_ema"]),
            "oversampling": _plain(W2_GEOMETRY_CONTRACT["oversampling"]),
            "workspace": self.workspace_report(),
        }


__all__ = [
    "W2_FAMILY", "W2_CONTRACT_ROOT_SCHEMA", "W2_PROFILE_SCHEMA", "W2_GEOMETRY_CONTRACT_SCHEMA",
    "W2_OPERATOR_SEMANTIC_SCHEMA", "W2_PARENT_LINK_SCHEMA", "W2_SOURCE_IDENTITY_SCHEMA",
    "W2_G2_CANDIDATE_SCHEMA", "W2_GATE_STATUS_SCHEMA", "W2_RUN_INDEX_SCHEMA",
    "W2_SCHEMA_REGISTRY_SCHEMA", "W2_RUN_DOMAIN", "W2_CONTRACT_ROOT_HASH_DOMAIN",
    "W2_PROFILE_HASH_DOMAIN", "W2_GEOMETRY_CONTRACT_HASH_DOMAIN",
    "W2_OPERATOR_SEMANTIC_HASH_DOMAIN", "W2_SCHEMA_REGISTRY_HASH_DOMAIN", "SCALE_COUNT",
    "COMPONENT_COUNT", "MODE_COUNT", "STATE_WIDTH", "MAX_BATCH_LANES", "AXIS_ORDER",
    "VECTOR_ORDER", "ACTIVE_SHAPES", "ACTIVE_SITE_COUNTS", "SHEET_SPACINGS_M",
    "SHEET_EXTENTS_M", "SHEET_CELL_AREAS_M2", "SIGNED_FREQUENCIES_Y",
    "SIGNED_FREQUENCIES_X", "OVERSAMPLING_FACTORS", "MAX_REFINEMENT_FACTORS",
    "W2_WORKSPACE_BYTE_CAP", "W2_NUMERIC_TOLERANCE", "W2_NUMERIC_TOLERANCE_VALUE",
    "COORDINATE_ORIGIN_M", "PHI", "W_D", "W_C", "BODY_FRAME_TRANSLATION_M",
    "BODY_FRAME_ROTATION_QUARTER_TURNS", "G2_TRANSLATION_PROBE_M",
    "G2_ROTATION_PROBE_QUARTER_TURNS", "W2_SCHEMA_REGISTRY",
    "W2_SCHEMA_REGISTRY_SHA256", "W2_GEOMETRY_CONTRACT", "W2_GEOMETRY_CONTRACT_SHA256",
    "W2_CONTRACT_ROOT_ID", "VerificationError", "W2GeometryProfile", "Epsilon2RemapReceipt",
    "PeriodicSheetGeometry", "load_w2_geometry_profile", "validate_w2_geometry_profile",
    "flat_mode_index", "unflatten_mode_index", "ey_ei_to_d_c", "d_c_to_ey_ei",
    "vy_vi_to_vd_vc", "vd_vc_to_vy_vi", "d_c_weighted_energy",
]
