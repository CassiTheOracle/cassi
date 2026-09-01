"""Exercise live field-owned context relevance, outcome steering, and restart."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Sequence


from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_persistent_provider import (
    EMPTY_CONTEXT_EVENT_ID,
    PersistentFieldProvider,
    ProviderConfig,
)

_CONTEXT_SESSION_ID = "live-steering-context"
_TARGET_ID = "typescript"
_STEERING_QUERY = "repair tsc compilation failures"
_TOPICS = (
    (
        "typescript",
        "fix TypeScript build errors",
        "clean generated declarations before running the ordered typecheck",
    ),
    (
        "unicode",
        "preserve exact UTF-8 byte spans",
        "slice encoded UTF-8 bytes at revision-bound offsets",
    ),
    (
        "gpu",
        "reduce GPU context ranking latency",
        "batch independent candidate lanes on the live Qi field",
    ),
)


def _event(
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
            identity,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    return {**identity, "event_id": event_id, "user": user}


def _rank(
    provider: PersistentFieldProvider,
    *,
    user: str,
    query: str,
    candidates: Sequence[dict[str, Any]],
    context_session_id: str = _CONTEXT_SESSION_ID,
) -> dict[str, Any]:
    result = provider.rank_context({
        "user": user,
        "context_session_id": context_session_id,
        "query": query,
        "candidates": candidates,
    })
    return {
        "state_sha256": result["state_sha256"],
        "ranked": result["ranked"],
        "working": result["working"],
        "timings_ms": result["timings_ms"],
    }


def _score(snapshot: dict[str, Any], candidate_id: str) -> float:
    return next(
        float(item["score"])
        for item in snapshot["ranked"]
        if item["id"] == candidate_id
    )


def run(
    *,
    phi_config_path: Path,
    corpus_checkpoint_path: Path,
    device: str,
) -> dict[str, Any]:
    user = "live-context-steering"
    stream_id = "live-context-steering-stream"
    candidates = []
    for candidate_id, _, text in _TOPICS:
        revision = hashlib.sha256(
            f"{candidate_id}\0fact\0{text}".encode("utf-8")
        ).hexdigest()
        candidates.append({
            "id": candidate_id,
            "record_id": candidate_id,
            "revision": revision,
            "start_byte": 0,
            "end_byte": len(text.encode("utf-8")),
            "text": text,
        })

    with tempfile.TemporaryDirectory(
        prefix="cassi-context-steering-"
    ) as state_dir:
        config = ProviderConfig(
            phi_config_path=phi_config_path,
            corpus_checkpoint_path=corpus_checkpoint_path,
            state_dir=Path(state_dir),
            max_output_symbols=8,
            device=device,
        )
        provider = PersistentFieldProvider(config)
        provider.start()
        previous_event_id = EMPTY_CONTEXT_EVENT_ID
        sequence = 1
        observations: list[dict[str, Any]] = []
        try:
            for candidate in candidates:
                event = _event(
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
                sequence += 1

            for turn, ((_, query, _), candidate) in enumerate(
                zip(_TOPICS, candidates), start=1
            ):
                event = _event(
                    user=user,
                    stream_id=stream_id,
                    sequence=sequence,
                    previous_event_id=previous_event_id,
                    payload={
                        "kind": "feedback",
                        "context_session_id": _CONTEXT_SESSION_ID,
                        "turn_id": turn,
                        "query": query,
                        "candidates": [candidate],
                        "outcome": "completed",
                    },
                )
                provider.observe_context(event)
                previous_event_id = event["event_id"]
                sequence += 1

            baseline = _rank(
                provider,
                user=user,
                query=_STEERING_QUERY,
                candidates=candidates,
            )

            target = candidates[0]
            stages: list[tuple[str, str, bool]] = [
                ("successful_feedback", "completed", False),
                ("error_feedback", "error", True),
                ("recovery_feedback", "completed", False),
            ]
            snapshots: dict[str, dict[str, Any]] = {"baseline": baseline}
            for turn, (stage, outcome, is_error) in enumerate(
                stages, start=10
            ):
                event = _event(
                    user=user,
                    stream_id=stream_id,
                    sequence=sequence,
                    previous_event_id=previous_event_id,
                    payload={
                        "kind": "feedback",
                        "context_session_id": _CONTEXT_SESSION_ID,
                        "turn_id": turn,
                        "query": _STEERING_QUERY,
                        "candidates": [target],
                        "outcome": outcome,
                        "tool_result": {
                            "id": f"tc-steer-{turn}",
                            "name": "pytest",
                            "is_error": is_error,
                        },
                    },
                )
                observed = provider.observe_context(event)
                observations.append({
                    "stage": stage,
                    "selected_ids": observed["selected_ids"],
                    "forgotten_symbols": observed["forgotten_symbols"],
                    "state_out_sha256": observed["state_out_sha256"],
                })
                previous_event_id = event["event_id"]
                sequence += 1
                snapshots[stage] = _rank(
                    provider,
                    user=user,
                    query=_STEERING_QUERY,
                    candidates=candidates,
                )

            isolated = _rank(
                provider,
                user=user,
                query=_STEERING_QUERY,
                candidates=candidates,
                context_session_id="isolated-context",
            )
            engine_fingerprint = provider.provider_fingerprint
        finally:
            provider.close()

        restarted_provider = PersistentFieldProvider(config)
        restarted_provider.start()
        try:
            restarted = _rank(
                restarted_provider,
                user=user,
                query=_STEERING_QUERY,
                candidates=candidates,
            )
        finally:
            restarted_provider.close()

    successful = snapshots["successful_feedback"]
    errored = snapshots["error_feedback"]
    recovered = snapshots["recovery_feedback"]
    if successful["ranked"][0]["id"] != _TARGET_ID:
        raise AssertionError("successful feedback did not steer the target to top-1")
    if _score(successful, _TARGET_ID) <= _score(baseline, _TARGET_ID):
        raise AssertionError("successful feedback did not increase target relevance")
    if _score(errored, _TARGET_ID) >= _score(successful, _TARGET_ID):
        raise AssertionError("error feedback did not remove exact target credit")
    if recovered["ranked"][0]["id"] != _TARGET_ID:
        raise AssertionError("recovery feedback did not restore target top-1")
    if _score(recovered, _TARGET_ID) <= _score(errored, _TARGET_ID):
        raise AssertionError("recovery feedback did not restore target credit")
    if any(float(item["score"]) != 0.0 for item in isolated["ranked"]):
        raise AssertionError("context steering leaked across sessions")
    if restarted["state_sha256"] != recovered["state_sha256"]:
        raise AssertionError("restart changed the field state")
    if restarted["ranked"] != recovered["ranked"]:
        raise AssertionError("restart changed the context ranking")

    return {
        "scenario": "live-field-context-steering",
        "device": device,
        "engine_fingerprint": engine_fingerprint,
        "query": _STEERING_QUERY,
        "target_id": _TARGET_ID,
        "candidate_ids": [candidate["id"] for candidate in candidates],
        "observations": observations,
        "snapshots": snapshots,
        "isolated": isolated,
        "restarted": restarted,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phi-config",
        type=Path,
        default=CONFIG_DIR / "cassi-phi-harmonic-language.json",
    )
    parser.add_argument(
        "--corpus-checkpoint",
        type=Path,
        default=ARTIFACT_DIR / "cassi-phi-harmonic-language" / "field-state.pt",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run(
        phi_config_path=args.phi_config,
        corpus_checkpoint_path=args.corpus_checkpoint,
        device=args.device,
    )
    encoded = json.dumps(result, sort_keys=True, indent=2, allow_nan=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
