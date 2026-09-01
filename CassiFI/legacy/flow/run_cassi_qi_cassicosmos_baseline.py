"""Freeze the real pre-adapter CassiCosmos battery and its raw identities.

This runner owns no Godot adapter behavior.  It invokes the existing
``verify/run_all.gd`` battery exactly as documented, captures the child-runner
bytes, copies every arm log emitted by this invocation, and writes a
content-addressed evidence bundle.  A missing executable/project is a blocked
run; no synthetic pass or replacement evidence is emitted.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes

SCHEMA = "cassi.qi-world-adapter-baseline-runner.v1"
RECEIPT_SCHEMA = "cassi.qi-world-adapter-baseline-receipt.v1"
COMMAND_SCHEMA = "cassi.qi-world-adapter-baseline-command.v1"
PROCESS_SCHEMA = "cassi.qi-world-adapter-baseline-process-receipt.v1"
TRACE_SCHEMA = "cassi.qi-world-adapter-baseline-trace.v1"
ANCHOR_SCHEMA = "cassi.qi-world-adapter-baseline-anchor.v1"
DIGEST_SCHEMA = "cassi.qi-world-adapter-baseline-digest-index.v1"
SOURCE_SCHEMA = "cassi.qi-world-adapter-baseline-source-inventory.v1"
SCENE_SCHEMA = "cassi.qi-world-adapter-baseline-scene-inventory.v1"

ROOT = Path(__file__).resolve().parent
COSMOS = (ROOT / "../CassiCosmos").resolve()
DIAG = ROOT / "_diag" / "cassi-qi-flow-w13c-final"
DEFAULT_TIMEOUT_SECONDS = 1_200
GODOT_RELATIVE = (
    Path("AppData/Local/Microsoft/WinGet/Packages/")
    / "GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe"
    / "Godot_v4.7.1-stable_mono_win64"
    / "Godot_v4.7.1-stable_mono_win64_console.exe"
)
ADAPTER_TARGETS = (
    "scripts/cassi_qi_world_adapter.gd",
    "scenes/qi_world_adapter.tscn",
    "scenes/verify_qi_world_adapter.tscn",
)
REQUIRED_INPUTS = (
    ("cassi_qi_world.py", ROOT / "cassi_qi_world.py"),
    ("cassi-qi-flow-development.json", ROOT / "cassi-qi-flow-development.json"),
    ("cassi-qi-flow-canonical-fixtures.json", ROOT / "cassi-qi-flow-canonical-fixtures.json"),
    ("../CassiCosmos/project.godot", COSMOS / "project.godot"),
    ("../CassiCosmos/verify/README.md", COSMOS / "verify" / "README.md"),
    ("../CassiCosmos/verify/run_all.gd", COSMOS / "verify" / "run_all.gd"),
    ("CassiFI/07-world-loop-and-transactions.md", ROOT / "CassiFI" / "07-world-loop-and-transactions.md"),
    ("CassiFI/10-work-packages.md", ROOT / "CassiFI" / "10-work-packages.md"),
    ("CassiFI/11-validation-gates.md", ROOT / "CassiFI" / "11-validation-gates.md"),
    ("CassiFI/13-requirements-registry.md", ROOT / "CassiFI" / "13-requirements-registry.md"),
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_write(path: Path, value: Any) -> str:
    raw = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return sha256(raw)


def file_entry(logical: str, path: Path, *, kind: str = "file") -> dict[str, Any]:
    if not path.is_file():
        return {"kind": kind, "path": logical, "exists": False, "byte_count": 0, "sha256": None}
    raw = path.read_bytes()
    return {"kind": kind, "path": logical, "exists": True, "byte_count": len(raw), "sha256": sha256(raw)}


def find_godot() -> Path | None:
    configured = os.environ.get("CASSI_GODOT_EXE")
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_file() else None
    path = Path.home() / GODOT_RELATIVE
    return path if path.is_file() else None


def load_brief(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != "cassi.qi-world-adapter-brief.v1":
        raise ValueError("brief schema mismatch")
    if value.get("pre_adapter_state") != "baseline-before-adapter-edit":
        raise ValueError("brief is not the pre-adapter brief")
    if value.get("adapter_config", {}).get("adapter_enabled") is not False:
        raise ValueError("adapter config must be default-off")
    if value.get("adapter_config", {}).get("second_qi_field") is not False:
        raise ValueError("second Qi field must be disabled")
    return value


def brief_identity(brief: dict[str, Any]) -> tuple[str, str]:
    input_descriptor = {
        "brief_id": brief["brief_id"],
        "brief_version": brief["brief_version"],
        "input_identities": brief["input_identities"],
        "adapter_config": brief["adapter_config"],
        "adapter_fixture": brief["adapter_fixture"],
        "godot_command": brief["battery_baseline"]["godot_command"],
        "scene_battery": brief["battery_baseline"]["scene_battery"],
    }
    input_sha = sha256(canonical_json_bytes(input_descriptor))
    brief_for_hash = dict(brief)
    brief_for_hash["baseline_input_sha256"] = ""
    brief_for_hash["brief_sha256"] = ""
    return input_sha, sha256(canonical_json_bytes(brief_for_hash))


def run_all_arms(run_all: Path) -> list[str]:
    text = run_all.read_text(encoding="utf-8", errors="strict")
    return re.findall(r'^\s*"([a-z0-9_]+)"\s*,?\s*$', text, re.MULTILINE)




def snapshot_arm_logs(log_dir: Path, arm_names: list[str]) -> dict[str, str]:
    """Record pre-run bytes so stale logs cannot be retained as this run's evidence."""
    snapshots: dict[str, str] = {}
    for index, name in enumerate(arm_names, 1):
        path = log_dir / f"arm{index:02d}_{name}.log"
        if path.is_file():
            snapshots[path.name] = sha256(path.read_bytes())
    return snapshots


def copy_arm_logs(
    log_dir: Path,
    arm_names: list[str],
    out_dir: Path,
    *,
    before_hashes: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    before_hashes = before_hashes or {}
    for index, name in enumerate(arm_names, 1):
        path = log_dir / f"arm{index:02d}_{name}.log"
        relative = f"arm_logs/{path.name}"
        if not path.is_file():
            entries.append(
                {
                    "path": relative,
                    "source": str(path),
                    "exists": False,
                    "emitted_this_run": False,
                    "byte_count": 0,
                    "sha256": None,
                }
            )
            continue
        raw = path.read_bytes()
        digest = sha256(raw)
        if before_hashes.get(path.name) == digest:
            # The file is present but was not changed by this invocation.  Do
            # not copy prior-run bytes into the immutable baseline bundle.
            entries.append(
                {
                    "path": relative,
                    "source": str(path),
                    "exists": False,
                    "source_exists": True,
                    "stale": True,
                    "emitted_this_run": False,
                    "byte_count": 0,
                    "sha256": None,
                }
            )
            continue
        target = out_dir / "arm_logs" / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        entries.append(
            {
                "path": relative,
                "source": str(path),
                "exists": True,
                "emitted_this_run": True,
                "byte_count": len(raw),
                "sha256": digest,
            }
        )
    return entries


def kill_process_tree(pid: int) -> dict[str, Any]:
    """Terminate the wrapper and every child arm on a timed-out Windows run."""
    if os.name != "nt":
        return {"method": "process.kill", "attempted": False, "reason": "non-windows"}
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
        output = result.stdout or b""
        return {
            "method": "taskkill",
            "attempted": True,
            "returncode": result.returncode,
            "output_sha256": sha256(output),
            "output_byte_count": len(output),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {"method": "taskkill", "attempted": True, "error": f"{type(exc).__name__}: {exc}"}


def source_inventory(brief: dict[str, Any], run_all: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    entries = [file_entry(logical, path) for logical, path in REQUIRED_INPUTS]
    for target in ADAPTER_TARGETS:
        entries.append(file_entry(f"../CassiCosmos/{target}", COSMOS / target, kind="authorized-adapter-target"))
    arm_names = run_all_arms(run_all) if run_all.is_file() else []
    scene_entries = [file_entry(f"../CassiCosmos/scenes/{name}.tscn", COSMOS / "scenes" / f"{name}.tscn", kind="battery-scene") for name in arm_names]
    source = {
        "schema": SOURCE_SCHEMA,
        "brief_id": brief["brief_id"],
        "pre_adapter": True,
        "entries": entries,
        "authorized_adapter_targets": list(ADAPTER_TARGETS),
    }
    scenes = {
        "schema": SCENE_SCHEMA,
        "brief_id": brief["brief_id"],
        "battery_script": file_entry("../CassiCosmos/verify/run_all.gd", run_all),
        "expected_arm_count": brief["battery_baseline"]["expected_arms"],
        "arm_names": arm_names,
        "entries": scene_entries,
    }
    return source, scenes


def decode_output_lines(raw: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines(keepends=True):
        text = line.decode("utf-8", errors="replace").rstrip("\r\n")
        row: dict[str, Any] = {"bytes_b64": base64.b64encode(line).decode("ascii"), "text": text}
        match = re.search(r"\[Battery\] arm (\d+)/(\d+) ([^:]+): (PASS|FAIL)", text)
        if match:
            row["event"] = "arm-result"
            row["arm_index"] = int(match.group(1))
            row["arm_count"] = int(match.group(2))
            row["arm_name"] = match.group(3).strip()
            row["result"] = match.group(4)
        elif text.startswith("[Battery] ") and (" PASS" in text or " FAILED" in text):
            row["event"] = "battery-summary"
        rows.append(row)
    return rows


def classify_unavailable(exc: BaseException) -> str:
    if isinstance(exc, (FileNotFoundError, PermissionError, subprocess.TimeoutExpired)):
        return "BLOCKED"
    return "FAILED"


def build_digest_index(raw_root: Path, files: Iterable[str]) -> tuple[dict[str, Any], str]:
    entries: dict[str, dict[str, Any]] = {}
    for rel in sorted(files):
        path = raw_root / rel
        raw = path.read_bytes()
        entries[rel] = {"byte_count": len(raw), "sha256": sha256(raw)}
    body = {"schema": DIGEST_SCHEMA, "files": entries, "artifact_root_sha256": ""}
    root_sha = sha256(canonical_json_bytes(body))
    body["artifact_root_sha256"] = root_sha
    return body, root_sha


def byte_verify(raw_root: Path, digest: dict[str, Any]) -> None:
    for rel, expected in digest["files"].items():
        raw = (raw_root / rel).read_bytes()
        if len(raw) != expected["byte_count"] or sha256(raw) != expected["sha256"]:
            raise RuntimeError(f"byte verification failed for {rel}")
    check = dict(digest)
    claimed = check.pop("artifact_root_sha256")
    check["artifact_root_sha256"] = ""
    if sha256(canonical_json_bytes(check)) != claimed:
        raise RuntimeError("artifact root hash verification failed")


def write_blocked(
    brief: dict[str, Any],
    brief_path: Path,
    reason: str,
    godot: Path | None,
    *,
    run_root: Path | None = None,
) -> Path:
    input_sha, _ = brief_identity(brief)
    run_root = run_root or DIAG / input_sha
    raw_root = run_root / "inputs" / "raw" / "g13c-pre-adapter"
    raw_root.mkdir(parents=True, exist_ok=True)
    (raw_root / "battery-output.log").write_bytes(b"")
    command = {
        "schema": COMMAND_SCHEMA,
        "brief_id": brief["brief_id"],
        "argv": [str(godot) if godot else None, "--path", ".", "--headless", "-s", "res://verify/run_all.gd"],
        "cwd": str(COSMOS),
        "shell": False,
        "status": "BLOCKED",
        "reason": reason,
    }
    canonical_write(raw_root / "command.json", command)
    process = {"schema": PROCESS_SCHEMA, "status": "BLOCKED", "reason": reason, "returncode": None, "pid": None}
    canonical_write(raw_root / "process-receipt.json", process)
    source, scenes = source_inventory(brief, COSMOS / "verify" / "run_all.gd")
    canonical_write(raw_root / "source-inventory.json", source)
    canonical_write(raw_root / "scene-inventory.json", scenes)
    trace = {"schema": TRACE_SCHEMA, "status": "BLOCKED", "reason": reason, "raw_output_sha256": sha256(b""), "lines": []}
    canonical_write(raw_root / "trace.json", trace)
    anchor = {"schema": ANCHOR_SCHEMA, "status": "BLOCKED", "reason": reason, "deterministic_artifacts": {}, "unavailable": ["battery-output.log has zero captured bytes"]}
    canonical_write(raw_root / "anchor.json", anchor)
    files = [p.relative_to(raw_root).as_posix() for p in raw_root.rglob("*") if p.is_file()]
    files = sorted(path for path in files if path != "digest-index.json")
    digest, root_sha = build_digest_index(raw_root, files)
    canonical_write(raw_root / "digest-index.json", digest)
    byte_verify(raw_root, digest)
    receipt = {"schema": RECEIPT_SCHEMA, "runner": SCHEMA, "brief_id": brief["brief_id"], "status": "BLOCKED", "reason": reason, "baseline_input_sha256": input_sha, "artifact_root": str(run_root), "artifact_root_sha256": root_sha}
    canonical_write(raw_root / "receipt.json", receipt)
    return run_root


def run(brief_path: Path, timeout_seconds: float) -> tuple[Path, int]:
    brief = load_brief(brief_path)
    input_sha, brief_sha = brief_identity(brief)
    if brief.get("baseline_input_sha256") not in ("", input_sha):
        raise ValueError("brief baseline input identity mismatch")
    if brief.get("brief_sha256") not in ("", brief_sha):
        raise ValueError("brief self identity mismatch")
    godot = find_godot()
    run_all = COSMOS / "verify" / "run_all.gd"
    if godot is None:
        return write_blocked(brief, brief_path, "Godot console executable unavailable", godot), 2
    if not COSMOS.is_dir() or not (COSMOS / "project.godot").is_file() or not run_all.is_file():
        return write_blocked(brief, brief_path, "CassiCosmos project or verify/run_all.gd unavailable", godot), 2
    run_root = DIAG / input_sha
    raw_root = run_root / "inputs" / "raw" / "g13c-pre-adapter"
    if run_root.exists():
        raise FileExistsError(f"baseline artifact root already exists: {run_root}")
    lock_path = DIAG / ".g13c-pre-adapter.lock"
    DIAG.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        contention_root = DIAG / "blocked" / f"lock-{os.getpid()}"
        return write_blocked(
            brief,
            brief_path,
            "another baseline runner holds the one-Godot lock",
            godot,
            run_root=contention_root,
        ), 2
    os.close(lock_fd)
    try:
        run_root.mkdir(parents=True)
        raw_root.mkdir(parents=True)
        (run_root / "inputs" / "brief.json").write_bytes(brief_path.read_bytes())
        canonical_write(run_root / "inputs" / "adapter-config.json", brief["adapter_config"])
        canonical_write(run_root / "inputs" / "adapter-fixture.json", brief["adapter_fixture"])
        log_dir = COSMOS / "_diag" / "battery_logs"
        arm_names = run_all_arms(run_all)
        before_log_hashes = snapshot_arm_logs(log_dir, arm_names)
        command_argv = [str(godot), "--path", ".", "--headless", "-s", "res://verify/run_all.gd"]
        command = {
            "schema": COMMAND_SCHEMA,
            "brief_id": brief["brief_id"],
            "argv": command_argv,
            "cwd": str(COSMOS),
            "shell": False,
            "runner_arms_windowed": True,
            "godot_executable_sha256": sha256(godot.read_bytes()),
        }
        command_sha = canonical_write(raw_root / "command.json", command)
        started_ns = time.monotonic_ns()
        status = "PASS"
        returncode: int | None = None
        pid: int | None = None
        timed_out = False
        output = b""
        error: str | None = None
        termination: dict[str, Any] | None = None
        try:
            proc = subprocess.Popen(command_argv, cwd=str(COSMOS), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            pid = proc.pid
            output, _ = proc.communicate(timeout=timeout_seconds if timeout_seconds > 0 else None)
            returncode = proc.returncode
            if returncode != 0:
                status = "FAILED"
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            status = "BLOCKED"
            error = f"battery timed out after {timeout_seconds:g} seconds"
            termination = kill_process_tree(proc.pid)
            if termination.get("method") != "taskkill" or termination.get("returncode") not in (0, 128, 255):
                proc.kill()
            output, _ = proc.communicate()
            returncode = proc.returncode
        except (OSError, subprocess.SubprocessError) as exc:
            status = classify_unavailable(exc)
            error = f"{type(exc).__name__}: {exc}"
        ended_ns = time.monotonic_ns()
        (raw_root / "battery-output.log").write_bytes(output)
        process = {
            "schema": PROCESS_SCHEMA,
            "status": status,
            "pid": pid,
            "returncode": returncode,
            "timed_out": timed_out,
            "captured_stream": "stdout+stderr",
            "byte_count": len(output),
            "output_sha256": sha256(output),
            "duration_ms": (ended_ns - started_ns) // 1_000_000,
        }
        if error:
            process["error"] = error
        if termination is not None:
            process["termination"] = termination
        process_sha = canonical_write(raw_root / "process-receipt.json", process)
        log_entries = copy_arm_logs(log_dir, arm_names, raw_root, before_hashes=before_log_hashes)
        source, scenes = source_inventory(brief, run_all)
        source_sha = canonical_write(raw_root / "source-inventory.json", source)
        scene_sha = canonical_write(raw_root / "scene-inventory.json", scenes)
        trace = {
            "schema": TRACE_SCHEMA,
            "status": status,
            "returncode": returncode,
            "raw_output_sha256": sha256(output),
            "raw_output_byte_count": len(output),
            "lines": decode_output_lines(output),
            "arm_logs": log_entries,
        }
        trace_sha = canonical_write(raw_root / "trace.json", trace)
        config_sha = sha256((run_root / "inputs" / "adapter-config.json").read_bytes())
        fixture_sha = sha256((run_root / "inputs" / "adapter-fixture.json").read_bytes())
        output_sha = sha256(output)
        anchor = {
            "schema": ANCHOR_SCHEMA,
            "status": status,
            "brief_sha256": sha256(brief_path.read_bytes()),
            "command_sha256": command_sha,
            "process_receipt_sha256": process_sha,
            "source_inventory_sha256": source_sha,
            "scene_inventory_sha256": scene_sha,
            "adapter_config_sha256": config_sha,
            "adapter_fixture_sha256": fixture_sha,
            "battery_output_sha256": output_sha,
            "trace_sha256": trace_sha,
            "arm_logs": {item["path"]: item["sha256"] for item in log_entries},
            "wire_bytes": {"status": "not-emitted-by-run_all", "synthetic": False},
        }
        anchor_sha = canonical_write(raw_root / "anchor.json", anchor)
        files = [p.relative_to(raw_root).as_posix() for p in raw_root.rglob("*") if p.is_file()]
        files = sorted(path for path in files if path != "digest-index.json")
        digest, artifact_root_sha = build_digest_index(raw_root, files)
        canonical_write(raw_root / "digest-index.json", digest)
        byte_verify(raw_root, digest)
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "runner": SCHEMA,
            "brief_id": brief["brief_id"],
            "status": status,
            "returncode": returncode,
            "baseline_input_sha256": input_sha,
            "artifact_root": str(run_root),
            "artifact_root_sha256": artifact_root_sha,
            "anchor_sha256": anchor_sha,
            "battery_output_sha256": output_sha,
            "arm_log_count": len(log_entries),
            "wire_status": "not-emitted-by-run_all",
            "synthetic_evidence": False,
        }
        canonical_write(raw_root / "receipt.json", receipt)
        return run_root, 0 if status == "PASS" else 1
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, default=ROOT / "CASSI-QI-WORLD-ADAPTER-BRIEF.json")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    try:
        run_root, code = run(args.brief.resolve(), args.timeout)
    except Exception as exc:
        print(f"[W13C baseline] BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"[W13C baseline] artifact_root={run_root}")
    print(f"[W13C baseline] status={'PASS' if code == 0 else 'FAILED/BLOCKED'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
