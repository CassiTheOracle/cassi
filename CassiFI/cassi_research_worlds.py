from __future__ import annotations

"""Bounded, field-owned observations of physics and simulated worlds.

This integration deliberately exposes two different responsibilities:

* ``physics_observation`` uses only the read-only CassiCosmos 7599 adapter.  It
  never deposits, steps, clears, or otherwise mutates the running engine.
* ``market_world_step`` replays caller-supplied closed bars through the existing
  CassiTrading residency engine with field learning disabled.  The account and
  position state therefore changes because of the supplied bars and fixed
  strategy, not because this module owns another adaptive system.

All adaptive continuation is returned to the caller as evidence; this module
keeps no world, model, or checkpoint state between operations.
"""

import hashlib
import importlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from cassi_cosmos_adapter import CassiCosmos7599Adapter
from cassi_field_atlas import FieldIntelligenceError


PHYSICS_KIND = "physics_observation"
MARKET_KIND = "market_world_step"
INSTRUMENT_KIND = "instrument_world_step"
CATALOG_SCHEMA = "cassi.research-worlds-catalog.v1"
PHYSICS_SCHEMA = "cassi.research-worlds-physics.v1"
MARKET_SCHEMA = "cassi.research-worlds-market.v1"
INSTRUMENT_SCHEMA = "cassi.research-worlds-instrument.v1"
_MAX_BARS = 512
_MAX_FIELD_BYTES = 64 * 1024


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


def _text(value: Any, name: str, *, max_bytes: int = 512) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    if len(value.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} is too long")
    return value


def _finite(value: Any, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


def _bounded_int(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _operation_id(request: Mapping[str, Any]) -> str:
    return _text(request.get("operation_id"), "operation_id", max_bytes=512)


def _evidence_with_digest(body: Mapping[str, Any]) -> dict[str, Any]:
    evidence = dict(body)
    evidence["evidence_sha256"] = _digest(evidence)
    return evidence


def _error_evidence(error: Exception, *, code: str) -> dict[str, Any]:
    return _evidence_with_digest(
        {
            "schema": "cassi.research-worlds-error.v1",
            "error_code": code,
            "error_type": type(error).__name__,
            "message": str(error),
        }
    )


def _artifact_home(home: Path) -> Path:
    if not isinstance(home, Path):
        home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    return home


def _save_physics_source(home: Path, operation_id: str, content: bytes) -> dict[str, Any]:
    """Persist bounded raw bridge bytes so provenance is independently checkable."""
    if len(content) > _MAX_FIELD_BYTES:
        # The adapter itself enforces a much larger transport bound.  Do not
        # copy an unexpectedly large response into a resident artifact.
        return {
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "persisted": False,
            "reason": "source-response-exceeds-research-artifact-bound",
        }
    digest = hashlib.sha256(content).hexdigest()
    path = home / f"physics-source-{digest}.bin"
    if not path.exists():
        path.write_bytes(content)
    return {
        "bytes": len(content),
        "sha256": digest,
        "path": str(path),
        "persisted": True,
    }


def _physics_work(request: Mapping[str, Any], *, artifact_home: Path) -> dict[str, Any]:
    operation_id = _operation_id(request)
    command = request.get("cmd", request.get("command"))
    fields = request.get("fields")
    if not isinstance(command, str) or not command:
        raise ValueError("physics request requires cmd")
    if not isinstance(fields, Sequence) or isinstance(fields, (str, bytes)):
        raise ValueError("physics request requires fields")
    field_names = list(fields)
    if not field_names or any(not isinstance(field, str) or not field for field in field_names):
        raise ValueError("physics fields must be non-empty text")
    host = request.get("host", "127.0.0.1")
    port = _bounded_int(request.get("port", 7599), "port", minimum=1, maximum=65535)
    timeout = _finite(request.get("timeout", 5.0), "timeout")
    if timeout <= 0.0 or timeout > 60.0:
        raise ValueError("timeout must be in (0, 60]")
    adapter = CassiCosmos7599Adapter(host=_text(host, "host"), port=port, timeout=timeout)
    journal = _artifact_home(artifact_home) / "cosmos-read-journal"
    adapter.bind_durable_journal(journal)
    normalized_request: dict[str, Any] = {"cmd": command, "fields": field_names}
    if command in {"project", "qi_project"}:
        normalized_request["k"] = _bounded_int(request.get("k", 1), "k", minimum=1, maximum=64)
    try:
        acknowledgment = adapter.execute_once(
            operation_id=operation_id,
            action="observe",
            target=f"cosmos:7599:{command}",
            payload={"request": normalized_request},
        )
    except FieldIntelligenceError:
        raise
    source = _save_physics_source(
        _artifact_home(artifact_home),
        operation_id,
        acknowledgment.source_content,
    )
    acknowledgment_body = dict(acknowledgment.as_dict())
    # Keep raw bytes in the content-addressed artifact, rather than duplicating
    # them in the resident field evidence envelope.
    acknowledgment_body.pop("source_content_base64", None)
    acknowledgment_body["source"] = source
    body = {
        "schema": PHYSICS_SCHEMA,
        "operation_id": operation_id,
        "simulation_label": "read-only-cassicosmos-observation",
        "mutation_guard": {
            "action": "observe",
            "allowed_commands": ["ping", "state", "project", "qi_state", "qi_project"],
            "writes_performed": False,
        },
        "request": normalized_request,
        "acknowledgment": acknowledgment_body,
    }
    evidence = _evidence_with_digest(body)
    if acknowledgment.status == "succeeded":
        return {
            "status": "observed",
            "summary": f"Read-only CassiCosmos {command} observation succeeded.",
            "evidence": evidence,
        }
    return {
        "status": "support-gap",
        "summary": (
            f"CassiCosmos {command} observation was not available: "
            f"adapter status={acknowledgment.status}."
        ),
        "evidence": evidence,
    }


def _trading_modules() -> tuple[Any, Any, Any]:
    """Import the existing local trading implementation without network access."""
    trading_root = Path(__file__).resolve().parents[1] / "CassiTrading"
    if not trading_root.is_dir():
        raise ModuleNotFoundError(f"local CassiTrading workspace is unavailable: {trading_root}")
    root_text = str(trading_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    foundry = importlib.import_module("cassi_trading_foundry")
    residency = importlib.import_module("run_cassi_market_residency")
    return foundry, residency, trading_root


def _market_bars(raw_bars: Any) -> tuple[Any, ...]:
    if not isinstance(raw_bars, Sequence) or isinstance(raw_bars, (str, bytes)):
        raise ValueError("market request requires an ordered bars sequence")
    if not 96 <= len(raw_bars) <= _MAX_BARS:
        raise ValueError(f"market bars must contain between 96 and {_MAX_BARS} rows")
    foundry, _, _ = _trading_modules()
    bars = []
    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    for index, raw in enumerate(raw_bars):
        if not isinstance(raw, Mapping) or set(raw) != required:
            raise ValueError(f"bar {index} must contain exactly {sorted(required)}")
        bars.append(foundry.MarketBar(**dict(raw)))
    # Existing run_online_arm enforces strict chronology and one symbol.  Do a
    # cheap local check first to make malformed resident requests rejected.
    symbols = {bar.symbol for bar in bars}
    if len(symbols) != 1:
        raise ValueError("market bars must contain exactly one symbol")
    timestamps = [bar.timestamp for bar in bars]
    if timestamps != sorted(timestamps) or len(set(timestamps)) != len(timestamps):
        raise ValueError("market bar timestamps must be strictly increasing")
    return tuple(bars)


def _market_work(request: Mapping[str, Any], *, artifact_home: Path) -> dict[str, Any]:
    del artifact_home  # The existing replay receipt is returned directly; no sidecar state is kept.
    operation_id = _operation_id(request)
    bars = _market_bars(request.get("bars"))
    source = request.get("source")
    if source is None:
        source = {
            "kind": "embedded-request",
            "source_id": f"research-worlds:{bars[0].symbol}",
            "source_revision": "caller-supplied-bars.v1",
            "availability": "all-bars-supplied-before-simulation",
        }
    if not isinstance(source, Mapping):
        raise ValueError("source must be an object")
    source_body = dict(source)
    source_kind = _text(source_body.get("kind"), "source.kind")
    source_id = _text(source_body.get("source_id"), "source.source_id")
    source_revision = _text(source_body.get("source_revision"), "source.source_revision")
    warmup = _bounded_int(
        request.get("warmup_bars", 16),
        "warmup_bars",
        minimum=8,
        maximum=len(bars) - 2,
    )
    review_interval = _bounded_int(
        request.get("review_interval", 8),
        "review_interval",
        minimum=4,
        maximum=len(bars),
    )
    initial_equity = _finite(request.get("initial_equity", 1.0), "initial_equity")
    if initial_equity <= 0.0:
        raise ValueError("initial_equity must be positive")
    fee_bps = _finite(request.get("fee_bps", 10.0), "fee_bps", minimum=0.0)
    slippage_bps = _finite(request.get("slippage_bps", 5.0), "slippage_bps", minimum=0.0)
    max_position = _finite(request.get("max_position", 1.0), "max_position", minimum=0.0)
    timeframe_hours = _finite(request.get("timeframe_hours", 1.0), "timeframe_hours", minimum=0.000001)
    if max_position > 1.0:
        raise ValueError("max_position cannot exceed one")
    foundry, residency, _ = _trading_modules()
    config = residency.ResidencyConfig(
        calibration_bars=len(bars),
        external_bars=len(bars),
        warmup_bars=warmup,
        review_interval=review_interval,
        minimum_live_steps=1,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        initial_equity=initial_equity,
        max_position=max_position,
        timeframe_hours=timeframe_hours,
        field_component_limit=1.0,
        field_wave_width=16,
    )
    # This is intentionally a deterministic, field-blind adapter.  The one
    # persistent Cassi field can later learn from this receipt; no adaptive
    # field/checkpoint is owned or hidden here.
    receipt = residency.run_online_arm(
        bars,
        config=config,
        arm_name=f"research-worlds:{operation_id}",
        learning_enabled=False,
        teach_field=False,
        initial_composition_id="balanced",
    )
    stream = receipt["stream"]
    decisions = list(stream["decisions"])
    metrics = dict(stream["metrics"])
    first_equity = initial_equity
    final_equity = float(decisions[-1]["equity"]) if decisions else first_equity
    final_position = int(decisions[-1]["position_after"]) if decisions else 0
    transitions = sum(
        int(row["position_before"] != row["position_after"])
        for row in decisions
    )
    realized = [float(row["net_return"]) for row in decisions if row["phase"] == "live"]
    learning_opportunities: list[dict[str, Any]] = []
    live_rows = [row for row in decisions if row.get("phase") == "live"]
    if len(live_rows) >= 8:
        def sign(value: Any) -> str:
            numeric = float(value)
            return (
                "positive"
                if numeric > 0.0
                else "negative"
                if numeric < 0.0
                else "flat"
            )

        def example(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
            return {
                "action": {
                    "position_before": int(left["position_before"]),
                    "position_after": int(left["position_after"]),
                },
                "context": {
                    "symbol": bars[0].symbol,
                    "timeframe_hours": timeframe_hours,
                },
                "future": {"next_bar_net_return_sign": sign(right["net_return"])},
                "history": [
                    {
                        "position": int(left["position_after"]),
                        "net_return_sign": sign(left["net_return"]),
                    }
                ],
                "question": "What is the next closed-bar net-return sign?",
            }

        grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for left, right in zip(live_rows, live_rows[1:]):
            row = example(left, right)
            key = (
                tuple(sorted(row["action"].items())),
                tuple(sorted(row["history"][0].items())),
                tuple(sorted(row["future"].items())),
            )
            grouped.setdefault(key, []).append(row)
        examples = [rows[0] for _, rows in sorted(grouped.items()) if rows]
        holdout = [
            rows[1]
            for _, rows in sorted(grouped.items())
            if len(rows) >= 2
        ]
        examples = examples[:8]
        holdout = holdout[:8]
        if len(examples) >= 2 and holdout:
            learning_opportunities.append(
                {
                    "candidate_id": f"market-predictive-state:{_digest({'operation_id': operation_id, 'bars': receipt['data']['data_sha256']})}",
                    "learning_kind": "predictive-state",
                    "expected_gain": 1.0,
                    "novelty": 1.0,
                    "priority": 0.5,
                    "cost": 1.0,
                    "risk": 0.0,
                    "request": {
                        "representation_id": f"market-next-return:{receipt['data']['data_sha256'][:16]}",
                        "signature": {
                            "clock_boundary": {"kind": "available_until"},
                            "collection_boundary": {
                                "kind": "embedded-bars",
                                "bars_sha256": receipt["data"]["data_sha256"],
                            },
                            "comparison_metric": "exact-next-bar-net-return-sign",
                            "horizon": 1,
                            "interval": {"bars": 1},
                            "output_measure": {
                                "name": "next_bar_net_return_sign",
                                "values": ["negative", "flat", "positive"],
                            },
                            "prediction_semantics": "constraint-set",
                            "probability_model": None,
                            "tolerance": 0.0,
                            "units": {"return": "fraction", "time": "bar"},
                        },
                        "examples": examples,
                        "holdout": holdout,
                        "window": 1,
                    },
                }
            )
    body = {
        "schema": MARKET_SCHEMA,
        "operation_id": operation_id,
        "simulation_label": "closed-bar-local-simulation",
        "external_effects": {
            "network": False,
            "exchange": False,
            "orders": False,
            "live_market_claim": False,
        },
        "input_provenance": {
            "kind": source_kind,
            "source_id": source_id,
            "source_revision": source_revision,
            "availability": source_body.get("availability", "caller-declared"),
            "bars": len(bars),
            "bars_sha256": receipt["data"]["data_sha256"],
            "event_root_sha256": receipt["data"]["event_root_sha256"],
        },
        "simulation": {
            "engine": "CassiTrading.run_online_arm",
            "field_learning": False,
            "initial_state": {
                "equity": first_equity,
                "position": 0,
                "strategy": receipt["initial_strategy"],
                "composition_id": "balanced",
            },
            "final_state": {
                "equity": final_equity,
                "position": final_position,
                "steps": len(decisions),
                "position_transitions": transitions,
            },
            "changed": bool(
                transitions or abs(final_equity - first_equity) > 1e-15 or any(realized)
            ),
            "config": config.as_dict(),
            "metrics": metrics,
            "reviews": list(stream["reviews"]),
            "decisions": decisions,
        },
        "continuation": {
            "kind": "field-learning-input",
            "observations": [
                {
                    "step": int(row["bar_index"]),
                    "available_until": row["available_until"],
                    "position_before": row["position_before"],
                    "position_after": row["position_after"],
                    "realized_return": row["realized_return"],
                    "net_return": row["net_return"],
                    "equity": row["equity"],
                    "lookahead_guard": row["lookahead_guard"],
                }
                for row in decisions
            ],
            "final_metrics": metrics,
        },
    }
    body["learning_opportunities"] = learning_opportunities
    body["evidence_contract"] = {
        "observations_are_replayable": True,
        "learning_rows_come_only_from_realized_decisions": True,
    }
    evidence = _evidence_with_digest(body)
    return {
        "status": "observed",
        "summary": (
            f"Closed-bar simulation advanced {len(decisions)} steps with "
            f"{transitions} position transitions and final equity {final_equity:.12g}."
        ),
        "evidence": evidence,
        "learning_opportunities": learning_opportunities,
    }


def _catalog_bars(count: int = 96, seed: int = 17) -> list[dict[str, Any]]:
    """Build one fully embedded deterministic history from a declared regime."""
    regimes = {
        17: {
            "symbol": "RESIDENT-SYNTH",
            "drifts": (0.006, -0.005, 0.004, -0.003),
            "oscillation": 0.0008,
            "frequency": 0.71,
            "wick_frequency": 0.37,
        },
        23: {
            "symbol": "RESIDENT-SYNTH-23",
            "drifts": (-0.004, 0.007, -0.006, 0.005),
            "oscillation": 0.0012,
            "frequency": 0.53,
            "wick_frequency": 0.29,
        },
    }
    regime = regimes.get(seed)
    if regime is None:
        raise ValueError(f"unsupported resident synthetic regime seed: {seed}")
    bars: list[dict[str, Any]] = []
    price = 100.0
    for index in range(count):
        block = (index // 24) % 4
        drift = regime["drifts"][block]
        oscillation = regime["oscillation"] * math.sin(
            index * regime["frequency"] + seed
        )
        change = drift + oscillation
        opening = price
        closing = opening * (1.0 + change)
        wick = 0.0015 + 0.0005 * abs(
            math.sin(index * regime["wick_frequency"])
        )
        bars.append(
            {
                "timestamp": f"2026-01-01T{index:04d}Z",
                "symbol": regime["symbol"],
                "open": opening,
                "high": max(opening, closing) * (1.0 + wick),
                "low": min(opening, closing) * (1.0 - wick),
                "close": closing,
                "volume": 1000.0 + 25.0 * (index % 11),
            }
        )
        price = closing
    return bars


def _instrument_work(request: Mapping[str, Any], *, artifact_home: Path) -> dict[str, Any]:
    """Run a deterministic instrument with delayed measurements and a live cue."""
    operation_id = _operation_id(request)
    scenario = request.get("scenario", {})
    if not isinstance(scenario, Mapping):
        raise ValueError("instrument scenario must be an object")
    steps = _bounded_int(scenario.get("steps", 32), "scenario.steps", minimum=16, maximum=256)
    change_at = _bounded_int(
        scenario.get("change_at", steps // 2),
        "scenario.change_at",
        minimum=2,
        maximum=steps - 2,
    )
    delay = _bounded_int(scenario.get("delay", 3), "scenario.delay", minimum=1, maximum=16)
    low = _finite(scenario.get("low", 0.0), "scenario.low")
    high = _finite(scenario.get("high", 1.0), "scenario.high")
    if high == low:
        raise ValueError("instrument levels must differ")
    context_available = scenario.get("context_available", True)
    if not isinstance(context_available, bool):
        raise ValueError("scenario.context_available must be boolean")
    tolerance = _finite(
        scenario.get("tolerance", 1e-12),
        "scenario.tolerance",
        minimum=0.0,
    )
    program = request.get("program", {})
    if not isinstance(program, Mapping):
        raise ValueError("instrument program must be an object")
    strategy = _text(program.get("strategy", "hold-last"), "program.strategy")
    if strategy not in {"hold-last", "context-gated", "trend"}:
        raise ValueError(f"unsupported instrument strategy: {strategy}")
    window = _bounded_int(program.get("window", 1), "program.window", minimum=1, maximum=16)
    target = [low if index < change_at else high for index in range(steps)]
    trace: list[dict[str, Any]] = []
    previous_measurements: list[float] = []
    for index in range(steps):
        delayed_index = index - delay
        measurement = target[delayed_index] if delayed_index >= 0 else low
        cue = 1 if context_available and index >= change_at else 0
        if strategy == "context-gated":
            prediction = high if cue else low
        elif strategy == "trend":
            history = previous_measurements[-window:]
            slope = history[-1] - history[-2] if len(history) >= 2 else 0.0
            prediction = measurement + slope
            prediction = max(min(prediction, max(low, high)), min(low, high))
        else:
            prediction = measurement
        error = abs(prediction - target[index])
        trace.append(
            {
                "step": index,
                "measurement": measurement,
                "context_cue": cue,
                "prediction": prediction,
                "target": target[index],
                "absolute_error": error,
                "correct": bool(error <= tolerance),
            }
        )
        previous_measurements.append(measurement)
    correct = sum(1 for row in trace if row["correct"])
    mean_abs_error = sum(float(row["absolute_error"]) for row in trace) / steps
    recovery = next(
        (
            row["step"] - change_at
            for row in trace
            if row["step"] >= change_at and row["correct"]
        ),
        None,
    )
    world = {
        "schema": INSTRUMENT_SCHEMA,
        "scenario": {
            "steps": steps,
            "change_at": change_at,
            "delay": delay,
            "low": low,
            "high": high,
            "context_available": context_available,
            "tolerance": tolerance,
        },
        "program": {"strategy": strategy, "window": window},
    }
    trace_sha256 = _digest(trace)
    body: dict[str, Any] = {
        "schema": INSTRUMENT_SCHEMA,
        "operation_id": operation_id,
        "world": world,
        "trace": trace,
        "trace_sha256": trace_sha256,
        "metrics": {
            "accuracy": correct / steps,
            "correct_steps": correct,
            "mean_abs_error": mean_abs_error,
            "recovery_delay": recovery,
            "steps": steps,
            "strategy": strategy,
        },
        "external_effects": {
            "network": False,
            "hardware": False,
            "orders": False,
            "writes": ["bounded-local-artifact"],
        },
    }
    artifact_home = _artifact_home(artifact_home)
    artifact_digest = _digest(body)
    artifact_path = artifact_home / f"instrument-{artifact_digest}.json"
    encoded = _canonical_bytes(body) + b"\n"
    if artifact_path.exists():
        if artifact_path.read_bytes() != encoded:
            raise ValueError("instrument artifact identity collision")
    else:
        artifact_path.write_bytes(encoded)
    body["artifact"] = {
        "path": str(artifact_path),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
    }
    evidence = _evidence_with_digest(body)
    predictive_rows = [
        {
            "history": [
                {
                    "measurement": row["measurement"],
                    "context_cue": row["context_cue"],
                }
            ],
            "future": {"target": row["target"]},
            "question": "What is the current instrument level?",
            "context": {"strategy": strategy},
            "action": {},
        }
        for row in trace
    ]
    split = max(2, len(predictive_rows) - 8)
    opportunity = {
        "candidate_id": f"instrument-context:{trace_sha256[:24]}",
        "learning_kind": "predictive-state",
        "expected_gain": max(0.0, 1.0 - float(body["metrics"]["mean_abs_error"])),
        "novelty": 1.0 if strategy != "hold-last" else 0.0,
        "priority": 1.0,
        "cost": float(steps),
        "risk": 0.0,
        "request": {
            "representation_id": f"instrument-context:{trace_sha256[:24]}",
            "signature": {
                "clock_boundary": {
                    "decision_clock": "instrument-step",
                    "outcome_clock": "instrument-step",
                },
                "collection_boundary": {
                    "availability": "complete-generated-trace",
                    "trace_sha256": trace_sha256,
                },
                "comparison_metric": "exact-equality",
                "horizon": 1,
                "interval": {"steps": 1},
                "output_measure": {"coordinates": ["target"], "kind": "json"},
                "prediction_semantics": "constraint-set",
                "probability_model": None,
                "tolerance": tolerance,
                "units": {"target": "instrument-level"},
            },
            "examples": predictive_rows[:split],
            "holdout": predictive_rows[split:],
            "window": window,
        },
    }
    return {
        "status": "observed",
        "summary": (
            f"Instrument strategy {strategy} completed {steps} generated steps "
            f"with accuracy {correct / steps:.6g}."
        ),
        "evidence": evidence,
        "observations": trace,
        "learning_opportunities": [opportunity],
    }


def initial_work(workspace: Path) -> list[dict[str, Any]]:
    """Return reusable bounded obligations for the resident field.

    The market request embeds every bar and initial account parameter.  The
    physics request names only a read command and can truthfully return a
    support-gap when no local CassiCosmos bridge is running.
    """
    del workspace  # Paths are not hidden input; requests are self-contained.
    return [
        {
            "id": "research-worlds:physics:state",
            "kind": PHYSICS_KIND,
            "summary": "Read the current CassiCosmos scalar state without mutation.",
            "request": {
                "operation_id": "research-worlds:physics:state",
                "kind": PHYSICS_KIND,
                "cmd": "state",
                "fields": ["step", "t", "mean_ey", "mean_ei", "max_eps2"],
                "host": "127.0.0.1",
                "port": 7599,
                "timeout": 5.0,
            },
            "metadata": {
                "schema": CATALOG_SCHEMA,
                "read_only": True,
                "support_gap_is_truthful": True,
            },
        },
        {
            "id": "research-worlds:market:synthetic-17",
            "kind": MARKET_KIND,
            "summary": "Advance a deterministic embedded closed-bar market world and expose account consequences.",
            "request": {
                "operation_id": "research-worlds:market:synthetic-17",
                "kind": MARKET_KIND,
                "seed": 17,
                "bars": _catalog_bars(),
                "source": {
                    "kind": "synthetic-local",
                    "source_id": "research-worlds:resident-synth",
                    "source_revision": "synthetic-bars-v1-seed-17",
                    "availability": "all-bars-embedded-before-simulation",
                },
                "warmup_bars": 16,
                "review_interval": 8,
                "initial_equity": 1.0,
                "fee_bps": 10.0,
                "slippage_bps": 5.0,
                "max_position": 1.0,
                "timeframe_hours": 1.0,
            },
            "metadata": {
                "schema": CATALOG_SCHEMA,
                "simulation_only": True,
                "network": False,
                "history_embedded": True,
            },
        },
        {
            "id": "research-worlds:market:synthetic-23",
            "kind": MARKET_KIND,
            "summary": "Advance an alternating-trend synthetic regime with an independent embedded history.",
            "request": {
                "operation_id": "research-worlds:market:synthetic-23",
                "kind": MARKET_KIND,
                "seed": 23,
                "bars": _catalog_bars(seed=23),
                "source": {
                    "kind": "synthetic-local",
                    "source_id": "research-worlds:resident-synth-regime-23",
                    "source_revision": "synthetic-bars-v1-seed-23",
                    "availability": "all-bars-embedded-before-simulation",
                },
                "warmup_bars": 16,
                "review_interval": 8,
                "initial_equity": 1.0,
                "fee_bps": 10.0,
                "slippage_bps": 5.0,
                "max_position": 1.0,
                "timeframe_hours": 1.0,
            },
            "metadata": {
                "schema": CATALOG_SCHEMA,
                "simulation_only": True,
                "network": False,
                "history_embedded": True,
                "regime": "alternating-trend",
            },
        },
    ]


def execute_work(
    request: Mapping[str, Any],
    *,
    workspace: Path,
    artifact_home: Path,
    semantic: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute one bounded research-world operation under the resident contract."""
    del workspace, semantic  # No hidden workspace state or semantic sidecar.
    if not isinstance(request, Mapping):
        return {
            "status": "rejected",
            "summary": "Research-world request must be an object.",
            "evidence": _evidence_with_digest(
                {"schema": "cassi.research-worlds-error.v1", "error_code": "INVALID_REQUEST"}
            ),
        }
    try:
        kind = _text(request.get("kind"), "kind")
        if kind == PHYSICS_KIND:
            return _physics_work(request, artifact_home=Path(artifact_home))
        if kind == MARKET_KIND:
            return _market_work(request, artifact_home=Path(artifact_home))
        if kind == INSTRUMENT_KIND:
            return _instrument_work(request, artifact_home=Path(artifact_home))
        raise ValueError(f"unsupported research-world kind: {kind}")
    except FieldIntelligenceError as exc:
        return {
            "status": "rejected",
            "summary": f"Research-world request was rejected by the read-only contract: {exc}",
            "evidence": _error_evidence(exc, code="INVALID_REQUEST"),
        }
    except (ModuleNotFoundError, ImportError) as exc:
        return {
            "status": "support-gap",
            "summary": f"Required local world implementation is unavailable: {exc}",
            "evidence": _error_evidence(exc, code="IMPLEMENTATION_UNAVAILABLE"),
        }
    except (ValueError, TypeError, KeyError) as exc:
        return {
            "status": "rejected",
            "summary": f"Research-world request is malformed: {exc}",
            "evidence": _error_evidence(exc, code="INVALID_REQUEST"),
        }


__all__ = [
    "CATALOG_SCHEMA",
    "INSTRUMENT_KIND",
    "INSTRUMENT_SCHEMA",
    "MARKET_KIND",
    "MARKET_SCHEMA",
    "PHYSICS_KIND",
    "PHYSICS_SCHEMA",
    "execute_work",
    "initial_work",
]
