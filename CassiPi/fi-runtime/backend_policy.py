"""Whole-request backend selection from measured costs (performance item 13).

The policy is deterministic and measurement-bound, never a learned planner:

- An explicit placement or backend policy stays authoritative.
- An ``auto`` request selects one backend for its whole lifetime from
  measured evidence only: the shared cost ledger (observed setup, source
  and destination transfer, residency bytes, and use seconds per unit of
  observed work) plus the probed Vulkan capability.  A request without
  complete cost evidence keeps the existing default choice; the policy
  never invents a performance number.
- Migration between placements is admitted only at a safe boundary with
  an exact predecessor identity, a bounded remaining-work forecast, and a
  measured migration cost (setup plus a copy charged on both source and
  destination) that the forecast strictly beats.  Both representations
  stay reserved until the fence confirms the destination.
- Only placements that actually execute the requested arithmetic are
  eligible.  The native Vulkan path runs the exact u32 word-operation
  group (set, copy, fill, compare-set, add-constant) only, so anything
  else stays on CPU even when a Vulkan device is available.
"""
from __future__ import annotations

import threading
from typing import Any, Mapping

__all__ = [
    "AUTO_POLICY",
    "VULKAN_WORD_OPCODES",
    "WORD_OPERATION_GROUPS",
    "CostLedger",
    "LEDGER",
    "migration_decision",
    "normalize_capability",
    "observed_capability",
    "observed_cost",
    "record_capability",
    "record_cost",
    "select_backend",
]

AUTO_POLICY = "auto"
VULKAN_WORD_OPCODES = frozenset({"set", "copy", "fill", "compare-set", "add-constant"})

# The one capability value the native probe/status path emits for an
# available Vulkan runtime, plus the equivalent legacy string older native
# builds recorded into cost ledgers; both denote the exact u32
# word-operation group, so already-recorded ledger entries stay usable.
WORD_OPERATION_GROUPS = frozenset({
    "exact-word-operation-groups",
    "u32-set-fill-nonoverlap-copy-compare-set-add-constant-compute",
})


def normalize_capability(probe: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Normalize a native runtime ``probe_vulkan``/``status`` report."""

    if not isinstance(probe, Mapping):
        return {
            "available": False,
            "device": None,
            "reason": "no-probe",
            "operation_groups": None,
            "word_ops_supported": False,
            "model_runtime_ready": False,
        }
    provided_available = probe.get("available")
    available = str(probe.get("status", "")) == "ready" or str(probe.get("vulkan", "")) == "ready"
    if isinstance(provided_available, bool):
        # A measured trial observation (e.g. a contract disagreement) can
        # demote a ready probe; the measurement wins over the probe string.
        available = available and provided_available
    reason = str(probe.get("reason", "") or probe.get("vulkan_reason", "") or "")
    device = probe.get("device") or probe.get("vulkan_device")
    groups = probe.get("operation_groups")
    word_ops = available and str(groups or "") in WORD_OPERATION_GROUPS
    return {
        "available": bool(available),
        "device": str(device) if device else None,
        "reason": reason or ("ready" if available else "unavailable"),
        "operation_groups": str(groups) if groups else None,
        "word_ops_supported": bool(word_ops),
        "model_runtime_ready": str(probe.get("model_runtime", "")) == "ready",
    }


class CostLedger:
    """Observed setup/transfer/residency/use counters, never estimates.

    Each entry holds measured running sums; ``observed`` exposes only
    derived per-work and per-byte rates computed from those sums, and
    returns ``None`` until at least one observed use sample exists.
    """

    _FIELDS = (
        "work", "use_seconds", "copy_bytes", "copy_seconds",
        "setup_seconds", "resident_bytes",
    )

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[tuple[str, str], dict[str, float]] = {}
        self._capability: dict[str, Any] | None = None

    def record(
        self,
        placement: str,
        *,
        scope: str,
        work: int | float | None = None,
        use_seconds: float | None = None,
        copy_bytes: int | None = None,
        copy_seconds: float | None = None,
        setup_seconds: float | None = None,
        resident_bytes: int | None = None,
    ) -> None:
        if not placement or not isinstance(placement, str):
            raise ValueError("cost ledger requires a placement name")
        if not scope or not isinstance(scope, str):
            raise ValueError("cost ledger requires a workload scope")
        with self._lock:
            entry = self._entries.setdefault(
                (str(scope), str(placement)),
                {field: 0.0 for field in self._FIELDS},
            )
            for name, value in (
                ("work", work),
                ("use_seconds", use_seconds),
                ("copy_bytes", copy_bytes),
                ("copy_seconds", copy_seconds),
                ("setup_seconds", setup_seconds),
                ("resident_bytes", resident_bytes),
            ):
                if value is None:
                    continue
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                    raise ValueError(f"cost ledger field {name!r} must be a nonnegative number")
                entry[name] = float(entry[name]) + float(value)

    def observed(self, placement: str, *, scope: str) -> Mapping[str, Any] | None:
        """Measured per-work and per-byte rates, or ``None`` without samples."""

        with self._lock:
            entry = self._entries.get((str(scope), str(placement)))
            if entry is None:
                return None
            work = entry["work"]
            if work <= 0 or entry["use_seconds"] <= 0:
                return None
            return {
                "use_seconds_per_work": entry["use_seconds"] / work,
                "copy_seconds_per_byte": (
                    entry["copy_seconds"] / entry["copy_bytes"]
                    if entry["copy_bytes"] > 0 and entry["copy_seconds"] > 0
                    else None
                ),
                "setup_seconds": entry["setup_seconds"],
                "resident_bytes": entry["resident_bytes"],
                "work": work,
                "use_seconds": entry["use_seconds"],
                "samples": 1 if work > 0 else 0,
            }

    def transfer(self, placement: str, *, scope: str = "residency") -> Mapping[str, Any] | None:
        """Measured migration infrastructure rates, independent of workload.

        Residency attach measurements (setup plus the source/destination
        copy of the resident image) are scope-independent placement costs,
        so they are read from the ``residency`` scope without requiring a
        use sample.
        """

        with self._lock:
            entry = self._entries.get((str(scope), str(placement)))
            if entry is None:
                return None
            if (
                entry["copy_bytes"] <= 0 or entry["copy_seconds"] <= 0
                or entry["resident_bytes"] <= 0
            ):
                return None
            return {
                "copy_seconds_per_byte": entry["copy_seconds"] / entry["copy_bytes"],
                "setup_seconds": entry["setup_seconds"],
                "resident_bytes": entry["resident_bytes"],
            }

    def capability(self) -> Mapping[str, Any] | None:
        with self._lock:
            return dict(self._capability) if self._capability is not None else None

    def set_capability(self, capability: Mapping[str, Any]) -> None:
        with self._lock:
            self._capability = dict(capability)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._capability = None


LEDGER = CostLedger()


def record_cost(
    placement: str,
    *,
    scope: str,
    work: int | float | None = None,
    use_seconds: float | None = None,
    copy_bytes: int | None = None,
    copy_seconds: float | None = None,
    setup_seconds: float | None = None,
    resident_bytes: int | None = None,
) -> None:
    LEDGER.record(
        placement,
        scope=scope,
        work=work,
        use_seconds=use_seconds,
        copy_bytes=copy_bytes,
        copy_seconds=copy_seconds,
        setup_seconds=setup_seconds,
        resident_bytes=resident_bytes,
    )


def record_capability(capability: Mapping[str, Any]) -> None:
    LEDGER.set_capability(normalize_capability(capability))


def observed_cost(placement: str, *, scope: str) -> Mapping[str, Any] | None:
    return LEDGER.observed(placement, scope=scope)


def observed_capability() -> Mapping[str, Any] | None:
    return LEDGER.capability()


def _forecast_total(observed: Mapping[str, Any], bounded_work: int) -> float | None:
    use = observed.get("use_seconds_per_work")
    if use is None:
        return None
    return float(use) * float(bounded_work)


def select_backend(
    requested: str,
    *,
    supported,
    default: str,
    scope: str,
    current: str | None = None,
    bounded_work: int | None = None,
    capability: Mapping[str, Any] | None = None,
    ledger: CostLedger = LEDGER,
) -> dict[str, Any]:
    """Choose one backend for a whole request from measured evidence.

    ``supported`` is the caller's list of placements that can actually
    execute this request's arithmetic, in preference order.  Staying on the
    current placement costs no setup or transfer; another placement pays
    its measured setup plus a measured both-ends copy of the resident
    bytes.  The cheapest measured total wins; nothing measured, nothing
    chosen outside ``default``.
    """

    normalized_capability = (
        dict(capability) if capability is not None else ledger.capability()
    )
    if requested != AUTO_POLICY:
        return {
            "requested": requested,
            "selected": requested,
            "reason": "explicit-policy",
            "evidence": None,
            "candidates": [],
            "capability": normalized_capability,
        }
    if bounded_work is not None and (isinstance(bounded_work, bool) or bounded_work < 0):
        raise ValueError("bounded_work must be a nonnegative integer")
    eligible: list[dict[str, Any]] = []
    for name in dict.fromkeys(str(item) for item in supported):
        if name == "vulkan":
            if normalized_capability is None or not normalized_capability.get("available"):
                continue
        observed = ledger.observed(name, scope=scope)
        if observed is None:
            continue
        total = _forecast_total(observed, bounded_work) if bounded_work is not None else None
        if total is None:
            continue
        if current is not None and name != current:
            # A migration pays the measured residency attach: setup plus the
            # transfer charged on both the source and the destination. Those
            # rates are scope-independent infrastructure, so they are read
            # from the residency ledger; without a measured sample the
            # switch cannot be priced honestly and is skipped.
            transfer = ledger.transfer(name)
            if transfer is None:
                continue
            total += float(transfer["setup_seconds"]) + 2.0 * (
                float(transfer["copy_seconds_per_byte"])
                * float(transfer["resident_bytes"])
            )
        eligible.append({"placement": name, "forecast_seconds": total})
    if not eligible:
        return {
            "requested": requested,
            "selected": default,
            "reason": "no-cost-evidence-existing-choice",
            "evidence": None,
            "candidates": [],
            "capability": normalized_capability,
        }
    best = min(eligible, key=lambda row: (row["forecast_seconds"], supported.index(row["placement"]) if row["placement"] in supported else len(supported)))
    hold = next((row for row in eligible if row["placement"] == current), None)
    if (
        current is not None
        and hold is not None
        and best["placement"] != current
        and best["forecast_seconds"] >= hold["forecast_seconds"]
    ):
        selected, reason = current, "current-placement-ties-or-beats"
    elif current is not None and best["placement"] != current:
        selected, reason = best["placement"], "measured-forecast-beats-costs"
    else:
        selected, reason = best["placement"], "measured-forecast-selected"
    return {
        "requested": requested,
        "selected": selected,
        "reason": reason,
        "evidence": {
            "scope": scope,
            "bounded_work": bounded_work,
            "forecast_seconds": {
                row["placement"]: row["forecast_seconds"] for row in eligible
            },
        },
        "candidates": [row["placement"] for row in eligible],
        "capability": normalized_capability,
    }


def migration_decision(
    *,
    current: str,
    candidate: str,
    scope: str,
    bounded_remaining_work: int | None,
    migration_bytes: int,
    ledger: CostLedger = LEDGER,
    predecessor_state_sha256: str | None = None,
    expected_state_sha256: str | None = None,
    fence: int | None = None,
    expected_fence: int | None = None,
    boundary_safe: bool = False,
) -> dict[str, Any]:
    """Admit a backend move only when identity, boundary and cost all hold."""

    hold = {
        "decision": "hold",
        "current": current,
        "candidate": candidate,
        "reason": None,
        "measured": None,
    }
    if not boundary_safe:
        hold["reason"] = "no-safe-boundary"
        return hold
    if (
        predecessor_state_sha256 is not None
        and expected_state_sha256 is not None
        and predecessor_state_sha256 != expected_state_sha256
    ):
        hold["reason"] = "predecessor-identity-changed"
        return hold
    if fence is not None and expected_fence is not None and fence != expected_fence:
        hold["reason"] = "fence-stale"
        return hold
    candidate_observed = ledger.observed(candidate, scope=scope)
    current_observed = ledger.observed(current, scope=scope)
    if candidate_observed is None or current_observed is None or bounded_remaining_work is None:
        hold["reason"] = "no-cost-evidence"
        return hold
    # Transfer infrastructure is scope-independent: setup and per-byte copy
    # come from the measured residency attach, never from the workload scope.
    transfer = ledger.transfer(candidate)
    if transfer is None:
        hold["reason"] = "no-measured-migration-cost"
        return hold
    migration_seconds = float(transfer["setup_seconds"]) + float(
        transfer["copy_seconds_per_byte"]
    ) * float(migration_bytes)
    per_work_saving = current_observed["use_seconds_per_work"] - candidate_observed["use_seconds_per_work"]
    forecast_saving = per_work_saving * float(bounded_remaining_work)
    hold["measured"] = {
        "scope": scope,
        "migration_seconds": migration_seconds,
        "forecast_saving_seconds": forecast_saving,
        "bounded_remaining_work": bounded_remaining_work,
    }
    if forecast_saving <= migration_seconds:
        hold["reason"] = "forecast-does-not-beat-measured-migration"
        return hold
    return {
        "decision": "migrate",
        "current": current,
        "candidate": candidate,
        "reason": "bounded-forecast-beats-measured-migration",
        "measured": hold["measured"],
    }
