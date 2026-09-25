"""Coinbase Exchange public REST/WebSocket ingestion with bounded recovery.

The adapter is read-only.  It captures exact public source messages, admits
canonical events, reconciles closed candles over an overlapping REST window,
and never authenticates or submits an order.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import socket
import ssl
import struct
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from cassi_market_contracts import Event, digest_value
from cassi_market_ingestion import (
    DataHealth,
    DataHealthMonitor,
    IngestResult,
    IngestionError,
    IngestionStore,
    RawCapture,
    atomic_write_json,
    bucket_start,
    parse_utc,
    utc_stamp,
)
from cassi_trading_foundry import MarketBar


COINBASE_SOURCE_ID = "coinbase-exchange"
COINBASE_REST_URL = "https://api.exchange.coinbase.com"
COINBASE_WEBSOCKET_URL = "wss://ws-feed.exchange.coinbase.com"
COINBASE_ADAPTER_VERSION = "cassi.coinbase-public-ingestion.v1"
COINBASE_RUN_SCHEMA = "cassi.coinbase-ingestion-run.v1"
_ALLOWED_GRANULARITIES = frozenset({60, 300, 900, 3600, 21600, 86400})
_FEED_CHANNEL_PROFILES: dict[str, tuple[str, ...]] = {
    "all": ("heartbeat", "ticker", "matches"),
    "quotes": ("heartbeat", "ticker"),
    "bars": ("heartbeat",),
}


class CoinbaseError(IngestionError):
    """Coinbase public data or transport violated the ingestion contract."""


@dataclass(frozen=True, slots=True)
class CoinbaseConfig:
    product: str = "BTC-USD"
    granularity: int = 3600
    bootstrap_bars: int = 299
    overlap_bars: int = 6
    websocket_url: str = COINBASE_WEBSOCKET_URL
    rest_url: str = COINBASE_REST_URL
    socket_timeout_seconds: float = 5.0
    reconnect_initial_seconds: float = 1.0
    reconnect_max_seconds: float = 30.0
    revision_confirmations: int = 2
    reconcile_interval_seconds: int = 60
    # Coinbase serves a bucket's final candle as it closes, so the live loop
    # reconciles this long after each close and retries until the bar lands.
    close_settle_seconds: float = 2.0
    close_retry_seconds: float = 5.0
    public_feed_channels: str = "all"
    transient_retention_seconds: int = 86_400
    maintenance_interval_seconds: int = 3_600

    def __post_init__(self) -> None:
        if not isinstance(self.product, str) or not self.product.strip():
            raise CoinbaseError("Coinbase product must be nonempty text")
        if self.granularity not in _ALLOWED_GRANULARITIES:
            raise CoinbaseError("unsupported Coinbase candle granularity")
        if not 12 <= self.bootstrap_bars <= 299:
            raise CoinbaseError("bootstrap_bars must be between 12 and 299")
        if not 1 <= self.overlap_bars < self.bootstrap_bars:
            raise CoinbaseError("overlap_bars must be positive and below bootstrap_bars")
        if self.revision_confirmations < 2:
            raise CoinbaseError("source revisions require at least two confirmations")
        if self.public_feed_channels not in _FEED_CHANNEL_PROFILES:
            allowed = ", ".join(sorted(_FEED_CHANNEL_PROFILES))
            raise CoinbaseError(f"public_feed_channels must be one of: {allowed}")
        if (
            not isinstance(self.reconcile_interval_seconds, int)
            or isinstance(self.reconcile_interval_seconds, bool)
            or self.reconcile_interval_seconds <= 0
        ):
            raise CoinbaseError("reconcile_interval_seconds must be positive")
        for name, value in (
            ("transient_retention_seconds", self.transient_retention_seconds),
            ("maintenance_interval_seconds", self.maintenance_interval_seconds),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise CoinbaseError(f"{name} must be a nonnegative integer")
        if self.transient_retention_seconds and not self.maintenance_interval_seconds:
            raise CoinbaseError("transient retention requires a positive maintenance interval")
        for name, value in (
            ("socket_timeout_seconds", self.socket_timeout_seconds),
            ("reconnect_initial_seconds", self.reconnect_initial_seconds),
            ("reconnect_max_seconds", self.reconnect_max_seconds),
            ("close_settle_seconds", self.close_settle_seconds),
            ("close_retry_seconds", self.close_retry_seconds),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) <= 0.0:
                raise CoinbaseError(f"{name} must be positive")
        if self.reconnect_max_seconds < self.reconnect_initial_seconds:
            raise CoinbaseError("maximum reconnect delay cannot be below the initial delay")

    @property
    def websocket_channels(self) -> tuple[str, ...]:
        return _FEED_CHANNEL_PROFILES[self.public_feed_channels]

    @property
    def subscribes_matches(self) -> bool:
        return "matches" in self.websocket_channels


class CoinbaseREST(Protocol):
    def fetch_product(self, product: str) -> Mapping[str, Any]: ...

    def fetch_candles(
        self,
        product: str,
        granularity: int,
        start: datetime,
        end: datetime,
    ) -> Sequence[Any]: ...


class CoinbaseRESTClient:
    def __init__(self, base_url: str = COINBASE_REST_URL, *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, query: Mapping[str, Any] | None = None) -> Any:
        suffix = "" if not query else "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(
            self.base_url + path + suffix,
            headers={"User-Agent": "CassiTradingIngestion/1.0", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise CoinbaseError(f"Coinbase REST request failed for {path}: {exc}") from exc

    def fetch_product(self, product: str) -> Mapping[str, Any]:
        payload = self._get(f"/products/{urllib.parse.quote(product, safe='')}")
        if not isinstance(payload, Mapping):
            raise CoinbaseError("Coinbase product response must be an object")
        return dict(payload)

    def fetch_candles(
        self,
        product: str,
        granularity: int,
        start: datetime,
        end: datetime,
    ) -> Sequence[Any]:
        if end <= start:
            raise CoinbaseError("candle request end must follow start")
        if (end - start).total_seconds() > granularity * 300:
            raise CoinbaseError("candle request exceeds Coinbase's 300-bucket limit")
        payload = self._get(
            f"/products/{urllib.parse.quote(product, safe='')}/candles",
            {
                "granularity": granularity,
                "start": utc_stamp(start),
                "end": utc_stamp(end),
            },
        )
        if not isinstance(payload, list):
            raise CoinbaseError("Coinbase candle response must be a list")
        return payload


class WebSocketConnection:
    """Small RFC 6455 client sufficient for the uncompressed Coinbase feed."""

    def __init__(self, url: str, *, timeout: float = 5.0) -> None:
        self.url = url
        self.timeout = timeout
        self._socket: ssl.SSLSocket | None = None
        self._buffer = bytearray()
        self._fragment_opcode: int | None = None
        self._fragment_payload = bytearray()

    def connect(self) -> None:
        parsed = urllib.parse.urlparse(self.url)
        if parsed.scheme != "wss" or not parsed.hostname:
            raise CoinbaseError("WebSocket URL must use wss://")
        port = parsed.port or 443
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        raw = socket.create_connection((parsed.hostname, port), timeout=self.timeout)
        raw.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        context = ssl.create_default_context()
        wrapped = context.wrap_socket(raw, server_hostname=parsed.hostname)
        wrapped.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "User-Agent: CassiTradingIngestion/1.0\r\n"
            "\r\n"
        ).encode("ascii")
        wrapped.sendall(request)
        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = wrapped.recv(4096)
            if not chunk:
                wrapped.close()
                raise CoinbaseError("WebSocket server closed during handshake")
            response.extend(chunk)
            if len(response) > 65536:
                wrapped.close()
                raise CoinbaseError("WebSocket handshake headers are too large")
        header_bytes, remainder = bytes(response).split(b"\r\n\r\n", 1)
        lines = header_bytes.decode("iso-8859-1").split("\r\n")
        if not lines or " 101 " not in f" {lines[0]} ":
            wrapped.close()
            raise CoinbaseError(f"WebSocket upgrade rejected: {lines[0] if lines else 'empty response'}")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        expected_accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        if headers.get("sec-websocket-accept") != expected_accept:
            wrapped.close()
            raise CoinbaseError("WebSocket handshake accept digest mismatch")
        if headers.get("upgrade", "").lower() != "websocket":
            wrapped.close()
            raise CoinbaseError("WebSocket upgrade header missing")
        self._socket = wrapped
        self._buffer.extend(remainder)

    @staticmethod
    def encode_client_frame(payload: bytes, *, opcode: int = 0x1, mask_key: bytes | None = None) -> bytes:
        if len(payload) >= 2**63:
            raise CoinbaseError("WebSocket payload is too large")
        key = mask_key or os.urandom(4)
        if len(key) != 4:
            raise CoinbaseError("WebSocket mask key must contain four bytes")
        first = 0x80 | opcode
        size = len(payload)
        if size < 126:
            header = bytes((first, 0x80 | size))
        elif size <= 0xFFFF:
            header = bytes((first, 0x80 | 126)) + struct.pack("!H", size)
        else:
            header = bytes((first, 0x80 | 127)) + struct.pack("!Q", size)
        masked = bytes(value ^ key[index % 4] for index, value in enumerate(payload))
        return header + key + masked

    def _recv_exact(self, size: int) -> bytes:
        if self._socket is None:
            raise CoinbaseError("WebSocket is not connected")
        while len(self._buffer) < size:
            chunk = self._socket.recv(max(4096, size - len(self._buffer)))
            if not chunk:
                raise ConnectionError("WebSocket closed")
            self._buffer.extend(chunk)
        result = bytes(self._buffer[:size])
        del self._buffer[:size]
        return result

    def _receive_frame(self) -> tuple[bool, int, bytes]:
        first, second = self._recv_exact(2)
        fin = bool(first & 0x80)
        if first & 0x70:
            raise CoinbaseError("unsupported WebSocket extension bits")
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        size = second & 0x7F
        if size == 126:
            size = struct.unpack("!H", self._recv_exact(2))[0]
        elif size == 127:
            size = struct.unpack("!Q", self._recv_exact(8))[0]
        if size > 16 * 1024 * 1024:
            raise CoinbaseError("WebSocket frame exceeds the ingestion limit")
        mask = self._recv_exact(4) if masked else None
        payload = self._recv_exact(size)
        if mask is not None:
            payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        return fin, opcode, payload

    def send_json(self, value: Mapping[str, Any]) -> None:
        if self._socket is None:
            raise CoinbaseError("WebSocket is not connected")
        self._socket.sendall(self.encode_client_frame(json.dumps(dict(value), separators=(",", ":")).encode("utf-8")))

    def _send_control(self, opcode: int, payload: bytes = b"") -> None:
        if self._socket is not None:
            self._socket.sendall(self.encode_client_frame(payload, opcode=opcode))

    def receive_json(self) -> Mapping[str, Any]:
        while True:
            fin, opcode, payload = self._receive_frame()
            if opcode == 0x8:
                self._send_control(0x8, payload[:125])
                raise ConnectionError("WebSocket close frame received")
            if opcode == 0x9:
                self._send_control(0xA, payload[:125])
                continue
            if opcode == 0xA:
                continue
            if opcode in {0x1, 0x2}:
                if self._fragment_opcode is not None:
                    raise CoinbaseError("new WebSocket message arrived before fragmented message completed")
                if fin:
                    complete = payload
                else:
                    self._fragment_opcode = opcode
                    self._fragment_payload.extend(payload)
                    continue
            elif opcode == 0x0:
                if self._fragment_opcode is None:
                    raise CoinbaseError("unexpected WebSocket continuation frame")
                self._fragment_payload.extend(payload)
                if not fin:
                    continue
                complete = bytes(self._fragment_payload)
                opcode = self._fragment_opcode
                self._fragment_opcode = None
                self._fragment_payload.clear()
            else:
                raise CoinbaseError(f"unsupported WebSocket opcode: {opcode}")
            if opcode != 0x1:
                raise CoinbaseError("Coinbase sent a non-text data message")
            try:
                value = json.loads(complete.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CoinbaseError("Coinbase sent invalid WebSocket JSON") from exc
            if not isinstance(value, Mapping):
                raise CoinbaseError("Coinbase WebSocket message must be an object")
            return dict(value)

    def close(self) -> None:
        sock, self._socket = self._socket, None
        if sock is not None:
            try:
                sock.sendall(self.encode_client_frame(b"", opcode=0x8))
            except OSError:
                pass
            finally:
                sock.close()

    def __enter__(self) -> "WebSocketConnection":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class CoinbaseMessageProcessor:
    def __init__(self, store: IngestionStore, config: CoinbaseConfig) -> None:
        self.store = store
        self.config = config

    @staticmethod
    def _positive(payload: Mapping[str, Any], name: str) -> float:
        try:
            value = float(payload[name])
        except (KeyError, TypeError, ValueError) as exc:
            raise CoinbaseError(f"Coinbase message has invalid {name}") from exc
        if not math.isfinite(value) or value <= 0.0:
            raise CoinbaseError(f"Coinbase message {name} must be positive and finite")
        return value

    def _capture(
        self,
        payload: Mapping[str, Any],
        *,
        session_id: str,
        received_at: str | None,
        received_monotonic_ns: int | None,
    ) -> RawCapture:
        message_type = str(payload.get("type", "unknown"))
        sequence = payload.get("sequence") or payload.get("trade_id")
        observed_at = payload.get("time") or payload.get("timestamp")
        return self.store.capture_raw(
            source_id=COINBASE_SOURCE_ID,
            session_id=session_id,
            channel=f"ws:{message_type}",
            payload=dict(payload),
            sequence=sequence,
            observed_at=str(observed_at) if observed_at else None,
            received_at=received_at,
            received_monotonic_ns=received_monotonic_ns,
        )

    def process(
        self,
        payload: Mapping[str, Any],
        *,
        session_id: str,
        received_at: str | None = None,
        received_monotonic_ns: int | None = None,
        capture: RawCapture | None = None,
    ) -> IngestResult | None:
        raw = capture or self._capture(
            payload,
            session_id=session_id,
            received_at=received_at,
            received_monotonic_ns=received_monotonic_ns,
        )
        message_type = str(payload.get("type", ""))
        available_at = raw.received_at
        if message_type == "subscriptions":
            channels = payload.get("channels")
            if not isinstance(channels, list):
                raise CoinbaseError("Coinbase subscription response has no channel list")
            names = {str(row.get("name")) for row in channels if isinstance(row, Mapping)}
            required = set(self.config.websocket_channels)
            self.store.set_state("subscription_confirmed", required.issubset(names), at=available_at)
            self.store.note_activity("subscription", at=available_at, value={"channels": sorted(names)})
            return None
        if message_type == "error":
            self.store.increment_metric("feed_errors")
            self.store.set_state("last_feed_error", dict(payload), at=available_at)
            raise CoinbaseError(f"Coinbase feed error: {payload.get('message', 'unknown error')}")
        if message_type not in {"heartbeat", "ticker", "match", "last_match", "status"}:
            self.store.increment_metric("unsupported_messages")
            return None

        observed_at = str(payload.get("time") or payload.get("timestamp") or available_at)
        parse_utc(observed_at)
        product = str(payload.get("product_id") or self.config.product)
        sequence = payload.get("sequence")
        if message_type == "heartbeat":
            if product != self.config.product:
                return None
            self.store.note_activity("heartbeat", at=available_at, value={"sequence": sequence})
            self.store.note_activity("market", at=available_at, value={"kind": "heartbeat"})
            last_trade_id = payload.get("last_trade_id")
            if last_trade_id is not None and self.config.subscribes_matches:
                self._observe_trade_cursor(int(last_trade_id), from_heartbeat=True, at=available_at)
            natural_key = f"heartbeat|{COINBASE_SOURCE_ID}|{product}|{sequence}"
            event_type = "market-heartbeat"
            units: dict[str, str] = {}
        elif message_type == "ticker":
            if product != self.config.product:
                return None
            price = self._positive(payload, "price")
            bid = self._positive(payload, "best_bid")
            ask = self._positive(payload, "best_ask")
            if bid > ask:
                raise CoinbaseError("Coinbase ticker has a crossed best bid/ask")
            self.store.note_activity("quote", at=available_at, value={"bid": bid, "ask": ask})
            self.store.note_activity("market", at=available_at, value={"kind": "ticker", "price": price})
            identity = sequence if sequence is not None else payload.get("trade_id") or observed_at
            natural_key = f"quote|{COINBASE_SOURCE_ID}|{product}|{identity}"
            event_type = "market-quote"
            units = {"price": "price", "best_bid": "price", "best_ask": "price"}
        elif message_type in {"match", "last_match"}:
            if product != self.config.product:
                return None
            self._positive(payload, "price")
            self._positive(payload, "size")
            try:
                trade_id = int(payload["trade_id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CoinbaseError("Coinbase match has invalid trade_id") from exc
            self._observe_trade_cursor(trade_id, from_heartbeat=False, at=available_at)
            self.store.note_activity("trade", at=available_at, value={"trade_id": trade_id})
            self.store.note_activity("market", at=available_at, value={"kind": "trade", "trade_id": trade_id})
            natural_key = f"trade|{COINBASE_SOURCE_ID}|{product}|{trade_id}"
            event_type = "market-trade"
            units = {"price": "price", "size": "asset-units"}
        else:
            natural_key = f"status|{COINBASE_SOURCE_ID}|{digest_value(dict(payload))}"
            event_type = "market-status"
            units = {}

        semantic = dict(payload)
        event_id = f"{COINBASE_SOURCE_ID}:{event_type}:{digest_value({'key': natural_key, 'payload': semantic})[:40]}"
        event = Event(
            event_id=event_id,
            source_id=COINBASE_SOURCE_ID,
            source_revision=COINBASE_ADAPTER_VERSION,
            observed_at=observed_at,
            available_at=available_at,
            event_type=event_type,
            subject_ids=(product,),
            payload=semantic,
            units=units,
            coordinate_frame="coinbase-exchange",
            source_span={
                "raw_id": raw.raw_id,
                "session_id": raw.session_id,
                "received_monotonic_ns": raw.received_monotonic_ns,
            },
        )
        self.store.increment_metric("ws_messages")
        return self.store.ingest_event(
            event,
            natural_key=natural_key,
            raw_id=raw.raw_id,
            semantic_value=semantic,
        )

    def _observe_trade_cursor(self, trade_id: int, *, from_heartbeat: bool, at: str) -> None:
        key = f"coinbase:last_trade_id:{self.config.product}"
        previous = self.store.get_state(key)
        if previous is None:
            self.store.set_state(key, trade_id, at=at)
            return
        previous_id = int(previous)
        if not from_heartbeat:
            if trade_id > previous_id + 1:
                self.store.increment_metric("trade_id_gaps", trade_id - previous_id - 1)
                self.store.set_state("recovery_required", True, at=at)
                self.store.set_state(
                    "last_trade_gap",
                    {"after": previous_id, "before": trade_id, "detected_at": at},
                    at=at,
                )
            elif trade_id <= previous_id:
                self.store.increment_metric("out_of_order_trades")
        elif trade_id > previous_id + 1:
            self.store.increment_metric("heartbeat_trade_gaps", trade_id - previous_id - 1)
            self.store.set_state("recovery_required", True, at=at)
        if trade_id > previous_id:
            self.store.set_state(key, trade_id, at=at)


class CoinbaseIngestionService:
    def __init__(
        self,
        store: IngestionStore,
        config: CoinbaseConfig | None = None,
        *,
        rest_client: CoinbaseREST | None = None,
        session_id: str | None = None,
    ) -> None:
        self.store = store
        self.config = config or CoinbaseConfig()
        self.rest = rest_client or CoinbaseRESTClient(self.config.rest_url)
        self.session_id = session_id or f"coinbase-{uuid.uuid4()}"
        self.processor = CoinbaseMessageProcessor(store, self.config)
        self._next_reconcile: datetime | None = None
        self._next_maintenance: datetime | None = None

    @staticmethod
    def _candle(row: Any, product: str) -> MarketBar:
        if not isinstance(row, list) or len(row) < 6:
            raise CoinbaseError("Coinbase returned an invalid candle row")
        try:
            timestamp = int(row[0])
            low, high, opening, closing, volume = (float(value) for value in row[1:6])
        except (TypeError, ValueError) as exc:
            raise CoinbaseError("Coinbase candle row contains invalid numbers") from exc
        return MarketBar(
            timestamp=utc_stamp(datetime.fromtimestamp(timestamp, tz=timezone.utc)),
            symbol=product,
            open=opening,
            high=high,
            low=low,
            close=closing,
            volume=volume,
        )

    def _admit_product_payload(
        self,
        envelope: Mapping[str, Any],
        *,
        raw: RawCapture,
    ) -> Mapping[str, Any]:
        request = envelope.get("request")
        response = envelope.get("response")
        if not isinstance(request, Mapping) or not isinstance(response, Mapping):
            raise CoinbaseError("recorded product payload is malformed")
        product = str(request.get("product"))
        payload = dict(response)
        if product != self.config.product or str(payload.get("id")) != product:
            raise CoinbaseError("Coinbase product metadata identity mismatch")
        status = str(payload.get("status", ""))
        if status != "online":
            self.store.set_state("product_online", False, at=raw.received_at)
            raise CoinbaseError(f"Coinbase product is not online: {status or 'unknown'}")
        self.store.set_state("product_online", True, at=raw.received_at)
        self.store.set_state("product_metadata", payload, at=raw.received_at)
        natural_key = f"product-metadata|{COINBASE_SOURCE_ID}|{product}|{digest_value(payload)}"
        event = Event(
            event_id=f"{COINBASE_SOURCE_ID}:product:{digest_value(natural_key)[:40]}",
            source_id=COINBASE_SOURCE_ID,
            source_revision=COINBASE_ADAPTER_VERSION,
            observed_at=raw.received_at,
            available_at=raw.received_at,
            event_type="market-product",
            subject_ids=(product,),
            payload=payload,
            coordinate_frame="coinbase-exchange",
            source_span={"raw_id": raw.raw_id},
        )
        self.store.ingest_event(event, natural_key=natural_key, raw_id=raw.raw_id, semantic_value=payload)
        return payload

    def capture_product_metadata(self) -> Mapping[str, Any]:
        payload = dict(self.rest.fetch_product(self.config.product))
        received = utc_stamp()
        envelope = {"request": {"product": self.config.product}, "response": payload}
        raw = self.store.capture_raw(
            source_id=COINBASE_SOURCE_ID,
            session_id=self.session_id,
            channel="rest:product",
            payload=envelope,
            observed_at=received,
            received_at=received,
        )
        return self._admit_product_payload(envelope, raw=raw)

    def _reconcile_bounds(self, now: datetime) -> tuple[datetime, datetime]:
        end = bucket_start(now, self.config.granularity)
        latest = self.store.latest_accepted_bar(self.config.product)
        if latest is None:
            start = end - timedelta(seconds=self.config.bootstrap_bars * self.config.granularity)
        else:
            latest_start = parse_utc(latest[1].timestamp)
            start = latest_start - timedelta(seconds=(self.config.overlap_bars - 1) * self.config.granularity)
            minimum = end - timedelta(seconds=self.config.bootstrap_bars * self.config.granularity)
            start = max(start, minimum)
        return start, end

    def _admit_candle_payload(
        self,
        envelope: Mapping[str, Any],
        *,
        raw: RawCapture,
        allow_promotions: bool,
        include_root: bool = True,
    ) -> dict[str, Any]:
        request = envelope.get("request")
        response = envelope.get("response")
        if not isinstance(request, Mapping) or not isinstance(response, list):
            raise CoinbaseError("recorded candle envelope is malformed")
        product = str(request.get("product"))
        try:
            granularity = int(request["granularity"])
            start = parse_utc(str(request["start"]))
            end = parse_utc(str(request["end"]))
        except (KeyError, TypeError, ValueError, IngestionError) as exc:
            raise CoinbaseError("recorded candle request metadata is invalid") from exc
        if product != self.config.product or granularity != self.config.granularity:
            raise CoinbaseError("candle envelope does not match ingestion configuration")
        accepted = duplicates = conflicts = promoted = 0
        for raw_row in response:
            bar = self._candle(raw_row, product)
            observed = parse_utc(bar.timestamp)
            if observed < start or observed >= end:
                continue
            result = self.store.ingest_bar(
                bar,
                source_id=COINBASE_SOURCE_ID,
                source_revision=COINBASE_ADAPTER_VERSION,
                granularity=granularity,
                available_at=raw.received_at,
                raw_id=raw.raw_id,
                origin="coinbase-rest-candles",
                promote_after_confirmations=self.config.revision_confirmations if allow_promotions else None,
            )
            if result.status == "accepted":
                accepted += 1
            elif result.status == "duplicate":
                duplicates += 1
            elif result.status == "conflict":
                conflicts += 1
            elif result.status == "promoted":
                promoted += 1
        gaps = self.store.bar_gaps(
            source_id=COINBASE_SOURCE_ID,
            symbol=product,
            granularity=granularity,
            start=start,
            end=end,
        )
        self.store.set_state(f"bar_gap_count:{product}:{granularity}", len(gaps), at=raw.received_at)
        self.store.set_state(f"bar_gaps:{product}:{granularity}", list(gaps), at=raw.received_at)
        self.store.set_state("recovery_required", bool(gaps or self.store.unresolved_conflicts()), at=raw.received_at)
        self.store.note_activity(
            "reconcile",
            at=raw.received_at,
            value={"start": utc_stamp(start), "end": utc_stamp(end), "gaps": len(gaps)},
        )
        body: dict[str, Any] = {
            "schema": "cassi.coinbase-rest-reconciliation.v1",
            "product": product,
            "granularity": granularity,
            "start": utc_stamp(start),
            "end": utc_stamp(end),
            "received_at": raw.received_at,
            "rows": len(response),
            "accepted": accepted,
            "duplicates": duplicates,
            "conflicts": conflicts,
            "promoted": promoted,
            "gaps": list(gaps),
            "event_root_sha256": (
                self.store.event_root(event_type="market-bar", subject_id=product) if include_root else None
            ),
        }
        body["content_sha256"] = digest_value(body)
        return body

    def reconcile(self, *, now: datetime | None = None, include_root: bool = True) -> dict[str, Any]:
        """Fetch and admit closed candles; the live loop skips the full-history root it would discard."""
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        start, end = self._reconcile_bounds(current)
        rows = list(self.rest.fetch_candles(self.config.product, self.config.granularity, start, end))
        received = utc_stamp()
        envelope = {
            "request": {
                "product": self.config.product,
                "granularity": self.config.granularity,
                "start": utc_stamp(start),
                "end": utc_stamp(end),
            },
            "response": rows,
        }
        raw = self.store.capture_raw(
            source_id=COINBASE_SOURCE_ID,
            session_id=self.session_id,
            channel="rest:candles",
            payload=envelope,
            observed_at=utc_stamp(end),
            received_at=received,
        )
        self.store.increment_metric("rest_reconciliations")
        receipt = self._admit_candle_payload(envelope, raw=raw, allow_promotions=True, include_root=include_root)
        self._next_reconcile = self._next_reconcile_after(current)
        return receipt

    def _next_reconcile_after(self, current: datetime) -> datetime:
        """Keep the regular cadence, and pull each bar right after it closes."""
        granularity = timedelta(seconds=self.config.granularity)
        interval = timedelta(seconds=self.config.reconcile_interval_seconds)
        opened = bucket_start(current, self.config.granularity)
        regular = current + interval
        latest = self.store.latest_accepted_bar(self.config.product)
        closed_missing = latest is None or parse_utc(latest[1].timestamp) < opened - granularity
        if closed_missing and current - opened < interval:
            return min(regular, current + timedelta(seconds=self.config.close_retry_seconds))
        return min(regular, opened + granularity + timedelta(seconds=self.config.close_settle_seconds))

    def bootstrap(self, *, now: datetime | None = None) -> dict[str, Any]:
        product = self.capture_product_metadata()
        reconciliation = self.reconcile(now=now)
        return {
            "schema": "cassi.coinbase-bootstrap.v1",
            "product": dict(product),
            "reconciliation": reconciliation,
            "session_id": self.session_id,
        }

    def _subscribe(self, websocket: WebSocketConnection) -> None:
        channels = list(self.config.websocket_channels)
        request = {
            "type": "subscribe",
            "product_ids": [self.config.product],
            "channels": channels,
        }
        sent_at = utc_stamp()
        self.store.capture_raw(
            source_id="cassi-ingestion",
            session_id=self.session_id,
            channel="ws:subscribe:outbound",
            payload=request,
            observed_at=sent_at,
            received_at=sent_at,
        )
        websocket.send_json(request)

    def maintain(self, *, now: datetime | None = None) -> dict[str, Any] | None:
        """Drop liveness rows older than the retention window; closed bars are permanent."""
        if not self.config.transient_retention_seconds:
            return None
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if self._next_maintenance is not None and current < self._next_maintenance:
            return None
        self._next_maintenance = current + timedelta(seconds=self.config.maintenance_interval_seconds)
        result = self.store.prune_transient(
            before=utc_stamp(current - timedelta(seconds=self.config.transient_retention_seconds)),
        )
        self.store.note_activity("maintenance", at=utc_stamp(current), value=result)
        return result

    def publish_health(self, monitor: DataHealthMonitor, path: Path | None = None) -> DataHealth:
        health = monitor.evaluate()
        if path is not None:
            atomic_write_json(path, health.as_dict())
        return health

    def run(
        self,
        monitor: DataHealthMonitor,
        *,
        health_path: Path | None = None,
        max_messages: int = 0,
        max_seconds: float = 0.0,
        on_health: Callable[[DataHealth], None] | None = None,
    ) -> dict[str, Any]:
        if max_messages < 0 or max_seconds < 0.0:
            raise CoinbaseError("run bounds cannot be negative")
        started = time.monotonic()
        messages = 0
        connections = 0
        delay = self.config.reconnect_initial_seconds
        last_health: DataHealth | None = None
        while not max_seconds or time.monotonic() - started < max_seconds:
            self.store.set_state("subscription_confirmed", False)
            try:
                with WebSocketConnection(
                    self.config.websocket_url,
                    timeout=self.config.socket_timeout_seconds,
                ) as websocket:
                    connections += 1
                    self.store.increment_metric("websocket_connections")
                    self._subscribe(websocket)
                    delay = self.config.reconnect_initial_seconds
                    while True:
                        if max_seconds and time.monotonic() - started >= max_seconds:
                            break
                        try:
                            payload = websocket.receive_json()
                        except socket.timeout:
                            last_health = self.publish_health(monitor, health_path)
                            if on_health is not None:
                                on_health(last_health)
                            if last_health.state == "RED":
                                raise ConnectionError("feed health became red while waiting for a message")
                            continue
                        try:
                            self.processor.process(payload, session_id=self.session_id)
                        except CoinbaseError:
                            self.store.increment_metric("schema_rejections")
                            raise
                        messages += 1
                        now = datetime.now(timezone.utc)
                        if self.store.get_state("recovery_required", False) or (
                            self._next_reconcile is not None and now >= self._next_reconcile
                        ):
                            self.reconcile(now=now, include_root=False)
                        self.maintain(now=now)
                        last_health = self.publish_health(monitor, health_path)
                        if on_health is not None:
                            on_health(last_health)
                        if max_messages and messages >= max_messages:
                            break
                    if (max_messages and messages >= max_messages) or (
                        max_seconds and time.monotonic() - started >= max_seconds
                    ):
                        break
            except (CoinbaseError, ConnectionError, OSError, ssl.SSLError) as exc:
                self.store.increment_metric("websocket_reconnects")
                self.store.set_state("last_connection_error", str(exc))
                if (max_messages and messages >= max_messages) or (
                    max_seconds and time.monotonic() - started >= max_seconds
                ):
                    break
                time.sleep(delay)
                delay = min(self.config.reconnect_max_seconds, delay * 2.0)
        last_health = last_health or self.publish_health(monitor, health_path)
        body: dict[str, Any] = {
            "schema": COINBASE_RUN_SCHEMA,
            "status": "PASS" if messages > 0 else "NO_MESSAGES",
            "session_id": self.session_id,
            "product": self.config.product,
            "granularity": self.config.granularity,
            "messages": messages,
            "connections": connections,
            "health": last_health.as_dict(),
            "bar_event_root_sha256": self.store.event_root(event_type="market-bar", subject_id=self.config.product),
            "market_event_root_sha256": self.store.event_root(subject_id=self.config.product),
            "external_effect": "public-market-data-read-only",
            "order_submissions": 0,
        }
        body["content_sha256"] = digest_value(body)
        return body

    def replay_recording(self, path: Path) -> dict[str, Any]:
        count = 0
        for record in IngestionStore.iter_recording(path):
            channel = str(record["channel"])
            payload = record["payload"]
            raw = self.store.capture_raw(
                source_id=str(record["source_id"]),
                session_id=str(record["session_id"]),
                channel=channel,
                payload=payload,
                sequence=record.get("sequence"),
                observed_at=record.get("observed_at"),
                received_at=str(record["received_at"]),
                received_monotonic_ns=int(record["received_monotonic_ns"]),
            )
            if channel.startswith("ws:") and channel != "ws:subscribe:outbound":
                if not isinstance(payload, Mapping):
                    raise CoinbaseError("recorded WebSocket payload is not an object")
                self.processor.process(
                    payload,
                    session_id=str(record["session_id"]),
                    capture=raw,
                )
            elif channel == "rest:candles":
                if not isinstance(payload, Mapping):
                    raise CoinbaseError("recorded candle payload is not an object")
                self._admit_candle_payload(payload, raw=raw, allow_promotions=True)
            elif channel == "rest:product":
                if not isinstance(payload, Mapping):
                    raise CoinbaseError("recorded product payload is not an object")
                self._admit_product_payload(payload, raw=raw)
            count += 1
        body: dict[str, Any] = {
            "schema": "cassi.coinbase-recording-replay.v1",
            "status": "PASS",
            "records": count,
            "bar_event_root_sha256": self.store.event_root(event_type="market-bar", subject_id=self.config.product),
            "market_event_root_sha256": self.store.event_root(subject_id=self.config.product),
        }
        body["content_sha256"] = digest_value(body)
        return body


__all__ = [
    "COINBASE_ADAPTER_VERSION",
    "COINBASE_RUN_SCHEMA",
    "COINBASE_SOURCE_ID",
    "CoinbaseConfig",
    "CoinbaseError",
    "CoinbaseIngestionService",
    "CoinbaseMessageProcessor",
    "CoinbaseRESTClient",
    "WebSocketConnection",
]
