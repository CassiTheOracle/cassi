"""Direct tests for the fractal-durability exploration runner.

These assert observable behavior: what the canonical workspace round trip does to
the state, what analysis-only reads do to it, what the impulse receipts bound,
what the measured recovery figures say about restart and unrelated activity, and
what the declared source state changes. Nothing here asserts an implementation
detail of the runner.
"""

from __future__ import annotations

import numpy as np
import pytest

from cassi_resonant_field import (
    ResonantProfile,
    analyze_helical_packet,
    initial_workspace,
)

from run_fractal_durability_exploration import (
    ITEM_SPECS,
    ORTHOGONALITY_ALLOWANCE,
    SOURCE_OFF_MARGIN,
    SOURCE_OFF_MULTI_ITEM_COUNTS,
    DurabilityConfig,
    arm_declarations,
    build_receipt,
    capture_items,
    page_sha256,
    read_frame,
    receipt_digest,
    restart_workspace,
    source_off_arm_name,
    source_off_baseline_names,
    write_item,
)

# Bounded configuration for the tests: a short activity horizon, two-item arms
# only, and a small owner probe. Every declared number below is measured on it.
COMPACT = DurabilityConfig(
    activity_ticks=16,
    activity_samples=(8, 16),
    multi_item_counts=(2,),
    owner_probe_ticks=8,
    owner_probe_observations=4,
)

# The declared separation: on this configuration the headline item's recovery
# fraction after unrelated activity is far below its recovery fraction with no
# activity, and both arms are deterministic, so the gap is not noise. The margin
# sits well inside the measured gap.
ACTIVITY_DECAY_MARGIN = 0.05
# The restart legs carry no activity, so the restart arm reproduces the
# immediate arm exactly; the allowance is the declared round-trip identity.
RESTART_IDENTITY_ALLOWANCE = 0.0
# A written item's own share must beat the same-arm control direction by this
# margin or the readout does not distinguish the item from background activity.
CONTROL_MARGIN = 0.05


@pytest.fixture(scope="module")
def receipt():
    return build_receipt(COMPACT)


def test_workspace_round_trip_preserves_the_state_and_the_read_frame() -> None:
    workspace, _impulse = write_item(
        initial_workspace(ResonantProfile()), ITEM_SPECS[0], COMPACT.write_budget
    )
    state_before, page_before = workspace.state_sha256, page_sha256(workspace)
    frame_before = read_frame(workspace, COMPACT.read_frame_path)

    restored, report = restart_workspace(workspace)

    assert report["state_digest_identical"] and report["page_digest_identical"]
    assert restored.state_sha256 == state_before
    assert page_sha256(restored) == page_before
    np.testing.assert_array_equal(read_frame(restored, COMPACT.read_frame_path), frame_before)


def test_analysis_only_reads_leave_the_canonical_state_unchanged() -> None:
    workspace, _impulse = write_item(
        initial_workspace(ResonantProfile()), ITEM_SPECS[0], COMPACT.write_budget
    )
    state_before, page_before = workspace.state_sha256, page_sha256(workspace)

    for _ in range(3):
        analyze_helical_packet(workspace, path=COMPACT.read_frame_path)
        read_frame(workspace, COMPACT.read_frame_path)
        analyze_helical_packet(workspace, path="L")

    assert workspace.state_sha256 == state_before
    assert page_sha256(workspace) == page_before


def test_declared_item_writes_respect_their_energy_bound() -> None:
    profile = ResonantProfile()
    captures = capture_items(COMPACT, profile)
    for capture in captures:
        assert capture["applied_work"] <= COMPACT.write_budget + capture["energy_roundoff_allowance"]
        assert abs(capture["balance_defect"]) <= capture["energy_roundoff_allowance"]
        assert capture["deposited_energy"] > 0.0
    workspace = initial_workspace(profile)
    successor, receipt = write_item(workspace, ITEM_SPECS[0], COMPACT.write_budget)
    assert successor.state_sha256 != workspace.state_sha256
    assert receipt["requested_work"] == COMPACT.write_budget
    assert receipt["accepted"] is True


def test_declared_item_directions_are_orthogonal_within_the_declared_allowance(receipt) -> None:
    overlap = np.asarray(receipt["declared"]["item_direction_overlap_squared_cosine"])
    off_diagonal = overlap[~np.eye(len(ITEM_SPECS), dtype=bool)]
    assert overlap.shape == (len(ITEM_SPECS), len(ITEM_SPECS))
    np.testing.assert_allclose(np.diag(overlap), 1.0, rtol=0.0, atol=1e-12)
    assert off_diagonal.max() <= ORTHOGONALITY_ALLOWANCE
    assert receipt["declared"]["item_directions_mutually_orthogonal"] is True


def test_restart_reproduces_the_immediate_readout_exactly(receipt) -> None:
    arms = receipt["arms"]
    immediate = arms["immediate"]["readout"]
    restarted = arms["restart-no-activity"]["readout"]
    assert arms["restart-no-activity"]["restart"]["state_digest_identical"] is True
    assert arms["restart-and-activity"]["restart"]["state_digest_identical"] is True
    assert abs(immediate["recovery_fraction"] - restarted["recovery_fraction"]) <= RESTART_IDENTITY_ALLOWANCE
    assert immediate["packet_energy"] == restarted["packet_energy"]
    # An unrelated activity leg is not a no-op: the restarted arm and the arm
    # that also works differ, so the restart arm above is not measuring activity.
    assert (
        arms["restart-and-activity"]["readout"]["recovery_fraction"]
        < restarted["recovery_fraction"]
    )


def test_unrelated_activity_decays_the_written_direction(receipt) -> None:
    arms = receipt["arms"]
    written = arms["immediate"]["readout"]["recovery_fraction"]
    worked = arms["activity-no-restart"]["readout"]["recovery_fraction"]
    restart_worked = arms["restart-and-activity"]["readout"]["recovery_fraction"]
    assert written == pytest.approx(1.0, abs=1e-9)
    assert written - worked >= ACTIVITY_DECAY_MARGIN
    assert restart_worked == pytest.approx(worked, abs=RESTART_IDENTITY_ALLOWANCE)
    # The activity is real work on the canonical field, not a no-op read: the
    # canonical heartbeat and sources did work while the field advanced.
    assert arms["activity-no-restart"]["activity"]["dissipated_work_total"] > 0.0
    assert arms["activity-no-restart"]["activity"]["positive_heartbeat_work_total"] > 0.0
    assert arms["activity-no-restart"]["activity"]["source_enabled"] is True
    assert arms["activity-no-restart"]["activity"]["field_ticks"] == COMPACT.activity_ticks
    assert arms["restart-no-activity"]["activity"]["positive_heartbeat_work_total"] == 0.0
    # The per-tick series agrees with the endpoint readout it ends on.
    series = receipt["reading"]["activity_series"]["activity-no-restart"]
    assert [row["tick"] for row in series] == list(COMPACT.activity_samples)
    assert series[-1]["written_item_share"] == pytest.approx(worked, rel=0.0, abs=1e-12)
    assert series[-1]["control_share"] == pytest.approx(
        arms["activity-no-restart"]["readout"]["control_share"], rel=0.0, abs=1e-12
    )


def test_written_item_is_distinguishable_from_its_control_after_activity(receipt) -> None:
    readout = receipt["arms"]["activity-no-restart"]["readout"]
    assert readout["control_item"] is not None
    assert readout["control_item"] != readout["written_items"][0]
    assert readout["control_share"] is not None
    assert readout["recovery_fraction"] - readout["control_share"] >= CONTROL_MARGIN
    assert readout["distinguishable_from_control"] is True
    # The no-item arm is the background control: nothing was written, so its
    # recovery fraction is undefined rather than zero.
    empty = receipt["arms"]["no-item-restart-and-activity"]["readout"]
    assert empty["written_items"] == []
    assert empty["recovery_fraction"] is None
    assert empty["distance_from_pre_activity"] > 0.0


def test_multi_item_arms_report_per_item_shares_and_cross_item_confusion(receipt) -> None:
    for name in ("restart-only-k2", "restart-and-activity-k2"):
        readout = receipt["arms"][name]["readout"]
        assert sorted(readout["own_shares"]) == sorted(readout["written_items"])
        assert len(readout["written_items"]) == 2
        assert set(readout["cross_item_confusion"]) == set(readout["written_items"])
        for written, row in readout["cross_item_confusion"].items():
            assert set(row) == {spec.name for spec in ITEM_SPECS}
            assert row[written] == pytest.approx(readout["own_shares"][written], rel=0.0, abs=1e-12)
        fractions = readout["declared_frame_energy_fraction"]
        assert sum(fractions.values()) == pytest.approx(1.0, rel=1e-9)
        assert all(value >= 0.0 for value in fractions.values())
        assert readout["recovery_fraction"] == min(readout["own_shares"].values())
    # Writing items into an already written field deposits a different amount
    # than the isolated capture; the receipt reports that, not hides it, and the
    # written direction still lands on its own axis when nothing else happens.
    multi = receipt["arms"]["restart-only-k2"]
    attenuation = multi["deposit_attenuation"]
    assert set(attenuation) == {"root-scale", "root-detail"}
    assert attenuation["root-scale"] == pytest.approx(1.0, rel=0.05)
    assert multi["readout"]["recovery_fraction"] == pytest.approx(1.0, abs=1e-9)
    worked = receipt["arms"]["restart-and-activity-k2"]["readout"]["recovery_fraction"]
    assert worked < multi["readout"]["recovery_fraction"]


def test_recovery_figures_are_deterministic(receipt) -> None:
    second = build_receipt(COMPACT)
    assert receipt["receipt_digest"] == second["receipt_digest"]
    for arm, body in receipt["arms"].items():
        assert body["readout"]["recovery_fraction"] == second["arms"][arm]["readout"]["recovery_fraction"]
        assert body["readout"]["distance_from_pre_activity"] == (
            second["arms"][arm]["readout"]["distance_from_pre_activity"]
        )
        for row, other in zip(body["activity_rows"], second["arms"][arm]["activity_rows"]):
            assert row["written_item_share"] == other["written_item_share"]


def test_receipt_digest_is_deterministic_and_covers_the_measurements(receipt) -> None:
    body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    assert receipt_digest(body) == receipt["receipt_digest"]

    mutated = {**body}
    arms = {name: dict(arm) for name, arm in body["arms"].items()}
    readout = dict(arms["activity-no-restart"]["readout"])
    readout["recovery_fraction"] = readout["recovery_fraction"] + 0.25
    arms["activity-no-restart"]["readout"] = readout
    mutated["arms"] = arms
    assert receipt_digest(mutated) != receipt["receipt_digest"]

    dropped = {key: value for key, value in body.items() if key != "boundary"}
    assert receipt_digest(dropped) != receipt["receipt_digest"]


def test_owner_probe_states_what_is_reachable_and_what_is_not(receipt) -> None:
    probe = receipt["owner_probe"]
    assert probe["status"] == "reachable"
    assert probe["workspace_state_sha256_preserved_across_restart"] is True
    assert probe["prepared_query_restart_stable"] is True
    assert probe["prepared_query_addressed_written_packet"] is False
    assert probe["packet_impulse_transition_available"] is False
    assert receipt["restart_identity"]["owner_checkpoint_carries_written_item"] is False
    assert "no packet-impulse operation" in probe["reason"]


# --------------------------------------------------------------------------
# declared source state
# --------------------------------------------------------------------------
def test_source_off_counterparts_write_restart_and_read_exactly_like_their_baselines(
    receipt,
) -> None:
    arms = receipt["arms"]
    declared = {row["arm"]: row for row in receipt["declared"]["declared_arms"]}
    names = source_off_baseline_names(COMPACT)
    assert names, "the declared configuration must declare source-off counterparts"
    for name in names:
        counterpart = source_off_arm_name(name)
        assert counterpart in arms and counterpart in declared
        base_declared = declared[name]
        off_declared = declared[counterpart]
        # The counterpart differs from its baseline in the source state alone.
        assert off_declared["source_enabled"] is False
        assert base_declared["source_enabled"] is True
        assert off_declared["written_items"] == base_declared["written_items"]
        assert off_declared["restart"] is base_declared["restart"]
        assert off_declared["activity"] is base_declared["activity"]
        assert arms[counterpart]["declared"]["source_enabled"] is False
        assert [row["tick"] for row in arms[counterpart]["activity_rows"]] == [
            row["tick"] for row in arms[name]["activity_rows"]
        ]
        assert (
            arms[counterpart]["readout"]["written_items"]
            == arms[name]["readout"]["written_items"]
        )
        # The write leg is identical, so the deposit and its attenuation agree.
        assert arms[counterpart]["measured_deposit_energy"] == arms[name]["measured_deposit_energy"]
        assert arms[counterpart]["deposit_attenuation"] == arms[name]["deposit_attenuation"]
    # The declared production configuration declares the k = 2 and k = 4
    # counterparts the attribution question needs.
    production = {arm.name for arm in arm_declarations(DurabilityConfig())}
    for count in SOURCE_OFF_MULTI_ITEM_COUNTS:
        assert source_off_arm_name(f"restart-and-activity-k{count}") in production


def test_source_off_stops_the_heartbeat_work_and_leaves_the_body_advancing(receipt) -> None:
    arms = receipt["arms"]
    on = arms["restart-and-activity"]
    off = arms["restart-and-activity-sources-off"]
    # The source is the heartbeat's positive work and nothing else: it is absent
    # in the source-off arm and present in the source-on arm.
    assert on["activity"]["positive_heartbeat_work_total"] > 0.0
    assert off["activity"]["positive_heartbeat_work_total"] == 0.0
    assert receipt["source_control"]["largest_source_off_source_work"] == 0.0
    assert receipt["source_control"]["smallest_positive_source_work"] > 0.0
    # The body still integrates and dissipates with the source off, so the arm is
    # a quiet body rather than a stopped one.
    assert off["activity"]["dissipated_work_total"] > 0.0
    assert off["activity"]["field_ticks"] == on["activity"]["field_ticks"] == COMPACT.activity_ticks
    # The clocks are not part of the source: both advance identically.
    for on_row, off_row in zip(on["activity_rows"], off["activity_rows"]):
        assert on_row["source_enabled"] is True and off_row["source_enabled"] is False
        assert off_row["heartbeat_phase"] == on_row["heartbeat_phase"]
        assert off_row["breath_phase"] == on_row["breath_phase"]
        assert off_row["field_ticks"] == on_row["field_ticks"]
    # Every declared source-off activity arm reports an empty source.
    for name, arm in arms.items():
        if arm["declared"]["activity"] and not arm["declared"]["source_enabled"]:
            assert arm["activity"]["positive_heartbeat_work_total"] == 0.0, name
            assert arm["activity"]["source_enabled"] is False, name
    # The declared source-off arms write nothing new into the frame either: the
    # no-item pair's read frame is unchanged by the source state being off.
    background = next(
        row for row in receipt["source_contrast"]["pairs"] if row["arm"].startswith("no-item")
    )
    assert background["sources_off_distance_from_pre_activity"] == 0.0
    assert background["sources_on_distance_from_pre_activity"] > 0.0


@pytest.fixture(scope="module")
def declared_receipt():
    """The declared production configuration: the horizon the source-off margin is exercised on.

    The compact configuration stops at 16 ticks, where the two source states agree
    to about 0.002 — below the declared 0.01 margin — so the declared separation is
    measured on the declared 64-tick horizon the receipt itself reports.
    """

    return build_receipt(DurabilityConfig())


def test_the_two_source_states_separate_the_read_tick_recovery_by_the_declared_margin(
    declared_receipt,
) -> None:
    contrast = declared_receipt["source_contrast"]
    assert contrast["declared_margin"] == SOURCE_OFF_MARGIN
    single = next(
        row for row in contrast["pairs"] if row["arm"] == contrast["single_item_arm"]
    )
    assert single["contrast_figure"] == "recovery_fraction"
    assert single["read_tick"] == DurabilityConfig().activity_ticks
    # The derived figure is the difference of the two arms' own readouts at the
    # same tick, not an independent measurement.
    assert single["recovery_fraction_difference"] == (
        single["sources_on_recovery_fraction"] - single["sources_off_recovery_fraction"]
    )
    # The two arms can differ, and at the declared horizon they do: the margin is
    # exercised rather than reported beside an agreement.
    assert abs(single["recovery_fraction_difference"]) >= SOURCE_OFF_MARGIN
    assert single["separated_by_margin"] is True
    assert abs(contrast["minimum_multi_item_difference"]) >= SOURCE_OFF_MARGIN
    assert contrast["minimum_multi_item_separated_by_margin"] is True
    assert contrast["minimum_multi_item_difference"] == min(
        contrast["multi_item_differences"].values()
    )
    # The source state moves the frame's total energy far more than it moves the
    # written direction, which is what the attribution reading rests on.
    assert abs(single["total_packet_energy_ratio_difference"]) > abs(
        single["recovery_fraction_difference"]
    )
    for name, arm in declared_receipt["arms"].items():
        if arm["declared"]["activity"] and not arm["declared"]["source_enabled"]:
            assert arm["activity"]["positive_heartbeat_work_total"] == 0.0, name


def test_alignment_versus_energy_reading_names_the_measured_direction(declared_receipt) -> None:
    block = declared_receipt["source_contrast"]["alignment_versus_energy"]
    margin = block["margin"]
    assert block["per_arm"], "the reading must cover the declared activity arms"
    for name, reading in block["per_arm"].items():
        difference = reading["alignment_retention_at_read"] - reading["energy_retention_at_read"]
        assert difference == reading["alignment_minus_energy"]
        assert reading["falls_faster_than_energy"] is (difference <= -margin)
        assert reading["falls_slower_than_energy"] is (difference >= margin)
        assert reading["same_rate_as_energy"] is (abs(difference) < margin)
        assert [row["tick"] for row in reading["series"]][-1] == reading["read_tick"]
    off = block["per_arm"]["restart-and-activity-sources-off"]
    on = block["per_arm"]["restart-and-activity"]
    assert on["read_tick"] == off["read_tick"]
    # With the source off the direction still loses most of its share while the
    # frame keeps most of its energy, so the comparison the attribution rests on
    # has a direction rather than an agreement.
    assert off["falls_faster_than_energy"] is True
    assert off["alignment_retention_at_read"] < off["energy_retention_at_read"] - margin
    sentence = declared_receipt["reading"]["source_off_alignment_sentence"]
    assert off["falls_faster_than_energy"] is True and "faster than" in sentence
    assert repr(off["alignment_retention_at_read"]) in sentence
    assert repr(off["energy_retention_at_read"]) in sentence
