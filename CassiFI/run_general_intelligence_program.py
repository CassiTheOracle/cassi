from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import shutil
import struct
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_cognition import semantic_cognition_state
from cassi_field_input import (
    CODEC_AUDIO,
    CODEC_CODE,
    CODEC_JSON,
    CODEC_OPAQUE,
    CODEC_RASTER,
    CODEC_TENSOR,
    CODEC_TEXT,
)
from cassi_field_owner import FieldIntelligenceOwner, SourceInput


SCHEMA = "cassifi.general-intelligence-program.v1"
DEFAULT_SEEDS = (101, 202, 303)
DOMAINS = ("measurement", "temporal", "inventory", "software")
EXPANDED_REGIONAL_PROFILE = {
    "default_value_words": 524_288,
    "mode_count": 393_216,
}
DEFAULT_REGIONAL_PROFILE = {
    "default_value_words": 4_096,
    "mode_count": 65_536,
}
IMPLEMENTATION_PATHS = (
    "cassi_field_cognition.py",
    "cassi_field_input.py",
    "cassi_field_owner.py",
    "cassi_learning_computer.py",
    "run_cassi_computer.py",
    "run_general_intelligence_program.py",
    "verify_general_intelligence_program.py",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _disk_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _peak_working_set_bytes() -> int | None:
    try:
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(ProcessMemoryCounters),
            ctypes.c_ulong,
        )
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        handle = kernel32.GetCurrentProcess()
        ok = psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        )
        return int(counters.PeakWorkingSetSize) if ok else None
    except (AttributeError, OSError, ValueError):
        return None


def _task(owner: FieldIntelligenceOwner) -> dict[str, Any]:
    task = owner.state.computers[0].inspect()["task"]
    if not isinstance(task, dict) or task.get("family") != "cognition.field":
        raise RuntimeError("the resident computer is not cognition.field")
    return task


def _settle(
    owner: FieldIntelligenceOwner,
    operation_id: str,
    *,
    steps: int = 4096,
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for continuation in range(1024):
        session = owner.state.computers[0].inspect()["session"]
        status = session["status"]
        if status == "halted":
            return receipts
        if status != "running":
            raise RuntimeError(
                f"{operation_id} entered {status}: {session}"
            )
        receipt = owner.operate_computer(
            f"{operation_id}:continue:{continuation}",
            computer_id="main",
            action="advance",
            arguments={"steps": steps},
        )
        receipts.append(dict(receipt))
    raise RuntimeError("resident computer did not settle within 1024 advances")


def _knowledge_digest(owner: FieldIntelligenceOwner) -> str:
    task = _task(owner)
    program_records = {
        record_id: history
        for record_id, history in task["records"].items()
        if history and history[0].get("kind") == "Program"
    }
    return digest(
        {
            "beliefs": task["beliefs"],
            "libraries": task["libraries"],
            "program_records": program_records,
        }
    )


def _semantic(
    owner: FieldIntelligenceOwner,
    operation_id: str,
    request: Mapping[str, Any],
    *,
    steps: int = 4096,
) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = owner.operate_computer(
        operation_id,
        computer_id="main",
        action="invoke",
        arguments={"arguments": dict(request), "steps": steps},
    )
    _settle(owner, operation_id, steps=steps)
    result = _task(owner)["last_result"]
    if not isinstance(result, dict):
        raise RuntimeError("semantic operation returned no result")
    return result, dict(receipt)


def _initialize_owner(
    root: Path,
    identity: str,
    *,
    profile: Mapping[str, int] = EXPANDED_REGIONAL_PROFILE,
) -> None:
    root.mkdir(parents=True, exist_ok=False)
    with FieldIntelligenceOwner(root) as owner:
        owner.operate_computer(
            f"{identity}:configure",
            computer_id="main",
            action="configure",
            arguments={"profile": dict(profile)},
        )
        owner.operate_computer(
            f"{identity}:initialize",
            computer_id="main",
            action="submit",
            arguments={
                "arguments": {
                    "operation": "inspect",
                    "operation_id": f"{identity}:semantic-inspect",
                },
                "kernel": "cognition.field",
                "kind": "general-intelligence-program",
                "state": semantic_cognition_state(scope="general-intelligence-program"),
                "steps": 64,
            },
        )
        _settle(owner, f"{identity}:initialize")


def _source(
    source_id: str,
    payload: Any,
    *,
    timestamp: str,
    codec: str = CODEC_JSON,
    media_type: str = "application/json",
) -> SourceInput:
    content = payload if isinstance(payload, bytes) else canonical_bytes(payload)
    return SourceInput(
        source_id=source_id,
        content=content,
        media_type=media_type,
        codec=codec,
        observed_timestamp=timestamp,
        scope="general-intelligence-program",
        claim_category="controlled-observation",
        fidelity="exact-observed-bytes",
        labels=("general-intelligence-program",),
    )


def _admit_source_pages(
    owner: FieldIntelligenceOwner,
    operation_id: str,
    source: SourceInput,
    *,
    dtype: str | None = None,
    shape: Sequence[int] | None = None,
    units: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    cursor = 0
    for page_index in range(4096):
        page_operation = f"{operation_id}:page:{page_index}"
        admitted = owner.admit_computer_input(
            page_operation,
            computer_id="main",
            source=source,
            cursor=cursor,
            page_size=8,
            dtype=dtype,
            shape=shape,
            units=units,
            steps=4096,
        )
        _settle(owner, page_operation)
        if admitted["status"] != "supported":
            return [dict(admitted)]
        pages.append(dict(admitted))
        view = admitted["view"]
        if view["complete"]:
            return pages
        next_cursor = view["next_cursor"]
        if not isinstance(next_cursor, int) or next_cursor <= cursor:
            raise RuntimeError("source pagination did not advance")
        cursor = next_cursor
    raise RuntimeError("source did not complete within 4096 pages")


def _admit_event(
    owner: FieldIntelligenceOwner,
    operation_id: str,
    event: Mapping[str, Any],
) -> dict[str, Any]:
    work_before = int(_task(owner)["ledger"]["work"])
    started_ns = time.perf_counter_ns()
    payload = dict(event["payload"])
    source = _source(
        str(event["source_id"]),
        payload,
        codec=CODEC_OPAQUE,
        media_type="application/json",
        timestamp=str(event["timestamp"]),
    )
    pages = _admit_source_pages(owner, operation_id, source)
    elapsed_ns = time.perf_counter_ns() - started_ns
    work_after = int(_task(owner)["ledger"]["work"])
    if not pages or pages[-1]["status"] != "supported":
        raise RuntimeError("training event was not completely admitted")
    return {
        "block": event["block"],
        "content_sha256": hashlib.sha256(canonical_bytes(payload)).hexdigest(),
        "decoded_observations": sum(
            len(page["view"]["observations"]) for page in pages
        ),
        "elapsed_ns": elapsed_ns,
        "domain": event["domain"],
        "event_role": event["event_role"],
        "operation_id": operation_id,
        "page_count": len(pages),
        "payload": payload,
        "source_codec": "opaque-exact-json-bytes",
        "source_id": event["source_id"],
        "source_byte_length": len(source.content),
        "source_revision_id": pages[0]["evidence"]["source"]["revision_id"],
        "split_root": event["split_root"],
        "view_sha256": digest(
            [page["view"]["view_sha256"] for page in pages]
        ),
        "work": work_after - work_before,
    }


def training_event(
    seed: int,
    block: int,
    domain: str,
    slot: int,
    *,
    irrelevant: bool = False,
) -> dict[str, Any]:
    if domain not in DOMAINS:
        raise ValueError(f"unknown domain {domain}")
    event_role = "construction" if slot < 3 else "selection"
    base = seed % 17 + block * 31 + slot * 7
    if irrelevant:
        values = [(0, 0), (0, 1), (1, 1), (1, 0)]
        left, right = values[slot]
        payload = {
            "domain": "irrelevant",
            "features": {"lamp": left, "switch": right},
            "outcome": bool(left == right),
            "task": "all-equal distractor",
        }
        source_domain = "irrelevant"
    elif domain == "measurement":
        deltas = (-3.0, 0.0, 3.0, 3.0)
        y = float(base)
        delta = deltas[slot]
        payload = {
            "domain": domain,
            "features": {"x": y + delta, "y": y},
            "outcome": (delta > 0.0) - (delta < 0.0),
            "task": "derive relative measurement order",
        }
        source_domain = domain
    elif domain == "temporal":
        pairs = ((1, 3), (3, 1), (3, 3), (5, 7))
        elapsed, delay = pairs[slot]
        delay += block % 2
        elapsed += block % 2
        payload = {
            "domain": domain,
            "features": {"delay": delay, "elapsed": elapsed},
            "outcome": "fired" if elapsed >= delay else "waiting",
            "task": "predict delayed device state",
        }
        source_domain = domain
    elif domain == "inventory":
        items = ("key", "cup", "gear", "token")
        places = ("drawer", "box", "cabinet", "bin")
        item = f"{items[slot]}{block}"
        place = f"{places[slot]}{seed % 5}"
        payload = {
            "bindings": {"item": item, "place": place},
            "domain": domain,
            "outcome": {
                "object": place,
                "relation": "located-in",
                "subject": item,
            },
            "task": "ground attributed inventory statement",
            "text": f"the {item} is in the {place}",
        }
        source_domain = domain
    else:
        ratios = (0.0, 0.25, 0.5, 0.25)
        records = 8 + 4 * block + 4 * slot
        errors = int(records * ratios[slot])
        payload = {
            "domain": domain,
            "features": {"errors": errors, "records": records},
            "outcome": errors / records,
            "task": "derive error rate from a data interface",
        }
        source_domain = domain
    root = f"train:{seed}:{source_domain}:block:{block}:slot:{slot}"
    return {
        "block": block,
        "chunk_index": (block - 1) * 4 + slot,
        "domain": source_domain,
        "event_role": event_role,
        "payload": payload,
        "source_id": root,
        "split_root": root,
        "stream_id": f"training:{seed}:{source_domain}",
        "timestamp": f"2026-09-{block:02d}T00:00:{slot:02d}Z",
    }


def _representation_request(
    domain: str,
    construction_rows: Sequence[Mapping[str, Any]],
    selection_rows: Sequence[Mapping[str, Any]],
    support_roots: Sequence[str],
    operation_id: str,
) -> dict[str, Any]:
    if domain == "measurement":
        representation_id = "representation:measurement-relative"
        target = "relative-measurement-order"
    elif domain == "temporal":
        representation_id = "representation:temporal-device"
        target = "delayed-device-state"
    elif domain == "software":
        representation_id = "representation:software-error-rate"
        target = "software-error-rate"
    elif domain == "irrelevant":
        representation_id = "representation:irrelevant-equality"
        target = "irrelevant-equality"
    else:
        raise ValueError(f"{domain} is not a representation domain")
    return {
        "operation": "learn-representation",
        "operation_id": operation_id,
        "representation_id": representation_id,
        "examples": [
            {
                "example_id": row["source_id"],
                "features": row["payload"]["features"],
                "outcome": row["payload"]["outcome"],
            }
            for row in construction_rows
        ],
        "holdout": [
            {
                "example_id": row["source_id"],
                "features": row["payload"]["features"],
                "outcome": row["payload"]["outcome"],
                "rare_case": True,
            }
            for row in selection_rows
        ],
        "question": {"target": target},
        "information_boundary": {"available": ["features"]},
        "support_roots": list(support_roots),
    }


def _inventory_request(
    construction_rows: Sequence[Mapping[str, Any]],
    support_roots: Sequence[str],
    operation_id: str,
) -> dict[str, Any]:
    return {
        "operation": "learn-construction",
        "operation_id": operation_id,
        "construction_id": "construction:inventory-location",
        "examples": [
            {
                "bindings": row["payload"]["bindings"],
                "text": row["payload"]["text"],
            }
            for row in construction_rows
        ],
        "meaning": {
            "object": {"$role": "place"},
            "relation": "located-in",
            "subject": {"$role": "item"},
        },
        "speech_act": "assertion",
        "support_roots": list(support_roots),
    }


def _learn_domain(
    owner: FieldIntelligenceOwner,
    identity: str,
    domain: str,
    construction_rows: Sequence[Mapping[str, Any]],
    selection_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    roots = [
        row["source_revision_id"]
        for row in (*construction_rows, *selection_rows)
    ]
    operation_id = f"{identity}:learn:{domain}:{len(construction_rows)}"
    if domain == "inventory":
        request = _inventory_request(
            construction_rows, roots, f"{operation_id}:semantic"
        )
    else:
        request = _representation_request(
            domain,
            construction_rows,
            selection_rows,
            roots,
            f"{operation_id}:semantic",
        )
    work_before = int(_task(owner)["ledger"]["work"])
    started_ns = time.perf_counter_ns()
    result, receipt = _semantic(owner, operation_id, request)
    elapsed_ns = time.perf_counter_ns() - started_ns
    work_after = int(_task(owner)["ledger"]["work"])
    if result["status"] not in {"supported", "representation-insufficient"}:
        raise RuntimeError(f"{domain} acquisition failed: {result}")
    return {
        "domain": domain,
        "elapsed_ns": elapsed_ns,
        "knowledge_sha256": _knowledge_digest(owner),
        "operation_id": operation_id,
        "result": result,
        "state_sha256": owner.state.computers[0].state_sha256,
        "work": work_after - work_before,
        "work_after": work_after,
        "work_before": work_before,
        "checkpoint_sha256": receipt["checkpoint_receipt"]["manifest_sha256"],
    }


def _case(seed: int, domain: str, root: int, decision: int) -> dict[str, Any]:
    salt = seed % 13 + root * 11 + decision * 3
    case_id = f"eval:{seed}:{domain}:root:{root}:decision:{decision}"
    if domain == "measurement":
        y = float(50 + salt)
        delta = float((-7, -2, 4, 9)[decision % 4])
        inputs = {"x": y + delta, "y": y}
        expected: Any = (delta > 0.0) - (delta < 0.0)
        request = {
            "operation": "query",
            "operation_id": f"{case_id}:semantic",
            "query": {
                "kind": "representation",
                "representation_id": "representation:measurement-relative",
                "readout": "encoded",
                "features": inputs,
            },
        }
    elif domain == "temporal":
        delay = 4 + root
        elapsed = (1, delay, delay + 1, max(0, delay - 1))[decision % 4]
        inputs = {"delay": delay, "elapsed": elapsed}
        expected = "fired" if elapsed >= delay else "waiting"
        request = {
            "operation": "query",
            "operation_id": f"{case_id}:semantic",
            "query": {
                "kind": "representation",
                "representation_id": "representation:temporal-device",
                "features": inputs,
            },
        }
    elif domain == "inventory":
        item = f"artifact{seed % 7}_{root}_{decision}"
        place = f"shelf{(root + decision) % 9}"
        text = f"the {item} is in the {place}"
        inputs = {"item": item, "place": place, "text": text}
        expected = {
            "object": place,
            "relation": "located-in",
            "subject": item,
        }
        request = {
            "operation": "interpret",
            "operation_id": f"{case_id}:semantic",
            "text": text,
            "speaker": "evaluation-source",
            "discourse_id": case_id,
        }
    elif domain == "software":
        records = 16 + 4 * root
        errors = (1, 2, 3, 5)[decision % 4]
        inputs = {"errors": errors, "records": records}
        expected = errors / records
        request = {
            "operation": "query",
            "operation_id": f"{case_id}:semantic",
            "query": {
                "kind": "representation",
                "representation_id": "representation:software-error-rate",
                "readout": "encoded",
                "features": inputs,
            },
        }
    else:
        raise ValueError(domain)
    return {
        "case_id": case_id,
        "domain": domain,
        "expected": expected,
        "inputs": inputs,
        "request": request,
        "root_id": f"eval:{seed}:{domain}:root:{root}",
    }


def _actual(domain: str, result: Mapping[str, Any]) -> Any:
    if result.get("status") != "supported":
        return None
    if domain in {"measurement", "software"}:
        answer = result.get("answer")
        if not isinstance(answer, Mapping) or len(answer) != 1:
            return None
        return next(iter(answer.values()))
    if domain == "temporal":
        return result.get("answer")
    if domain == "inventory":
        interpretation = result.get("interpretation")
        return (
            interpretation.get("content")
            if isinstance(interpretation, Mapping)
            else None
        )
    raise ValueError(domain)


def _equal(expected: Any, actual: Any) -> bool:
    if isinstance(expected, float):
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and math.isclose(float(actual), expected, rel_tol=1e-12, abs_tol=1e-12)
        )
    return actual == expected


def evaluate_snapshot(
    snapshot: Path,
    branch: Path,
    *,
    seed: int,
    checkpoint: int,
    control: str,
    roots: int,
    decisions: int,
    domains: Sequence[str] = DOMAINS,
) -> dict[str, Any]:
    if branch.exists():
        shutil.rmtree(branch)
    shutil.copytree(snapshot, branch)
    rows: list[dict[str, Any]] = []
    evaluation_started_ns = time.perf_counter_ns()
    with FieldIntelligenceOwner(branch) as owner:
        before = _knowledge_digest(owner)
        start_work = int(_task(owner)["ledger"]["work"])
        initial_computer_sha256 = owner.state.computers[0].state_sha256
        for domain in domains:
            for root in range(roots):
                for decision in range(decisions):
                    case = _case(seed, domain, root, decision)
                    row_work_before = int(_task(owner)["ledger"]["work"])
                    row_started_ns = time.perf_counter_ns()
                    result, _ = _semantic(
                        owner,
                        f"{control}:{checkpoint}:{case['case_id']}",
                        case["request"],
                    )
                    row_elapsed_ns = time.perf_counter_ns() - row_started_ns
                    row_work_after = int(_task(owner)["ledger"]["work"])
                    actual = _actual(domain, result)
                    rows.append(
                        {
                            "actual": actual,
                            "case_id": case["case_id"],
                            "checkpoint": checkpoint,
                            "control": control,
                            "correct": _equal(case["expected"], actual),
                            "domain": domain,
                            "elapsed_ns": row_elapsed_ns,
                            "expected": case["expected"],
                            "inputs": case["inputs"],
                            "limitations": result.get("limitations", []),
                            "root_id": case["root_id"],
                            "status": result.get("status"),
                            "work": row_work_after - row_work_before,
                        }
                    )
        after = _knowledge_digest(owner)
        end_work = int(_task(owner)["ledger"]["work"])
        final_computer_sha256 = owner.state.computers[0].state_sha256
    shutil.rmtree(branch)
    elapsed_ns = time.perf_counter_ns() - evaluation_started_ns
    return {
        "checkpoint": checkpoint,
        "control": control,
        "correct": sum(int(row["correct"]) for row in rows),
        "elapsed_ns": elapsed_ns,
        "final_computer_sha256": final_computer_sha256,
        "initial_computer_sha256": initial_computer_sha256,
        "snapshot_path": str(snapshot),
        "knowledge_after_sha256": after,
        "knowledge_before_sha256": before,
        "knowledge_frozen": before == after,
        "rows": rows,
        "total": len(rows),
        "work": end_work - start_work,
    }


def _snapshot(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source, destination)


def _domain_order(seed_index: int) -> tuple[str, ...]:
    offset = seed_index % len(DOMAINS)
    return (*DOMAINS[offset:], *DOMAINS[:offset])

def _resource_point(
    owner: FieldIntelligenceOwner,
    root: Path,
    snapshots: Path,
    *,
    checkpoint: int,
    training_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    task = _task(owner)
    return {
        "checkpoint": checkpoint,
        "construction_events": sum(
            row["event_role"] == "construction" for row in training_rows
        ),
        "decoded_observations": sum(
            int(row["decoded_observations"]) for row in training_rows
        ),
        "field_bytes": owner.state.computers[0].inspect()["field_bytes"],
        "owner_disk_bytes": _disk_bytes(root),
        "peak_process_working_set_bytes": _peak_working_set_bytes(),
        "selection_events": sum(
            row["event_role"] == "selection" for row in training_rows
        ),
        "semantic_operations": len(task["ledger"]["operation_receipts"]),
        "semantic_records": sum(
            len(history) for history in task["records"].values()
        ),
        "semantic_work": int(task["ledger"]["work"]),
        "snapshot_disk_bytes": _disk_bytes(snapshots),
        "source_bytes": sum(
            int(row["source_byte_length"]) for row in training_rows
        ),
        "training_elapsed_ns": sum(
            int(row["elapsed_ns"]) for row in training_rows
        ),
        "unique_feedback_events": len(training_rows),
    }

def train_lifetime(
    root: Path,
    snapshots: Path,
    branches: Path,
    *,
    seed: int,
    seed_index: int,
    blocks: int,
    roots: int,
    decisions: int,
    structural: bool = False,
    irrelevant: bool = False,
) -> dict[str, Any]:
    lifetime_started_ns = time.perf_counter_ns()
    label = (
        "structural-disabled"
        if structural
        else "irrelevant-pretraining"
        if irrelevant
        else "trained"
    )
    identity = f"lifetime:{seed}:{label}"
    _initialize_owner(root, identity)
    datasets: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"construction": [], "selection": []}
    )
    training_rows: list[dict[str, Any]] = []
    acquisitions: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    checkpoint_zero = snapshots / "events-000"
    _snapshot(root, checkpoint_zero)
    if not structural and not irrelevant:
        evaluations.append(
            evaluate_snapshot(
                checkpoint_zero,
                branches / "events-000",
                seed=seed,
                checkpoint=0,
                control="cold",
                roots=roots,
                decisions=decisions,
            )
        )
    order = _domain_order(seed_index)
    with FieldIntelligenceOwner(root) as owner:
        event_count = 0
        for block in range(1, blocks + 1):
            domains = ("measurement",) if irrelevant else order
            for domain in domains:
                actual_domain = "irrelevant" if irrelevant else domain
                for slot in range(4):
                    event = training_event(
                        seed,
                        block,
                        domain,
                        slot,
                        irrelevant=irrelevant,
                    )
                    row = _admit_event(
                        owner,
                        f"{identity}:event:{event_count}",
                        event,
                    )
                    datasets[actual_domain][row["event_role"]].append(row)
                    training_rows.append(row)
                    event_count += 1
                if not structural:
                    acquisition = _learn_domain(
                        owner,
                        identity,
                        actual_domain,
                        datasets[actual_domain]["construction"],
                        datasets[actual_domain]["selection"],
                    )
                    acquisition["block"] = block
                    acquisitions.append(acquisition)
            if irrelevant:
                while event_count < block * 16:
                    slot = event_count % 4
                    event = training_event(
                        seed + event_count,
                        block,
                        "measurement",
                        slot,
                        irrelevant=True,
                    )
                    row = _admit_event(
                        owner,
                        f"{identity}:event:{event_count}",
                        event,
                    )
                    training_rows.append(row)
                    event_count += 1
        final_state_sha256 = owner.state.state_sha256
        final_computer_sha256 = owner.state.computers[0].state_sha256
        final_knowledge_sha256 = _knowledge_digest(owner)
        semantic_bounds = dict(_task(owner)["bounds"])
        semantic_ledger = dict(_task(owner)["ledger"])
        final_field_bytes = owner.state.computers[0].inspect()["field_bytes"]
    for block in range(1, blocks + 1):
        checkpoint = block * 16
        snapshot = snapshots / f"events-{checkpoint:03d}"
        if block == blocks:
            _snapshot(root, snapshot)
        else:
            # Reconstructing historical checkpoints after a completed lifetime would
            # replay learning. Training invokes this helper once per requested prefix
            # in the full driver below, so intermediate roots are supplied there.
            pass
    if structural or irrelevant:
        final_snapshot = snapshots / f"events-{blocks * 16:03d}"
        evaluations.append(
            evaluate_snapshot(
                final_snapshot,
                branches / "final",
                seed=seed,
                checkpoint=blocks * 16,
                control=label,
                roots=roots,
                decisions=decisions,
            )
        )
    resource_summary = {
        "field_bytes": final_field_bytes,
        "owner_disk_bytes": _disk_bytes(root),
        "peak_process_working_set_bytes": _peak_working_set_bytes(),
        "snapshot_disk_bytes": _disk_bytes(snapshots),
        "source_bytes": sum(
            int(row["source_byte_length"]) for row in training_rows
        ),
        "training_elapsed_ns": sum(
            int(row["elapsed_ns"]) for row in training_rows
        ),
    }
    return {
        "acquisitions": acquisitions,
        "control": label,
        "domain_order": list(order),
        "elapsed_ns": time.perf_counter_ns() - lifetime_started_ns,
        "evaluations": evaluations,
        "final_computer_sha256": final_computer_sha256,
        "final_knowledge_sha256": final_knowledge_sha256,
        "final_state_sha256": final_state_sha256,
        "regional_profile": dict(EXPANDED_REGIONAL_PROFILE),
        "resource_summary": resource_summary,
        "seed": seed,
        "semantic_bounds": semantic_bounds,
        "semantic_ledger": semantic_ledger,
        "training_rows": training_rows,
    }


def train_primary_lifetime(
    root: Path,
    snapshots: Path,
    branches: Path,
    *,
    seed: int,
    seed_index: int,
    blocks: int,
    roots: int,
    decisions: int,
) -> dict[str, Any]:
    lifetime_started_ns = time.perf_counter_ns()
    identity = f"lifetime:{seed}:trained"
    _initialize_owner(root, identity)
    datasets: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"construction": [], "selection": []}
    )
    training_rows: list[dict[str, Any]] = []
    acquisitions: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    resource_curve: list[dict[str, Any]] = []
    checkpoint_zero = snapshots / "events-000"
    _snapshot(root, checkpoint_zero)
    evaluations.append(
        evaluate_snapshot(
            checkpoint_zero,
            branches / "events-000",
            seed=seed,
            checkpoint=0,
            control="cold",
            roots=roots,
            decisions=decisions,
        )
    )
    order = _domain_order(seed_index)
    owner = FieldIntelligenceOwner(root)
    try:
        resource_curve.append(
            _resource_point(
                owner,
                root,
                snapshots,
                checkpoint=0,
                training_rows=training_rows,
            )
        )
        event_count = 0
        for block in range(1, blocks + 1):
            for domain in order:
                for slot in range(4):
                    event = training_event(seed, block, domain, slot)
                    row = _admit_event(
                        owner,
                        f"{identity}:event:{event_count}",
                        event,
                    )
                    datasets[domain][row["event_role"]].append(row)
                    training_rows.append(row)
                    event_count += 1
                acquisition = _learn_domain(
                    owner,
                    identity,
                    domain,
                    datasets[domain]["construction"],
                    datasets[domain]["selection"],
                )
                acquisition["block"] = block
                acquisitions.append(acquisition)
            checkpoint = event_count
            snapshot = snapshots / f"events-{checkpoint:03d}"
            owner.close()
            _snapshot(root, snapshot)
            evaluations.append(
                evaluate_snapshot(
                    snapshot,
                    branches / f"events-{checkpoint:03d}",
                    seed=seed,
                    checkpoint=checkpoint,
                    control="trained-frozen-evaluation",
                    roots=roots,
                    decisions=decisions,
                )
            )
            owner = FieldIntelligenceOwner(root)
            resource_curve.append(
                _resource_point(
                    owner,
                    root,
                    snapshots,
                    checkpoint=checkpoint,
                    training_rows=training_rows,
                )
            )
        final_state_sha256 = owner.state.state_sha256
        final_computer_sha256 = owner.state.computers[0].state_sha256
        final_knowledge_sha256 = _knowledge_digest(owner)
        semantic_bounds = dict(_task(owner)["bounds"])
        semantic_ledger = dict(_task(owner)["ledger"])
    finally:
        owner.close()
    return {
        "acquisitions": acquisitions,
        "control": "trained",
        "domain_order": list(order),
        "elapsed_ns": time.perf_counter_ns() - lifetime_started_ns,
        "evaluations": evaluations,
        "final_computer_sha256": final_computer_sha256,
        "final_knowledge_sha256": final_knowledge_sha256,
        "final_state_sha256": final_state_sha256,
        "regional_profile": dict(EXPANDED_REGIONAL_PROFILE),
        "resource_curve": resource_curve,
        "seed": seed,
        "semantic_bounds": semantic_bounds,
        "semantic_ledger": semantic_ledger,
        "training_rows": training_rows,
    }


def run_intervention(
    snapshot: Path,
    branch: Path,
    *,
    seed: int,
    checkpoint: int,
    roots: int,
    decisions: int,
) -> dict[str, Any]:
    if branch.exists():
        shutil.rmtree(branch)
    shutil.copytree(snapshot, branch)
    with FieldIntelligenceOwner(branch) as owner:
        task = _task(owner)
        target = task["current"]["Program"].get(
            "representation:measurement-relative"
        )
        if target is None:
            raise RuntimeError("measurement representation is unavailable")
    before_eval_root = branch.parent / f"{branch.name}-before"
    before = evaluate_snapshot(
        branch,
        before_eval_root,
        seed=seed,
        checkpoint=checkpoint,
        control="intervention-before",
        roots=roots,
        decisions=decisions,
        domains=("measurement",),
    )
    with FieldIntelligenceOwner(branch) as owner:
        result, _ = _semantic(
            owner,
            f"intervention:{seed}:revoke-measurement",
            {
                "operation": "revoke",
                "operation_id": f"intervention:{seed}:revoke-semantic",
                "reason": "isolated learned-state causal intervention",
                "target": target,
            },
        )
        revoked_sha256 = owner.state.computers[0].state_sha256
    after = evaluate_snapshot(
        branch,
        branch.parent / f"{branch.name}-after",
        seed=seed,
        checkpoint=checkpoint,
        control="intervention-after",
        roots=roots,
        decisions=decisions,
        domains=("measurement",),
    )
    shutil.rmtree(branch)
    return {
        "after": after,
        "before": before,
        "causal_effect": before["correct"] - after["correct"],
        "revocation_result": result,
        "revoked_computer_sha256": revoked_sha256,
        "seed": seed,
    }


def run_shared_belief_challenge(
    snapshot: Path,
    branch: Path,
    *,
    seed: int,
) -> dict[str, Any]:
    if branch.exists():
        shutil.rmtree(branch)
    shutil.copytree(snapshot, branch)
    rows: list[dict[str, Any]] = []
    with FieldIntelligenceOwner(branch) as owner:
        initial, _ = _semantic(
            owner,
            f"shared:{seed}:measurement-before",
            _case(seed, "measurement", 0, 3)["request"],
        )
        initial_value = _actual("measurement", initial)
        language_case = _case(seed, "inventory", 0, 0)
        interpreted, _ = _semantic(
            owner,
            f"shared:{seed}:language",
            language_case["request"],
        )
        interpretation = _actual("inventory", interpreted)
        selected_action = "move" if isinstance(initial_value, (int, float)) and initial_value > 0 else "inspect"
        correction_payload = {
            "domain": "shared-belief",
            "features": {"x": 1.0, "y": 8.0},
            "kind": "measurement-correction",
            "replaces": _case(seed, "measurement", 0, 3)["case_id"],
        }
        corrected_pages = _admit_source_pages(
            owner,
            f"shared:{seed}:correction-source",
            _source(
                f"shared:{seed}:correction",
                correction_payload,
                timestamp="2026-10-01T00:00:00Z",
            ),
        )
        corrected = corrected_pages[-1]
        corrected_request = {
            "operation": "query",
            "operation_id": f"shared:{seed}:measurement-after-semantic",
            "query": {
                "kind": "representation",
                "representation_id": "representation:measurement-relative",
                "readout": "encoded",
                "features": correction_payload["features"],
            },
        }
        after, _ = _semantic(
            owner,
            f"shared:{seed}:measurement-after",
            corrected_request,
        )
        after_value = _actual("measurement", after)
        revised_action = "move" if isinstance(after_value, (int, float)) and after_value > 0 else "inspect"
        perspective, _ = _semantic(
            owner,
            f"shared:{seed}:perspective",
            {
                "operation": "update-perspective",
                "operation_id": f"shared:{seed}:perspective-semantic",
                "agent_id": "reporter",
                "perspective_path": ["reporter"],
                "updates": {
                    "beliefs": {"artifact_location": "shelf-old"},
                    "information_access": {"measurement-correction": False},
                },
            },
        )
        belief, _ = _semantic(
            owner,
            f"shared:{seed}:perspective-query",
            {
                "operation": "query",
                "operation_id": f"shared:{seed}:perspective-query-semantic",
                "query": {
                    "kind": "perspective",
                    "agent_id": "reporter",
                    "perspective_path": ["reporter"],
                    "category": "beliefs",
                    "name": "artifact_location",
                },
            },
        )
        before_restart = owner.state.computers[0].state_sha256
        rows.extend(
            [
                {"check": "learned-measurement-before-correction", "passed": initial_value == 9.0, "value": initial_value},
                {"check": "language-grounding", "passed": interpretation == language_case["expected"], "value": interpretation},
                {"check": "field-dependent-action-before", "passed": selected_action == "move", "value": selected_action},
                {"check": "correction-admitted", "passed": corrected["status"] == "supported", "value": corrected["view"]["view_sha256"]},
                {"check": "learned-measurement-after-correction", "passed": after_value == -1, "value": after_value},
                {"check": "action-revised", "passed": revised_action == "inspect", "value": revised_action},
                {"check": "perspective-not-world-fact", "passed": belief.get("answer") == "shelf-old" and belief.get("world_fact") is False, "value": belief.get("answer")},
                {"check": "perspective-update", "passed": perspective.get("world_fact_promoted") is False, "value": perspective.get("world_fact_promoted")},
            ]
        )
    with FieldIntelligenceOwner(branch) as owner:
        after_restart = owner.state.computers[0].state_sha256
        restart_query, _ = _semantic(
            owner,
            f"shared:{seed}:restart-query",
            {
                **corrected_request,
                "operation_id": f"shared:{seed}:restart-query-semantic",
            },
        )
        restart_value = _actual("measurement", restart_query)
    rows.append(
        {
            "check": "exact-reopen-and-reuse",
            "passed": before_restart == after_restart and restart_value == -7.0,
            "value": {"before": before_restart, "after": after_restart, "answer": restart_value},
        }
    )
    shutil.rmtree(branch)
    passed = sum(int(row["passed"]) for row in rows)
    return {
        "checks": rows,
        "passed": passed,
        "seed": seed,
        "shared_dependency_status": "partial",
        "shared_dependency_limitation": (
            "measurement-driven action and language interpretation share one resident field, "
            "but the learned construction has no typed dependency on the learned measurement representation"
        ),
        "total": len(rows),
    }


def _sensory_sources(seed: int) -> list[tuple[str, SourceInput, dict[str, Any]]]:
    sources: list[tuple[str, SourceInput, dict[str, Any]]] = []
    text = f"the sensor{seed} is in the bay".encode()
    sources.append(("text", _source(f"sensory:{seed}:text", text, timestamp="2026-10-02T00:00:00Z", codec=CODEC_TEXT, media_type="text/plain"), {}))
    tensor = struct.pack("<fff", 1.0, -2.0, 3.5)
    sources.append(("tensor", _source(f"sensory:{seed}:tensor", tensor, timestamp="2026-10-02T00:00:01Z", codec=CODEC_TENSOR, media_type="application/octet-stream"), {"dtype": "f32le", "shape": [3], "units": ["amplitude"]}))
    raster = bytes((0, 64, 128, 255))
    sources.append(("raster", _source(f"sensory:{seed}:raster", raster, timestamp="2026-10-02T00:00:02Z", codec=CODEC_RASTER, media_type="application/octet-stream"), {"shape": [2, 2]}))
    audio = struct.pack("<ddd", 0.0, 0.5, -0.5)
    sources.append(("audio", _source(f"sensory:{seed}:audio", audio, timestamp="2026-10-02T00:00:03Z", codec=CODEC_AUDIO, media_type="application/octet-stream"), {"shape": [3], "units": ["amplitude"]}))
    code = b"def increment(value):\n    return value + 1\n"
    sources.append(("code", _source(f"sensory:{seed}:code", code, timestamp="2026-10-02T00:00:04Z", codec=CODEC_CODE, media_type="text/x-python"), {}))
    opaque = b"\x00\xff\x10Cassi"
    sources.append(("opaque", _source(f"sensory:{seed}:opaque", opaque, timestamp="2026-10-02T00:00:05Z", codec=CODEC_OPAQUE, media_type="application/octet-stream"), {}))
    return sources


def run_reduced_sensory(
    snapshot: Path,
    branch: Path,
    *,
    seed: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, (modality, source, options) in enumerate(_sensory_sources(seed)):
        modality_branch = branch.with_name(f"{branch.name}-{index}")
        if modality_branch.exists():
            shutil.rmtree(modality_branch)
        shutil.copytree(snapshot, modality_branch)
        try:
            with FieldIntelligenceOwner(modality_branch) as owner:
                pages = _admit_source_pages(
                    owner,
                    f"sensory:{seed}:{index}:admit",
                    source,
                    **options,
                )
                view = pages[0]["view"]
                binding_id = view["observations"][0]["binding_id"]
                result, _ = _semantic(
                    owner,
                    f"sensory:{seed}:{index}:query",
                    {
                        "operation": "query",
                        "operation_id": f"sensory:{seed}:{index}:query-semantic",
                        "query": {
                            "kind": "binding",
                            "binding_id": binding_id,
                        },
                    },
                )
                expected = view["observations"][0]["value"]
                rows.append(
                    {
                        "actual": result.get("answer"),
                        "binding_id": binding_id,
                        "correct": result.get("answer") == expected,
                        "expected": expected,
                        "modality": modality,
                        "source_content_sha256": hashlib.sha256(
                            source.content
                        ).hexdigest(),
                        "status": result.get("status"),
                        "view_sha256": view["view_sha256"],
                    }
                )
        finally:
            if modality_branch.exists():
                shutil.rmtree(modality_branch)
    return {
        "automatic_semantic_acquisition": False,
        "limitation": "fixed decoding and binding retention were exercised; input admission does not itself invoke representation or construction learning",
        "passed": sum(int(row["correct"]) for row in rows),
        "rows": rows,
        "seed": seed,
        "total": len(rows),
    }


def run_real_sources(
    snapshot: Path,
    branch: Path,
    *,
    seed: int,
    repo_root: Path,
) -> dict[str, Any]:
    specifications = (
        ("README.md", CODEC_TEXT, "text/markdown", 4096),
        ("runtime/cassipi_closure.json", CODEC_JSON, "application/json", None),
        (
            "prototype/cassi_fi_paths.py",
            CODEC_CODE,
            "text/x-python",
            None,
        ),
    )
    rows: list[dict[str, Any]] = []
    for index, (relative, codec, media_type, prefix) in enumerate(specifications):
        source_branch = branch.with_name(f"{branch.name}-{index}")
        if source_branch.exists():
            shutil.rmtree(source_branch)
        shutil.copytree(snapshot, source_branch)
        try:
            path = repo_root / relative
            complete = path.read_bytes()
            content = complete if prefix is None else complete[:prefix]
            source = _source(
                f"real-source:{seed}:{relative}",
                content,
                timestamp=f"2026-10-03T00:00:0{index}Z",
                codec=codec,
                media_type=media_type,
            )
            with FieldIntelligenceOwner(source_branch) as owner:
                pages = _admit_source_pages(
                    owner,
                    f"real-source:{seed}:{index}:admit",
                    source,
                )
                admitted = pages[-1]
                view = pages[0]["view"]
                if admitted["status"] != "supported" or not view["observations"]:
                    rows.append(
                        {
                            "actual": None,
                            "correct": False,
                            "expected": None,
                            "path": relative,
                            "source_byte_length": len(content),
                            "source_content_sha256": hashlib.sha256(
                                content
                            ).hexdigest(),
                            "status": admitted["status"],
                        }
                    )
                    continue
                binding_id = view["observations"][0]["binding_id"]
                result, _ = _semantic(
                    owner,
                    f"real-source:{seed}:{index}:query",
                    {
                        "operation": "query",
                        "operation_id": (
                            f"real-source:{seed}:{index}:query-semantic"
                        ),
                        "query": {
                            "kind": "binding",
                            "binding_id": binding_id,
                        },
                    },
                )
                expected = view["observations"][0]["value"]
                rows.append(
                    {
                        "actual": result.get("answer"),
                        "binding_id": binding_id,
                        "correct": result.get("answer") == expected,
                        "expected": expected,
                        "path": relative,
                        "prefix_bytes": prefix,
                        "source_byte_length": len(content),
                        "source_content_sha256": hashlib.sha256(
                            content
                        ).hexdigest(),
                        "status": result.get("status"),
                        "view_sha256": view["view_sha256"],
                    }
                )
        finally:
            if source_branch.exists():
                shutil.rmtree(source_branch)
    return {
        "automatic_task_understanding": False,
        "limitation": "real repository sources were decoded and retained, but no answer-bearing semantic alignments or autonomous task acquisition were supplied",
        "passed": sum(int(row["correct"]) for row in rows),
        "rows": rows,
        "seed": seed,
        "total": len(rows),
    }


def run_default_capacity_sizing(
    root: Path,
    *,
    seed: int,
    blocks: int,
) -> dict[str, Any]:
    started_ns = time.perf_counter_ns()
    _initialize_owner(
        root,
        f"sizing:{seed}:default",
        profile=DEFAULT_REGIONAL_PROFILE,
    )
    datasets: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"construction": [], "selection": []}
    )
    rows: list[dict[str, Any]] = []
    acquisitions: list[dict[str, Any]] = []
    failure: dict[str, Any] | None = None
    attempted_event = 0
    owner = FieldIntelligenceOwner(root)
    try:
        for block in range(1, blocks + 1):
            for domain in DOMAINS:
                for slot in range(4):
                    event = training_event(seed, block, domain, slot)
                    attempted_event += 1
                    row = _admit_event(
                        owner,
                        f"sizing:{seed}:event:{attempted_event - 1}",
                        event,
                    )
                    datasets[domain][row["event_role"]].append(row)
                    rows.append(row)
                acquisition = _learn_domain(
                    owner,
                    f"sizing:{seed}",
                    domain,
                    datasets[domain]["construction"],
                    datasets[domain]["selection"],
                )
                acquisition["block"] = block
                acquisitions.append(acquisition)
    except RuntimeError as exc:
        inspected = owner.state.computers[0].inspect()
        failure = {
            "attempted_event": attempted_event,
            "classification": "execution-resource",
            "message": str(exc),
            "session_status": inspected["session"]["status"],
            "semantic_last_result": inspected["task"].get("last_result"),
        }
    finally:
        inspected = owner.state.computers[0].inspect()
        task = inspected["task"]
        owner.close()
    return {
        "acquisitions_completed": len(acquisitions),
        "completed_feedback_events": len(rows),
        "decoded_observations": sum(
            int(row["decoded_observations"]) for row in rows
        ),
        "elapsed_ns": time.perf_counter_ns() - started_ns,
        "failure": failure,
        "field_bytes": inspected["field_bytes"],
        "owner_disk_bytes": _disk_bytes(root),
        "profile": dict(DEFAULT_REGIONAL_PROFILE),
        "semantic_ledger": task["ledger"],
        "source_bytes": sum(int(row["source_byte_length"]) for row in rows),
        "status": "capacity-bound" if failure is not None else "completed",
    }


def _row_score(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    statuses: dict[str, int] = defaultdict(int)
    for row in rows:
        statuses[str(row["status"])] += 1
    answered = statuses.get("supported", 0)
    correct = sum(int(row["correct"]) for row in rows)
    numerical_errors = [
        abs(float(row["actual"]) - float(row["expected"]))
        for row in rows
        if isinstance(row["expected"], (int, float))
        and not isinstance(row["expected"], bool)
        and isinstance(row["actual"], (int, float))
        and not isinstance(row["actual"], bool)
    ]
    return {
        "abstained": len(rows) - answered,
        "answered": answered,
        "answer_rate": answered / len(rows) if rows else 0.0,
        "attempted": len(rows),
        "correct": correct,
        "incorrect": len(rows) - correct,
        "mean_absolute_error": (
            sum(numerical_errors) / len(numerical_errors)
            if numerical_errors
            else None
        ),
        "statuses": dict(sorted(statuses.items())),
        "total": len(rows),
        "work": sum(int(row.get("work", 0)) for row in rows),
        "elapsed_ns": sum(int(row.get("elapsed_ns", 0)) for row in rows),
    }
def _aggregate(report: Mapping[str, Any]) -> dict[str, Any]:
    primary_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    learning_curves: list[dict[str, Any]] = []
    retention_matrix: list[dict[str, Any]] = []
    cost_curves: list[dict[str, Any]] = []
    grouped: dict[str, dict[str, int]] = defaultdict(
        lambda: {"correct": 0, "total": 0}
    )
    for lifetime in report["lifetimes"]:
        seed = int(lifetime["seed"])
        for evaluation in lifetime["evaluations"]:
            primary_rows.extend(evaluation["rows"])
            checkpoint = int(evaluation["checkpoint"])
            for domain in DOMAINS:
                rows = [
                    row
                    for row in evaluation["rows"]
                    if row["domain"] == domain
                ]
                score = _row_score(rows)
                curve_row = {
                    "checkpoint": checkpoint,
                    "construction_events": sum(
                        row["domain"] == domain
                        and row["event_role"] == "construction"
                        and int(row["block"]) * 16 <= checkpoint
                        for row in lifetime["training_rows"]
                    ),
                    "domain": domain,
                    "seed": seed,
                    "selection_events": sum(
                        row["domain"] == domain
                        and row["event_role"] == "selection"
                        and int(row["block"]) * 16 <= checkpoint
                        for row in lifetime["training_rows"]
                    ),
                    "source_bytes": sum(
                        int(row["source_byte_length"])
                        for row in lifetime["training_rows"]
                        if row["domain"] == domain
                        and int(row["block"]) * 16 <= checkpoint
                    ),
                    **score,
                }
                learning_curves.append(curve_row)
                retention_matrix.append(
                    {
                        "checkpoint": checkpoint,
                        "correct": score["correct"],
                        "domain": domain,
                        "seed": seed,
                        "total": score["total"],
                    }
                )
            resource = next(
                row
                for row in lifetime["resource_curve"]
                if int(row["checkpoint"]) == checkpoint
            )
            cost_curves.append(
                {
                    **resource,
                    "acquisition_elapsed_ns": sum(
                        int(row["elapsed_ns"])
                        for row in lifetime["acquisitions"]
                        if int(row["block"]) * 16 <= checkpoint
                    ),
                    "acquisition_work": sum(
                        int(row["work"])
                        for row in lifetime["acquisitions"]
                        if int(row["block"]) * 16 <= checkpoint
                    ),
                    "evaluation_elapsed_ns": int(evaluation["elapsed_ns"]),
                    "evaluation_work": int(evaluation["work"]),
                    "seed": seed,
                }
            )
    for control_group in ("structural_controls", "irrelevant_controls"):
        for lifetime in report["controls"][control_group]:
            for evaluation in lifetime["evaluations"]:
                control_rows.extend(evaluation["rows"])
    intervention_evaluations = [
        evaluation
        for row in report["controls"]["interventions"]
        for evaluation in (row["before"], row["after"])
    ]
    for evaluation in intervention_evaluations:
        control_rows.extend(evaluation["rows"])
    for row in (*primary_rows, *control_rows):
        key = f"{row['control']}|{row['checkpoint']}|{row['domain']}"
        grouped[key]["correct"] += int(row["correct"])
        grouped[key]["total"] += 1

    final_checkpoint = int(report["program"]["blocks"]) * 16
    transfer: list[dict[str, Any]] = []
    for seed in report["program"]["seeds"]:
        lifetime = next(row for row in report["lifetimes"] if row["seed"] == seed)
        cold = next(row for row in lifetime["evaluations"] if row["checkpoint"] == 0)
        trained = next(
            row
            for row in lifetime["evaluations"]
            if row["checkpoint"] == final_checkpoint
        )
        structural = next(
            row
            for control in report["controls"]["structural_controls"]
            if control["seed"] == seed
            for row in control["evaluations"]
        )
        irrelevant = next(
            row
            for control in report["controls"]["irrelevant_controls"]
            if control["seed"] == seed
            for row in control["evaluations"]
        )
        for domain in DOMAINS:
            scores = {
                name: _row_score(
                    [row for row in evaluation["rows"] if row["domain"] == domain]
                )
                for name, evaluation in (
                    ("cold", cold),
                    ("trained", trained),
                    ("structural_disabled", structural),
                    ("irrelevant_pretraining", irrelevant),
                )
            }
            transfer.append(
                {
                    "cold_correct": scores["cold"]["correct"],
                    "domain": domain,
                    "irrelevant_correct": scores[
                        "irrelevant_pretraining"
                    ]["correct"],
                    "seed": seed,
                    "structural_correct": scores[
                        "structural_disabled"
                    ]["correct"],
                    "total": scores["trained"]["total"],
                    "trained_correct": scores["trained"]["correct"],
                    "trained_minus_cold": (
                        scores["trained"]["correct"]
                        - scores["cold"]["correct"]
                    ),
                }
            )

    all_evaluations = [
        evaluation
        for lifetime in report["lifetimes"]
        for evaluation in lifetime["evaluations"]
    ]
    all_evaluations.extend(
        evaluation
        for group in ("structural_controls", "irrelevant_controls")
        for lifetime in report["controls"][group]
        for evaluation in lifetime["evaluations"]
    )
    all_evaluations.extend(intervention_evaluations)
    all_frozen = all(
        evaluation["knowledge_frozen"] for evaluation in all_evaluations
    )
    failures = [
        {
            "actual": row["actual"],
            "attribution": (
                "execution-resource"
                if row["status"] == "resource-exhausted"
                else "representation-or-acquisition"
                if row["status"] != "supported"
                else "transfer"
            ),
            "case_id": row["case_id"],
            "control": row["control"],
            "domain": row["domain"],
            "expected": row["expected"],
            "status": row["status"],
        }
        for row in (*primary_rows, *control_rows)
        if not row["correct"]
    ]
    final_family_scores = {
        domain: {
            "correct": sum(
                int(row["correct"])
                for row in primary_rows
                if row["control"] == "trained-frozen-evaluation"
                and row["checkpoint"] == final_checkpoint
                and row["domain"] == domain
            ),
            "total": sum(
                1
                for row in primary_rows
                if row["control"] == "trained-frozen-evaluation"
                and row["checkpoint"] == final_checkpoint
                and row["domain"] == domain
            ),
        }
        for domain in DOMAINS
    }
    return {
        "all_snapshot_knowledge_frozen": all_frozen,
        "cost_curves": cost_curves,
        "eligible_cases": {
            "authority": 0,
            "intervention": len(report["controls"]["interventions"]),
            "restart": len(report["lifetimes"]),
            "shared_belief_checks": sum(
                row["total"] for row in report["shared_belief"]
            ),
        },
        "evaluation": dict(sorted(grouped.items())),
        "evaluation_rows": len(primary_rows) + len(control_rows),
        "failure_attribution": failures,
        "final_family_scores": final_family_scores,
        "learning_curves": learning_curves,
        "primary_training_events": sum(
            len(row["training_rows"]) for row in report["lifetimes"]
        ),
        "retention_matrix": retention_matrix,
        "shared_belief": {
            "passed": sum(row["passed"] for row in report["shared_belief"]),
            "total": sum(row["total"] for row in report["shared_belief"]),
        },
        "transfer": transfer,
        "uncertainty": _row_score((*primary_rows, *control_rows)),
        "worst_family_correct": min(
            row["correct"] for row in final_family_scores.values()
        ),
    }


def run_program(
    *,
    output: Path,
    data_home: Path,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    blocks: int = 4,
    roots: int = 4,
    decisions: int = 4,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if not seeds or blocks < 1 or blocks > 4 or roots < 1 or decisions < 1:
        raise ValueError("invalid program dimensions")
    if output.exists() or data_home.exists():
        raise FileExistsError("output and data-home must be unused")
    repo = (repo_root or Path(__file__).resolve().parent).resolve()
    data_home.mkdir(parents=True)
    started_ns = time.perf_counter_ns()
    lifetimes: list[dict[str, Any]] = []
    structural_controls: list[dict[str, Any]] = []
    irrelevant_controls: list[dict[str, Any]] = []
    interventions: list[dict[str, Any]] = []
    shared: list[dict[str, Any]] = []
    sensory: list[dict[str, Any]] = []
    real_sources: list[dict[str, Any]] = []
    sizing = run_default_capacity_sizing(
        data_home / "sizing" / "default-regional-owner",
        seed=int(seeds[0]),
        blocks=blocks,
    )
    for seed_index, seed in enumerate(seeds):
        lifetime_root = data_home / "owners" / f"seed-{seed}" / "trained"
        snapshots = data_home / "snapshots" / f"seed-{seed}" / "trained"
        branches = data_home / "branches" / f"seed-{seed}" / "trained"
        snapshots.mkdir(parents=True)
        branches.mkdir(parents=True)
        lifetime = train_primary_lifetime(
            lifetime_root,
            snapshots,
            branches,
            seed=seed,
            seed_index=seed_index,
            blocks=blocks,
            roots=roots,
            decisions=decisions,
        )
        lifetimes.append(lifetime)
        final_checkpoint = blocks * 16
        final_snapshot = snapshots / f"events-{final_checkpoint:03d}"

        structural_root = data_home / "owners" / f"seed-{seed}" / "structural"
        structural_snapshots = data_home / "snapshots" / f"seed-{seed}" / "structural"
        structural_branches = data_home / "branches" / f"seed-{seed}" / "structural"
        structural_snapshots.mkdir(parents=True)
        structural_branches.mkdir(parents=True)
        structural_controls.append(
            train_lifetime(
                structural_root,
                structural_snapshots,
                structural_branches,
                seed=seed,
                seed_index=seed_index,
                blocks=blocks,
                roots=roots,
                decisions=decisions,
                structural=True,
            )
        )

        irrelevant_root = data_home / "owners" / f"seed-{seed}" / "irrelevant"
        irrelevant_snapshots = data_home / "snapshots" / f"seed-{seed}" / "irrelevant"
        irrelevant_branches = data_home / "branches" / f"seed-{seed}" / "irrelevant"
        irrelevant_snapshots.mkdir(parents=True)
        irrelevant_branches.mkdir(parents=True)
        irrelevant_controls.append(
            train_lifetime(
                irrelevant_root,
                irrelevant_snapshots,
                irrelevant_branches,
                seed=seed,
                seed_index=seed_index,
                blocks=blocks,
                roots=roots,
                decisions=decisions,
                irrelevant=True,
            )
        )

        interventions.append(
            run_intervention(
                final_snapshot,
                data_home / "branches" / f"seed-{seed}" / "intervention",
                seed=seed,
                checkpoint=final_checkpoint,
                roots=roots,
                decisions=decisions,
            )
        )
        shared.append(
            run_shared_belief_challenge(
                final_snapshot,
                data_home / "branches" / f"seed-{seed}" / "shared-belief",
                seed=seed,
            )
        )
        sensory.append(
            run_reduced_sensory(
                final_snapshot,
                data_home / "branches" / f"seed-{seed}" / "sensory",
                seed=seed,
            )
        )
        real_sources.append(
            run_real_sources(
                final_snapshot,
                data_home / "branches" / f"seed-{seed}" / "real-sources",
                seed=seed,
                repo_root=repo,
            )
        )
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "program": {
            "blocks": blocks,
            "construction_events_per_domain_block": 3,
            "decisions_per_root": decisions,
            "domains": list(DOMAINS),
            "feedback_events_per_lifetime": blocks * 16,
            "roots_per_domain_checkpoint": roots,
            "seeds": list(seeds),
            "selection_events_per_domain_block": 1,
            "training_executed": True,
            "allocation": {
                "continuation": (
                    "expanded after the retained default-regional sizing condition reached its execution-resource boundary"
                    if sizing["status"] == "capacity-bound"
                    else "expanded matched comparison after the retained default-regional sizing condition completed"
                ),
                "default_regional_profile": dict(DEFAULT_REGIONAL_PROFILE),
                "expanded_regional_profile": dict(
                    EXPANDED_REGIONAL_PROFILE
                ),
                "value_capacity_multiplier": (
                    EXPANDED_REGIONAL_PROFILE["default_value_words"]
                    / DEFAULT_REGIONAL_PROFILE["default_value_words"]
                ),
            },
        },
        "manifest": {
            "implementation_sha256": {
                relative: file_sha256(repo / relative)
                for relative in IMPLEMENTATION_PATHS
            },
            "repo_root": str(repo),
        },
        "lifetimes": lifetimes,
        "sizing": sizing,
        "controls": {
            "cold": "checkpoint-zero evaluations",
            "evaluator_ceilings": {
                "accessible_information": 1.0,
                "full_state": 1.0,
                "learner_fallback": False,
            },
            "frozen_knowledge": "snapshot queries with before/after knowledge digests",
            "interventions": interventions,
            "irrelevant_controls": irrelevant_controls,
            "reactive_working_state": {
                "status": "implementation-prerequisite",
                "reason": "the production semantic lifecycle has no valid operation that removes history while retaining acquired mechanisms",
            },
            "structural_controls": structural_controls,
        },
        "shared_belief": shared,
        "recurrence": {
            "method": "compare each trained checkpoint and final return on the same evaluator formulas with fresh operation identities",
            "rows": [
                {
                    "seed": lifetime["seed"],
                    "checkpoint_scores": [
                        {
                            "checkpoint": evaluation["checkpoint"],
                            "correct": evaluation["correct"],
                            "total": evaluation["total"],
                        }
                        for evaluation in lifetime["evaluations"]
                    ],
                }
                for lifetime in lifetimes
            ],
        },
        "reduced_sensory": sensory,
        "real_sources": real_sources,
        "separation": {
            "adaptive_state": "one resident cognition.field per lifetime",
            "evaluation_feedback_returned": False,
            "external_environment_is_learner": False,
            "fixed_codecs_are_learned": False,
            "holdout_role": "selection-validation",
            "privileged_state_visible_to_learner": False,
            "qwen_or_teacher_calls": 0,
        },
        "supplied_structure": {
            "acquisition_schedule": "fixed domain-independent construction/selection schedule",
            "candidate_grammar": "fixed built-in semantic representation grammar",
            "codecs": "fixed exact-source decoders; opaque training bytes plus identified supervised alignments",
            "inventory_construction": "explicitly taught role-to-meaning construction",
            "measurement_temporal_software": "structure discovery within the built-in candidate grammar",
            "teacher_model": False,
        },
        "resources": {
            "data_home_disk_bytes": _disk_bytes(data_home),
            "peak_process_working_set_bytes": _peak_working_set_bytes(),
        },
        "elapsed_ns": time.perf_counter_ns() - started_ns,
    }
    report["summary"] = _aggregate(report)
    report["receipt_sha256"] = digest(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(report) + b"\n")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("_diag/general_intelligence_program.json"),
    )
    parser.add_argument(
        "--data-home",
        type=Path,
        default=Path("_diag/general-intelligence-program"),
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument("--roots", type=int, default=4)
    parser.add_argument("--decisions", type=int, default=4)
    args = parser.parse_args(argv)
    report = run_program(
        output=args.output,
        data_home=args.data_home,
        seeds=args.seeds,
        blocks=args.blocks,
        roots=args.roots,
        decisions=args.decisions,
    )
    print(
        json.dumps(
            {
                "receipt_sha256": report["receipt_sha256"],
                "schema": report["schema"],
                "summary": report["summary"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
