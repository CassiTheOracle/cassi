"""Independent source-and-runtime verifier for sealed W2/G2 artifacts.

The verifier imports no W2 producer or materializer code.  It derives every
sheet from the snapshotted W1 profile, decodes the raw fixtures, and replays
FFT2, differential, metric, transform, cross-scale, and remap checks directly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import torch

from cassi_qi_profile import canonical_hash, canonical_json_bytes, canonical_json_loads


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
FIXTURE_SCHEMA = "cassi.qi-flow-g2-periodic-fft2-fixtures.v1"
W1_CONTRACT_ROOT_HASH_DOMAIN = "cassi.qi-flow-contract-root-bootstrap.v1"
TOLERANCE = 1.0e-10
PHI = (1.0 + math.sqrt(5.0)) / 2.0
W_D = 1.0 / (1.0 + PHI * PHI)
W_C = 1.0 + PHI * PHI
_REPOSITORY = Path(__file__).resolve().parent
_SOURCE_PATHS = {
    "CassiFI/01-field-physics.md",
    "CassiFI/10-work-packages.md",
    "CassiFI/11-validation-gates.md",
    "cassi-qi-flow-development.json",
    "cassi_qi_field.py",
    "cassi_qi_geometry.py",
    "cassi_qi_profile.py",
    "run_cassi_qi_geometry.py",
    "test_cassi_qi_geometry.py",
    "test_cassi_qi_geometry_field.py",
    "verify_cassi_qi_geometry.py",
}
_CONTROL_IDS = {
    "schema_mutation_rejected",
    "profile_hash_mutation_rejected",
    "source_mutation_rejected",
    "extra_axis_variant_rejected",
    "transposed_axes_rejected",
    "padding_rejected",
    "centered_roll_variant_rejected",
    "wrong_signed_nyquist_rejected",
    "wrong_normalization_rejected",
    "one_cell_coordinate_permutation_rejected",
    "wrong_translation_sign_rejected",
    "vector_rotation_sign_rejected",
    "negative_epsilon_rejected",
    "inactive_tail_control",
}


class W2GeometryVerificationError(RuntimeError):
    """Raised when independently replayed W2/G2 evidence is incomplete."""


def _fail(message: str) -> None:
    raise W2GeometryVerificationError(message)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _f64(value: float) -> str:
    value = 0.0 if value == 0.0 else float(value)
    if not math.isfinite(value):
        _fail("non-finite numeric evidence")
    return "f64:" + struct.pack(">d", value).hex()


def _as_f64(value: Any, *, name: str) -> float:
    if not isinstance(value, str) or not value.startswith("f64:") or len(value) != 20:
        _fail(f"{name} is not a canonical f64 tag")
    try:
        result = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
    except (ValueError, struct.error):
        _fail(f"{name} has malformed f64 bits")
    if not math.isfinite(result) or (result == 0.0 and math.copysign(1.0, result) < 0.0):
        _fail(f"{name} is non-finite or negative zero")
    return result


def _read_object(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        _fail(f"missing object {relative}")
    raw = path.read_bytes()
    try:
        value = canonical_json_loads(raw)
    except Exception as exc:
        raise W2GeometryVerificationError(f"{relative} is not canonical JSON") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        _fail(f"{relative} is not exact canonical object framing")
    return value


def _exact_keys(value: Mapping[str, Any], keys: set[str], *, name: str) -> None:
    if set(value) != keys:
        _fail(f"{name} keys are not exact")


def _exact(value: Any, expected: Any, *, name: str) -> None:
    if value != expected:
        _fail(f"{name} does not match the immutable W2 contract")


def _self_hash(value: Mapping[str, Any], domain: str, *, field: str = "self_sha256") -> str:
    body = dict(value)
    body.pop(field, None)
    return canonical_hash(body, domain)


def _hash_field(value: Mapping[str, Any], domain: str, *, field: str, name: str) -> None:
    actual = value.get(field)
    body = dict(value)
    body.pop(field, None)
    if not _is_sha256(actual) or actual != canonical_hash(body, domain):
        _fail(f"{name} hash is invalid")


def _valid_relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        _fail("artifact path is not canonical POSIX relative syntax")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        _fail("artifact path escapes its root")
    return value


def _parse_w1_source(root: Path) -> dict[str, Any]:
    path = root / "run-spec/sources/cassi-qi-flow-development.json"
    raw = path.read_bytes() if path.is_file() else b""
    try:
        wrapper = canonical_json_loads(raw)
    except Exception as exc:
        raise W2GeometryVerificationError("snapshotted W1 profile config is malformed") from exc
    if not isinstance(wrapper, dict) or canonical_json_bytes(wrapper) != raw or not isinstance(wrapper.get("profile"), dict):
        _fail("snapshotted W1 profile config is not canonical")
    return wrapper["profile"]


def _verify_source_identity(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    identity = _read_object(root, "run-spec/source-identity.json")
    _exact_keys(identity, {"schema", "family", "sources", "self_sha256"}, name="source identity")
    _exact(identity["schema"], W2_SOURCE_IDENTITY_SCHEMA, name="source identity schema")
    _exact(identity["family"], W2_FAMILY, name="source identity family")
    if identity.get("self_sha256") != _self_hash(identity, W2_SOURCE_IDENTITY_SCHEMA):
        _fail("source identity self hash is invalid")
    sources = identity.get("sources")
    if not isinstance(sources, list) or not sources:
        _fail("source identity has no sources")
    paths = []
    for record in sources:
        if not isinstance(record, dict):
            _fail("source record is not an object")
        _exact_keys(record, {"path", "byte_count", "sha256"}, name="source record")
        relative = _valid_relative_path(record["path"])
        paths.append(relative)
        if not isinstance(record["byte_count"], int) or isinstance(record["byte_count"], bool) or record["byte_count"] < 0 or not _is_sha256(record["sha256"]):
            _fail(f"source identity is malformed for {relative}")
        snapshot = root / "run-spec/sources" / relative
        current = _REPOSITORY / relative
        if not snapshot.is_file() or not current.is_file():
            _fail(f"source is missing for {relative}")
        snapshot_raw = snapshot.read_bytes()
        current_raw = current.read_bytes()
        if len(snapshot_raw) != record["byte_count"] or _sha256(snapshot_raw) != record["sha256"]:
            _fail(f"source snapshot identity failed for {relative}")
        if current_raw != snapshot_raw:
            _fail(f"artifact is not source-exact for {relative}")
    expected_paths = sorted(_SOURCE_PATHS, key=lambda value: value.encode("utf-8"))
    if paths != expected_paths:
        _fail("source identity path inventory or UTF-8 order is wrong")
    return identity, sources, _parse_w1_source(root)


def _sheet_material(w1: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int, int, int, int]:
    field = w1.get("field")
    spatial = w1.get("spatial")
    if not isinstance(field, Mapping) or not isinstance(spatial, Mapping):
        _fail("W1 source lacks field/spatial material")
    scale_count = field.get("scale_count")
    component_count = field.get("component_count")
    mode_count = field.get("mode_count")
    batch_limit = field.get("batch_limit")
    if (scale_count, component_count, mode_count, batch_limit) != (4, 9, 32, 4):
        _fail("W1 packed layout is not the frozen [4,9*32,B<=4] contract")
    per_scale = spatial.get("per_scale")
    active_shapes = spatial.get("active_shapes")
    if not isinstance(per_scale, list) or len(per_scale) != scale_count or not isinstance(active_shapes, list) or len(active_shapes) != scale_count:
        _fail("W1 per-scale sheet inventory is incomplete")
    sheets = []
    for scale, source in enumerate(per_scale):
        if not isinstance(source, Mapping) or source.get("scale_index") != scale:
            _fail("W1 scale sheets are not ordered")
        shape = source.get("active_shape")
        if shape != active_shapes[scale] or not isinstance(shape, list) or len(shape) != 2:
            _fail("W1 active shape mismatch")
        ny, nx = shape
        active_count = ny * nx
        if source.get("active_site_count") != active_count or active_count > mode_count:
            _fail("W1 active site count is invalid")
        spacing = source.get("spacing_m")
        extent = source.get("extent_m")
        signed = source.get("signed_frequency_bins")
        oversampling = source.get("oversampling")
        if not all(isinstance(value, Mapping) for value in (spacing, extent, signed, oversampling)):
            _fail("W1 sheet metric material is malformed")
        dy = _as_f64(spacing.get("dy"), name=f"W1 scale {scale} dy")
        dx = _as_f64(spacing.get("dx"), name=f"W1 scale {scale} dx")
        ly = _as_f64(extent.get("L_y"), name=f"W1 scale {scale} Ly")
        lx = _as_f64(extent.get("L_x"), name=f"W1 scale {scale} Lx")
        area = _as_f64(source.get("metric_cell_area"), name=f"W1 scale {scale} cell area")
        if abs(ly - ny * dy) > 1.0e-15 or abs(lx - nx * dx) > 1.0e-15 or abs(area - dx * dy) > 1.0e-18:
            _fail("W1 sheet metric identities fail")
        frequencies_y = list(signed.get("y", []))
        frequencies_x = list(signed.get("x", []))
        if frequencies_y != _signed_indices(ny) or frequencies_x != _signed_indices(nx):
            _fail("W1 signed FFT bins are invalid")
        factors = list(oversampling.get("factors", []))
        if len(factors) != 2 or any(not isinstance(value, int) or isinstance(value, bool) or value < 2 or value > 4 for value in factors):
            _fail("W1 oversampling factors are invalid")
        sheets.append(
            {
                "scale": scale,
                "shape": (ny, nx),
                "active_count": active_count,
                "dy": dy,
                "dx": dx,
                "ly": ly,
                "lx": lx,
                "area": area,
                "spacing_tags": [spacing["dy"], spacing["dx"]],
                "extent_tags": [extent["L_y"], extent["L_x"]],
                "area_tag": source["metric_cell_area"],
                "frequency_y": frequencies_y,
                "frequency_x": frequencies_x,
                "oversampling": tuple(factors),
            }
        )
    return sheets, scale_count, component_count, mode_count, batch_limit


def _signed_indices(count: int) -> list[int]:
    positive_stop = (count - 1) // 2 + 1
    return list(range(positive_stop)) + list(range(positive_stop - count, 0))


def _verify_geometry_contract(geometry: Mapping[str, Any], w1: Mapping[str, Any]) -> list[dict[str, Any]]:
    sheets, scale_count, component_count, mode_count, batch_limit = _sheet_material(w1)
    _exact_keys(
        geometry,
        {
            "schema", "family", "storage", "axes", "boundary_condition", "coordinate",
            "per_scale_sheets", "cross_scale", "fft2", "metric", "coordinate_translation",
            "spatial_transforms", "epsilon2_ema", "oversampling", "refinement", "workspace",
        },
        name="geometry contract",
    )
    _exact(geometry["schema"], W2_GEOMETRY_CONTRACT_SCHEMA, name="geometry schema")
    _exact(geometry["family"], W2_FAMILY, name="geometry family")
    _exact(
        geometry["storage"],
        {
            "shape": "[S,9M,B]",
            "scale_count": scale_count,
            "component_count": component_count,
            "mode_count": mode_count,
            "component_stride": mode_count,
            "state_width": component_count * mode_count,
            "batch_limit": batch_limit,
            "active_site_order": "x-fastest/y-major",
            "inactive_tail": "exact-zero",
        },
        name="geometry storage",
    )
    _exact(
        geometry["axes"],
        {
            "sheet_axis_order": ["y", "x"],
            "vector_component_order": ["x", "y"],
            "body_frame_handedness": "right-handed-x-y",
        },
        name="geometry axes",
    )
    _exact(geometry["boundary_condition"], "periodic", name="boundary condition")
    _exact(
        geometry["coordinate"],
        {
            "units": "m",
            "coordinate_formula": "(y,x)=(origin_y+y*dy,origin_x+x*dx)",
            "per_scale": True,
        },
        name="coordinate convention",
    )
    actual_sheets = geometry.get("per_scale_sheets")
    if not isinstance(actual_sheets, list) or len(actual_sheets) != scale_count:
        _fail("geometry sheet inventory is incomplete")
    for sheet, actual in zip(sheets, actual_sheets):
        scale = sheet["scale"]
        ny, nx = sheet["shape"]
        active = sheet["active_count"]
        factors_y, factors_x = sheet["oversampling"]
        expected = {
            "scale": scale,
            "temporal_rank": "full",
            "active_rectangle": {"origin_yx": [0, 0], "shape_yx": [ny, nx], "exclusive_stop_yx": [ny, nx]},
            "active_site_count": active,
            "active_flat_indices": list(range(active)),
            "flat_mode_formula": "m=y*Nx+x",
            "component_offsets": [component * mode_count for component in range(component_count)],
            "gather": {"source": "state[s,c*M:(c+1)*M,b]", "target": "active[y,x,b]", "order": "x-fastest/y-major"},
            "scatter": {"source": "active[y,x,b]", "target": "state[s,c*M:(c+1)*M,b]", "order": "x-fastest/y-major"},
            "inactive_tail_proof": {
                "physical_slots": mode_count,
                "active_slots": active,
                "tail_interval": [active, mode_count],
                "inactive_slots": mode_count - active,
                "property": "inactive-tail-is-exact-zero",
            },
            "origin_m": [_f64(0.0), _f64(0.0)],
            "extent_m": sheet["extent_tags"],
            "spacing_m": sheet["spacing_tags"],
            "cell_area_m2": sheet["area_tag"],
            "signed_frequency_y": sheet["frequency_y"],
            "signed_frequency_x": sheet["frequency_x"],
            "oversampling": {
                "factors_yx": [factors_y, factors_x],
                "shape_yx": [ny * factors_y, nx * factors_x],
                "fine_cell_area_m2": _f64(sheet["area"] / (factors_y * factors_x)),
            },
        }
        _exact(actual, expected, name=f"geometry scale {scale} sheet")
    pairs = [
        {
            "source_scale": source,
            "target_scale": target,
            "P": f"identity-N{sheets[source]['active_count']}",
            "P_adjoint": f"W_source^-1 P^H W_target=identity-N{sheets[source]['active_count']}",
        }
        for source in range(scale_count)
        for target in range(scale_count)
    ]
    _exact(
        geometry["cross_scale"],
        {"temporal_rank": "full", "operator": "identity-low-pass.v1", "pairs": pairs},
        name="cross-scale contract",
    )
    fft2 = geometry["fft2"]
    if not isinstance(fft2, Mapping) or fft2.get("normalization") != "ortho" or fft2.get("transform_axes") != "(y,x)" or fft2.get("flattening") != "m=y*Nx+x" or fft2.get("literal_signed_nyquist") != "negative":
        _fail("FFT2 convention is incomplete")
    _exact(
        geometry["metric"],
        {
            "base": "W_s=dx_s*dy_s*I",
            "inner_product": "sum(conj(left)*right)*dx_s*dy_s",
            "gradient_divergence_adjoint": "grad^*=-div",
            "laplacian_adjoint": "laplacian^*=laplacian",
        },
        name="metric contract",
    )
    coordinate = geometry["coordinate_translation"]
    if not isinstance(coordinate, Mapping) or _as_f64(coordinate.get("phi"), name="coordinate phi") != PHI or _as_f64(coordinate.get("w_D"), name="coordinate wD") != W_D or _as_f64(coordinate.get("w_C"), name="coordinate wC") != W_C:
        _fail("D/C coordinate transform is not exact")
    transforms = geometry["spatial_transforms"]
    if not isinstance(transforms, Mapping):
        _fail("spatial transform contract is missing")
    release = transforms.get("release_body_frame")
    probes = transforms.get("g2_probes")
    if not isinstance(release, Mapping) or release.get("translation_m") != [_f64(0.0), _f64(0.0)] or release.get("rotation_quarter_turns") != 0 or release.get("rotation_matrix_xy") != [[1, 0], [0, 1]]:
        _fail("release body frame is not the frozen identity pose")
    if not isinstance(probes, Mapping) or probes.get("translation_m") != [sheets[0]["spacing_tags"][0], sheets[0]["spacing_tags"][1]] or probes.get("rotation_quarter_turns") != 2:
        _fail("nonidentity G2 transform probes are not exact")
    epsilon = geometry["epsilon2_ema"]
    if not isinstance(epsilon, Mapping) or epsilon.get("component") != 8 or epsilon.get("remap") != "positive-conservative-overlap.v1":
        _fail("epsilon2 EMA remap contract is invalid")
    workspace = geometry["workspace"]
    if not isinstance(workspace, Mapping) or workspace.get("byte_cap") != 524_288 or max(value for key, value in workspace.items() if key.endswith("_bytes")) > workspace["byte_cap"]:
        _fail("workspace accounting exceeds its cap")
    return sheets


def _verify_profile_chain(root: Path, w1_source: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    profile = _read_object(root, "run-spec/w2-profile.json")
    contract_root = _read_object(root, "run-spec/w2-contract-root.json")
    geometry = _read_object(root, "run-spec/w2-geometry-contract.json")
    operator = _read_object(root, "run-spec/w2-operator-contract.json")
    registry = _read_object(root, "run-spec/w2-schema-registry.json")
    parent = _read_object(root, "run-spec/parent-w1.json")
    w1_profile = _read_object(root, "run-spec/parent-w1-profile.json")
    w1_root = _read_object(root, "run-spec/parent-w1-contract-root.json")
    _exact(profile.get("schema"), W2_PROFILE_SCHEMA, name="profile schema")
    _exact(profile.get("family"), W2_FAMILY, name="profile family")
    _exact(contract_root.get("schema"), W2_CONTRACT_ROOT_SCHEMA, name="root schema")
    _exact(operator.get("schema"), W2_OPERATOR_SEMANTIC_SCHEMA, name="operator schema")
    _exact(registry.get("schema"), W2_SCHEMA_REGISTRY_SCHEMA, name="registry schema")
    if canonical_json_bytes(profile.get("geometry_contract")) != canonical_json_bytes(geometry):
        _fail("profile geometry does not equal standalone geometry")
    if canonical_json_bytes(profile.get("operator_semantic")) != canonical_json_bytes(operator):
        _fail("profile operator does not equal standalone operator")
    if canonical_json_bytes(profile.get("contract_root")) != canonical_json_bytes(contract_root):
        _fail("profile root does not equal standalone root")
    if canonical_json_bytes(profile.get("schema_registry")) != canonical_json_bytes(registry):
        _fail("profile registry does not equal standalone registry")
    if canonical_json_bytes(profile.get("parent_w1")) != canonical_json_bytes(parent):
        _fail("profile parent does not equal standalone parent")
    if not isinstance(w1_profile.get("schema"), str) or not isinstance(w1_root.get("schema"), str):
        _fail("embedded W1 material lacks schemas")
    _hash_field(w1_profile, w1_profile["schema"], field="profile_sha256", name="embedded W1 profile")
    _hash_field(w1_root, W1_CONTRACT_ROOT_HASH_DOMAIN, field="self_sha256", name="embedded W1 contract root")
    if w1_profile.get("contract_root_sha256") != w1_root.get("self_sha256"):
        _fail("embedded W1 profile/root link is invalid")
    generated_w1_keys = {"schema", "contract_root_sha256", "semantic_subhashes", "profile_sha256"}
    if set(w1_profile) != set(w1_source) | generated_w1_keys or any(w1_profile.get(key) != value for key, value in w1_source.items()):
        _fail("embedded W1 profile does not equal the source-exact development config")
    if parent.get("profile_sha256") != w1_profile.get("profile_sha256") or parent.get("contract_root_sha256") != w1_root.get("self_sha256"):
        _fail("W2 parent does not bind embedded W1 identity")
    if parent.get("spatial") != w1_profile.get("spatial"):
        _fail("W2 parent does not bind exact W1 spatial material")
    state_layout = parent.get("state_layout")
    field = w1_profile.get("field")
    if not isinstance(state_layout, Mapping) or not isinstance(field, Mapping):
        _fail("W2 parent state layout is missing")
    for key in ("scale_count", "mode_count", "component_count", "batch_limit", "active_shapes", "active_site_counts"):
        if state_layout.get(key) != field.get(key):
            _fail(f"W2 parent state layout {key} differs from W1")
    if parent.get("state_layout_sha256") != canonical_hash(parent["state_layout"], W2_PARENT_LINK_SCHEMA + ".state-layout") or parent.get("spatial_contract_sha256") != canonical_hash(parent["spatial"], W2_PARENT_LINK_SCHEMA + ".spatial"):
        _fail("W2 parent component hashes are invalid")
    geometry_hash = canonical_hash(geometry, W2_GEOMETRY_CONTRACT_SCHEMA)
    operator_hash = canonical_hash(operator, W2_OPERATOR_SEMANTIC_SCHEMA)
    registry_hash = canonical_hash(registry, W2_SCHEMA_REGISTRY_SCHEMA)
    if profile.get("geometry_contract_sha256") != geometry_hash or profile.get("operator_semantic_sha256") != operator_hash or profile.get("schema_registry_sha256") != registry_hash:
        _fail("W2 profile component hashes are invalid")
    _hash_field(contract_root, W2_CONTRACT_ROOT_SCHEMA, field="self_sha256", name="W2 contract root")
    _hash_field(profile, W2_PROFILE_SCHEMA, field="profile_sha256", name="W2 profile")
    if profile.get("contract_root_sha256") != contract_root.get("self_sha256"):
        _fail("profile root link is invalid")
    if operator.get("geometry_contract_sha256") != geometry_hash or operator.get("geometry_contract") != geometry or operator.get("parent_w1") != parent:
        _fail("operator semantic ancestry is invalid")
    expected_root_links = {
        "schema_registry": {"schema": W2_SCHEMA_REGISTRY_SCHEMA, "sha256": registry_hash},
        "geometry_contract": {"schema": W2_GEOMETRY_CONTRACT_SCHEMA, "sha256": geometry_hash},
        "operator_semantic": {"schema": W2_OPERATOR_SEMANTIC_SCHEMA, "sha256": operator_hash},
    }
    for key, expected in expected_root_links.items():
        if contract_root.get(key) != expected:
            _fail(f"root {key} link is invalid")
    if contract_root.get("parent_w1") != parent:
        _fail("root parent link is invalid")
    sheets = _verify_geometry_contract(geometry, w1_profile)
    return profile, contract_root, geometry, sheets


def _decode_tensor(raw: bytes, *, encoding: str, shape: list[int], name: str) -> torch.Tensor:
    count = math.prod(shape)
    try:
        if encoding == "float64-le":
            if len(raw) != count * 8:
                _fail(f"{name} byte count is wrong")
            values = [item[0] for item in struct.iter_unpack("<d", raw)]
            tensor = torch.tensor(values, dtype=torch.float64)
        elif encoding == "complex128-le-interleaved":
            if len(raw) != count * 16:
                _fail(f"{name} byte count is wrong")
            values = [complex(real, imaginary) for real, imaginary in struct.iter_unpack("<dd", raw)]
            tensor = torch.tensor(values, dtype=torch.complex128)
        else:
            _fail(f"{name} encoding is unknown")
    except struct.error as exc:
        raise W2GeometryVerificationError(f"{name} raw bytes are malformed") from exc
    tensor = tensor.reshape(shape).contiguous()
    if not bool(torch.isfinite(tensor).all().item()):
        _fail(f"{name} contains non-finite values")
    return tensor


def _fixture_field(sheet: Mapping[str, Any], *, lanes: int = 2) -> torch.Tensor:
    ny, nx = sheet["shape"]
    y = torch.arange(ny, dtype=torch.float64)[:, None] * sheet["dy"]
    x = torch.arange(nx, dtype=torch.float64)[None, :] * sheet["dx"]
    values = (
        torch.exp(1.0j * (2.0 * math.pi * y / sheet["ly"] + 4.0 * math.pi * x / sheet["lx"]))
        + 0.5 * torch.exp(-1.0j * (2.0 * math.pi * y / sheet["ly"] - 2.0 * math.pi * x / sheet["lx"]))
    )
    return torch.stack(tuple((lane + 1.0) * values + 0.125j * (sheet["scale"] + lane + 1.0) for lane in range(lanes)), dim=-1).contiguous()


def _nyquist_fixture(sheet: Mapping[str, Any], *, lanes: int = 2) -> torch.Tensor:
    ny, nx = sheet["shape"]
    pattern = torch.tensor([(-1.0) ** index for index in range(nx)], dtype=torch.complex128)
    return torch.stack(
        tuple(1.0j * (sheet["scale"] + 1.0) * (lane + 1.0) * pattern[None, :].repeat(ny, 1) for lane in range(lanes)),
        dim=-1,
    ).contiguous()


def _verify_fixtures(root: Path, sheets: list[dict[str, Any]], mode_count: int = 32) -> tuple[dict[str, Any], dict[str, torch.Tensor]]:
    manifest = _read_object(root, "gates/g2-geometry/fixtures.json")
    _exact_keys(manifest, {"schema", "family", "layout", "fixtures", "self_sha256"}, name="fixture manifest")
    _exact(manifest["schema"], FIXTURE_SCHEMA, name="fixture schema")
    _exact(manifest["family"], W2_FAMILY, name="fixture family")
    _exact(manifest["layout"], "row-major-last-lane-fastest", name="fixture layout")
    if manifest["self_sha256"] != _self_hash(manifest, FIXTURE_SCHEMA):
        _fail("fixture manifest self hash is invalid")
    expected: dict[str, tuple[str, str, list[int], torch.Tensor]] = {}
    for sheet in sheets:
        scale = sheet["scale"]
        field = _fixture_field(sheet)
        vector = torch.stack((field, (0.5 + 0.25j) * field.conj()), dim=0).contiguous()
        nyquist = _nyquist_fixture(sheet)
        expected[f"complex_scale_{scale}"] = (f"gates/g2-geometry/raw/complex-scale-{scale}.c128le", "complex128-le-interleaved", list(field.shape), field)
        expected[f"vector_scale_{scale}"] = (f"gates/g2-geometry/raw/vector-scale-{scale}.c128le", "complex128-le-interleaved", list(vector.shape), vector)
        expected[f"signed_nyquist_scale_{scale}"] = (
            "gates/g2-geometry/raw/signed-nyquist.c128le" if scale == 0 else f"gates/g2-geometry/raw/signed-nyquist-{scale}.c128le",
            "complex128-le-interleaved",
            list(nyquist.shape),
            nyquist,
        )
    epsilon = (torch.arange(1, mode_count * 2 + 1, dtype=torch.float64).reshape(mode_count, 2) / 128.0).contiguous()
    expected["epsilon2_ema"] = ("gates/g2-geometry/raw/epsilon2-ema.f64le", "float64-le", list(epsilon.shape), epsilon)
    records = manifest.get("fixtures")
    if not isinstance(records, list) or len(records) != len(expected):
        _fail("fixture record inventory is incomplete")
    if [record.get("fixture_id") for record in records if isinstance(record, Mapping)] != sorted(expected, key=lambda value: value.encode("utf-8")):
        _fail("fixture records are not uniquely UTF-8 sorted")
    decoded = {}
    for record in records:
        if not isinstance(record, Mapping):
            _fail("fixture record is not an object")
        _exact_keys(record, {"fixture_id", "path", "encoding", "shape", "byte_count", "sha256"}, name="fixture record")
        fixture_id = record["fixture_id"]
        if fixture_id not in expected:
            _fail("fixture id is unregistered")
        path, encoding, shape, normative = expected[fixture_id]
        _exact(record["path"], path, name=f"{fixture_id} path")
        _exact(record["encoding"], encoding, name=f"{fixture_id} encoding")
        _exact(record["shape"], shape, name=f"{fixture_id} shape")
        if not isinstance(record["byte_count"], int) or isinstance(record["byte_count"], bool) or not _is_sha256(record["sha256"]):
            _fail(f"{fixture_id} byte identity is malformed")
        raw_path = root / _valid_relative_path(path)
        raw = raw_path.read_bytes() if raw_path.is_file() else b""
        if len(raw) != record["byte_count"] or _sha256(raw) != record["sha256"]:
            _fail(f"{fixture_id} raw identity failed")
        tensor = _decode_tensor(raw, encoding=encoding, shape=shape, name=fixture_id)
        if not torch.equal(tensor, normative):
            _fail(f"{fixture_id} differs from the independent deterministic fixture")
        decoded[fixture_id] = tensor
    return manifest, decoded


def _max_abs(values: torch.Tensor) -> float:
    return float(values.abs().max().item()) if values.numel() else 0.0

def _normalized_error(actual: torch.Tensor, expected: torch.Tensor) -> float:
    scale = max(1.0, _max_abs(actual), _max_abs(expected))
    return _max_abs(actual - expected) / scale


def _fft2(values: torch.Tensor) -> torch.Tensor:
    return torch.fft.fft2(values, dim=(-3, -2), norm="ortho")


def _ifft2(values: torch.Tensor) -> torch.Tensor:
    return torch.fft.ifft2(values, dim=(-3, -2), norm="ortho")


def _symbols(sheet: Mapping[str, Any]) -> tuple[torch.Tensor, torch.Tensor]:
    ky = (2.0 * math.pi / sheet["ly"]) * torch.tensor(sheet["frequency_y"], dtype=torch.float64)
    kx = (2.0 * math.pi / sheet["lx"]) * torch.tensor(sheet["frequency_x"], dtype=torch.float64)
    return ky[:, None].to(torch.complex128), kx[None, :].to(torch.complex128)


def _apply(values: torch.Tensor, symbol: torch.Tensor) -> torch.Tensor:
    return _ifft2((_fft2(values) * symbol[..., None]).contiguous())


def _gradient(values: torch.Tensor, sheet: Mapping[str, Any]) -> torch.Tensor:
    ky, kx = _symbols(sheet)
    return torch.stack((_apply(values, 1.0j * kx), _apply(values, 1.0j * ky)), dim=0).contiguous()


def _divergence(values: torch.Tensor, sheet: Mapping[str, Any]) -> torch.Tensor:
    gradient_x = _gradient(values[0].contiguous(), sheet)[0]
    gradient_y = _gradient(values[1].contiguous(), sheet)[1]
    return (gradient_x + gradient_y).contiguous()


def _laplacian(values: torch.Tensor, sheet: Mapping[str, Any]) -> torch.Tensor:
    ky, kx = _symbols(sheet)
    return _apply(values, -(ky.square() + kx.square()))


def _curl(values: torch.Tensor, sheet: Mapping[str, Any]) -> torch.Tensor:
    return (_gradient(values[1].contiguous(), sheet)[0] - _gradient(values[0].contiguous(), sheet)[1]).contiguous()


def _inner(left: torch.Tensor, right: torch.Tensor, *, area: float) -> torch.Tensor:
    return torch.sum(left.conj() * right, dim=tuple(range(left.ndim - 1))) * area


def _translate(values: torch.Tensor, sheet: Mapping[str, Any], delta: tuple[float, float]) -> torch.Tensor:
    ky, kx = _symbols(sheet)
    phase = torch.exp((-1.0j) * (ky * delta[0] + kx * delta[1]))
    return _ifft2((_fft2(values) * phase[..., None]).contiguous())


def _rotate(values: torch.Tensor, quarter_turns: int) -> torch.Tensor:
    if quarter_turns % 4 == 0:
        return values.clone()
    rotated = torch.roll(torch.flip(values, dims=(-3, -2)), shifts=(1, 1), dims=(-3, -2))
    return (-rotated if values.ndim == 4 else rotated).contiguous()


def _fft_matrix(sheet: Mapping[str, Any]) -> torch.Tensor:
    ny, nx = sheet["shape"]
    y = torch.arange(ny, dtype=torch.float64)
    x = torch.arange(nx, dtype=torch.float64)
    fy = torch.tensor(sheet["frequency_y"], dtype=torch.float64)
    fx = torch.tensor(sheet["frequency_x"], dtype=torch.float64)
    matrix_y = torch.exp((-2.0j * math.pi / ny) * fy[:, None] * y[None, :]) / math.sqrt(ny)
    matrix_x = torch.exp((-2.0j * math.pi / nx) * fx[:, None] * x[None, :]) / math.sqrt(nx)
    return torch.kron(matrix_y, matrix_x).to(torch.complex128)


def _cross_matrix(source: Mapping[str, Any], target: Mapping[str, Any]) -> torch.Tensor:
    if (source["ly"], source["lx"]) != (target["ly"], target["lx"]):
        _fail("cross-scale extents differ")
    if source["shape"] == target["shape"]:
        return torch.eye(source["active_count"], dtype=torch.complex128)
    target_pairs = {(y, x): row for row, (y, x) in enumerate((pair for y in target["frequency_y"] for pair in ((y, x) for x in target["frequency_x"])))}
    injection = torch.zeros((target["active_count"], source["active_count"]), dtype=torch.complex128)
    for row, pair in enumerate((pair for y in source["frequency_y"] for pair in ((y, x) for x in source["frequency_x"]))):
        target_row = target_pairs.get(pair)
        if target_row is not None:
            injection[target_row, row] = math.sqrt(target["active_count"] / source["active_count"])
    return (_fft_matrix(target).conj().T @ injection @ _fft_matrix(source)).contiguous()


def _axis_overlap(source_count: int, target_count: int, extent: float) -> torch.Tensor:
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


def _remap_matrix(source: Mapping[str, Any], target: Mapping[str, Any]) -> torch.Tensor:
    return torch.kron(
        _axis_overlap(source["shape"][0], target["shape"][0], source["ly"]),
        _axis_overlap(source["shape"][1], target["shape"][1], source["lx"]),
    ).contiguous()


def _inject(values: torch.Tensor, sheet: Mapping[str, Any], factors: tuple[int, int]) -> torch.Tensor:
    spectrum = _fft2(values)
    ny, nx = sheet["shape"]
    fine_y, fine_x = ny * factors[0], nx * factors[1]
    fine = torch.zeros((*spectrum.shape[:-3], fine_y, fine_x, spectrum.shape[-1]), dtype=torch.complex128)
    for y, signed_y in enumerate(sheet["frequency_y"]):
        for x, signed_x in enumerate(sheet["frequency_x"]):
            fine[..., signed_y % fine_y, signed_x % fine_x, :] = spectrum[..., y, x, :]
    return _ifft2((fine * math.sqrt(factors[0] * factors[1])).contiguous())


def _restrict(values: torch.Tensor, sheet: Mapping[str, Any], factors: tuple[int, int]) -> torch.Tensor:
    spectrum = _fft2(values)
    ny, nx = sheet["shape"]
    fine_y, fine_x = ny * factors[0], nx * factors[1]
    coarse = torch.empty((*spectrum.shape[:-3], ny, nx, spectrum.shape[-1]), dtype=torch.complex128)
    for y, signed_y in enumerate(sheet["frequency_y"]):
        for x, signed_x in enumerate(sheet["frequency_x"]):
            coarse[..., y, x, :] = spectrum[..., signed_y % fine_y, signed_x % fine_x, :]
    return _ifft2((coarse / math.sqrt(factors[0] * factors[1])).contiguous())


def _bandlimited_gaussian(sheet: Mapping[str, Any]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    ny, nx = sheet["shape"]
    y = torch.arange(ny, dtype=torch.float64)[:, None] * sheet["dy"]
    x = torch.arange(nx, dtype=torch.float64)[None, :] * sheet["dx"]
    value = torch.zeros((ny, nx), dtype=torch.complex128)
    derivative_x = torch.zeros_like(value)
    derivative_y = torch.zeros_like(value)
    laplacian = torch.zeros_like(value)
    for frequency_y in [value for value in sheet["frequency_y"] if abs(value) <= 1]:
        for frequency_x in [value for value in sheet["frequency_x"] if abs(value) <= 2]:
            coefficient = math.exp(-0.6 * (frequency_y * frequency_y + frequency_x * frequency_x))
            ky = 2.0 * math.pi * frequency_y / sheet["ly"]
            kx = 2.0 * math.pi * frequency_x / sheet["lx"]
            wave = coefficient * torch.exp(1.0j * (ky * y + kx * x))
            value += wave
            derivative_x += 1.0j * kx * wave
            derivative_y += 1.0j * ky * wave
            laplacian -= (kx * kx + ky * ky) * wave
    return value[..., None].contiguous(), derivative_x[..., None].contiguous(), derivative_y[..., None].contiguous(), laplacian[..., None].contiguous()


def _reported(mapping: Mapping[str, Any], key: str, actual: float, actual_errors: list[float], *, tolerance: float = TOLERANCE) -> None:
    claimed = _as_f64(mapping.get(key), name=key)
    if actual > tolerance or claimed > tolerance or abs(claimed - actual) > max(1.0e-12, tolerance * 0.01):
        _fail(f"independent replay disagrees with {key}")
    actual_errors.append(actual)


def _verify_coordinate_conversions(rows: Mapping[str, Any], fields: list[torch.Tensor]) -> None:
    _exact(_as_f64(rows.get("phi"), name="coordinate phi"), PHI, name="coordinate phi")
    random = fields[0]
    basis = torch.eye(8, 2, dtype=torch.float64).to(torch.complex128)
    conjugate = random.reshape(-1, random.shape[-1])[:8].contiguous()
    fixtures = {
        "zero": (torch.zeros_like(basis), torch.zeros_like(basis)),
        "basis": (basis, torch.flip(basis, dims=(0,)).contiguous()),
        "random": (random, (0.5j * random).contiguous()),
        "conjugate_pair": (conjugate, conjugate.conj().contiguous()),
        "amplitude_extremes": (torch.full_like(basis, 0.5 + 0.5j), torch.full_like(basis, -0.5 + 0.5j)),
    }
    actual_rows = rows.get("fixtures")
    if not isinstance(actual_rows, list) or [row.get("fixture") for row in actual_rows if isinstance(row, Mapping)] != list(fixtures):
        _fail("coordinate conversion fixture inventory is wrong")
    for row, (fixture_id, (ey, ei)) in zip(actual_rows, fixtures.items()):
        if not isinstance(row, Mapping):
            _fail("coordinate conversion row is malformed")
        d = ey - PHI * ei
        c = (PHI * ey + ei) * W_D
        restored_ey = W_D * d + PHI * c
        restored_ei = c - PHI * W_D * d
        position_error = max(_max_abs(restored_ey - ey), _max_abs(restored_ei - ei))
        metric_error = _max_abs(W_D * d.abs().square() + W_C * c.abs().square() - (ey.abs().square() + ei.abs().square()))
        if row.get("fixture") != fixture_id or _as_f64(row.get("position_roundtrip_error"), name="position roundtrip") > TOLERANCE or _as_f64(row.get("velocity_roundtrip_error"), name="velocity roundtrip") > TOLERANCE or _as_f64(row.get("metric_identity_error"), name="metric identity") > TOLERANCE:
            _fail("coordinate conversion receipt exceeds tolerance")
        if position_error > TOLERANCE or metric_error > TOLERANCE:
            _fail("independent coordinate conversion replay failed")


def _verify_rows(candidate: Mapping[str, Any], decoded: Mapping[str, torch.Tensor], sheets: list[dict[str, Any]]) -> float:
    rows = candidate.get("rows")
    if not isinstance(rows, Mapping):
        _fail("candidate rows are missing")
    _exact_keys(rows, {"per_scale", "zero_tail", "coordinate_translation", "cross_scale", "epsilon2_ema", "maximum_numeric_error", "numeric_error_count"}, name="candidate rows")
    per_scale = rows.get("per_scale")
    if not isinstance(per_scale, list) or len(per_scale) != len(sheets):
        _fail("per-scale evidence is incomplete")
    actual_errors: list[float] = []
    fields = []
    for sheet, row in zip(sheets, per_scale):
        if not isinstance(row, Mapping):
            _fail("per-scale evidence row is malformed")
        scale = sheet["scale"]
        field = decoded[f"complex_scale_{scale}"]
        vector = decoded[f"vector_scale_{scale}"]
        nyquist = decoded[f"signed_nyquist_scale_{scale}"]
        fields.append(field)
        _exact(row.get("scale"), scale, name="evidence scale")
        _exact(row.get("shape_yx"), list(sheet["shape"]), name="evidence shape")
        _exact(row.get("active_site_count"), sheet["active_count"], name="evidence active count")
        _exact(row.get("signed_frequency_y"), sheet["frequency_y"], name="evidence signed y")
        _exact(row.get("signed_frequency_x"), sheet["frequency_x"], name="evidence signed x")
        if _as_f64(row.get("coordinate_origin_error"), name="coordinate origin") > TOLERANCE or _as_f64(row.get("coordinate_spacing_error"), name="coordinate spacing") > TOLERANCE:
            _fail("coordinate evidence exceeds tolerance")
        errors = row.get("errors")
        if not isinstance(errors, Mapping):
            _fail("per-scale numeric errors are missing")
        fft = _fft2(field)
        packed = field.reshape(sheet["active_count"], field.shape[-1])
        gradient = _gradient(field, sheet)
        divergence = _divergence(vector, sheet)
        laplacian = _laplacian(field, sheet)
        ones = torch.ones((*sheet["shape"], 1), dtype=torch.complex128)
        ny, nx = sheet["shape"]
        y = torch.arange(ny, dtype=torch.float64)[:, None] * sheet["dy"]
        x = torch.arange(nx, dtype=torch.float64)[None, :] * sheet["dx"]
        ramp = (torch.sin(2.0 * math.pi * y / sheet["ly"]) + 0.5 * torch.sin(2.0 * math.pi * x / sheet["lx"]))[..., None].to(torch.complex128).contiguous()
        ramp_dx = (math.pi / sheet["lx"] * torch.cos(2.0 * math.pi * x / sheet["lx"]))[..., None].to(torch.complex128)
        ramp_dy = (2.0 * math.pi / sheet["ly"] * torch.cos(2.0 * math.pi * y / sheet["ly"]))[..., None].to(torch.complex128)
        plane = torch.exp(1.0j * (2.0 * math.pi * y / sheet["ly"] + 4.0 * math.pi * x / sheet["lx"]))[..., None].contiguous()
        gaussian, gaussian_dx, gaussian_dy, gaussian_laplacian = _bandlimited_gaussian(sheet)
        translated = _translate(field, sheet, (sheet["dy"], sheet["dx"]))
        rotated = _rotate(field, 2)
        factors = sheet["oversampling"]
        fine = _inject(field, sheet, factors)
        fft_expected = fft.reshape(sheet["active_count"], field.shape[-1])
        nyquist_expected = (math.pi / sheet["dx"]) * nyquist.imag
        div_grad = _divergence(gradient, sheet)
        gradient_left = _inner(gradient, vector, area=sheet["area"])
        gradient_right = -_inner(field, divergence, area=sheet["area"])
        laplacian_left = _inner(field, laplacian, area=sheet["area"])
        laplacian_right = _inner(laplacian, field, area=sheet["area"])
        translated_expected = torch.roll(field, shifts=(1, 1), dims=(0, 1))
        rotated_expected = torch.roll(torch.flip(field, dims=(0, 1)), shifts=(1, 1), dims=(0, 1))
        constant_gradient = _gradient(ones, sheet)
        constant_laplacian = _laplacian(ones, sheet)
        ramp_gradient = _gradient(ramp, sheet)
        plane_gradient = _gradient(plane, sheet)
        plane_laplacian = _laplacian(plane, sheet)
        gaussian_gradient = _gradient(gaussian, sheet)
        gaussian_laplacian_actual = _laplacian(gaussian, sheet)
        restricted_fine = _restrict(fine, sheet, factors)
        injected_constant = _inject(ones, sheet, factors)
        fine_metric = _inner(fine, fine, area=sheet["area"] / (factors[0] * factors[1]))
        base_metric = _inner(field, field, area=sheet["area"])
        projected_fine = _inject(restricted_fine, sheet, factors)
        actual = {
            "mode_roundtrip_error": 0.0,
            "gather_scatter_error": 0.0,
            "fft_roundtrip_error": _normalized_error(_ifft2(fft), field),
            "fft_matrix_error": _normalized_error(_fft_matrix(sheet) @ packed, fft_expected),
            "signed_nyquist_gradient_error": _normalized_error(_gradient(nyquist, sheet)[0], nyquist_expected),
            "divergence_gradient_laplacian_error": _normalized_error(div_grad, laplacian),
            "gradient_divergence_adjoint_error": _normalized_error(gradient_left, gradient_right),
            "laplacian_self_adjoint_error": _normalized_error(laplacian_left, laplacian_right),
            "translation_error": _normalized_error(translated, translated_expected),
            "translation_inverse_error": _normalized_error(_translate(translated, sheet, (-sheet["dy"], -sheet["dx"])), field),
            "rotation_error": _normalized_error(rotated, rotated_expected),
            "rotation_inverse_error": _normalized_error(_rotate(rotated, 2), field),
            "release_translation_identity_error": _normalized_error(_translate(field, sheet, (0.0, 0.0)), field),
            "release_rotation_identity_error": _normalized_error(_rotate(field, 0), field),
            "constant_gradient_error": _normalized_error(constant_gradient, torch.zeros_like(constant_gradient)),
            "constant_laplacian_error": _normalized_error(constant_laplacian, torch.zeros_like(constant_laplacian)),
            "ramp_gradient_error": max(
                _normalized_error(ramp_gradient[0], ramp_dx),
                _normalized_error(ramp_gradient[1], ramp_dy),
            ),
            "sinusoid_gradient_error": max(
                _normalized_error(plane_gradient[0], 1.0j * (4.0 * math.pi / sheet["lx"]) * plane),
                _normalized_error(plane_gradient[1], 1.0j * (2.0 * math.pi / sheet["ly"]) * plane),
            ),
            "plane_wave_laplacian_error": _normalized_error(
                plane_laplacian,
                -((4.0 * math.pi / sheet["lx"]) ** 2 + (2.0 * math.pi / sheet["ly"]) ** 2) * plane,
            ),
            "gaussian_gradient_error": max(
                _normalized_error(gaussian_gradient[0], gaussian_dx),
                _normalized_error(gaussian_gradient[1], gaussian_dy),
            ),
            "gaussian_laplacian_error": _normalized_error(gaussian_laplacian_actual, gaussian_laplacian),
            "oversampling_roundtrip_error": _normalized_error(restricted_fine, field),
            "oversampling_constant_error": _normalized_error(injected_constant, torch.ones_like(injected_constant)),
            "oversampling_metric_error": _normalized_error(fine_metric, base_metric),
            "oversampling_projector_error": _normalized_error(projected_fine, fine),
        }
        if set(errors) != set(actual):
            _fail("per-scale error inventory is not exact")
        for key, value in actual.items():
            _reported(errors, key, value, actual_errors)
        if _as_f64(row.get("curl_norm"), name="curl norm") <= 0.0 or _as_f64(row.get("nyquist_imaginary_norm"), name="nyquist norm") <= 0.0:
            _fail("nonzero G2 observability fixture collapsed")
    expected_tail = {
        "inactive_tail_is_exact_zero": True,
        "per_scale": [
            {"scale": sheet["scale"], "active_slots": sheet["active_count"], "inactive_slots": 32 - sheet["active_count"], "inactive_nonzero": 0}
            for sheet in sheets
        ],
    }
    _exact(rows.get("zero_tail"), expected_tail, name="zero-tail proof")
    _verify_coordinate_conversions(rows.get("coordinate_translation", {}), fields)
    cross_rows = rows.get("cross_scale")
    remap_rows = rows.get("epsilon2_ema")
    if not isinstance(cross_rows, list) or not isinstance(remap_rows, list) or len(cross_rows) != 16 or len(remap_rows) != 16:
        _fail("cross-scale/remap evidence inventory is incomplete")
    position = 0
    epsilon = decoded["epsilon2_ema"]
    for source in sheets:
        for target in sheets:
            cross = cross_rows[position]
            remap = remap_rows[position]
            if not isinstance(cross, Mapping) or not isinstance(remap, Mapping):
                _fail("cross-scale/remap row is malformed")
            _exact((cross.get("source_scale"), cross.get("target_scale")), (source["scale"], target["scale"]), name="cross-scale pair")
            matrix = _cross_matrix(source, target)
            adjoint = matrix.conj().T * (target["area"] / source["area"])
            _exact(cross.get("matrix_shape"), list(matrix.shape), name="cross matrix shape")
            _exact(cross.get("adjoint_matrix_shape"), list(adjoint.shape), name="cross adjoint shape")
            right = fields[source["scale"]].reshape(source["active_count"], -1)
            left = fields[target["scale"]].reshape(target["active_count"], -1)
            mapped = (matrix @ right).reshape(*target["shape"], -1)
            adjoint_mapped = (adjoint @ left).reshape(*source["shape"], -1)
            actual_adjoint = _normalized_error(
                _inner(fields[target["scale"]], mapped, area=target["area"]),
                _inner(adjoint_mapped, fields[source["scale"]], area=source["area"]),
            )
            _reported(cross, "weighted_adjoint_error", actual_adjoint, actual_errors)
            _exact((remap.get("source_scale"), remap.get("target_scale")), (source["scale"], target["scale"]), name="remap pair")
            active_source = epsilon[: source["active_count"]]
            mapped_epsilon = _remap_matrix(source, target) @ active_source
            source_mass = torch.sum(active_source, dim=0) * source["area"]
            target_mass = torch.sum(mapped_epsilon, dim=0) * target["area"]
            mass_error = _normalized_error(target_mass, source_mass)
            _reported(remap, "mass_error", mass_error, actual_errors)
            if _as_f64(remap.get("source_minimum"), name="source minimum") < 0.0 or _as_f64(remap.get("target_minimum"), name="target minimum") < 0.0 or bool(torch.any(mapped_epsilon < 0.0).item()):
                _fail("positive remap evidence is negative")
            position += 1
    controls = candidate.get("mutation_controls")
    if not isinstance(controls, Mapping) or set(controls) != _CONTROL_IDS or any(value is not True for value in controls.values()):
        _fail("G2 mutation controls are incomplete")
    claimed_maximum = _as_f64(rows.get("maximum_numeric_error"), name="maximum numeric error")
    actual_maximum = max(actual_errors)
    if claimed_maximum > TOLERANCE or actual_maximum > TOLERANCE or abs(claimed_maximum - actual_maximum) > 1.0e-12:
        _fail("maximum numeric error receipt is invalid")
    if rows.get("numeric_error_count") != len(actual_errors):
        _fail("numeric error count is invalid")
    return actual_maximum


def _verify_gate_and_index(
    root: Path,
    profile: Mapping[str, Any],
    source_identity: Mapping[str, Any],
    fixture_manifest: Mapping[str, Any],
    sheets: list[dict[str, Any]],
    decoded: Mapping[str, torch.Tensor],
) -> tuple[dict[str, Any], dict[str, Any], float]:
    candidate = _read_object(root, "gates/g2-geometry/candidate.json")
    _exact(candidate.get("schema"), W2_G2_CANDIDATE_SCHEMA, name="candidate schema")
    _exact(candidate.get("family"), W2_FAMILY, name="candidate family")
    if candidate.get("self_sha256") != _self_hash(candidate, W2_G2_CANDIDATE_SCHEMA):
        _fail("candidate self hash is invalid")
    for key in ("parent_w1", "profile_sha256", "contract_root_sha256", "geometry_contract_sha256", "operator_semantic_sha256"):
        expected = profile.get(key)
        if candidate.get(key) != expected:
            _fail(f"candidate {key} ancestry is invalid")
    if candidate.get("source_identity_sha256") != source_identity.get("self_sha256") or candidate.get("fixture_manifest_sha256") != fixture_manifest.get("self_sha256"):
        _fail("candidate source/fixture ancestry is invalid")
    _exact(candidate.get("tolerance"), _f64(TOLERANCE), name="candidate tolerance")
    metadata = candidate.get("operator_metadata")
    if not isinstance(metadata, Mapping):
        _fail("operator metadata is missing")
    _exact(metadata.get("active_shapes_yx"), [list(sheet["shape"]) for sheet in sheets], name="metadata shapes")
    _exact(metadata.get("active_site_counts"), [sheet["active_count"] for sheet in sheets], name="metadata active counts")
    _exact(metadata.get("per_scale_sheets"), profile["geometry_contract"]["per_scale_sheets"], name="metadata sheets")
    if metadata.get("geometry_profile_sha256") != profile.get("profile_sha256") or metadata.get("geometry_contract_root_sha256") != profile.get("contract_root_sha256") or metadata.get("operator_semantic_sha256") != profile.get("operator_semantic_sha256"):
        _fail("operator metadata ancestry is invalid")
    maximum_error = _verify_rows(candidate, decoded, sheets)
    status = _read_object(root, "gates/g2-geometry/status.json")
    _exact_keys(status, {"schema", "family", "gate", "status", "candidate_sha256", "profile_sha256", "source_identity_sha256", "fixture_manifest_sha256", "self_sha256"}, name="gate status")
    _exact((status.get("schema"), status.get("family"), status.get("gate"), status.get("status")), (W2_GATE_STATUS_SCHEMA, W2_FAMILY, "G2", "PASS"), name="gate status identity")
    if status.get("candidate_sha256") != candidate.get("self_sha256") or status.get("profile_sha256") != profile.get("profile_sha256") or status.get("source_identity_sha256") != source_identity.get("self_sha256") or status.get("fixture_manifest_sha256") != fixture_manifest.get("self_sha256"):
        _fail("gate status ancestry is invalid")
    if status.get("self_sha256") != _self_hash(status, W2_GATE_STATUS_SCHEMA):
        _fail("gate status self hash is invalid")
    index = _read_object(root, "index.json")
    _exact_keys(index, {"schema", "artifact_schema", "family", "parent_w1", "profile_sha256", "contract_root_sha256", "geometry_contract_sha256", "operator_semantic_sha256", "source_identity_sha256", "candidate_sha256", "objects", "run_id", "status", "self_sha256"}, name="run index")
    _exact((index.get("schema"), index.get("artifact_schema"), index.get("family"), index.get("status")), (W2_RUN_INDEX_SCHEMA, W2_RUN_DOMAIN, W2_FAMILY, "PASS_W2_G2"), name="run index identity")
    for key in ("parent_w1", "profile_sha256", "contract_root_sha256", "geometry_contract_sha256", "operator_semantic_sha256"):
        if index.get(key) != profile.get(key):
            _fail(f"run index {key} ancestry is invalid")
    if index.get("source_identity_sha256") != source_identity.get("self_sha256") or index.get("candidate_sha256") != candidate.get("self_sha256"):
        _fail("run index evidence ancestry is invalid")
    objects = index.get("objects")
    if not isinstance(objects, list):
        _fail("run index objects are missing")
    actual_paths = sorted(
        (path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.name != "index.json"),
        key=lambda value: value.encode("utf-8"),
    )
    if [record.get("path") for record in objects if isinstance(record, Mapping)] != actual_paths:
        _fail("run index object inventory/order is wrong")
    for record in objects:
        if not isinstance(record, Mapping):
            _fail("run index object record is malformed")
        _exact_keys(record, {"path", "byte_count", "sha256"}, name="run object")
        relative = _valid_relative_path(record["path"])
        path = root / relative
        raw = path.read_bytes() if path.is_file() else b""
        if len(raw) != record.get("byte_count") or _sha256(raw) != record.get("sha256"):
            _fail(f"run object identity failed for {relative}")
    material = dict(index)
    material.pop("run_id")
    material.pop("status")
    material.pop("self_sha256")
    if index.get("run_id") != canonical_hash(material, W2_RUN_DOMAIN):
        _fail("run id is invalid")
    if index.get("self_sha256") != _self_hash(index, W2_RUN_INDEX_SCHEMA):
        _fail("run index self hash is invalid")
    return candidate, index, maximum_error


def verify_artifact(artifact: Path | str) -> dict[str, Any]:
    """Verify a complete sealed W2/G2 artifact without importing W2 code."""

    root = Path(artifact).resolve()
    if not root.is_dir():
        _fail("W2 artifact directory does not exist")
    source_identity, _, w1_source = _verify_source_identity(root)
    profile, _, _, sheets = _verify_profile_chain(root, w1_source)
    fixture_manifest, decoded = _verify_fixtures(root, sheets)
    candidate, index, maximum_error = _verify_gate_and_index(root, profile, source_identity, fixture_manifest, sheets, decoded)
    receipt: dict[str, Any] = {
        "schema": "cassi.qi-flow-w2-periodic-fft2-verification.v1",
        "status": "PASS_W2_G2",
        "run_id": index["run_id"],
        "candidate_sha256": candidate["self_sha256"],
        "source_identity_sha256": source_identity["self_sha256"],
        "maximum_numeric_error": _f64(maximum_error),
    }
    receipt["self_sha256"] = canonical_hash(receipt, receipt["schema"])
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify a sealed W2/G2 ragged periodic FFT2 artifact.")
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_artifact(args.artifact), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
