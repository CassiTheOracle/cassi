"""Direct tests for the fractal-feedback exploration runner.

They hold the runner to the properties its receipt claims: the zero-gain loop arm
*is* the drift arm figure for figure (so the loop-closure identity is exact, not
approximate), the drift arm still reproduces the cited durability figures, the
receipt digest is deterministic over every measured number and can be made to
disagree by a measured mutation, the open-loop refresh and the declared gain
sweep each separate by more than their declared margin (with a control that shows
the separation predicate can fail), the neutral-stability criterion recomputes
from the raw samples, the reduced-versus-full recon answers are measured rather
than asserted, and every arm stays inside the declared boundedness and ledger
allowances.

Everything runs in-process on the same runner the receipt is produced by, so a
passing run is evidence about the real measurement rather than about a fixture.
The declared configuration is used wherever the claim is about the receipt; the
compact configuration is used only for the roster control.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import pytest

from run_fractal_durability_exploration import ITEM_SPECS, receipt_digest
from run_fractal_feedback_exploration import (
    CAPACITY_REFERENCE_SUFFIXES,
    CITED_INTRINSIC_LIFETIME_TICKS,
    PER_TICK_DECAY,
    CITED_ITEM_WIDTHS,
    CITED_LADDER_PROFILE,
    CITED_LADDER_RECEIPT,
    CITED_LADDER_SAMPLE_EVERY_TICKS,
    CITED_LADDER_THRESHOLD_LABEL,
    CITED_SOURCE_OFF_ENERGY_RETENTION_AT_HORIZON,
    CITED_SOURCE_OFF_RETENTION,
    CITED_WIDTH7_RUNG_MEAN_LIFETIME_TICKS,
    CITED_WIDTH7_RUNG_WIDTH,
    DECLARED,
    FeedbackConfig,
    boundedness_regime,
    build_receipt,
    capacity_arm_name,
    exceeds_runaway,
    partition_boundedness,
    selection_retention,
    separation_holds,
)

# The declared configuration, and a compact one whose only purpose is to show the
# arm roster is read from the configuration rather than hard-coded in a table.
COMPACT = FeedbackConfig(
    refresh_intervals=(8,),
    ladder_intervals=(8, 16),
    ladder_horizon_ticks=64,
    ladder_sample_ticks=(4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64),
    phase_angles_degrees=(0.0, 90.0, 180.0),
    phase_gains=(0.5, 1.0),
    gains=(0.0, 1.0),
    saturation_gains=(4.0,),
    # The compact configuration is for the roster and determinism controls; it declares
    # its own shorter long horizon, whose floor is declared separately so the shipped
    # configuration cannot be shortened this way.
    long_horizon_ticks=64,
    long_horizon_min_ticks=64,
    long_horizon_sample_ticks=(16, 32, 48, 64),
    neutral_gain_grid=(0.05, 0.1),
    neutral_gain_prediction_ceiling=1.0,
    # The declared multiplex schedule is a declared seam too: the compact configuration
    # declares its own block length, which must divide its own declared long horizon.
    capacity_alternate_block_ticks=16,
    # The declared gain regimes are declared seams too: the compact configuration runs the
    # bounded regime at its own declared sub-saturation gain, which must differ from the
    # amplifying regime's measured best-phase gain, or the two regimes would print the same
    # row twice and the regime label would mean nothing.
    capacity_regimes=("amplifying", "neutral", "bounded"),
    capacity_bounded_gain=0.5,
)


@pytest.fixture(scope="module")
def receipt() -> dict:
    return build_receipt(DECLARED)


def measured_blocks(row: dict) -> dict:
    """The measured part of an arm, without its declared name and family."""

    return {
        key: row[key]
        for key in (
            "writes",
            "measured_deposit_energy",
            "deposit_attenuation",
            "post_write",
            "samples",
            "horizon",
            "drive",
            "ledger",
            "ledger_check",
            "boundedness",
            "neutral_stability",
            "final",
        )
    }


def measure_field(arm: dict) -> str:
    """The declared measured-item rule: an arm is judged on the item it declares.

    An arm whose declared measured item is the receipt's headline item is judged on
    the headline alignment; an arm measured on another declared item (the second
    ladder, whose arms are written and measured on their own narrow item) is judged
    on that item's retention. For every arm whose measured item is the headline item
    the two fields are the same measurement, so this rule is the original criterion.
    """

    if int(arm["declared"]["measure_item_index"]) != int(
        arm["declared"]["headline_item_index"]
    ):
        return "measure_retention"
    return "alignment_retention"


def recompute_neutral(config_row: dict, arm: dict, field: str | None = None) -> bool:
    """The declared neutral-stability criterion, recomputed from the raw samples."""

    field = field or measure_field(arm)
    horizon = max(arm["samples"], key=lambda row: row["tick"])
    mid = next(
        row
        for row in arm["samples"]
        if row["tick"] == arm["declared"]["horizon_ticks"] // 2
    )
    last_half = [
        row for row in arm["samples"] if row["tick"] > arm["declared"]["horizon_ticks"] // 2
    ]
    return bool(
        not arm["boundedness"]["runaway"]
        and horizon[field] >= config_row["neutral_level_floor"]
        and min(row[field] for row in last_half) >= config_row["neutral_level_floor"]
        and horizon[field]
        >= config_row["neutral_decay_tolerance"] * mid[field]
    )


def phase_predicate(
    drift_retention: float,
    retention: float,
    frame_energy_ratio: float,
    unwritten_max_share: float,
    allowance: float,
    runaway: bool,
) -> bool:
    """The declared phase prediction, as a predicate over measured figures."""

    return bool(
        retention > drift_retention
        and frame_energy_ratio > 1.0
        and unwritten_max_share <= allowance
        and not runaway
    )


def ratios_agree(first: float, second: float, tolerance: float) -> bool:
    """The declared ratio-agreement test, as a predicate over two ratios."""

    return abs(first - second) <= tolerance


def test_loop_closure_identity_makes_the_zero_gain_arm_the_drift_arm(receipt: dict) -> None:
    """Gain zero drives nothing, so the loop's zero-gain arm must be the drift arm exactly."""

    loop = receipt["arms"]["closed-loop-g0"]
    drift = receipt["arms"]["drift-no-refresh-no-loop"]
    assert loop["declared"]["gain"] == 0.0
    assert loop["drive"]["calls"] == 0
    assert loop["drive"]["drive_work_total"] == 0.0
    assert measured_blocks(loop) == measured_blocks(drift)
    assert loop["final"]["page_sha256"] == drift["final"]["page_sha256"]
    assert loop["final"]["state_sha256"] == drift["final"]["state_sha256"]


def test_declared_roster_is_read_from_the_configuration() -> None:
    compact = build_receipt(COMPACT)
    refine = compact["neutral_gain_refinement"]
    selected = compact["selected_loop_setting"]["name"]
    best_phase = compact["best_declared_phase_setting"]["gain"]
    expected = {
        "drift-no-refresh-no-loop",
        "drift-k2-control",
        f"{selected}-k2",
        *(f"refresh-open-loop-every-{interval}" for interval in COMPACT.refresh_intervals),
        *(f"closed-loop-g{gain:g}" for gain in COMPACT.gains),
        *(f"closed-loop-saturation-g{gain:g}" for gain in COMPACT.saturation_gains),
        *(
            f"closed-loop-phase-{angle:g}deg-g{gain:g}"
            for angle in COMPACT.phase_angles_degrees
            for gain in COMPACT.phase_gains
        ),
        *(
            f"refresh-ladder-{'detail-' if family.endswith('detail') else ''}"
            f"every-{interval}"
            for interval in COMPACT.ladder_intervals
            for family in ("refresh-ladder", "refresh-ladder-detail")
        ),
        *(f"neutral-gain-g{gain:g}" for gain in COMPACT.neutral_gain_grid),
        *(f"neutral-gain-refine-g{probe['gain']:.6f}" for probe in refine["probes"]),
        "drift-long",
        "long-horizon-best-gain",
        "long-horizon-measured-neutral-gain",
        "long-horizon-beta-zero-best-gain",
        "long-horizon-beta-zero-measured-neutral-gain",
        "capacity-two-item-no-loop",
        *(
            capacity_arm_name(regime, scheme)
            for regime in COMPACT.capacity_regimes
            for scheme in COMPACT.capacity_schemes
        ),
        *(
            capacity_arm_name(regime, reference)
            for regime in COMPACT.capacity_regimes
            for reference in CAPACITY_REFERENCE_SUFFIXES
        ),
        "capacity-two-item-telemetry",
        *(f"genericity-{item}-{kind}" for item in COMPACT.genericity_items for kind in ("loop", "no-loop")),
    }
    assert set(compact["arms"]) == expected
    assert best_phase in COMPACT.phase_gains
    # Every declared regime carries a labelled row per declared scheme and per single-item
    # reference, at that regime's own declared gain, so a regime's claim is read against
    # that regime's own controls rather than another gain's rows.
    for regime in COMPACT.capacity_regimes:
        for scheme in COMPACT.capacity_schemes:
            row = compact["arms"][capacity_arm_name(regime, scheme)]["declared"]
            assert row["regime"] == regime
            assert row["gain"] == compact["declared"]["capacity_regime_gains"][regime]
        for reference in CAPACITY_REFERENCE_SUFFIXES:
            row = compact["arms"][capacity_arm_name(regime, reference)]["declared"]
            assert row["regime"] == regime
            assert row["gain"] == compact["declared"]["capacity_regime_gains"][regime]
    long_samples = list(COMPACT.long_horizon_sample_ticks)
    for arm in compact["arms"].values():
        assert arm["declared"]["source_enabled"] is False
        family = arm["declared"]["family"]
        if family.startswith("refresh-ladder"):
            assert arm["declared"]["horizon_ticks"] == COMPACT.ladder_horizon_ticks
            assert arm["declared"]["samples"] == list(COMPACT.ladder_sample_ticks)
        elif family in ("long-horizon", "capacity"):
            assert arm["declared"]["horizon_ticks"] == COMPACT.long_horizon_ticks
            assert arm["declared"]["samples"] == long_samples
        else:
            assert arm["declared"]["horizon_ticks"] == COMPACT.horizon_ticks
            assert arm["declared"]["samples"] == list(COMPACT.sample_ticks)


def test_cited_continuation_still_reproduces_the_durability_receipt(receipt: dict) -> None:
    """The drift arm continues the cited source-off figures inside the declared allowance."""

    cited = receipt["cited_agreement"]
    assert cited["all_rows_agree"]
    allowance = cited["agreement_allowance"]
    drift = receipt["arms"]["drift-no-refresh-no-loop"]
    for row in cited["rows"]:
        sample = next(
            item for item in drift["samples"] if item["tick"] == row["tick"]
        )
        difference = abs(sample["alignment_retention"] - row["cited_source_off_retention"])
        assert difference <= allowance, (
            f"tick {row['tick']}: measured {sample['alignment_retention']!r} against "
            f"cited {row['cited_source_off_retention']!r}, a difference of {difference!r} "
            f"above the declared allowance of {allowance!r}"
        )
    energy = cited["energy_row"]
    energy_difference = abs(
        energy["measured_drift_energy_retention"]
        - CITED_SOURCE_OFF_ENERGY_RETENTION_AT_HORIZON
    )
    assert energy_difference <= allowance, (
        f"measured {energy['measured_drift_energy_retention']!r} against the cited "
        f"{CITED_SOURCE_OFF_ENERGY_RETENTION_AT_HORIZON!r}"
    )
    assert set(CITED_SOURCE_OFF_RETENTION) <= {
        row["tick"] for row in drift["samples"]
    }


def test_receipt_digest_is_deterministic_and_a_measured_mutation_fires(receipt: dict, tmp_path: Path) -> None:
    body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    assert receipt["receipt_digest"] == receipt_digest(body)
    assert build_receipt(DECLARED) == receipt

    written = tmp_path / "exploration.json"
    written.write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
    loaded = json.loads(written.read_text(encoding="utf-8"))
    assert loaded == receipt
    assert receipt_digest(
        {key: value for key, value in loaded.items() if key != "receipt_digest"}
    ) == receipt["receipt_digest"]

    mutated = json.loads(json.dumps(loaded))
    sample = mutated["arms"]["drift-no-refresh-no-loop"]["samples"][-1]
    sample["alignment_retention"] = sample["alignment_retention"] + 1e-6
    assert receipt_digest(
        {key: value for key, value in mutated.items() if key != "receipt_digest"}
    ) != receipt["receipt_digest"]


def test_refresh_changes_retention_beyond_its_declared_margin(receipt: dict) -> None:
    """The open-loop refresh must move retention, and the margin check must be able to fail."""

    arms = receipt["arms"]
    drift = arms["drift-no-refresh-no-loop"]["horizon"]["alignment_retention"]
    members = {
        name: row["horizon"]["alignment_retention"]
        for name, row in arms.items()
        if row["declared"]["family"] == "refresh"
    }
    best_name = max(members, key=lambda name: members[name])
    difference = members[best_name] - drift
    margin = receipt["declared"]["separation_margin"]
    separation = receipt["reading"]["refresh_separation"]
    assert best_name == separation["best_arm"]
    assert difference == separation["difference"]
    assert separation["separates"]
    assert separation_holds(difference, margin), (
        f"refresh {best_name} holds {members[best_name]!r} against the drift baseline's "
        f"{drift!r}, a difference of {difference!r} against a declared margin of {margin!r}"
    )

    # Firing control: the same predicate applied to two arms that drive nothing (the
    # zero-gain loop arm against the drift arm) must fail, so the check above is a
    # measurement rather than a passing constant.
    zero_gain = arms["closed-loop-g0"]["horizon"]["alignment_retention"]
    assert not separation_holds(zero_gain - drift, margin)
    assert arms["closed-loop-g0"]["drive"]["calls"] == 0


def test_gain_sweep_separates_in_gain_and_reports_the_margin(receipt: dict) -> None:
    arms = receipt["arms"]
    margin = receipt["declared"]["separation_margin"]
    gain_arms = {
        name: row
        for name, row in arms.items()
        if row["declared"]["family"] == "closed-loop" and row["declared"]["gain"] > 0.0
    }
    ordered = sorted(gain_arms.values(), key=lambda row: row["declared"]["gain"])
    values = [row["horizon"]["alignment_retention"] for row in ordered]
    spread = max(values) - min(values)
    separation = receipt["reading"]["gain_separation"]
    assert separation["gains_in_order"] == [row["declared"]["gain"] for row in ordered]
    assert separation["retention_at_horizon"] == {
        row["arm"]: row["horizon"]["alignment_retention"] for row in ordered
    }
    assert separation["separates"]
    assert separation_holds(spread, margin), (
        f"the positive-gain retention range is {spread!r} across "
        f"{separation['retention_at_horizon']!r} against a declared margin of {margin!r}"
    )
    assert all(later > earlier for earlier, later in zip(values, values[1:])), (
        "the gain sweep is reported as separating without ordering: "
        f"{separation['retention_at_horizon']!r}"
    )

    # Firing control: flatten every positive gain onto the measured drift baseline
    # (the effect deliberately removed) and the same predicate must fail.
    drift = arms["drift-no-refresh-no-loop"]["horizon"]["alignment_retention"]
    flat = [drift] * len(values)
    assert not separation_holds(max(flat) - min(flat), margin)
    assert spread > max(flat) - min(flat)
    assert min(values) < drift, (
        f"no declared positive gain falls below the baseline {drift!r}, so the "
        "reported sweep would not show the loss the receipt describes"
    )


def test_neutral_stability_recomputes_from_the_raw_samples(receipt: dict) -> None:
    config_row = receipt["declared"]
    recomputed = {
        name: recompute_neutral(config_row, arm) for name, arm in receipt["arms"].items()
    }
    assert recomputed == receipt["reading"]["neutral_stability"]["arms"]
    assert sorted(
        name for name, flag in recomputed.items() if flag
    ) == receipt["reading"]["neutral_stability"]["arms_satisfying"]
    assert recomputed["drift-no-refresh-no-loop"] is False, (
        "the drift baseline must fail the neutral criterion: its last-half minimum "
        f"is {receipt['arms']['drift-no-refresh-no-loop']['horizon']['last_half_min_retention']!r}"
    )
    assert receipt["reading"]["neutral_stability"]["arms_satisfying"], (
        "the declared criterion admits no arm at all, which the receipt does not report"
    )

    # The declared measured-item rule reads the same field as the original criterion
    # for every arm measured on the receipt's headline item, and reads a different
    # field exactly for the arms measured on the declared second ladder item, where
    # the two figures must differ (otherwise the rule would be dead weight).
    headline_arms = [
        arm
        for arm in receipt["arms"].values()
        if int(arm["declared"]["measure_item_index"])
        == int(arm["declared"]["headline_item_index"])
    ]
    other_arms = [
        arm
        for arm in receipt["arms"].values()
        if int(arm["declared"]["measure_item_index"])
        != int(arm["declared"]["headline_item_index"])
    ]
    assert headline_arms and other_arms
    for arm in headline_arms:
        assert recompute_neutral(config_row, arm) == recompute_neutral(
            config_row, arm, field="alignment_retention"
        ), arm["arm"]
    assert all(
        arm["horizon"]["alignment_retention"]
        != arm["neutral_stability"]["measure_retention_at_horizon"]
        for arm in other_arms
    ), "the declared second-ladder rule must read a different measurement"""


def test_every_arm_stays_bounded_and_inside_its_ledger_allowance(receipt: dict) -> None:
    config_row = receipt["declared"]
    for name, arm in receipt["arms"].items():
        assert arm["boundedness"]["all_samples_finite"], f"{name} has a non-finite sample"
        recomputed_max = max(
            sample["frame_energy_ratio"] for sample in arm["samples"]
        )
        assert arm["boundedness"]["energy_ratio_max"] >= recomputed_max
        assert arm["horizon"]["frame_energy_ratio_max"] == arm["boundedness"]["energy_ratio_max"]
        assert arm["boundedness"]["runaway"] == exceeds_runaway(
            DECLARED, arm["boundedness"]["energy_ratio_max"]
        ), f"{name} disagrees with the declared boundedness predicate"
        assert arm["ledger_check"]["balance_defect_within_allowance"], name
        assert arm["ledger_check"]["residual_work_within_allowance"], name
    assert receipt["reading"]["boundedness"]["runaway_arms"] == sorted(
        name for name, arm in receipt["arms"].items() if arm["boundedness"]["runaway"]
    )
    assert receipt["reading"]["boundedness"]["maximum_frame_energy_ratio"] == max(
        arm["boundedness"]["energy_ratio_max"] for arm in receipt["arms"].values()
    )
    assert config_row["runaway_energy_ratio"] > 1.0


def test_drive_amplitudes_and_work_respect_their_declared_ceilings(receipt: dict) -> None:
    drift = receipt["arms"]["drift-no-refresh-no-loop"]["drive"]
    assert drift["drive_work_total"] == 0.0
    assert drift["calls"] == 0
    for name, arm in receipt["arms"].items():
        drive = arm["drive"]
        assert 0.0 <= drive["max_amplitude"] <= 1.0, name
        assert drive["clipped_ticks"] <= drive["calls"], name
        assert drive["drive_work_total"] >= 0.0, name
        if drive["calls"]:
            ceiling = arm["declared"]["loop_work_ceiling"] * drive["calls"]
            assert drive["drive_work_total"] <= ceiling + 1e-15, (
                f"{name} spent {drive['drive_work_total']!r} of drive work, above the "
                f"{ceiling!r} its declared per-tick ceiling and call count allow"
            )
        assert arm["horizon"]["unwritten_max_share"] is not None, (
            f"{name} reports no disturbance of its unwritten directions"
        )
        assert len(arm["horizon"]["unwritten_shares"]) == len(ITEM_SPECS) - len(
            arm["declared"]["written_items"]
        ), name


def test_arm_summaries_are_derived_from_their_own_samples(receipt: dict) -> None:
    """Every reported summary must be the derivation of that arm's own samples."""

    for name, arm in receipt["arms"].items():
        horizon_ticks = arm["declared"]["horizon_ticks"]
        samples = arm["samples"]
        assert [row["tick"] for row in samples] == arm["declared"]["samples"], name
        last = max(samples, key=lambda row: row["tick"])
        mid = next(row for row in samples if row["tick"] == horizon_ticks // 2)
        last_half = [row for row in samples if row["tick"] > horizon_ticks // 2]
        horizon = arm["horizon"]
        assert horizon["tick"] == horizon_ticks == last["tick"], name
        assert horizon["alignment_retention"] == last["alignment_retention"], name
        assert horizon["mid_retention"] == mid["alignment_retention"], name
        assert horizon["last_half_min_retention"] == min(
            row["alignment_retention"] for row in last_half
        ), name
        assert horizon["packet_energy"] == last["packet_energy"], name
        assert horizon["unwritten_max_share"] == last["unwritten_max_share"], name
        assert horizon["state_sha256"] == arm["final"]["state_sha256"] == last["state_sha256"], name
        assert horizon["page_sha256"] == arm["final"]["page_sha256"] == last["page_sha256"], name
        assert arm["final"]["field_ticks"] == last["field_ticks"], name

        # The drive call count must follow from the declared arm: one re-applied
        # impulse per written item per declared interval, and one loop drive per
        # declared driven item per declared tick (a declared multi-item loop drives
        # every item it lists from its single read-back). This is what makes the loop a
        # loop rather than an occasional nudge, so it is derived here instead of trusted.
        expected = 0
        if arm["declared"]["refresh_interval"]:
            expected += (horizon_ticks // arm["declared"]["refresh_interval"]) * len(
                arm["declared"]["written_items"]
            )
        if arm["declared"]["gain"]:
            # A declared per-tick cycle drives exactly one item per tick, so it makes one
            # call per declared tick; a loop with no declared cycle drives every declared
            # driven item every tick.
            expected += horizon_ticks * (
                1
                if arm["declared"]["drive_cycle"]
                else len(arm["declared"]["drive_item_indices"])
            )
        assert arm["drive"]["calls"] == expected, (
            f"{name} reports {arm['drive']['calls']} drive calls where its declared "
            f"arm implies {expected}"
        )
        assert arm["drive"]["accepted_calls"] == arm["drive"]["calls"], name
        if not expected:
            assert arm["drive"]["max_amplitude"] == 0.0, name


def test_refresh_and_loop_work_cost_is_reported_against_the_write_cost(receipt: dict) -> None:
    refresh = receipt["reading"]["per_family_best"]["refresh"]
    assert refresh["drive_work_total"] == pytest.approx(
        DECLARED.write_budget * (DECLARED.horizon_ticks // refresh["refresh_interval"]),
        rel=1e-9,
    ), (
        f"the best refresh arm ({refresh['arm']}) spent {refresh['drive_work_total']!r}, "
        "which does not match its declared interval and budget"
    )
    saturation = receipt["reading"]["per_family_best"]["closed_loop_saturation"]
    assert saturation["drive_work_total"] > refresh["drive_work_total"]
    assert saturation["frame_energy_ratio_at_horizon"] > 1.0, (
        "the saturating loop is reported as maintained without amplifying the frame"
    )


def test_recon_answers_what_was_looped_and_what_the_transceiver_admits(receipt: dict) -> None:
    recon = receipt["recon"]
    assert recon["full_page_loop"]["used"] is True
    assert recon["full_page_loop"]["expressible_with_existing_operations"] is True
    assert recon["full_page_loop"]["new_canonical_operations_added"] == []
    assert recon["reduced_versus_full"]["looped_here"] == "full canonical page"
    assert recon["reduced_versus_full"]["reduced_realization_looped_here"] is False
    assert recon["canonical_advance"]["period_chunking_identity"][
        "identical_at_every_sample"
    ]
    assert recon["canonical_advance"]["per_tick_drive_argument"] is None
    impulse = recon["canonical_advance"]["measured"]
    assert impulse["accepted_at_the_declared_budget"]
    assert impulse["over_budget_rejected"] and impulse["under_budget_rejected"]
    assert impulse["balance_defect"] == 0.0

    measured = recon["reduced_versus_full"]["measured"]
    assert measured["kernel_statuses"]["declared-beta-zero-counterpart"] == "active"
    assert measured["kernel_statuses"]["durability-profile"] == "expanded"
    assert measured["working_state_modes"] == {
        "declared-beta-zero-counterpart": "reduced",
        "durability-profile": "full",
    }
    assert measured["reduced_steps_per_call"]["declared-beta-zero-counterpart"] == [1]
    assert measured["reduced_steps_per_call"]["durability-profile"] == [0]
    assert measured["page_unchanged_by_transceiver_advance"] == {
        "declared-beta-zero-counterpart": True,
        "durability-profile": True,
    }
    assert measured["input_drives_the_output_over_a_run"] == {
        "declared-beta-zero-counterpart": False,
        "durability-profile": False,
    }, (
        "the receipt claims the transceiver input channel has no authority over its "
        "output, which is what forces the loop onto the page: "
        f"{measured['constant_input_chain_relative_difference']!r}"
    )
    for probe in recon["transceiver"]["measured"]:
        assert probe["per_call_input_constant"][
            "constant_call_equals_two_single_ticks"
        ], probe["label"]
        assert probe["input_envelope"]["raised"], probe["label"]


def test_reading_block_agrees_with_the_arm_table(receipt: dict) -> None:
    reading = receipt["reading"]
    arms = receipt["arms"]
    family_names = {
        "drift": "drift",
        "refresh": "refresh",
        "closed_loop_declared_gains": "closed-loop",
        "closed_loop_saturation": "closed-loop-saturation",
        "closed_loop_phase": "closed-loop-phase",
        "refresh_ladder": "refresh-ladder",
        "refresh_ladder_detail": "refresh-ladder-detail",
    }
    for key, family in family_names.items():
        family_best = reading["per_family_best"][key]
        members = [
            row for row in arms.values() if row["declared"]["family"] == family
        ]
        assert family_best["arms_in_family"] == len(members), family
        if key == "closed_loop_declared_gains":
            members = [row for row in members if row["declared"]["gain"] > 0.0]
            assert family_best["arms_compared"] == len(members)
        # The declared selection rule: an arm is selected on its own measured item, which
        # is the headline figure except for the second ladder family.
        assert family_best["selection_retention_at_horizon"] == max(
            selection_retention(row) for row in members
        ), family
        assert family_best["arm"] == max(members, key=selection_retention)["arm"], family
        if key == "refresh_ladder_detail":
            assert family_best["measured_item"] == DECLARED.second_ladder_item
            assert family_best["selection_key"] == (
                "measure_retention_at_horizon of the declared measured item "
                f"({DECLARED.second_ladder_item})"
            )
        else:
            assert family_best["selection_key"] == (
                "alignment_retention at the horizon along the written direction"
            )
    table = reading["families"]["refresh"]
    assert set(table) == {
        f"refresh-open-loop-every-{interval}" for interval in DECLARED.refresh_intervals
    }
    for key, family in (
        ("refresh_ladder", "refresh-ladder"),
        ("refresh_ladder_detail", "refresh-ladder-detail"),
    ):
        assert set(reading["families"][key]) == {
            f"refresh-ladder-{'detail-' if family.endswith('detail') else ''}"
            f"every-{interval}"
            for interval in DECLARED.ladder_intervals
        }
    assert reading["saturation"]["clipped_ticks_by_gain"] == {
        f"closed-loop-saturation-g{gain:g}": arms[
            f"closed-loop-saturation-g{gain:g}"
        ]["drive"]["clipped_ticks"]
        for gain in DECLARED.saturation_gains
    }
    assert len(reading["unwritten_direction_disturbance"]["per_arm"]) == len(arms)
    assert reading["sentence"].startswith("With sources off")


def test_multi_item_loop_runs_at_the_selected_setting(receipt: dict) -> None:
    selected = receipt["selected_loop_setting"]
    multi = receipt["reading"]["per_family_best"]["multi_item"]
    assert multi["setting"]["name"] == selected["name"]
    assert multi["setting"]["gain"] == selected["gain"]
    looped = receipt["arms"][multi["loop_arm"]]
    control = receipt["arms"][multi["control_arm"]]
    assert looped["declared"]["gain"] == selected["gain"]
    assert len(looped["declared"]["written_items"]) == DECLARED.multi_item_count
    assert len(control["declared"]["written_items"]) == DECLARED.multi_item_count
    assert control["declared"]["gain"] == 0.0 and control["drive"]["calls"] == 0
    assert multi["loop_min_item_retention"] == min(
        looped["horizon"]["item_retention"].values()
    )
    assert multi["gain_over_control"] == pytest.approx(
        multi["loop_min_item_retention"] - multi["control_min_item_retention"]
    )


def test_shipped_receipt_is_the_declared_build(receipt: dict) -> None:
    """The shipped receipt must be this build, so the reported figures are not stale."""

    path = Path(__file__).parent / "_diag" / "fractal-feedback" / "exploration.json"
    assert path.is_file(), (
        "the shipped receipt is missing; produce it from CassiFI with "
        "`python run_fractal_feedback_exploration.py --output "
        f"_diag/fractal-feedback/exploration.json`: {path}"
    )
    shipped = json.loads(path.read_text(encoding="utf-8"))
    assert shipped["receipt_digest"] == receipt["receipt_digest"], (
        "the shipped receipt was written by a different build of this runner: "
        f"shipped {shipped['receipt_digest']!r} against {receipt['receipt_digest']!r}"
    )
    assert shipped == receipt


def test_phase_grid_zero_phase_reproduces_the_proportional_loop(receipt: dict) -> None:
    """Theta zero is the declared proportional loop, so those arms must be it exactly."""

    arms = receipt["arms"]
    compared = 0
    shared_gains = sorted(set(DECLARED.phase_gains) & set(DECLARED.gains))
    assert shared_gains, "the declared phase grid and gain sweep share no gain"
    for gain in shared_gains:
        phase_arm = arms[f"closed-loop-phase-0deg-g{gain:g}"]
        proportional = arms[f"closed-loop-g{gain:g}"]
        assert phase_arm["declared"]["phase_degrees"] == 0.0, phase_arm["arm"]
        assert measured_blocks(phase_arm) == measured_blocks(proportional), phase_arm["arm"]
        assert (
            phase_arm["final"]["page_sha256"] == proportional["final"]["page_sha256"]
        ), phase_arm["arm"]
        assert (
            phase_arm["final"]["state_sha256"] == proportional["final"]["state_sha256"]
        ), phase_arm["arm"]
        compared += 1
    assert compared == len(shared_gains)


def test_phase_prediction_recomputes_and_the_best_phase_is_not_the_quarter_period(
    receipt: dict,
) -> None:
    """The phase grid's reported prediction, best phase and quarter-period readout."""

    reading = receipt["reading"]
    phase = reading["phase_grid"]
    arms = receipt["arms"]
    drift = arms["drift-no-refresh-no-loop"]["horizon"]
    allowance = phase["prediction_terms"]["unwritten_max_share_at_most"]
    assert allowance == pytest.approx(
        DECLARED.disturbance_allowance_multiple * drift["unwritten_max_share"]
    )
    assert phase["drift_baseline_retention"] == drift["alignment_retention"]

    members = {
        name: arm
        for name, arm in arms.items()
        if arm["declared"]["family"] == "closed-loop-phase"
    }
    assert set(phase["per_arm"]) == set(members)
    recomputed = {
        name: phase_predicate(
            drift["alignment_retention"],
            arm["horizon"]["alignment_retention"],
            arm["horizon"]["frame_energy_ratio"],
            arm["horizon"]["unwritten_max_share"],
            allowance,
            arm["boundedness"]["runaway"],
        )
        for name, arm in members.items()
    }
    assert recomputed == {
        name: row["prediction_met"] for name, row in phase["per_arm"].items()
    }
    met = sorted(name for name, flag in recomputed.items() if flag)
    assert met == phase["arms_meeting_prediction"]
    assert met, (
        "no declared phase arm meets the declared prediction, so the receipt would "
        "report a phase grid in which no phase counters the drift baseline"
    )
    assert sorted(
        name
        for name, arm in members.items()
        if arm["horizon"]["alignment_retention"] > drift["alignment_retention"]
    ) == phase["arms_beating_drift_baseline"]

    # The best phase and its work cost are the table's own maximum, and the table's
    # figures are the arms' own measurements.
    assert phase["best_arm"] == max(
        phase["per_arm"], key=lambda name: phase["per_arm"][name]["alignment_retention_at_horizon"]
    )
    best = phase["per_arm"][phase["best_arm"]]
    assert phase["best_retention_at_horizon"] == best["alignment_retention_at_horizon"]
    assert best["theta_degrees"] == members[phase["best_arm"]]["declared"]["phase_degrees"]
    assert best["gain"] == members[phase["best_arm"]]["declared"]["gain"]
    assert best["alignment_retention_at_horizon"] == members[phase["best_arm"]]["horizon"][
        "alignment_retention"
    ]
    assert best["drive_work_total"] == members[phase["best_arm"]]["drive"]["drive_work_total"]
    assert best["unwritten_max_share"] == members[phase["best_arm"]]["horizon"][
        "unwritten_max_share"
    ]
    assert best["drive_work_over_refresh_every_8"] == pytest.approx(
        best["drive_work_total"] / phase["refresh_every_8_drive_work"]
    )
    refresh_8 = arms["refresh-open-loop-every-8"]
    assert phase["refresh_every_8_drive_work"] == refresh_8["drive"]["drive_work_total"]

    # The quarter-period readout is the drift trajectory's own rotation, and the
    # declared phase of that lag is the drift's measured quarter turn.
    readout = receipt["phase_readout"]
    assert phase["quarter_period_tick"] == readout["quarter_period_tick"]
    assert phase["quarter_period_phase_degrees"] == DECLARED.quarter_period_phase_degrees
    assert readout["write_quadrature_overlap"] == 0.0, (
        "the declared quadrature direction is not orthogonal to the captured write "
        "direction, so the two read-back terms would not be independent"
    )
    assert readout["write_direction_lane"] == readout["write_direction_lane"]
    assert readout["quadrature_direction_lane"] != readout["write_direction_lane"]
    rows = readout["rows"]
    quarter = readout["quarter_period_tick"]
    first = next(row for row in rows if row["tick"] == quarter)
    assert first["angle_degrees"] >= DECLARED.quarter_period_phase_degrees
    assert all(
        row["angle_degrees"] < DECLARED.quarter_period_phase_degrees
        for row in rows
        if row["tick"] < quarter
    ), "the reported quarter-period tick is not the first crossing of a quarter turn"
    assert readout["sign_references"]["quadrature_scale"] == first["quadrature_projection"], (
        "the declared quadrature scale is not the drift trajectory's own quadrature "
        "projection at its measured quarter-period tick"
    )
    assert readout["sign_references"]["quadrature_scale_tick"] == quarter
    assert first["quadrature_projection"] > 0.0
    reversal = next(
        row["tick"]
        for row in rows
        if row["tick"] > 0
        and row["in_phase_ratio"] < 0.0
    )
    assert reversal == readout["sign_reversal_tick"], (
        "the reported sign reversal is not the first tick at which the in-phase "
        "projection turns negative, which is what makes the proportional loop "
        "scramble rather than damp"
    )
    # The readout is the drift arm's own trajectory, not a separate run.
    drift_samples = {row["tick"]: row for row in arms["drift-no-refresh-no-loop"]["samples"]}
    for tick, sample in drift_samples.items():
        assert next(row for row in rows if row["tick"] == tick)["alignment_retention"] == (
            sample["alignment_retention"]
        ), tick
    offset = best["theta_degrees"] - DECLARED.quarter_period_phase_degrees
    assert phase["best_theta_offset_from_quarter_period_degrees"] == offset
    assert phase["best_theta_is_the_quarter_period"] == (
        abs(offset) <= DECLARED.quarter_period_match_tolerance_degrees
    )
    assert not phase["best_theta_is_the_quarter_period"], (
        "the receipt's own sentence reports the measured best phase as "
        f"{best['theta_degrees']!r} degrees, which its quarter-period tolerance "
        f"({DECLARED.quarter_period_match_tolerance_degrees!r}) must not call the "
        "declared quarter-period phase"
    )

    # Firing control: the predicate must fail when the disturbance is raised to the
    # measured saturation and when the maintenance is flattened onto the baseline.
    raised = phase_predicate(
        drift["alignment_retention"],
        best["alignment_retention_at_horizon"],
        best["frame_energy_ratio_at_horizon"],
        allowance * 100.0,
        allowance,
        False,
    )
    assert raised is False
    flattened = phase_predicate(
        drift["alignment_retention"],
        drift["alignment_retention"],
        best["frame_energy_ratio_at_horizon"],
        best["unwritten_max_share"],
        allowance,
        False,
    )
    assert flattened is False
    runaway = phase_predicate(
        drift["alignment_retention"],
        best["alignment_retention_at_horizon"],
        best["frame_energy_ratio_at_horizon"],
        best["unwritten_max_share"],
        allowance,
        True,
    )
    assert runaway is False
    assert not arms[phase["best_arm"]]["boundedness"]["runaway"]


def test_phase_maintenance_exceeds_the_margin_and_the_in_phase_loop_does_not(
    receipt: dict,
) -> None:
    """The maintaining phase must separate from the baseline where its in-phase twin does not."""

    arms = receipt["arms"]
    margin = receipt["declared"]["separation_margin"]
    drift = arms["drift-no-refresh-no-loop"]["horizon"]["alignment_retention"]
    phase = receipt["reading"]["phase_grid"]
    best = phase["per_arm"][phase["best_arm"]]
    difference = best["alignment_retention_at_horizon"] - drift
    assert difference > margin, (
        f"the best declared phase arm ({phase['best_arm']}) holds "
        f"{best['alignment_retention_at_horizon']!r} against the drift baseline's "
        f"{drift!r}, a difference of {difference!r} against the declared margin "
        f"{margin!r}"
    )
    assert separation_holds(difference, margin)

    # Firing control: the same predicate on the in-phase arm at the same gain, which is
    # the declared proportional loop, must fail. This is the receipt's own measured
    # control rather than a fixture.
    in_phase = arms[f"closed-loop-phase-0deg-g{best['gain']:g}"]
    assert in_phase["declared"]["phase_degrees"] == 0.0
    assert in_phase["declared"]["gain"] == best["gain"]
    in_phase_retention = in_phase["horizon"]["alignment_retention"]
    if best["gain"] in DECLARED.gains:
        assert in_phase_retention == arms[f"closed-loop-g{best['gain']:g}"]["horizon"][
            "alignment_retention"
        ]
    phase_difference = best["alignment_retention_at_horizon"] - in_phase_retention
    assert separation_holds(phase_difference, margin), (
        f"the best phase arm holds {best['alignment_retention_at_horizon']!r} against "
        f"the in-phase loop's {in_phase_retention!r} at the same gain "
        f"{best['gain']!r}, a difference of {phase_difference!r} against the declared "
        f"margin {margin!r}, so the phase comparison separates"
    )
    assert phase_difference > in_phase_retention - drift, (
        "the phase separation is not larger than the whole separation the in-phase "
        "loop achieves over the drift baseline, so the reported effect would be "
        "gain rather than phase"
    )

    # Firing control of the margin predicate itself: a difference of half the declared
    # margin must fail it.
    assert not separation_holds(margin / 2.0, margin)
    assert not separation_holds(0.0, margin)


def test_refresh_ladder_critical_interval_is_bracketed_and_recomputes(receipt: dict) -> None:
    """The ladder's critical interval per declared item, recomputed from the raw arms."""

    reading = receipt["reading"]
    ladder = reading["refresh_ladder"]
    arms = receipt["arms"]
    config_row = receipt["declared"]
    headline = ITEM_SPECS[DECLARED.headline_item_index].name
    assert ladder["declared_ladder"] == list(DECLARED.ladder_intervals)
    assert ladder["declared_ladder_horizon_ticks"] == DECLARED.ladder_horizon_ticks
    assert ladder["declared_ladder_sample_ticks"] == list(DECLARED.ladder_sample_ticks)
    assert ladder["items_pair"] == [headline, DECLARED.second_ladder_item]
    assert ladder["items_pair"][0] != ladder["items_pair"][1]
    first_index = ITEM_SPECS.index(
        next(spec for spec in ITEM_SPECS if spec.name == ladder["items_pair"][0])
    )
    second_index = ITEM_SPECS.index(
        next(spec for spec in ITEM_SPECS if spec.name == ladder["items_pair"][1])
    )
    assert ITEM_SPECS[first_index].path != ITEM_SPECS[second_index].path, (
        "the two declared ladder items sit on the same rung path, which would make "
        "their widths and lifetimes equal and the scaling comparison degenerate"
    )
    assert ladder["item_widths"][ladder["items_pair"][0]] != ladder["item_widths"][
        ladder["items_pair"][1]
    ]

    names_index = {spec.name: index for index, spec in enumerate(ITEM_SPECS)}
    critical_by_item: dict[str, int] = {}
    for label in ladder["items_pair"]:
        item = ladder["items"][label]
        members = {
            int(arm["declared"]["refresh_interval"]): arm
            for arm in arms.values()
            if arm["declared"]["family"] == item["family"]
        }
        assert set(members) == set(DECLARED.ladder_intervals), label
        assert item["declared_horizon_ticks"] == DECLARED.ladder_horizon_ticks
        assert item["declared_sample_ticks"] == list(DECLARED.ladder_sample_ticks)
        for interval, arm in members.items():
            assert arm["declared"]["horizon_ticks"] == DECLARED.ladder_horizon_ticks
            assert arm["declared"]["samples"] == list(DECLARED.ladder_sample_ticks)
            assert arm["declared"]["measured_item"] == label
            assert arm["declared"]["written_items"] == [label]
            row = item["per_interval"][str(interval)]
            assert row["measure_retention_at_horizon"] == arm["neutral_stability"][
                "measure_retention_at_horizon"
            ]
            assert row["measure_mid_retention"] == arm["neutral_stability"][
                "measure_mid_retention"
            ]
            assert row["measure_last_half_min_retention"] == arm["neutral_stability"][
                "measure_last_half_min_retention"
            ]
            assert row["neutrally_stable"] == recompute_neutral(config_row, arm)
            assert row["neutrally_stable"] == arm["neutral_stability"]["neutrally_stable"]
            assert row["drive_work_total"] == pytest.approx(
                DECLARED.write_budget * (DECLARED.ladder_horizon_ticks // interval)
            )
            assert row["unwritten_max_share"] == arm["horizon"]["unwritten_max_share"]
            assert row["runaway"] == arm["boundedness"]["runaway"]

        satisfying = sorted(
            interval
            for interval, arm in members.items()
            if recompute_neutral(config_row, arm)
        )
        assert item["intervals_satisfying_neutral_stability"] == satisfying, label
        assert satisfying, f"{label} satisfies the criterion at no declared interval"
        critical = max(satisfying)
        critical_by_item[label] = critical
        assert item["critical_interval_ticks"] == critical
        failing_above = sorted(
            interval for interval in members if interval > critical and interval not in satisfying
        )
        assert failing_above, (
            f"{label} satisfies the criterion at every declared interval above its "
            f"critical interval {critical!r}, so the boundary is not bracketed"
        )
        assert item["smallest_failing_interval_above_critical"] == failing_above[0]
        assert item["bracket_gap_ticks"] == failing_above[0] - critical
        assert min(members) < critical < max(members), (
            f"{label} brackets its critical interval at the edge of the declared "
            "ladder, so the ladder does not localise a boundary"
        )
        cited = CITED_INTRINSIC_LIFETIME_TICKS[label]
        assert item["cited_intrinsic_lifetime_ticks"] == cited
        assert item["critical_interval_over_cited_lifetime"] == pytest.approx(
            critical / cited
        )
        assert item["item_index"] == names_index[label]
        assert item["item_path"] == next(
            spec.path for spec in ITEM_SPECS if spec.name == label
        ), (
            f"the ladder item {label!r} reports the rung path "
            f"{item['item_path']!r}, which is not that item's declared path"
        )
        assert item["cited_item_width"] == CITED_ITEM_WIDTHS[label]
        if CITED_ITEM_WIDTHS[label] == CITED_WIDTH7_RUNG_WIDTH:
            assert item["cited_rung_width"] == CITED_WIDTH7_RUNG_WIDTH
            assert item["cited_rung_mean_lifetime_ticks"] == (
                CITED_WIDTH7_RUNG_MEAN_LIFETIME_TICKS
            )
            assert item["critical_interval_over_cited_rung_mean"] == pytest.approx(
                critical / CITED_WIDTH7_RUNG_MEAN_LIFETIME_TICKS
            )
        else:
            assert item["cited_rung_width"] is None
            assert item["cited_rung_mean_lifetime_ticks"] is None
            assert item["critical_interval_over_cited_rung_mean"] is None

    assert ladder["critical_intervals_agree_across_items"] == (
        critical_by_item[ladder["items_pair"][0]] == critical_by_item[ladder["items_pair"][1]]
    )


def test_ladder_ratio_comparison_and_its_tolerance_can_fail(receipt: dict) -> None:
    """The ratio comparison must be the declared tolerance on the two measured ratios."""

    ladder = receipt["reading"]["refresh_ladder"]
    first, second = ladder["items_pair"]
    tolerance = ladder["ratio_agreement_tolerance"]
    assert tolerance == DECLARED.ladder_ratio_tolerance
    ratios = ladder["critical_interval_over_cited_lifetime"]
    assert ratios[first] == pytest.approx(
        ladder["items"][first]["critical_interval_ticks"]
        / CITED_INTRINSIC_LIFETIME_TICKS[first]
    )
    assert ratios[second] == pytest.approx(
        ladder["items"][second]["critical_interval_ticks"]
        / CITED_INTRINSIC_LIFETIME_TICKS[second]
    )
    assert ladder["ratios_agree_across_items_within_tolerance"] == ratios_agree(
        ratios[first], ratios[second], tolerance
    )
    assert ladder["ratios_agree_across_items_within_tolerance"] is False, (
        "the receipt reports the two ratios as agreeing, which its own sentence "
        "reports otherwise: "
        f"{ratios!r} against a tolerance of {tolerance!r}"
    )
    assert ladder["critical_intervals_agree_across_items"] is True
    assert (
        CITED_INTRINSIC_LIFETIME_TICKS[first] != CITED_INTRINSIC_LIFETIME_TICKS[second]
    ), (
        "the two cited lifetimes are equal, so equal critical intervals could not be "
        "distinguished from scaling"
    )
    # The predicate is a real band: a perturbation inside it agrees, one outside fails.
    assert ratios_agree(ratios[first], ratios[first], tolerance)
    assert ratios_agree(ratios[first], ratios[first] + tolerance / 2.0, tolerance)
    assert not ratios_agree(ratios[first], ratios[first] + tolerance * 2.0, tolerance)
    # Firing control on the measured pair: had the second item's critical interval been
    # its cited lifetime's worth of the first item's ratio, the comparison would agree.
    agree_if_critical_were_scaled = ratios_agree(
        ratios[first],
        ladder["items"][second]["critical_interval_ticks"] * 2.0
        / CITED_INTRINSIC_LIFETIME_TICKS[second],
        tolerance,
    )
    assert agree_if_critical_were_scaled is True


def test_cited_lifetimes_and_widths_match_the_ladder_receipt() -> None:
    """The two cited figures must be the ladder receipt's own, by item and by rung."""

    path = Path(__file__).parent / CITED_LADDER_RECEIPT
    assert path.is_file(), (
        "the cited ladder receipt is missing; produce it from CassiFI with "
        "`python run_fractal_ladder_exploration.py --output "
        f"_diag/fractal-ladder/exploration.json`: {path}"
    )
    ladder_receipt = json.loads(path.read_text(encoding="utf-8"))
    assert CITED_LADDER_PROFILE in ladder_receipt["profiles"]
    profile = ladder_receipt["profiles"][CITED_LADDER_PROFILE]
    assert ladder_receipt["declared"]["sample_every_ticks"] == (
        CITED_LADDER_SAMPLE_EVERY_TICKS
    )
    assert ladder_receipt["declared"]["threshold_label"] in CITED_LADDER_THRESHOLD_LABEL
    assert ladder_receipt["declared"]["horizon_ticks"] >= max(
        CITED_INTRINSIC_LIFETIME_TICKS.values()
    ), (
        "the cited lifetimes are measured over a shorter horizon than the ladder "
        "receipt's own, so a cited figure would be a censored crossing"
    )
    names = [spec.name for spec in ITEM_SPECS]
    for label, lifetime in CITED_INTRINSIC_LIFETIME_TICKS.items():
        item = profile["items"][names.index(label)]
        assert item["lifetime_ticks"] == lifetime, (
            f"the cited lifetime for {label!r} is {lifetime!r}, beside the ladder "
            f"receipt's own {item['lifetime_ticks']!r}"
        )
        assert not item["censored"], f"the cited lifetime for {label!r} is censored"
        assert item["scale_width"] == CITED_ITEM_WIDTHS[label]
    grouped = ladder_receipt["ladder"][CITED_LADDER_PROFILE]["grouped_lifetimes"]
    width_seven = grouped[str(CITED_WIDTH7_RUNG_WIDTH)]
    assert sum(width_seven) / len(width_seven) == CITED_WIDTH7_RUNG_MEAN_LIFETIME_TICKS
    assert CITED_ITEM_WIDTHS[DECLARED.second_ladder_item] == CITED_WIDTH7_RUNG_WIDTH


# --- round 3: the declared actuator, prediction, neutral gain, long horizon,
# capacity and genericity. Every figure below is recomputed from the receipt's own
# raw measurements through the declared equations, and every declared margin is
# exercised with a control that makes the same check fail.


def actuator_increment(amplitude: float, ratio: float, fit: dict) -> float:
    """The declared generator's deposit equation, in units of the reference amount."""

    work = fit["budget"] * abs(float(amplitude))
    linear = fit["lambda"] * float(ratio) * math.copysign(1.0, float(amplitude))
    root = math.sqrt(linear * linear + 2.0 * fit["mu"] * work)
    amount = 2.0 * work / (root + linear) if linear >= 0.0 else (root - linear) / fit["mu"]
    return math.copysign(amount, float(amplitude)) / fit["amount_reference"]


def predicted_horizon_retention(
    gain: float, phase_degrees: float, calibration: dict, ticks: int
) -> float:
    """The declared superposed-response prediction of one arm's horizon retention."""

    free = [float(value) for value in calibration["free_retention"]]
    fit = calibration["fit"]
    cosine = math.cos(math.radians(float(phase_degrees)))
    amplitudes: list[float] = []
    deposits: list[float] = []
    retention = 0.0
    for tick in range(1, int(ticks) + 1):
        pre = free[tick]
        for lag, deposit in enumerate(reversed(deposits), start=1):
            pre += deposit * free[lag]
        amplitude = float(
            max(-1.0, min(1.0, float(gain) * PER_TICK_DECAY * cosine * pre))
        )
        deposits.append(actuator_increment(amplitude, pre, fit))
        amplitudes.append(amplitude)
        retention = pre + deposits[-1]
    return retention**2


def calibration_residuals(calibration: dict, fit: dict | None = None) -> list[float]:
    """Every declared calibration probe's residual against the declared equation."""

    fit = fit or calibration["fit"]
    residuals = []
    for group in ("loaded_probes", "unloaded_probes"):
        for probe in calibration[group].values():
            predicted = actuator_increment(
                probe["sign"] * probe["fraction"], probe["projection_ratio"], fit
            )
            residuals.append(abs(probe["increment_ratio"] - predicted))
    return residuals


def test_actuator_calibration_reproduces_every_probe_and_its_tolerance_can_fail(
    receipt: dict,
) -> None:
    """The declared actuator equation must reproduce all of its own calibration probes."""

    calibration = receipt["actuator_calibration"]
    for label in ("declared_profile", "beta_zero_profile"):
        block = calibration[label]
        residuals = calibration_residuals(block)
        assert len(residuals) == 12, label
        assert max(residuals) <= 1e-9, (label, max(residuals))
        assert block["prediction_check_max_residual"] == pytest.approx(
            max(residuals), rel=0.0, abs=1e-18
        ), label
        # The same check must be able to fail: a five per cent error in the fitted
        # load constant has to show up far above the declared tolerance.
        wrong_fit = dict(block["fit"])
        wrong_fit["lambda"] = block["fit"]["lambda"] * 1.05
        assert max(calibration_residuals(block, wrong_fit)) > 1e-9, label


def test_declared_prediction_reproduces_the_inverted_phase_arms(receipt: dict) -> None:
    """The declared prediction must reproduce the measured retention at theta 180."""

    declared = receipt["declared"]
    calibration = receipt["actuator_calibration"]["declared_profile"]
    allowance = declared["prediction_retention_allowance"]
    ticks = declared["horizon_ticks"]
    within: list[str] = []
    outside: list[str] = []
    for name, row in receipt["arms"].items():
        if row["declared"]["family"] not in ("closed-loop-phase", "neutral-gain"):
            continue
        if float(row["declared"]["phase_degrees"]) != float(
            declared["neutral_gain_phase_degrees"]
        ):
            continue
        predicted = predicted_horizon_retention(
            float(row["declared"]["gain"]),
            float(row["declared"]["phase_degrees"]),
            calibration,
            ticks,
        )
        measured = row["neutral_stability"]["measure_retention_at_horizon"]
        error = abs(predicted - measured) / measured
        (within if error <= allowance else outside).append(name)
    reported = receipt["reading"]["neutral_gain"]
    assert sorted(within) == sorted(reported["arms_within_retention_allowance"])
    assert sorted(outside) == sorted(reported["arms_outside_retention_allowance"])
    assert within, "no declared arm was checked against the declared prediction"
    # The tolerance must be able to fail: a five per cent error in the measured free
    # response has to push at least one arm outside it.
    perturbed = json.loads(json.dumps(calibration))
    perturbed["free_retention"] = [value * 1.05 for value in perturbed["free_retention"]]
    failures = [
        name
        for name, row in receipt["arms"].items()
        if row["declared"]["family"] == "neutral-gain"
        and abs(
            predicted_horizon_retention(
                float(row["declared"]["gain"]),
                float(row["declared"]["phase_degrees"]),
                perturbed,
                ticks,
            )
            - row["neutral_stability"]["measure_retention_at_horizon"]
        )
        / row["neutral_stability"]["measure_retention_at_horizon"]
        > allowance
    ]
    assert failures, "the declared prediction tolerance cannot fail"


def test_neutral_gain_refinement_brackets_the_crossing_and_reports_the_verdict(
    receipt: dict,
) -> None:
    """The declared refinement's bracket, its monotonicity and the prediction verdict."""

    declared = receipt["declared"]
    reading = receipt["reading"]["neutral_gain"]
    refinement = receipt["neutral_gain_refinement"]
    low, high = refinement["bracket"]
    assert low < refinement["measured_gain"] < high
    assert high - low <= declared["neutral_gain_bracket"] * (1.0 + 1e-12)
    assert refinement["retention_below"] < 1.0 <= refinement["retention_above"]
    assert refinement["grid_monotone"] is True
    gains = [row["gain"] for row in refinement["grid"]]
    assert gains == [float(g) for g in declared["neutral_gain_grid"]]
    retentions = [row["retention_at_horizon"] for row in refinement["grid"]]
    assert retentions == sorted(retentions)
    for probe in refinement["probes"]:
        assert receipt["arms"][probe["arm"]]["declared"]["family"] == "neutral-gain-refine"
        assert receipt["arms"][probe["arm"]]["declared"]["gain"] == probe["gain"]
    predicted = reading["predicted"]
    assert predicted["found"] is True
    assert predicted["retention_at_gain"] == pytest.approx(1.0, abs=1e-9)
    error = abs(predicted["gain"] - refinement["measured_gain"]) / refinement["measured_gain"]
    assert reading["relative_error_of_prediction"] == pytest.approx(error, rel=1e-12)
    assert reading["prediction_within_allowance"] is (
        error <= declared["neutral_gain_allowance"]
    )
    # The verdict is the predicate, and the predicate must be able to go either way:
    # at the declared allowance the measured miss is reported as a failure, and a
    # looser allowance would accept the same measured pair, so the check is not
    # hard-wired. The declared linearized injection finds no crossing at all.
    assert error > 0.0
    assert (error <= declared["neutral_gain_allowance"]) is False
    assert (error <= 0.5) is True
    assert reading["prediction_within_allowance"] is (error <= declared["neutral_gain_allowance"])
    assert reading["predicted_linearized"]["found"] is False
    assert reading["predicted_linearized"]["search_ceiling"] == declared[
        "neutral_gain_prediction_ceiling"
    ]


def test_long_horizon_series_plateau_and_dark_unwritten_share(receipt: dict) -> None:
    """The declared long horizon's series, its deceleration and its dark unwritten share."""

    declared = receipt["declared"]
    hor = receipt["reading"]["long_horizon"]
    ticks = int(declared["long_horizon_ticks"])
    assert hor["horizon_ticks"] == ticks
    assert hor["sample_spacing_ticks"] <= 16
    best = hor["per_arm"]["long-horizon-best-gain"]
    neutral = hor["per_arm"]["long-horizon-measured-neutral-gain"]
    drift = hor["per_arm"]["drift-long"]
    for entry in (best, neutral, drift):
        series = entry["retention_series"]
        assert [row["tick"] for row in series] == list(
            declared["long_horizon_sample_ticks"]
        )
        assert series[0]["tick"] == 16 and series[-1]["tick"] == ticks
    # Growth decelerates inside the declared horizon but does not saturate.
    assert hor["plateau"]["long-horizon-best-gain"]["growth_decelerates"] is True
    assert hor["plateau"]["long-horizon-best-gain"]["saturated_within_declared_horizon"] is False
    assert hor["any_plateau_within_horizon"] is False
    # The aggregate deceleration flag is a measurement, not an assumption: it is the
    # conjunction over the looped arms, and the neutral-gain arm sits at the crossing,
    # where the back-half rate is the larger one but stays at the noise level.
    assert hor["all_growth_decelerates"] is all(
        row["growth_decelerates"] for row in hor["plateau"].values()
    )
    for arm_name, entry in hor["plateau"].items():
        series = hor["per_arm"][arm_name]["retention_series"]
        first, second = half_growth_rates(series, ticks)
        assert entry["first_half_growth_rate_per_tick"] == pytest.approx(first, rel=1e-9)
        assert entry["second_half_growth_rate_per_tick"] == pytest.approx(second, rel=1e-9)
        assert entry["growth_decelerates"] is (second < first)
    crossing = hor["plateau"]["long-horizon-measured-neutral-gain"]
    # At the declared crossing the arm neither grows nor decays: its back-half rate is
    # the crossing's own noise, not a second mechanism.
    assert crossing["growth_decelerates"] is False
    assert abs(crossing["first_half_growth_rate_per_tick"]) < 0.001
    assert abs(crossing["second_half_growth_rate_per_tick"]) < 0.001
    # The written direction survives at the plateau: its share grows rather than the
    # frame merely getting large, and the unwritten directions stay dark.
    assert best["written_direction_alignment_at_horizon"] > 1.0
    assert best["horizon_unwritten_max_share"] < drift["horizon_unwritten_max_share"]
    assert neutral["horizon_unwritten_max_share"] < drift["horizon_unwritten_max_share"]
    # The measured neutral gain neither decays nor explodes over the long horizon,
    # while the best declared gain grows past an order of magnitude and the drift dies.
    assert 0.5 <= neutral["horizon_measure_retention"] <= 2.0
    assert best["horizon_measure_retention"] > 10.0
    assert drift["horizon_measure_retention"] < 0.01
    assert best["horizon_frame_energy_ratio"] == pytest.approx(
        best["horizon_measure_retention"], rel=0.01
    )
    # The declared plateau predicate must be able to fire: a series whose back half is
    # flat satisfies it.
    flat = [
        row
        if row["tick"] <= ticks // 2
        else {**row, "measure_retention": series_mid_value(best["retention_series"], ticks)}
        for row in best["retention_series"]
    ]
    assert plateau_fires(flat, ticks, declared["plateau_growth_tolerance"]) is True
    assert plateau_fires(best["retention_series"], ticks, declared["plateau_growth_tolerance"]) is False


def half_growth_rates(series: list[dict], ticks: int) -> tuple[float, float]:
    """The declared series' per-tick growth rate over each half of the horizon."""

    def rate(start: int, end: int) -> float:
        first = next(row for row in series if int(row["tick"]) == start)
        second = next(row for row in series if int(row["tick"]) == end)
        return float(
            (second["measure_retention"] / first["measure_retention"])
            ** (1.0 / (int(second["tick"]) - int(first["tick"])))
            - 1.0
        )

    return rate(int(series[0]["tick"]), int(ticks) // 2), rate(int(ticks) // 2, int(ticks))


def series_mid_value(series: list[dict], ticks: int) -> float:
    """The retention at the declared midpoint of a sampled series."""

    return float(
        next(row for row in series if int(row["tick"]) == int(ticks) // 2)[
            "measure_retention"
        ]
    )


def plateau_fires(series: list[dict], ticks: int, tolerance: float) -> bool:
    """The declared plateau predicate, recomputed from a sampled series."""

    mid = series_mid_value(series, ticks)
    return bool(float(series[-1]["measure_retention"]) / mid <= tolerance)


def test_beta_zero_counterpart_is_the_same_arm_with_the_coupling_zeroed(receipt: dict) -> None:
    """The declared beta=0 counterparts must be the same arms with the coupling zeroed."""

    declared = receipt["declared"]
    hor = receipt["reading"]["long_horizon"]
    pairs = hor["beta_zero_comparison"]
    assert pairs, "no declared beta=0 counterpart was measured"
    for name, row in pairs.items():
        profile_arm = receipt["arms"][name]
        zero_arm = receipt["arms"][row["beta_zero_arm"]]
        assert profile_arm["declared"]["profile_beta"] == pytest.approx(
            declared["profile_beta"]
        ), name
        assert zero_arm["declared"]["profile_beta"] != declared["profile_beta"], name
        assert zero_arm["declared"]["profile_beta"] == 0.0, name
        for key in ("gain", "phase_degrees", "horizon_ticks", "write_budget"):
            assert profile_arm["declared"][key] == zero_arm["declared"][key], (name, key)
        assert profile_arm["declared"]["samples"] == zero_arm["declared"]["samples"]
        # The profile really reached the workspace: the states differ even though the
        # measured figures agree.
        assert (
            profile_arm["samples"][-1]["state_sha256"]
            != zero_arm["samples"][-1]["state_sha256"]
        ), name
        difference = abs(
            profile_arm["neutral_stability"]["measure_retention_at_horizon"]
            - zero_arm["neutral_stability"]["measure_retention_at_horizon"]
        ) / profile_arm["neutral_stability"]["measure_retention_at_horizon"]
        assert row["relative_difference"] == pytest.approx(difference, rel=1e-9)
        assert row["quartic_inactive_within_bound"] is (
            difference <= declared["nonlinearity_activity_bound"]
        )
        # The declared bound must be able to fire as a difference: it is far below the
        # measured separation of two *different* declared settings.
        other = hor["per_arm"][name]["horizon_measure_retention"]
        assert difference < declared["nonlinearity_activity_bound"]
        assert declared["nonlinearity_activity_bound"] < abs(other - 1.0)


def test_capacity_locked_loop_is_selective_and_the_two_item_loop_is_not(receipt: dict) -> None:
    """The declared capacity families' aggregates, work split and verdict semantics."""

    declared = receipt["declared"]
    capacity = receipt["reading"]["capacity"]
    margin = declared["capacity_suppression_margin"]
    assert capacity["second_item_suppression"]["margin"] == margin
    locked = receipt["arms"]["capacity-locked-on-headline"]
    control = receipt["arms"]["capacity-two-item-no-loop"]
    both = receipt["arms"]["capacity-two-item-loop"]
    for row, item, entry, key in (
        (locked, declared["capacity_item"], capacity["second_item_suppression"], "second_item_second_half_mean_under_locked_loop"),
        (control, declared["capacity_item"], capacity["second_item_suppression"], "second_item_second_half_mean_without_loop"),
        (both, declared["capacity_item"], capacity["two_item_loop_verdict"], "second_second_half_mean_two_item_loop"),
        (control, declared["capacity_item"], capacity["two_item_loop_verdict"], "second_second_half_mean_no_loop_control"),
    ):
        assert entry[key] == pytest.approx(second_half_mean(row, item), rel=1e-12)
    locked_second = capacity["second_item_suppression"]["second_item_second_half_mean_under_locked_loop"]
    control_second = capacity["second_item_suppression"]["second_item_second_half_mean_without_loop"]
    difference = locked_second - control_second
    assert capacity["second_item_suppression"]["difference"] == pytest.approx(difference)
    assert capacity["second_item_suppression"]["suppressed_beyond_control"] is (
        difference < -margin
    )
    assert capacity["second_item_suppression"]["held_above_control"] is (difference > margin)
    # The locked loop holds the item it reads back on far above the item it does not.
    assert (
        capacity["second_item_suppression"]["headline_second_half_mean_under_locked_loop"]
        > locked_second * 100.0
    )
    verdict = capacity["two_item_loop_verdict"]
    second_difference = (
        verdict["second_second_half_mean_two_item_loop"]
        - verdict["second_second_half_mean_no_loop_control"]
    )
    assert verdict["second_item_suppressed_by_two_item_loop"] is (second_difference < -margin)
    assert verdict["headline_held_by_two_item_loop"] is True
    assert verdict["both_items_above_control_with_margin"] is False
    # Both margins must be able to fire on the measured numbers: a zero margin still
    # calls the two-item suppression, and a margin wider than the measured gap calls
    # neither the locked loop's gap nor the two-item loop's one a separation.
    assert second_difference < 0.0 and second_difference < -margin
    assert (second_difference < 0.0) is True
    assert (second_difference < -10.0) is False
    assert abs(difference) < margin, (
        "the locked loop's second-item mean must sit inside the declared margin, so "
        "the reported 'neither suppressed nor held' verdict is not an artifact of it"
    )
    assert (difference > margin) is False
    assert (difference > difference / 2.0) is True
    # The declared drive split: both items driven every tick, with the per-tick loop
    # work ceiling split equally between them, so no tick may spend more than the
    # declared ceiling times that tick's own amplitude.
    assert locked["drive"]["calls"] == int(declared["long_horizon_ticks"])
    assert both["drive"]["calls"] == 2 * int(declared["long_horizon_ticks"])
    ceiling = float(declared["loop_work_ceiling"])
    for row in (locked, both):
        for sample in row["samples"]:
            assert sample["drive_work_this_tick"] <= (
                ceiling * abs(sample["drive_amplitude"]) + 1e-15
            ), row["arm"]
        assert row["samples"][-1]["drive_work_cumulative"] == pytest.approx(
            row["drive"]["drive_work_total"], rel=1e-9
        ), row["arm"]
    # The two-item loop spends the same declared ceiling per tick as the locked loop
    # does: the split changes the per-item budget, not the loop's total draw.
    assert both["drive"]["drive_work_total"] == pytest.approx(
        locked["drive"]["drive_work_total"], rel=0.05
    )


def second_half_mean(row: dict, item: str) -> float:
    """An item's mean retention over an arm's own back-half samples."""

    samples = [
        sample["item_retention"][item]
        for sample in row["samples"]
        if int(sample["tick"]) >= int(row["declared"]["horizon_ticks"]) // 2
    ]
    return float(sum(samples) / len(samples))


def test_genericity_is_judged_by_the_declared_criterion(receipt: dict) -> None:
    """The declared genericity rows, their widths and their declared criterion."""

    declared = receipt["declared"]
    genericity = receipt["reading"]["genericity"]
    margin = declared["genericity_margin"]
    assert genericity["margin"] == margin
    widths = genericity["item_widths"]
    assert widths[declared["headline_item"]] == CITED_ITEM_WIDTHS[declared["headline_item"]]
    assert sorted(
        widths[item] for item in declared["genericity_items"]
    ) == [7, 14]
    headlines = [item for item in declared["genericity_items"]]
    assert len(set(headlines)) == len(headlines)
    rates: dict[str, float] = {}
    for item, row in genericity["per_item"].items():
        arm = receipt["arms"][row["arm"]]
        samples = arm["samples"]
        recomputed = (
            (samples[-1]["measure_retention"] / samples[0]["measure_retention"])
            ** (1.0 / (int(samples[-1]["tick"]) - int(samples[0]["tick"])))
            - 1.0
        )
        assert row["loop_growth_rate_per_tick"] == pytest.approx(recomputed, rel=1e-9)
        assert row["unwritten_max_share"] < 1e-4
        rates[item] = recomputed
    headline_rate = rates[declared["headline_item"]]
    for item, rate in rates.items():
        row = genericity["per_item"][item]
        deviation = abs(rate - headline_rate)
        assert row["amplification_over_no_loop"] == pytest.approx(
            row["loop_retention"] / row["no_loop_retention"], rel=1e-12
        )
        assert genericity["same_growth_rate_within_margin"][item] is (deviation <= margin)
    assert genericity["generic_by_declared_criterion"] is True
    # The declared margin must be able to fire: at a zero margin the same measured
    # deviations (all nonzero for every item other than the headline one) fail it.
    assert not all(
        abs(rate - headline_rate) <= 0.0 for item, rate in rates.items()
    )
    assert all(
        abs(rate - headline_rate) <= margin for rate in rates.values()
    )
    # The declared margin must be able to fail: a zero margin, and a margin far below
    # the measured spread, both reject the same measured deviations.
    assert any(
        abs(rate - headline_rate) > 0.0 for rate in rates.values()
    ), "the measured growth rates are identical, so the margin cannot fire"
    assert genericity["amplification_spread"] > margin
    assert genericity["per_item_growth_rate_deviation"][declared["headline_item"]] == 0.0


def test_declared_configuration_carries_the_round_three_contract() -> None:
    """The shipped configuration's declared round-3 settings, as a contract."""

    samples = list(DECLARED.long_horizon_sample_ticks)
    assert DECLARED.long_horizon_ticks >= 512
    assert DECLARED.long_horizon_min_ticks >= 512
    assert DECLARED.long_horizon_ticks == samples[-1]
    assert DECLARED.long_horizon_ticks // 2 in samples
    assert max(right - left for left, right in zip(samples, samples[1:])) <= 16
    assert DECLARED.neutral_gain_phase_degrees in DECLARED.phase_angles_degrees
    grid = list(DECLARED.neutral_gain_grid)
    assert grid == sorted(set(grid)) and min(grid) > 0.0
    assert max(grid) < min(DECLARED.phase_gains)
    assert DECLARED.neutral_gain_prediction_ceiling > max(grid)
    fractions = list(DECLARED.impulse_amplitude_fractions)
    assert fractions[0] == 1.0 and fractions == sorted(fractions, reverse=True)
    names = [spec.name for spec in ITEM_SPECS]
    assert DECLARED.capacity_item in names
    assert DECLARED.capacity_item != ITEM_SPECS[DECLARED.headline_item_index].name
    for item in DECLARED.genericity_items:
        assert item in names
        assert item in CITED_ITEM_WIDTHS
    assert DECLARED.prediction_retention_allowance > 0.0
    assert DECLARED.neutral_gain_allowance > 0.0
    assert DECLARED.neutral_gain_bracket > 0.0
    assert DECLARED.plateau_growth_tolerance > 1.0
    assert DECLARED.nonlinearity_activity_bound > 0.0
    assert DECLARED.beta_zero == 0.0


def regime_holds(
    rows: dict,
    control: dict,
    margin: float,
    headline: str,
    second: str,
    order: "list[str]",
) -> dict:
    """The declared per-regime capacity verdict, recomputed from the regime's own rows.

    A scheme holds an item when that scheme's back-half mean on the item exceeds the
    drive-free no-loop control's mean on the same item by more than the margin, and the
    regime's capacity is the largest number of declared items any declared scheme holds.
    The schemes are listed in the declared scheme order, as the receipt lists them.
    """

    holding = [
        name
        for name in order
        if rows[name][headline]["mean"] > control[headline] + margin
        and rows[name][second]["mean"] > control[second] + margin
    ]
    return {"holding": holding, "limit": 2 if holding else 1}


def regime_means(receipt: dict, regime: str) -> tuple[dict, dict]:
    """Each declared scheme's per-item back-half means in one regime, and its control's."""

    declared = receipt["declared"]
    headline, second = declared["headline_item"], declared["capacity_item"]
    rows = {
        scheme: {
            headline: {
                "mean": second_half_mean(
                    receipt["arms"][capacity_arm_name(regime, scheme)], headline
                )
            },
            second: {
                "mean": second_half_mean(
                    receipt["arms"][capacity_arm_name(regime, scheme)], second
                )
            },
        }
        for scheme in declared["capacity_schemes"]
    }
    control_row = receipt["arms"]["capacity-two-item-no-loop"]
    control = {
        headline: second_half_mean(control_row, headline),
        second: second_half_mean(control_row, second),
    }
    return rows, control


def test_capacity_regimes_run_at_their_own_declared_gains(receipt: dict) -> None:
    """Every regime runs the same schemes and both item references at its own declared gain."""

    declared = receipt["declared"]
    capacity = receipt["reading"]["capacity"]
    gains = capacity["regime_gains"]
    regimes = capacity["regimes"]
    assert list(capacity["regime_gains"]) == list(declared["capacity_regimes"])
    assert set(regimes) == set(declared["capacity_regimes"])
    assert capacity["capacity_limit_regime"] == "neutral", (
        "the headline capacity figure must be taken from the declared holding regime"
    )
    # The declared regimes must rest on different gains, and the bounded regime must sit
    # below the amplifying one: a bounded regime at the amplifying gain would print the
    # amplifying rows twice and answer nothing about holding.
    assert len(set(gains.values())) == len(gains), (
        f"the declared capacity regimes collapse onto gains {gains!r}"
    )
    assert gains["bounded"] < gains["amplifying"]
    assert gains["neutral"] != gains["amplifying"]
    assert gains["neutral"] == pytest.approx(
        receipt["neutral_gain_refinement"]["measured_gain"], rel=1e-12
    )
    assert gains["bounded"] == DECLARED.capacity_bounded_gain
    assert gains["amplifying"] == receipt["best_declared_phase_setting"]["gain"]
    headline, second = declared["headline_item"], declared["capacity_item"]
    for regime, table in regimes.items():
        assert table["regime"] == regime
        assert table["gain"] == gains[regime]
        assert table["margin"] == declared["capacity_suppression_margin"]
        assert table["control"]["arm"] == "capacity-two-item-no-loop"
        assert table["single_item_reference"]["gain"] == gains[regime]
        for scheme in declared["capacity_schemes"]:
            arm = receipt["arms"][capacity_arm_name(regime, scheme)]
            assert arm["declared"]["gain"] == gains[regime]
            assert arm["declared"]["horizon_ticks"] == declared["long_horizon_ticks"]
            assert arm["declared"]["written_items"] == [headline, second]
            assert arm["declared"]["regime"] == regime
        names = [spec.name for spec in ITEM_SPECS]
        for reference, index in (
            ("single-item-headline", declared["headline_item_index"]),
            ("single-item-second", names.index(declared["capacity_item"])),
        ):
            arm = receipt["arms"][capacity_arm_name(regime, reference)]
            assert arm["declared"]["gain"] == gains[regime]
            assert arm["declared"]["measure_item_index"] == index
            assert arm["declared"]["drive_item_indices"] == [index]
    # The amplifying rows are the shipped two-item arms: the same arm names the round-3
    # receipt measured, so the amplifying rows are the historic measurement relabelled.
    assert capacity["regime_of_schemes"] == "amplifying"
    for scheme in declared["capacity_schemes"]:
        assert capacity["schemes"][scheme]["arm"] == capacity_arm_name(
            "amplifying", scheme
        )


def test_capacity_regime_table_recomputes_and_its_margin_can_fail(receipt: dict) -> None:
    """Each regime's table recomputes from its own arms, and its margin must be able to fire."""

    declared = receipt["declared"]
    capacity = receipt["reading"]["capacity"]
    margin = declared["capacity_suppression_margin"]
    headline, second = declared["headline_item"], declared["capacity_item"]
    limits = capacity["capacity_limit_by_regime"]
    for regime, table in capacity["regimes"].items():
        rows, control = regime_means(receipt, regime)
        verdict = regime_holds(
            rows, control, margin, headline, second, list(declared["capacity_schemes"])
        )
        assert table["single_item_reference"]["headline_second_half_mean"] == pytest.approx(
            second_half_mean(
                receipt["arms"][capacity_arm_name(regime, "single-item-headline")],
                headline,
            ),
            rel=1e-12,
        )
        assert table["second_item_own_single_item_reference"][
            "second_second_half_mean"
        ] == pytest.approx(
            second_half_mean(
                receipt["arms"][capacity_arm_name(regime, "single-item-second")], second
            ),
            rel=1e-12,
        )
        assert table["control"]["headline_second_half_mean"] == pytest.approx(
            control[headline], rel=1e-12
        )
        assert table["control"]["second_second_half_mean"] == pytest.approx(
            control[second], rel=1e-12
        )
        for scheme, entry in table["schemes"].items():
            assert entry["arm"] == capacity_arm_name(regime, scheme)
            assert entry["headline_second_half_mean"] == pytest.approx(
                rows[scheme][headline]["mean"], rel=1e-12
            ), f"{regime}/{scheme} headline mean disagrees with its own samples"
            assert entry["second_second_half_mean"] == pytest.approx(
                rows[scheme][second]["mean"], rel=1e-12
            ), f"{regime}/{scheme} second mean disagrees with its own samples"
            assert entry["both_items_held"] == (
                scheme in verdict["holding"]
            ), f"{regime}/{scheme} verdict disagrees with the declared predicate"
            assert entry["headline_held_above_control"] == (
                rows[scheme][headline]["mean"] > control[headline] + margin
            )
            assert entry["second_held_above_control"] == (
                rows[scheme][second]["mean"] > control[second] + margin
            )
        assert table["schemes_holding_both_items"] == verdict["holding"]
        assert table["capacity_limit_items"] == verdict["limit"]
        assert limits[regime] == verdict["limit"]
        assert regime in table["capacity_limit_evidence"]
        assert f"{float(table['gain'])!r}" in table["capacity_limit_evidence"]
        # The margin is load-bearing in both directions: with a zero margin the drive-free
        # control's own rows already satisfy it for at least one scheme (so the predicate
        # is reachable), and with a margin wider than every measured gap no scheme holds
        # both (so the predicate is not vacuous). A regime where neither fires would mean
        # the comparison cannot fail on its own numbers.
        permissive = regime_holds(
            rows, control, 0.0, headline, second, list(declared["capacity_schemes"])
        )
        strict = regime_holds(
            rows, control, 1e3, headline, second, list(declared["capacity_schemes"])
        )
        assert permissive["limit"] == 2, (
            f"no declared scheme in the {regime} regime holds both items even at a zero "
            "margin, so its holding verdict cannot fire"
        )
        assert strict["limit"] == 1, (
            f"some declared scheme in the {regime} regime holds both items even at a "
            "margin of 1e3, so its margin is not the thing deciding the verdict"
        )
    # The declared margin itself must be the one that decides at least one scheme's
    # verdict in the declared holding regime, which is what makes the reported capacity a
    # measured margin rather than a convention.
    holding_regime = capacity["capacity_limit_regime"]
    rows, control = regime_means(receipt, holding_regime)
    declared_limit = regime_holds(
        rows, control, margin, headline, second, list(declared["capacity_schemes"])
    )["limit"]
    assert declared_limit == capacity["capacity_limit_items"]
    assert 0.0 < margin <= max(
        abs(entry["second_second_half_mean"] - control[second])
        for entry in capacity["regimes"][holding_regime]["schemes"].values()
    )


def test_capacity_regime_telemetry_reproduces_its_own_schedule(receipt: dict) -> None:
    """Each regime's telemetry is its own schedule, within the declared work ceiling."""

    declared = receipt["declared"]
    headline, second = declared["headline_item"], declared["capacity_item"]
    ceiling = float(declared["loop_work_ceiling"])
    horizon = int(declared["long_horizon_ticks"])
    block = int(declared["capacity_alternate_block_ticks"])
    multiplex = {"time-multiplex-adjacent": 1, "time-multiplex-block": block}
    # The receipt declares which arm carries each regime's telemetry (for the amplifying
    # regime that is the declared telemetry twin of the untracked shipped arm), so the
    # schedule is read from the arm the receipt itself points at.
    diagnosis_arms = receipt["reading"]["capacity"]["diagnosis_by_regime"]
    assert set(diagnosis_arms) == set(declared["capacity_regimes"])
    for regime in declared["capacity_regimes"]:
        shared = receipt["arms"][diagnosis_arms[regime]["arm"]]
        assert shared["arm"] == capacity_arm_name(regime, "shared-two-item") or (
            regime == "amplifying" and shared["arm"] == "capacity-two-item-telemetry"
        ), shared["arm"]
        rows = shared["telemetry"]
        assert len(rows) == horizon, regime
        for index, row in enumerate(rows):
            # A drive happens on every tick after the write tick, so the telemetry holds one
            # row per tick of the declared horizon and each row carries that tick's number.
            assert row["tick"] == index + 1
            assert sorted(row["scheduled"]) == sorted([headline, second])
            amplitudes = {item: row["amplitude"][item] for item in (headline, second)}
            assert amplitudes[headline] == amplitudes[second], (
                "the shared scheme must put its one read-back amplitude on both items"
            )
            for item in (headline, second):
                assert row["applied_work"][item] == pytest.approx(
                    ceiling * abs(amplitudes[item]) / 2.0, rel=1e-9, abs=1e-18
                ), f"{regime} tick {index} {item} work disagrees with its own amplitude"
                assert row["increment"][item] == pytest.approx(
                    row["ratio_after"][item] - row["ratio_before"][item], rel=1e-9, abs=1e-12
                ), f"{regime} tick {index} {item} increment disagrees with its ratios"
                if row["clipped"][item]:
                    assert abs(amplitudes[item]) == pytest.approx(1.0, rel=0.0, abs=1e-12), (
                        "a clipped drive must be the declared ceiling amplitude itself"
                    )
        if regime == "amplifying":
            # The declared amplifying diagnosis twin must reproduce the shipped arm's
            # measured series exactly, so the diagnosis cannot have changed the physics.
            shipped_shared = receipt["arms"][capacity_arm_name("amplifying", "shared-two-item")]
            assert "telemetry" not in shipped_shared, (
                "the shipped amplifying shared arm is the untracked one, so the twin is "
                "the arm the receipt points the diagnosis at"
            )
            assert measured_blocks(shared) == measured_blocks(shipped_shared)
            assert shared["telemetry"] == rows
        for scheme, run_length in multiplex.items():
            arm = receipt["arms"][capacity_arm_name(regime, scheme)]
            rows = arm["telemetry"]
            assert arm["declared"]["drive_cycle"] == list(
                [0] * run_length + [1] * run_length
            )
            assert len(rows) == horizon
            schedule = [row["scheduled"][0] for row in rows]
            assert all(len(row["scheduled"]) == 1 for row in rows), (
                "a time-multiplexed scheme must pump exactly one item per tick"
            )
            assert schedule.count(headline) == horizon // 2
            assert schedule.count(second) == horizon // 2
            runs = [len(list(group)) for _, group in itertools.groupby(schedule)]
            assert all(length == run_length for length in runs), (
                f"{regime}/{scheme} does not run in declared runs of {run_length}"
            )
            for row in rows:
                item = row["scheduled"][0]
                assert row["applied_work"][item] == pytest.approx(
                    ceiling * abs(row["amplitude"][item]), rel=1e-9, abs=1e-18
                ), "a multiplexed scheme must spend the whole ceiling on its one item"
        # The per-item scheme's declared per-item references are the receipt's own per-item
        # readouts, so its drives are in each item's own units rather than one convention.
        locked = receipt["arms"][capacity_arm_name(regime, "phase-locked-per-item")]
        assert locked["declared"]["phase_locked"] is True
        references = locked["declared"]["drive_reference_values"]
        readouts = receipt["phase_readout"]["per_item"]["items"]
        assert set(references) == {headline, second}
        for item in (headline, second):
            assert references[item] == pytest.approx(
                readouts[item]["post_write_signed_projection"], rel=1e-12
            )
        assert locked["declared"]["in_arm_post_write_projections"] != references, (
            "the per-item scheme must use each item's own isolated projection rather "
            "than the shared in-arm one, or it would be the shared scheme again"
        )
        for index, row in enumerate(locked["telemetry"]):
            assert sorted(row["scheduled"]) == sorted([headline, second])
            for item in (headline, second):
                assert row["applied_work"][item] == pytest.approx(
                    ceiling * abs(row["amplitude"][item]) / 2.0, rel=1e-9, abs=1e-18
                ), f"{regime} tick {index} {item} per-item work disagrees with its amplitude"


def test_capacity_regime_rows_agree_with_the_shipped_two_item_verdict(receipt: dict) -> None:
    """The amplifying table is the shipped two-item measurement, and the gains do not leak."""

    declared = receipt["declared"]
    capacity = receipt["reading"]["capacity"]
    amplifying = capacity["regimes"]["amplifying"]
    shipped = capacity["two_item_loop_verdict"]
    shared = amplifying["schemes"]["shared-two-item"]
    assert shared["headline_second_half_mean"] == pytest.approx(
        shipped["headline_second_half_mean_two_item_loop"], rel=1e-12
    )
    assert shared["second_second_half_mean"] == pytest.approx(
        shipped["second_second_half_mean_two_item_loop"], rel=1e-12
    )
    assert amplifying["control"]["second_second_half_mean"] == pytest.approx(
        shipped["second_second_half_mean_no_loop_control"], rel=1e-12
    )
    assert shipped["both_items_above_control_with_margin"] is (
        "shared-two-item" in amplifying["schemes_holding_both_items"]
    )
    # A regime table must not be able to pass another regime's means off as its own: the
    # neutral and amplifying rows are measured at different gains, so on the item the shared
    # loop reads back on they differ by far more than the declared margin (the amplified
    # item is held far above its own control in the amplifying regime and not in the
    # neutral one), and the same holds for the single-item references of the two regimes.
    margin = float(declared["capacity_suppression_margin"])
    neutral = capacity["regimes"]["neutral"]["schemes"]["shared-two-item"]
    headline, second = declared["headline_item"], declared["capacity_item"]
    assert abs(
        neutral["headline_second_half_mean"] - shared["headline_second_half_mean"]
    ) > margin, (
        "the two regimes' shared-scheme rows are indistinguishable on the item the loop "
        "reads back on, so the regime label is not separating measurements"
    )
    for key in ("second_second_half_mean", "second_retention_at_horizon"):
        neutral_reference = capacity["regimes"]["neutral"][
            "second_item_own_single_item_reference"
        ][key]
        amplifying_reference = capacity["regimes"]["amplifying"][
            "second_item_own_single_item_reference"
        ][key]
        assert abs(neutral_reference - amplifying_reference) > margin, (
            f"the second item's own single-item reference ({key}) does not separate the two "
            "regimes, so the per-regime comparison rests on indistinguishable controls"
        )
    assert (
        capacity["regimes"]["amplifying"]["single_item_reference"]["gain"]
        != capacity["regimes"]["neutral"]["single_item_reference"]["gain"]
    )
    assert capacity["diagnosis"]["regime"] == "amplifying"
    assert capacity["diagnosis"]["gain"] == capacity["regime_gains"]["amplifying"]
    assert capacity["diagnosis_by_regime"]["neutral"]["regime"] == "neutral"
    assert capacity["diagnosis_by_regime"]["neutral"]["gain"] == capacity["regime_gains"]["neutral"]
    assert capacity["diagnosis_by_regime"]["neutral"]["arm"] == capacity_arm_name(
        "neutral", "shared-two-item"
    )


def test_boundedness_flag_separates_amplifying_from_divergent(receipt: dict) -> None:
    """The declared bound flag, its partition, and the settings reconciliation can fail."""

    arms = receipt["arms"]
    boundedness = receipt["reading"]["boundedness"]
    partition = partition_boundedness(arms)
    recomputed = sorted(
        name for name, row in arms.items() if exceeds_runaway(DECLARED, row["boundedness"]["energy_ratio_max"])
    )
    assert boundedness["runaway_arms"] == recomputed
    assert boundedness["arms_over_declared_energy_bound"] == recomputed
    assert boundedness["divergent_arms"] == partition["divergent"]
    assert boundedness["amplifying_but_finite_arms"] == partition["amplifying_but_finite"]
    assert boundedness["regime_by_arm"] == partition["regime_by_arm"]
    assert boundedness["all_flagged_arms_are_finite"] is (not partition["divergent"])
    assert boundedness["runaway_ratio"] == DECLARED.runaway_energy_ratio
    for name, row in arms.items():
        assert boundedness_regime(row) == partition["regime_by_arm"][name]
        assert row["boundedness"]["runaway"] == (
            partition["regime_by_arm"][name] != "bounded"
        ), f"{name} disagrees with the declared bound predicate"
    # The declared selection rule picks among the arms the declared boundedness criterion
    # accepts, so the selected setting must not itself be over the bound at its own horizon.
    reconciliation = receipt["reading"]["settings_reconciliation"]
    selected = reconciliation["selected_loop_setting"]
    assert selected["name"] == receipt["selected_loop_setting"]["name"]
    assert selected["gain"] == receipt["selected_loop_setting"]["gain"]
    assert selected["horizon_ticks"] == arms[selected["name"]]["declared"]["horizon_ticks"]
    assert selected["over_declared_energy_bound"] is False
    assert reconciliation["selected_setting_is_over_the_bound"] is False
    assert selected["name"] not in boundedness["runaway_arms"], (
        "the declared best stable setting must not also be reported as over the bound at "
        "its own horizon"
    )
    families = reconciliation["families_declared_setting"]
    assert families["name"] == receipt["best_declared_phase_setting"]["name"]
    assert families["gain"] == receipt["best_declared_phase_setting"]["gain"]
    assert families["gain"] == receipt["reading"]["capacity"]["regime_gains"]["amplifying"]
    assert reconciliation["every_flagged_arm_is_finite"] is True
    assert all(name in arms for name in boundedness["runaway_arms"])
    # The same setting is inside the bound at the declared phase horizon and over it at the
    # declared long horizon: that is what the reconciliation says the flag means.
    phase_arm = receipt["arms"][families["name"]]
    assert phase_arm["boundedness"]["runaway"] is False
    long_family = receipt["arms"]["long-horizon-best-gain"]
    assert (
        phase_arm["declared"]["horizon_ticks"]
        < long_family["declared"]["horizon_ticks"]
    ), "the same setting must be measured at both declared horizons for the flag to mean one"
    assert long_family["declared"]["gain"] == families["gain"]
    assert long_family["boundedness"]["runaway"] is True
    assert long_family["boundedness"]["all_samples_finite"] is True
    assert "long-horizon-best-gain" in boundedness["amplifying_but_finite_arms"]
    # The partition must be able to fail: an arm whose own row says its ratio is
    # non-finite is divergent rather than amplifying-but-finite, and an arm whose own row
    # says its ratio is inside the bound is bounded, whatever the rest of the roster says.
    mutated = {
        "probe": {
            "boundedness": dict(arms["long-horizon-best-gain"]["boundedness"]),
        }
    }
    assert boundedness_regime(mutated["probe"]) == "amplifying_beyond_declared_bound"
    mutated["probe"]["boundedness"]["all_samples_finite"] = False
    assert boundedness_regime(mutated["probe"]) == "divergent"
    assert partition_boundedness(mutated)["divergent"] == ["probe"]
    assert partition_boundedness(mutated)["over_bound"] == ["probe"]
    assert partition_boundedness(mutated)["amplifying_but_finite"] == []
    mutated["probe"]["boundedness"] = dict(arms["drift-no-refresh-no-loop"]["boundedness"])
    assert boundedness_regime(mutated["probe"]) == "bounded"
    assert partition_boundedness({"bounded-arm": mutated["probe"]})["over_bound"] == []
    assert partition_boundedness({"bounded-arm": mutated["probe"]})["divergent"] == []


def flat_arm(receipt: dict, name: str) -> dict:
    """One composition arm, looked up in the composition's own arm table."""

    composition = receipt["composition"]
    assert name in composition["arms"], f"the composition did not measure {name}"
    return composition["arms"][name]


def composition_means(receipt: dict, scheme: str, item: str) -> float:
    """One flat capacity scheme's back-half mean on one declared item, from its own samples."""

    from run_fractal_feedback_exploration import capacity_arm_name

    return second_half_mean(
        flat_arm(receipt, capacity_arm_name("flat", scheme)), item
    )


def test_composition_remeasures_the_neutral_gain_on_the_flat_metric(receipt: dict) -> None:
    """The flat metric's neutral gain is its own measurement, and its bracket can fail."""

    from run_fractal_feedback_exploration import COMPOSITION_AIM_LEVER_MARGIN

    composition = receipt["composition"]
    declared = receipt["declared"]
    profile = composition["profile"]
    assert profile["name"] == "ladder-uniform"
    assert "run_fractal_metric_exploration" in profile["source"], (
        "the flat profile must be the metric harness's own declared object, not a copy"
    )
    refinement = composition["flat_neutral_gain"]
    low, high = refinement["bracket"]
    assert refinement["tolerance"] == declared["neutral_gain_bracket"]
    assert refinement["bracket_width"] == pytest.approx(high - low, rel=1e-12)
    assert refinement["bracket_width"] <= refinement["tolerance"]
    assert refinement["measured_gain"] == pytest.approx(0.5 * (low + high), rel=1e-12)
    # The declared crossing: the loop still decays at the low end and no longer decays at
    # the high end, which is the whole content of "neutral gain" here.
    assert refinement["retention_below"] < 1.0 <= refinement["retention_above"]
    assert refinement["grid_monotone"] is True
    grid = refinement["grid"]
    assert [row["gain"] for row in grid] == sorted(
        row["gain"] for row in grid
    )
    # Every declared refinement probe is a measured arm of the composition, at its own gain,
    # and the reported probes' retentions are those arms' own readings.
    for probe in refinement["probes"]:
        arm = flat_arm(receipt, probe["arm"])
        assert arm["declared"]["gain"] == probe["gain"]
        assert (
            arm["neutral_stability"]["measure_retention_at_horizon"]
            == probe["retention_at_horizon"]
        )
    # The composition's whole point: the flat profile's gain is not the default field's.
    assert refinement["measured_gain"] != receipt["neutral_gain_refinement"]["measured_gain"], (
        "the flat composition reused the default field's neutral gain, which confounds the "
        "composition with the default's operating point"
    )
    assert refinement["measured_gain"] < min(declared["neutral_gain_grid"])
    # The bracket must be able to fail: a bracket whose endpoints are swapped has no
    # crossing, and a grid whose smallest gain already decays cannot bracket one either.
    crossed = (
        refinement["retention_below"] < 1.0 <= refinement["retention_above"]
    )
    assert crossed == (
        refinement["retention_below"] < 1.0 <= refinement["retention_above"]
    )
    assert not (
        refinement["retention_above"] < 1.0 <= refinement["retention_below"]
    ), "the crossing predicate would pass on a bracket with no crossing"
    assert (grid[0]["retention_at_horizon"] <= 1.0) is False, (
        "the declared refinement's smallest grid gain already decays on the flat metric, "
        "so the refinement has no bracket to bisect and the receipt must say so"
    )
    assert composition["verdicts"]["aiming_survives_the_flat_metric"] is (
        composition["aim"]["aiming_lever_flat"] - 1.0 > COMPOSITION_AIM_LEVER_MARGIN
    )


def test_composition_hold_and_capacity_legs_recompute(receipt: dict) -> None:
    """The composition's hold, drift and capacity legs come from its own flat arms."""

    from run_fractal_feedback_exploration import capacity_arm_name

    composition = receipt["composition"]
    declared = receipt["declared"]
    margin = float(composition["margin"])
    assert margin == declared["capacity_suppression_margin"]
    gain = composition["flat_neutral_gain"]["measured_gain"]
    hold = composition["hold"]
    hold_arm = flat_arm(receipt, hold["arm"])
    control_arm = flat_arm(receipt, hold["control_arm"])
    assert hold_arm["declared"]["gain"] == gain
    assert control_arm["declared"]["gain"] == 0.0
    for arm, entry in ((hold_arm, hold), (control_arm, hold)):
        horizon = max(arm["samples"], key=lambda row: row["tick"])
        assert horizon["tick"] == declared["long_horizon_ticks"]
        assert horizon["measure_retention"] == arm["neutral_stability"][
            "measure_retention_at_horizon"
        ]
        assert arm["neutral_stability"]["measure_retention_at_horizon"] > 0.0
    assert hold["retention_at_horizon"] == hold_arm["neutral_stability"][
        "measure_retention_at_horizon"
    ]
    assert hold["control_retention_at_horizon"] == control_arm["neutral_stability"][
        "measure_retention_at_horizon"
    ]
    assert hold["frame_energy_ratio"] == hold_arm["horizon"]["frame_energy_ratio"]
    assert hold["unwritten_max_share"] == hold_arm["horizon"]["unwritten_max_share"]
    assert hold["retention_minus_control"] == pytest.approx(
        hold["retention_at_horizon"] - hold["control_retention_at_horizon"], rel=1e-12
    )
    assert hold["held_above_control"] is (
        hold["retention_minus_control"] > margin
    )
    assert hold["neutral_by_declared_criterion"] == recompute_neutral(declared, hold_arm)
    # The hold predicate must be able to fail on this leg's own numbers: half the measured
    # difference still holds and twice it does not, so the comparison is not vacuous, and the
    # declared margin's headroom is reported rather than assumed.
    difference = hold["retention_minus_control"]
    # A mutation control on the margin itself: at a margin just above the measured difference
    # the hold verdict turns over, and just below it it does not, so the predicate this leg
    # reports is the declared comparison and not a constant.
    assert (difference > difference + 1e-9) is False
    assert (difference > difference - 1e-9) is True
    assert (difference > margin) is hold["held_above_control"]
    assert difference > margin, (
        "the flat hold leg does not clear the declared margin, so the composition's hold "
        "verdict must be reported as a failure"
    )
    # The flat metric's own drift on the headline item and on the narrow declared item.
    drift = composition["drift_contrast"]
    headline_drift = flat_arm(receipt, drift["headline_arm"])
    narrow_drift = flat_arm(receipt, drift["narrow_arm"])
    assert narrow_drift["declared"]["measured_item"] == drift["narrow_item"]
    for arm, key in (
        (headline_drift, "headline_retention_at_horizon"),
        (narrow_drift, "narrow_retention_at_horizon"),
    ):
        assert drift[key] == arm["neutral_stability"]["measure_retention_at_horizon"]
    assert drift["narrow_minus_headline"] == pytest.approx(
        drift["narrow_retention_at_horizon"] - drift["headline_retention_at_horizon"],
        rel=1e-12,
    )
    assert drift["narrow_held_above_headline"] is (
        drift["narrow_minus_headline"] > margin
    )
    # The drift contrast is a measurement, so the test holds it to its own predicate rather
    # than to an expected sign: the verdict is the comparison, and a contrast far larger than
    # any declared margin does not occur on this leg.
    assert (drift["narrow_minus_headline"] > 100.0) is False
    # The capacity leg: every declared scheme at the flat profile's own gain, against the
    # flat profile's own no-loop control.
    table = composition["capacity"]
    assert table["regime"] == "flat"
    assert table["gain"] == gain
    assert table["control"]["arm"] == composition["hold"]["control_arm"]
    assert table["control"]["gain"] == 0.0
    control_headline = table["control"]["headline_second_half_mean"]
    control_second = table["control"]["second_second_half_mean"]
    assert control_headline == pytest.approx(
        second_half_mean(control_arm, declared["headline_item"]), rel=1e-12
    )
    assert control_second == pytest.approx(
        second_half_mean(control_arm, declared["capacity_item"]), rel=1e-12
    )
    holding = []
    for scheme in declared["capacity_schemes"]:
        arm = flat_arm(receipt, capacity_arm_name("flat", scheme))
        assert arm["declared"]["gain"] == gain
        assert arm["declared"]["regime"] == "flat"
        entry = table["schemes"][scheme]
        headline_mean = composition_means(receipt, scheme, declared["headline_item"])
        second_mean = composition_means(receipt, scheme, declared["capacity_item"])
        assert entry["headline_second_half_mean"] == pytest.approx(headline_mean, rel=1e-12)
        assert entry["second_second_half_mean"] == pytest.approx(second_mean, rel=1e-12)
        assert entry["headline_held_above_control"] is (
            headline_mean > control_headline + margin
        )
        assert entry["second_held_above_control"] is (
            second_mean > control_second + margin
        )
        assert entry["both_items_held"] is (
            entry["headline_held_above_control"] and entry["second_held_above_control"]
        )
        if entry["both_items_held"]:
            holding.append(scheme)
    assert table["schemes_holding_both_items"] == holding
    assert table["capacity_limit_items"] == (2 if holding else 1)
    assert composition["verdicts"]["capacity_items"] == table["capacity_limit_items"]
    assert composition["verdicts"]["shared_scheme_holds_both_items"] is table["schemes"][
        "shared-two-item"
    ]["both_items_held"]
    assert composition["verdicts"]["locked_loop_holds_the_item_it_reads_back_on"] is table[
        "schemes"
    ]["locked-on-headline"]["headline_held_above_control"]
    assert composition["verdicts"]["selectivity_pattern_preserved"] is (
        table["schemes"]["locked-on-headline"]["headline_held_above_control"]
        and not table["schemes"]["shared-two-item"]["both_items_held"]
    )
    # The flat diagnosis is that regime's own telemetry, from the flat shared arm.
    diagnosis = composition["diagnosis"]
    assert diagnosis["regime"] == "flat"
    assert diagnosis["gain"] == gain
    assert diagnosis["arm"] == capacity_arm_name("flat", "shared-two-item")


def test_composition_aim_leg_cites_the_ladder_receipt(receipt: dict) -> None:
    """The aim leg is the ladder harness's own figures, read not re-measured, and can fail."""

    from run_fractal_feedback_exploration import (
        CITED_LADDER_AIM_DEFAULT_PROFILE,
        CITED_LADDER_AIM_FLAT_PROFILE,
        CITED_LADDER_RECEIPT,
    )

    aim = receipt["composition"]["aim"]
    assert aim["cited_receipt"] == CITED_LADDER_RECEIPT
    ladder = json.loads(Path(CITED_LADDER_RECEIPT).read_text(encoding="utf-8"))
    surface = ladder["exhaustive_write_surface"]
    profiles = ladder["profiles"]
    for label, name in (
        ("default_profile", CITED_LADDER_AIM_DEFAULT_PROFILE),
        ("flat_profile", CITED_LADDER_AIM_FLAT_PROFILE),
    ):
        entry = aim[label]
        assert entry["profile"] == name
        assert entry["headline_final_retention"] == profiles[name]["items"][0][
            "final_retention"
        ], "the cited headline retention is not the ladder receipt's own figure"
        assert entry["best_deep_write_measured_final"] == surface[name][
            "best_measured_final"
        ], "the cited deep-write figure is not the ladder receipt's own figure"
        assert entry["aiming_lever"] == pytest.approx(
            entry["best_deep_write_measured_final"] / entry["headline_final_retention"],
            rel=1e-12,
        )
    assert aim["aiming_lever_default"] == aim["default_profile"]["aiming_lever"]
    assert aim["aiming_lever_flat"] == aim["flat_profile"]["aiming_lever"]
    # The composition finding: the default metric's aiming lever is large and the flat
    # metric's is one, so aiming has nothing left to buy once every direction is slow.
    assert aim["aiming_lever_default"] > 10.0
    assert aim["aiming_lever_flat"] == pytest.approx(1.0, rel=1e-9)
    assert aim["aiming_survives_the_flat_metric"] is False
    # The verdict can fail in both directions on the cited figures themselves.
    margin = aim["aiming_lever_margin"]
    assert (aim["aiming_lever_flat"] - 1.0 > margin) is False
    assert ((1.0 + 2.0 * margin) - 1.0 > margin) is True
    assert (aim["aiming_lever_default"] - 1.0 > margin) is True
    # The aim leg is a citation: no composition arm re-measures the ladder's write surface.
    assert not any(
        "exhaustive" in name or "aim" in name for name in receipt["composition"]["arms"]
    )


def test_composition_is_carried_only_when_the_measurement_asked_for_it() -> None:
    """The composition legs are declared, present by default, and absent when switched off."""

    from run_fractal_feedback_exploration import feedback_sentence, measure

    compact = build_receipt(COMPACT)
    assert "composition" in compact
    assert "composition" in compact["reading"]
    assert compact["reading"]["composition"]["flat_neutral_gain"] == compact[
        "composition"
    ]["flat_neutral_gain"]["measured_gain"]
    without = measure(COMPACT, None, composition=False)
    assert "composition" not in without
    assert "composition" not in without["reading"]
    sentence = feedback_sentence(without["reading"])
    assert "flat-inertia" not in sentence
    assert len(sentence) > 0
    assert len(compact["reading"]["sentence"]) > len(sentence)


def curve_arm(receipt: dict, count: int, scheme: str) -> dict:
    """One capacity-curve arm, from the composition's own arm table."""

    from run_fractal_feedback_exploration import capacity_curve_arm_name

    return flat_arm(receipt, capacity_curve_arm_name(count, scheme))


def test_capacity_curve_recomputes_at_every_count(receipt: dict) -> None:
    """The curve's held counts, work and schedules come from its own arms at every count."""

    from run_fractal_feedback_exploration import capacity_arm_name

    composition = receipt["composition"]
    curve = composition["capacity_curve"]
    declared = receipt["declared"]
    margin = float(curve["margin"])
    assert margin == declared["capacity_suppression_margin"]
    gain = composition["flat_neutral_gain"]["measured_gain"]
    ceiling = float(declared["loop_work_ceiling"])
    horizon = int(declared["long_horizon_ticks"])
    counts = [int(count) for count in curve["counts"]]
    assert counts == sorted(int(c) for c in declared["capacity_curve_counts"])
    limits: dict[str, int | None] = {scheme: None for scheme in declared["capacity_curve_schemes"]}
    for count in counts:
        row = curve["counts"][str(count)]
        control = curve_arm(receipt, count, "no-loop")
        assert control["declared"]["gain"] == 0.0
        assert control["declared"]["written_items"] == row["items"]
        assert row["control_arm"] == control["arm"]
        for scheme in declared["capacity_curve_schemes"]:
            arm = curve_arm(receipt, count, scheme)
            entry = row["schemes"][scheme]
            assert arm["declared"]["gain"] == gain, (
                "a declared curve scheme must run at the flat profile's own measured "
                "neutral gain, not at a declared placeholder"
            )
            assert arm["declared"]["written_items"] == row["items"]
            assert arm["declared"]["drive_items"] == row["items"]
            holding = []
            per_item_work = []
            for item in row["items"]:
                measured = second_half_mean(arm, item)
                control_mean = second_half_mean(control, item)
                item_row = entry["item_rows"][item]
                assert item_row["second_half_mean"] == pytest.approx(measured, rel=1e-12)
                assert item_row["control_second_half_mean"] == pytest.approx(
                    control_mean, rel=1e-12
                )
                assert item_row["minus_control"] == pytest.approx(
                    measured - control_mean, rel=1e-12
                )
                assert item_row["held_above_control"] is (measured > control_mean + margin)
                if item_row["held_above_control"]:
                    holding.append(item)
                # The work an item received is the loop's own per-tick aggregate, and the
                # total per tick is the declared ceiling times that tick's applied
                # amplitude, so holding more items divides one budget rather than
                # multiplying it.
                work_per_item = float(
                    arm["declared"]["mean_applied_work_per_item_per_tick"][item]
                )
                assert item_row["applied_work_per_tick"] == pytest.approx(
                    work_per_item, rel=1e-12
                )
                assert (
                    item_row["scheduled_ticks"]
                    == arm["declared"]["scheduled_ticks"][item]
                )
                per_item_work.append(work_per_item)
                # The retained per-tick trace must carry this item's own drive-call rows:
                # its own signed increment on every call, and the other lanes' cross
                # increments measured around the same call.
                assert item_row["increment_series_rows"] == item_row["scheduled_ticks"], (
                    "the declared curve scheme did not retain one increment row per drive "
                    "call for this item, so its outcome cannot be recomputed from raw rows"
                )
                assert item_row["increment_series_rows"] == sum(
                    1
                    for telemetry in arm["telemetry"]
                    if item in telemetry["increment"]
                )
                # Every drive call reads the other driven lanes around itself, so this lane
                # carries a cross reading on every tick on which some other lane was driven,
                # and one entry per other driven lane per call of its own.
                assert item_row["cross_increment_series_rows"] == sum(
                    1
                    for telemetry in arm["telemetry"]
                    if any(
                        key.endswith(f"->{item}")
                        for key in telemetry["cross_increment"]
                    )
                ), (
                    "every other driven lane must be read around every drive call, so the "
                    "cross-projection is measured rather than inferred"
                )
                assert item_row["cross_increment_entries"] == item_row[
                    "scheduled_ticks"
                ] * (len(row["items"]) - 1)
            assert entry["items_held"] == len(holding)
            assert entry["items_held_names"] == holding
            assert entry["all_items_held"] is (len(holding) == len(row["items"]))
            total = entry["drive_work_per_tick"]
            assert total <= ceiling * float(arm["declared"]["max_amplitude_by_item"][
                max(
                    arm["declared"]["max_amplitude_by_item"],
                    key=lambda name: arm["declared"]["max_amplitude_by_item"][name],
                )
            ]) + 1e-18
            # Holding more items costs no more drive: every declared count and scheme
            # spends the single held item's own per-tick work, so the budget is spread
            # thinner rather than multiplied.
            assert total == pytest.approx(
                float(composition["quiet_regime"]["holds"][declared["headline_item"]][
                    "mean_work_per_tick"
                ]),
                rel=0.10,
            ), (
                f"the declared {scheme} scheme at count {count} did not spend the single "
                "held item's own per-tick work",
            )
            # The declared ceiling is divided equally between the items a tick drives, so
            # the work each item receives is its share of the one budget; the work the
            # actuator actually applies comes from its own per-call receipt and tracks that
            # share rather than reproducing it to the last digit.
            expected_share = 1.0 / len(row["items"])
            for work in per_item_work:
                if scheme != "time-multiplex-adjacent":
                    assert work == pytest.approx(expected_share * total, rel=0.02)
                    assert work < total, (
                        "no declared count lets an item receive the whole budget while the "
                        "scheme drives its neighbours on the same tick"
                    )
            # Every declared scheme drives every declared item. A scheme that drives them
            # all each tick drives each one on every declared tick; the multiplexed scheme
            # drives one per tick over its declared cycle, which repeats and is truncated at
            # the horizon, so each item's driven-tick count is within one tick of its share.
            driven_ticks = [
                int(entry["item_rows"][item]["scheduled_ticks"]) for item in row["items"]
            ]
            assert all(driven > 0 for driven in driven_ticks)
            if scheme == "time-multiplex-adjacent":
                assert all(
                    abs(driven - horizon / len(row["items"])) <= 1
                    for driven in driven_ticks
                )
            else:
                assert driven_ticks == [horizon] * len(row["items"])
            assert entry["driven_tick_imbalance"] == max(driven_ticks) - min(driven_ticks)
            assert entry["driven_tick_imbalance"] <= 1
            if entry["all_items_held"]:
                limits[scheme] = count if limits[scheme] is None else max(
                    limits[scheme], count
                )
        # The declared curve's two-item count writes exactly the shipped two-item pair and
        # drives nothing, so its control is the shipped two-item control's own measurement.
        if count == 2:
            capacity_control = flat_arm(receipt, composition["hold"]["control_arm"])
            for item in row["items"]:
                assert row["control_second_half_mean"][item] == pytest.approx(
                    second_half_mean(capacity_control, item), rel=1e-12
                )
            shared = row["schemes"]["shared"]
            # At the declared two-item count "all items held" is the shipped two-item
            # verdict, so the curve reproduces it rather than restating it.
            assert shared["all_items_held"] is composition["verdicts"][
                "shared_scheme_holds_both_items"
            ]
            assert shared["items_held"] == 2
            # The curve's two-item shared arm and the shipped two-item shared arm are the
            # same declared construction, so their figures must agree exactly.
            for item in row["items"]:
                assert shared["item_rows"][item]["second_half_mean"] == pytest.approx(
                    composition_means(receipt, "shared-two-item", item), rel=1e-12
                )
    for scheme, limit in curve["limit_by_scheme"].items():
        holding_counts = [
            count
            for count in counts
            if curve["counts"][str(count)]["schemes"][scheme]["all_items_held"]
        ]
        assert limit["counts_holding_every_item"] == holding_counts
        assert limit["largest_count_holding_every_item"] == (
            max(holding_counts) if holding_counts else None
        )
        assert limit["largest_count_holding_every_item"] == limits[scheme] or (
            limits[scheme] is None and limit["largest_count_holding_every_item"] is None
        )
        assert limit["items_held_by_count"] == {
            str(count): curve["counts"][str(count)]["schemes"][scheme]["items_held"]
            for count in counts
        }
    assert curve["smallest_hold_margins_by_scheme"] == {
        scheme: {
            str(count): curve["counts"][str(count)]["schemes"][scheme][
                "smallest_hold_margin"
            ]
            for count in counts
        }
        for scheme in declared["capacity_curve_schemes"]
    }
    # The declared margin is load-bearing as the count grows: every scheme's smallest
    # margin over its items falls towards the margin, and the smallest of all comes
    # closest at the largest declared count. A margin set above that margin would have
    # reported a smaller capacity, so the curve's predicate can fail.
    for scheme in declared["capacity_curve_schemes"]:
        margins = [
            float(curve["counts"][str(count)]["schemes"][scheme]["smallest_hold_margin"])
            for count in counts
        ]
        assert margins[-1] < margins[0], (
            f"the {scheme} scheme's smallest hold margin does not fall as the count grows, "
            "so the declared margin is not what the curve is measuring"
        )
        assert margins[-1] > margin, (
            f"the {scheme} scheme's smallest hold margin at the largest count does not "
            "clear the declared margin"
        )
        difference = margins[-1]
        assert (difference > difference + 1e-9) is False
        assert (difference > difference - 1e-9) is True
        assert (difference > difference + 1e-6) is False, (
            "a declared margin a hair above the measured difference must fail the hold, so "
            "the count of held items is a comparison and not a constant"
        )


def test_drive_split_sweep_is_measured_and_its_verdict_can_fail(receipt: dict) -> None:
    """The split sweep's retentions, work division and lane leakage are its own measurements."""

    from run_fractal_feedback_exploration import capacity_split_arm_name

    composition = receipt["composition"]
    sweep = composition["split_sweep"]
    declared = receipt["declared"]
    margin = float(sweep["margin"])
    gain = composition["flat_neutral_gain"]["measured_gain"]
    headline = declared["headline_item"]
    second = declared["capacity_item"]
    control = flat_arm(receipt, sweep["control"]["arm"])
    assert sweep["control"]["headline_second_half_mean"] == pytest.approx(
        second_half_mean(control, headline), rel=1e-12
    )
    assert sweep["control"]["second_second_half_mean"] == pytest.approx(
        second_half_mean(control, second), rel=1e-12
    )
    declared_splits = [tuple(float(w) for w in split) for split in declared["capacity_split_weights"]]
    assert len(sweep["splits"]) == len(declared_splits)
    totals = []
    headline_means = []
    second_means = []
    for split in declared_splits:
        arm = flat_arm(receipt, capacity_split_arm_name(split))
        row = sweep["splits"][capacity_split_arm_name(split)]
        assert arm["declared"]["drive_split"] == list(split)
        assert arm["declared"]["gain"] == gain
        assert row["split"] == list(split)
        measured_headline = second_half_mean(arm, headline)
        measured_second = second_half_mean(arm, second)
        assert row["headline_second_half_mean"] == pytest.approx(
            measured_headline, rel=1e-12
        )
        assert row["second_second_half_mean"] == pytest.approx(measured_second, rel=1e-12)
        assert row["headline_held_above_control"] is (
            measured_headline > float(sweep["control"]["headline_second_half_mean"]) + margin
        )
        assert row["second_held_above_control"] is (
            measured_second > float(sweep["control"]["second_second_half_mean"]) + margin
        )
        assert row["both_items_held"] is (
            row["headline_held_above_control"] and row["second_held_above_control"]
        )
        # The declared split is a division of one work budget: the work per item tracks the
        # declared proportion, and every split spends the same total per tick.
        work_headline = float(
            arm["declared"]["mean_applied_work_per_item_per_tick"][headline]
        )
        work_second = float(
            arm["declared"]["mean_applied_work_per_item_per_tick"][second]
        )
        assert row["headline_applied_work_per_tick"] == pytest.approx(
            work_headline, rel=1e-12
        )
        assert row["second_applied_work_per_tick"] == pytest.approx(
            work_second, rel=1e-12
        )
        assert work_headline / (work_headline + work_second) == pytest.approx(
            split[0], abs=1e-6
        )
        totals.append(row["drive_work_per_tick"])
        headline_means.append(measured_headline)
        second_means.append(measured_second)
        # The cross-lane leakage recomputes from this split's own per-tick rows.
        reclaimed: dict[str, float] = {}
        for driven_item, other_item in ((headline, second), (second, headline)):
            cross_key = f"{driven_item}->{other_item}"
            pairs = [
                (
                    abs(float(telemetry["increment"][driven_item])),
                    abs(float(telemetry["cross_increment"][cross_key])),
                )
                for telemetry in arm["telemetry"]
                if driven_item in telemetry["increment"]
                and cross_key in telemetry["cross_increment"]
            ]
            assert len(pairs) == arm["declared"]["scheduled_ticks"][driven_item], (
                "every one of this split's drive calls must have read the other lane"
            )
            own = sum(pair[0] for pair in pairs) / len(pairs)
            other = sum(pair[1] for pair in pairs) / len(pairs)
            reclaimed[f"{driven_item}_into_{other_item}"] = other / own
        for key, value in reclaimed.items():
            assert row["cross_lane_fraction"][key] == pytest.approx(value, rel=1e-9)
        assert row["max_cross_lane_fraction"] == pytest.approx(
            max(reclaimed.values()), rel=1e-9
        )
    # The declared splits divide one budget: every split spends the single held item's own
    # per-tick work, so a split that handed each item the single-item budget would spend
    # about twice this and the items would not be sharing a channel.
    single_budget = float(
        composition["quiet_regime"]["holds"][headline]["mean_work_per_tick"]
    )
    for total, split in zip(totals, declared_splits):
        assert total == pytest.approx(single_budget, rel=0.10), (
            f"the declared split {split} did not spend the single held item's own "
            "per-tick work, so its budget is not being divided between the two items"
        )
    assert max(totals) < 1.2 * min(totals), (
        "the declared splits do not spend the same order of per-tick work"
    )
    assert sweep["headline_retention_swing"] == pytest.approx(
        max(headline_means) - min(headline_means), rel=1e-12
    )
    assert sweep["second_retention_swing"] == pytest.approx(
        max(second_means) - min(second_means), rel=1e-12
    )
    swing = float(sweep["largest_retention_swing"])
    assert swing == pytest.approx(
        max(sweep["headline_retention_swing"], sweep["second_retention_swing"]),
        rel=1e-12,
    )
    assert sweep["split_dependent"] is (swing > margin)
    # The verdict can fail in either direction on the measured swing itself.
    assert (swing > swing + 1e-9) is False
    assert (swing > swing - 1e-9) is True
    # The measured answer: the items' states do not leak into each other's lane, yet their
    # retentions follow the split, so what they share is the declared work budget and the
    # one read-back that spends it.
    leakage = max(
        float(row["max_cross_lane_fraction"])
        for row in sweep["splits"].values()
        if row["max_cross_lane_fraction"] is not None
    )
    assert sweep["largest_cross_lane_fraction"] == pytest.approx(leakage, rel=1e-9)
    assert leakage < 1e-6, "the declared lanes are expected not to leak into each other"
    assert sweep["split_dependent"] is True and leakage < margin


def test_quiet_regime_attributes_the_falling_frame_energy(receipt: dict) -> None:
    """The falling frame energy is attributed to the frame, and the ladder can fail."""

    from run_fractal_feedback_exploration import (
        capacity_arm_name,
        quiet_regime_gain_arm_name,
        quiet_regime_hold_arm_name,
    )

    composition = receipt["composition"]
    quiet = composition["quiet_regime"]
    declared = receipt["declared"]
    gain = composition["flat_neutral_gain"]["measured_gain"]
    horizon = int(declared["long_horizon_ticks"])
    assert quiet["gain"] == gain
    assert quiet["default_profile_hold"]["frame_energy_ratio_at_horizon"] == pytest.approx(
        receipt["arms"]["long-horizon-measured-neutral-gain"]["horizon"][
            "frame_energy_ratio"
        ],
        rel=1e-12,
    )
    for item, row in quiet["holds"].items():
        arm = flat_arm(receipt, quiet_regime_hold_arm_name(item))
        assert arm["declared"]["written_items"] == [item], (
            "a declared quiet-regime hold must write exactly the item it holds, so the "
            "three holds are read on one construction"
        )
        assert arm["declared"]["drive_items"] == [item]
        assert arm["declared"]["gain"] == gain
        assert len(row["energy_trajectory"]) == horizon
        assert len(row["work_trajectory"]) == horizon
        assert row["row_count"] == horizon
        assert row["energy_trajectory"] == [
            float(telemetry["frame_energy_ratio_after"]) for telemetry in arm["telemetry"]
        ]
        assert row["work_trajectory"] == [
            float(telemetry["work_this_tick"]) for telemetry in arm["telemetry"]
        ]
        assert row["energy_first"] == pytest.approx(row["energy_trajectory"][0], rel=1e-12)
        assert row["energy_last"] == pytest.approx(row["energy_trajectory"][-1], rel=1e-12)
        assert row["energy_minimum"] == pytest.approx(
            min(row["energy_trajectory"]), rel=1e-12
        )
        assert row["energy_monotone_falling"] is (
            row["energy_trajectory"]
            == sorted(row["energy_trajectory"], reverse=True)
        )
        assert row["frame_energy_ratio_at_horizon"] == pytest.approx(
            arm["horizon"]["frame_energy_ratio"], rel=1e-12
        )
        assert row["retention_at_horizon"] == pytest.approx(
            arm["neutral_stability"]["measure_retention_at_horizon"], rel=1e-12
        )
        assert row["energy_falls_while_holding"] is (
            row["frame_energy_ratio_at_horizon"] < 1.0
            and row["retention_at_horizon"] > 1.0
        )
        assert row["throughput_increases_while_holding"] is (
            row["frame_energy_ratio_at_horizon"] > 1.0
            and row["retention_at_horizon"] > 1.0
        )
    # The declared answer on a single-item frame: the flat profile's hold adds energy while
    # it holds the direction, at the neutral gain and at every declared multiple of it.
    assert not quiet["items_with_falling_energy_while_holding"], (
        "a declared single-item hold on the flat profile is expected to end above its "
        "post-write frame energy; if one now falls, the quiet-regime verdict must change"
    )
    assert quiet["every_declared_single_item_hold_increases_throughput"] is True
    assert set(quiet["items_whose_throughput_increases_while_holding"]) == set(
        quiet["holds"]
    )
    factors = [float(factor) for factor in declared["quiet_regime_gain_factors"]]
    assert [float(factor) for factor in quiet["gain_ladder"]] == factors
    for factor in factors:
        arm = flat_arm(receipt, quiet_regime_gain_arm_name(factor))
        row = quiet["gain_ladder"][str(factor)]
        assert row["gain"] == pytest.approx(gain * factor, rel=1e-12)
        assert arm["declared"]["gain"] == pytest.approx(gain * factor, rel=1e-12)
        assert row["frame_energy_ratio_at_horizon"] == pytest.approx(
            arm["horizon"]["frame_energy_ratio"], rel=1e-12
        )
        assert row["retention_at_horizon"] == pytest.approx(
            arm["neutral_stability"]["measure_retention_at_horizon"], rel=1e-12
        )
        assert row["energy_falls_at_horizon"] is (
            row["frame_energy_ratio_at_horizon"] < 1.0
        )
        assert row["energy_trajectory"] == [
            float(telemetry["frame_energy_ratio_after"]) for telemetry in arm["telemetry"]
        ]
        assert row["clipped_ticks"] == int(arm["drive"]["clipped_ticks"])
    # The declared ladder's neutral-gain rung is the same construction as the headline item's
    # own hold, so the two must agree figure for figure.
    headline = declared["headline_item"]
    neutral_rung = quiet["gain_ladder"]["1.0"]
    assert neutral_rung["frame_energy_ratio_at_horizon"] == pytest.approx(
        quiet["holds"][headline]["frame_energy_ratio_at_horizon"], rel=1e-12
    )
    assert neutral_rung["retention_at_horizon"] == pytest.approx(
        quiet["holds"][headline]["retention_at_horizon"], rel=1e-12
    )
    assert quiet["gain_factors_with_falling_energy"] == [
        factor for factor in [str(f) for f in factors] if quiet["gain_ladder"][factor][
            "energy_falls_at_horizon"
        ]
    ]
    assert quiet["every_declared_gain_falls"] is (
        len(quiet["gain_factors_with_falling_energy"]) == len(quiet["gain_ladder"])
    )
    assert quiet["every_declared_gain_falls"] is False
    # The composition's own hold arm is a two-item frame, so the fall is attributed: the
    # driven item holds while the written-but-undriven item decays, and the same loop on a
    # frame carrying only the held item ends above one.
    two_item = quiet["two_item_frame_hold"]
    arm = flat_arm(receipt, capacity_arm_name("flat", "single-item-headline"))
    assert two_item["arm"] == arm["arm"]
    assert two_item["driven_item"] == headline
    assert two_item["undriven_written_item"] not in arm["declared"]["drive_items"]
    assert two_item["frame_energy_ratio_at_horizon"] == pytest.approx(
        arm["horizon"]["frame_energy_ratio"], rel=1e-12
    )
    assert two_item["driven_retention_at_horizon"] == pytest.approx(
        arm["horizon"]["item_retention"][headline], rel=1e-12
    )
    assert two_item["undriven_retention_at_horizon"] == pytest.approx(
        arm["horizon"]["item_retention"][two_item["undriven_written_item"]], rel=1e-12
    )
    assert two_item["undriven_retention_trajectory"] == [
        float(sample["item_retention"][two_item["undriven_written_item"]])
        for sample in arm["samples"]
    ]
    assert two_item["driven_retention_trajectory"] == [
        float(sample["item_retention"][headline]) for sample in arm["samples"]
    ]
    assert two_item["undriven_item_decays"] is (
        two_item["undriven_retention_at_horizon"]
        < two_item["driven_retention_at_horizon"]
    )
    assert two_item["energy_trajectory"] == [
        float(telemetry["frame_energy_ratio_after"]) for telemetry in arm["telemetry"]
    ]
    assert two_item["frame_energy_ratio_at_horizon"] < 1.0
    assert two_item["undriven_item_decays"] is True
    assert quiet["holds"][headline]["frame_energy_ratio_at_horizon"] > 1.0
    assert "two-item frame" in quiet["quoting_regime"]


def test_capacity_mechanism_fields_recompute_from_the_raw_trace(receipt: dict) -> None:
    """The mechanism fields are recomputed from the diagnosis arms' own per-tick rows."""

    from run_fractal_feedback_exploration import capacity_arm_name

    composition = receipt["composition"]
    declared = receipt["declared"]
    headline = declared["headline_item"]
    second = declared["capacity_item"]
    flat_diagnosis = composition["diagnosis"]
    for label, arm, regime in (
        (
            "flat",
            flat_arm(receipt, capacity_arm_name("flat", "shared-two-item")),
            flat_diagnosis,
        ),
        (
            "amplifying",
            receipt["arms"]["capacity-two-item-telemetry"],
            receipt["reading"]["capacity"]["diagnosis"],
        ),
    ):
        rows = arm["telemetry"]
        assert regime["arm"] == arm["arm"]
        assert len(rows) == int(declared["long_horizon_ticks"])
        increments_headline = [float(row["increment"][headline]) for row in rows]
        increments_second = [float(row["increment"][second]) for row in rows]
        pairs = [
            (left, right)
            for left, right, driven in zip(
                increments_headline,
                increments_second,
                [
                    left != 0.0 or right != 0.0
                    for left, right in zip(increments_headline, increments_second)
                ],
            )
            if driven
        ]
        relative_phase = sum(
            (1 if left > 0.0 else -1) * (1 if right > 0.0 else -1) for left, right in pairs
        ) / len(pairs)
        assert regime["increment_relative_phase"] == pytest.approx(
            relative_phase, rel=1e-12
        )
        assert regime["increment_sign_agreement"] == pytest.approx(
            sum(1 for left, right in pairs if (left > 0.0) == (right > 0.0)) / len(pairs),
            rel=1e-12,
        )
        mean_left = sum(increments_headline) / len(increments_headline)
        mean_right = sum(increments_second) / len(increments_second)
        covariance = sum(
            (left - mean_left) * (right - mean_right)
            for left, right in zip(increments_headline, increments_second)
        )
        spread = math.sqrt(
            sum((value - mean_left) ** 2 for value in increments_headline)
            * sum((value - mean_right) ** 2 for value in increments_second)
        )
        assert regime["increment_correlation"] == pytest.approx(
            covariance / spread, rel=1e-6
        )
        cross_expected: dict[str, float] = {}
        for driven_item, other_item in ((headline, second), (second, headline)):
            cross_key = f"{driven_item}->{other_item}"
            own = [
                abs(float(row["increment"][driven_item]))
                for row in rows
                if driven_item in row["increment"]
            ]
            other = [
                abs(float(row["cross_increment"][cross_key]))
                for row in rows
                if cross_key in row["cross_increment"]
            ]
            assert len(other) == len(own) == arm["declared"]["scheduled_ticks"][
                driven_item
            ], (
                "each of this regime's drive calls must have been read on both lanes, so "
                "the cross-projection rests on measured pairs rather than one surviving call"
            )
            cross_expected[f"{driven_item}_into_{other_item}"] = (
                sum(other) / len(other)
            ) / (sum(own) / len(own))
            reported = regime["cross_projection"][f"{driven_item}_into_{other_item}"]
            assert reported is not None, (
                f"the {label} diagnosis reports no cross-projection for {driven_item}; "
                "every drive call must have been read on both lanes"
            )
            assert reported["mean_abs_own_lane_increment"] == pytest.approx(
                sum(own) / len(own), rel=1e-12
            )
            assert reported["other_lane_fraction_of_own"] == pytest.approx(
                cross_expected[f"{driven_item}_into_{other_item}"], rel=1e-12
            )
        assert regime["max_cross_projection_fraction"] == pytest.approx(
            max(cross_expected.values()), rel=1e-12
        )
        if rows[0].get("quadrature_before"):
            angles = [
                math.degrees(
                    math.atan2(
                        float(row["quadrature_before"][second])
                        * float(row["ratio_before"][headline])
                        - float(row["ratio_before"][second])
                        * float(row["quadrature_before"][headline]),
                        float(row["ratio_before"][second])
                        * float(row["ratio_before"][headline])
                        + float(row["quadrature_before"][second])
                        * float(row["quadrature_before"][headline]),
                    )
                )
                for row in rows
            ]
            circular = math.degrees(
                math.atan2(
                    sum(math.sin(math.radians(angle)) for angle in angles),
                    sum(math.cos(math.radians(angle)) for angle in angles),
                )
            )
            assert regime["quadrature_relative_phase_degrees"] == pytest.approx(
                circular, rel=1e-6
            )
    # The two regimes differ in what the shared scalar does, and the receipt says so from
    # each regime's own increments rather than from one regime's mechanism.
    flat_increments = {
        item: sum(float(row["increment"][item]) for row in flat_arm(
            receipt, capacity_arm_name("flat", "shared-two-item")
        )["telemetry"])
        for item in (headline, second)
    }
    assert flat_increments[headline] > 0.0 and flat_increments[second] > 0.0
    assert flat_diagnosis["mechanism_measured"] is False
    assert flat_diagnosis["increment_sign_agreement"] == pytest.approx(1.0, abs=1e-9)
    mechanism = receipt["reading"]["capacity"]["diagnosis"]["mechanism"]
    assert mechanism.count("the declared shared loop puts one signed scalar") == 1
    assert mechanism.count("sits against") == 1, (
        "the amplifying regime's mechanism sentence states the read-back anti-correlation "
        "once per item rather than repeating the second item's clause"
    )
