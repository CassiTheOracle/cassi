"""Loopback HTTP/SSE surface for the explicit Cassi field–brain entity profile."""

from __future__ import annotations

import argparse
import hmac
from contextlib import ExitStack
import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlparse
from cassi_autonomous_researcher import (
    CapabilityDenied,
    ProgramConflict,
    ProgramNotFound,
    ResearchBrainUnavailable,
    ResponsibilityAdmissionError,
)

from cassi_field_brain_entity import (
    BrainUnavailable,
    CapabilityApprovalRequired,
    FieldBrainEntity,
    ProgramBackendUnavailable,
    ProgramCapabilityDenied,
    ProgramComputationConflict,
    ProgramComputationNotFound,
    SurfaceAuthorizationDenied,
    SurfaceUnavailable,
    SurfaceWait,
    TurnConflict,
    TurnNotFound,
    open_local_entity,
)
from surface.records import (
    SurfaceAuthorizationError,
    SurfaceCapabilityError,
    SurfaceConflictError,
    SurfaceValidationError,
)
from surface.linux_audio import WslPulseAudioBackend
from surface.linux_session import LinuxSessionSupervisor
from surface.rfb import LinuxXvncBackend
from surface.trading_paper import TradingPaperSurfaceBackend


class SurfaceOriginDenied(PermissionError):
    """A browser-originated Surface request did not match the authenticated origin."""



class EntityHTTPServer(ThreadingHTTPServer):
    """HTTP server whose one entity serializes every adaptive mutation."""

    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        entity: FieldBrainEntity,
        *,
        api_token: str,
    ) -> None:
        if not isinstance(api_token, str) or len(api_token) < 32:
            raise ValueError("entity API token must contain at least 32 characters")
        super().__init__(address, EntityRequestHandler)
        self.entity = entity
        self.api_token = api_token

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        if self.entity.config.research_resident_enabled:
            self.entity.researcher.start()
        try:
            super().serve_forever(poll_interval=poll_interval)
        finally:
            self.entity.researcher.stop()


class EntityRequestHandler(BaseHTTPRequestHandler):
    server: EntityHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _json(self, status: HTTPStatus, value: Mapping[str, Any]) -> None:
        body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _raw(
        self,
        status: HTTPStatus,
        body: bytes,
        *,
        content_type: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.send_header("x-content-type-options", "nosniff")
        self.send_header("cross-origin-resource-policy", "same-origin")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
    def _workspace_asset(self, path: str) -> bool:
        assets = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/workspace": ("index.html", "text/html; charset=utf-8"),
            "/workspace/": ("index.html", "text/html; charset=utf-8"),
            "/workspace/index.html": ("index.html", "text/html; charset=utf-8"),
            "/workspace/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/workspace/styles.css": ("styles.css", "text/css; charset=utf-8"),
        }
        asset = assets.get(path)
        if asset is None:
            return False
        filename, content_type = asset
        try:
            body = (
                Path(__file__).resolve().with_name("research_workspace")
                / filename
            ).read_bytes()
        except OSError:
            self._json(
                HTTPStatus.NOT_FOUND,
                {"error": "research workspace asset is unavailable"},
            )
            return True
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.send_header(
            "content-security-policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self' blob:; connect-src 'self'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'",
        )
        self.send_header("referrer-policy", "no-referrer")
        self.send_header("x-content-type-options", "nosniff")
        self.send_header("x-frame-options", "DENY")
        self.send_header("cross-origin-resource-policy", "same-origin")
        self.end_headers()
        self.wfile.write(body)
        return True

    def _require_authorization(self) -> None:
        supplied = self.headers.get("authorization")
        expected = f"Bearer {self.server.api_token}"
        if supplied is None or not hmac.compare_digest(supplied, expected):
            raise PermissionError("a valid bearer token is required")

    def _require_surface_origin(self) -> None:
        origin = self.headers.get("origin")
        if origin is None:
            return
        parsed = urlparse(origin)
        host = self.headers.get("host", "")
        if (
            parsed.scheme != "http"
            or not parsed.netloc
            or parsed.netloc.casefold() != host.casefold()
            or parsed.path
            or parsed.params
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise SurfaceOriginDenied("Surface requests must use the exact same-origin host")

    def _body(
        self,
        *,
        max_bytes: int = 65_536,
        reject_duplicate_keys: bool = False,
    ) -> Mapping[str, Any]:
        raw_length = self.headers.get("content-length")
        if raw_length is None:
            raise ValueError("content-length is required")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("content-length must be an integer") from exc
        if length < 0 or length > max_bytes:
            raise ValueError(f"request body exceeds {max_bytes} bytes")

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("request JSON must not contain duplicate object keys")
                result[key] = value
            return result

        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("request body was truncated")
            decoded = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=unique_object if reject_duplicate_keys else None,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("request body must be UTF-8 JSON") from exc
        if not isinstance(decoded, dict):
            raise ValueError("request body must be a JSON object")
        return decoded

    @staticmethod
    def _required(body: Mapping[str, Any], names: set[str]) -> None:
        unknown = set(body) - names
        missing = names - set(body)
        if missing or unknown:
            raise ValueError(
                f"expected fields {sorted(names)}, missing {sorted(missing)}, unknown {sorted(unknown)}"
            )

    @staticmethod
    def _allowed(body: Mapping[str, Any], required: set[str], optional: set[str]) -> None:
        unknown = set(body) - required - optional
        missing = required - set(body)
        if missing or unknown:
            raise ValueError(
                f"required fields {sorted(required)}, optional fields {sorted(optional)}, "
                f"missing {sorted(missing)}, unknown {sorted(unknown)}"
            )

    def _events(self, cursor: int) -> None:
        events = self.server.entity.journal.events_after(cursor)
        payload = b"".join(
            b"id: " + str(event["cursor"]).encode("ascii") + b"\n"
            + b"event: " + str(event["kind"]).encode("utf-8") + b"\n"
            + b"data: "
            + json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n\n"
            for event in events
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "text/event-stream; charset=utf-8")
        self.send_header("content-length", str(len(payload)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _research_events(self, program_id: str, cursor: int, *, wait_seconds: float = 0.0) -> None:
        if wait_seconds > 0:
            events = self.server.entity.researcher.wait_events(
                cursor,
                program_id=program_id,
                timeout=wait_seconds,
            )
        else:
            events = self.server.entity.researcher.events_after(cursor, program_id=program_id)
        payload = b"".join(
            b"id: " + str(event["sequence"]).encode("ascii") + b"\n"
            + b"event: " + str(event["kind"]).encode("utf-8") + b"\n"
            + b"data: "
            + json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n\n"
            for event in events
        )
        self._raw(HTTPStatus.OK, payload, content_type="text/event-stream; charset=utf-8")
    def _turn_events(self, turn_id: str, cursor: int, *, wait_seconds: float = 0.0) -> None:
        events = self.server.entity.turn_events(
            turn_id,
            after=cursor,
            wait_seconds=wait_seconds,
        )
        payload = b"".join(
            b"id: " + str(event["cursor"]).encode("ascii") + b"\n"
            + b"event: " + str(event["kind"]).encode("utf-8") + b"\n"
            + b"data: "
            + json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n\n"
            for event in events
        )
        self._raw(HTTPStatus.OK, payload, content_type="text/event-stream; charset=utf-8")

    @staticmethod
    def _program_view_query(parsed: Any) -> tuple[str, int, int]:
        values = parse_qs(parsed.query)
        unknown = set(values) - {"category", "offset", "limit"}
        if unknown:
            raise ValueError(
                f"unknown program view query fields: {sorted(unknown)}"
            )
        category = values.get("category", ["objects"])
        offset = values.get("offset", ["0"])
        limit = values.get("limit", ["64"])
        if len(category) != 1 or len(offset) != 1 or len(limit) != 1:
            raise ValueError(
                "category, offset and limit must occur at most once"
            )
        return category[0], int(offset[0]), int(limit[0])


    def _handle_surface_get(self, parsed: Any, route: list[str]) -> bool:
        if route[:2] != ["v1", "surface"]:
            return False
        self._require_surface_origin()
        if parsed.path == "/v1/surface":
            values = parse_qs(parsed.query, strict_parsing=True)
            if set(values) != {"program_id"} or len(values["program_id"]) != 1:
                raise ValueError("surface description requires one program_id")
            self._json(
                HTTPStatus.OK,
                self.server.entity.describe_surface(values["program_id"][0]),
            )
            return True
        if parsed.path == "/v1/surface/sources":
            values = parse_qs(parsed.query, strict_parsing=True)
            if set(values) != {"backend_id", "program_id"} or any(
                len(items) != 1 for items in values.values()
            ):
                raise ValueError("sources require one backend_id and one program_id")
            self._json(
                HTTPStatus.OK,
                {
                    "sources": self.server.entity.surface_sources(
                        values["backend_id"][0],
                        program_id=values["program_id"][0],
                    )
                },
            )
            return True
        if len(route) == 4 and route[:2] == ["v1", "surface"] and route[2] == "operations":
            values = parse_qs(parsed.query, strict_parsing=True)
            if set(values) != {"program_id"} or len(values["program_id"]) != 1:
                raise ValueError("operation inspection requires one program_id")
            self._json(
                HTTPStatus.OK,
                self.server.entity.inspect_surface_operation(
                    unquote(route[3]), program_id=values["program_id"][0]
                ),
            )
            return True
        if len(route) == 4 and route[:3] == ["v1", "surface", "guidance"]:
            values = parse_qs(parsed.query, strict_parsing=True)
            if set(values) != {"program_id"} or len(values["program_id"]) != 1:
                raise ValueError("guidance inspection requires one program_id")
            self._json(
                HTTPStatus.OK,
                self.server.entity.inspect_surface_guidance(
                    unquote(route[3]), program_id=values["program_id"][0]
                ),
            )
            return True
        if len(route) >= 4 and route[:3] == ["v1", "surface", "bindings"]:
            binding_id = unquote(route[3])
            if len(route) == 4:
                values = parse_qs(parsed.query, strict_parsing=True)
                if set(values) != {"program_id"} or len(values["program_id"]) != 1:
                    raise ValueError("binding inspection requires one program_id")
                self._json(
                    HTTPStatus.OK,
                    self.server.entity.inspect_surface_binding(
                        binding_id, program_id=values["program_id"][0]
                    ),
                )
                return True
            if len(route) == 5 and route[4] == "capture":
                values = parse_qs(parsed.query, strict_parsing=True)
                if not {"program_id"} <= set(values) or set(values) - {
                    "program_id", "grant_id"
                }:
                    raise ValueError("capture requires program_id and optional grant_id")
                if any(len(items) != 1 for items in values.values()):
                    raise ValueError("capture query fields must occur exactly once")
                capture_context = {"program_id": values["program_id"][0]}
                if "grant_id" in values:
                    capture_context["grant_id"] = values["grant_id"][0]
                self._json(
                    HTTPStatus.OK,
                    self.server.entity.capture_surface(binding_id, **capture_context),
                )
                return True
            if (
                len(route) == 7
                and route[4] == "publications"
                and route[6] == "pixels"
            ):
                values = parse_qs(parsed.query, strict_parsing=True)
                if set(values) != {"program_id", "offset", "length"}:
                    raise ValueError(
                        "pixel pages require exactly program_id, offset and length"
                    )
                if any(len(values[key]) != 1 for key in values):
                    raise ValueError("pixel page query fields must occur exactly once")
                generation = int(route[5])
                offset = int(values["offset"][0])
                requested_length = int(values["length"][0])
                program_id = values["program_id"][0]
                metadata = self.server.entity.inspect_surface_publication(
                    binding_id, generation, program_id=program_id
                )
                total_length = metadata.get("byte_length")
                source_epoch = metadata.get("source_epoch")
                geometry_revision = metadata.get("geometry_revision")
                pixel_format = metadata.get("pixel_format")
                if (
                    isinstance(total_length, bool)
                    or not isinstance(total_length, int)
                    or total_length <= 0
                    or isinstance(source_epoch, bool)
                    or not isinstance(source_epoch, int)
                    or isinstance(geometry_revision, bool)
                    or not isinstance(geometry_revision, int)
                    or pixel_format not in {"BGRA8", "RGBA8", "RGB8", "GRAY8"}
                ):
                    raise RuntimeError("Surface publication returned invalid page metadata")
                if (
                    offset < 0
                    or offset >= total_length
                    or not 1 <= requested_length <= (4 << 20)
                ):
                    raise ValueError("pixel page range is outside the published buffer")
                page_length = min(requested_length, total_length - offset)
                page = self.server.entity.read_surface_page(
                    binding_id,
                    generation,
                    offset,
                    page_length,
                    program_id=program_id,
                )
                if len(page) != page_length:
                    raise RuntimeError("Surface broker returned an incomplete pixel page")
                self._raw(
                    HTTPStatus.OK,
                    page,
                    content_type="application/octet-stream",
                    headers={
                        "x-surface-generation": str(generation),
                        "x-surface-offset": str(offset),
                        "x-surface-page-length": str(len(page)),
                        "x-surface-total-byte-length": str(total_length),
                        "x-surface-pixel-format": pixel_format,
                        "x-surface-source-epoch": str(source_epoch),
                        "x-surface-geometry-revision": str(geometry_revision),
                    },
                )
                return True
            if (
                len(route) == 7
                and route[4] == "publications"
                and route[6] == "audio"
            ):
                values = parse_qs(parsed.query, strict_parsing=True)
                if set(values) != {
                    "program_id", "grant_id", "offset", "length"
                }:
                    raise ValueError(
                        "audio pages require exactly program_id, grant_id, offset and length"
                    )
                if any(len(items) != 1 for items in values.values()):
                    raise ValueError("audio page query fields must occur exactly once")
                generation = int(route[5])
                program_id = values["program_id"][0]
                grant_id = values["grant_id"][0]
                offset = int(values["offset"][0])
                requested_length = int(values["length"][0])
                metadata = self.server.entity.inspect_surface_publication(
                    binding_id,
                    generation,
                    program_id=program_id,
                    grant_id=grant_id,
                )
                audio = metadata.get("audio")
                total_length = audio.get("byte_length") if isinstance(audio, Mapping) else None
                audio_format = audio.get("audio_format") if isinstance(audio, Mapping) else None
                if (
                    isinstance(total_length, bool)
                    or not isinstance(total_length, int)
                    or total_length <= 0
                    or not isinstance(audio_format, str)
                    or not audio_format
                    or len(audio_format.encode("utf-8")) > 64
                ):
                    raise RuntimeError("Surface publication returned invalid audio metadata")
                if (
                    offset < 0
                    or offset >= total_length
                    or not 1 <= requested_length <= (4 << 20)
                ):
                    raise ValueError("audio page range is outside the published buffer")
                page_length = min(requested_length, total_length - offset)
                page = self.server.entity.read_surface_audio_page(
                    binding_id,
                    generation,
                    offset,
                    page_length,
                    program_id=program_id,
                    grant_id=grant_id,
                )
                if len(page) != page_length:
                    raise RuntimeError("Surface broker returned an incomplete audio page")
                self._raw(
                    HTTPStatus.OK,
                    page,
                    content_type="application/octet-stream",
                    headers={
                        "x-surface-generation": str(generation),
                        "x-surface-offset": str(offset),
                        "x-surface-page-length": str(len(page)),
                        "x-surface-total-byte-length": str(total_length),
                        "x-surface-audio-format": audio_format,
                    },
                )
                return True
        return False

    def _handle_surface_post(
        self,
        parsed: Any,
        route: list[str],
        body: Mapping[str, Any],
    ) -> bool:
        if route[:2] != ["v1", "surface"]:
            return False
        query_route = (
            len(route) == 5
            and tuple(route[:3]) in {
                ("v1", "surface", "guidance"),
                ("v1", "surface", "operations"),
            }
            and route[4] == "reconcile"
            or len(route) == 5
            and route[:3] == ["v1", "surface", "bindings"]
            and route[4] in {"release", "pause", "resume", "revoke", "release-human"}
        )
        if parsed.query and not query_route:
            raise ValueError("this Surface mutation route does not accept query fields")
        if parsed.path == "/v1/surface/bind":
            self._allowed(body, {"program_id", "backend_id", "source_id"}, set())
            self._json(
                HTTPStatus.CREATED,
                self.server.entity.bind_surface(
                    body["backend_id"],
                    body["source_id"],
                    program_id=body["program_id"],
                ),
            )
            return True
        if parsed.path == "/v1/surface/guidance":
            self._allowed(
                body,
                {
                    "request_id",
                    "program_id",
                    "binding_id",
                    "publication_generation",
                    "source_epoch",
                    "geometry_revision",
                    "annotation",
                    "instruction",
                },
                set(),
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.guide_surface_program(**body),
            )
            return True
        if (
            len(route) == 5
            and route[:3] == ["v1", "surface", "guidance"]
            and route[4] == "reconcile"
        ):
            values = parse_qs(parsed.query, strict_parsing=True)
            if set(values) != {"program_id"} or len(values["program_id"]) != 1:
                raise ValueError("guidance reconciliation requires one program_id")
            self._allowed(body, set(), set())
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.reconcile_surface_guidance(
                    unquote(route[3]), program_id=values["program_id"][0]
                ),
            )
            return True
        if (
            len(route) == 5
            and route[:3] == ["v1", "surface", "mission"]
            and route[4] == "grant"
        ):
            self._allowed(
                body,
                {"binding_id", "operations", "expires_ns", "scope"},
                set(),
            )
            self._json(
                HTTPStatus.CREATED,
                self.server.entity.grant_surface(
                    program_id=unquote(route[3]),
                    **body,
                ),
            )
            return True
        if parsed.path == "/v1/surface/procedures/advance":
            self._allowed(
                body,
                {
                    "operation_id",
                    "program_id",
                    "procedure_ref",
                    "run_id",
                    "binding_id",
                    "grant_id",
                    "context",
                },
                {
                    "bindings",
                    "cancel_requested",
                    "checkpoint_ref",
                    "deadline_ns",
                    "effect_outcome",
                    "goal_revision",
                    "maximum_work",
                    "observation_ref",
                    "resource_reservation",
                    "support_roots",
                },
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.advance_surface_procedure(body),
            )
            return True
        if parsed.path == "/v1/surface/intents":
            self._allowed(
                body,
                {
                    "program_id",
                    "operation_id",
                    "binding_id",
                    "grant_id",
                    "operation",
                    "payload",
                    "expected_source_epoch",
                    "expected_geometry_revision",
                },
                {
                    "expected_focus_epoch",
                    "expected_input_domain_epoch",
                    "sequence",
                    "created_ns",
                    "deadline_ns",
                    "max_duration_ns",
                    "semantic_target",
                    "dependency_versions",
                    "expected_effect",
                    "resource_reservation",
                    "stop_conditions",
                    "goal_revision",
                },
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.submit_surface_intent(body),
            )
            return True
        if (
            len(route) == 5
            and route[:3] == ["v1", "surface", "operations"]
            and route[4] == "reconcile"
        ):
            values = parse_qs(parsed.query, strict_parsing=True)
            if set(values) != {"program_id"} or len(values["program_id"]) != 1:
                raise ValueError("operation reconciliation requires one program_id")
            self._allowed(body, {"outcome"}, set())
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.reconcile_surface_operation(
                    unquote(route[3]),
                    body["outcome"],
                    program_id=values["program_id"][0],
                ),
            )
            return True
        if len(route) == 5 and route[:3] == ["v1", "surface", "bindings"]:
            binding_id = unquote(route[3])
            action = route[4]
            if action in {"release", "pause", "resume", "revoke", "release-human"}:
                values = parse_qs(parsed.query, strict_parsing=True)
                if set(values) != {"program_id"} or len(values["program_id"]) != 1:
                    raise ValueError(f"{action} requires one program_id")
                self._allowed(body, set(), set())
                method = {
                    "release": self.server.entity.release_surface,
                    "pause": self.server.entity.pause_surface,
                    "resume": self.server.entity.resume_surface,
                    "revoke": self.server.entity.revoke_surface,
                    "release-human": self.server.entity.release_surface_human,
                }[action]
                self._json(
                    HTTPStatus.OK,
                    method(binding_id, program_id=values["program_id"][0]),
                )
                return True
            if action == "take-control":
                self._allowed(
                    body, {"program_id", "operations", "expires_ns"}, set()
                )
                self._json(
                    HTTPStatus.CREATED,
                    self.server.entity.take_surface_control(
                        binding_id,
                        program_id=body["program_id"],
                        operations=body["operations"],
                        expires_ns=body["expires_ns"],
                    ),
                )
                return True
        return False
    def _handle_program_get(self, parsed: Any, route: list[str]) -> bool:
        if parsed.path == "/v1/programs":
            self._json(
                HTTPStatus.OK,
                {
                    "schema": "cassi.entity.research-program-list.v1",
                    "programs": self.server.entity.research_programs(),
                },
            )
            return True
        if len(route) == 3 and route[:2] == ["v1", "programs"]:
            self._json(
                HTTPStatus.OK,
                self.server.entity.research_program(unquote(route[2])),
            )
            return True
        if (
            len(route) == 4
            and route[:2] == ["v1", "programs"]
            and route[3] == "computations"
        ):
            self._json(
                HTTPStatus.OK,
                self.server.entity.program_computations(unquote(route[2])),
            )
            return True
        if (
            len(route) == 5
            and route[:2] == ["v1", "programs"]
            and route[3] == "computations"
        ):
            category, offset, limit = self._program_view_query(parsed)
            self._json(
                HTTPStatus.OK,
                self.server.entity.inspect_program_computation(
                    program_id=unquote(route[2]),
                    computation_id=unquote(route[4]),
                    category=category,
                    offset=offset,
                    limit=limit,
                ),
            )
            return True
        if (
            len(route) == 4
            and route[:2] == ["v1", "programs"]
            and route[3] == "workspace"
        ):
            category, offset, limit = self._program_view_query(parsed)
            self._json(
                HTTPStatus.OK,
                self.server.entity.inspect_program_computation(
                    program_id=unquote(route[2]),
                    computation_id="workspace",
                    category=category,
                    offset=offset,
                    limit=limit,
                ),
            )
            return True
        if (
            len(route) == 4
            and route[:2] == ["v1", "programs"]
            and route[3] == "workbench"
        ):
            values = parse_qs(parsed.query)
            unknown = set(values) - {"question", "maximum"}
            if unknown:
                raise ValueError(
                    f"unknown workbench query fields: {sorted(unknown)}"
                )
            maximum = values.get("maximum", ["64"])
            if len(maximum) != 1:
                raise ValueError("maximum must occur at most once")
            question = values.get("question", [])
            if len(question) > 1:
                raise ValueError("question must occur at most once")
            if question and question[0]:
                self._json(
                    HTTPStatus.OK,
                    self.server.entity.research_workbench_context(
                        unquote(route[2]),
                        question[0],
                        maximum=int(maximum[0]),
                    )
                    or {
                        "schema": "cassi.research-workbench-context.v1",
                        "program_id": unquote(route[2]),
                        "unavailable": "this entity has no field workbench",
                    },
                )
                return True
            self._json(
                HTTPStatus.OK,
                self.server.entity.research_workbench(unquote(route[2]))
                or {
                    "schema": "cassi.research-workbench-view.v1",
                    "program_id": unquote(route[2]),
                    "unavailable": "this entity has no field workbench",
                },
            )
            return True
        if (
            len(route) in {4, 5}
            and route[:2] == ["v1", "programs"]
            and route[3] == "events"
            and (len(route) == 4 or route[4] == "stream")
        ):
            values = parse_qs(parsed.query)
            unknown = set(values) - {"after", "wait"}
            if unknown:
                raise ValueError(
                    f"unknown research event query fields: {sorted(unknown)}"
                )
            after = values.get("after", ["0"])
            wait = values.get("wait", ["0"])
            if len(after) != 1 or len(wait) != 1:
                raise ValueError("after and wait must occur at most once")
            wait_seconds = max(0.0, min(float(wait[0]), 60.0))
            self._research_events(
                unquote(route[2]),
                int(after[0]),
                wait_seconds=wait_seconds,
            )
            return True
        return False

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            if self._workspace_asset(parsed.path):
                return
            self._require_authorization()
            if parsed.path == "/v1/health":
                self._json(HTTPStatus.OK, {"status": "ok", "entity": self.server.entity.inspect()})
                return
            if parsed.path == "/v1/state":
                self._json(HTTPStatus.OK, self.server.entity.inspect())
                return
            if parsed.path == "/v1/computers/resources":
                values = parse_qs(parsed.query, strict_parsing=True)
                if set(values) != {"computer_id"} or len(values["computer_id"]) != 1:
                    raise ValueError("computer_id must occur exactly once")
                self._json(
                    HTTPStatus.OK,
                    self.server.entity.computer_resources(values["computer_id"][0]),
                )
                return
            if parsed.path == "/v1/memory":
                values = parse_qs(parsed.query)
                unknown = set(values) - {"limit", "include_unsettled"}
                if unknown:
                    raise ValueError(
                        f"unknown memory query fields: {sorted(unknown)}"
                    )
                limit_values = values.get("limit", ["32"])
                unsettled_values = values.get("include_unsettled", ["true"])
                if len(limit_values) != 1 or len(unsettled_values) != 1:
                    raise ValueError(
                        "memory query fields must occur at most once"
                    )
                unsettled_text = unsettled_values[0].lower()
                if unsettled_text not in {"true", "false"}:
                    raise ValueError(
                        "include_unsettled must be true or false"
                    )
                self._json(
                    HTTPStatus.OK,
                    self.server.entity.inspect_memory(
                        limit=int(limit_values[0]),
                        include_unsettled=unsettled_text == "true",
                    ),
                )
                return
            if parsed.path == "/v1/theory/documents":
                self._json(HTTPStatus.OK, self.server.entity.catalog_theory_documents())
                return
            if parsed.path == "/v1/research/status":
                self._json(HTTPStatus.OK, self.server.entity.researcher.status())
                return
            if parsed.path == "/v1/research/collaboration":
                self._json(
                    HTTPStatus.OK,
                    self.server.entity.research_collaboration(),
                )
                return
            if parsed.path == "/v1/research/capabilities":
                self._json(HTTPStatus.OK, self.server.entity.researcher.capability_map())
                return
            if parsed.path == "/v1/responsibilities/snapshot":
                self._json(
                    HTTPStatus.OK,
                    self.server.entity.research_responsibility_snapshot(),
                )
                return
            route = parsed.path.strip("/").split("/")
            if self._handle_surface_get(parsed, route):
                return
            if self._handle_program_get(parsed, route):
                return
            if (
                len(route) == 5
                and route[:2] == ["v1", "turns"]
                and route[3] == "tool-results"
            ):
                values = parse_qs(parsed.query)
                unknown = set(values) - {"page", "page_bytes"}
                if unknown:
                    raise ValueError(
                        f"unknown tool result page query fields: {sorted(unknown)}"
                    )
                page = values.get("page", ["0"])
                page_bytes = values.get("page_bytes", ["7500"])
                if len(page) != 1 or len(page_bytes) != 1:
                    raise ValueError("page and page_bytes must occur at most once")
                self._json(
                    HTTPStatus.OK,
                    self.server.entity.tool_result_page(
                        turn_id=unquote(route[2]),
                        call_id=unquote(route[4]),
                        page_index=int(page[0]),
                        page_bytes=int(page_bytes[0]),
                    ),
                )
                return
            if len(route) == 3 and route[:2] == ["v1", "turns"]:
                self._json(HTTPStatus.OK, self.server.entity.inspect_turn(unquote(route[2])))
                return
            if len(route) == 4 and route[:2] == ["v1", "turns"] and route[3] == "events":
                values = parse_qs(parsed.query)
                unknown = set(values) - {"after", "wait"}
                if unknown:
                    raise ValueError(f"unknown turn event query fields: {sorted(unknown)}")
                after = values.get("after", ["0"])
                wait = values.get("wait", ["0"])
                if len(after) != 1 or len(wait) != 1:
                    raise ValueError("after and wait must occur at most once")
                wait_seconds = max(0.0, min(float(wait[0]), 60.0))
                self._turn_events(unquote(route[2]), int(after[0]), wait_seconds=wait_seconds)
                return
            if len(route) == 4 and route[:3] == ["v1", "research", "artifacts"]:
                body = self.server.entity.researcher.store.artifact_bytes(route[3])
                self._raw(HTTPStatus.OK, body, content_type="application/octet-stream")
                return
            if parsed.path == "/v1/capabilities/proposal":
                values = parse_qs(parsed.query, strict_parsing=True)
                if set(values) != {"proposal_id"} or len(values["proposal_id"]) != 1:
                    raise ValueError("proposal_id must occur exactly once")
                self._json(HTTPStatus.OK, self.server.entity.describe_proposal(values["proposal_id"][0]))
                return
            if parsed.path == "/v1/events":
                values = parse_qs(parsed.query, strict_parsing=True)
                unknown = set(values) - {"after"}
                if unknown:
                    raise ValueError(f"unknown event query fields: {sorted(unknown)}")
                after = values.get("after", ["0"])
                if len(after) != 1:
                    raise ValueError("after must occur once")
                self._events(int(after[0]))
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "unknown route"})
        except SurfaceWait as exc:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": str(exc), "kind": "surface-wait", "details": dict(exc.details)},
            )
        except SurfaceOriginDenied as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "surface-origin-denied"})
        except SurfaceAuthorizationDenied as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "surface-authorization-denied"})
        except SurfaceAuthorizationError as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "surface-authorization-denied"})
        except SurfaceConflictError as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc), "kind": "surface-conflict"})
        except SurfaceValidationError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "kind": "surface-validation"})
        except SurfaceCapabilityError as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc), "kind": "surface-capability-unavailable"})
        except SurfaceUnavailable as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc), "kind": "surface-unavailable"})
        except CapabilityDenied as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "research-capability-denied"})
        except ProgramComputationNotFound as exc:
            self._json(
                HTTPStatus.NOT_FOUND,
                {"error": str(exc), "kind": "program-computation-not-found"},
            )
        except ProgramComputationConflict as exc:
            self._json(
                HTTPStatus.CONFLICT,
                {"error": str(exc), "kind": "program-computation-conflict"},
            )
        except ProgramCapabilityDenied as exc:
            self._json(
                HTTPStatus.FORBIDDEN,
                {"error": str(exc), "kind": "program-capability-denied"},
            )
        except ProgramBackendUnavailable as exc:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": str(exc), "kind": "program-backend-unavailable"},
            )
        except TurnNotFound as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc), "kind": "typed-turn-not-found"})
        except TurnConflict as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc), "kind": "typed-turn-conflict"})
        except ProgramNotFound as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc), "kind": "research-program-not-found"})
        except ResponsibilityAdmissionError as exc:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": str(exc), "kind": "responsibility-snapshot-unavailable"},
            )
        except PermissionError as exc:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def _handle_program_post(
        self,
        parsed: Any,
        route: list[str],
        body: Mapping[str, Any],
    ) -> bool:
        if route == ["v1", "programs"]:
            self._allowed(
                body,
                {
                    "request_id", "program_id", "project_id", "title",
                    "mission", "initial_question", "observed_at",
                },
                {
                    "priority", "cycle_limit", "allowed_roots",
                    "allowed_tools", "network_hosts", "deliverable",
                    "surface_scope", "responsibility",
                },
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.create_research_program(**body),
            )
            return True
        if (
            len(route) == 4
            and route[:2] == ["v1", "programs"]
            and route[3] == "consequences"
        ):
            self._allowed(
                body,
                {"request_id", "consequence", "observed_at"},
                set(),
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.record_research_consequence(
                    program_id=unquote(route[2]),
                    **body,
                ),
            )
            return True
        if (
            len(route) == 4
            and route[:2] == ["v1", "programs"]
            and route[3] == "computations"
        ):
            self._allowed(
                body,
                {
                    "request_id", "computation_id",
                    "expected_owner_state_sha256", "proposal", "observed_at",
                },
                set(),
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.propose_program_computation(
                    program_id=unquote(route[2]),
                    **body,
                ),
            )
            return True
        if (
            len(route) == 6
            and route[:2] == ["v1", "programs"]
            and route[3] == "computations"
            and route[5] == "control"
        ):
            self._allowed(
                body,
                {
                    "request_id", "expected_owner_state_sha256",
                    "action", "arguments", "observed_at",
                },
                set(),
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.control_program_computation(
                    program_id=unquote(route[2]),
                    computation_id=unquote(route[4]),
                    **body,
                ),
            )
            return True
        if (
            len(route) == 6
            and route[:2] == ["v1", "programs"]
            and route[3] == "computations"
            and route[5] == "branches"
        ):
            self._allowed(
                body,
                {
                    "request_id", "expected_owner_state_sha256", "action",
                    "branch_id", "arguments", "observed_at",
                },
                set(),
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.branch_program_computation(
                    program_id=unquote(route[2]),
                    computation_id=unquote(route[4]),
                    **body,
                ),
            )
            return True
        if (
            len(route) == 4
            and route[:2] == ["v1", "programs"]
            and route[3] == "workspace"
        ):
            self._allowed(
                body,
                {
                    "request_id", "expected_owner_state_sha256",
                    "command", "observed_at",
                },
                set(),
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.command_program_workspace(
                    program_id=unquote(route[2]),
                    **body,
                ),
            )
            return True
        if (
            len(route) == 4
            and route[:2] == ["v1", "programs"]
            and route[3] == "control"
        ):
            self._allowed(
                body,
                {"request_id", "action", "observed_at"},
                {
                    "message", "computation_id", "computation_arguments",
                    "expected_owner_state_sha256",
                },
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.control_research_program(
                    program_id=unquote(route[2]),
                    **body,
                ),
            )
            return True
        if (
            len(route) == 4
            and route[:2] == ["v1", "programs"]
            and route[3] == "guidance"
        ):
            self._allowed(
                body,
                {"request_id", "content", "observed_at"},
                {"workspace_command", "expected_owner_state_sha256"},
            )
            self._json(
                HTTPStatus.ACCEPTED,
                self.server.entity.guide_research_program(
                    program_id=unquote(route[2]),
                    **body,
                ),
            )
            return True
        return False

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._require_authorization()
            parsed = urlparse(self.path)
            route = parsed.path.strip("/").split("/")
            if route[:2] == ["v1", "surface"]:
                self._require_surface_origin()
                body = self._body(
                    max_bytes=16_384,
                    reject_duplicate_keys=True,
                )
                if not self._handle_surface_post(parsed, route, body):
                    self._json(HTTPStatus.NOT_FOUND, {"error": "unknown Surface route"})
                return
            body = self._body()
            if self._handle_program_post(parsed, route, body):
                return
            if parsed.path == "/v1/research/resources":
                self._allowed(
                    body,
                    {"allocation_id", "member_id", "objective", "budgets"},
                    {
                        "reservation_id", "mission_account_id", "work_order_id",
                        "lease_duration_ns", "scientific_relevance",
                    },
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.allocate_research_resources(**body),
                )
                return
            if parsed.path == "/v1/computers/operate":
                self._allowed(
                    body,
                    {"operation_id", "computer_id", "action"},
                    {"arguments", "expected_state_sha256"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.operate_computer(**body),
                )
                return
            if parsed.path == "/v1/research/workbench/dependency-change":
                self._allowed(
                    body,
                    {"request_id", "changes"},
                    {"program_ids"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.apply_research_workbench_change(**body),
                )
                return
            if parsed.path == "/v1/research/advance-member":
                self._required(body, set())
                result = self.server.entity.advance_research_member()
                self._json(
                    HTTPStatus.OK,
                    {"status": "waiting"} if result is None else dict(result),
                )
                return
            if parsed.path == "/v1/research/member/control":
                self._required(
                    body, {"control_id", "member_id", "action", "reason"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.control_research_member(**body),
                )
                return
            if parsed.path == "/v1/research/cohort/migrate":
                self._allowed(
                    body,
                    {"migration_id", "member_ids", "reason"},
                    {"profile"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.migrate_research_cohort(**body),
                )
                return
            if parsed.path == "/v1/research/cohort/recover":
                self._required(body, {"migration_id"})
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.recover_research_cohort(
                        str(body["migration_id"])
                    ),
                )
                return
            collaboration_routes = {
                "/v1/research/collaboration/request": (
                    self.server.entity.request_research_collaboration,
                    {
                        "request_id", "requester_instance_id", "objective",
                        "desired_roles", "source_representation",
                        "target_representation", "maximum_members",
                        "maximum_work", "input_artifact_ids",
                    },
                ),
                "/v1/research/collaboration/assign": (
                    self.server.entity.assign_research_collaboration,
                    {
                        "assignment_id", "request_id", "assignee_instance_id",
                        "role", "task", "resource_allocation_id",
                        "input_artifact_ids",
                    },
                ),
                "/v1/research/collaboration/respond": (
                    self.server.entity.respond_research_collaboration,
                    {
                        "response_id", "assignment_id",
                        "responder_instance_id", "status", "representation",
                        "content", "artifact_ids", "evidence_ids", "limitations",
                    },
                ),
                "/v1/research/collaboration/translate": (
                    self.server.entity.translate_research_collaboration,
                    {
                        "translation_id", "source_response_id",
                        "translator_instance_id", "source_representation",
                        "target_representation", "translated_content",
                        "mapping", "validation_status", "limitations",
                    },
                ),
                "/v1/research/collaboration/synthesize": (
                    self.server.entity.synthesize_research_collaboration,
                    {
                        "synthesis_id", "request_id",
                        "synthesizer_instance_id", "response_ids",
                        "translation_ids", "result", "agreements",
                        "disagreements", "unresolved",
                    },
                ),
                "/v1/research/collaboration/affect-report": (
                    self.server.entity.report_research_affect,
                    {
                        "message_id", "sender_instance_id", "recipient_scope",
                        "report_kind", "interpretation_status", "requested_help",
                        "content", "applicability", "question_ref", "goal_ref",
                        "episode_id", "evidence_roots", "visibility_refs",
                    },
                ),
            }
            collaboration_route = collaboration_routes.get(parsed.path)
            if collaboration_route is not None:
                method, fields = collaboration_route
                optional = set()
                if parsed.path == "/v1/research/collaboration/affect-report":
                    optional = {
                        "question_ref", "goal_ref", "episode_id",
                        "evidence_roots", "visibility_refs",
                    }
                self._allowed(body, fields - optional, optional)
                result = method(**body)
                payload = (
                    dict(result)
                    if isinstance(result, Mapping)
                    else {"document_id": result}
                )
                self._json(HTTPStatus.ACCEPTED, payload)
                return
            if parsed.path == "/v1/auxiliary":
                self._allowed(
                    body,
                    {"request_id", "purpose", "prompt", "max_tokens"},
                    set(),
                )
                self._json(HTTPStatus.OK, self.server.entity.auxiliary(**body))
                return
            if parsed.path == "/v1/turns":
                self._allowed(
                    body,
                    {
                        "turn_id",
                        "request_id",
                        "conversation_id",
                        "project_id",
                        "content",
                        "kind",
                        "observed_at",
                    },
                    {"source", "tool_catalog", "host_scope"},
                )
                self._json(HTTPStatus.ACCEPTED, self.server.entity.receive_turn(**body))
                return
            if len(route) == 4 and route[:2] == ["v1", "turns"] and route[3] == "tool-results":
                self._required(body, {"request_id", "results", "observed_at"})
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.submit_turn_tool_results(
                        turn_id=unquote(route[2]),
                        **body,
                    ),
                )
                return
            if len(route) == 4 and route[:2] == ["v1", "turns"] and route[3] == "resume":
                self._required(body, {"request_id", "observed_at"})
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.resume_turn(
                        turn_id=unquote(route[2]),
                        **body,
                    ),
                )
                return
            if len(route) == 4 and route[:2] == ["v1", "turns"] and route[3] == "cancel":
                self._required(body, {"request_id", "observed_at"})
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.cancel_turn(
                        turn_id=unquote(route[2]),
                        **body,
                    ),
                )
                return
            if parsed.path == "/v1/messages":
                self._required(
                    body,
                    {"request_id", "conversation_id", "project_id", "content", "observed_at"},
                )
                self._json(HTTPStatus.ACCEPTED, self.server.entity.receive_message(**body))
                return
            if parsed.path == "/v1/commitments":
                self._required(
                    body,
                    {
                        "request_id",
                        "commitment_id",
                        "conversation_id",
                        "project_id",
                        "title",
                        "purpose",
                        "observed_at",
                    },
                )
                self._json(HTTPStatus.ACCEPTED, self.server.entity.create_commitment(**body))
                return
            if parsed.path == "/v1/theory/tasks":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "task", "observed_at"},
                )
                self._json(HTTPStatus.ACCEPTED, self.server.entity.assign_theory_task(**body))
                return
            if parsed.path == "/v1/theory/read":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "target_path", "observed_at"},
                )
                self._json(HTTPStatus.ACCEPTED, self.server.entity.read_theory_document(**body))
                return
            if parsed.path == "/v1/theory/study-document":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "target_path", "observed_at"},
                )
                self._json(HTTPStatus.ACCEPTED, self.server.entity.study_theory_document(**body))
                return
            if parsed.path == "/v1/theory/maps/foundations":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "observed_at"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.build_foundational_claim_map(**body),
                )
                return
            if parsed.path == "/v1/theory/relations/foundations":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "observed_at"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.build_foundational_relation_graph(**body),
                )
                return
            if parsed.path == "/v1/theory/relations/foundations/study":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "observed_at"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.synthesize_foundational_relation(**body),
                )
                return
            if parsed.path == "/v1/theory/contributions/xi-attractor":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "observed_at"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.derive_xi_attractor_obligation(**body),
                )
                return
            if parsed.path == "/v1/theory/specifications/dwarf-likelihood":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "observed_at"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.build_dwarf_likelihood_spec(**body),
                )
                return
            if parsed.path == "/v1/theory/observations/dwarf-sources":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "observed_at"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.admit_dwarf_observation_sources(**body),
                )
                return
            if parsed.path == "/v1/theory/observations/dwarf-kinematics/audit":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "observed_at"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.audit_dwarf_kinematic_sources(**body),
                )
                return
            if parsed.path == "/v1/theory/observations/dwarf-stellar-populations":
                self._required(
                    body,
                    {"request_id", "task_id", "conversation_id", "project_id", "observed_at"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.admit_dwarf_stellar_population_evidence(**body),
                )
                return
            if parsed.path == "/v1/capabilities/proposals":
                self._required(
                    body,
                    {
                        "request_id",
                        "proposal_id",
                        "commitment_id",
                        "conversation_id",
                        "project_id",
                        "capability",
                        "target_path",
                        "start_byte",
                        "max_bytes",
                        "observed_at",
                    },
                )
                self._json(HTTPStatus.ACCEPTED, self.server.entity.propose_capability(**body))
                return
            if parsed.path == "/v1/theory/study":
                self._required(body, {"request_id", "proposal_id", "observed_at"})
                self._json(HTTPStatus.ACCEPTED, self.server.entity.study_theory_excerpt(**body))
                return
            if parsed.path == "/v1/capabilities/approvals":
                self._required(body, {"request_id", "proposal_id", "approved_by", "observed_at"})
                self._json(HTTPStatus.ACCEPTED, self.server.entity.approve_capability(**body))
                return
            if parsed.path == "/v1/capabilities/execute":
                self._required(body, {"request_id", "proposal_id", "observed_at"})
                self._json(HTTPStatus.ACCEPTED, self.server.entity.execute_capability(**body))
                return
            if parsed.path == "/v1/cycles/commitment":
                self._required(
                    body,
                    {
                        "request_id",
                        "commitment_id",
                        "conversation_id",
                        "project_id",
                        "observed_at",
                    },
                )
                self._json(HTTPStatus.ACCEPTED, self.server.entity.advance_commitment(**body))
                return
            if parsed.path == "/v1/cycles/self-question":
                self._required(body, {"request_id", "conversation_id", "project_id", "observed_at"})
                self._json(HTTPStatus.ACCEPTED, self.server.entity.think(**body))
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "unknown route"})
        except SurfaceWait as exc:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": str(exc), "kind": "surface-wait", "details": dict(exc.details)},
            )
        except SurfaceOriginDenied as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "surface-origin-denied"})
        except SurfaceAuthorizationDenied as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "surface-authorization-denied"})
        except SurfaceAuthorizationError as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "surface-authorization-denied"})
        except SurfaceConflictError as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc), "kind": "surface-conflict"})
        except SurfaceValidationError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "kind": "surface-validation"})
        except SurfaceCapabilityError as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc), "kind": "surface-capability-unavailable"})
        except SurfaceUnavailable as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc), "kind": "surface-unavailable"})
        except CapabilityApprovalRequired as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "approval-required"})
        except CapabilityDenied as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "research-capability-denied"})
        except ProgramCapabilityDenied as exc:
            self._json(
                HTTPStatus.FORBIDDEN,
                {"error": str(exc), "kind": "program-capability-denied"},
            )
        except ProgramBackendUnavailable as exc:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": str(exc), "kind": "program-backend-unavailable"},
            )
        except ProgramComputationNotFound as exc:
            self._json(
                HTTPStatus.NOT_FOUND,
                {"error": str(exc), "kind": "program-computation-not-found"},
            )
        except ProgramComputationConflict as exc:
            self._json(
                HTTPStatus.CONFLICT,
                {"error": str(exc), "kind": "program-computation-conflict"},
            )
        except TurnNotFound as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc), "kind": "typed-turn-not-found"})
        except TurnConflict as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc), "kind": "typed-turn-conflict"})
        except ProgramNotFound as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc), "kind": "research-program-not-found"})
        except ProgramConflict as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc), "kind": "research-program-conflict"})
        except ResponsibilityAdmissionError as exc:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": str(exc), "kind": "responsibility-admission-wait"},
            )
        except PermissionError as exc:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        except (BrainUnavailable, ResearchBrainUnavailable) as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc), "kind": "brain-unavailable"})
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

def _start_linux_surface(
    config_path: Path,
) -> tuple[LinuxSessionSupervisor, LinuxXvncBackend, WslPulseAudioBackend | None]:
    """Start one configured guest, then prove its authenticated display has a full frame."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) != {"session", "rfb"}:
        raise ValueError("Linux Surface config must contain exactly session and rfb")
    rfb = config["rfb"]
    if not isinstance(rfb, dict) or set(rfb) != {"transport"}:
        raise ValueError("Linux Surface rfb config must contain exactly transport")
    transport = rfb["transport"]
    if (not isinstance(transport, dict) or transport.get("kind") != "protected-tcp-tls"
            or transport.get("protected") is not True or transport.get("host") != "127.0.0.1"):
        raise ValueError("Linux Surface requires authenticated TLS on the host loopback")

    supervisor = LinuxSessionSupervisor(config["session"])
    backend: LinuxXvncBackend | None = None
    audio_backend: WslPulseAudioBackend | None = None
    try:
        supervisor.start()
        status = supervisor.wait_ready()
        if not status["ready"]:
            raise RuntimeError("dedicated Linux desktop did not pass its configured readiness probe")
        source_id = status["session_id"]
        display_backend = LinuxXvncBackend([{
            "source_id": source_id,
            "source_instance": status["source_instance"],
            "environment_incarnation": status["environment_incarnation"],
            "transport": transport,
        }])
        backend = display_backend
        binding = display_backend.bind(source_id)
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            frame = display_backend.capture(binding)
            if frame["coverage"]["complete"] and frame["coverage"]["connection_state"] == "live":
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("dedicated Linux desktop has no complete RFB baseline")
        session = config["session"]
        if session["audio"]["kind"] == "pulseaudio":
            audio_env = session["audio"]["environment"]
            audio_route = WslPulseAudioBackend(
                distribution=session["distribution"], user=session["user"], home=session["home"],
                session_id=source_id, runtime_dir=session["runtime_dir"],
                server_socket=audio_env["PULSE_SERVER"].removeprefix("unix:"),
                session_endpoint_id=audio_env["PULSE_SINK"], monitor_source_id=audio_env["PULSE_SOURCE"],
            )
            audio_backend = audio_route
            if not audio_route.sources():
                raise RuntimeError("dedicated Linux audio monitor did not pass its route probe")
        return supervisor, backend, audio_backend
    except BaseException:
        if audio_backend is not None:
            audio_backend.close()
        if backend is not None:
            backend.close()
        supervisor.close()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the explicit Cassi field–brain entity API on loopback.")
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument(
        "--brain-backend",
        choices=("resident", "external"),
        default="resident",
        help="resident owner-backed Qwen graph (default) or explicit loopback baseline",
    )
    parser.add_argument(
        "--resource-limits",
        type=json.loads,
        default=None,
        help="JSON object configuring RAM/VRAM/storage/scratch/transfer policy",
    )
    parser.add_argument("--model-url", default=None, help="loopback URL for --brain-backend external")
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path("Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf"),
    )
    parser.add_argument("--resident-backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--resident-state-directory", type=Path)
    parser.add_argument("--resident-library-path", type=Path)
    parser.add_argument("--resident-threads", type=int, default=8)
    parser.add_argument("--api-token-file", type=Path, required=True)
    parser.add_argument(
        "--trading-paper-view",
        type=Path,
        help="register a verified read-only paper application view on Surface",
    )
    parser.add_argument(
        "--surface-linux-config",
        type=Path,
        help="host-owned dedicated Linux session and authenticated RFB transport config",
    )
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--entity-id", default="cassi")
    parser.add_argument("--max-response-tokens", type=int, default=2_048)
    parser.add_argument("--max-question-tokens", type=int, default=768)
    parser.add_argument("--brain-context-tokens", type=int, default=32_768)
    parser.add_argument("--brain-context-reserve-tokens", type=int, default=128)
    parser.add_argument("--capability-root", type=Path, default=Path.cwd())
    parser.add_argument("--theory-root", type=Path, default=Path.cwd().parent / "CassiTheory")
    parser.add_argument("--research-home", type=Path)
    parser.add_argument("--research-root", type=Path, action="append")
    parser.add_argument("--research-network-host", action="append", default=[])
    parser.add_argument("--research-cycle-seconds", type=float, default=1.0)
    parser.add_argument(
        "--research-tool",
        action="append",
        choices=(
            "list_files",
            "read_file",
            "search_text",
            "write_artifact",
            "inspect_artifact",
            "fetch_url",
            "run_existing_python",
        ),
    )
    parser.add_argument("--no-resident", action="store_true")
    parser.add_argument("--no-program-native", action="store_true")
    parser.add_argument("--require-program-native", action="store_true")
    parser.add_argument("--program-native-runtime", type=Path)
    parser.add_argument("--program-native-device", type=int, default=0)
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65_535:
        parser.error("--port must be in 1..65535")
    try:
        api_token = arguments.api_token_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        parser.error(f"cannot read --api-token-file: {exc}")
    if len(api_token) < 32:
        parser.error("--api-token-file must contain at least 32 characters")
    with ExitStack() as owned:
        surface_backends: list[Any] = []
        if arguments.trading_paper_view is not None:
            surface_backends.append(TradingPaperSurfaceBackend(arguments.trading_paper_view))
        if arguments.surface_linux_config is not None:
            supervisor, linux_backend, audio_backend = _start_linux_surface(arguments.surface_linux_config)
            owned.callback(supervisor.close)
            owned.callback(linux_backend.close)
            surface_backends.append(linux_backend)
            if audio_backend is not None:
                owned.callback(audio_backend.close)
                surface_backends.append(audio_backend)
        entity = open_local_entity(
            arguments.data_home,
            model_url=arguments.model_url,
            model_path=arguments.model_path,
            brain_backend=arguments.brain_backend,
            resident_backend=arguments.resident_backend,
            resident_state_directory=arguments.resident_state_directory,
            resident_library_path=arguments.resident_library_path,
            resident_threads=arguments.resident_threads,
            entity_id=arguments.entity_id,
            max_response_tokens=arguments.max_response_tokens,
            max_question_tokens=arguments.max_question_tokens,
            brain_context_tokens=arguments.brain_context_tokens,
            brain_context_reserve_tokens=arguments.brain_context_reserve_tokens,
            resource_limits=arguments.resource_limits,
            capability_root=arguments.capability_root,
            theory_root=arguments.theory_root,
            research_home=arguments.research_home,
            research_roots=tuple(arguments.research_root) if arguments.research_root else None,
            research_network_hosts=tuple(arguments.research_network_host),
            research_cycle_interval_seconds=arguments.research_cycle_seconds,
            research_default_tools=(
                tuple(arguments.research_tool)
                if arguments.research_tool
                else (
                    "list_files",
                    "read_file",
                    "search_text",
                    "write_artifact",
                    "inspect_artifact",
                )
            ),
            research_resident_enabled=not arguments.no_resident,
            program_native_enabled=not arguments.no_program_native,
            program_native_required=arguments.require_program_native,
            program_native_runtime_executable=arguments.program_native_runtime,
            program_native_device_index=arguments.program_native_device,
            surface_backends=tuple(surface_backends),
        )
        owned.callback(entity.close)
        server = EntityHTTPServer(("127.0.0.1", arguments.port), entity, api_token=api_token)
        owned.callback(server.server_close)
        print(
            json.dumps(
                {"status": "ready", "host": "127.0.0.1", "port": arguments.port, "entity": entity.inspect()},
                sort_keys=True,
            ),
            flush=True,
        )
        server.serve_forever()


if __name__ == "__main__":
    main()
