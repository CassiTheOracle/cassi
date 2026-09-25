from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cassi_market_ingestion import (
    CanonicalPaperConsumer,
    DataHealth,
    DataHealthMonitor,
    HealthPolicy,
    IngestionError,
    IngestionStore,
    utc_stamp,
)
from cassi_paper import PaperConfig, PaperSession
from cassi_trading_foundry import MarketBar, StrategyProgram


class MarketIngestionCoreTests(unittest.TestCase):
    def _bar(self, hour: int, *, close: float = 101.0) -> MarketBar:
        high = max(102.0, close + 1.0)
        return MarketBar(
            timestamp=f"2026-01-01T{hour:02d}:00:00.000000Z",
            symbol="BTC-USD",
            open=100.0,
            high=high,
            low=99.0,
            close=close,
            volume=10.0,
        )

    def _capture(self, store: IngestionStore, index: int, received_at: str):
        return store.capture_raw(
            source_id="coinbase-exchange",
            session_id="test-session",
            channel="rest:candles",
            payload={"row": index},
            received_at=received_at,
            observed_at=received_at,
        )

    def test_closed_bar_admission_is_idempotent_durable_and_rejects_lookahead(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "market.sqlite3"
            with IngestionStore(path) as store:
                available = "2026-01-01T01:00:02.000000Z"
                capture = self._capture(store, 1, available)
                accepted = store.ingest_bar(
                    self._bar(0),
                    source_id="coinbase-exchange",
                    source_revision="test-v1",
                    granularity=3600,
                    available_at=available,
                    raw_id=capture.raw_id,
                    origin="test-rest",
                )
                duplicate_capture = self._capture(store, 2, available)
                duplicate = store.ingest_bar(
                    self._bar(0),
                    source_id="coinbase-exchange",
                    source_revision="test-v1",
                    granularity=3600,
                    available_at=available,
                    raw_id=duplicate_capture.raw_id,
                    origin="test-rest",
                )
                self.assertEqual(accepted.status, "accepted")
                self.assertEqual(duplicate.status, "duplicate")
                self.assertEqual(len(store.accepted_bars("BTC-USD")), 1)
                self.assertEqual(store.raw_count(), 2)
                event_root = store.event_root(event_type="market-bar", subject_id="BTC-USD")
                with self.assertRaises(IngestionError):
                    store.ingest_bar(
                        self._bar(1),
                        source_id="coinbase-exchange",
                        source_revision="test-v1",
                        granularity=3600,
                        available_at="2026-01-01T01:59:59.000000Z",
                        raw_id=None,
                        origin="test-rest",
                    )
            with IngestionStore(path) as reopened:
                self.assertEqual(reopened.event_root(event_type="market-bar", subject_id="BTC-USD"), event_root)
                self.assertEqual(len(reopened.accepted_bars("BTC-USD")), 1)

    def test_pending_event_page_advances_after_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "market.sqlite3") as store:
            admitted = []
            for hour in range(4):
                result = store.ingest_bar(
                    self._bar(hour),
                    source_id="coinbase-exchange",
                    source_revision="test-v1",
                    granularity=3600,
                    available_at=f"2026-01-01T{hour + 1:02d}:00:01.000000Z",
                    raw_id=None,
                    origin="rest",
                )
                admitted.append(result.event.event_id)
            pending = lambda limit=None: store.pending_events(
                "trader-member",
                event_type="market-bar",
                subject_id="BTC-USD",
                limit=limit,
            )
            self.assertEqual([event.event_id for event in pending(2)], admitted[:2])
            store.mark_delivered("trader-member", admitted[0], disposition="processed")
            self.assertEqual([event.event_id for event in pending(1)], admitted[1:2])
            self.assertEqual([event.event_id for event in pending()], admitted[1:])
            with self.assertRaises(IngestionError):
                pending(0)
            with self.assertRaises(IngestionError):
                pending(True)

    def test_conflicting_bar_requires_repeat_confirmation_before_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "market.sqlite3") as store:
            first_at = "2026-01-01T01:00:02.000000Z"
            first = self._capture(store, 1, first_at)
            store.ingest_bar(
                self._bar(0, close=101.0),
                source_id="coinbase-exchange",
                source_revision="test-v1",
                granularity=3600,
                available_at=first_at,
                raw_id=first.raw_id,
                origin="rest",
                promote_after_confirmations=2,
            )
            second_at = "2026-01-01T01:05:00.000000Z"
            conflict = store.ingest_bar(
                self._bar(0, close=103.0),
                source_id="coinbase-exchange",
                source_revision="test-v1",
                granularity=3600,
                available_at=second_at,
                raw_id=self._capture(store, 2, second_at).raw_id,
                origin="rest",
                promote_after_confirmations=2,
            )
            self.assertEqual(conflict.status, "conflict")
            self.assertEqual(store.unresolved_conflicts(), 1)
            confirmed_at = "2026-01-01T01:10:00.000000Z"
            confirmed = store.ingest_bar(
                self._bar(0, close=103.0),
                source_id="coinbase-exchange",
                source_revision="test-v1",
                granularity=3600,
                available_at=confirmed_at,
                raw_id=self._capture(store, 3, confirmed_at).raw_id,
                origin="rest",
                promote_after_confirmations=2,
            )
            self.assertEqual(confirmed.status, "promoted")
            self.assertEqual(store.unresolved_conflicts(), 0)
            latest = store.latest_accepted_bar("BTC-USD")
            self.assertIsNotNone(latest)
            assert latest is not None
            self.assertEqual(latest[1].close, 103.0)

    def test_health_circuit_changes_from_green_to_red_when_heartbeat_stales(self) -> None:
        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "market.sqlite3") as store:
            now = datetime(2026, 1, 1, 2, 0, 3, tzinfo=timezone.utc)
            available = utc_stamp(now)
            store.ingest_bar(
                self._bar(1),
                source_id="coinbase-exchange",
                source_revision="test-v1",
                granularity=3600,
                available_at=available,
                raw_id=self._capture(store, 1, available).raw_id,
                origin="rest",
            )
            store.set_state("subscription_confirmed", True, at=available)
            store.set_state("bar_gap_count:BTC-USD:3600", 0, at=available)
            store.set_state("recovery_required", False, at=available)
            for activity in ("heartbeat", "market", "reconcile"):
                store.note_activity(activity, at=available)
            monitor = DataHealthMonitor(store, symbol="BTC-USD", granularity=3600)
            green = monitor.evaluate(now=now)
            red = monitor.evaluate(now=now + timedelta(seconds=20))
            self.assertEqual(green.state, "GREEN")
            self.assertTrue(green.can_open_exposure)
            self.assertEqual(green.metrics["candle_close_to_receipt_wall_delta_seconds"], 3.0)
            self.assertIsNone(green.metrics["exchange_to_receipt_wall_delta_seconds"])
            self.assertEqual(red.state, "RED")
            self.assertFalse(red.can_open_exposure)
            self.assertTrue(any(reason["code"] == "heartbeat-stale" for reason in red.reasons))

    def test_health_history_keeps_transitions_and_one_row_per_interval(self) -> None:
        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "market.sqlite3") as store:
            start = datetime(2026, 1, 1, 2, 0, 3, tzinfo=timezone.utc)
            available = utc_stamp(start)
            store.ingest_bar(
                self._bar(1),
                source_id="coinbase-exchange",
                source_revision="test-v1",
                granularity=3600,
                available_at=available,
                raw_id=self._capture(store, 1, available).raw_id,
                origin="rest",
            )
            store.set_state("subscription_confirmed", True, at=available)
            monitor = DataHealthMonitor(
                store, symbol="BTC-USD", granularity=3600, policy=HealthPolicy(snapshot_interval_seconds=10.0),
            )

            def evaluate(offset: float, *, fresh: bool = False) -> str:
                now = start + timedelta(seconds=offset)
                if fresh:
                    for activity in ("heartbeat", "market", "reconcile"):
                        store.note_activity(activity, at=utc_stamp(now))
                return monitor.evaluate(now=now).state

            states = [
                evaluate(0, fresh=True), evaluate(1), evaluate(20), evaluate(22),
                evaluate(40, fresh=True), evaluate(52, fresh=True),
            ]
            self.assertEqual(states, ["GREEN", "GREEN", "RED", "RED", "GREEN", "GREEN"])
            history = [
                (row["state"], row["evaluated_at"])
                for row in store._db.execute("SELECT state, evaluated_at FROM health_snapshots ORDER BY snapshot_id")
            ]
            self.assertEqual(
                history,
                [(state, utc_stamp(start + timedelta(seconds=offset))) for state, offset in (
                    ("GREEN", 0), ("RED", 20), ("GREEN", 40), ("GREEN", 52),
                )],
            )
            monitor.evaluate(now=start + timedelta(seconds=53))
            self.assertEqual(
                store.get_state("latest_health")["evaluated_at"], utc_stamp(start + timedelta(seconds=53)),
            )
            self.assertEqual(store._db.execute("SELECT COUNT(*) FROM health_snapshots").fetchone()[0], 4)
            thinned = store.thin_health_snapshots(interval_seconds=30.0)
            self.assertEqual((thinned["kept"], thinned["removed"]), (3, 1))

    def test_recording_round_trip_preserves_exact_raw_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            with IngestionStore(directory / "market.sqlite3") as store:
                received = "2026-01-01T00:00:01.000000Z"
                store.capture_raw(
                    source_id="feed",
                    session_id="session",
                    channel="ws:ticker",
                    payload={"type": "ticker", "price": "100.5"},
                    sequence=7,
                    observed_at="2026-01-01T00:00:00.000000Z",
                    received_at=received,
                    received_monotonic_ns=123,
                )
                receipt = store.export_recording(directory / "recording.jsonl.gz")
            records = list(IngestionStore.iter_recording(directory / "recording.jsonl.gz"))
            self.assertEqual(receipt["records"], 1)
            self.assertEqual(records[0]["payload"], {"price": "100.5", "type": "ticker"})
            self.assertEqual(records[0]["received_monotonic_ns"], 123)

    def test_paper_consumer_warms_history_then_decides_only_on_new_bar(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            with IngestionStore(directory / "market.sqlite3") as store:
                for hour in range(12):
                    available = f"2026-01-01T{hour + 1:02d}:00:01.000000Z"
                    store.ingest_bar(
                        self._bar(hour),
                        source_id="coinbase-exchange",
                        source_revision="test-v1",
                        granularity=3600,
                        available_at=available,
                        raw_id=self._capture(store, hour, available).raw_id,
                        origin="rest",
                    )
                session = PaperSession(
                    StrategyProgram.seed(),
                    config=PaperConfig(venue="coinbase-canonical-paper", timeframe_seconds=3600),
                )
                consumer = CanonicalPaperConsumer(
                    store=store,
                    session=session,
                    symbol="BTC-USD",
                    consumer_id="paper:test",
                    state_path=directory / "paper-state.json",
                    latest_path=directory / "paper-latest.json",
                )
                prepared = consumer.prepare()
                self.assertEqual(prepared["warmed_bars"], 12)
                self.assertEqual(session.receipts, {})
                available = "2026-01-01T13:00:01.000000Z"
                new_result = store.ingest_bar(
                    self._bar(12),
                    source_id="coinbase-exchange",
                    source_revision="test-v1",
                    granularity=3600,
                    available_at=available,
                    raw_id=self._capture(store, 13, available).raw_id,
                    origin="rest",
                )
                health_body = {
                    "schema": "cassi.market-data-health.v1",
                    "state": "GREEN",
                    "evaluated_at": available,
                    "reasons": [],
                    "metrics": {},
                    "can_observe": True,
                    "can_open_exposure": True,
                }
                health = DataHealth(
                    state="GREEN",
                    evaluated_at=available,
                    reasons=(),
                    metrics={},
                    can_observe=True,
                    can_open_exposure=True,
                    content_sha256="0" * 64,
                )
                drained = consumer.drain(health)
                self.assertEqual(drained["processed"], 1)
                receipt = session.receipts[new_result.event.event_id]
                self.assertEqual(receipt["event"], new_result.event.as_dict())
                self.assertEqual(receipt["data_health"]["state"], health_body["state"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
