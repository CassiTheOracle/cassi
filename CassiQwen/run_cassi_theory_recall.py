#!/usr/bin/env python3
"""Evaluate uncapped Qwen use of restarted CassiFI memory over CassiTheory.

The experiment is deliberately staged. ``prepare`` chunks and admits a frozen
CassiTheory corpus, ``baseline`` asks a separately restarted Qwen without that
memory, ``recall`` restarts both Qwen and CassiFI and lets Qwen select and read
remembered source chunks, and ``analyze`` compares grounded answer fidelity.
Every chat request omits max_tokens, max_completion_tokens, and n_predict so
llama.cpp generates until the model emits EOS (its n_predict=-1 default).
"""

from __future__ import annotations

import argparse
import http.client
import hashlib
import json
import os
from pathlib import Path
import psutil
import re
import statistics
import time
from typing import Any, Mapping, Sequence

from cassi_field_qwen_workbench import (
    CassiFieldWorkMemory,
    LocalQwenClient,
    WorkMemoryRecord,
    cassifi_source_identity,
    ownership_receipt,
)


SCHEMA = "cassi.field-qwen.theory-recall.v5"
PROTOCOL_SCHEMA = "cassi.field-qwen.theory-recall.protocol.v1"
CORPUS_ID = "cassitheory-20260908-practical-recall-0.8b"
DEFAULT_MODEL = Path("Qwen3.5-0.8B-Q4_0.gguf")
DEFAULT_THEORY_ROOT = Path("../CassiTheory")
MAX_CHUNK_CHARS = 10000
MAX_RECALLED_CHUNKS_PER_QUESTION = 10
GENERATION_LIMIT_KEYS = frozenset({"max_tokens", "max_completion_tokens", "n_predict"})
EXPECTED_QUESTIONS_SHA256 = "8f56d86b4758b454644a80fbc8c6951244238ad15bf3b2ace794de3490e57522"
GENERATION_SEED = 424242

CORPUS_PATHS = (
    "computations/matter-formation-continuum-report.md",
    "foundations/matter-completion-boundary.md",
    "foundations/particle-stationary-action-closure.md",
    "foundations/nonabelian-magnetic-core-boundary.md",
    "foundations/dimensionful-cascade.md",
    "foundations/dimensionful-constants-status.md",
    "foundations/quantum-free-fall-correspondence.md",
    "consciousness/cascade-consciousness.md",
    "consciousness/time-memory-and-wake-locks.md",
    "open-questions-cassi-answers.md",
    "parameter-inventory.md",
    "predictions/falsifiable-predictions.md",
    "cassi-physics.md",
    "EPISTEMIC-MAP.md",
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def digest_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)



def mapping_difference_keys(left: Mapping[str, Any], right: Mapping[str, Any]) -> list[str]:
    return sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))

def normalized_excerpt(text: str, limit: int = 260) -> str:
    clean = re.sub(r"[`*_#|]", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:limit]


def split_oversized(text: str, limit: int) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text.strip())
    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > limit:
            if current:
                pieces.append(current)
                current = ""
            start = 0
            while start < len(paragraph):
                end = min(start + limit, len(paragraph))
                if end < len(paragraph):
                    boundary = paragraph.rfind(" ", start, end)
                    if boundary > start + limit // 2:
                        end = boundary
                pieces.append(paragraph[start:end].strip())
                start = end
            continue
        proposed = paragraph if not current else current + "\n\n" + paragraph
        if len(proposed) <= limit:
            current = proposed
        else:
            pieces.append(current)
            current = paragraph
    if current:
        pieces.append(current)
    return pieces or [""]


def chunk_document(theory_root: Path, relative_path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = theory_root / relative_path
    require(path.is_file(), f"missing CassiTheory source: {path}")
    text = path.read_text(encoding="utf-8")
    source_sha256 = digest_path(path)
    headings = list(re.finditer(r"(?m)^(#{1,2})\s+(.+?)\s*$", text))
    title = headings[0].group(2) if headings else relative_path
    document = {
        "path": relative_path,
        "title": title,
        "sha256": source_sha256,
        "bytes": path.stat().st_size,
        "synopsis": normalized_excerpt(text, 360),
    }
    chunks: list[dict[str, Any]] = []
    current_h2 = title
    if not headings:
        raise RuntimeError(f"CassiTheory source has no Markdown heading: {path}")
    for heading_index, match in enumerate(headings):
        level = len(match.group(1))
        heading = match.group(2).strip()
        if level == 1:
            current_h2 = title
        else:
            current_h2 = heading
        start = match.start()
        end = headings[heading_index + 1].start() if heading_index + 1 < len(headings) else len(text)
        section = text[start:end].strip()
        section_label = current_h2
        for part_index, piece in enumerate(split_oversized(section, MAX_CHUNK_CHARS), start=1):
            identity = {
                "corpus": CORPUS_ID,
                "path": relative_path,
                "heading": section_label,
                "part": part_index,
                "text_sha256": hashlib.sha256(piece.encode("utf-8")).hexdigest(),
            }
            chunk_id = "ct-" + digest_value(identity)[:20]
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "path": relative_path,
                    "heading": section_label,
                    "part": part_index,
                    "source_sha256": source_sha256,
                    "text_sha256": identity["text_sha256"],
                    "chars": len(piece),
                    "synopsis": normalized_excerpt(piece),
                    "text": piece,
                }
            )
    return document, chunks


def claim(*alternatives: str) -> list[str]:
    return list(alternatives)


def questions() -> list[dict[str, Any]]:
    return [
        {
            "id": "matter-completion",
            "question": (
                "What has CassiTheory actually established about matter formation as of September 2026, "
                "and why does the complete physical mechanism still fail? Reconcile the prepared scalar, "
                "fermionic-production, and completion-gate evidence rather than listing them independently."
            ),
            "required_sources": [
                "computations/matter-formation-continuum-report.md",
                "foundations/matter-completion-boundary.md",
            ],
            "claims": [
                claim("conjunctive completion gate is `fail`", "conjunctive completion gate is fail", "completion gate remains fail"),
                claim("hypothesized/open", "hypothesized and open"),
                claim("separate supplied models", "distinct candidate systems", "do not define one matter-formation mechanism"),
                claim("quantum state", "initial quantum state"),
                claim("physical normalization", "absolute normalization"),
                claim("real-time localized formation", "localized forming evolution"),
                claim("nonlinear stability", "nonlinear orbital stability"),
                claim("particle identity", "particle identification"),
            ],
        },
        {
            "id": "fixed-charge-stability",
            "question": (
                "Explain the strongest fixed-charge localization and stability evidence in the current matter "
                "campaign. Which charge branches qualified or did not, what did the finite-grid curvature and "
                "spatial checks show, and which continuum or dynamical conclusions are still unavailable?"
            ),
            "required_sources": [
                "computations/matter-formation-continuum-report.md",
                "foundations/particle-stationary-action-closure.md",
            ],
            "claims": [
                claim("q_c=4", "$q_c=4$", "q c = 4"),
                claim("does not emerge", "did not emerge"),
                claim("q_c=16", "$q_c=16$", "q c = 16"),
                claim("q_c=64", "$q_c=64$", "q c = 64"),
                claim("inconclusive"),
                claim("q_c=256", "$q_c=256$", "q c = 256"),
                claim("24 frozen radial embeddings", "all 24", "twenty-four"),
                claim("positive measured amplitude curvature", "positive curvature"),
                claim("finite-grid", "finite grid"),
                claim("real-time", "real time"),
                claim("continuum", "infinite-volume", "infinite volume"),
            ],
        },
        {
            "id": "topology-statistics",
            "question": (
                "Does the present Cassi matter sector derive fermionic statistics from its scalar or gauge "
                "topology? Give the precise topology results for the unrestricted positive-density sector, "
                "ordinary 2π rotation, separated collision-excluded lumps, and large gauge components, then "
                "state what additional physical choices would be needed."
            ),
            "required_sources": [
                "computations/matter-formation-continuum-report.md",
                "foundations/nonabelian-magnetic-core-boundary.md",
            ],
            "claims": [
                claim("contractible"),
                claim("u(2π)=+1", "u(2\\pi)=+1", "2π rotation", "2 pi rotation"),
                claim("pi_1(q_n)=s_n", "π_1(q_n)=s_n", "fundamental group", "permutation classes"),
                claim("bosonic and fermionic", "trivial and sign characters", "sign character"),
                claim("does not select", "not select"),
                claim("integer winding", "degree characters", "winding characters"),
                claim("quantization", "quantum representation"),
                claim("particle sector", "multiparticle sector", "restricted quantum sector"),
            ],
        },
        {
            "id": "dimensionful-constants",
            "question": (
                "Can Cassi derive c, ħ, and G from φ? Explain the one-anchor limitation, the conditional c "
                "relation, the difference between the declared λ=0.1 convention and the solver default, and "
                "the status of the present-day horizon rung."
            ),
            "required_sources": [
                "foundations/dimensionful-constants-status.md",
                "foundations/dimensionful-cascade.md",
            ],
            "claims": [
                claim("not derivable", "cannot derive", "not independently derivable"),
                claim("dimensionless"),
                claim("planck length", "ell_{\\text{pl}}", "ℓ_pl"),
                claim("external anchor", "external dimensionful anchor"),
                claim("c=\\lambda", "c = λ", "c = lambda", "c=λ"),
                claim("tau", "τ", "pde-to-physical-time"),
                claim("0.1"),
                claim("0.02"),
                claim("291.54", "approximately 292", "n ≈ 292"),
                claim("empirical", "epoch-dependent", "epoch dependent"),
            ],
        },
        {
            "id": "quantum-free-fall",
            "question": (
                "What does CassiTheory conclude from the quantum free-fall matter-wave correspondence? State "
                "the recovered phase law and species comparison, then separate compatibility with standard "
                "minimal coupling from evidence for Cassi-specific gravity or two-fluid corrections."
            ),
            "required_sources": ["foundations/quantum-free-fall-correspondence.md"],
            "claims": [
                claim("k_eff g t^2", "k_{\\rm eff}gt^2", "k_{eff} g t^2", "k_eff·g·t²"),
                claim("silicon", "si"),
                claim("rubidium", "rb"),
                claim("mass-independent", "independent of the test mass", "species-independent", "species independent"),
                claim("minimal coupling"),
                claim("compatibility", "compatible"),
                claim("not evidence", "does not provide evidence", "not a cassi-specific prediction"),
                claim("two-fluid", "yang/yin", "yang–yin"),
                claim("not test", "unconstrained", "no bound"),
            ],
        },
        {
            "id": "memory-wake-consciousness",
            "question": (
                "In CassiTheory's speculative consciousness and memory mapping, distinguish Π, ε, the causal "
                "IIR trace, q-mediated persistence, and a driven wake-lock. What did the wake tests actually "
                "establish, and what stronger claims about consciousness, hauntings, or future information do "
                "they not establish?"
            ),
            "required_sources": [
                "consciousness/time-memory-and-wake-locks.md",
                "consciousness/cascade-consciousness.md",
            ],
            "claims": [
                claim("π", "pi"),
                claim("raw imbalance", "density difference"),
                claim("ε", "epsilon"),
                claim("deviation", "conversion"),
                claim("iir"),
                claim("τ=φ^{-1}", "tau = phi^-1", "phi^{-1}", "φ^{-1}"),
                claim("q", "coherence"),
                claim("undriven", "un-driven"),
                claim("decay"),
                claim("driver", "recurring trigger"),
                claim("0.005%", "0.005 percent"),
                claim("speculative", "creative exploration"),
                claim("unwritten information", "future information", "future states"),
            ],
        },
    ]


def protocol_definition(theory_root: Path) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    for relative_path in CORPUS_PATHS:
        document, document_chunks = chunk_document(theory_root, relative_path)
        documents.append(document)
        chunks.extend(document_chunks)
    return {
        "schema": PROTOCOL_SCHEMA,
        "corpus_id": CORPUS_ID,
        "created_date": "2026-09-08",
        "theory_root": str(theory_root.resolve()),
        "chunking": {"method": "markdown-h1-h2-then-paragraph", "max_chunk_chars": MAX_CHUNK_CHARS},
        "generation_policy": {
            "request_fields_omitted": sorted(GENERATION_LIMIT_KEYS),
            "llama_cpp_default": "n_predict=-1; generate until EOS",
            "temperature": 0,
            "stream": False,
            "thinking": False,
        },
        "documents": documents,
        "chunks": chunks,
        "questions": questions(),
    }


def load_protocol(out_dir: Path) -> tuple[dict[str, Any], str]:
    protocol = json.loads((out_dir / "protocol.json").read_text(encoding="utf-8"))
    require(protocol.get("schema") == PROTOCOL_SCHEMA, "invalid theory recall protocol")
    actual = digest_value(protocol)
    identity = json.loads((out_dir / "protocol-identity.json").read_text(encoding="utf-8"))
    require(identity.get("sha256") == actual, "protocol identity mismatch")
    return protocol, actual


def memory_record(chunk: Mapping[str, Any]) -> WorkMemoryRecord:
    return WorkMemoryRecord(
        source_id=f"cassitheory:{chunk['chunk_id']}",
        context={"corpus": CORPUS_ID, "chunk_id": str(chunk["chunk_id"])},
        payload={
            "chunk_id": chunk["chunk_id"],
            "path": chunk["path"],
            "heading": chunk["heading"],
            "part": chunk["part"],
            "source_sha256": chunk["source_sha256"],
            "text_sha256": chunk["text_sha256"],
            "text": chunk["text"],
        },
        observed_timestamp="2026-09-08T00:00:00Z",
        labels=("cassitheory", "practical-recall"),
    )


def compact_learning(receipt: Mapping[str, Any]) -> dict[str, Any]:
    regional = receipt["regional_field"]
    return {
        "status": receipt["status"],
        "source_revision_id": receipt["source_revision_id"],
        "superseded_revision_id": receipt.get("superseded_revision_id"),
        "binding_id": receipt["binding_id"],
        "state_sha256": receipt["state_sha256"],
        "generation": receipt["generation"],
        "regional_field_state_sha256": regional["field_state_sha256"],
        "semantic_active_bindings": regional["semantic_active_bindings"],
        "semantic_transitions": regional["semantic_transitions"],
    }


def compact_recall(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": receipt["status"],
        "query_id": receipt["query_id"],
        "context": receipt["context"],
        "selected_source_revision_ids": receipt["selected_source_revision_ids"],
        "records": receipt["records"],
        "candidate_binding_ids": receipt["candidate_binding_ids"],
        "field_state_before_sha256": receipt["field_state_before_sha256"],
        "field_state_after_sha256": receipt["field_state_after_sha256"],
        "field_generation": receipt["field_generation"],
        "regional_field": receipt["regional_field"],
    }


def run_prepare(out_dir: Path, theory_root: Path) -> Mapping[str, Any]:
    require(not out_dir.exists(), f"output directory already exists: {out_dir}")
    out_dir.mkdir(parents=True)
    protocol = protocol_definition(theory_root)
    protocol_sha256 = digest_value(protocol)
    atomic_json(out_dir / "protocol.json", protocol)
    atomic_json(out_dir / "protocol-identity.json", {"schema": PROTOCOL_SCHEMA, "sha256": protocol_sha256})

    memory_path = out_dir / "field-memory"
    trajectory: list[dict[str, Any]] = []
    learning: list[dict[str, Any]] = []
    with CassiFieldWorkMemory(memory_path) as memory:
        state_initial = memory.state_receipt()
        for index, chunk in enumerate(protocol["chunks"], start=1):
            learned = compact_learning(memory.learn(memory_record(chunk)))
            learning.append({"chunk_id": chunk["chunk_id"], **learned})
            if index == 1 or index % 25 == 0 or index == len(protocol["chunks"]):
                trajectory.append({"records_admitted": index, "state": memory.state_receipt()})
        state_after_learning = memory.state_receipt()

    with CassiFieldWorkMemory(memory_path) as restarted:
        state_after_restart = restarted.state_receipt()
        regional_field = restarted.regional_field_receipt()
    require(state_after_restart == state_after_learning, "field memory did not reproduce after ingestion restart")

    prepare = {
        "schema": SCHEMA,
        "stage": "prepare",
        "status": "complete",
        "protocol_sha256": protocol_sha256,
        "harness": harness_identity(),
        "corpus": {
            "documents": len(protocol["documents"]),
            "chunks": len(protocol["chunks"]),
            "source_bytes": sum(int(row["bytes"]) for row in protocol["documents"]),
            "source_sha256": digest_value({row["path"]: row["sha256"] for row in protocol["documents"]}),
        },
        "cassifi_source_identity": cassifi_source_identity(),
        "state_initial": state_initial,
        "state_after_learning": state_after_learning,
        "state_after_restart": state_after_restart,
        "regional_field": regional_field,
        "restart_exact": True,
        "trajectory": trajectory,
        "learning": learning,
    }
    atomic_json(out_dir / "prepare.json", prepare)
    print(json.dumps({"stage": "prepare", "status": "complete", **prepare["corpus"], "restart_exact": True}, sort_keys=True))
    return prepare


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    decoder = json.JSONDecoder()
    for start in [index for index, char in enumerate(stripped) if char == "{"]:
        try:
            value, _end = decoder.raw_decode(stripped[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("response contains no JSON object")


def uncapped_chat(
    client: LocalQwenClient,
    *,
    system: str,
    user: str,
    response_format: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request_body: dict[str, Any] = {
        "model": client.model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "seed": GENERATION_SEED,
        "stream": False,
        "reasoning_format": "deepseek",
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if response_format is not None:
        request_body["response_format"] = dict(response_format)
    response_format_sha256 = digest_value(response_format) if response_format is not None else None
    present_limits = sorted(GENERATION_LIMIT_KEYS.intersection(request_body))
    require(not present_limits, f"generation limit fields unexpectedly present: {present_limits}")
    started = time.perf_counter_ns()
    status, body, raw = client.request("POST", "/v1/chat/completions", request_body, timeout=3600.0)
    elapsed_ns = time.perf_counter_ns() - started
    require(status == 200, f"Qwen chat returned HTTP {status}: {raw}")
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise RuntimeError("Qwen response has no single choice")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise RuntimeError("Qwen response choice is not an object")
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise RuntimeError("Qwen response message is missing")
    content = message.get("content")
    reasoning = message.get("reasoning_content", "")
    require(isinstance(content, str) and bool(content.strip()), "Qwen response content is empty")
    require(isinstance(reasoning, str), "Qwen response reasoning content is invalid")
    generation_parameters = {
        key: value
        for key, value in request_body.items()
        if key not in {"model", "messages"}
    }
    return {
        "content": content,
        "reasoning_content": reasoning,
        "finish_reason": choice.get("finish_reason"),
        "elapsed_ns": elapsed_ns,
        "usage": body.get("usage", {}),
        "timings": body.get("timings", {}),
        "server_cassi_receipt": body.get("cassi"),
        "request_keys": sorted(request_body),
        "generation_parameters": generation_parameters,
        "generation_contract_sha256": digest_value(generation_parameters),
        "system_sha256": digest_value(system),
        "user_prompt_sha256": digest_value(user),
        "generation_limit_fields_present": present_limits,
        "json_schema_sha256": response_format_sha256,
        "request_policy": "no max_tokens, max_completion_tokens, or n_predict; llama.cpp n_predict=-1 default",
    }


ANSWER_SYSTEM = (
    "You are a technical reviewer. Answer the question accurately and do not fabricate CassiTheory-specific facts. "
    "When remembered source chunks are supplied, use them as the authority for CassiTheory-specific claims, distinguish "
    "Derived, Mapped, Calibrated, Hypothesized, conditional, failed, and open results exactly, and cite relevant "
    "root-relative source paths and section names. When no remembered chunks are supplied, use only knowledge already "
    "encoded in the model and do not invent source citations. Write a complete but focused technical answer and stop "
    "naturally when it is complete."
)
NATIVE_SYSTEM = (
    "You are a technical reviewer. Answer the question accurately from knowledge encoded in the model. "
    "Do not fabricate CassiTheory-specific facts or source citations. Write a complete but focused technical answer "
    "and stop naturally when it is complete."
)
NATIVE_PROMPT_STRUCTURE = "QUESTION\n{question}\n\nAnswer the question accurately."


ANSWER_PROMPT_STRUCTURE = (
    "QUESTION\n{question}\n\n"
    "REMEMBERED_SOURCE_CHUNKS\n{source_memory}\n\n"
    "Answer the question accurately from the information available above. Do not invent facts or citations."
)


def answer_contract() -> dict[str, Any]:
    generation_parameters = {
        "temperature": 0,
        "seed": GENERATION_SEED,
        "stream": False,
        "reasoning_format": "deepseek",
        "chat_template_kwargs": {"enable_thinking": False},
    }
    return {
        "system_sha256": digest_value(ANSWER_SYSTEM),
        "prompt_structure_sha256": digest_value(ANSWER_PROMPT_STRUCTURE),
        "generation_contract_sha256": digest_value(generation_parameters),
        "controlled_difference": "REMEMBERED_SOURCE_CHUNKS JSON array only",
    }


def native_contract() -> dict[str, Any]:
    contract = answer_contract()
    return {
        "system_sha256": digest_value(NATIVE_SYSTEM),
        "prompt_structure_sha256": digest_value(NATIVE_PROMPT_STRUCTURE),
        "generation_contract_sha256": contract["generation_contract_sha256"],
        "scope": "native-only diagnostic without an empty memory block or memory-specific instruction",
    }


def harness_identity() -> dict[str, Any]:
    return {
        "schema": "cassi.field-qwen.theory-recall.harness.v1",
        "script_sha256": digest_path(Path(__file__)),
        "max_chunk_chars": MAX_CHUNK_CHARS,
        "max_recalled_chunks_per_question": MAX_RECALLED_CHUNKS_PER_QUESTION,
        "answer_system": ANSWER_SYSTEM,
        "answer_prompt_structure": ANSWER_PROMPT_STRUCTURE,
        "answer_contract": answer_contract(),
        "native_system": NATIVE_SYSTEM,
        "native_prompt_structure": NATIVE_PROMPT_STRUCTURE,
        "native_contract": native_contract(),
    }


def answer_prompt(question: str, records: Sequence[Mapping[str, Any]]) -> str:
    source_memory = [
        {
            "chunk_id": row["chunk_id"],
            "path": row["path"],
            "heading": row["heading"],
            "part": row["part"],
            "source_sha256": row["source_sha256"],
            "text": row["text"],
        }
        for row in records
    ]
    return ANSWER_PROMPT_STRUCTURE.format(
        question=question,
        source_memory=json.dumps(source_memory, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def metrics_process_identity(client: LocalQwenClient) -> dict[str, Any]:
    connection = http.client.HTTPConnection(client.host, client.port, timeout=60.0)
    connection.request("GET", client.prefix + "/metrics")
    response = connection.getresponse()
    raw = response.read()
    process_start_time = response.getheader("Process-Start-Time-Unix")
    melt = {
        "status": response.status,
        "process_start_time_unix": process_start_time,
        "body_sha256": hashlib.sha256(raw).hexdigest(),
    }
    connection.close()
    require(response.status == 200, f"server metrics returned HTTP {response.status}")
    require(bool(process_start_time), "server metrics omitted Process-Start-Time-Unix")
    return melt


def client_identity(
    client: LocalQwenClient,
    model_path: Path,
    server_binary: Path,
    server_pid: int,
    preflight_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    process = psutil.Process(server_pid)
    process_executable = Path(process.exe()).resolve()
    require(digest_path(process_executable) == digest_path(server_binary), "reported server PID does not run the expected binary")
    listeners = [
        {"host": str(connection.laddr.ip), "port": int(connection.laddr.port), "status": connection.status}
        for connection in process.net_connections(kind="tcp")
        if connection.laddr and connection.status == psutil.CONN_LISTEN
    ]
    require(
        any(row["host"] in {"127.0.0.1", "::1"} and row["port"] == client.port for row in listeners),
        "reported server PID does not own the expected loopback listener",
    )
    props_status, props, props_raw = client.request("GET", "/props", timeout=60.0)
    require(props_status == 200, f"server properties returned HTTP {props_status}: {props_raw}")
    final_metrics = metrics_process_identity(client)
    require(
        final_metrics["process_start_time_unix"] == preflight_metrics["process_start_time_unix"],
        "server process changed during the measured stage",
    )
    return {
        "model": {
            "path": str(model_path.resolve()),
            "sha256": client.model_sha256,
            "served_model_id": client.model_id,
            "bytes": model_path.stat().st_size,
        },
        "server_binary": {
            "path": str(server_binary.resolve()),
            "sha256": digest_path(server_binary),
            "bytes": server_binary.stat().st_size,
        },
        "server_runtime": {
            "process_id": server_pid,
            "process_create_time_ns": int(process.create_time() * 1e9),
            "listeners": listeners,
            "props_sha256": digest_value(props),
            "default_generation_settings": props.get("default_generation_settings"),
            "total_slots": props.get("total_slots"),
            "preflight_metrics": dict(preflight_metrics),
            "final_metrics": final_metrics,
        },
    }


def run_baseline(out_dir: Path, base_url: str, model_path: Path, server_binary: Path, server_pid: int) -> Mapping[str, Any]:
    protocol, protocol_sha256 = load_protocol(out_dir)
    client = LocalQwenClient(base_url, model_path=model_path)
    preflight_metrics = metrics_process_identity(client)
    rows: list[dict[str, Any]] = []
    partial = out_dir / "baseline.partial.json"
    for item in protocol["questions"]:
        result = uncapped_chat(client, system=ANSWER_SYSTEM, user=answer_prompt(item["question"], []))
        rows.append({"id": item["id"], "question": item["question"], "answer": result})
        atomic_json(partial, {"schema": SCHEMA, "stage": "baseline", "status": "partial", "protocol_sha256": protocol_sha256, "rows": rows})
    result = {
        "schema": SCHEMA,
        "stage": "baseline",
        "status": "complete",
        "protocol_sha256": protocol_sha256,
        "harness": harness_identity(),
        "answer_contract": answer_contract(),
        **client_identity(client, model_path, server_binary, server_pid, preflight_metrics),
        "rows": rows,
    }
    atomic_json(out_dir / "baseline.json", result)
    if partial.exists():
        partial.unlink()
    print(json.dumps({"stage": "baseline", "status": "complete", "questions": len(rows), "tokens": sum(int(row["answer"]["usage"].get("completion_tokens", 0)) for row in rows)}, sort_keys=True))
    return result


def run_native(out_dir: Path, base_url: str, model_path: Path, server_binary: Path, server_pid: int) -> Mapping[str, Any]:
    protocol, protocol_sha256 = load_protocol(out_dir)
    client = LocalQwenClient(base_url, model_path=model_path)
    preflight_metrics = metrics_process_identity(client)
    rows: list[dict[str, Any]] = []
    partial = out_dir / "native.partial.json"
    for item in protocol["questions"]:
        prompt = NATIVE_PROMPT_STRUCTURE.format(question=item["question"])
        answer = uncapped_chat(client, system=NATIVE_SYSTEM, user=prompt)
        rows.append({"id": item["id"], "question": item["question"], "answer": answer})
        atomic_json(
            partial,
            {"schema": SCHEMA, "stage": "native", "status": "partial", "protocol_sha256": protocol_sha256, "rows": rows},
        )
    result = {
        "schema": SCHEMA,
        "stage": "native",
        "status": "complete",
        "protocol_sha256": protocol_sha256,
        "harness": harness_identity(),
        "answer_contract": native_contract(),
        **client_identity(client, model_path, server_binary, server_pid, preflight_metrics),
        "rows": rows,
    }
    atomic_json(out_dir / "native.json", result)
    if partial.exists():
        partial.unlink()
    print(
        json.dumps(
            {
                "stage": "native",
                "status": "complete",
                "questions": len(rows),
                "tokens": sum(int(row["answer"]["usage"].get("completion_tokens", 0)) for row in rows),
            },
            sort_keys=True,
        )
    )
    return result


def unique_valid(values: Any, valid: set[str]) -> list[str]:
    if not isinstance(values, list):
        return []
    selected: list[str] = []
    for value in values:
        if isinstance(value, str) and value in valid and value not in selected:
            selected.append(value)
    return selected

def selection_response_format(
    name: str,
    field: str,
    valid: set[str],
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    require(bool(valid), f"{name} has no valid selection values")
    selection_limit = len(valid) if max_items is None else min(len(valid), max_items)
    require(selection_limit > 0, f"{name} has no positive selection capacity")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    field: {
                        "type": "array",
                        "items": {"type": "string", "enum": sorted(valid)},
                        "minItems": 1,
                        "maxItems": selection_limit,
                        "uniqueItems": True,
                    }
                },
                "required": [field],
                "additionalProperties": False,
            },
        },
    }




def run_recall(out_dir: Path, base_url: str, model_path: Path, server_binary: Path, server_pid: int) -> Mapping[str, Any]:
    protocol, protocol_sha256 = load_protocol(out_dir)
    prepare = json.loads((out_dir / "prepare.json").read_text(encoding="utf-8"))
    require(prepare["restart_exact"], "prepared memory lacks exact restart receipt")
    worst_case_recall_transitions = MAX_RECALLED_CHUNKS_PER_QUESTION * len(protocol["questions"])
    require(worst_case_recall_transitions <= 64, "configured recall exceeds the 64 prepared-branch capacity")
    client = LocalQwenClient(base_url, model_path=model_path)
    preflight_metrics = metrics_process_identity(client)
    documents = protocol["documents"]
    chunks = protocol["chunks"]
    valid_paths = {str(row["path"]) for row in documents}
    chunk_by_id = {str(row["chunk_id"]): row for row in chunks}
    document_index = [
        {"path": row["path"], "title": row["title"], "synopsis": row["synopsis"]}
        for row in documents
    ]
    rows: list[dict[str, Any]] = []
    recalls_for_ownership: list[Mapping[str, Any]] = []
    qwen_for_ownership: list[Mapping[str, Any]] = []
    partial = out_dir / "recall.partial.json"

    with CassiFieldWorkMemory(out_dir / "field-memory") as memory:
        state_before = memory.state_receipt()
        require(
            state_before == prepare["state_after_restart"],
            "recall session did not open the frozen ingested state; differing receipt keys: "
            + json.dumps(mapping_difference_keys(state_before, prepare["state_after_restart"])),
        )
        for item in protocol["questions"]:
            doc_prompt = (
                "Select the CassiTheory documents materially needed to answer the question. "
                "Return JSON only as {\"document_paths\":[...]}. Do not answer the question. "
                "Choose every needed document and no irrelevant ones.\n\n"
                f"QUESTION={item['question']}\n\nDOCUMENT_INDEX="
                + json.dumps(document_index, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
            doc_plan = uncapped_chat(
                client,
                system="You route private technical questions to source documents. Return the requested JSON object only.",
                user=doc_prompt,
                response_format=selection_response_format(f"documents_{item['id']}", "document_paths", valid_paths),
            )
            qwen_for_ownership.append(doc_plan)
            require(doc_plan["finish_reason"] == "stop", f"document planner did not stop cleanly for {item['id']}")
            try:
                doc_value = parse_json_object(doc_plan["content"])
            except (ValueError, TypeError) as error:
                raise RuntimeError(f"document planner violated its JSON schema for {item['id']}: {error}") from error
            selected_paths = unique_valid(doc_value.get("document_paths"), valid_paths)
            require(bool(selected_paths), f"document planner selected no source for {item['id']}")

            section_index = [
                {"chunk_id": row["chunk_id"], "path": row["path"], "heading": row["heading"], "synopsis": row["synopsis"]}
                for row in chunks
                if row["path"] in selected_paths
            ]
            section_valid_ids = {str(row["chunk_id"]) for row in section_index}
            section_prompt = (
                "Select the remembered source chunks materially needed to answer the question. "
                "Return JSON only as {\"chunk_ids\":[...]}. Do not answer the question. "
                f"Choose up to {MAX_RECALLED_CHUNKS_PER_QUESTION} chunks for a complete, status-accurate synthesis while excluding irrelevant chunks.\n\n"
                f"QUESTION={item['question']}\n\nCHUNK_INDEX="
                + json.dumps(section_index, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
            section_plan = uncapped_chat(
                client,
                system="You route private technical questions to exact remembered source chunks. Return the requested JSON object only.",
                user=section_prompt,
                response_format=selection_response_format(
                    f"chunks_{item['id']}",
                    "chunk_ids",
                    section_valid_ids,
                    max_items=MAX_RECALLED_CHUNKS_PER_QUESTION,
                ),
            )
            qwen_for_ownership.append(section_plan)
            require(section_plan["finish_reason"] == "stop", f"section planner did not stop cleanly for {item['id']}")
            try:
                section_value = parse_json_object(section_plan["content"])
            except (ValueError, TypeError) as error:
                raise RuntimeError(f"section planner violated its JSON schema for {item['id']}: {error}") from error
            selected_chunk_ids = unique_valid(section_value.get("chunk_ids"), section_valid_ids)
            require(bool(selected_chunk_ids), f"section planner selected no source chunk for {item['id']}")

            compact_recalls: list[dict[str, Any]] = []
            records: list[Mapping[str, Any]] = []
            for chunk_id in selected_chunk_ids:
                recall_result = memory.recall(
                    {"corpus": CORPUS_ID, "chunk_id": chunk_id},
                    operation_label=f"theory:{item['id']}:{chunk_id}",
                )
                compact_recalls.append(compact_recall(recall_result))
                recalls_for_ownership.append(recall_result)
                require(len(recall_result["records"]) == 1, f"field failed exact recall for {chunk_id}")
                payload = recall_result["records"][0]["payload"]
                require(payload["chunk_id"] == chunk_id, f"field returned wrong chunk for {chunk_id}")
                require(payload["text_sha256"] == chunk_by_id[chunk_id]["text_sha256"], f"recalled text identity mismatch for {chunk_id}")
                records.append(payload)

            state_before_answer = memory.state_receipt()
            answer = uncapped_chat(client, system=ANSWER_SYSTEM, user=answer_prompt(item["question"], records))
            qwen_for_ownership.append(answer)
            state_after_answer = memory.state_receipt()
            require(state_after_answer == state_before_answer, "Qwen answer generation changed CassiFI memory")
            rows.append(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "document_plan": doc_plan,
                    "document_plan_error": None,
                    "document_selection_provenance": "json_schema",
                    "selected_document_paths": selected_paths,
                    "section_plan": section_plan,
                    "section_plan_error": None,
                    "section_selection_provenance": "json_schema",
                    "selected_chunk_ids": selected_chunk_ids,
                    "recalls": compact_recalls,
                    "recalled_records": records,
                    "answer": answer,
                    "field_state_before_answer": state_before_answer,
                    "field_state_after_answer": state_after_answer,
                    "answer_preserved_memory": True,
                }
            )
            atomic_json(partial, {"schema": SCHEMA, "stage": "recall", "status": "partial", "protocol_sha256": protocol_sha256, "rows": rows})
        state_after = memory.state_receipt()
        regional_field = memory.regional_field_receipt()

    with CassiFieldWorkMemory(out_dir / "field-memory") as restarted:
        state_after_restart = restarted.state_receipt()
        regional_field_after_restart = restarted.regional_field_receipt()
    require(state_after_restart == state_after, "post-evaluation memory did not reproduce after restart")
    require(
        regional_field_after_restart == regional_field,
        "regional field receipt did not reproduce after recall restart",
    )
    receipt = ownership_receipt(
        model_path=model_path,
        model_sha256=client.model_sha256,
        recalls=recalls_for_ownership,
        qwen_results=qwen_for_ownership,
        state=state_after,
    )
    result = {
        "schema": SCHEMA,
        "stage": "recall",
        "status": "complete",
        "protocol_sha256": protocol_sha256,
        "harness": harness_identity(),
        "answer_contract": answer_contract(),
        **client_identity(client, model_path, server_binary, server_pid, preflight_metrics),
        "state_before": state_before,
        "state_after": state_after,
        "state_after_restart": state_after_restart,
        "restart_exact": True,
        "regional_field": regional_field_after_restart,
        "field_recall_budget": {
            "max_prepared_branches": 64,
            "max_chunks_per_question": MAX_RECALLED_CHUNKS_PER_QUESTION,
            "questions": len(protocol["questions"]),
            "worst_case_recall_transitions": worst_case_recall_transitions,
        },
        "rows": rows,
        "ownership_receipt": receipt,
    }
    atomic_json(out_dir / "recall.json", result)
    if partial.exists():
        partial.unlink()
    print(json.dumps({"stage": "recall", "status": "complete", "questions": len(rows), "recalled_chunks": sum(len(row["selected_chunk_ids"]) for row in rows), "restart_exact": True}, sort_keys=True))
    return result


def run_placebo(out_dir: Path, base_url: str, model_path: Path, server_binary: Path, server_pid: int) -> Mapping[str, Any]:
    protocol, protocol_sha256 = load_protocol(out_dir)
    recall = json.loads((out_dir / "recall.json").read_text(encoding="utf-8"))
    require(recall["protocol_sha256"] == protocol_sha256, "placebo source recall uses a different protocol")
    chunk_by_id = {str(row["chunk_id"]): row for row in protocol["chunks"]}
    client = LocalQwenClient(base_url, model_path=model_path)
    preflight_metrics = metrics_process_identity(client)
    rows: list[dict[str, Any]] = []
    partial = out_dir / "placebo.partial.json"
    for recalled in recall["rows"]:
        selected_chunk_ids = [str(value) for value in recalled["selected_chunk_ids"]]
        records = [chunk_by_id[chunk_id] for chunk_id in selected_chunk_ids]
        answer = uncapped_chat(
            client,
            system=ANSWER_SYSTEM,
            user=answer_prompt(str(recalled["question"]), records),
        )
        rows.append(
            {
                "id": recalled["id"],
                "question": recalled["question"],
                "selected_chunk_ids": selected_chunk_ids,
                "literal_records": records,
                "source_provenance": "protocol.json literal chunks selected by the frozen recall-stage planner",
                "answer": answer,
            }
        )
        atomic_json(
            partial,
            {"schema": SCHEMA, "stage": "placebo", "status": "partial", "protocol_sha256": protocol_sha256, "rows": rows},
        )
    result = {
        "schema": SCHEMA,
        "stage": "placebo",
        "status": "complete",
        "protocol_sha256": protocol_sha256,
        "harness": harness_identity(),
        "answer_contract": answer_contract(),
        **client_identity(client, model_path, server_binary, server_pid, preflight_metrics),
        "rows": rows,
    }
    atomic_json(out_dir / "placebo.json", result)
    if partial.exists():
        partial.unlink()
    print(
        json.dumps(
            {
                "stage": "placebo",
                "status": "complete",
                "questions": len(rows),
                "tokens": sum(int(row["answer"]["usage"].get("completion_tokens", 0)) for row in rows),
            },
            sort_keys=True,
        )
    )
    return result


def score_answer(text: str, item: Mapping[str, Any]) -> dict[str, Any]:
    lowered = text.casefold()

    def matches(term: Any) -> bool:
        normalized = str(term).casefold()
        return re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", lowered) is not None

    claim_rows: list[dict[str, Any]] = []
    for alternatives in item["claims"]:
        matched = next((term for term in alternatives if matches(term)), None)
        claim_rows.append({"alternatives": alternatives, "matched": matched, "passed": matched is not None})
    citation_rows = [
        {"path": path, "passed": matches(path)}
        for path in item["required_sources"]
    ]
    claims_passed = sum(bool(row["passed"]) for row in claim_rows)
    citations_passed = sum(bool(row["passed"]) for row in citation_rows)
    claim_fraction = claims_passed / len(claim_rows)
    return {
        "claims_passed": claims_passed,
        "claims_total": len(claim_rows),
        "claim_fraction": claim_fraction,
        "any_claim_recalled": claims_passed > 0,
        "substantial_claim_coverage": claim_fraction >= 0.35,
        "citations_passed": citations_passed,
        "citations_total": len(citation_rows),
        "citation_fraction": citations_passed / len(citation_rows),
        "complete": claims_passed == len(claim_rows) and citations_passed == len(citation_rows),
        "claim_rows": claim_rows,
        "citation_rows": citation_rows,
    }


def aggregate_scores(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def totals(subset: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        claims_passed = sum(int(row["score"]["claims_passed"]) for row in subset)
        claims_total = sum(int(row["score"]["claims_total"]) for row in subset)
        citations_passed = sum(int(row["score"]["citations_passed"]) for row in subset)
        citations_total = sum(int(row["score"]["citations_total"]) for row in subset)
        completion_tokens = sum(int(row["answer"]["usage"].get("completion_tokens", 0)) for row in subset)
        return {
            "questions": len(subset),
            "claims_passed": claims_passed,
            "claims_total": claims_total,
            "claim_fraction": claims_passed / claims_total if claims_total else None,
            "claims_per_1k_completion_tokens": (
                1000.0 * claims_passed / completion_tokens
                if completion_tokens
                else None
            ),
            "citations_passed": citations_passed,
            "citations_total": citations_total,
            "citation_fraction": citations_passed / citations_total if citations_total else None,
            "completion_tokens": completion_tokens,
        }

    score_totals = totals(rows)
    natural_eos_rows = [row for row in rows if row["answer"].get("finish_reason") == "stop"]
    return {
        "questions": len(rows),
        "answers_with_any_claim_recalled": sum(bool(row["score"]["any_claim_recalled"]) for row in rows),
        "answers_with_substantial_claim_coverage": sum(bool(row["score"]["substantial_claim_coverage"]) for row in rows),
        "complete_answers": sum(bool(row["score"]["complete"]) for row in rows),
        **score_totals,
        "prompt_tokens": sum(int(row["answer"]["usage"].get("prompt_tokens", 0)) for row in rows),
        "answer_seconds": sum(int(row["answer"]["elapsed_ns"]) for row in rows) / 1e9,
        "median_answer_seconds": statistics.median(int(row["answer"]["elapsed_ns"]) for row in rows) / 1e9,
        "natural_eos": len(natural_eos_rows),
        "natural_eos_subset": totals(natural_eos_rows),
        "length_responses": sum(row["answer"].get("finish_reason") == "length" for row in rows),
        "generation_limit_fields_present": sorted({key for row in rows for key in row["answer"]["generation_limit_fields_present"]}),
    }


def write_transcript(path: Path, comparisons: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        "CassiTheory uncapped four-arm restarted-memory practical test",
        "============================================================",
        "",
        "All chat requests omitted max_tokens, max_completion_tokens, and n_predict.",
        "Arms: native-only; shared-prompt empty memory; field recall; literal-text placebo.",
        "",
    ]
    for row in comparisons:
        lines.extend(
            [
                f"[{row['id']}]",
                f"Question: {row['question']}",
                f"Selected documents: {json.dumps(row['selected_document_paths'], ensure_ascii=False)}",
                f"Selected chunks: {json.dumps(row['selected_chunk_ids'], ensure_ascii=False)}",
                (
                    f"Native-only: {row['native_completion_tokens']} tokens; finish={row['native_finish_reason']}; "
                    f"{row['native_claims_per_1k_completion_tokens']:.6f} claims/1k tokens"
                ),
                (
                    f"Empty-memory: {row['baseline_completion_tokens']} tokens; finish={row['baseline_finish_reason']}; "
                    f"{row['baseline_claims_per_1k_completion_tokens']:.6f} claims/1k tokens"
                ),
                (
                    f"Field recall: {row['recall_completion_tokens']} tokens; finish={row['recall_finish_reason']}; "
                    f"{row['recall_claims_per_1k_completion_tokens']:.6f} claims/1k tokens"
                ),
                (
                    f"Literal placebo: {row['placebo_completion_tokens']} tokens; finish={row['placebo_finish_reason']}; "
                    f"{row['placebo_claims_per_1k_completion_tokens']:.6f} claims/1k tokens"
                ),
                (
                    "Scores: "
                    f"native={row['native_score']['claims_passed']}/{row['native_score']['claims_total']}; "
                    f"empty={row['baseline_score']['claims_passed']}/{row['baseline_score']['claims_total']}; "
                    f"field={row['recall_score']['claims_passed']}/{row['recall_score']['claims_total']}; "
                    f"placebo={row['placebo_score']['claims_passed']}/{row['placebo_score']['claims_total']}"
                ),
                "",
                "NATIVE-ONLY ANSWER",
                row["native_answer"],
                "",
                "EMPTY-MEMORY ANSWER",
                row["baseline_answer"],
                "",
                "FIELD-RECALL ANSWER",
                row["recall_answer"],
                "",
                "LITERAL-TEXT PLACEBO ANSWER",
                row["placebo_answer"],
                "",
                "-" * 80,
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_analyze(out_dir: Path) -> Mapping[str, Any]:
    protocol, protocol_sha256 = load_protocol(out_dir)
    chunk_by_id = {str(row["chunk_id"]): row for row in protocol["chunks"]}
    prepare = json.loads((out_dir / "prepare.json").read_text(encoding="utf-8"))
    native = json.loads((out_dir / "native.json").read_text(encoding="utf-8"))
    baseline = json.loads((out_dir / "baseline.json").read_text(encoding="utf-8"))
    recall = json.loads((out_dir / "recall.json").read_text(encoding="utf-8"))
    placebo = json.loads((out_dir / "placebo.json").read_text(encoding="utf-8"))
    stages = (prepare, native, baseline, recall, placebo)
    questions_sha256 = digest_value(protocol["questions"])
    current_harness = harness_identity()
    expected_answer_contract = answer_contract()
    expected_native_contract = native_contract()
    exploratory_corpus = {
        "documents": 14,
        "chunks": 352,
        "source_bytes": 1668399,
        "source_sha256": "b9c2f52c2a966fdcae8e0d3a916071b768916149081e5698e07722743599015e",
    }
    protocol_corpus = {
        "documents": len(protocol["documents"]),
        "chunks": len(protocol["chunks"]),
        "source_bytes": sum(int(row["bytes"]) for row in protocol["documents"]),
        "source_sha256": digest_value({row["path"]: row["sha256"] for row in protocol["documents"]}),
    }

    require(all(stage["schema"] == SCHEMA for stage in stages), "stage schemas differ from the current harness")
    require(all(stage["protocol_sha256"] == protocol_sha256 for stage in stages), "stage protocol identities differ")
    measurement_harness = prepare["harness"]
    require(all(stage["harness"] == measurement_harness for stage in stages), "measured-stage harness identities differ")
    require(prepare["corpus"] == protocol_corpus, "prepare corpus identity differs from its frozen protocol")
    require(
        protocol_corpus["documents"] == 14 and protocol_corpus["chunks"] == 352,
        "pinned corpus document or chunk count differs from the controlled design",
    )
    require(questions_sha256 == EXPECTED_QUESTIONS_SHA256, "frozen questions, claims, or citation targets changed")
    with CassiFieldWorkMemory(out_dir / "field-memory") as persisted_memory:
        persisted_state = persisted_memory.state_receipt()
        persisted_regional_field = persisted_memory.regional_field_receipt()
    require(
        baseline["answer_contract"] == recall["answer_contract"] == placebo["answer_contract"] == expected_answer_contract,
        "shared answer instruction contracts differ",
    )
    require(native["answer_contract"] == expected_native_contract, "native-only answer contract differs")
    require(
        native["model"]["sha256"]
        == baseline["model"]["sha256"]
        == recall["model"]["sha256"]
        == placebo["model"]["sha256"],
        "model identity differs across restarted sessions",
    )
    require(
        native["server_binary"]["sha256"]
        == baseline["server_binary"]["sha256"]
        == recall["server_binary"]["sha256"]
        == placebo["server_binary"]["sha256"],
        "server binary differs across restarted sessions",
    )
    runtime_contracts = {
        stage["stage"]: {
            "default_generation_settings": stage["server_runtime"]["default_generation_settings"],
            "total_slots": stage["server_runtime"]["total_slots"],
        }
        for stage in (native, baseline, recall, placebo)
    }
    require(
        len({digest_value(contract) for contract in runtime_contracts.values()}) == 1,
        "stable server runtime contracts differ across restarted sessions",
    )
    require(
        persisted_state == recall["state_after_restart"],
        "persisted field state differs from recall artifact; differing receipt keys: "
        + json.dumps(mapping_difference_keys(persisted_state, recall["state_after_restart"])),
    )
    require(
        persisted_regional_field == recall["regional_field"],
        "persisted regional field differs from recall artifact",
    )
    require(prepare["cassifi_source_identity"] == recall["ownership_receipt"]["cassifi_source_identity"], "CassiFI source identity changed")
    require(prepare["restart_exact"] and recall["restart_exact"], "memory restart evidence is incomplete")
    require(recall["state_after"]["all_finite"], "regional field state is non-finite")

    native_by_id = {row["id"]: row for row in native["rows"]}
    baseline_by_id = {row["id"]: row for row in baseline["rows"]}
    recall_by_id = {row["id"]: row for row in recall["rows"]}
    placebo_by_id = {row["id"]: row for row in placebo["rows"]}
    comparisons: list[dict[str, Any]] = []
    native_scored: list[dict[str, Any]] = []
    baseline_scored: list[dict[str, Any]] = []
    recall_scored: list[dict[str, Any]] = []
    placebo_scored: list[dict[str, Any]] = []

    def completion_tokens(row: Mapping[str, Any]) -> int:
        return int(row["answer"]["usage"].get("completion_tokens", 0))

    def claims_per_1k(score: Mapping[str, Any], tokens: int) -> float:
        return 1000.0 * int(score["claims_passed"]) / tokens if tokens else 0.0

    for item in protocol["questions"]:
        native_row = native_by_id[item["id"]]
        base = baseline_by_id[item["id"]]
        remembered = recall_by_id[item["id"]]
        placebo_row = placebo_by_id[item["id"]]
        native_score = score_answer(native_row["answer"]["content"], item)
        base_score = score_answer(base["answer"]["content"], item)
        remembered_score = score_answer(remembered["answer"]["content"], item)
        placebo_score = score_answer(placebo_row["answer"]["content"], item)
        native_scored.append({**native_row, "score": native_score})
        baseline_scored.append({**base, "score": base_score})
        recall_scored.append({**remembered, "score": remembered_score})
        placebo_scored.append({**placebo_row, "score": placebo_score})

        require(
            base["answer"]["system_sha256"]
            == remembered["answer"]["system_sha256"]
            == placebo_row["answer"]["system_sha256"]
            == expected_answer_contract["system_sha256"],
            f"shared answer system differs for {item['id']}",
        )
        require(
            base["answer"]["generation_contract_sha256"]
            == remembered["answer"]["generation_contract_sha256"]
            == placebo_row["answer"]["generation_contract_sha256"]
            == expected_answer_contract["generation_contract_sha256"],
            f"shared answer generation parameters differ for {item['id']}",
        )
        require(
            base["answer"]["user_prompt_sha256"] == digest_value(answer_prompt(item["question"], [])),
            f"empty-memory answer prompt did not use the common constructor for {item['id']}",
        )
        reconstructed_records = [chunk_by_id[chunk_id] for chunk_id in remembered["selected_chunk_ids"]]
        expected_grounded_prompt_sha256 = digest_value(answer_prompt(item["question"], reconstructed_records))
        require(
            remembered["answer"]["user_prompt_sha256"]
            == placebo_row["answer"]["user_prompt_sha256"]
            == expected_grounded_prompt_sha256,
            f"field and literal-placebo answer prompts differ for {item['id']}",
        )
        require(
            remembered["selected_chunk_ids"] == placebo_row["selected_chunk_ids"],
            f"field and literal-placebo chunks differ for {item['id']}",
        )

        selected_paths = set(remembered["selected_document_paths"])
        required_paths = set(item["required_sources"])
        relevant_paths = selected_paths & required_paths
        selected_required_chunks = [
            chunk_id
            for chunk_id in remembered["selected_chunk_ids"]
            if chunk_by_id[chunk_id]["path"] in required_paths
        ]
        byte_exact = bool(remembered["recalls"]) and all(len(row["records"]) == 1 for row in remembered["recalls"])
        relevant_recall = bool(selected_required_chunks)
        useful_answer_recall = relevant_recall and bool(remembered_score["any_claim_recalled"])
        native_tokens = completion_tokens(native_row)
        base_tokens = completion_tokens(base)
        remembered_tokens = completion_tokens(remembered)
        placebo_tokens = completion_tokens(placebo_row)
        comparisons.append(
            {
                "id": item["id"],
                "question": item["question"],
                "selected_document_paths": remembered["selected_document_paths"],
                "selected_chunk_ids": remembered["selected_chunk_ids"],
                "byte_exact_retrieval": byte_exact,
                "source_set_exact": selected_paths == required_paths,
                "relevant_document_recall": bool(relevant_paths),
                "required_source_coverage": len(relevant_paths) / len(required_paths),
                "irrelevant_documents_selected": len(selected_paths - required_paths),
                "relevant_recall": relevant_recall,
                "selected_required_chunk_ids": selected_required_chunks,
                "useful_answer_recall": useful_answer_recall,
                "answer_preserved_memory": remembered["answer_preserved_memory"],
                "native_score": native_score,
                "baseline_score": base_score,
                "recall_score": remembered_score,
                "placebo_score": placebo_score,
                "native_completion_tokens": native_tokens,
                "baseline_completion_tokens": base_tokens,
                "recall_completion_tokens": remembered_tokens,
                "placebo_completion_tokens": placebo_tokens,
                "native_finish_reason": native_row["answer"].get("finish_reason"),
                "baseline_finish_reason": base["answer"].get("finish_reason"),
                "recall_finish_reason": remembered["answer"].get("finish_reason"),
                "placebo_finish_reason": placebo_row["answer"].get("finish_reason"),
                "native_claims_per_1k_completion_tokens": claims_per_1k(native_score, native_tokens),
                "baseline_claims_per_1k_completion_tokens": claims_per_1k(base_score, base_tokens),
                "recall_claims_per_1k_completion_tokens": claims_per_1k(remembered_score, remembered_tokens),
                "placebo_claims_per_1k_completion_tokens": claims_per_1k(placebo_score, placebo_tokens),
                "field_vs_placebo_same_prompt": (
                    remembered["answer"]["user_prompt_sha256"] == placebo_row["answer"]["user_prompt_sha256"]
                ),
                "field_vs_placebo_same_answer": remembered["answer"]["content"] == placebo_row["answer"]["content"],
                "native_answer": native_row["answer"]["content"],
                "baseline_answer": base["answer"]["content"],
                "recall_answer": remembered["answer"]["content"],
                "placebo_answer": placebo_row["answer"]["content"],
                "native_reasoning": native_row["answer"]["reasoning_content"],
                "baseline_reasoning": base["answer"]["reasoning_content"],
                "recall_reasoning": remembered["answer"]["reasoning_content"],
                "placebo_reasoning": placebo_row["answer"]["reasoning_content"],
            }
        )

    native_summary = aggregate_scores(native_scored)
    baseline_summary = aggregate_scores(baseline_scored)
    recall_summary = aggregate_scores(recall_scored)
    placebo_summary = aggregate_scores(placebo_scored)
    recall_summary["useful_answer_recalls"] = sum(bool(row["useful_answer_recall"]) for row in comparisons)
    recall_summary["grounded_useful_answers"] = sum(
        bool(row["useful_answer_recall"]) and int(row["recall_score"]["citations_passed"]) > 0
        for row in comparisons
    )
    placebo_summary["useful_answer_recalls"] = sum(
        bool(row["relevant_recall"]) and bool(row["placebo_score"]["any_claim_recalled"])
        for row in comparisons
    )
    placebo_summary["grounded_useful_answers"] = sum(
        bool(row["relevant_recall"])
        and bool(row["placebo_score"]["any_claim_recalled"])
        and int(row["placebo_score"]["citations_passed"]) > 0
        for row in comparisons
    )
    for summary in (native_summary, baseline_summary):
        summary["useful_answer_recalls"] = 0
        summary["grounded_useful_answers"] = 0

    def subtract(after: Any, before: Any) -> float | int | None:
        if after is None or before is None:
            return None
        return after - before

    def summary_delta(after: Mapping[str, Any], before: Mapping[str, Any]) -> dict[str, Any]:
        keys = (
            "answers_with_any_claim_recalled",
            "answers_with_substantial_claim_coverage",
            "complete_answers",
            "claims_passed",
            "claim_fraction",
            "claims_per_1k_completion_tokens",
            "citations_passed",
            "citation_fraction",
            "completion_tokens",
            "useful_answer_recalls",
            "grounded_useful_answers",
            "prompt_tokens",
            "answer_seconds",
            "median_answer_seconds",
            "natural_eos",
            "length_responses",
        )
        natural_keys = (
            "questions",
            "claims_passed",
            "claim_fraction",
            "claims_per_1k_completion_tokens",
            "citations_passed",
            "citation_fraction",
            "completion_tokens",
        )
        return {
            **{key: subtract(after.get(key), before.get(key)) for key in keys},
            "natural_eos_subset": {
                "selection": "post-treatment-selected; descriptive only, never the headline comparison",
                **{
                    key: subtract(after["natural_eos_subset"].get(key), before["natural_eos_subset"].get(key))
                    for key in natural_keys
                },
            },
        }

    all_qwen_calls = [row["answer"] for row in native["rows"]]
    all_qwen_calls.extend(row["answer"] for row in baseline["rows"])
    for row in recall["rows"]:
        all_qwen_calls.extend((row["document_plan"], row["section_plan"], row["answer"]))
    all_qwen_calls.extend(row["answer"] for row in placebo["rows"])
    no_generation_caps = all(not row["generation_limit_fields_present"] for row in all_qwen_calls)
    require(no_generation_caps, "one or more Qwen requests contained a generation cap")

    process_identities = {
        stage["stage"]: (
            int(stage["server_runtime"]["process_id"]),
            int(stage["server_runtime"]["process_create_time_ns"]),
        )
        for stage in (native, baseline, recall, placebo)
    }
    first_request_cache_n = {
        "native": native["rows"][0]["answer"]["timings"].get("cache_n"),
        "baseline": baseline["rows"][0]["answer"]["timings"].get("cache_n"),
        "recall": recall["rows"][0]["document_plan"]["timings"].get("cache_n"),
        "placebo": placebo["rows"][0]["answer"]["timings"].get("cache_n"),
    }
    metrics_stable_within_stage = {
        stage["stage"]: (
            stage["server_runtime"]["preflight_metrics"]["process_start_time_unix"]
            == stage["server_runtime"]["final_metrics"]["process_start_time_unix"]
        )
        for stage in (native, baseline, recall, placebo)
    }
    separately_restarted_qwen = (
        len(set(process_identities.values())) == len(process_identities)
        and all(int(value) == 0 for value in first_request_cache_n.values())
        and all(metrics_stable_within_stage.values())
    )
    require(separately_restarted_qwen, "four-arm Qwen process restart evidence is incomplete")

    recall_vs_baseline_slowdowns = [
        int(recall_by_id[row["id"]]["answer"]["elapsed_ns"])
        / int(baseline_by_id[row["id"]]["answer"]["elapsed_ns"])
        for row in comparisons
    ]
    recall_vs_placebo_slowdowns = [
        int(recall_by_id[row["id"]]["answer"]["elapsed_ns"])
        / int(placebo_by_id[row["id"]]["answer"]["elapsed_ns"])
        for row in comparisons
    ]
    theory_ownership_receipt = dict(recall["ownership_receipt"])
    generic_field_owned = dict(theory_ownership_receipt["field_owned_decisions"])
    exact_source_exposures = int(generic_field_owned.get("source_revision_selections", 0))
    generic_field_owned["source_revision_selections"] = exact_source_exposures
    theory_ownership_receipt["field_owned_decisions"] = generic_field_owned
    theory_ownership_receipt["field_owned_operations"] = {
        "semantic_binding_queries": exact_source_exposures,
        "exact_keyed_source_revision_exposures": exact_source_exposures,
    }
    qwen_owned = dict(theory_ownership_receipt["qwen_owned_decisions"])
    qwen_owned["source_chunk_selections"] = exact_source_exposures
    theory_ownership_receipt["qwen_owned_decisions"] = qwen_owned
    theory_ownership_receipt["claim_boundary"] = (
        "CassiFI owns the durable regional cognition.field state, semantic binding queries, and byte-exact keyed "
        "source exposure. Qwen planners choose the requested document and chunk roots; Qwen owns natural-language "
        "reasoning and every emitted token."
    )

    replay_path = out_dir / "replay-probe.json"
    replay_diagnostic: dict[str, Any] = {
        "available": replay_path.is_file(),
        "determinism_precondition_passed": None,
    }
    if replay_path.is_file():
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
        replay_variants = [replay["stored_field"], replay["stored_placebo"], *replay["live_replays"]]
        require(
            len({row["user_prompt_sha256"] for row in replay_variants}) == 1,
            "decode replay prompts differ",
        )
        require(
            len({digest_value(row["generation_parameters"]) for row in replay_variants}) == 1,
            "decode replay generation parameters differ",
        )
        replay_answer_hashes = [str(row["content_sha256"]) for row in replay_variants]
        replay_tokens = [int(row["completion_tokens"]) for row in replay_variants]
        replay_diagnostic = {
            "available": True,
            "schema": replay["schema"],
            "question_id": replay["question_id"],
            "identical_prompt_sha256": replay_variants[0]["user_prompt_sha256"],
            "identical_generation_parameters": replay_variants[0]["generation_parameters"],
            "samples": len(replay_variants),
            "distinct_answer_sha256": len(set(replay_answer_hashes)),
            "completion_tokens": replay_tokens,
            "completion_token_range": [min(replay_tokens), max(replay_tokens)],
            "finish_reasons": [row["finish_reason"] for row in replay_variants],
            "determinism_precondition_passed": len(set(replay_answer_hashes)) == 1,
            "interpretation": (
                "The fixed seed is a request-parity field, not evidence of reproducible decoding. Any divergence among "
                "these byte-identical same-parameter requests is backend noise and invalidates single-generation answer "
                "quality attribution between campaign arms."
            ),
        }

    analysis = {
        "schema": SCHEMA,
        "stage": "analysis",
        "status": "verified",
        "protocol_sha256": protocol_sha256,
        "analysis_harness": current_harness,
        "measurement_harness": measurement_harness,
        "corpus": prepare["corpus"],
        "corpus_comparability": {
            "controlled_source_identity": protocol_corpus,
            "controlled_source_pinned_by_protocol_sha256": protocol_sha256,
            "matches_exploratory_source_identity": protocol_corpus == exploratory_corpus,
            "exploratory_source_identity": exploratory_corpus,
            "source_bytes_delta_since_exploratory": (
                int(protocol_corpus["source_bytes"]) - int(exploratory_corpus["source_bytes"])
            ),
            "questions_and_frozen_claim_targets_match": questions_sha256 == EXPECTED_QUESTIONS_SHA256,
            "questions_sha256": questions_sha256,
            "expected_questions_sha256": EXPECTED_QUESTIONS_SHA256,
            "chunk_to_section_mapping_rederived_from_controlled_corpus": True,
        },
        "sessions": {
            "separately_restarted_qwen": separately_restarted_qwen,
            "process_identities": process_identities,
            "first_request_cache_n": first_request_cache_n,
            "metrics_stable_within_stage": metrics_stable_within_stage,
            "metrics_header_interpretation": (
                "Process-Start-Time-Unix is retained only as a stable within-process server marker on this Windows build; "
                "distinctness rests on the OS PID plus psutil process_create_time_ns tuple."
            ),
            "same_model_sha256": True,
            "same_server_binary_sha256": True,
            "same_stable_server_runtime_contract": True,
            "stable_server_runtime_contracts": runtime_contracts,
            "full_server_properties_sha256": {
                stage["stage"]: stage["server_runtime"]["props_sha256"]
                for stage in (native, baseline, recall, placebo)
            },
            "full_properties_note": (
                "Full /props hashes include the deliberately distinct per-session LLAMA_MEDIA_MARKER. "
                "Comparability is required on the default generation settings and slot count; model and server "
                "binary identities are independently hash-pinned."
            ),
            "shared_prompt_answer_contract": expected_answer_contract,
            "native_only_contract": expected_native_contract,
            "field_restart_exact_before_questions": prepare["restart_exact"],
            "field_restart_exact_after_questions": recall["restart_exact"],
        },
        "prompt_parity": {
            "field_and_placebo_same_answer_prompt": all(
                row["field_vs_placebo_same_prompt"] for row in comparisons
            ),
            "field_and_placebo_same_selected_chunks": all(
                recall_by_id[row["id"]]["selected_chunk_ids"] == placebo_by_id[row["id"]]["selected_chunk_ids"]
                for row in comparisons
            ),
            "empty_memory_constructor_verification": "required per row against answer_prompt(question, [])",
            "shared_instruction_difference": "REMEMBERED_SOURCE_CHUNKS JSON array contents only",
            "native_only_contract_scope": expected_native_contract["scope"],
        },
        "uncapped_generation": {
            "verified": no_generation_caps,
            "requests": len(all_qwen_calls),
            "limit_fields_present": sorted({key for row in all_qwen_calls for key in row["generation_limit_fields_present"]}),
            "all_responses_nonempty": all(bool(row["content"].strip()) for row in all_qwen_calls),
            "all_natural_eos": all(row.get("finish_reason") == "stop" for row in all_qwen_calls),
            "policy": "max_tokens, max_completion_tokens, and n_predict omitted; llama.cpp n_predict=-1 default; each finish reason recorded",
            "natural_eos_responses": sum(row.get("finish_reason") == "stop" for row in all_qwen_calls),
            "length_responses": sum(row.get("finish_reason") == "length" for row in all_qwen_calls),
        },
        "native_only": native_summary,
        "empty_memory": baseline_summary,
        "field_recall": recall_summary,
        "literal_text_placebo": placebo_summary,
        "deltas": {
            "native_only_to_empty_memory": summary_delta(baseline_summary, native_summary),
            "empty_memory_to_field_recall": summary_delta(recall_summary, baseline_summary),
            "empty_memory_to_literal_text_placebo": summary_delta(placebo_summary, baseline_summary),
            "literal_text_placebo_to_field_recall": summary_delta(recall_summary, placebo_summary),
            "interpretation": (
                "Prompt-token deltas are deterministic input costs. Completion-token, answer-time, claim, citation, "
                "and finish-reason deltas are descriptive samples only because the decode-replay determinism "
                "precondition failed."
            ),
        },
        "timing": {
            "field_recall_vs_empty_memory_answer_slowdown_median": statistics.median(recall_vs_baseline_slowdowns),
            "field_recall_vs_empty_memory_answer_slowdown_mean_tail_diagnostic": statistics.mean(recall_vs_baseline_slowdowns),
            "field_recall_vs_literal_placebo_answer_slowdown_median": statistics.median(recall_vs_placebo_slowdowns),
            "field_recall_vs_literal_placebo_answer_slowdown_mean_tail_diagnostic": statistics.mean(recall_vs_placebo_slowdowns),
            "interpretation": (
                "Recorded timings are descriptive only. Identical same-process requests ranged from short natural "
                "completion to a length-terminated runaway, so neither median nor mean supports a causal arm comparison."
            ),
        },
        "memory": {
            "chunks_recalled": sum(len(row["selected_chunk_ids"]) for row in recall["rows"]),
            "byte_exact_retrievals": sum(
                len(row["recalls"])
                for row in recall["rows"]
                if all(len(receipt["records"]) == 1 for receipt in row["recalls"])
            ),
            "questions_with_byte_exact_retrieval": sum(bool(row["byte_exact_retrieval"]) for row in comparisons),
            "questions_with_exact_source_set": sum(bool(row["source_set_exact"]) for row in comparisons),
            "questions_with_relevant_document_recall": sum(bool(row["relevant_document_recall"]) for row in comparisons),
            "questions_with_relevant_recall": sum(bool(row["relevant_recall"]) for row in comparisons),
            "mean_required_source_coverage": statistics.mean(float(row["required_source_coverage"]) for row in comparisons),
            "irrelevant_documents_selected": sum(int(row["irrelevant_documents_selected"]) for row in comparisons),
            "answers_preserving_memory": sum(bool(row["answer_preserved_memory"]) for row in recall["rows"]),
            "field_vs_literal_placebo_exact_answer_matches": sum(
                bool(row["field_vs_placebo_same_answer"]) for row in comparisons
            ),
            "regional_field": recall["regional_field"],
            "semantic_boundary": {
                "computer_id": recall["regional_field"]["computer_id"],
                "profile_sha256": recall["regional_field"]["profile_sha256"],
                "catalog_sha256": recall["regional_field"]["catalog_sha256"],
                "semantic_state_schema": recall["regional_field"]["semantic_state_schema"],
                "semantic_active_bindings": recall["regional_field"]["semantic_active_bindings"],
                "semantic_transitions": recall["regional_field"]["semantic_transitions"],
                "field_semantic_selection_decisions": sum(
                    len(row["recalls"]) for row in recall["rows"]
                ),
                "selection_owner": "cognition.field Binding query and exact active-source boundary",
                "field_operation": "owner-operated semantic inspect/query followed by byte-exact source recall",
                "interpretation": (
                    "The regional field stores typed semantic bindings and their exact evidence roots. "
                    "The Qwen prompt receives only records selected by cognition.field and verified against active source bytes."
                ),
            },
            "state_before": recall["state_before"],
            "state_after": recall["state_after"],
            "state_after_restart": recall["state_after_restart"],
        },
        "comparisons": comparisons,
        "ownership_receipt": theory_ownership_receipt,
        "decode_reproducibility": replay_diagnostic,
        "answer_quality_verdict": {
            "status": "NULL",
            "field_vs_literal_answer_channel": "none after byte-identical prompt materialization",
            "field_vs_literal_exact_answer_matches": sum(
                bool(row["field_vs_placebo_same_answer"]) for row in comparisons
            ),
            "field_vs_literal_questions": len(comparisons),
            "reason": (
                "Field recall and literal-text placebo use byte-identical answer prompts, and the field remains frozen "
                "during answer generation. The same-process replay produced distinct outputs under the same prompt, "
                "temperature zero, and fixed seed, so no single-generation answer-quality delta is attributable."
            ),
        },
        "cost_boundary": {
            "empty_memory_prompt_tokens": int(baseline_summary["prompt_tokens"]),
            "field_recall_prompt_tokens": int(recall_summary["prompt_tokens"]),
            "literal_text_placebo_prompt_tokens": int(placebo_summary["prompt_tokens"]),
            "retrieved_context_prompt_token_overhead": (
                int(recall_summary["prompt_tokens"]) - int(baseline_summary["prompt_tokens"])
            ),
            "field_vs_literal_prompt_token_delta": (
                int(recall_summary["prompt_tokens"]) - int(placebo_summary["prompt_tokens"])
            ),
            "completion_derived_comparisons_interpretable": False,
            "interpretation": (
                "The 61,970-token input overhead belongs to exposing the same recalled text in either field or literal "
                "form. Output length and decode time are noise-bounded by failed replay determinism."
            ),
        },
        "scoring_boundary": (
            "The native-only arm is a diagnostic for the empty-memory directive effect, not an instruction-parity control. "
            "Empty-memory, field-recall, and literal-text-placebo requests use byte-identical system instructions, one "
            "prompt constructor, and the same fixed generation parameter values. The seed proves request parity only; "
            "same-process replay shows that this backend is not output-deterministic at temperature zero. Empty-memory "
            "versus placebo therefore measures supplied-context input cost but only descriptively samples output quality. "
            "Field recall versus placebo has no field channel after prompt materialization and is a NULL control. Recall "
            "is reported at byte-exact and relevant-source levels. Phrase coverage remains a deterministic diagnostic, "
            "not a semantic truth oracle; full transcripts are retained for manual interpretation."
        ),
    }
    atomic_json(out_dir / "analysis.json", analysis)
    write_transcript(out_dir / "answers.txt", comparisons)
    print(
        json.dumps(
            {
                "stage": "analysis",
                "status": "verified",
                "native_only": native_summary,
                "empty_memory": baseline_summary,
                "field_recall": recall_summary,
                "literal_text_placebo": placebo_summary,
                "deltas": analysis["deltas"],
            },
            sort_keys=True,
        )
    )
    return analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "native", "baseline", "recall", "placebo", "analyze"))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--theory-root", type=Path, default=DEFAULT_THEORY_ROOT)
    parser.add_argument("--base-url", default="http://127.0.0.1:18086")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--server-binary", type=Path, default=Path("native/llama.cpp/build-cassi/bin/Release/llama-server.exe"))
    parser.add_argument("--server-pid", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stage == "prepare":
        run_prepare(args.out_dir.resolve(), args.theory_root.resolve())
    elif args.stage in {"native", "baseline", "recall", "placebo"}:
        server_pid = args.server_pid
        require(isinstance(server_pid, int) and server_pid > 0, f"{args.stage} requires --server-pid")
        common = (
            args.out_dir.resolve(),
            args.base_url,
            args.model.resolve(),
            args.server_binary.resolve(),
            server_pid,
        )
        if args.stage == "native":
            run_native(*common)
        elif args.stage == "baseline":
            run_baseline(*common)
        elif args.stage == "recall":
            run_recall(*common)
        else:
            run_placebo(*common)
    else:
        run_analyze(args.out_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
