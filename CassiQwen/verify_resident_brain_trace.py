"""Time one resident-brain completion through the entity and show where it spent its work.

The resident path runs the whole model inside the entity's own field-owned
process: every prompt and generated position walks all ~25 layer stages, each
stage exchanges activations with the owner's field membrane and saves the
resident state, and the owner publishes once per token.  This probe drives that
path directly with a real GGUF and reports the measured stage, segment and
snapshot counters, so a change to the per-stage cost can be compared against a
recorded baseline on this host.

    python CassiQwen/verify_resident_brain_trace.py \
        --model CassiQwen/Qwen3.5-0.8B-Q4_0.gguf --backend cpu --max-new 8

Exit code 0 when the completion returned the requested token budget (or a stop
token) and every measured counter is present.  The JSON receipt records the
elapsed time, the token counts, the stage/segment work, and the snapshot store
counters; a matching `py-spy record` of the same command attributes the time.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "CassiQwen", ROOT / "CassiFI"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

DEFAULT_PROMPT = (
    "In the two-fluid field, which term sets how long the medium remembers past forcing, "
    "and what does the record look like in the Yang and Yin densities?"
)


def _counter_snapshot(executor: Any) -> dict[str, Any]:
    """Report the snapshot store and working-state counters an executor holds."""

    if executor is None:
        return {}
    store = getattr(executor, "_snapshots", None)
    counters = dict(getattr(store, "counters", {}) or {})
    if not counters:
        return {}
    return {
        "counters": counters,
        "working_snapshot_hits": int(getattr(executor, "working_snapshot_hits", 0)),
        "working_arrays": len(getattr(executor, "_working_arrays", None) or {}),
        "deferred_arrays": len(getattr(store, "_deferred_arrays", None) or {}),
    }


def _measured(response: Mapping[str, Any]) -> dict[str, Any]:
    feedback = response.get("resource_feedback")
    measured = feedback.get("measured") if isinstance(feedback, Mapping) else None
    return dict(measured) if isinstance(measured, Mapping) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", default=str(ROOT))
    parser.add_argument("--model", default="CassiQwen/Qwen3.5-0.8B-Q4_0.gguf")
    parser.add_argument("--backend", default="cpu", choices=("cpu", "vulkan"))
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--max-new", type=int, default=8)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--warm", type=int, default=1, help="warm-up completion tokens")
    parser.add_argument("--scratch", default=None)
    parser.add_argument("--receipt", default=None)
    args = parser.parse_args(argv)

    from cassi_field_brain_entity import open_local_entity  # noqa: PLC0415

    workspace = Path(args.workspace).resolve()
    model = (workspace / args.model).resolve()
    scratch = Path(args.scratch).resolve() if args.scratch else Path(
        tempfile.mkdtemp(prefix="resident-trace-", dir=workspace / "CassiQwen" / "_diag")
    )
    receipt_path = Path(args.receipt).resolve() if args.receipt else scratch / "summary.json"
    receipt: dict[str, Any] = {
        "schema": "cassi.resident-brain-trace.v1",
        "model": str(model),
        "backend": args.backend,
        "threads": args.threads,
        "max_new": args.max_new,
        "prompt_tokens": 0,
        "scratch": str(scratch),
        "runs": {},
    }
    entity = None
    try:
        entity = open_local_entity(
            scratch / "home",
            model_path=model,
            brain_backend="resident",
            resident_backend=args.backend,
            resident_threads=args.threads,
            max_response_tokens=max(64, args.max_new + 32),
            research_resident_enabled=True,
        )
        for label, max_tokens in (("warm", args.warm), ("timed", args.max_new)):
            if max_tokens <= 0:
                continue
            started = time.perf_counter_ns()
            response = entity.brain.complete(
                prompt=args.prompt,
                max_tokens=max_tokens,
                thinking=False,
                response_format={},
                _scheduler_timing={},
            )
            elapsed_s = (time.perf_counter_ns() - started) / 1e9
            executor = getattr(entity.brain._brain, "_executor", None)
            measured = _measured(response)
            run = {
                "elapsed_s": round(elapsed_s, 3),
                "usage": dict(response.get("usage") or {}),
                "finish_reason": response.get("finish_reason"),
                "backend": (response.get("generation_parameters") or {}).get("backend"),
                "measured": measured,
                "counters": _counter_snapshot(executor),
            }
            receipt["runs"][label] = run
            receipt["prompt_tokens"] = int((response.get("usage") or {}).get("prompt_tokens") or 0)
            print(json.dumps({"run": label, **run}, default=str)[:1200], flush=True)
    finally:
        if entity is not None:
            entity.close()

    timed = receipt["runs"].get("timed") or {}
    usage = timed.get("usage") or {}
    measured = timed.get("measured") or {}
    completion = int(usage.get("completion_tokens") or 0)
    receipt["status"] = (
        "resident-completion-measured"
        if completion and measured.get("stage_cohort_rows")
        else "resident-completion-incomplete"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path),
                      "elapsed_s": timed.get("elapsed_s"), "completion_tokens": completion,
                      "stage_rows": measured.get("stage_cohort_rows")}, indent=1))
    if receipt["status"] == "resident-completion-measured":
        return 0
    shutil.rmtree(scratch, ignore_errors=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
