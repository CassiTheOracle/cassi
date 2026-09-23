"""Shared API driver for the programmable-swarm program benchmark.

This module is the benchmark's only transport boundary.  It speaks the existing
authenticated entity surface implemented by :mod:`cassi_field_brain_server`,
and it adds nothing to the server: no new route, no planner, no fault
injection, and no local solver.  Every call returns exactly one
:class:`BenchmarkSample`, so a caller can always distinguish a real server
success from an HTTP failure, a transport failure, and a protocol failure.

Guarantees
----------

* One attempt per call.  There is no retry, no reconnection, no revision
  refresh, and no cache: ``request_id`` and ``expected_owner_state_sha256``
  travel from the caller to the server verbatim, and a stale revision is
  reported as the server's conflict rather than silently corrected.
* No credential leaves the process except as the ``Authorization`` header,
  and nothing is logged.  ``repr`` omits the token, and
  :meth:`BenchmarkSample.measurement` reports status, sizes, and timing
  without the response payload.
* Timing is observation only.  ``elapsed_ns`` is a monotonic reading handed
  back to the caller; the client keeps no adaptive state.

Usage
-----

::

    client = ProgramBenchmarkClient("http://127.0.0.1:8090", token)
    health = client.health().require_ok()
    revision = owner_state_sha256(health)

    proposal = program_proposal(
        language="python",
        profile={"mode": "exec", "steps": 64},
        source_reference=inline_text_reference("obstacle", source),
        backend_policy=backend_policy("logical-cpu"),
    )
    admitted = client.admit_computation(
        program_id,
        request_id="bench-admit-1",
        computation_id="search",
        expected_owner_state_sha256=revision,
        proposal=proposal,
    )
    if not admitted.ok:
        record = admitted.measurement()          # credential-free bench record
        reason = admitted.error
"""

from __future__ import annotations

import hashlib
import http.client
import json
import socket
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urlencode, urlparse

MEASUREMENT_SCHEMA = "cassi.program-benchmark.client-sample.v1"
ERROR_TRANSPORT = "transport"
ERROR_PROTOCOL = "protocol"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
MINIMUM_API_TOKEN_BYTES = 32
DEFAULT_TIMEOUT_SECONDS = 30.0
#: The entity server refuses a request body larger than this (`_body`).
MAX_REQUEST_BODY_BYTES = 65_536

# These mirror the current entity surface so a benchmark can be constructed
# against it.  The server remains the authority: the client passes actions and
# capabilities through unchanged, including unsupported ones, so a rejected
# request is observable as a real HTTP failure.
PROGRAM_CAPABILITIES = ("effect-proposal", "model-request")
PROGRAM_BACKENDS = ("logical-cpu", "native-cpu", "vulkan")
PROGRAM_PROPOSAL_FIELDS = (
    "language",
    "profile",
    "source_reference",
    "input_references",
    "limits",
    "capability_requirements",
    "backend_policy",
    "payload",
)
PROGRAM_CONTROL_ACTIONS = ("pause", "resume", "cancel", "complete", "wake")
COMPUTATION_CONTROL_ACTIONS = (
    "step",
    "run",
    "pause",
    "resume",
    "cancel",
    "revoke",
    "resume-external",
    "resume-external-model",
    "begin-speculation",
    "optimize",
    "optimizer-status",
    "invalidate-optimization",
)
BRANCH_ACTIONS = ("begin", "commit", "rollback")
WORKSPACE_OPERATIONS = (
    "admit-record",
    "propose",
    "investigate",
    "settle-branch",
    "compare",
    "retain",
    "record-forecast",
    "record-outcome",
    "invalidate",
    "control-branch",
    "pause",
    "resume",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _segment(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("path identifier must be a nonempty string")
    return quote(value, safe="")


def _view_query(category: str, offset: int, limit: int) -> str:
    return urlencode({"category": category, "offset": offset, "limit": limit})


def _observed_at(value: str | None) -> str:
    """Every program route requires ``observed_at``.

    A caller-supplied timestamp is used verbatim (exact replay); when it is
    omitted the client stamps UTC now, the same value the server would
    generate for its own default.
    """

    if value is None:
        return datetime.now(UTC).isoformat(timespec="microseconds")
    if not isinstance(value, str) or not value:
        raise ValueError("observed_at must be an ISO-8601 timestamp string")
    return value


def _include(body: dict[str, Any], **values: Any) -> None:
    for key, value in values.items():
        if value is not None:
            body[key] = value


def _classify_failure(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return ERROR_TRANSPORT, "timeout"
    if isinstance(exc, http.client.RemoteDisconnected):
        return ERROR_TRANSPORT, "remote-disconnected"
    if isinstance(
        exc,
        (
            http.client.BadStatusLine,
            http.client.UnknownProtocol,
            http.client.LineTooLong,
        ),
    ):
        return ERROR_PROTOCOL, "malformed-response-head"
    if isinstance(exc, http.client.IncompleteRead):
        return ERROR_TRANSPORT, "incomplete-read"
    if isinstance(exc, OSError):
        return ERROR_TRANSPORT, type(exc).__name__
    return ERROR_PROTOCOL, type(exc).__name__


def _detail(exc: BaseException) -> str:
    text = str(exc).strip().replace("\n", " ")
    return f"{type(exc).__name__}: {text}"[:240] if text else type(exc).__name__


def _parse_event_stream(raw: bytes) -> tuple[Any, str | None, str | None, str | None]:
    """Parse the exact server frames ``id: n\\nevent: kind\\ndata: {json}\\n\\n``."""

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, ERROR_PROTOCOL, "invalid-event-stream", "event stream is not UTF-8"
    events: list[dict[str, Any]] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        cursor: Any = None
        kind = ""
        data: list[str] = []
        for line in block.split("\n"):
            if not line or line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
            if field == "id":
                cursor = int(value) if value.isdigit() else value
            elif field == "event":
                kind = value
            elif field == "data":
                data.append(value)
        if cursor is None and not kind and not data:
            continue
        if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
            return None, ERROR_PROTOCOL, "invalid-event-cursor", "event frame has no event id"
        if not data:
            return None, ERROR_PROTOCOL, "missing-event-data", "event frame carries no data"
        try:
            parsed = json.loads("\n".join(data))
        except json.JSONDecodeError:
            return None, ERROR_PROTOCOL, "invalid-event-data", "event frame data is not JSON"
        if not isinstance(parsed, dict):
            return None, ERROR_PROTOCOL, "invalid-event-data", "event frame data is not an object"
        events.append({"cursor": cursor, "event": kind, "data": parsed})
    return events, None, None, None


def _parse_response(
    content_type: str | None, raw: bytes
) -> tuple[Any, str | None, str | None, str | None]:
    if content_type is None:
        return None, ERROR_PROTOCOL, "missing-content-type", "response carries no content type"
    media = content_type.split(";", 1)[0].strip().lower()
    if media == "application/json":
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, ERROR_PROTOCOL, "invalid-json-body", "response body is not UTF-8 JSON"
        if not isinstance(value, (dict, list)):
            return (
                None,
                ERROR_PROTOCOL,
                "unexpected-json-shape",
                "response JSON is neither object nor array",
            )
        return value, None, None, None
    if media == "text/event-stream":
        return _parse_event_stream(raw)
    return (
        None,
        ERROR_PROTOCOL,
        "unexpected-content-type",
        f"unexpected response content type {media!r}",
    )


def _payload_kind(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def owner_state_sha256(payload: Any) -> str | None:
    """Read the programmable owner revision from a response payload.

    This is a pure read of one already-received payload: it neither fetches nor
    remembers a revision, so a benchmark always sends the exact revision it
    observed.
    """

    paths = (
        ("owner",),
        ("programmable_computation", "owner"),
        ("entity", "programmable_computation", "owner"),
        ("programmable_computations", "owner"),
        ("programmable_workspace", "owner"),
        ("result", "owner"),
    )
    for path in paths:
        node: Any = payload
        for key in path:
            if not isinstance(node, Mapping):
                node = None
                break
            node = node.get(key)
        if isinstance(node, Mapping):
            digest = node.get("state_sha256")
            if isinstance(digest, str) and digest:
                return digest
    return None


def backend_policy(
    preferred: str, *, allowed: Sequence[str] | None = None, required: bool = False
) -> dict[str, Any]:
    """Build the exact three-field backend policy the entity admits."""

    return {
        "preferred": preferred,
        "allowed": [preferred] if allowed is None else list(allowed),
        "required": bool(required),
    }


def inline_text_reference(name: str, content: str) -> dict[str, Any]:
    """Reference exact text (a program source) with its content digest."""

    return {
        "kind": "inline-text",
        "name": name,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content": content,
    }


def inline_json_reference(name: str, value: Any) -> dict[str, Any]:
    """Reference an exact JSON value with the digest of its canonical encoding."""

    return {
        "kind": "inline-json",
        "name": name,
        "sha256": hashlib.sha256(_canonical(value)).hexdigest(),
        "value": value,
    }


def research_artifact_reference(
    name: str, *, artifact_id: str, sha256: str, encoding: str = "utf-8"
) -> dict[str, Any]:
    """Reference a stored research artifact by its digest (the caller knows it)."""

    return {
        "kind": "research-artifact",
        "name": name,
        "sha256": sha256,
        "artifact_id": artifact_id,
        "encoding": encoding,
    }


def local_gguf_reference(name: str, *, path: str, sha256: str) -> dict[str, Any]:
    """Reference a local GGUF model backing by its lowercase digest."""

    return {"kind": "local-gguf", "name": name, "path": path, "sha256": sha256}


def program_proposal(
    *,
    language: str,
    profile: Mapping[str, Any],
    source_reference: Mapping[str, Any],
    backend_policy: Mapping[str, Any],
    input_references: Mapping[str, Any] | None = None,
    limits: Mapping[str, Any] | None = None,
    capability_requirements: Sequence[str] | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the exact eight-field proposal object the entity admits.

    Nothing is inferred: the caller names the language, profile, source,
    backend policy, and any capability requirement.  Omitted collections
    become empty ones, which is the server's own meaning for them.
    """

    return {
        "language": language,
        "profile": dict(profile),
        "source_reference": dict(source_reference),
        "input_references": dict(input_references or {}),
        "limits": dict(limits or {}),
        "capability_requirements": list(capability_requirements or ()),
        "backend_policy": dict(backend_policy),
        "payload": dict(payload or {}),
    }


class ProgramBenchmarkError(Exception):
    """Base class for a classified benchmark call failure."""

    def __init__(self, sample: "BenchmarkSample") -> None:
        super().__init__(sample.error)
        self.sample = sample


class ProgramBenchmarkTransportError(ProgramBenchmarkError):
    """The request never produced a usable HTTP response (connection, socket, timeout)."""


class ProgramBenchmarkProtocolError(ProgramBenchmarkError):
    """A response arrived but did not satisfy the entity API contract."""


class ProgramBenchmarkHTTPError(ProgramBenchmarkError):
    """The server answered with a non-2xx status; ``payload`` is its parsed body."""

    @property
    def status(self) -> int | None:
        return self.sample.status

    @property
    def payload(self) -> Any:
        return self.sample.payload


@dataclass(frozen=True)
class BenchmarkSample:
    """One exact request/response observation of the entity API.

    ``status`` is ``None`` only when no HTTP response was produced.
    ``payload`` holds the parsed response: a JSON object/array, or the parsed
    event frames of an SSE reply.  ``raw_body`` always holds the retained
    response bytes, so the measurement can be bound to a digest without the
    client storing anything.
    """

    method: str
    path: str
    status: int | None
    payload: Any | None
    raw_body: bytes
    content_type: str | None
    elapsed_ns: int
    request_body_bytes: int
    error_kind: str | None = None
    error_type: str | None = None
    detail: str | None = None
    request_id: str | None = None
    page_size: int | None = None

    @property
    def response_body_bytes(self) -> int:
        return len(self.raw_body)

    @property
    def ok(self) -> bool:
        """A 2xx status whose body satisfied the API contract."""

        return self.status is not None and 200 <= self.status < 300 and self.error_kind is None

    @property
    def http_error(self) -> bool:
        return self.status is not None and not 200 <= self.status < 300

    @property
    def transport_error(self) -> bool:
        return self.error_kind == ERROR_TRANSPORT

    @property
    def protocol_error(self) -> bool:
        return self.error_kind == ERROR_PROTOCOL

    @property
    def error(self) -> str:
        """One-line description of a failure, empty for a success."""

        if self.ok:
            return ""
        parts: list[str] = []
        if self.status is not None:
            parts.append(f"HTTP {self.status}")
        if self.error_kind is not None:
            parts.append(f"{self.error_kind} error")
        if self.error_type:
            parts.append(self.error_type)
        if self.detail:
            parts.append(self.detail)
        return f"{self.method} {self.path}: " + ("; ".join(parts) or "unclassified failure")

    @property
    def events(self) -> tuple[Mapping[str, Any], ...]:
        """Parsed event frames, bounded by ``page_size`` when one was requested."""

        if not isinstance(self.payload, list):
            return ()
        frames = self.payload if self.page_size is None else self.payload[: self.page_size]
        return tuple(frames)

    @property
    def truncated(self) -> bool:
        """True when the server returned more event frames than the requested page."""

        return (
            self.page_size is not None
            and isinstance(self.payload, list)
            and len(self.payload) > self.page_size
        )

    @property
    def next_cursor(self) -> int | None:
        """Cursor to resume event paging from, or ``None`` when the page is empty."""

        frames = self.events
        return None if not frames else int(frames[-1]["cursor"])

    @property
    def response_sha256(self) -> str:
        return hashlib.sha256(self.raw_body).hexdigest()

    def measurement(self) -> dict[str, Any]:
        """Credential-free, payload-free record of this call for a benchmark receipt."""

        return {
            "schema": MEASUREMENT_SCHEMA,
            "method": self.method,
            "path": self.path,
            "status": self.status,
            "ok": self.ok,
            "http_error": self.http_error,
            "transport_error": self.transport_error,
            "protocol_error": self.protocol_error,
            "error_kind": self.error_kind,
            "error_type": self.error_type,
            "detail": self.detail,
            "request_id": self.request_id,
            "elapsed_ns": self.elapsed_ns,
            "request_body_bytes": self.request_body_bytes,
            "response_body_bytes": self.response_body_bytes,
            "response_sha256": self.response_sha256,
            "content_type": self.content_type,
            "payload_kind": _payload_kind(self.payload),
            "event_count": len(self.payload) if isinstance(self.payload, list) else None,
            "returned_events": len(self.events),
            "next_cursor": self.next_cursor,
            "truncated": self.truncated,
        }

    def require_ok(self) -> Any:
        """Return the payload, or raise the failure this sample classified."""

        if self.ok:
            return self.payload
        if self.error_kind == ERROR_TRANSPORT:
            raise ProgramBenchmarkTransportError(self)
        if self.http_error:
            raise ProgramBenchmarkHTTPError(self)
        raise ProgramBenchmarkProtocolError(self)


class ProgramBenchmarkClient:
    """The benchmark's single transport boundary for the entity program API."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not isinstance(base_url, str):
            raise ValueError("base_url must be an entity URL string")
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
            raise ValueError(
                "entity API must be loopback HTTP (127.0.0.1, ::1, or localhost)"
            )
        if parsed.query or parsed.fragment:
            raise ValueError("base_url cannot carry a query or fragment")
        try:
            port = parsed.port or 80
        except ValueError as exc:
            raise ValueError("base_url port is invalid") from exc
        if not isinstance(api_token, str) or len(api_token) < MINIMUM_API_TOKEN_BYTES:
            raise ValueError(
                f"entity API token must contain at least {MINIMUM_API_TOKEN_BYTES} characters"
            )
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise ValueError("timeout must be a positive number of seconds")
        self._host = parsed.hostname
        self._port = port
        self._prefix = parsed.path.rstrip("/")
        self._api_token = api_token
        self._timeout = float(timeout)

    def __repr__(self) -> str:
        """Renders the endpoint; the bearer token is never included."""

        return (
            f"ProgramBenchmarkClient(base_url='http://{self._host}:{self._port}"
            f"{self._prefix}', timeout={self._timeout})"
        )

    def request(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> BenchmarkSample:
        """Perform exactly one authenticated request and classify its outcome."""

        if not isinstance(method, str) or method.upper() not in {"GET", "POST"}:
            raise ValueError("program benchmark client speaks GET and POST only")
        method = method.upper()
        if not isinstance(path, str) or not path.startswith("/") or "#" in path:
            raise ValueError("request path must be an absolute path without a fragment")
        payload: bytes | None = None
        if body is not None:
            if not isinstance(body, Mapping):
                raise ValueError("request body must be a mapping")
            try:
                payload = _canonical(body)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"request body is not JSON serializable: {exc}") from exc
        request_id = body.get("request_id") if isinstance(body, Mapping) else None
        headers = {
            "accept": "application/json, text/event-stream",
            "authorization": f"Bearer {self._api_token}",
        }
        if payload is not None:
            headers["content-type"] = "application/json"
        connection = http.client.HTTPConnection(
            self._host,
            self._port,
            timeout=self._timeout if timeout is None else timeout,
        )
        status: int | None = None
        content_type: str | None = None
        raw = b""
        failure: BaseException | None = None
        started = time.perf_counter_ns()
        try:
            connection.request(
                method, self._prefix + path, body=payload, headers=headers
            )
            response = connection.getresponse()
            status = int(response.status)
            content_type = response.getheader("content-type")
            raw = response.read()
        except Exception as exc:
            failure = exc
        finally:
            elapsed_ns = time.perf_counter_ns() - started
            connection.close()
        request_bytes = 0 if payload is None else len(payload)
        if failure is not None:
            if isinstance(failure, http.client.IncompleteRead):
                raw = bytes(failure.partial)
            kind, error_type = _classify_failure(failure)
            return BenchmarkSample(
                method=method,
                path=path,
                status=status,
                payload=None,
                raw_body=raw,
                content_type=content_type,
                elapsed_ns=elapsed_ns,
                request_body_bytes=request_bytes,
                error_kind=kind,
                error_type=error_type,
                detail=_detail(failure),
                request_id=request_id if isinstance(request_id, str) else None,
            )
        parsed, error_kind, error_type, detail = _parse_response(content_type, raw)
        return BenchmarkSample(
            method=method,
            path=path,
            status=status,
            payload=parsed,
            raw_body=raw,
            content_type=content_type,
            elapsed_ns=elapsed_ns,
            request_body_bytes=request_bytes,
            error_kind=error_kind,
            error_type=error_type,
            detail=detail,
            request_id=request_id if isinstance(request_id, str) else None,
        )

    def health(self) -> BenchmarkSample:
        """GET /v1/health: entity identity plus the programmable owner revision."""

        return self.request("GET", "/v1/health")

    def state(self) -> BenchmarkSample:
        """GET /v1/state: the full entity inspection."""

        return self.request("GET", "/v1/state")

    def research_status(self) -> BenchmarkSample:
        return self.request("GET", "/v1/research/status")

    def research_capabilities(self) -> BenchmarkSample:
        return self.request("GET", "/v1/research/capabilities")

    def list_programs(self) -> BenchmarkSample:
        return self.request("GET", "/v1/programs")

    def get_program(self, program_id: str) -> BenchmarkSample:
        """GET one research program with its computations and workspace."""

        return self.request("GET", f"/v1/programs/{_segment(program_id)}")

    def list_computations(self, program_id: str) -> BenchmarkSample:
        """GET the program's computations and the attached backends."""

        return self.request("GET", f"/v1/programs/{_segment(program_id)}/computations")

    def inspect_computation(
        self,
        program_id: str,
        computation_id: str,
        *,
        category: str = "objects",
        offset: int = 0,
        limit: int = 64,
    ) -> BenchmarkSample:
        """GET one paged computation view (objects, frames, methods, ...)."""

        query = _view_query(category, offset, limit)
        return self.request(
            "GET",
            f"/v1/programs/{_segment(program_id)}/computations/"
            f"{_segment(computation_id)}?{query}",
        )

    def inspect_workspace(
        self,
        program_id: str,
        *,
        category: str = "objects",
        offset: int = 0,
        limit: int = 64,
    ) -> BenchmarkSample:
        """GET one paged view of the program's shared research workspace."""

        query = _view_query(category, offset, limit)
        return self.request(
            "GET", f"/v1/programs/{_segment(program_id)}/workspace?{query}"
        )

    def program_events(
        self,
        program_id: str,
        *,
        after: int = 0,
        wait_seconds: float = 0.0,
        page_size: int | None = None,
        timeout: float | None = None,
    ) -> BenchmarkSample:
        """GET the revision-bound program events after a committed cursor.

        The server returns every event after ``after`` (optionally waiting for
        the first one).  ``page_size`` bounds only ``sample.events``; the full
        response stays in ``sample.payload`` and its digest in
        ``sample.response_sha256``, and ``sample.truncated`` reports the cut.

        The server clamps ``wait_seconds`` to 60 s and answers only after the
        wait, so pass ``timeout`` when the configured client timeout is
        smaller than the wait.
        """

        if page_size is not None and (
            isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 0
        ):
            raise ValueError("page_size must be a nonnegative integer")
        query: dict[str, Any] = {"after": after}
        if wait_seconds:
            query["wait"] = wait_seconds
        sample = self.request(
            "GET",
            f"/v1/programs/{_segment(program_id)}/events?{urlencode(query)}",
            timeout=timeout,
        )
        return sample if page_size is None else replace(sample, page_size=page_size)

    def create_program(
        self,
        *,
        request_id: str,
        program_id: str,
        project_id: str,
        title: str,
        mission: str,
        initial_question: str,
        observed_at: str | None = None,
        priority: float | None = None,
        cycle_limit: int | None = None,
        allowed_roots: Sequence[str] | None = None,
        allowed_tools: Sequence[str] | None = None,
        network_hosts: Sequence[str] | None = None,
        deliverable: Mapping[str, Any] | None = None,
    ) -> BenchmarkSample:
        """POST /v1/programs: create the program the benchmark will drive."""

        body: dict[str, Any] = {
            "request_id": request_id,
            "program_id": program_id,
            "project_id": project_id,
            "title": title,
            "mission": mission,
            "initial_question": initial_question,
            "observed_at": _observed_at(observed_at),
        }
        _include(
            body,
            priority=priority,
            cycle_limit=cycle_limit,
            allowed_roots=allowed_roots,
            allowed_tools=allowed_tools,
            network_hosts=network_hosts,
            deliverable=deliverable,
        )
        return self.request("POST", "/v1/programs", body)

    def admit_computation(
        self,
        program_id: str,
        *,
        request_id: str,
        computation_id: str,
        expected_owner_state_sha256: str,
        proposal: Mapping[str, Any],
        observed_at: str | None = None,
    ) -> BenchmarkSample:
        """POST a program computation proposal for owner admission."""

        return self.request(
            "POST",
            f"/v1/programs/{_segment(program_id)}/computations",
            {
                "request_id": request_id,
                "computation_id": computation_id,
                "expected_owner_state_sha256": expected_owner_state_sha256,
                "proposal": proposal,
                "observed_at": _observed_at(observed_at),
            },
        )

    def control_computation(
        self,
        program_id: str,
        computation_id: str,
        *,
        request_id: str,
        expected_owner_state_sha256: str,
        action: str,
        arguments: Mapping[str, Any] | None = None,
        observed_at: str | None = None,
    ) -> BenchmarkSample:
        """POST one computation control action against the expected owner revision."""

        return self.request(
            "POST",
            f"/v1/programs/{_segment(program_id)}/computations/"
            f"{_segment(computation_id)}/control",
            {
                "request_id": request_id,
                "expected_owner_state_sha256": expected_owner_state_sha256,
                "action": action,
                "arguments": {} if arguments is None else arguments,
                "observed_at": _observed_at(observed_at),
            },
        )

    def branch_computation(
        self,
        program_id: str,
        computation_id: str,
        *,
        request_id: str,
        expected_owner_state_sha256: str,
        action: str,
        branch_id: str,
        arguments: Mapping[str, Any] | None = None,
        observed_at: str | None = None,
    ) -> BenchmarkSample:
        """POST a begin/commit/rollback of one scoped working branch."""

        return self.request(
            "POST",
            f"/v1/programs/{_segment(program_id)}/computations/"
            f"{_segment(computation_id)}/branches",
            {
                "request_id": request_id,
                "expected_owner_state_sha256": expected_owner_state_sha256,
                "action": action,
                "branch_id": branch_id,
                "arguments": {} if arguments is None else arguments,
                "observed_at": _observed_at(observed_at),
            },
        )

    def command_workspace(
        self,
        program_id: str,
        *,
        request_id: str,
        expected_owner_state_sha256: str,
        command: Mapping[str, Any],
        observed_at: str | None = None,
    ) -> BenchmarkSample:
        """POST one structured research-workspace command.

        ``command`` carries its own ``operation`` and
        ``expected_field_revision``; both are passed through verbatim so a
        stale field revision surfaces as the server's conflict.
        """

        return self.request(
            "POST",
            f"/v1/programs/{_segment(program_id)}/workspace",
            {
                "request_id": request_id,
                "expected_owner_state_sha256": expected_owner_state_sha256,
                "command": command,
                "observed_at": _observed_at(observed_at),
            },
        )

    def control_program(
        self,
        program_id: str,
        *,
        request_id: str,
        action: str,
        observed_at: str | None = None,
        message: str | None = None,
        computation_id: str | None = None,
        computation_arguments: Mapping[str, Any] | None = None,
        expected_owner_state_sha256: str | None = None,
    ) -> BenchmarkSample:
        """POST a program control action, optionally targeting one computation."""

        body: dict[str, Any] = {
            "request_id": request_id,
            "action": action,
            "observed_at": _observed_at(observed_at),
        }
        _include(
            body,
            message=message,
            computation_id=computation_id,
            computation_arguments=computation_arguments,
            expected_owner_state_sha256=expected_owner_state_sha256,
        )
        return self.request(
            "POST", f"/v1/programs/{_segment(program_id)}/control", body
        )

    def guide_program(
        self,
        program_id: str,
        *,
        request_id: str,
        content: str,
        observed_at: str | None = None,
        workspace_command: Mapping[str, Any] | None = None,
        expected_owner_state_sha256: str | None = None,
    ) -> BenchmarkSample:
        """POST guidance, optionally realized as one structured workspace command."""

        body: dict[str, Any] = {
            "request_id": request_id,
            "content": content,
            "observed_at": _observed_at(observed_at),
        }
        _include(
            body,
            workspace_command=workspace_command,
            expected_owner_state_sha256=expected_owner_state_sha256,
        )
        return self.request(
            "POST", f"/v1/programs/{_segment(program_id)}/guidance", body
        )


__all__ = [
    "BRANCH_ACTIONS",
    "BenchmarkSample",
    "COMPUTATION_CONTROL_ACTIONS",
    "DEFAULT_TIMEOUT_SECONDS",
    "ERROR_PROTOCOL",
    "ERROR_TRANSPORT",
    "LOOPBACK_HOSTS",
    "MAX_REQUEST_BODY_BYTES",
    "MEASUREMENT_SCHEMA",
    "MINIMUM_API_TOKEN_BYTES",
    "PROGRAM_BACKENDS",
    "PROGRAM_CAPABILITIES",
    "PROGRAM_CONTROL_ACTIONS",
    "PROGRAM_PROPOSAL_FIELDS",
    "ProgramBenchmarkClient",
    "ProgramBenchmarkError",
    "ProgramBenchmarkHTTPError",
    "ProgramBenchmarkProtocolError",
    "ProgramBenchmarkTransportError",
    "WORKSPACE_OPERATIONS",
    "backend_policy",
    "inline_json_reference",
    "inline_text_reference",
    "local_gguf_reference",
    "owner_state_sha256",
    "program_proposal",
    "research_artifact_reference",
]
