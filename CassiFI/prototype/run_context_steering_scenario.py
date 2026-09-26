"""Exercise field-native Mnemic condensation, exact recall, and restart."""

from __future__ import annotations

import argparse
import hashlib
import json
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

_CONTEXT_SESSION_ID = "live-mnemic-context"
_ALIAS_QUERY = "repair tsc compilation failures"
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
        "reduce GPU context recall latency",
        "batch complete opaque addresses against the live Qi field",
    ),
)


def _revision(record_id: str, text: str) -> str:
    return hashlib.sha256(f"{record_id}\0fact\0{text}".encode("utf-8")).hexdigest()


def _address(record_id: str, text: str, revision: str) -> str:
    return mnemic_field_address(
        record_id=record_id,
        revision=revision,
        start_byte=0,
        end_byte=len(text.encode("utf-8")),
        semantic_kind="fact",
    ).hex()


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


def _recall(
    provider: PersistentFieldProvider,
    *,
    user: str,
    query: str,
    addresses: Sequence[str],
) -> dict[str, Any]:
    return provider.recall_context(
        {
            "user": user,
            "context_session_id": _CONTEXT_SESSION_ID,
            "query": query,
            "addresses": list(addresses),
        }
    )


def run(
    *,
    phi_config_path: Path,
    corpus_checkpoint_path: Path,
    device: str,
) -> dict[str, Any]:
    user = "live-mnemic-recall"
    stream_id = "live-mnemic-recall-stream"
    records = []
    for record_id, query, text in _TOPICS:
        revision = _revision(record_id, text)
        records.append(
            {
                "id": record_id,
                "query": query,
                "text": text,
                "revision": revision,
                "address": _address(record_id, text, revision),
            }
        )
    addresses = [record["address"] for record in records]

    with tempfile.TemporaryDirectory(prefix="cassi-mnemic-recall-") as state_dir:
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
        try:
            receipts = []
            for record in records:
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
                            "id": record["id"],
                            "node_type": "fact",
                            "revision": record["revision"],
                            "content": record["text"],
                            "field_address": record["address"],
                        },
                    },
                )
                receipts.append(provider.observe_context(event))
                previous_event_id = event["event_id"]
                sequence += 1

            exact = {
                record["id"]: _recall(
                    provider,
                    user=user,
                    query=record["text"],
                    addresses=addresses,
                )
                for record in records
            }
            target = records[0]
            feedback = _event(
                user=user,
                stream_id=stream_id,
                sequence=sequence,
                previous_event_id=previous_event_id,
                payload={
                    "kind": "feedback",
                    "context_session_id": _CONTEXT_SESSION_ID,
                    "turn_id": 10,
                    "query": _ALIAS_QUERY,
                    "candidates": [
                        {
                            "id": target["id"],
                            "record_id": target["id"],
                            "revision": target["revision"],
                            "start_byte": 0,
                            "end_byte": len(target["text"].encode("utf-8")),
                            "text": target["text"],
                            "field_address": target["address"],
                        }
                    ],
                    "outcome": "completed",
                },
            )
            feedback_receipt = provider.observe_context(feedback)
            alias = _recall(
                provider,
                user=user,
                query=_ALIAS_QUERY,
                addresses=addresses,
            )
            checkpoint = Path(feedback_receipt["checkpoint"])
            checkpoint_before_read = checkpoint.read_bytes()
            repeated = _recall(
                provider,
                user=user,
                query=_ALIAS_QUERY,
                addresses=addresses,
            )
            if checkpoint.read_bytes() != checkpoint_before_read:
                raise AssertionError("field recall mutated the persistent checkpoint")
            engine_fingerprint = provider.provider_fingerprint
        finally:
            provider.close()

        restarted_provider = PersistentFieldProvider(config)
        restarted_provider.start()
        try:
            restarted = _recall(
                restarted_provider,
                user=user,
                query=_ALIAS_QUERY,
                addresses=addresses,
            )
        finally:
            restarted_provider.close()

    for record in records:
        if exact[record["id"]]["address"] != record["address"]:
            raise AssertionError(f"exact cue missed {record['id']}")
    if alias["address"] != records[0]["address"]:
        raise AssertionError("successful-use condensation missed the target address")
    for key in ("address", "signal", "selection_margin", "availability", "state_sha256"):
        if repeated[key] != alias[key]:
            raise AssertionError(f"read-only recall changed {key}")
    if restarted["address"] != alias["address"]:
        raise AssertionError("restart changed the recalled exact address")
    if restarted["mnemic_state_sha256"] != alias["mnemic_state_sha256"]:
        raise AssertionError("restart changed the Mnemic Qi field")

    return {
        "schema": "cassi.mnemic.live-recall-scenario.v1",
        "device": device,
        "engine_fingerprint": engine_fingerprint,
        "candidate_addresses": addresses,
        "write_receipts": [
            {
                "state_out_sha256": receipt["state_out_sha256"],
                "mnemic_state_out_sha256": receipt["mnemic_state_out_sha256"],
                "transitions": receipt["transitions"],
            }
            for receipt in receipts
        ],
        "exact": exact,
        "feedback": feedback_receipt,
        "alias": alias,
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
