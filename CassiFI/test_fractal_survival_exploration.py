"""Direct tests for the fractal survival exploration runner.

Everything is built in-process from the two harnesses it imports; nothing is read
from disk and no harness ``main`` is re-run.  The tests assert observable
behaviour of the runner: that the declared arrangement hooks actually drive the
built profiles and move a measured quantity, that the declared scale-depth metric
agrees with the measured packet supports, that the attribution arms really split
the compound arrangement into its two declared hooks (rail-only carries the
compound rail and the default mass metric, mass-only the converse, and the
``undivided`` topology-hook arm is shown to move both channels at once), that
both declared contrast margins and all three attribution margins can fail (each
shown by a firing mutation on the real receipt body, the additivity test in both
signs), that every reported figure is reproducible, and that the content digest
is reproducible and mutation-sensitive.
"""
from __future__ import annotations

import copy
import json

import pytest

import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry
import run_fractal_survival_exploration as survival

BODY_CORE_KEYS = ("schema", "declared", "profiles", "scaffold", "spacing", "attribution")


def body_core(receipt: dict) -> dict:
    """The measured body the summary and the digest are computed from."""

    return {key: receipt[key] for key in BODY_CORE_KEYS}


def without_timing(receipt: dict) -> dict:
    return {key: value for key, value in receipt.items() if key != "elapsed_seconds"}


@pytest.fixture(scope="module")
def receipts() -> tuple[dict, dict]:
    """Two independent full runs of the declared measurement."""

    return survival.build_receipt(), survival.build_receipt()


# --------------------------------------------------------------------------
# declared construction actually drives the body
# --------------------------------------------------------------------------
def test_declared_profiles_differ_in_the_declared_hooks(receipts):
    receipt, _ = receipts
    hooks = {
        name: receipt["profiles"][name]["profile_hooks"]
        for name in survival.PROFILE_NAMES
    }
    # the declared hook fields differ exactly as the arrangements declare
    assert hooks[survival.DEFAULT_PROFILE_NAME]["has_projected_transport"] is False
    assert hooks[survival.DEFAULT_PROFILE_NAME]["has_projected_inv_mass"] is False
    for name in ("nested-core-shell", "recursive-paired-loops"):
        assert hooks[name]["has_projected_transport"] is True
    assert hooks["nested-core-shell"]["has_projected_inv_mass"] is True
    assert hooks["recursive-paired-loops"]["has_projected_inv_mass"] is False
    # the built rails really differ, in a level figure and in full bytes
    assert len({hooks[name]["transport_l1"] for name in survival.PROFILE_NAMES}) == 3
    assert len({hooks[name]["transport_sha256"] for name in survival.PROFILE_NAMES}) == 3
    # and the receipt's hooks are the hooks of freshly built profiles, not stale data
    for name in survival.PROFILE_NAMES:
        built = survival.profile_hook_signature(survival.build_declared_profile(name))
        assert built == hooks[name], name


def test_declared_hooks_move_the_measured_recovery(receipts):
    receipt, _ = receipts
    for arm_name in survival.SCAFFOLD_ARM_NAMES:
        recoveries = [
            receipt["scaffold"]["per_profile"][name][arm_name]["recovery_fraction"]
            for name in survival.PROFILE_NAMES
        ]
        assert len(set(recoveries)) == 3, (arm_name, recoveries)


def test_default_profile_is_the_canonical_default():
    canonical = survival.profile_hook_signature(durability.ResonantProfile())
    via_geometry = survival.profile_hook_signature(
        geometry.build_profile(
            geometry.arrangement_named(survival.DEFAULT_PROFILE_NAME)
        )
    )
    assert canonical == via_geometry
    assert canonical["has_projected_transport"] is False
    assert canonical["has_projected_inv_mass"] is False


def test_scale_depth_metric_agrees_with_the_measured_supports(receipts):
    receipt, _ = receipts
    for item in receipt["declared"]["item_declarations"]:
        assert item["declared_scale_depth"] == len(item["path"])
        assert item["declared_support_width"] == (
            item["declared_support"][1] - item["declared_support"][0]
        )
    for profile_name in survival.PROFILE_NAMES:
        hooks = receipt["profiles"][profile_name]["profile_hooks"]
        port_count = hooks["port_count"]
        for row in receipt["profiles"][profile_name]["items"]:
            depth = row["declared_scale_depth"]
            assert row["measured_scale_depth"] == depth, row
            assert row["measured_support_width"] * 2**depth == port_count, row
            assert row["support"]["stop"] - row["support"]["start"] == row[
                "measured_support_width"
            ]


def test_declared_pairs_span_the_declared_scale_distances(receipts):
    receipt, _ = receipts
    pairs = {row["name"]: row for row in receipt["declared"]["pair_declarations"]}
    assert pairs[survival.NEAR_PAIR_NAME]["declared_scale_distance"] == 0
    assert pairs[survival.FAR_PAIR_NAME]["declared_scale_distance"] == 2
    assert pairs["mid"]["declared_scale_distance"] == 1
    assert len(
        {
            row["declared_scale_distance"]
            for row in receipt["declared"]["pair_declarations"]
        }
    ) == 3
    # the near pair is the same-scale disjoint sibling pair
    assert pairs[survival.NEAR_PAIR_NAME]["declared_scale_depths"] == [1, 1]
    assert pairs[survival.NEAR_PAIR_NAME]["declared_support_relation"] == "disjoint-adjacent"
    assert pairs[survival.FAR_PAIR_NAME]["declared_support_relation"] == "nested"


# --------------------------------------------------------------------------
# the declared margin tests can fail
# --------------------------------------------------------------------------
def test_profile_contrast_margin_verdict_matches_the_declared_comparison(receipts):
    receipt, _ = receipts
    summary = receipt["summary"]
    margin = receipt["declared"]["profile_recovery_margin"]
    assert summary["scaffold_recovery_margin"] == margin
    seen = set()
    for per_arm in summary["scaffold_recovery_delta_vs_default"].values():
        for entry in per_arm.values():
            expected = abs(entry["absolute_difference"]) >= entry["margin"]
            assert entry["separates"] is expected
            seen.add(entry["separates"])
    assert seen == {True, False}
    assert summary["scaffold_dependence"] is any(
        entry["separates"]
        for per_arm in summary["scaffold_recovery_delta_vs_default"].values()
        for entry in per_arm.values()
    )


def test_profile_contrast_margin_can_fail_under_mutation(receipts):
    receipt, _ = receipts
    core = copy.deepcopy(body_core(receipt))
    assert survival.summarize(core)["scaffold_dependence"] is True
    # erase the contrast: give every non-default profile the default recovery
    default_rows = core["scaffold"]["per_profile"][survival.DEFAULT_PROFILE_NAME]
    for profile_name, arm_rows in core["scaffold"]["per_profile"].items():
        if profile_name == survival.DEFAULT_PROFILE_NAME:
            continue
        for arm_name in survival.SCAFFOLD_ARM_NAMES:
            arm_rows[arm_name]["recovery_fraction"] = default_rows[arm_name][
                "recovery_fraction"
            ]
    mutated = survival.summarize(core)
    assert mutated["scaffold_dependence"] is False
    assert all(
        entry["separates"] is False
        for per_arm in mutated["scaffold_recovery_delta_vs_default"].values()
        for entry in per_arm.values()
    )


def test_profile_contrast_margin_fires_just_above_the_threshold(receipts):
    receipt, _ = receipts
    core = copy.deepcopy(body_core(receipt))
    margin = receipt["declared"]["profile_recovery_margin"]
    default_rows = core["scaffold"]["per_profile"][survival.DEFAULT_PROFILE_NAME]
    target = core["scaffold"]["per_profile"]["nested-core-shell"]
    for arm_name in survival.SCAFFOLD_ARM_NAMES:
        base = default_rows[arm_name]["recovery_fraction"]
        # the margin test is a threshold, so just below it must not separate ...
        target[arm_name]["recovery_fraction"] = base + margin * 0.5
        assert (
            survival.summarize(core)["scaffold_recovery_delta_vs_default"][
                "nested-core-shell"
            ][arm_name]["separates"]
            is False
        )
        # ... and just above it must
        target[arm_name]["recovery_fraction"] = base + margin * 2.0
        assert (
            survival.summarize(core)["scaffold_recovery_delta_vs_default"][
                "nested-core-shell"
            ][arm_name]["separates"]
            is True
        )


def test_spacing_margin_verdict_matches_the_declared_comparison(receipts):
    receipt, _ = receipts
    headline = receipt["summary"]["spacing_headline"]
    assert headline["confusion_separates"] is (
        headline["confusion_difference"] >= headline["confusion_margin"]
    )
    assert headline["recovery_separates"] is (
        headline["recovery_difference"] >= headline["recovery_margin"]
    )
    assert headline["separates"] is (
        headline["confusion_separates"] and headline["recovery_separates"]
    )
    figures = receipt["summary"]["spacing_figures_default_profile"]
    near = figures[survival.NEAR_PAIR_NAME]
    far = figures[survival.FAR_PAIR_NAME]
    assert headline["confusion_difference"] == pytest.approx(
        near["max_off_diagonal_deposit_share"]
        - far["max_off_diagonal_deposit_share"]
    )
    assert headline["recovery_difference"] == pytest.approx(
        far["recovery_fraction"] - near["recovery_fraction"]
    )


def test_spacing_margin_can_fail_under_mutation(receipts):
    receipt, _ = receipts
    core = copy.deepcopy(body_core(receipt))
    assert survival.summarize(core)["spacing_headline"]["separates"] is True
    # erase the spacing contrast on the declared default profile: make the far
    # pair read exactly like the near pair
    pairs = core["spacing"]["per_profile"][survival.DEFAULT_PROFILE_NAME]["pairs"]
    near = pairs[survival.NEAR_PAIR_NAME]
    far = pairs[survival.FAR_PAIR_NAME]
    far["max_off_diagonal_deposit_share"] = near["max_off_diagonal_deposit_share"]
    far["recovery_fraction"] = near["recovery_fraction"]
    mutated = survival.summarize(core)["spacing_headline"]
    assert mutated["confusion_separates"] is False
    assert mutated["recovery_separates"] is False
    assert mutated["separates"] is False


def test_spacing_margin_fires_just_around_the_threshold(receipts):
    receipt, _ = receipts
    core = copy.deepcopy(body_core(receipt))
    pairs = core["spacing"]["per_profile"][survival.DEFAULT_PROFILE_NAME]["pairs"]
    near = pairs[survival.NEAR_PAIR_NAME]
    far = pairs[survival.FAR_PAIR_NAME]
    confusion_margin = receipt["declared"]["spacing_confusion_margin"]
    recovery_margin = receipt["declared"]["spacing_recovery_margin"]
    far["max_off_diagonal_deposit_share"] = (
        near["max_off_diagonal_deposit_share"] - confusion_margin * 0.5
    )
    far["recovery_fraction"] = near["recovery_fraction"] + recovery_margin * 0.5
    below = survival.summarize(core)["spacing_headline"]
    assert below["confusion_separates"] is False
    assert below["recovery_separates"] is False
    assert below["separates"] is False
    far["max_off_diagonal_deposit_share"] = (
        near["max_off_diagonal_deposit_share"] - confusion_margin * 2.0
    )
    far["recovery_fraction"] = near["recovery_fraction"] + recovery_margin * 2.0
    above = survival.summarize(core)["spacing_headline"]
    assert above["confusion_separates"] is True
    assert above["recovery_separates"] is True
    assert above["separates"] is True


def test_declared_no_activity_baseline_arm_is_the_receipt_s_own_control(receipts):
    receipt, _ = receipts
    summary = receipt["summary"]
    # the same margin test applied to the baseline arm is not vacuous: on the real
    # numbers it returns a different verdict than the activity arm does
    baseline = summary["spacing_headline_without_activity"]
    assert baseline["near_recovery_fraction"] == pytest.approx(1.0)
    assert baseline["far_recovery_fraction"] == pytest.approx(1.0)
    assert baseline["separates"] is False
    assert summary["spacing_headline"]["separates"] is True
    # the baseline is measured on every declared profile, not restated
    for profile_name in survival.PROFILE_NAMES:
        figures = summary["spacing_figures_without_activity_per_profile"][profile_name]
        for pair_name in (survival.NEAR_PAIR_NAME, survival.FAR_PAIR_NAME, "mid"):
            assert figures[pair_name]["recovery_fraction"] == pytest.approx(1.0)
            assert figures[pair_name]["written_direction_energy_fraction_total"] == pytest.approx(1.0)
            assert figures[pair_name]["unwritten_direction_energy_fraction_total"] == pytest.approx(0.0)


# --------------------------------------------------------------------------
# attribution: the compound arrangement's two declared hooks are separated
# --------------------------------------------------------------------------
def test_attribution_arms_are_built_from_the_declared_hooks(receipts):
    receipt, _ = receipts
    hooks = receipt["summary"]["attribution_hook_signatures"]
    metrics = receipt["summary"]["attribution_mass_metric_signatures"]
    default = survival.DEFAULT_PROFILE_NAME
    rail = survival.RAIL_ONLY_PROFILE_NAME
    mass_only = survival.MASS_ONLY_PROFILE_NAME
    compound = survival.COMPOUND_PROFILE_NAME
    # the rail-only arm carries the compound rail with the default mass metric
    assert hooks[rail]["has_projected_transport"] is True
    assert hooks[rail]["has_projected_inv_mass"] is False
    assert hooks[rail]["transport_sha256"] == hooks[compound]["transport_sha256"]
    assert metrics[rail]["source"] == "inertances"
    assert metrics[rail]["diagonal_sha256"] == metrics[default]["diagonal_sha256"]
    # the mass-only arm carries the compound mass metric with the default rail
    assert hooks[mass_only]["has_projected_transport"] is False
    assert hooks[mass_only]["has_projected_inv_mass"] is True
    assert hooks[mass_only]["transport_sha256"] == hooks[default]["transport_sha256"]
    assert metrics[mass_only]["source"] == "projected_inv_mass"
    assert metrics[mass_only]["diagonal_sha256"] == metrics[compound]["diagonal_sha256"]
    assert metrics[mass_only]["diagonal_sha256"] != metrics[default]["diagonal_sha256"]
    # the compound arm is exactly the two single-channel hooks together, and is
    # the same body the scaffold contrast measures
    assert hooks[compound]["has_projected_transport"] is True
    assert hooks[compound]["has_projected_inv_mass"] is True
    assert hooks[compound] == receipt["profiles"][compound]["profile_hooks"]
    # the receipt's rows are freshly built arms, not stale data
    rows = receipt["attribution"]["per_arm"]
    for name in survival.ATTRIBUTION_PROFILE_NAMES:
        built = survival.build_attribution_profile(name)
        assert survival.profile_hook_signature(built) == rows[name]["profile_hooks"], name
        assert survival.mass_metric_signature(built) == rows[name]["mass_metric"], name
    # the declared rules are carried in the receipt, one per arm
    rules = {row["name"]: row for row in receipt["declared"]["attribution_arm_declarations"]}
    assert sorted(rules) == sorted(survival.ATTRIBUTION_PROFILE_NAMES)
    for name, row in rules.items():
        assert row["rule"] == rows[name]["declared_construction_rule"], name
        assert row["channel"] == rows[name]["declared_channel"], name
        assert row["toggles"] == rows[name]["declared_toggles"], name
    # the declared channel label must match the hooks the arm actually moves
    one_channel_hooks = {
        "default": (False, False),
        "rail": (True, False),
        "mass": (False, True),
        "rail+mass": (True, True),
    }
    for name, row in rules.items():
        channel = row["channel"]
        if channel in one_channel_hooks:
            transport_flag, mass_flag = one_channel_hooks[channel]
            assert hooks[name]["has_projected_transport"] is transport_flag, name
            assert hooks[name]["has_projected_inv_mass"] is mass_flag, name
        else:
            # the one declared arm that is not a one-channel label says so, and it
            # is the topology-hook arm
            assert name == survival.TOPOLOGY_MASS_PROFILE_NAME, (name, channel)
            assert "topology" in channel, channel
    # the declared default arm is the canonical default body
    assert survival.profile_hook_signature(durability.ResonantProfile()) == hooks[default]
    assert survival.mass_metric_signature(durability.ResonantProfile()) == metrics[default]


def test_attribution_default_and_compound_rows_reproduce_the_scaffold_contrast(receipts):
    receipt, _ = receipts
    # the attribution contrast measures the same two bodies the scaffold contrast
    # measures, in its own pass: the rows must agree exactly
    rows = receipt["attribution"]["per_arm"]
    for name in (survival.DEFAULT_PROFILE_NAME, survival.COMPOUND_PROFILE_NAME):
        assert rows[name]["arms"] == receipt["scaffold"]["per_profile"][name], name


def test_attribution_declares_undivided_as_a_topology_hook_contrast(receipts):
    receipt, _ = receipts
    rules = {row["name"]: row for row in receipt["declared"]["attribution_arm_declarations"]}
    undivided = survival.TOPOLOGY_MASS_PROFILE_NAME
    # declared: the geometry harness's other mass contrast is not a mass-only
    # variant, and the receipt says what it toggles instead
    assert rules[undivided]["channel"] != rules[survival.MASS_ONLY_PROFILE_NAME]["channel"]
    assert "topology" in rules[undivided]["toggles"]
    # measured: it carries neither projected hook, yet both its rail and its mass
    # metric differ from the default profile's, so it cannot be read as one channel
    hooks = receipt["summary"]["attribution_hook_signatures"]
    metrics = receipt["summary"]["attribution_mass_metric_signatures"]
    assert hooks[undivided]["has_projected_transport"] is False
    assert hooks[undivided]["has_projected_inv_mass"] is False
    assert hooks[undivided]["transport_sha256"] != hooks[survival.DEFAULT_PROFILE_NAME][
        "transport_sha256"
    ]
    assert hooks[undivided]["transport_sha256"] != hooks[survival.RAIL_ONLY_PROFILE_NAME][
        "transport_sha256"
    ]
    assert (
        metrics[undivided]["diagonal_sha256"]
        != metrics[survival.DEFAULT_PROFILE_NAME]["diagonal_sha256"]
    )
    assert metrics[undivided]["diagonal_min"] == pytest.approx(1.0)
    assert metrics[undivided]["diagonal_max"] == pytest.approx(1.0)
    assert metrics[survival.DEFAULT_PROFILE_NAME]["diagonal_min"] < metrics[
        survival.DEFAULT_PROFILE_NAME
    ]["diagonal_max"]
    # it is excluded from the two-channel decomposition and reported as its own
    # compound delta against the default profile instead
    assert undivided not in receipt["summary"]["attribution_components"]
    assert undivided in receipt["summary"]["attribution_delta_vs_default"]
    for arm_name, entry in receipt["summary"]["attribution_delta_vs_default"][
        undivided
    ].items():
        assert entry["profile_recovery_fraction"] == receipt["summary"][
            "attribution_recovery_fraction"
        ][undivided][arm_name]


def test_attribution_components_match_the_receipt_s_own_recoveries(receipts):
    receipt, _ = receipts
    summary = receipt["summary"]
    recoveries = summary["attribution_recovery_fraction"]
    default = survival.DEFAULT_PROFILE_NAME
    for arm_name, figures in summary["attribution_components"].items():
        base = recoveries[default][arm_name]
        rail = recoveries[survival.RAIL_ONLY_PROFILE_NAME][arm_name]
        mass = recoveries[survival.MASS_ONLY_PROFILE_NAME][arm_name]
        compound = recoveries[survival.COMPOUND_PROFILE_NAME][arm_name]
        assert figures["default_recovery_fraction"] == base
        assert figures["rail_only_recovery_fraction"] == rail
        assert figures["mass_only_recovery_fraction"] == mass
        assert figures["compound_recovery_fraction"] == compound
        assert figures["rail_component"] == pytest.approx(rail - base)
        assert figures["mass_component"] == pytest.approx(mass - base)
        assert figures["compound_gain"] == pytest.approx(compound - base)
        assert figures["attributed_gain"] == pytest.approx(
            figures["rail_component"] + figures["mass_component"]
        )
        assert figures["interaction_residual"] == pytest.approx(
            figures["compound_gain"] - figures["attributed_gain"]
        )


def test_attribution_margins_give_the_declared_verdicts(receipts):
    receipt, _ = receipts
    summary = receipt["summary"]
    channels = {
        (True, True): "rail-and-mass",
        (True, False): "rail",
        (False, True): "mass",
        (False, False): "neither",
    }
    for arm_name, figures in summary["attribution_components"].items():
        assert figures["rail_component_reaches_margin"] is (
            abs(figures["rail_component"]) >= figures["rail_component_margin"]
        )
        assert figures["mass_component_reaches_margin"] is (
            abs(figures["mass_component"]) >= figures["mass_component_margin"]
        )
        assert figures["additivity_holds"] is (
            abs(figures["interaction_residual"]) <= figures["additivity_tolerance"]
        )
        assert figures["declared_channel"] == channels[
            (
                figures["rail_component_reaches_margin"],
                figures["mass_component_reaches_margin"],
            )
        ]
    headline = summary["attribution_headline"]
    assert headline["arm"] == survival.ATTRIBUTION_HEADLINE_ARM_NAME
    assert headline == {
        "arm": headline["arm"],
        **summary["attribution_components"][headline["arm"]],
    }
    # the measured verdict on the real numbers: the rail channel stays below its
    # declared margin in both declared arms, the mass channel reaches its own, and
    # the decomposition residual stays inside the declared tolerance
    for figures in summary["attribution_components"].values():
        assert figures["rail_component_reaches_margin"] is False
        assert figures["mass_component_reaches_margin"] is True
        assert figures["additivity_holds"] is True
    assert headline["declared_channel"] == "mass"
    assert abs(headline["mass_component"]) > abs(headline["rail_component"])


def test_attribution_rail_component_margin_can_fire_and_fail(receipts):
    receipt, _ = receipts
    core = copy.deepcopy(body_core(receipt))
    margin = receipt["declared"]["rail_component_margin"]
    arms = core["attribution"]["per_arm"]
    default = survival.DEFAULT_PROFILE_NAME
    assert margin > 0.0
    for arm_name in survival.SCAFFOLD_ARM_NAMES:
        base = arms[default]["arms"][arm_name]["recovery_fraction"]
        target = arms[survival.RAIL_ONLY_PROFILE_NAME]["arms"][arm_name]
        # the margin test is a threshold: just below it must not fire
        target["recovery_fraction"] = base + margin * 0.5
        below = survival.summarize(core)["attribution_components"][arm_name]
        assert below["rail_component_reaches_margin"] is False
        # and just above it must
        target["recovery_fraction"] = base + margin * 2.0
        above = survival.summarize(core)["attribution_components"][arm_name]
        assert above["rail_component_reaches_margin"] is True
        assert above["rail_component"] == pytest.approx(margin * 2.0)
        assert above["declared_channel"] == "rail-and-mass"


def test_attribution_mass_component_margin_can_fail_and_fire(receipts):
    receipt, _ = receipts
    core = copy.deepcopy(body_core(receipt))
    margin = receipt["declared"]["mass_component_margin"]
    arms = core["attribution"]["per_arm"]
    default = survival.DEFAULT_PROFILE_NAME
    assert margin > 0.0
    for arm_name in survival.SCAFFOLD_ARM_NAMES:
        base = arms[default]["arms"][arm_name]["recovery_fraction"]
        target = arms[survival.MASS_ONLY_PROFILE_NAME]["arms"][arm_name]
        # erase the mass channel: with the rail channel already below its own
        # margin on the real numbers, neither channel may then be declared
        target["recovery_fraction"] = base
        erased = survival.summarize(core)["attribution_components"][arm_name]
        assert erased["mass_component_reaches_margin"] is False
        assert erased["declared_channel"] == "neither"
        assert erased["compound_gain"] != pytest.approx(0.0)
        # a mass component just above the margin must fire again
        target["recovery_fraction"] = base + margin * 2.0
        fired = survival.summarize(core)["attribution_components"][arm_name]
        assert fired["mass_component_reaches_margin"] is True
        assert fired["declared_channel"] == "mass"


def test_attribution_additivity_tolerance_is_two_sided_and_can_fail(receipts):
    receipt, _ = receipts
    core = copy.deepcopy(body_core(receipt))
    tolerance = receipt["declared"]["attribution_additivity_tolerance"]
    assert tolerance > 0.0
    arms = core["attribution"]["per_arm"]
    default = survival.DEFAULT_PROFILE_NAME
    arm_name = survival.ATTRIBUTION_HEADLINE_ARM_NAME
    base = arms[default]["arms"][arm_name]["recovery_fraction"]
    rail_gain = (
        arms[survival.RAIL_ONLY_PROFILE_NAME]["arms"][arm_name]["recovery_fraction"] - base
    )
    mass_gain = (
        arms[survival.MASS_ONLY_PROFILE_NAME]["arms"][arm_name]["recovery_fraction"] - base
    )
    target = arms[survival.COMPOUND_PROFILE_NAME]["arms"][arm_name]
    # setting the compound gain to the sum of the components must hold exactly
    target["recovery_fraction"] = base + rail_gain + mass_gain
    exact = survival.summarize(core)["attribution_components"][arm_name]
    assert exact["interaction_residual"] == pytest.approx(0.0, abs=1e-12)
    assert exact["additivity_holds"] is True
    # inner edge of the declared tolerance, both signs, still holds
    for sign in (1.0, -1.0):
        target["recovery_fraction"] = (
            base + rail_gain + mass_gain + sign * tolerance * 0.5
        )
        inner = survival.summarize(core)["attribution_components"][arm_name]
        assert inner["interaction_residual"] == pytest.approx(sign * tolerance * 0.5)
        assert inner["additivity_holds"] is True
        # outer edge, both signs, must fail
        target["recovery_fraction"] = (
            base + rail_gain + mass_gain + sign * tolerance * 2.0
        )
        outer = survival.summarize(core)["attribution_components"][arm_name]
        assert outer["additivity_holds"] is False


def test_attribution_spacing_separates_on_the_rail_channel_not_the_mass_channel(receipts):
    receipt, _ = receipts
    summary = receipt["summary"]
    confusion_margin = receipt["declared"]["spacing_confusion_margin"]
    recovery_margin = receipt["declared"]["spacing_recovery_margin"]
    assert sorted(summary["attribution_spacing_separation_per_profile"]) == sorted(
        survival.SPACING_ATTRIBUTION_PROFILE_NAMES
    )
    for profile_name, figures in summary[
        "attribution_spacing_separation_per_profile"
    ].items():
        assert figures["confusion_separates"] is (
            figures["confusion_difference"] >= confusion_margin
        )
        assert figures["recovery_separates"] is (
            figures["recovery_difference"] >= recovery_margin
        )
        assert figures["separates"] is (
            figures["confusion_separates"] and figures["recovery_separates"]
        )
        # the figures are this arm's own measured pair records, not restated
        records = receipt["attribution"]["spacing"]["per_profile"][profile_name]["pairs"]
        assert sorted(records) == sorted(
            name for name, _ in survival.PAIR_DECLARATIONS
        )
        near = records[survival.NEAR_PAIR_NAME]
        far = records[survival.FAR_PAIR_NAME]
        assert figures["near_max_off_diagonal_deposit_share"] == near[
            "max_off_diagonal_deposit_share"
        ]
        assert figures["far_max_off_diagonal_deposit_share"] == far[
            "max_off_diagonal_deposit_share"
        ]
        assert figures["near_recovery_fraction"] == near["recovery_fraction"]
        assert figures["recovery_difference"] == pytest.approx(
            far["recovery_fraction"] - near["recovery_fraction"]
        )
    # measured: the separation survives the rail change alone and does not survive
    # the mass change alone, so it is the rail channel that carries it
    assert summary["spacing_separates_per_profile"][survival.DEFAULT_PROFILE_NAME] is True
    assert (
        summary["attribution_spacing_separates_per_profile"][
            survival.RAIL_ONLY_PROFILE_NAME
        ]
        is True
    )
    assert (
        summary["attribution_spacing_separates_per_profile"][
            survival.MASS_ONLY_PROFILE_NAME
        ]
        is False
    )
    # the verdict is derived: erasing this arm's own pair contrast removes it
    core = copy.deepcopy(body_core(receipt))
    pairs = core["attribution"]["spacing"]["per_profile"][
        survival.RAIL_ONLY_PROFILE_NAME
    ]["pairs"]
    pairs[survival.FAR_PAIR_NAME]["max_off_diagonal_deposit_share"] = pairs[
        survival.NEAR_PAIR_NAME
    ]["max_off_diagonal_deposit_share"]
    pairs[survival.FAR_PAIR_NAME]["recovery_fraction"] = pairs[
        survival.NEAR_PAIR_NAME
    ]["recovery_fraction"]
    mutated = survival.summarize(core)["attribution_spacing_separation_per_profile"][
        survival.RAIL_ONLY_PROFILE_NAME
    ]
    assert mutated["confusion_separates"] is False
    assert mutated["recovery_separates"] is False
    assert mutated["separates"] is False


# --------------------------------------------------------------------------
# measured structure
# --------------------------------------------------------------------------
def test_cross_item_confusion_covers_the_declared_frame(receipts):
    receipt, _ = receipts
    declared_names = [row["name"] for row in receipt["declared"]["item_declarations"]]
    for profile_name in survival.PROFILE_NAMES:
        for pair_name, record in receipt["spacing"]["per_profile"][profile_name][
            "pairs"
        ].items():
            written = record["written_items"]
            assert sorted(written) == sorted(
                record["declared_written_items"]
            )
            matrix = record["cross_item_confusion"]
            assert sorted(matrix) == sorted(written)
            for written_item, row in matrix.items():
                assert sorted(row) == sorted(declared_names)
                # the diagonal of a row is that item's own recovery fraction
                assert row[written_item] == pytest.approx(
                    record["per_item_recovery_fraction"][written_item]
                )
            off_diagonal = [
                value
                for written_item, row in matrix.items()
                for read_item, value in row.items()
                if read_item != written_item
            ]
            assert record["max_off_diagonal_deposit_share"] == pytest.approx(
                max(off_diagonal)
            )
            assert record["off_diagonal_deposit_share_sum"] == pytest.approx(
                sum(off_diagonal)
            )
            fractions = record["declared_frame_energy_fraction"]
            assert sorted(fractions) == sorted(declared_names)
            assert sum(fractions.values()) == pytest.approx(1.0, rel=1e-9)
            assert record["unwritten_direction_energy_fraction_total"] == pytest.approx(
                sum(
                    value
                    for name, value in fractions.items()
                    if name not in written
                )
            )


def test_pair_arms_report_the_declared_restart_identity(receipts):
    receipt, _ = receipts
    for profile_name in survival.PROFILE_NAMES:
        for pair_name, record in receipt["spacing"]["per_profile"][profile_name][
            "pairs"
        ].items():
            assert record["restart_applied"] is True, (profile_name, pair_name)
            assert record["restart_state_digest_identical"] is True
            assert record["restart_page_digest_identical"] is True
            for item, share in record["write_time_alignment"].items():
                assert share == pytest.approx(1.0), (profile_name, pair_name, item)


def test_control_margin_is_the_durability_harness_declaration(receipts):
    receipt, _ = receipts
    assert receipt["declared"]["control_margin"] == durability.DurabilityConfig().control_margin
    arm = receipt["scaffold"]["per_profile"][survival.DEFAULT_PROFILE_NAME][
        "restart-and-activity"
    ]
    assert arm["distinguishable_from_control"] is (
        arm["recovery_fraction"] - arm["control_share"] >= arm["control_margin"]
    )


def test_scaffold_arms_are_the_durability_harness_declarations(receipts):
    receipt, _ = receipts
    declared = {arm.name: arm for arm in durability.arm_declarations(durability.DurabilityConfig())}
    for arm_name in survival.SCAFFOLD_ARM_NAMES:
        assert arm_name in declared
    for profile_name in survival.PROFILE_NAMES:
        rows = receipt["scaffold"]["per_profile"][profile_name]
        for arm_name in survival.SCAFFOLD_ARM_NAMES:
            record = rows[arm_name]
            assert record["declared_written_items"] == [
                durability.ITEM_SPECS[index].name
                for index in declared[arm_name].item_indices
            ]
            assert record["activity_ticks"] == durability.DurabilityConfig().activity_ticks
            assert record["restart_state_digest_identical"] is True
        assert rows[survival.BACKGROUND_ARM_NAME]["written_items"] == []


# --------------------------------------------------------------------------
# determinism and digest
# --------------------------------------------------------------------------
def test_every_reported_figure_is_reproducible(receipts):
    first, second = receipts
    assert without_timing(first) == without_timing(second)
    assert json.dumps(without_timing(first), sort_keys=True) == json.dumps(
        without_timing(second), sort_keys=True
    )


def test_content_digest_is_reproducible_and_covers_the_body(receipts):
    first, second = receipts
    assert first["content_digest"] == second["content_digest"]
    core = body_core(first)
    body = {**core, "summary": first["summary"], "boundary": first["boundary"]}
    assert survival.digest_body(body) == first["content_digest"]


def test_content_digest_fires_under_mutation(receipts):
    first, _ = receipts
    core = copy.deepcopy(body_core(first))
    baseline = survival.digest_body(
        {**core, "summary": first["summary"], "boundary": first["boundary"]}
    )
    assert baseline == first["content_digest"]
    core["scaffold"]["per_profile"][survival.DEFAULT_PROFILE_NAME][
        "restart-and-activity"
    ]["recovery_fraction"] += 1e-6
    mutated = survival.digest_body(
        {**core, "summary": first["summary"], "boundary": first["boundary"]}
    )
    assert mutated != baseline
    # a mutation that only moves the derived summary must also move the digest
    core_again = copy.deepcopy(body_core(first))
    body = {**core_again, "summary": first["summary"], "boundary": first["boundary"]}
    body["summary"] = copy.deepcopy(first["summary"])
    body["summary"]["spacing_headline"]["separates"] = not body["summary"][
        "spacing_headline"
    ]["separates"]
    assert survival.digest_body(body) != baseline
    # and a mutation inside the attribution block must move it too
    core_attribution = copy.deepcopy(body_core(first))
    core_attribution["attribution"]["per_arm"][
        survival.MASS_ONLY_PROFILE_NAME
    ]["arms"][survival.ATTRIBUTION_HEADLINE_ARM_NAME]["recovery_fraction"] += 1e-6
    mutated_attribution = survival.digest_body(
        {**core_attribution, "summary": first["summary"], "boundary": first["boundary"]}
    )
    assert mutated_attribution != baseline
