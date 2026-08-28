from __future__ import annotations

import argparse
import hashlib
import os
import struct
import tempfile
from pathlib import Path
from typing import Any

import torch
from cassi_qi_bootstrap import finite_float

from cassi_qi_field import (
    QI_FLOW_STATE_V3_SCHEMA,
    QI_FLOW_STATE_V3_TENSOR_DOMAIN,
    QiFlowStateV3,
    dump_v3_state_bytes,
    load_v3_checkpoint,
    load_v3_state_bytes,
    save_v3_checkpoint,
    v3_state_identity,
)
from cassi_qi_profile import (
    PROFILE_MISMATCH,
    canonical_hash,
    canonical_json_bytes,
    canonical_json_loads,
    load_development_profile,
    validate_contract_root,
)


_REPOSITORY = Path(__file__).resolve().parent
_W0_ARTIFACT_SHA256 = "6594761eeaf97fcc839d5b931908ff7990dd7d853094b7b94c0fad2b2fac8d47"
_W0_HISTORICAL_MANIFEST_SHA256 = "98814b75591d73174c8aaac9a23f5717c656ddabe94b2776b1ea79dff10feba8"
_PLAN_DOCUMENT_SET_SHA256 = "4da5d103b60dd21b5c1ccf5db4a9b7abc22f91c92044b57bf041a761be09cad6"
_W0_PARENT = _REPOSITORY / "_diag" / "cassi-qi-flow-w0-final" / _W0_ARTIFACT_SHA256
_DEFAULT_OUTPUT = _REPOSITORY / "_diag" / "cassi-qi-flow-w1-identity-candidate" / "identity.json"
_MAGIC = b"CASSI-QI-FLOW-STATE-V3\x00"
_CANDIDATE_SCHEMA = "cassi.qi-flow-g1-identity-candidate.v1"


def _split_checkpoint(payload: bytes) -> tuple[dict[str, Any], bytes]:
    prefix_size = len(_MAGIC) + 8
    if not payload.startswith(_MAGIC):
        raise RuntimeError("v3 test payload lost its canonical state framing")
    header_size = struct.unpack(">Q", payload[len(_MAGIC):prefix_size])[0]
    header_end = prefix_size + header_size
    header = canonical_json_loads(payload[prefix_size:header_end])
    if not isinstance(header, dict):
        raise RuntimeError("v3 test payload header is not an object")
    return header, payload[header_end:]


def _join_checkpoint(header: dict[str, Any], raw: bytes) -> bytes:
    header_bytes = canonical_json_bytes(header)
    return _MAGIC + struct.pack(">Q", len(header_bytes)) + header_bytes + raw


def _frame(value: bytes) -> bytes:
    return struct.pack(">Q", len(value)) + value


def _raw_state_sha256(header: dict[str, Any], raw: bytes) -> str:
    shape = header["shape"]
    if not isinstance(shape, list) or len(shape) != 3:
        raise RuntimeError("v3 mutation control cannot reconstruct its state shape")
    dtype = header["dtype"]
    state_contract = header["state_contract_sha256"]
    if not isinstance(dtype, str) or not isinstance(state_contract, str):
        raise RuntimeError("v3 mutation control cannot reconstruct its state identity")
    digest = hashlib.sha256()
    digest.update(_frame(QI_FLOW_STATE_V3_TENSOR_DOMAIN.encode("utf-8")))
    digest.update(_frame(state_contract.encode("ascii")))
    digest.update(_frame(dtype.encode("ascii")))
    digest.update(struct.pack(">I", len(shape)))
    for dimension in shape:
        if isinstance(dimension, bool) or not isinstance(dimension, int):
            raise RuntimeError("v3 mutation control has an invalid state shape")
        digest.update(struct.pack(">Q", dimension))
    digest.update(struct.pack(">Q", len(raw)))
    digest.update(raw)
    return digest.hexdigest()


def _reseal_header(
    header: dict[str, Any],
    raw: bytes,
    *,
    rehash_raw_state: bool = False,
) -> dict[str, Any]:
    sealed = dict(header)
    if rehash_raw_state:
        sealed["source_raw_sha256"] = hashlib.sha256(raw).hexdigest()
        sealed["state_sha256"] = _raw_state_sha256(sealed, raw)
    sealed.pop("self_sha256", None)
    sealed["self_sha256"] = canonical_hash(sealed, QI_FLOW_STATE_V3_SCHEMA)
    return sealed


def _must_reject(payload: bytes, profile: Any) -> bool:
    try:
        load_v3_state_bytes(payload, profile)
    except PROFILE_MISMATCH:
        return True
    return False


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def integrated_state(profile: Any) -> QiFlowStateV3:
    state = QiFlowStateV3.create(profile, batch_lanes=1)
    field_contract = profile.payload["field"]
    bounds = field_contract["state_bounds"]
    component_limit = min(finite_float(value) for value in bounds["component_abs_max"])
    complex_limit = min(finite_float(value) for value in bounds["complex_amplitude_max"]) / (2.0**0.5)
    density_limit = (finite_float(bounds["density_max"]) / 8.0) ** 0.5
    epsilon_limit = finite_float(bounds["epsilon2_ema_max"])
    fill_limit = min(component_limit, complex_limit, density_limit, epsilon_limit) / 4.0
    packed = state.field.reshape(
        int(field_contract["scale_count"]),
        9,
        int(field_contract["mode_count"]),
        1,
    )
    for scale, active_sites in enumerate(field_contract["active_site_counts"]):
        active = packed[scale, :, : int(active_sites), :]
        values = torch.arange(
            1,
            active.numel() + 1,
            dtype=state.field.dtype,
            device=state.field.device,
        ).reshape_as(active)
        active.copy_(values * (fill_limit / float(active.numel() + 1)))
    return state


def _mutation_controls(payload: bytes, profile: Any, state: QiFlowStateV3) -> dict[str, bool]:
    header, raw = _split_checkpoint(payload)
    before = state.field.view(torch.uint8).clone()

    extra_tensor = dict(header)
    extra_tensor["extra_tensor"] = "forbidden"
    adaptive_map = dict(header)
    adaptive_map["adaptive_map"] = {"forbidden": 1}
    scalar_ledger = dict(header)
    scalar_ledger["scalar_ledger"] = {"forbidden": 1}
    wrong_profile = dict(header)
    wrong_profile["profile_sha256"] = "0" * 64
    wrong_root = dict(header)
    wrong_root["contract_root_sha256"] = "0" * 64
    wrong_backend = dict(header)
    wrong_backend["backend"] = "cuda"
    wrong_self = dict(header)
    wrong_self["self_sha256"] = "0" * 64

    nonfinite_raw = bytearray(raw)
    scalar_format = "<f" if header["dtype"] == "float32" else "<d"
    struct.pack_into(scalar_format, nonfinite_raw, 0, float("nan"))
    resealed_nonfinite = _reseal_header(
        dict(header),
        bytes(nonfinite_raw),
        rehash_raw_state=True,
    )

    field_contract = profile.payload["field"]
    mode_count = int(field_contract["mode_count"])
    batch_count = int(header["shape"][2])
    scalar_size = struct.calcsize(scalar_format)

    out_of_bounds_raw = bytearray(raw)
    component_limit = finite_float(
        field_contract["state_bounds"]["component_abs_max"][0]
    )
    struct.pack_into(scalar_format, out_of_bounds_raw, 0, component_limit * 2.0)
    resealed_out_of_bounds = _reseal_header(
        dict(header),
        bytes(out_of_bounds_raw),
        rehash_raw_state=True,
    )

    negative_epsilon_raw = bytearray(raw)
    epsilon_offset = 8 * mode_count * batch_count * scalar_size
    struct.pack_into(scalar_format, negative_epsilon_raw, epsilon_offset, -1.0)
    resealed_negative_epsilon = _reseal_header(
        dict(header),
        bytes(negative_epsilon_raw),
        rehash_raw_state=True,
    )

    inactive_tail_rejected = True
    for scale, active_count in enumerate(field_contract["active_site_counts"]):
        if int(active_count) >= mode_count:
            continue
        inactive_tail_raw = bytearray(raw)
        scalar_index = (
            scale * 9 * mode_count * batch_count
            + int(active_count) * batch_count
        )
        struct.pack_into(
            scalar_format,
            inactive_tail_raw,
            scalar_index * scalar_size,
            1.0,
        )
        resealed_inactive_tail = _reseal_header(
            dict(header),
            bytes(inactive_tail_raw),
            rehash_raw_state=True,
        )
        inactive_tail_rejected = _must_reject(
            _join_checkpoint(resealed_inactive_tail, bytes(inactive_tail_raw)),
            profile,
        )
        break

    controls = {
        "legacy_v1_rejected": _must_reject(b'{"schema":"cassi.qi.field-state.v1"}', profile),
        "legacy_v2_rejected": _must_reject(b'{"schema":"cassi.qi.field-state.v2"}', profile),
        "truncated_rejected": _must_reject(payload[:-1], profile),
        "extra_tensor_rejected": _must_reject(
            _join_checkpoint(_reseal_header(extra_tensor, raw), raw),
            profile,
        ),
        "adaptive_map_rejected": _must_reject(
            _join_checkpoint(_reseal_header(adaptive_map, raw), raw),
            profile,
        ),
        "scalar_ledger_rejected": _must_reject(
            _join_checkpoint(_reseal_header(scalar_ledger, raw), raw),
            profile,
        ),
        "profile_mutation_rejected": _must_reject(
            _join_checkpoint(_reseal_header(wrong_profile, raw), raw),
            profile,
        ),
        "root_mutation_rejected": _must_reject(
            _join_checkpoint(_reseal_header(wrong_root, raw), raw),
            profile,
        ),
        "backend_mutation_rejected": _must_reject(
            _join_checkpoint(_reseal_header(wrong_backend, raw), raw),
            profile,
        ),
        "self_hash_mutation_rejected": _must_reject(
            _join_checkpoint(wrong_self, raw),
            profile,
        ),
        "raw_mutation_rejected": _must_reject(
            _join_checkpoint(header, raw[:-1] + bytes([raw[-1] ^ 1])),
            profile,
        ),
        "nonfinite_raw_rejected": _must_reject(
            _join_checkpoint(resealed_nonfinite, bytes(nonfinite_raw)),
            profile,
        ),
        "out_of_bounds_raw_rejected": _must_reject(
            _join_checkpoint(resealed_out_of_bounds, bytes(out_of_bounds_raw)),
            profile,
        ),
        "negative_epsilon2_ema_rejected": _must_reject(
            _join_checkpoint(
                resealed_negative_epsilon,
                bytes(negative_epsilon_raw),
            ),
            profile,
        ),
        "inactive_tail_rejected": inactive_tail_rejected,
        "predecessor_unchanged": bool(torch.equal(state.field.view(torch.uint8), before)),
    }
    if not all(controls.values()):
        failed = sorted(name for name, passed in controls.items() if not passed)
        raise RuntimeError(f"identity mutation controls unexpectedly passed: {failed!r}")
    return controls


def run(profile_path: Path, output_path: Path) -> dict[str, Any]:
    if not _W0_PARENT.is_dir():
        raise RuntimeError(f"sealed W0 parent is unavailable: {_W0_PARENT}")
    profile = load_development_profile(profile_path)
    root = validate_contract_root(profile.contract_root)
    if root.sha256 != profile.contract_root_sha256:
        raise RuntimeError("validated integrated contract root no longer matches the loaded development profile")

    calibration = QiFlowStateV3.create(profile, batch_lanes=1)
    calibration_identity = v3_state_identity(calibration, profile)
    integrated = integrated_state(profile)
    integrated_identity = v3_state_identity(integrated, profile)
    payload = dump_v3_state_bytes(integrated, profile)

    with tempfile.TemporaryDirectory(prefix="cassi-qi-flow-w1-") as directory:
        checkpoint = Path(directory) / "integrated.qiflow"
        persisted_hash = save_v3_checkpoint(checkpoint, integrated, profile)
        restarted = load_v3_checkpoint(checkpoint, profile, device=profile.state_layout["backend"])
    exact_restart = bool(torch.equal(restarted.field.view(torch.uint8), integrated.field.view(torch.uint8)))
    if not exact_restart or restarted.state_sha256(profile) != persisted_hash:
        raise RuntimeError("same-backend v3 restart was not exact")

    mutation_controls = _mutation_controls(payload, profile, integrated)
    parent_relative = _W0_PARENT.relative_to(_REPOSITORY).as_posix()
    candidate: dict[str, Any] = {
        "schema": _CANDIDATE_SCHEMA,
        "w1_scope": "identity-checkpoint-v3",
        "parents": [
            {
                "kind": "sealed-w0-final",
                "path": parent_relative,
                "artifact_sha256": _W0_ARTIFACT_SHA256,
                "historical_manifest_sha256": _W0_HISTORICAL_MANIFEST_SHA256,
                "plan_document_set_sha256": _PLAN_DOCUMENT_SET_SHA256,
            }
        ],
        "plan_document_set_sha256": _PLAN_DOCUMENT_SET_SHA256,
        "profile_sha256": profile.profile_sha256,
        "contract_root_sha256": profile.contract_root_sha256,
        "state_contract_sha256": profile.state_contract_sha256,
        "execution_schedule_sha256": profile.execution_schedule_sha256,
        "topology_sha256": profile.topology_sha256,
        "source_identity_sha256": profile.source_identity_sha256,
        "calibration": {
            "profile_sha256": profile.profile_sha256,
            "contract_root_sha256": profile.contract_root_sha256,
            "state_contract_sha256": profile.state_contract_sha256,
            "execution_schedule_sha256": profile.execution_schedule_sha256,
            "topology_sha256": profile.topology_sha256,
            "source_identity_sha256": profile.source_identity_sha256,
            "state_sha256": calibration_identity["state_sha256"],
            "source_raw_sha256": calibration_identity["source_raw_sha256"],
            "shape": calibration_identity["shape"],
        },
        "integrated": {
            "state_sha256": integrated_identity["state_sha256"],
            "source_raw_sha256": integrated_identity["source_raw_sha256"],
            "shape": integrated_identity["shape"],
        },
        "exact_restart": {
            "same_backend": profile.state_layout["backend"],
            "raw_bits_equal": exact_restart,
            "state_sha256": persisted_hash,
        },
        "mutation_controls": mutation_controls,
    }
    candidate["self_sha256"] = canonical_hash(candidate, _CANDIDATE_SCHEMA)
    _atomic_write(output_path, canonical_json_bytes(candidate))
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the sealed-parent W1/G1 v3 identity checkpoint gate.")
    parser.add_argument(
        "--profile",
        type=Path,
        default=_REPOSITORY / "cassi-qi-flow-development.json",
        help="fixed-parent development profile materialization",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="new W1 identity candidate path; never a W0 path",
    )
    arguments = parser.parse_args()
    candidate = run(arguments.profile, arguments.out)
    print(canonical_json_bytes({"artifact": str(arguments.out), "self_sha256": candidate["self_sha256"]}).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
