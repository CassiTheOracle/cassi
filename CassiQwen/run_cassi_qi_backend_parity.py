"""Execute and materialize CassiFI W14A/G14A backend parity evidence.

The runner is the only side that imports the live Torch backend.  Its output is
an immutable, content-addressed run root; :mod:`verify_cassi_qi_backend_parity`
reads that root using only the standard library.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

import torch

from cassi_qi_backend import (
    ADVANCE_OPERATOR_ID,
    BACKEND_CAPABILITY_SCHEMA,
    BACKEND_IDENTITY_SCHEMA,
    BACKEND_MEMORY_SCHEMA,
    BACKEND_OPERATOR_SCHEMA,
    BACKEND_PROBE_SCHEMA,
    FIXED_OPERATOR_ID,
    QiBackendError,
    QiBackendUnavailable,
    QiDriveBundle,
    QiParityGuardBands,
    TorchFlowBackend,
    compare_candidate_trajectories,
    compare_termwise_parity,
)
from cassi_qi_field import QiFlowStateV3
from cassi_qi_profile import canonical_json_bytes, load_development_profile

ROOT = Path(__file__).resolve().parent
DEFAULT_PROFILE = ROOT / "cassi-qi-flow-development.json"
DEFAULT_OUTPUT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w14a-backend-parity-final"
GATE_RELATIVE = Path("gates") / "g14a-operator-parity"
TERM_ORDER = ("current", "momentum", "work", "topology", "receipt", "state")

INDEX_SCHEMA = "cassi.qi-flow-w14a-run-index.v1"
MANIFEST_SCHEMA = "cassi.qi-flow-w14a-manifest.v1"
GATE_INDEX_SCHEMA = "cassi.qi-flow-w14a-gate-index.v1"
TERM_SCHEMA = "cassi.qi-flow-w14a-termwise-receipt.v1"
TRAJECTORY_SCHEMA = "cassi.qi-flow-w14a-trajectory-receipt.v1"
CONTROL_SCHEMA = "cassi.qi-flow-w14a-mutation-controls.v1"
RAW_SCHEMA = "cassi.qi-flow-w14a-raw-index.v1"
STATUS_SCHEMA = "cassi.qi-flow-gate-status.v1"

REQUIRED_REGISTRY_SCHEMAS = (
    "cassi.qi-flow-runtime-config.v1",
    "cassi.qi-flow-backend-identity.v1",
    "cassi.qi-flow-backend-capability.v1",
    "cassi.qi-flow-backend-capacity.v1",
    "cassi.qi-flow-backend-memory.v1",
    "cassi.qi-flow-backend-operator.v1",
    "cassi.qi-flow-backend-probe.v1",
    "cassi.qi-flow-backend-receipt.v1",
    "cassi.qi-flow-backend-step.v1",
    "cassi.qi-flow-gate-status.v1",
    "cassi.qi-flow-schema-registry.v1",
)


class W14AExecutionError(RuntimeError):
    """A required parity execution failed before an evidence record existed."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _stable_bytes(value: Any) -> bytes:
    """Hash bytes for runner-owned objects (which contain no binary tensors)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    return value


def _write_json(path: Path, value: Any) -> bytes:
    payload = canonical_json_bytes(_plain(value)) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _tensor_bytes(value: torch.Tensor) -> bytes:
    value = value.detach().contiguous().to(device="cpu")
    return value.numpy().tobytes(order="C")


def _tensor_descriptor(value: torch.Tensor, *, role: str) -> tuple[bytes, dict[str, Any]]:
    raw = _tensor_bytes(value)
    dtype = "float32" if value.dtype is torch.float32 else "float64" if value.dtype is torch.float64 else str(value.dtype)
    if dtype not in {"float32", "float64"}:
        raise W14AExecutionError(f"{role} has unsupported dtype {dtype}")
    descriptor = {
        "role": role,
        "dtype": dtype,
        "byte_order": "little",
        "shape": [int(item) for item in value.shape],
        "bytes": len(raw),
        "sha256": _sha256(raw),
    }
    return raw, descriptor


def _profile_with_dtype(profile: Any, *, dtype: str, device: str, suffix: str) -> Any:
    overrides: dict[str, Any] = {
        "field": {"dtype": dtype},
        "backend_contract": {"dtype": dtype, "device": device},
    }
    return profile.from_defaults(profile_id=f"{profile.payload['profile_id']}-{suffix}", overrides=overrides)


def _seeded_state(backend: TorchFlowBackend, profile: Any, batch: int) -> QiFlowStateV3:
    state = backend.initial_state(batch)
    with torch.no_grad():
        # Seed every batch lane with the same deterministic one-lane fixture.
        # A flat arange over the full tensor would interleave lane values and
        # make batching-vs-independent trajectory parity compare different
        # predecessor states.
        lane_shape = state.field.shape[:2] + (1,)
        values = torch.arange(
            state.field.shape[0] * state.field.shape[1],
            dtype=backend.dtype,
            device=backend.device,
        ).reshape(lane_shape).expand_as(state.field).clone()
        # Powers of two are exactly representable in both oracle and candidate
        # dtypes, so the work term measures backend arithmetic rather than
        # decimal-to-binary conversion noise.
        values = values * torch.tensor(2.0**-20, dtype=backend.dtype, device=backend.device)
        state.field.copy_(values)
    state.validate(profile, device=backend.device)
    return state


def _state_on_backend(source: QiFlowStateV3, backend: TorchFlowBackend, profile: Any) -> QiFlowStateV3:
    field = source.field.detach().to(device=backend.device, dtype=backend.dtype).contiguous()
    return QiFlowStateV3.from_field(profile, field)


def _term_values(profile: Any, predecessor: QiFlowStateV3, output: torch.Tensor, *, step: Any, probe: Any) -> dict[str, Any]:
    output = output.detach().contiguous()
    predecessor_field = predecessor.field.detach().contiguous()
    mode_count = int(profile.payload["field"]["mode_count"])
    delta = output - predecessor_field.to(device=output.device, dtype=output.dtype)
    finite = bool(torch.isfinite(output).all().item())
    topology = {
        "layout": [int(item) for item in output.shape],
        "finite": finite,
        "active_value_count": int(output.numel()),
        "transition": "COMMITTED" if bool(step.committable) else "REJECTED",
    }
    receipt = {
        "advance_status": str(step.receipt.get("status")),
        "advance_operator_id": str(step.operator_id),
        "transaction_id": str(step.transaction_id),
        "fixed_executed": bool(probe.executed),
        "fixed_parity_status": str(probe.parity_status),
    }
    return {
        "current": output[:, :1, :],
        "momentum": output[:, mode_count : mode_count + 1, :],
        "work": float(delta.abs().sum().item()),
        "topology": topology,
        "receipt": receipt,
        "state": output,
    }


def _fixed_term_values(profile: Any, predecessor: QiFlowStateV3, output: torch.Tensor, *, probe: Any) -> dict[str, Any]:
    output = output.detach().contiguous()
    predecessor_field = predecessor.field.detach().to(device=output.device, dtype=output.dtype)
    mode_count = int(profile.payload["field"]["mode_count"])
    delta = output - predecessor_field
    return {
        "current": output[:, :1, :],
        "momentum": output[:, mode_count : mode_count + 1, :],
        "work": float(delta.abs().sum().item()),
        "topology": {
            "layout": [int(item) for item in output.shape],
            "finite": bool(torch.isfinite(output).all().item()),
            "active_value_count": int(output.numel()),
            "transition": "FIXED-PROBE",
        },
        "receipt": {
            "fixed_executed": bool(probe.executed),
            "fixed_parity_status": str(probe.parity_status),
            "operator_id": str(probe.operator_id),
        },
        "state": output,
    }


def _mutation_controls(backend: TorchFlowBackend, profile: Any, state: QiFlowStateV3, prepared: Any) -> dict[str, Any]:
    controls: list[dict[str, Any]] = []

    def reject(control_id: str, action: Any) -> None:
        try:
            action()
        except QiBackendError as exc:
            controls.append({"control_id": control_id, "expected": "REJECT", "observed": "REJECT", "status": "PASS", "reason": f"{type(exc).__name__}: {exc}"})
        except Exception as exc:  # An unexpected exception is evidence of a broken rejection boundary.
            controls.append({"control_id": control_id, "expected": "REJECT", "observed": "ERROR", "status": "FAIL", "reason": f"{type(exc).__name__}: {exc}"})
        else:
            controls.append({"control_id": control_id, "expected": "REJECT", "observed": "ACCEPT", "status": "FAIL", "reason": "mutation was accepted"})

    tampered = replace(prepared, operator_sha256="0" * 64)
    reject(
        "prepared-handle-operator-hash-mutation",
        lambda: backend.execute_advance(state, QiDriveBundle(transaction_id="control-prepared", delta=0.0, prepared=tampered)),
    )
    reject(
        "missing-prepared-handle",
        lambda: backend.execute_advance(state, QiDriveBundle(transaction_id="control-missing")),
    )
    wrong_dtype = torch.zeros_like(state.field, dtype=torch.float32 if state.field.dtype is torch.float64 else torch.float64)
    reject(
        "drive-dtype-mutation",
        lambda: backend.execute_advance(state, QiDriveBundle(transaction_id="control-dtype", delta=wrong_dtype, prepared=prepared)),
    )
    return {"schema": CONTROL_SCHEMA, "controls": controls, "status": "PASS" if controls and all(item["status"] == "PASS" for item in controls) else "FAIL", "control_count": len(controls)}


def _pair_execution(
    oracle_backend: TorchFlowBackend,
    candidate_backend: TorchFlowBackend,
    oracle_profile: Any,
    candidate_profile: Any,
    oracle_state: QiFlowStateV3,
    candidate_state: QiFlowStateV3,
    guards: QiParityGuardBands,
    *,
    label: str,
) -> tuple[dict[str, Any], dict[str, tuple[bytes, dict[str, Any]]]]:
    oracle_advance = oracle_backend.prepare(oracle_profile, 1, operator_id=ADVANCE_OPERATOR_ID)
    candidate_advance = candidate_backend.prepare(candidate_profile, 1, operator_id=ADVANCE_OPERATOR_ID)
    oracle_fixed = oracle_backend.prepare(oracle_profile, 1, operator_id=FIXED_OPERATOR_ID)
    candidate_fixed = candidate_backend.prepare(candidate_profile, 1, operator_id=FIXED_OPERATOR_ID)

    drive_delta = 2.0**-20
    oracle_step = oracle_backend.execute_advance(oracle_state, QiDriveBundle(transaction_id=f"{label}-advance", delta=drive_delta, prepared=oracle_advance))
    candidate_step = candidate_backend.execute_advance(candidate_state, QiDriveBundle(transaction_id=f"{label}-advance", delta=drive_delta, prepared=candidate_advance))
    oracle_probe = oracle_backend.fixed_operator_probe(oracle_state, prepared=oracle_fixed)
    candidate_probe = candidate_backend.fixed_operator_probe(candidate_state, prepared=candidate_fixed)

    if oracle_step.candidate is None or candidate_step.candidate is None:
        raise W14AExecutionError(f"{label} advance did not produce a candidate")
    oracle_output = oracle_step.candidate.field
    candidate_output = candidate_step.candidate.field
    oracle_fixed_output = oracle_output.new_empty(oracle_output.shape)
    candidate_fixed_output = candidate_output.new_empty(candidate_output.shape)
    # fixed_operator_probe is intentionally exercised above; this is the same pure operator
    # applied to its already validated input so its term payload has actual values.
    from cassi_qi_backend import fixed_operator_probe
    oracle_fixed_output = fixed_operator_probe(oracle_state.field)
    candidate_fixed_output = fixed_operator_probe(candidate_state.field)

    oracle_terms = _term_values(oracle_profile, oracle_state, oracle_output, step=oracle_step, probe=oracle_probe)
    candidate_terms = _term_values(candidate_profile, candidate_state, candidate_output, step=candidate_step, probe=candidate_probe)
    advance_parity = compare_termwise_parity(
        oracle_profile,
        oracle_backend,
        candidate_backend,
        oracle_terms,
        candidate_terms,
        guard_bands=guards,
        executed=True,
        oracle_prepared=oracle_advance,
        candidate_prepared=candidate_advance,
    )
    oracle_fixed_terms = _fixed_term_values(oracle_profile, oracle_state, oracle_fixed_output, probe=oracle_probe)
    candidate_fixed_terms = _fixed_term_values(candidate_profile, candidate_state, candidate_fixed_output, probe=candidate_probe)
    fixed_parity = compare_termwise_parity(
        oracle_profile,
        oracle_backend,
        candidate_backend,
        oracle_fixed_terms,
        candidate_fixed_terms,
        guard_bands=guards,
        executed=True,
        oracle_prepared=oracle_fixed,
        candidate_prepared=candidate_fixed,
    )

    parity_statuses = [advance_parity.parity_status, fixed_parity.parity_status]
    if "FAIL" in parity_statuses:
        status = "FAIL"
    elif "ABSTAIN" in parity_statuses:
        status = "ABSTAIN"
    elif all(item == "PASS" for item in parity_statuses):
        status = "PASS"
    else:
        status = "NOT_RUN"
    raw: dict[str, tuple[bytes, dict[str, Any]]] = {}
    for role, tensor in (
        (f"{label}-advance-oracle", oracle_output),
        (f"{label}-advance-candidate", candidate_output),
        (f"{label}-fixed-oracle", oracle_fixed_output),
        (f"{label}-fixed-candidate", candidate_fixed_output),
        (f"{label}-predecessor-oracle", oracle_state.field),
        (f"{label}-predecessor-candidate", candidate_state.field),
    ):
        raw[role] = _tensor_descriptor(tensor, role=role)
    record = {
        "label": label,
        "schema": TERM_SCHEMA,
        "status": status,
        "executed": True,
        "term_order": list(TERM_ORDER),
        "advance": {
            "parity_status": advance_parity.parity_status,
            "receipt": _plain(advance_parity.to_payload()),
            "step_receipt": _plain(oracle_step.receipt),
            "candidate_step_receipt": _plain(candidate_step.receipt),
            "oracle_probe": _plain(oracle_probe.to_payload()),
            "candidate_probe": _plain(candidate_probe.to_payload()),
        },
        "fixed": {
            "parity_status": fixed_parity.parity_status,
            "receipt": _plain(fixed_parity.to_payload()),
        },
        "prepared": {
            "oracle_advance": _plain(oracle_advance.to_payload()),
            "candidate_advance": _plain(candidate_advance.to_payload()),
            "oracle_fixed": _plain(oracle_fixed.to_payload()),
            "candidate_fixed": _plain(candidate_fixed.to_payload()),
        },
        "backend_receipts": {
            "oracle": _plain(oracle_backend.backend_receipt(step=oracle_step)),
            "candidate": _plain(candidate_backend.backend_receipt(step=candidate_step)),
        },
        "counter_delta": {
            "oracle": _plain(oracle_backend.memory_receipt().to_payload()),
            "candidate": _plain(candidate_backend.memory_receipt().to_payload()),
        },
    }
    return record, raw


def _trajectory_execution(backend: TorchFlowBackend, profile: Any, guards: QiParityGuardBands) -> tuple[dict[str, Any], dict[str, tuple[bytes, dict[str, Any]]]]:
    batched_state = _seeded_state(backend, profile, 2)
    batched_prepared = backend.prepare(profile, 2, operator_id=ADVANCE_OPERATOR_ID)
    batched_step = backend.execute_advance(batched_state, QiDriveBundle(transaction_id="trajectory-batched", delta=1.0e-6, prepared=batched_prepared))
    if batched_step.candidate is None:
        raise W14AExecutionError("batched trajectory did not produce a candidate")
    independent_fields: list[torch.Tensor] = []
    for index in range(2):
        state = _seeded_state(backend, profile, 1)
        prepared = backend.prepare(profile, 1, operator_id=ADVANCE_OPERATOR_ID)
        step = backend.execute_advance(state, QiDriveBundle(transaction_id=f"trajectory-independent-{index}", delta=1.0e-6, prepared=prepared))
        if step.candidate is None:
            raise W14AExecutionError(f"independent trajectory {index} did not produce a candidate")
        independent_fields.append(step.candidate.field)
    batched_fields = [batched_step.candidate.field[:, :, index : index + 1] for index in range(2)]
    trajectory = compare_candidate_trajectories(profile, batched_fields, independent_fields, guard_bands=guards, executed=True)
    raw: dict[str, tuple[bytes, dict[str, Any]]] = {}
    for index, value in enumerate(batched_fields):
        raw[f"trajectory-batched-{index}"] = _tensor_descriptor(value, role=f"trajectory-batched-{index}")
    for index, value in enumerate(independent_fields):
        raw[f"trajectory-independent-{index}"] = _tensor_descriptor(value, role=f"trajectory-independent-{index}")
    return {
        "schema": TRAJECTORY_SCHEMA,
        "status": trajectory.parity_status,
        "executed": trajectory.executed,
        "term_order": list(TERM_ORDER),
        "receipt": _plain(trajectory.to_payload()),
        "batched_prepared": _plain(batched_prepared.to_payload()),
        "batch_size": 2,
        "independent_count": len(independent_fields),
    }, raw


def _attempt_rocm(oracle_backend: TorchFlowBackend, oracle_profile: Any, oracle_state: QiFlowStateV3, guards: QiParityGuardBands, rocm_profile: Any) -> tuple[dict[str, Any], dict[str, tuple[bytes, dict[str, Any]]], TorchFlowBackend | None]:
    try:
        backend = TorchFlowBackend(rocm_profile, device="cuda:0", dtype=torch.float32, seed=0)
    except QiBackendUnavailable as exc:
        return {"label": "rocm-f32", "status": "NOT_RUN", "executed": False, "requested_device": "cuda:0", "reason": f"{type(exc).__name__}: {exc}", "fallback": False}, {}, None
    except Exception as exc:
        return {"label": "rocm-f32", "status": "FAIL", "executed": False, "requested_device": "cuda:0", "reason": f"{type(exc).__name__}: {exc}", "fallback": False}, {}, None
    try:
        candidate_state = _state_on_backend(oracle_state, backend, rocm_profile)
        record, raw = _pair_execution(oracle_backend, backend, oracle_profile, rocm_profile, oracle_state, candidate_state, guards, label="rocm-f32")
        record["fallback"] = False
        return record, raw, backend
    except Exception as exc:
        return {"label": "rocm-f32", "status": "FAIL", "executed": False, "requested_device": "cuda:0", "reason": f"{type(exc).__name__}: {exc}", "fallback": False}, {}, backend


def _record_failure(label: str, exc: BaseException) -> dict[str, Any]:
    return {"label": label, "status": "FAIL", "executed": False, "reason": f"{type(exc).__name__}: {exc}"}


def _copy_source(stage: Path, source: Path, relative: str) -> tuple[str, str]:
    target = stage / "run-spec" / "sources" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = source.read_bytes()
    target.write_bytes(raw)
    return relative, _sha256(raw)


def _write_run(output_root: Path, profile_path: Path, data: dict[str, Any], raw_values: dict[str, tuple[bytes, dict[str, Any]]]) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".w14a-", dir=str(output_root.parent)))
    try:
        source_identity: dict[str, str] = {}
        source_files = (
            ("cassi_qi_backend.py", ROOT / "cassi_qi_backend.py"),
            ("cassi_qi_field.py", ROOT / "cassi_qi_field.py"),
            ("cassi_qi_profile.py", ROOT / "cassi_qi_profile.py"),
            ("run_cassi_qi_backend_parity.py", ROOT / "run_cassi_qi_backend_parity.py"),
            ("verify_cassi_qi_backend_parity.py", ROOT / "verify_cassi_qi_backend_parity.py"),
            ("cassi-qi-flow-development.json", profile_path),
        )
        for relative, source in source_files:
            name, digest = _copy_source(stage, source, relative)
            source_identity[name] = digest
        registry_source = ROOT / "cassi-fi-schema-registry" / "manifest.json"
        name, digest = _copy_source(stage, registry_source, "cassi-fi-schema-registry/manifest.json")
        source_identity[name] = digest
        _write_json(stage / "run-spec" / "profiles" / "oracle.json", data["profiles"]["oracle"])
        _write_json(stage / "run-spec" / "profiles" / "cpu-f32.json", data["profiles"]["cpu-f32"])
        _write_json(stage / "run-spec" / "profiles" / "rocm-f32.json", data["profiles"]["rocm-f32"])

        gate = stage / GATE_RELATIVE
        gate.mkdir(parents=True, exist_ok=True)
        _write_json(gate / "termwise.json", data["termwise"])
        _write_json(gate / "trajectory.json", data["trajectory"])
        _write_json(gate / "backend-receipts.json", data["backend_receipts"])
        _write_json(gate / "guard-bands.json", data["guards"])
        _write_json(gate / "mutation-controls.json", data["controls"])
        _write_json(gate / "execution-counters.json", data["execution_counters"])
        raw_descriptors: list[dict[str, Any]] = []
        raw_dir = gate / "raw"
        for role, (raw, descriptor) in sorted(raw_values.items()):
            safe = role.replace("/", "-").replace(" ", "-")
            suffix = ".f32le" if descriptor["dtype"] == "float32" else ".f64le"
            target = raw_dir / f"{safe}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            row = dict(descriptor)
            row["path"] = target.relative_to(stage).as_posix()
            raw_descriptors.append(row)
        _write_json(gate / "raw-index.json", {"schema": RAW_SCHEMA, "objects": raw_descriptors})
        gate_index = {
            "schema": GATE_INDEX_SCHEMA,
            "gate": "G14A",
            "status": data["status"],
            "term_order": list(TERM_ORDER),
            "required_receipts": ["termwise.json", "trajectory.json", "backend-receipts.json", "guard-bands.json", "mutation-controls.json", "execution-counters.json", "raw-index.json"],
            "source_identity_sha256": data["source_identity_sha256"],
            "profile_sha256": data["profile_identity"]["oracle"]["profile_sha256"],
        }
        gate_index_bytes = _write_json(gate / "index.json", gate_index)
        status_payload = {
            "schema": STATUS_SCHEMA,
            "gate": "G14A",
            "status": data["status"],
            "reason": data["reason"],
            "executed_backends": data["executed_backends"],
            "missing_backends": data["missing_backends"],
        }
        _write_json(gate / "status.json", status_payload)

        files: list[dict[str, Any]] = []
        for path in sorted(item for item in stage.rglob("*") if item.is_file()):
            relative = path.relative_to(stage).as_posix()
            if relative in {"index.json", "manifest.json"}:
                continue
            raw = path.read_bytes()
            files.append({"path": relative, "bytes": len(raw), "sha256": _sha256(raw)})
        manifest_body = {"schema": MANIFEST_SCHEMA, "files": files}
        manifest = {**manifest_body, "manifest_sha256": _sha256(_stable_bytes(manifest_body))}
        manifest_bytes = _write_json(stage / "manifest.json", manifest)
        index_body = {
            "schema": INDEX_SCHEMA,
            "gate": "G14A",
            "gate_relative_path": GATE_RELATIVE.as_posix(),
            "status": data["status"],
            "reason": data["reason"],
            "manifest_sha256": manifest["manifest_sha256"],
            "source_identity": source_identity,
            "source_identity_sha256": data["source_identity_sha256"],
            "profile_identity": data["profile_identity"],
            "backend_identity": data["backend_identity"],
            "operator_identity": data["operator_identity"],
            "registry": data["registry"],
            "executed_backends": data["executed_backends"],
            "missing_backends": data["missing_backends"],
            "gate_index_sha256": _sha256(gate_index_bytes),
            "gate_status_sha256": _sha256((stage / GATE_RELATIVE / "status.json").read_bytes()),
            "termwise_sha256": _sha256((stage / GATE_RELATIVE / "termwise.json").read_bytes()),
            "trajectory_sha256": _sha256((stage / GATE_RELATIVE / "trajectory.json").read_bytes()),
            "raw_index_sha256": _sha256((stage / GATE_RELATIVE / "raw-index.json").read_bytes()),
        }
        artifact_sha = _sha256(_stable_bytes(index_body))
        index = {**index_body, "run_id": artifact_sha, "artifact_sha256": artifact_sha}
        _write_json(stage / "index.json", index)
        destination = output_root / artifact_sha
        if destination.exists():
            shutil.rmtree(stage)
        else:
            os.replace(stage, destination)
            stage = destination
        return destination
    finally:
        if stage.exists() and stage.name.startswith(".w14a-"):
            shutil.rmtree(stage, ignore_errors=True)


def run(*, profile_path: Path | str = DEFAULT_PROFILE, output_root: Path | str = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    """Execute W14A CPU-f64/CPU-f32 and an explicit ROCm-f32 attempt."""
    profile_path = Path(profile_path)
    output_root = Path(output_root)
    profile = load_development_profile(profile_path)
    cpu_profile = _profile_with_dtype(profile, dtype="float32", device="cpu", suffix="cpu-f32")
    rocm_profile = _profile_with_dtype(profile, dtype="float32", device="cuda", suffix="rocm-f32")
    guards = QiParityGuardBands.from_profile(profile)

    oracle = TorchFlowBackend(profile, device="cpu", dtype=torch.float64, seed=0)
    cpu32 = TorchFlowBackend(cpu_profile, device="cpu", dtype=torch.float32, seed=0)
    oracle_state = _seeded_state(oracle, profile, 1)
    cpu32_state = _state_on_backend(oracle_state, cpu32, cpu_profile)
    raw_values: dict[str, tuple[bytes, dict[str, Any]]] = {}
    termwise: dict[str, Any] = {"schema": TERM_SCHEMA, "term_order": list(TERM_ORDER), "comparisons": {}}
    backend_receipts: dict[str, Any] = {}
    try:
        cpu_record, cpu_raw = _pair_execution(oracle, cpu32, profile, cpu_profile, oracle_state, cpu32_state, guards, label="cpu-f32")
        termwise["comparisons"]["cpu-f32"] = cpu_record
        raw_values.update(cpu_raw)
    except Exception as exc:
        termwise["comparisons"]["cpu-f32"] = _record_failure("cpu-f32", exc)
    try:
        trajectory, trajectory_raw = _trajectory_execution(oracle, profile, guards)
    except Exception as exc:
        trajectory = {"schema": TRAJECTORY_SCHEMA, "status": "FAIL", "executed": False, "reason": f"{type(exc).__name__}: {exc}"}
        trajectory_raw = {}
    raw_values.update(trajectory_raw)

    rocm_record, rocm_raw, rocm_backend = _attempt_rocm(oracle, profile, oracle_state, guards, rocm_profile)
    termwise["comparisons"]["rocm-f32"] = rocm_record
    raw_values.update(rocm_raw)

    if isinstance(termwise["comparisons"].get("cpu-f32"), Mapping):
        backend_receipts["cpu-f32"] = termwise["comparisons"]["cpu-f32"].get("backend_receipts")
    if isinstance(rocm_record, Mapping) and rocm_record.get("backend_receipts") is not None:
        backend_receipts["rocm-f32"] = rocm_record.get("backend_receipts")
    backend_receipts["oracle-memory"] = _plain(oracle.memory_receipt().to_payload())
    backend_receipts["cpu-f32-memory"] = _plain(cpu32.memory_receipt().to_payload())
    if rocm_backend is not None:
        backend_receipts["rocm-f32-memory"] = _plain(rocm_backend.memory_receipt().to_payload())

    control_rows = _mutation_controls(oracle, profile, oracle_state, oracle.prepare(profile, 1, operator_id=ADVANCE_OPERATOR_ID))
    if rocm_record.get("status") == "NOT_RUN":
        control_rows["controls"].append({"control_id": "rocm-unavailable-no-cpu-fallback", "expected": "NOT_RUN", "observed": "NOT_RUN", "status": "PASS", "reason": rocm_record.get("reason", "device unavailable")})
        control_rows["control_count"] = len(control_rows["controls"])

    statuses = [str(termwise["comparisons"].get(label, {}).get("status", "FAIL")) for label in ("cpu-f32", "rocm-f32")]
    statuses.append(str(trajectory.get("status", "FAIL")))
    control_status = str(control_rows.get("status"))
    if "FAIL" in statuses or control_status == "FAIL":
        status = "FAIL"
    elif "ABSTAIN" in statuses:
        status = "ABSTAIN"
    elif "NOT_RUN" in statuses:
        status = "NOT_RUN"
    elif all(item == "PASS" for item in statuses):
        status = "PASS"
    else:
        status = "FAIL"
    executed_backends = ["cpu-f64", "cpu-f32"]
    missing_backends: list[str] = []
    if rocm_record.get("executed"):
        executed_backends.append("rocm-f32")
    else:
        missing_backends.append("rocm-f32")
    source_identity_sha256 = _sha256(_stable_bytes({
        "cassi_qi_backend.py": _sha256((ROOT / "cassi_qi_backend.py").read_bytes()),
        "cassi_qi_field.py": _sha256((ROOT / "cassi_qi_field.py").read_bytes()),
        "cassi_qi_profile.py": _sha256((ROOT / "cassi_qi_profile.py").read_bytes()),
        "run_cassi_qi_backend_parity.py": _sha256((ROOT / "run_cassi_qi_backend_parity.py").read_bytes()),
        "verify_cassi_qi_backend_parity.py": _sha256((ROOT / "verify_cassi_qi_backend_parity.py").read_bytes()),
        "cassi-qi-flow-development.json": _sha256(profile_path.read_bytes()),
        "cassi-fi-schema-registry/manifest.json": _sha256((ROOT / "cassi-fi-schema-registry" / "manifest.json").read_bytes()),
    }))
    data = {
        "status": status,
        "reason": "; ".join([str(rocm_record.get("reason")) for _ in [0] if rocm_record.get("reason")]) or ("ROCm-f32 is unavailable; no CPU fallback was used" if "rocm-f32" in missing_backends else "all required executions completed"),
        "profiles": {"oracle": _plain(profile.payload), "cpu-f32": _plain(cpu_profile.payload), "rocm-f32": _plain(rocm_profile.payload)},
        "profile_identity": {
            "oracle": {"profile_sha256": profile.profile_sha256, "backend_sha256": profile.backend_sha256, "state_contract_sha256": profile.state_contract_sha256, "dtype": "float64", "device": "cpu"},
            "cpu-f32": {"profile_sha256": cpu_profile.profile_sha256, "backend_sha256": cpu_profile.backend_sha256, "state_contract_sha256": cpu_profile.state_contract_sha256, "dtype": "float32", "device": "cpu"},
            "rocm-f32": {"profile_sha256": rocm_profile.profile_sha256, "backend_sha256": rocm_profile.backend_sha256, "state_contract_sha256": rocm_profile.state_contract_sha256, "dtype": "float32", "device": "cuda"},
        },
        "backend_identity": {
            "oracle": _plain(oracle.identity_receipt),
            "cpu-f32": _plain(cpu32.identity_receipt),
            "rocm-f32": _plain(rocm_backend.identity_receipt) if rocm_backend is not None else {"status": rocm_record.get("status"), "requested_device": "cuda:0", "fallback": False},
        },
        "operator_identity": {
            "fixed_operator_id": FIXED_OPERATOR_ID,
            "advance_operator_id": ADVANCE_OPERATOR_ID,
            "oracle": {"fixed": oracle.prepare(profile, 1, operator_id=FIXED_OPERATOR_ID).operator_sha256, "advance": oracle.prepare(profile, 1, operator_id=ADVANCE_OPERATOR_ID).operator_sha256},
            "cpu-f32": {"fixed": cpu32.prepare(cpu_profile, 1, operator_id=FIXED_OPERATOR_ID).operator_sha256, "advance": cpu32.prepare(cpu_profile, 1, operator_id=ADVANCE_OPERATOR_ID).operator_sha256},
        },
        "registry": {"manifest_path": "run-spec/sources/cassi-fi-schema-registry/manifest.json", "required_schemas": list(REQUIRED_REGISTRY_SCHEMAS), "source_sha256": _sha256((ROOT / "cassi-fi-schema-registry" / "manifest.json").read_bytes())},
        "source_identity_sha256": source_identity_sha256,
        "termwise": termwise,
        "trajectory": trajectory,
        "backend_receipts": backend_receipts,
        "guards": {"schema": BACKEND_PROBE_SCHEMA, "payload": _plain(guards.to_payload())},
        "controls": control_rows,
        "execution_counters": {"oracle": _plain(oracle.memory_receipt().to_payload()), "cpu-f32": _plain(cpu32.memory_receipt().to_payload()), "rocm-f32": _plain(rocm_backend.memory_receipt().to_payload()) if rocm_backend is not None else None},
        "profile_identity_hash": profile.profile_sha256,
        "executed_backends": executed_backends,
        "missing_backends": missing_backends,
    }
    artifact = _write_run(output_root, profile_path, data, raw_values)
    try:
        relative = artifact.relative_to(ROOT).as_posix()
    except ValueError:
        relative = str(artifact)
    return {"schema": INDEX_SCHEMA, "artifact": relative, "run_id": artifact.name, "status": status, "gate": "G14A", "executed_backends": executed_backends, "missing_backends": missing_backends}


def run_artifact(*, profile_path: Path | str = DEFAULT_PROFILE, output_root: Path | str = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    return run(profile_path=profile_path, output_root=output_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    print(canonical_json_bytes(run(profile_path=args.profile, output_root=args.output_root)).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
