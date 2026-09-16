from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

import psutil


REQUEST_SCHEMA = "cassifi.cassipi-owner-request.v1"
MAX_REQUEST_BYTES = 1024 * 1024
RUNTIME_ID = "cassifi.cassipi-field-intelligence.v3"
CANDIDATE_COUNT = 64
INPUT_SHA256 = "3" * 64


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _launch(runtime: Path, data_home: Path, cwd: Path) -> subprocess.Popen[str]:
    cwd.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-B",
            str(runtime / "cassi_cassipi_worker.py"),
            "--data-home",
            str(data_home),
        ],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_descriptor(
    data_home: Path,
    process: subprocess.Popen[str],
    *,
    after_launch_id: str | None = None,
) -> tuple[Mapping[str, Any], float]:
    started = time.perf_counter()
    path = data_home / "runtime.json"
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                time.sleep(0.01)
                continue
            if isinstance(value, dict) and value.get("launch_id") != after_launch_id:
                return value, (time.perf_counter() - started) * 1000
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(
                f"owner exited before readiness: code={process.returncode}, "
                f"stdout={stdout!r}, stderr={stderr!r}"
            )
        time.sleep(0.01)
    raise TimeoutError("owner did not publish its descriptor")


def _raw_rpc(
    descriptor: Mapping[str, Any],
    body: bytes,
) -> tuple[int, Mapping[str, Any]]:
    request = Request(
        str(descriptor["endpoint"]),
        data=body,
        headers={
            "Authorization": f"Bearer {descriptor['bearer_secret']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        try:
            payload = json.loads(error.read())
        except ConnectionAbortedError:
            payload = {}
        return error.code, payload


def _envelope(operation: str, params: Mapping[str, Any], *, request_id: str | None = None) -> dict[str, Any]:
    return {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id or f"probe-{uuid.uuid4().hex}",
        "operation": operation,
        "params": dict(params),
    }


def _rpc(
    descriptor: Mapping[str, Any],
    operation: str,
    params: Mapping[str, Any],
) -> Mapping[str, Any]:
    status, response = _raw_rpc(descriptor, _canonical(_envelope(operation, params)))
    if status != 200 or response.get("ok") is not True:
        raise RuntimeError(f"{operation} failed: status={status}, response={response}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"{operation} returned no result object")
    return result


def _owner_status(descriptor: Mapping[str, Any]) -> Mapping[str, Any]:
    return _rpc(descriptor, "status", {})["owner"]


def _attach(descriptor: Mapping[str, Any], client_id: str, scope: Mapping[str, str]) -> str:
    _rpc(descriptor, "attach", {"client_id": client_id})
    result = _rpc(
        descriptor,
        "bind_scope",
        {
            "client_id": client_id,
            "scope": {
                "schema": "cassipi.authenticated-host-scope.v1",
                **scope,
            },
        },
    )
    return str(result["scope_token"])


def _attached(
    descriptor: Mapping[str, Any],
    operation: str,
    client_id: str,
    scope_token: str,
    request: Mapping[str, Any],
) -> Mapping[str, Any]:
    return _rpc(
        descriptor,
        operation,
        {
            "client_id": client_id,
            "scope_token": scope_token,
            "request": dict(request),
        },
    )
def _attached_response(
    descriptor: Mapping[str, Any],
    operation: str,
    client_id: str,
    scope_token: str,
    request: Mapping[str, Any],
) -> tuple[int, Mapping[str, Any]]:
    return _raw_rpc(
        descriptor,
        _canonical(
            _envelope(
                operation,
                {
                    "client_id": client_id,
                    "scope_token": scope_token,
                    "request": dict(request),
                },
            )
        ),
    )




def _source(scope: Mapping[str, str], native_id: str, content: bytes) -> dict[str, Any]:
    return {
        "source_id": f"probe:{native_id}",
        "content_base64": base64.b64encode(content).decode("ascii"),
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "mime_type": "application/octet-stream" if b"\x00" in content else "text/plain",
        "codec": "binary" if b"\x00" in content else "utf-8",
        **scope,
        "native_source_entry_id": native_id,
        "author_origin": "local-measurement-probe",
        "message_role": "assistant",
        "observed_timestamp": "2026-09-05T00:00:00Z",
        "claim_category": "assistant-claim",
        "fidelity": "exact-observed-bytes",
    }


def _observe_request(
    scope: Mapping[str, str],
    *,
    operation_id: str,
    producer_id: str,
    sequence: int,
    predecessor: str | None,
    parent_head: str,
    content: bytes,
    memory_scope: str = "task",
) -> dict[str, Any]:
    return {
        "schema": "cassipi.observe.v1",
        "operation_id": operation_id,
        "native_identity": operation_id,
        "producer_id": producer_id,
        "producer_sequence": sequence,
        "predecessor_event_id": predecessor,
        **scope,
        "parent_head_id": parent_head,
        "event_kind": "observation",
        "source": _source(scope, operation_id, content),
        "payload": {"memory_scope": memory_scope},
        "native_entry_id": operation_id,
    }


def _observe(
    descriptor: Mapping[str, Any],
    client_id: str,
    scope_token: str,
    request: Mapping[str, Any],
) -> Mapping[str, Any]:
    return _attached(descriptor, "observe", client_id, scope_token, request)


def _projection_scope(
    descriptor: Mapping[str, Any],
    scope: Mapping[str, str],
    *,
    task: str,
    provider_call_id: str,
    mandatory: list[str] | None = None,
    allowed_memory_scopes: list[str] | None = None,
    owner: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    owner_status = owner or _owner_status(descriptor)
    return {
        **scope,
        "task": task,
        "expected_head_id": owner_status["field_head_sha256"],
        "expected_journal_head_sha256": owner_status["journal_head_sha256"],
        "expected_revocation_epoch": owner_status["revocation_epoch"],
        "input_revision_sha256": INPUT_SHA256,
        "provider_call_id": provider_call_id,
        "model_id": "local-measurement-model",
        "tokenizer_id": "measurement-byte4-v1",
        "allowed_memory_scopes": allowed_memory_scopes or ["task"],
        "mandatory_revision_ids": mandatory or [],
        "excluded_revision_ids": [],
    }


def _token_counts(inventory: Mapping[str, Any]) -> dict[str, int]:
    return {
        representation["action_id"]: max(
            1,
            math.ceil(len(_canonical(representation["message"])) / 4),
        )
        for candidate in inventory["candidates"]
        for representation in candidate["representations"]
    }


def _project(
    descriptor: Mapping[str, Any],
    client_id: str,
    scope_token: str,
    projection_scope: Mapping[str, Any],
    inventory: Mapping[str, Any],
    token_counts: Mapping[str, int],
    context_window_tokens: int,
) -> Mapping[str, Any]:
    return _attached(
        descriptor,
        "project",
        client_id,
        scope_token,
        {
            "schema": "cassipi.projection.v1",
            "scope": dict(projection_scope),
            "inventory_sha256": inventory["inventory_sha256"],
            "budget": {
                "schema": "cassipi.projection-budget.v1",
                "context_window_tokens": context_window_tokens,
                "system_tokens": 20,
                "tool_schema_tokens": 30,
                "protected_tokens": 40,
                "image_tokens": 0,
                "current_request_tokens": 20,
                "reserved_output_tokens": 128,
                "host_overhead_tokens": 16,
            },
            "token_counts": dict(token_counts),
        },
    )


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _transport_boundary(descriptor: Mapping[str, Any]) -> Mapping[str, Any]:
    outcomes: dict[str, Any] = {}
    for label, size in (
        ("below", MAX_REQUEST_BYTES - 1),
        ("at", MAX_REQUEST_BYTES),
        ("above", MAX_REQUEST_BYTES + 1),
    ):
        envelope = _envelope("status", {"padding": ""}, request_id=f"boundary-{label}")
        empty = _canonical(envelope)
        padding = size - len(empty)
        if padding < 0:
            raise AssertionError("boundary request envelope exceeds target before padding")
        envelope["params"]["padding"] = "x" * padding
        body = _canonical(envelope)
        if len(body) != size:
            raise AssertionError(f"could not construct exact {size}-byte request")
        status, response = _raw_rpc(descriptor, body)
        code = response.get("error", {}).get("code")
        outcomes[label] = {"bytes": size, "http_status": status, "error_code": code}
    if outcomes["below"]["error_code"] != "INVALID_REQUEST":
        raise AssertionError(outcomes)
    if outcomes["at"]["error_code"] != "INVALID_REQUEST":
        raise AssertionError(outcomes)
    if outcomes["above"]["http_status"] != 413 or outcomes["above"]["error_code"] not in {
        None,
        "PAYLOAD_TOO_LARGE",
    }:
        raise AssertionError(outcomes)
    return outcomes


def _max_source_request(
    descriptor: Mapping[str, Any],
    client_id: str,
    scope_token: str,
    scope: Mapping[str, str],
    *,
    sequence: int,
    predecessor: str | None,
) -> tuple[Mapping[str, Any], Mapping[str, Any], int]:
    owner = _owner_status(descriptor)

    def wrapped(size: int) -> tuple[dict[str, Any], bytes]:
        content = (b"\xff\x00" * ((size + 1) // 2))[:size]
        request = _observe_request(
            scope,
            operation_id="observe-max-source",
            producer_id=client_id,
            sequence=sequence,
            predecessor=predecessor,
            parent_head=owner["field_head_sha256"],
            content=content,
        )
        envelope = _envelope(
            "observe",
            {"client_id": client_id, "scope_token": scope_token, "request": request},
            request_id="max-source-request",
        )
        return request, _canonical(envelope)

    low, high = 0, MAX_REQUEST_BYTES
    while low < high:
        middle = (low + high + 1) // 2
        if len(wrapped(middle)[1]) <= MAX_REQUEST_BYTES:
            low = middle
        else:
            high = middle - 1
    request, body = wrapped(low)
    status, response = _raw_rpc(descriptor, body)
    if status != 200 or response.get("ok") is not True:
        raise RuntimeError(f"maximum source request failed: {status} {response}")
    next_size = low + 1
    while len(wrapped(next_size)[1]) <= MAX_REQUEST_BYTES:
        next_size += 1
    too_large_status, too_large = _raw_rpc(descriptor, wrapped(next_size)[1])
    if too_large_status != 413 or too_large.get("error", {}).get("code") not in {
        None,
        "PAYLOAD_TOO_LARGE",
    }:
        raise AssertionError(too_large)
    return request, response["result"], len(body)


def _selection_identity(result: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        {
            "action_id": row["action_id"],
            "revision_id": row["revision_id"],
            "representation": row["representation"],
            "source_sha256": row["source"]["content_sha256"],
            "tokens": row["tokens"],
        }
        for row in result["selected"]
    ]


def _scope_markers(result: Mapping[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, sort_keys=True)


def _run(runtime: Path, receipt_path: Path) -> Mapping[str, Any]:
    manifest_path = runtime / "runtime-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"packaged runtime is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("runtime_id") != RUNTIME_ID:
        raise RuntimeError("installed runtime identity is incompatible")

    scopes = {
        "main": {
            "profile_id": "profile-measurement",
            "project_id": "project-a",
            "session_id": "session-siblings",
            "branch_id": "branch-main",
            "task_scope": "task-main",
        },
        "sibling": {
            "profile_id": "profile-measurement",
            "project_id": "project-a",
            "session_id": "session-siblings",
            "branch_id": "branch-sibling",
            "task_scope": "task-sibling",
        },
        "unrelated": {
            "profile_id": "profile-measurement",
            "project_id": "project-b",
            "session_id": "session-unrelated",
            "branch_id": "branch-unrelated",
            "task_scope": "task-unrelated",
        },
    }
    markers = {
        "main": "MAIN_SCOPE_PRIVATE_EVIDENCE",
        "sibling": "SIBLING_PRIVATE_EVIDENCE",
        "unrelated": "UNRELATED_PROJECT_PRIVATE_EVIDENCE",
    }
    shared_markers = {
        "project": "PROJECT_A_SHARED_EVIDENCE",
        "profile": "PROFILE_SHARED_EVIDENCE",
        "branch": "MAIN_BRANCH_SHARED_EVIDENCE",
    }

    with tempfile.TemporaryDirectory(prefix="cassipi-envelope-") as temporary:
        root = Path(temporary)
        data_home = root / "data-home"
        process = _launch(runtime, data_home, root / "outside-checkout")
        descriptor: Mapping[str, Any] = {}
        restarted: subprocess.Popen[str] | None = None
        restarted_descriptor: Mapping[str, Any] = {}
        tokens: dict[str, str] = {}
        first_request: Mapping[str, Any] | None = None
        first_revision: str | None = None
        try:
            descriptor, cold_start_ms = _wait_descriptor(data_home, process)
            cold_rss = psutil.Process(process.pid).memory_info().rss
            handshake = _rpc(
                descriptor,
                "handshake",
                {"expected": {"runtime_id": RUNTIME_ID}},
            )
            if handshake["compatibility"]["encoding_schema"] != "cassipi.direct-host-metadata-codec.v2":
                raise AssertionError("packaged field codec identity changed")
            for name, scope in scopes.items():
                tokens[name] = _attach(descriptor, f"measure-{name}", scope)

            initial_owner = _owner_status(descriptor)
            predecessor: str | None = None
            for sequence in range(CANDIDATE_COUNT):
                owner = _owner_status(descriptor)
                content = (
                    f"{markers['main']} candidate {sequence:03d}: bananas are yellow; "
                    f"value {sequence * 17}."
                ).encode()
                request = _observe_request(
                    scopes["main"],
                    operation_id=f"observe-main-{sequence:03d}",
                    producer_id="measure-main",
                    sequence=sequence,
                    predecessor=predecessor,
                    parent_head=owner["field_head_sha256"],
                    content=content,
                )
                observed = _observe(descriptor, "measure-main", tokens["main"], request)
                predecessor = str(observed["event_id"])
                if sequence == 0:
                    first_request = request
                    first_revision = str(observed["source"]["revision_id"])

            maximum_request, maximum_result, maximum_body_bytes = _max_source_request(
                descriptor,
                "measure-main",
                tokens["main"],
                scopes["main"],
                sequence=CANDIDATE_COUNT,
                predecessor=predecessor,
            )
            predecessor = str(maximum_result["event_id"])
            maximum_source_bytes = len(base64.b64decode(maximum_request["source"]["content_base64"]))
            for offset, (memory_scope, marker) in enumerate(shared_markers.items(), start=1):
                owner = _owner_status(descriptor)
                request = _observe_request(
                    scopes["main"],
                    operation_id=f"observe-shared-{memory_scope}",
                    producer_id="measure-main",
                    sequence=CANDIDATE_COUNT + offset,
                    predecessor=predecessor,
                    parent_head=owner["field_head_sha256"],
                    content=marker.encode(),
                    memory_scope=memory_scope,
                )
                observed = _observe(descriptor, "measure-main", tokens["main"], request)
                predecessor = str(observed["event_id"])
            if first_revision is None:
                raise AssertionError("first observed revision was not recorded")

            projection_scope = _projection_scope(
                descriptor,
                scopes["main"],
                task="Which measured candidate says bananas are yellow?",
                provider_call_id="measurement-main-before",
                mandatory=[first_revision],
                allowed_memory_scopes=["task", "branch", "project", "profile"],
            )
            cold_started = time.perf_counter()
            inventory = _attached(
                descriptor,
                "projection_inventory",
                "measure-main",
                tokens["main"],
                projection_scope,
            )
            token_counts = _token_counts(inventory)
            before_isolation = _project(
                descriptor,
                "measure-main",
                tokens["main"],
                projection_scope,
                inventory,
                token_counts,
                2048,
            )
            cold_projection_ms = (time.perf_counter() - cold_started) * 1000
            if before_isolation["external_model_calls"] != 0:
                raise AssertionError("projection called an external model")

            warm_samples: list[float] = []
            for _ in range(11):
                started = time.perf_counter()
                _project(
                    descriptor,
                    "measure-main",
                    tokens["main"],
                    projection_scope,
                    inventory,
                    token_counts,
                    2048,
                )
                warm_samples.append((time.perf_counter() - started) * 1000)

            budget_sweeps: dict[str, Any] = {}
            for budget in (512, 768, 2048):
                projected = _project(
                    descriptor,
                    "measure-main",
                    tokens["main"],
                    projection_scope,
                    inventory,
                    token_counts,
                    budget,
                )
                budget_sweeps[str(budget)] = {
                    "selected_count": len(projected["selected"]),
                    "used_tokens": projected["accounting"]["used_tokens"],
                    "remaining_tokens": projected["accounting"]["remaining_tokens"],
                    "selected_evidence_tokens": projected["accounting"]["selected_evidence_tokens"],
                    "abstained": projected["status"] == "abstained",
                }
            repeated_scope = _projection_scope(
                descriptor,
                scopes["main"],
                task="Which measured candidate says bananas are yellow?",
                provider_call_id="measurement-main-repeat",
                mandatory=[first_revision],
                allowed_memory_scopes=["task", "branch", "project", "profile"],
            )
            repeated_inventory = _attached(
                descriptor,
                "projection_inventory",
                "measure-main",
                tokens["main"],
                repeated_scope,
            )
            repeated_projection = _project(
                descriptor,
                "measure-main",
                tokens["main"],
                repeated_scope,
                repeated_inventory,
                _token_counts(repeated_inventory),
                2048,
            )
            if repeated_projection["messages"] != before_isolation["messages"]:
                raise AssertionError("same-scope query transition changed projected messages")
            if _selection_identity(repeated_projection) != _selection_identity(before_isolation):
                raise AssertionError("same-scope query transition changed selected source identities")


            scope_predecessors: dict[str, str | None] = {"sibling": None, "unrelated": None}
            for name in ("sibling", "unrelated"):
                owner = _owner_status(descriptor)
                request = _observe_request(
                    scopes[name],
                    operation_id=f"observe-{name}",
                    producer_id=f"measure-{name}",
                    sequence=0,
                    predecessor=scope_predecessors[name],
                    parent_head=owner["field_head_sha256"],
                    content=markers[name].encode(),
                )
                observed = _observe(descriptor, f"measure-{name}", tokens[name], request)
                scope_predecessors[name] = str(observed["event_id"])

            after_scope = _projection_scope(
                descriptor,
                scopes["main"],
                task="Which measured candidate says bananas are yellow?",
                provider_call_id="measurement-main-after",
                mandatory=[first_revision],
                allowed_memory_scopes=["task", "branch", "project", "profile"],
            )
            after_inventory = _attached(
                descriptor,
                "projection_inventory",
                "measure-main",
                tokens["main"],
                after_scope,
            )
            after_isolation = _project(
                descriptor,
                "measure-main",
                tokens["main"],
                after_scope,
                after_inventory,
                _token_counts(after_inventory),
                2048,
            )
            if after_isolation["messages"] != repeated_projection["messages"]:
                raise AssertionError("private scope changed main projected messages")
            if _selection_identity(after_isolation) != _selection_identity(repeated_projection):
                raise AssertionError("private scope changed main selected source identities")

            def concurrent_inventory_attempt(name: str) -> tuple[str, int, Mapping[str, Any]]:
                scoped = _projection_scope(
                    descriptor,
                    scopes[name],
                    task=f"Retrieve {markers[name]}",
                    provider_call_id=f"measurement-concurrent-conflict-{name}",
                    mandatory=[first_revision] if name == "main" else None,
                    allowed_memory_scopes=["task", "branch", "project", "profile"],
                    owner=concurrent_owner,
                )
                status, response = _attached_response(
                    descriptor,
                    "projection_inventory",
                    f"measure-{name}",
                    tokens[name],
                    scoped,
                )
                return name, status, response

            concurrent_owner = _owner_status(descriptor)
            concurrent_started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=3) as pool:
                conflict_rows = list(pool.map(concurrent_inventory_attempt, scopes))
            concurrent_ms = (time.perf_counter() - concurrent_started) * 1000
            committed = [row for row in conflict_rows if row[1] == 200 and row[2].get("ok") is True]
            stale = [
                row
                for row in conflict_rows
                if row[1] == 409
                and row[2].get("error", {}).get("code") == "STALE_FIELD_HEAD"
            ]
            if len(committed) != 1 or len(stale) != 2:
                raise AssertionError(f"unexpected optimistic concurrency outcome: {conflict_rows}")

            def sequential_projection(name: str) -> tuple[str, Mapping[str, Any]]:
                scoped = _projection_scope(
                    descriptor,
                    scopes[name],
                    task=f"Retrieve {markers[name]}",
                    provider_call_id=f"measurement-sequential-{name}",
                    mandatory=[first_revision] if name == "main" else None,
                    allowed_memory_scopes=["task", "branch", "project", "profile"],
                )
                scoped_inventory = _attached(
                    descriptor,
                    "projection_inventory",
                    f"measure-{name}",
                    tokens[name],
                    scoped,
                )
                result = _project(
                    descriptor,
                    f"measure-{name}",
                    tokens[name],
                    scoped,
                    scoped_inventory,
                    _token_counts(scoped_inventory),
                    2048,
                )
                return name, {
                    "candidate_count": len(scoped_inventory["candidates"]),
                    "inventory": scoped_inventory,
                    "result": result,
                }

            concurrent = dict(sequential_projection(name) for name in scopes)
            forbidden = {
                "main": [markers["sibling"], markers["unrelated"]],
                "sibling": [markers["main"], markers["unrelated"], shared_markers["branch"]],
                "unrelated": [
                    markers["main"],
                    markers["sibling"],
                    shared_markers["project"],
                    shared_markers["branch"],
                ],
            }
            for name, row in concurrent.items():
                encoded = _scope_markers({"inventory": row["inventory"], "result": row["result"]})
                for marker in forbidden[name]:
                    if marker in encoded:
                        raise AssertionError(f"{marker} leaked into {name}")

            transport = _transport_boundary(descriptor)
            before_lifecycle = _owner_status(descriptor)
            operation_id = "measurement-compact"
            lifecycle_request = {
                "schema": "cassipi.lifecycle-prepare.v1",
                "operation_id": operation_id,
                **scopes["unrelated"],
                "parent_head_id": before_lifecycle["field_head_sha256"],
                "checkpoint_id": before_lifecycle["checkpoint_id"],
                "checkpoint_hash": before_lifecycle["checkpoint_hash"],
                "revocation_epoch": before_lifecycle["revocation_epoch"],
                "operation_kind": "compact",
                "source_session_id": scopes["unrelated"]["session_id"],
                "source_leaf_id": "measurement-leaf",
                "covered_through_entry_id": "measurement-leaf",
                "source_root_digest": before_lifecycle["source_root_digest"],
                "target_head_id": before_lifecycle["field_head_sha256"],
            }
            lifecycle_started = time.perf_counter()
            prepared = _attached(
                descriptor,
                "lifecycle_prepare",
                "measure-unrelated",
                tokens["unrelated"],
                lifecycle_request,
            )
            _attached(
                descriptor,
                "lifecycle_commit",
                "measure-unrelated",
                tokens["unrelated"],
                {
                    "schema": "cassipi.lifecycle-commit.v1",
                    "operation_id": operation_id,
                    **scopes["unrelated"],
                    "committed_entry_id": "measurement-owner-marker",
                    "binding": prepared["binding"],
                },
            )
            compaction_lifecycle_ms = (time.perf_counter() - lifecycle_started) * 1000

            loaded_owner = _owner_status(descriptor)
            loaded_rss = psutil.Process(process.pid).memory_info().rss
            previous_launch_id = str(descriptor["launch_id"])
            process.kill()
            process.wait(timeout=10)

            restarted = _launch(runtime, data_home, root / "restart-outside")
            restarted_descriptor, restart_ms = _wait_descriptor(
                data_home,
                restarted,
                after_launch_id=previous_launch_id,
            )
            restart_handshake = _rpc(
                restarted_descriptor,
                "handshake",
                {"expected": {"runtime_id": RUNTIME_ID}},
            )
            replay_token = _attach(restarted_descriptor, "measure-replay", scopes["main"])
            before_replay = _owner_status(restarted_descriptor)
            if first_request is None:
                raise AssertionError("first request was not recorded")
            replayed = _observe(
                restarted_descriptor,
                "measure-replay",
                replay_token,
                first_request,
            )
            after_replay = _owner_status(restarted_descriptor)
            if replayed["receipt"]["replayed"] is not True:
                raise AssertionError("committed operation did not replay exactly once")
            if (
                before_replay["field_head_sha256"] != after_replay["field_head_sha256"]
                or before_replay["journal_head_sha256"] != after_replay["journal_head_sha256"]
            ):
                raise AssertionError("replay mutated recovered owner state")
            _rpc(restarted_descriptor, "detach", {"client_id": "measure-replay"})
            _rpc(restarted_descriptor, "shutdown", {"if_idle": True})
            restarted.wait(timeout=10)
            restarted = None

            receipt = {
                "schema": "cassipi.integration-envelope-receipt.v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "PASS",
                "runtime": {
                    "root": str(runtime.resolve()),
                    "runtime_id": manifest["runtime_id"],
                    "manifest_sha256": _sha256(manifest_path),
                    "closure_sha256": handshake["compatibility"]["closure_sha256"],
                    "corpus_schema": handshake["compatibility"]["corpus_schema"],
                    "encoding_schema": handshake["compatibility"]["encoding_schema"],
                },
                "measured_envelope": {
                    "candidate_count": len(inventory["candidates"]),
                    "configured_short_candidate_count": CANDIDATE_COUNT,
                    "maximum_archived_source_bytes_in_one_request": maximum_source_bytes,
                    "maximum_source_request_body_bytes": maximum_body_bytes,
                    "worker_request_limit_bytes": MAX_REQUEST_BYTES,
                    "simultaneous_clients": 3,
                    "memory_scopes_exercised": ["task", "branch", "project", "profile"],
                },
                "latency_ms": {
                    "cold_owner_start": round(cold_start_ms, 3),
                    "restart": round(restart_ms, 3),
                    "cold_inventory_plus_projection": round(cold_projection_ms, 3),
                    "warm_projection_p50": round(_percentile(warm_samples, 0.50), 3),
                    "warm_projection_p95": round(_percentile(warm_samples, 0.95), 3),
                    "compaction_prepare_plus_commit": round(compaction_lifecycle_ms, 3),
                    "optimistic_concurrency_inventory_wall": round(concurrent_ms, 3),
                },
                "memory_bytes": {
                    "cold_worker_rss": cold_rss,
                    "loaded_worker_rss": loaded_rss,
                    "rss_growth": loaded_rss - cold_rss,
                },
                "capacity": {
                    "limits": loaded_owner["capacity"]["limits"],
                    "initial_usage": initial_owner["capacity"]["usage"],
                    "loaded_usage": loaded_owner["capacity"]["usage"],
                },
                "budget_sweeps": budget_sweeps,
                "transport_boundary": transport,
                "scope_isolation": {
                    "status": "PASS",
                    "same_scope_query_preserved_selection_and_messages": True,
                    "main_selection_and_messages_stable_after_private_learning": True,
                    "returned_source_leakage": False,
                    "client_candidate_counts": {
                        name: row["candidate_count"] for name, row in concurrent.items()
                    },
                    "optimistic_concurrency": {
                        "committed": len(committed),
                        "stale_field_head_rejections": len(stale),
                    },
                },
                "recovery": {
                    "status": "PASS",
                    "hard_process_stop_used": True,
                    "committed_operation_replayed_without_mutation": True,
                    "startup_recovery": restart_handshake["recovery"],
                },
                "projection": {
                    "external_model_calls": before_isolation["external_model_calls"],
                    "field_selected": (
                        None
                        if not before_isolation["selected"]
                        else before_isolation["selected"][0]["action_id"]
                    ),
                    "selected_count": len(before_isolation["selected"]),
                },
            }
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_bytes(_canonical(receipt) + b"\n")
            return receipt
        finally:
            if restarted is not None and restarted.poll() is None:
                restarted.kill()
                restarted.wait(timeout=10)
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the installed CassiPi runtime envelope.")
    parser.add_argument(
        "--profile",
        default="cassipi-rehearsal",
        help="Official Oh My Pi profile containing the installed CassiPi package.",
    )
    parser.add_argument(
        "--runtime",
        type=Path,
        help="Explicit packaged runtime root; overrides --profile.",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "probes" / "receipts" / "integration-envelope.json",
    )
    args = parser.parse_args()
    runtime = args.runtime or (
        Path.home()
        / ".omp"
        / "profiles"
        / args.profile
        / "local-plugins"
        / "cassipi"
        / "fi-runtime"
    )
    receipt = _run(runtime.resolve(), args.receipt.resolve())
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "receipt": str(args.receipt.resolve()),
                "runtime_manifest_sha256": receipt["runtime"]["manifest_sha256"],
                "candidate_count": receipt["measured_envelope"]["candidate_count"],
                "maximum_archived_source_bytes": receipt["measured_envelope"]["maximum_archived_source_bytes_in_one_request"],
                "warm_projection_p95_ms": receipt["latency_ms"]["warm_projection_p95"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
