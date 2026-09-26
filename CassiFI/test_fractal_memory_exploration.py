"""Direct tests for the fractal-memory exploration runner.

They hold the runner to the properties its receipt claims: the packet view
round-trips inside its declared allowance, analysis-only passes leave the
canonical field byte-identical, every bounded impulse respects its declared work
bound, the receipt digest is deterministic over the measured numbers, and the
retention instrumentation separates two declared damping settings by a declared
margin (a check that fails if the measurement ever loses its resolution).

Everything runs in-process on a compact configuration of the same runner the
receipt is produced by, so a passing run is evidence about the real measurement
rather than about a fixture.
"""

from __future__ import annotations

import numpy as np
import pytest

from cassi_resonant_field import (
    advance_workspace,
    analyze_helical_packet,
    apply_helical_packet_impulse,
    compose_helical_packets,
    helical_packet_channels,
    initial_workspace,
    split_helical_packet,
)
from run_fractal_memory_exploration import (
    EVENT_KIND,
    ExplorationConfig,
    build_receipt,
    page_sha256,
    receipt_digest,
)

COMPACT = ExplorationConfig(
    scale_paths=("", "LL"),
    horizon_ticks=64,
    retention_samples=(16, 64),
    channel_samples=(4, 16, 64),
    altered_settings=(
        ("damping-double", {"damping": 0.024}),
        ("descriptor-only", {"arithmetic": "declared-descriptor-label"}),
    ),
    live_baseline_ticks=16,
    cycle_count=3,
    cycle_ticks=4,
    recovery_horizon_ticks=128,
    recovery_stride_ticks=32,
    integrity_paths=("", "L"),
)

# Declared separation: on the compact configuration the measured difference in
# total packet energy ratio between the default profile and doubled damping is
# ~0.089 on the "LL" rung; the margin below sits well inside that gap and well
# outside run-to-run noise, which is exactly zero.
RETENTION_MARGIN = 0.05


def live_state():
    """A canonical state with both position and momentum content, built by canonical calls."""

    workspace, _advance = advance_workspace(
        initial_workspace(), ticks=COMPACT.live_baseline_ticks, source_enabled=True
    )
    workspace, _impulse = apply_helical_packet_impulse(
        workspace,
        path="",
        component="scale",
        flow_signal=(0.6, -0.8),
        work_budget=1e-3,
        evidence_tick=workspace.evidence_tick,
        event_kind=EVENT_KIND,
    )
    return workspace


@pytest.fixture(scope="module")
def receipt():
    return build_receipt(COMPACT)


def test_packet_view_round_trips_within_the_declared_allowance(receipt) -> None:
    integrity = receipt["view_integrity"]
    allowance = receipt["declared"]["config"]["reconstruction_allowance"]
    assert integrity["within_declared_allowance"]
    assert integrity["maximum_coefficient_reconstruction_error"] <= allowance

    workspace = live_state()
    for path in COMPACT.integrity_paths:
        parent = analyze_helical_packet(workspace, path=path)
        left, right = split_helical_packet(parent)
        recomposed = compose_helical_packets(left, right)
        np.testing.assert_allclose(
            np.asarray(recomposed["coefficients"], dtype=np.float64),
            np.asarray(parent["coefficients"], dtype=np.float64),
            rtol=0.0,
            atol=allowance,
        )
        np.testing.assert_allclose(
            helical_packet_channels(recomposed),
            helical_packet_channels(parent),
            rtol=0.0,
            atol=allowance,
        )
        assert recomposed["coefficient_squared_norm"] == pytest.approx(
            parent["coefficient_squared_norm"], rel=1e-12, abs=1e-15
        )


def test_analysis_only_packet_passes_leave_the_canonical_state_untouched() -> None:
    workspace = live_state()
    state_before = workspace.state_sha256
    page_before = workspace.page_bytes
    page_digest_before = page_sha256(workspace)

    parent = analyze_helical_packet(workspace, path="")
    left, right = split_helical_packet(parent)
    compose_helical_packets(left, right)
    helical_packet_channels(left)
    analyze_helical_packet(workspace, path="LL")

    assert workspace.state_sha256 == state_before
    assert workspace.page_bytes == page_before
    assert page_sha256(workspace) == page_digest_before


def test_impulses_respect_their_declared_energy_bound(receipt) -> None:
    for arm in receipt["scale_retention"]["arms"]:
        impulse = arm["impulse"]
        assert impulse["accepted"]
        assert impulse["requested_work"] == receipt["declared"]["config"]["drive_budget"]
        assert impulse["applied_work"] == pytest.approx(
            impulse["requested_work"], abs=impulse["energy_roundoff_allowance"]
        )
        assert abs(impulse["balance_defect"]) <= impulse["energy_roundoff_allowance"]

    repeated = receipt["repeated_drive"]
    deposited = sum(row["impulse_applied_work"] for row in repeated["cycles"])
    assert repeated["final_ledger"]["helical_packet_work"] == pytest.approx(
        deposited, rel=1e-12, abs=1e-15
    )
    assert deposited == pytest.approx(
        COMPACT.repeated_drive_budget * COMPACT.cycle_count, rel=1e-9, abs=1e-12
    )

    workspace = live_state()
    before = float(workspace.ledger["helical_packet_work"])
    successor, impulse = apply_helical_packet_impulse(
        workspace,
        path="",
        component="scale",
        flow_signal=(1.0, 0.0),
        work_budget=COMPACT.drive_budget,
        evidence_tick=workspace.evidence_tick,
        event_kind=EVENT_KIND,
    )
    assert impulse["applied_work"] == pytest.approx(
        COMPACT.drive_budget, abs=impulse["energy_roundoff_allowance"]
    )
    assert successor.ledger["helical_packet_work"] == pytest.approx(
        before + COMPACT.drive_budget, rel=1e-9, abs=1e-12
    )
    assert successor.state_sha256 != workspace.state_sha256


def test_receipt_digest_is_deterministic_and_covers_the_measurements(receipt) -> None:
    body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    assert receipt["receipt_digest"] == receipt_digest(body)
    assert build_receipt(COMPACT)["receipt_digest"] == receipt["receipt_digest"]

    mutated = {key: value for key, value in body.items()}
    mutated["reading"] = {
        **mutated["reading"],
        "repeated_drive": {
            **mutated["reading"]["repeated_drive"],
            "closure_residual": mutated["reading"]["repeated_drive"]["closure_residual"] + 1.0,
        },
    }
    assert receipt_digest(mutated) != receipt["receipt_digest"]


def test_retention_separates_two_declared_damping_settings(receipt) -> None:
    arms = {arm["arm"]: {rung["scale_path"]: rung for rung in arm["rungs"]} for arm in
            receipt["profile_dependence"]["arms"]}
    default, altered = arms["default"], arms["damping-double"]
    for path in COMPACT.scale_paths:
        assert (
            default[path]["total_energy_ratio"] - altered[path]["total_energy_ratio"]
            >= RETENTION_MARGIN
        )
        assert altered[path]["page_sha256"] != default[path]["page_sha256"]

    # Off-path settings are the zero control: the canonical page is bit-identical
    # and only the declared-profile descriptor moves.
    control = arms["descriptor-only"]
    for path in COMPACT.scale_paths:
        assert control[path]["page_sha256"] == default[path]["page_sha256"]
        assert control[path]["total_energy_ratio"] == default[path]["total_energy_ratio"]
    comparison = next(
        row for row in receipt["profile_dependence"]["comparisons"] if row["arm"] == "descriptor-only"
    )
    assert comparison["any_page_identical_to_default"]
    assert all(not row["state_digest_identical_to_default"] for row in comparison["rungs"])
