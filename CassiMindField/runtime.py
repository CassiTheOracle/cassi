#!/usr/bin/env python3
"""Run one bounded, field-selected source rewrite over CassiMindField.

Only ``src/`` generations are mutable.  The verifier in ``CassiFI`` is kept
outside the target so a candidate cannot change the oracle that promotes it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
CASSIQWEN = WORKSPACE / "CassiQwen"
CASSIRESEARCH = CASSIQWEN / "research"
CASSIFI = WORKSPACE / "CassiFI"
for path in (CASSIQWEN, CASSIRESEARCH, CASSIFI):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cassi_field_qwen_workbench import CassiFieldWorkMemory  # noqa: E402
from cassi_python import PythonCase, evaluate_source_candidate  # noqa: E402
from cassi_teacher_field import TeacherFieldController  # noqa: E402
if __package__:
    from .field_owner_rewrite import PendingRewriteReview, RewriteOwnerGate  # noqa: E402
else:
    from field_owner_rewrite import PendingRewriteReview, RewriteOwnerGate  # noqa: E402
from verify_cassi_mind_field import verify_candidate_source  # noqa: E402


SCHEMA = "cassimindfield.self-rewrite.v1"
SOURCE_RELATIVE = Path("src") / "mind_program.py"
SEED_SOURCE = ROOT / "seed" / "mind_program.py"
CASES = (
    PythonCase("negative", {"value": -7}, -34),
    PythonCase("zero", {"value": 0}, 1),
    PythonCase("positive", {"value": 9}, 46),
    PythonCase("large", {"value": 123}, 616),
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return sha256_bytes(canonical(value))


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical(value) + b"\n")
    os.replace(temporary, path)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def materialize_live_source(root: Path, source: str) -> None:
    atomic_text(root / SOURCE_RELATIVE, source)

def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)

def _transition_path(root: Path, generation: int) -> Path:
    return root / "operations" / f"rewrite-g{generation:04d}.json"


def stage_transition(root: Path, pointer: Mapping[str, Any], transition: Mapping[str, Any]) -> None:
    """Durably bind the lineage row to its verified manifest before moving the pointer."""
    generation = int(pointer["generation"])
    require(generation == transition["next_generation"], "transition target differs from pointer")
    manifest = json.loads((generation_path(root, generation) / "manifest.json").read_text(encoding="utf-8"))
    require(digest(manifest) == pointer["manifest_sha256"], "transition manifest digest mismatch")
    require(manifest["candidate_id"] == transition["candidate"]["candidate_id"], "transition candidate mismatch")
    record = {
        "schema": "cassimindfield.rewrite-transition.v1",
        "generation": generation,
        "manifest_sha256": pointer["manifest_sha256"],
        "transition": dict(transition),
    }
    atomic_json(_transition_path(root, generation), {**record, "sha256": digest(record)})


def finish_transition(root: Path, pointer: Mapping[str, Any], transition: dict[str, Any], review: Mapping[str, Any]) -> None:
    transition["responsibility_review"] = dict(review)
    stage_transition(root, pointer, transition)


def reconcile_transitions(
    root: Path, pointer: Mapping[str, Any], recorded: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Recover committed lineage after owner-report delivery or receipt write was interrupted."""
    rows = list(recorded)
    current = int(pointer["generation"])
    previous = 0
    for row in rows:
        require(
            isinstance(row, dict)
            and row.get("generation") == previous
            and row.get("next_generation") == previous + 1,
            "rewrite receipt lineage is discontinuous",
        )
        previous += 1
    require(previous <= current, "rewrite receipt is ahead of the promotion pointer")
    for generation in range(previous + 1, current + 1):
        path = _transition_path(root, generation)
        require(path.is_file(), "promoted rewrite is missing its transition journal")
        record = json.loads(path.read_text(encoding="utf-8"))
        core = {key: value for key, value in record.items() if key != "sha256"}
        require(
            set(core) == {"schema", "generation", "manifest_sha256", "transition"}
            and record.get("sha256") == digest(core)
            and core["schema"] == "cassimindfield.rewrite-transition.v1"
            and core["generation"] == generation,
            "rewrite transition journal failed its hash guard",
        )
        manifest = json.loads((generation_path(root, generation) / "manifest.json").read_text(encoding="utf-8"))
        require(digest(manifest) == core["manifest_sha256"], "recovered transition manifest digest mismatch")
        if generation == current:
            require(core["manifest_sha256"] == pointer["manifest_sha256"], "recovered transition pointer mismatch")
        row = core["transition"]
        require(
            isinstance(row, dict)
            and row.get("generation") == generation - 1
            and row.get("next_generation") == generation
            and isinstance(row.get("candidate"), dict)
            and row["candidate"].get("candidate_id") == manifest.get("candidate_id"),
            "recovered transition does not describe its promoted candidate",
        )
        if row.get("responsibility_review") == {"status": "pending-delivery"}:
            row["responsibility_review"] = {"status": "delivered-on-recovery"}
            stage_transition(root, {"generation": generation, "manifest_sha256": core["manifest_sha256"]}, row)
        rows.append(row)
    return rows


def generation_path(root: Path, generation: int) -> Path:
    return root / "generations" / f"g{generation:04d}"


def current_pointer(root: Path) -> Path:
    return root / "current.json"


def source_path(root: Path, generation: int) -> Path:
    return generation_path(root, generation) / SOURCE_RELATIVE


def read_pointer(root: Path) -> Mapping[str, Any] | None:
    path = current_pointer(root)
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, Mapping), "current pointer is not an object")
    return value


def bootstrap(root: Path) -> Mapping[str, Any]:
    seed_source = root / "seed" / SEED_SOURCE.name
    if not seed_source.is_file():
        seed_source = SEED_SOURCE
    require(seed_source.is_file(), f"seed source is missing: {seed_source}")
    existing = read_pointer(root)
    if existing is not None:
        generation = int(existing["generation"])
        source = source_path(root, generation).read_text(encoding="utf-8")
        materialize_live_source(root, source)
        return existing
    source = seed_source.read_text(encoding="utf-8")
    target = source_path(root, 0)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8", newline="\n")
    materialize_live_source(root, source)
    manifest = {
        "schema": "cassimindfield.generation-manifest.v1",
        "generation": 0,
        "parent_generation": None,
        "source_relative": SOURCE_RELATIVE.as_posix(),
        "source_sha256": sha256_text(source),
        "source_bytes": len(source.encode("utf-8")),
        "patch": None,
    }
    atomic_json(generation_path(root, 0) / "manifest.json", manifest)
    pointer = {
        "schema": "cassimindfield.current.v1",
        "generation": 0,
        "source_sha256": manifest["source_sha256"],
        "manifest_sha256": digest(manifest),
    }
    atomic_json(current_pointer(root), pointer)
    return pointer


def candidate_rows(source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(
        candidate_id: str,
        task_id: str,
        find: str,
        replace: str,
        *,
        whole_lines: bool = False,
    ) -> None:
        if find not in source or source.count(find) != 1:
            return
        if whole_lines:
            start = source.index(find)
            end = start + len(find)
            if (start > 0 and source[start - 1] != "\n") or (
                end < len(source) and source[end] != "\n"
            ):
                return
        candidate = source.replace(find, replace, 1)
        optimization = evaluate_source_candidate(source, candidate, CASES)
        rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_origin": "verified_pool",
                "task_id": task_id,
                "candidate_sha256": sha256_text(candidate),
                "candidate_steps": optimization.candidate_steps,
                "original_steps": optimization.original_steps,
                "improved": bool(optimization.improved),
                "status": optimization.status,
                "patch": {
                    "schema": "cassimindfield.source-edit.v1",
                    "operation": "replace_once",
                    "find": find,
                    "replace": replace,
                    "base_source_sha256": sha256_text(source),
                },
                "candidate_source": candidate,
            }
        )

    add("constant-fold", "constant_fold", "(2 + 3)", "5")
    add(
        "identical-branch",
        "identical_branch",
        "result = (2 + 3) * tmp + 1 if value >= 0 else (2 + 3) * tmp + 1",
        "result = (2 + 3) * tmp + 1",
    )
    add(
        "identical-branch:function",
        "identical_branch",
        "    return (2 + 3) * tmp + 1 if value >= 0 else (2 + 3) * tmp + 1",
        "    return (2 + 3) * tmp + 1",
        whole_lines=True,
    )
    add(
        "redundant-assignment",
        "redundant_assignment",
        "tmp = value\nresult = 5 * tmp + 1",
        "result = 5 * value + 1",
        whole_lines=True,
    )
    add(
        "redundant-assignment",
        "redundant_assignment",
        "tmp = value\nresult = (2 + 3) * tmp + 1",
        "result = (2 + 3) * value + 1",
        whole_lines=True,
    )
    add(
        "redundant-assignment:function",
        "redundant_assignment",
        "    tmp = value\n    return 5 * tmp + 1",
        "    return 5 * value + 1",
        whole_lines=True,
    )
    add(
        "redundant-assignment:function",
        "redundant_assignment",
        "    tmp = value\n    return (2 + 3) * tmp + 1",
        "    return (2 + 3) * value + 1",
        whole_lines=True,
    )
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique.setdefault(str(row["candidate_sha256"]), row)
    return list(unique.values())


def apply_patch(source: str, patch: Mapping[str, Any]) -> str:
    require(patch.get("schema") == "cassimindfield.source-edit.v1", "unsupported patch schema")
    require(patch.get("operation") == "replace_once", "unsupported patch operation")
    require(patch.get("base_source_sha256") == sha256_text(source), "patch base source mismatch")
    find = patch.get("find")
    replace = patch.get("replace")
    require(isinstance(find, str) and find, "patch find text is invalid")
    require(isinstance(replace, str), "patch replacement text is invalid")
    require(source.count(find) == 1, "patch must match exactly one source span")
    return source.replace(find, replace, 1)


def run(
    root: Path,
    cycles: int,
    *,
    field_owner_url: str | None = None,
    owner_client: Any | None = None,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    owner_gate = RewriteOwnerGate(
        root,
        field_owner_url=(
            field_owner_url
            if field_owner_url is not None
            else os.environ.get("CASSI_FIELD_OWNER_URL", "http://127.0.0.1:8090")
        ),
        owner_client=owner_client,
    )
    pointer = bootstrap(root)
    memory_home = root / "state" / "field-memory"
    receipt_path = root / "self-rewrite-receipt.json"
    prior_receipt = (
        json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt_path.exists()
        else {}
    )
    transitions: list[dict[str, Any]] = list(prior_receipt.get("transitions", []))
    initial_transition_count = len(transitions)
    transitions = reconcile_transitions(root, pointer, transitions)
    awaiting_review = False
    with CassiFieldWorkMemory(memory_home) as memory:
        controller = TeacherFieldController(
            memory,
            run_id=f"cassimindfield:{sha256_text(str(root.resolve()))[:16]}",
        )
        for _ in range(cycles):
            generation = int(pointer["generation"])
            source = source_path(root, generation).read_text(encoding="utf-8")
            source_hash = sha256_text(source)
            require(source_hash == pointer["source_sha256"], "current source does not match pointer")
            candidates = candidate_rows(source)
            if not candidates:
                break
            try:
                owner_gate.start(generation)
                descriptors = [
                    {
                        key: row[key]
                        for key in (
                            "candidate_id",
                            "candidate_origin",
                            "task_id",
                            "candidate_sha256",
                            "candidate_steps",
                            "improved",
                            "status",
                        )
                    }
                    for row in candidates
                ]
                planned = str(candidates[0]["candidate_id"])
                field_begin = controller.begin(
                    generation=generation,
                    attempt=0,
                    previous_source_sha256=source_hash,
                    candidate_descriptors=descriptors,
                    planned_edit_id=planned,
                    thinking_max_tokens=1,
                )
                action = field_begin["action"]
                selected_id = str(action["candidate_id"])
                selected = next((row for row in candidates if row["candidate_id"] == selected_id), None)
                require(selected is not None, f"field selected unknown candidate: {selected_id}")
                candidate_source = apply_patch(source, selected["patch"])
                check = verify_candidate_source(source, candidate_source, CASES)
                next_generation = generation + 1
                responsibility_continuity = owner_gate.before_promotion(next_generation)
                status = "PASS" if check["passed"] else "REJECT"
                field_outcome = controller.observe_outcome(
                    field_begin,
                    status=status,
                    candidate_origin="verified_pool",
                    candidate_sha256=str(selected["candidate_sha256"]),
                    task_id=str(selected["task_id"]),
                    candidate_steps=int(check["candidate_steps"]),
                    original_steps=int(check["original_steps"]),
                    reasoning_chars=0,
                    completion_tokens=0,
                    thinking_requested=False,
                    thinking_effective=False,
                )
                require(check["passed"], f"candidate failed independent verification: {check}")
                target = source_path(root, next_generation)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(candidate_source, encoding="utf-8", newline="\n")
                materialize_live_source(root, candidate_source)
                manifest = {
                    "schema": "cassimindfield.generation-manifest.v1",
                    "generation": next_generation,
                    "parent_generation": generation,
                    "source_relative": SOURCE_RELATIVE.as_posix(),
                    "source_sha256": sha256_text(candidate_source),
                    "source_bytes": len(candidate_source.encode("utf-8")),
                    "candidate_id": selected_id,
                    "responsibility_continuity": responsibility_continuity,
                    "patch": dict(selected["patch"]),
                    "field_action_id": action["action_id"],
                }
                atomic_json(generation_path(root, next_generation) / "manifest.json", manifest)
                next_pointer = {
                    "schema": "cassimindfield.current.v1",
                    "generation": next_generation,
                    "source_sha256": manifest["source_sha256"],
                    "manifest_sha256": digest(manifest),
                }
                transition = {
                    "generation": generation,
                    "next_generation": next_generation,
                    "field_action": dict(action),
                    "field_begin": dict(field_begin),
                    "candidate": {
                        "candidate_id": selected_id,
                        "task_id": selected["task_id"],
                        "source_sha256": selected["candidate_sha256"],
                        "patch": dict(selected["patch"]),
                    },
                    "verification": check,
                    "field_outcome": dict(field_outcome),
                    "responsibility_review": {"status": "pending-delivery"},
                }
                stage_transition(root, next_pointer, transition)
                atomic_json(current_pointer(root), next_pointer)
                pointer = next_pointer
                owner_review = owner_gate.promoted(next_generation)
                finish_transition(root, pointer, transition, owner_review)
                transitions.append(transition)
            except PendingRewriteReview:
                owner_gate.abort(generation)
                if len(transitions) == initial_transition_count:
                    raise
                awaiting_review = True
                break
            except BaseException:
                owner_gate.abort(generation)
                raise
        field_state = memory.regional_field_receipt()
    receipt = {
        "schema": SCHEMA,
        "status": "awaiting-review" if awaiting_review else "complete",
        "source_relative": SOURCE_RELATIVE.as_posix(),
        "cycles_requested": int(prior_receipt.get("cycles_requested", 0)) + cycles,
        "transitions": transitions,
        "current": dict(pointer),
        "field_state": {
            "field_state_sha256": field_state.get("field_state_sha256"),
            "checkpoint_receipt": field_state.get("checkpoint_receipt"),
        },
    }
    atomic_json(root / "self-rewrite-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--field-owner-url", default=os.environ.get("CASSI_FIELD_OWNER_URL", "http://127.0.0.1:8090"))
    args = parser.parse_args()
    require(1 <= args.cycles <= 4, "cycles must be in [1, 4]")
    receipt = run(
        args.root.resolve(),
        args.cycles,
        field_owner_url=args.field_owner_url,
    )
    print(json.dumps({
        "status": receipt["status"],
        "generations": len(receipt["transitions"]),
        "current_generation": receipt["current"]["generation"],
        "field_state_sha256": receipt["field_state"]["field_state_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
