#!/usr/bin/env python3
"""Canonical Cassi field-owned trading runtime connected to Cassi Hive.

The append-only ledger contains observations and provenance.  The only learned
state is one owner-operated ``cognition.field`` regional computer.  Market
models are retained as semantic mechanisms in that field; no model, score,
policy, or adaptive cache is persisted beside it.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
import tempfile
from collections import deque
from itertools import islice
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, cast


_CASSIFI_ROOT = Path(__file__).resolve().parents[1] / "CassiFI"
if str(_CASSIFI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIFI_ROOT))

from cassi_field_atlas import FieldIntelligenceError, canonical_json_bytes  # type: ignore  # noqa: E402
from cassi_field_cognition import (  # type: ignore  # noqa: E402
    SEMANTIC_STATE_SCHEMA,
    semantic_cognition_state,
)
from cassi_field_hive import (  # type: ignore  # noqa: E402
    ExperienceCandidate,
    ExperienceEvidence,
)
from cassi_field_open_vocab import episode_source_payload  # type: ignore  # noqa: E402
from cassi_field_owner import CapacityLimits, SourceInput  # type: ignore  # noqa: E402
from cassi_field_program import (  # type: ignore  # noqa: E402
    canonical_semantic_program_payload,
    execute_canonical_semantic_program,
    execute_semantic_program,
    semantic_program_payload,
)
from cassi_field_regions import (  # type: ignore  # noqa: E402
    RegionalProfile,
    resolve_semantic_record,
)
from cassi_hive_runtime import HiveField  # type: ignore  # noqa: E402
from cassi_hive_session import open_field_session  # type: ignore  # noqa: E402
from cassi_hive_policy import SkillPolicy  # type: ignore  # noqa: E402
from cassi_hive_store import decode_bundle  # type: ignore  # noqa: E402
from cassi_regional_catalog import STANDARD_KERNEL_CATALOG  # type: ignore  # noqa: E402

from cassi_paper import PaperAccount, PaperConfig, PaperExecutionEngine  # type: ignore  # noqa: E402


PAPER_CONSUMER_SCHEMA = "cassi.trading-field-paper-consumer.v1"
PAPER_CONSUMER_CONFIG_SCHEMA = "cassi.trading-field-paper-config.v1"
PAPER_CONSUMER_ACTIVATION_SCHEMA = "cassi.trading-field-paper-activation.v1"
PAPER_CONSUMER_EVENT_SCHEMA = "cassi.trading-field-paper-event.v1"
PAPER_CONSUMER_CAUSAL_EVENT_SCHEMA = "cassi.trading-field-paper-event.v2"
PAPER_CONSUMER_STATE_SCHEMA = "cassi.trading-field-paper-state.v2"
PAPER_CONSUMER_LEGACY_STATE_SCHEMA = "cassi.trading-field-paper-state.v1"
PAPER_CONSUMER_CAUSAL_CUTOVER_SCHEMA = "cassi.trading-field-paper-causal-cutover.v1"
PAPER_CONSUMER_CANCELLATION_SCHEMA = "cassi.trading-field-paper-pending-cancellation.v1"
PAPER_EXECUTION_MODEL = "next-bar-close-causal"
PAPER_INTERNAL_MODEL_NOTE = (
    "field decision/outcome evidence retains modeled fixed exposure on observed "
    "price paths; it is not paper-account execution or executable paper P&L"
)
_EMPTY_PAPER_CAUSAL_STATE = {
    "pending_order": None,
    "last_execution": None,
    "last_expiry": None,
}
_EMPTY_PAPER_RECEIPT_SHA256 = "0" * 64
def _paper_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _paper_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("paper timestamp must be nonempty text")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("paper timestamp is not ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("paper timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


TRADING_FIELD_SCHEMA = "cassi.trading-field.v1"
TRADING_LEDGER_SCHEMA = "cassi.trading-evidence-ledger.v1"
TRADING_SKILL_SCHEMA = "cassi.trading-semantic-skill.v1"
COMPUTER_ID = "main"
HOSTED_COMPUTER_ID = "cassi-trading"
COGNITION_KERNEL = "cognition.field"
SEMANTIC_SCOPE = "cassi-trading"
SEMANTIC_FRAME = "cassi-trading-field-v1"
# Resident evidence (bars, decisions, outcomes, archives) shares the declared
# workspace with the field geometry reservation.
_GEOMETRY_HEADROOM_BYTES = 64 * 1024 * 1024
MODEL_OUTPUTS = ("objective", "net_return", "max_drawdown", "downside", "cost")
# Discovery speaks slightly beyond the range it observed, and only splits that
# leave this many supporting decisions on each side are kept: a later
# evaluation slice sits outside the panel's observed range often enough that an
# exact-envelope mechanism stays silent exactly when it is being judged.
DISCOVERY_COVERAGE_MARGIN = 0.25
DISCOVERY_MIN_LEAF = 4
REGIME_FEATURE_NAMES = (
    "regime_trend_up",
    "regime_trend_down",
    "regime_range",
    "regime_transition",
    "regime_reversal",
    "regime_volatility_expansion",
    "regime_volatility_compression",
    "regime_liquidity_shock",
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _finite(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    return result




def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


@dataclass(frozen=True, slots=True)
class MarketBar:
    """One closed market candle available to the field at its timestamp."""

    timestamp: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, str) or not self.timestamp:
            raise ValueError("bar timestamp must be nonempty text")
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError("bar symbol must be nonempty text")
        for name in ("open", "high", "low", "close", "volume"):
            _finite(getattr(self, name), f"bar {name}", minimum=0.0)
        if min(self.open, self.close) > self.high:
            raise ValueError("bar high is below open or close")
        if max(self.open, self.close) < self.low:
            raise ValueError("bar low is above open or close")
        if self.low <= 0.0:
            raise ValueError("bar prices must be positive")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MarketBar":
        return cls(
            timestamp=str(value["timestamp"]),
            symbol=str(value["symbol"]),
            open=float(value["open"]),
            high=float(value["high"]),
            low=float(value["low"]),
            close=float(value["close"]),
            volume=float(value["volume"]),
        )


def _declared_workspace_bytes(mode_count: int) -> int:
    """Workspace ceiling that covers one field geometry and its resident evidence.

    The owner reserves nine eight-byte words per declared field mode, so a wider
    semantic region needs a workspace ceiling that covers the geometry it is
    carved from, plus the resident evidence sharing it.
    """

    return max(
        64 * 1024 * 1024,
        mode_count * 9 * 8 + _GEOMETRY_HEADROOM_BYTES,
    )


@dataclass(frozen=True, slots=True)
class TradingFieldConfig:
    """Fixed observation, risk, learning, and field geometry contract."""

    symbol: str = "BTC-USD"
    bar_hours: float = 1.0
    feature_windows: tuple[int, ...] = (1, 6, 24, 168)
    outcome_horizons: tuple[int, ...] = (1, 6, 24, 168)
    action_levels: tuple[float, ...] = (-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0)
    warmup_bars: int = 168
    decision_interval: int = 4
    fee_bps: float = 10.0
    spread_bps: float = 5.0
    slippage_bps: float = 5.0
    short_funding_bps_daily: float = 1.0
    initial_equity: float = 1.0
    max_position: float = 1.0
    allow_short: bool = True
    soft_drawdown: float = 0.20
    hard_drawdown: float = 0.35
    hard_stop_cooldown_bars: int = 720
    hard_stop_reentry_bars: int = 720
    hard_stop_reentry_cap: float = 0.25
    risk_penalty: float = 1.5
    downside_penalty: float = 0.5
    minimum_action_edge: float = 0.0005
    model_window: int = 256
    semantic_evaluation_decisions: int = 24
    semantic_panel_decisions: int = 8
    semantic_panel_actions: tuple[float, ...] = ()
    episode_batch_decisions: int = 16
    update_thresholds: tuple[int, ...] = (256, 768, 1_536)
    update_interval: int = 1_024
    field_mode_count: int = 786_432

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError("symbol must be nonempty text")
        _finite(self.bar_hours, "bar_hours", minimum=1.0e-9)
        integer_values = {
            "warmup_bars": self.warmup_bars,
            "decision_interval": self.decision_interval,
            "hard_stop_cooldown_bars": self.hard_stop_cooldown_bars,
            "hard_stop_reentry_bars": self.hard_stop_reentry_bars,
            "model_window": self.model_window,
            "semantic_evaluation_decisions": self.semantic_evaluation_decisions,
            "semantic_panel_decisions": self.semantic_panel_decisions,
            "episode_batch_decisions": self.episode_batch_decisions,
            "update_interval": self.update_interval,
            "field_mode_count": self.field_mode_count,
        }
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in integer_values.values()):
            raise ValueError("trading field integer bounds must be positive")
        for label, values in (
            ("feature_windows", self.feature_windows),
            ("outcome_horizons", self.outcome_horizons),
            ("update_thresholds", self.update_thresholds),
        ):
            if not values or any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in values):
                raise ValueError(f"{label} must contain positive integers")
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{label} must be sorted and unique")
        if self.warmup_bars < max(self.feature_windows):
            raise ValueError("warmup_bars must cover every feature window")
        actions = tuple(float(value) for value in self.action_levels)
        if tuple(sorted(set(actions))) != actions or 0.0 not in actions:
            raise ValueError("action_levels must be sorted, unique, and include zero")
        if any(abs(value) > self.max_position for value in actions):
            raise ValueError("action_levels exceed max_position")
        if not self.allow_short and any(value < 0.0 for value in actions):
            raise ValueError("short action levels require allow_short")
        for name in (
            "fee_bps",
            "spread_bps",
            "slippage_bps",
            "short_funding_bps_daily",
            "risk_penalty",
            "downside_penalty",
            "minimum_action_edge",
        ):
            _finite(getattr(self, name), name, minimum=0.0)
        _finite(self.initial_equity, "initial_equity", minimum=1.0e-12)
        _finite(self.max_position, "max_position", minimum=1.0e-12)
        _finite(self.hard_stop_reentry_cap, "hard_stop_reentry_cap", minimum=1.0e-12)
        if self.hard_stop_reentry_cap > self.max_position:
            raise ValueError("hard_stop_reentry_cap must not exceed max_position")
        if not 0.0 < self.soft_drawdown < self.hard_drawdown < 1.0:
            raise ValueError("drawdown bounds must satisfy 0 < soft < hard < 1")
        if self.semantic_evaluation_decisions > self.model_window:
            raise ValueError("semantic evaluation cannot exceed the model window")
        if self.semantic_panel_decisions > self.model_window:
            raise ValueError("semantic panel cannot exceed the model window")
        if self.semantic_panel_decisions < 4:
            raise ValueError("semantic panel needs at least four decisions")
        panel_actions = tuple(float(value) for value in self.semantic_panel_actions)
        if panel_actions:
            if tuple(sorted(set(panel_actions))) != panel_actions:
                raise ValueError("semantic panel actions must be sorted and unique")
            if len(panel_actions) < 2:
                raise ValueError("semantic panel actions need at least two levels")
            if set(panel_actions) - set(actions):
                raise ValueError("semantic panel actions must be action levels")

    @classmethod
    def from_mapping(cls, value: Any) -> "TradingFieldConfig":
        if not isinstance(value, Mapping):
            raise TypeError("trading field configuration must be an object")
        names = {field.name for field in fields(cls)}
        if set(value) - names - {"compatibility_sha256"}:
            raise ValueError("trading field configuration contains unknown fields")
        if names - set(value):
            raise ValueError("trading field configuration is incomplete")
        payload = {name: value[name] for name in names}
        for name in (
            "feature_windows",
            "outcome_horizons",
            "action_levels",
            "semantic_panel_actions",
            "update_thresholds",
        ):
            raw = payload[name]
            if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
                raise ValueError(f"{name} must be a sequence")
            payload[name] = tuple(raw)
        config = cls(**payload)
        declared = value.get("compatibility_sha256")
        if declared is not None and declared != config.compatibility_sha256:
            raise ValueError("trading field configuration compatibility digest is invalid")
        return config


    @property
    def transaction_cost(self) -> float:
        return (self.fee_bps + self.spread_bps + self.slippage_bps) / 10_000.0

    @property
    def compatibility_sha256(self) -> str:
        return _digest(
            {
                "schema": TRADING_FIELD_SCHEMA,
                "symbol": self.symbol,
                "bar_hours": self.bar_hours,
                "feature_windows": list(self.feature_windows),
                "outcome_horizons": list(self.outcome_horizons),
                "action_levels": list(self.action_levels),
                "allow_short": self.allow_short,
                "max_position": self.max_position,
                "outputs": list(MODEL_OUTPUTS),
            }
        )

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for name in (
            "feature_windows",
            "outcome_horizons",
            "action_levels",
            "semantic_panel_actions",
            "update_thresholds",
        ):
            value[name] = list(value[name])
        value["compatibility_sha256"] = self.compatibility_sha256
        return value


class TradingEvidenceLedger:
    """Append-only hash-chained observations; never an adaptive store."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rows: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        previous = "0" * 64
        with self.path.open("rb") as handle:
            for line_number, raw in enumerate(handle, 1):
                if not raw.endswith(b"\n"):
                    raise ValueError(f"trading ledger line {line_number} is incomplete")
                try:
                    row = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError(f"trading ledger line {line_number} is invalid") from exc
                if not isinstance(row, Mapping):
                    raise ValueError(f"trading ledger line {line_number} is not an object")
                body = dict(row)
                stated = body.pop("content_sha256", None)
                if stated != _digest(body):
                    raise ValueError(f"trading ledger line {line_number} digest mismatch")
                if body.get("schema") != TRADING_LEDGER_SCHEMA:
                    raise ValueError(f"trading ledger line {line_number} schema mismatch")
                if body.get("sequence") != line_number or body.get("previous_sha256") != previous:
                    raise ValueError(f"trading ledger line {line_number} chain mismatch")
                event_id = body.get("event_id")
                if not isinstance(event_id, str) or len(event_id) != 64:
                    raise ValueError(f"trading ledger line {line_number} event identity is invalid")
                if event_id in self._by_id:
                    raise ValueError(f"trading ledger repeats event {event_id}")
                normalized = dict(row)
                self._rows.append(normalized)
                self._by_id[event_id] = normalized
                previous = cast(str, stated)

    @property
    def head_sha256(self) -> str:
        return "0" * 64 if not self._rows else str(self._rows[-1]["content_sha256"])

    def append(self, kind: str, payload: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        normalized_payload = json.loads(_canonical_bytes(dict(payload)))
        event_id = _digest({"kind": kind, "payload": normalized_payload})
        existing = self._by_id.get(event_id)
        if existing is not None:
            return existing, True
        body: dict[str, Any] = {
            "schema": TRADING_LEDGER_SCHEMA,
            "sequence": len(self._rows) + 1,
            "previous_sha256": self.head_sha256,
            "event_id": event_id,
            "kind": kind,
            "payload": normalized_payload,
        }
        row = {**body, "content_sha256": _digest(body)}
        blob = _canonical_bytes(row) + b"\n"
        with self.path.open("ab") as handle:
            handle.write(blob)
            handle.flush()
            os.fsync(handle.fileno())
        self._rows.append(row)
        self._by_id[event_id] = row
        return row, False

    def rows(self, kind: str | None = None) -> tuple[Mapping[str, Any], ...]:
        if kind is None:
            return tuple(self._rows)
        return tuple(row for row in self._rows if row["kind"] == kind)

    def get(self, event_id: str) -> Mapping[str, Any] | None:
        return self._by_id.get(event_id)


@dataclass(slots=True)
class _AccountState:
    equity: float
    peak: float
    position: float

    @property
    def drawdown(self) -> float:
        return 1.0 - self.equity / self.peak


class TradingField:
    """One persistent trading experience stream over one Cassi field owner."""

    def __init__(
        self,
        data_home: Path,
        *,
        config: TradingFieldConfig | None = None,
        hive_home: Path | None = None,
        import_skills: bool | None = None,
        instance_id: str = "auto",
        owner: Any | None = None,
    ) -> None:
        self.data_home = Path(data_home)
        self.data_home.mkdir(parents=True, exist_ok=True)
        self.ledger = TradingEvidenceLedger(self.data_home / "trading-evidence.jsonl")
        configuration_rows = self.ledger.rows("configuration")
        if config is None and configuration_rows:
            self.config = TradingFieldConfig.from_mapping(configuration_rows[0]["payload"])
        else:
            self.config = config or TradingFieldConfig()
        if configuration_rows:
            if any(row["payload"] != self.config.as_dict() for row in configuration_rows):
                raise ValueError("trading field configuration differs from the resident evidence ledger")
        skill_policy_rows = self.ledger.rows("skill-policy")
        resident_imports = (
            bool(cast(Mapping[str, Any], skill_policy_rows[-1]["payload"])["import_enabled"])
            if skill_policy_rows
            else False
        )
        resolved_imports = resident_imports if import_skills is None else bool(import_skills)
        self._profile = RegionalProfile(
            mode_count=self.config.field_mode_count,
            directory_capacity=256,
            max_native_work=32,
            kernel_names=STANDARD_KERNEL_CATALOG.names,
        )
        self._semantic_bounds: Mapping[str, int] = {
            "max_alternatives": 8,
            "max_observations": 1_024,
            "max_records": 8_192,
            "max_timeline": 8_192,
            "max_operations": 8_192,
            "max_versions": 128,
            "max_work": 65_536,
        }
        task_template = semantic_cognition_state(
            scope=SEMANTIC_SCOPE,
            frame=SEMANTIC_FRAME,
            bounds=self._semantic_bounds,
        )
        self._semantic_task_identity = {
            name: task_template[name]
            for name in ("schema", "family", "scope", "frame", "bounds")
        }
        workspace_bytes = _declared_workspace_bytes(self.config.field_mode_count)
        self._limits = CapacityLimits(
            max_state_bytes=workspace_bytes,
            max_workspace_bytes=workspace_bytes,
            max_operator_effort=int(self._semantic_bounds["max_work"]),
        )
        policy = SkillPolicy.for_mode(
            "scout",
            import_enabled=resolved_imports,
            export_enabled=True,
            apply_mode="never",
            sync_mode="on-open" if resolved_imports else "manual",
            export_mode="explicit",
            allowed_kinds=("reasoning-strategy",),
            allowed_domains=("trading",),
        )
        self._borrowed_owner = owner is not None
        self._computer_id = HOSTED_COMPUTER_ID if self._borrowed_owner else COMPUTER_ID
        if self._borrowed_owner and self.ledger.rows():
            self._require_matching_legacy_computer(owner)
        if owner is None:
            if not configuration_rows:
                self.ledger.append("configuration", self.config.as_dict())
            if import_skills is not None:
                self._persist_import_preference(resolved_imports)
        metadata = {
            "domain": "trading",
            "runtime_schema": TRADING_FIELD_SCHEMA,
            "compatibility_sha256": self.config.compatibility_sha256,
        }
        if owner is None:
            self.session = open_field_session(
                self.data_home,
                hive_home=hive_home,
                role="trading-field",
                mode="scout",
                instance_id=instance_id,
                policy=policy,
                profile_sha256=self._profile.fingerprint,
                limits=self._limits,
                metadata=metadata,
            )
        else:
            owner_home = getattr(owner, "data_home", None)
            if owner_home is None:
                raise RuntimeError("borrowed trading owner must expose its serialized field home")
            self.session = HiveField.attach(
                owner,
                field_home=Path(owner_home),
                hive_home=hive_home,
                role="trading-field",
                mode="scout",
                instance_id=instance_id,
                policy=policy,
                metadata=metadata,
                owns_owner=False,
            )
        self.owner = self.session.adapter.owner
        self._closed = False
        try:
            self._ensure_computer()
            if self._borrowed_owner:
                if not configuration_rows:
                    self.ledger.append("configuration", self.config.as_dict())
                if import_skills is not None:
                    self._persist_import_preference(resolved_imports)
            self._bars: list[MarketBar] = []
            self._bar_event_ids: list[str] = []
            self._decisions: list[Mapping[str, Any]] = []
            self._outcomes: list[Mapping[str, Any]] = []
            self._model_updates: list[Mapping[str, Any]] = []
            self._bar_rows_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
            self._decision_rows_by_index: dict[
                int, tuple[str, Mapping[str, Any]]
            ] = {}
            self._outcome_keys: set[tuple[str, int]] = set()
            self._outcome_event_ids: dict[tuple[str, int], str] = {}
            self._outcomes_by_horizon: dict[int, list[Mapping[str, Any]]] = {
                horizon: [] for horizon in self.config.outcome_horizons
            }
            self._model_updates_by_horizon: dict[
                int, list[Mapping[str, Any]]
            ] = {horizon: [] for horizon in self.config.outcome_horizons}
            self._model_deferrals_by_horizon: dict[
                int, list[Mapping[str, Any]]
            ] = {horizon: [] for horizon in self.config.outcome_horizons}
            self._model_cache: dict[
                int, Mapping[str, Any] | None
            ] = {}
            self._model_cache_state_sha256: str | None = None
            # A retained program is immutable, so its canonical payload is
            # validated once per revision instead of once per evaluation.
            self._canonical_programs: dict[str, Mapping[str, Any]] = {}
            self._pending_maturities: set[tuple[int, int]] = set()
            self._account = _AccountState(self.config.initial_equity, self.config.initial_equity, 0.0)
            self._risk_peak = self.config.initial_equity
            self._hard_stop_index: int | None = None
            self._reentry_until: int | None = None
            self._equity_before_decision: dict[int, float] = {}
            self._equity_after_decision: dict[int, float] = {}
            self._rebuild_runtime()
            self._imported_skills = self._discover_hive_skills() if resolved_imports else ()
        except Exception:
            self.session.close()
            raise

    @classmethod
    def open(
        cls,
        data_home: Path,
        *,
        config: TradingFieldConfig | None = None,
        hive_home: Path | None = None,
        import_skills: bool | None = None,
        instance_id: str = "auto",
        owner: Any | None = None,
    ) -> "TradingField":
        return cls(
            data_home,
            config=config,
            hive_home=hive_home,
            import_skills=import_skills,
            instance_id=instance_id,
            owner=owner,
        )

    def __enter__(self) -> "TradingField":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self.session.close()
            self._closed = True

    def _persist_import_preference(self, enabled: bool) -> None:
        rows = self.ledger.rows("skill-policy")
        if (
            rows
            and bool(cast(Mapping[str, Any], rows[-1]["payload"])["import_enabled"])
            == enabled
        ):
            return
        self.ledger.append(
            "skill-policy",
            {
                "revision": len(rows) + 1,
                "import_enabled": enabled,
                "export_enabled": True,
                "application_mode": "local-holdout-only",
            },
        )

    def _task_matches_trading_identity(self, task: Any) -> bool:
        return isinstance(task, Mapping) and all(
            task.get(name) == value
            for name, value in self._semantic_task_identity.items()
        )

    def _require_matching_legacy_computer(self, owner: Any) -> None:
        message = (
            "existing trading-evidence.jsonl has no matching hosted trading "
            "computer; refusing to reset trading learning. Preserve this ledger "
            "and its historical field home, then perform an explicit evidence-"
            "preserving migration to a matching cassi-trading computer/profile "
            "and cognition.field task before retrying."
        )
        rows = tuple(getattr(getattr(owner, "state", None), "computers", ()))
        matching = tuple(
            row
            for row in rows
            if getattr(row, "computer_id", None) == self._computer_id
        )
        if len(matching) != 1:
            raise RuntimeError(message)
        profile = getattr(matching[0], "profile", None)
        if getattr(profile, "fingerprint", None) != self._profile.fingerprint:
            raise RuntimeError(
                message + " The resident computer profile does not match."
            )
        try:
            inspected = owner.inspect_computers()
        except Exception as exc:
            raise RuntimeError(message) from exc
        computer_rows = (
            inspected.get("computers")
            if isinstance(inspected, Mapping)
            else None
        )
        if not isinstance(computer_rows, list):
            raise RuntimeError(message)
        inspected_matching = tuple(
            row
            for row in computer_rows
            if isinstance(row, Mapping) and row.get("computer_id") == self._computer_id
        )
        if (
            len(inspected_matching) != 1
            or not self._task_matches_trading_identity(
                inspected_matching[0].get("task")
            )
        ):
            raise RuntimeError(
                message
                + " The resident computer does not contain the exact trading cognition task."
            )

    def _computer_row(self) -> Any:
        rows = tuple(self.owner.state.computers)
        if self._borrowed_owner:
            matches = tuple(
                row for row in rows if row.computer_id == self._computer_id
            )
            if len(matches) != 1:
                raise RuntimeError("trading field requires exactly one hosted trading regional computer")
            row = matches[0]
        else:
            if len(rows) != 1 or rows[0].computer_id != self._computer_id:
                raise RuntimeError("trading field requires exactly one regional computer")
            row = rows[0]
        if row.profile.fingerprint != self._profile.fingerprint:
            raise RuntimeError("resident trading field profile differs from this runtime")
        return row

    def _computer_inspect(self) -> Mapping[str, Any]:
        inspected = self.owner.inspect_computers()
        rows = inspected.get("computers") if isinstance(inspected, Mapping) else None
        if not isinstance(rows, list):
            raise RuntimeError("trading regional computer inspection is incomplete")
        matching = tuple(
            row
            for row in rows
            if isinstance(row, Mapping) and row.get("computer_id") == self._computer_id
        )
        if len(matching) != 1 or (
            not self._borrowed_owner and len(rows) != 1
        ):
            raise RuntimeError("trading regional computer inspection is incomplete")
        return matching[0]

    def _operation_id(self, kind: str, identity: Any) -> str:
        token = _digest({"kind": kind, "identity": identity})[:40]
        return f"trading-{kind}-{token}"

    def _ensure_computer(self) -> None:
        existing = tuple(self.owner.state.computers)
        matching = tuple(
            row for row in existing if row.computer_id == self._computer_id
        )
        if not matching:
            if not self._borrowed_owner and not existing:
                usage = self.owner.inspect().get("capacity", {}).get("usage", {})
                if any(int(usage.get(name, 0)) for name in ("variables", "charts", "programs", "predictions", "plans", "macros")):
                    raise RuntimeError("trading data home contains a parallel legacy adaptive state")
            self.owner.operate_computer(
                self._operation_id("configure-computer", self._profile.fingerprint),
                computer_id=self._computer_id,
                action="configure",
                arguments={"profile": self._profile.as_dict()},
                expected_state_sha256=self.owner.state.state_sha256,
            )
        elif len(matching) != 1:
            raise RuntimeError("trading owner contains duplicate hosted trading regional computers")
        self._computer_row()
        inspected = self._computer_inspect()
        task = inspected.get("task")
        if not isinstance(task, Mapping):
            raise RuntimeError("trading regional task is unavailable")
        if task.get("schema") == "cassifi.learning-computer-idle.v1":
            state = semantic_cognition_state(
                scope=SEMANTIC_SCOPE,
                frame=SEMANTIC_FRAME,
                bounds=self._semantic_bounds,
            )
            self.owner.operate_computer(
                self._operation_id("submit-semantic", self.config.compatibility_sha256),
                computer_id=self._computer_id,
                action="submit",
                arguments={
                    "kernel": COGNITION_KERNEL,
                    "state": state,
                    "arguments": {
                        "operation": "inspect",
                        "operation_id": self._operation_id("semantic-initialize", self.config.compatibility_sha256),
                    },
                    "steps": 1,
                },
                expected_state_sha256=self.owner.state.state_sha256,
            )
            task = self._computer_inspect().get("task")
        if not self._task_matches_trading_identity(task):
            raise RuntimeError("trading computer does not contain the exact cognition.field trading task")
    def _invoke_semantic(self, label: str, request: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        before = {
            "manifest_sha256": self.owner.checkpoints.current_manifest_sha256,
            "state_sha256": self.owner.state.state_sha256,
        }
        invocation_id = self._operation_id(
            "invoke",
            {"label": label, "request": dict(request)},
        )
        invocation_receipt = self.owner.operate_computer(
            invocation_id,
            computer_id=self._computer_id,
            action="invoke-settled",
            arguments={
                "arguments": dict(request),
                "steps": int(self._semantic_bounds["max_work"]),
            },
        )
        receipt = invocation_receipt["receipt"]
        checkpoint = invocation_receipt["checkpoint_receipt"]
        result = receipt.get("consumed_result")
        if not isinstance(result, Mapping):
            raise RuntimeError("trading semantic request produced no result")
        predecessor_state_sha256 = before["state_sha256"]
        if checkpoint["predecessor_manifest_sha256"] != before["manifest_sha256"]:
            predecessor_state_sha256 = self.owner.checkpoints.load_version(
                checkpoint["predecessor_manifest_sha256"]
            ).state_sha256
        transition = {
            "operation_id": invocation_id,
            "generation": checkpoint["generation"],
            "manifest_sha256": checkpoint["manifest_sha256"],
            "state_sha256": checkpoint["state_sha256"],
            "predecessor_manifest_sha256": checkpoint["predecessor_manifest_sha256"],
            "predecessor_state_sha256": predecessor_state_sha256,
        }
        return result, transition

    def _rebuild_runtime(self) -> None:
        bar_rows = list(self.ledger.rows("bar"))
        seen_keys: dict[tuple[str, str], Mapping[str, Any]] = {}
        for row in bar_rows:
            payload = cast(Mapping[str, Any], row["payload"])
            bar = MarketBar.from_mapping(cast(Mapping[str, Any], payload["bar"]))
            key = (bar.symbol, bar.timestamp)
            if key in seen_keys and seen_keys[key] != payload:
                raise ValueError("trading ledger contains conflicting bars")
            seen_keys[key] = payload
            if self._bars and bar.timestamp <= self._bars[-1].timestamp:
                raise ValueError("trading ledger bars are not strictly chronological")
            self._bars.append(bar)
            self._bar_event_ids.append(str(row["event_id"]))
            self._bar_rows_by_key[key] = row

        decision_rows = self.ledger.rows("decision")
        for row in decision_rows:
            decision = cast(Mapping[str, Any], row["payload"])
            index = int(decision["bar_index"])
            if index in self._decision_rows_by_index:
                raise ValueError("trading ledger repeats a decision bar")
            self._decisions.append(decision)
            self._decision_rows_by_index[index] = (str(row["event_id"]), decision)

        for row in self.ledger.rows("outcome"):
            outcome = cast(Mapping[str, Any], row["payload"])
            key = (str(outcome["decision_event_id"]), int(outcome["horizon"]))
            if key in self._outcome_keys:
                raise ValueError("trading ledger repeats a decision outcome")
            self._outcomes.append(outcome)
            self._outcome_keys.add(key)
            self._outcome_event_ids[key] = str(row["event_id"])
            self._outcomes_by_horizon[int(outcome["horizon"])].append(outcome)

        for row in self.ledger.rows("model-update"):
            update = cast(Mapping[str, Any], row["payload"])
            self._model_updates.append(update)
            self._model_updates_by_horizon[int(update["horizon"])].append(update)

        for row in self.ledger.rows("model-update-deferred"):
            deferral = cast(Mapping[str, Any], row["payload"])
            self._model_deferrals_by_horizon[int(deferral["horizon"])].append(
                deferral
            )

        if self._bars:
            last_index = len(self._bars) - 1
            for decision_index, (decision_id, _) in self._decision_rows_by_index.items():
                for horizon in self.config.outcome_horizons:
                    if (
                        decision_index + horizon <= last_index
                        and (decision_id, horizon) not in self._outcome_keys
                    ):
                        self._pending_maturities.add((decision_index, horizon))

        decisions = {
            index: decision
            for index, (_, decision) in self._decision_rows_by_index.items()
        }
        account = _AccountState(
            self.config.initial_equity, self.config.initial_equity, 0.0
        )
        self._risk_peak = self.config.initial_equity
        self._hard_stop_index = None
        self._reentry_until = None
        for index, bar in enumerate(self._bars):
            if index > 0:
                realized = bar.close / self._bars[index - 1].close - 1.0
                account.equity *= 1.0 + account.position * realized
                if account.equity <= 0.0 or not math.isfinite(account.equity):
                    raise ValueError(
                        "resident account path became nonpositive or nonfinite"
                    )
                account.peak = max(account.peak, account.equity)
                self._risk_peak = max(self._risk_peak, account.equity)
            self._equity_before_decision[index] = account.equity
            decision = decisions.get(index)
            if decision is not None:
                self._account = account
                self._advance_risk_budget(index)
                risk_drawdown = self._risk_drawdown()
                if self._hard_stop_index is not None:
                    pass
                elif risk_drawdown >= self.config.hard_drawdown:
                    self._hard_stop_index = index
                if "risk_drawdown" in decision:
                    if not math.isclose(
                        float(decision["risk_drawdown"]),
                        risk_drawdown,
                        rel_tol=1.0e-12,
                        abs_tol=1.0e-12,
                    ):
                        raise ValueError(
                            "resident decision risk budget does not replay"
                        )
                    if (
                        int(decision.get("hard_stop_bar_index") or -1)
                        != int(self._hard_stop_index or -1)
                        or int(decision.get("recovery_reentry_until") or -1)
                        != int(self._reentry_until or -1)
                    ):
                        raise ValueError(
                            "resident decision risk gates do not replay"
                        )
                expected_before = float(decision["account_equity_before"])
                if not math.isclose(
                    account.equity,
                    expected_before,
                    rel_tol=1.0e-12,
                    abs_tol=1.0e-12,
                ):
                    raise ValueError(
                        "resident decision account predecessor does not replay"
                    )
                target = float(decision["target"])
                change = abs(target - account.position)
                account.equity *= 1.0 - change * self.config.transaction_cost
                account.position = target
                expected_after = float(decision["account_equity_after"])
                if not math.isclose(
                    account.equity,
                    expected_after,
                    rel_tol=1.0e-12,
                    abs_tol=1.0e-12,
                ):
                    raise ValueError(
                        "resident decision execution cost does not replay"
                    )
                account.peak = max(account.peak, account.equity)
            self._equity_after_decision[index] = account.equity
        self._account = account

    def _bar_payload(self, bar: MarketBar, index: int) -> Mapping[str, Any]:
        return {"bar": bar.as_dict(), "bar_index": index, "availability": "closed-candle"}

    def _features(self, index: int) -> dict[str, float]:
        if index < max(self.config.feature_windows):
            raise ValueError("feature history is not mature")
        bars = self._bars
        current = bars[index]
        state: dict[str, float] = {}
        one_bar_returns = [
            math.log(bars[offset].close / bars[offset - 1].close)
            for offset in range(1, index + 1)
        ]
        for window in self.config.feature_windows:
            start = index - window
            state[f"return_{window}"] = math.log(current.close / bars[start].close)
            changes = one_bar_returns[-window:]
            state[f"volatility_{window}"] = math.sqrt(sum(value * value for value in changes) / len(changes))
            state[f"range_{window}"] = sum(
                (bar.high - bar.low) / bar.close for bar in bars[index - window + 1 : index + 1]
            ) / window
            volumes = [math.log1p(bar.volume) for bar in bars[index - window + 1 : index + 1]]
            average = sum(volumes) / len(volumes)
            variance = sum((value - average) ** 2 for value in volumes) / len(volumes)
            state[f"volume_z_{window}"] = 0.0 if variance <= 1.0e-20 else (volumes[-1] - average) / math.sqrt(variance)
        long_window = max(self.config.feature_windows)
        peak = max(bar.close for bar in bars[index - long_window + 1 : index + 1])
        state["market_drawdown"] = 1.0 - current.close / peak
        state["position"] = self._account.position
        state["account_drawdown"] = self._account.drawdown
        medium_window = self.config.feature_windows[
            min(len(self.config.feature_windows) - 1, 2)
        ]
        short_window = self.config.feature_windows[
            min(len(self.config.feature_windows) - 1, 1)
        ]
        long_return = state[f"return_{long_window}"]
        medium_return = state[f"return_{medium_window}"]
        medium_volatility = state[f"volatility_{medium_window}"]
        short_volatility = state[f"volatility_{short_window}"]
        long_volatility = state[f"volatility_{long_window}"]
        aligned = long_return * medium_return >= 0.0
        state["regime_trend_up"] = float(long_return > long_volatility)
        state["regime_trend_down"] = float(long_return < -long_volatility)
        state["regime_range"] = float(
            abs(long_return) <= long_volatility
        )
        state["regime_transition"] = float(not aligned)
        state["regime_reversal"] = float(
            not aligned and abs(medium_return) > medium_volatility
        )
        state["regime_volatility_expansion"] = float(
            short_volatility > 1.25 * max(long_volatility, 1.0e-12)
        )
        state["regime_volatility_compression"] = float(
            short_volatility < 0.80 * max(long_volatility, 1.0e-12)
        )
        state["regime_liquidity_shock"] = float(
            abs(state[f"volume_z_{short_window}"]) >= 2.0
            and state[f"range_{short_window}"]
            >= state[f"range_{long_window}"]
        )
        return {name: float(state[name]) for name in sorted(state)}

    def _regime(self, state: Mapping[str, float]) -> str:
        if state["regime_trend_up"] > 0.5:
            direction = "up"
        elif state["regime_trend_down"] > 0.5:
            direction = "down"
        else:
            direction = "range"
        phase = "transition" if state["regime_transition"] > 0.5 else "aligned"
        if state["regime_liquidity_shock"] > 0.5:
            volatility = "liquidity-shock"
        elif state["regime_volatility_expansion"] > 0.5:
            volatility = "expansion"
        elif state["regime_volatility_compression"] > 0.5:
            volatility = "compression"
        else:
            volatility = "normal"
        return f"{direction}-{phase}-{volatility}"

    def _baseline_target(self, state: Mapping[str, float]) -> float:
        windows = self.config.feature_windows
        short = state[f"return_{windows[0]}"]
        medium = state[f"return_{windows[min(1, len(windows) - 1)]}"]
        long = state[f"return_{windows[-1]}"]
        volatility = state[f"volatility_{windows[min(2, len(windows) - 1)]}"]
        score = 0.20 * short + 0.35 * medium + 0.45 * long
        threshold = max(0.0005, 0.5 * volatility)
        if score > threshold:
            requested = self.config.max_position if score > 2.0 * threshold else 0.5 * self.config.max_position
        elif score < -threshold and self.config.allow_short:
            requested = -self.config.max_position if score < -2.0 * threshold else -0.5 * self.config.max_position
        else:
            requested = 0.0
        return min(self.config.action_levels, key=lambda value: (abs(value - requested), abs(value)))

    def _action_values(self, target: float, state: Mapping[str, float], position_before: float) -> dict[str, float]:
        action = {
            "target": float(target),
            "abs_target": abs(float(target)),
            "turnover": abs(float(target) - position_before),
            "position_before": position_before,
        }
        for level in self.config.action_levels:
            label = f"level_{'m' if level < 0.0 else 'p'}{int(round(abs(level) * 100)):03d}"
            action[label] = 1.0 if math.isclose(target, level, abs_tol=1.0e-12) else 0.0
        for name, value in state.items():
            action[f"target_x_{name}"] = float(target) * float(value)
        return action

    def _mechanism_id(self, horizon: int) -> str:
        return f"trading-market-h{horizon}"

    def _reserved_slice_verdict(
        self,
        horizon: int,
        program: Mapping[str, Any],
        *,
        candidate_id: str,
        training_rows: int,
        training_decisions: int,
    ) -> dict[str, Any] | None:
        """Judge a retained program on the same slice as every candidate.

        The reserved slice is the chronological tail of the field's own model
        window: the constant baseline is fitted on its earlier decisions and
        every mechanism is measured on the later ones, so a mechanism that came
        from the semantic panel faces the identical data, support, and margin
        requirement as a locally fitted candidate.
        """
        selected = self._select_model_outcomes(horizon)
        if len(selected) < 2:
            return None
        holdout_count = max(
            1, min(self.config.semantic_evaluation_decisions, len(selected) // 5)
        )
        train_rows = self._modeled_rows(selected[:-holdout_count])
        holdout_rows = self._modeled_rows(selected[-holdout_count:])
        if not train_rows or not holdout_rows:
            return None
        _, baseline_domain = self._fit_affine(
            train_rows,
            holdout_rows,
            state_features=(),
            action_features=(),
            candidate_id="constant-baseline",
        )
        domain, unsupported = self._program_loss(
            program,
            holdout_rows,
            candidate_id=candidate_id,
            baseline_objective_rmse=float(baseline_domain["objective_rmse"]),
            training_rows=training_rows,
            training_decisions=training_decisions,
        )
        domain["reserved_support_gap_rows"] = unsupported
        return domain

    def _model_from_reference(
        self, reference: Mapping[str, Any], horizon: int | None = None
    ) -> Mapping[str, Any] | None:
        task = self._computer_inspect().get("task")
        records = task.get("records") if isinstance(task, Mapping) else None
        if not isinstance(records, Mapping):
            return None
        try:
            record = resolve_semantic_record(cast(Any, records), cast(Any, reference))
        except Exception:
            return None
        payload = record.get("payload")
        if not isinstance(payload, Mapping) or not isinstance(payload.get("program"), Mapping):
            return None
        parameter_domain = payload.get("parameter_domain", {})
        parameter_domain = (
            dict(parameter_domain) if isinstance(parameter_domain, Mapping) else {}
        )
        selection = parameter_domain.get("context_selection")
        if isinstance(selection, Mapping):
            errors = selection["selected_composite_holdout_output_errors"]
            baseline_errors = selection["candidate_holdout_output_errors"].get(
                "constant-baseline", {}
            )
            branches = selection["branches"]
            training_rows = sum(
                int(branch["training_scored_count"]) for branch in branches
            )
            training_decisions = sum(
                int(branch["training_distinct_pair_or_episode_count"])
                for branch in branches
            )
            panel_holdout_rows = int(
                errors.get("objective", {}).get("observed_count", 0)
            )
            panel_rmse = float(errors.get("objective", {}).get("rmse", 1.0e12))
            panel_baseline = float(
                baseline_errors.get("objective", {}).get("rmse", 0.0)
            )
            panel_domain = {
                "schema": "cassi.trading-model-diagnostics.v1",
                "candidate_id": payload.get("selected_candidate"),
                "training_rows": training_rows,
                "validation_rows": panel_holdout_rows,
                "objective_rmse": panel_rmse,
                "baseline_objective_rmse": panel_baseline,
                "relative_objective_loss": panel_rmse / max(1.0e-12, panel_baseline),
                "adequate_for_trading": False,
                "output_errors": {
                    name: float(
                        errors.get(name, {}).get("absolute_error_p90", 1.0e12)
                    )
                    for name in MODEL_OUTPUTS
                },
                "context_selection": selection,
                "panel_holdout_rows": panel_holdout_rows,
                "panel_support_gap_rows": int(
                    selection.get("support_gap_holdout_count", 0)
                ),
            }
            verdict = (
                self._reserved_slice_verdict(
                    horizon,
                    payload["program"],
                    candidate_id=str(payload.get("selected_candidate")),
                    training_rows=training_rows,
                    training_decisions=training_decisions,
                )
                if horizon is not None
                else None
            )
            # A discovered composite steers only on the field's own reserved
            # slice, under the identical standard every candidate faces. The
            # panel's held-out numbers stay in the record as discovery evidence.
            parameter_domain = panel_domain if verdict is None else {**panel_domain, **verdict}
        return {
            "record": record,
            "reference": dict(reference),
            "program": dict(cast(Mapping[str, Any], payload["program"])),
            "parameter_domain": parameter_domain,
            "selected_candidate": payload.get("selected_candidate"),
        }

    def _load_model_for_horizon(
        self, horizon: int
    ) -> Mapping[str, Any] | None:
        for update in reversed(self._model_updates):
            if int(update["horizon"]) != horizon:
                continue
            reference = update.get("mechanism_reference")
            if isinstance(reference, Mapping):
                return self._model_from_reference(reference, horizon)
        task = self._computer_inspect().get("task")
        tasks = task.get("tasks") if isinstance(task, Mapping) else None
        mechanism_task = (
            tasks.get(f"mechanism:{self._mechanism_id(horizon)}")
            if isinstance(tasks, Mapping)
            else None
        )
        reference = (
            mechanism_task.get("mechanism")
            if isinstance(mechanism_task, Mapping)
            else None
        )
        return (
            self._model_from_reference(reference, horizon)
            if isinstance(reference, Mapping)
            else None
        )

    def _model_for_horizon(
        self, horizon: int
    ) -> Mapping[str, Any] | None:
        state_sha256 = self._computer_row().state_sha256
        if state_sha256 != self._model_cache_state_sha256:
            self._model_cache.clear()
            self._model_cache_state_sha256 = state_sha256
        if horizon not in self._model_cache:
            self._model_cache[horizon] = self._load_model_for_horizon(
                horizon
            )
        return self._model_cache[horizon]

    def _canonical_program(
        self, model: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """The model's program in canonical payload form, validated once."""

        key = str(model["reference"])
        cached = self._canonical_programs.get(key)
        if cached is None:
            cached = canonical_semantic_program_payload(model["program"])
            self._canonical_programs[key] = cached
        return cached

    def _predict_action(self, state: Mapping[str, float], target: float) -> tuple[dict[str, Any], ...]:
        action = self._action_values(target, state, self._account.position)
        predictions: list[dict[str, Any]] = []
        for horizon in self.config.outcome_horizons:
            model = self._model_for_horizon(horizon)
            if model is None:
                continue
            result = execute_canonical_semantic_program(
                self._canonical_program(model), state, action=action
            )
            if result.get("status") != "supported":
                continue
            values = cast(Mapping[str, Any], result["values"])
            domain = cast(Mapping[str, Any], model["parameter_domain"])
            errors = domain.get("output_errors", {})
            if not isinstance(errors, Mapping):
                errors = {}
            prediction = {
                "horizon": horizon,
                "model_reference": model["reference"],
                "selected_candidate": model["selected_candidate"],
                "adequate_for_trading": bool(domain.get("adequate_for_trading", False)),
                "values": {name: float(values[name]) for name in MODEL_OUTPUTS},
                "errors": {name: float(errors.get(name, 0.0)) for name in MODEL_OUTPUTS},
            }
            predictions.append(prediction)
        return tuple(predictions)

    def _candidate_score(self, predictions: Sequence[Mapping[str, Any]]) -> tuple[float, float, bool]:
        adequate = [row for row in predictions if row["adequate_for_trading"]]
        if not adequate:
            return -math.inf, math.inf, False
        weights = [1.0 / math.sqrt(float(row["horizon"])) for row in adequate]
        total = sum(weights)
        score = 0.0
        risk = 0.0
        for weight, row in zip(weights, adequate, strict=True):
            values = cast(Mapping[str, float], row["values"])
            errors = cast(Mapping[str, float], row["errors"])
            lower_objective = values["objective"] - errors["objective"]
            upper_drawdown = values["max_drawdown"] + errors["max_drawdown"]
            upper_downside = values["downside"] + errors["downside"]
            score += weight * (lower_objective - self.config.downside_penalty * upper_downside)
            risk += weight * upper_drawdown
        return score / total, risk / total, True

    def _choose_action(self, index: int, state: Mapping[str, float]) -> Mapping[str, Any]:
        baseline = self._baseline_target(state)
        rows: list[dict[str, Any]] = []
        for target in self.config.action_levels:
            predictions = self._predict_action(state, target)
            score, risk, adequate = self._candidate_score(predictions)
            rows.append(
                {
                    "target": target,
                    "score": score if math.isfinite(score) else None,
                    "predicted_drawdown": risk if math.isfinite(risk) else None,
                    "adequate": adequate,
                    "predictions": list(predictions),
                }
            )
        by_target = {float(row["target"]): row for row in rows}
        baseline_row = by_target[float(baseline)]
        adequate_rows = [
            row
            for row in rows
            if row["adequate"]
            and cast(float, row["predicted_drawdown"]) <= self.config.soft_drawdown
        ]
        selected = baseline
        source = "fixed-baseline"
        if adequate_rows:
            best = max(
                adequate_rows,
                key=lambda row: (cast(float, row["score"]), -abs(float(row["target"])), -float(row["target"])),
            )
            baseline_score = baseline_row["score"]
            if baseline_score is None or cast(float, best["score"]) >= cast(float, baseline_score) + self.config.minimum_action_edge:
                selected = float(best["target"])
                source = "field-mechanism"
        self._advance_risk_budget(index)
        risk_drawdown = self._risk_drawdown()
        if self._hard_stop_index is not None:
            selected = 0.0
            source = "hard-risk-gate"
        elif risk_drawdown >= self.config.hard_drawdown:
            self._hard_stop_index = index
            selected = 0.0
            source = "hard-risk-gate"
        elif (
            self._reentry_until is not None
            and index < self._reentry_until
            and abs(selected) > self.config.hard_stop_reentry_cap
        ):
            selected = math.copysign(self.config.hard_stop_reentry_cap, selected)
            selected = min(self.config.action_levels, key=lambda value: abs(value - selected))
            source = "recovery-reentry"
        elif risk_drawdown >= self.config.soft_drawdown and abs(selected) > 0.25:
            selected = math.copysign(0.25, selected)
            selected = min(self.config.action_levels, key=lambda value: abs(value - selected))
            source = "soft-risk-gate"
        return {
            "target": selected,
            "baseline_target": baseline,
            "selection_source": source,
            "risk_drawdown": risk_drawdown,
            "hard_stop_bar_index": self._hard_stop_index,
            "recovery_reentry_until": self._reentry_until,
            "candidates": rows,
        }

    def _risk_drawdown(self) -> float:
        return max(0.0, 1.0 - self._account.equity / max(self._risk_peak, 1.0e-12))

    def _advance_risk_budget(self, index: int) -> None:
        """Release a completed hard-stop halt and re-base the risk budget."""
        stop_index = self._hard_stop_index
        if stop_index is None:
            return
        if index - stop_index < self.config.hard_stop_cooldown_bars:
            return
        self._hard_stop_index = None
        self._risk_peak = self._account.equity
        self._reentry_until = index + self.config.hard_stop_reentry_bars

    def _decision_due(self, index: int) -> bool:
        return index >= self.config.warmup_bars and (index - self.config.warmup_bars) % self.config.decision_interval == 0

    def _record_decision(self, index: int) -> Mapping[str, Any]:
        state = self._features(index)
        selection = self._choose_action(index, state)
        target = float(selection["target"])
        before = self._account.equity
        change = abs(target - self._account.position)
        self._account.equity *= 1.0 - change * self.config.transaction_cost
        if self._account.equity <= 0.0:
            raise RuntimeError("decision execution cost exhausted account equity")
        self._account.position = target
        self._account.peak = max(self._account.peak, self._account.equity)
        self._equity_after_decision[index] = self._account.equity
        payload = {
            "bar_event_id": self._bar_event_ids[index],
            "bar_index": index,
            "timestamp": self._bars[index].timestamp,
            "symbol": self.config.symbol,
            "state": state,
            "regime": self._regime(state),
            "position_before": float(state["position"]),
            "target": target,
            "baseline_target": float(selection["baseline_target"]),
            "selection_source": selection["selection_source"],
            "risk_drawdown": float(selection["risk_drawdown"]),
            "hard_stop_bar_index": selection["hard_stop_bar_index"],
            "recovery_reentry_until": selection["recovery_reentry_until"],
            "candidate_predictions": selection["candidates"],
            "account_equity_before": before,
            "account_equity_after": self._account.equity,
            "transaction_cost": change * self.config.transaction_cost,
            "policy_version": self.config.compatibility_sha256,
        }
        row, replayed = self.ledger.append("decision", payload)
        if replayed:
            raise RuntimeError("new bar unexpectedly reproduced an existing decision")
        self._decisions.append(cast(Mapping[str, Any], row["payload"]))
        self._decision_rows_by_index[index] = (
            str(row["event_id"]),
            cast(Mapping[str, Any], row["payload"]),
        )
        return row

    def _fixed_action_outcome(self, decision: Mapping[str, Any], horizon: int, target: float) -> dict[str, float]:
        start = int(decision["bar_index"])
        end = start + horizon
        position_before = float(decision["position_before"])
        turnover = abs(target - position_before)
        cost = turnover * self.config.transaction_cost
        equity = 1.0 - cost
        peak = 1.0
        maximum_drawdown = max(0.0, 1.0 - equity / peak)
        step_returns: list[float] = [-cost] if cost > 0.0 else []
        funding_per_bar = abs(min(0.0, target)) * self.config.short_funding_bps_daily / 10_000.0 * self.config.bar_hours / 24.0
        for offset in range(start + 1, end + 1):
            market_return = self._bars[offset].close / self._bars[offset - 1].close - 1.0
            net_step = target * market_return - funding_per_bar
            equity *= 1.0 + net_step
            peak = max(peak, equity)
            maximum_drawdown = max(maximum_drawdown, 1.0 - equity / peak)
            step_returns.append(net_step)
            cost += funding_per_bar
        negative = [value for value in step_returns if value < 0.0]
        downside = math.sqrt(sum(value * value for value in negative) / len(negative)) if negative else 0.0
        net_return = equity - 1.0
        objective = net_return - self.config.risk_penalty * maximum_drawdown - self.config.downside_penalty * downside
        return {
            "objective": objective,
            "net_return": net_return,
            "max_drawdown": maximum_drawdown,
            "downside": downside,
            "cost": cost,
        }

    def _decision_prediction(self, decision: Mapping[str, Any], horizon: int, target: float) -> float | None:
        candidates = decision.get("candidate_predictions", [])
        if not isinstance(candidates, list):
            return None
        for candidate in candidates:
            if not isinstance(candidate, Mapping) or not math.isclose(float(candidate.get("target", math.inf)), target, abs_tol=1.0e-12):
                continue
            predictions = candidate.get("predictions", [])
            if not isinstance(predictions, list):
                return None
            for prediction in predictions:
                if isinstance(prediction, Mapping) and int(prediction.get("horizon", -1)) == horizon:
                    values = prediction.get("values")
                    if isinstance(values, Mapping) and "objective" in values:
                        return float(values["objective"])
        return None

    def _mature_outcomes(
        self, current_index: int
    ) -> tuple[Mapping[str, Any], ...]:
        candidates = set(self._pending_maturities)
        for horizon in self.config.outcome_horizons:
            decision_index = current_index - horizon
            if decision_index in self._decision_rows_by_index:
                candidates.add((decision_index, horizon))

        added: list[Mapping[str, Any]] = []
        for decision_index, horizon in sorted(candidates):
            if decision_index + horizon > current_index:
                continue
            decision_id, decision = self._decision_rows_by_index[decision_index]
            key = (decision_id, horizon)
            if key in self._outcome_keys:
                self._pending_maturities.discard((decision_index, horizon))
                continue
            modeled_actions = []
            for target in self.config.action_levels:
                metrics = self._fixed_action_outcome(decision, horizon, target)
                modeled_actions.append(
                    {
                        "target": target,
                        "selected_action": math.isclose(
                            target,
                            float(decision["target"]),
                            abs_tol=1.0e-12,
                        ),
                        "provenance": (
                            "modeled-fixed-exposure-on-observed-price-path"
                        ),
                        **metrics,
                    }
                )
            selected = next(row for row in modeled_actions if row["selected_action"])
            best = max(modeled_actions, key=lambda row: float(row["objective"]))
            predicted = self._decision_prediction(
                decision, horizon, float(decision["target"])
            )
            start_equity = float(decision["account_equity_after"])
            actual_equity = self._equity_before_decision[
                decision_index + horizon
            ]
            actual_return = actual_equity / start_equity - 1.0
            payload = {
                "decision_event_id": decision_id,
                "decision_index": decision_index,
                "maturity_bar_event_id": self._bar_event_ids[
                    decision_index + horizon
                ],
                "maturity_timestamp": self._bars[
                    decision_index + horizon
                ].timestamp,
                "horizon": horizon,
                "state": decision["state"],
                "regime": decision["regime"],
                "position_before": decision["position_before"],
                "selected_target": decision["target"],
                "selection_source": decision["selection_source"],
                "observed_policy_path": {
                    "provenance": "observed-account-path-with-later-policy-actions",
                    "net_return": actual_return,
                },
                "modeled_actions": modeled_actions,
                "selected_modeled_outcome": selected,
                "best_modeled_target": best["target"],
                "regret": float(best["objective"])
                - float(selected["objective"]),
                "predicted_objective": predicted,
                "prediction_error": (
                    None
                    if predicted is None
                    else abs(predicted - float(selected["objective"]))
                ),
                "causal_status": "observational-no-market-impact-model",
            }
            row, replayed = self.ledger.append("outcome", payload)
            if not replayed:
                normalized = cast(Mapping[str, Any], row["payload"])
                self._outcomes.append(normalized)
                self._outcomes_by_horizon[horizon].append(normalized)
                added.append(row)
                self._outcome_event_ids[key] = str(row["event_id"])
            self._outcome_keys.add(key)
            self._pending_maturities.discard((decision_index, horizon))
        return tuple(added)

    def _update_due(self, horizon: int) -> bool:
        outcomes = self._outcomes_by_horizon[horizon]
        updates = self._model_updates_by_horizon[horizon]
        deferrals = self._model_deferrals_by_horizon[horizon]
        count = len(outcomes)
        latest_update_count = (
            int(updates[-1]["outcome_count"]) if updates else 0
        )
        latest_deferral_count = (
            int(deferrals[-1]["outcome_count"]) if deferrals else 0
        )
        if deferrals and latest_deferral_count >= latest_update_count:
            return count - latest_deferral_count >= self.config.update_interval
        if len(updates) < len(self.config.update_thresholds):
            return count >= self.config.update_thresholds[len(updates)]
        return count - latest_update_count >= self.config.update_interval

    def _select_model_outcomes(
        self, horizon: int
    ) -> list[Mapping[str, Any]]:
        rows = self._outcomes_by_horizon[horizon]
        if len(rows) <= self.config.model_window:
            return list(rows)
        recent_count = self.config.model_window // 2
        recent = rows[-recent_count:]
        recent_ids = {str(row["decision_event_id"]) for row in recent}
        earlier = [
            row
            for row in rows[:-recent_count]
            if str(row["decision_event_id"]) not in recent_ids
        ]
        earlier.sort(
            key=lambda row: (
                float(row["prediction_error"] or 0.0) + float(row["regret"]),
                int(row["decision_index"]),
            ),
            reverse=True,
        )
        replay = earlier[: self.config.model_window - recent_count]
        selected = [*replay, *recent]
        selected.sort(key=lambda row: int(row["decision_index"]))
        return selected

    def _modeled_rows(self, outcomes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for outcome in outcomes:
            state = {str(name): float(value) for name, value in cast(Mapping[str, Any], outcome["state"]).items()}
            position_before = float(outcome["position_before"])
            actions = cast(Sequence[Mapping[str, Any]], outcome["modeled_actions"])
            for action_outcome in actions:
                target = float(action_outcome["target"])
                rows.append(
                    {
                        "decision_event_id": str(outcome["decision_event_id"]),
                        "decision_index": int(outcome["decision_index"]),
                        "state": state,
                        "action": self._action_values(target, state, position_before),
                        "next": {name: float(action_outcome[name]) for name in MODEL_OUTPUTS},
                        "selected_action": bool(action_outcome["selected_action"]),
                        "horizon": int(outcome["horizon"]),
                    }
                )
        return rows

    @staticmethod
    def _solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
        size = len(vector)
        augmented = [list(row) + [vector[index]] for index, row in enumerate(matrix)]
        for column in range(size):
            pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
            if abs(augmented[pivot][column]) <= 1.0e-18:
                raise ValueError("ridge system is singular")
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
            scale = augmented[column][column]
            augmented[column] = [value / scale for value in augmented[column]]
            for row in range(size):
                if row == column:
                    continue
                factor = augmented[row][column]
                if factor == 0.0:
                    continue
                augmented[row] = [
                    value - factor * pivot_value
                    for value, pivot_value in zip(augmented[row], augmented[column], strict=True)
                ]
        return [augmented[index][-1] for index in range(size)]

    def _fit_affine(
        self,
        train: Sequence[Mapping[str, Any]],
        validation: Sequence[Mapping[str, Any]],
        *,
        state_features: Sequence[str],
        action_features: Sequence[str],
        candidate_id: str,
        baseline_objective_rmse: float | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        descriptors = [("state", name) for name in state_features] + [("action", name) for name in action_features]
        width = len(descriptors) + 1
        design = [
            [1.0] + [float(cast(Mapping[str, Any], row[space])[name]) for space, name in descriptors]
            for row in train
        ]
        outputs: dict[str, Any] = {}
        coefficients_by_output: dict[str, list[float]] = {}
        matrix = [[0.0 for _ in range(width)] for _ in range(width)]
        vectors = {
            output: [0.0 for _ in range(width)]
            for output in MODEL_OUTPUTS
        }
        for features, row in zip(design, train, strict=True):
            targets = cast(Mapping[str, Any], row["next"])
            for left, left_value in enumerate(features):
                for output in MODEL_OUTPUTS:
                    vectors[output][left] += (
                        left_value * float(targets[output])
                    )
                for right in range(left, width):
                    matrix[left][right] += (
                        left_value * features[right]
                    )
        for left in range(width):
            for right in range(left + 1, width):
                matrix[right][left] = matrix[left][right]
        for diagonal in range(1, width):
            matrix[diagonal][diagonal] += 1.0e-6
        for output in MODEL_OUTPUTS:
            coefficients = self._solve_linear(matrix, vectors[output])
            coefficients_by_output[output] = coefficients
            terms: dict[str, float] = {}
            action_terms: dict[str, float] = {}
            for coefficient, (space, name) in zip(coefficients[1:], descriptors, strict=True):
                if abs(coefficient) < 1.0e-15:
                    continue
                (terms if space == "state" else action_terms)[name] = coefficient
            outputs[output] = {
                "terms": terms,
                "action_terms": action_terms,
                "bias": coefficients[0],
                "error": 0.0,
            }
        program = semantic_program_payload(
            program_kind="affine",
            body={
                "clamp": {
                    "max_drawdown": [0.0, 10.0],
                    "downside": [0.0, 10.0],
                    "cost": [0.0, 10.0],
                },
                "outputs": outputs,
            },
            reads=list(state_features),
            writes=list(MODEL_OUTPUTS),
            max_work=len(MODEL_OUTPUTS),
        )
        evaluation = list(validation) if validation else list(train)
        domain, _ = self._program_loss(
            program,
            evaluation,
            candidate_id=candidate_id,
            baseline_objective_rmse=baseline_objective_rmse,
            training_rows=len(train),
            training_decisions=len(
                {str(row["decision_event_id"]) for row in train}
            ),
        )
        return program, domain

    def _program_loss(
        self,
        program: Mapping[str, Any],
        rows: Sequence[Mapping[str, Any]],
        *,
        candidate_id: str,
        baseline_objective_rmse: float | None,
        training_rows: int,
        training_decisions: int,
    ) -> tuple[dict[str, Any], int]:
        """Absolute errors of one program on one slice, and its unsupported rows.

        One gate judges every retained program: at least six supporting training
        decisions, full support on the evaluated slice, and at least two percent
        less objective error than the constant baseline on that same slice.
        """
        errors: dict[str, list[float]] = {name: [] for name in MODEL_OUTPUTS}
        canonical = canonical_semantic_program_payload(program)
        unsupported = 0
        for row in rows:
            result = execute_canonical_semantic_program(
                canonical,
                cast(Mapping[str, Any], row["state"]),
                action=cast(Mapping[str, Any], row["action"]),
            )
            if result.get("status") != "supported":
                unsupported += 1
                continue
            values = cast(Mapping[str, Any], result["values"])
            for output in MODEL_OUTPUTS:
                errors[output].append(
                    abs(
                        float(values[output])
                        - float(cast(Mapping[str, Any], row["next"])[output])
                    )
                )
        output_errors = {name: _percentile(values, 0.90) for name, values in errors.items()}
        objective_rmse = math.sqrt(
            sum(value * value for value in errors["objective"])
            / max(1, len(errors["objective"]))
        )
        if baseline_objective_rmse is None:
            adequate = False
            relative = 1.0
        else:
            relative = objective_rmse / max(1.0e-12, baseline_objective_rmse)
            adequate = (
                training_decisions >= 6
                and unsupported == 0
                and relative <= 0.98
            )
        domain = {
            "schema": "cassi.trading-model-diagnostics.v1",
            "candidate_id": candidate_id,
            "training_rows": training_rows,
            "validation_rows": len(rows),
            "objective_rmse": objective_rmse,
            "baseline_objective_rmse": objective_rmse if baseline_objective_rmse is None else baseline_objective_rmse,
            "relative_objective_loss": relative,
            "adequate_for_trading": adequate,
            "output_errors": output_errors,
        }
        return domain, unsupported

    def _local_candidates(
        self,
        train: Sequence[Mapping[str, Any]],
        validation: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        state_names = sorted(cast(Mapping[str, Any], train[0]["state"]))
        action_names = sorted(cast(Mapping[str, Any], train[0]["action"]))
        regime_state_names = [
            name for name in state_names if name.startswith("regime_")
        ]
        contextual_state_names = [
            name for name in state_names if not name.startswith("regime_")
        ]
        contextual_action_names = [
            name
            for name in action_names
            if not name.startswith("target_x_regime_")
        ]
        baseline_program, baseline_domain = self._fit_affine(
            train,
            validation,
            state_features=(),
            action_features=(),
            candidate_id="constant-baseline",
        )
        baseline_rmse = float(baseline_domain["objective_rmse"])
        exposure_names = [
            name for name in action_names if not name.startswith("target_x_")
        ]
        exposure_program, exposure_domain = self._fit_affine(
            train,
            validation,
            state_features=(),
            action_features=exposure_names,
            candidate_id="exposure-only",
            baseline_objective_rmse=baseline_rmse,
        )
        contextual_program, contextual_domain = self._fit_affine(
            train,
            validation,
            state_features=contextual_state_names,
            action_features=contextual_action_names,
            candidate_id="contextual-multiscale",
            baseline_objective_rmse=baseline_rmse,
        )
        regime_program, regime_domain = self._fit_affine(
            train,
            validation,
            state_features=state_names,
            action_features=action_names,
            candidate_id="regime-conditioned",
            baseline_objective_rmse=baseline_rmse,
        )
        regime_domain["regime_features"] = regime_state_names
        candidates = [
            ("constant-baseline", baseline_program, baseline_domain),
            ("exposure-only", exposure_program, exposure_domain),
            ("contextual-multiscale", contextual_program, contextual_domain),
            ("regime-conditioned", regime_program, regime_domain),
        ]
        return [
            {
                "candidate_id": candidate_id,
                "program": program,
                "parameter_domain": domain,
                "selection_assumptions": [
                    "observed-market-path",
                    "modeled-no-market-impact",
                    "noncausal-comparison",
                ],
            }
            for candidate_id, program, domain in candidates
        ]

    def _semantic_episode(self, row: Mapping[str, Any]) -> dict[str, Any]:
        target = float(cast(Mapping[str, Any], row["action"])["target"])
        return {
            "episode_id": _digest({"decision": row["decision_event_id"], "horizon": row["horizon"], "target": target}),
            "pair_id": str(row["decision_event_id"]),
            "state": dict(cast(Mapping[str, Any], row["state"])),
            "action": dict(cast(Mapping[str, Any], row["action"])),
            "next": dict(cast(Mapping[str, Any], row["next"])),
            "context": {"provenance": "modeled-fixed-exposure-on-observed-price-path"},
            "interval": {"duration_bars": int(row["horizon"])},
            "intervention": False,
            "outcome_status": "observed-and-scored",
            "collection": {
                "outcome_availability": "observed-price-path-complete",
                "policy_version": self.config.compatibility_sha256,
                "selection_assumptions": ["no-market-impact-model"],
                "selection_mode": "deterministic",
            },
        }

    @staticmethod
    def _atom(value: Any) -> dict[str, Any]:
        if isinstance(value, bool):
            typ = "boolean"
        elif isinstance(value, int):
            typ = "integer"
        elif isinstance(value, float):
            typ = "number"
        elif isinstance(value, str):
            typ = "lexeme"
        else:
            raise TypeError("typed trading atom is unsupported")
        return {"kind": "atom", "type": typ, "value": value}

    @classmethod
    def _record_term(cls, values: Mapping[str, Any]) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        for name, value in values.items():
            if isinstance(value, Mapping):
                fields[name] = cls._record_term(cast(Mapping[str, Any], value))
            elif isinstance(value, (list, tuple)):
                fields[name] = {
                    "kind": "sequence",
                    "items": [cls._record_term(item) if isinstance(item, Mapping) else cls._atom(item) for item in value],
                }
            else:
                fields[name] = cls._atom(value)
        return {"kind": "record", "fields": fields}

    def _typed_batch_episode(self, horizon: int, outcomes: Sequence[Mapping[str, Any]], batch_id: str) -> dict[str, Any]:
        experience_terms = []
        for outcome in outcomes[-self.config.episode_batch_decisions :]:
            modeled = [
                {
                    "target": float(row["target"]),
                    "selected_action": bool(row["selected_action"]),
                    "provenance": str(row["provenance"]),
                    **{name: float(row[name]) for name in MODEL_OUTPUTS},
                }
                for row in cast(Sequence[Mapping[str, Any]], outcome["modeled_actions"])
            ]
            experience_terms.append(
                {
                    "decision_event_id": str(outcome["decision_event_id"]),
                    "state": dict(cast(Mapping[str, Any], outcome["state"])),
                    "selected_target": float(outcome["selected_target"]),
                    "selection_source": str(outcome["selection_source"]),
                    "observed_policy_path": dict(cast(Mapping[str, Any], outcome["observed_policy_path"])),
                    "modeled_actions": modeled,
                    "regret": float(outcome["regret"]),
                    "prediction_error": float(outcome["prediction_error"] or 0.0),
                }
            )
        return {
            "event_id": batch_id,
            "source_revision_ids": ["pending-source"],
            "pre_state": self._record_term(
                {
                    "domain": "trading",
                    "horizon_bars": horizon,
                    "unique_decisions": len(outcomes),
                    "compatibility_sha256": self.config.compatibility_sha256,
                }
            ),
            "action": {
                "kind": "constructor",
                "name": "update-market-mechanism",
                "args": [self._atom(horizon)],
                "type": {"kind": "named", "name": "trading-model-update"},
            },
            "post_state": self._record_term({"experiences": experience_terms}),
            "bindings": {
                "symbol": self._atom(self.config.symbol),
                "horizon": self._atom(horizon),
            },
            "observation": {
                "success": True,
                "provenance": "observed-decisions-plus-no-impact-action-panel",
                "causal_status": "unidentified",
                "unique_decision_count": len(experience_terms),
            },
        }
    def _typed_batch_summary_episode(
        self,
        horizon: int,
        outcomes: Sequence[Mapping[str, Any]],
        batch_id: str,
    ) -> dict[str, Any]:
        selected = outcomes[-self.config.episode_batch_decisions :]
        target_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        regime_counts = {
            name: 0
            for name in REGIME_FEATURE_NAMES
        }
        totals = {
            "observed_net_return": 0.0,
            "prediction_error": 0.0,
            "regret": 0.0,
        }
        for outcome in selected:
            target = str(float(outcome["selected_target"]))
            target_counts[target] = target_counts.get(target, 0) + 1
            source = str(outcome["selection_source"])
            source_counts[source] = source_counts.get(source, 0) + 1
            state = cast(Mapping[str, Any], outcome["state"])
            for name in regime_counts:
                regime_counts[name] += int(float(state.get(name, 0.0)) > 0.5)
            observed = cast(Mapping[str, Any], outcome["observed_policy_path"])
            totals["observed_net_return"] += float(observed["net_return"])
            totals["prediction_error"] += float(outcome["prediction_error"] or 0.0)
            totals["regret"] += float(outcome["regret"])
        count = len(selected)
        means = {
            name: total / count
            for name, total in totals.items()
        }
        return {
            "event_id": batch_id,
            "source_revision_ids": ["pending-source"],
            "pre_state": self._record_term(
                {
                    "domain": "trading",
                    "horizon_bars": horizon,
                    "unique_decisions": len(outcomes),
                    "compatibility_sha256": self.config.compatibility_sha256,
                }
            ),
            "action": {
                "kind": "constructor",
                "name": "update-market-mechanism",
                "args": [self._atom(horizon)],
                "type": {"kind": "named", "name": "trading-model-update"},
            },
            "post_state": self._record_term(
                {
                    "batch_summary": {
                        "first_decision_event_id": str(selected[0]["decision_event_id"]),
                        "last_decision_event_id": str(selected[-1]["decision_event_id"]),
                        "target_counts": target_counts,
                        "selection_source_counts": source_counts,
                        "regime_counts": regime_counts,
                        "means": means,
                    }
                }
            ),
            "bindings": {
                "symbol": self._atom(self.config.symbol),
                "horizon": self._atom(horizon),
            },
            "observation": {
                "success": True,
                "provenance": "observed-decisions-plus-no-impact-action-panel",
                "causal_status": "unidentified",
                "unique_decision_count": count,
            },
        }


    def _archive_batch(self, horizon: int, outcomes: Sequence[Mapping[str, Any]], batch_id: str) -> tuple[str, str]:
        detail_episode = self._typed_batch_episode(
            horizon, outcomes, batch_id
        )
        detail_payload = episode_source_payload(detail_episode)
        detail_archive = self.owner.archive_source(
            operation_id=self._operation_id("archive-batch-details", batch_id),
            source=SourceInput(
                source_id=f"trading-batch-details-{batch_id[:24]}",
                content=canonical_json_bytes(detail_payload),
                media_type="application-json",
                codec="utf-8",
                observed_timestamp=str(outcomes[-1]["maturity_timestamp"]),
                scope="trading-learning",
                claim_category="observed-modeled-outcome-batch",
                fidelity="canonical-normalized",
                labels=("trading", "market-experience", "full-detail"),
            ),
            context={"domain": "trading", "horizon": horizon, "batch_id": batch_id},
            epistemic_type="derived",
            event_kind="trading-experience-batch-details",
        )
        detail_source = cast(Mapping[str, Any], detail_archive["source"])
        episode = self._typed_batch_summary_episode(
            horizon, outcomes, batch_id
        )
        summary_payload = episode_source_payload(episode)
        archive = self.owner.archive_source(
            operation_id=self._operation_id("archive-batch-summary", batch_id),
            source=SourceInput(
                source_id=f"trading-batch-summary-{batch_id[:24]}",
                content=canonical_json_bytes(summary_payload),
                media_type="application-json",
                codec="utf-8",
                observed_timestamp=str(outcomes[-1]["maturity_timestamp"]),
                scope="trading-learning",
                claim_category="observed-modeled-outcome-batch-summary",
                fidelity="canonical-normalized",
                labels=("trading", "market-experience", "field-summary"),
            ),
            context={
                "domain": "trading",
                "horizon": horizon,
                "batch_id": batch_id,
                "detail_revision_id": str(detail_source["revision_id"]),
            },
            epistemic_type="derived",
            event_kind="trading-experience-batch-summary",
        )
        source = cast(Mapping[str, Any], archive["source"])
        revision_id = str(source["revision_id"])
        episode["source_revision_ids"] = [revision_id]
        admission_id = self._operation_id("admit-batch-summary", batch_id)
        admitted_task = self._computer_inspect()
        resident_task = admitted_task.get("task")
        indexes = (
            resident_task.get("indexes")
            if isinstance(resident_task, Mapping)
            else None
        )
        events = (
            indexes.get("events")
            if isinstance(indexes, Mapping)
            else None
        )
        if not isinstance(events, Mapping) or batch_id not in events:
            self.owner.admit_open_vocab_episode(
                admission_id,
                revision_id,
                episode,
                batch_id,
                settled=True,
            )
            admitted_task = self._computer_inspect()
            resident_task = admitted_task.get("task")
            indexes = (
                resident_task.get("indexes")
                if isinstance(resident_task, Mapping)
                else None
            )
            events = (
                indexes.get("events")
                if isinstance(indexes, Mapping)
                else None
            )
        if not isinstance(events, Mapping) or batch_id not in events:
            raise RuntimeError("trading experience admission produced no event")
        return revision_id, batch_id

    def _discover_hive_skills(self) -> tuple[Mapping[str, Any], ...]:
        if not self.session.skills.import_enabled:
            return ()
        result: list[Mapping[str, Any]] = []
        for document in self.session.hive.list_bundle_documents(after_generation=0):
            bundle = decode_bundle(document)
            if bundle.status != "promoted" or self.session.hive.is_revoked(bundle.object_id):
                continue
            for learned in bundle.learned_objects:
                if learned.get("kind") != "reasoning-strategy":
                    continue
                skill = learned.get("object")
                if (
                    isinstance(skill, Mapping)
                    and skill.get("schema") == TRADING_SKILL_SCHEMA
                    and skill.get("compatibility_sha256") == self.config.compatibility_sha256
                    and isinstance(skill.get("program"), Mapping)
                    and int(skill.get("horizon", -1)) in self.config.outcome_horizons
                ):
                    normalized_skill = json.loads(canonical_json_bytes(skill))
                    result.append(
                        {"bundle_id": bundle.object_id, "skill": normalized_skill}
                    )
        deduplicated: dict[str, Mapping[str, Any]] = {}
        for row in result:
            key = _digest(cast(Mapping[str, Any], row["skill"])["program"])
            deduplicated[key] = row
        return tuple(sorted(deduplicated.values(), key=lambda row: str(row["bundle_id"])))

    def enable_skill_imports(self) -> Mapping[str, Any]:
        self.session.skills.enable_import(apply_mode="never", sync_mode="on-open")
        self._persist_import_preference(True)
        return self.sync_skills()

    def disable_skill_imports(self) -> Mapping[str, Any]:
        self.session.skills.disable_import()
        self._persist_import_preference(False)
        self._imported_skills = ()
        return self.skill_status()

    def sync_skills(self) -> Mapping[str, Any]:
        sync = self.session.skills.sync()
        self._imported_skills = self._discover_hive_skills()
        return {"sync": sync.as_dict(), **self.skill_status()}

    def skill_status(self) -> Mapping[str, Any]:
        return {
            "import_enabled": self.session.skills.import_enabled,
            "export_enabled": self.session.skills.export_enabled,
            "imported_bundle_ids": [str(row["bundle_id"]) for row in self._imported_skills],
            "exported_capsule_ids": self.session.status()["exported_capsule_ids"],
        }

    def _imported_candidates(self, horizon: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for row in reversed(self._imported_skills):
            skill = cast(Mapping[str, Any], row["skill"])
            if int(skill["horizon"]) != horizon:
                continue
            candidate_id = f"hive-{str(row['bundle_id'])[:12]}"
            program = dict(cast(Mapping[str, Any], skill["program"]))
            declared = skill.get("diagnostics", {})
            declared = dict(declared) if isinstance(declared, Mapping) else {}
            # A hive method proposes; this field still measures it on the same
            # reserved slice as every locally fitted candidate. The contributing
            # field's evidence stays on the record as the method's provenance.
            local = self._reserved_slice_verdict(
                horizon,
                program,
                candidate_id=candidate_id,
                training_rows=int(declared.get("training_rows", 0) or 0),
                training_decisions=int(declared.get("training_decisions", 0) or 0),
            )
            result.append(
                {
                    "candidate_id": candidate_id,
                    "program": program,
                    "parameter_domain": {
                        **(local if local is not None else declared),
                        "source_bundle_id": row["bundle_id"],
                        "source_verification": declared,
                    },
                    "selection_assumptions": [
                        "promoted-hive-proposal",
                        "local-heldout-selection",
                        "noncausal-comparison",
                    ],
                }
            )
            if len(result) >= 5:
                break
        return result

    def _best_adequate_candidate(
        self, candidates: Sequence[Mapping[str, Any]]
    ) -> Mapping[str, Any] | None:
        """The candidate with the smallest reserved-slice loss that proves itself."""
        proven = [
            candidate
            for candidate in candidates
            if bool(
                cast(Mapping[str, Any], candidate.get("parameter_domain", {})).get(
                    "adequate_for_trading", False
                )
            )
        ]
        if not proven:
            return None
        return min(
            proven,
            key=lambda candidate: (
                float(
                    cast(Mapping[str, Any], candidate["parameter_domain"]).get(
                        "relative_objective_loss", math.inf
                    )
                ),
                str(candidate["candidate_id"]),
            ),
        )

    def _adopt_proven_candidate(
        self,
        *,
        horizon: int,
        batch_id: str,
        candidate: Mapping[str, Any],
        episodes: Sequence[Mapping[str, Any]],
        holdout: Sequence[Mapping[str, Any]],
        support_event_id: str,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
        """Retain a candidate that proved itself where the field's own choice did not."""
        result, transition = self._invoke_semantic(
            f"learn-h{horizon}-{batch_id}-proven",
            {
                "operation": "learn-mechanism",
                "operation_id": self._operation_id(
                    "learn-mechanism-proven", batch_id
                ),
                "mechanism_id": self._mechanism_id(horizon),
                "episodes": list(episodes),
                "holdout": list(holdout),
                "candidates": [dict(candidate)],
                "support_roots": [support_event_id],
            },
        )
        if result.get("status") not in {"supported", "representation-insufficient"}:
            return None
        reference = result.get("mechanism")
        if not isinstance(reference, Mapping):
            return None
        model = self._model_from_reference(reference, horizon)
        if model is None or not bool(
            cast(Mapping[str, Any], model["parameter_domain"]).get(
                "adequate_for_trading", False
            )
        ):
            return None
        return model, transition

    def _publish_skill(
        self,
        *,
        horizon: int,
        batch_id: str,
        source_revision_id: str,
        support_event_id: str,
        outcome_ids: Sequence[str],
        model: Mapping[str, Any],
        transition: Mapping[str, Any],
    ) -> str | None:
        if not self.session.skills.export_enabled:
            raise RuntimeError("trading skill export must remain enabled")
        domain = model.get("parameter_domain", {})
        skill = {
            "schema": TRADING_SKILL_SCHEMA,
            "compatibility_sha256": self.config.compatibility_sha256,
            "horizon": horizon,
            "program": model["program"],
            "diagnostics": domain,
            "selected_candidate": model.get("selected_candidate"),
            "source_batch_id": batch_id,
        }
        assessment_id = _digest({"skill": skill, "support": list(outcome_ids)})
        capsule = self.session.publish_experience(
            transition={
                **dict(transition),
                "source": {"revision_id": source_revision_id},
                "event": {"event_id": support_event_id},
            },
            task_id=f"trading-skill-h{horizon}",
            context={"domain": "trading", "symbol": self.config.symbol, "horizon": horizon},
            action={"operation": "learn-semantic-market-mechanism"},
            prediction={"candidate": model.get("selected_candidate")},
            outcome={"status": model["record"]["status"], "skill_sha256": _digest(skill)},
            candidate=ExperienceCandidate(
                kind="reasoning-strategy",
                object=skill,
                operation_plan=(
                    {
                        "operation": "evaluate-trading-semantic-candidate",
                        "compatibility_sha256": self.config.compatibility_sha256,
                        "horizon": horizon,
                    },
                ),
                guards=(
                    {"field": "compatibility_sha256", "equals": self.config.compatibility_sha256},
                ),
                dependencies=(),
            ),
            evidence=ExperienceEvidence(
                support_event_ids=tuple(outcome_ids),
                assessment_ids=(assessment_id,),
                held_out_results=(
                    {
                        "candidate": model.get("selected_candidate"),
                        "diagnostics": domain,
                        "horizon": horizon,
                    },
                ),
                counterexamples=(),
                derivation_roots=(support_event_id,),
            ),
            predecessor_state_sha256=str(transition["predecessor_state_sha256"]),
            transfer_visibility="provenance-only",
        )
        return capsule.object_id

    def _retrain_horizon(self, horizon: int) -> Mapping[str, Any]:
        selected_outcomes = self._select_model_outcomes(horizon)
        if len(selected_outcomes) < 2:
            raise RuntimeError("trading mechanism needs at least two matured decisions")
        decision_count = len(selected_outcomes)
        holdout_count = max(1, min(self.config.semantic_evaluation_decisions, decision_count // 5))
        train_outcomes = selected_outcomes[:-holdout_count]
        holdout_outcomes = selected_outcomes[-holdout_count:]
        train_rows = self._modeled_rows(train_outcomes)
        holdout_rows = self._modeled_rows(holdout_outcomes)
        candidates = self._local_candidates(train_rows, holdout_rows)
        candidates.extend(self._imported_candidates(horizon))
        candidates = candidates[: int(self._semantic_bounds["max_alternatives"])]
        panel_actions = tuple(self.config.semantic_panel_actions) or tuple(
            self.config.action_levels
        )
        panel_limit = min(
            self.config.semantic_panel_decisions,
            max(
                2,
                int(self._semantic_bounds["max_observations"])
                // len(panel_actions),
            ),
        )
        semantic_holdout_count = min(
            len(holdout_outcomes),
            max(1, panel_limit // 2),
        )
        semantic_holdout_outcomes = holdout_outcomes[
            -semantic_holdout_count:
        ]
        semantic_train_capacity = panel_limit - len(
            semantic_holdout_outcomes
        )
        semantic_train_outcomes = train_outcomes[
            -semantic_train_capacity:
        ]
        semantic_train = [
            self._semantic_episode(row)
            for row in self._modeled_rows(semantic_train_outcomes)
            if float(row["action"]["target"]) in panel_actions
        ]
        semantic_holdout = [
            self._semantic_episode(row)
            for row in self._modeled_rows(semantic_holdout_outcomes)
            if float(row["action"]["target"]) in panel_actions
        ]
        batch_id = _digest(
            {
                "horizon": horizon,
                "outcomes": [str(row["decision_event_id"]) for row in selected_outcomes],
                "candidate_programs": [_digest(row["program"]) for row in candidates],
            }
        )
        source_revision_id, support_event_id = self._archive_batch(horizon, selected_outcomes, batch_id)
        semantic_operation_id = self._operation_id("learn-mechanism", batch_id)
        result, transition = self._invoke_semantic(
            f"learn-h{horizon}-{batch_id}",
            {
                "operation": "learn-mechanism",
                "operation_id": semantic_operation_id,
                "mechanism_id": self._mechanism_id(horizon),
                "episodes": semantic_train,
                "holdout": semantic_holdout,
                "candidates": candidates,
                "support_roots": [support_event_id],
                "context_discovery": {
                    "coverage_margin": DISCOVERY_COVERAGE_MARGIN,
                    "min_leaf": DISCOVERY_MIN_LEAF,
                },
            },
        )
        if result.get("status") == "support-gap":
            deferred, replayed = self.ledger.append(
                "model-update-deferred",
                {
                    "horizon": horizon,
                    "outcome_count": len(self._outcomes_by_horizon[horizon]),
                    "reason": "context-support-gap",
                    "learning_result": dict(result),
                },
            )
            if not replayed:
                self._model_deferrals_by_horizon[horizon].append(
                    cast(Mapping[str, Any], deferred["payload"])
                )
            return deferred
        if result.get("status") not in {"supported", "representation-insufficient"}:
            raise RuntimeError(f"trading mechanism learning failed: {result.get('status')}")
        mechanism_reference = result.get("mechanism")
        model = (
            self._model_from_reference(mechanism_reference, horizon)
            if isinstance(mechanism_reference, Mapping)
            else None
        )
        if model is None:
            raise RuntimeError("trading field retained no selected mechanism")
        kernel_candidate = model["selected_candidate"]
        kernel_diagnostics = dict(cast(Mapping[str, Any], model["parameter_domain"]))
        adopted_fallback: str | None = None
        retained = cast(Mapping[str, Any], model["parameter_domain"])
        proven = self._best_adequate_candidate(candidates)
        if not bool(retained.get("adequate_for_trading", False)):
            choice = proven
        else:
            # One slice, one standard: whichever mechanism proved itself best on
            # the reserved slice guides, whether the field fitted it locally or
            # discovery selected it from the semantic panel.
            choice = (
                proven
                if proven is not None
                and float(
                    cast(Mapping[str, Any], proven["parameter_domain"])[
                        "relative_objective_loss"
                    ]
                )
                < float(retained.get("relative_objective_loss", math.inf))
                else None
            )
        if choice is not None:
            adoption = self._adopt_proven_candidate(
                horizon=horizon,
                batch_id=batch_id,
                candidate=choice,
                episodes=semantic_train,
                holdout=semantic_holdout,
                support_event_id=support_event_id,
            )
            if adoption is not None:
                model, transition = adoption
                adopted_fallback = str(choice["candidate_id"])
        outcome_ids = [
            self._outcome_event_ids[
                (str(row["decision_event_id"]), int(row["horizon"]))
            ]
            for row in selected_outcomes
        ]
        capsule_id = self._publish_skill(
            horizon=horizon,
            batch_id=batch_id,
            source_revision_id=source_revision_id,
            support_event_id=support_event_id,
            outcome_ids=outcome_ids,
            model=model,
            transition=transition,
        )
        payload = {
            "horizon": horizon,
            "outcome_count": len(self._outcomes_by_horizon[horizon]),
            "selected_decision_event_ids": [str(row["decision_event_id"]) for row in selected_outcomes],
            "training_decisions": len(train_outcomes),
            "holdout_decisions": len(holdout_outcomes),
            "semantic_training_decisions": len(semantic_train_outcomes),
            "semantic_holdout_decisions": len(semantic_holdout_outcomes),
            "semantic_observation_count": len(semantic_train)
            + len(semantic_holdout),
            "batch_id": batch_id,
            "source_revision_id": source_revision_id,
            "support_event_id": support_event_id,
            "mechanism_reference": model["reference"],
            "selected_candidate": model["selected_candidate"],
            "kernel_selected_candidate": kernel_candidate,
            "kernel_context_selection": (
                result.get("context_selection")
                if isinstance(result.get("context_selection"), Mapping)
                else None
            ),
            "proven_candidate_fallback": adopted_fallback,
            "mechanism_status": model["record"]["status"],
            "diagnostics": model["parameter_domain"],
            "kernel_diagnostics": kernel_diagnostics,
            "candidate_diagnostics": {
                str(candidate["candidate_id"]): candidate[
                    "parameter_domain"
                ]
                for candidate in candidates
            },
            "imported_bundle_ids": [str(row["bundle_id"]) for row in self._imported_skills],
            "exported_skill_capsule_id": capsule_id,
            "field_state_sha256": self.owner.state.state_sha256,
        }
        ledger_row, replayed = self.ledger.append("model-update", payload)
        if not replayed:
            self._model_updates.append(cast(Mapping[str, Any], ledger_row["payload"]))
            self._model_updates_by_horizon[horizon].append(
                cast(Mapping[str, Any], ledger_row["payload"])
            )
        return ledger_row

    def _workspace_capacity(self) -> tuple[int, int, int]:
        capacity = self.owner.inspect().get("capacity", {})
        limits = capacity.get("limits", {}) if isinstance(capacity, Mapping) else {}
        usage = capacity.get("usage", {}) if isinstance(capacity, Mapping) else {}
        limit = int(limits.get("max_workspace_bytes", 0))
        used = int(usage.get("workspace_bytes", 0))
        reserve = max(8 * 1024 * 1024, math.ceil(0.20 * limit))
        return used, limit, reserve
    def _semantic_capacity(self) -> tuple[int, int, int]:
        regions = self._computer_inspect().get("region_capacity")
        task = regions.get("task") if isinstance(regions, Mapping) else None
        if not isinstance(task, Mapping):
            raise RuntimeError("trading semantic region capacity is unavailable")
        used = 4 * int(task["used_words"])
        limit = 4 * int(task["capacity_words"])
        reserve = 4 * math.ceil(0.20 * int(task["capacity_words"]))
        return used, limit, reserve


    def _defer_capacity_update(
        self, horizon: int, *, capacity_error: str | None = None
    ) -> Mapping[str, Any]:
        used, limit, reserve = self._workspace_capacity()
        semantic_used, semantic_limit, semantic_reserve = (
            self._semantic_capacity()
        )
        semantic_exhausted = (
            semantic_limit <= 0
            or semantic_limit - semantic_used < semantic_reserve
        )
        payload = {
            "horizon": horizon,
            "outcome_count": len(self._outcomes_by_horizon[horizon]),
            "reason": (
                "learning-update-capacity"
                if capacity_error is not None
                else "semantic-region-capacity-reserve"
                if semantic_exhausted
                else "workspace-capacity-reserve"
            ),
            "workspace_bytes": used,
            "max_workspace_bytes": limit,
            "required_reserve_bytes": reserve,
            "available_bytes": max(0, limit - used),
            "semantic_task_bytes": semantic_used,
            "semantic_task_capacity_bytes": semantic_limit,
            "semantic_required_reserve_bytes": semantic_reserve,
            "semantic_available_bytes": max(
                0, semantic_limit - semantic_used
            ),
            "capacity_error": capacity_error,
        }
        row, replayed = self.ledger.append("model-update-deferred", payload)
        if not replayed:
            self._model_deferrals_by_horizon[horizon].append(
                cast(Mapping[str, Any], row["payload"])
            )
        return row

    def _capacity_allows_update(self) -> bool:
        used, limit, reserve = self._workspace_capacity()
        semantic_used, semantic_limit, semantic_reserve = (
            self._semantic_capacity()
        )
        return (
            limit > 0
            and limit - used >= reserve
            and semantic_limit > 0
            and semantic_limit - semantic_used >= semantic_reserve
        )

    def _retrain_due_models(self) -> tuple[Mapping[str, Any], ...]:
        rows = []
        for horizon in self.config.outcome_horizons:
            if not self._update_due(horizon):
                continue
            if not self._capacity_allows_update():
                rows.append(self._defer_capacity_update(horizon))
                continue
            try:
                rows.append(self._retrain_horizon(horizon))
            except FieldIntelligenceError as exc:
                if exc.code != "WORK_CAPACITY":
                    raise
                rows.append(
                    self._defer_capacity_update(
                        horizon, capacity_error=str(exc)
                    )
                )
        return tuple(rows)

    def ingest_bar(self, bar: MarketBar | Mapping[str, Any]) -> Mapping[str, Any]:
        if self._closed:
            raise RuntimeError("trading field is closed")
        owned = bar if isinstance(bar, MarketBar) else MarketBar.from_mapping(bar)
        if owned.symbol != self.config.symbol:
            raise ValueError("bar symbol differs from the trading field symbol")
        key = (owned.symbol, owned.timestamp)
        existing = self._bar_rows_by_key.get(key)
        if existing is not None:
            expected = self._bar_payload(
                owned,
                int(cast(Mapping[str, Any], existing["payload"])["bar_index"]),
            )
            if cast(Mapping[str, Any], existing["payload"]) != expected:
                raise ValueError("bar timestamp conflicts with resident evidence")
            return {"status": "replayed", "bar_event_id": existing["event_id"]}
        if self._bars and owned.timestamp <= self._bars[-1].timestamp:
            raise ValueError("new bars must be strictly chronological")
        index = len(self._bars)
        row, replayed = self.ledger.append("bar", self._bar_payload(owned, index))
        if replayed:
            return {"status": "replayed", "bar_event_id": row["event_id"]}
        if self._bars:
            realized = owned.close / self._bars[-1].close - 1.0
            self._account.equity *= 1.0 + self._account.position * realized
            if self._account.equity <= 0.0 or not math.isfinite(self._account.equity):
                raise RuntimeError("market move exhausted account equity")
            self._account.peak = max(self._account.peak, self._account.equity)
            self._risk_peak = max(self._risk_peak, self._account.equity)
        self._bars.append(owned)
        self._bar_event_ids.append(str(row["event_id"]))
        self._bar_rows_by_key[key] = row
        self._equity_before_decision[index] = self._account.equity
        outcomes = self._mature_outcomes(index)
        updates = self._retrain_due_models()
        decision = self._record_decision(index) if self._decision_due(index) else None
        self._equity_after_decision[index] = self._account.equity
        return {
            "status": "admitted",
            "bar_event_id": row["event_id"],
            "decision_event_id": None if decision is None else decision["event_id"],
            "matured_outcome_ids": [item["event_id"] for item in outcomes],
            "model_update_ids": [item["event_id"] for item in updates],
        }

    def run(self, bars: Iterable[MarketBar | Mapping[str, Any]]) -> Mapping[str, Any]:
        admitted = 0
        replayed = 0
        for bar in bars:
            result = self.ingest_bar(bar)
            if result["status"] == "replayed":
                replayed += 1
            else:
                admitted += 1
        return {"admitted_bars": admitted, "replayed_bars": replayed, **self.status()}

    def status(self) -> Mapping[str, Any]:
        models: dict[str, Any] = {}
        for horizon in self.config.outcome_horizons:
            model = self._model_for_horizon(horizon)
            if model is None:
                models[str(horizon)] = None
                continue
            domain = cast(Mapping[str, Any], model["parameter_domain"])
            models[str(horizon)] = {
                "reference": model["reference"],
                "status": model["record"]["status"],
                "selected_candidate": model["selected_candidate"],
                "adequate_for_trading": bool(
                    domain.get("adequate_for_trading", False)
                ),
                "objective_rmse": domain.get("objective_rmse"),
                "baseline_objective_rmse": domain.get(
                    "baseline_objective_rmse"
                ),
                "relative_objective_loss": domain.get(
                    "relative_objective_loss"
                ),
                "training_rows": domain.get("training_rows"),
                "validation_rows": domain.get("validation_rows"),
                "matured_outcomes": len(
                    self._outcomes_by_horizon[horizon]
                ),
                "update_count": len(
                    self._model_updates_by_horizon[horizon]
                ),
            }
        owner_inspection = self.owner.inspect()
        capacity = owner_inspection.get("capacity", {})
        limits = capacity.get("limits", {}) if isinstance(capacity, Mapping) else {}
        usage = capacity.get("usage", {}) if isinstance(capacity, Mapping) else {}
        workspace_limit = int(limits.get("max_workspace_bytes", 0))
        workspace_used = int(usage.get("workspace_bytes", 0))
        workspace_reserve = max(
            8 * 1024 * 1024, math.ceil(0.20 * workspace_limit)
        )
        semantic_used, semantic_limit, semantic_reserve = (
            self._semantic_capacity()
        )
        legacy_names = ("variables", "charts", "programs", "predictions", "plans", "macros")
        legacy_usage = {
            name: int(usage.get(name, 0)) if isinstance(usage, Mapping) else 0
            for name in legacy_names
        }
        return {
            "schema": TRADING_FIELD_SCHEMA,
            "symbol": self.config.symbol,
            "bar_count": len(self._bars),
            "decision_count": len(self._decisions),
            "outcome_count": len(self._outcomes),
            "model_update_count": len(self._model_updates),
            "field_state_sha256": self.owner.state.state_sha256,
            "field_manifest_sha256": self.owner.checkpoints.current_manifest_sha256,
            "ledger_head_sha256": self.ledger.head_sha256,
            "account": {
                "equity": self._account.equity,
                "peak": self._account.peak,
                "drawdown": self._account.drawdown,
                "position": self._account.position,
            },
            "risk": {
                "risk_peak": self._risk_peak,
                "risk_drawdown": self._risk_drawdown(),
                "hard_stop_bar_index": self._hard_stop_index,
                "recovery_reentry_until": self._reentry_until,
            },
            "models": models,
            "learning_capacity": {
                "workspace_bytes": workspace_used,
                "max_workspace_bytes": workspace_limit,
                "required_reserve_bytes": workspace_reserve,
                "available_bytes": max(0, workspace_limit - workspace_used),
                "semantic_task_bytes": semantic_used,
                "semantic_task_capacity_bytes": semantic_limit,
                "semantic_required_reserve_bytes": semantic_reserve,
                "semantic_available_bytes": max(
                    0, semantic_limit - semantic_used
                ),
                "deferred_update_count": sum(
                    len(rows)
                    for rows in self._model_deferrals_by_horizon.values()
                ),
            },
            "skills": self.skill_status(),
            "ownership": {
                "learned_state": "single-owner-operated-cognition-field",
                "ledger_role": "immutable-evidence-only",
                "hive_role": "verified-candidate-exchange",
                "computer_count": len(tuple(self.owner.state.computers)),
                "computer_id": self._computer_id,
                "legacy_adaptive_objects": sum(legacy_usage.values()),
                "legacy_capacity_usage": legacy_usage,
            },
        }


@dataclass(slots=True)
class CanonicalFieldConsumer:
    """Deliver accepted ingestion events exactly once into the trading field."""

    store: Any
    field: TradingField
    symbol: str
    consumer_id: str

    def drain(self, *, max_bars: int = 0) -> Mapping[str, Any]:
        if isinstance(max_bars, bool) or max_bars < 0:
            raise ValueError("max_bars cannot be negative")
        pending = self.store.pending_events(
            self.consumer_id,
            event_type="market-bar",
            subject_id=self.symbol,
        )
        selected = pending if max_bars == 0 else pending[:max_bars]
        admitted = 0
        replayed = 0
        last_source_event_id: str | None = None
        for event in selected:
            result = self.field.ingest_bar(
                MarketBar.from_mapping(cast(Mapping[str, Any], event.payload))
            )
            status = str(result["status"])
            if status == "admitted":
                admitted += 1
            else:
                replayed += 1
            source_payload = {
                "consumer_id": self.consumer_id,
                "canonical_event_id": event.event_id,
                "source_id": event.source_id,
                "source_revision": event.source_revision,
                "observed_at": event.observed_at,
                "available_at": event.available_at,
                "source_payload_sha256": _digest(event.payload),
                "trading_bar_event_id": result["bar_event_id"],
                "trading_disposition": status,
            }
            source_row, _ = self.field.ledger.append(
                "source-delivery", source_payload
            )
            self.store.mark_delivered(
                self.consumer_id,
                event.event_id,
                disposition=f"trading-field-{status}",
                receipt_sha256=str(source_row["content_sha256"]),
            )
            last_source_event_id = str(event.event_id)
        return {
            "schema": "cassi.trading-field-consumer.v1",
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "processed": len(selected),
            "admitted_bars": admitted,
            "replayed_bars": replayed,
            "pending_before": len(pending),
            "pending_after": self.store.pending_count(
                self.consumer_id,
                event_type="market-bar",
                subject_id=self.symbol,
            ),
            "last_source_event_id": last_source_event_id,
            "field": self.field.status(),
        }


class CanonicalFieldPaperConsumer:
    """Paper accepted canonical bars with an append-only causal cutover.

    Version-one receipts remain immutable legacy evidence.  Version-two
    receipts commit account state and the signal/settlement provenance needed
    for an idempotent next-bar-close simulation.
    """

    def __init__(
        self,
        store: Any,
        field: TradingField,
        symbol: str,
        consumer_id: str,
        *,
        paper_config: PaperConfig,
        paper_state_path: Path,
    ) -> None:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("paper consumer symbol must be nonempty text")
        if not isinstance(consumer_id, str) or not consumer_id.strip():
            raise ValueError("paper consumer id must be nonempty text")
        if symbol != field.config.symbol:
            raise ValueError("paper consumer symbol differs from the trading field")
        if not isinstance(paper_config, PaperConfig):
            raise TypeError("paper_config must be a PaperConfig")
        self.store = store
        self.field = field
        self.symbol = symbol
        self.consumer_id = consumer_id
        self.paper_config = paper_config
        self.paper_state_path = Path(paper_state_path)
        self._config_document = paper_config.as_dict()
        for name in (
            "initial_cash",
            "fee_bps",
            "slippage_bps",
            "max_position_fraction",
            "max_turnover",
            "max_drawdown",
            "minimum_order_fraction",
        ):
            self._config_document[name] = float(self._config_document[name])
        self._config_sha256 = _digest(self._config_document)
        self.engine = PaperExecutionEngine(paper_config)
        self.account = PaperAccount.create(float(paper_config.initial_cash))
        self._activation: dict[str, Any] | None = None
        self._bootstrap_event_ids: set[str] = set()
        self._paper_receipts: dict[str, dict[str, Any]] = {}
        self._paper_rows: dict[str, Mapping[str, Any]] = {}
        self._ordered_paper_rows: list[Mapping[str, Any]] = []
        self._source_links_by_event: dict[str, list[Mapping[str, Any]]] = {}
        self._latest_paper_row: Mapping[str, Any] | None = None
        self._latest_receipt: dict[str, Any] | None = None
        self._recovery_state = "fresh"
        self._causal_cutover: dict[str, Any] | None = None
        self._legacy_receipt_count = 0
        self._legacy_fill_count = 0
        self._causal_fill_count = 0
        self._fill_count = 0
        self._latest_legacy_fill: dict[str, Any] | None = None
        self._latest_causal_fill: dict[str, Any] | None = None
        self._latest_fill: dict[str, Any] | None = None
        self._accepted_event_ids_on_open: set[str] | None = None
        self._bootstrap_holes: set[str] = set()
        self._pending_event_buffer: deque[Any] | None = None
        self._pending_event_buffer_complete = False
        self._causal_state: dict[str, Any] = dict(_EMPTY_PAPER_CAUSAL_STATE)
        self._causal_state_event_id: str | None = None
        self._causal_states_by_record_id: dict[str, dict[str, Any]] = {}
        self._causal_cutover_event_id: str | None = None
        self._recovered_receipt_count = 0
        self._outcomes_by_decision: dict[str, list[Mapping[str, Any]]] = {}
        self._outcome_scan_cursor = 0
        self._load_configuration()
        self._load_causal_cutover()
        self._load_activation()
        self._load_paper_receipts()
        self._load_source_links()
        self._validate_delivery_watermark()
        self._recover_snapshot()
        self._refresh_field_outcomes()

    def _consumer_rows(self, kind: str) -> list[Mapping[str, Any]]:
        return [
            row
            for row in self.field.ledger.rows(kind)
            if row["payload"].get("consumer_id") == self.consumer_id
        ]

    def _load_source_links(self) -> None:
        for row in self.field.ledger.rows("source-delivery"):
            payload = row["payload"]
            if payload.get("consumer_id") != self.consumer_id:
                continue
            event_id = payload.get("canonical_event_id")
            if isinstance(event_id, str):
                self._source_links_by_event.setdefault(event_id, []).append(payload)

    def _validate_delivery_watermark(self) -> None:
        if self._activation is None:
            return
        accepted_ids = self._accepted_event_ids_on_open
        if accepted_ids is None:
            raise ValueError("paper activation recovery lacks its accepted-event index")
        pending = list(
            self.store.pending_events(
                self.consumer_id,
                event_type="market-bar",
                subject_id=self.symbol,
            )
        )
        self._pending_event_buffer = deque(pending)
        self._pending_event_buffer_complete = True
        pending_ids = {str(event.event_id) for event in pending}
        known_ids = accepted_ids | self._bootstrap_event_ids
        for event_id in known_ids:
            receipt = self._paper_receipts.get(event_id)
            if receipt is None and event_id not in pending_ids:
                raise ValueError(
                    "paper delivery watermark advanced without a durable paper receipt"
                )
            if receipt is None:
                continue
            event = self.store.event(event_id)
            if event.as_dict() != receipt.get("canonical_event"):
                raise ValueError("paper recovery source event differs from its receipt")
            receipt_row = self._paper_rows[event_id]
            links = self._source_links_by_event.get(event_id, [])
            if event_id not in pending_ids and not links:
                raise ValueError(
                    "delivered paper event is missing its durable source-delivery link"
                )
            for link in links:
                self._validate_source_delivery_link(event, receipt_row, receipt, link)
        for event_id, links in self._source_links_by_event.items():
            receipt = self._paper_receipts.get(event_id)
            if receipt is None:
                raise ValueError("source-delivery link has no durable paper receipt")
            event = self.store.event(event_id)
            receipt_row = self._paper_rows[event_id]
            for link in links:
                self._validate_source_delivery_link(event, receipt_row, receipt, link)

    def _load_configuration(self) -> None:
        rows = self._consumer_rows("paper-consumer-config")
        expected = {
            "schema": PAPER_CONSUMER_CONFIG_SCHEMA,
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "paper_config": self._config_document,
            "paper_config_sha256": self._config_sha256,
            "paper_only": True,
            "external_effect": "none",
        }
        if rows:
            if len(rows) != 1 or dict(rows[0]["payload"]) != expected:
                raise ValueError("paper consumer configuration conflicts with resident evidence")
            return
        if (
            self.paper_state_path.exists()
            or self._consumer_rows("paper-consumer-activation")
            or self._consumer_rows("paper-event")
        ):
            raise ValueError("paper state exists without its resident consumer configuration")
        self.field.ledger.append("paper-consumer-config", expected)

    def _load_activation(self) -> None:
        rows = self._consumer_rows("paper-consumer-activation")
        if not rows:
            return
        if len(rows) != 1:
            raise ValueError("paper consumer has conflicting activation boundaries")
        activation = dict(rows[0]["payload"])
        if (
            activation.get("schema") != PAPER_CONSUMER_ACTIVATION_SCHEMA
            or activation.get("consumer_id") != self.consumer_id
            or activation.get("symbol") != self.symbol
            or activation.get("paper_config_sha256") != self._config_sha256
        ):
            raise ValueError("paper consumer activation record is invalid")
        event_ids = activation.get("bootstrap_event_ids")
        event_hashes = activation.get("bootstrap_event_sha256")
        if (
            not isinstance(event_ids, list)
            or any(not isinstance(event_id, str) or not event_id for event_id in event_ids)
            or len(set(event_ids)) != len(event_ids)
            or not isinstance(event_hashes, Mapping)
            or set(event_hashes) != set(event_ids)
            or any(not isinstance(value, str) or len(value) != 64 for value in event_hashes.values())
        ):
            raise ValueError("paper consumer activation event manifest is invalid")
        boundary_id = event_ids[-1] if event_ids else None
        if activation.get("activation_boundary_event_id") != boundary_id:
            raise ValueError("paper consumer activation boundary does not match its manifest")
        accepted_by_id = {
            str(event.event_id): event
            for event in self.store.accepted_events(
                event_type="market-bar",
                subject_id=self.symbol,
            )
        }

        def resolve_event(event_id: str) -> Any:
            event = accepted_by_id.get(event_id)
            if event is not None:
                return event
            try:
                return self.store.event(event_id)
            except Exception as exc:
                raise ValueError(f"paper bootstrap event is unavailable: {event_id}") from exc

        if boundary_id is not None:
            boundary_event = resolve_event(boundary_id)
            if (
                boundary_event.observed_at != activation.get("activation_boundary_observed_at")
                or _digest(boundary_event.as_dict()) != event_hashes[boundary_id]
            ):
                raise ValueError("paper activation boundary event changed")
        elif activation.get("activation_boundary_observed_at") is not None:
            raise ValueError("empty paper activation manifest has a timestamp")
        for event_id in event_ids:
            event = resolve_event(event_id)
            if _digest(event.as_dict()) != event_hashes[event_id]:
                raise ValueError(f"paper bootstrap event changed: {event_id}")
        self._activation = activation
        self._bootstrap_event_ids = set(event_ids)
        self._accepted_event_ids_on_open = set(accepted_by_id)

    def _load_causal_cutover(self) -> None:
        rows = self._consumer_rows("paper-causal-cutover")
        if not rows:
            return
        if len(rows) != 1:
            raise ValueError("paper consumer has conflicting causal cutover boundaries")
        row = rows[0]
        marker = dict(row["payload"])
        body = dict(marker)
        stated_sha256 = body.pop("content_sha256", None)
        if (
            stated_sha256 != _digest(body)
            or marker.get("schema") != PAPER_CONSUMER_CAUSAL_CUTOVER_SCHEMA
            or marker.get("consumer_id") != self.consumer_id
            or marker.get("symbol") != self.symbol
            or marker.get("paper_config_sha256") != self._config_sha256
            or marker.get("execution_model") != PAPER_EXECUTION_MODEL
            or marker.get("field_internal_model") != PAPER_INTERNAL_MODEL_NOTE
            or not isinstance(marker.get("legacy_receipt_count"), int)
            or isinstance(marker.get("legacy_receipt_count"), bool)
            or marker.get("legacy_receipt_count") < 0
            or not isinstance(marker.get("legacy_receipt_head_sha256"), str)
            or len(marker["legacy_receipt_head_sha256"]) != 64
            or not isinstance(marker.get("legacy_account"), Mapping)
            or marker.get("legacy_account_sha256") != _digest(marker["legacy_account"])
        ):
            raise ValueError("paper causal cutover boundary is invalid")
        PaperAccount.from_dict(cast(Mapping[str, Any], marker["legacy_account"]))
        self._causal_cutover = marker
        self._causal_cutover_event_id = str(row["event_id"])

    def _order_digest(self, order: Mapping[str, Any]) -> str:
        body = dict(order)
        stated = body.pop("order_sha256", None)
        if stated != _digest(body):
            raise ValueError("paper pending order digest mismatch")
        return str(stated)

    def _validate_pending_order(
        self,
        order: Any,
        *,
        event_id: str | None = None,
        decision_id: str | None = None,
        decision: Mapping[str, Any] | None = None,
        event_doc: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(order, Mapping):
            raise ValueError("paper causal state contains an invalid pending order")
        normalized = dict(order)
        self._order_digest(normalized)
        try:
            signal_observed = _paper_timestamp(str(normalized["signal_observed_at"]))
            expected = _paper_timestamp(str(normalized["expected_execution_observed_at"]))
            created = _paper_timestamp(str(normalized["signal_created_at"]))
            available = _paper_timestamp(str(normalized["signal_available_at"]))
            timeframe = normalized["timeframe_seconds"]
            target = _finite(normalized["target_exposure"], "pending order target")
            signal_reference_price = _finite(
                normalized["signal_reference_price"], "signal reference price"
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("paper pending order fields are invalid") from exc
        if (
            normalized.get("schema") != "cassi.trading-field-paper-pending-order.v1"
            or normalized.get("consumer_id") != self.consumer_id
            or normalized.get("symbol") != self.symbol
            or not isinstance(timeframe, int)
            or isinstance(timeframe, bool)
            or timeframe != self.paper_config.timeframe_seconds
            or expected != signal_observed + timedelta(seconds=timeframe)
            or created < available
            or target < -1.0e-12
            or target > self.paper_config.max_position_fraction + 1.0e-12
            or signal_reference_price <= 0.0
            or normalized.get("desired_target") != target
            or normalized.get("source_decision_event_id")
            != normalized.get("field_decision_event_id")
            or normalized.get("max_wait_bars") != 1
            or not isinstance(normalized.get("signal_health"), Mapping)
            or not isinstance(normalized.get("signal_source_id"), str)
            or not normalized.get("signal_source_id")
            or not isinstance(normalized.get("signal_source_revision"), str)
            or not normalized.get("signal_source_revision")
            or not isinstance(normalized.get("trading_bar_event_id"), str)
            or not normalized.get("trading_bar_event_id")
            or not isinstance(normalized.get("field_decision_event_id"), str)
            or not isinstance(normalized.get("field_decision_sha256"), str)
            or len(normalized["field_decision_sha256"]) != 64
        ):
            raise ValueError("paper pending order timing or identity is invalid")
        if event_id is not None and (
            normalized.get("signal_event_id") != event_id
            or normalized.get("field_decision_event_id") != decision_id
            or decision is None
            or normalized.get("field_decision_sha256") != _digest(decision)
            or event_doc is None
            or normalized.get("signal_canonical_event_sha256") != _digest(event_doc)
            or normalized.get("signal_source_payload_sha256")
            != _digest(event_doc.get("payload"))
            or normalized.get("signal_source_id") != event_doc.get("source_id")
            or normalized.get("signal_source_revision") != event_doc.get("source_revision")
            or normalized.get("signal_observed_at") != event_doc.get("observed_at")
            or normalized.get("signal_available_at") != event_doc.get("available_at")
            or not isinstance(event_doc.get("payload"), Mapping)
            or signal_reference_price != event_doc["payload"].get("close")
        ):
            raise ValueError("paper pending order does not match its decision or source event")
        return normalized

    def _load_paper_receipts(self) -> None:
        receipt_rows = self._consumer_rows("paper-event")
        if receipt_rows and self._activation is None:
            raise ValueError("paper receipts exist without a frozen activation boundary")
        ledger_rows = self.field.ledger.rows()
        consumer_rows = [
            row
            for row in ledger_rows
            if row["payload"].get("consumer_id") == self.consumer_id
            and row.get("kind") in ("paper-event", "paper-pending-cancellation")
        ]
        cutover_row = (
            None
            if self._causal_cutover_event_id is None
            else self.field.ledger.get(self._causal_cutover_event_id)
        )
        if self._causal_cutover_event_id is not None and (
            cutover_row is None or cutover_row.get("kind") != "paper-causal-cutover"
        ):
            raise ValueError("paper causal cutover ledger link is missing")
        cutover_sequence = 0 if cutover_row is None else int(cutover_row["sequence"])
        previous_receipt_sha256 = _EMPTY_PAPER_RECEIPT_SHA256
        previous_timestamp: str | None = None
        causal_state = dict(_EMPTY_PAPER_CAUSAL_STATE)
        receipt_sequence = 0
        legacy_rows: list[Mapping[str, Any]] = []
        for row in consumer_rows:
            row_kind = row["kind"]
            payload = dict(row["payload"])
            if row_kind == "paper-pending-cancellation":
                body = dict(payload)
                stated = body.pop("content_sha256", None)
                current_order = causal_state.get("pending_order")
                latest_receipt_row = (
                    None if not self._ordered_paper_rows else self._ordered_paper_rows[-1]
                )
                if (
                    self._causal_cutover is None
                    or int(row["sequence"]) <= cutover_sequence
                    or stated != _digest(body)
                    or payload.get("schema") != PAPER_CONSUMER_CANCELLATION_SCHEMA
                    or payload.get("consumer_id") != self.consumer_id
                    or payload.get("symbol") != self.symbol
                    or current_order is None
                    or payload.get("previous_causal_state_sha256") != _digest(causal_state)
                    or payload.get("pending_order") != current_order
                    or payload.get("pending_order_sha256") != current_order.get("order_sha256")
                    or not isinstance(payload.get("reason"), str)
                    or not payload["reason"]
                    or len(payload["reason"]) > 256
                    or latest_receipt_row is None
                    or payload.get("paper_receipt_event_id") != latest_receipt_row["event_id"]
                    or payload.get("paper_receipt_sha256")
                    != latest_receipt_row["payload"].get("content_sha256")
                ):
                    raise ValueError("paper pending cancellation conflicts with causal state")
                _paper_timestamp(str(payload.get("cancelled_at", "")))
                expiry = {
                    "kind": "cancelled",
                    "reason": payload["reason"],
                    "cancelled_at": payload.get("cancelled_at"),
                    "pending_order": current_order,
                }
                next_state = {
                    "pending_order": None,
                    "last_execution": causal_state.get("last_execution"),
                    "last_expiry": expiry,
                }
                if (
                    payload.get("causal_state") != next_state
                    or payload.get("causal_state_sha256") != _digest(next_state)
                ):
                    raise ValueError("paper pending cancellation state digest mismatch")
                causal_state = next_state
                self._causal_state_event_id = str(row["event_id"])
                self._causal_states_by_record_id[str(row["event_id"])] = dict(causal_state)
                continue

            receipt_sequence += 1
            receipt = payload
            body = dict(receipt)
            stated_sha256 = body.pop("content_sha256", None)
            if stated_sha256 != _digest(body):
                raise ValueError("paper event receipt digest mismatch")
            schema = receipt.get("schema")
            legacy = schema == PAPER_CONSUMER_EVENT_SCHEMA
            causal = schema == PAPER_CONSUMER_CAUSAL_EVENT_SCHEMA
            if (
                not (legacy or causal)
                or receipt.get("consumer_id") != self.consumer_id
                or receipt.get("symbol") != self.symbol
                or receipt.get("paper_config_sha256") != self._config_sha256
                or receipt.get("paper_only") is not True
                or receipt.get("external_effect") != "none"
                or receipt.get("receipt_sequence") != receipt_sequence
                or receipt.get("previous_receipt_sha256") != previous_receipt_sha256
            ):
                raise ValueError("paper event receipt identity or chain mismatch")
            if causal and (
                self._causal_cutover is None
                or int(row["sequence"]) <= cutover_sequence
                or receipt.get("causal_cutover_event_id") != self._causal_cutover_event_id
                or receipt.get("execution_model") != PAPER_EXECUTION_MODEL
                or receipt.get("signal_to_fill_lag_bars") != 1
                or receipt.get("field_internal_model") != PAPER_INTERNAL_MODEL_NOTE
                or receipt.get("causal_state_before_sha256") != _digest(causal_state)
            ):
                raise ValueError("paper causal receipt lacks its cutover or prior-state link")
            if legacy and self._causal_cutover is not None and int(row["sequence"]) > cutover_sequence:
                raise ValueError("legacy paper receipt appears after the causal cutover")
            event_doc = receipt.get("canonical_event")
            if not isinstance(event_doc, Mapping):
                raise ValueError("paper event receipt lacks its canonical source event")
            event_id = str(receipt.get("canonical_event_id", ""))
            if (
                event_doc.get("event_id") != event_id
                or event_doc.get("event_type") != "market-bar"
                or event_doc.get("subject_ids") != [self.symbol]
                or _digest(event_doc) != receipt.get("canonical_event_sha256")
                or _digest(event_doc.get("payload")) != receipt.get("source_payload_sha256")
            ):
                raise ValueError("paper receipt canonical source evidence is inconsistent")
            if previous_timestamp is not None and str(event_doc["observed_at"]) <= previous_timestamp:
                raise ValueError("paper receipt events are not strictly chronological")
            decision = receipt.get("field_decision")
            decision_id = receipt.get("field_decision_event_id")
            if decision is None:
                if decision_id is not None or receipt.get("field_decision_sha256") is not None:
                    raise ValueError("paper receipt has an orphan field decision identity")
            elif (
                not isinstance(decision, Mapping)
                or decision_id is None
                or _digest(decision) != receipt.get("field_decision_sha256")
                or decision.get("bar_event_id") != receipt.get("trading_bar_event_id")
            ):
                raise ValueError("paper receipt field decision evidence is inconsistent")
            if event_id in self._paper_receipts:
                raise ValueError("paper ledger repeats a canonical event receipt")
            account = PaperAccount.from_dict(cast(Mapping[str, Any], receipt["account"]))
            if (
                account.last_timestamp is None
                or _paper_timestamp(account.last_timestamp) != _paper_timestamp(str(event_doc["observed_at"]))
                or any(float(units) < -1.0e-12 for units in account.positions.values())
                or set(account.positions) - {self.symbol}
            ):
                raise ValueError("paper receipt account violates its symbol or long-only boundary")
            if event_id in self._bootstrap_event_ids:
                if receipt.get("disposition") != "bootstrap-warmup" or receipt.get("fill") is not None:
                    raise ValueError("bootstrap event was reinterpreted as paper-fill eligible")
            elif receipt.get("disposition") == "bootstrap-warmup":
                raise ValueError("non-bootstrap event was recorded as historical warmup")
            if causal:
                settlement = receipt.get("settlement")
                expiry = receipt.get("order_expiry")
                if settlement is not None and expiry is not None:
                    raise ValueError("paper receipt both settles and expires one pending order")
                previous_order = causal_state.get("pending_order")
                expected_state = dict(causal_state)
                if settlement is not None:
                    if (
                        previous_order is None
                        or not isinstance(settlement, Mapping)
                        or settlement.get("schema") != "cassi.trading-field-paper-settlement.v1"
                        or settlement.get("pending_order") != previous_order
                        or settlement.get("signal_event_id") != previous_order.get("signal_event_id")
                        or settlement.get("field_decision_event_id")
                        != previous_order.get("field_decision_event_id")
                        or settlement.get("execution_event_id") != event_id
                        or settlement.get("execution_source_id") != event_doc.get("source_id")
                        or settlement.get("execution_source_revision")
                        != event_doc.get("source_revision")
                        or settlement.get("execution_observed_at") != event_doc.get("observed_at")
                        or settlement.get("execution_available_at") != event_doc.get("available_at")
                        or settlement.get("execution_source_payload_sha256")
                        != receipt["source_payload_sha256"]
                        or settlement.get("execution_canonical_event_sha256")
                        != receipt["canonical_event_sha256"]
                        or settlement.get("fill") != receipt.get("fill")
                        or settlement.get("settlement_health") != receipt.get("data_health")
                        or settlement.get("signal_health") != previous_order.get("signal_health")
                        or settlement.get("status") not in (
                            "filled",
                            "settled-no-fill",
                            "blocked-health-increase",
                        )
                    ):
                        raise ValueError("paper settlement does not link the earlier pending order")
                    signal_available = _paper_timestamp(str(previous_order["signal_available_at"]))
                    signal_created = _paper_timestamp(str(previous_order["signal_created_at"]))
                    execution_available = _paper_timestamp(str(event_doc["available_at"]))
                    expected_execution = _paper_timestamp(
                        str(previous_order["expected_execution_observed_at"])
                    )
                    if (
                        execution_available <= signal_created
                        or _paper_timestamp(str(event_doc["observed_at"])) != expected_execution
                        or signal_available > signal_created
                    ):
                        raise ValueError("paper settlement is not a later contiguous available bar")
                    settlement_fill = settlement.get("fill")
                    if settlement.get("status") == "filled":
                        if (
                            not isinstance(settlement_fill, Mapping)
                            or settlement_fill.get("event_id") != event_id
                            or _paper_timestamp(str(settlement_fill.get("timestamp")))
                            != _paper_timestamp(str(event_doc.get("observed_at")))
                            or settlement.get("price") != settlement_fill.get("price")
                            or settlement.get("execution_price") != settlement_fill.get("price")
                        ):
                            raise ValueError("paper fill does not use its later execution bar close")
                    elif settlement_fill is not None or receipt.get("fill") is not None:
                        raise ValueError("non-fill settlement contains a paper fill")
                    expected_state["pending_order"] = None
                    expected_state["last_execution"] = dict(settlement)
                elif expiry is not None:
                    if (
                        previous_order is None
                        or not isinstance(expiry, Mapping)
                        or expiry.get("kind") != "expired"
                        or expiry.get("pending_order") != previous_order
                        or expiry.get("event_id") != event_id
                        or expiry.get("source_id") != event_doc.get("source_id")
                        or expiry.get("source_revision") != event_doc.get("source_revision")
                        or expiry.get("observed_at") != event_doc.get("observed_at")
                        or expiry.get("available_at") != event_doc.get("available_at")
                        or expiry.get("source_payload_sha256") != receipt["source_payload_sha256"]
                        or expiry.get("canonical_event_sha256") != receipt["canonical_event_sha256"]
                        or receipt.get("fill") is not None
                    ):
                        raise ValueError("paper order expiry does not link the pending signal")
                    expected_time = _paper_timestamp(
                        str(previous_order["expected_execution_observed_at"])
                    )
                    signal_created = _paper_timestamp(str(previous_order["signal_created_at"]))
                    current_time = _paper_timestamp(str(event_doc["observed_at"]))
                    reason = (
                        "timeframe-gap"
                        if current_time > expected_time
                        else "noncontiguous-timeframe"
                    )
                    if current_time == expected_time:
                        reason = "source-already-available-at-signal"
                        if _paper_timestamp(str(event_doc["available_at"])) > signal_created:
                            raise ValueError("paper source-availability expiry was not causal")
                    elif expiry.get("reason") != reason:
                        raise ValueError("paper order expired for an incorrect timeframe reason")
                    if expiry.get("reason") != reason:
                        raise ValueError("paper order expiry reason is inconsistent")
                    expected_state["pending_order"] = None
                    expected_state["last_expiry"] = dict(expiry)
                pending_order = receipt.get("pending_order")
                if pending_order is not None:
                    pending_order = self._validate_pending_order(
                        pending_order,
                        event_id=event_id,
                        decision_id=None if decision_id is None else str(decision_id),
                        decision=decision if isinstance(decision, Mapping) else None,
                        event_doc=event_doc,
                    )
                expected_state["pending_order"] = pending_order
                if (
                    receipt.get("causal_state") != expected_state
                    or receipt.get("causal_state_sha256") != _digest(expected_state)
                    or receipt.get("last_execution") != expected_state["last_execution"]
                    or receipt.get("last_expiry") != expected_state["last_expiry"]
                ):
                    raise ValueError("paper receipt causal state transition is inconsistent")
                causal_state = expected_state
                self._causal_state_event_id = str(row["event_id"])
                self._causal_states_by_record_id[str(row["event_id"])] = dict(causal_state)
            else:
                legacy_rows.append(row)
            raw_fill = receipt.get("fill")
            if raw_fill is not None:
                execution_model = (
                    PAPER_EXECUTION_MODEL
                    if causal
                    else "legacy-same-bar-v1"
                )
                fill = dict(raw_fill)
                fill.setdefault("execution_model", execution_model)
                self._fill_count += 1
                self._latest_fill = fill
                if causal:
                    self._causal_fill_count += 1
                    self._latest_causal_fill = fill
                else:
                    self._legacy_fill_count += 1
                    self._latest_legacy_fill = fill
            previous_receipt_sha256 = str(stated_sha256)
            previous_timestamp = str(event_doc["observed_at"])
            self._paper_receipts[event_id] = receipt
            self._paper_rows[event_id] = row
            self._ordered_paper_rows.append(row)
        if self._causal_cutover is not None:
            legacy_before_cutover = [
                row for row in legacy_rows if int(row["sequence"]) < cutover_sequence
            ]
            if (
                len(legacy_before_cutover) != self._causal_cutover["legacy_receipt_count"]
                or (
                    _EMPTY_PAPER_RECEIPT_SHA256
                    if not legacy_before_cutover
                    else legacy_before_cutover[-1]["payload"]["content_sha256"]
                )
                != self._causal_cutover["legacy_receipt_head_sha256"]
                or any(int(row["sequence"]) > cutover_sequence for row in legacy_rows)
            ):
                raise ValueError("paper causal cutover does not preserve the legacy receipt prefix")
            expected_legacy_account = (
                PaperAccount.create(float(self.paper_config.initial_cash)).as_dict()
                if not legacy_before_cutover
                else legacy_before_cutover[-1]["payload"]["account"]
            )
            if self._causal_cutover["legacy_account"] != expected_legacy_account:
                raise ValueError("paper causal cutover account baseline differs from legacy evidence")
        if self._ordered_paper_rows:
            self._latest_paper_row = self._ordered_paper_rows[-1]
            self._latest_receipt = dict(self._latest_paper_row["payload"])
            self.account = PaperAccount.from_dict(
                cast(Mapping[str, Any], self._latest_receipt["account"])
            )
        self._causal_state = causal_state
        self._legacy_receipt_count = len(legacy_rows)
        self._bootstrap_holes = self._bootstrap_event_ids - self._paper_receipts.keys()

    def _snapshot_body(self) -> dict[str, Any]:
        if self._activation is None or self._latest_paper_row is None or self._latest_receipt is None:
            raise ValueError("paper state cannot be snapshotted before a durable paper receipt")
        body: dict[str, Any] = {
            "schema": PAPER_CONSUMER_STATE_SCHEMA,
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "paper_config": self._config_document,
            "paper_config_sha256": self._config_sha256,
            "activation": self._activation,
            "account": self.account.as_dict(),
            "last_event_id": self._latest_receipt["canonical_event_id"],
            "last_receipt_event_id": self._latest_paper_row["event_id"],
            "last_receipt_sha256": self._latest_receipt["content_sha256"],
            "paper_only": True,
            "external_effect": "none",
            "causal_state": dict(self._causal_state),
            "causal_state_sha256": _digest(self._causal_state),
            "causal_state_event_id": self._causal_state_event_id,
            "causal_cutover_event_id": self._causal_cutover_event_id,
        }
        body["content_sha256"] = _digest(body)
        return body

    def _write_snapshot(self) -> None:
        document = self._snapshot_body()
        path = self.paper_state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ) + "\n"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=path.parent, delete=False
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _recover_snapshot(self) -> None:
        if not self.paper_state_path.exists():
            if not self._ordered_paper_rows:
                self._recovery_state = "no-paper-state-yet"
                return
            self._recovery_state = "snapshot-restored-from-ledger"
            self._recovered_receipt_count = len(self._ordered_paper_rows)
            self._write_snapshot()
            return
        try:
            snapshot = json.loads(self.paper_state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("paper state snapshot is unreadable") from exc
        if not isinstance(snapshot, Mapping):
            raise ValueError("paper state snapshot is not an object")
        body = dict(snapshot)
        stated_sha256 = body.pop("content_sha256", None)
        if stated_sha256 != _digest(body):
            raise ValueError("paper state snapshot digest mismatch")
        if (
            snapshot.get("schema") not in (
                PAPER_CONSUMER_STATE_SCHEMA,
                PAPER_CONSUMER_LEGACY_STATE_SCHEMA,
            )
            or snapshot.get("consumer_id") != self.consumer_id
            or snapshot.get("symbol") != self.symbol
            or snapshot.get("paper_config") != self._config_document
            or snapshot.get("paper_config_sha256") != self._config_sha256
            or snapshot.get("paper_only") is not True
            or snapshot.get("external_effect") != "none"
            or self._activation is None
            or snapshot.get("activation") != self._activation
            or not self._ordered_paper_rows
        ):
            raise ValueError("paper state snapshot identity does not match resident evidence")
        account = PaperAccount.from_dict(cast(Mapping[str, Any], snapshot["account"]))
        snapshot_row_index = next(
            (
                index
                for index, row in enumerate(self._ordered_paper_rows)
                if row["event_id"] == snapshot.get("last_receipt_event_id")
            ),
            -1,
        )
        if snapshot_row_index < 0:
            raise ValueError("paper snapshot points beyond the durable receipt ledger")
        snapshot_receipt = cast(
            Mapping[str, Any], self._ordered_paper_rows[snapshot_row_index]["payload"]
        )
        if (
            snapshot.get("last_event_id") != snapshot_receipt.get("canonical_event_id")
            or snapshot.get("last_receipt_sha256") != snapshot_receipt.get("content_sha256")
            or account.as_dict() != snapshot_receipt.get("account")
        ):
            raise ValueError("paper snapshot account does not match its durable receipt")
        snapshot_causal_state = snapshot.get(
            "causal_state", dict(_EMPTY_PAPER_CAUSAL_STATE)
        )
        snapshot_causal_pointer = snapshot.get("causal_state_event_id")
        if (
            not isinstance(snapshot_causal_state, Mapping)
            or snapshot.get("causal_state_sha256", _digest(snapshot_causal_state))
            != _digest(snapshot_causal_state)
            or snapshot.get("causal_cutover_event_id")
            not in (None, self._causal_cutover_event_id)
        ):
            raise ValueError("paper snapshot causal state digest or cutover link is invalid")
        expected_snapshot_causal = (
            dict(_EMPTY_PAPER_CAUSAL_STATE)
            if snapshot_causal_pointer is None
            else self._causal_states_by_record_id.get(str(snapshot_causal_pointer))
        )
        if (
            expected_snapshot_causal is None
            or dict(snapshot_causal_state) != expected_snapshot_causal
        ):
            raise ValueError("paper snapshot causal state does not match its durable record")
        receipts_advanced = snapshot_row_index < len(self._ordered_paper_rows) - 1
        causal_advanced = (
            snapshot_causal_pointer != self._causal_state_event_id
            or dict(snapshot_causal_state) != self._causal_state
        )
        if (
            receipts_advanced
            or causal_advanced
            or snapshot.get("schema") == PAPER_CONSUMER_LEGACY_STATE_SCHEMA
        ):
            self._recovery_state = (
                "causal-state-advanced-from-ledger"
                if causal_advanced
                else "snapshot-advanced-from-ledger"
            )
            self._recovered_receipt_count = (
                len(self._ordered_paper_rows) - snapshot_row_index - 1
            ) + int(causal_advanced)
            self.account = PaperAccount.from_dict(
                cast(Mapping[str, Any], self._latest_receipt["account"])
            )
            self._write_snapshot()
        else:
            self.account = account
            self._recovery_state = "snapshot-matched-ledger"

    def _ensure_activation(self) -> None:
        if self._activation is not None:
            return
        if self._ordered_paper_rows or self.paper_state_path.exists():
            raise ValueError("paper state lacks its immutable activation boundary")
        events = self.store.accepted_events(
            event_type="market-bar",
            subject_id=self.symbol,
        )
        event_ids = [str(event.event_id) for event in events]
        event_hashes = {
            str(event.event_id): _digest(event.as_dict())
            for event in events
        }
        boundary = events[-1] if events else None
        activation = {
            "schema": PAPER_CONSUMER_ACTIVATION_SCHEMA,
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "paper_config_sha256": self._config_sha256,
            "activation_boundary_event_id": None if boundary is None else boundary.event_id,
            "activation_boundary_observed_at": None if boundary is None else boundary.observed_at,
            "bootstrap_event_ids": event_ids,
            "bootstrap_event_sha256": event_hashes,
        }
        row, replayed = self.field.ledger.append("paper-consumer-activation", activation)
        if dict(row["payload"]) != activation:
            raise ValueError("paper activation boundary conflicts with resident evidence")
        self._activation = dict(row["payload"])
        self._bootstrap_event_ids = set(event_ids)
        self._accepted_event_ids_on_open = set(event_ids)
        self._bootstrap_holes = set(event_ids) - self._paper_receipts.keys()
        pending = list(
            self.store.pending_events(
                self.consumer_id,
                event_type="market-bar",
                subject_id=self.symbol,
            )
        )
        pending_ids = {str(event.event_id) for event in pending}
        if any(event_id not in pending_ids for event_id in self._bootstrap_holes):
            raise ValueError(
                "paper activation found an advanced delivery watermark without a receipt"
            )
        self._pending_event_buffer = deque(pending)
        self._pending_event_buffer_complete = True
        if replayed:
            raise ValueError("paper activation record appeared concurrently")

    def _ensure_causal_cutover(self) -> None:
        if self._causal_cutover is not None:
            return
        if self._activation is None:
            raise ValueError("paper causal cutover requires a fixed activation boundary")
        legacy_rows = [
            row
            for row in self._ordered_paper_rows
            if row["payload"].get("schema") == PAPER_CONSUMER_EVENT_SCHEMA
        ]
        if any(
            row["payload"].get("schema") == PAPER_CONSUMER_CAUSAL_EVENT_SCHEMA
            for row in self._ordered_paper_rows
        ):
            raise ValueError("causal paper receipts exist without their cutover boundary")
        legacy_account = (
            PaperAccount.create(float(self.paper_config.initial_cash)).as_dict()
            if not legacy_rows
            else dict(legacy_rows[-1]["payload"]["account"])
        )
        body: dict[str, Any] = {
            "schema": PAPER_CONSUMER_CAUSAL_CUTOVER_SCHEMA,
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "paper_config_sha256": self._config_sha256,
            "execution_model": PAPER_EXECUTION_MODEL,
            "field_internal_model": PAPER_INTERNAL_MODEL_NOTE,
            "legacy_receipt_count": len(legacy_rows),
            "legacy_receipt_head_sha256": (
                _EMPTY_PAPER_RECEIPT_SHA256
                if not legacy_rows
                else str(legacy_rows[-1]["payload"]["content_sha256"])
            ),
            "legacy_account": legacy_account,
            "legacy_account_sha256": _digest(legacy_account),
            "cutover_created_at": _paper_now(),
        }
        body["content_sha256"] = _digest(body)
        row, replayed = self.field.ledger.append("paper-causal-cutover", body)
        if dict(row["payload"]) != body:
            raise ValueError("paper causal cutover conflicts with resident evidence")
        self._causal_cutover = dict(body)
        self._causal_cutover_event_id = str(row["event_id"])
        if replayed:
            raise ValueError("paper causal cutover appeared concurrently")

    def _field_decision_for_bar(
        self, bar_event_id: str
    ) -> tuple[str | None, Mapping[str, Any] | None]:
        bar_row = self.field.ledger.get(bar_event_id)
        if bar_row is None or bar_row.get("kind") != "bar":
            raise ValueError("resident trading bar evidence is missing")
        index = int(cast(Mapping[str, Any], bar_row["payload"])["bar_index"])
        entry = self.field._decision_rows_by_index.get(index)
        if entry is None:
            if self.field._decision_due(index):
                raise ValueError("resident field decision due for the bar is missing")
            return None, None
        decision_id, decision = entry
        if (
            decision.get("bar_index") != index
            or decision.get("bar_event_id") != bar_event_id
            or decision.get("timestamp") != bar_row["payload"]["bar"]["timestamp"]
            or decision.get("symbol") != self.symbol
        ):
            raise ValueError("resident field decision does not belong to the canonical bar")
        return str(decision_id), decision

    def _mark_account(self, bar: MarketBar) -> None:
        self.account.mark(bar)
        if self.account.equity <= self.account.peak_equity * (
            1.0 - self.paper_config.max_drawdown
        ):
            self.account.frozen = True

    def _prepare_target(
        self,
        bar: MarketBar,
        requested_value: float,
        health: Mapping[str, Any],
    ) -> dict[str, Any]:
        requested = _finite(requested_value, "field target")
        current = self.account.exposure_fraction(self.symbol, bar.close)
        maximum = self.paper_config.max_position_fraction
        adjustments: list[dict[str, Any]] = []
        target = requested
        if target < 0.0:
            adjustments.append(
                {"rule": "long-only-negative-target-clipped", "from": target, "to": 0.0}
            )
            target = 0.0
        sized = min(maximum, max(0.0, target))
        if not math.isclose(sized, target, rel_tol=0.0, abs_tol=1.0e-12):
            adjustments.append({"rule": "maximum-position-fraction", "from": target, "to": sized})
        target = sized
        health_can_open = (
            health.get("state") == "GREEN"
            and health.get("can_open_exposure") is True
        )
        if not health_can_open and target > current + 1.0e-12:
            adjustments.append(
                {"rule": "unhealthy-feed-blocks-increase", "from": target, "to": current}
            )
            target = current
        turnover_low = max(0.0, current - self.paper_config.max_turnover)
        turnover_high = min(maximum, current + self.paper_config.max_turnover)
        turnover_target = min(turnover_high, max(turnover_low, target))
        if not math.isclose(turnover_target, target, rel_tol=0.0, abs_tol=1.0e-12):
            adjustments.append(
                {"rule": "maximum-turnover", "from": target, "to": turnover_target}
            )
        target = turnover_target
        frozen = self.account.frozen
        if frozen and target > current + 1.0e-12:
            adjustments.append(
                {"rule": "drawdown-freeze-blocks-increase", "from": target, "to": current}
            )
            target = current
        return {
            "requested_target": requested,
            "size_limited_target": sized,
            "applied_target": target,
            "resulting_exposure": current,
            "current_exposure": current,
            "health_allows_increase": health_can_open,
            "account_frozen": frozen,
            "maximum_position_fraction": maximum,
            "maximum_turnover": self.paper_config.max_turnover,
            "adjustments": adjustments,
        }

    def _apply_order_target(
        self,
        bar: MarketBar,
        target: float,
        health: Mapping[str, Any],
        *,
        operation_id: str,
        canonical_event_id: str,
        signal_health: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        application = self._prepare_target(bar, target, health)
        current = float(application["current_exposure"])
        applied = float(application["applied_target"])
        if applied > current + 1.0e-12 and signal_health is not None and not (
            signal_health.get("state") == "GREEN"
            and signal_health.get("can_open_exposure") is True
        ):
            application["adjustments"].append(
                {"rule": "signal-health-blocks-increase", "from": applied, "to": current}
            )
            applied = current
            application["applied_target"] = applied
        frozen = self.account.frozen
        fill = None
        if not math.isclose(applied, current, rel_tol=0.0, abs_tol=1.0e-12):
            thaw_for_reduction = frozen and 0.0 < applied < current - 1.0e-12
            if thaw_for_reduction:
                self.account.frozen = False
            try:
                fill = self.engine.execute_target(
                    self.account,
                    bar,
                    target_exposure=applied,
                    operation_id=operation_id,
                    event_id=canonical_event_id,
                )
            finally:
                if frozen:
                    self.account.frozen = True
        application["resulting_exposure"] = self.account.exposure_fraction(
            self.symbol, bar.close
        )
        return application, None if fill is None else fill.as_dict()

    def _make_pending_order(
        self,
        event: Any,
        bar: MarketBar,
        *,
        trading_bar_event_id: str,
        decision_id: str,
        decision: Mapping[str, Any],
        application: Mapping[str, Any],
        health: Mapping[str, Any],
        signal_created_at: str,
    ) -> dict[str, Any] | None:
        current = float(application["current_exposure"])
        target = float(application["applied_target"])
        if abs(target - current) < self.paper_config.minimum_order_fraction:
            return None
        event_document = event.as_dict()
        expected_time = _paper_timestamp(bar.timestamp) + timedelta(
            seconds=self.paper_config.timeframe_seconds
        )
        body: dict[str, Any] = {
            "schema": "cassi.trading-field-paper-pending-order.v1",
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "source_decision_event_id": decision_id,
            "field_decision_event_id": decision_id,
            "field_decision_sha256": _digest(decision),
            "trading_bar_event_id": trading_bar_event_id,
            "signal_event_id": str(event.event_id),
            "signal_source_id": str(event.source_id),
            "signal_source_revision": str(event.source_revision),
            "signal_observed_at": str(event.observed_at),
            "signal_available_at": str(event.available_at),
            "signal_created_at": signal_created_at,
            "signal_reference_price": float(bar.close),
            "signal_source_payload_sha256": _digest(event.payload),
            "signal_canonical_event_sha256": _digest(event_document),
            "target_exposure": target,
            "desired_target": target,
            "current_exposure_at_signal": current,
            "timeframe_seconds": self.paper_config.timeframe_seconds,
            "max_wait_bars": 1,
            "expected_execution_observed_at": expected_time.isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z"),
            "signal_health": dict(health),
            "signal_health_allows_increase": bool(
                health.get("state") == "GREEN"
                and health.get("can_open_exposure") is True
            ),
            "signal_target_application": dict(application),
        }
        body["order_sha256"] = _digest(body)
        return body

    def _settle_pending_order(
        self,
        event: Any,
        bar: MarketBar,
        *,
        health: Mapping[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
        order = self._causal_state.get("pending_order")
        if order is None:
            return None, None, None
        if not isinstance(order, Mapping):
            raise ValueError("paper pending causal state is malformed")
        expected_time = _paper_timestamp(str(order["expected_execution_observed_at"]))
        current_time = _paper_timestamp(str(event.observed_at))
        signal_created = _paper_timestamp(str(order["signal_created_at"]))
        event_available = _paper_timestamp(str(event.available_at))
        reason: str | None = None
        if current_time != expected_time:
            reason = "timeframe-gap" if current_time > expected_time else "noncontiguous-timeframe"
        elif event_available <= signal_created:
            reason = "source-already-available-at-signal"
        if reason is not None:
            expiry = {
                "kind": "expired",
                "reason": reason,
                "expired_at": _paper_now(),
                "pending_order": dict(order),
                "event_id": str(event.event_id),
                "source_id": str(event.source_id),
                "source_revision": str(event.source_revision),
                "observed_at": str(event.observed_at),
                "available_at": str(event.available_at),
                "source_payload_sha256": _digest(event.payload),
                "canonical_event_sha256": _digest(event.as_dict()),
            }
            return None, expiry, None
        operation_id = (
            f"paper:{self.paper_config.venue}:{self.consumer_id}:"
            f"{order['order_sha256']}:{event.event_id}"
        )
        application, fill = self._apply_order_target(
            bar,
            float(order["target_exposure"]),
            health,
            operation_id=operation_id,
            canonical_event_id=str(event.event_id),
            signal_health=cast(Mapping[str, Any], order["signal_health"]),
        )
        health_blocked = any(
            item.get("rule")
            in ("unhealthy-feed-blocks-increase", "signal-health-blocks-increase")
            for item in application["adjustments"]
        )
        settlement_status = (
            "filled"
            if fill is not None
            else "blocked-health-increase"
            if health_blocked
            else "settled-no-fill"
        )
        settlement = {
            "schema": "cassi.trading-field-paper-settlement.v1",
            "status": settlement_status,
            "reason": "health-blocked-increase" if health_blocked else None,
            "signal_event_id": order["signal_event_id"],
            "field_decision_event_id": order["field_decision_event_id"],
            "execution_event_id": str(event.event_id),
            "execution_source_id": str(event.source_id),
            "execution_source_revision": str(event.source_revision),
            "execution_observed_at": str(event.observed_at),
            "execution_available_at": str(event.available_at),
            "execution_source_payload_sha256": _digest(event.payload),
            "execution_canonical_event_sha256": _digest(event.as_dict()),
            "signal_reference_price": order["signal_reference_price"],
            "execution_reference_price": float(bar.close),
            "signal_to_execution_seconds": (event_available - signal_created).total_seconds(),
            "execution_price": None if fill is None else fill["price"],
            "price": None if fill is None else fill["price"],
            "target_application": application,
            "signal_health": dict(order["signal_health"]),
            "settlement_health": dict(health),
            "fill": fill,
            "pending_order": dict(order),
            "settled_at": _paper_now(),
        }
        return settlement, None, fill

    def _refresh_field_outcomes(self) -> None:
        ledger_rows = self.field.ledger._rows
        for row in ledger_rows[self._outcome_scan_cursor :]:
            if row.get("kind") != "outcome":
                continue
            outcome = row["payload"]
            decision_id = outcome.get("decision_event_id")
            if isinstance(decision_id, str):
                self._outcomes_by_decision.setdefault(decision_id, []).append(row)
        self._outcome_scan_cursor = len(ledger_rows)

    def _field_model_report(
        self, decision_id: str | None
    ) -> dict[str, Any] | None:
        if decision_id is None:
            return None
        self._refresh_field_outcomes()
        outcomes = []
        for row in self._outcomes_by_decision.get(decision_id, ()):
            outcome = row["payload"]
            selected = outcome.get("selected_modeled_outcome")
            outcomes.append(
                {
                    "outcome_event_id": row["event_id"],
                    "horizon": outcome.get("horizon"),
                    "selected_modeled_outcome": (
                        None if not isinstance(selected, Mapping) else dict(selected)
                    ),
                }
            )
        return {
            "decision_event_id": decision_id,
            "provenance": "field-internal modeled fixed exposure on observed price path",
            "paper_account_execution_model": PAPER_EXECUTION_MODEL,
            "outcomes": outcomes,
            "interpretation": PAPER_INTERNAL_MODEL_NOTE,
        }

    def _receipt_for_event(
        self,
        event: Any,
        bar: MarketBar,
        *,
        trading_bar_event_id: str,
        field_decision_event_id: str | None,
        field_decision: Mapping[str, Any] | None,
        health: Mapping[str, Any],
        bootstrap: bool,
        signal_created_at: str,
    ) -> dict[str, Any]:
        self._mark_account(bar)
        previous_state = dict(self._causal_state)
        settlement, order_expiry, fill = self._settle_pending_order(
            event,
            bar,
            health=health,
        )
        next_state = dict(previous_state)
        if settlement is not None:
            next_state["pending_order"] = None
            next_state["last_execution"] = settlement
        if order_expiry is not None:
            next_state["pending_order"] = None
            next_state["last_expiry"] = order_expiry

        if bootstrap:
            target = (
                None
                if field_decision is None
                else _finite(field_decision["target"], "field target")
            )
            application: dict[str, Any] = {
                "requested_target": target,
                "size_limited_target": None,
                "applied_target": None,
                "resulting_exposure": self.account.exposure_fraction(self.symbol, bar.close),
                "current_exposure": self.account.exposure_fraction(self.symbol, bar.close),
                "health_allows_increase": (
                    health.get("state") == "GREEN"
                    and health.get("can_open_exposure") is True
                ),
                "account_frozen": self.account.frozen,
                "maximum_position_fraction": self.paper_config.max_position_fraction,
                "maximum_turnover": self.paper_config.max_turnover,
                "adjustments": [{"rule": "initial-history-no-paper-fills"}],
            }
            disposition = "bootstrap-warmup"
            if settlement is not None or order_expiry is not None:
                raise ValueError("bootstrap history cannot settle a causal paper order")
        elif field_decision is None:
            current = self.account.exposure_fraction(self.symbol, bar.close)
            application = {
                "requested_target": None,
                "size_limited_target": None,
                "applied_target": None,
                "resulting_exposure": current,
                "current_exposure": current,
                "health_allows_increase": (
                    health.get("state") == "GREEN"
                    and health.get("can_open_exposure") is True
                ),
                "account_frozen": self.account.frozen,
                "maximum_position_fraction": self.paper_config.max_position_fraction,
                "maximum_turnover": self.paper_config.max_turnover,
                "adjustments": [{"rule": "bar-has-no-field-decision"}],
            }
            disposition = (
                "paper-filled"
                if fill is not None
                else "paper-order-expired"
                if order_expiry is not None
                else "paper-settled-no-fill"
                if settlement is not None
                else "no-field-decision"
            )
        else:
            application = self._prepare_target(
                bar,
                _finite(field_decision["target"], "field target"),
                health,
            )
            new_order = self._make_pending_order(
                event,
                bar,
                trading_bar_event_id=trading_bar_event_id,
                decision_id=str(field_decision_event_id),
                decision=field_decision,
                application=application,
                health=health,
                signal_created_at=signal_created_at,
            )
            next_state["pending_order"] = new_order
            if fill is not None:
                disposition = "paper-filled"
            elif order_expiry is not None:
                disposition = "paper-order-expired"
            elif settlement is not None:
                disposition = "paper-settled-no-fill"
            elif new_order is not None:
                disposition = "paper-order-pending"
            else:
                disposition = "paper-no-order"
        if bootstrap and field_decision is None:
            disposition = "bootstrap-warmup"
        event_document = event.as_dict()
        decision_sha256 = None if field_decision is None else _digest(field_decision)
        body: dict[str, Any] = {
            "schema": PAPER_CONSUMER_CAUSAL_EVENT_SCHEMA,
            "execution_model": PAPER_EXECUTION_MODEL,
            "signal_to_fill_lag_bars": 1,
            "field_internal_model": PAPER_INTERNAL_MODEL_NOTE,
            "field_internal_modeled_outcomes": self._field_model_report(
                None if field_decision_event_id is None else str(field_decision_event_id)
            ),
            "causal_cutover_event_id": self._causal_cutover_event_id,
            "causal_state_before_sha256": _digest(previous_state),
            "causal_state": next_state,
            "causal_state_sha256": _digest(next_state),
            "pending_order": next_state["pending_order"],
            "last_execution": next_state["last_execution"],
            "last_expiry": next_state["last_expiry"],
            "settlement": settlement,
            "order_expiry": order_expiry,
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "paper_config_sha256": self._config_sha256,
            "receipt_sequence": len(self._ordered_paper_rows) + 1,
            "previous_receipt_sha256": (
                _EMPTY_PAPER_RECEIPT_SHA256
                if self._latest_receipt is None
                else self._latest_receipt["content_sha256"]
            ),
            "canonical_event_id": event.event_id,
            "canonical_event": event_document,
            "canonical_event_sha256": _digest(event_document),
            "source_payload_sha256": _digest(event.payload),
            "trading_bar_event_id": trading_bar_event_id,
            "field_decision_event_id": field_decision_event_id,
            "field_decision": None if field_decision is None else dict(field_decision),
            "field_decision_sha256": decision_sha256,
            "field_target": (
                None
                if field_decision is None
                else _finite(field_decision["target"], "field target")
            ),
            "target_application": application,
            "disposition": disposition,
            "fill": fill,
            "account": self.account.as_dict(),
            "data_health": dict(health),
            "paper_only": True,
            "external_effect": "none",
        }
        body["content_sha256"] = _digest(body)
        return body

    def _append_paper_receipt(self, receipt: Mapping[str, Any]) -> Mapping[str, Any]:
        if receipt.get("schema") != PAPER_CONSUMER_CAUSAL_EVENT_SCHEMA:
            raise ValueError("new paper receipts must use the causal schema")
        if self._causal_cutover is None:
            raise ValueError("causal paper receipt cannot precede its cutover boundary")
        if receipt.get("causal_state_before_sha256") != _digest(self._causal_state):
            raise ValueError("causal paper receipt does not follow current pending state")
        row, replayed = self.field.ledger.append("paper-event", receipt)
        if dict(row["payload"]) != dict(receipt):
            raise ValueError("paper event receipt conflicts with resident evidence")
        event_id = str(receipt["canonical_event_id"])
        if event_id in self._paper_receipts:
            if self._paper_receipts[event_id] != dict(receipt):
                raise ValueError("canonical event has conflicting paper receipts")
            return row
        if replayed:
            raise ValueError("unindexed paper receipt already exists in the trading ledger")
        causal_state = receipt.get("causal_state")
        if not isinstance(causal_state, Mapping):
            raise ValueError("causal paper receipt has no durable causal state")
        self._causal_state = dict(causal_state)
        self._causal_state_event_id = str(row["event_id"])
        self._causal_states_by_record_id[str(row["event_id"])] = dict(causal_state)
        self._paper_receipts[event_id] = dict(receipt)
        self._paper_rows[event_id] = row
        self._ordered_paper_rows.append(row)
        self._bootstrap_holes.discard(event_id)
        raw_fill = receipt.get("fill")
        if raw_fill is not None:
            fill = dict(raw_fill)
            fill.setdefault("execution_model", PAPER_EXECUTION_MODEL)
            self._fill_count += 1
            self._causal_fill_count += 1
            self._latest_fill = fill
            self._latest_causal_fill = fill
        self._latest_paper_row = row
        self._latest_receipt = dict(receipt)
        return row
    def _verify_existing_receipt(
        self,
        receipt: Mapping[str, Any],
        event: Any,
        bar_event_id: str,
        decision_id: str | None,
        decision: Mapping[str, Any] | None,
    ) -> None:
        event_document = event.as_dict()
        if (
            receipt.get("canonical_event") != event_document
            or receipt.get("canonical_event_sha256") != _digest(event_document)
            or receipt.get("source_payload_sha256") != _digest(event.payload)
            or receipt.get("trading_bar_event_id") != bar_event_id
            or receipt.get("field_decision_event_id") != decision_id
            or receipt.get("field_decision") != (None if decision is None else dict(decision))
            or receipt.get("field_decision_sha256")
            != (None if decision is None else _digest(decision))
        ):
            raise ValueError("retry source or field decision differs from its paper receipt")
        if receipt.get("schema") == PAPER_CONSUMER_CAUSAL_EVENT_SCHEMA:
            pending = receipt.get("pending_order")
            if pending is not None:
                self._validate_pending_order(
                    pending,
                    event_id=str(event.event_id),
                    decision_id=decision_id,
                    decision=decision,
                    event_doc=event_document,
                )

    def _source_delivery_body(
        self,
        event: Any,
        receipt_row: Mapping[str, Any],
        receipt: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "canonical_event_id": event.event_id,
            "source_id": event.source_id,
            "source_revision": event.source_revision,
            "observed_at": event.observed_at,
            "available_at": event.available_at,
            "source_payload_sha256": _digest(event.payload),
            "canonical_event_sha256": _digest(event.as_dict()),
            "trading_bar_event_id": receipt["trading_bar_event_id"],
            "field_decision_event_id": receipt["field_decision_event_id"],
            "paper_receipt_event_id": receipt_row["event_id"],
            "paper_receipt_sha256": receipt["content_sha256"],
            "trading_disposition": receipt["disposition"],
            "execution_model": receipt.get("execution_model", "legacy-same-bar-v1"),
            "pending_order_sha256": (
                None
                if receipt.get("pending_order") is None
                else receipt["pending_order"].get("order_sha256")
            ),
            "last_execution_event_id": (
                None
                if receipt.get("last_execution") is None
                else receipt["last_execution"].get("execution_event_id")
            ),
        }

    def _validate_source_delivery_link(
        self,
        event: Any,
        receipt_row: Mapping[str, Any],
        receipt: Mapping[str, Any],
        link: Mapping[str, Any],
    ) -> None:
        expected = self._source_delivery_body(event, receipt_row, receipt)
        required = (
            "source_id",
            "source_revision",
            "source_payload_sha256",
            "trading_bar_event_id",
        )
        if any(key not in link or link.get(key) != expected[key] for key in required):
            raise ValueError("source-delivery link conflicts with canonical paper evidence")
        optional = (
            "consumer_id",
            "canonical_event_id",
            "observed_at",
            "available_at",
            "canonical_event_sha256",
            "field_decision_event_id",
            "paper_receipt_event_id",
            "paper_receipt_sha256",
            "trading_disposition",
            "execution_model",
            "pending_order_sha256",
            "last_execution_event_id",
        )
        if any(key in link and link[key] != expected[key] for key in optional):
            raise ValueError("source-delivery link names different paper provenance")

    def _source_delivery(
        self,
        event: Any,
        receipt_row: Mapping[str, Any],
        receipt: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        body = self._source_delivery_body(event, receipt_row, receipt)
        existing_links = self._source_links_by_event.get(str(event.event_id), [])
        for link in existing_links:
            self._validate_source_delivery_link(event, receipt_row, receipt, link)
        row, _ = self.field.ledger.append("source-delivery", body)
        if dict(row["payload"]) != body:
            raise ValueError("source-delivery link conflicts with resident evidence")
        if dict(row["payload"]) not in existing_links:
            self._source_links_by_event.setdefault(str(event.event_id), []).append(
                row["payload"]
            )
        return row

    def cancel_pending(self, reason: str) -> Mapping[str, Any]:
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 256:
            raise ValueError("pending cancellation reason must contain 1 to 256 characters")
        normalized_reason = reason.strip()
        pending = self._causal_state.get("pending_order")
        if pending is None:
            return {
                "cancelled": False,
                "reason": normalized_reason,
                "pending_order": None,
                "last_expiry": self._causal_state.get("last_expiry"),
            }
        if not isinstance(pending, Mapping):
            raise ValueError("paper pending causal state is malformed")
        if self._latest_paper_row is None:
            raise ValueError("paper pending order has no durable receipt anchor")
        self._ensure_causal_cutover()
        cancelled_at = _paper_now()
        expiry = {
            "kind": "cancelled",
            "reason": normalized_reason,
            "cancelled_at": cancelled_at,
            "pending_order": dict(pending),
        }
        next_state = {
            "pending_order": None,
            "last_execution": self._causal_state.get("last_execution"),
            "last_expiry": expiry,
        }
        body: dict[str, Any] = {
            "schema": PAPER_CONSUMER_CANCELLATION_SCHEMA,
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "reason": normalized_reason,
            "cancelled_at": cancelled_at,
            "pending_order": dict(pending),
            "pending_order_sha256": pending.get("order_sha256"),
            "previous_causal_state_sha256": _digest(self._causal_state),
            "causal_state": next_state,
            "causal_state_sha256": _digest(next_state),
            "paper_receipt_event_id": self._latest_paper_row["event_id"],
            "paper_receipt_sha256": self._latest_receipt["content_sha256"],
        }
        body["content_sha256"] = _digest(body)
        row, replayed = self.field.ledger.append("paper-pending-cancellation", body)
        if dict(row["payload"]) != body:
            raise ValueError("paper pending cancellation conflicts with resident evidence")
        if replayed:
            raise ValueError("paper pending cancellation appeared concurrently")
        self._causal_state = next_state
        self._causal_state_event_id = str(row["event_id"])
        self._causal_states_by_record_id[str(row["event_id"])] = dict(next_state)
        self._recovery_state = "causal-cancellation-snapshot-pending"
        self._write_snapshot()
        self._recovery_state = "snapshot-current"
        return {
            "cancelled": True,
            "reason": normalized_reason,
            "pending_order": dict(pending),
            "last_expiry": expiry,
            "cancellation_event_id": row["event_id"],
        }

    def activate(self) -> None:
        """Freeze the existing accepted history before a continuing worker waits for new bars."""
        self._ensure_activation()

    def drain(
        self,
        *,
        max_bars: int = 0,
        health: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if isinstance(max_bars, bool) or not isinstance(max_bars, int) or max_bars < 0:
            raise ValueError("max_bars cannot be negative")
        if not isinstance(health, Mapping):
            raise TypeError("health must be a DataHealth.as_dict() mapping")
        health_document = dict(health)
        _canonical_bytes(health_document)
        self._ensure_activation()
        pending_before = self.store.pending_count(
            self.consumer_id,
            event_type="market-bar",
            subject_id=self.symbol,
        )
        if self._pending_event_buffer is None or not self._pending_event_buffer or (
            max_bars == 0 and not self._pending_event_buffer_complete
        ):
            limit = (
                max_bars
                if max_bars > 0 and not self._bootstrap_holes
                else None
            )
            pending = list(
                self.store.pending_events(
                    self.consumer_id,
                    event_type="market-bar",
                    subject_id=self.symbol,
                    limit=limit,
                )
            )
            self._pending_event_buffer = deque(pending)
            self._pending_event_buffer_complete = limit is None
        if self._pending_event_buffer is None:
            raise ValueError("paper pending-event index is unavailable")
        pending_buffer = self._pending_event_buffer
        selected = (
            list(pending_buffer)
            if max_bars == 0
            else list(islice(pending_buffer, max_bars))
        )
        admitted = 0
        replayed = 0
        paper_fills = 0
        last_source_event_id: str | None = None
        for event in selected:
            bar = MarketBar.from_mapping(cast(Mapping[str, Any], event.payload))
            if (
                event.event_type != "market-bar"
                or event.subject_ids != (self.symbol,)
                or _paper_timestamp(event.observed_at) != _paper_timestamp(bar.timestamp)
            ):
                raise ValueError(
                    "accepted event does not match the paper consumer's market-bar contract"
                )
            event_hash = _digest(event.as_dict())
            if event.event_id in self._bootstrap_event_ids:
                expected_hash = self._activation["bootstrap_event_sha256"][event.event_id]
                if event_hash != expected_hash:
                    raise ValueError("paper bootstrap event changed after activation")
            prior_receipt = self._paper_receipts.get(str(event.event_id))
            if prior_receipt is None and _paper_timestamp(event.available_at) > _paper_timestamp(
                _paper_now()
            ):
                raise ValueError("accepted paper bar is not yet available to the host")
            result = self.field.ingest_bar(bar)
            status = str(result["status"])
            if status == "admitted":
                admitted += 1
            else:
                replayed += 1
            trading_bar_event_id = str(result["bar_event_id"])
            decision_id, decision = self._field_decision_for_bar(trading_bar_event_id)
            if prior_receipt is not None:
                self._verify_existing_receipt(
                    prior_receipt,
                    event,
                    trading_bar_event_id,
                    decision_id,
                    decision,
                )
                receipt_row = self._paper_rows[str(event.event_id)]
                receipt = prior_receipt
                self._recovery_state = "snapshot-update-pending"
                self._write_snapshot()
                self._recovery_state = "snapshot-current"
            else:
                if self._latest_receipt is not None and (
                    _paper_timestamp(event.observed_at)
                    <= _paper_timestamp(
                        str(self._latest_receipt["canonical_event"]["observed_at"])
                    )
                ):
                    raise ValueError(
                        "unreceipted paper event precedes already committed paper state"
                    )
                self._ensure_causal_cutover()
                signal_created_at = _paper_now()
                if _paper_timestamp(event.available_at) > _paper_timestamp(signal_created_at):
                    raise ValueError("paper signal predates source availability")
                account_before = self.account.as_dict()
                causal_state_before = dict(self._causal_state)
                try:
                    receipt = self._receipt_for_event(
                        event,
                        bar,
                        trading_bar_event_id=trading_bar_event_id,
                        field_decision_event_id=decision_id,
                        field_decision=decision,
                        health=health_document,
                        bootstrap=event.event_id in self._bootstrap_event_ids,
                        signal_created_at=signal_created_at,
                    )
                    receipt_row = self._append_paper_receipt(receipt)
                except Exception:
                    self.account = PaperAccount.from_dict(account_before)
                    self._causal_state = causal_state_before
                    raise
                self._recovery_state = "snapshot-update-pending"
                self._write_snapshot()
                self._recovery_state = "snapshot-current"
                if receipt["fill"] is not None:
                    paper_fills += 1
            source_row = self._source_delivery(event, receipt_row, receipt)
            self.store.mark_delivered(
                self.consumer_id,
                event.event_id,
                disposition=f"trading-field-{receipt['disposition']}",
                receipt_sha256=str(source_row["content_sha256"]),
            )
            if (
                not pending_buffer
                or str(pending_buffer[0].event_id) != str(event.event_id)
            ):
                raise ValueError("paper pending-event index lost chronological order")
            pending_buffer.popleft()
            last_source_event_id = str(event.event_id)
        if not pending_buffer:
            self._pending_event_buffer = None
            self._pending_event_buffer_complete = False
        pending_after = self.store.pending_count(
            self.consumer_id,
            event_type="market-bar",
            subject_id=self.symbol,
        )
        return {
            "schema": PAPER_CONSUMER_SCHEMA,
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "processed": len(selected),
            "admitted_bars": admitted,
            "replayed_bars": replayed,
            "paper_fills": paper_fills,
            "pending_before": pending_before,
            "pending_after": pending_after,
            "pending_order": self._causal_state.get("pending_order"),
            "last_execution": self._causal_state.get("last_execution"),
            "last_expiry": self._causal_state.get("last_expiry"),
            "last_source_event_id": last_source_event_id,
            "field": self.field.status(),
            "paper_status": self.paper_status(),
        }

    def paper_status(self) -> Mapping[str, Any]:
        last = self._latest_receipt
        if last is None:
            last_event = None
            field_target = None
            source = None
            last_receipt = None
            data_health = None
            latest_field_model = None
        else:
            event = cast(Mapping[str, Any], last["canonical_event"])
            last_event = {
                "canonical_event_id": last["canonical_event_id"],
                "source_id": event["source_id"],
                "source_revision": event["source_revision"],
                "observed_at": event["observed_at"],
                "trading_bar_event_id": last["trading_bar_event_id"],
                "field_decision_event_id": last["field_decision_event_id"],
                "paper_receipt_event_id": (
                    None
                    if self._latest_paper_row is None
                    else self._latest_paper_row["event_id"]
                ),
                "paper_receipt_sha256": last["content_sha256"],
                "disposition": last["disposition"],
                "execution_model": last.get("execution_model", "legacy-same-bar-v1"),
            }
            application = cast(Mapping[str, Any], last["target_application"])
            field_target = {
                "value": last["field_target"],
                "requested": last["field_target"],
                "applied": application.get("applied_target"),
                "decision_event_id": last["field_decision_event_id"],
                "selection_source": (
                    None
                    if last["field_decision"] is None
                    else last["field_decision"].get("selection_source")
                ),
            }
            source = {
                "canonical_event_id": last["canonical_event_id"],
                "source_id": event["source_id"],
                "source_revision": event["source_revision"],
                "source_payload_sha256": last["source_payload_sha256"],
                "canonical_event_sha256": last["canonical_event_sha256"],
                "observed_at": event["observed_at"],
                "available_at": event["available_at"],
            }
            last_receipt = {
                **dict(last),
                "ledger_event_id": (
                    None
                    if self._latest_paper_row is None
                    else self._latest_paper_row["event_id"]
                ),
                "ledger_content_sha256": (
                    None
                    if self._latest_paper_row is None
                    else self._latest_paper_row["content_sha256"]
                ),
            }
            data_health = dict(last["data_health"])
            latest_field_model = self._field_model_report(
                None
                if last["field_decision_event_id"] is None
                else str(last["field_decision_event_id"])
            )
        activation_boundary = None
        if self._activation is not None:
            activation_boundary = {
                "event_id": self._activation["activation_boundary_event_id"],
                "observed_at": self._activation["activation_boundary_observed_at"],
                "bootstrap_event_count": len(self._bootstrap_event_ids),
            }
        cutover = self._causal_cutover
        legacy_account = (
            None if cutover is None else dict(cutover["legacy_account"])
        )
        causal_account_change = None
        if legacy_account is not None:
            baseline_equity = float(legacy_account["equity"])
            causal_account_change = {
                "provenance": "account change since immutable causal cutover baseline; not standalone realized P&L",
                "baseline_equity": baseline_equity,
                "current_equity": self.account.equity,
                "equity_change": self.account.equity - baseline_equity,
                "legacy_fills_before_cutover": self._legacy_receipt_count,
            }
        execution_model = {
            "paper_account": PAPER_EXECUTION_MODEL,
            "signal_to_fill_lag_bars": 1,
            "timeframe_seconds": self.paper_config.timeframe_seconds,
            "maximum_wait_bars": 1,
            "legacy_receipts": "immutable v1 same-bar results; not reinterpreted",
            "field_internal_model": PAPER_INTERNAL_MODEL_NOTE,
            "cutover_event_id": self._causal_cutover_event_id,
        }
        return {
            "schema": PAPER_CONSUMER_SCHEMA,
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "paper_only": True,
            "external_effect": "none",
            "execution_model": execution_model,
            "causal_cutover": cutover,
            "latest_legacy_fill": self._latest_legacy_fill,
            "legacy_fill_count": self._legacy_fill_count,
            "latest_causal_fill": self._latest_causal_fill,
            "causal_fill_count": self._causal_fill_count,
            "causal_account_change": causal_account_change,
            "field_internal_modeled_outcomes": latest_field_model,
            "activation_boundary": activation_boundary,
            "processed": len(self._paper_receipts),
            "pending": self.store.pending_count(
                self.consumer_id,
                event_type="market-bar",
                subject_id=self.symbol,
            ),
            "pending_order": self._causal_state.get("pending_order"),
            "last_execution": self._causal_state.get("last_execution"),
            "last_expiry": self._causal_state.get("last_expiry"),
            "causal_state_event_id": self._causal_state_event_id,
            "field_target": field_target,
            "fill_count": self._fill_count,
            "latest_fill": self._latest_fill,
            "account": self.account.as_dict(),
            "source": source,
            "health": data_health,
            "last_event": last_event,
            "last_receipt": last_receipt,
            "recovery": {
                "state": self._recovery_state,
                "recovered_receipt_count": self._recovered_receipt_count,
                "snapshot_exists": self.paper_state_path.exists(),
                "last_receipt_sha256": (
                    None if last is None else last["content_sha256"]
                ),
                "causal_state_sha256": _digest(self._causal_state),
            },
        }


def load_bars_csv(path: Path, *, symbol: str | None = None) -> tuple[MarketBar, ...]:
    rows: list[MarketBar] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("market CSV lacks timestamp, OHLC, or volume columns")
        for raw in reader:
            row_symbol = symbol or raw.get("symbol")
            if not row_symbol:
                raise ValueError("market CSV needs a symbol column or explicit symbol")
            rows.append(
                MarketBar(
                    timestamp=str(raw["timestamp"]),
                    symbol=str(row_symbol),
                    open=float(raw["open"]),
                    high=float(raw["high"]),
                    low=float(raw["low"]),
                    close=float(raw["close"]),
                    volume=float(raw["volume"]),
                )
            )
    return tuple(rows)


def generate_demo_bars(count: int = 260, *, symbol: str = "BTC-USD") -> tuple[MarketBar, ...]:
    if count < 32:
        raise ValueError("demo stream needs at least 32 bars")
    price = 100.0
    rows = []
    for index in range(count):
        block = (index // 32) % 4
        drift = (0.006, -0.004, 0.003, -0.002)[block]
        change = drift + 0.0012 * math.sin(index * 1.7)
        opening = price
        closing = opening * (1.0 + change)
        rows.append(
            MarketBar(
                timestamp=f"2025-01-{1 + index // 24:02d}T{index % 24:02d}:00:00Z",
                symbol=symbol,
                open=opening,
                high=max(opening, closing) * 1.001,
                low=min(opening, closing) * 0.999,
                close=closing,
                volume=1000.0 + 25.0 * (index % 11),
            )
        )
        price = closing
    return tuple(rows)


__all__ = [
    "CanonicalFieldConsumer",
    "CanonicalFieldPaperConsumer",
    "MarketBar",
    "TradingEvidenceLedger",
    "TradingField",
    "TradingFieldConfig",
    "generate_demo_bars",
    "load_bars_csv",
]
