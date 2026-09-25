"""Deterministic heterogeneous market scenarios for transfer experiments."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from cassi_market_contracts import digest_value
from cassi_trading_foundry import MarketBar

SCENARIO_SCHEMA = "cassi.market-scenario.v1"
SCENARIO_MANIFEST_SCHEMA = "cassi.market-scenario-manifest.v1"


class ScenarioError(ValueError):
    """A scenario profile cannot generate valid market bars."""


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScenarioError(f"{name} must be nonempty text")
    return value


def _nonnegative(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScenarioError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ScenarioError(f"{name} must be finite and nonnegative")
    return result


@dataclass(frozen=True, slots=True)
class ScenarioProfile:
    """A bounded deterministic sequence of regime-specific return dynamics."""

    scenario_id: str
    regime_drifts: tuple[float, ...]
    oscillation: float = 0.0012
    phase: float = 1.7
    wick_scale: float = 0.001
    volume_scale: float = 25.0

    def __post_init__(self) -> None:
        _text("scenario_id", self.scenario_id)
        if not isinstance(self.regime_drifts, tuple) or not self.regime_drifts:
            raise ScenarioError("regime_drifts must be a nonempty tuple")
        for drift in self.regime_drifts:
            if isinstance(drift, bool) or not isinstance(drift, (int, float)) or not math.isfinite(float(drift)):
                raise ScenarioError("regime drifts must be finite numbers")
        for name in ("oscillation", "phase", "wick_scale", "volume_scale"):
            _nonnegative(name, getattr(self, name))
        if self.phase == 0.0:
            raise ScenarioError("phase must be positive")
        if self.wick_scale >= 1.0:
            raise ScenarioError("wick_scale must be below one")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCENARIO_SCHEMA,
            "scenario_id": self.scenario_id,
            "regime_drifts": list(self.regime_drifts),
            "oscillation": self.oscillation,
            "phase": self.phase,
            "wick_scale": self.wick_scale,
            "volume_scale": self.volume_scale,
        }


SCENARIO_PROFILES: Mapping[str, ScenarioProfile] = {
    "trend": ScenarioProfile(
        "trend",
        (0.006, 0.005, 0.004, 0.003),
        oscillation=0.0005,
        phase=1.3,
        wick_scale=0.001,
        volume_scale=20.0,
    ),
    "reversal": ScenarioProfile(
        "reversal",
        (0.006, -0.006, 0.006, -0.006),
        oscillation=0.0015,
        phase=1.9,
        wick_scale=0.002,
        volume_scale=40.0,
    ),
    "volatile": ScenarioProfile(
        "volatile",
        (0.003, -0.003, 0.004, -0.004),
        oscillation=0.005,
        phase=2.7,
        wick_scale=0.012,
        volume_scale=90.0,
    ),
    "mean_revert": ScenarioProfile(
        "mean_revert",
        (0.004, -0.004, 0.002, -0.002),
        oscillation=0.003,
        phase=0.8,
        wick_scale=0.003,
        volume_scale=35.0,
    ),
    "positive_jump": ScenarioProfile(
        "positive_jump",
        (0.001, 0.020, 0.002, 0.001),
        oscillation=0.0002,
        phase=1.1,
        wick_scale=0.001,
        volume_scale=20.0,
    ),
}


def build_scenario_manifest(
    assignments: Mapping[str, ScenarioProfile],
    *,
    bar_count: int,
) -> dict[str, Any]:
    if not assignments:
        raise ScenarioError("scenario manifest requires instruments")
    if isinstance(bar_count, bool) or not isinstance(bar_count, int) or bar_count < 32:
        raise ScenarioError("bar_count must be at least 32")
    instruments = []
    for instrument, profile in sorted(assignments.items()):
        _text("instrument", instrument)
        if not isinstance(profile, ScenarioProfile):
            raise ScenarioError("scenario assignments must contain ScenarioProfile values")
        instruments.append(
            {
                "instrument": instrument,
                "profile": profile.as_dict(),
                "bar_count": bar_count,
            }
        )
    manifest: dict[str, Any] = {
        "schema": SCENARIO_MANIFEST_SCHEMA,
        "instruments": instruments,
        "generator": "generate_scenario_bars",
    }
    manifest["content_sha256"] = digest_value(manifest)
    return manifest


def generate_scenario_bars(
    count: int = 240,
    *,
    symbol: str = "SCENARIO",
    profile: ScenarioProfile,
) -> tuple[MarketBar, ...]:
    """Generate deterministic OHLCV bars with intentionally distinct dynamics."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 32:
        raise ScenarioError("scenario market requires at least 32 bars")
    _text("symbol", symbol)
    if not isinstance(profile, ScenarioProfile):
        raise ScenarioError("profile must be a ScenarioProfile")
    price = 100.0
    bars: list[MarketBar] = []
    for index in range(count):
        block = (index // 32) % len(profile.regime_drifts)
        drift = profile.regime_drifts[block]
        oscillation = profile.oscillation * math.sin(index * profile.phase)
        change = drift + oscillation
        opening = price
        closing = opening * (1.0 + change)
        wick = profile.wick_scale * (1.0 + abs(math.sin(index * 0.37 + profile.phase)))
        high = max(opening, closing) * (1.0 + wick)
        low = min(opening, closing) * (1.0 - wick)
        bars.append(
            MarketBar(
                timestamp=f"2025-01-01T{index:04d}Z",
                symbol=symbol,
                open=opening,
                high=high,
                low=low,
                close=closing,
                volume=1000.0 + profile.volume_scale * (index % 11),
            )
        )
        price = closing
    return tuple(bars)


__all__ = [
    "SCENARIO_MANIFEST_SCHEMA",
    "SCENARIO_PROFILES",
    "SCENARIO_SCHEMA",
    "ScenarioError",
    "ScenarioProfile",
    "build_scenario_manifest",
    "generate_scenario_bars",
]
