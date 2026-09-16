"""Tests for the owner write path, its read half, and the write -> hold -> read cycle.

The contract under test is the transition this workstream added: a written packet
impulse enters the field through ``FieldIntelligenceOwner.write_packet_impulse``,
publishes one immutable successor, is exactly-once under its operation identity,
keeps the evidence clock, carries the written pattern across a restart, and is
the same write as the existing aimed narrow-path route. The read half is the
owner's ``read_packet_deposit`` operation: it names a written direction exactly as
the write names it, returns the deposit the canonical page carries along that
direction, agrees with the library's own route to the same number, misses on a
blank page and on an unwritten direction, and is declared as the design declares
a readout -- a temporal prediction that moves neither the page nor either clock
and is reachable through the surface dispatch. The measured blocks of the
exploration receipt are asserted beside it, including their can-fail controls, so
a change that makes the write inert, that lets the zero-work control through,
that lets a read recover a direction it never read, or that turns the diagnosis
into an assumption fails here.

The receipt is built once at a compact declared horizon (the same profile, items,
budget and loop as the shipped receipt, with the long-horizon floor lowered to
that horizon) so the whole file stays well inside a minute.
"""

from __future__ import annotations

import shutil

import numpy as np
import pytest

import run_fractal_durability_exploration as durability
import run_fractal_feedback_exploration as feedback
from cassi_field_owner import FieldIntelligenceOwner
from run_owner_write_path_exploration import (
    DRIFT_ARM,
    OWNER_HOLD_ARM,
    READ_ONLY_SURFACE_OPERATIONS,
    OwnerWritePathConfig,
    build_receipt,
    dispatch_operations,
    flat_profile,
    open_owner,
    owner_write_items,
    receipt_digest,
)

# The declared compact test configuration: the same profile, items, budget, loop
# and phase as the shipped receipt, with the declared long horizon lowered to the
# refinement horizon and its multiplex block halved, which is the shortest
# declared schedule the feedback harness's own config validation admits. It keeps
# the whole file inside a minute without changing any measured quantity's meaning.
COMPACT = OwnerWritePathConfig(
    long_horizon_ticks=64,
    long_horizon_min_ticks=64,
    capacity_alternate_block_ticks=32,
    sample_every_ticks=16,
)


@pytest.fixture(scope="module")
def receipt():
    return build_receipt(COMPACT)


@pytest.fixture(scope="module")
def profile():
    return flat_profile()


def test_owner_write_path_is_a_transition_on_the_field(receipt) -> None:
    impulse = receipt["impulse"]
    arm = impulse["impulse_arm"]
    assert impulse["margin"] == COMPACT.impulse_deposit_fraction
    assert arm["deposit_fraction_of_captured"] >= impulse["margin"]
    assert impulse["impulse_arm_passes"]
    assert arm["page_digest_changed"] and arm["state_digest_changed"]
    assert arm["page_sha256_before"] != arm["page_sha256_after"]
    assert arm["logical_tick_unchanged"] and arm["evidence_tick_unchanged"]
    assert arm["field_ticks_unchanged"]
    assert arm["generation_after"] == arm["generation_before"] + 1
    write = arm["writes"][0]
    assert write["accepted"] and write["event_kind"] == COMPACT.event_kind
    assert write["balance_defect"] == pytest.approx(
        0.0, abs=write["requested_work"] * 1e-12
    )
    assert arm["ledger_after"]["helical_packet_work"] == pytest.approx(
        arm["ledger_after"]["stored_energy"], rel=1e-12, abs=1e-15
    )


def test_zero_work_control_leaves_the_field_and_fails_the_predicate(receipt) -> None:
    control = receipt["impulse"]["zero_impulse_control"]
    assert receipt["impulse"]["zero_impulse_control_must_fail"]
    assert not control["accepted"]
    assert control["read_frame_deposit"] == 0.0
    assert control["deposit_fraction_of_captured"] < COMPACT.impulse_deposit_fraction
    assert not receipt["impulse"]["zero_impulse_control_passes"]
    assert control["page_digest_unchanged"] and control["state_digest_unchanged"]
    assert control["page_sha256_before"] == control["page_sha256_after"]
    assert control["logical_tick_unchanged"]


def test_the_write_contract_is_exactly_once_with_a_lineage_check(receipt) -> None:
    contract = receipt["owner_contract"]
    assert contract["first_accepted"] and not contract["first_replayed"]
    assert contract["first_generation"] == contract["generation_before"] + 1
    assert contract["write_keeps_the_evidence_clock"]
    assert contract["write_keeps_the_logical_tick"]
    assert contract["replay_replayed"] and contract["replay_does_not_write_again"]
    assert contract["replay_returns_the_retained_receipt"]
    assert contract["replay_generation"] == contract["first_generation"]
    assert contract["conflicting_call_refused"]
    assert contract["conflicting_call_error"].startswith("FieldIntelligenceError")
    assert contract["stale_predecessor_refused"]
    assert contract["stale_predecessor_error"].startswith("FieldIntelligenceError")
    assert contract["matching_predecessor_accepted"]
    assert contract["predecessor_stamp_is_the_atlas_state_digest"]


def test_the_written_page_survives_an_owner_restart(receipt, profile) -> None:
    contract = receipt["owner_contract"]
    assert contract["state_digest_preserved_at_close"]
    assert contract["page_digest_preserved_at_close"]
    assert contract["read_frame_bit_identical_at_close"]
    assert contract["read_frame_max_abs_difference_at_close"] == 0.0
    assert contract["generation_preserved_at_close"]
    assert contract["logical_tick_preserved_at_close"]
    assert contract["evidence_tick_preserved_at_close"]
    assert contract["reopened_state_sha256"] == contract["state_at_close_sha256"]
    assert contract["reopened_page_sha256"] == contract["page_at_close_sha256"]
    assert (
        contract["page_at_close_sha256"] != contract["first_write_page_sha256"]
    )

    # The same restart identity, asserted against the library directly: the owner
    # reopened from its data home hands back the written page, not a fresh field.
    spec = durability.ITEM_SPECS[COMPACT.headline_item_index]
    owner, home = open_owner(profile)
    try:
        first = owner_write_items(owner, (COMPACT.headline_item_index,), COMPACT, "test")
        workspace = owner.state.resonant_workspace
        state_before = workspace.state_sha256
        page_before = durability.page_sha256(workspace)
        frame_before = durability.read_frame(workspace, COMPACT.read_frame_path)
        owner.close()
        restored = FieldIntelligenceOwner(home)
        try:
            reopened = restored.state.resonant_workspace
            assert reopened.state_sha256 == state_before
            assert durability.page_sha256(reopened) == page_before
            np.testing.assert_array_equal(
                durability.read_frame(reopened, COMPACT.read_frame_path), frame_before
            )
        finally:
            restored.close()
    finally:
        shutil.rmtree(home, ignore_errors=True)
    assert first["writes"][0]["item"] == spec.name


def test_the_owner_route_is_the_same_write_as_the_existing_route(receipt) -> None:
    identity = receipt["route_identity"]
    assert identity["items"] == [
        "root-scale",
        "left-detail",
    ]
    assert identity["allowance"] == 0.0
    assert identity["page_digest_identical"]
    assert identity["state_digest_identical"]
    assert identity["ledger_identical"]
    assert identity["read_frame_max_abs_difference"] == 0.0
    assert identity["owner_page_sha256"] == identity["existing_route_page_sha256"]
    assert identity["owner_deposits"] == identity["existing_route_deposits"]


def test_the_input_realization_is_measured_inert_with_a_firing_control(receipt) -> None:
    diagnosis = receipt["diagnosis"]
    declared = diagnosis["declared_profile"]
    inert = diagnosis["beta_zero_counterpart"]
    control = diagnosis["supported_relation_control"]
    verdicts = diagnosis["verdicts"]

    assert verdicts["declared_profile_input_is_inert"]
    assert verdicts["beta_zero_counterpart_input_is_inert"]
    assert declared["output_spread"] <= COMPACT.authority_allowance
    assert inert["output_spread"] == 0.0
    # The mechanism, measured rather than asserted: the lift and the readout row
    # are supported on different ports' coordinates and the compact path's input
    # column is annihilated, while the full path moves the state exactly by the
    # lift and the declared readout still does not see it.
    assert declared["support_overlap"] == []
    assert declared["output_row_dot_input_lift"] == 0.0
    assert declared["compact_map_available"] is False
    assert verdicts["declared_profile"]["the_lift_moves_the_state_here"]
    assert verdicts["declared_profile"]["the_readout_is_blind_to_that_movement"]
    assert inert["compact_map_available"] is True
    assert inert["compact_map_direct_term"] == [0.0]
    assert abs(inert["compact_map_drive_input_column_norm"]) < 1e-15
    assert verdicts["beta_zero_counterpart"][
        "the_input_is_annihilated_before_it_reaches_the_state"
    ]
    # The control: the identical code path carries a signal once the declared
    # problem declares a supported relation between the two ports.
    assert verdicts["supported_relation_control_fires"]
    assert control["input_has_authority"]
    assert control["output_spread"] > declared["output_spread"]
    assert control["compact_map_drive_input_column_norm"] > 1e-3
    assert diagnosis["owner_transition_surface"]["write_packet_impulse_present_on_the_owner"]
    assert not diagnosis["owner_transition_surface"]["advance_carries_a_write"]


def test_the_cycle_holds_the_written_pattern_and_the_no_loop_control_fails(
    receipt,
) -> None:
    cycle = receipt["cycle"]
    verdicts = cycle["verdicts"]
    assert cycle["item"] == "root-scale"
    assert cycle["gain"] > 0.0
    assert cycle["gain_bracket"][0] <= cycle["gain"] <= cycle["gain_bracket"][1]
    assert cycle["gain_bracket_width"] <= COMPACT.feedback_config().neutral_gain_bracket
    assert cycle["neutral_gain"]["grid_monotone"]
    assert len(cycle["neutral_gain"]["probes"]) > 0
    assert verdicts["gain_refinement_measured_every_probe"]

    assert verdicts["hold_passes_the_predicate"]
    assert verdicts["no_loop_control_must_fail"]
    assert verdicts["no_loop_control_fails_the_predicate"]
    assert not verdicts["no_loop_control_passes_the_predicate"]
    assert verdicts["hold_beats_the_control_by_the_margin"]
    assert verdicts["hold_exceeds_the_control_by"] >= verdicts["hold_margin"]
    assert verdicts["owner_route_matches_the_existing_route"]
    assert verdicts["route_fidelity_difference"] == 0.0
    assert verdicts["readout_is_item_specific"]
    assert verdicts["readout_specificity_difference"] >= verdicts["cross_item_margin"]
    assert verdicts["skeleton_reproduces_the_declared_loop"]

    equivalence = cycle["skeleton_equivalence"]
    assert equivalence["fidelity_series_identical"]
    assert equivalence["page_digest_series_identical"]
    assert equivalence["state_digest_series_identical"]
    assert equivalence["max_fidelity_difference"] == 0.0
    assert equivalence["samples_compared"] == len(COMPACT.long_horizon_sample_ticks)
    assert equivalence["skeleton_horizon_state_sha256"] == (
        equivalence["reference_horizon_state_sha256"]
    )

    series = cycle["owner_arm"]["retention_series"]
    assert [row["tick"] for row in series] == list(COMPACT.long_horizon_sample_ticks)
    assert series[-1]["fidelity"] == cycle["owner_arm"]["fidelity_at_horizon"]
    assert series[-1]["fidelity"] > cycle["no_loop_control"]["fidelity_at_horizon"]
    assert cycle["owner_arm"]["drive_work_total"] > 0.0


def test_two_items_under_the_declared_work_split(receipt) -> None:
    pair = receipt["pair"]
    verdicts = pair["verdicts"]
    assert pair["items"] == ["root-scale", "left-detail"]
    assert [row["split"] for row in pair["rows"]] == [
        [float(left), float(right)]
        for left, right in feedback.FeedbackConfig().capacity_split_weights
    ]
    assert verdicts["no_loop_control_must_fail"]
    assert verdicts["no_loop_control_fails_the_predicate"]
    assert verdicts["uniform_split_both_items_beat_the_no_loop_control_by_the_margin"]
    assert verdicts["all_splits_beat_the_no_loop_control_by_the_margin"]
    uniform = pair["rows"][0]["item_retention"]
    for name, control in pair["no_loop_control"]["item_retention"].items():
        assert uniform[name] - control >= verdicts["margin"]
        assert verdicts["differences_from_the_no_loop_control"][name] == pytest.approx(
            uniform[name] - control, rel=1e-12, abs=1e-15
        )
    passing = [
        row["split"]
        for row in pair["rows"]
        if all(
            value >= verdicts["neutral_level_floor"]
            for value in row["item_retention"].values()
        )
    ]
    assert verdicts["splits_where_both_items_pass_the_predicate"] == passing
    assert len(pair["owner_write"]) == 2
    assert all(write["accepted"] for write in pair["owner_write"])


def test_receipt_digest_is_deterministic_and_covers_the_measurements(receipt) -> None:
    body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    assert receipt["receipt_digest"] == receipt_digest(body)
    assert build_receipt(COMPACT)["receipt_digest"] == receipt["receipt_digest"]

    mutated = {key: value for key, value in body.items()}
    mutated["impulse"] = {
        **mutated["impulse"],
        "impulse_arm": {
            **mutated["impulse"]["impulse_arm"],
            "read_frame_deposit": mutated["impulse"]["impulse_arm"]["read_frame_deposit"]
            + 1.0,
        },
    }
    assert receipt_digest(mutated) != receipt["receipt_digest"]

    mutated_reading = {key: value for key, value in body.items()}
    mutated_reading["reading"] = {
        **mutated_reading["reading"],
        "the_impulse_reaches_the_field": (
            mutated_reading["reading"]["the_impulse_reaches_the_field"] + " (edited)"
        ),
    }
    assert receipt_digest(mutated_reading) != receipt["receipt_digest"]


def test_the_design_quotes_in_the_port_reading_are_verbatim() -> None:
    """The reading cites the design text, so the citations are checked, not typed."""

    import re
    from pathlib import Path

    from run_owner_write_path_exploration import OVERLAPPING_SELECTION_READING

    def flatten(text: str) -> str:
        return re.sub(r"\s+", " ", text)

    sources = {
        "FIELD-INTELLIGENCE-DESIGN.md": flatten(
            Path("FIELD-INTELLIGENCE-DESIGN.md").read_text(encoding="utf-8")
        ),
        "README.md": flatten(Path("README.md").read_text(encoding="utf-8")),
    }
    quotes = OVERLAPPING_SELECTION_READING["design_text"]
    assert len(quotes) == 4
    for key, quoted in quotes.items():
        document = "README.md" if key.startswith("README") else "FIELD-INTELLIGENCE-DESIGN.md"
        body = flatten(quoted.strip().strip("'"))
        for part in (piece for piece in body.split(" ... ") if piece):
            assert part in sources[document], f"{key} is not verbatim in {document}"


def test_the_declared_ports_are_disjoint_and_overlapping_selection_is_refused(
    receipt,
) -> None:
    support = receipt["port_support"]
    profile = support["profile"]
    assert profile["port_count"] == 28
    assert profile["pools"] == 7
    assert profile["ports_per_pool"] == 4
    assert profile["phase_space_coordinates"] == 112
    assert len(support["declared_ports"]) == 28
    assert support["declared_ports"][0]["common_support"] == [0, 28]
    assert support["declared_ports"][0]["strand_support"] == [56, 84]

    overlap = support["overlap"]
    assert overlap["unordered_port_pairs_considered"] == 378
    assert overlap["overlapping_port_pairs_found"] == 0
    assert overlap["disjoint_port_pairs_found"] == 378
    assert overlap["disjoint_port_pairs"][0] == [0, 1]
    assert (
        len(overlap["disjoint_port_pairs"]) + overlap["overlapping_port_pairs_found"]
        == overlap["unordered_port_pairs_considered"]
    )
    assert support["detector_control"]["control_fires"]
    assert support["detector_control"]["overlapping_coordinates"] == [0, 28]

    placement = support["written_pattern_placement"]
    assert placement["touched_lanes"] == [2, 3]
    assert placement["touched_port_count"] == 28
    assert placement["readout_phase_space_coordinates"] == [4, 32]
    assert placement["readout_pair_page_coordinates"] == [36, 37]
    assert placement["readout_pair_lanes"] == [0, 1]
    assert support["verdicts"]["the_write_touches_the_strand_pair"]
    assert support["verdicts"]["the_readout_pair_is_the_common_pair"]
    assert support["verdicts"]["the_write_pair_and_the_readout_pair_are_disjoint"]

    shipped = support["measured_selections"]["(a) shipped_selection"]
    assert shipped["input_support_phase_space_coordinates"] == [0, 28]
    assert shipped["readout_support_phase_space_coordinates"] == [4, 32]
    assert shipped["support_overlap"] == []
    assert shipped["output_row_dot_input_lift"] == 0.0
    assert shipped["output_spread"] < receipt["declared"]["config"]["authority_allowance"]
    assert not shipped["input_has_authority"]
    assert support["verdicts"]["the_shipped_selection_is_inert"]

    overlapping = support["measured_selections"]["(b) overlapping_selection"]
    assert not overlapping["on_this_profile"]["accepted"]
    assert overlapping["on_this_profile"]["refusal"] == "ResonantNumericalError"
    assert overlapping["on_this_profile"]["shared_port"] == 0
    assert overlapping["refused_on_every_profile_tried"]
    assert overlapping["on_other_declared_profiles"]
    assert not any(row["accepted"] for row in overlapping["on_other_declared_profiles"])
    assert support["verdicts"]["an_overlapping_selection_is_refused_by_the_library"]

    control = support["measured_selections"]["(c) coupled_relation_control"]
    assert control["problem_precision"] == [[2.0, 1.0], [1.0, 2.0]]
    assert control["input_has_authority"]
    assert control["output_spread"] > shipped["output_spread"]
    assert control["support_overlap"] == []
    assert control["fires_with_the_same_disjoint_supports"]
    assert support["verdicts"]["the_coupled_relation_control_fires_without_a_support_overlap"]


def test_the_coupled_control_is_the_diagnosis_control_not_a_new_relation(receipt) -> None:
    diagnosis_control = receipt["diagnosis"]["supported_relation_control"]
    reported = receipt["port_support"]["measured_selections"][
        "(c) coupled_relation_control"
    ]
    assert reported["problem_precision"] == [[2.0, 1.0], [1.0, 2.0]]
    assert reported["output_spread"] == diagnosis_control["output_spread"]
    assert (
        reported["input_support_phase_space_coordinates"]
        == diagnosis_control["input_lift_support_coordinates"]
    )
    assert (
        reported["readout_support_phase_space_coordinates"]
        == diagnosis_control["readout_row_support_coordinates"]
    )
    assert receipt["port_support"]["measured_selections"]["(a) shipped_selection"][
        "output_spread"
    ] == receipt["diagnosis"]["declared_profile"]["output_spread"]
    assert receipt["port_support"]["reading"]["what_was_not_done"]


def test_the_owner_read_surface_reaches_the_deposit_only_through_the_raw_page(
    receipt,
) -> None:
    surface = receipt["owner_read_surface"]
    declared = surface["surface"]
    assert declared["declared_operations"] >= 40
    assert "inspect_transceivers" in declared["read_only_operations"]
    assert "advance" not in declared["read_only_operations"]
    assert sorted(declared["read_only_operations_exercised_with_no_arguments"]) == [
        "inspect",
        "inspect_computers",
        "inspect_resonance",
        "inspect_transceivers",
    ]
    assert "query" in declared["read_only_operations_taking_arguments_not_exercised_here"]

    readback = surface["reading_the_written_page_back"]
    assert readback["deposit_in_the_declared_read_frame"] > 0.0
    assert readback["blank_page_deposit_in_the_declared_read_frame"] == 0.0
    assert readback["raw_page_recovery"] == readback["deposit_in_the_declared_read_frame"]
    assert readback["raw_page_recovery_equals_the_written_deposit"]
    assert readback["written_event_kind"] == receipt["declared"]["config"]["event_kind"]
    assert readback["written_applied_work"] > 0.0

    inspection = surface["inspection"]
    assert inspection["paths_naming_a_deposit_or_a_written_direction"] == []
    # The same scan finds the intervention's own ledger entries, so the empty
    # direction scan above is a live comparison rather than a vacuous one.
    assert inspection["paths_naming_the_intervention_itself"]
    assert all(
        "packet" in path for path in inspection["paths_naming_the_intervention_itself"]
    )
    assert inspection["inspect_payload_unchanged_by_the_reads"]
    assert inspection["inspect_resonance_payload_unchanged_by_the_reads"]
    assert inspection["page_unchanged_by_the_reads"]
    assert (
        inspection["evidence_tick_before_the_reads"]
        == inspection["evidence_tick_after_the_reads"]
    )
    assert (
        inspection["field_generation_before_the_reads"]
        == inspection["field_generation_after_the_reads"]
    )

    closest = surface["closest_surface"]
    assert closest["the_readout_sees_the_written_page"]
    assert closest["max_difference_over_the_read"] > closest["allowance"]
    assert closest["first_tick_difference"] > closest["allowance"]
    assert closest["blank_page_outputs"] == [0.0, 0.0, 0.0, 0.0]
    assert closest["readout_support_coordinates"] == [4, 32]
    assert closest["readout_support_is_the_output_ports_common_pair"]
    assert closest["written_page_outputs"] == sorted(closest["written_page_outputs"])
    assert all(value > 0.0 for value in closest["written_page_outputs"])

    assert surface["verdicts"]["the_owner_exposes_an_evidence_producing_read_of_the_deposit"] is False
    assert surface["verdicts"]["inspection_alone_names_no_deposit_or_written_direction"]
    assert surface["verdicts"]["the_raw_page_recovers_the_written_deposit_exactly"]
    assert surface["verdicts"]["the_reads_change_no_page_state_or_evidence"]
    assert surface["verdicts"]["the_closest_read_carries_the_written_page"]


def test_the_owner_read_operation_recovers_a_written_direction(receipt) -> None:
    operation = receipt["read_operation"]
    recovery = operation["recovery"]
    assert operation["operation"] == "read_packet_deposit"
    assert operation["verdicts"]["the_owner_declares_a_read_operation_for_a_written_direction"]
    assert operation["verdicts"]["the_read_operation_appears_in_the_dispatch_inventory"]
    assert operation["verdicts"]["the_read_is_reachable_through_the_surface_dispatch"]

    written = recovery["written_deposit_in_the_declared_read_frame"]
    assert written > 0.0
    assert recovery["recovered_by_the_read_operation"] == pytest.approx(
        written, rel=recovery["allowance"]
    )
    assert recovery["read_recovers_the_written_deposit"]
    # The library's own route to the same number: the page projected on the
    # harness's captured unit direction for the same item.
    assert (
        recovery["recovered_by_the_library_along_the_captured_direction"] == written
    )
    assert recovery["the_dispatch_returns_the_same_readout"]
    assert recovery["direction_sha256"] == operation["direction_identity"][
        "captured_direction_sha256"
    ]
    assert operation["direction_identity"][
        "the_reads_direction_is_the_captured_writes_direction"
    ]
    assert recovery["the_write_was_accepted"]
    assert recovery["written_applied_work"] > 0.0
    assert (
        operation["declared_direction"]["item"]
        != operation["declared_direction"]["unwritten_item"]
    )


def test_the_read_operation_controls_miss_the_written_deposit(receipt) -> None:
    controls = receipt["read_operation"]["controls"]
    written = receipt["read_operation"]["recovery"][
        "written_deposit_in_the_declared_read_frame"
    ]
    assert controls["predicate"]
    for name in ("blank_page", "unwritten_direction"):
        control = controls[name]
        assert control["must_fail"]
        assert control["recovered"] == 0.0
        assert control["passes_the_recovery_predicate"] is False
        assert control["recovered_fraction_of_the_written_deposit"] == 0.0
        assert control["recovered"] < written

    # The controls can fail. With the declared direction dropped from the read
    # implementation (the page's own frame energy is returned instead), the
    # unwritten direction reaches the written deposit and passes the very
    # predicate that rejected it, the clean readout returns once the mutation is
    # removed, and the firing control itself leaves the page unchanged.
    firing = controls["firing_control"]
    verdicts = receipt["read_operation"]["verdicts"]
    assert firing["mutated_unwritten_direction_recovered"] == pytest.approx(
        written, rel=1e-12
    )
    assert firing["the_unwritten_direction_control_fires_under_the_mutation"]
    assert verdicts["the_unwritten_direction_control_fires_under_a_direction_blind_read"]
    assert not firing["the_blank_page_control_fires_under_the_mutation"]
    assert firing["mutated_unwritten_direction_recovered"] > controls[
        "unwritten_direction"
    ]["recovered"]
    assert firing["recovered_after_the_mutation_was_removed"] == written
    assert firing["the_clean_readout_returns_after_the_mutation_is_removed"]
    assert firing["the_mutation_was_removed_before_this_block_returned"]
    assert firing["the_firing_control_leaves_the_page_unchanged"]
    assert verdicts["the_clean_readout_returns_once_the_mutation_is_removed"]


def test_the_readout_is_a_share_along_the_declared_direction(receipt) -> None:
    operation = receipt["read_operation"]
    dual = operation["two_written_directions"]
    energy = dual["page_read_frame_energy"]
    reads = dual["recovered_by_the_read_operation"]
    assert energy > 0.0
    assert len(reads) == 2
    assert all(value > 0.0 for value in reads.values())
    # Neither direction recovers the whole page: the readout is a projection along
    # the named direction, not a page summary. A read that returned the frame's
    # energy would fail this.
    assert all(value < energy for value in reads.values())
    assert operation["verdicts"][
        "the_read_recovers_a_share_of_a_two_write_page_rather_than_its_total"
    ]
    assert dual["share_of_the_page_each_read_recovers"] == {
        name: value / energy for name, value in reads.items()
    }
    assert dual["written_deposits_in_their_own_frames"].keys() == reads.keys()
    assert dual["what_this_shows"]


def test_the_read_is_a_prediction_that_moves_neither_the_page_nor_the_clocks(
    receipt,
) -> None:
    operation = receipt["read_operation"]
    invariants = operation["invariants"]
    assert operation["recovery"]["readout_kind"] == "temporal-prediction"
    assert operation["recovery"]["read_declares_evidence_added"] is False
    assert invariants["page_before_the_reads"] == invariants["page_after_the_reads"]
    assert invariants["page_unchanged_by_the_reads"]
    assert invariants["generation_unchanged_by_the_reads"]
    assert invariants["evidence_tick_unchanged_by_the_reads"]
    assert invariants["inspect_payload_unchanged_by_the_reads"]
    assert invariants["inspect_resonance_payload_unchanged_by_the_reads"]
    assert operation["verdicts"]["the_read_changes_no_page_generation_or_evidence_tick"]
    assert operation["verdicts"]["the_read_is_declared_a_temporal_prediction"]
    assert operation["verdicts"]["the_read_is_not_an_evidence_producing_read"]

    # The invariants are live: the write the reads read moves both quantities the
    # reads preserve, and an admitted observation moves the evidence clock.
    controls = operation["invariant_controls"]
    assert controls["the_write_changes_the_page_digest"]
    assert controls["the_write_advances_the_generation"]
    assert controls["page_before_the_write"] != controls["page_after_the_write"]
    clock = controls["evidence_tick_control"]
    assert clock["evidence_tick_after_the_admission"] == (
        clock["evidence_tick_before_the_admission"] + 1
    )
    assert clock["an_admission_moves_the_evidence_clock"]
    assert operation["verdicts"]["the_write_changes_what_the_read_preserves"]
    assert operation["verdicts"]["an_admission_moves_the_evidence_clock"]


def test_the_read_is_declared_read_only_and_the_scan_now_names_the_direction(
    receipt,
) -> None:
    operation = receipt["read_operation"]
    inventory = operation["surface_inventory"]
    assert inventory["read_only_operations"] == sorted(inventory["read_only_operations"])
    assert "read_packet_deposit" in inventory["read_only_operations"]
    assert inventory["the_read_operation_is_declared_read_only"]
    assert inventory["declared_operations"] == len(dispatch_operations())
    assert inventory["read_only_operations"] == sorted(
        name for name in dispatch_operations() if name in READ_ONLY_SURFACE_OPERATIONS
    )

    scan = operation["exposure_scan"]
    before = scan["before_the_read_operation"]
    after = scan["after_the_read_operation"]
    assert before["paths_naming_a_deposit_or_a_written_direction"] == []
    assert before["paths_naming_the_intervention_itself"]
    # The same scan the surface block reports, so the before/after pair is one
    # measurement convention applied twice rather than two conventions.
    assert before["published_key_paths"] == receipt["owner_read_surface"]["inspection"][
        "published_key_paths"
    ]
    assert before["paths_naming_a_deposit_or_a_written_direction"] == (
        receipt["owner_read_surface"]["inspection"][
            "paths_naming_a_deposit_or_a_written_direction"
        ]
    )
    assert after["published_key_paths"] > before["published_key_paths"]
    assert after["paths_naming_a_deposit_or_a_written_direction"]
    assert "recovered_deposit" in after["paths_naming_a_deposit_or_a_written_direction"]
    assert "direction_sha256" in after["paths_naming_a_deposit_or_a_written_direction"]
    assert after["paths_the_read_operation_adds"]

    matcher = scan["matcher_controls"]
    assert matcher["paths_naming_it_before"] == []
    assert matcher["paths_naming_it_after"] == []
    assert operation["verdicts"]["the_exposure_scan_now_names_the_written_direction"]
    assert operation["verdicts"]["the_scan_finds_no_path_naming_the_absent_word"]
    assert operation["if_the_read_were_declared_as_evidence"]
