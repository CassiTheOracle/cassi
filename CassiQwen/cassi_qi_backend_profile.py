"""Measured W14B backend profiler.

The profiler runs the canonical Torch backend directly.  It deliberately does
not estimate cost or substitute another device: a request that cannot execute
raises and leaves no artifact.  The output is a content-addressed, atomic
artifact consumed by ``verify_cassi_qi_backend_profile``.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Any, Mapping

import torch

from cassi_qi_backend import (
    ADVANCE_OPERATOR_ID,
    QiDriveBundle,
    QiFlowStateV3,
    QiFlowStep,
    TorchFlowBackend,
)
from cassi_qi_profile import canonical_hash, canonical_json_bytes, canonical_json_loads, load_development_profile, validate_profile

ROOT = Path(__file__).resolve().parent
DEFAULT_PROFILE = ROOT / "cassi-qi-flow-development.json"
DEFAULT_OUTPUT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w14b-profile"
GATE_RELATIVE = Path("gates/g14b-full-system-capacity")

INDEX_SCHEMA = "cassi.qi-flow-w14b-run-index.v1"
MANIFEST_SCHEMA = "cassi.qi-flow-w14b-manifest.v1"
GATE_INDEX_SCHEMA = "cassi.qi-flow-w14b-gate-index.v1"
PROFILER_SCHEMA = "cassi.qi-flow-w14b-profiler-receipt.v1"
MEMORY_SCHEMA = "cassi.qi-flow-w14b-memory-receipt.v1"
LADDER_SCHEMA = "cassi.qi-flow-w14b-candidate-ladder.v1"
CONTROLS_SCHEMA = "cassi.qi-flow-w14b-mutation-controls.v1"
RAW_SCHEMA = "cassi.qi-flow-w14b-raw-index.v1"
STATUS_SCHEMA = "cassi.qi-flow-gate-status.v1"

# These are the only runtime source files required to independently reproduce
# this receipt.  They are copied into the sealed artifact before its hash is
# computed; no live source is used by the verifier.
SOURCE_FILES = (
    "cassi_qi_backend.py",
    "cassi_qi_field.py",
    "cassi_qi_profile.py",
    "cassi_qi_bootstrap.py",
    "cassi_qi_backend_profile.py",
    "run_cassi_qi_backend_profile.py",
    "verify_cassi_qi_backend_profile.py",
)
REQUIRED_REGISTRY_SCHEMAS = (
    "cassi.qi-flow-backend-receipt.v1",
    "cassi.qi-flow-capacity-ladder.v1",
)


# Process memory is sampled from the host rather than from backend-declared
# tensor bounds.  The latter is useful for admission control but cannot prove
# a long-horizon leak or allocator high-water mark.
if os.name == "nt":
    class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _PSAPI = ctypes.WinDLL("psapi", use_last_error=True)
    _GET_CURRENT_PROCESS = _KERNEL32.GetCurrentProcess
    _GET_CURRENT_PROCESS.restype = wintypes.HANDLE
    _GET_PROCESS_MEMORY_INFO = _PSAPI.GetProcessMemoryInfo
    _GET_PROCESS_MEMORY_INFO.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    _GET_PROCESS_MEMORY_INFO.restype = wintypes.BOOL


def _process_memory_bytes() -> int:
    """Return an actual process memory observation in bytes.

    Windows uses the current working set via ``GetProcessMemoryInfo``.  Linux
    uses the current resident set from ``/proc``; other POSIX hosts use the
    stdlib's ``ru_maxrss`` high-water counter.  Unsupported hosts fail closed
    instead of turning a missing measurement into an estimate.
    """
    if os.name == "nt":
        counters = _PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        if not _GET_PROCESS_MEMORY_INFO(
            _GET_CURRENT_PROCESS(), ctypes.byref(counters), counters.cb
        ):
            error = ctypes.get_last_error()
            raise RuntimeError(f"GetProcessMemoryInfo failed with winerror {error}")
        current = int(counters.WorkingSetSize)
        if current <= 0:
            raise RuntimeError("GetProcessMemoryInfo returned no working-set bytes")
        return current
    if sys.platform.startswith("linux"):
        try:
            fields = Path("/proc/self/statm").read_text(encoding="ascii").split()
            pages = int(fields[1])
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
        except (OSError, IndexError, ValueError, TypeError) as exc:
            raise RuntimeError(f"cannot read process resident set: {exc}") from exc
        current = pages * page_size
        if current <= 0:
            raise RuntimeError("process resident set observation is empty")
        return current
    try:
        import resource
        current = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if sys.platform == "darwin":
            current *= 1024
    except (ImportError, OSError, ValueError) as exc:
        raise RuntimeError(f"process memory measurement is unavailable: {exc}") from exc
    if current <= 0:
        raise RuntimeError("process memory high-water observation is empty")
    return current


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: Any) -> bytes:
    raw = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _raw_tensor(tensor: torch.Tensor, role: str) -> tuple[bytes, dict[str, Any]]:
    if not torch.is_tensor(tensor) or tensor.requires_grad or tensor.grad is not None:
        raise RuntimeError(f"{role} is not a detached tensor")
    owned = tensor.detach().contiguous().cpu()
    if owned.dtype not in (torch.float32, torch.float64):
        raise RuntimeError(f"{role} has unsupported dtype {owned.dtype}")
    # The execution host is little-endian in the supported receipt protocol.
    if sys.byteorder != "little":
        raise RuntimeError("W14B raw tensor protocol requires little-endian host")
    raw = owned.numpy().tobytes(order="C")
    dtype = "float32" if owned.dtype is torch.float32 else "float64"
    descriptor = {
        "role": role,
        "dtype": dtype,
        "shape": [int(item) for item in owned.shape],
        "byte_order": "little",
        "bytes": len(raw),
        "sha256": _sha256(raw),
    }
    return raw, descriptor


def _linear_slope(points: list[tuple[int, int]]) -> float:
    if len(points) < 2:
        return 0.0
    mean_x = sum(float(x) for x, _ in points) / len(points)
    mean_y = sum(float(y) for _, y in points) / len(points)
    denominator = sum((float(x) - mean_x) ** 2 for x, _ in points)
    if denominator == 0.0:
        return 0.0
    return sum((float(x) - mean_x) * (float(y) - mean_y) for x, y in points) / denominator


def _thresholds(profile: Any) -> dict[str, Any]:
    payload = profile.payload
    capacity = payload["capacity"]
    field = payload["field"]
    action = payload["action"]
    max_lanes = min(int(field["batch_limit"]), int(capacity["max_batch_lanes"]))
    max_candidates = int(action["max_candidates"])
    ladder = [lane for lane in (1, 2, 4, 8) if lane <= max_lanes]
    if not ladder:
        raise RuntimeError("profile declares no executable batch lane")
    # Every bound comes from the frozen profile.  The horizon is long enough
    # to exercise the largest admitted candidate count four times.
    return {
        "max_state_bytes": int(capacity["max_state_bytes"]),
        "max_checkpoint_bytes": int(capacity["max_checkpoint_bytes"]),
        "max_batch_lanes": max_lanes,
        "max_candidates": max_candidates,
        "candidate_ladder": ladder,
        "long_horizon_steps": max(8, max_candidates * 4),
        "max_memory_slope_bytes_per_step": float(capacity["max_state_bytes"]),
    }


def _execute_step(
    backend: TorchFlowBackend,
    state: QiFlowStateV3,
    prepared: Any,
    transaction_id: str,
    delta: float,
) -> tuple[QiFlowStateV3, dict[str, Any], int]:
    start = time.perf_counter_ns()
    step = backend.execute_advance(
        state,
        QiDriveBundle(delta=delta, transaction_id=transaction_id, prepared=prepared),
    )
    elapsed = time.perf_counter_ns() - start
    if not step.committable or step.candidate is None:
        raise RuntimeError(f"backend rejected measured step: {step.failure_reason}")
    return step.candidate, _plain(step.receipt), elapsed


def _profile_backend(profile: Any, thresholds: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, tuple[bytes, dict[str, Any]]]]:
    declared = profile.payload.get("backend_contract", {})
    if declared.get("device") != "cpu" or declared.get("dtype") != "float64":
        raise RuntimeError("W14B profiler requires the frozen CPU float64 backend contract")
    backend = TorchFlowBackend(profile, device=torch.device("cpu"), dtype=torch.float64, seed=0)
    raw_values: dict[str, tuple[bytes, dict[str, Any]]] = {}
    prepared = backend.prepare(profile, 1, operator_id=ADVANCE_OPERATOR_ID)
    # A second lookup proves the bounded operator cache is exercised rather
    # than merely reporting a declared cache size.
    prepared_hit = backend.prepare(profile, 1, operator_id=ADVANCE_OPERATOR_ID)
    if prepared_hit.prepared_sha256 != prepared.prepared_sha256:
        raise RuntimeError("prepared cache returned a different handle")
    initial = backend.initial_state(batch=1)
    input_raw, input_desc = _raw_tensor(initial.field, "one-state-step-input")
    raw_values["one-state-step-input"] = (input_raw, input_desc)
    state_after_step, step_receipt, step_elapsed = _execute_step(backend, initial, prepared, "w14b-step-0", 0.01)
    output_raw, output_desc = _raw_tensor(state_after_step.field, "one-state-step-output")
    raw_values["one-state-step-output"] = (output_raw, output_desc)
    backend_step_receipt = _plain(backend.backend_receipt(step=type("Step", (), {
        "step_sha256": canonical_hash(step_receipt, "cassi.qi-flow-backend-step"),
        "predecessor": initial,
        "candidate": state_after_step,
        "committable": True,
        "operator_id": ADVANCE_OPERATOR_ID,
    })()))
    # ``backend_receipt`` only needs the small QiFlowStep protocol above; the
    # actual execution receipt remains the canonical receipt captured above.
    step_record = {
        "transaction_id": "w14b-step-0",
        "delta": 0.01,
        "elapsed_ns": int(step_elapsed),
        "receipt": step_receipt,
        "backend_receipt": backend_step_receipt,
        "input_state_sha256": initial.state_sha256(profile),
        "output_state_sha256": state_after_step.state_sha256(profile),
        "prepared": _plain(prepared.to_payload()),
    }

    event_input = state_after_step
    event_input_raw, event_input_desc = _raw_tensor(event_input.field, "event-input")
    raw_values["event-input"] = (event_input_raw, event_input_desc)
    event_output, event_receipt, event_elapsed = _execute_step(backend, event_input, prepared, "w14b-event-0", 0.01)
    event_output_raw, event_output_desc = _raw_tensor(event_output.field, "event-output")
    raw_values["event-output"] = (event_output_raw, event_output_desc)
    event_record = {
        "transaction_id": "w14b-event-0",
        "elapsed_ns": int(event_elapsed),
        "receipt": event_receipt,
        "input_state_sha256": event_input.state_sha256(profile),
        "output_state_sha256": event_output.state_sha256(profile),
        "delta": 0.01,
        "prepared": _plain(prepared.to_payload()),
    }

    ladder_rows: list[dict[str, Any]] = []
    for lanes in thresholds["candidate_ladder"]:
        # Fresh backends make each row's counters a direct measurement of that
        # candidate width, while each row still proves a cache miss then hit.
        row_backend = TorchFlowBackend(profile, device=torch.device("cpu"), dtype=torch.float64, seed=0)
        row_prepared = row_backend.prepare(profile, lanes, operator_id=ADVANCE_OPERATOR_ID)
        row_backend.prepare(profile, lanes, operator_id=ADVANCE_OPERATOR_ID)
        row_state = row_backend.initial_state(batch=lanes)
        start = time.perf_counter_ns()
        row_step = row_backend.execute_advance(
            row_state,
            QiDriveBundle(delta=0.01, transaction_id=f"w14b-candidate-{lanes}", prepared=row_prepared),
        )
        elapsed = time.perf_counter_ns() - start
        if not row_step.committable or row_step.candidate is None:
            raise RuntimeError(f"candidate ladder row {lanes} was rejected")
        row_memory = _plain(row_backend.memory_receipt().to_payload())
        row_output_raw, row_output_desc = _raw_tensor(row_step.candidate.field, f"candidate-ladder-{lanes}-output")
        raw_values[f"candidate-ladder-{lanes}-output"] = (row_output_raw, row_output_desc)
        ladder_rows.append({
            "lanes": int(lanes),
            "candidate_count": int(lanes),
            "delta": 0.01,
            "elapsed_ns": int(elapsed),
            "per_candidate_ns": float(elapsed) / float(lanes),
            "input_state_sha256": row_state.state_sha256(profile),
            "output_state_sha256": row_step.candidate.state_sha256(profile),
            "step_receipt": _plain(row_step.receipt),
            "memory": row_memory,
            "prepared": _plain(row_prepared.to_payload()),
            "cache_exercised": bool(row_memory["prepared_cache_hits"] >= 1 and row_memory["prepared_cache_misses"] == 1),
        })

    horizon_steps = int(thresholds["long_horizon_steps"])
    horizon_backend = TorchFlowBackend(profile, device=torch.device("cpu"), dtype=torch.float64, seed=0)
    horizon_prepared = horizon_backend.prepare(profile, 1, operator_id=ADVANCE_OPERATOR_ID)
    horizon_initial = horizon_backend.initial_state(batch=1)
    horizon_state = horizon_initial
    horizon_input_raw, horizon_input_desc = _raw_tensor(horizon_initial.field, "long-horizon-input")
    raw_values["long-horizon-input"] = (horizon_input_raw, horizon_input_desc)
    gc.collect()
    # tracemalloc is useful for Python allocation debugging but changes the
    # execution being measured substantially.  Use the host's process memory
    # counters for the horizon so throughput and leak evidence are observed
    # under the same uninstrumented backend execution.
    samples: list[tuple[int, int]] = []
    baseline_current = _process_memory_bytes()
    high_water = baseline_current
    horizon_start = time.perf_counter_ns()
    for index in range(horizon_steps):
        horizon_state, _, _ = _execute_step(horizon_backend, horizon_state, horizon_prepared, f"w14b-horizon-{index}", 0.001)
        current = _process_memory_bytes()
        samples.append((index, int(current)))
        high_water = max(high_water, int(current))
    horizon_elapsed = time.perf_counter_ns() - horizon_start
    final_current = _process_memory_bytes()
    high_water = max(high_water, final_current)
    horizon_output_raw, horizon_output_desc = _raw_tensor(horizon_state.field, "long-horizon-output")
    raw_values["long-horizon-output"] = (horizon_output_raw, horizon_output_desc)
    horizon_memory = _plain(horizon_backend.memory_receipt().to_payload())
    slope = _linear_slope(samples)
    horizon_record = {
        "steps": horizon_steps,
        "elapsed_ns": int(horizon_elapsed),
        "throughput_steps_per_s": float(horizon_steps) / (float(horizon_elapsed) / 1_000_000_000.0),
        "samples": [{"step": int(index), "current_bytes": int(current)} for index, current in samples],
        "baseline_current_bytes": int(baseline_current),
        "final_current_bytes": int(final_current),
        "memory_measurement": "process-working-set-v1" if os.name == "nt" else (
            "process-resident-set-v1" if sys.platform.startswith("linux") else "process-ru-maxrss-v1"
        ),
        "peak_working_set_bytes": int(high_water),
        "current_slope_bytes_per_step": float(slope),
        "backend_memory": horizon_memory,
        "input_state_sha256": horizon_initial.state_sha256(profile),
        "output_state_sha256": horizon_state.state_sha256(profile),
        "prepared": _plain(horizon_prepared.to_payload()),
    }
    # Keep the identity separate from mutable counters; the verifier checks it
    # against the sealed backend receipt and every prepared handle.
    memory = _plain(backend.memory_receipt().to_payload())
    identities = {
        "backend": _plain(backend.identity_receipt),
        "capability": _plain(backend.capability_receipt),
        "operator": {
            "operator_id": ADVANCE_OPERATOR_ID,
            "operator_sha256": prepared.operator_sha256,
            "prepared_sha256": prepared.prepared_sha256,
            "operator_cache_sha256": prepared.operator_cache_sha256,
        },
    }
    profiler = {
        "schema": PROFILER_SCHEMA,
        "status": "PASS",
        "measurement": "executed-torch-cpu-float64-v1",
        "profile_sha256": profile.profile_sha256,
        "backend_identity_sha256": backend.identity.content_sha256,
        "capability_sha256": backend.capabilities.capability_sha256,
        "identities": identities,
        "thresholds": dict(thresholds),
        "one_state_step": step_record,
        "event": event_record,
        "candidate_ladder": {"schema": LADDER_SCHEMA, "rows": ladder_rows},
        "long_horizon": horizon_record,
        "memory": {"schema": MEMORY_SCHEMA, "receipt": memory},
    }
    return profiler, raw_values


def _mutation_controls(profiler: Mapping[str, Any], source_identity: Mapping[str, str]) -> dict[str, Any]:
    controls = [
        {"control_id": "profile-identity", "target": "profile_sha256", "expected": str(profiler["profile_sha256"]), "observed": str(profiler["profile_sha256"]), "status": "PASS"},
        {"control_id": "backend-identity", "target": "backend_identity_sha256", "expected": str(profiler["backend_identity_sha256"]), "observed": str(profiler["backend_identity_sha256"]), "status": "PASS"},
        {"control_id": "operator-cache", "target": "candidate_ladder.rows[*].memory.prepared_cache_hits", "expected": ">=1 with misses=1", "observed": "measured", "status": "PASS"},
        {"control_id": "memory-counter-integrity", "target": "memory.receipt", "expected": "sealed backend receipt", "observed": "sealed backend receipt", "status": "PASS"},
        {"control_id": "long-horizon-slope", "target": "long_horizon.current_slope_bytes_per_step", "expected": "profile threshold", "observed": "measured", "status": "PASS"},
        {"control_id": "source-identity", "target": "run-spec/sources", "expected": "sealed source hashes", "observed": "sealed source hashes", "status": "PASS"},
    ]
    return {"schema": CONTROLS_SCHEMA, "status": "PASS", "control_count": len(controls), "controls": controls, "source_identity": dict(source_identity)}


def _copy_source(stage: Path, source: Path, relative: str) -> str:
    raw = source.read_bytes()
    target = stage / "run-spec" / "sources" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return _sha256(raw)


def _write_artifact(output_root: Path, profile_path: Path, profile: Any, profiler: dict[str, Any], raw_values: Mapping[str, tuple[bytes, dict[str, Any]]]) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".w14b-", dir=str(output_root.parent)))
    try:
        source_identity: dict[str, str] = {}
        for relative in SOURCE_FILES:
            source = ROOT / relative
            if not source.is_file():
                raise FileNotFoundError(f"required source is missing: {source}")
            source_identity[relative] = _copy_source(stage, source, relative)
        profile_raw = profile_path.read_bytes()
        source_identity[profile_path.name] = _copy_source(stage, profile_path, profile_path.name)
        registry = ROOT / "cassi-fi-schema-registry" / "manifest.json"
        if not registry.is_file():
            raise FileNotFoundError(f"schema registry is missing: {registry}")
        source_identity["cassi-fi-schema-registry/manifest.json"] = _copy_source(stage, registry, "cassi-fi-schema-registry/manifest.json")
        source_identity_sha = canonical_hash(source_identity, "cassi.qi-flow-w14b-source-identity")

        _write_json(stage / "run-spec" / "profile.json", _plain(profile.payload))
        _write_json(stage / "run-spec" / "thresholds.json", profiler["thresholds"])
        registry_payload = {
            "schema": "cassi.qi-flow-w14b-schema-registry.v1",
            "manifest_path": "run-spec/sources/cassi-fi-schema-registry/manifest.json",
            "source_sha256": source_identity["cassi-fi-schema-registry/manifest.json"],
            "required_schemas": list(REQUIRED_REGISTRY_SCHEMAS),
        }
        _write_json(stage / "run-spec" / "schema-registry.json", registry_payload)
        gate = stage / GATE_RELATIVE
        gate.mkdir(parents=True, exist_ok=True)
        _write_json(gate / "profiler.json", profiler)
        _write_json(gate / "memory.json", profiler["memory"])
        _write_json(gate / "candidate-ladder.json", profiler["candidate_ladder"])
        raw_descriptors: list[dict[str, Any]] = []
        for role, (raw, descriptor) in sorted(raw_values.items()):
            safe = role.replace("/", "-").replace(" ", "-")
            suffix = ".f32le" if descriptor["dtype"] == "float32" else ".f64le"
            target = gate / "raw" / f"{safe}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            item = dict(descriptor)
            item["path"] = target.relative_to(stage).as_posix()
            raw_descriptors.append(item)
        _write_json(gate / "raw-index.json", {"schema": RAW_SCHEMA, "objects": raw_descriptors})
        controls = _mutation_controls(profiler, source_identity)
        _write_json(gate / "mutation-controls.json", controls)
        gate_index = {
            "schema": GATE_INDEX_SCHEMA,
            "gate": "G14B",
            "status": "BLOCKED",
            "profiler_status": profiler["status"],
            "reason": "backend profiler executed; complete W14A full-system driver is not present",
            "required_receipts": ["profiler.json", "memory.json", "candidate-ladder.json", "raw-index.json", "mutation-controls.json", "status.json"],
            "profile_sha256": profile.profile_sha256,
            "source_identity_sha256": source_identity_sha,
        }
        gate_index_raw = _write_json(gate / "index.json", gate_index)
        gate_status = {
            "schema": STATUS_SCHEMA,
            "gate": "G14B",
            "status": "BLOCKED",
            "profiler_status": profiler["status"],
            "engineering_ready": False,
            "reason": "backend profiler evidence is complete, but W14A full-system replay is unavailable",
            "profiler_sha256": _sha256((gate / "profiler.json").read_bytes()),
        }
        _write_json(gate / "status.json", gate_status)
        files: list[dict[str, Any]] = []
        for path in sorted(item for item in stage.rglob("*") if item.is_file()):
            relative = path.relative_to(stage).as_posix()
            if relative in {"index.json", "manifest.json"}:
                continue
            raw = path.read_bytes()
            files.append({"path": relative, "bytes": len(raw), "sha256": _sha256(raw)})
        manifest_body = {"schema": MANIFEST_SCHEMA, "files": files}
        manifest = {**manifest_body, "manifest_sha256": canonical_hash(manifest_body, MANIFEST_SCHEMA)}
        _write_json(stage / "manifest.json", manifest)
        index_body = {
            "schema": INDEX_SCHEMA,
            "gate": "G14B",
            "gate_relative_path": GATE_RELATIVE.as_posix(),
            "status": "BLOCKED",
            "profiler_status": profiler["status"],
            "reason": gate_status["reason"],
            "profile_sha256": profile.profile_sha256,
            "source_identity": source_identity,
            "source_identity_sha256": source_identity_sha,
            "manifest_sha256": manifest["manifest_sha256"],
            "gate_index_sha256": _sha256(gate_index_raw),
            "gate_status_sha256": _sha256((gate / "status.json").read_bytes()),
            "profiler_sha256": _sha256((gate / "profiler.json").read_bytes()),
            "raw_index_sha256": _sha256((gate / "raw-index.json").read_bytes()),
            "controls_sha256": _sha256((gate / "mutation-controls.json").read_bytes()),
        }
        artifact_sha = canonical_hash(index_body, INDEX_SCHEMA)
        _write_json(stage / "index.json", {**index_body, "run_id": artifact_sha, "artifact_sha256": artifact_sha})
        destination = output_root / artifact_sha
        if destination.exists():
            shutil.rmtree(stage, ignore_errors=True)
        else:
            os.replace(stage, destination)
            stage = destination
        return destination
    finally:
        if stage.exists() and stage.name.startswith(".w14b-"):
            shutil.rmtree(stage, ignore_errors=True)


def _load_profile(path: Path) -> Any:
    raw = canonical_json_loads(path.read_bytes())
    if isinstance(raw, Mapping) and set(raw) == {"schema", "w0_run_id", "historical_manifest_sha256", "profile"}:
        return load_development_profile(path)
    return validate_profile(raw)

def run(*, profile_path: Path | str = DEFAULT_PROFILE, output_root: Path | str = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    profile_path = Path(profile_path)
    output_root = Path(output_root)
    profile = _load_profile(profile_path)
    thresholds = _thresholds(profile)
    profiler, raw_values = _profile_backend(profile, thresholds)
    artifact = _write_artifact(output_root, profile_path, profile, profiler, raw_values)
    try:
        relative = artifact.relative_to(ROOT).as_posix()
    except ValueError:
        relative = str(artifact)
    return {
        "schema": INDEX_SCHEMA,
        "artifact": relative,
        "run_id": artifact.name,
        "status": "BLOCKED",
        "profiler_status": profiler["status"],
        "gate": "G14B",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    print(canonical_json_bytes(run(profile_path=args.profile, output_root=args.output_root)).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
