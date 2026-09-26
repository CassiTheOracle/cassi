#!/usr/bin/env python3
"""Run and independently verify native Cassi apprenticeship receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np

RECEIPT_KEYS = {
    "schema", "profile", "model_sha256", "profile_sha256", "field_sha256",
    "checkpoint_sha256", "field_revision", "field_geometry", "field_device",
    "native_backends", "teacher_policy", "route_policy", "execution_topology",
    "field_graph_outputs_live", "single_qwen_graph_intervention", "status",
    "error_code", "durable", "stats", "services", "tokens",
}
NATIVE_ZERO_KEYS = {
    "native_service_calls", "full_teacher_queries", "teacher_failures",
    "teacher_audits", "audit_mismatches", "native_prefill_tokens",
    "native_context_creations", "native_logits_reads", "native_replay_tokens",
    "native_decode_tokens", "native_ggml_nodes_executed",
    "native_output_rows_computed", "logical_weight_bytes",
    "loaded_model_tensor_bytes", "native_cache_bytes_peak",
    "native_cache_bytes_remaining",
}


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_last_json(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    raise RuntimeError("command output contains no JSON object")


def read_last_jsonl(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing receipt file: {path}")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"empty receipt file: {path}")
    value = json.loads(lines[-1])
    if not isinstance(value, dict):
        raise RuntimeError(f"receipt is not an object: {path}")
    return value


def verify_checkpoint(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 184:
        raise RuntimeError(f"checkpoint is too short: {path}")
    header = struct.unpack_from("<8sIIQIIIIQQ", data, 0)
    magic, version, scales, modes, layers, embedding_width, vocabulary_size, pages, field_bytes, revision = header
    if magic != b"CASSIAP1" or version != 1 or scales != 4:
        raise RuntimeError(f"checkpoint header is invalid: {path}")
    if revision == (1 << 64) - 1:
        raise RuntimeError(f"checkpoint revision is terminal: {path}")
    model_sha = data[56:88].hex()
    profile_sha = data[88:120].hex()
    offset = 120
    page_records: list[dict[str, int]] = []
    for _ in range(pages):
        kind, layer, width, entries, mode_offset = struct.unpack_from("<IiIIQ", data, offset)
        offset += 24
        page_records.append({
            "kind": kind,
            "layer": layer,
            "width": width,
            "entries": entries,
            "mode_offset": mode_offset,
        })
    expected_size = offset + field_bytes + 64
    if len(data) != expected_size:
        raise RuntimeError(
            f"checkpoint size mismatch: actual={len(data)} expected={expected_size}")
    payload = data[offset:offset + field_bytes]
    payload_sha = hashlib.sha256(payload).digest()
    stored_payload_sha = data[offset + field_bytes:offset + field_bytes + 32]
    image_sha = hashlib.sha256(data[:-32]).digest()
    stored_image_sha = data[-32:]
    if payload_sha != stored_payload_sha or image_sha != stored_image_sha:
        raise RuntimeError(f"checkpoint checksum mismatch: {path}")
    if field_bytes != scales * 9 * modes * 4:
        raise RuntimeError(f"checkpoint field geometry is inconsistent: {path}")

    values = np.frombuffer(payload, dtype="<f4")
    if values.size != scales * 9 * modes or not np.isfinite(values).all():
        raise RuntimeError(f"checkpoint field payload is nonfinite or malformed: {path}")
    field = values.reshape((scales, 9, modes))
    for page in page_records:
        begin = page["mode_offset"]
        end = begin + page["width"]
        if begin < 0 or end > modes or np.any(field[:, :, begin:end] != 0.0):
            raise RuntimeError(f"checkpoint persists nonzero transient state: {path}")

    return {
        "path": str(path.resolve()),
        "file_bytes": len(data),
        "file_sha256": hashlib.sha256(data).hexdigest(),
        "checkpoint_sha256": image_sha.hex(),
        "field_sha256": payload_sha.hex(),
        "model_sha256": model_sha,
        "profile_sha256": profile_sha,
        "revision": revision,
        "scales": scales,
        "modes": modes,
        "layers": layers,
        "embedding_width": embedding_width,
        "vocabulary_size": vocabulary_size,
        "field_bytes": field_bytes,
        "pages": page_records,
    }


def verify_receipt(
    receipt: dict[str, Any],
    model_sha: str,
    checkpoint: dict[str, Any] | None,
) -> None:
    missing = RECEIPT_KEYS - receipt.keys()
    extra = receipt.keys() - RECEIPT_KEYS
    if missing or extra:
        raise RuntimeError(f"receipt keys differ: missing={sorted(missing)} extra={sorted(extra)}")
    if receipt["schema"] != "cassi.apprentice.receipt.v1":
        raise RuntimeError("receipt schema mismatch")
    if receipt["profile"] != "cassi.qi.apprentice-engram.v1":
        raise RuntimeError("receipt profile mismatch")
    if receipt["model_sha256"] != model_sha:
        raise RuntimeError("receipt model hash differs from the independently hashed GGUF")
    if not receipt["field_graph_outputs_live"] or receipt["single_qwen_graph_intervention"]:
        raise RuntimeError("receipt misstates the off-graph live field topology")
    stats = receipt["stats"]
    committed = int(stats["committed_tokens"])
    categories = sum(int(stats[key]) for key in (
        "field_exact_tokens", "field_interpolated_tokens", "teacher_guided_tokens"))
    if committed != categories or committed != len(receipt["tokens"]):
        raise RuntimeError("receipt token ownership categories do not partition committed tokens")
    if len(receipt["services"]) != int(receipt["field_geometry"]["pages"]):
        raise RuntimeError("receipt service records do not match page geometry")
    native_backends = receipt["native_backends"]
    if native_backends is not None:
        if (not isinstance(native_backends, list) or
                any(not isinstance(name, str) or not name for name in native_backends) or
                native_backends != sorted(native_backends)):
            raise RuntimeError("receipt native backends are not a known sorted list")
    if checkpoint is not None:
        expected_pairs = {
            "checkpoint_sha256": checkpoint["checkpoint_sha256"],
            "field_sha256": checkpoint["field_sha256"],
            "profile_sha256": checkpoint["profile_sha256"],
            "field_revision": checkpoint["revision"],
        }
        for key, expected in expected_pairs.items():
            if receipt[key] != expected:
                raise RuntimeError(f"receipt {key} differs from checkpoint: {receipt[key]} != {expected}")
        geometry = receipt["field_geometry"]
        for key in ("scales", "layers", "embedding_width", "vocabulary_size", "pages"):
            expected = len(checkpoint["pages"]) if key == "pages" else checkpoint[key]
            if int(geometry[key]) != int(expected):
                raise RuntimeError(f"receipt field geometry differs at {key}")


def verify_native_independence(receipt: dict[str, Any]) -> None:
    stats = receipt["stats"]
    nonzero = {key: stats[key] for key in NATIVE_ZERO_KEYS if int(stats[key]) != 0}
    if nonzero:
        raise RuntimeError(f"teacher-free receipt still depends on native Qwen work: {nonzero}")
    if int(stats["field_observations"]) != 0:
        raise RuntimeError("teacher-free replay changed retained learning")
    if receipt["native_backends"] != []:
        raise RuntimeError(f"vocab-only replay does not prove an empty native backend set: {receipt['native_backends']}")
    if receipt["teacher_policy"] != "never":
        raise RuntimeError("teacher-free receipt has the wrong teacher policy")


class Driver:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.model = Path(args.model).resolve()
        self.binary_dir = Path(args.binary_dir).resolve()
        self.output = Path(args.out).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.commands_dir = self.output / "commands"
        self.commands_dir.mkdir(parents=True, exist_ok=True)
        self.model_sha = sha256_path(self.model)
        self.command_records: list[dict[str, Any]] = []
        self.transfer_result: dict[str, Any] | None = None

        required = [
            "cassi-qwen.exe",
            "test-cassi-apprentice-qwen.exe",
            "test-cassi-apprentice-owner.exe",
        ]
        for name in required:
            if not (self.binary_dir / name).is_file():
                raise RuntimeError(f"required native binary is missing: {self.binary_dir / name}")
        hashes: dict[str, str] = {}
        for path in sorted(self.binary_dir.iterdir(), key=lambda value: value.name.lower()):
            if path.suffix.lower() == ".dll" or path.name in required:
                hashes[path.name] = sha256_path(path)
        write_json(self.output / "build-identity.json", {
            "binary_dir": str(self.binary_dir),
            "files": hashes,
            "model": str(self.model),
            "model_sha256": self.model_sha,
        })

    def run(
        self,
        label: str,
        argv: Iterable[str | os.PathLike[str]],
        *,
        allow_failure: bool = False,
        timeout: int = 7200,
    ) -> subprocess.CompletedProcess[str]:
        command = [str(value) for value in argv]
        started = time.time()
        completed = subprocess.run(
            command,
            cwd=self.binary_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        record = {
            "label": label,
            "command": command,
            "cwd": str(self.binary_dir),
            "returncode": completed.returncode,
            "wall_seconds": time.time() - started,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        self.command_records.append(record)
        write_json(self.commands_dir / f"{label}.json", record)
        if completed.returncode != 0 and not allow_failure:
            raise RuntimeError(
                f"{label} failed with exit code {completed.returncode}; see {self.commands_dir / f'{label}.json'}")
        return completed

    def direct_request(
        self,
        label: str,
        state: Path,
        prompt: str,
        tokens: int,
        teacher: str,
        *,
        initialize: bool = False,
        allow_failure: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any], subprocess.CompletedProcess[str]]:
        receipt_path = self.output / "receipts" / f"{label}.jsonl"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.unlink(missing_ok=True)
        command = [
            self.binary_dir / "cassi-qwen.exe",
            "--mode", "apprentice",
            "--model", self.model,
            "--prompt", prompt,
            "--tokens", str(tokens),
            "--gpu-layers", str(self.args.gpu_layers),
            "--ctx-size", "128",
            "--cassi-apprentice-state", state,
            "--cassi-apprentice-memory-mib", str(self.args.memory_mib),
            "--cassi-apprentice-device", self.args.field_device,
            "--cassi-apprentice-teacher", teacher,
            "--cassi-apprentice-route", "auto",
            "--cassi-apprentice-audit-interval", "0",
            "--cassi-apprentice-receipt", receipt_path,
        ]
        if initialize:
            command.append("--cassi-apprentice-init")
        completed = self.run(label, command, allow_failure=allow_failure)
        receipt = read_last_jsonl(receipt_path)
        checkpoint = verify_checkpoint(state)
        verify_receipt(receipt, self.model_sha, checkpoint)
        return receipt, checkpoint, completed

    def transfer(self) -> dict[str, Any]:
        if self.transfer_result is not None:
            return self.transfer_result
        directory = self.output / "transfer"
        directory.mkdir(parents=True, exist_ok=True)
        state = directory / "knowledge.cqfs"
        for suffix in ("", ".previous", ".lock"):
            Path(str(state) + suffix).unlink(missing_ok=True)

        prompts = {
            "A": "Continue briefly. Label A:",
            "B": "Continue briefly. Label B:",
        }
        learned: dict[str, list[int]] = {}
        previous_checkpoint: str | None = None
        runs: list[dict[str, Any]] = []
        first = True
        for pass_index in range(2):
            for label, prompt in prompts.items():
                receipt, checkpoint, _ = self.direct_request(
                    f"transfer-teach-{label.lower()}-{pass_index + 1}",
                    state,
                    prompt,
                    8,
                    "always",
                    initialize=first,
                )
                first = False
                if receipt["status"] != "complete" or int(receipt["stats"]["full_teacher_queries"]) == 0:
                    raise RuntimeError("transfer teaching did not use the declared full teacher")
                if previous_checkpoint == checkpoint["checkpoint_sha256"]:
                    raise RuntimeError("teaching did not change checkpoint identity")
                previous_checkpoint = checkpoint["checkpoint_sha256"]
                tokens = [int(value) for value in receipt["tokens"]]
                if label in learned and learned[label] != tokens:
                    raise RuntimeError(f"teacher trajectory {label} was not deterministic")
                learned[label] = tokens
                runs.append({
                    "label": label,
                    "pass": pass_index + 1,
                    "tokens": tokens,
                    "field_revision": receipt["field_revision"],
                    "checkpoint_sha256": checkpoint["checkpoint_sha256"],
                    "field_observations": receipt["stats"]["field_observations"],
                    "native_ggml_nodes_executed": receipt["stats"]["native_ggml_nodes_executed"],
                    "logical_weight_bytes": receipt["stats"]["logical_weight_bytes"],
                })

        trained_bytes = state.read_bytes()
        replay: dict[str, Any] = {}
        for label, prompt in prompts.items():
            before = state.read_bytes()
            receipt, checkpoint, _ = self.direct_request(
                f"transfer-replay-{label.lower()}", state, prompt, 8, "never")
            if receipt["status"] != "complete" or [int(value) for value in receipt["tokens"]] != learned[label]:
                raise RuntimeError(f"teacher-free trajectory {label} did not reproduce its teacher IDs")
            verify_native_independence(receipt)
            after = state.read_bytes()
            if before != after or trained_bytes != after:
                raise RuntimeError("teacher-free replay changed the checkpoint image")
            replay[label] = {
                "tokens": receipt["tokens"],
                "field_exact_tokens": receipt["stats"]["field_exact_tokens"],
                "field_interpolated_tokens": receipt["stats"]["field_interpolated_tokens"],
                "checkpoint_sha256": checkpoint["checkpoint_sha256"],
                "native_zero": True,
            }

        result = {
            "schema": "cassi.apprentice.transfer-evidence.v1",
            "verdict": "PASS",
            "state": str(state),
            "prompts": prompts,
            "learned": learned,
            "teaching_runs": runs,
            "teacher_free_replay": replay,
            "checkpoint": verify_checkpoint(state),
        }
        write_json(directory / "result.json", result)
        self.transfer_result = result
        return result

    def pipeline(self) -> dict[str, Any]:
        native_device = "gpu" if self.args.gpu_layers > 0 else "cpu"
        directory = self.output / "pipeline"
        directory.mkdir(parents=True, exist_ok=True)
        completed = self.run("pipeline", [
            self.binary_dir / "test-cassi-apprentice-qwen.exe",
            self.model,
            native_device,
            self.args.field_device,
            directory,
            str(self.args.memory_mib),
            "--case", "pipeline",
        ])
        result = parse_last_json(completed.stdout)
        if result.get("verdict") != "PASS" or result.get("case") != "pipeline":
            raise RuntimeError("native pipeline harness did not produce a passing receipt")
        field_bytes = int(result["field_bytes"])
        admission_bytes = int(result["pending_admission_payload_bytes_peak"])
        rollback_bytes = int(result["pending_rollback_bytes_peak"])
        if not 0 < admission_bytes < rollback_bytes == field_bytes:
            raise RuntimeError(
                "native pipeline did not keep pre-accept staging below the accept-time rollback image"
            )
        write_json(directory / "result.json", result)
        return result

    def lifecycle(self) -> dict[str, Any]:
        native_device = "gpu" if self.args.gpu_layers > 0 else "cpu"
        directory = self.output / "lifecycle"
        directory.mkdir(parents=True, exist_ok=True)
        completed = self.run("lifecycle", [
            self.binary_dir / "test-cassi-apprentice-qwen.exe",
            self.model,
            native_device,
            self.args.field_device,
            directory,
            str(self.args.memory_mib),
            "--case", "lifecycle",
        ])
        result = parse_last_json(completed.stdout)
        if result.get("verdict") != "PASS":
            raise RuntimeError("native lifecycle harness did not pass")
        field_bytes = int(result["field_bytes"])
        admission_bytes = int(result["pending_admission_payload_bytes_peak"])
        rollback_bytes = int(result["pending_rollback_bytes_peak"])
        revision_rollback_bytes = int(result["revision_overflow_rollback_bytes_peak"])
        if not 0 < admission_bytes < rollback_bytes == field_bytes or revision_rollback_bytes != 0:
            raise RuntimeError(
                "native lifecycle did not preserve bounded proposal staging, exact accept-time rollback, "
                "and allocation-free revision preflight"
            )
        write_json(directory / "result.json", result)
        return result

    def owner(self, scenario: str) -> dict[str, Any]:
        directory = self.output / "owner"
        directory.mkdir(parents=True, exist_ok=True)
        completed = self.run(f"owner-{scenario}", [
            self.binary_dir / "test-cassi-apprentice-owner.exe",
            self.model,
            directory,
            self.args.field_device,
        ])
        result = parse_last_json(completed.stdout)
        if result.get("verdict") != "PASS":
            raise RuntimeError("owner persistence harness did not pass")
        result["covers"] = ["checkpoint", "lock", "publication"]
        result["requested_scenario"] = scenario
        write_json(directory / "result.json", result)
        return result

    def generalization(self) -> dict[str, Any]:
        transfer = self.transfer()
        source_state = Path(transfer["state"])
        learned = transfer["learned"]
        directory = self.output / "generalization"
        directory.mkdir(parents=True, exist_ok=True)
        variants = {
            "heldout_casing": "continue briefly. label a:",
            "heldout_paraphrase": "Please continue briefly. Label A:",
            "same_last_token_different_context": "Reverse the instruction. Label A:",
            "role_reversal": "Answer as the label, then continue. Label B:",
        }
        rows: list[dict[str, Any]] = []
        for name, prompt in variants.items():
            never_state = directory / f"{name}-never.cqfs"
            teacher_state = directory / f"{name}-teacher.cqfs"
            shutil.copyfile(source_state, never_state)
            shutil.copyfile(source_state, teacher_state)
            never_receipt, _, never_process = self.direct_request(
                f"generalization-{name}-never",
                never_state,
                prompt,
                2,
                "never",
                allow_failure=True,
            )
            verify_native_independence(never_receipt)
            teacher_receipt, _, _ = self.direct_request(
                f"generalization-{name}-teacher",
                teacher_state,
                prompt,
                2,
                "always",
            )
            predicted = [int(value) for value in never_receipt["tokens"]]
            teacher = [int(value) for value in teacher_receipt["tokens"]]
            matching_prefix = 0
            for predicted_token, teacher_token in zip(predicted, teacher):
                if predicted_token != teacher_token:
                    break
                matching_prefix += 1
            rows.append({
                "case": name,
                "prompt": prompt,
                "status": never_receipt["status"],
                "error_code": never_receipt["error_code"],
                "predicted_tokens": predicted,
                "teacher_tokens": teacher,
                "matching_prefix_tokens": matching_prefix,
                "agreement": predicted == teacher and never_receipt["status"] == "complete",
                "teacher_free_returncode": never_process.returncode,
                "field_exact_tokens": never_receipt["stats"]["field_exact_tokens"],
                "field_interpolated_tokens": never_receipt["stats"]["field_interpolated_tokens"],
                "teacher_full_queries": teacher_receipt["stats"]["full_teacher_queries"],
                "engram_evictions": never_receipt["stats"]["engram_evictions"],
            })

        all_teacher_tokens = [token for sequence in learned.values() for token in sequence]
        frequency = max(set(all_teacher_tokens), key=all_teacher_tokens.count) if all_teacher_tokens else None
        controls = {
            "exact_trajectory": learned,
            "last_token": {"A": learned["A"][-1:] if learned["A"] else [], "B": learned["B"][-1:] if learned["B"] else []},
            "token_frequency": frequency,
            "shuffled_association": {"A": learned["B"], "B": learned["A"]},
        }
        result = {
            "schema": "cassi.apprentice.generalization-evidence.v1",
            "verdict": "MEASURED",
            "cases": rows,
            "controls": controls,
            "summary": {
                "teacher_agreement": sum(1 for row in rows if row["agreement"]),
                "field_emitted": sum(1 for row in rows if row["status"] == "complete"),
                "teacher_required": sum(
                    1 for row in rows if row["error_code"] == "apprentice_teacher_required"),
                "tested": len(rows),
            },
        }
        write_json(directory / "result.json", result)
        return result

    def execute(self) -> dict[str, Any]:
        scenario = self.args.scenario
        evidence: dict[str, Any] = {}
        if scenario in ("transfer", "all"):
            evidence["transfer"] = self.transfer()
        if scenario in ("pipeline", "all"):
            evidence["pipeline"] = self.pipeline()
        if scenario in ("generalization", "all"):
            evidence["generalization"] = self.generalization()
        if scenario in ("lifecycle", "all"):
            evidence["lifecycle"] = self.lifecycle()
        if scenario in ("checkpoint", "lock", "publication"):
            evidence[scenario] = self.owner(scenario)
        elif scenario == "all":
            evidence["owner"] = self.owner("all")

        result = {
            "schema": "cassi.apprentice.run.v1",
            "verdict": "PASS",
            "scenario": scenario,
            "model": str(self.model),
            "model_sha256": self.model_sha,
            "field_device": self.args.field_device,
            "gpu_layers": self.args.gpu_layers,
            "memory_mib": self.args.memory_mib,
            "evidence": evidence,
            "commands": [record["label"] for record in self.command_records],
        }
        write_json(self.output / "result.json", result)
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--field-device", choices=("CPU", "Vulkan0"), required=True)
    parser.add_argument("--gpu-layers", type=int, required=True)
    parser.add_argument("--memory-mib", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--binary-dir",
        default="native/llama.cpp/build-qi/bin/Release",
    )
    parser.add_argument(
        "--scenario",
        choices=("transfer", "pipeline", "generalization", "checkpoint", "lock", "publication", "lifecycle", "all"),
        default="all",
    )
    args = parser.parse_args()
    if args.gpu_layers < 0 or args.memory_mib <= 0:
        parser.error("--gpu-layers must be nonnegative and --memory-mib must be positive")
    return args


def main() -> int:
    try:
        args = parse_args()
        result = Driver(args).execute()
        print(json.dumps(result, separators=(",", ":")))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({
            "schema": "cassi.apprentice.run.v1",
            "verdict": "FAIL",
            "error": str(error),
        }, separators=(",", ":")), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
