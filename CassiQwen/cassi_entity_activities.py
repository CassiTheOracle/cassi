"""Bounded, source-bound worlds admitted into the continuing Cassi entity."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
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
                  operation_id: str, result: Mapping[str, Any]) -> None:
    """File a compact sourced consequence in the same work memory as the brain."""
    entity._record(
        source_id=f"entity:hosted:{activity}:{_identity(operation_id)}",
        context={"entity_id": entity.config.entity_id,
                 "project_id": program["project_id"], "scope": "hosted-activity"},
        observed_at=datetime.now(timezone.utc).isoformat(),
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

