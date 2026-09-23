#!/usr/bin/env python3
"""Smoke and independent verification for the promotion kernel."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MIND_FIELD = ROOT.parent / "CassiMindField"
if str(MIND_FIELD) not in sys.path:
    sys.path.insert(0, str(MIND_FIELD))

from promotion_kernel import (  # noqa: E402
    FieldState,
    PromotionCandidate,
    PromotionError,
    PromotionIntegrityError,
    PromotionKernel,
    PromotionRefusal,
    StateMigration,
    digest,
    source_digest,
)


class VerificationError(RuntimeError):
    """Raised when a promotion receipt does not prove its contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _source_receipt(files: dict[str, str], label: str) -> dict[str, object]:
    return {
        "schema": "cassimindfield.architecture-synthesis.v1",
        "candidate": label,
        "source_digest": source_digest(files),
        "files": {
            path: {"sha256": hashlib.sha256(files[path].encode("utf-8")).hexdigest(), "bytes": len(files[path].encode("utf-8"))}
            for path in sorted(files)
        },
    }


def _expect_refusal(callable_value, label: str) -> None:
    try:
        callable_value()
    except (PromotionRefusal, PromotionIntegrityError, PromotionError, ValueError):
        return
    raise VerificationError(f"refusal control was accepted: {label}")


def verify() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cassimindfield-promotion-") as temporary:
        root = Path(temporary)
        kernel = PromotionKernel(root)
        base_files = {"src/service.py": "def value():\n    return 1\n"}
        base_receipt = _source_receipt(base_files, "base")
        base_candidate = PromotionCandidate("base_candidate", base_files, base_receipt)
        state0 = FieldState("field.state.v1", {"counter": 1, "nested": {"mode": "cold"}})
        generation0 = kernel.initialize(base_candidate, state0)
        require(generation0.generation == "g0000", "initial generation id is not deterministic")
        require(kernel.current() is not None and kernel.current().generation == "g0000", "initial current pointer is wrong")

        migrated_payload = {"steps": 1, "nested": {"mode": "warm"}}
        state1 = FieldState("field.state.v2", migrated_payload)
        migration_operations = (
            {"kind": "rename", "path": ["counter"], "target": ["steps"]},
            {"kind": "delete", "path": ["nested", "mode"]},
            {"kind": "set", "path": ["nested", "mode"], "value": "warm"},
        )
        migration = StateMigration("field.state.v1", "field.state.v2", state0.digest(), state1.digest(), migration_operations)
        files1 = {"src/service.py": "def value():\n    return 2\n", "src/adapter.py": "from service import value\n"}
        candidate1 = PromotionCandidate("successor_candidate", files1, _source_receipt(files1, "successor"))
        generation1 = kernel.promote(candidate1, state1, migration=migration)
        require(generation1.generation == "g0001" and generation1.parent_generation == "g0000", "generation DAG parent is wrong")
        require(kernel.current().generation == "g0001", "promotion did not atomically advance pointer")
        require(kernel.read_state("g0001").to_dict() == state1.to_dict(), "state migration target was not persisted")
        require(kernel.verify_dag() == [generation0, generation1], "immutable generation DAG verification failed")

        rollback = kernel.rollback("g0000")
        current_after_rollback = kernel.current()
        require(rollback.to_dict() == generation0.to_dict(), "rollback returned a different generation")
        require(current_after_rollback is not None and current_after_rollback.to_dict() == generation0.to_dict(), "rollback pointer is not exact")
        pointer = json.loads(kernel.pointer_path.read_text(encoding="utf-8"))
        require(pointer["generation"] == "g0000" and pointer["generation_digest"] == generation0.generation_digest, "rollback pointer bytes are wrong")

        _expect_refusal(lambda: PromotionCandidate("mutated_candidate", {"src/service.py": "def value():\n    return 9\n"}, base_receipt).source_digest(), "candidate/source receipt mismatch")

        source_path = root / "generations" / "g0001" / "source" / "src" / "service.py"
        original_source = source_path.read_text(encoding="utf-8")
        source_path.write_text(original_source.replace("return 2", "return 99"), encoding="utf-8")
        _expect_refusal(lambda: kernel.read_generation("g0001"), "source mutation")
        source_path.write_text(original_source, encoding="utf-8")
        require(kernel.read_generation("g0001").generation == "g0001", "source mutation control did not restore cleanly")

        receipt_path = root / "generations" / "g0001" / "receipt.json"
        original_receipt = receipt_path.read_text(encoding="utf-8")
        mutated_receipt = json.loads(original_receipt)
        mutated_receipt["candidate"] = "tampered"
        receipt_path.write_text(json.dumps(mutated_receipt), encoding="utf-8")
        _expect_refusal(lambda: kernel.read_generation("g0001"), "receipt mutation")
        receipt_path.write_text(original_receipt, encoding="utf-8")

        state_path = root / "generations" / "g0001" / "field_state.json"
        original_state = state_path.read_text(encoding="utf-8")
        mutated_state = json.loads(original_state)
        mutated_state["payload"]["steps"] = 777
        state_path.write_text(json.dumps(mutated_state), encoding="utf-8")
        _expect_refusal(lambda: kernel.read_generation("g0001"), "field-state mutation")
        state_path.write_text(original_state, encoding="utf-8")

        pointer_original = kernel.pointer_path.read_text(encoding="utf-8")
        pointer_mutation = json.loads(pointer_original)
        pointer_mutation["generation"] = "g0001"
        kernel.pointer_path.write_text(json.dumps(pointer_mutation), encoding="utf-8")
        _expect_refusal(lambda: kernel.current(), "current pointer mutation")
        kernel.pointer_path.write_text(pointer_original, encoding="utf-8")
        require(kernel.current().generation == "g0000", "pointer mutation control did not restore rollback")

        bad_migration = StateMigration("field.state.v1", "field.state.v3", state0.digest(), digest({"schema": "field.state.v3", "payload": {"wrong": True}}), migration_operations)
        _expect_refusal(lambda: __import__("promotion_kernel").apply_state_migration(state0, bad_migration), "migration target digest")

        return {
            "status": "PASS",
            "generations": [generation0.generation, generation1.generation],
            "rollback_generation": current_after_rollback.generation,
            "source_digest": generation1.source_digest,
            "candidate_digest": generation1.candidate_digest,
            "field_state_digest": generation1.field_state_digest,
            "state_migration": True,
            "mutation_controls": ["candidate", "source", "receipt", "field_state", "pointer", "migration"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the measured promotion receipt before PASS")
    arguments = parser.parse_args()
    receipt = verify()
    if arguments.json:
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
