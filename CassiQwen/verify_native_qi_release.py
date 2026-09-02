#!/usr/bin/env python3
"""Verify the canonical native Qi boundary and every Qwen-displacement rung.

This intentionally invokes the direct native executables. It never invokes the
unstable llama-cli wrapper and never loads the 27B teacher model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
BIN = ROOT / "native" / "llama.cpp" / "build-qi" / "bin" / "Release"
FIXTURE = ROOT / "_diag" / "canonical-native-qi-v1"
MODEL = ROOT / "Qwen3.5-0.8B-Q4_0.gguf"
RECEIPT = ROOT / "_diag" / "native-qi-release-verification.json"
COUPLED_STATE = ROOT / "_diag" / "native-runtime-coupled-state.f32"
FIELD_STATE = ROOT / "_diag" / "native-runtime-field-state.f32"

MODEL_SHA256 = "57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf"
CONTRACT_SHA256 = "fd34a9ac52df28e3c292080053ecde18d742cf6049e840209add2d82f433d320"
CONTRACT_FILE_SHA256 = "90ae65d322a0fc697a63a2949546e141f195f954b9221e617cce4222960fb32f"
CHECKPOINT_SHA256 = "58f21773729db4f0cecd5886da4a9cd19e9507cd95586fe63cb4e9babc490b01"
CHECKPOINT_STATE_SHA256 = "616d017c5a7fe4917c6abcb9674b7623803ce3a49d9269b0e5b970dad8722728"
STATE_BYTES = 4 * 6144 * 9 * 4
EXPECTED_RELEASE_BINARIES = {
    "cassi-qwen.exe": {
        "bytes": 50688,
        "sha256": "3314865dae6a3f8f610ce650c2032ae0d5b5902ad9852b28341fde242a1b1ea4",
    },
    "test-cassi-qi-canonical.exe": {
        "bytes": 69632,
        "sha256": "2a5bc1a6ecb5b07a96ad25cb2e3076f8731e961b439074e0328e926b1bca7303",
    },
    "test-cassi-qi-field.exe": {
        "bytes": 24064,
        "sha256": "63e63d87201e55c1d00c8ec110406e1555c5f4dfb9af400e5568bfc0130168ad",
    },
    "test-cassi-qi-qwen.exe": {
        "bytes": 40960,
        "sha256": "c9c7c94cf03d89ea0cd60caf1c6aee95e47df115149cc94964f90bfedff89df3",
    },
    "llama.dll": {
        "bytes": 2487808,
        "sha256": "e4c7d238d35f87f97d77c41b1b4b371501fd4bc627ac32560e19d48988b9a5ba",
    },
    "ggml.dll": {
        "bytes": 68608,
        "sha256": "fd5da3e3a763edaf880236dfdba55148153a5aa0fbc42913dc2a4c663b040ebd",
    },
    "ggml-base.dll": {
        "bytes": 681472,
        "sha256": "698e0d6312ff376245669375fd1b922603e76432c61bb929571d4f12e7da84f4",
    },
    "ggml-cpu.dll": {
        "bytes": 1063424,
        "sha256": "28a17fff74240bb094cd17f03a7e3d64da8e7cbc74e5c8266611056df5fe7633",
    },
    "ggml-vulkan.dll": {
        "bytes": 52704256,
        "sha256": "25f9c5f74675b48b7cd909e48f07f74e5653480001fd544b31e96413ec50d6af",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def executable(name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    path = BIN / f"{name}{suffix}"
    require(path.is_file(), f"missing release executable: {path}")
    return path

def assert_release_binaries() -> None:
    for name, expected in EXPECTED_RELEASE_BINARIES.items():
        path = BIN / name
        require(path.is_file(), f"missing pinned release binary: {path}")
        require(path.stat().st_size == expected["bytes"],
                f"pinned release binary size changed: {name}")
        require(sha256(path) == expected["sha256"],
                f"pinned release binary hash changed: {name}")



def parse_json_line(stdout: bytes, command_name: str) -> dict[str, Any]:
    for raw_line in reversed(stdout.splitlines()):
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise RuntimeError(f"{command_name} emitted no JSON receipt")


def run_command(records: list[dict[str, Any]], name: str, argv: list[Path | str],
                timeout: float = 180.0) -> tuple[dict[str, Any], str]:
    command = [str(item) for item in argv]
    assert_release_binaries()
    executable_path = Path(command[0]).resolve()
    if (executable_path.parent != BIN.resolve()
            or executable_path.name not in EXPECTED_RELEASE_BINARIES):
        raise RuntimeError(f"{name} executable is outside the pinned release set")
    expected_executable = EXPECTED_RELEASE_BINARIES[executable_path.name]
    executable_bytes = executable_path.stat().st_size
    executable_sha256 = sha256(executable_path)
    require(
        executable_bytes == expected_executable["bytes"]
        and executable_sha256 == expected_executable["sha256"],
        f"{name} executable does not match its source-pinned release digest",
    )
    completed = subprocess.run(
        command,
        cwd=BIN,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    require(
        executable_path.is_file()
        and executable_path.stat().st_size == executable_bytes
        and sha256(executable_path) == executable_sha256,
        f"{name} executable changed while it was running",
    )
    stdout_text = completed.stdout.decode("utf-8", errors="replace")
    stderr_text = completed.stderr.decode("utf-8", errors="replace")
    records.append({
        "name": name,
        "argv": [relative(executable_path)] + command[1:],
        "executable_bytes": executable_bytes,
        "executable_sha256": executable_sha256,
        "expected_executable_bytes": expected_executable["bytes"],
        "expected_executable_sha256": expected_executable["sha256"],
        "returncode": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        "stdout_tail": stdout_text.splitlines()[-8:],
        "stderr_tail": stderr_text.splitlines()[-12:],
    })
    require(completed.returncode == 0,
            f"{name} exited {completed.returncode}: {stderr_text[-1000:]}")
    return parse_json_line(completed.stdout, name), stdout_text + "\n" + stderr_text


def verify_contract() -> dict[str, Any]:
    contract_path = FIXTURE / "contract.json"
    require(sha256(contract_path) == CONTRACT_FILE_SHA256,
            "canonical contract artifact hash changed")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    require(contract.get("schema") == "cassi.qi.native-contract.v1",
            "wrong canonical contract schema")
    require(contract.get("contract_sha256") == CONTRACT_SHA256,
            "canonical contract hash changed")
    require(contract.get("checkpoint", {}).get("sha256") == CHECKPOINT_SHA256,
            "canonical checkpoint file hash changed")
    require(contract.get("checkpoint", {}).get("state_sha256") == CHECKPOINT_STATE_SHA256,
            "canonical checkpoint state hash changed")
    require(contract.get("layout", {}).get("state_shape_native") == [1, 4, 6144, 9],
            "native state layout changed")
    require(contract.get("layout", {}).get("state_shape_python") == [4, 55296, 1],
            "Python state layout changed")
    require(contract.get("transition", {}).get("operator") == "ggml_cassi_qi_field_step.v2",
            "native bridge operator changed")
    for item in contract.get("arrays", {}).values():
        path = FIXTURE / item["path"]
        require(path.stat().st_size == item["bytes"], f"fixture size changed: {path.name}")
        require(sha256(path) == item["sha256"], f"fixture hash changed: {path.name}")
    return contract


def verify_release(model: Path, fixture: Path, receipt_path: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    require(model.is_file(), f"missing verification model: {model}")
    model_hash = sha256(model)
    require(model_hash == MODEL_SHA256, "0.8B verification model hash changed")
    contract = verify_contract()
    state = fixture / "state-h0.f32"
    require(state.stat().st_size == STATE_BYTES, "canonical native state byte count changed")
    release_binaries = [BIN / name for name in EXPECTED_RELEASE_BINARIES]
    assert_release_binaries()
    runtime_binaries = {
        relative(path): dict(EXPECTED_RELEASE_BINARIES[path.name])
        for path in release_binaries
    }

    canonical, canonical_log = run_command(
        records,
        "canonical_cpu_vulkan_parity",
        [executable("test-cassi-qi-canonical"), fixture],
    )
    require(canonical.get("schema") == "cassi.qi.native-parity.v1", "wrong parity schema")
    require(canonical.get("verdict") == "PASS", "canonical parity did not pass")
    require(float(canonical["cpu_python_max_abs"]) <= 5.0e-5, "CPU/oracle parity failed")
    require(float(canonical["vulkan_python_max_abs"]) <= 5.0e-3,
            "Vulkan/oracle parity failed")
    require(float(canonical["cpu_vulkan_max_abs"]) <= 5.0e-3,
            "CPU/Vulkan parity failed")
    require(canonical.get("save_reload_exact") is True, "state save/reload was not exact")
    require("AMD Radeon RX 7900 XTX" in canonical_log,
            "canonical test did not use the RX 7900 XTX Vulkan device")

    legacy, legacy_log = run_command(
        records,
        "native_qi_stress",
        [executable("test-cassi-qi-field")],
        timeout=300.0,
    )
    require(legacy.get("events") == 10000, "native stress event count changed")
    require(float(legacy["one_event_max_abs_diff"]) <= 1.0e-4,
            "one-event CPU/Vulkan stress parity failed")
    require(float(legacy["max_abs_diff"]) <= 5.0e-3,
            "10k-event CPU/Vulkan stress parity failed")
    require("AMD Radeon RX 7900 XTX" in legacy_log,
            "native stress did not use the RX 7900 XTX Vulkan device")

    rungs: list[dict[str, Any]] = []
    field_layers = [12, 12, 12, 13, 12, 12, 12]
    for displacement, field_layer in enumerate(field_layers):
        rung, log = run_command(
            records,
            f"qwen_displacement_{displacement}",
            [
                executable("test-cassi-qi-qwen"),
                model,
                state,
                "gpu",
                str(field_layer),
                str(displacement),
            ],
        )
        require(rung.get("schema") == "cassi.qi.qwen-displacement.v1",
                f"rung {displacement} returned wrong schema")
        require(rung.get("verdict") == "PASS", f"rung {displacement} did not pass")
        require(rung.get("null_graph_nodes_fail_closed") is True,
                f"rung {displacement} null graph query did not fail closed")
        require(rung.get("backend") == "gpu", f"rung {displacement} was not GPU-backed")
        require(rung.get("displacement") == displacement,
                f"rung {displacement} returned the wrong level")
        require(rung.get("state_floats") == 221184,
                f"rung {displacement} returned the wrong state size")
        require(math.isfinite(float(rung["state_max_abs_delta"]))
                and float(rung["state_max_abs_delta"]) > 0.0,
                f"rung {displacement} did not advance the field")
        require(rung["state_before_fnv1a"] != rung["state_after_fnv1a"],
                f"rung {displacement} field hash did not change")
        require(math.isfinite(float(rung["logit_max_abs"])),
                f"rung {displacement} logits were not finite")
        require("AMD Radeon RX 7900 XTX" in log,
                f"rung {displacement} did not use the RX 7900 XTX")
        graph_nodes = int(rung.get("graph_nodes", -1))
        require(graph_nodes > 0,
                f"rung {displacement} returned no graph-node evidence")
        rung["field_layer"] = field_layer
        rungs.append(rung)

    require(rungs[0]["selected"] == rungs[0]["qwen_top1"],
            "rung 0 did not preserve Qwen selection")
    require(rungs[0]["qwen_top1"] != rungs[0]["field_full"],
            "canonical field choice did not differ from Qwen at rung 0")
    require(rungs[1]["candidate_changed"] is True
            and rungs[1]["selected"] == rungs[1]["field_candidate"],
            "rung 1 candidate ownership was not field-conditioned")
    for displacement in range(2, 7):
        require(rungs[displacement]["selected"] == rungs[displacement]["field_full"],
                f"rung {displacement} did not select the full-vocabulary field argmax")
    require(rungs[3]["graph_nodes"] < rungs[0]["graph_nodes"],
            "rung 3 did not remove recurrent-state graph work")
    require(rungs[4]["graph_nodes"] < rungs[3]["graph_nodes"],
            "rung 4 did not remove attention/KV graph work")
    require(rungs[5]["graph_nodes"] < rungs[4]["graph_nodes"],
            "rung 5 did not remove full transformer-block graph work")
    require(rungs[6]["graph_nodes"] <= rungs[5]["graph_nodes"],
            "rung 6 did not preserve the model-head bypass")
    require(rungs[6]["qwen_top1"] == rungs[6]["field_full"]
            and float(rungs[6]["field_logit_max_abs_error"]) <= 1.0e-5,
            "rung 6 logits are not exactly field-owned")

    coupled, coupled_log = run_command(
        records,
        "production_coupled_runtime",
        [
            executable("cassi-qwen"),
            "--model", model,
            "--state", state,
            "--out-state", COUPLED_STATE,
            "--mode", "coupled",
            "--prompt", "Cassi",
            "--tokens", "2",
            "--gpu-layers", "99",
            "--field-layer", "12",
        ],
    )
    require(coupled.get("schema") == "cassi.qi.native-runtime.v1"
            and coupled.get("verdict") == "PASS", "coupled runtime did not pass")
    require(coupled.get("mode") == "coupled", "coupled runtime returned wrong mode")
    require(coupled.get("sampler") == "llama_sampler_greedy_over_field_logits",
            "coupled runtime did not use the upstream greedy sampler over field logits")
    require(coupled.get("qwen_forward_passes") == 3,
            "coupled runtime returned the wrong Qwen forward count")
    require(coupled["state_before_fnv1a"] != coupled["state_after_fnv1a"],
            "coupled runtime did not advance the field")
    require(COUPLED_STATE.stat().st_size == STATE_BYTES,
            "coupled runtime wrote the wrong state size")
    require("AMD Radeon RX 7900 XTX" in coupled_log,
            "coupled runtime did not use the RX 7900 XTX")

    field, field_log = run_command(
        records,
        "production_field_only_runtime",
        [
            executable("cassi-qwen"),
            "--model", model,
            "--state", state,
            "--out-state", FIELD_STATE,
            "--mode", "field",
            "--prompt", "Cassi",
            "--tokens", "2",
            "--gpu-layers", "0",
            "--field-layer", "12",
        ],
    )
    require(field.get("schema") == "cassi.qi.native-runtime.v1"
            and field.get("verdict") == "PASS", "field-only runtime did not pass")
    require(field.get("mode") == "field" and field.get("vocab_only") is True,
            "field-only runtime did not use vocab-only loading")
    require(field.get("token_sense") == "fixed_64_mode_hash_v1",
            "field-only token-sense law changed")
    require(field.get("qwen_forward_passes") == 0
            and field.get("model_logits_read") == 0
            and field.get("qwen_tensor_bytes_loaded") == 0,
            "field-only runtime touched Qwen execution state")
    require(int(field.get("gguf_tensor_bytes_declared", 0)) > 0,
            "field-only receipt did not distinguish declared from loaded tensor bytes")
    require(field["state_before_fnv1a"] != field["state_after_fnv1a"],
            "field-only runtime did not advance the field")
    require(FIELD_STATE.stat().st_size == STATE_BYTES,
            "field-only runtime wrote the wrong state size")
    require("vocab only - skipping tensors" in field_log,
            "field-only runtime emitted no skipped-tensor evidence")

    decision_scopes = (
        "Qwen owns the measured token decision",
        "field owns selection within the Qwen top-64 candidate set",
        "field owns selection over the complete vocabulary",
        "field owns complete-vocabulary selection; one selected recurrent state write is omitted",
        "field owns complete-vocabulary selection; attention/recurrent/KV execution is omitted in blocks 12-23",
        "field owns complete-vocabulary selection; complete transformer execution is omitted in blocks 12-23",
        "field owns exact output logits and selection; blocks 12-23, output norm, and tied output projection are omitted",
    )
    state_writes_skipped = (
        [],
        [],
        [],
        ["selected delta-net convolution/SSM recurrent write"],
        ["attention, recurrent, and KV updates in blocks 12-23"],
        ["all native state reads and writes in blocks 12-23"],
        ["all native state reads and writes in blocks 12-23"],
    )
    weight_regions_not_executed = (
        [],
        [],
        [],
        [],
        ["attention/recurrent weights in blocks 12-23"],
        ["all transformer weights in blocks 12-23"],
        [
            "all transformer weights in blocks 12-23",
            "output_norm.weight",
            "tied token_embd.weight output projection",
        ],
    )
    declared_tensor_bytes = int(field["gguf_tensor_bytes_declared"])
    rung_accounting: list[dict[str, Any]] = []
    for displacement, rung in enumerate(rungs):
        rung_accounting.append({
            "displacement": displacement,
            "measured_tokens": 1,
            "field_owned_token_decisions": 0 if displacement == 0 else 1,
            "decision_scope": decision_scopes[displacement],
            "evidence_classification": {
                "graph_nodes": "runtime_measured",
                "token_decisions": "runtime_measured",
                "state_write_regions": "reserved_graph_contract",
                "weight_regions": "reserved_graph_contract",
                "runtime_byte_touches": "unmeasured",
            },
            "graph_nodes": rung["graph_nodes"],
            "graph_nodes_removed_from_level_0": (
                rungs[0]["graph_nodes"] - rung["graph_nodes"]
            ),
            "native_dynamic_state": {
                "allocation_bytes_removed": 0,
                "remaining_allocated_bytes": None,
                "remaining_measurement": (
                    "not byte-instrumented; the coupled context allocation remains"
                ),
                "writes_skipped": state_writes_skipped[displacement],
            },
            "qwen_weights": {
                "gguf_tensor_bytes_declared": declared_tensor_bytes,
                "load_scope": "full model loaded for every coupled displacement rung",
                "bytes_touched_per_token": None,
                "touch_measurement": (
                    "not byte-instrumented; regions are excluded by the "
                    "reserved displacement graph; runtime byte touches are not measured"
                ),
                "regions_not_executed": weight_regions_not_executed[displacement],
            },
        })

    assert_release_binaries()

    receipt = {
        "schema": "cassi.qi.native-release-verification.v1",
        "verdict": "PASS",
        "verification_target": {
            "model": relative(model),
            "model_sha256": model_hash,
            "model_bytes": model.stat().st_size,
            "source_repository": "https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF",
            "source_lfs_sha256": MODEL_SHA256,
            "model_role": "small_exact_native_verification_target",
            "gpu": "AMD Radeon RX 7900 XTX",
            "llama_cli_invocations": 0,
            "qwen_27b_invocations": 0,
        },
        "canonical_contract": {
            "path": relative(fixture / "contract.json"),
            "contract_sha256": contract["contract_sha256"],
            "contract_file_sha256": CONTRACT_FILE_SHA256,
            "checkpoint_sha256": contract["checkpoint"]["sha256"],
            "checkpoint_state_sha256": contract["checkpoint"]["state_sha256"],
            "python_layout": contract["layout"]["state_shape_python"],
            "native_layout": contract["layout"]["state_shape_native"],
            "transition_operator": contract["transition"]["operator"],
            "transition_scope": "defined native bridge law; not numerical parity with QiFieldController.cycle",
        },
        "canonical_parity": canonical,
        "native_stress": legacy,
        "displacement_rungs": rungs,
        "production_coupled": coupled,
        "production_field_only": field,
        "ownership_accounting": {
            "coupled_displacement_rungs": rung_accounting,
            "production_coupled": {
                "measured_tokens": 2,
                "field_owned_token_decisions": 2,
                "field_state_bytes": STATE_BYTES,
                "qwen_forward_passes": coupled["qwen_forward_passes"],
                "qwen_dynamic_state_bytes_remaining": None,
                "remaining_measurement": "not byte-instrumented",
            },
            "production_field_only": {
                "measured_tokens": 2,
                "field_owned_token_decisions": 2,
                "field_state_bytes": STATE_BYTES,
                "qwen_dynamic_state_bytes_allocated": 0,
                "qwen_tensor_bytes_loaded": field["qwen_tensor_bytes_loaded"],
                "qwen_weight_bytes_touched_per_token": 0,
                "qwen_forward_passes": field["qwen_forward_passes"],
                "model_logits_read": field["model_logits_read"],
                "gguf_tensor_bytes_declared": declared_tensor_bytes,
            },
        },
        "artifacts": {
            "coupled_state": {
                "path": relative(COUPLED_STATE),
                "bytes": COUPLED_STATE.stat().st_size,
                "sha256": sha256(COUPLED_STATE),
            },
            "field_state": {
                "path": relative(FIELD_STATE),
                "bytes": FIELD_STATE.stat().st_size,
                "sha256": sha256(FIELD_STATE),
            },
        },
        "commands": records,
        "runtime_binaries": runtime_binaries,
    }
    atomic_write(receipt_path, receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = verify_release(args.model.resolve(), args.fixture.resolve(),
                                 args.receipt.resolve())
    except Exception as error:
        receipt = {
            "schema": "cassi.qi.native-release-verification.v1",
            "verdict": "FAIL",
            "error": f"{type(error).__name__}: {error}",
        }
        atomic_write(args.receipt.resolve(), receipt)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
