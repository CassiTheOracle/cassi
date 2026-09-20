"""Loopback HTTP/SSE surface for the explicit Cassi field–brain entity profile."""

from __future__ import annotations

import argparse
import hmac
import json
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
)

from cassi_field_brain_entity import (
    BrainUnavailable,
    CapabilityApprovalRequired,
    FieldBrainEntity,
    TurnConflict,
    TurnNotFound,
    open_local_entity,
)



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

    def _raw(self, status: HTTPStatus, body: bytes, *, content_type: str) -> None:
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _require_authorization(self) -> None:
        supplied = self.headers.get("authorization")
        expected = f"Bearer {self.server.api_token}"
        if supplied is None or not hmac.compare_digest(supplied, expected):
            raise PermissionError("a valid bearer token is required")

    def _body(self) -> Mapping[str, Any]:
        raw_length = self.headers.get("content-length")
        if raw_length is None:
            raise ValueError("content-length is required")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("content-length must be an integer") from exc
        if length < 0 or length > 65_536:
            raise ValueError("request body exceeds 65536 bytes")
        try:
            decoded = json.loads(self.rfile.read(length).decode("utf-8"))
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

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._require_authorization()
            parsed = urlparse(self.path)
            if parsed.path == "/v1/health":
                self._json(HTTPStatus.OK, {"status": "ok", "entity": self.server.entity.inspect()})
                return
            if parsed.path == "/v1/state":
                self._json(HTTPStatus.OK, self.server.entity.inspect())
                return
            if parsed.path == "/v1/theory/documents":
                self._json(HTTPStatus.OK, self.server.entity.catalog_theory_documents())
                return
            if parsed.path == "/v1/research/status":
                self._json(HTTPStatus.OK, self.server.entity.researcher.status())
                return
            if parsed.path == "/v1/research/capabilities":
                self._json(HTTPStatus.OK, self.server.entity.researcher.capability_map())
                return
            if parsed.path == "/v1/programs":
                self._json(
                    HTTPStatus.OK,
                    {
                        "schema": "cassi.entity.research-program-list.v1",
                        "programs": self.server.entity.research_programs(),
                    },
                )
                return
            route = parsed.path.strip("/").split("/")
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
            if len(route) == 3 and route[:2] == ["v1", "programs"]:
                self._json(HTTPStatus.OK, self.server.entity.research_program(route[2]))
                return
            if (
                len(route) in {4, 5}
                and route[:2] == ["v1", "programs"]
                and route[3] == "events"
                and (len(route) == 4 or route[4] == "stream")
            ):
                values = parse_qs(parsed.query)
                unknown = set(values) - {"after", "wait"}
                if unknown:
                    raise ValueError(f"unknown research event query fields: {sorted(unknown)}")
                after = values.get("after", ["0"])
                wait = values.get("wait", ["0"])
                if len(after) != 1 or len(wait) != 1:
                    raise ValueError("after and wait must occur at most once")
                wait_seconds = max(0.0, min(float(wait[0]), 60.0))
                self._research_events(route[2], int(after[0]), wait_seconds=wait_seconds)
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
        except CapabilityDenied as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "research-capability-denied"})
        except TurnNotFound as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc), "kind": "typed-turn-not-found"})
        except TurnConflict as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc), "kind": "typed-turn-conflict"})
        except ProgramNotFound as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc), "kind": "research-program-not-found"})
        except PermissionError as exc:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._require_authorization()
            parsed = urlparse(self.path)
            body = self._body()
            route = parsed.path.strip("/").split("/")
            if parsed.path == "/v1/programs":
                self._allowed(
                    body,
                    {
                        "request_id",
                        "program_id",
                        "project_id",
                        "title",
                        "mission",
                        "initial_question",
                        "observed_at",
                    },
                    {
                        "priority",
                        "cycle_limit",
                        "allowed_roots",
                        "allowed_tools",
                        "network_hosts",
                    },
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.create_research_program(**body),
                )
                return
            if len(route) == 4 and route[:2] == ["v1", "programs"] and route[3] == "control":
                self._allowed(
                    body,
                    {"request_id", "action", "observed_at"},
                    {"message"},
                )
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.control_research_program(
                        program_id=route[2],
                        **body,
                    ),
                )
                return
            if len(route) == 4 and route[:2] == ["v1", "programs"] and route[3] == "guidance":
                self._required(body, {"request_id", "content", "observed_at"})
                self._json(
                    HTTPStatus.ACCEPTED,
                    self.server.entity.guide_research_program(
                        program_id=route[2],
                        **body,
                    ),
                )
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
        except CapabilityApprovalRequired as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "approval-required"})
        except CapabilityDenied as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc), "kind": "research-capability-denied"})
        except TurnNotFound as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc), "kind": "typed-turn-not-found"})
        except TurnConflict as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc), "kind": "typed-turn-conflict"})
        except ProgramNotFound as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc), "kind": "research-program-not-found"})
        except ProgramConflict as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc), "kind": "research-program-conflict"})
        except PermissionError as exc:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        except (BrainUnavailable, ResearchBrainUnavailable) as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc), "kind": "brain-unavailable"})
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the explicit Cassi field–brain entity API on loopback.")
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument("--model-url", default="http://127.0.0.1:8084")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--api-token-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--entity-id", default="cassi")
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
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65_535:
        parser.error("--port must be in 1..65535")
    try:
        api_token = arguments.api_token_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        parser.error(f"cannot read --api-token-file: {exc}")
    if len(api_token) < 32:
        parser.error("--api-token-file must contain at least 32 characters")
    entity = open_local_entity(
        arguments.data_home,
        model_url=arguments.model_url,
        model_path=arguments.model_path,
        entity_id=arguments.entity_id,
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
    )
    server = EntityHTTPServer(("127.0.0.1", arguments.port), entity, api_token=api_token)
    try:
        print(
            json.dumps(
                {"status": "ready", "host": "127.0.0.1", "port": arguments.port, "entity": entity.inspect()},
                sort_keys=True,
            ),
            flush=True,
        )
        server.serve_forever()
    finally:
        server.server_close()
        entity.close()


if __name__ == "__main__":
    main()
