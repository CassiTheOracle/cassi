#!/usr/bin/env python3
"""Seal the verified Cassi Qi native runtime and Cosmos mirror artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
DEFAULT_OUTPUT = ROOT / "_diag" / "native-qi-release-manifest.json"
DEFAULT_VERIFICATION = ROOT / "_diag" / "native-qi-release-verification.json"
DEFAULT_COSMOS = WORKSPACE / "CassiCosmos" / "_diag" / "qi_state_bridge_receipt.json"
DEFAULT_MIND_GATE = WORKSPACE / "CassiCosmos" / "_diag" / "mind_engine_gpu.json"
DEFAULT_FIELD_DEPENDENCE = (
    WORKSPACE / "CassiFI" / "artifacts" / "qwen-displacement"
    / "qi-field-order-dependence.json"
)
CANONICAL_CONTRACT_FILE_SHA256 = "90ae65d322a0fc697a63a2949546e141f195f954b9221e617cce4222960fb32f"


SOURCE_PATHS = (
    "CassiFI/cassi_qi_field.py",
    "CassiFI/tests/test_cassi_field_language.py",
    "CassiFI/verification/canonical_native_qi_oracle.py",
    "CassiFI/verification/export_canonical_native_qi_fixture.py",
    "CassiFI/verification/measure_cassi_field_order_dependence.py",
    "CassiQwen/native/llama.cpp/common/arg.cpp",
    "CassiQwen/native/llama.cpp/common/common.cpp",
    "CassiQwen/native/llama.cpp/common/common.h",
    "CassiQwen/native/llama.cpp/examples/CMakeLists.txt",
    "CassiQwen/native/llama.cpp/ggml/include/ggml-rpc.h",
    "CassiQwen/native/llama.cpp/ggml/include/ggml.h",
    "CassiQwen/native/llama.cpp/ggml/src/ggml.c",
    "CassiQwen/native/llama.cpp/ggml/src/ggml-backend-meta.cpp",
    "CassiQwen/native/llama.cpp/ggml/src/ggml-cpu/ggml-cpu.c",
    "CassiQwen/native/llama.cpp/ggml/src/ggml-cpu/ops.cpp",
    "CassiQwen/native/llama.cpp/ggml/src/ggml-cpu/ops.h",
    "CassiQwen/native/llama.cpp/ggml/src/ggml-rpc/ggml-rpc.cpp",
    "CassiQwen/native/llama.cpp/ggml/src/ggml-vulkan/ggml-vulkan.cpp",
    "CassiQwen/native/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/cassi_qi_field_step.comp",
    "CassiQwen/native/llama.cpp/include/llama.h",
    "CassiQwen/native/llama.cpp/src/llama-cparams.h",
    "CassiQwen/native/llama.cpp/src/llama-context.cpp",
    "CassiQwen/native/llama.cpp/src/llama-context.h",
    "CassiQwen/native/llama.cpp/src/llama-graph.cpp",
    "CassiQwen/native/llama.cpp/src/llama-graph.h",
    "CassiQwen/native/llama.cpp/src/models/delta-net-base.cpp",
    "CassiQwen/native/llama.cpp/src/models/models.h",
    "CassiQwen/native/llama.cpp/src/models/qwen35.cpp",
    "CassiQwen/native/llama.cpp/tests/test-cassi-qi-canonical.cpp",
    "CassiQwen/native/llama.cpp/tests/test-cassi-qi-field.cpp",
    "CassiQwen/native/llama.cpp/tests/test-cassi-qi-qwen.cpp",
    "CassiQwen/native/llama.cpp/tests/CMakeLists.txt",
    "CassiQwen/native/llama.cpp/examples/cassi-qwen/cassi-qwen.cpp",
    "CassiQwen/native/llama.cpp/examples/cassi-qwen/CMakeLists.txt",
    "CassiQwen/README.md",
    "CassiQwen/verify_native_qi_release.py",
    "CassiQwen/write_native_qi_release_manifest.py",
    "CassiCosmos/scripts/cassi_mind_engine.gd",
    "CassiCosmos/scripts/verify_mind_engine.gd",
    "CassiCosmos/tools/qi_state_bridge.py",
    "CassiCosmos/verify/README.md",
)

BINARY_PATHS = (
    "CassiQwen/native/llama.cpp/build-qi/bin/Release/cassi-qwen.exe",
    "CassiQwen/native/llama.cpp/build-qi/bin/Release/test-cassi-qi-canonical.exe",
    "CassiQwen/native/llama.cpp/build-qi/bin/Release/test-cassi-qi-field.exe",
    "CassiQwen/native/llama.cpp/build-qi/bin/Release/test-cassi-qi-qwen.exe",
    "CassiQwen/native/llama.cpp/build-qi/bin/Release/llama.dll",
    "CassiQwen/native/llama.cpp/build-qi/bin/Release/ggml.dll",
    "CassiQwen/native/llama.cpp/build-qi/bin/Release/ggml-base.dll",
    "CassiQwen/native/llama.cpp/build-qi/bin/Release/ggml-cpu.dll",
    "CassiQwen/native/llama.cpp/build-qi/bin/Release/ggml-vulkan.dll",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} does not contain an object")
    return value


def describe(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing release input: {path}")
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def seal_paths(paths: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    return {path: describe(WORKSPACE / path) for path in paths}


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_manifest(verification_path: Path, cosmos_path: Path, mind_gate_path: Path,
                   field_dependence_path: Path) -> dict[str, Any]:
    verification = load_json(verification_path)
    cosmos = load_json(cosmos_path)
    mind_gate = load_json(mind_gate_path)
    dependence = load_json(field_dependence_path)

    require(verification.get("schema") == "cassi.qi.native-release-verification.v1"
            and verification.get("verdict") == "PASS",
            "native release verification is not PASS")
    require(cosmos.get("schema") == "cassi.qi.cosmos-bridge-receipt.v1"
            and cosmos.get("verdict") == "PASS",
            "Cosmos Qi mirror verification is not PASS")
    qi_gate = mind_gate.get("qi_mirror", {})
    require(qi_gate.get("snapshot_reply", {}).get("ok") is True,
            "mind-engine Qi snapshot gate did not pass")
    require(qi_gate.get("duplicate_reply", {}).get("idempotent") is True,
            "mind-engine Qi idempotence gate did not pass")
    require(qi_gate.get("conflict_reply", {}).get("ok") is False
            and qi_gate.get("stale_reply", {}).get("ok") is False
            and qi_gate.get("nonfinite_reply", {}).get("ok") is False
            and qi_gate.get("short_reply", {}).get("ok") is False,
            "mind-engine Qi rejection gates did not pass")
    require(qi_gate.get("project_reply", {}).get("cmd") == "qi_project",
            "mind-engine Qi projection gate did not pass")
    require(qi_gate.get("clear_reply", {}).get("ok") is True
            and qi_gate.get("cleared_state", {}).get("available") is False
            and qi_gate.get("pde_isolated") is True,
            "mind-engine Qi isolation/clear gate did not pass")
    require(dependence.get("schema") == "cassi.qi-field-order-dependence.v1"
            and dependence.get("verdict") == "FIELD_DEPENDENT"
            and dependence.get("field_dependence") is True,
            "exploratory field-order dependence receipt is not FIELD_DEPENDENT")

    contract_hash = verification["canonical_contract"]["contract_sha256"]
    contract_file_hash = verification["canonical_contract"].get("contract_file_sha256")
    canonical_contract_path = ROOT / "_diag" / "canonical-native-qi-v1" / "contract.json"
    require(isinstance(contract_file_hash, str)
            and contract_file_hash == CANONICAL_CONTRACT_FILE_SHA256
            and sha256(canonical_contract_path) == contract_file_hash,
            "verified canonical contract artifact changed before sealing")
    require(cosmos.get("contract_file_sha256") == contract_file_hash,
            "Cosmos mirrored a different canonical contract artifact")
    field_state = verification["artifacts"]["field_state"]
    require(cosmos.get("contract_sha256") == contract_hash,
            "Cosmos mirrored a different canonical contract")
    require(cosmos.get("state_sha256") == field_state["sha256"],
            "Cosmos did not mirror the verified field-only runtime state")
    require(cosmos.get("state_bytes") == field_state["bytes"],
            "Cosmos mirrored the wrong state byte count")
    require(cosmos.get("model_or_sampler_state_written_by_cosmos") is False,
            "Cosmos receipt does not prove a read-only mirror")

    evidence_paths = {
        "native_verification": verification_path,
        "cosmos_bridge": cosmos_path,
        "mind_engine_gate": mind_gate_path,
        "exploratory_field_dependence": field_dependence_path,
        "canonical_contract": canonical_contract_path,
        "canonical_initial_state": ROOT / "_diag" / "canonical-native-qi-v1" / "state-h0.f32",
        "field_only_output_state": ROOT / field_state["path"],
        "verification_model": ROOT / verification["verification_target"]["model"],
    }

    sealed_sources = seal_paths(SOURCE_PATHS)
    sealed_binaries = seal_paths(BINARY_PATHS)
    runtime_binaries = verification.get("runtime_binaries")
    if not isinstance(runtime_binaries, dict) or not runtime_binaries:
        raise RuntimeError("native verification did not bind its runtime binaries")
    runtime_keys = {f"CassiQwen/{path}" for path in runtime_binaries}
    require(runtime_keys == set(sealed_binaries),
            "verified runtime binary set differs from the release binary set")
    for runtime_path, observed in runtime_binaries.items():
        if not isinstance(runtime_path, str) or not isinstance(observed, dict):
            raise RuntimeError(
                "native verification contains a malformed runtime binary record")
        sealed = sealed_binaries[f"CassiQwen/{runtime_path}"]
        require(observed.get("bytes") == sealed["bytes"]
                and observed.get("sha256") == sealed["sha256"],
                f"verified runtime binary changed before sealing: {runtime_path}")

    commands = verification.get("commands")
    if not isinstance(commands, list) or not commands:
        raise RuntimeError("native verification contains no command records")
    for command in commands:
        if not isinstance(command, dict):
            raise RuntimeError("native command record is malformed")
        argv = command.get("argv")
        if not isinstance(argv, list) or not argv or not isinstance(argv[0], str):
            raise RuntimeError("native command record has no executable path")
        require(command.get("returncode") == 0,
                f"native command did not pass: {command.get('name', argv[0])}")
        binary_key = f"CassiQwen/{argv[0]}"
        require(binary_key in sealed_binaries,
                f"native command executable is not sealed: {argv[0]}")
        sealed = sealed_binaries[binary_key]
        require(command.get("executable_bytes") == sealed["bytes"]
                and command.get("executable_sha256") == sealed["sha256"],
                f"native command executable changed before sealing: {argv[0]}")
        require(command.get("expected_executable_bytes") == sealed["bytes"]
                and command.get("expected_executable_sha256") == sealed["sha256"],
                f"native command expected digest is not sealed: {argv[0]}")

    return {
        "schema": "cassi.qi.native-release-manifest.v1",
        "verdict": "PASS",
        "authority": {
            "persistent_adaptive_state": "canonical Cassi Qi field only",
            "canonical_python_layout": [4, 55296, 1],
            "canonical_native_layout": [1, 4, 6144, 9],
            "layout_relation": "exact transpose at the bridge boundary; never reshape",
            "native_transition": "ggml_cassi_qi_field_step.v2",
            "transition_scope": "defined native bridge law; not a numerical reimplementation of QiFieldController.cycle",
            "qwen_coupled_role": "immutable forward teacher through the selected field layer",
            "field_only_role": "GGUF vocabulary/tokenizer metadata only; no Qwen context, tensor load, forward pass, recurrent/KV state, model logits, LM head, or model sampler",
            "cosmos_role": "read-only hash-bound monotonic state mirror and projection",
        },
        "verified_displacement_sequence": {
            "0": "Qwen greedy baseline with field state observation",
            "1": "field-owned selection over the Qwen candidate set",
            "2": "field-owned selection over the complete vocabulary",
            "3": "selected recurrent state write bypassed",
            "4": "attention/recurrent/KV work bypassed at and after the field layer",
            "5": "complete transformer blocks bypassed at and after the field layer",
            "6": "output norm, LM head, and model logits replaced by exact field-owned logits sampled by upstream greedy sampling",
        },
        "ownership_accounting": verification["ownership_accounting"],
        "evidence_scope": {
            "native_exact_target": verification["verification_target"],
            "legacy_frozen_qi_field_dependence_v2": {
                "status": "UNAVAILABLE",
                "claim": "no source or receipt was reconstructed or relabeled",
            },
            "exploratory_field_order_dependence": {
                "status": dependence["verdict"],
                "receipt_sha256": dependence["receipt_sha256"],
                "trained_memory_unchanged": all(
                    item["trained_memory_unchanged"]
                    for item in dependence["comparisons"].values()
                ),
                "all_outputs_field_owned": all(
                    arm["all_outputs_field_owned"] for arm in dependence["arms"]
                ),
            },
            "qwen_27b": {
                "status": "NOT_VERIFIED",
                "reason": "two operator-reported hard hangs occurred while the iGPU was enabled; the 27B model and llama-cli were not rerun",
            },
            "workstation_gpu_condition": {
                "operator_report": "iGPU disabled before this verification",
                "runtime_observation": "native verification logs identify AMD Radeon RX 7900 XTX",
            },
            "frozen_python_ctypes_runtime": {
                "status": "UNCHANGED",
                "path": "CassiQwen/runtimes/llama-b10472-wip9/llama.dll",
                "note": "the native build-qi ABI is consumed by direct executables, not substituted under the frozen Python runner",
            },
        },
        "receipts": {
            name: {"path": path.resolve().relative_to(WORKSPACE).as_posix(), **describe(path)}
            for name, path in evidence_paths.items()
        },
        "sources": sealed_sources,
        "binaries": sealed_binaries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification", type=Path, default=DEFAULT_VERIFICATION)
    parser.add_argument("--cosmos", type=Path, default=DEFAULT_COSMOS)
    parser.add_argument("--mind-gate", type=Path, default=DEFAULT_MIND_GATE)
    parser.add_argument("--field-dependence", type=Path, default=DEFAULT_FIELD_DEPENDENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = build_manifest(
            args.verification.resolve(),
            args.cosmos.resolve(),
            args.mind_gate.resolve(),
            args.field_dependence.resolve(),
        )
    except Exception as error:
        manifest = {
            "schema": "cassi.qi.native-release-manifest.v1",
            "verdict": "FAIL",
            "error": f"{type(error).__name__}: {error}",
        }
    atomic_write(args.output.resolve(), manifest)
    print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    return 0 if manifest["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
