#!/usr/bin/env python3
"""Capacity ladder for the native Qi field: the integrator timestep `--cassi-qi-field-dt`.

`dt` enters `vulkan-shaders/cassi_qi_field_step.comp` in three places: the write
blend (`write_gain = dt * write_gate`), the drift update (`work[i] += a[i] * dt`)
and the scale advance (`scale_dt`).  It is therefore the field's *capacity*
knob — how much of the decoded activity the field absorbs and how fast its own
state evolves — as opposed to the injection scale, which scales only the field's
influence back on the model.

Measured ladder (2026-09-16, layer 32, displacement 0, scales 4, one binary
2e89f1bf, prompt fixed):

    dt 0.005   109 tok  944c659c95e3793a   free-form and the 17-case battery both
                                           reproduce the reference byte-for-byte
    dt 0.02     95 tok  a206c6f807f37ddd   free-form diverges immediately; battery
                                           field arm moves 4 answers, scores held
                                           (16/17), baseline arm untouched
    dt 0.05    108 tok  accab2f47f75fa34   free-form diverges late; battery degrades
                                           (field 16 -> 11, baseline 6 -> 4)

Two rules follow, and this probe enforces both.

  * The free-form generation is the liveness instrument.  A capacity change that
    leaves the battery tally flat is not inert — the battery's answers are short
    and greedy and cannot resolve it.  `freeform` reports the token count and
    digest per dt; equality there is the only real null.
  * A campaign is evidence only next to a default-dt control campaign on the
    same binary (`compare` shows both columns).  The control must reproduce the
    reference run byte-for-byte; otherwise a text change is attributable to the
    rebuild, not to `dt`.

The comparator reads each arm receipt row's `raw_output` and refuses to compare
if that key is absent: a guessed key returns the empty string on both sides and
every case then "matches", which is what a first pass here actually did.  The
receipt is the only place the answer text lives — `answer_pass` alone hides
whitespace-only and equal-scoring text changes.

No harness source is touched: `dt` is a server flag, so the workcase protocol
digest is unchanged (`8f6442f6...` in every run below).

    python probe_cassi_qi_dt_ladder.py freeform --dt 0.02 --dt 0.05 --out _diag/dt-ladder.json
    python probe_cassi_qi_dt_ladder.py campaign --dt 0.02 --out-dir _diag/workcases-b8-dt0p02-20260916
    python probe_cassi_qi_dt_ladder.py compare --ref _diag/workcases-b8-qifield-20260916 --run _diag/workcases-b8-dt0p005-20260916 --run _diag/workcases-b8-dt0p02-20260916
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cassi_field_qwen_workbench import LocalQwenClient  # noqa: E402
from probe_cassi_field_dose import (  # noqa: E402
    kill_tree,
    listening_pid,
    llama_server_pids,
    sha256_file,
    wait_port_free,
    wait_ready,
)

DEFAULT_BINARY = pathlib.Path("native/llama.cpp/b8/bin/Release/llama-server.exe")
DEFAULT_MODEL = pathlib.Path("Qwen3.8-27B-Q4_K_M.gguf")
DEFAULT_REF_RUN = pathlib.Path("_diag/workcases-b8-qifield-20260916")
RUNNER = "run_cassi_field_qwen_workcases.py"
PROMPT = "Describe a calm morning at a harbour in about 60 words. Plain prose, no lists."
ARMS = ("baseline", "field")

# `llama-server.exe` is a 10 KB stub: the code under test is in its siblings, so
# a receipt that pins only the exe attests nothing about the implementation.
IMPLEMENTATION_SIDECARS = ("llama-server-impl.dll", "llama.dll", "llama-common.dll", "ggml-vulkan.dll")
MANIFEST_FILE = "implementation-manifest.json"


def implementation_manifest(binary: pathlib.Path, sidecars: tuple[str, ...] = IMPLEMENTATION_SIDECARS) -> dict[str, dict]:
    """Size and digest of the executable and every sibling library that holds it."""
    manifest: dict[str, dict] = {}
    for path in (binary, *(binary.parent / name for name in sidecars)):
        if path.is_file():
            manifest[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return manifest


def run_implementation(run_dir: pathlib.Path) -> dict[str, dict] | None:
    """The pinned implementation for a run: its own sidecar first, then an inline block.

    The runner's receipts (`baseline.json`, `field.json`, `analysis.json`) pin only
    `server_binary` — the 10 KB stub — and are never edited after the fact, so the
    pin lives in a file the probe owns.
    """
    sidecar = run_dir / MANIFEST_FILE
    if sidecar.is_file():
        recorded = json.loads(sidecar.read_text(encoding="utf-8")).get("implementation")
        if isinstance(recorded, dict):
            return recorded
    launch = run_dir / "server-launch.json"
    if not launch.is_file():
        return None
    recorded = json.loads(launch.read_text(encoding="utf-8")).get("implementation")
    return recorded if isinstance(recorded, dict) else None


def write_implementation_sidecar(run_dir: pathlib.Path, binary: pathlib.Path, *, role: str, note: str) -> dict:
    paths = [path for path in (binary, *(binary.parent / name for name in IMPLEMENTATION_SIDECARS)) if path.is_file()]
    document = {
        "schema": "cassi.field-qwen.implementation-manifest.v1",
        "role": role,
        "server_binary": binary.name,
        "server_binary_sha256": sha256_file(binary),
        "build_mtime": max(path.stat().st_mtime for path in paths),
        "implementation": implementation_manifest(binary),
        "note": note,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / MANIFEST_FILE).write_text(json.dumps(document, indent=2), encoding="utf-8")
    return document


def server_argv(model: pathlib.Path, *, port: int, layer: int, scales: int, displacement: int, dt: float,
                substitute: float = 0.0, injection_scale: float | None = None) -> list[str]:
    argv = [
        "--model", str(model), "--host", "127.0.0.1", "--port", str(port), "--ctx-size", "16384",
        "--parallel", "1", "--gpu-layers", "40", "--batch-size", "512", "--ubatch-size", "512",
        "--slot-save-path", "_diag/native-slots", "--metrics",
        "--cassi-qi-field", "--cassi-qi-field-layer", str(layer), "--cassi-qi-field-scales", str(scales),
        "--cassi-qi-field-dt", repr(float(dt)),
    ]
    if displacement != 0:
        argv += ["--cassi-qi-displacement", str(displacement)]
    if substitute > 0.0:
        argv += ["--cassi-qi-substitute", repr(float(substitute))]
    if injection_scale is not None:
        argv += ["--cassi-qi-injection-scale", repr(float(injection_scale))]
    return argv


class Server:
    """Direct child process, so the listener PID and the argv in the receipt are
    the ones that answered.  The PowerShell launcher keeps its own argument list,
    which makes `--cassi-qi-field-dt` unforwardable without editing it."""

    def __init__(self, *, binary: pathlib.Path, model: pathlib.Path, port: int, argv: list[str], log_path: pathlib.Path):
        self.port = port
        self.argv = argv
        self.binary = binary
        self.binary_sha256 = sha256_file(binary)
        self.log_path = log_path
        self.proc: subprocess.Popen | None = None
        self.log = None

    def __enter__(self) -> "Server":
        occupied = listening_pid(self.port)
        if occupied is not None:
            raise RuntimeError(f"port {self.port} already held by pid {occupied}; refusing to measure")
        if llama_server_pids():
            raise RuntimeError(f"llama-server already running: {sorted(llama_server_pids())}; refusing to measure")
        launched_after = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        self.log = self.log_path.open("wb")
        self.proc = subprocess.Popen([str(self.binary), *self.argv], cwd=str(HERE),
                                     stdout=self.log, stderr=subprocess.STDOUT)
        wait_ready(self.port, timeout_s=600.0, proc=self.proc, log_path=self.log_path, launched_after=launched_after)
        pid = listening_pid(self.port)
        live = llama_server_pids()
        if pid != self.proc.pid or list(live) != [self.proc.pid]:
            raise RuntimeError(f"listener pid {pid} is not the launched pid {self.proc.pid} (live: {live})")
        self.pid = pid
        return self

    def __exit__(self, *_exc) -> None:
        if self.proc is not None:
            kill_tree(self.proc)
        if self.log is not None:
            self.log.close()
        if not wait_port_free(self.port):
            raise RuntimeError(f"port {self.port} still answering after teardown")
        if llama_server_pids():
            raise RuntimeError(f"llama-server survived teardown: {sorted(llama_server_pids())}")


def cmd_freeform(args: argparse.Namespace) -> int:
    binary, model = args.binary.resolve(), args.model.resolve()
    arms = [(dt, substitute) for dt in args.dt for substitute in args.substitute]
    receipt: dict = {
        "schema": "cassi.field-qwen.dt-ladder.freeform.v1",
        "probe": "one temperature-0 request per fresh server; equality is the only null",
        "server_binary_sha256": sha256_file(binary),
        "implementation": implementation_manifest(binary),
        "model": model.name,
        "prompt": PROMPT,
        "config": {"layer": args.layer, "scales": args.scales, "displacement": args.displacement},
        "arms": [],
    }
    for dt, substitute in arms:
        argv = server_argv(model, port=args.port, layer=args.layer, scales=args.scales,
                           displacement=args.displacement, dt=dt, substitute=substitute,
                           injection_scale=args.injection_scale)
        log_path = args.out.with_name(f"{args.out.stem}-server-dt{dt:g}-sub{substitute:g}.log")
        with Server(binary=binary, model=model, port=args.port, argv=argv, log_path=log_path) as server:
            completion = LocalQwenClient(f"http://127.0.0.1:{args.port}", model_path=model).complete(
                prompt=PROMPT, max_tokens=args.max_tokens, thinking=False)
            content = completion["content"]
            arm = {
                "dt": dt,
                "substitute": substitute,
                "listener_pid": server.pid,
                "argv": argv,
                "completion_tokens": completion.get("usage", {}).get("completion_tokens"),
                "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "head": content[:80],
            }
        receipt["arms"].append(arm)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(f"dt {dt:g} substitute {substitute:g}: {arm['completion_tokens']} tokens  sha {arm['content_sha256'][:16]}", flush=True)
        print(f"  head: {arm['head']}", flush=True)
    distinct = len({arm["content_sha256"] for arm in receipt["arms"]})
    print(f"\n{len(receipt['arms'])} arms, {distinct} distinct generations")
    print(f"receipt: {args.out}")
    return 0


def cmd_campaign(args: argparse.Namespace) -> int:
    binary, model = args.binary.resolve(), args.model.resolve()
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    def stage(*stage_args: str) -> None:
        proc = subprocess.run([sys.executable, RUNNER, *stage_args], capture_output=True, text=True, timeout=3200)
        summary = (proc.stdout or "").strip().splitlines()
        print(f"[{stage_args[0]}] exit={proc.returncode} {summary[-1] if summary else ''}", flush=True)
        if proc.returncode != 0:
            raise RuntimeError(f"runner stage {stage_args[0]} failed: {(proc.stderr or '')[-400:]}")

    stage("prepare", "--out-dir", str(out_dir))
    argv = server_argv(model, port=args.port, layer=args.layer, scales=args.scales,
                       displacement=args.displacement, dt=args.dt, substitute=args.substitute,
                       injection_scale=args.injection_scale)
    with Server(binary=binary, model=model, port=args.port, argv=argv,
                log_path=out_dir / "server.log") as server:
        write_implementation_sidecar(
            out_dir, binary,
            role=f"field substitution: dt {args.dt:g}, substitute {args.substitute:g} at layer {args.layer}, "
                 f"displacement {args.displacement}",
            note="recorded at launch from the build on disk; the runner's own receipts pin only the stub executable",
        )
        (out_dir / "server-launch.json").write_text(json.dumps({
            "schema": "cassi.field-qwen.server-launch.v1",
            "role": f"field substitution: dt {args.dt:g}, substitute {args.substitute:g} at layer {args.layer}, "
                    f"displacement {args.displacement}",
            "argv": argv,
            "server_binary_sha256": server.binary_sha256,
            "implementation_manifest": MANIFEST_FILE,
            "listener": {"pid": server.pid, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                         "sole_llama_server": list(llama_server_pids()) == [server.pid]},
        }, indent=2), encoding="utf-8")
        for arm in ARMS:
            stage(arm, "--out-dir", str(out_dir), "--server-binary", str(binary))
    stage("analyze", "--out-dir", str(out_dir))

    receipt = compare_runs(args.ref, [out_dir], arms=ARMS)
    receipt["dt"] = args.dt
    receipt["substitute"] = args.substitute
    receipt["run_binary_sha256"] = sha256_file(binary)
    (out_dir / "dt-compare.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(compare_table(receipt))
    print(f"receipt: {out_dir / 'dt-compare.json'}")
    return 0


def row_text(row: dict) -> str:
    text = row.get("raw_output")
    if not isinstance(text, str):
        raise KeyError(
            f"row {row.get('id')!r} has no `raw_output`: refusing to compare. "
            "A guessed key returns the empty string on both sides and every case then 'matches'."
        )
    return text


def arm_rows(run_dir: pathlib.Path, arm: str) -> dict[str, dict]:
    document = json.loads((run_dir / f"{arm}.json").read_text(encoding="utf-8"))
    return {row["id"]: row for row in document["rows"]}


def compare_runs(ref_dir: pathlib.Path, run_dirs: list[pathlib.Path], *, arms: tuple[str, ...] = ARMS) -> dict:
    ref_impl = run_implementation(ref_dir)
    receipt: dict = {"schema": "cassi.field-qwen.dt-ladder.compare.v1", "ref": ref_dir.name,
                     "ref_implementation": ref_impl, "arms": {}}
    for arm in arms:
        reference = arm_rows(ref_dir, arm)
        entry: dict = {
            "ref_cases": len(reference),
            "ref_passes": sum(bool(row["answer_pass"]) for row in reference.values()),
            "runs": {},
        }
        for run_dir in run_dirs:
            current = arm_rows(run_dir, arm)
            shared = sorted(set(reference) & set(current))
            changed = [case for case in shared if row_text(current[case]) != row_text(reference[case])]
            impl = run_implementation(run_dir)
            entry["runs"][run_dir.name] = {
                "cases": len(current),
                "text_identical": len(shared) - len(changed),
                "changed": changed,
                "missing": sorted(set(reference) - set(current)),
                "unexpected": sorted(set(current) - set(reference)),
                "passes": sum(bool(row["answer_pass"]) for row in current.values()),
                "completion_tokens": sum(row.get("usage", {}).get("completion_tokens", 0) for row in current.values()),
                "implementation": impl,
            }
            if ref_impl is not None and impl is not None:
                entry["runs"][run_dir.name]["implementation_differs_from_ref"] = sorted(
                    name for name in {*ref_impl, *impl}
                    if ref_impl.get(name, {}).get("sha256") != impl.get(name, {}).get("sha256")
                )
        receipt["arms"][arm] = entry
    return receipt


def compare_table(receipt: dict) -> str:
    def impl_label(block: dict | None) -> str:
        if not block:
            return "impl unrecorded"
        key = "llama-server-impl.dll" if "llama-server-impl.dll" in block else next(iter(block))
        return f"impl {key[:22]} {block[key]['sha256'][:8]}"

    lines = [f"ref {receipt['ref']}  ({impl_label(receipt.get('ref_implementation'))})"]
    for arm, entry in receipt["arms"].items():
        lines.append(f"  {arm}: ref {entry['ref_passes']}/{entry['ref_cases']} pass")
        for name, run in entry["runs"].items():
            lines.append(
                f"    {name:42s} pass {run['passes']:2d}/{run['cases']}  "
                f"text-identical {run['text_identical']:2d}/{run['cases']}  tokens {run['completion_tokens']}  "
                f"({impl_label(run.get('implementation'))})"
            )
            if run.get("implementation_differs_from_ref"):
                lines.append(f"      implementation differs from ref: {', '.join(run['implementation_differs_from_ref'])}")
            if run["changed"]:
                lines.append(f"      changed: {', '.join(run['changed'])}")
            for key in ("missing", "unexpected"):
                if run[key]:
                    lines.append(f"      {key}: {', '.join(run[key])}")
    return "\n".join(lines)


def cmd_compare(args: argparse.Namespace) -> int:
    receipt = compare_runs(args.ref, args.run, arms=tuple(args.arms))
    print(compare_table(receipt))
    if args.out:
        args.out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(f"receipt: {args.out}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--binary", type=pathlib.Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=pathlib.Path, default=DEFAULT_MODEL)
    parser.add_argument("--port", type=int, default=8084)
    parser.add_argument("--layer", type=int, default=32)
    parser.add_argument("--scales", type=int, default=4)
    parser.add_argument("--displacement", type=int, default=0)
    parser.add_argument("--injection-scale", type=float, default=None,
                        help="additive coupling at the Qi layer; 0 removes the injection so a "
                             "substitution arm's only field channel is the state write")
    sub = parser.add_subparsers(dest="command", required=True)

    free = sub.add_parser("freeform", help="one open-ended generation per fresh server (liveness instrument)")
    free.add_argument("--dt", type=float, action="append", required=True)
    free.add_argument("--substitute", type=float, action="append", default=None,
                      help="field share of the suppressed recurrent-state write; repeat for a ladder")
    free.add_argument("--max-tokens", type=int, default=200)
    free.add_argument("--out", type=pathlib.Path, required=True)
    free.set_defaults(func=cmd_freeform)

    campaign = sub.add_parser("campaign", help="prepare/baseline/field/analyze on one server, then compare")
    campaign.add_argument("--dt", type=float, required=True)
    campaign.add_argument("--substitute", type=float, default=0.0,
                         help="field share of the suppressed recurrent-state write (0 = plain lesion)")
    campaign.add_argument("--out-dir", type=pathlib.Path, required=True)
    campaign.add_argument("--ref", type=pathlib.Path, default=DEFAULT_REF_RUN)
    campaign.set_defaults(func=cmd_campaign)

    compare = sub.add_parser("compare", help="disk-only per-case comparison of stored arm receipts")
    compare.add_argument("--ref", type=pathlib.Path, required=True)
    compare.add_argument("--run", type=pathlib.Path, action="append", required=True)
    compare.add_argument("--arms", nargs="+", default=list(ARMS))
    compare.add_argument("--out", type=pathlib.Path)
    compare.set_defaults(func=cmd_compare)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "freeform" and not args.substitute:
        args.substitute = [0.0]
    try:
        return args.func(args)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "error", "command": args.command, "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
