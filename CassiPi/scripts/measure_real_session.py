"""Measure field-owned context projection on a real Oh My Pi session.

The stock host compacts by sending the whole context to the provider for a
summary. This measurement replays the material a real compaction had to digest
into a disposable field-owned runtime, observing every entry exactly the way the
installed extension does (canonical message bytes plus host replay metadata), and
projects it at the boundary the installed CassiPi profile uses. Zero provider
calls are made.

Reported per run:

- the real session's own compaction accounting, recorded by the stock host;
- the replayed segment's raw bytes, entries, and byte-estimated tokens;
- what the field selected at each evidence cap, with previews and whether the
  segment tail (latest user message, latest assistant text) survived selection;
- whether an early, relevance-rejected revision can still be forced back
  exactly, which is what makes the projection lossless in principle.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Iterable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

import measure_integration as mi  # noqa: E402  (local probe helper module)


SESSION_ROOT = Path.home() / ".omp" / "agent" / "sessions"
DEFAULT_RECEIPT = Path(__file__).resolve().parents[1] / "probes" / "receipts" / "real-session-projection.json"
HOST_REPLAY_SCHEMA = "cassipi.host-message-replay.v1"
HOST_REPLAY_VOLATILE_FIELDS = ["content[].thinkingSignature"]
# The worker rejects any request above 1 MiB, and the source is base64-encoded
# inside it. Entries larger than this cannot be observed as one source.
DEFAULT_MAX_SOURCE_BYTES = 640 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _largest_session() -> Path:
    candidates = [path for path in SESSION_ROOT.rglob("*.jsonl") if path.stat().st_size > 100_000]
    if not candidates:
        raise SystemExit(f"no session transcripts found under {SESSION_ROOT}")
    return max(candidates, key=lambda path: path.stat().st_size)


def read_session(path: Path) -> dict[str, Any]:
    """Return the session's entries in file order with their raw message objects."""
    messages: list[dict[str, Any]] = []
    compactions: list[dict[str, Any]] = []
    session_meta: dict[str, Any] = {}
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for index, line in enumerate(handle):
            if (
                '"type":"message"' not in line
                and '"type":"compaction"' not in line
                and '"type":"session"' not in line
            ):
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = entry.get("type")
            if kind == "session":
                session_meta = entry
            elif kind == "compaction":
                compactions.append(
                    {
                        "index": index,
                        "tokens_before": int(entry.get("tokensBefore") or 0),
                        "tokens_after": int(entry.get("tokensAfter") or 0),
                        "summary_chars": len(str(entry.get("summary") or "")),
                    }
                )
            elif kind == "message":
                raw = entry.get("message")
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                if not isinstance(raw, dict):
                    continue
                messages.append(
                    {
                        "index": index,
                        "entry_id": str(entry.get("id") or f"line-{index}"),
                        "timestamp": str(entry.get("timestamp") or "1970-01-01T00:00:00.000Z"),
                        "role": str(raw.get("role") or "unknown"),
                        "tool_call_id": raw.get("toolCallId"),
                        "message": raw,
                    }
                )
    return {"messages": messages, "compactions": compactions, "session": session_meta}


def select_segment(
    parsed: Mapping[str, Any],
    *,
    segment: str,
    max_messages: int,
) -> tuple[list[dict[str, Any]], str]:
    messages = list(parsed["messages"])
    compactions = list(parsed["compactions"])
    if not compactions:
        return messages[-max_messages:], "whole-session"
    boundary = compactions[-1]["index"]
    if segment == "tail":
        selected = [message for message in messages if message["index"] > boundary]
        label = "after-last-compaction"
    else:
        previous = compactions[-2]["index"] if len(compactions) > 1 else -1
        selected = [message for message in messages if previous < message["index"] < boundary]
        label = "digested-by-last-compaction"
    return selected[-max_messages:], label


def claim_category(role: str) -> str:
    if role == "user":
        return "user-instruction"
    if role == "assistant":
        return "assistant-claim"
    if role == "toolResult":
        return "action-outcome"
    return "tool-observation"


def _observe_request(
    scope: Mapping[str, str],
    *,
    entry: Mapping[str, Any],
    content: bytes,
    content_sha256: str,
    replay_sha256: str,
    producer_id: str,
    sequence: int,
    predecessor: str | None,
    parent_head: str,
) -> dict[str, Any]:
    role = str(entry["role"])
    event_kind = "action-outcome" if role == "toolResult" else "observation"
    native_identity = f"{entry['entry_id']}:{content_sha256}:{event_kind}"
    action_id = entry.get("tool_call_id")
    source = {
        "source_id": f"omp:{scope['session_id']}:{entry['entry_id']}",
        "content_base64": base64.b64encode(content).decode("ascii"),
        "content_sha256": content_sha256,
        "mime_type": "application/vnd.omp.event+json",
        "codec": "utf-8",
        "host_replay_schema": HOST_REPLAY_SCHEMA,
        "host_replay_sha256": replay_sha256,
        "host_replay_volatile_fields": list(HOST_REPLAY_VOLATILE_FIELDS),
        **scope,
        "native_source_entry_id": entry["entry_id"],
        "author_origin": "omp-host",
        "message_role": role,
        "observed_timestamp": entry["timestamp"],
        "claim_category": claim_category(role),
        "parent_revision_id": None,
        "fidelity": "exact-observed-bytes",
    }
    if action_id is not None:
        source["action_id"] = str(action_id)
    return {
        "schema": "cassipi.observe.v1",
        "operation_id": f"observe:{_sha256_bytes(f'{producer_id}:{native_identity}'.encode())}",
        "native_identity": native_identity,
        "producer_id": producer_id,
        "producer_sequence": sequence,
        "predecessor_event_id": predecessor,
        **scope,
        "parent_head_id": parent_head,
        "event_kind": event_kind,
        "source": source,
        "payload": {
            "memory_scope": "branch",
            "message_role": role,
            **({"action_id": str(action_id)} if action_id is not None else {}),
        },
        "native_entry_id": entry["entry_id"],
    }


def _project(
    descriptor: Mapping[str, Any],
    client_id: str,
    scope_token: str,
    projection_scope: Mapping[str, Any],
    inventory: Mapping[str, Any],
    token_counts: Mapping[str, int],
    *,
    window: int,
    host_overhead: int,
    reserve: int,
    protected_tokens: int,
) -> Mapping[str, Any]:
    return mi._attached(
        descriptor,
        "project",
        client_id,
        scope_token,
        {
            "schema": "cassipi.projection.v1",
            "scope": dict(projection_scope),
            "inventory_sha256": inventory["inventory_sha256"],
            "budget": {
                "schema": "cassipi.projection-budget.v1",
                "context_window_tokens": window,
                "system_tokens": 0,
                "tool_schema_tokens": 0,
                "protected_tokens": protected_tokens,
                "image_tokens": 0,
                "current_request_tokens": 0,
                "reserved_output_tokens": reserve,
                "host_overhead_tokens": host_overhead,
            },
            "token_counts": dict(token_counts),
        },
    )


def _preview(row: Mapping[str, Any], limit: int = 220) -> str:
    message = row.get("message") if isinstance(row, Mapping) else None
    content = message.get("content") if isinstance(message, Mapping) else None
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = " ".join(
            str(block.get("text") or "")
            for block in content
            if isinstance(block, Mapping) and block.get("type") == "text"
        )
    else:
        text = json.dumps(message)[:limit]
    return " ".join(text.split())[:limit]


def _run(args: argparse.Namespace) -> dict[str, Any]:
    session_path = (args.session or _largest_session()).expanduser().resolve()
    parsed = read_session(session_path)
    segment, segment_label = select_segment(parsed, segment=args.segment, max_messages=args.max_messages)
    if not segment:
        raise SystemExit("selected segment contains no messages")

    runtime = args.runtime.expanduser().resolve()
    sys.path.insert(0, str(runtime))
    from cassi_cassipi_v2 import _host_message_replay_sha256  # noqa: PLC0415
    from cassi_field_atlas import canonical_json_bytes  # noqa: PLC0415

    encoded: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry in segment:
        content = canonical_json_bytes(entry["message"])
        record = {
            "entry": entry,
            "content": content,
            "bytes": len(content),
            "replay_sha256": _host_message_replay_sha256(entry["message"]),
        }
        if len(content) > args.max_source_bytes:
            skipped.append(
                {
                    "entry_id": entry["entry_id"],
                    "role": entry["role"],
                    "bytes": len(content),
                }
            )
            continue
        encoded.append(record)

    raw_bytes = sum(record["bytes"] for record in encoded) + sum(item["bytes"] for item in skipped)
    observed_bytes = sum(record["bytes"] for record in encoded)

    session_id = str(parsed["session"].get("id") or session_path.stem)
    scope = {
        "profile_id": "omp-main",
        "project_id": "cassi",
        "session_id": f"omp-session:{session_id}",
        "branch_id": "branch-main",
        "task_scope": "task-main",
    }
    latest_user = next(
        (entry for entry in reversed(segment) if entry["role"] == "user" and entry in [r["entry"] for r in encoded]),
        None,
    )
    latest_assistant = next(
        (entry for entry in reversed(segment) if entry["role"] == "assistant" and entry in [r["entry"] for r in encoded]),
        None,
    )
    tail_digests = {
        label: _sha256_bytes(record["content"])
        for label, entry in (("latest_user", latest_user), ("latest_assistant", latest_assistant))
        if entry is not None
        for record in [next(r for r in encoded if r["entry"] is entry)]
    }

    with tempfile.TemporaryDirectory(prefix="cassipi-real-session-") as temporary:
        root = Path(temporary)
        data_home = root / "data-home"
        process = mi._launch(runtime, data_home, root / "outside-checkout")
        descriptor: Mapping[str, Any] = {}
        projections: list[dict[str, Any]] = []
        client_id = "real-session-replay"
        try:
            descriptor, cold_start_ms = mi._wait_descriptor(data_home, process)
            handshake = mi._rpc(descriptor, "handshake", {"expected": {"runtime_id": mi.RUNTIME_ID}})
            scope_tokens: dict[str, str] = {}

            def token_for(task_scope: str) -> str:
                if task_scope not in scope_tokens:
                    scope_tokens[task_scope] = mi._attach(descriptor, client_id, {**scope, "task_scope": task_scope})
                return scope_tokens[task_scope]

            scope_token = token_for(scope["task_scope"])
            predecessor: str | None = None
            first_revision: str | None = None
            first_digest: str | None = None
            active_task = scope["task_scope"]
            observe_started = time.perf_counter()
            slowest: list[dict[str, Any]] = []
            for sequence, record in enumerate(encoded):
                entry = record["entry"]
                if entry["role"] == "user":
                    active_task = entry["entry_id"]
                entry_started = time.perf_counter()
                owner = mi._owner_status(descriptor, timeout=args.rpc_timeout)
                request = _observe_request(
                    {**scope, "task_scope": active_task},
                    entry=entry,
                    content=record["content"],
                    content_sha256=_sha256_bytes(record["content"]),
                    replay_sha256=record["replay_sha256"],
                    producer_id=client_id,
                    sequence=sequence,
                    predecessor=predecessor,
                    parent_head=owner["field_head_sha256"],
                )
                result = mi._observe(
                    descriptor, client_id, token_for(active_task), request, timeout=args.rpc_timeout
                )
                predecessor = str(result["event_id"])
                if first_revision is None:
                    first_revision = str(result["source"]["revision_id"])
                    first_digest = _sha256_bytes(record["content"])
                elapsed_ms = (time.perf_counter() - entry_started) * 1000
                slowest.append(
                    {"entry_id": entry["entry_id"], "bytes": record["bytes"], "observe_ms": round(elapsed_ms, 1)}
                )
                if args.progress and (sequence + 1) % args.progress == 0:
                    print(
                        f"observed {sequence + 1}/{len(encoded)} entries in "
                        f"{(time.perf_counter() - observe_started):.0f}s",
                        file=sys.stderr,
                        flush=True,
                    )
            observe_ms = (time.perf_counter() - observe_started) * 1000
            slowest.sort(key=lambda row: row["observe_ms"], reverse=True)

            task = ""
            if latest_user is not None:
                task = mi._canonical(latest_user["message"]).decode("utf-8")[:4000]
            task = task or "continue current task"

            for cap in args.evidence_caps:
                window = args.host_overhead + args.output_reserve + cap
                projection_scope = mi._projection_scope(
                    descriptor,
                    scope,
                    task=task,
                    provider_call_id=f"real-session-cap-{cap}",
                    allowed_memory_scopes=["branch", "task"],
                )
                inventory = mi._attached(
                    descriptor, "projection_inventory", client_id, scope_token, dict(projection_scope)
                )
                token_counts = mi._token_counts(inventory)
                started = time.perf_counter()
                result = _project(
                    descriptor,
                    client_id,
                    scope_token,
                    projection_scope,
                    inventory,
                    token_counts,
                    window=window,
                    host_overhead=args.host_overhead,
                    reserve=args.output_reserve,
                    protected_tokens=0,
                )
                latency_ms = (time.perf_counter() - started) * 1000
                digests = {
                    str(row["source"]["content_sha256"]): row for row in result["selected"] if row.get("source")
                }
                projections.append(
                    {
                        "evidence_cap_tokens": cap,
                        "context_window_tokens": window,
                        "candidate_count": len(inventory["candidates"]),
                        "selected_count": len(result["selected"]),
                        "selected_tokens": sum(int(row.get("tokens") or 0) for row in result["selected"]),
                        "selected_mandatory": sum(1 for row in result["selected"] if row.get("mandatory")),
                        "tail_present": {label: digest in digests for label, digest in tail_digests.items()},
                        "latency_ms": round(latency_ms, 1),
                        "accounting": result.get("accounting"),
                        "previews": [
                            {
                                "representation": row.get("representation"),
                                "mandatory": bool(row.get("mandatory")),
                                "tokens": row.get("tokens"),
                                "field_score": row.get("field_score"),
                                "native_entry_id": row["source"].get("native_source_entry_id"),
                                "message_role": row["source"].get("message_role"),
                                "preview": _preview(row),
                            }
                            for row in result["selected"]
                        ],
                    }
                )

            mandatory_result: dict[str, Any] = {}
            if first_revision is not None:
                cap = args.evidence_caps[-1]
                window = args.host_overhead + args.output_reserve + cap
                projection_scope = mi._projection_scope(
                    descriptor,
                    scope,
                    task="recall the earliest replayed entry exactly",
                    provider_call_id="real-session-mandatory",
                    mandatory=[first_revision],
                    allowed_memory_scopes=["branch", "task"],
                )
                inventory = mi._attached(
                    descriptor, "projection_inventory", client_id, scope_token, dict(projection_scope)
                )
                token_counts = mi._token_counts(inventory)
                result = _project(
                    descriptor,
                    client_id,
                    scope_token,
                    projection_scope,
                    inventory,
                    token_counts,
                    window=window,
                    host_overhead=args.host_overhead,
                    reserve=args.output_reserve,
                    protected_tokens=0,
                )
                mandatory_result = {
                    "revision_id": first_revision,
                    "selected_count": len(result["selected"]),
                    "selected_tokens": sum(int(row.get("tokens") or 0) for row in result["selected"]),
                    "exact_bytes_present": any(
                        str(row["source"].get("content_sha256")) == first_digest for row in result["selected"]
                    ),
                }

            runtime_identity = {
                "runtime_id": handshake["owner"]["runtime_id"],
                "manifest_sha256": handshake["owner"].get("manifest_sha256"),
            }
        finally:
            try:
                if descriptor:
                    mi._rpc(descriptor, "detach", {"client_id": client_id})
                    mi._rpc(descriptor, "shutdown", {"if_idle": True})
            except Exception:  # pragma: no cover - shutdown is best effort
                pass
            try:
                process.wait(timeout=30)
            except Exception:  # pragma: no cover
                process.kill()
                process.wait(timeout=30)

    last_compaction = parsed["compactions"][-1] if parsed["compactions"] else {}
    session_wide = {
        "compaction_events": len(parsed["compactions"]),
        "provider_input_tokens_spent_summarizing": sum(item["tokens_before"] for item in parsed["compactions"]),
        "retained_after_compactions": sum(item["tokens_after"] for item in parsed["compactions"]),
        "summary_tokens_est": math.ceil(sum(item["summary_chars"] for item in parsed["compactions"]) / 4),
    }
    receipt = {
        "schema": "cassipi.real-session-projection.v1",
        "created_at": _utc_now(),
        "runtime": runtime_identity,
        "session": {
            "path": str(session_path),
            "bytes": session_path.stat().st_size,
            "id": session_id,
            "cwd": parsed["session"].get("cwd"),
            "compaction_events": session_wide["compaction_events"],
            "last_compaction": last_compaction,
            "session_wide_compaction_accounting": session_wide,
        },
        "replayed_segment": {
            "selection": segment_label,
            "entries": len(segment),
            "observed_sources": len(encoded),
            "skipped_oversized_sources": skipped,
            "observed_bytes": observed_bytes,
            "raw_bytes": raw_bytes,
            "byte_estimated_tokens": math.ceil(raw_bytes / 4),
            "roles": {
                role: sum(1 for record in encoded if record["entry"]["role"] == role)
                for role in sorted({record["entry"]["role"] for record in encoded})
            },
            "observe_ms": round(observe_ms, 1),
            "slowest_observations": slowest[:5],
        },
        "budget": {
            "host_overhead_tokens": args.host_overhead,
            "output_reserve_tokens": args.output_reserve,
            "evidence_caps_tokens": args.evidence_caps,
            "provider_calls": 0,
        },
        "projections": projections,
        "mandatory_exact_recall": mandatory_result,
        "cold_start_ms": round(cold_start_ms, 1),
    }
    problems: list[str] = []
    for projection in projections:
        if projection["selected_tokens"] > projection["evidence_cap_tokens"]:
            problems.append(f"cap {projection['evidence_cap_tokens']} overspent: {projection['selected_tokens']}")
        if projection["selected_count"] < 1:
            problems.append(f"cap {projection['evidence_cap_tokens']} selected nothing")
    if mandatory_result and mandatory_result.get("exact_bytes_present") is not True:
        problems.append("mandatory exact recall did not return the earliest replayed bytes")
    receipt["verdict"] = "PASS" if not problems else "FAIL"
    receipt["problems"] = problems
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, help="Session transcript; defaults to the largest one on disk.")
    parser.add_argument(
        "--segment",
        choices=["last-compaction", "tail"],
        default="last-compaction",
        help="Replay the material the last compaction digested, or the tail after it.",
    )
    parser.add_argument("--max-messages", type=int, default=800)
    parser.add_argument(
        "--rpc-timeout",
        type=float,
        default=300.0,
        help="Seconds to allow one owner call; large observations take longer than the default 60 s.",
    )
    parser.add_argument("--progress", type=int, default=50, help="Print progress every N observations; 0 disables.")
    parser.add_argument("--max-source-bytes", type=int, default=DEFAULT_MAX_SOURCE_BYTES)
    parser.add_argument("--host-overhead", type=int, default=22_000)
    parser.add_argument("--output-reserve", type=int, default=8_192)
    parser.add_argument(
        "--evidence-caps",
        type=lambda value: [int(item) for item in value.split(",")],
        default=[16_384, 49_152],
    )
    parser.add_argument(
        "--runtime",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "fi-runtime",
        help="Packaged runtime root to measure against.",
    )
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    receipt = _run(args)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": receipt["verdict"],
                "receipt": str(args.receipt),
                "segment": receipt["replayed_segment"]["selection"],
                "entries": receipt["replayed_segment"]["entries"],
                "observed": receipt["replayed_segment"]["observed_sources"],
                "skipped_oversized": len(receipt["replayed_segment"]["skipped_oversized_sources"]),
                "raw_tokens_est": receipt["replayed_segment"]["byte_estimated_tokens"],
                "projections": [
                    {
                        "cap": projection["evidence_cap_tokens"],
                        "candidates": projection["candidate_count"],
                        "selected": projection["selected_count"],
                        "tokens": projection["selected_tokens"],
                        "mandatory": projection["selected_mandatory"],
                        "tail_present": projection["tail_present"],
                    }
                    for projection in receipt["projections"]
                ],
                "mandatory_exact_recall": receipt["mandatory_exact_recall"],
                "problems": receipt["problems"],
            },
            indent=1,
            sort_keys=True,
        )
    )
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
