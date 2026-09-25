#!/usr/bin/env python3
"""Run Cassi's durable read-only market ingestion and paper-consumer service."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cassi_coinbase_ingestion import COINBASE_RUN_SCHEMA, CoinbaseConfig, CoinbaseIngestionService
from cassi_market_contracts import digest_value
from cassi_market_ingestion import (
    CanonicalPaperConsumer,
    DataHealthMonitor,
    HealthPolicy,
    IngestionStore,
    atomic_write_json,
    utc_stamp,
)
from cassi_paper import PaperConfig, PaperSession
from cassi_trading_foundry import StrategyProgram


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("once", "live", "replay", "compact", "retract"),
        default="once",
        help=(
            "compact prunes expired liveness rows, thins health history, and rebuilds the file "
            "(feed stopped); retract withdraws every canonical event of one source"
        ),
    )
    parser.add_argument(
        "--retract-source",
        help="canonical source_id whose events are withdrawn by --mode retract",
    )
    parser.add_argument(
        "--retract-reason",
        default="source admitted non-market content",
        help="operator reason recorded with a retraction",
    )
    parser.add_argument("--db", type=Path, default=Path("_diag/market-ingestion/market.sqlite3"))
    parser.add_argument("--product", default="BTC-USD")
    parser.add_argument("--granularity", type=int, default=3600)
    parser.add_argument("--bootstrap-bars", type=int, default=299)
    parser.add_argument("--overlap-bars", type=int, default=6)
    parser.add_argument("--recording", type=Path, help="export exact raw messages as JSONL or JSONL.GZ")
    parser.add_argument("--replay", type=Path, help="raw recording used by --mode replay")
    parser.add_argument("--health", type=Path, default=Path("_diag/market-ingestion/health.json"))
    parser.add_argument("--receipt", type=Path, default=Path("_diag/market-ingestion/run-receipt.json"))
    parser.add_argument(
        "--public-feed-channels",
        choices=("all", "quotes", "bars"),
        default="all",
        help=(
            "public WebSocket channel profile: all (heartbeat+ticker+matches, default), "
            "quotes (heartbeat+ticker), bars (heartbeat only; closed bars via REST)"
        ),
    )
    parser.add_argument(
        "--transient-retention-hours",
        type=float,
        default=24.0,
        help="keep heartbeat rows and their raw messages this long; closed bars are kept forever (0 keeps all)",
    )
    parser.add_argument("--max-messages", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=0.0)
    parser.add_argument("--no-paper", action="store_true")
    parser.add_argument("--paper-state", type=Path, default=Path("_diag/market-ingestion/paper-state.json"))
    parser.add_argument("--paper-latest", type=Path, default=Path("_diag/market-ingestion/paper-latest.json"))
    parser.add_argument("--initial-cash", type=float, default=10_000.0)
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--max-drawdown", type=float, default=0.20)
    parser.add_argument("--require-account-reconciliation", action="store_true")
    return parser.parse_args()


def _paper_consumer(args: argparse.Namespace, store: IngestionStore) -> CanonicalPaperConsumer | None:
    if args.no_paper or args.mode == "replay":
        return None
    program = StrategyProgram.seed()
    config = PaperConfig(
        venue="coinbase-canonical-paper",
        initial_cash=args.initial_cash,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        max_drawdown=args.max_drawdown,
        timeframe_seconds=args.granularity,
    )
    if args.paper_state.is_file():
        session = PaperSession.load_state(args.paper_state, program)
        if session.config != config:
            raise SystemExit("paper state configuration mismatch")
    else:
        session = PaperSession(program, config=config)
    return CanonicalPaperConsumer(
        store=store,
        session=session,
        symbol=args.product,
        consumer_id=f"canonical-paper:{args.product}:{args.granularity}",
        state_path=args.paper_state,
        latest_path=args.paper_latest,
    )


def _compact(args: argparse.Namespace, store: IngestionStore, config: CoinbaseConfig) -> int:
    now = datetime.now(timezone.utc)
    pruned = None
    if config.transient_retention_seconds:
        pruned = store.prune_transient(
            before=utc_stamp(now - timedelta(seconds=config.transient_retention_seconds)),
        )
    thinned = store.thin_health_snapshots(interval_seconds=HealthPolicy().snapshot_interval_seconds)
    rebuilt = store.vacuum()
    receipt = {
        "schema": "cassi.market-ingestion-command.v1",
        "mode": "compact",
        "result": {"compacted_at": utc_stamp(now), "pruned": pruned, "health": thinned, "file": rebuilt},
        "db": str(args.db),
        "external_effect": "none",
        "authenticated_exchange_calls": 0,
        "order_submissions": 0,
    }
    receipt["content_sha256"] = digest_value(receipt)
    atomic_write_json(args.receipt, receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


def _retract(args: argparse.Namespace, store: IngestionStore) -> int:
    if not args.retract_source:
        raise SystemExit("--mode retract requires --retract-source")
    retraction = store.retract_events(
        source_id=args.retract_source,
        reason=args.retract_reason,
    )
    receipt = {
        "schema": "cassi.market-ingestion-command.v1",
        "mode": "retract",
        "result": retraction,
        "db": str(args.db),
        "external_effect": "none",
        "authenticated_exchange_calls": 0,
        "order_submissions": 0,
    }
    receipt["content_sha256"] = digest_value(receipt)
    atomic_write_json(args.receipt, receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


def main() -> int:
    args = parse_args()
    if args.max_messages < 0 or args.max_seconds < 0.0:
        raise SystemExit("run bounds cannot be negative")
    if args.transient_retention_hours < 0.0:
        raise SystemExit("transient retention cannot be negative")
    if args.mode == "replay" and args.replay is None:
        raise SystemExit("--mode replay requires --replay")
    if args.mode != "replay" and args.replay is not None:
        raise SystemExit("--replay is valid only with --mode replay")
    if args.mode != "retract" and args.retract_source is not None:
        raise SystemExit("--retract-source is valid only with --mode retract")
    config = CoinbaseConfig(
        product=args.product,
        granularity=args.granularity,
        bootstrap_bars=args.bootstrap_bars,
        overlap_bars=args.overlap_bars,
        public_feed_channels=args.public_feed_channels,
        transient_retention_seconds=int(args.transient_retention_hours * 3600),
    )
    with IngestionStore(args.db) as store:
        if args.mode == "compact":
            return _compact(args, store, config)
        if args.mode == "retract":
            return _retract(args, store)
        service = CoinbaseIngestionService(store, config)
        consumer = _paper_consumer(args, store)
        if args.mode == "replay":
            replay_path = args.replay
            if not isinstance(replay_path, Path):
                raise SystemExit("--mode replay requires a Path-valued --replay")
            result: dict[str, object] = service.replay_recording(replay_path)
            health_document = None
            consumer_result = None
        else:
            bootstrap = service.bootstrap()
            preparation = None if consumer is None else consumer.prepare()
            monitor = DataHealthMonitor(
                store,
                symbol=args.product,
                granularity=args.granularity,
                consumer_id=None if consumer is None else consumer.consumer_id,
                require_heartbeat=args.mode == "live",
                require_account_reconciliation=args.require_account_reconciliation,
            )
            if args.mode == "once":
                health = service.publish_health(monitor, args.health)
                consumer_result = None if consumer is None else consumer.drain(health)
                result = {
                    "schema": "cassi.market-ingestion-once.v1",
                    "status": "PASS" if health.state == "GREEN" else "DEGRADED",
                    "bootstrap": bootstrap,
                }
            else:
                def on_health(health_update):
                    if consumer is not None:
                        consumer.drain(health_update)

                raw_before_run = store.raw_count()
                live_result: dict[str, object] | None = None
                try:
                    live_result = service.run(
                        monitor,
                        health_path=args.health,
                        max_messages=args.max_messages,
                        max_seconds=args.max_seconds,
                        on_health=on_health,
                    )
                except KeyboardInterrupt:
                    pass
                health = service.publish_health(monitor, args.health)
                if live_result is None:
                    result = {
                        "schema": COINBASE_RUN_SCHEMA,
                        "status": "STOPPED_BY_OPERATOR",
                        "session_id": service.session_id,
                        "product": config.product,
                        "granularity": config.granularity,
                        "raw_records_captured": store.raw_count() - raw_before_run,
                        "health": health.as_dict(),
                        "bar_event_root_sha256": store.event_root(
                            event_type="market-bar",
                            subject_id=config.product,
                        ),
                        "market_event_root_sha256": store.event_root(subject_id=config.product),
                        "external_effect": "public-market-data-read-only",
                        "order_submissions": 0,
                    }
                    result["content_sha256"] = digest_value(result)
                else:
                    result = live_result
                consumer_result = None if consumer is None else consumer.drain(health)
            health_document = health.as_dict()
            result["paper_preparation"] = preparation
        export = None if args.recording is None else store.export_recording(args.recording)
        receipt = {
            "schema": "cassi.market-ingestion-command.v1",
            "mode": args.mode,
            "result": result,
            "health": health_document,
            "paper": consumer_result,
            "recording": export,
            "db": str(args.db),
            "external_effect": "public-market-data-read-only",
            "authenticated_exchange_calls": 0,
            "order_submissions": 0,
        }
        receipt["content_sha256"] = digest_value(receipt)
        atomic_write_json(args.receipt, receipt)
        print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
