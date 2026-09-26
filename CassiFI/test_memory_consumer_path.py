"""Focused checks for the memory consumer path.

The fixture builds the whole receipt once at a short declared hold horizon (two
driven ticks at the even parity the recovery claim is declared at, so the suite
stays inside its wall-clock bound), and the checks run against figures this file
measures rather than against the shipped receipt's numbers. Every predicate the runner claims has a can-fail
block here: the identity control's write, the mismatch control's different
item, the no-memory arm's blank page, the policy mutation, the unwritten
direction's recovery, and the admission that moves the evidence clock.
"""

from __future__ import annotations

import json

import pytest

from run_memory_consumer_path import (
    ARM_IDENTITY_CONTROL,
    ARM_MEMORY_USED,
    ARM_MISMATCH,
    ARM_NO_MEMORY,
    ARM_POLICY_MUTATED,
    CITED_NEUTRAL_GAIN,
    ORTHOGONALITY_ALLOWANCE,
    PURSUIT_MARGIN,
    READ_FLOOR_FRACTION,
    READ_RECOVERY_ALLOWANCE,
    RECEIPT_PATH,
    SCHEMA,
    SEPARATION_MARGIN,
    STRIP_KEYS,
    MemoryConsumerConfig,
    build_receipt,
    receipt_digest,
)

COMPACT = MemoryConsumerConfig(hold_horizon_ticks=2)


@pytest.fixture(scope="module")
def receipt() -> dict:
    return build_receipt(COMPACT)


@pytest.fixture(scope="module")
def arms(receipt: dict) -> dict:
    return {record["arm"]: record for record in receipt["arms"]}


@pytest.fixture(scope="module")
def episodes(receipt: dict) -> dict:
    """The field episodes by the name the arms refer to them by."""
    return {episode["episode"]: episode for episode in receipt["field_episodes"].values()}


def test_every_declared_arm_was_measured(receipt: dict, arms: dict) -> None:
    """The four arms and the firing control are declared and carried by the receipt."""

    assert receipt["schema"] == SCHEMA
    assert set(receipt["declared"]["arms"]) == {
        ARM_MEMORY_USED,
        ARM_IDENTITY_CONTROL,
        ARM_NO_MEMORY,
        ARM_MISMATCH,
        ARM_POLICY_MUTATED,
    }
    assert set(arms) == set(receipt["declared"]["arms"])


def test_the_memory_arm_pursues_what_it_retrieved(receipt: dict, arms: dict) -> None:
    arm = arms[ARM_MEMORY_USED]
    statistic = arm["statistic"]

    assert arm["retrieval"]["read_calls"] == 1
    assert arm["retrieval"]["retrieved_deposit"] == pytest.approx(
        receipt["captures"]["target_captured_deposit"], rel=READ_RECOVERY_ALLOWANCE
    )
    assert arm["decision"]["retrieved_reaches_the_floor"] is True
    assert arm["decision"]["selected_item"] == receipt["captures"]["target_name"]
    assert arm["decision"]["selected_is_the_target"] is True
    assert statistic["the_act_deposited_something"] is True
    assert statistic["share_along_target"] >= PURSUIT_MARGIN
    assert statistic["share_along_target"] > statistic["share_along_mismatch"]
    assert receipt["comparisons"]["the_memory_arm_pursues_the_target"] is True


def test_the_identity_control_carries_the_write_and_suppresses_only_the_read(
    receipt: dict, arms: dict, episodes: dict
) -> None:
    """B is the same field episode as A, with the consumer's read replaced by zero."""

    memory, identity = arms[ARM_MEMORY_USED], arms[ARM_IDENTITY_CONTROL]

    assert identity["field_episode"] == memory["field_episode"]
    assert (
        identity["act"]["page_before"]
        == episodes[identity["field_episode"]]["held_page_sha256"]
    )
    assert identity["act"]["page_before"] == memory["act"]["page_before"]
    instrument = identity["instrument_read_by_the_runner"]
    assert instrument["recovered_deposit"] == pytest.approx(
        memory["retrieval"]["retrieved_deposit"], rel=READ_RECOVERY_ALLOWANCE
    )
    assert instrument["recovered_deposit"] >= identity["decision"]["read_floor"]
    assert identity["retrieval"]["read_calls"] == 0
    assert identity["retrieval"]["retrieved_deposit"] == 0.0
    assert identity["retrieval"]["suppressed_value"] == 0.0
    assert identity["retrieval"]["readout_kind"] is None
    assert identity["act"]["accepted"] is True
    assert identity["act"]["the_act_changes_the_page"] is True
    assert identity["decision"]["retrieved_reaches_the_floor"] is False
    assert identity["decision"]["selected_item"] == receipt["declared"]["config"]["fallback_item"]
    assert identity["statistic"]["share_along_target"] < PURSUIT_MARGIN


def test_the_no_memory_arm_reads_a_blank_page(
    receipt: dict, arms: dict, episodes: dict
) -> None:
    arm = arms[ARM_NO_MEMORY]
    episode = episodes[arm["field_episode"]]

    assert episode["written_item"] is None
    assert arm["retrieval"]["read_calls"] == 1
    assert arm["retrieval"]["retrieved_deposit"] == 0.0
    assert arm["retrieval"]["read_frame_energy"] == 0.0
    assert arm["retrieval"]["readout_kind"] == "temporal-prediction"
    assert arm["decision"]["retrieved_reaches_the_floor"] is False
    assert arm["decision"]["selected_item"] == receipt["declared"]["config"]["fallback_item"]
    assert arm["statistic"]["share_along_target"] < PURSUIT_MARGIN
    assert arm["act"]["accepted"] is True


def test_the_mismatch_control_writes_a_different_item(
    receipt: dict, arms: dict, episodes: dict
) -> None:
    mismatch, memory = arms[ARM_MISMATCH], arms[ARM_MEMORY_USED]
    episode = episodes[mismatch["field_episode"]]

    assert episode["written_item"] == receipt["declared"]["config"]["mismatch_item"]
    assert episode["written_item"] != receipt["declared"]["config"]["target_item"]
    assert mismatch["retrieval"]["query_item"] == receipt["declared"]["config"]["target_item"]
    assert mismatch["act"]["accepted"] is True
    assert mismatch["act"]["the_act_changes_the_page"] is True
    assert mismatch["decision"]["selected_item"] == receipt["declared"]["config"]["fallback_item"]
    assert mismatch["statistic"]["share_along_target"] < PURSUIT_MARGIN
    assert mismatch["statistic"]["share_along_target"] < memory["statistic"]["share_along_target"]


def test_the_memory_contribution_is_attributable_to_content(receipt: dict, arms: dict) -> None:
    """A separates from both controls by the declared margin, and D from A too."""

    comparisons = receipt["comparisons"]

    assert comparisons["pursuit_margin"] == PURSUIT_MARGIN
    assert comparisons["separation_margin"] == SEPARATION_MARGIN
    assert comparisons["A_minus_B"] == pytest.approx(
        arms[ARM_MEMORY_USED]["statistic"]["share_along_target"]
        - arms[ARM_IDENTITY_CONTROL]["statistic"]["share_along_target"]
    )
    assert comparisons["A_minus_D"] >= SEPARATION_MARGIN
    assert comparisons["A_minus_the_greater_control"] >= SEPARATION_MARGIN
    assert comparisons["A_separates_from_B_by_the_declared_margin"] is True
    assert comparisons["A_separates_from_C_by_the_declared_margin"] is True
    assert comparisons["A_separates_from_D_by_the_declared_margin"] is True
    contribution = comparisons["memory_contribution_attributable_to_content"]
    assert contribution["against_the_mismatch_control"] >= SEPARATION_MARGIN
    assert contribution["against_the_identity_control"] >= SEPARATION_MARGIN
    assert contribution["both_hold_by_the_declared_margin"] is True


def test_the_read_floor_is_the_declared_fraction_of_the_captured_deposit(receipt: dict) -> None:
    config = receipt["declared"]["config"]

    assert config["read_floor_fraction"] == READ_FLOOR_FRACTION
    assert config["hold_horizon_ticks"] == COMPACT.hold_horizon_ticks
    for record in receipt["arms"]:
        decision = record["decision"]
        assert decision["read_floor"] == pytest.approx(
            READ_FLOOR_FRACTION * decision["target_captured_deposit"]
        )
        assert decision["retrieved_reaches_the_floor"] is (
            record["retrieval"]["retrieved_deposit"] >= decision["read_floor"]
        )


def test_the_statistic_fires_under_the_policy_mutation(receipt: dict, arms: dict) -> None:
    """C's own page, with the retrieval ignored: the predicate must fire here."""

    mutated, plain_no_memory = arms[ARM_POLICY_MUTATED], arms[ARM_NO_MEMORY]

    assert mutated["policy"]["policy_mutated"] is True
    assert mutated["field_episode"] == plain_no_memory["field_episode"]
    assert mutated["act"]["page_before"] == plain_no_memory["act"]["page_before"]
    assert mutated["retrieval"]["retrieved_deposit"] == 0.0
    assert mutated["decision"]["retrieved_reaches_the_floor"] is False
    assert mutated["statistic"]["share_along_target"] >= PURSUIT_MARGIN
    assert plain_no_memory["statistic"]["share_along_target"] < PURSUIT_MARGIN
    firing = receipt["comparisons"]["firing_control"]
    assert firing["the_predicate_fires_under_the_mutation"] is True
    assert firing["the_unmutated_no_memory_arm_does_not_fire"] is True
    assert firing["mutated_share_against_the_unmutated_arm"] >= SEPARATION_MARGIN


def test_every_arm_actuated_something(receipt: dict, arms: dict) -> None:
    """A zero increment would make the shares undefined rather than zero."""

    energies = receipt["comparisons"]["every_arm_actuated_something"]["act_increment_energy"]

    assert set(energies) == set(arms)
    for name, energy in energies.items():
        assert energy > 0.0, name
        record = arms[name]
        assert record["act"]["accepted"] is True
        assert record["act"]["applied_work"] > 0.0
        assert record["statistic"]["act_increment_energy"] == pytest.approx(energy)


def test_the_reads_are_predictions_that_move_no_page_and_no_clock(
    receipt: dict, arms: dict
) -> None:
    for record in receipt["arms"]:
        retrieval = record["retrieval"]
        if retrieval["read_calls"] == 0:
            assert retrieval["readout_kind"] is None
            continue
        assert retrieval["readout_kind"] == "temporal-prediction"
        assert retrieval["readout_declares_evidence_added"] is False
    for episode in receipt["field_episodes"].values():
        assert episode["read_invariants"]["the_reads_change_no_page"] is True
        assert episode["read_invariants"]["page_before_the_reads"] == (
            episode["read_invariants"]["page_after_the_reads"]
        )
        assert episode["clocks"]["the_episode_moves_no_evidence_clock"] is True
        assert episode["clocks"]["generation_at_the_horizon"] > episode["clocks"][
            "generation_before_the_episode"
        ]
    clock = receipt["evidence_clock"]
    assert clock["an_admission_moves_the_evidence_clock"] is True
    assert clock["evidence_tick_after_the_admission"] == (
        clock["evidence_tick_before_the_admission"] + 1
    )
    verdicts = receipt["reading"]["verdicts"]
    assert verdicts["no_consumer_episode_moves_the_evidence_clock"] is True
    assert verdicts["no_field_episode_moves_the_evidence_clock"] is True
    assert verdicts["an_admission_moves_the_evidence_clock"] is True


def test_the_owner_route_runs_the_declared_loop(receipt: dict) -> None:
    target, mismatch = receipt["field_episodes"]["target"], receipt["field_episodes"]["mismatch"]
    for name, episode in (("target", target), ("mismatch", mismatch)):
        replay = episode["owner_route_against_the_declared_loop"]
        assert replay["replay_page_sha256"] == episode["held_page_sha256"], name
        assert replay["the_owner_route_reproduces_the_declared_loop"] is True, name
        assert episode["hold"]["advance_ticks"] == episode["hold_horizon_ticks"], name
        assert episode["hold"]["drive_accepted"] == episode["hold_horizon_ticks"], name
        assert episode["hold"]["drive_applied_work_total"] > 0.0, name

    blank = receipt["field_episodes"]["blank"]
    replay = blank["owner_route_against_the_declared_loop"]
    assert replay["the_batched_advance_is_the_single_tick_advance"] is True
    assert replay["batched_advance_page_sha256"] == blank["held_page_sha256"]
    assert replay["single_tick_advance_page_sha256"] == blank["held_page_sha256"]
    assert blank["held_page_sha256"] != blank["blank_page_sha256"]
    assert blank["gain"] is None
    assert blank["hold"]["drive_accepted"] == 0
    assert blank["hold"]["drive_skipped_ticks"] == blank["hold_horizon_ticks"]
    assert receipt["reading"]["verdicts"]["the_batched_blank_advance_is_the_single_tick_advance"]
    assert receipt["reading"]["verdicts"]["the_declared_holds_run_at_even_horizon_parity"]


def test_the_held_read_recovers_the_written_direction_and_misses_the_unwritten_one(
    receipt: dict,
) -> None:
    written = 0
    for episode in receipt["field_episodes"].values():
        reads = episode["read_on_the_held_page"]
        if episode["written_item"] is None:
            assert "post_hold_recovery_allowance" not in reads
            assert all(
                readout["recovered_deposit"] == 0.0
                and readout["read_frame_energy"] == 0.0
                for readout in reads["by_item"].values()
            )
            continue
        written += 1
        assert episode["hold_horizon_parity"] == "even"
        assert reads["post_hold_recovery_allowance"] == READ_RECOVERY_ALLOWANCE
        assert reads["the_written_directions_recovery_is_within_the_hold_allowance"] is True
        assert reads["written_direction_relative_difference"] <= READ_RECOVERY_ALLOWANCE
        # The raw difference is the hold's own measured phase: an even horizon sits
        # at the written phase, and the read is a squared projection of the held frame.
        assert abs(reads["signed_ratio_at_horizon"] - 1.0) < 1e-4
        assert reads["by_item"][episode["written_item"]]["recovered_deposit"] == (
            pytest.approx(
                receipt["captures"]["captured_deposits"][episode["written_item"]]
                * reads["signed_ratio_at_horizon"] ** 2,
                rel=1e-9,
            )
        )
        assert reads["the_unwritten_directions_recovery_misses_the_allowance"] is True
        assert reads["unwritten_direction_relative_difference"] > READ_RECOVERY_ALLOWANCE
        assert reads["unwritten_item"] != episode["written_item"]
    assert written == len(receipt["field_episodes"]) - 1


def test_the_declared_directions_are_distinct_in_the_read_frame(receipt: dict) -> None:
    captures = receipt["captures"]

    assert captures["greatest_off_diagonal_squared_cosine"] <= ORTHOGONALITY_ALLOWANCE
    assert captures["on_diagonal_squared_cosine_min"] == pytest.approx(1.0)
    assert captures["on_diagonal_squared_cosine_max"] == pytest.approx(1.0)
    assert captures["the_declared_candidates_are_orthogonal_in_the_read_frame"] is True
    assert receipt["reading"]["verdicts"][
        "the_declared_candidates_are_orthogonal_in_the_read_frame"
    ] is True


def test_the_neutral_gain_is_measured_once_and_neutral_on_every_held_page(receipt: dict) -> None:
    gains = receipt["neutral_gain"]
    refinement = gains["refinement"]
    probes = gains["neutrality_on_the_written_items_pages"]

    assert refinement["measured_gain"] > 0.0
    assert refinement["cross_receipt_reference"][
        "the_refinement_reproduces_the_cited_gain"
    ] is True
    assert refinement["cross_receipt_reference"]["cited_gain"] == CITED_NEUTRAL_GAIN
    assert set(probes) == {"target", "mismatch"}
    for name, probe in probes.items():
        assert probe["gain"] == pytest.approx(refinement["measured_gain"]), name
        assert probe["retention_at_the_measured_gain"] == pytest.approx(
            1.0, abs=refinement["tolerance"]
        ), name
        assert (
            probe["retention_at_the_measured_gain"] > probe["retention_with_no_drive"]
        ), name
        assert probe["retention_with_no_drive"] < 1.0, name
        assert probe["the_measured_gain_is_neutral_on_this_items_page"] is True, name
    for name, episode in receipt["field_episodes"].items():
        if episode["written_item"] is None:
            assert episode["gain"] is None, name
            continue
        assert episode["gain"] == pytest.approx(refinement["measured_gain"]), name
    assert receipt["reading"]["verdicts"][
        "the_measured_gain_is_neutral_on_both_written_items_pages"
    ] is True


def test_the_receipt_states_what_the_prediction_declaration_means(receipt: dict) -> None:
    prediction = receipt["reading"]["prediction_reading"]

    assert prediction["does_this_demonstration_need_the_read_treated_as_evidence"] is False
    assert prediction["what_the_alternative_declaration_would_move"][
        "measured_evidence_clock_after_the_admission"
    ] == (
        prediction["what_the_alternative_declaration_would_move"][
            "measured_evidence_clock_before_the_admission"
        ]
        + 1
    )
    assert "temporal-prediction" in prediction["the_reads_declaration"]
    assert "intervention" in prediction["what_it_means_for_this_consumer"]
    assert receipt["reading"]["verdicts"]["the_reads_are_declared_temporal_predictions"] is True
    assert receipt["reading"]["honest_negatives"] == [
        negative
        for negative in receipt["reading"]["honest_negatives"]
        if isinstance(negative, str)
    ]


def test_the_receipt_digest_is_deterministic_and_covers_the_measurements(receipt: dict) -> None:
    body = {key: value for key, value in receipt.items() if key != "receipt_digest"}

    assert receipt["receipt_digest"] == receipt_digest(body)

    # A pure function of the measured body: re-serialising it in a different key
    # order, and re-timing it, leave the digest alone.
    reordered = json.loads(json.dumps(body, sort_keys=True))
    assert receipt_digest(reordered) == receipt["receipt_digest"]
    assert "runtime_seconds" in STRIP_KEYS and "runtime_seconds" in body
    retimed = {**body, "runtime_seconds": body["runtime_seconds"] + 1.0e6}
    assert receipt_digest(retimed) == receipt["receipt_digest"]

    mutated_statistic = {key: value for key, value in body.items()}
    mutated_statistic["comparisons"] = {
        **mutated_statistic["comparisons"],
        "C_share_along_target": mutated_statistic["comparisons"]["C_share_along_target"] + 1.0,
    }
    assert receipt_digest(mutated_statistic) != receipt["receipt_digest"]

    mutated_arms = {key: value for key, value in body.items()}
    mutated_arms["arms"] = [
        {**record, "retrieval": {**record["retrieval"], "retrieved_deposit": 12345.0}}
        if record["arm"] == ARM_MEMORY_USED
        else record
        for record in mutated_arms["arms"]
    ]
    assert receipt_digest(mutated_arms) != receipt["receipt_digest"]

    mutated_reading = {key: value for key, value in body.items()}
    mutated_reading["reading"] = {
        **mutated_reading["reading"],
        "verdicts": {
            **mutated_reading["reading"]["verdicts"],
            "the_memory_arm_pursues_the_target": False,
        },
    }
    assert receipt_digest(mutated_reading) != receipt["receipt_digest"]


def test_the_receipt_lands_beside_a_declared_neighbourhood(receipt: dict) -> None:
    """The shipped path is a declared location and the runner writes nothing else."""

    assert RECEIPT_PATH.parent.name == "memory-consumer-path"
    assert RECEIPT_PATH.parent.parent.name == "_diag"
    assert receipt["question"].endswith("?")
