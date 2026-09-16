"""Native-field workcase campaign: the field-on half, scored against the verified off half.

The runner's `baseline`/`field` stages differ by CassiFI work memory in the prompt, not by the
native Qi field; the native field is a server launch flag. Only the field-on config is run here:
`_diag/native-field-off/` is already complete and verified, and `run_arm` aborts with "arm already
exists" if a config is repeated.

`prepare` refuses to write into an existing non-empty directory, so this driver clears the run dir
first and stops the config if any stage fails rather than continuing into a partial artifact set.
"""

import json
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
SERVER = HERE / "native/llama.cpp/b8/bin/Release/llama-server.exe"
MODEL = "Qwen3.8-27B-Q4_K_M.gguf"
RUNNER = HERE / "run_cassi_field_qwen_workcases.py"
VERIFIER = HERE / "verify_cassi_field_qwen_workcases.py"

FIELD_ON = True

FIELD_FLAGS = [
    "--cassi-qi-field",
    "--cassi-qi-displacement", "3",
    "--cassi-qi-substitute", "1.0",
    "--cassi-qi-field-layer", "32",
    "--cassi-qi-field-row-width", "6144",
]

CONFIGS = [
    {"name": "on", "port": 8084, "own_server": True, "flags": FIELD_FLAGS},
]

LOG = []


def say(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    LOG.append(line)
    print(line, flush=True)


def run(cmd, timeout):
    say("run: " + " ".join(str(c) for c in cmd))
    try:
        r = subprocess.run([str(c) for c in cmd], cwd=str(HERE), capture_output=True,
                           text=True, timeout=timeout)
        tail = (r.stdout + r.stderr).strip().splitlines()[-6:]
        say(f"  rc={r.returncode}")
        for t in tail:
            say("  | " + t[:180])
        return r.returncode
    except subprocess.TimeoutExpired:
        say("  TIMEOUT")
        return 124


def props_ready(port, deadline):
    url = f"http://127.0.0.1:{port}/props"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            pass
        time.sleep(5)
    return False


def start_own_server(port):
    cmd = [str(SERVER), "-m", MODEL, "--port", str(port)] + (FIELD_FLAGS if FIELD_ON else [])
    proc = subprocess.Popen([str(c) for c in cmd], cwd=str(HERE),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if props_ready(port, time.time() + 900):
        say(f"  server ready on {port} (pid {proc.pid}, field {'on' if FIELD_ON else 'off'})")
        return proc
    say(f"  server FAILED to become ready on {port}")
    proc.kill()
    return None


def main():
    results = {}
    for cfg in CONFIGS:
        run_dir = HERE / "_diag" / f"native-field-{cfg['name']}"
        say(f"=== config {cfg['name']} (port {cfg['port']}) -> {run_dir}")

        own = start_own_server(cfg["port"]) if cfg["own_server"] else None
        if cfg["own_server"] and own is None:
            results[cfg["name"]] = {"server": "unavailable"}
            continue
        if own is None and not props_ready(cfg["port"], time.time() + 900):
            say(f"  hub server on {cfg['port']} never became ready")
            results[cfg["name"]] = {"server": "unavailable"}
            continue

        base_url = f"http://127.0.0.1:{cfg['port']}"
        out = ["--out-dir", str(run_dir)]
        common = out + ["--server-binary", str(SERVER), "--model", MODEL]
        r = {}
        stages = [
            ("prepare", [sys.executable, str(RUNNER), "prepare"] + common),
            ("baseline", [sys.executable, str(RUNNER), "baseline"] + common + ["--base-url", base_url]),
            ("field", [sys.executable, str(RUNNER), "field"] + common + ["--base-url", base_url]),
            ("analyze", [sys.executable, str(RUNNER), "analyze"] + out),
            ("verify", [sys.executable, str(VERIFIER), "--run-dir", str(run_dir)]),
        ]
        for name, cmd in stages:
            if name == "prepare":
                shutil.rmtree(run_dir, ignore_errors=True)  # prepare refuses a non-empty dir
            r[name] = run(cmd, 1800)
            if r[name] != 0:
                say(f"  stage {name} failed; abandoning config {cfg['name']}")
                break
        results[cfg["name"]] = r

        if own is not None:
            own.terminate()
            say(f"  server stopped (pid {own.pid})")

    summary = HERE / "_diag" / "native-field-campaign-summary.json"
    summary.write_text(json.dumps({"results": results, "log": LOG}, indent=2), encoding="utf-8")
    say(f"summary -> {summary}")


if __name__ == "__main__":
    main()
