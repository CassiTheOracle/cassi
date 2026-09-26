"""Prove that a native token run reproduces the one-token path exactly.

A token run decodes up to `NATIVE_TOKEN_RUN_MAX` tokens inside one owner
admission and records each token as its own continuation row.  The run's rows
must equal what the same owner produces one token at a time, for greedy,
categorical and stop-token sampling, and after clearing the runtime's task
cooperation so the owner rebuilds each round from its own history.

    python CassiFI/verify_native_token_runs.py \
        --model CassiQwen/Qwen3.5-0.8B-Q4_0.gguf

It runs five short programs against a real GGUF and prints one JSON receipt:
a greedy token run, the same prompt one token at a time, the greedy run rebuilt
from owner history, a stop-token run and its one-token twin, and a categorical
run rebuilt from owner history with its one-token twin.  Exit code 0 means
every pair matched token for token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "CassiFI") not in sys.path:
    sys.path.insert(0, str(ROOT / "CassiFI"))

from cassi_field_owner import FieldIntelligenceOwner  # noqa: E402  (path set above)
from cassi_field_runtime import ResidentFieldRuntime  # noqa: E402
from cassi_field_runtime_native import NativeFieldRuntimeClient  # noqa: E402
from cassi_programmable_swarm import ProgrammableSwarm  # noqa: E402
from programs.model.gguf import inspect_gguf  # noqa: E402
from programs.model.records import build_model_package  # noqa: E402
import programs.model.runtime as model_runtime  # noqa: E402

DEFAULT_EXE = ROOT / "CassiFI/native/field-runtime/build/Release/cassifi-field-runtime.exe"
PROMPT = (785, 6722, 315, 9625, 374)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="GGUF the runtime serves")
    parser.add_argument("--exe", default=str(DEFAULT_EXE), help="native field-runtime binary")
    parser.add_argument("--placement", default="vulkan", help="swarm placement for the model task")
    parser.add_argument("--max-new", type=int, default=20, help="tokens each program generates")
    parser.add_argument("--context-size", type=int, default=512)
    parser.add_argument(
        "--cpu-only",
        action="store_true",
        help="run the native runtime without a device backend",
    )
    args = parser.parse_args()

    model = Path(args.model).expanduser().resolve(strict=True)
    executable = Path(args.exe).expanduser().resolve(strict=True)
    source_sha256 = _sha256_file(model)
    manifest = inspect_gguf(model)
    package = build_model_package(
        program_id="verify-native-token-runs",
        architecture=manifest["metadata"]["general.architecture"],
        graph=[
            {
                "operation_id": "native",
                "stage": "model",
                "op": "native-transformer",
                "inputs": [],
                "output": None,
                "parameters": {
                    "source_id": manifest["source_id"],
                    "source_sha256": source_sha256,
                },
                "state_effects": ["native-model-continuation"],
            }
        ],
        tensors={},
        tokenizer=manifest["tokenizer"],
        primitive_contracts=("immutable-gguf-v1", "model-continuation-v1"),
    )

    scratch = Path(tempfile.mkdtemp(prefix="verify-token-runs-", dir=tempfile.gettempdir()))
    receipt: dict[str, Any] = {
        "model": str(model),
        "model_sha256": source_sha256,
        "executable": str(executable),
        "placement": args.placement,
        "scratch": str(scratch),
        "runs": {},
    }
    categorical = {"mode": "categorical", "temperature": 0.8, "top_k": 40}
    runtime: ResidentFieldRuntime | None = None

    def run(label: str, *, runs: bool, sampler: Mapping[str, Any] | None = None,
            rng_seed: int = 1, stop_tokens: tuple[int, ...] = (), rebuild: bool = False) -> list[int]:
        nonlocal runtime
        model_runtime.NATIVE_TOKEN_RUN_MAX = 8 if runs else 1
        if runtime is not None:
            runtime.shutdown()
        client = NativeFieldRuntimeClient.launch(
            executable, instance_id=f"verify-{label}-{secrets.token_hex(4)}",
            device_index=0, cpu_only=args.cpu_only, connect_timeout_s=60.0,
        )
        runtime = ResidentFieldRuntime(native_client=client)
        owner = FieldIntelligenceOwner(scratch / label)
        swarm = ProgrammableSwarm()
        swarm.add_member("a", owner, computer_id=f"verify-{label}", runtime=runtime,
                         placement=args.placement)
        swarm.ensure_computer("a")
        swarm.ensure_program_runtime("a")
        swarm.bind_model_backing(source_sha256, str(model), context_size=args.context_size,
                                 gpu_layers=-1)
        started = swarm.start_model(
            "a", package, prompt_tokens=PROMPT, max_new_tokens=args.max_new,
            stop_tokens=stop_tokens, sampler=sampler, rng_seed=rng_seed,
            placement=args.placement, steps=0, task_id=f"task-{label}",
        )
        task_id = started["task_id"]
        swarm._invoke_runtime("a", {"operation": "advance-task", "task_id": task_id,
                                    "quantum": 1, "arguments": {}})
        rounds = 0
        run_lengths: list[int] = []
        started_ns = time.perf_counter_ns()
        while swarm.inspect("a", task_id=task_id)["status"] not in {"completed", "faulted", "cancelled"}:
            if rebuild:
                # Force the owner to rebuild this round from its own accepted history.
                swarm._native_task_sync.clear()
            result = swarm.step("a", task_id=task_id)
            rounds += 1
            group = (result.get("native_model") or {}).get("group") or {}
            cohort = (group.get("cohort") or [{}])[0]
            run_lengths.append(int((cohort.get("run") or {}).get("length", 1)))
            if rounds > args.max_new + 4:
                raise AssertionError(f"{label}: task did not complete in {rounds} rounds")
        state = swarm.raw_state("a", task_id=task_id)
        task_state = state["tasks"][task_id]["state"] if "tasks" in state else state
        tokens = [int(token) for token in task_state["generated_tokens"]]
        receipt["runs"][label] = {
            "tokens": tokens,
            "rounds": rounds,
            "run_lengths": run_lengths,
            "elapsed_s": round((time.perf_counter_ns() - started_ns) / 1e9, 2),
        }
        return tokens

    try:
        greedy = run("greedy-run", runs=True)
        one_at_a_time = run("greedy-single", runs=False)
        assert greedy == one_at_a_time, ("greedy token run and one-token path differ",
                                        greedy, one_at_a_time)
        rebuilt = run("greedy-run-rebuild", runs=True, rebuild=True)
        assert rebuilt == greedy, ("greedy token run rebuilt from owner history differs",
                                   rebuilt, greedy)
        stop = greedy[3]
        stopped = run("stop-run", runs=True, stop_tokens=(stop,))
        stopped_single = run("stop-single", runs=False, stop_tokens=(stop,))
        assert stopped == stopped_single and stopped[-1] == stop, (
            "stop-token run and one-token path differ", stopped, stopped_single)
        sampled = run("cat-run-rebuild", runs=True, sampler=categorical, rng_seed=7, rebuild=True)
        sampled_single = run("cat-single", runs=False, sampler=categorical, rng_seed=7)
        assert sampled == sampled_single, (
            "categorical run and one-token path differ", sampled, sampled_single)
        receipt["status"] = "token-runs-match-one-token-path"
        receipt["stop_token"] = stop
    finally:
        if runtime is not None:
            runtime.shutdown()
        shutil.rmtree(scratch, ignore_errors=True)

    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("status") == "token-runs-match-one-token-path" else 1


if __name__ == "__main__":
    raise SystemExit(main())
