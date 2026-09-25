from __future__ import annotations

import struct
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cassi_coinbase_ingestion import (
    CoinbaseConfig,
    CoinbaseIngestionService,
    CoinbaseMessageProcessor,
    WebSocketConnection,
)
from cassi_market_ingestion import DataHealthMonitor, IngestionStore, utc_stamp


class FakeCoinbaseREST:
    def fetch_product(self, product: str):
        return {
            "id": product,
            "status": "online",
            "base_currency": "BTC",
            "quote_currency": "USD",
            "base_increment": "0.00000001",
            "quote_increment": "0.01",
            "min_market_funds": "10",
        }

    def fetch_candles(self, product: str, granularity: int, start: datetime, end: datetime):
        rows = []
        cursor = int(start.timestamp())
        while cursor < int(end.timestamp()):
            offset = (cursor // granularity) % 20
            opening = 100.0 + offset
            rows.append([cursor, opening - 1.0, opening + 2.0, opening, opening + 1.0, 10.0 + offset])
            cursor += granularity
        return list(reversed(rows))


class LaggingCoinbaseREST(FakeCoinbaseREST):
    """Serves candles only for buckets before ``published_until`` when it is set."""

    published_until: datetime | None = None

    def fetch_candles(self, product: str, granularity: int, start: datetime, end: datetime):
        rows = super().fetch_candles(product, granularity, start, end)
        if self.published_until is None:
            return rows
        cutoff = int(self.published_until.timestamp())
        return [row for row in rows if row[0] < cutoff]



class CoinbaseIngestionTests(unittest.TestCase):
    def test_bootstrap_processor_health_and_recording_replay_share_bar_root(self) -> None:
        now = datetime(2026, 1, 2, 0, 0, 3, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            config = CoinbaseConfig(product="BTC-USD", granularity=3600, bootstrap_bars=12, overlap_bars=3)
            source_path = directory / "source.sqlite3"
            with IngestionStore(source_path) as source:
                service = CoinbaseIngestionService(
                    source,
                    config,
                    rest_client=FakeCoinbaseREST(),
                    session_id="source-session",
                )
                bootstrap = service.bootstrap(now=now)
                self.assertEqual(bootstrap["reconciliation"]["accepted"], 12)
                received = utc_stamp(now + timedelta(seconds=1))
                processor = CoinbaseMessageProcessor(source, config)
                processor.process(
                    {
                        "type": "subscriptions",
                        "channels": [
                            {"name": "heartbeat", "product_ids": ["BTC-USD"]},
                            {"name": "ticker", "product_ids": ["BTC-USD"]},
                            {"name": "matches", "product_ids": ["BTC-USD"]},
                        ],
                    },
                    session_id="source-session",
                    received_at=received,
                    received_monotonic_ns=100,
                )
                processor.process(
                    {
                        "type": "heartbeat",
                        "sequence": 100,
                        "last_trade_id": 500,
                        "product_id": "BTC-USD",
                        "time": utc_stamp(now),
                    },
                    session_id="source-session",
                    received_at=received,
                    received_monotonic_ns=101,
                )
                processor.process(
                    {
                        "type": "ticker",
                        "sequence": 101,
                        "trade_id": 500,
                        "product_id": "BTC-USD",
                        "price": "101.0",
                        "best_bid": "100.9",
                        "best_ask": "101.1",
                        "time": utc_stamp(now),
                    },
                    session_id="source-session",
                    received_at=received,
                    received_monotonic_ns=102,
                )
                processor.process(
                    {
                        "type": "match",
                        "sequence": 102,
                        "trade_id": 501,
                        "product_id": "BTC-USD",
                        "price": "101.0",
                        "size": "0.01",
                        "side": "buy",
                        "time": utc_stamp(now),
                    },
                    session_id="source-session",
                    received_at=received,
                    received_monotonic_ns=103,
                )
                monitor = DataHealthMonitor(source, symbol="BTC-USD", granularity=3600)
                health = monitor.evaluate(now=now + timedelta(seconds=2))
                self.assertEqual(health.state, "GREEN")
                self.assertEqual(health.metrics["exchange_to_receipt_wall_delta_seconds"], 1.0)
                self.assertEqual(health.metrics["latest_market_received_at"], received)
                self.assertEqual(source.get_state("subscription_confirmed"), True)
                delayed_received = utc_stamp(now + timedelta(seconds=2))
                processor.process(
                    {
                        "type": "ticker",
                        "sequence": 103,
                        "trade_id": 502,
                        "product_id": "BTC-USD",
                        "price": "101.0",
                        "best_bid": "100.9",
                        "best_ask": "101.1",
                        "time": utc_stamp(now - timedelta(seconds=31)),
                    },
                    session_id="source-session",
                    received_at=delayed_received,
                    received_monotonic_ns=104,
                )
                divergent = monitor.evaluate(now=now + timedelta(seconds=3))
                self.assertEqual(divergent.state, "RED")
                self.assertFalse(divergent.can_open_exposure)
                self.assertEqual(divergent.metrics["exchange_to_receipt_wall_delta_seconds"], 33.0)
                self.assertTrue(
                    any(reason["code"] == "exchange-receipt-time-divergence" for reason in divergent.reasons)
                )
                bar_root = source.event_root(event_type="market-bar", subject_id="BTC-USD")
                market_root = source.event_root(subject_id="BTC-USD")
                recording = directory / "feed.jsonl.gz"
                export = source.export_recording(recording)
                self.assertGreater(export["records"], 3)
            with IngestionStore(directory / "replay.sqlite3") as replay_store:
                replay_service = CoinbaseIngestionService(
                    replay_store,
                    config,
                    rest_client=FakeCoinbaseREST(),
                    session_id="replay-session",
                )
                replay = replay_service.replay_recording(recording)
                self.assertEqual(replay["bar_event_root_sha256"], bar_root)
                self.assertEqual(replay["market_event_root_sha256"], market_root)
                self.assertEqual(len(replay_store.accepted_bars("BTC-USD")), 12)


    def test_public_feed_profiles_subscription_and_bars_gap_contract(self) -> None:
        now = datetime(2026, 1, 2, 0, 0, 3, tzinfo=timezone.utc)
        received = utc_stamp(now + timedelta(seconds=1))

        class RecordingSocket:
            def __init__(self) -> None:
                self.request = None

            def send_json(self, value) -> None:
                self.request = value

        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "market.sqlite3") as store:
            default = CoinbaseConfig(bootstrap_bars=12, overlap_bars=3)
            default_service = CoinbaseIngestionService(
                store, default, rest_client=FakeCoinbaseREST(), session_id="default"
            )
            default_socket = RecordingSocket()
            default_service._subscribe(default_socket)
            self.assertEqual(default_socket.request["channels"], ["heartbeat", "ticker", "matches"])

            configured = CoinbaseConfig(
                bootstrap_bars=12,
                overlap_bars=3,
                public_feed_channels="quotes",
                reconcile_interval_seconds=60,
            )
            service = CoinbaseIngestionService(
                store, configured, rest_client=FakeCoinbaseREST(), session_id="public-research"
            )
            service.bootstrap()
            websocket = RecordingSocket()
            service._subscribe(websocket)
            self.assertEqual(websocket.request["channels"], ["heartbeat", "ticker"])
            processor = service.processor
            processor.process(
                {
                    "type": "subscriptions",
                    "channels": [
                        {"name": "heartbeat", "product_ids": ["BTC-USD"]},
                        {"name": "ticker", "product_ids": ["BTC-USD"]},
                    ],
                },
                session_id="public-research",
                received_at=received,
            )
            self.assertTrue(store.get_state("subscription_confirmed"))
            trade_root_before = store.event_root(event_type="market-trade", subject_id="BTC-USD")
            quote_root_before = store.event_root(event_type="market-quote", subject_id="BTC-USD")
            processor.process(
                {
                    "type": "heartbeat",
                    "sequence": 100,
                    "last_trade_id": 500,
                    "product_id": "BTC-USD",
                    "time": utc_stamp(now),
                },
                session_id="public-research",
                received_at=received,
            )
            processor.process(
                {
                    "type": "ticker",
                    "sequence": 101,
                    "trade_id": 500,
                    "product_id": "BTC-USD",
                    "price": "101.0",
                    "best_bid": "100.9",
                    "best_ask": "101.1",
                    "time": utc_stamp(now),
                },
                session_id="public-research",
                received_at=received,
            )
            processor.process(
                {
                    "type": "heartbeat",
                    "sequence": 102,
                    "last_trade_id": 600,
                    "product_id": "BTC-USD",
                    "time": utc_stamp(now),
                },
                session_id="public-research",
                received_at=received,
            )
            self.assertFalse(store.get_state("recovery_required", False))
            self.assertEqual(store.metric("heartbeat_trade_gaps"), 0)
            self.assertEqual(store.metric("ws_messages"), 3)
            self.assertNotEqual(store.event_root(event_type="market-quote", subject_id="BTC-USD"), quote_root_before)
            self.assertEqual(store.event_root(event_type="market-trade", subject_id="BTC-USD"), trade_root_before)
            self.assertEqual(len(store.accepted_bars("BTC-USD")), 12)
            self.assertEqual(store.get_state("bar_gap_count:BTC-USD:3600"), 0)
            self.assertEqual(configured.reconcile_interval_seconds, 60)

            default_processor = CoinbaseMessageProcessor(store, default)
            default_processor.process(
                {
                    "type": "subscriptions",
                    "channels": [
                        {"name": "heartbeat", "product_ids": ["BTC-USD"]},
                        {"name": "ticker", "product_ids": ["BTC-USD"]},
                    ],
                },
                session_id="default",
                received_at=received,
            )
            self.assertFalse(store.get_state("subscription_confirmed"))
            for sequence, last_trade_id in ((103, 500), (104, 900)):
                default_processor.process(
                    {
                        "type": "heartbeat",
                        "sequence": sequence,
                        "last_trade_id": last_trade_id,
                        "product_id": "BTC-USD",
                        "time": utc_stamp(now),
                    },
                    session_id="default",
                    received_at=received,
                )
            self.assertEqual(store.metric("heartbeat_trade_gaps"), 399)
            self.assertEqual(store.get_state("recovery_required"), True)

        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "bars.sqlite3") as store:
            bars_config = CoinbaseConfig(
                bootstrap_bars=12,
                overlap_bars=3,
                public_feed_channels="bars",
                reconcile_interval_seconds=60,
            )
            bars_service = CoinbaseIngestionService(
                store, bars_config, rest_client=FakeCoinbaseREST(), session_id="bars-research"
            )
            bars_service.bootstrap()
            bars_socket = RecordingSocket()
            bars_service._subscribe(bars_socket)
            self.assertEqual(bars_socket.request["channels"], ["heartbeat"])
            bars_processor = bars_service.processor
            bars_processor.process(
                {
                    "type": "subscriptions",
                    "channels": [{"name": "heartbeat", "product_ids": ["BTC-USD"]}],
                },
                session_id="bars-research",
                received_at=received,
            )
            self.assertTrue(store.get_state("subscription_confirmed"))
            trade_root_before = store.event_root(event_type="market-trade", subject_id="BTC-USD")
            quote_root_before = store.event_root(event_type="market-quote", subject_id="BTC-USD")
            market_root_before = store.event_root(subject_id="BTC-USD")
            for sequence, last_trade_id in ((100, 500), (101, 700)):
                bars_processor.process(
                    {
                        "type": "heartbeat",
                        "sequence": sequence,
                        "last_trade_id": last_trade_id,
                        "product_id": "BTC-USD",
                        "time": utc_stamp(now),
                    },
                    session_id="bars-research",
                    received_at=received,
                )
            self.assertFalse(store.get_state("recovery_required", False))
            self.assertEqual(store.metric("heartbeat_trade_gaps"), 0)
            self.assertEqual(store.metric("trade_id_gaps"), 0)
            self.assertEqual(store.event_root(event_type="market-trade", subject_id="BTC-USD"), trade_root_before)
            self.assertEqual(store.event_root(event_type="market-quote", subject_id="BTC-USD"), quote_root_before)
            self.assertNotEqual(store.event_root(subject_id="BTC-USD"), market_root_before)

            monitor = DataHealthMonitor(store, symbol="BTC-USD", granularity=3600)
            health = monitor.evaluate(now=now + timedelta(seconds=2))
            self.assertEqual(health.state, "GREEN")
            self.assertEqual(health.metrics["latest_market_event_type"], "market-heartbeat")
            self.assertEqual(health.metrics["latest_market_received_at"], received)

            bars_service.reconcile(now=now + timedelta(seconds=60))
            self.assertEqual(store.metric("rest_reconciliations"), 2)
            self.assertEqual(len(store.accepted_bars("BTC-USD")), 12)
            self.assertEqual(store.get_state("bar_gap_count:BTC-USD:3600"), 0)
            self.assertFalse(store.get_state("recovery_required", False))

        with self.assertRaises(Exception) as ctx:
            CoinbaseConfig(bootstrap_bars=12, overlap_bars=3, public_feed_channels="matches")
        self.assertIn("public_feed_channels", str(ctx.exception))

    def test_trade_gap_sets_recovery_required_until_rest_reconciliation(self) -> None:
        now = datetime(2026, 1, 2, 0, 0, 3, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "market.sqlite3") as store:
            config = CoinbaseConfig(bootstrap_bars=12, overlap_bars=3)
            service = CoinbaseIngestionService(store, config, rest_client=FakeCoinbaseREST(), session_id="gap")
            service.bootstrap(now=now)
            processor = service.processor
            for trade_id in (100, 102):
                processor.process(
                    {
                        "type": "match",
                        "sequence": trade_id,
                        "trade_id": trade_id,
                        "product_id": "BTC-USD",
                        "price": "100",
                        "size": "0.1",
                        "side": "sell",
                        "time": utc_stamp(now),
                    },
                    session_id="gap",
                    received_at=utc_stamp(now + timedelta(seconds=trade_id - 99)),
                )
            self.assertEqual(store.get_state("recovery_required"), True)
            self.assertEqual(store.metric("trade_id_gaps"), 1)
            service.reconcile(now=now + timedelta(seconds=4))
            self.assertEqual(store.get_state("recovery_required"), False)

    def test_maintenance_prunes_expired_heartbeats_and_keeps_bars_and_deliveries(self) -> None:
        now = datetime(2026, 1, 2, 0, 0, 3, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "bars.sqlite3") as store:
            config = CoinbaseConfig(
                bootstrap_bars=12,
                overlap_bars=3,
                public_feed_channels="bars",
                transient_retention_seconds=3600,
                maintenance_interval_seconds=600,
            )
            service = CoinbaseIngestionService(store, config, rest_client=FakeCoinbaseREST(), session_id="retention")
            service.bootstrap(now=now)
            bar_root = store.event_root(event_type="market-bar", subject_id="BTC-USD")
            delivered = store.accepted_bars("BTC-USD")[0][0]
            store.mark_delivered("member", delivered.event_id, disposition="processed")
            for sequence, offset in ((100, -7200), (101, -5400), (102, -60)):
                at = utc_stamp(now + timedelta(seconds=offset))
                service.processor.process(
                    {"type": "heartbeat", "sequence": sequence, "last_trade_id": 400 + sequence,
                     "product_id": "BTC-USD", "time": at},
                    session_id="retention",
                    received_at=at,
                )
            raw_before = store.raw_count()
            pruned = service.maintain(now=now)
            self.assertEqual((pruned["events"], pruned["raw_messages"]), (2, 2))
            self.assertIsNone(service.maintain(now=now + timedelta(seconds=60)))
            self.assertEqual(store.raw_count(), raw_before - 2)
            self.assertEqual(store.retained_raw_count(), store.raw_count())
            self.assertEqual(store.event_root(event_type="market-bar", subject_id="BTC-USD"), bar_root)
            self.assertEqual(
                [event.payload["sequence"] for event in store.accepted_events(event_type="market-heartbeat")], [102],
            )
            self.assertEqual(store.delivery_count("member"), 1)
            with self.assertRaises(Exception):
                store.prune_transient(before=utc_stamp(now), event_types=("market-bar",))

    def test_bar_close_is_reconciled_promptly_and_health_waits_out_publication(self) -> None:
        def at(minute: int, second: int) -> datetime:
            return datetime(2026, 1, 2, 0, minute, second, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "bars.sqlite3") as store:
            rest = LaggingCoinbaseREST()
            config = CoinbaseConfig(granularity=300, bootstrap_bars=12, overlap_bars=3, public_feed_channels="bars")
            service = CoinbaseIngestionService(store, config, rest_client=rest, session_id="close")
            monitor = DataHealthMonitor(store, symbol="BTC-USD", granularity=300)

            def bar_missing(now: datetime) -> bool:
                return "latest-closed-bar-missing" in {reason["code"] for reason in monitor.evaluate(now=now).reasons}

            service.bootstrap(now=at(9, 30))
            self.assertEqual(service._next_reconcile, at(10, 2))

            rest.published_until = at(5, 0)
            service.reconcile(now=at(10, 2))
            self.assertEqual(service._next_reconcile, at(10, 7))
            self.assertFalse(bar_missing(at(10, 29)))
            self.assertTrue(bar_missing(at(10, 31)))

            rest.published_until = None
            service.reconcile(now=at(10, 7))
            self.assertEqual(store.latest_accepted_bar("BTC-USD")[1].timestamp, utc_stamp(at(5, 0)))
            self.assertEqual(service._next_reconcile, at(11, 7))
            self.assertFalse(bar_missing(at(10, 31)))

    def test_websocket_client_frame_is_masked_and_round_trips(self) -> None:
        payload = b'{"type":"subscribe"}'
        mask = b"\x01\x02\x03\x04"
        frame = WebSocketConnection.encode_client_frame(payload, mask_key=mask)
        self.assertTrue(frame[1] & 0x80)
        length = frame[1] & 0x7F
        offset = 2
        if length == 126:
            length = struct.unpack("!H", frame[offset : offset + 2])[0]
            offset += 2
        self.assertEqual(length, len(payload))
        self.assertEqual(frame[offset : offset + 4], mask)
        encoded = frame[offset + 4 :]
        decoded = bytes(value ^ mask[index % 4] for index, value in enumerate(encoded))
        self.assertEqual(decoded, payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
