"""Bounded, source-bound worlds admitted into the continuing Cassi entity."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class ActivityRefused(RuntimeError):
    """A hosted action lacks the current programme, source, or safety scope."""


def _identity(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def _admit_intent(receipt: Path, identity: Mapping[str, Any]) -> bool:
    """Bind a non-replayable action before it can affect a world or field."""
    intent = receipt.with_name("intent.json")
    body = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False)
    intent.parent.mkdir(parents=True, exist_ok=True)
    try:
        with intent.open("x", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if intent.read_text(encoding="utf-8") != body:
            raise ActivityRefused("the hosted operation identity was reused with different arguments")
        if not receipt.is_file():
            raise ActivityRefused("prior hosted effect has no receipt; inspect the unfinished operation")
        return False
    if receipt.exists():
        raise ActivityRefused("a hosted receipt exists without its bound operation intent")
    return True


def _current_program(entity: Any, supplied: Mapping[str, Any], activity: str, operation: str) -> Mapping[str, Any]:
    program_id = supplied.get("program_id")
    if not isinstance(program_id, str) or not program_id:
        raise ActivityRefused("hosted activity requires a programme identity")
    current = entity.researcher.program(program_id)
    if current is None or current.get("status") != "active":
        raise ActivityRefused("the hosted activity programme is no longer active")
    scope = current.get("activity_scope", {})
    activities = scope.get("activities", {}) if isinstance(scope, Mapping) else {}
    allowed = activities.get(activity, ()) if isinstance(activities, Mapping) else ()
    if not isinstance(allowed, (list, tuple)) or allowed.count(operation) != 1:
        raise ActivityRefused("the current programme does not authorize this activity operation")
    return current


def _field_result(entity: Any, program: Mapping[str, Any], activity: str, operation: str,
                  operation_id: str, result: Mapping[str, Any], *,
                  observed_at: str | None = None) -> None:
    """File a compact sourced consequence in the same work memory as the brain."""
    entity._record(
        source_id=f"entity:hosted:{activity}:{_identity(operation_id)}",
        context={"entity_id": entity.config.entity_id,
                 "project_id": program["project_id"], "scope": "hosted-activity"},
        observed_at=observed_at or datetime.now(timezone.utc).isoformat(),
        kind="hosted-activity",
        payload={"activity_id": activity, "operation": operation,
                 "operation_id": operation_id, "result": dict(result)},
    )


class NetHackActivity:
    """Let the resident brain play a bounded life with borrowed field memory.

    Config and save files are inspected by NetHackWorld, never rewritten or
    cleared by this hosted path. Nothing starts merely because this activity is
    registered; an active programme must explicitly choose `play-life`.
    """

    activity_id = "nethack"

    def __init__(self, *, program: Path | None = None, player: str = "Cassi",
                 world_factory: Any | None = None) -> None:
        self.program = None if program is None else Path(program)
        self.player = player
        self._world_factory = world_factory
        self.entity: Any | None = None
        self._lock = threading.RLock()

    def attach(self, entity: Any) -> None:
        self.entity = entity

    def describe(self) -> Mapping[str, Any]:
        return {
            "activity_id": self.activity_id,
            "operations": ["play-life"],
            "source": "local NetHack terminal; preserved player configuration and saves",
            "effect": "bounded local gameplay, one borrowed field memory, source-bound life receipt",
            "max_turns": 40,
            "brain": "entity resident model; strict decisions, 32 action / 96 reflection tokens",
        }

    def _receipt_result(self, path: Path, entity: Any) -> Mapping[str, Any]:
        body = path.read_bytes()
        receipt = json.loads(body)
        if not isinstance(receipt, dict):
            raise ActivityRefused("game receipt is not an object")
        living = receipt.get("living") or {}
        reflection = living.get("reflection") or {} if isinstance(living, dict) else {}
        return {
            "status": "ERROR" if receipt.get("error") else "COMPLETE",
            "error": receipt.get("error"),
            "turns": receipt.get("turns"),
            "final": receipt.get("final"),
            "lesson_summary": reflection.get("life") if isinstance(reflection, dict) else None,
            "receipt_path": str(path),
            "receipt_sha256": hashlib.sha256(body).hexdigest(),
            "field_home": str(entity.memory.data_home),
            "brain_model": entity.brain.model_id,
        }

    def _run(self, operation: str, parameters: Mapping[str, Any], *,
             program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        if self.entity is None:
            raise ActivityRefused("game activity is not attached")
        current = _current_program(self.entity, program, self.activity_id, operation)
        if operation != "play-life" or set(parameters) - {"turns"}:
            raise ActivityRefused("game activity accepts only play-life with optional turns")
        turns = parameters.get("turns", 16)
        if isinstance(turns, bool) or not isinstance(turns, int) or not 1 <= turns <= 40:
            raise ActivityRefused("game life requires 1 to 40 turns")
        path = self.entity.config.data_home / "activities" / self.activity_id / _identity(operation_id) / "receipt.json"
        if _admit_intent(path, {
            "activity_id": self.activity_id, "operation": operation,
            "program_id": current["program_id"], "parameters": {"turns": turns},
            "player": self.player, "executable": str(self.program) if self.program else None,
        }):
            from games.livingmemory import GameMemory  # type: ignore[import-not-found]
            from games.nethack import NetHackWorld  # type: ignore[import-not-found]
            from games.player import BrainPlayer  # type: ignore[import-not-found]
            from run_cassi_game import build_parser, play_life  # type: ignore[import-not-found]

            args = build_parser().parse_args(["play", "--player", "brain", "--no-view",
                                              "--turns", str(turns)])
            args.follow = True
            world = (self._world_factory() if self._world_factory is not None else
                     NetHackWorld(program=self.program, player=self.player,
                                  preserve_existing_state=True, write_config=False,
                                  allow_save=False))
            if (getattr(world, "name", None) != "nethack" or
                    not getattr(world, "preserve_existing_state", False) or
                    getattr(world, "write_config", True) or
                    getattr(world, "allow_save", True)):
                raise ActivityRefused("hosted NetHack world must preserve player state")
            living = GameMemory(home=self.entity.memory.data_home, memory=self.entity.memory)
            player = BrainPlayer(
                completion=self.entity.brain.complete, model=self.entity.brain.model_id,
                require_brain=True, action_max_tokens=32, reflection_max_tokens=96,
            )
            try:
                play_life(args, living=living, world=world, player=player,
                          life_label=_identity(operation_id)[:16], run_dir=path.parent)
            except Exception:
                if not path.is_file():
                    raise
            finally:
                living.close()  # borrowed: the entity continues owning its field
        result = self._receipt_result(path, self.entity)
        _field_result(self.entity, current, self.activity_id, operation, operation_id, result)
        return result

    def run(self, operation: str, parameters: Mapping[str, Any], *,
            program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        with self._lock:
            return self._run(operation, parameters, program=program, operation_id=operation_id)



class _CurrentTradingVerifier:
    def __init__(self, entity: Any, program_id: str, data_home: Path, ingestion_db: Path):
        self.entity = entity
        self.program_id = program_id
        self.data_home = data_home
        self.ingestion_db = ingestion_db

    def verify(self) -> Mapping[str, Any]:
        from cassi_trader_application import validate_entity_program_payload  # type: ignore[import-not-found]
        return validate_entity_program_payload(
            self.entity.researcher.program(self.program_id),
            program_id=self.program_id, data_home=self.data_home,
            ingestion_db=self.ingestion_db,
        )


class TradingActivity:
    """Admit canonical closed bars and optional simulated paper steps into Cassi."""

    activity_id = "trading"

    def __init__(self, *, data_home: Path, ingestion_db: Path,
                 paper_program_id: str | None = None, symbol: str = "BTC-USD") -> None:
        self.data_home = Path(data_home).expanduser().resolve()
        self.ingestion_db = Path(ingestion_db).expanduser().resolve()
        self.paper_program_id = paper_program_id
        self.symbol = symbol
        self.entity: Any | None = None
        self._lock = threading.RLock()

    def attach(self, entity: Any) -> None:
        self.entity = entity

    def describe(self) -> Mapping[str, Any]:
        return {
            "activity_id": self.activity_id,
            "operations": ["ingest"] + (["paper-step"] if self.paper_program_id else []),
            "source": str(self.ingestion_db),
            "member_home": str(self.data_home),
            "effect": "canonical closed-bar ingestion and field-selected paper simulation; no live order path",
            "max_new_bars": 256,
            "paper_program_id": self.paper_program_id,
        }

    def _run(self, operation: str, parameters: Mapping[str, Any], *,
             program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        if self.entity is None:
            raise ActivityRefused("trading activity is not attached")
        current = _current_program(self.entity, program, self.activity_id, operation)
        if operation not in self.describe()["operations"] or set(parameters) - {"max_new_bars"}:
            raise ActivityRefused("trading requires an enabled bounded ingestion or paper step")
        limit = parameters.get("max_new_bars", 16)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 256:
            raise ActivityRefused("trading step requires 1 to 256 new bars")
        if not self.ingestion_db.is_file():
            raise ActivityRefused("the configured canonical ingestion database does not exist")
        if operation == "paper-step" and current["program_id"] != self.paper_program_id:
            raise ActivityRefused("paper simulation is bound to a different active programme")
        path = (self.entity.config.data_home / "activities" / self.activity_id /
                _identity(operation_id) / "receipt.json")
        if _admit_intent(path, {
            "activity_id": self.activity_id, "operation": operation,
            "program_id": current["program_id"], "parameters": {"max_new_bars": limit},
            "data_home": str(self.data_home), "ingestion_db": str(self.ingestion_db),
            "symbol": self.symbol, "paper_program_id": self.paper_program_id,
        }):
            trading_dir = Path(__file__).resolve().parent.parent / "CassiTrading"
            if str(trading_dir) not in sys.path:
                sys.path.insert(0, str(trading_dir))
            from run_cassi_trading_field import _parser, run_hosted_trading_field  # type: ignore[import-not-found]

            command = ["--data-home", str(self.data_home), "run",
                       "--ingestion-db", str(self.ingestion_db), "--symbol", self.symbol,
                       "--max-new-bars", str(limit), "--receipt", str(path)]
            verifier = None
            if operation == "paper-step":
                paper_id = self.paper_program_id
                if paper_id is None:
                    raise ActivityRefused("paper activity is not configured")
                command += ["--paper-only", "--entity-program-id", paper_id,
                            "--member-id", self.entity.config.entity_id,
                            "--mission-id", paper_id]
                verifier = _CurrentTradingVerifier(
                    self.entity, paper_id, self.data_home, self.ingestion_db,
                )
            args = _parser().parse_args(command)
            run_hosted_trading_field(args, owner=self.entity._program_owner, verifier=verifier)
        body = path.read_bytes()
        receipt = json.loads(body)
        if not isinstance(receipt, dict):
            raise ActivityRefused("trading receipt is not an object")
        source = receipt.get("source") or {}
        result = receipt.get("result") or {}
        summary = {
            "status": receipt.get("status", "PASS"),
            "reason": receipt.get("reason"),
            "mode": operation,
            "processed_bars": receipt.get("processed_bars", result.get("processed", 0))
            if isinstance(result, dict) else receipt.get("processed_bars", 0),
            "admitted_bars": result.get("admitted_bars") if isinstance(result, dict) else None,
            "source_event_root_sha256": source.get("accepted_event_root_sha256")
            if isinstance(source, dict) else None,
            "receipt_path": str(path),
            "receipt_sha256": hashlib.sha256(body).hexdigest(),
            "field_owner": self.entity.config.entity_id,
            "external_order_path": False,
        }
        _field_result(self.entity, current, self.activity_id, operation, operation_id, summary)
        return summary

    def run(self, operation: str, parameters: Mapping[str, Any], *,
            program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        with self._lock:
            return self._run(operation, parameters, program=program, operation_id=operation_id)



_SELF_REWRITE_RUNNERS = {
    "source": "runtime",
    "self-host": "self_host_runtime",
    "workspace": "workspace_runtime",
    "patchset": "patchset_runtime",
    "impact": "impact_runtime",
}


class SelfRewriteActivity:
    """Advance one host-bound CassiMindField generation through the live owner."""

    activity_id = "self-rewrite"

    def __init__(
        self,
        *,
        root: Path,
        variant: str,
    ) -> None:
        if not isinstance(variant, str) or variant not in _SELF_REWRITE_RUNNERS:
            raise ActivityRefused("self-rewrite variant is not enabled by the host")
        self.root = Path(root).expanduser().resolve()
        self.variant = variant
        self.entity: Any | None = None
        self._lock = threading.RLock()

    def attach(self, entity: Any) -> None:
        self.entity = entity

    def describe(self) -> Mapping[str, Any]:
        return {
            "activity_id": self.activity_id,
            "operations": ["advance"],
            "variant": self.variant,
            "effect": "advance one field-selected immutable generation under the live responsibility owner",
            "max_generations_per_operation": 1,
        }

    @staticmethod
    def _safe_identifier(value: Any, label: str) -> str:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 256
            or not all(char.isascii() and (char.isalnum() or char in "._:-") for char in value)
        ):
            raise ActivityRefused(f"self-rewrite {label} is not a bounded identifier")
        return value

    def _host_module(self, module_name: str, module_dir: Path) -> Any:
        expected = (module_dir / f"{module_name}.py").resolve()
        try:
            module = importlib.import_module(module_name)
            module_file = getattr(module, "__file__", None)
            if not isinstance(module_file, str):
                raise ActivityRefused("the configured self-rewrite runner has no source path")
            actual = Path(module_file).resolve()
        except Exception as exc:
            raise ActivityRefused("the configured self-rewrite runner is unavailable") from exc
        if actual != expected:
            raise ActivityRefused("the self-rewrite runner did not resolve from the host module path")
        return module

    def _runner_components(self) -> tuple[Any, Any, Any]:
        module_dir = Path(__file__).resolve().parent.parent / "CassiMindField"
        module_dir_text = str(module_dir.resolve())
        if module_dir_text in sys.path:
            sys.path.remove(module_dir_text)
        sys.path.insert(0, module_dir_text)
        owner_module = self._host_module("field_owner_rewrite", module_dir)
        self._host_module("runtime", module_dir)
        runner_name = _SELF_REWRITE_RUNNERS[self.variant]
        runner_module = (
            self._host_module(runner_name, module_dir)
            if runner_name != "runtime"
            else self._host_module("runtime", module_dir)
        )
        run = getattr(runner_module, "run", None)
        owner_client = getattr(owner_module, "LocalFieldOwnerClient", None)
        pending_review = getattr(owner_module, "PendingRewriteReview", None)
        if not callable(run) or not callable(owner_client) or not isinstance(pending_review, type):
            raise ActivityRefused("the configured self-rewrite runner lacks its host owner interface")
        return run, owner_client(self.entity), pending_review

    def _current_generation(self) -> int:
        path = self.root / "current.json"
        if not path.is_file():
            return 0
        try:
            pointer = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ActivityRefused("self-rewrite current pointer is unreadable") from exc
        if not isinstance(pointer, Mapping):
            raise ActivityRefused("self-rewrite current pointer is not an object")
        generation = pointer.get("generation")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
            raise ActivityRefused("self-rewrite current generation is invalid")
        return generation

    def _review_owner_ref(self, transition: Mapping[str, Any] | None) -> Mapping[str, Any]:
        if self.entity is None:
            raise ActivityRefused("self-rewrite activity is not attached")
        program_id = None
        if transition is not None:
            review = transition.get("responsibility_review")
            if isinstance(review, Mapping) and review.get("program_id") is not None:
                program_id = self._safe_identifier(review.get("program_id"), "review owner")
        if program_id is None:
            link_path = self.root / "field-owner-link.json"
            if link_path.is_file():
                try:
                    link = json.loads(link_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    raise ActivityRefused("self-rewrite owner reference is unreadable") from exc
                if not isinstance(link, Mapping):
                    raise ActivityRefused("self-rewrite owner reference is not an object")
                linked_program = link.get("program_id")
                if linked_program is not None:
                    program_id = self._safe_identifier(linked_program, "review owner")
        entity_id = self._safe_identifier(self.entity.config.entity_id, "entity owner")
        return {"entity_id": entity_id, "program_id": program_id}

    def _summary(
        self,
        receipt: Mapping[str, Any],
        *,
        initial_generation: int,
        actual_generation: int,
    ) -> Mapping[str, Any]:
        status = receipt.get("status")
        current = receipt.get("current")
        if (
            not isinstance(status, str)
            or status not in {"complete", "awaiting-review"}
            or not isinstance(current, Mapping)
        ):
            raise ActivityRefused("self-rewrite runner returned an invalid bounded receipt")
        generation = current.get("generation")
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation != actual_generation
            or generation < initial_generation
            or generation > initial_generation + 1
        ):
            raise ActivityRefused("self-rewrite runner advanced an unexpected generation")
        transitions = receipt.get("transitions")
        if not isinstance(transitions, list):
            raise ActivityRefused("self-rewrite runner returned an invalid transition list")
        candidate_id = None
        transition = None
        if generation == initial_generation + 1:
            matches = [
                row for row in transitions
                if isinstance(row, Mapping)
                and not isinstance(row.get("next_generation"), bool)
                and row.get("generation") == initial_generation
                and row.get("next_generation") == generation
            ]
            if len(matches) != 1 or not isinstance(matches[0].get("candidate"), Mapping):
                raise ActivityRefused("self-rewrite generation lacks its candidate reference")
            transition = matches[0]
            candidate_id = self._safe_identifier(
                transition["candidate"].get("candidate_id"), "candidate"
            )
        summary = {
            "generation": generation,
            "status": status,
            "candidate_id": candidate_id,
            "review_owner_ref": self._review_owner_ref(transition),
        }
        return self._validate_summary(summary)

    def _validate_summary(self, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if set(value) != {"generation", "status", "candidate_id", "review_owner_ref"}:
            raise ActivityRefused("self-rewrite receipt contains unexpected fields")
        generation = value.get("generation")
        status = value.get("status")
        candidate_id = value.get("candidate_id")
        owner_ref = value.get("review_owner_ref")
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 0
            or not isinstance(status, str)
            or status not in {"complete", "awaiting-review"}
            or (candidate_id is not None and not isinstance(candidate_id, str))
            or not isinstance(owner_ref, Mapping)
            or set(owner_ref) != {"entity_id", "program_id"}
        ):
            raise ActivityRefused("self-rewrite receipt is invalid")
        if candidate_id is not None:
            candidate_id = self._safe_identifier(candidate_id, "candidate")
        entity_id = self._safe_identifier(owner_ref.get("entity_id"), "entity owner")
        owner_program = owner_ref.get("program_id")
        if owner_program is not None:
            owner_program = self._safe_identifier(owner_program, "review owner")
        return {
            "generation": generation,
            "status": status,
            "candidate_id": candidate_id,
            "review_owner_ref": {"entity_id": entity_id, "program_id": owner_program},
        }

    def _write_receipt(self, path: Path, summary: Mapping[str, Any]) -> None:
        body = json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)

    def _read_receipt(self, path: Path) -> Mapping[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ActivityRefused("self-rewrite activity receipt is unreadable") from exc
        if not isinstance(value, Mapping):
            raise ActivityRefused("self-rewrite activity receipt is not an object")
        return self._validate_summary(value)

    def _run(self, operation: str, parameters: Mapping[str, Any], *,
             program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        if self.entity is None:
            raise ActivityRefused("self-rewrite activity is not attached")
        current = _current_program(self.entity, program, self.activity_id, operation)
        if operation != "advance" or not isinstance(parameters, Mapping) or parameters:
            raise ActivityRefused("self-rewrite accepts only advance with empty parameters")
        if not isinstance(operation_id, str) or not operation_id:
            raise ActivityRefused("self-rewrite requires an operation identity")
        runner, owner_client, pending_review = self._runner_components()
        path = (
            self.entity.config.data_home / "activities" / self.activity_id
            / _identity(operation_id) / "receipt.json"
        )
        identity = {
            "activity_id": self.activity_id,
            "operation": operation,
            "program_id": current["program_id"],
            "parameters": {},
            "root": str(self.root),
            "variant": self.variant,
        }
        if _admit_intent(path, identity):
            initial_generation = self._current_generation()
            try:
                runner_receipt = runner(
                    self.root,
                    1,
                    owner_client=owner_client,
                )
            except pending_review:
                actual_generation = self._current_generation()
                if actual_generation != initial_generation:
                    raise ActivityRefused("pending review followed an unexpected generation change")
                summary = self._validate_summary({
                    "generation": initial_generation,
                    "status": "awaiting-review",
                    "candidate_id": None,
                    "review_owner_ref": self._review_owner_ref(None),
                })
            else:
                actual_generation = self._current_generation()
                if not isinstance(runner_receipt, Mapping):
                    raise ActivityRefused("self-rewrite runner returned a non-object receipt")
                summary = self._summary(
                    runner_receipt,
                    initial_generation=initial_generation,
                    actual_generation=actual_generation,
                )
            self._write_receipt(path, summary)
        else:
            summary = self._read_receipt(path)
        _field_result(self.entity, current, self.activity_id, operation, operation_id, summary)
        return summary


_PCSX2_MAX_OBSERVATION_BYTES = 1_048_576
_PCSX2_MAX_RELATE_RANGES = 256
_PCSX2_MAX_CANDIDATES = 16
_PCSX2_MAX_OPERATION_RECEIPTS = 256
_PCSX2_DECOMPILE_MAX_TOKENS = 1_536
_PCSX2_DECOMPILE_PSEUDOCODE_LIMIT = 4_000
_PCSX2_DECOMPILE_PROSE_LIMIT = 1_000
_PCSX2_PROMPT_LIMIT = 8_000
_PCSX2_MAX_CAPTURE_SAMPLES = 3_600
_PCSX2_MAX_FIELD_SAMPLES = 2_048
_PCSX2_MAX_PLAY_STEPS = 64
_PCSX2_MAX_CAPTURE_SECONDS = 300
_PCSX2_MAX_CAPTURE_BYTES = 64 * 1024 * 1024
_PCSX2_MAX_CAPTURE_EPISODES = 256
_PCSX2_RECEIPT_EPISODES = 32
_PCSX2_SESSION_ARTIFACT_BYTES = 16 * 1024 * 1024
_PCSX2_EXPECTED_PROCESS = "pcsx2-qt.exe"


def _plain_json(value: Any, label: str) -> Any:
    """Normalize hosted evidence into JSON-safe structures."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item, label) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item, label) for item in value]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ActivityRefused(f"{label} contains a non-finite number")
        return value
    raise ActivityRefused(f"{label} contains an unsupported evidence type")


def _bounded_json(value: Any, label: str,
                  limit: int = _PCSX2_MAX_OBSERVATION_BYTES) -> Any:
    body = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    if len(body.encode("utf-8")) > limit:
        raise ActivityRefused(f"{label} exceeds the bounded evidence size")
    return value


def _pcsx2_text(value: Any, label: str, limit: int = 256) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > limit
        or not all(32 <= ord(character) <= 126 for character in value)
    ):
        raise ActivityRefused(f"pcsx2 {label} is not bounded printable text")
    return value


def _pcsx2_identifier(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or not all(char.isascii() and (char.isalnum() or char in "._:-") for char in value)
    ):
        raise ActivityRefused(f"pcsx2 {label} is not a bounded identifier")
    return value


def _pcsx2_index(value: Any, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ActivityRefused(f"pcsx2 {label} must be an integer in {low}..{high}")
    return value


def _pcsx2_file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pcsx2_write_atomic(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _pcsx2_game_identity(identity: Any) -> tuple[str | None, str | None]:
    """Extract the PCSX2 cheat-file identity (serial and CRC) from live PINE data."""
    if not isinstance(identity, Mapping):
        return None, None
    serial = None
    for key in ("serial", "boot_serial", "game_id", "gameid", "disc_id", "gameID"):
        value = identity.get(key)
        if isinstance(value, str) and value.strip():
            serial = value.strip()
            break
    crc = None
    for key in (
        "crc", "pcsx2_crc", "crc32", "game_crc", "crc_hex", "game_uuid", "uuid",
    ):
        value = identity.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 0xFFFF_FFFF:
            crc = f"{value:08X}"
            break
        if isinstance(value, str) and value.strip():
            crc = value.strip()
            break
    if not serial or not crc:
        return None, None
    uppercase = serial.upper()
    compact = "".join(character for character in uppercase if character.isascii() and character.isalnum())
    if len(compact) == 9 and compact[:4].isalpha() and compact[4:].isdigit():
        serial = f"{compact[:4]}-{compact[4:]}"
    else:
        serial = "".join(
            character if (character.isascii() and (character.isalnum() or character in "._-"))
            else "-"
            for character in uppercase
        )
    crc = crc.upper().removeprefix("0X")
    if not serial or any(ch not in "0123456789ABCDEF" for ch in crc) or len(crc) > 8:
        return None, None
    return serial, crc.zfill(8)

def _pcsx2_identity_is_running(identity: Any) -> bool:
    if not isinstance(identity, Mapping):
        return False
    reported = []
    status_name = identity.get("status_name")
    if isinstance(status_name, str) and status_name.strip():
        reported.append(status_name.strip().lower() == "running")
    status = identity.get("status")
    if isinstance(status, str) and status.strip():
        reported.append(status.strip().lower() == "running")
    elif isinstance(status, int) and not isinstance(status, bool):
        reported.append(status == 0)
    return bool(reported) and all(reported)


def _validate_snapshot_changes(
    changed: Any,
) -> tuple[list[dict[str, int]], list[dict[str, int]], int]:
    if (
        not isinstance(changed, Mapping)
        or set(changed) != {
            "changed_ranges", "changed_pages", "changed_byte_count",
            "base_address", "page_size",
        }
    ):
        raise ActivityRefused("the snapshot comparison returned an unexpected structure")
    raw_ranges = changed["changed_ranges"]
    raw_pages = changed["changed_pages"]
    if not isinstance(raw_ranges, list) or not isinstance(raw_pages, list):
        raise ActivityRefused("the snapshot comparison returned non-list changes")
    _pcsx2_index(changed["base_address"], "snapshot base address", 0, 0xFFFF_FFFF)
    _pcsx2_index(changed["page_size"], "snapshot page size", 1, 0x1_0000_0000)
    changed_byte_count = _pcsx2_index(
        changed["changed_byte_count"], "changed byte count",
        0, _PCSX2_MAX_OBSERVATION_BYTES,
    )
    if len(raw_ranges) > _PCSX2_MAX_RELATE_RANGES:
        raise ActivityRefused("the snapshot comparison exceeds the bounded change budget")
    ranges: list[dict[str, int]] = []
    previous_end = -1
    for span in raw_ranges:
        if not isinstance(span, Mapping) or set(span) - {"start", "end", "bytes_before", "bytes_after"}:
            raise ActivityRefused("the snapshot comparison returned an invalid changed range")
        start = _pcsx2_index(span.get("start"), "changed range start", 0, 0xFFFF_FFFF)
        end = _pcsx2_index(span.get("end"), "changed range end", 1, 0x1_0000_0000)
        if end <= start:
            raise ActivityRefused("the snapshot comparison returned an empty changed range")
        if start < previous_end:
            raise ActivityRefused("the snapshot comparison returned unordered changed ranges")
        previous_end = end
        ranges.append({"start": start, "end": end})
    pages: list[dict[str, int]] = []
    previous_page = -1
    for page in raw_pages:
        if not isinstance(page, Mapping) or not {"page", "start", "end"} <= set(page):
            raise ActivityRefused("the snapshot comparison returned an invalid changed page")
        index = _pcsx2_index(page.get("page"), "changed page index", 0, 2**62)
        if index <= previous_page:
            raise ActivityRefused("the snapshot comparison returned unordered changed pages")
        previous_page = index
        pages.append({
            "page": index,
            "start": _pcsx2_index(page.get("start"), "changed page start", 0, 0xFFFF_FFFF),
            "end": _pcsx2_index(page.get("end"), "changed page end", 1, 0x1_0000_0000),
        })
    if changed_byte_count != sum(span["end"] - span["start"] for span in ranges):
        raise ActivityRefused("the snapshot comparison returned an inconsistent byte count")
    return ranges, pages, changed_byte_count


class PCSX2Activity:
    """Catalog a fixed PS2 ISO and bridge field-only live PCSX2 sensorimotor data.

    PINE remains strictly read-only.  Native field observation keeps exact raw
    bridge bytes in the activity home; adaptive transitions use the entity's
    existing field owner.  Virtual input is available only to a separately
    authorized ``field-act`` programme operation and is bounded by native
    foreground/PID, human-priority, and duration fences.
    """

    activity_id = "pcsx2"

    def __init__(self, *, iso_path: Path, data_home: Path,
                 pine_host: str = "127.0.0.1", pine_slot: int = 28_011,
                 pine_timeout: float = 2.0,
                 max_observation_bytes: int = 65_536,
                 xinput_slot: int = 0,
                 max_capture_samples: int = _PCSX2_MAX_CAPTURE_SAMPLES,
                 input_source: Any | None = None) -> None:
        self.iso_path = self._configured_iso(iso_path)
        self.data_home = self._configured_home(data_home)
        self.pine_host = self._configured_host(pine_host)
        self.pine_slot = _pcsx2_index(pine_slot, "PINE slot", 1, 65_535)
        self.pine_timeout = self._configured_timeout(pine_timeout)
        self.max_observation_bytes = _pcsx2_index(
            max_observation_bytes, "maximum observation size", 1, _PCSX2_MAX_OBSERVATION_BYTES,
        )
        self.xinput_slot = _pcsx2_index(xinput_slot, "XInput slot", 0, 3)
        self.max_capture_samples = _pcsx2_index(
            max_capture_samples, "maximum capture samples", 2, _PCSX2_MAX_CAPTURE_SAMPLES,
        )
        self._gameplay_input_source = input_source
        self.entity: Any | None = None
        self._lock = threading.RLock()
        self._iso_sha256: str | None = None
        self._atlas: Any | None = None
    # -- host configuration --------------------------------------------------

    @staticmethod
    def _configured_iso(value: Any) -> Path:
        if not isinstance(value, (str, Path)):
            raise ActivityRefused("the fixed pcsx2 ISO must be a path")
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ActivityRefused("the fixed pcsx2 ISO path must be absolute")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ActivityRefused("the fixed pcsx2 ISO does not exist") from exc
        if not resolved.is_file():
            raise ActivityRefused("the fixed pcsx2 ISO is not a regular file")
        return resolved

    @staticmethod
    def _configured_home(value: Any) -> Path:
        if not isinstance(value, (str, Path)):
            raise ActivityRefused("the pcsx2 data home must be a path")
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ActivityRefused("the pcsx2 data home must be absolute")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ActivityRefused("the pcsx2 data home does not exist") from exc
        if not resolved.is_dir():
            raise ActivityRefused("the pcsx2 data home is not an existing directory")
        return resolved

    @staticmethod
    def _configured_host(value: Any) -> str:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 253
            or not all(char.isascii() and (char.isalnum() or char in ".-") for char in value)
        ):
            raise ActivityRefused("the pcsx2 PINE host is not a bounded host name")
        return value

    @staticmethod
    def _configured_timeout(value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ActivityRefused("the pcsx2 PINE timeout must be a number")
        if not 0 < float(value) <= 60:
            raise ActivityRefused("the pcsx2 PINE timeout must be within 0..60 seconds")
        return float(value)

    # -- hosted surface -------------------------------------------------------

    def attach(self, entity: Any) -> None:
        self.entity = entity

    def describe(self) -> Mapping[str, Any]:
        return {
            "activity_id": self.activity_id,
            "operations": [
                "catalog", "observe", "capture-session", "relate", "decompile",
                "field-observe", "field-act", "field-play",
            ],
            "source": str(self.iso_path),
            "data_home": str(self.data_home),
            "pine": {"host": self.pine_host, "slot": self.pine_slot, "read_only": True},
            "input": {
                "backend": "windows-xinput",
                "slot": self.xinput_slot,
                "process": _PCSX2_EXPECTED_PROCESS,
                "foreground_only": True,
            },
            "field_input": {
                "backend": "native-pcsx2-sio",
                "physical_source": "pad-events-consumed-by-the-emulator",
                "requires_connected_xinput_device": False,
            },
            "effect": (
                "read-only PINE catalog and bounded observation; native v1 field "
                "baseline/deltas plus SIO-consumed pad events; owner-backed temporal "
                "learning/action selection; virtual pad actions only for an active "
                "programme-authorized field-act or field-play operation, with physical "
                "input priority"
            ),
            "native_field": {
                "protocol": "CASSIIPC-v1",
                "raw_evidence": "activity-home",
                "max_action_frames": 120,
                "cold_inquiry_default_action_frames": 2,
                "max_play_steps": _PCSX2_MAX_PLAY_STEPS,
                "max_play_timeout_seconds": 600,
                "virtual_input_default": "disabled",
            },
            "max_observation_bytes": self.max_observation_bytes,
            "max_capture_samples": self.max_capture_samples,
            "max_capture_seconds": _PCSX2_MAX_CAPTURE_SECONDS,
        }

    # -- shared plumbing ------------------------------------------------------

    def _pcsx2(self) -> Any:
        try:
            import pcsx2  # type: ignore[import-not-found]
        except Exception as exc:
            raise ActivityRefused("the pcsx2 package is not importable on this host") from exc
        missing = [
            name
            for name in ("PineClient", "PineError", "catalog_iso", "FunctionAtlas", "compare_snapshots")
            if not hasattr(pcsx2, name)
        ]
        if missing:
            raise ActivityRefused(
                "the pcsx2 package lacks its contract interface: " + ",".join(missing)
            )
        return pcsx2

    def _hash_iso(self) -> str:
        digest = hashlib.sha256()
        with self.iso_path.open("rb") as handle:
            while chunk := handle.read(8 * 1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def _iso_digest(self) -> str:
        if self._iso_sha256 is None:
            self._iso_sha256 = self._hash_iso()
        return self._iso_sha256

    def _load_atlas(self) -> Any:
        if self._atlas is None:
            pcsx2 = self._pcsx2()
            self._atlas = pcsx2.catalog_iso(self.iso_path, self.data_home / "atlas")
        identity = getattr(self._atlas, "identity", None)
        digest = identity.get("iso_sha256") if isinstance(identity, Mapping) else None
        if (
            self._iso_sha256 is None
            and isinstance(digest, str)
            and len(digest) == 64
            and all(character in "0123456789abcdef" for character in digest)
        ):
            self._iso_sha256 = digest
        return self._atlas

    @staticmethod
    def _require_configured_game(atlas: Any, pine_identity: Any) -> tuple[str, str]:
        atlas_identity = getattr(atlas, "identity", None)
        expected = _pcsx2_game_identity(atlas_identity)
        if None in expected:
            raise ActivityRefused("the fixed ISO atlas lacks a complete game identity")
        live = _pcsx2_game_identity(pine_identity)
        if None in live:
            raise ActivityRefused("PINE did not report a complete running-game identity")
        if not _pcsx2_identity_is_running(pine_identity):
            raise ActivityRefused("PINE did not report a running game")
        if live != expected:
            raise ActivityRefused(
                "the running PINE game does not match the fixed ISO identity"
            )
        return live[0], live[1]  # type: ignore[return-value]

    def _admitted(self, path: Path, identity: Mapping[str, Any],
                  work: Any, replay: Any) -> Mapping[str, Any]:
        if _admit_intent(path, identity):
            summary = work()
            _pcsx2_write_atomic(
                path,
                json.dumps(
                    dict(summary), ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), allow_nan=False,
                ).encode("utf-8"),
            )
            return summary
        return replay()

    @staticmethod
    def _field_observed_at(receipt_path: Path) -> str:
        """Persist one field timestamp so a receipt replay learns the same document."""
        path = receipt_path.parent / "field-observed-at.txt"
        if path.is_file():
            try:
                value = path.read_text(encoding="utf-8").strip()
                parsed = datetime.fromisoformat(value)
            except (OSError, ValueError) as exc:
                raise ActivityRefused("the stored field timestamp is invalid") from exc
            if parsed.tzinfo is None or len(value) > 64:
                raise ActivityRefused("the stored field timestamp is invalid")
            return value
        value = datetime.now(timezone.utc).isoformat()
        _pcsx2_write_atomic(path, (value + "\n").encode("utf-8"))
        return value

    @staticmethod
    def _read_receipt(path: Path, label: str) -> Mapping[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ActivityRefused(f"the stored {label} is unreadable") from exc
        if not isinstance(value, Mapping):
            raise ActivityRefused(f"the stored {label} is not an object")
        return value

    @staticmethod
    def _replayed(summary: Mapping[str, Any], keys: set[str], label: str) -> Mapping[str, Any]:
        if set(summary) != keys or summary.get("status") != "COMPLETE":
            raise ActivityRefused(f"the stored {label} is invalid")
        return summary

    def _run(self, operation: str, parameters: Mapping[str, Any], *,
             program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        if self.entity is None:
            raise ActivityRefused("pcsx2 activity is not attached")
        if not isinstance(operation_id, str) or not operation_id:
            raise ActivityRefused("pcsx2 requires an operation identity")
        handlers = {
            "catalog": self._catalog,
            "observe": self._observe,
            "capture-session": self._capture_session,
            "relate": self._relate,
            "decompile": self._decompile,
            "field-observe": self._field_observe,
            "field-act": self._field_act,
            "field-play": self._field_play,
        }
        handler = handlers.get(operation)
        if handler is None:
            raise ActivityRefused(
                "pcsx2 accepts only catalog, observe, capture-session, relate, decompile, "
                "field-observe, field-act, or field-play"
            )
        current = _current_program(self.entity, program, self.activity_id, operation)
        path = self.data_home / "operations" / _identity(operation_id) / "receipt.json"
        summary = handler(current, parameters, operation_id, path)
        _field_result(
            self.entity, current, self.activity_id, operation, operation_id, summary,
            observed_at=self._field_observed_at(path),
        )
        return summary

    def run(self, operation: str, parameters: Mapping[str, Any], *,
            program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        with self._lock:
            return self._run(operation, parameters, program=program, operation_id=operation_id)

    # -- catalog --------------------------------------------------------------

    def _catalog(self, current: Mapping[str, Any], parameters: Mapping[str, Any],
                 operation_id: str, path: Path) -> Mapping[str, Any]:
        if not isinstance(parameters, Mapping) or parameters:
            raise ActivityRefused("pcsx2 catalog accepts an empty bounded object")
        identity = {
            "activity_id": self.activity_id,
            "operation": "catalog",
            "program_id": current["program_id"],
            "parameters": {},
            "iso_path": str(self.iso_path),
            "data_home": str(self.data_home),
            "pine": {"host": self.pine_host, "slot": self.pine_slot},
        }

        def work() -> Mapping[str, Any]:
            atlas = self._load_atlas()
            catalog = _bounded_json(_plain_json(atlas.summary(), "atlas summary"), "atlas summary")
            atlas_identity = _bounded_json(
                _plain_json(atlas.identity, "atlas identity"), "atlas identity",
            )
            return {
                "status": "COMPLETE",
                "catalog": catalog,
                "atlas_identity": atlas_identity,
                "artifact": self._atlas_artifact(catalog),
                "receipt_path": str(path),
            }

        def replay() -> Mapping[str, Any]:
            summary = self._read_receipt(path, "catalog receipt")
            return self._replayed(
                summary, {"status", "catalog", "atlas_identity", "artifact", "receipt_path"},
                "catalog receipt",
            )

        return self._admitted(path, identity, work, replay)

    @staticmethod
    def _atlas_artifact(catalog: Mapping[str, Any]) -> Mapping[str, Any]:
        artifact: dict[str, Any] = {
            "atlas_path": None, "atlas_sha256": None, "sym_path": None, "sym_sha256": None,
        }
        paths = catalog.get("paths")
        if isinstance(paths, Mapping):
            flat = {"atlas_path": paths.get("atlas"), "sym_path": paths.get("sym")}
        else:
            flat = catalog
        for key in ("atlas_path", "sym_path"):
            value = flat.get(key)
            if isinstance(value, str) and value:
                source = Path(value)
                artifact[key] = str(source)
                artifact[key.replace("_path", "_sha256")] = (
                    _pcsx2_file_digest(source) if source.is_file() else None
                )
        return artifact

    # -- observe --------------------------------------------------------------

    def _observe(self, current: Mapping[str, Any], parameters: Mapping[str, Any],
                 operation_id: str, path: Path) -> Mapping[str, Any]:
        if not isinstance(parameters, Mapping) or set(parameters) - {"address", "size", "label", "binding_id"}:
            raise ActivityRefused("pcsx2 observe accepts only address, size, label, and binding_id")
        address = _pcsx2_index(parameters.get("address", 0), "observation address", 0, 0xFFFF_FFFF)
        size = _pcsx2_index(
            parameters.get("size", 4_096), "observation size", 1, self.max_observation_bytes,
        )
        if address + size > 0x1_0000_0000:
            raise ActivityRefused("pcsx2 observation window crosses the 32-bit address space")
        label = _pcsx2_text(parameters.get("label"), "observation label")
        binding_id = (
            _pcsx2_identifier(parameters["binding_id"], "surface binding")
            if "binding_id" in parameters else None
        )
        identity = {
            "activity_id": self.activity_id,
            "operation": "observe",
            "program_id": current["program_id"],
            "parameters": {"address": address, "size": size, "label": label, "binding_id": binding_id},
            "iso_path": str(self.iso_path),
            "data_home": str(self.data_home),
            "pine": {"host": self.pine_host, "slot": self.pine_slot},
        }

        def work() -> Mapping[str, Any]:
            observation_id = _identity(operation_id)
            pcsx2 = self._pcsx2()
            atlas = self._load_atlas()
            surface = None
            try:
                with pcsx2.PineClient(
                    host=self.pine_host, slot=self.pine_slot,
                    timeout=self.pine_timeout, allow_effects=False,
                ) as client:
                    pine_identity = _bounded_json(
                        _plain_json(client.identity(), "PINE identity"), "PINE identity",
                    )
                    live_before = self._require_configured_game(atlas, pine_identity)
                    if binding_id is not None:
                        surface = self._capture_surface(binding_id, current)
                    data = client.read(address, size)
                    pine_identity_after = _bounded_json(
                        _plain_json(client.identity(), "PINE identity"), "PINE identity",
                    )
                    live_after = self._require_configured_game(atlas, pine_identity_after)
                    if live_after != live_before:
                        raise ActivityRefused("the running PINE game changed during observation")
                    pine_identity = pine_identity_after
            except pcsx2.PineError as exc:
                raise ActivityRefused(f"PINE observation failed: {exc}") from exc
            if not isinstance(data, (bytes, bytearray)) or len(data) != size:
                raise ActivityRefused("PINE returned a bounded read of the wrong size")
            data = bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            binary_path = self._persist_observation_binary(sha, data)
            metadata = {
                "observation_id": observation_id,
                "activity_id": self.activity_id,
                "iso_sha256": self._iso_digest(),
                "address": address,
                "size": size,
                "label": label,
                "data_sha256": sha,
                "pine_identity": pine_identity,
                "pine": {"host": self.pine_host, "slot": self.pine_slot},
                "surface": surface,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
            metadata_path = self.data_home / "observations" / f"{observation_id}.json"
            _pcsx2_write_atomic(
                metadata_path,
                json.dumps(
                    metadata, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), allow_nan=False,
                ).encode("utf-8"),
            )
            return {
                "status": "COMPLETE",
                "observation_id": observation_id,
                "pine_identity": pine_identity,
                "pine": {"host": self.pine_host, "slot": self.pine_slot},
                "address": address,
                "size": size,
                "label": label,
                "sha256": sha,
                "artifact": {
                    "sha256": sha,
                    "memory_path": str(binary_path),
                    "metadata_path": str(metadata_path),
                },
                "surface": surface,
                "receipt_path": str(path),
            }

        def replay() -> Mapping[str, Any]:
            summary = self._read_receipt(path, "observation receipt")
            return self._replayed(
                summary,
                {"status", "observation_id", "pine_identity", "pine", "address", "size",
                 "label", "sha256", "artifact", "surface", "receipt_path"},
                "observation receipt",
            )

        return self._admitted(path, identity, work, replay)

    def _persist_observation_binary(self, sha: str, data: bytes) -> Path:
        path = self.data_home / "observations" / "data" / f"{sha}.bin"
        if path.is_file():
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise ActivityRefused("the observation artifact digest is inconsistent")
            return path
        _pcsx2_write_atomic(path, data)
        return path

    # -- captured gameplay ----------------------------------------------------

    @staticmethod
    def _gameplay_module() -> Any:
        try:
            module = importlib.import_module("pcsx2.gameplay")
        except Exception as exc:
            raise ActivityRefused("the PCSX2 gameplay input adapter is unavailable") from exc
        missing = [
            name
            for name in (
                "GameplayFocusLost",
                "GameplayInputError",
                "XInputSource",
                "meaningful_transitions",
            )
            if not hasattr(module, name)
        ]
        if missing:
            raise ActivityRefused(
                "the PCSX2 gameplay adapter lacks its contract interface: "
                + ",".join(missing)
            )
        return module

    def _gameplay_source(self, gameplay: Any) -> Any:
        source = self._gameplay_input_source
        if source is None:
            try:
                source = gameplay.XInputSource(
                    slot=self.xinput_slot,
                    expected_process=_PCSX2_EXPECTED_PROCESS,
                )
            except gameplay.GameplayInputError as exc:
                raise ActivityRefused(f"PCSX2 controller capture is unavailable: {exc}") from exc
            self._gameplay_input_source = source
        if not all(
            callable(getattr(source, name, None))
            for name in (
                "describe", "begin_session", "assert_foreground",
                "assert_pine_endpoint", "sample", "end_session",
            )
        ):
            raise ActivityRefused("the PCSX2 gameplay input source is invalid")
        try:
            description = self._input_source_identity(source.describe(), bound=False)
        except gameplay.GameplayInputError as exc:
            raise ActivityRefused(f"PCSX2 controller capture is unavailable: {exc}") from exc
        if description["slot"] != self.xinput_slot:
            raise ActivityRefused("the PCSX2 gameplay input source uses another controller slot")
        return source

    def _input_source_identity(self, value: Any, *, bound: bool) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ActivityRefused("the PCSX2 gameplay input source returned an invalid identity")
        backend = value.get("backend")
        process = value.get("process")
        slot = value.get("slot")
        pid = value.get("pid")
        if backend != "windows-xinput" or process != _PCSX2_EXPECTED_PROCESS:
            raise ActivityRefused("the PCSX2 gameplay input source is not host-bound")
        slot = _pcsx2_index(slot, "captured XInput slot", 0, 3)
        if pid is not None:
            pid = _pcsx2_index(pid, "captured PCSX2 process", 1, 0xFFFF_FFFF)
        if bound and pid is None:
            raise ActivityRefused("the PCSX2 gameplay input source did not bind a process")
        return {
            "backend": backend,
            "slot": slot,
            "process": process,
            "pid": pid,
            "scope": "foreground-process-session",
        }

    def _field_observe(self, current: Mapping[str, Any], parameters: Mapping[str, Any],
                       operation_id: str, path: Path) -> Mapping[str, Any]:
        return self._field_loop(
            current, parameters, operation_id, path, operation="field-observe",
            allow_actions=False,
        )

    def _field_act(self, current: Mapping[str, Any], parameters: Mapping[str, Any],
                   operation_id: str, path: Path) -> Mapping[str, Any]:
        return self._field_loop(
            current, parameters, operation_id, path, operation="field-act",
            allow_actions=True,
        )

    def _field_play(self, current: Mapping[str, Any], parameters: Mapping[str, Any],
                    operation_id: str, path: Path) -> Mapping[str, Any]:
        return self._field_loop(
            current, parameters, operation_id, path, operation="field-play",
            allow_actions=True, allow_steps=True,
        )

    def _field_loop(self, current: Mapping[str, Any], parameters: Mapping[str, Any],
                    operation_id: str, path: Path, *, operation: str,
                    allow_actions: bool, allow_steps: bool = False) -> Mapping[str, Any]:
        allowed = {"samples", "timeout_seconds"}
        if allow_actions:
            allowed.add("max_action_frames")
        if allow_steps:
            allowed.add("steps")
        if not isinstance(parameters, Mapping) or set(parameters) - allowed:
            options = "samples and timeout_seconds"
            if allow_actions:
                options += ", and max_action_frames"
            if allow_steps:
                options += ", and steps"
            raise ActivityRefused(f"pcsx2 {operation} accepts only {options}")
        samples = _pcsx2_index(
            parameters.get("samples", 16), "field-loop sample count", 1,
            min(self.max_capture_samples, _PCSX2_MAX_FIELD_SAMPLES),
        )
        max_action_frames = _pcsx2_index(
            parameters.get("max_action_frames", 2) if allow_actions else 2,
            "field action duration", 1, 120,
        )
        steps = _pcsx2_index(
            parameters.get("steps", 8) if allow_steps else 1,
            "field play step count", 1, _PCSX2_MAX_PLAY_STEPS,
        )
        # Each step carries its own minute of pad action and field decision
        # compute; a play session's fence scales with its declared step budget.
        timeout_limit = min(600.0, 60.0 * steps) if allow_steps else 60.0
        refusal = f"PCSX2 field-loop timeout must be within 0..{int(timeout_limit)} seconds"
        timeout_value = parameters.get("timeout_seconds", timeout_limit)
        if isinstance(timeout_value, bool) or not isinstance(timeout_value, (int, float)):
            raise ActivityRefused(refusal)
        try:
            timeout_seconds = float(timeout_value)
        except (OverflowError, ValueError) as exc:
            raise ActivityRefused(refusal) from exc
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= timeout_limit:
            raise ActivityRefused(refusal)
        normalized = {
            "samples": samples,
            "timeout_seconds": timeout_seconds,
            "max_action_frames": max_action_frames,
        }
        if allow_steps:
            normalized["steps"] = steps
        atlas = self._load_atlas()
        serial, crc = _pcsx2_game_identity(getattr(atlas, "identity", None))
        if serial is None or crc is None:
            raise ActivityRefused("the configured PCSX2 ISO atlas lacks serial and CRC identity")
        iso_sha256 = self._iso_digest()
        owner = getattr(self.entity, "_field_owner", None)
        field_lock = getattr(self.entity, "_field_lock", None)
        if (
            owner is None
            or not callable(getattr(field_lock, "__enter__", None))
            or not callable(getattr(field_lock, "__exit__", None))
        ):
            raise ActivityRefused("the entity has no attached field-intelligence owner")
        input_configuration = {
            "backend": "windows-xinput",
            "slot": self.xinput_slot,
            "process": _PCSX2_EXPECTED_PROCESS,
            "scope": "foreground-process-session",
        }
        identity = {
            "activity_id": self.activity_id,
            "operation": operation,
            "program_id": current["program_id"],
            "parameters": normalized,
            "iso_path": str(self.iso_path),
            "iso_sha256": iso_sha256,
            "game": {"serial": serial, "pcsx2_crc": crc},
            "input": input_configuration,
            "native_protocol": "CASSIIPC-v1",
        }
        artifact_home = path.parent / "field-evidence"

        def work() -> Mapping[str, Any]:
            bridge = None
            field = None
            gameplay = None
            source = None
            source_started = False
            client = None
            try:
                bridge = importlib.import_module("pcsx2.native_bridge")
                field = importlib.import_module("pcsx2.field")
                if not callable(getattr(bridge, "NativeBridgeClient", None)) or not callable(
                    getattr(field, "run_field_loop", None)
                ):
                    raise ActivityRefused("the native PCSX2 field-loop contract is incomplete")
                gameplay = self._gameplay_module()
                source = self._gameplay_source(gameplay)
                raw_source_identity = source.begin_session()
                source_started = True
                source_identity = self._input_source_identity(
                    raw_source_identity, bound=True,
                )

                def foreground_guard() -> bool:
                    try:
                        source.assert_foreground()
                        refreshed = _current_program(
                            self.entity, current, self.activity_id, operation,
                        )
                        return refreshed.get("program_id") == current.get("program_id")
                    except Exception:
                        return False

                client = bridge.NativeBridgeClient(
                    expected_server_pid=source_identity["pid"],
                    connect_timeout=min(timeout_seconds, 10.0),
                    io_timeout=min(timeout_seconds, 5.0),
                )
                outcome = field.run_field_loop(
                    client=client,
                    owner=owner,
                    field_lock=field_lock,
                    atlas=atlas,
                    program_id=current["program_id"],
                    operation_id=operation_id,
                    artifact_home=artifact_home,
                    expected_serial=serial,
                    expected_crc=int(crc, 16),
                    samples=samples,
                    allow_actions=allow_actions,
                    foreground_guard=foreground_guard,
                    timeout_seconds=timeout_seconds,
                    max_action_frames=max_action_frames,
                    steps=steps,
                )
                if not isinstance(outcome, Mapping) or outcome.get("status") != "COMPLETE":
                    raise ActivityRefused("native PCSX2 field loop returned an incomplete receipt")
                field_summary = _plain_json(outcome, "native field-loop receipt")
                summary = {
                    "status": "COMPLETE",
                    "operation": operation,
                    "operation_id": operation_id,
                    "program_id": current["program_id"],
                    "parameters": normalized,
                    "iso_path": str(self.iso_path),
                    "iso_sha256": iso_sha256,
                    "game": {"serial": serial, "pcsx2_crc": crc},
                    "input_configuration": input_configuration,
                    "input_source": source_identity,
                    "field": field_summary,
                    "receipt_path": str(path),
                }
                return _bounded_json(
                    summary, "native field-loop receipt", limit=self.max_observation_bytes,
                )
            except ActivityRefused:
                raise
            except Exception as exc:
                raise ActivityRefused(f"native PCSX2 field loop failed: {exc}") from exc
            finally:
                if client is not None:
                    try:
                        client.close()
                    except Exception:
                        pass
                if source_started and source is not None:
                    source.end_session()

        def replay() -> Mapping[str, Any]:
            summary = self._read_receipt(path, "native field-loop receipt")
            expected_keys = {
                "status", "operation", "operation_id", "program_id", "parameters",
                "iso_path", "iso_sha256", "game", "input_configuration",
                "input_source", "field", "receipt_path",
            }
            stored = self._replayed(summary, expected_keys, "native field-loop receipt")
            source_identity = stored.get("input_source")
            if not isinstance(source_identity, Mapping) or set(source_identity) != {
                "backend", "slot", "process", "pid", "scope",
            }:
                raise ActivityRefused("the stored native field-loop input identity is invalid")
            normalized_source = self._input_source_identity(source_identity, bound=True)
            if (
                dict(source_identity) != dict(normalized_source)
                or source_identity["slot"] != self.xinput_slot
                or source_identity["scope"] != input_configuration["scope"]
            ):
                raise ActivityRefused("the stored native field-loop input identity does not match")
            field_summary = stored.get("field")
            if (
                stored.get("operation") != operation
                or stored.get("operation_id") != operation_id
                or stored.get("program_id") != current["program_id"]
                or stored.get("parameters") != normalized
                or stored.get("iso_path") != str(self.iso_path)
                or stored.get("iso_sha256") != iso_sha256
                or stored.get("game") != {"serial": serial, "pcsx2_crc": crc}
                or stored.get("input_configuration") != input_configuration
                or stored.get("receipt_path") != str(path)
                or not isinstance(field_summary, Mapping)
                or field_summary.get("program_id") != current["program_id"]
                or field_summary.get("operation_id") != operation_id
            ):
                raise ActivityRefused("the stored native field-loop receipt does not match")
            return stored

        return self._admitted(path, identity, work, replay)




    def _capture_session(self, current: Mapping[str, Any], parameters: Mapping[str, Any],
                         operation_id: str, path: Path) -> Mapping[str, Any]:
        allowed = {"address", "size", "label", "samples", "sample_hz"}
        if not isinstance(parameters, Mapping) or set(parameters) - allowed:
            raise ActivityRefused(
                "pcsx2 capture-session accepts only address, size, label, samples, and sample_hz"
            )
        address = _pcsx2_index(
            parameters.get("address", 0), "capture address", 0, 0xFFFF_FFFF,
        )
        size = _pcsx2_index(
            parameters.get("size", 4_096), "capture size", 1, self.max_observation_bytes,
        )
        if address + size > 0x1_0000_0000:
            raise ActivityRefused("pcsx2 capture window crosses the 32-bit address space")
        label = _pcsx2_text(parameters.get("label"), "capture label")
        samples = _pcsx2_index(
            parameters.get("samples", 100),
            "capture sample count", 2, self.max_capture_samples,
        )
        sample_hz = _pcsx2_index(
            parameters.get("sample_hz", 10), "capture sample rate", 1, 60,
        )
        if samples > sample_hz * _PCSX2_MAX_CAPTURE_SECONDS:
            raise ActivityRefused("pcsx2 capture-session exceeds the bounded duration")
        if samples * size > _PCSX2_MAX_CAPTURE_BYTES:
            raise ActivityRefused("pcsx2 capture-session exceeds the bounded memory budget")
        session_id = _identity(operation_id)
        normalized = {
            "address": address,
            "size": size,
            "label": label,
            "samples": samples,
            "sample_hz": sample_hz,
        }
        identity = {
            "activity_id": self.activity_id,
            "operation": "capture-session",
            "program_id": current["program_id"],
            "parameters": normalized,
            "iso_path": str(self.iso_path),
            "data_home": str(self.data_home),
            "pine": {"host": self.pine_host, "slot": self.pine_slot},
            "input": {
                "backend": "windows-xinput",
                "slot": self.xinput_slot,
                "process": _PCSX2_EXPECTED_PROCESS,
            },
        }

        def work() -> Mapping[str, Any]:
            gameplay = self._gameplay_module()
            source = self._gameplay_source(gameplay)
            pcsx2 = self._pcsx2()
            atlas = self._load_atlas()
            rows: list[dict[str, Any]] = []
            episodes: list[dict[str, Any]] = []
            blobs: dict[str, bytes] = {}
            previous_state: Mapping[str, Any] | None = None
            pending: dict[str, Any] | None = None
            focus_gaps = 0
            unresolved_episodes = 0
            transition_samples = 0
            transition_count = 0

            def record_focus_gap(sequence: int, observed_ns: int) -> None:
                nonlocal focus_gaps, previous_state, pending, unresolved_episodes
                rows.append({
                    "seq": sequence,
                    "monotonic_ns": observed_ns,
                    "status": "focus-gap",
                })
                focus_gaps += 1
                previous_state = None
                if pending is not None:
                    unresolved_episodes += 1
                    pending = None
            started_ns = time.monotonic_ns()
            ended_ns = started_ns
            source_identity: Mapping[str, Any] | None = None
            pine_identity: Mapping[str, Any] | None = None
            try:
                with pcsx2.PineClient(
                    host=self.pine_host, slot=self.pine_slot,
                    timeout=self.pine_timeout, allow_effects=False,
                ) as client:
                    pine_identity = _bounded_json(
                        _plain_json(client.identity(), "PINE identity"), "PINE identity",
                    )
                    live_game = self._require_configured_game(atlas, pine_identity)
                    try:
                        source_identity = self._input_source_identity(
                            source.begin_session(), bound=True,
                        )
                    except (gameplay.GameplayFocusLost, gameplay.GameplayInputError) as exc:
                        raise ActivityRefused(
                            f"PCSX2 controller capture could not begin: {exc}"
                        ) from exc
                    period_ns = 1_000_000_000 // sample_hz
                    started_ns = time.monotonic_ns()
                    deadline_ns = (
                        started_ns
                        + int(_PCSX2_MAX_CAPTURE_SECONDS * 1_000_000_000)
                    )
                    try:
                        try:
                            source.assert_pine_endpoint(self.pine_host, self.pine_slot)
                        except (
                            gameplay.GameplayFocusLost,
                            gameplay.GameplayInputError,
                        ) as exc:
                            raise ActivityRefused(
                                f"PCSX2 PINE ownership could not be verified: {exc}"
                            ) from exc
                        for sequence in range(samples):
                            now_ns = time.monotonic_ns()
                            if now_ns >= deadline_ns:
                                raise ActivityRefused(
                                    "pcsx2 capture-session exceeded its wall-clock deadline"
                                )
                            target_ns = started_ns + sequence * period_ns
                            remaining_ns = target_ns - now_ns
                            if remaining_ns > 0:
                                time.sleep(remaining_ns / 1_000_000_000)
                            if time.monotonic_ns() >= deadline_ns:
                                raise ActivityRefused(
                                    "pcsx2 capture-session exceeded its wall-clock deadline"
                                )
                            if sequence and sequence % sample_hz == 0:
                                checked = _bounded_json(
                                    _plain_json(client.identity(), "PINE identity"),
                                    "PINE identity",
                                )
                                if self._require_configured_game(atlas, checked) != live_game:
                                    raise ActivityRefused(
                                        "the running PINE game changed during gameplay capture"
                                    )
                                pine_identity = checked
                            try:
                                raw_state = source.sample()
                                input_monotonic_ns = time.monotonic_ns()
                            except gameplay.GameplayFocusLost:
                                record_focus_gap(sequence, time.monotonic_ns())
                                continue
                            except gameplay.GameplayInputError as exc:
                                raise ActivityRefused(
                                    f"PCSX2 controller capture failed: {exc}"
                                ) from exc
                            if input_monotonic_ns >= deadline_ns:
                                raise ActivityRefused(
                                    "pcsx2 capture-session exceeded its wall-clock deadline"
                                )
                            state = _bounded_json(
                                _plain_json(raw_state, "XInput state"),
                                "XInput state", limit=4_096,
                            )
                            if not isinstance(state, Mapping):
                                raise ActivityRefused(
                                    "the PCSX2 gameplay input source returned an invalid state"
                                )
                            data = client.read(address, size)
                            memory_monotonic_ns = time.monotonic_ns()
                            if not isinstance(data, (bytes, bytearray)) or len(data) != size:
                                raise ActivityRefused(
                                    "PINE returned a gameplay read of the wrong size"
                                )
                            try:
                                source.assert_foreground()
                            except gameplay.GameplayFocusLost:
                                record_focus_gap(sequence, time.monotonic_ns())
                                continue
                            except gameplay.GameplayInputError as exc:
                                raise ActivityRefused(
                                    f"PCSX2 controller capture failed: {exc}"
                                ) from exc
                            if time.monotonic_ns() >= deadline_ns:
                                raise ActivityRefused(
                                    "pcsx2 capture-session exceeded its wall-clock deadline"
                                )
                            data = bytes(data)
                            sha = hashlib.sha256(data).hexdigest()
                            blobs.setdefault(sha, data)
                            try:
                                transitions = gameplay.meaningful_transitions(
                                    previous_state, state,
                                )
                            except gameplay.GameplayInputError as exc:
                                raise ActivityRefused(
                                    f"PCSX2 controller state was invalid: {exc}"
                                ) from exc
                            transitions = _bounded_json(
                                _plain_json(transitions, "controller transitions"),
                                "controller transitions", limit=16_384,
                            )
                            if not isinstance(transitions, list):
                                raise ActivityRefused(
                                    "the PCSX2 gameplay adapter returned invalid transitions"
                                )
                            if pending is not None:
                                episodes.append(self._session_episode(
                                    pcsx2, atlas, session_id, pending,
                                    {
                                        "seq": sequence,
                                        "memory_monotonic_ns": memory_monotonic_ns,
                                        "sha256": sha,
                                        "data": data,
                                    },
                                    address,
                                ))
                                pending = None
                            row = {
                                "seq": sequence,
                                "input_monotonic_ns": input_monotonic_ns,
                                "memory_monotonic_ns": memory_monotonic_ns,
                                "status": "captured",
                                "input": state,
                                "transitions": transitions,
                                "snapshot": {"sha256": sha, "size": size},
                            }
                            rows.append(row)
                            if transitions:
                                transition_samples += 1
                                transition_count += len(transitions)
                                if len(episodes) < _PCSX2_MAX_CAPTURE_EPISODES:
                                    pending = {
                                        "seq": sequence,
                                        "input_monotonic_ns": input_monotonic_ns,
                                        "sha256": sha,
                                        "data": data,
                                        "transitions": transitions,
                                    }
                                else:
                                    unresolved_episodes += 1
                            previous_state = state
                        ended_ns = time.monotonic_ns()
                    finally:
                        source.end_session()
                    pine_identity_after = _bounded_json(
                        _plain_json(client.identity(), "PINE identity"), "PINE identity",
                    )
                    if self._require_configured_game(atlas, pine_identity_after) != live_game:
                        raise ActivityRefused(
                            "the running PINE game changed during gameplay capture"
                        )
                    pine_identity = pine_identity_after
            except pcsx2.PineError as exc:
                raise ActivityRefused(f"PINE gameplay capture failed: {exc}") from exc
            if pending is not None:
                unresolved_episodes += 1
            captured = sum(row["status"] == "captured" for row in rows)
            if captured == 0:
                raise ActivityRefused(
                    "the gameplay capture saw no controller sample while PCSX2 was foreground"
                )
            for sha, data in blobs.items():
                self._persist_observation_binary(sha, data)
            controls, functions = self._aggregate_session_evidence(episodes, rows)
            manifest = {
                "schema": "cassi-pcsx2-gameplay-v1",
                "activity_id": self.activity_id,
                "session_id": session_id,
                "operation_id": operation_id,
                "iso_sha256": self._iso_digest(),
                "label": label,
                "window": {"address": address, "size": size},
                "pine": {"host": self.pine_host, "slot": self.pine_slot},
                "pine_identity": pine_identity,
                "input_source": source_identity,
                "sample_hz": sample_hz,
                "started_monotonic_ns": started_ns,
                "ended_monotonic_ns": ended_ns,
                "samples": rows,
                "episodes": episodes,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
            _bounded_json(
                manifest, "gameplay session artifact",
                limit=_PCSX2_SESSION_ARTIFACT_BYTES,
            )
            manifest_body = json.dumps(
                manifest, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
            manifest_sha = hashlib.sha256(manifest_body).hexdigest()
            manifest_path = self.data_home / "sessions" / f"{session_id}.json"
            _pcsx2_write_atomic(manifest_path, manifest_body)
            compact_episodes = [
                self._compact_session_episode(episode)
                for episode in episodes[:_PCSX2_RECEIPT_EPISODES]
            ]
            summary = {
                "status": "COMPLETE",
                "session_id": session_id,
                "label": label,
                "address": address,
                "size": size,
                "pine_identity": pine_identity,
                "pine": {"host": self.pine_host, "slot": self.pine_slot},
                "input_source": source_identity,
                "samples": {
                    "requested": samples,
                    "captured": captured,
                    "focus_gaps": focus_gaps,
                    "sample_hz": sample_hz,
                    "started_monotonic_ns": started_ns,
                    "ended_monotonic_ns": ended_ns,
                    "duration_ns": max(0, ended_ns - started_ns),
                    "unique_snapshots": len(blobs),
                },
                "temporal_evidence": {
                    "kind": "sampled-host-input-followed-by-memory",
                    "interpretation": "temporal-response-hypothesis",
                    "transition_samples": transition_samples,
                    "transition_count": transition_count,
                    "analyzed_episodes": len(episodes),
                    "unresolved_episodes": unresolved_episodes,
                },
                "controls": controls,
                "function_evidence": functions,
                "episodes": compact_episodes,
                "artifact": {
                    "path": str(manifest_path),
                    "sha256": manifest_sha,
                    "memory_blob_count": len(blobs),
                    "memory_bytes": sum(len(data) for data in blobs.values()),
                },
                "receipt_path": str(path),
            }
            return _bounded_json(summary, "gameplay capture receipt")

        def replay() -> Mapping[str, Any]:
            summary = self._read_receipt(path, "gameplay capture receipt")
            summary = self._replayed(
                summary,
                {
                    "status", "session_id", "label", "address", "size",
                    "pine_identity", "pine", "input_source", "samples",
                    "temporal_evidence", "controls", "function_evidence",
                    "episodes", "artifact", "receipt_path",
                },
                "gameplay capture receipt",
            )
            self._validate_session_artifact(
                summary, session_id=session_id, address=address, size=size,
            )
            return summary

        return self._admitted(path, identity, work, replay)

    def _session_episode(self, pcsx2: Any, atlas: Any, session_id: str,
                         before: Mapping[str, Any], after: Mapping[str, Any],
                         address: int) -> dict[str, Any]:
        changed = pcsx2.compare_snapshots(
            before["data"], after["data"], base_address=address, page_size=4_096,
        )
        raw_ranges = changed.get("changed_ranges") if isinstance(changed, Mapping) else None
        if isinstance(raw_ranges, list) and len(raw_ranges) > _PCSX2_MAX_RELATE_RANGES:
            changed_count = changed.get("changed_byte_count")
            if (
                isinstance(changed_count, bool)
                or not isinstance(changed_count, int)
                or not 0 <= changed_count <= len(before["data"])
            ):
                raise ActivityRefused(
                    "the dense gameplay comparison returned an invalid byte count"
                )
            changes = {
                "changed_byte_count": changed_count,
                "changed_range_count": len(raw_ranges),
                "changed_ranges": [],
                "changed_page_count": 0,
                "changed_pages": [],
                "analysis_status": "dense-change-budget",
            }
            evidence: list[Mapping[str, Any]] = []
            references: list[Mapping[str, Any]] = []
        else:
            ranges, pages, changed_count = _validate_snapshot_changes(changed)
            changes = dict(self._change_summary(ranges, pages, changed_count))
            changes["analysis_status"] = "complete"
            evidence = self._rank_functions(atlas, ranges, address)
            references = self._changed_references(atlas, ranges, address)[:64]
        before_seq = int(before["seq"])
        after_seq = int(after["seq"])
        return {
            "episode_id": _identity(f"{session_id}:{before_seq}:{after_seq}"),
            "evidence_kind": "temporal-response-hypothesis",
            "transition_seq": before_seq,
            "response_seq": after_seq,
            "transition_monotonic_ns": int(before["input_monotonic_ns"]),
            "response_monotonic_ns": int(after["memory_monotonic_ns"]),
            "latency_ns": max(
                0,
                int(after["memory_monotonic_ns"])
                - int(before["input_monotonic_ns"]),
            ),
            "transitions": before["transitions"],
            "before_sha256": before["sha256"],
            "after_sha256": after["sha256"],
            "changes": changes,
            "function_evidence": evidence,
            "references": references,
        }

    @staticmethod
    def _aggregate_session_evidence(
        episodes: list[dict[str, Any]],
        samples: list[dict[str, Any]],
    ) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
        controls: dict[str, dict[str, Any]] = {}
        functions: dict[tuple[str, str], dict[str, Any]] = {}
        for sample in samples:
            transitions = sample.get("transitions")
            if sample.get("status") != "captured" or not isinstance(transitions, list):
                continue
            for transition in transitions:
                control = transition.get("control") if isinstance(transition, Mapping) else None
                if not isinstance(control, str):
                    continue
                row = controls.setdefault(control, {"control": control, "events": 0})
                row["events"] += 1
        for episode in episodes:
            for evidence in episode["function_evidence"]:
                address = evidence.get("address")
                name = evidence.get("name")
                if not isinstance(address, str) or not isinstance(name, str):
                    continue
                row = functions.setdefault(
                    (address, name),
                    {
                        "address": address,
                        "name": name,
                        "source": evidence.get("source"),
                        "episode_count": 0,
                        "changed_bytes": 0,
                        "reference_hits": 0,
                        "observation_base_hits": 0,
                    },
                )
                row["episode_count"] += 1
                row["changed_bytes"] += int(evidence.get("changed_bytes", 0))
                row["reference_hits"] += int(evidence.get("reference_hits", 0))
                row["observation_base_hits"] += int(
                    evidence.get("observation_base_hits", 0)
                )
        ranked_controls = sorted(
            controls.values(), key=lambda row: (-row["events"], row["control"]),
        )
        ranked_functions = sorted(
            functions.values(),
            key=lambda row: (
                -row["episode_count"],
                -row["changed_bytes"],
                -row["reference_hits"],
                row["name"],
                row["address"],
            ),
        )
        return ranked_controls[:64], ranked_functions[:_PCSX2_MAX_CANDIDATES]

    @staticmethod
    def _compact_session_episode(episode: Mapping[str, Any]) -> Mapping[str, Any]:
        changes = episode["changes"]
        return {
            "episode_id": episode["episode_id"],
            "evidence_kind": episode["evidence_kind"],
            "transition_seq": episode["transition_seq"],
            "response_seq": episode["response_seq"],
            "latency_ns": episode["latency_ns"],
            "transition_monotonic_ns": episode["transition_monotonic_ns"],
            "response_monotonic_ns": episode["response_monotonic_ns"],
            "transitions": episode["transitions"],
            "before_sha256": episode["before_sha256"],
            "after_sha256": episode["after_sha256"],
            "changes": {
                **dict(changes),
                "changed_ranges": list(changes.get("changed_ranges", ()))[:16],
                "changed_pages": list(changes.get("changed_pages", ()))[:16],
            },
            "function_evidence": list(episode["function_evidence"])[:4],
            "references": list(episode["references"])[:8],
        }

    def _validate_session_artifact(self, summary: Mapping[str, Any], *,
                                   session_id: str, address: int, size: int) -> None:
        artifact = summary.get("artifact")
        if not isinstance(artifact, Mapping):
            raise ActivityRefused("the stored gameplay artifact reference is invalid")
        expected_path = self.data_home / "sessions" / f"{session_id}.json"
        if artifact.get("path") != str(expected_path) or not expected_path.is_file():
            raise ActivityRefused("the stored gameplay artifact is missing")
        body = expected_path.read_bytes()
        if hashlib.sha256(body).hexdigest() != artifact.get("sha256"):
            raise ActivityRefused("the stored gameplay artifact digest is inconsistent")
        try:
            manifest = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ActivityRefused("the stored gameplay artifact is unreadable") from exc
        current_iso_sha256 = self._hash_iso()
        if (
            not isinstance(manifest, Mapping)
            or manifest.get("schema") != "cassi-pcsx2-gameplay-v1"
            or manifest.get("activity_id") != self.activity_id
            or manifest.get("session_id") != session_id
            or manifest.get("iso_sha256") != current_iso_sha256
            or manifest.get("window") != {"address": address, "size": size}
        ):
            raise ActivityRefused("the stored gameplay artifact belongs to another session")
        rows = manifest.get("samples")
        if not isinstance(rows, list):
            raise ActivityRefused("the stored gameplay samples are invalid")
        checked: set[str] = set()
        captured = 0
        gaps = 0
        for sequence, row in enumerate(rows):
            if not isinstance(row, Mapping) or row.get("seq") != sequence:
                raise ActivityRefused("the stored gameplay sample ordering is invalid")
            status = row.get("status")
            if status == "focus-gap":
                gaps += 1
                continue
            if status != "captured":
                raise ActivityRefused("the stored gameplay sample status is invalid")
            snapshot = row.get("snapshot")
            sha = snapshot.get("sha256") if isinstance(snapshot, Mapping) else None
            if (
                not isinstance(sha, str)
                or len(sha) != 64
                or any(character not in "0123456789abcdef" for character in sha)
                or snapshot.get("size") != size
            ):
                raise ActivityRefused("the stored gameplay snapshot reference is invalid")
            captured += 1
            if sha in checked:
                continue
            binary_path = self.data_home / "observations" / "data" / f"{sha}.bin"
            if not binary_path.is_file():
                raise ActivityRefused("a stored gameplay memory artifact is missing")
            data = binary_path.read_bytes()
            if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
                raise ActivityRefused("a stored gameplay memory artifact is inconsistent")
            checked.add(sha)
        counts = summary.get("samples")
        if (
            not isinstance(counts, Mapping)
            or counts.get("requested") != len(rows)
            or counts.get("captured") != captured
            or counts.get("focus_gaps") != gaps
            or artifact.get("memory_blob_count") != len(checked)
        ):
            raise ActivityRefused("the stored gameplay sample counts are inconsistent")

    def _capture_surface(self, binding_id: str, current: Mapping[str, Any]) -> Mapping[str, Any]:
        """Capture already-authorized surface evidence through the entity broker.

        A binding id alone is not programme authority: the exact binding's
        ``(backend_id, source_id)`` must sit in the current programme's Surface
        scope with an authorized observation modality, and only bounded
        publication hashes plus source identity enter the receipt.
        """
        entity = self.entity
        if entity is None:
            raise ActivityRefused("the entity surface broker is unavailable")
        surface_error: tuple[type[BaseException], ...] = ()
        try:
            from surface.records import SurfaceError  # type: ignore[import-not-found]
        except Exception:
            pass
        else:
            surface_error = (SurfaceError,)
        inspect = getattr(entity, "inspect_surface_binding", None)
        capture = getattr(entity, "capture_surface", None)
        if not callable(inspect) or not callable(capture):
            raise ActivityRefused("the entity surface broker is unavailable")
        program_id = current["program_id"]
        try:
            record = inspect(binding_id, program_id=program_id)
        except surface_error as exc:
            raise ActivityRefused(f"surface binding refused: {exc}") from exc
        except Exception as exc:
            raise ActivityRefused(f"surface binding failed: {exc}") from exc
        if not isinstance(record, Mapping):
            raise ActivityRefused("the surface broker returned an invalid binding record")
        backend_id = record.get("backend_id")
        source_id = record.get("source_id")
        modalities = record.get("modalities")
        if (
            not isinstance(backend_id, str)
            or not backend_id
            or not isinstance(source_id, str)
            or not source_id
            or not isinstance(modalities, (list, tuple))
            or not (set(modalities) & {"pixels", "accessibility"})
        ):
            raise ActivityRefused(
                "the surface binding has no authorized observation modality in this programme"
            )
        scope = current.get("surface_scope")
        sources = scope.get("sources") if isinstance(scope, Mapping) else None
        rows = sources if isinstance(sources, list) else ()
        for row in rows:
            if (
                isinstance(row, Mapping)
                and row.get("backend_id") == backend_id
                and row.get("source_id") == source_id
            ):
                break
        else:
            raise ActivityRefused(
                "the surface binding is outside this programme's Surface scope"
            )
        try:
            publication = capture(binding_id, program_id=program_id)
        except surface_error as exc:
            raise ActivityRefused(f"surface capture refused: {exc}") from exc
        except Exception as exc:
            raise ActivityRefused(f"surface capture failed: {exc}") from exc
        if not isinstance(publication, Mapping):
            raise ActivityRefused("the surface broker returned an invalid publication")
        authorized = set(modalities)
        return {
            "binding_id": binding_id,
            "backend_id": backend_id,
            "source_id": source_id,
            "modalities": [
                name for name in ("pixels", "accessibility", "audio") if name in authorized
            ],
            "publication": self._publication_evidence(publication),
        }

    @staticmethod
    def _publication_evidence(publication: Mapping[str, Any]) -> Mapping[str, Any]:
        """Keep only bounded publication hashes, sizes, and source identity."""
        rows: dict[str, Any] = {}
        for key in sorted(str(key) for key in publication):
            value = publication[key]
            if isinstance(value, (bytes, bytearray, memoryview)):
                rows[key] = hashlib.sha256(bytes(value)).hexdigest()
                continue
            text = _plain_json(value, "surface capture")
            encoded = json.dumps(
                text, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
            if len(encoded) > 4_096:
                rows[key] = {
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                    "omitted": "bounded-evidence",
                }
            else:
                rows[key] = text
        return rows

    # -- relate ---------------------------------------------------------------

    def _relate(self, current: Mapping[str, Any], parameters: Mapping[str, Any],
                operation_id: str, path: Path) -> Mapping[str, Any]:
        if not isinstance(parameters, Mapping) or set(parameters) != {"before", "after", "label"}:
            raise ActivityRefused("pcsx2 relate requires before, after, and a concise label")
        before_id = _pcsx2_identifier(parameters["before"], "before observation")
        after_id = _pcsx2_identifier(parameters["after"], "after observation")
        label = _pcsx2_text(parameters["label"], "relation label")
        if before_id == after_id:
            raise ActivityRefused("pcsx2 relate needs two distinct observations")
        identity = {
            "activity_id": self.activity_id,
            "operation": "relate",
            "program_id": current["program_id"],
            "parameters": {"before": before_id, "after": after_id, "label": label},
            "iso_path": str(self.iso_path),
            "data_home": str(self.data_home),
            "pine": {"host": self.pine_host, "slot": self.pine_slot},
        }

        def work() -> Mapping[str, Any]:
            before = self._load_observation(before_id)
            after = self._load_observation(after_id)
            if before["address"] != after["address"] or before["size"] != after["size"]:
                raise ActivityRefused("related observations must cover the same bounded window")
            atlas = self._load_atlas()
            self._require_configured_game(
                atlas, before["metadata"].get("pine_identity"),
            )
            self._require_configured_game(
                atlas, after["metadata"].get("pine_identity"),
            )
            atlas_identity = _bounded_json(
                _plain_json(atlas.identity, "atlas identity"), "atlas identity",
            )
            pcsx2 = self._pcsx2()
            changed = pcsx2.compare_snapshots(
                before["data"], after["data"],
                base_address=before["address"], page_size=4_096,
            )
            ranges, pages, changed_byte_count = _validate_snapshot_changes(changed)
            evidence = self._rank_functions(atlas, ranges, before["address"])
            references = self._changed_references(atlas, ranges, before["address"])
            candidate = self._write_pnach_candidate(
                label, ranges, evidence, before, after, path,
            )
            summary = {
                "status": "COMPLETE",
                "label": label,
                "before": self._observation_ref(before_id, before),
                "after": self._observation_ref(after_id, after),
                "changes": self._change_summary(ranges, pages, changed_byte_count),
                "function_evidence": evidence,
                "references": references,
                "atlas_identity": atlas_identity,
                "pnach_candidate": candidate,
                "receipt_path": str(path),
            }
            return _bounded_json(summary, "relation receipt")

        def replay() -> Mapping[str, Any]:
            summary = self._read_receipt(path, "relation receipt")
            return self._replayed(
                summary,
                {"status", "label", "before", "after", "changes", "function_evidence",
                 "references", "atlas_identity", "pnach_candidate", "receipt_path"},
                "relation receipt",
            )

        return self._admitted(path, identity, work, replay)

    def _load_observation(self, observation_id: str) -> Mapping[str, Any]:
        path = self.data_home / "observations" / f"{observation_id}.json"
        if not path.is_file():
            raise ActivityRefused("the referenced observation is not stored by this activity")
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ActivityRefused("the stored observation metadata is unreadable") from exc
        if not isinstance(metadata, Mapping):
            raise ActivityRefused("the stored observation metadata is not an object")
        if (
            metadata.get("observation_id") != observation_id
            or metadata.get("activity_id") != self.activity_id
            or metadata.get("iso_sha256") != self._iso_digest()
        ):
            raise ActivityRefused("the referenced observation belongs to a different game")
        sha = metadata.get("data_sha256")
        if (
            not isinstance(sha, str)
            or len(sha) != 64
            or any(character not in "0123456789abcdef" for character in sha)
        ):
            raise ActivityRefused("the stored observation lacks a valid data digest")
        binary_path = self.data_home / "observations" / "data" / f"{sha}.bin"
        if not binary_path.is_file():
            raise ActivityRefused("the observation artifact is missing")
        data = binary_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            raise ActivityRefused("the observation artifact digest is inconsistent")
        address = _pcsx2_index(metadata.get("address"), "stored observation address", 0, 0xFFFF_FFFF)
        size = _pcsx2_index(metadata.get("size"), "stored observation size", 1, _PCSX2_MAX_OBSERVATION_BYTES)
        if len(data) != size or address + size > 0x1_0000_0000:
            raise ActivityRefused("the observation artifact length is inconsistent")
        return {
            "metadata": metadata, "address": address, "size": size,
            "data": data, "sha256": sha,
        }

    @staticmethod
    def _observation_ref(observation_id: str, observation: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "observation_id": observation_id,
            "sha256": observation["sha256"],
            "address": observation["address"],
            "size": observation["size"],
            "label": observation["metadata"].get("label"),
            "captured_at": observation["metadata"].get("captured_at"),
        }

    @staticmethod
    def _change_summary(ranges: list[dict[str, int]],
                        pages: list[dict[str, int]], changed_byte_count: int) -> Mapping[str, Any]:
        return {
            "changed_byte_count": changed_byte_count,
            "changed_range_count": len(ranges),
            "changed_ranges": [
                {"start": span["start"], "end": span["end"], "length": span["end"] - span["start"]}
                for span in ranges[:64]
            ],
            "changed_page_count": len(pages),
            "changed_pages": [
                {"page": page["page"], "start": page["start"], "end": page["end"]}
                for page in pages[:64]
            ],
        }

    # -- atlas evidence -------------------------------------------------------

    @staticmethod
    def _valid_record(record: Any) -> bool:
        address = getattr(record, "address", None)
        name = getattr(record, "name", None)
        source = getattr(record, "source", None)
        size = getattr(record, "size", None)
        return (
            isinstance(address, int)
            and not isinstance(address, bool)
            and 0 <= address <= 0xFFFF_FFFF
            and isinstance(name, str)
            and isinstance(source, str)
            and (size is None or (isinstance(size, int) and not isinstance(size, bool) and size > 0))
        )

    def _atlas_functions_for_address(self, atlas: Any, address: int) -> Any:
        try:
            records = atlas.functions_for_address(address)
        except Exception as exc:
            raise ActivityRefused("the atlas could not resolve a changed address") from exc
        if not isinstance(records, (list, tuple)):
            raise ActivityRefused("the atlas function lookup returned an unexpected type")
        return records

    def _atlas_symbol_at(self, atlas: Any, address: int) -> Any:
        try:
            record = atlas.symbol_at(address)
        except Exception as exc:
            raise ActivityRefused("the atlas could not resolve a symbol") from exc
        if record is None:
            return None
        if not self._valid_record(record):
            raise ActivityRefused("the atlas returned an invalid function record")
        return record

    def _atlas_edges(self, atlas: Any, method: str, address: int) -> list[int]:
        try:
            edges = getattr(atlas, method)(address)
        except Exception as exc:
            raise ActivityRefused(f"the atlas could not resolve {method} edges") from exc
        if not isinstance(edges, (list, tuple)):
            raise ActivityRefused("the atlas call edges returned an unexpected type")
        result = []
        for edge in edges:
            _pcsx2_index(edge, "atlas call edge", 0, 0xFFFF_FFFF)
            result.append(int(edge))
        return result

    def _atlas_references_near(self, atlas: Any, address: int) -> list[Mapping[str, Any]]:
        method = getattr(atlas, "references_near_address", None)
        if not callable(method):
            return []
        try:
            rows = method(address, span=64)
        except Exception as exc:
            raise ActivityRefused("the atlas could not resolve nearby data references") from exc
        if not isinstance(rows, (list, tuple)):
            raise ActivityRefused("the atlas nearby references returned an unexpected type")
        return [row for row in rows if isinstance(row, Mapping)]

    @staticmethod
    def _reference_match(reference: Mapping[str, Any], address: int,
                         observation_base: int) -> str | None:
        target = reference.get("to_address", reference.get("to_addr"))
        if isinstance(target, bool) or not isinstance(target, int):
            return None
        access = reference.get("access")
        if access == "memory":
            width = reference.get("width")
            if (
                isinstance(width, bool)
                or not isinstance(width, int)
                or width <= 0
                or target < 0
                or target + width > 0x1_0000_0000
            ):
                return None
            if target <= address < target + width:
                return "changed-byte"
        elif target == address:
            return "changed-byte"
        if access == "address" and target == observation_base:
            return "observation-base"
        return None

    def _matching_references(
        self, atlas: Any, ranges: list[dict[str, int]], observation_base: int,
    ) -> list[Mapping[str, Any]]:
        matched: dict[str, Mapping[str, Any]] = {}
        for span in ranges:
            for address in range(span["start"], span["end"]):
                for row in self._atlas_references_near(atlas, address):
                    if row.get("kind") != "data":
                        continue
                    relation_match = self._reference_match(row, address, observation_base)
                    if relation_match is None:
                        continue
                    plain = _bounded_json(
                        _plain_json(row, "atlas reference"), "atlas reference",
                    )
                    key = json.dumps(plain, sort_keys=True, separators=(",", ":"))
                    previous = matched.get(key)
                    if (
                        previous is not None
                        and previous.get("relation_match") == "changed-byte"
                    ):
                        continue
                    plain["relation_match"] = relation_match
                    matched[key] = plain
        return list(matched.values())

    def _accumulate(self, direct: dict[Any, dict[str, Any]], record: Any, *,
                    reference_match: str | None = None) -> None:
        if not self._valid_record(record):
            raise ActivityRefused("the atlas returned an invalid function record")
        key = (int(record.address), record.name, record.source, record.size)
        row = direct.setdefault(
            key, {
                "record": record,
                "changed_bytes": 0,
                "reference_hits": 0,
                "observation_base_hits": 0,
            },
        )
        if reference_match == "changed-byte":
            if row["reference_hits"] < _PCSX2_MAX_OBSERVATION_BYTES:
                row["reference_hits"] += 1
        elif reference_match == "observation-base":
            if row["observation_base_hits"] < _PCSX2_MAX_OBSERVATION_BYTES:
                row["observation_base_hits"] += 1
        elif row["changed_bytes"] < _PCSX2_MAX_OBSERVATION_BYTES:
            row["changed_bytes"] += 1

    def _rank_functions(
        self, atlas: Any, ranges: list[dict[str, int]], observation_base: int,
    ) -> list[Mapping[str, Any]]:
        direct: dict[Any, dict[str, Any]] = {}
        for span in ranges:
            for address in range(span["start"], span["end"]):
                for record in self._atlas_functions_for_address(atlas, address):
                    self._accumulate(direct, record)
        for reference in self._matching_references(atlas, ranges, observation_base):
            source = reference.get("from_address", reference.get("from_addr"))
            if isinstance(source, bool) or not isinstance(source, int):
                continue
            records: dict[tuple[Any, ...], Any] = {}
            for record in self._atlas_functions_for_address(atlas, source):
                if not self._valid_record(record):
                    raise ActivityRefused(
                        "the atlas returned an invalid referencing function",
                    )
                key = (record.address, record.name, record.source, record.size)
                records[key] = record
            for record in records.values():
                self._accumulate(
                    direct, record,
                    reference_match=str(reference["relation_match"]),
                )
        if not direct:
            return []
        changed_addresses = {row["record"].address for row in direct.values()}
        for row in direct.values():
            record = row["record"]
            callers = self._atlas_edges(atlas, "callers_of", record.address)
            callees = self._atlas_edges(atlas, "callees_of", record.address)
            row["callers"] = len(callers)
            row["callees"] = len(callees)
            row["call_neighborhood"] = (
                sum(1 for address in callers if address in changed_addresses)
                + sum(1 for address in callees if address in changed_addresses)
            )
        ranked = sorted(
            direct.values(),
            key=lambda row: (
                -row["reference_hits"], -row["changed_bytes"],
                -row["observation_base_hits"], -row["call_neighborhood"],
                row["record"].name, row["record"].address,
            ),
        )
        evidence = []
        for row in ranked[:_PCSX2_MAX_CANDIDATES]:
            record = row["record"]
            evidence.append({
                "address": f"0x{record.address & 0xFFFF_FFFF:08X}",
                "name": record.name,
                "source": record.source,
                "size": record.size,
                "changed_bytes": row["changed_bytes"],
                "reference_hits": row["reference_hits"],
                "observation_base_hits": row["observation_base_hits"],
                "call_neighborhood": row["call_neighborhood"],
                "callers": row["callers"],
                "callees": row["callees"],
            })
        return evidence

    def _changed_references(
        self, atlas: Any, ranges: list[dict[str, int]], observation_base: int,
    ) -> list[Any]:
        return self._matching_references(atlas, ranges, observation_base)[:32]

    # -- diagnostic .pnach candidate ------------------------------------------

    def _write_pnach_candidate(self, label: str, ranges: list[dict[str, int]],
                               evidence: list[Mapping[str, Any]],
                               before: Mapping[str, Any], after: Mapping[str, Any],
                               path: Path) -> Mapping[str, Any] | None:
        serial, crc = _pcsx2_game_identity(before["metadata"].get("pine_identity"))
        if serial is None or crc is None:
            return None
        if not evidence:
            return None
        top = evidence[0]
        stub_address = int(top["address"], 16)
        offset = stub_address - before["address"]
        data = before["data"]
        if offset < 0 or offset + 8 > len(data):
            return None
        original_words = [
            int.from_bytes(data[offset:offset + 4], "little"),
            int.from_bytes(data[offset + 4:offset + 8], "little"),
        ]
        group = "".join(
            character if (character.isascii() and (character.isalnum() or character in "._-"))
            else "-"
            for character in label
        )[:64] or "diagnostic-stub"
        lines = [
            "// Cassi hosted pcsx2 activity: diagnostic function-stub candidate.",
            "// INACTIVE evidence candidate; every patch line below is commented out.",
            "// Treat as evidence. Import and enable by hand only if ever needed;",
            "// Cassi never installs this file into PCSX2 cheat or patch directories.",
            f"// serial={serial}",
            f"// crc={crc}",
            f"// label={label}",
            f"// observation_before={before['sha256']}",
            f"// observation_after={after['sha256']}",
            f"// changed_ranges={len(ranges)}",
            f"//[{group}]",
            f"// first instruction 0x{stub_address:08X}; "
            f"original words {original_words[0]:08X} {original_words[1]:08X}",
            f"//patch=1,EE,{stub_address:08X},word,03E00008",
            f"//patch=1,EE,{stub_address + 4:08X},word,00000000",
        ]
        body = ("\n".join(lines) + "\n").encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()
        filename = f"{serial}_{crc}.pnach"
        latest = self.data_home / "candidates" / filename
        immutable = path.parent / filename
        _pcsx2_write_atomic(latest, body)
        _pcsx2_write_atomic(immutable, body)
        return {
            "filename": filename,
            "path": str(immutable),
            "sha256": digest,
            "latest_path": str(latest),
            "status": "inactive-candidate",
            "stub_address": f"0x{stub_address:08X}",
            "original_words": [f"{word:08X}" for word in original_words],
        }

    # -- decompile ------------------------------------------------------------

    def _decompile(self, current: Mapping[str, Any], parameters: Mapping[str, Any],
                   operation_id: str, path: Path) -> Mapping[str, Any]:
        if not isinstance(parameters, Mapping) or set(parameters) - {"address", "question"}:
            raise ActivityRefused("pcsx2 decompile accepts only address and an optional question")
        address = _pcsx2_index(parameters.get("address"), "function address", 0, 0xFFFF_FFFF)
        question = _pcsx2_text(parameters.get("question"), "interpretation question")
        identity = {
            "activity_id": self.activity_id,
            "operation": "decompile",
            "program_id": current["program_id"],
            "parameters": {"address": address, "question": question},
            "iso_path": str(self.iso_path),
            "data_home": str(self.data_home),
            "pine": {"host": self.pine_host, "slot": self.pine_slot},
        }

        def work() -> Mapping[str, Any]:
            atlas = self._load_atlas()
            record = self._atlas_symbol_at(atlas, address)
            if record is None or record.address != address:
                raise ActivityRefused("decompile requires an exact atlas function address")
            prior = self._prior_relation_evidence(record)
            context = self._interpretation_context(atlas, record, prior)
            prompt, prompt_evidence_ids = self._interpretation_prompt(
                record, context, question,
            )
            value = self._validate_interpretation(
                self._ask_brain(prompt), prompt_evidence_ids,
            )
            artifact = self._persist_interpretation(
                operation_id, record, context, prior, question,
                prompt_evidence_ids, value,
            )
            return {
                "status": "COMPLETE",
                "function": {
                    "address": f"0x{address:08X}",
                    "name": record.name,
                    "size": record.size,
                    "source": record.source,
                },
                "question": question,
                "interpretation": value,
                "artifact": artifact,
                "receipt_path": str(path),
            }

        def replay() -> Mapping[str, Any]:
            summary = self._read_receipt(path, "interpretation receipt")
            return self._replayed(
                summary,
                {"status", "function", "question", "interpretation", "artifact", "receipt_path"},
                "interpretation receipt",
            )

        return self._admitted(path, identity, work, replay)

    def _interpretation_context(
        self, atlas: Any, record: Any, prior: list[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        instructions = self._atlas_function_instructions(atlas, record)
        callers = self._atlas_edges(atlas, "callers_of", record.address)
        callees = self._atlas_edges(atlas, "callees_of", record.address)
        strings = self._atlas_strings_near(atlas, record.address)
        evidence: dict[str, str] = {}
        ids: list[str] = []

        def add(text: str) -> str:
            evidence_id = f"e{len(evidence) + 1}"
            evidence[evidence_id] = text
            ids.append(evidence_id)
            return evidence_id

        add(
            f"atlas function {record.name or 'unnamed'} at "
            f"0x{record.address & 0xFFFF_FFFF:08X} size {record.size} source {record.source}"
        )
        evidence_map = getattr(record, "evidence", None)
        body_sha = evidence_map.get("sha256") if isinstance(evidence_map, Mapping) else None
        if isinstance(body_sha, str) and len(body_sha) == 64:
            add(f"function body sha256: {body_sha}")
        referenced_values: set[str] = set()
        referenced_strings = (
            evidence_map.get("strings", ())
            if isinstance(evidence_map, Mapping)
            else ()
        )
        if not isinstance(referenced_strings, (list, tuple)):
            raise ActivityRefused("the atlas referenced-string evidence is malformed")
        for row in referenced_strings[:8]:
            if not isinstance(row, Mapping):
                raise ActivityRefused("the atlas referenced-string evidence is malformed")
            address = row.get("address")
            value = row.get("value", row.get("text"))
            if (
                not isinstance(address, int)
                or isinstance(address, bool)
                or not 0 <= address <= 0xFFFF_FFFF
                or not isinstance(value, str)
            ):
                raise ActivityRefused("the atlas referenced-string evidence is malformed")
            add(f"referenced string at 0x{address:08X}: {value[:128]}")
            referenced_values.add(value)
        for row in prior[:6]:
            detail = (
                "Prior relation evidence: "
                f"label={row.get('label')!r}, "
                f"changed_bytes={row.get('changed_bytes')}, "
                f"reference_hits={row.get('reference_hits')}, "
                f"observation_base_hits={row.get('observation_base_hits')}"
            )
            references = row.get("references")
            if isinstance(references, list) and references:
                rendered = []
                for reference in references[:8]:
                    if not isinstance(reference, Mapping):
                        continue
                    source = reference.get("from_address")
                    target = reference.get("to_address")
                    disasm = reference.get("disasm")
                    relation_match = reference.get("relation_match")
                    relation = (
                        f" [{relation_match}]"
                        if relation_match in {"changed-byte", "observation-base"}
                        else ""
                    )
                    rendered.append(
                        f"0x{source:08X}->0x{target:08X}{relation} {disasm}"
                        if isinstance(source, int) and isinstance(target, int)
                        else str(disasm or reference.get("kind") or "reference")
                    )
                if rendered:
                    detail += "; data references: " + " | ".join(rendered)
            changed_ranges = row.get("changed_ranges")
            if isinstance(changed_ranges, list) and changed_ranges:
                rendered_ranges = []
                for changed_range in changed_ranges[:8]:
                    if not isinstance(changed_range, Mapping):
                        continue
                    range_start = changed_range.get("start")
                    range_end = changed_range.get("end")
                    if isinstance(range_start, int) and isinstance(range_end, int):
                        rendered_ranges.append(f"0x{range_start:08X}-0x{range_end:08X}")
                if rendered_ranges:
                    detail += "; changed ranges: " + ", ".join(rendered_ranges)
            add(detail[:768])
        for line in instructions[:32]:
            add(f"disassembly: {line}")
        add("callers: " + (", ".join(f"0x{address:08X}" for address in callers[:16]) or "none"))
        add("callees: " + (", ".join(f"0x{address:08X}" for address in callees[:16]) or "none"))
        for text in strings[:8]:
            if text not in referenced_values:
                add(f"string near function: {text[:128]}")
        return {
            "evidence": evidence,
            "evidence_ids": ids,
            "callers": callers,
            "callees": callees,
        }

    def _atlas_function_instructions(self, atlas: Any, record: Any) -> list[str]:
        evidence = getattr(record, "evidence", None)
        rows = evidence.get("instructions") if isinstance(evidence, Mapping) else None
        if isinstance(rows, (list, tuple)) and rows:
            lines: list[str] = []
            for row in rows[:64]:
                if not isinstance(row, Mapping):
                    raise ActivityRefused("the atlas instruction evidence is malformed")
                address = row.get("address")
                text = row.get("text", row.get("disasm"))
                if isinstance(address, int) and isinstance(text, str):
                    lines.append(f"0x{address & 0xFFFF_FFFF:08X}: {text}")
                elif isinstance(text, str):
                    lines.append(text)
                else:
                    raise ActivityRefused("the atlas instruction evidence is malformed")
            if lines:
                return lines
        for name in ("function_disassembly", "disassembly_of", "instructions_of", "disasm_for_address"):
            method = getattr(atlas, name, None)
            if callable(method):
                try:
                    lines = method(record.address)
                except Exception as exc:
                    raise ActivityRefused("the atlas per-function disassembly failed") from exc
                if isinstance(lines, str):
                    return lines.splitlines()[:64]
                if isinstance(lines, (list, tuple)) and all(isinstance(line, str) for line in lines):
                    return list(lines)[:64]
                raise ActivityRefused("the atlas disassembly returned an unexpected type")
        lines: list[str] = []
        try:
            rows = atlas.references_for_address(record.address)
        except Exception as exc:
            raise ActivityRefused("the atlas could not resolve function references") from exc
        if not isinstance(rows, (list, tuple)):
            raise ActivityRefused("the atlas references returned an unexpected type")
        for row in rows[:32]:
            if isinstance(row, Mapping) and isinstance(row.get("disasm"), str):
                lines.append(row["disasm"][:160])
        return lines

    def _atlas_strings_near(self, atlas: Any, address: int) -> list[str]:
        method = getattr(atlas, "strings_near", None)
        if not callable(method):
            return []
        try:
            rows = method(address, span=64)
        except Exception as exc:
            raise ActivityRefused("the atlas string lookup failed") from exc
        if not isinstance(rows, (list, tuple)):
            raise ActivityRefused("the atlas string lookup returned an unexpected type")
        texts = []
        for row in rows:
            text = row.get("text", row.get("value")) if isinstance(row, Mapping) else row
            if isinstance(text, str):
                texts.append(text)
        return texts

    def _prior_relation_evidence(self, record: Any) -> list[Mapping[str, Any]]:
        operations = self.data_home / "operations"
        if not operations.is_dir():
            return []
        start = int(record.address)
        end = start + int(record.size)
        atlas_identity = getattr(self._load_atlas(), "identity", None)
        if not isinstance(atlas_identity, Mapping):
            return []
        expected_iso = atlas_identity.get("iso_sha256")
        expected_elf = atlas_identity.get("elf_sha256")
        if not isinstance(expected_iso, str) or not isinstance(expected_elf, str):
            return []

        def modified_at(path: Path) -> int:
            try:
                return path.stat().st_mtime_ns
            except OSError:
                return 0

        receipt_paths = sorted(
            operations.glob("*/receipt.json"), key=modified_at, reverse=True,
        )
        eligible = 0
        rows = []
        for receipt_path in receipt_paths:
            try:
                summary = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(summary, Mapping):
                continue
            relation_identity = summary.get("atlas_identity")
            changes = summary.get("changes")
            if (
                not isinstance(relation_identity, Mapping)
                or relation_identity.get("iso_sha256") != expected_iso
                or relation_identity.get("elf_sha256") != expected_elf
                or not isinstance(changes, Mapping)
            ):
                continue
            eligible += 1
            if eligible > _PCSX2_MAX_OPERATION_RECEIPTS:
                break

            matched = None
            for row in summary.get("function_evidence") or ():
                if not isinstance(row, Mapping) or not isinstance(row.get("address"), str):
                    continue
                try:
                    parsed = int(row["address"], 16)
                except ValueError:
                    continue
                if parsed == start:
                    matched = row
                    break
            references = []
            for reference in summary.get("references") or ():
                if not isinstance(reference, Mapping) or reference.get("kind") != "data":
                    continue
                source = reference.get("from_address", reference.get("from_addr"))
                if isinstance(source, bool) or not isinstance(source, int) or not start <= source < end:
                    continue
                references.append({
                    key: reference[key]
                    for key in (
                        "kind", "access", "width", "from_address", "to_address",
                        "disasm", "register", "relation_match",
                    )
                    if key in reference
                })
                if len(references) >= 8:
                    break
            if matched is None and not references:
                continue

            changed_ranges = []
            raw_ranges = changes.get("changed_ranges")
            for changed_range in raw_ranges if isinstance(raw_ranges, list) else ():
                if not isinstance(changed_range, Mapping):
                    continue
                range_start = changed_range.get("start")
                range_end = changed_range.get("end")
                if (
                    isinstance(range_start, int)
                    and not isinstance(range_start, bool)
                    and isinstance(range_end, int)
                    and not isinstance(range_end, bool)
                    and 0 <= range_start < range_end <= 0x1_0000_0000
                ):
                    changed_ranges.append({"start": range_start, "end": range_end})
                if len(changed_ranges) >= 8:
                    break
            label = summary.get("label")
            rows.append({
                "label": label if isinstance(label, str) else None,
                "changed_bytes": (
                    matched.get("changed_bytes")
                    if isinstance(matched, Mapping)
                    and isinstance(matched.get("changed_bytes"), int)
                    and not isinstance(matched.get("changed_bytes"), bool)
                    else None
                ),
                "reference_hits": (
                    matched.get("reference_hits")
                    if isinstance(matched, Mapping)
                    and isinstance(matched.get("reference_hits"), int)
                    and not isinstance(matched.get("reference_hits"), bool)
                    else len(references)
                ),
                "observation_base_hits": (
                    matched.get("observation_base_hits")
                    if isinstance(matched, Mapping)
                    and isinstance(matched.get("observation_base_hits"), int)
                    and not isinstance(matched.get("observation_base_hits"), bool)
                    else 0
                ),
                "references": references,
                "changed_ranges": changed_ranges,
                "receipt": str(receipt_path),
            })
            if len(rows) >= 16:
                break
        return rows

    def _interpretation_prompt(
        self, record: Any, context: Mapping[str, Any], question: str | None,
    ) -> tuple[str, list[str]]:
        header = [
            "You interpret one function of a PS2 game for the Cassi research programme.",
            "Every conclusion must cite the supplied evidence ids only; treat the atlas",
            "facts as recorded evidence, never as authoritative truth.",
            "",
        ]
        tail = []
        if question:
            tail.extend(["", f"Research question: {question}"])
        tail += [
            "",
            "Return JSON with exactly the keys pseudocode, behavioral_hypothesis,",
            "uncertainty, and evidence. Keep pseudocode under 2400 characters,",
            "each prose field under 700 characters, and cite at most 12 supplied ids.",
            "Separate direct loads and stores from addresses merely passed to callees;",
            "describe a callee's possible memory effects as uncertainty unless cited",
            "evidence establishes them.",
        ]
        evidence = context.get("evidence")
        if not isinstance(evidence, Mapping):
            raise ActivityRefused("the interpretation context lacks bounded evidence")
        high_priority = []
        disassembly = []
        for evidence_id, text in evidence.items():
            if not isinstance(evidence_id, str) or not isinstance(text, str):
                raise ActivityRefused("the interpretation context contains malformed evidence")
            item = (evidence_id, f"[{evidence_id}] {text}")
            (disassembly if text.startswith("disassembly: ") else high_priority).append(item)

        selected_lines: list[str] = []
        selected_ids: list[str] = []
        for evidence_id, line in high_priority + disassembly:
            candidate = "\n".join(header + selected_lines + [line] + tail)
            if len(candidate) > _PCSX2_PROMPT_LIMIT:
                continue
            selected_lines.append(line)
            selected_ids.append(evidence_id)
        prompt = "\n".join(header + selected_lines + tail)
        if not selected_ids or len(prompt) > _PCSX2_PROMPT_LIMIT:
            raise ActivityRefused("the interpretation prompt cannot retain bounded evidence")
        return prompt, selected_ids

    def _ask_brain(self, prompt: str) -> Any:
        entity = self.entity
        brain = getattr(entity, "brain", None) if entity is not None else None
        if brain is None or not callable(getattr(brain, "complete", None)):
            raise ActivityRefused("the resident brain is unavailable for interpretation")
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "cassi.pcsx2-function-interpretation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["pseudocode", "behavioral_hypothesis", "uncertainty", "evidence"],
                    "properties": {
                        "pseudocode": {"type": "string", "maxLength": _PCSX2_DECOMPILE_PSEUDOCODE_LIMIT},
                        "behavioral_hypothesis": {"type": "string", "maxLength": _PCSX2_DECOMPILE_PROSE_LIMIT},
                        "uncertainty": {"type": "string", "maxLength": _PCSX2_DECOMPILE_PROSE_LIMIT},
                        "evidence": {"type": "array", "items": {"type": "string"}, "maxItems": 16},
                    },
                },
            },
        }
        try:
            response = brain.complete(
                prompt=prompt,
                max_tokens=_PCSX2_DECOMPILE_MAX_TOKENS,
                thinking=False,
                response_format=response_format,
            )
        except Exception as exc:
            raise ActivityRefused(f"the resident brain refused interpretation: {exc}") from exc
        if not isinstance(response, Mapping):
            raise ActivityRefused("the resident brain returned a non-object response")
        if response.get("finish_reason") == "length":
            raise ActivityRefused("the resident brain interpretation exceeded its generation bound")
        content = response.get("content")
        if not isinstance(content, str):
            raise ActivityRefused("the resident brain returned no textual interpretation")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Tolerant parsing: unstructured text is kept as raw pseudocode evidence.
            return {"raw_text": content.strip()}

    def _validate_interpretation(self, value: Any, evidence_ids: list[str]) -> Mapping[str, Any]:
        required = {"pseudocode", "behavioral_hypothesis", "uncertainty", "evidence"}
        if isinstance(value, Mapping) and set(value) == {"raw_text"}:
            raw = value["raw_text"]
            if not isinstance(raw, str) or not raw or len(raw) > _PCSX2_DECOMPILE_PSEUDOCODE_LIMIT:
                raise ActivityRefused("the interpretation response exceeds its bounded text limits")
            return {
                "pseudocode": raw,
                "behavioral_hypothesis": "",
                "uncertainty": "the resident brain returned unstructured text; treat as raw evidence",
                "evidence": [],
            }
        if not isinstance(value, Mapping) or set(value) != required:
            raise ActivityRefused("the interpretation response lacks its required bounded structure")
        pseudocode = value["pseudocode"]
        hypothesis = value["behavioral_hypothesis"]
        uncertainty = value["uncertainty"]
        evidence = value["evidence"]
        if (
            not isinstance(pseudocode, str)
            or not pseudocode
            or len(pseudocode) > _PCSX2_DECOMPILE_PSEUDOCODE_LIMIT
            or not isinstance(hypothesis, str)
            or len(hypothesis) > _PCSX2_DECOMPILE_PROSE_LIMIT
            or not isinstance(uncertainty, str)
            or len(uncertainty) > _PCSX2_DECOMPILE_PROSE_LIMIT
        ):
            raise ActivityRefused("the interpretation response exceeds its bounded text limits")
        if not isinstance(evidence, list) or len(evidence) > len(evidence_ids):
            raise ActivityRefused("the interpretation evidence is not a bounded list")
        cited = []
        for row in evidence:
            if not isinstance(row, str) or row not in evidence_ids:
                raise ActivityRefused("the interpretation cites evidence outside the supplied ids")
            if row not in cited:
                cited.append(row)
        return {
            "pseudocode": pseudocode,
            "behavioral_hypothesis": hypothesis,
            "uncertainty": uncertainty,
            "evidence": cited,
        }

    def _persist_interpretation(self, operation_id: str, record: Any,
                                context: Mapping[str, Any],
                                prior: list[Mapping[str, Any]],
                                question: str | None,
                                supplied_evidence_ids: list[str],
                                value: Mapping[str, Any]) -> Mapping[str, Any]:
        raw_evidence = context.get("evidence")
        if not isinstance(raw_evidence, Mapping):
            raise ActivityRefused("the interpretation context lacks bounded evidence")
        supplied_evidence: dict[str, str] = {}
        for evidence_id in supplied_evidence_ids:
            text = raw_evidence.get(evidence_id)
            if not isinstance(text, str):
                raise ActivityRefused("the supplied interpretation evidence is inconsistent")
            supplied_evidence[evidence_id] = text
        body = {
            "schema": "cassi.pcsx2-function-interpretation.v1",
            "function": {
                "address": f"0x{record.address & 0xFFFF_FFFF:08X}",
                "name": record.name,
                "size": record.size,
                "source": record.source,
            },
            "question": question,
            "supplied_evidence": supplied_evidence,
            "source_relations": [dict(row) for row in prior],
            "interpretation": dict(value),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        path = (
            self.data_home / "artifacts" / "decompile" / _identity(operation_id)
            / "interpretation.json"
        )
        encoded = json.dumps(
            body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        _pcsx2_write_atomic(path, encoded)
        return {
            "schema": body["schema"],
            "path": str(path),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }

    def run(self, operation: str, parameters: Mapping[str, Any], *,
            program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        with self._lock:
            return self._run(operation, parameters, program=program, operation_id=operation_id)
