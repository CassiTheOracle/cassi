"""Focused tests for the two additive owner-surface options and their receipt.

Each test reads one measured figure out of the receipt and checks it against the
declared predicate it is supposed to answer. The module builds the receipt once
with a compact configuration: the same profile, item, budget and declared channel
as the shipped receipt, with the declared overlap lattice reduced to one ports-per
-pool setting and one beta setting, the authority window shortened to two ticks,
and the cost window shortened. Every predicate below is exercised on figures the
compact configuration still produces.
"""

from __future__ import annotations

import numpy as np
import pytest

from cassi_field_transceiver import advance_transceiver, condense_input, reset_transceiver
from cassi_resonant_field import ResonantProblem, initial_workspace
from run_owner_surface_options import (
    ABSENT_PATH_WORD,
    COUPLED_COUPLING,
    COUPLED_DIAGONAL,
    DECLARED_TOPOLOGIES,
    EVIDENCE_OPERATION_ID,
    OwnerSurfaceOptionsConfig,
    SHIPPED_COUPLING,
    SHIPPED_DIAGONAL,
    build_receipt,
    flat_profile,
    key_paths,
    matching_paths,
    open_owner,
    receipt_digest,
)

# The declared compact test configuration: the same profile, declared item,
# write budget, channel and overlap topologies as the shipped receipt, with the
# declared overlap lattice reduced to one ports-per-pool setting, the authority
# window shortened to its first two ticks and the cost window shortened, which is
# the shortest declared schedule that still exercises every measured predicate.
COMPACT = OwnerSurfaceOptionsConfig(
    authority_window_ticks=(1, 2),
    overlap_ports_per_pool=(4,),
    overlap_betas=(0.08,),
    cost_ticks=8,
    cost_repeats=1,
)


@pytest.fixture(scope="module")
def receipt():
    return build_receipt(COMPACT)


@pytest.fixture(scope="module")
def profile():
    return flat_profile()


def test_the_shipped_read_moves_nothing_and_the_evidence_reading_is_admitted(
    receipt,
) -> None:
    block = receipt["reading_declaration"]
    prediction = block["prediction_reading"]
    evidence = block["evidence_reading"]
    assert prediction["moves_nothing"]
    assert prediction["moved"]["moved_leaf_count"] == 0
    assert prediction["moved"]["moved_leaf_classes"] == {}
    assert bool(evidence["admission"]["event_id"])
    assert evidence["admission"]["epistemic_type"] == "observed"
    assert not evidence["admission"]["replayed"]
    assert evidence["admission"]["published_a_successor"]


def test_the_evidence_reading_moves_the_clock_the_store_and_the_declared_channel(
    receipt,
) -> None:
    evidence = receipt["reading_declaration"]["evidence_reading"]
    assert evidence["evidence_clock_moved_by"] == 1
    assert evidence["successors_published_by_the_admission"] == 1
    assert evidence["evidence_store_events_added"] == 1
    assert evidence["moved"]["moved_leaf_count"] > 0
    classes = evidence["moved"]["moved_leaf_classes"]
    assert classes.get("clock", 0) > 0
    assert classes.get("digest", 0) > 0
    before = evidence["declared_channel_before"]
    after = evidence["declared_channel_after"]
    channel = receipt["config"]["declared_deposit_chart"]
    assert before[channel]["contribution_count"] == 0
    assert after[channel]["contribution_count"] == 1
    assert after[channel]["version"] == before[channel]["version"] + 1


def test_nothing_downstream_of_the_admission_keys_on_observed_support(receipt) -> None:
    consumers = receipt["reading_declaration"]["observed_support_consumers"]
    assert consumers["the_declared_channel_moved"]
    assert not consumers["a_decision_input_moved"]
    assert consumers["moved_leaf_classes"].get("decision", 0) == 0
    assert consumers["declared_dispatch_operations"] > 0


def test_the_evidence_reading_is_refused_without_a_declared_channel(receipt) -> None:
    control = receipt["reading_declaration"]["control"]
    assert control["must_refuse"]
    assert control["refused"]
    assert control["error"]


def test_the_retry_replays_the_admission_instead_of_publishing_a_second_successor(
    receipt,
) -> None:
    retry = receipt["reading_declaration"]["retry"]
    assert retry["replayed"]
    assert retry["event_id_identical"]
    assert retry["source_revision_id_identical"]
    assert not retry["second_transition_published"]
    assert (
        retry["generation_after_the_retry"]
        == retry["generation_after_the_first_admission"]
    )
    assert retry["moved_by_the_retry"]["moved_leaf_count"] == 0


def test_the_two_readings_recover_the_same_deposit(receipt) -> None:
    recovered = receipt["reading_declaration"]["read_recovered_deposit"]
    assert recovered["the_two_readings_recover_the_same_deposit"]
    assert recovered["prediction"] > 0.0
    assert recovered["evidence"] == recovered["prediction"]
    assert recovered["readout_kind_of_the_shipped_reading"] == "temporal-prediction"


def test_the_exposure_scan_counts_each_reading_and_its_absent_control(receipt) -> None:
    side = receipt["reading_declaration"]["side_by_side"]["exposure_counts"]
    assert side["prediction"]["absent_control"] == 0
    assert side["evidence"]["absent_control"] == 0
    assert side["evidence"]["direction"] > side["prediction"]["direction"]
    assert ABSENT_PATH_WORD not in " ".join(
        path.lower()
        for path in key_paths(receipt["reading_declaration"]["prediction_reading"]["exposure"])
    )
    assert matching_paths(["a.deposit.b", "c.energy"], (ABSENT_PATH_WORD,)) == []
    assert matching_paths(["a.deposit.b", "c.energy"], ("deposit",)) == ["a.deposit.b"]


def test_the_opt_in_input_helper_reproduces_the_shipped_declared_input() -> None:
    profile = flat_profile()
    workspace = initial_workspace(profile)
    problem = ResonantProblem(
        variable_ids=("write-in", "write-out"), precision=np.eye(2, dtype=np.float64)
    )
    opt_in_kernel, _working, _receipt = condense_input(
        workspace,
        input_ids=("write-in",),
        output_ids=("write-out",),
        diagonal=SHIPPED_DIAGONAL,
        coupling=SHIPPED_COUPLING,
        rank=4,
        horizon_ticks=8,
    )
    from cassi_field_transceiver import condense_workspace
    from cassi_resonant_field import bind_workspace

    shipped_kernel, _working2, _receipt2 = condense_workspace(
        bind_workspace(workspace, problem),
        problem,
        input_ids=("write-in",),
        output_ids=("write-out",),
        rank=4,
        horizon_ticks=8,
    )
    assert opt_in_kernel["kernel_sha256"] == shipped_kernel["kernel_sha256"]
    # The can-fail control: the coupled relation is a different realization, so
    # the identity above is a property of the default, not of the helper.
    coupled_kernel, _working3, _receipt3 = condense_input(
        workspace,
        input_ids=("write-in",),
        output_ids=("write-out",),
        diagonal=COUPLED_DIAGONAL,
        coupling=COUPLED_COUPLING,
        rank=4,
        horizon_ticks=8,
    )
    assert coupled_kernel["kernel_sha256"] != shipped_kernel["kernel_sha256"]


def test_the_coupled_relation_carries_authority_and_the_shipped_one_does_not(
    receipt,
) -> None:
    authority = receipt["coupled_input"]["authority"]
    allowance = receipt["config"]["authority_allowance"]
    shipped = authority["declared_profile_shipped_relation"]
    coupled = authority["declared_profile_coupled_relation"]
    assert shipped["authority_window_average_spread"] == 0.0
    assert not shipped["per_tick"]["1"]["input_has_authority"]
    assert coupled["authority_window_average_spread"] > allowance
    assert coupled["per_tick"]["1"]["input_has_authority"]
    # The normalized figure is carried beside the absolute one; a proportional
    # response through the origin normalizes to one whatever its size, which is
    # why the absolute spread is the figure the predicate uses.
    assert coupled["per_tick"]["1"]["relative_spread"] == pytest.approx(1.0)
    assert coupled["per_tick"]["1"]["authority_absolute_spread"] > 0.0
    assert coupled["per_tick"]["1"]["authority_absolute_spread"] == pytest.approx(
        coupled["per_tick"]["1"]["magnitude"]
    )


def test_the_beta_zero_counterpart_is_reported_for_both_relations(receipt) -> None:
    authority = receipt["coupled_input"]["authority"]
    shipped = authority["beta_zero_counterpart_shipped_relation"]
    coupled = authority["beta_zero_counterpart_coupled_relation"]
    assert coupled["authority_window_average_spread"] > shipped["authority_window_average_spread"]
    # Honest negative: the shipped declared relation is inert on the declared
    # profile but not on its beta-zero counterpart, where the compact path has an
    # algebraic feedthrough. Both figures are in the receipt.
    assert authority["declared_profile_shipped_relation"]["authority_window_average_spread"] == 0.0
    assert shipped["authority_window_average_spread"] > 0.0


def test_the_coupled_input_does_not_reproduce_the_owner_write_path(receipt) -> None:
    route = receipt["coupled_input"]["route_identity"]
    assert route["amplitudes_reporting_page_identity"] == []
    assert route["best_amplitude"]["amplitude"] == 0.0
    declared_scan = route["identity_at_the_declared_scan"]["comparison"]
    assert not declared_scan["page_digest_identical"]
    assert not declared_scan["state_digest_identical"]
    assert declared_scan["read_frame_max_abs_difference"] > 0.0
    owner_page = route["route_page_against_the_owner_page"]
    assert not owner_page["route_page_at_the_best_amplitude_vs_the_owner_page"][
        "page_digest_identical"
    ]
    assert not owner_page["route_page_at_the_best_amplitude_vs_the_owner_page"][
        "field_bytes_identical"
    ]
    # The controls that show the predicate can report identity.
    control = route["reconstruction_control"]
    assert control["reports_identity"]
    assert control["comparison"]["page_digest_identical"]
    assert control["comparison"]["read_frame_max_abs_difference"] == 0.0
    assert not route["no_drive_control"]["comparison"]["page_digest_identical"]


def test_the_mapped_target_page_differs_from_the_owner_page_only_in_metadata(
    receipt,
) -> None:
    block = receipt["coupled_input"]["route_identity"]["route_page_against_the_owner_page"][
        "mapped_target_page_vs_the_owner_page"
    ]
    assert block["page_digest_identical"]
    assert not block["workspace_state_digest_identical"]
    assert block["metadata_fields_that_differ"]


def test_the_driven_readout_persists_after_the_drive_stops(receipt) -> None:
    persistence = receipt["coupled_input"]["persistence"]
    coupled = persistence["declared_profile_coupled_relation"]["readout_after_each_tick"]
    shipped = persistence["declared_profile_shipped_relation"]["readout_after_each_tick"]
    ticks = sorted(coupled, key=int)
    assert abs(float(coupled[ticks[-1]])) > abs(float(coupled[ticks[0]]))
    assert all(float(value) == 0.0 for value in shipped.values())


def test_the_coupled_work_is_measured_against_one_owner_write(receipt) -> None:
    cost = receipt["elapsed_seconds"]["cost"]
    shipped = cost["per_tick_seconds"]["declared_profile_shipped_relation"]["per_tick_seconds"]
    coupled = cost["per_tick_seconds"]["declared_profile_coupled_relation"]["per_tick_seconds"]
    assert shipped > 0.0
    assert coupled > shipped
    assert cost["owner_write_seconds"]["median_seconds"] > 0.0
    assert len(cost["owner_write_seconds"]["samples"]) == receipt["config"]["cost_repeats"]
    assert cost["coupled_per_tick_over_owner_write"] > 0.0
    # The wall-clock block is declared as the receipt's timing key and is stripped
    # from the digest; the declared cost block names where the figures are.
    assert receipt["coupled_input"]["cost"]["figures_at"] == "elapsed_seconds.cost"
    assert receipt["digest_convention"]["strip_keys"]
    assert "elapsed_seconds" in receipt["digest_convention"]["strip_keys"]


def test_every_declared_profile_refuses_an_overlapping_port_selection(receipt) -> None:
    block = receipt["overlap_enumeration"]
    summary = block["summary"]
    lattice = block["lattice"]
    expected = (
        len(lattice["topologies"])
        * len(lattice["ports_per_pool"])
        * len(lattice["betas"])
    )
    assert summary["profiles"] == expected == len(block["rows"])
    assert summary["overlapping_selection_accepted"] == 0
    assert summary["overlapping_selection_refused"] == expected
    assert summary["no_profile_admits_an_overlapping_selection"]
    assert summary["refusal_messages"] == [
        "ResonantNumericalError: inconsistent common-coordinate constraints"
    ]
    assert set(lattice["topologies"]) == set(DECLARED_TOPOLOGIES)
    for row in block["rows"]:
        assert row["the_two_declared_variables_share_a_port_in_the_overlap_selection"]
        assert not row["overlapping_selection"]["accepted"]
        assert set(row["overlap_ports"].values()) == {row["overlap_ports"]["write-in"]}


def test_the_overlap_controls_show_what_the_refusal_is_a_consequence_of(
    receipt,
) -> None:
    block = receipt["overlap_enumeration"]
    rows = len(block["rows"])
    controls = block["controls"]
    assert controls["zero_declared_value_on_the_shared_port"]["accepted"] == rows
    assert controls["unit_declared_value_on_distinct_ports"]["accepted"] == rows
    assert controls["unit_declared_value_on_the_shared_port"]["refused"] == rows
    assert controls["topology_name_control"]["refusal"]
    for row in block["rows"]:
        assert not row["boundary_with_a_unit_declared_value_on_the_shared_port"]["accepted"]
        assert row["boundary_with_a_zero_declared_value_on_the_shared_port"]["accepted"]
        assert row["boundary_with_a_unit_declared_value_on_distinct_ports"]["accepted"]
        assert row["distinct_port_selection"]["accepted"]


def test_the_receipt_digest_is_deterministic_and_covers_the_measurements(receipt) -> None:
    body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    assert receipt["receipt_digest"] == receipt_digest(body)
    assert build_receipt(COMPACT)["receipt_digest"] == receipt["receipt_digest"]
    assert len(receipt["receipt_digest"]) == 64


def test_the_receipt_digest_changes_when_a_measurement_changes(receipt) -> None:
    body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    assert receipt_digest(body) == receipt["receipt_digest"]

    mutated = {**body, "reading_declaration": dict(body["reading_declaration"])}
    evidence = dict(mutated["reading_declaration"]["evidence_reading"])
    evidence["evidence_clock_moved_by"] = int(evidence["evidence_clock_moved_by"]) + 1
    mutated["reading_declaration"] = {
        **mutated["reading_declaration"],
        "evidence_reading": evidence,
    }
    assert receipt_digest(mutated) != receipt["receipt_digest"]

    other = {**body, "overlap_enumeration": dict(body["overlap_enumeration"])}
    summary = dict(other["overlap_enumeration"]["summary"])
    summary["overlapping_selection_refused"] = 0
    other["overlap_enumeration"] = {**other["overlap_enumeration"], "summary": summary}
    assert receipt_digest(other) != receipt["receipt_digest"]


def test_a_second_reading_of_the_shipped_default_leaves_the_owner_state_alone() -> None:
    """An independent live check of the default, outside the receipt's fixture."""

    profile = flat_profile()
    config = COMPACT
    owner, home = open_owner(profile, config)
    try:
        from run_owner_surface_options import declared_direction, owner_write, surface_snapshot

        import run_fractal_durability_exploration as durability

        spec = durability.ITEM_SPECS[int(config.headline_item_index)]
        owner_write(owner, "test:write", spec, config)
        before = surface_snapshot(owner, config)
        for _ in range(2):
            owner.read_packet_deposit(**declared_direction(spec))
        after = surface_snapshot(owner, config)
        assert before == after
    finally:
        owner.close()
        import shutil

        shutil.rmtree(home, ignore_errors=True)


def test_nothing_outside_the_measurement_calls_the_opt_in_helpers(receipt) -> None:
    block = receipt["coupled_input"]["declaring_nothing"]
    assert block["files_calling_the_opt_in_helpers"] == block["expected_callers"]
    assert block["no_other_surface_calls_the_opt_in_helpers"]


def test_the_frozen_receipt_on_disk_carries_its_own_digest() -> None:
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent / "_diag" / "owner-surface-options" / "exploration.json"
    assert path.exists(), (
        f"the frozen receipt {path} is missing; produce it from CassiFI with "
        "`python run_owner_surface_options.py --output _diag/owner-surface-options/exploration.json`"
    )
    frozen = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in frozen.items() if key != "receipt_digest"}
    assert frozen["receipt_digest"] == receipt_digest(body)
    assert frozen["config"]["overlap_ports_per_pool"] == [4, 8, 16]
    assert len(frozen["overlap_enumeration"]["rows"]) == 24


def test_the_coupled_realization_carries_nothing_at_zero_drive() -> None:
    """A live control on the coupled kernel: no drive, no output; drive, output."""

    profile = flat_profile()
    workspace = initial_workspace(profile)
    coupled_kernel, _working, _receipt = condense_input(
        workspace,
        input_ids=("write-in",),
        output_ids=("write-out",),
        diagonal=COUPLED_DIAGONAL,
        coupling=COUPLED_COUPLING,
        rank=4,
        horizon_ticks=8,
    )
    _state, scan = advance_transceiver(
        coupled_kernel, reset_transceiver(coupled_kernel), inputs={"write-in": 0.0}, ticks=1
    )
    assert float(scan["values"]["write-out"]) == 0.0
    _state, driven = advance_transceiver(
        coupled_kernel, reset_transceiver(coupled_kernel), inputs={"write-in": 1.0}, ticks=1
    )
    assert float(driven["values"]["write-out"]) != 0.0
