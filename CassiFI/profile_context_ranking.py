"""Measure CassiFI context-ranking stages without mutating field state."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Sequence
import torch

from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_persistent_provider import (
    EMPTY_CONTEXT_EVENT_ID,
    PersistentFieldProvider,
    ProviderConfig,
)

STAGES = ("validation", "encoding", "load", "scoring", "total")


def percentile(values: Sequence[float], proportion: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * proportion) - 1)]
def context_event(
    *,
    user: str,
    stream_id: str,
    sequence: int,
    previous_event_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    identity = {
        "stream_id": stream_id,
        "sequence": sequence,
        "previous_event_id": previous_event_id,
        "payload": payload,
    }
    event_id = hashlib.sha256(
        json.dumps(
            identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    return {**identity, "event_id": event_id, "user": user}


def relevance_trial(
    provider: PersistentFieldProvider,
    *,
    device: str,
) -> dict[str, Any]:
    topics = (
        (
            "typescript",
            "fix TypeScript build errors",
            "clean generated declarations before running the ordered typecheck",
            "repair tsc compilation failures",
        ),
        (
            "unicode",
            "preserve exact UTF-8 byte spans",
            "slice encoded UTF-8 bytes at revision-bound offsets",
            "keep multibyte character offsets exact",
        ),
        (
            "gpu",
            "reduce GPU context ranking latency",
            "batch independent candidate lanes on the live Qi field",
            "speed up many context candidates on the graphics card",
        ),
        (
            "sqlite",
            "migrate the feedback SQLite schema",
            "add the tool outcome column before inserting feedback",
            "upgrade the feedback database table",
        ),
    )
    second_paraphrases = (
        "resolve compiler diagnostics in the TypeScript workspace",
        "recover the precise byte slice around emoji",
        "make the batched ranker faster on ROCm",
        "alter the context receipt table for a new column",
    )
    user = "context-relevance"
    context_session_id = "relevance-context"
    stream_id = "context-relevance-stream"
    previous_event_id = EMPTY_CONTEXT_EVENT_ID
    sequence = 1
    candidates: list[dict[str, Any]] = []

    for candidate_id, _, text, _ in topics:
        revision = hashlib.sha256(
            f"{candidate_id}\0fact\0{text}".encode()
        ).hexdigest()
        candidate = {
            "id": candidate_id,
            "record_id": candidate_id,
            "revision": revision,
            "start_byte": 0,
            "end_byte": len(text.encode("utf-8")),
            "text": text,
        }
        candidates.append(candidate)
        event = context_event(
            user=user,
            stream_id=stream_id,
            sequence=sequence,
            previous_event_id=previous_event_id,
            payload={
                "kind": "memory",
                "context_session_id": "",
                "operation": "store",
                "record": {
                    "id": candidate_id,
                    "node_type": "fact",
                    "revision": revision,
                    "content": text,
                },
            },
        )
        provider.observe_context(event)
        previous_event_id = event["event_id"]
        sequence += 1

    for (candidate_id, query, _, _), candidate in zip(topics, candidates):
        event = context_event(
            user=user,
            stream_id=stream_id,
            sequence=sequence,
            previous_event_id=previous_event_id,
            payload={
                "kind": "feedback",
                "context_session_id": context_session_id,
                "turn_id": sequence,
                "query": query,
                "candidates": [candidate],
                "outcome": "completed",
            },
        )
        provider.observe_context(event)
        previous_event_id = event["event_id"]
        sequence += 1

    state_sha256: str | None = None

    def rank(query: str, target: str | None) -> dict[str, Any]:
        nonlocal state_sha256
        result = provider.rank_context({
            "user": user,
            "context_session_id": context_session_id,
            "query": query,
            "candidates": candidates,
        })
        if state_sha256 is None:
            state_sha256 = result["state_sha256"]
        elif result["state_sha256"] != state_sha256:
            raise RuntimeError("relevance trial mutated persistent field state")
        ordered = result["ranked"]
        scores = {item["id"]: item["score"] for item in ordered}
        row: dict[str, Any] = {
            "query": query,
            "ordered_ids": [item["id"] for item in ordered],
            "scores": scores,
        }
        if target is not None:
            row["target"] = target
            row["target_rank"] = row["ordered_ids"].index(target) + 1
            row["margin"] = scores[target] - max(
                score for candidate_id, score in scores.items()
                if candidate_id != target
            )
        return row

    exact = [rank(query, candidate_id) for candidate_id, query, _, _ in topics]
    controller = provider.controller
    store = provider.store
    if controller is None or store is None:
        raise RuntimeError("provider did not start")
    loaded = store.load(user)
    if loaded is None:
        raise RuntimeError("relevance trial state was not saved")
    persistent_state = loaded[0]
    persistent_sha256 = controller.state_sha256(persistent_state)
    initial_state = provider.initial_state
    if initial_state is None:
        raise RuntimeError("provider did not start")

    field_vectors: dict[str, torch.Tensor] = {}

    def field_vector(query: str) -> torch.Tensor:
        vector = field_vectors.get(query)
        if vector is None:
            sensed = controller.sense_user_message(persistent_state, query)
            vector = (sensed.field - persistent_state.field).reshape(-1)
            field_vectors[query] = vector
        return vector

    reference_vectors = {
        candidate_id: field_vector(query)
        for candidate_id, query, _, _ in topics
    }

    def similarity(
        query: str,
        target: str | None,
        references: dict[str, torch.Tensor],
    ) -> dict[str, Any]:
        current = field_vector(query)
        scores = {
            candidate_id: float(
                torch.nn.functional.cosine_similarity(
                    current,
                    reference,
                    dim=0,
                    eps=torch.finfo(current.dtype).eps,
                ).item()
            )
            for candidate_id, reference in references.items()
        }
        ordered_ids = sorted(scores, key=lambda candidate_id: -scores[candidate_id])
        row: dict[str, Any] = {
            "query": query,
            "ordered_ids": ordered_ids,
            "scores": scores,
        }
        if target is not None:
            row["target"] = target
            row["target_rank"] = ordered_ids.index(target) + 1
        return row

    similarity_exact = [
        similarity(query, candidate_id, reference_vectors)
        for candidate_id, query, _, _ in topics
    ]
    similarity_paraphrase = [
        similarity(paraphrase_query, candidate_id, reference_vectors)
        for candidate_id, _, _, paraphrase_query in topics
    ]
    similarity_null = similarity(
        "compose a melody for solo cello", None, reference_vectors
    )
    candidate_vectors = {
        candidate_id: field_vector(text)
        for candidate_id, _, text, _ in topics
    }
    candidate_similarity_exact = [
        similarity(query, candidate_id, candidate_vectors)
        for candidate_id, query, _, _ in topics
    ]
    candidate_similarity_paraphrase = [
        similarity(paraphrase_query, candidate_id, candidate_vectors)
        for candidate_id, _, _, paraphrase_query in topics
    ]
    candidate_similarity_null = similarity(
        "compose a melody for solo cello", None, candidate_vectors
    )
    if controller.state_sha256(persistent_state) != persistent_sha256:
        raise RuntimeError("prompt-similarity trial mutated persistent field state")
    paraphrase = [
        rank(paraphrase_query, candidate_id)
        for candidate_id, _, _, paraphrase_query in topics
    ]
    null = rank("compose a melody for solo cello", None)
    pre_adaptation_state_sha256 = state_sha256
    adaptation_trace: list[dict[str, Any]] = []
    for turn, ((_, _, _, paraphrase_query), candidate) in enumerate(
        zip(topics, candidates),
        start=1,
    ):
        event = context_event(
            user=user,
            stream_id=stream_id,
            sequence=sequence,
            previous_event_id=previous_event_id,
            payload={
                "kind": "feedback",
                "context_session_id": context_session_id,
                "turn_id": 100 + turn,
                "query": paraphrase_query,
                "candidates": [candidate],
                "outcome": "completed",
                "tool_result": {
                    "id": f"tc-adapt-{turn}",
                    "name": "pytest",
                    "is_error": False,
                },
            },
        )
        observed = provider.observe_context(event)
        adaptation_trace.append({
            "candidate_id": candidate["id"],
            "selected_ids": observed["selected_ids"],
            "forgotten_symbols": observed["forgotten_symbols"],
        })
        previous_event_id = event["event_id"]
        sequence += 1

    state_sha256 = None
    adapted_paraphrase = [
        rank(paraphrase_query, candidate_id)
        for candidate_id, _, _, paraphrase_query in topics
    ]
    held_out_transfer = [
        rank(paraphrase_query, candidate_id)
        for (candidate_id, _, _, _), paraphrase_query in zip(
            topics, second_paraphrases
        )
    ]
    post_adaptation_state_sha256 = state_sha256
    post_loaded = store.load(user)
    if post_loaded is None:
        raise RuntimeError("adapted relevance trial state was not saved")
    post_associations = provider._resident_associations(
        controller, initial_state, post_loaded[0]
    )
    return {
        "trial": "relevance",
        "device": device,
        "engine_fingerprint": provider.provider_fingerprint,
        "pre_adaptation_state_sha256": pre_adaptation_state_sha256,
        "post_adaptation_state_sha256": post_adaptation_state_sha256,
        "exact_top1": sum(row["target_rank"] == 1 for row in exact),
        "paraphrase_top1": sum(row["target_rank"] == 1 for row in paraphrase),
        "exact": exact,
        "paraphrase": paraphrase,
        "null": null,
        "adapted_paraphrase_top1": sum(
            row["target_rank"] == 1 for row in adapted_paraphrase
        ),
        "held_out_transfer_top1": sum(
            row["target_rank"] == 1 for row in held_out_transfer
        ),
        "adapted_paraphrase": adapted_paraphrase,
        "held_out_transfer": held_out_transfer,
        "adaptation_trace": adaptation_trace,
        "resident_capacity": {
            "trajectory_capacity": controller.config.trajectory_capacity,
            "base_events": len(controller.learned_events(initial_state)),
            "context_events": sum(
                association.event_count for association in post_associations
            ),
            "associations": [
                {
                    "kind": association.kind,
                    "candidate_id": association.candidate_id,
                    "query": json.loads(association.prompt.decode("utf-8"))[1],
                    "event_count": association.event_count,
                    "sequence": association.sequence,
                }
                for association in post_associations
            ],
        },
        "field_prompt_similarity": {
            "exact_top1": sum(
                row["target_rank"] == 1 for row in similarity_exact
            ),
            "paraphrase_top1": sum(
                row["target_rank"] == 1 for row in similarity_paraphrase
            ),
            "exact": similarity_exact,
            "paraphrase": similarity_paraphrase,
            "null": similarity_null,
        },
        "field_candidate_similarity": {
            "exact_top1": sum(
                row["target_rank"] == 1 for row in candidate_similarity_exact
            ),
            "paraphrase_top1": sum(
                row["target_rank"] == 1
                for row in candidate_similarity_paraphrase
            ),
            "exact": candidate_similarity_exact,
            "paraphrase": candidate_similarity_paraphrase,
            "null": candidate_similarity_null,
        },
    }




def interference_trial(
    provider: PersistentFieldProvider,
    *,
    device: str,
) -> dict[str, Any]:
    user = "context-interference"
    context_session_id = "interference-context"
    stream_id = "context-interference-stream"
    query = "repair the context runtime"
    text = "use the exact field-owned runtime evidence"
    revision = hashlib.sha256(f"runtime\0fact\0{text}".encode()).hexdigest()
    candidate = {
        "id": "runtime",
        "record_id": "runtime",
        "revision": revision,
        "start_byte": 0,
        "end_byte": len(text.encode("utf-8")),
        "text": text,
    }
    sequence = 1
    previous_event_id = EMPTY_CONTEXT_EVENT_ID
    stored = context_event(
        user=user,
        stream_id=stream_id,
        sequence=sequence,
        previous_event_id=previous_event_id,
        payload={
            "kind": "memory",
            "context_session_id": "",
            "operation": "store",
            "record": {
                "id": "runtime",
                "node_type": "fact",
                "revision": revision,
                "content": text,
            },
        },
    )
    provider.observe_context(stored)
    previous_event_id = stored["event_id"]
    sequence += 1
    trace: list[dict[str, Any]] = []

    for turn in range(8):
        is_error = turn % 2 == 1
        outcome = "error" if is_error else "completed"
        event = context_event(
            user=user,
            stream_id=stream_id,
            sequence=sequence,
            previous_event_id=previous_event_id,
            payload={
                "kind": "feedback",
                "context_session_id": context_session_id,
                "turn_id": turn,
                "query": query,
                "candidates": [candidate],
                "outcome": outcome,
                "tool_result": {
                    "id": f"tc-reversal-{turn}",
                    "name": "pytest",
                    "is_error": is_error,
                },
            },
        )
        observed = provider.observe_context(event)
        previous_event_id = event["event_id"]
        sequence += 1
        ranked = provider.rank_context({
            "user": user,
            "context_session_id": context_session_id,
            "query": query,
            "candidates": [candidate],
        })
        trace.append({
            "turn": turn,
            "outcome": outcome,
            "score": ranked["ranked"][0]["score"],
            "state_sha256": ranked["state_sha256"],
            "selected_ids": observed["selected_ids"],
            "working_kinds": sorted({
                item["kind"] for item in ranked["working"]
            }),
        })

    for turn in range(16):
        event = context_event(
            user=user,
            stream_id=stream_id,
            sequence=sequence,
            previous_event_id=previous_event_id,
            payload={
                "kind": "feedback",
                "context_session_id": context_session_id,
                "turn_id": 100 + turn,
                "query": f"follow-up task {turn}",
                "candidates": [],
                "outcome": "completed",
                "tool_result": {
                    "id": f"tc-load-{turn}",
                    "name": "read",
                    "is_error": False,
                },
            },
        )
        provider.observe_context(event)
        previous_event_id = event["event_id"]
        sequence += 1

    loaded = provider.rank_context({
        "user": user,
        "context_session_id": context_session_id,
        "query": "follow-up task 15",
        "candidates": [],
    })
    isolated = provider.rank_context({
        "user": user,
        "context_session_id": "other-context",
        "query": "follow-up task 15",
        "candidates": [],
    })
    working = loaded["working"]
    kind_counts = {
        kind: sum(item["kind"] == kind for item in working)
        for kind in ("goal", "artifact", "failure")
    }
    return {
        "trial": "interference",
        "device": device,
        "engine_fingerprint": provider.provider_fingerprint,
        "reversal_trace": trace,
        "completed_scores_positive": all(
            item["score"] > 0.0
            for item in trace
            if item["outcome"] == "completed"
        ),
        "error_scores_zero": all(
            item["score"] == 0.0
            for item in trace
            if item["outcome"] == "error"
        ),
        "working_count": len(working),
        "working_kind_counts": kind_counts,
        "latest_goal_present": any(
            item["kind"] == "goal" and item["text"] == "follow-up task 15"
            for item in working
        ),
        "oldest_goal_present": any(
            item["kind"] == "goal" and item["text"] == "follow-up task 0"
            for item in working
        ),
        "isolated_working_count": len(isolated["working"]),
        "loaded_timings_ms": loaded["timings_ms"],
        "state_sha256": loaded["state_sha256"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phi-config", type=Path, default=CONFIG_DIR / "cassi-phi-harmonic-language.json")
    parser.add_argument("--corpus-checkpoint", type=Path, default=ARTIFACT_DIR / "cassi-phi-harmonic-language" / "field-state.pt")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument(
        "--trial",
        choices=("profile", "relevance", "interference"),
        default="profile",
    )
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args(argv)
    if not 1 <= args.samples <= 100 or not 0 <= args.warmup <= 20:
        parser.error("samples must be 1..100 and warmup must be 0..20")

    with tempfile.TemporaryDirectory(prefix="cassi-context-profile-") as state_dir:
        provider = PersistentFieldProvider(ProviderConfig(
            phi_config_path=args.phi_config,
            corpus_checkpoint_path=args.corpus_checkpoint,
            state_dir=Path(state_dir),
            max_output_symbols=8,
            device=args.device,
        ))
        provider.start()
        try:
            if args.trial == "relevance":
                print(json.dumps(
                    relevance_trial(provider, device=args.device),
                    sort_keys=True,
                    indent=2,
                ))
                return 0
            if args.trial == "interference":
                print(json.dumps(
                    interference_trial(provider, device=args.device),
                    sort_keys=True,
                    indent=2,
                ))
                return 0
            user = "context-profile"
            context_session_id = "profile-context"
            query = "rank exact field-owned context evidence"
            candidates: list[dict[str, Any]] = []
            for index in range(32):
                candidate_id = f"profile-{index:02d}"
                text = f"context ranking candidate {index:02d} preserves exact field-owned evidence"
                revision = hashlib.sha256(
                    f"{candidate_id}\0fact\0{text}".encode()
                ).hexdigest()
                candidates.append({
                    "id": candidate_id,
                    "record_id": candidate_id,
                    "revision": revision,
                    "start_byte": 0,
                    "end_byte": len(text.encode("utf-8")),
                    "text": text,
                })

            stream_id = "context-profile-stream"
            previous_event_id = EMPTY_CONTEXT_EVENT_ID
            for sequence, candidate in enumerate(candidates, start=1):
                event = context_event(
                    user=user,
                    stream_id=stream_id,
                    sequence=sequence,
                    previous_event_id=previous_event_id,
                    payload={
                        "kind": "memory",
                        "context_session_id": "",
                        "operation": "store",
                        "record": {
                            "id": candidate["record_id"],
                            "node_type": "fact",
                            "revision": candidate["revision"],
                            "content": candidate["text"],
                        },
                    },
                )
                provider.observe_context(event)
                previous_event_id = event["event_id"]
            next_sequence = len(candidates) + 1
            for offset in range(0, len(candidates), 8):
                feedback = context_event(
                    user=user,
                    stream_id=stream_id,
                    sequence=next_sequence,
                    previous_event_id=previous_event_id,
                    payload={
                        "kind": "feedback",
                        "context_session_id": context_session_id,
                        "turn_id": offset // 8,
                        "query": query,
                        "candidates": candidates[offset : offset + 8],
                        "outcome": "completed",
                    },
                )
                provider.observe_context(feedback)
                previous_event_id = feedback["event_id"]
                next_sequence += 1

            profile: dict[str, Any] = {
                "device": args.device,
                "engine_fingerprint": provider.provider_fingerprint,
                "samples": args.samples,
                "counts": {},
            }
            for count in (1, 4, 8, 16, 32):
                request = {
                    "user": user,
                    "context_session_id": context_session_id,
                    "query": query,
                    "candidates": candidates[:count],
                }
                measurements = {stage: [] for stage in STAGES}
                for iteration in range(args.warmup + args.samples):
                    result = provider.rank_context(request)
                    timings = result["timings_ms"]
                    if iteration >= args.warmup:
                        for stage in STAGES:
                            measurements[stage].append(float(timings[stage]))
                profile["counts"][str(count)] = {
                    stage: {
                        "p50_ms": percentile(values, 0.50),
                        "p95_ms": percentile(values, 0.95),
                    }
                    for stage, values in measurements.items()
                }
            print(json.dumps(profile, sort_keys=True, indent=2))
        finally:
            provider.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
