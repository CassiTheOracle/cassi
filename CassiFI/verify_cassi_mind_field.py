#!/usr/bin/env python3
"""Independent verifier for the bounded CassiMindField self-rewrite slice."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
CASSIQWEN = ROOT / "CassiQwen"
if str(CASSIQWEN) not in sys.path:
    sys.path.insert(0, str(CASSIQWEN))

from cassi_python import PythonCase, evaluate_source_candidate, verify_differential  # noqa: E402

SOURCE_RELATIVE = Path("src") / "mind_program.py"
CASES = (
    PythonCase("negative", {"value": -7}, -34),
    PythonCase("zero", {"value": 0}, 1),
    PythonCase("positive", {"value": 9}, 46),
    PythonCase("large", {"value": 123}, 616),
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def generation_path(root: Path, generation: int) -> Path:
    return root / "generations" / f"g{generation:04d}"


def source_path(root: Path, generation: int) -> Path:
    return generation_path(root, generation) / SOURCE_RELATIVE


def apply_patch(source: str, patch: Mapping[str, Any]) -> str:
    require(patch.get("schema") == "cassimindfield.source-edit.v1", "patch schema mismatch")
    require(patch.get("operation") == "replace_once", "patch operation mismatch")
    require(patch.get("base_source_sha256") == sha256_text(source), "patch base hash mismatch")
    find = patch.get("find")
    replace = patch.get("replace")
    require(isinstance(find, str) and isinstance(replace, str), "patch text is invalid")
    require(source.count(find) == 1, "patch does not match exactly one span")
    return source.replace(find, replace, 1)


def verify_candidate_source(
    original_source: str,
    candidate_source: str,
    cases: Sequence[PythonCase] = CASES,
) -> dict[str, Any]:
    optimization = evaluate_source_candidate(original_source, candidate_source, cases)
    differential = verify_differential(candidate_source, cases)
    return {
        "passed": bool(
            optimization.status == "PASS"
            and optimization.equivalent
            and optimization.improved
            and differential["passed"]
        ),
        "original_steps": optimization.original_steps,
        "candidate_steps": optimization.candidate_steps,
        "equivalent": optimization.equivalent,
        "improved": optimization.improved,
        "differential": differential,
    }


def verify_run(root: Path) -> dict[str, Any]:
    receipt_path = root / "self-rewrite-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("schema") == "cassimindfield.self-rewrite.v1", "receipt schema mismatch")
    transitions = receipt.get("transitions")
    require(isinstance(transitions, list) and transitions, "receipt has no transitions")
    previous_generation = 0
    for row in transitions:
        generation = int(row["generation"])
        next_generation = int(row["next_generation"])
        require(generation == previous_generation, "generation lineage is not contiguous")
        require(next_generation == generation + 1, "generation increment is invalid")
        before = source_path(root, generation).read_text(encoding="utf-8")
        after = source_path(root, next_generation).read_text(encoding="utf-8")
        manifest = json.loads((generation_path(root, next_generation) / "manifest.json").read_text(encoding="utf-8"))
        require(manifest["generation"] == next_generation, "manifest generation mismatch")
        require(manifest["parent_generation"] == generation, "manifest parent mismatch")
        require(manifest["source_sha256"] == sha256_text(after), "manifest source hash mismatch")
        patch = row["candidate"]["patch"]
        expected = apply_patch(before, patch)
        require(expected == after, "promoted source is not the declared patch result")
        check = verify_candidate_source(before, after)
        require(check["passed"], f"independent candidate verification failed: {check}")
        require(row["candidate"]["source_sha256"] == sha256_text(after), "candidate hash mismatch")
        action = row["field_action"]
        require(action["candidate_id"] == row["candidate"]["candidate_id"], "field action candidate mismatch")
        require(action["edit_id"] == action["candidate_id"], "field action edit mismatch")
        previous_generation = next_generation

    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    require(pointer["generation"] == previous_generation, "current pointer generation mismatch")
    final_source = source_path(root, previous_generation).read_text(encoding="utf-8")
    require(pointer["source_sha256"] == sha256_text(final_source), "current pointer source mismatch")
    live_source = (root / SOURCE_RELATIVE).read_text(encoding="utf-8")
    require(live_source == final_source, "materialized live source differs from current generation")
    final_manifest = json.loads((generation_path(root, previous_generation) / "manifest.json").read_text(encoding="utf-8"))
    require(pointer["manifest_sha256"] == digest(final_manifest), "current pointer manifest mismatch")

    mutation = final_source.replace(" + 1", " + 2", 1)
    require(mutation != final_source, "mutation control did not mutate source")
    mutation_check = verify_differential(mutation, CASES)
    require(not mutation_check["passed"], "mutation control was accepted")
    return {
        "status": "PASS",
        "generations": len(transitions),
        "current_generation": previous_generation,
        "mutation_control_rejected": True,
        "field_state_sha256": receipt.get("field_state", {}).get("field_state_sha256"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT / "CassiMindField")
    args = parser.parse_args()
    result = verify_run(args.root.resolve())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
