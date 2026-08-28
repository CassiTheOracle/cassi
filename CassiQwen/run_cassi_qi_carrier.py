"""Seal the source-exact W4/G4 periodic-FFT2 carrier artifact."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from cassi_qi_carrier import (
    W4_CARRIER_CANDIDATE_SCHEMA,
    W4_CARRIER_RECEIPT_DOMAIN,
    W4_RAW_STATE_DOMAIN,
    build_composition_derivation,
    build_composition_section,
    carrier_coordinates,
    carrier_total_energy,
    composition_forces,
    composition_reversal_fixture,
    load_w4_carrier_profile,
    negate_differential_coordinate,
    phase_current_reversal,
    phase_shuffled_equal_energy,
    transition_v4_carrier,
    yang_yin_exchange,
)
from cassi_qi_field import QiFlowStateV3
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_numerical_certificate import raw_state_bytes_from_field
from cassi_qi_profile import canonical_hash, canonical_json_bytes, load_development_profile
from cassi_qi_transport import load_w3_transport_profile, w3_stage_schedule

ROOT = Path(__file__).resolve().parent

# These identities deliberately belong to this runner's periodic-FFT2 evidence
# surface.  Law objects returned by cassi_qi_carrier retain their own immutable
# identities; this layer never invents a parent/run hash or reads an old one.
INDEX_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w4-periodic-fft2-artifact.v1"
MANIFEST_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-manifest.v1"
SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-source-identity.v1"
PARENT_IDENTITY_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-parent-w3n.v1"
PROFILE_BINDING_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-profile-binding.v1"
STAGE_SCHEDULE_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-stage-schedule.v1"
STATE_METADATA_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-state.v1"
RUNTIME_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-runtime.v1"
CONTROL_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-control.v1"
CONTROLS_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-controls.v1"
CERTIFICATE_EXTENSION_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-certificate-extension.v1"
HASH_GRAPH_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-hash-graph.v1"
STATUS_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-status.v1"
RAW_STATE_DOMAIN = W4_RAW_STATE_DOMAIN
RAW_FIXTURE_DOMAIN = "cassi.qi-flow-w4-periodic-fft2.raw-fixture.v1"

W3N_INDEX_SCHEMA = "cassi.qi-flow-w3n-periodic-fft2-index.v1"
W3N_STATUS = "PASS_W3N_G3N"
W3N_ROOT_NAME = "cassi-qi-flow-w3n-periodic-fft2-final"
W3_ROOT_NAME = "cassi-qi-flow-w3-periodic-fft2-final"
W2_ROOT_NAME = "cassi-qi-flow-w2-periodic-fft2-final"
W4_ROOT_NAME = "cassi-qi-flow-w4-periodic-fft2-final"

SOURCE_PATHS = tuple(
    sorted(
        (
            "cassi_qi_carrier.py",
            "run_cassi_qi_carrier.py",
            "verify_cassi_qi_carrier.py",
            "cassi_qi_numerical_certificate.py",
            "cassi_qi_field.py",
            "cassi_qi_geometry.py",
            "cassi_qi_transport.py",
            "cassi_qi_profile.py",
        ),
        key=lambda value: value.encode("utf-8"),
    )
)

CONTROL_IDS = (
    "D-only",
    "C-only",
    "D+C",
    "zero",
    "uniform",
    "structured",
    "scale-local",
    "potential-off",
    "imbalance-plus",
    "imbalance-minus",
    "coordinate-negation",
    "phase-current-reversal",
    "yang-yin-exchange",
    "phase-shuffled-equal-energy",
)


class CarrierArtifactError(RuntimeError):
    """The current validated W4 inputs cannot produce a sealed artifact."""


def _plain(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except Exception as exc:
        raise CarrierArtifactError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw.rstrip(b"\r\n"):
        raise CarrierArtifactError(f"canonical JSON object required: {path}")
    return value


def _write(stage: Path, relative: str, raw: bytes) -> None:
    path = stage / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _write_json(stage: Path, relative: str, value: Any) -> None:
    _write(stage, relative, canonical_json_bytes(_plain(value)))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _number(value: Any) -> float:
    if isinstance(value, str) and value.startswith("f64:") and len(value) == 20:
        return float(struct.unpack(">d", bytes.fromhex(value[4:]))[0])
    return float(value)


def _object_hash(value: Mapping[str, Any], domain: str) -> str:
    return canonical_hash(_plain(value), domain)


def _root(name: str) -> Path:
    return ROOT / "_diag" / name


def _field_layout(geometry: Any) -> dict[str, Any]:
    base = geometry.base_profile
    layout = _plain(base.state_layout)
    if not isinstance(layout, Mapping):
        raise CarrierArtifactError("validated profile has no state layout")
    scales = int(layout["scale_count"])
    modes = int(layout["mode_count"])
    components = int(layout["component_count"])
    batch_limit = int(layout["batch_limit"])
    active_shapes = [
        [int(shape[0]), int(shape[1])]
        for shape in layout.get("active_shapes", [])
    ]
    active_counts = [int(value) for value in layout.get("active_site_counts", [])]
    if len(active_shapes) != scales or len(active_counts) != scales:
        spatial = _plain(base.payload["spatial"])
        active_shapes = [[int(shape[0]), int(shape[1])] for shape in spatial["active_shapes"]]
        active_counts = [ny * nx for ny, nx in active_shapes]
    if scales < 1 or modes < 1 or components != 9 or batch_limit < 1:
        raise CarrierArtifactError("validated profile has an invalid [S,9M,B] layout")
    if any(count < 1 or count > modes for count in active_counts):
        raise CarrierArtifactError("validated profile active sheets exceed packed modes")
    component_order = list(base.payload["field"].get("component_order", []))
    required_components = ("Y_re", "Y_im", "I_re", "I_im", "VY_re", "VY_im", "VI_re", "VI_im", "epsilon2_ema")
    if tuple(component_order) != required_components:
        raise CarrierArtifactError("validated profile has no canonical nine-component order")
    return {
        "layout_id": str(layout.get("layout_id", "cassi.qi-flow-state-layout.v3")),
        "shape_prefix": [scales, components * modes],
        "scale_count": scales,
        "mode_count": modes,
        "component_count": components,
        "batch_limit": batch_limit,
        "dtype": str(layout.get("tensor_dtype")),
        "byte_order": str(layout.get("state_object_endianness")),
        "component_order": component_order,
        "active_shapes": active_shapes,
        "active_site_counts": active_counts,
    }


def _parent_source_rows(identity: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = identity.get("sources")
    if not isinstance(rows, list) or not rows:
        raise CarrierArtifactError("W3N source identity has no source rows")
    return rows


def _source_rows_are_current(identity: Mapping[str, Any]) -> bool:
    try:
        for row in _parent_source_rows(identity):
            relative = row.get("path")
            if not isinstance(relative, str):
                return False
            source = ROOT / relative
            if not source.is_file():
                return False
            raw = source.read_bytes()
            expected_bytes = row.get("bytes", row.get("byte_count"))
            if expected_bytes != len(raw) or row.get("sha256") != _sha(raw):
                return False
        claimed = identity.get("source_identity_sha256")
        if not isinstance(claimed, str):
            return False
        body = {key: value for key, value in identity.items() if key != "source_identity_sha256"}
        return claimed == canonical_hash(body, identity["schema"])
    except Exception:
        return False


def _candidate_identity(directory: Path, index: Mapping[str, Any], verification: Mapping[str, Any]) -> dict[str, Any]:
    identity_path = directory / "run-spec" / "source-identity.json"
    identity = _read_json(identity_path)
    parent_index = _plain(index)
    parents = parent_index.get("parents")
    if isinstance(parents, Mapping):
        w3 = _plain(parents.get("w3", {}))
        w2 = _plain(parents.get("w2", {}))
    else:
        w3 = _read_json(directory / "run-spec" / "accepted-w3.json") if (directory / "run-spec" / "accepted-w3.json").is_file() else {}
        w2 = {}
    if not w3:
        accepted = directory / "run-spec" / "accepted-w3.json"
        if accepted.is_file():
            w3 = _read_json(accepted)
    if not w2:
        w3_parent = w3.get("parent_w2")
        if isinstance(w3_parent, Mapping):
            w2 = _plain(w3_parent)
        elif "parent_w2_run_id" in w3:
            w2 = {
                "run_id": w3.get("parent_w2_run_id"),
                "profile_sha256": w3.get("parent_w2_profile_sha256"),
                "contract_root_sha256": w3.get("parent_w2_contract_root_sha256"),
            }
    certificate = _read_json(directory / "certificate" / "certificate-root.json")
    extension = _read_json(directory / "certificate" / "extension-0001.json")
    return {
        "schema": PARENT_IDENTITY_SCHEMA,
        "run_id": str(index.get("run_id", directory.name)),
        "index_sha256": _sha((directory / "index.json").read_bytes()),
        "status": index.get("status"),
        "source_identity_sha256": identity.get("source_identity_sha256"),
        "w3_profile_sha256": index.get("w3_profile_sha256", index.get("profile_sha256")),
        "w3_identity": w3,
        "w2_identity": w2,
        "numerical_certificate_sha256": certificate.get("self_sha256", index.get("numerical_certificate_sha256")),
        "certificate_extension_sha256": extension.get("self_sha256", index.get("certificate_extension_sha256")),
        "receipt_identities": {
            "candidate_sha256": index.get("candidate_sha256"),
            "status_sha256": index.get("status_sha256"),
            "numerical_certificate_sha256": index.get("numerical_certificate_sha256"),
            "certificate_extension_sha256": index.get("certificate_extension_sha256"),
        },
        "certificate_chain_id": certificate.get("certificate_chain_id"),
        "independent_verification": {
            str(key): _plain(value)
            for key, value in verification.items()
            if key not in {"root", "artifact", "path", "absolute_path"}
        },
    }


def _discover_w3n(geometry: Any, transport: Any) -> tuple[Path, dict[str, Any]]:
    root = _root(W3N_ROOT_NAME)
    if not root.is_dir():
        raise CarrierArtifactError(f"current W3N artifact root is missing: {root}")
    candidates: list[tuple[Path, dict[str, Any]]] = []
    try:
        from verify_cassi_qi_numerical_certificate import verify_artifact as verify_w3n_artifact
    except Exception as exc:
        raise CarrierArtifactError("independent W3N verifier is unavailable") from exc
    for directory in sorted(root.iterdir(), key=lambda item: item.name.encode("utf-8")):
        if not directory.is_dir() or directory.name.startswith(".") or not (directory / "index.json").is_file():
            continue
        try:
            index = _read_json(directory / "index.json")
            if index.get("schema") != W3N_INDEX_SCHEMA or index.get("status") != W3N_STATUS:
                continue
            profile_identity = index.get("w3_profile_sha256", index.get("profile_sha256"))
            if profile_identity != transport.profile_sha256:
                continue
            identity = _read_json(directory / "run-spec" / "source-identity.json")
            if index.get("run_id") != directory.name:
                continue
            if index.get("contract_root_sha256") != transport.contract_root_sha256:
                continue
            semantic_identity = index.get("transport_semantic_sha256", index.get("semantic_sha256"))
            if semantic_identity != transport.transport_semantic_sha256:
                continue
            if identity.get("schema") not in {SOURCE_IDENTITY_SCHEMA, "cassi.qi-flow-w3n-periodic-fft2-source-identity.v1"}:
                continue
            if not _source_rows_are_current(identity):
                continue
            if index.get("source_identity_sha256") != identity.get("source_identity_sha256"):
                continue
            verification = verify_w3n_artifact(directory)
            if not isinstance(verification, Mapping) or verification.get("status") not in {W3N_STATUS, "PASS"}:
                continue
            parent = _candidate_identity(directory, index, verification)
            w3 = parent.get("w3_identity", {})
            w2 = parent.get("w2_identity", {})
            if not isinstance(w3, Mapping) or not w3 or not isinstance(w2, Mapping) or not w2:
                continue
            if w3.get("profile_sha256") not in {None, transport.profile_sha256}:
                continue
            if w2.get("profile_sha256") not in {None, geometry.profile_sha256}:
                continue
            candidates.append((directory, parent))
        except Exception:
            # A malformed, stale, or independently rejected candidate is not
            # evidence.  It is filtered before the exact-one decision.
            continue
    if len(candidates) != 1:
        raise CarrierArtifactError(f"expected exactly one current source-exact W3N parent, found {len(candidates)}")
    return candidates[0]


def _load_parent_chain(parent_root: Path, parent: Mapping[str, Any]) -> dict[str, Any]:
    index = _read_json(parent_root / "index.json")
    w3 = dict(parent.get("w3_identity", {}))
    w2 = dict(parent.get("w2_identity", {}))
    w3_run = w3.get("run_id") or w3.get("parent_w3_run_id")
    w2_run = w2.get("run_id") or w3.get("parent_w2_run_id")
    w3_root = _root(W3_ROOT_NAME) / str(w3_run) if w3_run else None
    w2_root = _root(W2_ROOT_NAME) / str(w2_run) if w2_run else None
    if w3_root is not None and (w3_root / "index.json").is_file():
        w3_index_raw = (w3_root / "index.json").read_bytes()
        if w3.get("index_sha256") and _sha(w3_index_raw) != w3["index_sha256"]:
            raise CarrierArtifactError("W3 identity index hash mismatch")
        w3_index = _read_json(w3_root / "index.json")
        if not w2 and isinstance(w3_index.get("parents"), Mapping):
            w2 = _plain(w3_index["parents"].get("w2", {}))
        if not w2:
            w2 = {
                "run_id": w3_index.get("parent_w2_run_id"),
                "index_sha256": w3_index.get("parent_w2_index_sha256"),
                "profile_sha256": w3_index.get("parent_w2_profile_sha256"),
                "contract_root_sha256": w3_index.get("parent_w2_contract_root_sha256"),
            }
    if w2_root is not None and (w2_root / "index.json").is_file():
        w2_index_raw = (w2_root / "index.json").read_bytes()
        if w2.get("index_sha256") and _sha(w2_index_raw) != w2["index_sha256"]:
            raise CarrierArtifactError("W2 identity index hash mismatch")
    return {
        "w3n_index": index,
        "w3_identity": w3,
        "w2_identity": w2,
        "w3_run_id": str(w3_run) if w3_run else None,
        "w2_run_id": str(w2_run) if w2_run else None,
        "w3_root_name": W3_ROOT_NAME,
        "w2_root_name": W2_ROOT_NAME,
    }


def _state_hash(state: QiFlowStateV3) -> str:
    raw = raw_state_bytes_from_field(state.field)
    domain = RAW_STATE_DOMAIN.encode("utf-8")
    digest = hashlib.sha256()
    digest.update(len(domain).to_bytes(8, "big"))
    digest.update(domain)
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)
    return digest.hexdigest()


def _raw_fixture_hash(raw: bytes) -> str:
    return canonical_hash(
        {"schema": RAW_FIXTURE_DOMAIN, "raw_sha256": _sha(raw), "raw_byte_count": len(raw)},
        RAW_FIXTURE_DOMAIN,
    )


def _state_from_dc(
    *,
    geometry: Any,
    profile: Any,
    d: Sequence[torch.Tensor],
    c: Sequence[torch.Tensor],
    vd: Sequence[torch.Tensor] | None = None,
    vc: Sequence[torch.Tensor] | None = None,
) -> QiFlowStateV3:
    layout = _field_layout(geometry)
    batch = int(d[0].shape[-1])
    if any(tuple(value.shape) != (layout["mode_count"], batch) for value in (*d, *c)):
        raise CarrierArtifactError("D/C control arrays do not match the validated packed layout")
    if vd is None:
        vd = tuple(torch.zeros_like(value) for value in d)
    if vc is None:
        vc = tuple(torch.zeros_like(value) for value in c)
    base = QiFlowStateV3.create(geometry.base_profile, batch_lanes=batch)
    field = base.field.clone()
    modes = layout["mode_count"]
    component_index = {name: index for index, name in enumerate(layout["component_order"])}
    for scale in range(layout["scale_count"]):
        ey = profile.w_d * d[scale] + profile.phi * c[scale]
        ei = c[scale] - profile.phi * profile.w_d * d[scale]
        vy = profile.w_d * vd[scale] + profile.phi * vc[scale]
        vi = vc[scale] - profile.phi * profile.w_d * vd[scale]
        for name, value in (
            ("Y_re", ey.real),
            ("Y_im", ey.imag),
            ("I_re", ei.real),
            ("I_im", ei.imag),
            ("VY_re", vy.real),
            ("VY_im", vy.imag),
            ("VI_re", vi.real),
            ("VI_im", vi.imag),
        ):
            component = component_index[name]
            field[scale, component * modes : (component + 1) * modes, :] = value.contiguous()
        epsilon_component = component_index["epsilon2_ema"]
        field[scale, epsilon_component * modes : (epsilon_component + 1) * modes, :] = 0.0
    state = QiFlowStateV3(field.contiguous())
    state.validate(geometry.base_profile)
    return state


def _patterns(geometry: Any, profile: Any, batch: int) -> dict[str, QiFlowStateV3]:
    layout = _field_layout(geometry)
    scales = layout["scale_count"]
    modes = layout["mode_count"]
    active = torch.tensor(layout["active_site_counts"], dtype=torch.int64).view(scales, 1, 1)
    mode = torch.arange(modes, dtype=torch.int64).view(1, modes, 1)
    scale = torch.arange(scales, dtype=torch.float64).view(scales, 1, 1)
    lane = torch.arange(batch, dtype=torch.float64).view(1, 1, batch)
    mask = (mode < active).to(torch.float64)
    amplitude = 2.0e-4 * (1.0 + 0.11 * scale) * (1.0 + 0.07 * lane)
    phase_d = 0.17 * (mode.to(torch.float64) + 1.0) + 0.23 * scale + 0.19 * lane
    phase_c = 0.31 * (mode.to(torch.float64) + 1.0) - 0.13 * scale + 0.29 * lane
    d_structured = (amplitude * torch.exp(1j * phase_d) * mask).to(torch.complex128)
    c_structured = (0.83 * amplitude * torch.exp(1j * phase_c) * mask).to(torch.complex128)
    d_uniform = (2.0e-4 * mask.expand(-1, -1, batch)).to(torch.complex128)
    c_uniform = (1.5e-4 * mask.expand(-1, -1, batch)).to(torch.complex128)
    zeros = torch.zeros((scales, modes, batch), dtype=torch.complex128)
    d_local = torch.zeros_like(d_structured)
    c_local = torch.zeros_like(c_structured)
    slow_scale = int(geometry.base_profile.payload["retention"]["slow_scale"])
    if slow_scale < 0 or slow_scale >= scales:
        raise CarrierArtifactError("validated active sheet is outside the scale range")
    d_local[slow_scale] = d_structured[slow_scale]
    c_local[slow_scale] = c_structured[slow_scale]
    return {
        "D-only": _state_from_dc(geometry=geometry, profile=profile, d=tuple(d_uniform), c=tuple(zeros)),
        "C-only": _state_from_dc(geometry=geometry, profile=profile, d=tuple(zeros), c=tuple(c_uniform)),
        "D+C": _state_from_dc(geometry=geometry, profile=profile, d=tuple(d_structured), c=tuple(c_structured)),
        "zero": _state_from_dc(geometry=geometry, profile=profile, d=tuple(zeros), c=tuple(zeros)),
        "uniform": _state_from_dc(geometry=geometry, profile=profile, d=tuple(d_uniform), c=tuple(c_uniform)),
        "structured": _state_from_dc(geometry=geometry, profile=profile, d=tuple(d_structured), c=tuple(c_structured)),
        "scale-local": _state_from_dc(geometry=geometry, profile=profile, d=tuple(d_local), c=tuple(c_local)),
    }


def _broadcast_state(state: QiFlowStateV3, geometry: Any, batch: int) -> QiFlowStateV3:
    if int(state.field.shape[-1]) == batch:
        return state
    if int(state.field.shape[-1]) != 1:
        raise CarrierArtifactError("only a one-lane fixture may be broadcast")
    field = state.field.expand(-1, -1, batch).clone().contiguous()
    result = QiFlowStateV3(field)
    result.validate(geometry.base_profile)
    return result


def _json_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    value = _plain(receipt)
    try:
        canonical_json_bytes(value)
    except Exception as exc:
        raise CarrierArtifactError("carrier receipt is not canonical JSON material") from exc
    return value


def _state_metadata(state: QiFlowStateV3, geometry: Any, *, name: str, path: str, raw: bytes) -> dict[str, Any]:
    layout = _field_layout(geometry)
    metadata: dict[str, Any] = {
        "schema": STATE_METADATA_SCHEMA,
        "name": name,
        "path": path,
        "shape": [int(value) for value in state.field.shape],
        "shape_formula": "[S,9M,B]",
        "dtype": "float64",
        "endianness": "little",
        "byte_order": "little",
        "layout_id": layout["layout_id"],
        "scale_count": layout["scale_count"],
        "mode_count": layout["mode_count"],
        "component_count": layout["component_count"],
        "active_shapes": layout["active_shapes"],
        "active_site_counts": layout["active_site_counts"],
        "batch_lanes": int(state.field.shape[-1]),
        "bytes": len(raw),
        "byte_count": len(raw),
        "sha256": _sha(raw),
        "raw_sha256": _sha(raw),
        "raw_fixture_sha256": _raw_fixture_hash(raw),
        "state_sha256": _state_hash(state),
    }
    try:
        identity = state.identity_metadata(geometry.base_profile)
        metadata["state_contract_sha256"] = identity.get("state_contract_sha256")
        metadata["profile_sha256"] = identity.get("profile_sha256")
        metadata["contract_root_sha256"] = identity.get("contract_root_sha256")
        metadata["execution_schedule_sha256"] = identity.get("execution_schedule_sha256")
        metadata["topology_sha256"] = identity.get("topology_sha256")
        metadata["source_identity_sha256"] = identity.get("source_identity_sha256")
    except Exception:
        pass
    return metadata


def _store_state(stage: Path, state: QiFlowStateV3, geometry: Any, *, name: str, states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    raw = raw_state_bytes_from_field(state.field)
    state_sha = _state_hash(state)
    relative = f"fixtures/{state_sha}.f64le"
    path = stage / relative
    if path.exists() and path.read_bytes() != raw:
        raise CarrierArtifactError(f"content-addressed state collision: {state_sha}")
    if not path.exists():
        _write(stage, relative, raw)
    metadata = _state_metadata(state, geometry, name=name, path=relative, raw=raw)
    existing = states.get(state_sha)
    if existing is not None and existing["sha256"] != metadata["sha256"]:
        raise CarrierArtifactError("state metadata identity collision")
    states[state_sha] = metadata
    _write_json(stage, f"fixtures/{state_sha}.json", metadata)
    return metadata


def _control_ledger(receipt: Mapping[str, Any], profile: Any) -> dict[str, Any]:
    composition = receipt.get("composition", {})
    base_pre = _number(composition.get("base_energy_pre", 0.0))
    base_post = _number(composition.get("base_energy_post", base_pre))
    u_pre = _number(composition.get("U_pre", 0.0))
    u_d = _number(composition.get("U_D_path", u_pre))
    u_c = _number(composition.get("U_C_path", composition.get("U_post", u_d)))
    u_post = _number(composition.get("U_post", u_c))
    return {
        "schema": "cassi.qi-flow-w4-periodic-fft2-ledger.v1",
        "U_D": u_d,
        "U_C": u_c,
        "U_comp": u_post,
        "U_total": base_post + u_post,
        "U_comp_pre": u_pre,
        "U_comp_post": u_post,
        "metric_gradient_work": {
            "W_D": _number(composition.get("W_D", 0.0)),
            "W_center": _number(composition.get("W_center", 0.0)),
            "W_C": _number(composition.get("W_C", 0.0)),
            "Delta_U_comp": _number(composition.get("Delta_U", u_post - u_pre)),
            "coordinate_work_closure": _number(composition.get("coordinate_work_closure", 0.0)),
            "registered_coordinate_work_bound": _number(composition.get("registered_coordinate_work_bound", 0.0)),
            "total_coupled_closure": _number(composition.get("total_coupled_closure", 0.0)),
            "registered_total_coupled_integrator_bound": _number(composition.get("registered_total_coupled_integrator_bound", 0.0)),
            "force_D_sum_re": _number(composition.get("force_D_sum_re", 0.0)),
            "force_C_sum_re": _number(composition.get("force_C_sum_re", 0.0)),
        },
        "per_scale_U_pre": [_number(value) for value in composition.get("per_scale_U_pre", [])],
        "per_scale_U_post": [_number(value) for value in composition.get("per_scale_U_post", [])],
    }


def _epsilon_summary(state: QiFlowStateV3, geometry: Any, profile: Any) -> dict[str, Any]:
    _, _, epsilons, potentials = composition_forces(state, geometry=geometry, profile=profile)
    rows: list[dict[str, Any]] = []
    for scale, epsilon in enumerate(epsilons):
        rows.append(
            {
                "scale": scale,
                "batch_lanes": int(epsilon.shape[-1]),
                "epsilon_min": float(epsilon.min().item()),
                "epsilon_max": float(epsilon.max().item()),
                "epsilon_sum": float(epsilon.sum().item()),
                "potential": float(potentials[scale]),
            }
        )
    return {"per_scale": rows}

def _reversal_observations(geometry: Any, profile: Any, states: Mapping[str, QiFlowStateV3]) -> dict[str, Any]:
    observations: dict[str, Any] = {}
    for name, state in states.items():
        values = carrier_coordinates(state, geometry=geometry, profile=profile)
        _, _, epsilons, _ = composition_forces(state, geometry=geometry, profile=profile)
        observations[name] = {
            "position_density": [
                float((ey.abs().square() + ei.abs().square()).real.mean().item())
                for ey, ei in zip(values.ey, values.ei, strict=True)
            ],
            "epsilon": [float(epsilon.real.mean().item()) for epsilon in epsilons],
            "velocity_max_abs": max(
                [float(value.abs().amax().item()) for value in (*values.vd, *values.vc)] or [0.0]
            ),
            "full_energy": float(carrier_total_energy(state, geometry=geometry, profile=profile)),
        }
    minus = observations["minus"]
    plus = observations["plus"]
    if minus["velocity_max_abs"] != 0.0 or plus["velocity_max_abs"] != 0.0:
        raise CarrierArtifactError("composition-reversal-v1 fixture must have zero initial velocity")
    if any(abs(a - b) > 1.0e-10 * max(1.0, abs(a), abs(b)) for a, b in zip(minus["position_density"], plus["position_density"], strict=True)):
        raise CarrierArtifactError("composition-reversal-v1 position density is not identical")
    if abs(minus["full_energy"] - plus["full_energy"]) > 1.0e-10 * max(1.0, abs(minus["full_energy"]), abs(plus["full_energy"])):
        raise CarrierArtifactError("composition-reversal-v1 full energy is not identical")
    if not all(a * b < 0.0 for a, b in zip(minus["epsilon"], plus["epsilon"], strict=True)):
        raise CarrierArtifactError("composition-reversal-v1 epsilon is not opposite")
    return observations

def _control_result(
    *,
    stage: Path,
    name: str,
    batch: int,
    state: QiFlowStateV3,
    geometry: Any,
    transport: Any,
    profile: Any,
    certificate: Mapping[str, Any],
    potential: bool,
    states: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if int(state.field.shape[-1]) != batch:
        raise CarrierArtifactError(f"control {name} batch label does not match state lanes")
    predecessor_meta = _store_state(stage, state, geometry, name=f"{name}:batch-{batch}:predecessor", states=states)
    step = transition_v4_carrier(
        state,
        geometry_profile=geometry,
        transport_profile=transport,
        carrier_profile=profile,
        numerical_certificate=certificate,
        potential_enabled=potential,
    )
    if not step.committable or step.candidate is None:
        raise CarrierArtifactError(f"control {name} batch {batch} rejected: {step.failure_reason}")
    candidate = step.candidate
    candidate_meta = _store_state(stage, candidate, geometry, name=f"{name}:batch-{batch}:candidate", states=states)
    receipt = _json_receipt(step.receipt)
    if receipt.get("candidate_state_sha256") != candidate_meta["state_sha256"]:
        raise CarrierArtifactError(f"control {name} receipt/candidate state identity mismatch")
    if receipt.get("predecessor_state_sha256") != predecessor_meta["state_sha256"]:
        raise CarrierArtifactError(f"control {name} receipt/predecessor state identity mismatch")
    result: dict[str, Any] = {
        "schema": CONTROL_SCHEMA,
        "name": name,
        "batch_lanes": batch,
        "potential_enabled": potential,
        "predecessor": predecessor_meta,
        "candidate": candidate_meta,
        "predecessor_raw_sha256": predecessor_meta["raw_sha256"],
        "candidate_raw_sha256": candidate_meta["raw_sha256"],
        "predecessor_state_sha256": predecessor_meta["state_sha256"],
        "candidate_state_sha256": candidate_meta["state_sha256"],
        "receipt": receipt,
        "receipt_path": _control_path(name, batch),
        "receipt_sha256": receipt.get("self_sha256"),
        "ledger": _control_ledger(receipt, profile),
        "epsilon": _epsilon_summary(state, geometry, profile),
        "candidate_epsilon": _epsilon_summary(candidate, geometry, profile),
        "candidate_energy": carrier_total_energy(candidate, geometry=geometry, profile=profile),
    }
    return result


def _control_path(name: str, batch: int) -> str:
    safe = name.replace("+", "-plus-").replace("/", "-").replace(" ", "-")
    return f"gates/g04-carrier/controls/{safe}/batch-{batch}.json"
def _compact_control_index(stage: Path, controls: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    compact: dict[str, dict[str, Any]] = {}
    for name in CONTROL_IDS:
        row = controls.get(name)
        if not isinstance(row, Mapping):
            raise CarrierArtifactError(f"control {name} is missing before compact indexing")
        batches = row.get("batches")
        if not isinstance(batches, Mapping) or not batches:
            raise CarrierArtifactError(f"control {name} has no detailed batches before compact indexing")
        first = batches.get("1")
        if not isinstance(first, Mapping):
            raise CarrierArtifactError(f"control {name} has no batch-1 detail before compact indexing")
        batch_lanes = row.get("batch_lanes")
        if not isinstance(batch_lanes, list) or any(isinstance(value, bool) or not isinstance(value, int) for value in batch_lanes):
            raise CarrierArtifactError(f"control {name} has invalid aggregate batch lanes")
        batch_index: dict[str, dict[str, str]] = {}
        for batch_name in sorted((str(value) for value in batches), key=int):
            detail = batches.get(batch_name)
            if not isinstance(detail, Mapping):
                raise CarrierArtifactError(f"control {name} batch {batch_name} detail is malformed")
            relative = detail.get("receipt_path")
            if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise CarrierArtifactError(f"control {name} batch {batch_name} detail path is invalid")
            detail_path = stage / relative
            if not detail_path.is_file():
                raise CarrierArtifactError(f"control {name} batch {batch_name} detail file is missing")
            batch_index[batch_name] = {"path": relative, "sha256": _sha(detail_path.read_bytes())}
        compact[name] = {
            "schema": row.get("schema", CONTROL_SCHEMA),
            "name": row.get("name", name),
            "batch_lanes": list(batch_lanes),
            "potential_enabled": first.get("potential_enabled"),
            "batch_index": batch_index,
        }
    return compact




def _recompute_ledger_components(composition: Mapping[str, Any]) -> dict[str, float]:
    u_pre = _number(composition.get("U_pre", 0.0))
    u_d_path = _number(composition.get("U_D_path", u_pre))
    u_post = _number(composition.get("U_post", 0.0))
    delta_u = u_post - u_pre
    base_energy_post = _number(composition.get("base_energy_post", 0.0))
    base_energy_pre = _number(composition.get("base_energy_pre", 0.0))
    return {
        "coordinate_work_closure": -(u_d_path - u_pre) - (u_post - u_d_path) + delta_u,
        "wave_energy_delta": base_energy_post - base_energy_pre,
        "total_coupled_closure": base_energy_post - base_energy_pre + delta_u,
    }


def _negative_ledger_control(result: Mapping[str, Any]) -> dict[str, Any]:
    receipt = copy.deepcopy(dict(result["receipt"]))
    composition = receipt["composition"]
    mutation = 1.0
    composition["wave_energy_delta"] = _number(composition.get("wave_energy_delta", 0.0)) + mutation
    composition["total_coupled_closure"] = _number(composition.get("total_coupled_closure", 0.0)) + mutation
    receipt.pop("self_sha256", None)
    receipt["self_sha256"] = canonical_hash(receipt, W4_CARRIER_RECEIPT_DOMAIN)
    recomputed = _recompute_ledger_components(composition)
    return {
        "schema": "cassi.qi-flow-w4-periodic-fft2-negative-control.v1",
        "control_id": "coherent-wave-total-ledger-mutation",
        "expected_decision": "REJECT",
        "source_control": result["name"],
        "mutation": {"wave_energy_delta_add": mutation, "total_coupled_closure_add": mutation},
        "mutated_receipt": receipt,
        "raw_component_recomputation": recomputed,
        "rejection_reason": "coherent-wave-total-ledger-mutation",
    }


def _build_extension(
    *, parent_root: Mapping[str, Any], parent_extension: Mapping[str, Any], derivation: Mapping[str, Any], section: Mapping[str, Any], parent: Mapping[str, Any]
) -> dict[str, Any]:
    inventory = parent_extension.get("complete_section_inventory")
    if not isinstance(inventory, list):
        inventory = [parent_extension["added_section"]]
    body: dict[str, Any] = {
        "schema": CERTIFICATE_EXTENSION_SCHEMA,
        "source_extension_schema": "cassi.qi-flow-certificate-extension.v1",
        "certificate_chain_id": parent_root.get("certificate_chain_id"),
        "chain_ordinal": int(parent_extension.get("chain_ordinal", 1)) + 1,
        "parent_certificate_sha256": parent_extension["self_sha256"],
        "parent_section_inventory": inventory,
        "owning_package": "W4",
        "gate": "G4",
        "consumed_semantic_subhashes": _plain(parent_extension.get("consumed_semantic_subhashes", [])),
        "accepted_w3n_identity": _plain(parent),
        "composition_derivation_sha256": derivation["self_sha256"],
        "added_section": _plain(section),
        "complete_section_inventory": [*inventory, _plain(section)],
        "chain_status": "final",
    }
    extension = dict(body)
    extension["final_certificate_identity_sha256"] = canonical_hash(body, CERTIFICATE_EXTENSION_SCHEMA)
    extension["self_sha256"] = canonical_hash(extension, CERTIFICATE_EXTENSION_SCHEMA)
    return extension


def _combined_schedule(transport: Any) -> dict[str, Any]:
    duration = float(transport.pinned_parameters.h)
    transport_schedule = _plain(w3_stage_schedule(duration))
    stages = transport_schedule.get("stages")
    if not isinstance(stages, list) or len(stages) != 7:
        raise CarrierArtifactError("validated W3 schedule is not exactly seven stages")
    combined_stages = []
    for row in stages:
        stage = dict(row)
        stage["coordinate_system"] = ["D", "C", "V_D", "V_C"]
        stage["operator_family"] = "periodic-fft2.v1"
        stage["composition_mode"] = "reciprocal-metric-gradient-pair"
        combined_stages.append(stage)
    body = {
        "schema": STAGE_SCHEDULE_SCHEMA,
        "family": "combined-dc-symmetric-seven-stage.v2",
        "h_s": transport_schedule["h_s"],
        "substeps": 7,
        "transport_schedule": transport_schedule,
        "transport_schedule_sha256": canonical_hash(transport_schedule, transport_schedule["schema"]),
        "stages": combined_stages,
        "coordinates": {"position": ["D", "C"], "velocity": ["V_D", "V_C"]},
        "damping": "D-and-C-analytic-fft2-exactly-once-per-half.v1",
        "projection": "none;sole-packed-field-write.v1",
    }
    body["self_sha256"] = canonical_hash(body, STAGE_SCHEDULE_SCHEMA)
    return body


def _source_identity(stage: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for relative in SOURCE_PATHS:
        source = ROOT / relative
        if not source.is_file():
            raise CarrierArtifactError(f"required W4 source is missing: {relative}")
        raw = source.read_bytes()
        _write(stage, f"sources/{relative}", raw)
        rows.append({"path": relative, "bytes": len(raw), "sha256": _sha(raw)})
    body = {"schema": SOURCE_IDENTITY_SCHEMA, "sources": rows}
    return {**body, "source_identity_sha256": canonical_hash(body, SOURCE_IDENTITY_SCHEMA)}


def _objects(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file() and item.name not in {"index.json", "manifest.json"}),
        key=lambda item: item.relative_to(root).as_posix().encode("utf-8"),
    ):
        raw = path.read_bytes()
        rows.append({"path": path.relative_to(root).as_posix(), "bytes": len(raw), "sha256": _sha(raw)})
    return rows


def _run(*, output_root: str | Path | None = None) -> Path:
    base_profile = load_development_profile()
    geometry = load_w2_geometry_profile(base_profile=base_profile)
    transport = load_w3_transport_profile(geometry=geometry)
    parent_root, parent = _discover_w3n(geometry, transport)
    chain = _load_parent_chain(parent_root, parent)
    parent = dict(parent)
    parent["w3_identity"] = chain["w3_identity"]
    parent["w2_identity"] = chain["w2_identity"]
    parent_index = chain["w3n_index"]
    parent_certificate = _read_json(parent_root / "certificate" / "certificate-root.json")
    parent_extension = _read_json(parent_root / "certificate" / "extension-0001.json")
    if parent.get("numerical_certificate_sha256") != parent_certificate.get("self_sha256"):
        raise CarrierArtifactError("W3N parent certificate identity mismatch")
    if parent.get("certificate_extension_sha256") != parent_extension.get("self_sha256"):
        raise CarrierArtifactError("W3N parent extension identity mismatch")
    if parent.get("w3_profile_sha256") not in {None, transport.profile_sha256}:
        raise CarrierArtifactError("W3N parent transport profile is not current")

    profile = load_w4_carrier_profile(geometry=geometry, transport=transport)
    derivation = build_composition_derivation(carrier_profile=profile, numerical_certificate=parent_certificate)
    section = build_composition_section(carrier_profile=profile, derivation=derivation)
    extension = _build_extension(parent_root=parent_certificate, parent_extension=parent_extension, derivation=derivation, section=section, parent=parent)
    schedule = _combined_schedule(transport)
    layout = _field_layout(geometry)
    retention = _plain(geometry.base_profile.payload.get("retention", {}))
    edge_registry = retention.get("edge_registry")
    cycle_registry = retention.get("cycle_registry")
    if not isinstance(edge_registry, Mapping) or not isinstance(cycle_registry, Mapping):
        raise CarrierArtifactError("validated W2 profile omits edge/cycle registries")
    layout["topology"] = {
        "active_sheet": int(retention["slow_scale"]),
        "edge_registry": edge_registry,
        "cycle_registry": cycle_registry,
        "edge_registry_sha256": retention.get("edge_registry_sha256"),
        "cycle_registry_sha256": retention.get("cycle_registry_sha256"),
    }
    schedule.pop("self_sha256", None)
    schedule["scale_count"] = layout["scale_count"]
    schedule["active_sheet"] = layout["topology"]["active_sheet"]
    schedule["self_sha256"] = canonical_hash(schedule, STAGE_SCHEDULE_SCHEMA)
    fixture = composition_reversal_fixture(geometry=geometry, profile=profile)
    if fixture.get("fixture_id") != "composition-reversal-v1":
        raise CarrierArtifactError("composition reversal fixture identity mismatch")

    root = Path(output_root).resolve() if output_root is not None else _root(W4_ROOT_NAME)
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".w4-periodic-fft2-", dir=root))
    states: dict[str, dict[str, Any]] = {}
    try:
        source_identity = _source_identity(stage)
        _write_json(stage, "run-spec/source-identity.json", source_identity)
        _write_json(stage, "run-spec/parent-w3n.json", parent)
        _write_json(stage, "run-spec/w3n-index.json", parent_index)
        _write_json(stage, "run-spec/w3-w2-lineage.json", chain)
        _write_json(stage, "certificate/g3n-certificate-root.json", parent_certificate)
        _write_json(stage, "certificate/g3n-extension-0001.json", parent_extension)
        _write_json(stage, "certificate/composition-derivation.json", derivation)
        _write_json(stage, "certificate/composition-section.json", section)
        _write_json(stage, "certificate/certificate-root.json", parent_certificate)
        _write_json(stage, "certificate/extension-0001.json", parent_extension)
        _write_json(stage, "certificate/extension-0002.json", extension)
        _write_json(stage, "certificate/w4-extension.json", extension)
        _write_json(stage, "profile/carrier-profile.json", _plain(profile.payload))
        _write_json(stage, "profile/carrier-root.json", _plain(profile.root))
        profile_binding = {
            "schema": PROFILE_BINDING_SCHEMA,
            "carrier_profile_sha256": profile.profile_sha256,
            "carrier_root_sha256": profile.root_sha256,
            "w2_identity": _plain(parent.get("w2_identity", {})),
            "w3_identity": _plain(parent.get("w3_identity", {})),
            "w3n_identity": _plain(parent),
            "state_layout": layout,
            "immutable": True,
        }
        profile_binding["self_sha256"] = canonical_hash(profile_binding, PROFILE_BINDING_SCHEMA)
        _write_json(stage, "run-spec/w4-profile.json", profile_binding)
        _write_json(stage, "run-spec/w4-stage-schedule.json", schedule)

        patterns_by_batch = {batch: _patterns(geometry, profile, batch) for batch in range(1, layout["batch_limit"] + 1)}
        controls: dict[str, dict[str, Any]] = {}
        references: dict[str, Any] = {}
        for name in ("D-only", "C-only", "D+C", "zero", "uniform", "structured", "scale-local"):
            batches: dict[str, Any] = {}
            for batch, pattern in patterns_by_batch.items():
                state = pattern[name]
                result = _control_result(
                    stage=stage,
                    name=name,
                    batch=batch,
                    state=state,
                    geometry=geometry,
                    transport=transport,
                    profile=profile,
                    certificate=parent_certificate,
                    potential=True,
                    states=states,
                )
                batches[str(batch)] = result
                _write_json(stage, _control_path(name, batch), result)
            controls[name] = {
                **batches["1"],
                "schema": CONTROL_SCHEMA,
                "name": name,
                "batch_lanes": list(range(1, layout["batch_limit"] + 1)),
                "batches": batches,
            }

        dc_by_batch = {batch: patterns_by_batch[batch]["D+C"] for batch in patterns_by_batch}
        for name, potential in (("potential-off", False), ("structured", True)):
            if name == "structured":
                continue
            batches = {}
            for batch, state in dc_by_batch.items():
                if name == "potential-off":
                    reference_step = transition_v4_carrier(
                        state,
                        geometry_profile=geometry,
                        transport_profile=transport,
                        carrier_profile=profile,
                        numerical_certificate=parent_certificate,
                        potential_enabled=False,
                    )
                    if not reference_step.committable or reference_step.candidate is None:
                        raise CarrierArtifactError(f"uncoupled D+C reference rejected for batch {batch}")
                    reference_raw = raw_state_bytes_from_field(reference_step.candidate.field)
                    reference_state_meta = _store_state(
                        stage,
                        reference_step.candidate,
                        geometry,
                        name=f"potential-off:batch-{batch}:uncoupled-dc-reference",
                        states=states,
                    )
                    reference_receipt = _json_receipt(reference_step.receipt)
                    references[str(batch)] = {
                        "schema": "cassi.qi-flow-w4-periodic-fft2-uncoupled-dc-reference.v1",
                        "kind": "uncoupled-combined-dc-reference-v1",
                        "batch_lanes": batch,
                        "state": reference_state_meta,
                        "raw_sha256": _sha(reference_raw),
                        "state_sha256": reference_state_meta["state_sha256"],
                        "receipt": reference_receipt,
                        "receipt_sha256": reference_receipt.get("self_sha256"),
                    }
                result = _control_result(
                    stage=stage,
                    name=name,
                    batch=batch,
                    state=state,
                    geometry=geometry,
                    transport=transport,
                    profile=profile,
                    certificate=parent_certificate,
                    potential=potential,
                    states=states,
                )
                if name == "potential-off":
                    reference = references[str(batch)]
                    if result["candidate_raw_sha256"] != reference["raw_sha256"]:
                        raise CarrierArtifactError("potential-off differs from the uncoupled combined D+C reference")
                    if "combined-dc" not in str(result["receipt"].get("split", "")):
                        raise CarrierArtifactError("potential-off was reduced to the old W3 path")
                    result["uncoupled_reference"] = reference
                batches[str(batch)] = result
                _write_json(stage, _control_path(name, batch), result)
            controls[name] = {
                **batches["1"],
                "schema": CONTROL_SCHEMA,
                "name": name,
                "batch_lanes": list(range(1, layout["batch_limit"] + 1)),
                "batches": batches,
            }

        fixture_states = {"imbalance-plus": fixture["plus"], "imbalance-minus": fixture["minus"]}
        fixture_controls: dict[str, Any] = {}
        for name, fixture_state in fixture_states.items():
            batches = {}
            for batch in range(1, layout["batch_limit"] + 1):
                state = _broadcast_state(fixture_state, geometry, batch)
                result = _control_result(
                    stage=stage,
                    name=name,
                    batch=batch,
                    state=state,
                    geometry=geometry,
                    transport=transport,
                    profile=profile,
                    certificate=parent_certificate,
                    potential=True,
                    states=states,
                )
                batches[str(batch)] = result
                _write_json(stage, _control_path(name, batch), result)
            fixture_controls[name] = {
                **batches["1"],
                "schema": CONTROL_SCHEMA,
                "name": name,
                "batch_lanes": list(range(1, layout["batch_limit"] + 1)),
                "batches": batches,
            }
        controls.update(fixture_controls)

        transformed: dict[int, dict[str, QiFlowStateV3]] = {}
        for batch in range(1, layout["batch_limit"] + 1):
            source = patterns_by_batch[batch]["D+C"]
            transformed[batch] = {
                "coordinate-negation": negate_differential_coordinate(source, geometry=geometry, profile=profile),
                "phase-current-reversal": phase_current_reversal(source, geometry=geometry),
                "yang-yin-exchange": yang_yin_exchange(source, geometry=geometry, profile=profile),
                "phase-shuffled-equal-energy": phase_shuffled_equal_energy(source, geometry=geometry),
            }
            for name, transformed_state in transformed[batch].items():
                result = _control_result(
                    stage=stage,
                    name=name,
                    batch=batch,
                    state=transformed_state,
                    geometry=geometry,
                    transport=transport,
                    profile=profile,
                    certificate=parent_certificate,
                    potential=True,
                    states=states,
                )
                controls.setdefault(name, {"schema": CONTROL_SCHEMA, "name": name, "batch_lanes": [], "batches": {}})
                controls[name]["batches"][str(batch)] = result
                controls[name]["batch_lanes"].append(batch)
                _write_json(stage, _control_path(name, batch), result)
        for name in ("coordinate-negation", "phase-current-reversal", "yang-yin-exchange", "phase-shuffled-equal-energy"):
            controls[name]["batch_lanes"] = sorted(set(controls[name]["batch_lanes"]))
            for key, value in controls[name]["batches"]["1"].items():
                if key != "batch_lanes":
                    controls[name][key] = value

        # The exact fixture is retained as raw evidence, independently of the
        # per-batch steering controls above.
        reversal = _plain({key: value for key, value in fixture.items() if key not in {"minus", "plus"}})
        reversal["raw_state_sha256"] = {}
        reversal["full_energy"] = _plain(fixture["full_energy"])
        reversal["position_energy"] = _plain(fixture["position_energy"])
        reversal["observations"] = _reversal_observations(
            geometry,
            profile,
            {"minus": fixture["minus"], "plus": fixture["plus"]},
        )
        for arm in ("minus", "plus"):
            state = fixture[arm]
            raw = raw_state_bytes_from_field(state.field)
            relative = f"fixtures/composition-reversal-v1-{arm}.f64le"
            _write(stage, relative, raw)
            reversal["raw_state_sha256"][arm] = _state_hash(state)
            reversal[f"{arm}_state"] = _store_state(stage, state, geometry, name=f"composition-reversal-v1:{arm}", states=states)
        reversal["raw_fixture_paths"] = {arm: f"fixtures/composition-reversal-v1-{arm}.f64le" for arm in ("minus", "plus")}
        reversal["velocity_max_abs"] = 0.0
        control_details = controls
        controls = _compact_control_index(stage, control_details)


        controls_core = {
            "schema": CONTROLS_SCHEMA,
            "status": "PASS",
            "control_ids": list(CONTROL_IDS),
            "batch_lanes": list(range(1, layout["batch_limit"] + 1)),
            "heterogeneous_batch": layout["batch_limit"] > 1,
            "all_scales": layout["scale_count"],
            "controls": controls,
            "control_receipt_sha256": {
                name: {batch: control_details[name]["batches"][str(batch)]["receipt_sha256"] for batch in control_details[name]["batches"]}
                for name in CONTROL_IDS
            },
            "potential_off_reference": "uncoupled-combined-dc-reference-v1",
            "composition_curvature_work_extension": {
                "derivation_sha256": derivation["self_sha256"],
                "section_sha256": section["self_sha256"],
                "curvature_abs": derivation["bounds"]["curvature_abs"],
                "coordinate_work_rounding_abs": derivation["bounds"]["coordinate_work_rounding_abs"],
                "total_coupled_integrator_abs": derivation["bounds"]["total_coupled_integrator_abs"],
            },
            "coordinate_negation_is_not_epsilon_reversal": True,
            "phase_current_reversal": "R_J",
            "yang_yin_exchange": "explicit-metric-exchange",
            "phase_shuffle_is_equal_energy_falsifier": True,
        }
        controls_receipt = {**controls_core, "self_sha256": canonical_hash(controls_core, CONTROLS_SCHEMA)}
        _write_json(stage, "gates/g04-carrier/controls.json", controls_receipt)

        negative_control = _negative_ledger_control(control_details["imbalance-plus"]["batches"]["1"])
        _write_json(stage, "gates/g04-carrier/negative-controls/coherent-wave-total-ledger-mutation.json", negative_control)

        runtime = {
            "schema": RUNTIME_SCHEMA,
            "layout": layout,
            "schedule": schedule,
            "carrier_profile_sha256": profile.profile_sha256,
            "carrier_root_sha256": profile.root_sha256,
            "w3_transport_profile_sha256": transport.profile_sha256,
            "w2_geometry_profile_sha256": geometry.profile_sha256,
            "w3n_parent_run_id": parent["run_id"],
            "controls": controls,
            "references": references,
            "states": states,
            "composition_reversal_v1": reversal,
            "no_clipping": True,
            "no_projection": True,
            "no_new_state": True,
            "raw_state_domain": RAW_STATE_DOMAIN,
        }
        runtime["self_sha256"] = canonical_hash(runtime, RUNTIME_SCHEMA)
        _write_json(stage, "results/runtime.json", runtime)

        candidate_core = {
            "schema": W4_CARRIER_CANDIDATE_SCHEMA,
            "artifact_schema": "cassi.qi-flow-w4-periodic-fft2-carrier-candidate.v1",
            "status": "PASS_W4_G4",
            "parent_w3n": parent,
            "carrier_profile_sha256": profile.profile_sha256,
            "carrier_root_sha256": profile.root_sha256,
            "composition_derivation_sha256": derivation["self_sha256"],
            "composition_section_sha256": section["self_sha256"],
            "certificate_extension_sha256": extension["self_sha256"],
            "source_identity_sha256": source_identity["source_identity_sha256"],
            "stage_schedule_sha256": schedule["self_sha256"],
            "transport_stage_schedule_sha256": schedule["transport_schedule_sha256"],
            "control_ids": list(CONTROL_IDS),
            "controls": controls,
            "controls_sha256": controls_receipt["self_sha256"],
            "runtime_sha256": runtime["self_sha256"],
            "composition_reversal_v1": reversal,
            "counterfactuals": {"potential_off_uncoupled_dc": references},
            "negative_controls": {negative_control["control_id"]: negative_control},
            "candidate_fail_before_commit": {
                "post_candidate_guard": True,
                "rejected_candidate_exposed": False,
                "clipping": False,
                "projection": False,
                "new_state": False,
                "fallback": False,
            },
        }
        candidate = {**candidate_core, "self_sha256": canonical_hash(candidate_core, W4_CARRIER_CANDIDATE_SCHEMA)}
        _write_json(stage, "gates/g04-carrier/carrier.json", candidate)
        status_core = {
            "schema": STATUS_SCHEMA,
            "gate": "G4",
            "status": "PASS_W4_G4",
            "decision": "PASS_W4_G4",
            "conditions": {
                "current_source_exact_w3n": True,
                "independent_w3n_verification": True,
                "w3_w2_lineage_retained": True,
                "seven_stage_combined_dc_schedule": schedule["substeps"] == 7,
                "all_scales": layout["scale_count"] > 0,
                "heterogeneous_batches": layout["batch_limit"] > 1,
                "potential_off_uncoupled_dc": True,
                "composition_reversal_zero_velocity": True,
                "metric_gradient_work_recorded": True,
                "raw_predecessor_candidate_states": True,
                "no_clipping_projection_new_state": True,
            },
            "candidate_sha256": candidate["self_sha256"],
            "runtime_sha256": runtime["self_sha256"],
            "source_identity_sha256": source_identity["source_identity_sha256"],
            "certificate_extension_sha256": extension["self_sha256"],
        }
        status = {**status_core, "self_sha256": canonical_hash(status_core, STATUS_SCHEMA)}
        _write_json(stage, "gates/g04-carrier/status.json", status)

        hash_graph_core = {
            "schema": HASH_GRAPH_SCHEMA,
            "nodes": {
                "w3n": {"run_id": parent["run_id"], "index_sha256": parent["index_sha256"]},
                "w3": parent.get("w3_identity", {}),
                "w2": parent.get("w2_identity", {}),
                "certificate": {"self_sha256": parent_certificate.get("self_sha256")},
                "certificate_extension_parent": {"self_sha256": parent_extension.get("self_sha256")},
                "carrier_profile": {"self_sha256": profile.profile_sha256},
                "carrier_root": {"self_sha256": profile.root_sha256},
                "composition_derivation": {"self_sha256": derivation["self_sha256"]},
                "composition_section": {"self_sha256": section["self_sha256"]},
                "certificate_extension": {"self_sha256": extension["self_sha256"]},
                "runtime": {"self_sha256": runtime["self_sha256"]},
                "candidate": {"self_sha256": candidate["self_sha256"]},
                "status": {"self_sha256": status["self_sha256"]},
            },
            "edges": [
                ["w3n", "w3"],
                ["w3", "w2"],
                ["w3n", "certificate"],
                ["certificate", "certificate_extension_parent"],
                ["carrier_profile", "carrier_root"],
                ["certificate_extension_parent", "certificate_extension"],
                ["composition_derivation", "composition_section"],
                ["certificate_extension", "candidate"],
                ["runtime", "candidate"],
                ["candidate", "status"],
            ],
            "state_object_count": len(states),
            "receipt_count": sum(len(control_details[name]["batches"]) for name in CONTROL_IDS),
        }
        hash_graph = {**hash_graph_core, "self_sha256": canonical_hash(hash_graph_core, HASH_GRAPH_SCHEMA)}
        _write_json(stage, "run-spec/hash-graph.json", hash_graph)

        objects = _objects(stage)
        manifest_core = {
            "schema": MANIFEST_SCHEMA,
            "artifact_schema": INDEX_SCHEMA,
            "object_count": len(objects),
            "objects": objects,
            "inventory_excludes": ["index.json", "manifest.json"],
            "source_identity_sha256": source_identity["source_identity_sha256"],
            "candidate_sha256": candidate["self_sha256"],
            "status_sha256": status["self_sha256"],
        }
        manifest = {**manifest_core, "self_sha256": canonical_hash(manifest_core, MANIFEST_SCHEMA)}
        _write_json(stage, "manifest.json", manifest)
        objects = _objects(stage)
        index_core = {
            "schema": INDEX_SCHEMA,
            "status": "PASS_W4_G4",
            "parents": [parent],
            "parent_lineage": {"w3n": parent, "w3": parent.get("w3_identity", {}), "w2": parent.get("w2_identity", {})},
            "w3n_parent_run_id": parent["run_id"],
            "w3n_index_sha256": parent["index_sha256"],
            "w3_profile_sha256": transport.profile_sha256,
            "w2_geometry_profile_sha256": geometry.profile_sha256,
            "carrier_profile_sha256": profile.profile_sha256,
            "carrier_root_sha256": profile.root_sha256,
            "composition_derivation_sha256": derivation["self_sha256"],
            "certificate_extension_sha256": extension["self_sha256"],
            "candidate_sha256": candidate["self_sha256"],
            "status_sha256": status["self_sha256"],
            "runtime_sha256": runtime["self_sha256"],
            "source_identity_sha256": source_identity["source_identity_sha256"],
            "hash_graph_sha256": hash_graph["self_sha256"],
            "manifest_sha256": manifest["self_sha256"],
            "objects": objects,
        }
        run_id = canonical_hash(index_core, ARTIFACT_DOMAIN)
        index_without_self = {**index_core, "run_id": run_id}
        index = {**index_without_self, "self_sha256": canonical_hash(index_without_self, INDEX_SCHEMA)}
        _write_json(stage, "index.json", index)

        try:
            from verify_cassi_qi_carrier import verify as verify_w4

            verification = verify_w4(stage, allow_staging_root=True)
        except Exception as exc:
            raise CarrierArtifactError(f"independent W4 verification failed: {exc}") from exc
        if not isinstance(verification, Mapping) or verification.get("status") not in {"PASS", "PASS_W4_G4"}:
            raise CarrierArtifactError("independent W4 verification did not pass")
        destination = root / run_id
        if destination.exists():
            try:
                existing = verify_w4(destination)
            except Exception as exc:
                raise CarrierArtifactError(f"content-addressed W4 destination is invalid: {destination}") from exc
            if existing.get("status") not in {"PASS", "PASS_W4_G4"}:
                raise CarrierArtifactError("existing W4 destination did not independently verify")
            shutil.rmtree(stage, ignore_errors=True)
        else:
            stage.replace(destination)
        return destination
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def run_artifact(*, output_root: str | Path | None = None) -> Path:
    """Seal one immutable W4 artifact and return its content-addressed path."""
    return _run(output_root=output_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    try:
        output = run_artifact(output_root=args.output_root)
    except Exception as exc:
        print(f"W4/G4 FAIL: {type(exc).__name__}: {exc}")
        return 1
    print(f"PASS_W4_G4 {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
