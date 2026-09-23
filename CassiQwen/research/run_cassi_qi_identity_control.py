"""Prove the Qi field's default path is untouched by the learned mode-bank controls.

The `--cassi-qi-read-absolute`, `--cassi-qi-unwritten-latch`, and
`--cassi-qi-mode-bank` controls all default off. This runner holds the field at
its defaults, runs the same prompt on two builds of `cassi-qwen` across two
backends, and requires each build to reproduce its peer's state fingerprints and
out-state bytes at the same backend. The reference build is the one that predates
the controls, so agreement is bit-identity of the default path rather than
agreement of two copies of the same code.

    python research/run_cassi_qi_identity_control.py
    python research/run_cassi_qi_identity_control.py --builds b8 b8-learn b8-next --gpu-layers 0 99
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

from cassi_llama_capture import write_zero_state  # noqa: E402

LLAMA = ROOT / "native" / "llama.cpp"
MODEL = ROOT / "Qwen3.5-0.8B-Q4_0.gguf"
RECEIPT_SCHEMA = "cassi.qi.native-runtime.v1"


def build_binary(build: str) -> Path:
    binary = LLAMA / build / "bin" / "Release" / "cassi-qwen.exe"
    if not binary.is_file():
        raise FileNotFoundError(f"no cassi-qwen.exe for build {build!r} at {binary}")
    return binary


def run_one(build: str, gpu_layers: int, model: Path, out: Path, prompt: str,
            tokens: int, field_layer: int, state_template: Path) -> dict:
    binary = build_binary(build)
    directory = out / f"{build}-gpu{gpu_layers}"
    directory.mkdir(parents=True, exist_ok=True)
    state_in = directory / "state-in.f32"
    state_in.write_bytes(state_template.read_bytes())
    state_out = directory / "state-out.f32"
    environment = dict(os.environ)
    # The isolated build needs its own DLLs ahead of any other llama.cpp build.
    environment["PATH"] = str(binary.parent) + os.pathsep + environment.get("PATH", "")
    command = [
        str(binary), "--mode", "coupled", "--model", str(model),
        "--state", str(state_in), "--out-state", str(state_out),
        "--prompt", prompt, "--tokens", str(tokens),
        "--gpu-layers", str(gpu_layers), "--field-layer", str(field_layer),
        "--displacement", "0",
    ]
    completed = subprocess.run(command, cwd=directory, env=environment, timeout=1800,
                               capture_output=True, text=True)
    (directory / "stdout.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    receipt = None
    for line in completed.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if candidate.get("schema") == RECEIPT_SCHEMA:
                receipt = candidate
    if receipt is None:
        raise RuntimeError(f"{build} at --gpu-layers {gpu_layers} printed no {RECEIPT_SCHEMA} "
                           f"receipt; see {directory / 'stdout.log'}")
    if receipt.get("verdict") != "PASS":
        raise RuntimeError(f"{build} at --gpu-layers {gpu_layers} reported {receipt.get('verdict')!r}")
    receipt["out_state_sha256"] = hashlib.sha256(state_out.read_bytes()).hexdigest()
    receipt["out_state_bytes"] = state_out.stat().st_size
    receipt["command"] = " ".join(command)
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True),
                                            encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--builds", nargs="+", default=["b8", "b8-learn"],
                        help="build directories under native/llama.cpp; the first is the reference")
    parser.add_argument("--gpu-layers", nargs="+", type=int, default=[0, 99])
    parser.add_argument("--model", default=str(MODEL))
    parser.add_argument("--out", default=str(ROOT / "_diag" / "identity-control"))
    parser.add_argument("--prompt", default="resonant")
    parser.add_argument("--tokens", type=int, default=4)
    parser.add_argument("--field-layer", type=int, default=12)
    args = parser.parse_args()

    model = Path(args.model)
    if not model.is_file():
        raise FileNotFoundError(model)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_template = out / "zero.f32"
    write_zero_state(state_template)

    runs: dict[str, dict] = {}
    for gpu_layers in args.gpu_layers:
        for build in args.builds:
            runs[f"{build}-gpu{gpu_layers}"] = run_one(
                build, gpu_layers, model, out, args.prompt, args.tokens,
                args.field_layer, state_template)

    reference = args.builds[0]
    mismatches: list[str] = []
    print(f"{'backend':>8s} {'build':>10s} {'state_before_fnv1a':>21s} "
          f"{'state_after_fnv1a':>21s} {'out-state sha256':>16s}")
    for gpu_layers in args.gpu_layers:
        for build in args.builds:
            run = runs[f"{build}-gpu{gpu_layers}"]
            print(f"{gpu_layers:>8d} {build:>10s} {run['state_before_fnv1a']:>21d} "
                  f"{run['state_after_fnv1a']:>21d} {run['out_state_sha256'][:16]:>16s}")
        peer = runs[f"{reference}-gpu{gpu_layers}"]
        for build in args.builds[1:]:
            run = runs[f"{build}-gpu{gpu_layers}"]
            for field in ("state_before_fnv1a", "state_after_fnv1a", "out_state_sha256"):
                if run[field] != peer[field]:
                    mismatches.append(f"gpu{gpu_layers} {build} {field}: "
                                      f"{run[field]} != {peer[field]}")

    by_backend: dict[str, dict] = {}
    for gpu_layers in args.gpu_layers:
        by_backend[f"gpu{gpu_layers}"] = {
            "state_before_fnv1a": runs[f"{reference}-gpu{gpu_layers}"]["state_before_fnv1a"],
            "state_after_fnv1a": runs[f"{reference}-gpu{gpu_layers}"]["state_after_fnv1a"],
            "out_state_sha256": runs[f"{reference}-gpu{gpu_layers}"]["out_state_sha256"],
        }
    backends_agree = len({json.dumps(value, sort_keys=True) for value in by_backend.values()}) == 1

    summary = {
        "reference_build": reference,
        "builds": args.builds,
        "gpu_layers": args.gpu_layers,
        "model": {"path": str(model), "bytes": model.stat().st_size},
        "controls": "defaults: read_absolute off, unwritten_latch off, no mode bank",
        "prompt": args.prompt,
        "tokens": args.tokens,
        "field_layer": args.field_layer,
        "runs": runs,
        "default_path_bit_identical_across_builds": not mismatches,
        "mismatches": mismatches,
        "backends_agree": backends_agree,
        "by_backend": by_backend,
    }
    (out / "identity-control.json").write_text(json.dumps(summary, indent=2, sort_keys=True),
                                               encoding="utf-8")
    print()
    if mismatches:
        for mismatch in mismatches:
            print(f"MISMATCH {mismatch}")
        print(f"FAIL: the default path moved between builds; receipt {out / 'identity-control.json'}")
        return 1
    print(f"bit-identical across {', '.join(args.builds)} at each backend")
    if not backends_agree:
        print("the two backends differ from each other; the builds agree within a backend")
    print(f"receipt {out / 'identity-control.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
