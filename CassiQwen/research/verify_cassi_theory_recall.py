#!/usr/bin/env python3
"""Independently verify a CassiTheory field-memory recall campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_qwen_workbench import CassiFieldWorkMemory

STAGES = ("prepare", "native", "baseline", "recall", "placebo")
QWEN_STAGES = ("native", "baseline", "recall", "placebo")
CAP_KEYS = frozenset({"max_tokens", "max_completion_tokens", "n_predict"})


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} is not a JSON object")
    return value


def digest_value(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def digest_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def qwen_calls(stage: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    calls: list[Mapping[str, Any]] = []
    for row in stage["rows"]:
        if stage["stage"] == "recall":
            calls.extend((row["document_plan"], row["section_plan"], row["answer"]))
        else:
            calls.append(row["answer"])
    return calls


def stable_runtime_contract(stage: Mapping[str, Any]) -> dict[str, Any]:
    runtime = stage["server_runtime"]
    return {
        "default_generation_settings": runtime["default_generation_settings"],
        "total_slots": runtime["total_slots"],
    }


def summary_from_comparisons(rows: Sequence[Mapping[str, Any]], prefix: str) -> dict[str, int]:
    score_key = f"{prefix}_score"
    return {
        "questions": len(rows),
        "claims_passed": sum(int(row[score_key]["claims_passed"]) for row in rows),
        "claims_total": sum(int(row[score_key]["claims_total"]) for row in rows),
        "citations_passed": sum(int(row[score_key]["citations_passed"]) for row in rows),
        "citations_total": sum(int(row[score_key]["citations_total"]) for row in rows),
        "complete_answers": sum(bool(row[score_key]["complete"]) for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.run_dir.resolve()

    paths = {name: root / f"{name}.json" for name in (*STAGES, "protocol", "analysis")}
    require(all(path.is_file() for path in paths.values()), "campaign is missing a required JSON artifact")
    artifacts = {name: load(path) for name, path in paths.items()}
    protocol = artifacts["protocol"]
    prepare = artifacts["prepare"]
    native = artifacts["native"]
    baseline = artifacts["baseline"]
    recall = artifacts["recall"]
    placebo = artifacts["placebo"]
    analysis = artifacts["analysis"]

    protocol_sha256 = digest_value(protocol)
    measured = [artifacts[name] for name in STAGES]
    require(all(stage["protocol_sha256"] == protocol_sha256 for stage in measured), "protocol identity mismatch")
    require(analysis["protocol_sha256"] == protocol_sha256, "analysis protocol identity mismatch")
    require(len({stage["schema"] for stage in measured}) == 1, "measured-stage schema mismatch")
    require(all(stage["harness"] == prepare["harness"] for stage in measured), "measured-stage harness mismatch")
    require(analysis["measurement_harness"] == prepare["harness"], "analysis names the wrong measurement harness")

    protocol_corpus = {
        "documents": len(protocol["documents"]),
        "chunks": len(protocol["chunks"]),
        "source_bytes": sum(int(row["bytes"]) for row in protocol["documents"]),
        "source_sha256": digest_value({row["path"]: row["sha256"] for row in protocol["documents"]}),
    }
    require(prepare["corpus"] == protocol_corpus == analysis["corpus"], "frozen corpus identity mismatch")
    require(analysis["corpus_comparability"]["controlled_source_identity"] == protocol_corpus, "controlled corpus receipt mismatch")

    qwen_stages = [artifacts[name] for name in QWEN_STAGES]
    require(len({stage["model"]["sha256"] for stage in qwen_stages}) == 1, "model hashes differ")
    require(len({stage["server_binary"]["sha256"] for stage in qwen_stages}) == 1, "server binary hashes differ")
    require(len({digest_value(stable_runtime_contract(stage)) for stage in qwen_stages}) == 1, "stable runtime contracts differ")
    process_identities = {
        (int(stage["server_runtime"]["process_id"]), int(stage["server_runtime"]["process_create_time_ns"]))
        for stage in qwen_stages
    }
    require(len(process_identities) == len(qwen_stages), "Qwen stages did not use separate processes")
    for stage in qwen_stages:
        runtime = stage["server_runtime"]
        require(
            runtime["preflight_metrics"]["process_start_time_unix"]
            == runtime["final_metrics"]["process_start_time_unix"],
            f"{stage['stage']} server changed during its stage",
        )

    question_ids = [row["id"] for row in protocol["questions"]]
    for stage in (native, baseline, recall, placebo):
        require([row["id"] for row in stage["rows"]] == question_ids, f"{stage['stage']} question order differs")
    all_calls = [call for stage in qwen_stages for call in qwen_calls(stage)]
    require(all(call["content"].strip() for call in all_calls), "one or more Qwen calls returned empty content")
    require(all(not set(call["generation_limit_fields_present"]) & CAP_KEYS for call in all_calls), "a request was capped")
    require(all(int(stage["rows"][0]["answer" if stage["stage"] != "recall" else "document_plan"]["timings"].get("cache_n", -1)) == 0 for stage in qwen_stages), "a first request reused a native prompt cache")

    chunk_by_id = {row["chunk_id"]: row for row in protocol["chunks"]}
    byte_exact_retrievals = 0
    recall_by_id = {row["id"]: row for row in recall["rows"]}
    placebo_by_id = {row["id"]: row for row in placebo["rows"]}
    for question_id in question_ids:
        remembered = recall_by_id[question_id]
        literal = placebo_by_id[question_id]
        require(remembered["selected_chunk_ids"] == literal["selected_chunk_ids"], f"{question_id} selected chunks differ")
        require(
            remembered["answer"]["user_prompt_sha256"] == literal["answer"]["user_prompt_sha256"],
            f"{question_id} field and placebo prompts differ",
        )
        require(
            remembered["answer"]["generation_parameters"] == literal["answer"]["generation_parameters"],
            f"{question_id} field and placebo generation parameters differ",
        )
        require(remembered["answer_preserved_memory"], f"{question_id} answer mutated field memory")
        require(len(remembered["recalled_records"]) == len(remembered["selected_chunk_ids"]), f"{question_id} recall count differs")
        for record in remembered["recalled_records"]:
            source = chunk_by_id[record["chunk_id"]]
            for key in ("chunk_id", "path", "heading", "part", "source_sha256", "text"):
                require(record[key] == source[key], f"{question_id} recalled {record['chunk_id']} differs at {key}")
            byte_exact_retrievals += 1

    require(prepare["restart_exact"] and recall["restart_exact"], "field restart receipt is not exact")
    require(prepare["state_after_restart"] == recall["state_before"], "recall did not open the prepared state")
    require(recall["state_after"] == recall["state_after_restart"], "post-query field state did not round-trip")
    require(recall["state_after"]["all_finite"], "post-query regional field state is non-finite")
    with CassiFieldWorkMemory(root / "field-memory") as memory:
        require(memory.state_receipt() == recall["state_after_restart"], "persisted field receipt differs")
        require(
            memory.regional_field_receipt() == recall["regional_field"],
            "persisted regional field receipt differs",
        )

    comparisons = analysis["comparisons"]
    require([row["id"] for row in comparisons] == question_ids, "analysis comparison order differs")
    for prefix, summary_key in (
        ("native", "native_only"),
        ("baseline", "empty_memory"),
        ("recall", "field_recall"),
        ("placebo", "literal_text_placebo"),
    ):
        derived = summary_from_comparisons(comparisons, prefix)
        summary = analysis[summary_key]
        require(all(summary[key] == value for key, value in derived.items()), f"{summary_key} aggregate differs")

    replay_path = root / "replay-probe.json"
    replay = load(replay_path) if replay_path.is_file() else None
    replay_verified = False
    if replay is not None:
        variants = [replay["stored_field"], replay["stored_placebo"], *replay["live_replays"]]
        require(len({row["user_prompt_sha256"] for row in variants}) == 1, "replay prompts differ")
        require(len({digest_value(row["generation_parameters"]) for row in variants}) == 1, "replay parameters differ")
        require(len({row["content_sha256"] for row in variants}) >= 2, "replay did not demonstrate output nondeterminism")
        replay_verified = True
        require(
            analysis["decode_reproducibility"]["determinism_precondition_passed"] is False,
            "analysis did not record the failed replay determinism precondition",
        )
        require(analysis["answer_quality_verdict"]["status"] == "NULL", "answer-quality verdict is not NULL")

    selected_exposures = sum(len(row["selected_chunk_ids"]) for row in recall["rows"])
    ownership = analysis["ownership_receipt"]
    require(
        int(ownership["field_owned_decisions"]["source_revision_selections"])
        == selected_exposures,
        "analysis does not attribute semantic source selection to cognition.field",
    )
    require(
        int(ownership["field_owned_operations"]["exact_keyed_source_revision_exposures"])
        == selected_exposures,
        "field exact-exposure count differs",
    )
    require(
        int(ownership["qwen_owned_decisions"]["source_chunk_selections"])
        == selected_exposures,
        "Qwen planner source-selection count differs",
    )
    regional = recall["regional_field"]
    require(
        regional["semantic_state_schema"] == "cassifi.semantic-cognition-state.v1"
        and regional["kernel"] == "cognition.field"
        and int(regional["semantic_active_bindings"]) >= len(protocol["chunks"]),
        "regional semantic field receipt is incomplete",
    )
    require(
        int(analysis["cost_boundary"]["retrieved_context_prompt_token_overhead"])
        == int(analysis["field_recall"]["prompt_tokens"]) - int(analysis["empty_memory"]["prompt_tokens"]),
        "retrieved-context prompt-token overhead differs",
    )
    require(
        int(analysis["cost_boundary"]["field_vs_literal_prompt_token_delta"]) == 0,
        "field and literal prompt-token totals differ",
    )
    semantic = analysis["memory"]["semantic_boundary"]
    require(
        semantic["computer_id"] == regional["computer_id"]
        and semantic["profile_sha256"] == regional["profile_sha256"]
        and semantic["catalog_sha256"] == regional["catalog_sha256"]
        and semantic["semantic_state_schema"] == regional["semantic_state_schema"]
        and int(semantic["semantic_active_bindings"])
        == int(regional["semantic_active_bindings"]),
        "analysis semantic-boundary receipt differs from reopened regional field",
    )

    artifact_hashes = {
        path.name: digest_path(path)
        for path in sorted(root.glob("*.json"))
        if path.name != "independent-verification.json"
    }
    result = {
        "schema": "cassi.field-qwen.theory-recall.independent-verification.v1",
        "status": "verified",
        "checks": {
            "protocol_and_measurement_harness_identity": True,
            "frozen_corpus_rederived": True,
            "four_separate_qwen_processes": True,
            "same_model_binary_and_runtime_contract": True,
            "uncapped_nonempty_requests": len(all_calls),
            "field_placebo_prompt_parity": len(question_ids),
            "byte_exact_retrievals": byte_exact_retrievals,
            "field_restart_and_persistence_exact": True,
            "aggregates_rederived": True,
            "fixed_seed_replay_nondeterminism_verified": replay_verified,
            "regional_semantic_binding_receipt_verified": True,
            "prompt_input_cost_rederived": True,
        },
        "artifact_sha256": artifact_hashes,
    }
    output = root / "independent-verification.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
