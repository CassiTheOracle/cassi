"""Measure field-native exact-address recall without mutating the Qi field."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Sequence

from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_mnemic_condensation import mnemic_field_address
from cassi_persistent_provider import (
    EMPTY_CONTEXT_EVENT_ID,
    PersistentFieldProvider,
    ProviderConfig,
)

_STAGES = ("load", "scoring", "total")


def percentile(values: Sequence[float], proportion: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * proportion) - 1)]


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


def _record(index: int) -> dict[str, str]:
    record_id = f"profile-{index:04d}"
    signature = hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:20]
    text = (
        f"field memory signature {signature} preserves exact address evidence "
        f"through slow coherence mode {index % 17:02d}"
    )
    revision = hashlib.sha256(
        f"{record_id}\0fact\0{text}".encode("utf-8")
    ).hexdigest()
    address = mnemic_field_address(
        record_id=record_id,
        revision=revision,
        start_byte=0,
        end_byte=len(text.encode("utf-8")),
        semantic_kind="fact",
    ).hex()
    return {
        "id": record_id,
        "cue": signature,
        "text": text,
        "revision": revision,
        "address": address,
    }


def profile(
    *,
    phi_config_path: Path,
    corpus_checkpoint_path: Path,
    device: str,
    samples: int,
    warmup: int,
    candidate_count: int,
) -> dict[str, Any]:
    records = [_record(index) for index in range(candidate_count)]
    user = "mnemic-recall-profile"
    stream_id = "mnemic-recall-profile-stream"
    with tempfile.TemporaryDirectory(prefix="cassi-mnemic-profile-") as state_dir:
        provider = PersistentFieldProvider(
            ProviderConfig(
                phi_config_path=phi_config_path,
                corpus_checkpoint_path=corpus_checkpoint_path,
                state_dir=Path(state_dir),
                max_output_symbols=8,
                device=device,
            )
        )
        provider.start()
        try:
            previous_event_id = EMPTY_CONTEXT_EVENT_ID
            sequence = 1
            for record in records:
                stored = _event(
                    user=user,
                    stream_id=stream_id,
                    sequence=sequence,
                    previous_event_id=previous_event_id,
                    payload={
                        "kind": "memory",
                        "context_session_id": "",
                        "operation": "store",
                        "record": {
                            "id": record["id"],
                            "node_type": "fact",
                            "revision": record["revision"],
                            "content": record["text"],
                            "field_address": record["address"],
                        },
                    },
                )
                provider.observe_context(stored)
                previous_event_id = stored["event_id"]
                sequence += 1
                cue = _event(
                    user=user,
                    stream_id=stream_id,
                    sequence=sequence,
                    previous_event_id=previous_event_id,
                    payload={
                        "kind": "feedback",
                        "context_session_id": "profile-context",
                        "turn_id": sequence,
                        "query": record["cue"],
                        "candidates": [
                            {
                                "id": record["id"],
                                "record_id": record["id"],
                                "revision": record["revision"],
                                "start_byte": 0,
                                "end_byte": len(record["text"].encode("utf-8")),
                                "text": record["text"],
                                "field_address": record["address"],
                            }
                        ],
                        "outcome": "completed",
                    },
                )
                provider.observe_context(cue)
                previous_event_id = cue["event_id"]
                sequence += 1

            counts = sorted(
                {
                    min(candidate_count, count)
                    for count in (1, 4, 8, 16, 32, candidate_count)
                }
            )
            result: dict[str, Any] = {
                "schema": "cassi.mnemic.recall-profile.v1",
                "device": device,
                "engine_fingerprint": provider.provider_fingerprint,
                "samples": samples,
                "counts": {},
            }
            for count in counts:
                target = records[0]
                request = {
                    "user": user,
                    "context_session_id": "profile-context",
                    "query": target["cue"],
                    "addresses": [record["address"] for record in records[:count]],
                }
                measurements = {stage: [] for stage in _STAGES}
                state_sha256 = None
                for iteration in range(warmup + samples):
                    recalled = provider.recall_context(request)
                    if recalled["address"] != target["address"]:
                        raise RuntimeError(
                            f"field recall missed target with {count} addresses"
                        )
                    if state_sha256 is None:
                        state_sha256 = recalled["state_sha256"]
                    elif recalled["state_sha256"] != state_sha256:
                        raise RuntimeError("read-only field recall mutated state")
                    if iteration >= warmup:
                        for stage in _STAGES:
                            measurements[stage].append(
                                float(recalled["timings_ms"][stage])
                            )
                result["counts"][str(count)] = {
                    stage: {
                        "p50_ms": percentile(values, 0.50),
                        "p95_ms": percentile(values, 0.95),
                    }
                    for stage, values in measurements.items()
                }
            return result
        finally:
            provider.close()


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
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--candidates", type=int, default=32)
    args = parser.parse_args(argv)
    if not 1 <= args.samples <= 100 or not 0 <= args.warmup <= 20:
        parser.error("samples must be 1..100 and warmup must be 0..20")
    if not 1 <= args.candidates <= 256:
        parser.error("candidates must be 1..256")
    result = profile(
        phi_config_path=args.phi_config,
        corpus_checkpoint_path=args.corpus_checkpoint,
        device=args.device,
        samples=args.samples,
        warmup=args.warmup,
        candidate_count=args.candidates,
    )
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
