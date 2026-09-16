#!/usr/bin/env python3
"""Dose sweep for the native Qi field coupling, with its designed identity control.

The server reports nothing about its own field state: no `/props` field, no qi
metric, and the per-response `cassi` receipt exists only in apprentice mode.  So
the only falsifiable evidence that `--cassi-qi-field` reaches generation is the
one the header names itself — `llama.h` documents `cassi_qi_injection_scale` as
"additive flux coupling; 0 is the identity control".

This probe therefore measures the same prompt, on one binary, with the field
flag present in every coupled arm and only the injection scale varying:

    no-field        launcher with -NoCassiQiField      (modal path still on)
    scale 0         field on, identity control
    scale N         field on, coupled

Scale 0 with the field on must reproduce the no-field text byte-for-byte if the
additive injection is the field's only channel into generation, and every dose
above zero must move tokens if the coupling is live.  One request per freshly
started server: requests inside one server session are not independent.

No harness source is touched — the scale is delivered through the launcher's
inherited environment (`LLAMA_ARG_CASSI_QI_INJECTION_SCALE`), so the workcase
protocol digest is unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cassi_field_qwen_workbench import LocalQwenClient  # noqa: E402

DEFAULT_BINARY = r"native\llama.cpp\b8\bin\Release\llama-server.exe"
DEFAULT_MODEL = "Qwen3.8-27B-Q4_K_M.gguf"
PROMPT = "Describe a calm morning at a harbour in about 60 words. Plain prose, no lists."


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def listening_pid(port: int) -> int | None:
    """PID listening on `port`, or None. A stale server silently answers for a
    launch that never bound, which is how a run gets attributed to the wrong
    flags."""
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[1].endswith(f":{port}") and parts[3].upper() == "LISTENING":
            try:
                return int(parts[4])
            except ValueError:
                return None
    return None


def llama_server_pids() -> dict[int, str]:
    """Every live llama-server.exe with its creation stamp, newest last."""
    script = ("Get-CimInstance Win32_Process -Filter \"name='llama-server.exe'\" | "
              "ForEach-Object { \"$($_.ProcessId)|$($_.CreationDate.ToString('o'))\" }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                         capture_output=True, text=True, check=False).stdout
    found = {}
    for line in out.strip().splitlines():
        pid, _, created = line.strip().partition("|")
        if pid.isdigit():
            found[int(pid)] = created
    return found


def wait_ready(port: int, timeout_s: float, proc: subprocess.Popen, log_path: pathlib.Path,
               launched_after: str) -> None:
    """Poll readiness, but fail the moment the launcher itself dies.

    A launcher that throws exits instantly; polling the port alone would spend
    the full timeout discovering that, ten minutes per arm.
    """

    deadline = time.monotonic() + timeout_s
    url = f"http://127.0.0.1:{port}/props"
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            tail = log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-4:]
            raise RuntimeError(f"launcher exited with {proc.returncode}: " + " | ".join(tail))
        try:
            with urllib.request.urlopen(url, timeout=8) as response:
                if response.status == 200:
                    # Something answers. It must be OUR server: a survivor from an
                    # earlier arm answers instantly and would silently supply that
                    # arm's flags to this one's measurements.
                    pid = listening_pid(port)
                    live = llama_server_pids()
                    if pid is None or pid not in live or live[pid] < launched_after:
                        raise RuntimeError(
                            f"port {port} was answered by pid {pid} "
                            f"(created {live.get(pid)}, launched after {launched_after}) — "
                            "a stale server, not the one this arm started"
                        )
                    return
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(3.0)
    raise TimeoutError(f"server on port {port} never became ready")


def kill_tree(proc: subprocess.Popen) -> None:
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def wait_port_free(port: int, timeout_s: float = 60.0) -> bool:
    import socket

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(1.0)
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return True
        time.sleep(1.0)
    return False


def run_arm(
    *,
    label: str,
    port: int,
    server_path: pathlib.Path,
    model_path: pathlib.Path,
    field: bool,
    scale: float | None,
    max_tokens: int,
    out_dir: pathlib.Path,
    extra_flags: list[str] | None = None,
) -> dict:
    command = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "start-llama-server.ps1",
        # The launcher resolves this against its own directory with Join-Path,
        # which mangles an absolute leaf into a concatenation, so pass it relative.
        "-ServerPath", str(server_path.relative_to(HERE)),
        "-Port", str(port),
    ]
    if not field:
        command.append("-NoCassiQiField")
    for flag in extra_flags or []:
        command.append(flag)

    environment = dict(os.environ)
    if scale is not None:
        environment["LLAMA_ARG_CASSI_QI_INJECTION_SCALE"] = repr(float(scale))

    log_path = out_dir / f"server-{label}.log"
    record: dict = {
        "label": label,
        "field_flag": field,
        "injection_scale_env": environment.get("LLAMA_ARG_CASSI_QI_INJECTION_SCALE"),
        "launcher_command": command,
        "max_tokens": max_tokens,
    }
    print(f"[{label}] launching (field={field}, scale={scale})", flush=True)
    occupied = listening_pid(port)
    if occupied is not None:
        record["error"] = f"port {port} already held by pid {occupied} before launch; refusing to measure"
        print(f"[{label}] REFUSED: {record['error']}", flush=True)
        return record
    launched_after = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    with log_path.open("wb") as log:
        proc = subprocess.Popen(command, cwd=str(HERE), env=environment, stdout=log, stderr=subprocess.STDOUT)
        try:
            started = time.perf_counter()
            wait_ready(port, timeout_s=600.0, proc=proc, log_path=log_path, launched_after=launched_after)
            record["startup_s"] = round(time.perf_counter() - started, 2)
            client = LocalQwenClient(f"http://127.0.0.1:{port}", model_path=model_path)
            completion = client.complete(prompt=PROMPT, max_tokens=max_tokens, thinking=False)
            content = completion["content"]
            usage = completion.get("usage", {})
            timings = completion.get("timings", {})
            record.update(
                {
                    "completion_tokens": usage.get("completion_tokens"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "capped": usage.get("completion_tokens") == max_tokens,
                    "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    "content": content,
                    "prompt_eval_ms": timings.get("prompt_ms"),
                    "predicted_ms": timings.get("predicted_ms"),
                    "server_cassi_receipt": completion.get("server_cassi_receipt"),
                }
            )
            print(f"[{label}] {record['completion_tokens']} tokens sha {record['content_sha256'][:16]}", flush=True)
        except Exception as exc:  # a crash is a result, not an abort
            record["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[{label}] FAILED: {record['error']}", flush=True)
        finally:
            kill_tree(proc)
            record["port_released"] = wait_port_free(port)
            record["server_exit_code"] = proc.returncode
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scales", default="0,1,4,16", help="comma-separated injection scales")
    parser.add_argument("--include-no-field", action="store_true", help="add the -NoCassiQiField arm")
    parser.add_argument("--include-plain", action="store_true", help="add the -NoCassiModal -NoCassiQiField arm")
    parser.add_argument("--binary", default=DEFAULT_BINARY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=200)
    parser.add_argument("--port", type=int, default=8084)
    parser.add_argument("--label", default="dose-sweep")
    parser.add_argument("--tag", default=time.strftime("%Y%m%d"))
    args = parser.parse_args()

    server_path = (HERE / args.binary) if not pathlib.Path(args.binary).is_absolute() else pathlib.Path(args.binary)
    model_path = (HERE / args.model) if not pathlib.Path(args.model).is_absolute() else pathlib.Path(args.model)
    for path in (server_path, model_path):
        if not path.is_file():
            raise SystemExit(f"missing required artifact: {path}")

    out_dir = HERE / "_diag" / "cassi-field-attestation"
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / f"{args.label}-{args.tag}.json"

    arms: list[tuple[str, bool, float | None, list[str]]] = []
    if args.include_plain:
        # `--cassi-qi-field` clears cassi_modal, so the no-field arm still runs the
        # modal path. Only clearing both gives the plain-Qwen baseline.
        arms.append(("plain", False, None, ["-NoCassiModal"]))
    if args.include_no_field:
        arms.append(("no-field", False, None, []))
    for token in [part for part in args.scales.split(",") if part.strip()]:
        scale = float(token)
        arms.append((f"scale-{token.strip()}", True, scale, []))

    receipt: dict = {
        "prompt": PROMPT,
        "server_binary": str(server_path.relative_to(HERE)),
        "server_binary_bytes": server_path.stat().st_size,
        "server_binary_sha256": sha256_file(server_path),
        "model": model_path.name,
        "model_bytes": model_path.stat().st_size,
        "arms": [],
    }
    for label, field, scale, extra_flags in arms:
        record = run_arm(
            label=label,
            port=args.port,
            server_path=server_path,
            model_path=model_path,
            field=field,
            scale=scale,
            max_tokens=args.max_tokens,
            out_dir=out_dir,
            extra_flags=extra_flags,
        )
        receipt["arms"].append(record)
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    survivors = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    receipt["llama_server_survivors"] = "" if "No tasks" in survivors else survivors
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    print(f"\nreceipt: {receipt_path.relative_to(HERE)}")
    done = [arm for arm in receipt["arms"] if "error" not in arm]
    print(f"arms completed: {len(done)}/{len(receipt['arms'])}")
    base = next((arm for arm in done if arm["label"] == "no-field"), None)
    for arm in done:
        same = "" if base is None or arm is base else (" == no-field" if arm["content_sha256"] == base["content_sha256"] else " != no-field")
        print(f"  {arm['label']:>9}: {arm['completion_tokens']:>3} tok  sha {arm['content_sha256'][:16]}{same}")
    if base is not None:
        identity = next((arm for arm in done if arm["label"] == "scale-0"), None)
        if identity is not None:
            print(f"\nidentity control (scale 0 reproduces no-field byte-exactly): {identity['content_sha256'] == base['content_sha256']}")
    if receipt["llama_server_survivors"]:
        print(f"WARNING survivors:\n{receipt['llama_server_survivors']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
