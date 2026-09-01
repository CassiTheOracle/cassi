"""Run the frozen Cassi-QI validation gates with raw byte retention.

Commands are data from a manifest (or explicit ``--command`` values), never
shell strings.  A missing command is BLOCKED, a non-zero command is FAILED, and
only a completed zero-exit command is PASSED.  Every stdout/stderr byte is
retained beneath the gate evidence root for independent verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_SUMMARY = "cassi.qi-flow-validation-summary.v1"
SCHEMA_GATE_RESULT = "cassi.qi-flow-gate-status.v1"
SCHEMA_FAILURE = "cassi.qi-flow-failure.v1"
SHA256_RE = __import__("re").compile(r"^[0-9a-f]{64}$")
REQUIRED_GATES = (
    "G0", "G1", "G2", "G3", "G3N", "G4", "G4R", "G5", "G5V", "G6", "G6T", "G6A", "G6B", "G6C",
    "G7", "G7P", "G8", "G9", "G9O", "G10", "G10E", "G10A", "G11", "G11D", "G12", "G12M", "G12L",
    "G12A", "G12E", "G13", "G13R", "G13C", "G13D", "G14A", "G14B",
)


class ValidationError(ValueError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8", "strict")


def canonical_hash(value: Any, domain: str) -> str:
    domain_bytes = domain.encode("utf-8", "strict")
    payload = canonical_json_bytes(value)
    framed = len(domain_bytes).to_bytes(8, "big") + domain_bytes + len(payload).to_bytes(8, "big") + payload
    return hashlib.sha256(framed).hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> bytes:
    raw = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)
    return raw


def _finish(value: Mapping[str, Any], schema: str) -> dict[str, Any]:
    result = dict(value)
    body = dict(result)
    body.pop("self_sha256", None)
    result["self_sha256"] = canonical_hash(body, schema)
    return result


def _missing_hash(label: str) -> str:
    return canonical_hash({"missing": label}, "cassi.qi-flow-missing-input.v1")


def _load_commands(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read command manifest {path}: {exc}") from exc
    rows: Any = payload.get("commands", payload.get("validation_commands", payload)) if isinstance(payload, Mapping) else payload
    if isinstance(rows, Mapping):
        rows = [dict(value, gate_id=key) if isinstance(value, Mapping) else {"gate_id": key, "argv": value} for key, value in rows.items()]
    if not isinstance(rows, list):
        raise ValidationError("command manifest must contain a commands array/object")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValidationError("command row is not an object")
        gate_id = row.get("gate_id", row.get("gate"))
        argv = row.get("argv", row.get("command"))
        if not isinstance(gate_id, str) or not gate_id:
            raise ValidationError("command row has no gate_id")
        if isinstance(argv, str):
            argv = shlex.split(argv, posix=(os.name != "nt"))
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
            raise ValidationError(f"command {gate_id} has invalid argv")
        result[gate_id] = {"argv": list(argv), "cwd": row.get("cwd"), "env": row.get("env"), "timeout_s": row.get("timeout_s", row.get("timeout", 900))}
    return result


def _parse_status(stdout: bytes) -> str | None:
    try:
        value = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(value, Mapping):
        raw = value.get("status", value.get("outcome"))
        if isinstance(raw, str):
            lowered = raw.lower()
            if lowered in {"blocked", "not_run", "not-run", "pending"}:
                return "blocked"
            if lowered in {"failed", "fail", "error"}:
                return "failed"
            if lowered in {"passed", "pass", "ok"}:
                return "passed"
    return None


def execute_gate(gate_id: str, command: Mapping[str, Any] | None, *, evidence_root: Path, default_cwd: Path, default_timeout_s: float = 900.0) -> dict[str, Any]:
    gate_root = evidence_root / gate_id.lower()
    stdout_path = gate_root / "raw" / "stdout.bin"
    stderr_path = gate_root / "raw" / "stderr.bin"
    if command is None:
        row = {"artifact_sha256": None, "failure_code": "MISSING_VALIDATION_COMMAND", "gate_id": gate_id, "status": "blocked"}
        status_value = _finish({"schema": SCHEMA_GATE_RESULT, **row}, SCHEMA_GATE_RESULT)
        _write(gate_root / "status.json", status_value)
        return row
    argv = list(command["argv"])
    cwd_value = command.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) else default_cwd
    env_value = command.get("env")
    env = None
    if isinstance(env_value, Mapping):
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in env_value.items()})
    try:
        completed = subprocess.run(argv, cwd=str(cwd), env=env, capture_output=True, check=False, timeout=float(command.get("timeout_s", default_timeout_s)))
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, bytes) else (exc.stdout or b"")
        stderr = exc.stderr if isinstance(exc.stderr, bytes) else (exc.stderr or b"")
        returncode = None
        timed_out = True
    except (OSError, ValueError) as exc:
        stdout = b""
        stderr = str(exc).encode("utf-8", "replace")
        returncode = None
        timed_out = False
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    observed = _parse_status(stdout)
    if timed_out:
        status, failure = "failed", "COMMAND_TIMEOUT"
    elif returncode is None:
        status, failure = "blocked", "COMMAND_NOT_EXECUTABLE"
    elif returncode != 0:
        status, failure = "failed", f"COMMAND_EXIT_{returncode}"
    elif observed in {"blocked", "failed"}:
        status, failure = observed, "COMMAND_REPORTED_" + observed.upper()
    else:
        status, failure = "passed", None
    row = {"artifact_sha256": hashlib.sha256(stdout + b"\0" + stderr).hexdigest(), "failure_code": failure, "gate_id": gate_id, "status": status}
    result = _finish({"schema": SCHEMA_GATE_RESULT, "gate_id": gate_id, "status": status, "failure_code": failure, "artifact_sha256": row["artifact_sha256"]}, SCHEMA_GATE_RESULT)
    _write(gate_root / "status.json", result)
    _write(gate_root / "command.json", {"argv": argv, "cwd": str(cwd), "returncode": returncode, "timeout": timed_out})
    return row


def run_validation(*, root: Path, gates: Sequence[str] = REQUIRED_GATES, commands_path: Path | None = None, commands: Mapping[str, Mapping[str, Any]] | None = None, cwd: Path | None = None, default_timeout_s: float = 900.0, mode: str = "development") -> dict[str, Any]:
    gate_tuple = tuple(gates)
    if len(set(gate_tuple)) != len(gate_tuple):
        raise ValidationError("duplicate validation gate id")
    if mode == "release-candidate":
        required = tuple(REQUIRED_GATES)
        if gate_tuple != required:
            raise ValidationError("release-candidate mode requires the complete frozen gate set")
    elif mode != "development":
        raise ValidationError(f"unknown validation mode: {mode}")
    command_map = dict(commands) if commands is not None else _load_commands(commands_path)
    default_cwd = cwd or Path.cwd()
    outcomes = [execute_gate(gate_id, command_map.get(gate_id), evidence_root=root / "gates", default_cwd=default_cwd, default_timeout_s=default_timeout_s) for gate_id in gate_tuple]
    blockers = [f"{row['gate_id']}:{row['failure_code']}" for row in outcomes if row["status"] == "blocked"]
    failures = [f"{row['gate_id']}:{row['failure_code']}" for row in outcomes if row["status"] == "failed"]
    status = "PASS" if outcomes and all(row["status"] == "passed" for row in outcomes) else ("BLOCKED" if blockers else "FAIL")
    body: dict[str, Any] = {"schema": SCHEMA_SUMMARY, "status": status, "gate_outcomes": outcomes, "required_gate_ids": list(gate_tuple), "blockers": sorted(blockers), "failures": sorted(failures)}
    summary = _finish(body, SCHEMA_SUMMARY)
    summary_path = root / "validation-summary.json"
    _write(summary_path, summary)
    index_rows = []
    for gate_id in gates:
        status_path = root / "gates" / gate_id.lower() / "status.json"
        if status_path.exists():
            index_rows.append({"path": status_path.relative_to(root).as_posix(), "sha256": hashlib.sha256(status_path.read_bytes()).hexdigest()})
        for raw_name in ("stdout.bin", "stderr.bin"):
            raw_path = root / "gates" / gate_id.lower() / "raw" / raw_name
            if raw_path.exists():
                index_rows.append({"path": raw_path.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest()})
    index = _finish({"schema": "cassi.qi-flow-validation-evidence-index.v1", "objects": sorted(index_rows, key=lambda row: row["path"])}, "cassi.qi-flow-validation-evidence-index.v1")
    _write(root / "validation-evidence-index.json", index)
    return {"status": status, "summary": summary, "summary_path": summary_path, "blockers": blockers, "failures": failures}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("_diag/cassi-qi-flow"))
    parser.add_argument("--commands", type=Path, dest="commands_path")
    parser.add_argument("--mode", choices=("release-candidate", "development"), default="release-candidate")
    parser.add_argument("--gates", nargs="*", default=list(REQUIRED_GATES))
    args = parser.parse_args(argv)
    try:
        gate_ids = tuple(args.gates)
        if args.mode == "release-candidate" and gate_ids != tuple(REQUIRED_GATES):
            raise ValidationError("release-candidate mode requires the complete frozen gate set")
        result = run_validation(root=args.root, gates=gate_ids, commands_path=args.commands_path, mode=args.mode)
    except (OSError, ValidationError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"status": result["status"], "blockers": result["blockers"], "failures": result["failures"]}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2 if result["status"] == "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
