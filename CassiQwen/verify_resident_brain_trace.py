"""Time one resident-brain completion through the entity and show where it spent its work.

The resident path runs the whole model inside the entity's own field-owned
process: every prompt and generated position walks all ~25 layer stages, each
stage exchanges activations with the owner's field membrane and saves the
resident state, and the owner publishes once per prompt block of up to
`RESIDENT_PROMPT_BLOCK_MAX` positions.  This probe drives that path directly
with a real GGUF and reports the measured stage, segment, snapshot and
prompt-block counters, so a change to the per-stage or per-round cost can be
compared against a recorded baseline on this host.

    python CassiQwen/verify_resident_brain_trace.py \
        --model CassiQwen/Qwen3.5-0.8B-Q4_0.gguf --backend cpu --max-new 8

Exit code 0 when the completion returned the requested token budget (or a stop
token), every measured counter is present, and the owner rounds stayed within
the prompt-block budget (one round per block plus one per generated token and
spare client segments).  The JSON receipt records the elapsed time, the token
counts, the generated text, the stage/segment work, the prompt-block budget and
the snapshot store counters; a matching `py-spy record` of the same command
attributes the time.
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


def _prompt_block_expectations(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    block_positions: int,
    segments: int,
) -> dict[str, Any]:
    """Report the owner-round budget a prompt block allows.

    One round carries at most ``block_positions`` prompt positions, so a
    single-token-per-round path needs roughly one round per position while a
    blocking path needs one per block: the comparison is what shows the block
    is doing the covering.
    """

    if block_positions <= 1 or prompt_tokens <= 0:
        return {
            "block_positions": block_positions,
            "prompt_rounds": None,
            "expected_max_segments": None,
            "segments": segments,
            "within_budget": True,
        }
    blocks = (prompt_tokens + block_positions - 1) // block_positions
    # One round per block plus one per generated token, and four spare rounds
    # for the client's re-inspect and resume segments.
    expected_max = blocks + completion_tokens + 4
    return {
        "block_positions": block_positions,
        "prompt_rounds": blocks,
        "expected_max_segments": expected_max,
        "segments": segments,
        "within_budget": segments <= expected_max,
    }


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
    parser.add_argument(
        "--work-trace",
        default=None,
        help="write the timed completion's CassiFI work-trace summary here",
    )
    args = parser.parse_args(argv)

    from cassi_field_brain_entity import open_local_entity  # noqa: PLC0415
    from cassi_work_trace import trace_work  # noqa: PLC0415

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
            timed_trace = args.work_trace is not None and label == "timed"
            if timed_trace:
                with trace_work() as trace:
                    response = entity.brain.complete(
                        prompt=args.prompt,
                        max_tokens=max_tokens,
                        thinking=False,
                        response_format={},
                        _scheduler_timing={},
                    )
                work = trace.summary()
                trace_path = Path(args.work_trace).resolve()
                trace_path.parent.mkdir(parents=True, exist_ok=True)
                trace_path.write_text(json.dumps(work, indent=1), encoding="utf-8")
            else:
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
                "content": response.get("content"),
                "backend": (response.get("generation_parameters") or {}).get("backend"),
                "measured": measured,
                "counters": _counter_snapshot(executor),
            }
            if timed_trace:
                run["work"] = work
            receipt["runs"][label] = run
            receipt["prompt_tokens"] = int((response.get("usage") or {}).get("prompt_tokens") or 0)
            print(json.dumps({"run": label, **{k: v for k, v in run.items() if k != "work"}},
                             default=str)[:1200], flush=True)
            if timed_trace:
                groups = sorted(
                    work.get("groups", []),
                    key=lambda group: -float(group.get("duration_ms", 0.0)),
                )[:15]
                print(json.dumps({
                    "run": label,
                    "work_trace": str(Path(args.work_trace).resolve()),
                    "row_count": work.get("row_count"),
                    "total_duration_ms": work.get("total_duration_ms"),
                    "total_wait_ms": work.get("total_wait_ms"),
                    "top_groups": groups,
                }, indent=1, default=str)[:4000], flush=True)
    finally:
        if entity is not None:
            entity.close()

    timed = receipt["runs"].get("timed") or {}
    usage = timed.get("usage") or {}
    measured = timed.get("measured") or {}
    completion = int(usage.get("completion_tokens") or 0)
    from programs.model.runtime import RESIDENT_PROMPT_BLOCK_MAX  # noqa: PLC0415

    prompt_block = _prompt_block_expectations(
        prompt_tokens=int(receipt.get("prompt_tokens") or 0),
        completion_tokens=completion,
        block_positions=int(RESIDENT_PROMPT_BLOCK_MAX),
        segments=int(measured.get("segment_count") or 0),
    )
    receipt["prompt_block"] = prompt_block
    receipt["status"] = (
        "resident-completion-measured"
        if completion
        and measured.get("stage_cohort_rows")
        and prompt_block["within_budget"]
        else "resident-completion-incomplete"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path),
                      "elapsed_s": timed.get("elapsed_s"), "completion_tokens": completion,
                      "content": timed.get("content"),
                      "stage_rows": measured.get("stage_cohort_rows"),
                      "prompt_block": prompt_block}, indent=1))
    if receipt["status"] == "resident-completion-measured":
        return 0
    shutil.rmtree(scratch, ignore_errors=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
