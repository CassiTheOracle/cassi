#!/usr/bin/env python3
"""Run, inspect, and connect the canonical Cassi trading field."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import tempfile
import threading
from time import monotonic
from contextlib import ExitStack, contextmanager, nullcontext
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_trading_field import (  # type: ignore[import-not-found]
    CanonicalFieldConsumer,
    CanonicalFieldPaperConsumer,
    TradingField,
    TradingFieldConfig,
    generate_demo_bars,
    load_bars_csv,
)

from cassi_trader_application import TradingPaperApplication


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _bounded_poll_interval(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("poll interval must be a number") from exc
    if not 0.1 <= parsed <= 300.0:
        raise argparse.ArgumentTypeError("poll interval must be between 0.1 and 300 seconds")
    return parsed

def _positive_int_tuple(value: str) -> tuple[int, ...]:
    try:
        parsed = tuple(int(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "value must be a comma-separated list of positive integers"
        ) from exc
    if (
        not parsed
        or any(item < 1 for item in parsed)
        or tuple(sorted(set(parsed))) != parsed
    ):
        raise argparse.ArgumentTypeError(
            "values must be positive, sorted, and unique"
        )
    return parsed


def _number_tuple(value: str) -> tuple[float, ...]:
    try:
        parsed = tuple(float(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "value must be a comma-separated list of numbers"
        ) from exc
    if not parsed or tuple(sorted(set(parsed))) != parsed:
        raise argparse.ArgumentTypeError("values must be sorted and unique")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="One persistent field-owned trading intelligence connected to Cassi Hive."
    )
    parser.add_argument(
        "--data-home",
        type=Path,
        default=Path("_diag/trading-field"),
        help="persistent trading field home (default: _diag/trading-field)",
    )
    parser.add_argument(
        "--hive-home",
        type=Path,
        default=None,
        help="shared hive home; defaults to CASSI_HIVE_HOME or Cassi/.cassi/hive",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="admit a chronological market stream")
    source = run.add_mutually_exclusive_group()
    source.add_argument("--csv", type=Path, help="CSV with timestamp, OHLC, and volume")
    source.add_argument(
        "--ingestion-db",
        type=Path,
        help="SQLite market-ingestion store containing accepted closed candles",
    )
    source.add_argument(
        "--demo-bars",
        type=int,
        default=96,
        help="deterministic demo bars when --csv is omitted (default: 96)",
    )
    run.add_argument("--symbol", default="BTC-USD", help="symbol for a new field")
    run.add_argument(
        "--import-skills",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="persistently enable or disable staged hive skill imports",
    )
    run.add_argument(
        "--consumer-id",
        help="durable ingestion watermark identity; derived from the field home by default",
    )
    run.add_argument(
        "--max-new-bars",
        type=int,
        default=0,
        help="stop after this many new/pending bars; zero drains the selected source",
    )
    run.add_argument(
        "--paper-only",
        action="store_true",
        help="use the canonical field-selected paper consumer; requires --ingestion-db",
    )
    run.add_argument(
        "--entity-url",
        help="loopback entity server base URL required for paper runs",
    )
    run.add_argument(
        "--entity-program-id",
        help="authenticated entity program identity required for paper runs",
    )
    run.add_argument(
        "--entity-token-env",
        help="host environment variable containing the entity access token",
    )
    run.add_argument(
        "--follow",
        action="store_true",
        help="keep one paper worker open and process new accepted bars continuously",
    )
    run.add_argument(
        "--poll-interval",
        type=_bounded_poll_interval,
        default=1.0,
        help="interruptible follow polling interval in seconds (0.1 to 300; default: 1)",
    )
    run.add_argument(
        "--stop-file",
        type=Path,
        help="operator stop sentinel (default: STOP_PAPER_WORKER in the member home)",
    )
    run.add_argument(
        "--member-id",
        help="host identity to bind to a new paper application in this member home",
    )
    run.add_argument(
        "--mission-id",
        help="original host mission identity to bind to a new paper application",
    )
    run.add_argument(
        "--receipt",
        type=Path,
        help="atomically write a stable campaign receipt",
    )
    run.add_argument(
        "--update-thresholds",
        type=_positive_int_tuple,
        help=(
            "matured outcomes triggering initial field updates for a new field "
            "(comma-separated)"
        ),
    )
    run.add_argument(
        "--update-interval",
        type=_positive_int,
        help="matured outcomes between later field updates for a new field",
    )
    run.add_argument(
        "--semantic-panel-actions",
        type=_number_tuple,
        help="action levels carried by the compact semantic panel (comma-separated)",
    )
    run.add_argument(
        "--field-mode-count",
        type=_positive_int,
        help="declared field geometry for a new field (semantic region size)",
    )
    run.add_argument(
        "--semantic-panel-decisions",
        type=_positive_int,
        help="compact semantic panel size in decisions for a new field",
    )

    status = subparsers.add_parser("status", help="show field, risk, model, and hive state")
    status.add_argument(
        "--paper-only",
        action="store_true",
        help="inspect the durable paper application view; requires --ingestion-db",
    )
    status.add_argument(
        "--ingestion-db",
        type=Path,
        help="SQLite source database bound to the paper application view",
    )
    status.add_argument("--member-id", help="verify the persisted host member identity")
    status.add_argument("--mission-id", help="verify the persisted original mission identity")
    skills = subparsers.add_parser("skills", help="control hive skill exchange")
    skills.add_argument("action", choices=("status", "enable", "disable", "sync"))
    return parser


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))

def _digest(value: Any) -> str:
    blob = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _file_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _resident_config(evidence: Path) -> TradingFieldConfig | None:
    with evidence.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("kind") == "configuration":
                return TradingFieldConfig.from_mapping(row["payload"])
    return None


def _new_config(
    data_home: Path,
    symbol: str,
    *,
    update_thresholds: tuple[int, ...] | None,
    update_interval: int | None,
    field_mode_count: int | None,
    semantic_panel_decisions: int | None,
    semantic_panel_actions: tuple[float, ...] | None,
) -> TradingFieldConfig | None:
    requested = {
        "update_thresholds": update_thresholds,
        "update_interval": update_interval,
        "field_mode_count": field_mode_count,
        "semantic_panel_decisions": semantic_panel_decisions,
        "semantic_panel_actions": semantic_panel_actions,
    }
    evidence = data_home / "trading-evidence.jsonl"
    if evidence.exists():
        resident = _resident_config(evidence)
        if resident is None:
            return None
        # A resident field keeps the configuration it was created with. An
        # override that repeats the resident value is a resume and is allowed;
        # any other value would silently change what is being measured.
        changed = sorted(
            name
            for name, value in requested.items()
            if value is not None and value != getattr(resident, name)
        )
        if changed:
            raise SystemExit(
                "resident field keeps its "
                + " and ".join(changed)
                + "; a differing value requires a new --data-home"
            )
        return None
    defaults = TradingFieldConfig()
    return TradingFieldConfig(
        symbol=symbol,
        update_thresholds=(
            defaults.update_thresholds
            if update_thresholds is None
            else update_thresholds
        ),
        update_interval=(
            defaults.update_interval
            if update_interval is None
            else update_interval
        ),
        field_mode_count=(
            defaults.field_mode_count
            if field_mode_count is None
            else field_mode_count
        ),
        semantic_panel_decisions=(
            defaults.semantic_panel_decisions
            if semantic_panel_decisions is None
            else semantic_panel_decisions
        ),
        semantic_panel_actions=(
            defaults.semantic_panel_actions
            if semantic_panel_actions is None
            else semantic_panel_actions
        ),
    )

class _PaperWorkerLock:
    """Cross-platform exclusive lock for a member's controlling paper loop."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: Any = None
        self._windows = os.name == "nt"

    def __enter__(self) -> "_PaperWorkerLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+b")
        self._handle.seek(0, os.SEEK_END)
        if self._handle.tell() == 0:
            self._handle.write(b"\0")
            self._handle.flush()
        self._handle.seek(0)
        try:
            if self._windows:
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._handle.close()
            self._handle = None
            raise RuntimeError(
                "another paper worker already controls this member home"
            ) from exc
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            if self._windows:
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None




@contextmanager
def _open_field_session(
    data_home: Path,
    *,
    paper_worker: bool,
    config: TradingFieldConfig | None = None,
    hive_home: Path | None = None,
    import_skills: bool | None = None,
):
    with ExitStack() as stack:
        if paper_worker:
            stack.enter_context(_PaperWorkerLock(data_home / ".paper-worker.lock"))
        field = stack.enter_context(
            TradingField.open(
                data_home,
                config=config,
                hive_home=hive_home,
                import_skills=import_skills,
            )
        )
        yield field


def _program_summary(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    fields = (
        "program_id",
        "created_at",
        "mission_sha256",
        "mission_digest",
        "current_status",
        "status",
        "verified_at",
    )
    summary = {key: value[key] for key in fields if key in value}
    if "mission_digest" not in summary and "mission_sha256" in summary:
        summary["mission_digest"] = summary["mission_sha256"]
    if "current_status" not in summary and "status" in summary:
        summary["current_status"] = summary["status"]
    return summary


def _status_drain(
    last_drain: Mapping[str, Any] | None,
    consumer: CanonicalFieldPaperConsumer,
) -> dict[str, Any]:
    paper_status = consumer.paper_status()
    pending_after = (
        last_drain.get("pending_after", 0)
        if isinstance(last_drain, Mapping)
        else 0
    )
    return {
        "schema": (
            last_drain.get("schema")
            if isinstance(last_drain, Mapping)
            else "cassi.trading-field-paper-consumer.v1"
        ),
        "status": "status-refresh",
        "processed": 0,
        "pending_before": pending_after,
        "pending_after": pending_after,
        "paper_status": paper_status,
    }


def _write_paper_receipt(
    args: argparse.Namespace,
    *,
    data_home: Path,
    application: TradingPaperApplication,
    consumer: CanonicalFieldPaperConsumer,
    status: str,
    reason: str | None,
    processed_bars: int,
    verified_program: Mapping[str, Any] | None,
    health: Mapping[str, Any] | None,
    drain: Mapping[str, Any] | None,
    cancellation: Mapping[str, Any] | None,
    view: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    path = args.receipt.expanduser() if args.receipt is not None else None
    if path is None and (
        args.follow or status in {"BLOCKED", "ERROR", "STOPPED_BY_OPERATOR"}
    ):
        path = data_home / "trading-paper-worker-receipt.json"
    if path is None:
        return None
    paper_status = consumer.paper_status()
    body = {
        "schema": "cassi.trading-paper-run-receipt.v2",
        "mode": "follow" if args.follow else "once",
        "status": status,
        "reason": reason,
        "processed_bars": processed_bars,
        "application_view_path": str(application.view_path),
        "application_view_sha256": (
            view.get("content_sha256")
            if isinstance(view, Mapping)
            else None
        ),
        "entity_program": _program_summary(verified_program),
        "health": None if health is None else dict(health),
        "drain": None if drain is None else dict(drain),
        "paper_status": dict(paper_status),
        "pending_order": paper_status.get("pending_order"),
        "last_execution": paper_status.get("last_execution"),
        "pending_cancellation": (
            None if cancellation is None else dict(cancellation)
        ),
        "stop_file": (
            str(
                (
                    args.stop_file.expanduser()
                    if args.stop_file is not None
                    else data_home / "STOP_PAPER_WORKER"
                ).resolve()
            )
            if args.follow
            else None
        ),
        "external_effect": "none",
        "external_order_path": False,
    }
    receipt = {**body, "content_sha256": _digest(body)}
    _atomic_write(path, receipt)
    return {
        "path": str(path.resolve()),
        "content_sha256": receipt["content_sha256"],
    }


class _OperatorStopRequested(Exception):
    pass


def _authorized_paper_step(
    *,
    verifier: Any,
    application: TradingPaperApplication,
    store: Any,
    field: TradingField,
    consumer: CanonicalFieldPaperConsumer,
    monitor: Any,
    stop_check: Any = None,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    verified = verifier.verify()
    if not isinstance(verified, Mapping):
        raise TypeError("entity verifier returned a non-object result")
    if stop_check is not None and stop_check():
        raise _OperatorStopRequested
    bound = application.bind_verified_program(verified)
    if not isinstance(bound, Mapping):
        raise TypeError("paper application returned an invalid program attestation")
    health = monitor.evaluate().as_dict()
    if stop_check is not None and stop_check():
        raise _OperatorStopRequested
    drain = consumer.drain(max_bars=1, health=health)
    view = application.record_action(
        store=store,
        field=field,
        consumer=consumer,
        health=health,
        drain=drain,
    )
    return bound, health, drain, view

def _inactive_reason(exc: BaseException) -> str:
    status = getattr(exc, "status", None)
    if isinstance(status, str) and status.strip():
        safe_status = "".join(
            char.lower() if char.isalnum() else "-"
            for char in status.strip()
        ).strip("-")[:64]
        return f"entity-program-inactive:{safe_status or 'unknown'}"
    return "entity-program-inactive"


def _inactive_program_summary(
    program_id: str,
    exc: BaseException,
) -> dict[str, Any]:
    status = getattr(exc, "status", None)
    return {
        "program_id": program_id,
        "status": status if isinstance(status, str) else "inactive",
        "current_status": status if isinstance(status, str) else "inactive",
    }


def _install_stop_handlers(stop_event: threading.Event) -> dict[int, Any]:
    previous: dict[int, Any] = {}

    def request_stop(signum: int, frame: Any) -> None:
        stop_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, request_stop)
    return previous


def _restore_stop_handlers(previous: Mapping[int, Any]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def _run_paper_once(
    args: argparse.Namespace,
    *,
    data_home: Path,
    application: TradingPaperApplication,
    store: Any,
    field: TradingField,
    consumer: CanonicalFieldPaperConsumer,
    monitor: Any,
    verifier: Any,
    inactive_error: type[BaseException],
) -> dict[str, Any]:
    status = "PASS"
    reason: str | None = None
    processed_bars = 0
    verified_program: Mapping[str, Any] | None = None
    health: Mapping[str, Any] | None = None
    drain: Mapping[str, Any] | None = None
    cancellation: Mapping[str, Any] | None = None
    view: Mapping[str, Any] | None = None
    try:
        while True:
            if args.max_new_bars and processed_bars >= args.max_new_bars:
                break
            pending_before = store.pending_count(
                consumer.consumer_id,
                event_type="market-bar",
                subject_id=consumer.symbol,
            )
            if pending_before == 0:
                break
            try:
                verified_program, health, drain, view = _authorized_paper_step(
                    verifier=verifier,
                    application=application,
                    store=store,
                    field=field,
                    consumer=consumer,
                    monitor=monitor,
                )
            except inactive_error as exc:
                verified_program = _inactive_program_summary(
                    args.entity_program_id,
                    exc,
                )
                reason = _inactive_reason(exc)
                try:
                    cancellation = consumer.cancel_pending(reason)
                    status = "BLOCKED"
                except Exception:
                    status = "ERROR"
                    reason = "entity-program-inactive-cancellation-failed"
                break
            except KeyboardInterrupt:
                status = "STOPPED_BY_OPERATOR"
                reason = "operator-stop"
                try:
                    cancellation = consumer.cancel_pending(reason)
                except Exception:
                    status = "ERROR"
                    reason = "operator-stop-cancellation-failed"
                break
            except Exception as exc:
                verified_program = None
                status = "BLOCKED"
                reason = f"entity-or-paper-step-failed:{type(exc).__name__[:64]}"
                break
            count = drain.get("processed", 0)
            if isinstance(count, bool) or not isinstance(count, int) or count not in (0, 1):
                status = "ERROR"
                reason = "paper-consumer-violated-single-bar-bound"
                break
            processed_bars += count
            if count == 0:
                status = "BLOCKED"
                reason = "pending-source-bars-made-no-progress"
                break
    except KeyboardInterrupt:
        status = "STOPPED_BY_OPERATOR"
        reason = "operator-stop"
        try:
            cancellation = consumer.cancel_pending(reason)
        except Exception:
            status = "ERROR"
            reason = "operator-stop-cancellation-failed"

    receipt = _write_paper_receipt(
        args,
        data_home=data_home,
        application=application,
        consumer=consumer,
        status=status,
        reason=reason,
        processed_bars=processed_bars,
        verified_program=verified_program,
        health=health,
        drain=drain,
        cancellation=cancellation,
        view=view,
    )
    paper_status = dict(consumer.paper_status())
    return {
        "schema": "cassi.trading-paper-worker-result.v1",
        "mode": "once",
        "status": status,
        "reason": reason,
        "processed_bars": processed_bars,
        "application_view_path": str(application.view_path),
        "application_view_sha256": (
            view.get("content_sha256") if isinstance(view, Mapping) else None
        ),
        "entity_program": _program_summary(verified_program),
        "paper_status": paper_status,
        "pending_order": paper_status.get("pending_order"),
        "last_execution": paper_status.get("last_execution"),
        "campaign_receipt": receipt,
    }


def _run_paper_follow(
    args: argparse.Namespace,
    *,
    data_home: Path,
    application: TradingPaperApplication,
    store: Any,
    field: TradingField,
    consumer: CanonicalFieldPaperConsumer,
    monitor: Any,
    verifier: Any,
    inactive_error: type[BaseException],
    stop_event: threading.Event | None = None,
    announce_ready: bool = True,
) -> dict[str, Any]:
    stop_file = (
        args.stop_file.expanduser().resolve()
        if args.stop_file is not None
        else (data_home / "STOP_PAPER_WORKER").resolve()
    )
    stop_event = threading.Event() if stop_event is None else stop_event
    try:
        previous_handlers = _install_stop_handlers(stop_event)
    except ValueError:
        # Server-hosted workers run off the main thread and are stopped by their
        # owning entity's event; Python signal handlers are main-thread-only.
        previous_handlers = {}
    status = "RUNNING"
    reason: str | None = None
    processed_bars = 0
    verified_program: Mapping[str, Any] | None = None
    health: Mapping[str, Any] | None = None
    drain: Mapping[str, Any] | None = None
    cancellation: Mapping[str, Any] | None = None
    view: Mapping[str, Any] | None = None
    next_idle_verification = monotonic() + max(10.0, args.poll_interval)
    if announce_ready:
        print("CASSI_TRADER_PAPER_READY", flush=True)
    try:
        while True:
            if stop_event.is_set() or stop_file.is_file():
                status = "STOPPED_BY_OPERATOR"
                reason = "operator-stop"
                cancellation = consumer.cancel_pending(reason)
                break
            pending_before = store.pending_count(
                consumer.consumer_id,
                event_type="market-bar",
                subject_id=consumer.symbol,
            )
            if pending_before == 0 and monotonic() < next_idle_verification:
                stop_event.wait(args.poll_interval)
                continue
            try:
                if pending_before == 0:
                    # A paused mission must retire this member even between candles.
                    # Bound idle API traffic independently of the responsive stop poll.
                    verified_program = verifier.verify()
                    if not isinstance(verified_program, Mapping):
                        raise TypeError("entity verifier returned a non-object result")
                    next_idle_verification = monotonic() + max(10.0, args.poll_interval)
                    stop_event.wait(args.poll_interval)
                    continue
                verified_program, health, drain, view = _authorized_paper_step(
                    verifier=verifier,
                    application=application,
                    store=store,
                    field=field,
                    consumer=consumer,
                    monitor=monitor,
                    stop_check=lambda: stop_event.is_set() or stop_file.is_file(),
                )
                next_idle_verification = monotonic() + max(10.0, args.poll_interval)
            except _OperatorStopRequested:
                status = "STOPPED_BY_OPERATOR"
                reason = "operator-stop"
                cancellation = consumer.cancel_pending(reason)
                break
            except inactive_error as exc:
                status = "BLOCKED"
                reason = _inactive_reason(exc)
                verified_program = _inactive_program_summary(
                    args.entity_program_id,
                    exc,
                )
                cancellation = consumer.cancel_pending(reason)
                break
            except KeyboardInterrupt:
                status = "STOPPED_BY_OPERATOR"
                reason = "operator-stop"
                cancellation = consumer.cancel_pending(reason)
                break
            except Exception as exc:
                status = "BLOCKED"
                reason = f"entity-or-paper-step-failed:{type(exc).__name__[:64]}"
                verified_program = None
                break
            count = drain.get("processed", 0)
            if isinstance(count, bool) or not isinstance(count, int) or count not in (0, 1):
                status = "ERROR"
                reason = "paper-consumer-violated-single-bar-bound"
                break
            processed_bars += count
            if count == 0:
                status = "BLOCKED"
                reason = "pending-source-bars-made-no-progress"
                break
    except KeyboardInterrupt:
        status = "STOPPED_BY_OPERATOR"
        reason = "operator-stop"
        try:
            cancellation = consumer.cancel_pending(reason)
        except Exception:
            status = "ERROR"
            reason = "operator-stop-cancellation-failed"
    except Exception as exc:
        status = "ERROR"
        reason = f"paper-worker-failed:{type(exc).__name__[:64]}"
    finally:
        _restore_stop_handlers(previous_handlers)

    if status == "STOPPED_BY_OPERATOR" and verified_program is not None:
        try:
            health = monitor.evaluate().as_dict()
            status_drain = _status_drain(drain, consumer)
            view = application.record_action(
                store=store,
                field=field,
                consumer=consumer,
                health=health,
                drain=status_drain,
            )
            drain = status_drain
        except Exception:
            pass
    receipt = _write_paper_receipt(
        args,
        data_home=data_home,
        application=application,
        consumer=consumer,
        status=status,
        reason=reason,
        processed_bars=processed_bars,
        verified_program=verified_program,
        health=health,
        drain=drain,
        cancellation=cancellation,
        view=view,
    )
    paper_status = dict(consumer.paper_status())
    return {
        "schema": "cassi.trading-paper-worker-result.v1",
        "mode": "follow",
        "status": status,
        "reason": reason,
        "processed_bars": processed_bars,
        "stop_file": str(stop_file),
        "application_view_path": str(application.view_path),
        "application_view_sha256": (
            view.get("content_sha256") if isinstance(view, Mapping) else None
        ),
        "entity_program": _program_summary(verified_program),
        "paper_status": paper_status,
        "pending_order": paper_status.get("pending_order"),
        "last_execution": paper_status.get("last_execution"),
        "campaign_receipt": receipt,
    }


def _write_preflight_receipt(
    args: argparse.Namespace,
    *,
    data_home: Path,
    status: str,
    reason: str,
    paper_state_path: Path,
    verified_program: Mapping[str, Any] | None = None,
    inactive_status: str | None = None,
    cancellation: Mapping[str, Any] | None = None,
    consumer: CanonicalFieldPaperConsumer | None = None,
    application: TradingPaperApplication | None = None,
) -> dict[str, Any] | None:
    path = args.receipt.expanduser() if args.receipt is not None else None
    if path is None and (
        args.follow or status in {"BLOCKED", "ERROR", "STOPPED_BY_OPERATOR"}
    ):
        path = data_home / "trading-paper-worker-receipt.json"
    if path is None:
        return None
    paper_status = None if consumer is None else dict(consumer.paper_status())
    entity_program = _program_summary(verified_program)
    if entity_program is None and inactive_status is not None:
        entity_program = {
            "program_id": args.entity_program_id,
            "current_status": inactive_status,
        }
    body = {
        "schema": "cassi.trading-paper-run-receipt.v2",
        "mode": "follow" if args.follow else "once",
        "status": status,
        "reason": reason,
        "processed_bars": 0,
        "application_view_path": (
            str(application.view_path)
            if application is not None
            else str(data_home / "trading-paper-application.json")
        ),
        "application_view_sha256": None,
        "entity_program": entity_program,
        "health": None,
        "drain": None,
        "paper_status": paper_status,
        "pending_order": (
            None if paper_status is None else paper_status.get("pending_order")
        ),
        "last_execution": (
            None if paper_status is None else paper_status.get("last_execution")
        ),
        "pending_work_state": (
            "retained-unmodified" if paper_state_path.is_file() else "none"
        ),
        "paper_state_path": str(paper_state_path),
        "pending_cancellation": (
            None if cancellation is None else dict(cancellation)
        ),
        "external_effect": "none",
        "external_order_path": False,
    }
    receipt = {**body, "content_sha256": _digest(body)}
    _atomic_write(path, receipt)
    return {
        "path": str(path.resolve()),
        "content_sha256": receipt["content_sha256"],
    }


def _run_inactive_cancel(
    *,
    args: argparse.Namespace,
    data_home: Path,
    ingestion_db: Path,
    field: TradingField,
    consumer_id: str,
    paper_state_path: Path,
    granularity: int,
    reason: str,
    status_text: str | None,
    result_status: str = "BLOCKED",
    require_program_match: bool = True,
    store_type: Any,
    paper_config_type: Any,
) -> dict[str, Any] | None:
    binding_path = data_home / "trading-paper-application-binding.json"
    if not binding_path.is_file() or not paper_state_path.is_file():
        return None
    pinned: Mapping[str, Any] | None = None
    if require_program_match:
        try:
            previous_view = TradingPaperApplication.inspect(
                data_home=data_home,
                ingestion_db=ingestion_db,
                member_id=args.member_id,
                mission_id=args.mission_id,
            )
        except Exception:
            return None
        inspection = previous_view.get("inspection")
        pinned_value = (
            inspection.get("entity_program_attestation")
            if isinstance(inspection, Mapping)
            else None
        )
        if not isinstance(pinned_value, Mapping):
            return None
        pinned = pinned_value
        if pinned.get("program_id") != args.entity_program_id:
            return None
    application = TradingPaperApplication(
        data_home=data_home,
        ingestion_db=ingestion_db,
        symbol=field.config.symbol,
        consumer_id=consumer_id,
        paper_state_path=paper_state_path,
        member_id=args.member_id,
        mission_id=args.mission_id,
    )
    with store_type(ingestion_db) as store:
        consumer = CanonicalFieldPaperConsumer(
            store=store,
            field=field,
            symbol=field.config.symbol,
            consumer_id=consumer_id,
            paper_config=paper_config_type(timeframe_seconds=granularity),
            paper_state_path=paper_state_path,
        )
        cancellation = consumer.cancel_pending(reason)
        receipt = _write_preflight_receipt(
            args,
            data_home=data_home,
            status=result_status,
            reason=reason,
            paper_state_path=paper_state_path,
            inactive_status=status_text,
            cancellation=cancellation,
            consumer=consumer,
            application=application,
        )
        paper_status = dict(consumer.paper_status())
    entity_program = (
        {
            "program_id": args.entity_program_id,
            "current_status": status_text,
        }
        if status_text is not None
        else _program_summary(pinned)
    )
    return {
        "schema": "cassi.trading-paper-worker-result.v1",
        "mode": "follow" if args.follow else "once",
        "status": result_status,
        "reason": reason,
        "processed_bars": 0,
        "application_view_path": str(application.view_path),
        "entity_program": entity_program,
        "paper_status": paper_status,
        "pending_order": paper_status.get("pending_order"),
        "last_execution": paper_status.get("last_execution"),
        "campaign_receipt": receipt,
    }


def _run_paper_only(
    args: argparse.Namespace,
    *,
    data_home: Path,
    field: TradingField,
    _worker_lock_held: bool = False,
    verifier: Any | None = None,
    stop_event: threading.Event | None = None,
    announce_ready: bool = True,
) -> Mapping[str, Any]:
    if args.ingestion_db is None:
        raise SystemExit("--paper-only requires --ingestion-db")
    from cassi_market_ingestion import (  # type: ignore[import-not-found]
        DataHealthMonitor,
        IngestionStore,
    )
    from cassi_paper import PaperConfig  # type: ignore[import-not-found]
    from cassi_trader_application import (
        EntityProgramInactive,
        EntityProgramVerifier,
    )

    ingestion_db = args.ingestion_db.expanduser()
    consumer_id = args.consumer_id or (
        f"canonical-trading-paper:{field.config.symbol}:"
        f"{_digest(str(data_home.resolve()))[:16]}"
    )
    paper_state_path = data_home / "trading-paper-state.json"
    granularity = int(round(field.config.bar_hours * 3600))
    stop_file = (
        args.stop_file.expanduser().resolve()
        if args.stop_file is not None
        else (data_home / "STOP_PAPER_WORKER").resolve()
    )

    lock_context = (
        nullcontext()
        if _worker_lock_held
        else _PaperWorkerLock(data_home / ".paper-worker.lock")
    )
    with lock_context:
        binding_path = data_home / "trading-paper-application-binding.json"
        if args.follow and stop_file.is_file():
            if binding_path.is_file():
                try:
                    stopped = _run_inactive_cancel(
                        args=args,
                        data_home=data_home,
                        ingestion_db=ingestion_db,
                        field=field,
                        consumer_id=consumer_id,
                        paper_state_path=paper_state_path,
                        granularity=granularity,
                        reason="operator-stop",
                        status_text=None,
                        result_status="STOPPED_BY_OPERATOR",
                        require_program_match=False,
                        store_type=IngestionStore,
                        paper_config_type=PaperConfig,
                    )
                    if stopped is not None:
                        return stopped
                except Exception:
                    receipt = _write_preflight_receipt(
                        args,
                        data_home=data_home,
                        status="ERROR",
                        reason="operator-stop-cancellation-failed",
                        paper_state_path=paper_state_path,
                    )
                    return {
                        "schema": "cassi.trading-paper-worker-result.v1",
                        "mode": "follow",
                        "status": "ERROR",
                        "reason": "operator-stop-cancellation-failed",
                        "campaign_receipt": receipt,
                    }
            receipt = _write_preflight_receipt(
                args,
                data_home=data_home,
                status="STOPPED_BY_OPERATOR",
                reason="operator-stop",
                paper_state_path=paper_state_path,
            )
            return {
                "schema": "cassi.trading-paper-worker-result.v1",
                "mode": "follow",
                "status": "STOPPED_BY_OPERATOR",
                "reason": "operator-stop",
                "processed_bars": 0,
                "stop_file": str(stop_file),
                "campaign_receipt": receipt,
            }

        try:
            if verifier is None:
                verifier = EntityProgramVerifier(
                    args.entity_url,
                    args.entity_program_id,
                    token_env=args.entity_token_env,
                    data_home=data_home,
                    ingestion_db=ingestion_db,
                    timeout_seconds=5,
                )
            verifier_program_id = getattr(verifier, "program_id", None)
            if (
                getattr(args, "entity_program_id", None) is None
                and isinstance(verifier_program_id, str)
            ):
                setattr(args, "entity_program_id", verifier_program_id)
            initial_verification = verifier.verify()
            if not isinstance(initial_verification, Mapping):
                raise TypeError("entity verifier returned a non-object result")
            verified_id = initial_verification.get("program_id")
            requested_id = getattr(args, "entity_program_id", None)
            if (
                not isinstance(verified_id, str)
                or not verified_id.strip()
                or len(verified_id) > 512
                or (
                    requested_id is not None
                    and requested_id != verified_id
                )
            ):
                raise ValueError("entity verifier returned a different or invalid program identity")
            if requested_id is None:
                setattr(args, "entity_program_id", verified_id)
        except EntityProgramInactive as exc:
            inactive_status = getattr(exc, "status", None)
            status_text = (
                inactive_status
                if isinstance(inactive_status, str) and inactive_status.strip()
                else "inactive"
            )
            reason = _inactive_reason(exc)
            try:
                stopped = _run_inactive_cancel(
                    args=args,
                    data_home=data_home,
                    ingestion_db=ingestion_db,
                    field=field,
                    consumer_id=consumer_id,
                    paper_state_path=paper_state_path,
                    granularity=granularity,
                    reason=reason,
                    status_text=status_text,
                    store_type=IngestionStore,
                    paper_config_type=PaperConfig,
                )
                if stopped is not None:
                    return stopped
            except Exception:
                receipt = _write_preflight_receipt(
                    args,
                    data_home=data_home,
                    status="ERROR",
                    reason="entity-program-inactive-cancellation-failed",
                    paper_state_path=paper_state_path,
                    inactive_status=status_text,
                )
                return {
                    "schema": "cassi.trading-paper-worker-result.v1",
                    "mode": "follow" if args.follow else "once",
                    "status": "ERROR",
                    "reason": "entity-program-inactive-cancellation-failed",
                    "campaign_receipt": receipt,
                }
            receipt = _write_preflight_receipt(
                args,
                data_home=data_home,
                status="BLOCKED",
                reason=reason,
                paper_state_path=paper_state_path,
                inactive_status=status_text,
            )
            return {
                "schema": "cassi.trading-paper-worker-result.v1",
                "mode": "follow" if args.follow else "once",
                "status": "BLOCKED",
                "reason": reason,
                "processed_bars": 0,
                "entity_program": {
                    "program_id": args.entity_program_id,
                    "current_status": status_text,
                },
                "campaign_receipt": receipt,
            }
        except Exception as exc:
            reason = f"entity-program-verification-failed:{type(exc).__name__[:64]}"
            receipt = _write_preflight_receipt(
                args,
                data_home=data_home,
                status="BLOCKED",
                reason=reason,
                paper_state_path=paper_state_path,
            )
            return {
                "schema": "cassi.trading-paper-worker-result.v1",
                "mode": "follow" if args.follow else "once",
                "status": "BLOCKED",
                "reason": reason,
                "processed_bars": 0,
                "campaign_receipt": receipt,
            }

        try:
            application = TradingPaperApplication(
                data_home=data_home,
                ingestion_db=ingestion_db,
                symbol=field.config.symbol,
                consumer_id=consumer_id,
                paper_state_path=paper_state_path,
                member_id=args.member_id,
                mission_id=args.mission_id,
            )
        except Exception as exc:
            reason = f"paper-application-binding-failed:{type(exc).__name__[:64]}"
            receipt = _write_preflight_receipt(
                args,
                data_home=data_home,
                status="BLOCKED",
                reason=reason,
                paper_state_path=paper_state_path,
                verified_program=initial_verification,
            )
            return {
                "schema": "cassi.trading-paper-worker-result.v1",
                "mode": "follow" if args.follow else "once",
                "status": "BLOCKED",
                "reason": reason,
                "processed_bars": 0,
                "entity_program": _program_summary(initial_verification),
                "campaign_receipt": receipt,
            }
        try:
            bound_verification = application.bind_verified_program(initial_verification)
            if not isinstance(bound_verification, Mapping):
                raise TypeError("paper application returned an invalid program attestation")
            initial_verification = bound_verification
        except Exception as exc:
            reason = f"entity-program-binding-failed:{type(exc).__name__[:64]}"
            receipt = _write_preflight_receipt(
                args,
                data_home=data_home,
                status="BLOCKED",
                reason=reason,
                paper_state_path=paper_state_path,
                verified_program=initial_verification,
                application=application,
            )
            return {
                "schema": "cassi.trading-paper-worker-result.v1",
                "mode": "follow" if args.follow else "once",
                "status": "BLOCKED",
                "reason": reason,
                "processed_bars": 0,
                "application_view_path": str(application.view_path),
                "entity_program": _program_summary(initial_verification),
                "campaign_receipt": receipt,
            }

        consumer = None
        try:
            with IngestionStore(ingestion_db) as store:
                monitor = DataHealthMonitor(
                    store,
                    symbol=field.config.symbol,
                    granularity=granularity,
                    consumer_id=consumer_id,
                    require_heartbeat=True,
                    require_account_reconciliation=False,
                )
                consumer = CanonicalFieldPaperConsumer(
                    store=store,
                    field=field,
                    symbol=field.config.symbol,
                    consumer_id=consumer_id,
                    paper_config=PaperConfig(timeframe_seconds=granularity),
                    paper_state_path=paper_state_path,
                )
                consumer.activate()
                if args.follow:
                    return _run_paper_follow(
                        args,
                        data_home=data_home,
                        application=application,
                        store=store,
                        field=field,
                        consumer=consumer,
                        monitor=monitor,
                        verifier=verifier,
                        inactive_error=EntityProgramInactive,
                        stop_event=stop_event,
                        announce_ready=announce_ready,
                    )
                return _run_paper_once(
                    args,
                    data_home=data_home,
                    application=application,
                    store=store,
                    field=field,
                    consumer=consumer,
                    monitor=monitor,
                    verifier=verifier,
                    inactive_error=EntityProgramInactive,
                )
        except Exception as exc:
            reason = f"paper-worker-failed:{type(exc).__name__[:64]}"
            receipt = _write_preflight_receipt(
                args,
                data_home=data_home,
                status="ERROR",
                reason=reason,
                paper_state_path=paper_state_path,
                verified_program=initial_verification,
                consumer=consumer,
                application=application,
            )
            return {
                "schema": "cassi.trading-paper-worker-result.v1",
                "mode": "follow" if args.follow else "once",
                "status": "ERROR",
                "reason": reason,
                "processed_bars": 0,
                "application_view_path": str(application.view_path),
                "entity_program": _program_summary(initial_verification),
                "paper_status": (
                    None if consumer is None else dict(consumer.paper_status())
                ),
                "campaign_receipt": receipt,
            }


_HOSTED_MAX_NEW_BARS = 256


def run_hosted_trading_field(
    args: argparse.Namespace,
    *,
    owner: Any,
    verifier: Any | None = None,
    stop_event: threading.Event | None = None,
) -> Mapping[str, Any]:
    """Run canonical ingestion or a paper-only worker on a borrowed owner."""
    if owner is None:
        raise ValueError("hosted trading requires a borrowed serialized owner")
    if getattr(args, "command", None) != "run":
        raise ValueError("hosted trading accepts only the run command")
    ingestion_value = getattr(args, "ingestion_db", None)
    if ingestion_value is None:
        raise ValueError("hosted trading requires a canonical --ingestion-db source")
    paper_only = bool(getattr(args, "paper_only", False))
    follow = bool(getattr(args, "follow", False))
    if follow and not paper_only:
        raise ValueError("hosted follow mode requires --paper-only")
    if getattr(args, "stop_file", None) is not None and not follow:
        raise ValueError("a hosted stop file is only valid in follow mode")
    max_new_bars = getattr(args, "max_new_bars", 0)
    if isinstance(max_new_bars, bool) or not isinstance(max_new_bars, int):
        raise ValueError("--max-new-bars must be an integer")
    if follow:
        if max_new_bars != 0:
            raise ValueError("hosted follow mode cannot be combined with --max-new-bars")
        poll_interval = getattr(args, "poll_interval", 1.0)
        if (
            isinstance(poll_interval, bool)
            or not isinstance(poll_interval, (int, float))
            or not 0.1 <= poll_interval <= 300.0
        ):
            raise ValueError("hosted follow polling interval must be between 0.1 and 300 seconds")
        if stop_event is not None and not all(
            callable(getattr(stop_event, name, None))
            for name in ("is_set", "set", "wait")
        ):
            raise TypeError("stop_event must provide Event-compatible set, is_set, and wait")
    else:
        if not 1 <= max_new_bars <= _HOSTED_MAX_NEW_BARS:
            raise ValueError(
                f"hosted trading requires --max-new-bars between 1 and {_HOSTED_MAX_NEW_BARS}"
            )
        if stop_event is not None:
            raise ValueError("stop_event is only accepted for hosted follow mode")
    if paper_only and verifier is None:
        raise ValueError("hosted paper trading requires an injected active-program verifier")
    if not paper_only and verifier is not None:
        raise ValueError("a program verifier is only accepted for paper-only runs")

    data_home = Path(args.data_home).expanduser()
    ingestion_db = Path(ingestion_value).expanduser()
    consumer_id = getattr(args, "consumer_id", None) or (
        f"canonical-trading-{('paper' if paper_only else 'field')}:"
        f"{getattr(args, 'symbol', 'BTC-USD')}:"
        f"{_digest(str(data_home.resolve()))[:16]}"
    )
    config = _new_config(
        data_home,
        getattr(args, "symbol", "BTC-USD"),
        update_thresholds=getattr(args, "update_thresholds", None),
        update_interval=getattr(args, "update_interval", None),
        field_mode_count=getattr(args, "field_mode_count", None),
        semantic_panel_decisions=getattr(args, "semantic_panel_decisions", None),
        semantic_panel_actions=getattr(args, "semantic_panel_actions", None),
    )
    receipt_path_value = getattr(args, "receipt", None)
    receipt_path = (
        None if receipt_path_value is None else Path(receipt_path_value).expanduser()
    )
    hive_home_value = getattr(args, "hive_home", None)
    hive_home = None if hive_home_value is None else Path(hive_home_value).expanduser()
    import_skills = getattr(args, "import_skills", None)
    from cassi_market_ingestion import IngestionStore  # type: ignore[import-not-found]

    if paper_only:
        worker_args = argparse.Namespace(**vars(args))
        # The hosted receipt below binds the worker outcome to the canonical
        # ingestion root; keep one stable receipt format and avoid overwriting it.
        worker_args.receipt = None
        with _PaperWorkerLock(data_home / ".paper-worker.lock"):
            with TradingField.open(
                data_home,
                config=config,
                hive_home=hive_home,
                import_skills=import_skills,
                owner=owner,
            ) as field:
                result = dict(
                    _run_paper_only(
                        worker_args,
                        data_home=data_home,
                        field=field,
                        _worker_lock_held=True,
                        announce_ready=False,
                        verifier=verifier,
                        stop_event=stop_event,
                    )
                )
                with IngestionStore(ingestion_db) as store:
                    source = {
                        "kind": "market-ingestion-sqlite",
                        "path": str(ingestion_db.resolve()),
                        "consumer_id": consumer_id,
                        "accepted_event_root_sha256": store.event_root(
                            event_type="market-bar",
                            subject_id=field.config.symbol,
                        ),
                    }
                receipt_body = {
                    "schema": "cassi.trading-hosted-paper-receipt.v1",
                    "source": source,
                    "status": result.get("status"),
                    "reason": result.get("reason"),
                    "processed_bars": result.get("processed_bars", 0),
                    "application_view_sha256": result.get(
                        "application_view_sha256"
                    ),
                    "entity_program": result.get("entity_program"),
                    "paper_status": result.get("paper_status"),
                    "worker_receipt": result.get("campaign_receipt"),
                    "external_effect": "none",
                    "external_order_path": False,
                }
                receipt = {
                    **receipt_body,
                    "content_sha256": _digest(receipt_body),
                }
                if receipt_path is not None:
                    _atomic_write(receipt_path, receipt)
                return {
                    **result,
                    "campaign_receipt": receipt,
                    "campaign_receipt_path": (
                        None
                        if receipt_path is None
                        else str(receipt_path.resolve())
                    ),
                }

    with TradingField.open(
        data_home,
        config=config,
        hive_home=hive_home,
        import_skills=import_skills,
        owner=owner,
    ) as field:
        before = field.status()
        with IngestionStore(ingestion_db) as store:
            consumer = CanonicalFieldConsumer(
                store=store,
                field=field,
                symbol=field.config.symbol,
                consumer_id=consumer_id,
            )
            result = dict(consumer.drain(max_bars=max_new_bars))
            source = {
                "kind": "market-ingestion-sqlite",
                "path": str(ingestion_db.resolve()),
                "consumer_id": consumer_id,
                "accepted_event_root_sha256": store.event_root(
                    event_type="market-bar",
                    subject_id=field.config.symbol,
                ),
            }
        receipt_body = {
            "schema": "cassi.trading-field-campaign.v1",
            "source": source,
            "before": before,
            "result": result,
        }
        receipt = {
            **receipt_body,
            "content_sha256": _digest(receipt_body),
        }
        if receipt_path is not None:
            _atomic_write(receipt_path, receipt)
        return {
            "schema": "cassi.trading-hosted-result.v1",
            "mode": "ingestion",
            "status": "PASS",
            "result": result,
            "campaign_receipt": receipt,
            "campaign_receipt_path": (
                None if receipt_path is None else str(receipt_path.resolve())
            ),
        }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_home = args.data_home.expanduser()
    hive_home = None if args.hive_home is None else args.hive_home.expanduser()

    if args.command == "run":
        if args.max_new_bars < 0:
            raise SystemExit("--max-new-bars cannot be negative")
        if args.paper_only:
            if args.ingestion_db is None:
                raise SystemExit("--paper-only requires --ingestion-db")
            missing_entity_options = [
                option
                for option, value in (
                    ("--entity-url", args.entity_url),
                    ("--entity-program-id", args.entity_program_id),
                    ("--entity-token-env", args.entity_token_env),
                )
                if not isinstance(value, str) or not value.strip()
            ]
            if missing_entity_options:
                raise SystemExit(
                    "paper runs require " + ", ".join(missing_entity_options)
                )
            if args.follow and args.max_new_bars:
                raise SystemExit("--follow cannot be combined with --max-new-bars")
            if args.stop_file is not None and not args.follow:
                raise SystemExit("--stop-file requires --follow")
        else:
            if args.member_id is not None or args.mission_id is not None:
                raise SystemExit("--member-id and --mission-id require --paper-only")
            if (
                args.entity_url is not None
                or args.entity_program_id is not None
                or args.entity_token_env is not None
                or args.follow
                or args.stop_file is not None
            ):
                raise SystemExit(
                    "entity and worker options require --paper-only"
                )
        config = _new_config(
            data_home,
            args.symbol,
            update_thresholds=args.update_thresholds,
            update_interval=args.update_interval,
            field_mode_count=args.field_mode_count,
            semantic_panel_decisions=args.semantic_panel_decisions,
            semantic_panel_actions=args.semantic_panel_actions,
        )
        with _open_field_session(
            data_home,
            paper_worker=args.paper_only,
            config=config,
            hive_home=hive_home,
            import_skills=args.import_skills,
        ) as field:
            before = field.status()
            if args.paper_only:
                result = _run_paper_only(
                    args,
                    data_home=data_home,
                    field=field,
                    _worker_lock_held=True,
                )
                _print(result)
                return (
                    0
                    if result.get("status") in {"PASS", "STOPPED_BY_OPERATOR"}
                    else 2
                )
            if args.ingestion_db is not None:
                from cassi_market_ingestion import IngestionStore  # type: ignore[import-not-found]

                ingestion_db = args.ingestion_db.expanduser()
                consumer_id = args.consumer_id or (
                    f"canonical-trading-field:{field.config.symbol}:"
                    f"{_digest(str(data_home.resolve()))[:16]}"
                )
                with IngestionStore(ingestion_db) as store:
                    consumer = CanonicalFieldConsumer(
                        store=store,
                        field=field,
                        symbol=field.config.symbol,
                        consumer_id=consumer_id,
                    )
                    result = consumer.drain(max_bars=args.max_new_bars)
                    source_document = {
                        "kind": "market-ingestion-sqlite",
                        "path": str(ingestion_db.resolve()),
                        "consumer_id": consumer_id,
                        "accepted_event_root_sha256": store.event_root(
                            event_type="market-bar",
                            subject_id=field.config.symbol,
                        ),
                    }
            else:
                bars = (
                    load_bars_csv(
                        args.csv.expanduser(),
                        symbol=field.config.symbol,
                    )
                    if args.csv is not None
                    else generate_demo_bars(
                        args.demo_bars,
                        symbol=field.config.symbol,
                    )
                )
                total_bars = len(bars)
                if args.max_new_bars:
                    stop = min(
                        total_bars,
                        int(before["bar_count"]) + args.max_new_bars,
                    )
                    bars = bars[:stop]
                result = field.run(bars)
                source_document = {
                    "kind": "csv" if args.csv is not None else "deterministic-demo",
                    "path": (
                        None
                        if args.csv is None
                        else str(args.csv.expanduser().resolve())
                    ),
                    "file_sha256": (
                        None
                        if args.csv is None
                        else _file_sha256(args.csv.expanduser())
                    ),
                    "source_bar_count": total_bars,
                    "selected_bar_count": len(bars),
                    "first_timestamp": bars[0].timestamp if bars else None,
                    "last_timestamp": bars[-1].timestamp if bars else None,
                }
            if args.receipt is not None:
                receipt_body = {
                    "schema": "cassi.trading-field-campaign.v1",
                    "source": source_document,
                    "before": before,
                    "result": result,
                }
                receipt = {
                    **receipt_body,
                    "content_sha256": _digest(receipt_body),
                }
                receipt_path = args.receipt.expanduser()
                _atomic_write(receipt_path, receipt)
                result = {
                    **result,
                    "campaign_receipt": str(receipt_path.resolve()),
                    "campaign_receipt_sha256": receipt["content_sha256"],
                }
            _print(result)
        return 0

    if args.command == "status" and args.paper_only:
        if args.ingestion_db is None:
            raise SystemExit("status --paper-only requires --ingestion-db")
        result = TradingPaperApplication.inspect(
            data_home=data_home,
            ingestion_db=args.ingestion_db,
            member_id=args.member_id,
            mission_id=args.mission_id,
        )
        _print(result)
        return 0
    if args.command == "status" and (
        args.ingestion_db is not None
        or args.member_id is not None
        or args.mission_id is not None
    ):
        raise SystemExit("status paper identity options require --paper-only")
    with TradingField.open(data_home, hive_home=hive_home) as field:
        if args.command == "status" or args.action == "status":
            result = field.status()
        elif args.action == "enable":
            result = field.enable_skill_imports()
        elif args.action == "disable":
            result = field.disable_skill_imports()
        else:
            result = field.sync_skills()
        _print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
