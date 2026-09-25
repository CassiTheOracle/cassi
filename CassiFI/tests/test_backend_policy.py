from __future__ import annotations

from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

import backend_policy  # type: ignore[reportMissingImports]
from backend_policy import CostLedger, migration_decision, select_backend  # type: ignore[reportMissingImports]


READY_VULKAN_CAPABILITY = {
    "available": True,
    "device": "AMD Radeon RX 7900 XTX",
    "reason": "ready",
    "operation_groups": "exact-word-operation-groups",
    "word_ops_supported": True,
    "model_runtime_ready": True,
}


def _word_ops_ledger(cpu_seconds: float, vulkan_seconds: float, resident_bytes: int = 4096) -> CostLedger:
    ledger = CostLedger()
    ledger.record(
        "native-cpu", scope="word-ops", work=1000, use_seconds=cpu_seconds,
    )
    ledger.record(
        "vulkan", scope="word-ops", work=1000, use_seconds=vulkan_seconds,
    )
    ledger.record(
        "native-cpu", scope="residency", copy_bytes=resident_bytes,
        copy_seconds=0.001, resident_bytes=resident_bytes,
    )
    ledger.record(
        "vulkan", scope="residency", copy_bytes=resident_bytes,
        copy_seconds=0.001, resident_bytes=resident_bytes,
    )
    return ledger


def test_explicit_policy_is_authoritative() -> None:
    ledger = _word_ops_ledger(0.001, 0.0001)
    selection = select_backend(
        "native-cpu", supported=["native-cpu", "vulkan"], default="vulkan",
        scope="word-ops", current="vulkan", bounded_work=1000, ledger=ledger,
        capability=dict(READY_VULKAN_CAPABILITY),
    )
    assert selection["selected"] == "native-cpu"
    assert selection["reason"] == "explicit-policy"
    assert selection["evidence"] is None


def test_auto_without_evidence_keeps_existing_choice() -> None:
    ledger = CostLedger()
    selection = select_backend(
        "auto", supported=["native-cpu", "vulkan"], default="native-cpu",
        scope="word-ops", current="native-cpu", bounded_work=1000,
        ledger=ledger, capability=dict(READY_VULKAN_CAPABILITY),
    )
    assert selection["selected"] == "native-cpu"
    assert selection["reason"] == "no-cost-evidence-existing-choice"
    assert selection["candidates"] == []


def test_auto_excludes_vulkan_without_capability() -> None:
    ledger = _word_ops_ledger(0.01, 0.001)
    capability = {**READY_VULKAN_CAPABILITY, "available": False}
    selection = select_backend(
        "auto", supported=["native-cpu", "vulkan"], default="native-cpu",
        scope="word-ops", current="native-cpu", bounded_work=1000,
        ledger=ledger, capability=capability,
    )
    assert selection["selected"] == "native-cpu"
    assert "vulkan" not in selection["candidates"]
    assert "vulkan" not in selection["evidence"]["forecast_seconds"]


def test_auto_selects_measured_cheapest_forecast() -> None:
    ledger = _word_ops_ledger(0.02, 0.001)
    selection = select_backend(
        "auto", supported=["native-cpu", "vulkan"], default="native-cpu",
        scope="word-ops", current="native-cpu", bounded_work=1000,
        ledger=ledger, capability=dict(READY_VULKAN_CAPABILITY),
    )
    # Both are measured; the forecast includes the measured residency
    # transfer premium for the vulkan migration, and vulkan's use rate is
    # far cheaper, so the measured forecast selects vulkan.
    assert selection["reason"] == "measured-forecast-beats-costs"
    assert selection["selected"] == "vulkan"
    forecast = selection["evidence"]["forecast_seconds"]
    assert set(forecast) == {"native-cpu", "vulkan"}
    assert forecast["vulkan"] < forecast["native-cpu"]


def test_auto_keeps_current_when_it_ties_or_beats() -> None:
    ledger = _word_ops_ledger(0.001, 0.001)
    selection = select_backend(
        "auto", supported=["native-cpu", "vulkan"], default="native-cpu",
        scope="word-ops", current="native-cpu", bounded_work=1000,
        ledger=ledger, capability=dict(READY_VULKAN_CAPABILITY),
    )
    # Equal measured use rates: migrating to vulkan adds the transfer
    # premium, so the current placement wins.
    assert selection["selected"] == "native-cpu"
    assert selection["reason"] == "measured-forecast-selected"


def test_migration_holds_without_safe_boundary_or_identity() -> None:
    ledger = _word_ops_ledger(0.02, 0.001)
    hold = migration_decision(
        current="native-cpu", candidate="vulkan", scope="field-program",
        bounded_remaining_work=10**9, migration_bytes=4096, ledger=ledger,
        predecessor_state_sha256="a" * 64, expected_state_sha256="b" * 64,
        fence=1, expected_fence=1, boundary_safe=True,
    )
    assert hold["decision"] == "hold"
    assert hold["reason"] == "predecessor-identity-changed"

    fence_hold = migration_decision(
        current="native-cpu", candidate="vulkan", scope="field-program",
        bounded_remaining_work=10**9, migration_bytes=4096, ledger=ledger,
        predecessor_state_sha256="a" * 64, expected_state_sha256="a" * 64,
        fence=1, expected_fence=2, boundary_safe=True,
    )
    assert fence_hold["reason"] == "fence-stale"

    boundary_hold = migration_decision(
        current="native-cpu", candidate="vulkan", scope="field-program",
        bounded_remaining_work=10**9, migration_bytes=4096, ledger=ledger,
        predecessor_state_sha256="a" * 64, expected_state_sha256="a" * 64,
        fence=1, expected_fence=1, boundary_safe=False,
    )
    assert boundary_hold["reason"] == "no-safe-boundary"


def test_migration_holds_without_measured_evidence() -> None:
    ledger = CostLedger()
    ledger.record(
        "vulkan", scope="field-program", work=100, use_seconds=0.001,
    )
    hold = migration_decision(
        current="native-cpu", candidate="vulkan", scope="field-program",
        bounded_remaining_work=10**9, migration_bytes=4096, ledger=ledger,
        predecessor_state_sha256="a" * 64, expected_state_sha256="a" * 64,
        fence=1, expected_fence=1, boundary_safe=True,
    )
    assert hold["decision"] == "hold"
    assert hold["reason"] == "no-cost-evidence"

    ledger.record(
        "native-cpu", scope="field-program", work=100, use_seconds=0.002,
    )
    # Workload use rates exist, but the measured residency transfer
    # infrastructure for the candidate is absent: never migrate unpriced.
    no_transfer = migration_decision(
        current="native-cpu", candidate="vulkan", scope="field-program",
        bounded_remaining_work=10**9, migration_bytes=4096, ledger=ledger,
        predecessor_state_sha256="a" * 64, expected_state_sha256="a" * 64,
        fence=1, expected_fence=1, boundary_safe=True,
    )
    assert no_transfer["decision"] == "hold"
    assert no_transfer["reason"] == "no-measured-migration-cost"


def test_migration_admits_when_bounded_forecast_beats_measured_cost() -> None:
    ledger = _word_ops_ledger(0.02, 0.000001, resident_bytes=4096)
    ledger.record(
        "native-cpu", scope="field-program", work=100, use_seconds=0.02,
    )
    ledger.record(
        "vulkan", scope="field-program", work=100, use_seconds=0.000001,
    )
    decision = migration_decision(
        current="native-cpu", candidate="vulkan", scope="field-program",
        bounded_remaining_work=10**9, migration_bytes=4096, ledger=ledger,
        predecessor_state_sha256="a" * 64, expected_state_sha256="a" * 64,
        fence=1, expected_fence=1, boundary_safe=True,
    )
    assert decision["decision"] == "migrate"
    assert decision["reason"] == "bounded-forecast-beats-measured-migration"
    measured = decision["measured"]
    assert measured["forecast_saving_seconds"] > measured["migration_seconds"]


def test_word_op_coverage_requires_the_exact_group() -> None:
    assert set(("set", "copy", "fill", "compare-set", "add-constant")) <= backend_policy.VULKAN_WORD_OPCODES
    assert "multiply" not in backend_policy.VULKAN_WORD_OPCODES


def test_normalize_capability_matches_the_native_probe_value() -> None:
    # Producer (vulkan_status/probe_vulkan operation_groups tag) and consumer
    # agree on the exact value that gates Vulkan auto-selection.
    probe = {
        "status": "ready",
        "device": "AMD Radeon RX 7900 XTX",
        "reason": "ready",
        "operation_groups": "exact-word-operation-groups",
        "model_runtime": "ready",
    }
    normalized = backend_policy.normalize_capability(probe)
    assert normalized["available"] is True
    assert normalized["word_ops_supported"] is True
    assert normalized["operation_groups"] == "exact-word-operation-groups"
    assert normalized["model_runtime_ready"] is True

    # Already-recorded legacy ledger strings from earlier native builds keep
    # normalizing to the same supported capability.
    legacy = dict(probe, operation_groups="u32-set-fill-nonoverlap-copy-compare-set-add-constant-compute")
    assert backend_policy.normalize_capability(legacy)["word_ops_supported"] is True

    # Unavailable runtimes and a "none"/absent capability never report word ops.
    unavailable = dict(probe, status="unavailable", operation_groups="none")
    assert backend_policy.normalize_capability(unavailable)["word_ops_supported"] is False
    absent = dict(probe, operation_groups=None)
    assert backend_policy.normalize_capability(absent)["word_ops_supported"] is False
