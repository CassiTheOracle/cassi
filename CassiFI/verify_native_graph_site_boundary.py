"""Exercise the native decode boundary a graph-site dispatch waits for.

A graph-site intervention binds to exactly one decode step, so the native
preflight accepts a sequence that holds one unserviced token.  A freshly
created sequence holds an unserviced prompt of its own length and refuses
until an ordinary step reaches the first decode boundary.  The swarm defers
its token run across that boundary; this probe drives the same transition
against a real model and prints the receipts.

    python CassiFI/verify_native_graph_site_boundary.py \
        --model CassiQwen/Qwen3.5-0.8B-Q4_0.gguf --tokens 5

It checks three things: the prompt boundary refuses with the documented code,
one ordinary step services the prompt, and the same preflight is ready at the
boundary immediately after that step.  Exit code 0 means all three held.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "CassiFI") not in sys.path:
    sys.path.insert(0, str(ROOT / "CassiFI"))

from cassi_field_runtime_native import (  # noqa: E402  (path set above)
    NativeFieldRuntimeClient,
    NativeFieldRuntimeError,
)

DEFAULT_EXE = ROOT / "CassiFI/native/field-runtime/build/Release/cassifi-field-runtime.exe"
BOUNDARY_CODE = "native_sequence_not_at_single_token_boundary"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _runtime_exited(instance_id: str, timeout_s: float = 10.0) -> bool:
    try:
        import psutil
    except ImportError:
        return False
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        live = [
            process
            for process in psutil.process_iter(["name", "cmdline"])
            if "cassifi-field-runtime" in (process.info["name"] or "")
            and instance_id in " ".join(process.info["cmdline"] or [])
        ]
        if not live:
            return True
        time.sleep(0.25)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="GGUF the runtime serves")
    parser.add_argument("--exe", default=str(DEFAULT_EXE), help="native field-runtime binary")
    parser.add_argument("--tokens", type=int, default=5, help="prompt length to seed")
    parser.add_argument("--context-size", type=int, default=8192)
    parser.add_argument("--gpu-layers", type=int, default=-1)
    parser.add_argument("--cpu-only", action="store_true")
    args = parser.parse_args()

    model = Path(args.model).expanduser().resolve(strict=True)
    executable = Path(args.exe).expanduser().resolve(strict=True)
    source_sha256 = _sha256_file(model)
    sequence_sampler = {"mode": "categorical", "temperature": 0.8, "top_k": 40, "draw": 0.0}
    task_id = f"boundary-{secrets.token_hex(6)}"
    sequence_id = f"{task_id}-seq"
    receipt: dict[str, object] = {
        "model": str(model),
        "model_bytes": model.stat().st_size,
        "model_sha256": source_sha256,
        "executable": str(executable),
    }

    client = NativeFieldRuntimeClient.launch(
        executable, cpu_only=args.cpu_only, connect_timeout_s=30.0
    )
    instance_id = client.instance_id
    try:
        registered = client.register_model(
            source_sha256,
            model,
            context_size=args.context_size,
            gpu_layers=args.gpu_layers,
        )
        vocabulary_size = int(registered["vocabulary_size"])
        receipt["registered"] = registered
        prompt = tuple(31 + index for index in range(args.tokens))
        if prompt[-1] >= vocabulary_size:
            prompt = tuple(index % vocabulary_size for index in prompt)
        receipt["prompt_tokens"] = list(prompt)

        try:
            client.candidate_preflight(
                task_id,
                source_sha256,
                prompt,
                sequence_id=sequence_id,
                sampler=sequence_sampler,
                native_operation_id="op-0",
            )
        except NativeFieldRuntimeError as exc:
            refusal = str(exc)
            receipt["prompt_boundary_refusal"] = refusal
            if BOUNDARY_CODE not in refusal:
                raise
        else:
            raise AssertionError(
                "a sequence holding an unserviced prompt accepted a graph-site dispatch"
            )

        step = client.step_model(
            task_id,
            source_sha256,
            prompt,
            sampler_mode=sequence_sampler["mode"],
            temperature=sequence_sampler["temperature"],
            top_k=sequence_sampler["top_k"],
            draw=0.0,
            sequence_id=sequence_id,
            native_operation_id="op-0",
        )
        accepted = int(step["token"])
        receipt["ordinary_step"] = {
            "token": accepted,
            "token_count": step.get("token_count"),
            "sampler": step.get("sampler"),
            "exact_stages": step.get("exact_stages"),
        }
        if step.get("sampler", {}).get("mode") != sequence_sampler["mode"]:
            raise AssertionError(f"step sampler mode drifted: {step.get('sampler')!r}")

        boundary_history = (*prompt, accepted)
        preflight = client.candidate_preflight(
            task_id,
            source_sha256,
            boundary_history,
            sequence_id=sequence_id,
            sampler=sequence_sampler,
            native_operation_id="op-1",
        )
        receipt["boundary_preflight"] = {
            key: preflight.get(key)
            for key in ("ready", "next_position", "input_token_count", "task_id", "sequence_id")
        }
        sites = preflight.get("sites")
        receipt["boundary_site_summary"] = {
            "total": len(sites or ()),
            "supported": sum(1 for site in sites or () if site.get("supported")),
            "kinds": sorted({int(site["kind"]) for site in sites or () if "kind" in site}),
        }
        receipt["boundary_sites"] = [
            {
                key: site.get(key)
                for key in ("kind", "layer", "stage", "specialist", "supported", "source_sha256")
                if key in site
            }
            for site in sites or ()
            if site.get("supported")
        ]
        if preflight.get("ready") is not True:
            raise AssertionError("the boundary preflight did not report readiness")
        if preflight.get("next_position") != len(boundary_history) - 1:
            raise AssertionError(
                f"boundary preflight position {preflight.get('next_position')!r} "
                f"is not the pending token of a {len(boundary_history)}-token history"
            )
        receipt["status"] = "boundary-transition-verified"
    finally:
        client.shutdown()
    receipt["runtime_exited"] = _runtime_exited(instance_id)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if receipt.get("status") != "boundary-transition-verified" or not receipt["runtime_exited"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
