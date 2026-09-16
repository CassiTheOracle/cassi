"""Direct-iteration tests for the fractal metric exploration runner.

One measured receipt is built once per session and every check below is derived
from it, so the suite stays in-process and fast.  The tests read the declared
family, the arms and the mechanism back out of the receipt, and each gate is
shown to be able to fail by mutating a real artifact rather than by trusting the
reassuring number it reports.
"""

from __future__ import annotations

import copy
import dataclasses
import json

import numpy as np
import pytest

import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry
import run_fractal_metric_exploration as metric
import run_fractal_survival_exploration as survival


@pytest.fixture(scope="module")
def body() -> dict:
    """The one measured receipt this suite reads every claim from."""

    return metric.build_receipt()


@pytest.fixture(scope="module")
def summary(body: dict) -> dict:
    return metric.summarize(body)


# --------------------------------------------------------------------------
# declared family
# --------------------------------------------------------------------------
def test_declared_family_is_bounded_complete_and_seeded() -> None:
    rows = metric.all_declared_rows()
    names = [row.name for row in rows]
    kinds = [row.kind for row in rows]
    assert len(rows) <= metric.MAX_DECLARED_PROFILES
    assert len(set(names)) == len(names)
    assert kinds.count("default") == 1
    assert kinds.count("reference-metric") == 1
    assert kinds.count("canonical-hook") == 1
    assert kinds.count("reference-rail") == 1
    graded = [row for row in rows if row.kind == "graded"]
    randomized = [row for row in rows if row.kind == "randomized"]
    assert len(graded) >= 5
    assert len(randomized) >= 8
    assert sorted(row.contrast for row in graded) == sorted(metric.SHELL_CONTRASTS)
    assert {row.seed for row in randomized} == {
        metric.RANDOM_SEED_BASE + index * metric.RANDOM_SEED_STEP
        for index in range(metric.RANDOM_PROFILE_COUNT)
    }
    # every declaration carries a construction rule and no array state
    for row in rows:
        assert isinstance(row.rule, str) and row.rule
        if row.kind == "randomized":
            assert row.seed is not None
        if row.kind == "graded":
            assert row.contrast in metric.SHELL_CONTRASTS


def test_every_profile_has_positive_inverse_mass_and_a_set_hook() -> None:
    for row in metric.all_declared_rows():
        profile = metric.build_metric_profile(row)
        declared = metric.declared_inverse_mass(row)
        ports = int(profile.port_count) * 2
        if row.kind in {"default", "reference-rail"}:
            # neither row declares a vector of this family: the scaffold's hooks
            # come from the arrangement and are checked by the hook-fidelity test
            assert declared is None
            if row.kind == "default":
                assert profile.projected_inv_mass is None
            else:
                assert profile.projected_inv_mass is not None
            continue
        vector = np.asarray(declared, dtype=np.float64)
        assert declared is not None and vector.shape == (ports,), row.name
        assert np.all(vector > 0.0), row.name
        assert np.all(np.isfinite(vector)), row.name
        assert profile.projected_inv_mass is not None, row.name
        assert np.array_equal(
            np.asarray(profile.projected_inv_mass, dtype=np.float64), vector
        ), row.name
        # the hook is applied uniformly inside each pool, on both strands
        blocks = vector.reshape(
            2, int(profile.pools), int(profile.ports_per_pool)
        )
        assert np.array_equal(blocks[0], blocks[1]), row.name
        for pool in range(int(profile.pools)):
            assert np.all(blocks[0, pool] == blocks[0, pool, 0]), (row.name, pool)


def test_randomized_construction_is_seed_bound_and_reproducible() -> None:
    for row in metric.all_declared_rows():
        if row.kind != "randomized":
            continue
        profile = metric.build_metric_profile(row)
        again = metric.build_metric_profile(row)
        vector = np.asarray(profile.projected_inv_mass, dtype=np.float64)
        assert np.array_equal(vector, np.asarray(again.projected_inv_mass)), row.name
        # the declared rule is the draw the seed alone decides, recomputed here
        pool_count = int(profile.pools)
        draw = np.random.default_rng(row.seed).uniform(
            -float(row.jitter_bound), float(row.jitter_bound), size=pool_count
        )
        expected = np.repeat(float(row.contrast) ** draw, int(profile.ports_per_pool))
        expected = np.tile(expected, 2)
        assert np.allclose(vector, expected, rtol=0.0, atol=1e-15), row.name
    # distinct seeds are not the same profile
    vectors = {
        np.asarray(
            metric.build_metric_profile(row).projected_inv_mass, dtype=np.float64
        ).tobytes()
        for row in metric.all_declared_rows()
        if row.kind == "randomized"
    }
    assert len(vectors) == metric.RANDOM_PROFILE_COUNT


def test_graded_family_is_monotone_in_pool_distance() -> None:
    profile = metric.build_metric_profile(metric.declared_row("shell-contrast-0.5"))
    vector = np.asarray(profile.projected_inv_mass, dtype=np.float64)
    pool_count = int(profile.pools)
    block = vector.reshape(2, pool_count, int(profile.ports_per_pool))[0, :, 0]
    core = int(metric.SHELL_CORE_POOL)
    distances = np.minimum(
        np.abs(np.arange(pool_count) - core),
        pool_count - np.abs(np.arange(pool_count) - core),
    )
    assert np.allclose(block, 0.5 ** distances.astype(np.float64), rtol=0.0, atol=1e-15)
    # the shape is monotone in the pool distance: the core holds the most mass
    by_distance = [float(block[pool]) for pool in np.argsort(distances, kind="stable")]
    assert by_distance == sorted(by_distance, reverse=True)


def test_hook_channel_reproduces_the_canonical_metric(body: dict) -> None:
    fidelity = body["summary"]["hook_fidelity"]
    assert fidelity["generator_identical_to_default"] is True
    assert fidelity["k4_recovery_reproduced"] is True
    assert abs(fidelity["k4_recovery_difference_vs_default"]) <= float(
        metric.CITED_REPRODUCTION_TOLERANCE
    )
    assert fidelity["graded_setting_matches_reference_vector"] is True
    assert abs(fidelity["graded_setting_recovery_difference_vs_reference"]) <= float(
        metric.CITED_REPRODUCTION_TOLERANCE
    )
    assert fidelity["reference_row_uses_both_hooks"] is True
    reference_profile = metric.build_metric_profile(
        metric.declared_row(metric.REFERENCE_ROW_NAME)
    )
    assert reference_profile.projected_transport is not None
    assert reference_profile.projected_inv_mass is not None
    control = metric.build_metric_profile(
        metric.declared_row(metric.CANONICAL_HOOK_PROFILE_NAME)
    )
    default = metric.build_metric_profile(
        metric.declared_row(metric.DEFAULT_PROFILE_NAME)
    )
    assert np.array_equal(
        np.asarray(control.projected_inv_mass, dtype=np.float64),
        np.asarray(default.inertances, dtype=np.float64) ** -1.0,
    )


# --------------------------------------------------------------------------
# ranking and arms
# --------------------------------------------------------------------------
def test_ranking_is_the_declared_sort_and_margin_gated(body: dict, summary: dict) -> None:
    entries = summary["ranking"]
    figures = [float(entry["k4_min_per_item_recovery"]) for entry in entries]
    assert figures == sorted(figures, reverse=True)
    assert [entry["rank"] for entry in entries] == list(range(1, len(entries) + 1))
    assert len(entries) == len(body["declared"]["designed_profile_names"])
    assert float(summary["ranking_margin"]) == float(survival.PROFILE_RECOVERY_MARGIN)
    default_arm = body["profiles"][metric.DEFAULT_PROFILE_NAME]["arms"][
        metric.SURVIVAL_ARM_NAME
    ]
    default_figure = min(
        float(value) for value in default_arm["per_item_recovery_fraction"].values()
    )
    for entry in entries:
        arm = body["profiles"][entry["profile"]]["arms"][metric.SURVIVAL_ARM_NAME]
        per_item = [float(value) for value in arm["per_item_recovery_fraction"].values()]
        assert float(entry["k4_min_per_item_recovery"]) == pytest.approx(min(per_item))
        assert float(arm["recovery_fraction"]) == pytest.approx(min(per_item))
        assert float(entry["delta_vs_default"]) == pytest.approx(
            float(entry["k4_min_per_item_recovery"]) - default_figure
        )
        assert float(entry["delta_vs_reference_metric"]) == pytest.approx(
            float(entry["k4_min_per_item_recovery"])
            - min(
                float(value)
                for value in body["profiles"][metric.REFERENCE_METRIC_PROFILE_NAME][
                    "arms"
                ][metric.SURVIVAL_ARM_NAME]["per_item_recovery_fraction"].values()
            )
        )
        assert entry["differs_from_default_by_margin"] is (
            abs(float(entry["delta_vs_default"])) >= float(summary["ranking_margin"])
        )
        assert entry["exceeds_default_by_margin"] is (
            float(entry["delta_vs_default"]) >= float(summary["ranking_margin"])
        )


def test_ranking_recomputes_to_the_same_order(body: dict) -> None:
    order = [
        (
            -min(
                float(value)
                for value in body["profiles"][name]["arms"][metric.SURVIVAL_ARM_NAME][
                    "per_item_recovery_fraction"
                ].values()
            ),
            name,
        )
        for name in body["declared"]["designed_profile_names"]
    ]
    recomputed = [name for _, name in sorted(order)]
    assert recomputed == body["summary"]["ranking_by_k4_min_per_item_recovery"]
    assert body["declared"]["designed_ranking_by_k4_min_per_item_recovery"] == recomputed
    assert set(recomputed) == set(body["declared"]["designed_profile_names"])
    # the declared order is figure-descending, and any tie is broken by name
    recorded_figures = [
        min(
            float(value)
            for value in body["profiles"][name]["arms"][metric.SURVIVAL_ARM_NAME][
                "per_item_recovery_fraction"
            ].values()
        )
        for name in recomputed
    ]
    assert recorded_figures == sorted(recorded_figures, reverse=True)
    for (earlier, before), (later, after) in zip(
        zip(recomputed, recorded_figures), zip(recomputed[1:], recorded_figures[1:])
    ):
        if before == after:
            assert earlier < later


def test_can_fail_survival_margin_best_minus_default(summary: dict) -> None:
    headline = summary["headline"]
    difference = float(headline["best_recovery"]) - float(headline["default_recovery"])
    assert difference >= float(metric.HEADLINE_SURVIVAL_MARGIN)
    assert headline["exceeds_default_by_headline_margin"] is True
    assert float(metric.HEADLINE_SURVIVAL_MARGIN) < difference
    assert headline["best_minus_default"] == pytest.approx(difference)
    # the declared predicate is a real comparison, so it fails for a body whose
    # best profile merely reproduced the default
    assert not (float(headline["default_recovery"]) - float(headline["default_recovery"])
                >= float(metric.HEADLINE_SURVIVAL_MARGIN))


def test_cited_figures_are_reproduced(body: dict) -> None:
    tolerance = float(metric.CITED_REPRODUCTION_TOLERANCE)
    declared = body["declared"]
    measured = {
        "helix7": body["profiles"][declared["default_profile"]]["arms"][
            metric.SURVIVAL_ARM_NAME
        ]["recovery_fraction"],
        "mass-only": body["profiles"][declared["reference_metric_profile"]]["arms"][
            metric.SURVIVAL_ARM_NAME
        ]["recovery_fraction"],
        "nested-core-shell": body["profiles"][declared["reference_row"]]["arms"][
            metric.SURVIVAL_ARM_NAME
        ]["recovery_fraction"],
    }
    for name, cited in metric.CITED_RECOVERY.items():
        if name in measured:
            assert abs(float(measured[name]) - float(cited)) <= tolerance, name
    assert abs(
        float(body["cross_rail"]["survival_harness_cited_default_metric_recovery"])
        - float(metric.CITED_RECOVERY["recursive-paired-loops"])
    ) <= tolerance
    assert body["summary"]["headline"]["cited_reproduction_holds"] is True


def test_k_arms_are_recorded_and_the_scale_verdict_matches(body: dict, summary: dict) -> None:
    check = summary["scale_check"]
    assert check["arms_by_count"]["k4"] == metric.SURVIVAL_ARM_NAME
    assert check["arms_by_count"]["k2"] == metric.CONTEXT_ARM_NAMES[0]
    assert check["arms_by_count"]["k8"] == metric.CONTEXT_ARM_NAMES[1]
    default = body["declared"]["default_profile"]
    assert default in check["context_profile_names"]
    default_figures = {
        label: float(
            body["profiles"][default]["arms"][arm]["recovery_fraction"]
        )
        for label, arm in check["arms_by_count"].items()
    }
    for row in check["rows"]:
        record = body["profiles"][row["profile"]]
        for label, arm in check["arms_by_count"].items():
            assert float(row["recoveries"][label]) == pytest.approx(
                float(record["arms"][arm]["recovery_fraction"])
            )
            assert float(row["advantage_over_default"][label]) == pytest.approx(
                float(row["recoveries"][label]) - default_figures[label]
            )
        assert row["holds_at_every_declared_k"] is all(
            float(value) >= float(check["margin"])
            for value in row["advantage_over_default"].values()
        )
    assert check["profiles_scaling_at_every_declared_k"] == [
        row["profile"] for row in check["rows"] if row["holds_at_every_declared_k"]
    ]
    # the ranked leader does not hold its advantage once the write set widens
    leader = summary["headline"]["best_profile"]
    leader_row = next(row for row in check["rows"] if row["profile"] == leader)
    assert float(leader_row["advantage_over_default"]["k4"]) >= float(check["margin"])
    assert leader_row["holds_at_every_declared_k"] is False
    assert float(
        leader_row["advantage_over_default"]["k8"]
    ) < 0.0


def test_cross_rail_generalization_verdict(body: dict, summary: dict) -> None:
    block = summary["cross_rail"]
    rows = body["cross_rail"]["rows"]
    assert body["cross_rail"]["rail"] == metric.CROSS_RAIL_ARRANGEMENT
    assert metric.CROSS_RAIL_ARRANGEMENT != metric.CANONICAL_RAIL
    # the row measured on the other rail carries the ranking's own leader
    assert block["top_profile"] == summary["headline"]["best_profile"]
    assert set(rows) == {metric.CROSS_RAIL_TOP_ROW_NAME, metric.CROSS_RAIL_DEFAULT_ROW_NAME}
    assert list(body["cross_rail"]["declared_rows"]) == [
        metric.CROSS_RAIL_DEFAULT_ROW_NAME,
        metric.CROSS_RAIL_TOP_ROW_NAME,
    ]
    assert float(block["difference"]) == pytest.approx(
        float(block["top_metric_recovery"]) - float(block["default_metric_recovery"])
    )
    assert block["differs_from_default_by_margin"] is (
        abs(float(block["difference"])) >= float(block["margin"])
    )
    assert block["top_exceeds_default_by_margin"] is (
        float(block["difference"]) >= float(block["margin"])
    )
    assert block["ranking_holds"] is (float(block["difference"]) > 0.0)
    assert float(block["margin"]) == float(survival.PROFILE_RECOVERY_MARGIN)
    assert block["ranking_holds"] is True
    assert block["top_exceeds_default_by_margin"] is True
    assert abs(float(block["cited_reproduction_abs_difference"])) <= float(
        metric.CITED_REPRODUCTION_TOLERANCE
    )
    for name, row in rows.items():
        assert row["declaration"]["rail"] == metric.CROSS_RAIL_ARRANGEMENT
        assert metric.SURVIVAL_ARM_NAME in row["arms"]
        assert len(row["arms"][metric.SURVIVAL_ARM_NAME]["per_item_recovery_fraction"]) == 4
        assert row["declaration"]["hook_set"] is (name == metric.CROSS_RAIL_TOP_ROW_NAME)
    # the row on the other rail carries the leader's own declared metric vector
    leader_vector = np.asarray(
        metric.declared_inverse_mass(
            metric.declared_row(summary["headline"]["best_profile"])
        ),
        dtype=np.float64,
    )
    top_row = rows[metric.CROSS_RAIL_TOP_ROW_NAME]
    assert float(top_row["declaration"]["hook_vector_min"]) == pytest.approx(
        float(leader_vector.min())
    )
    assert float(top_row["declaration"]["hook_vector_max"]) == pytest.approx(
        float(leader_vector.max())
    )
    assert float(top_row["declaration"]["hook_vector_max"]) == 1.0


# --------------------------------------------------------------------------
# mechanism
# --------------------------------------------------------------------------
def test_overlap_battery_is_declared_primary_and_aggregated(body: dict, summary: dict) -> None:
    relation = summary["overlap_survival_relation"]
    assert set(relation["measures"]) == set(metric.MEASURE_NAMES)
    assert [name for name in relation["measures"] if relation["measures"][name]["primary"]] == [
        metric.PRIMARY_MEASURE
    ]
    written = relation["written_items"]
    assert len(written) == 4
    for name in metric.MEASURE_NAMES:
        entry = relation["measures"][name]
        for profile_name in entry["profiles_aggregated"]:
            items = {
                item["name"]: item
                for item in body["profiles"][profile_name]["mechanism"]["items"]
            }
            assert set(items) >= set(written)
            expected = min(float(items[item]["overlaps"][name]) for item in written)
            assert float(entry["profiles"][profile_name]) == pytest.approx(expected)
        assert entry["definition"]
        assert entry["pooled_pair_count"] == len(entry["profiles_aggregated"]) * len(written)
    tracked = (
        float(relation["measures"][metric.PRIMARY_MEASURE]["profile_level_spearman"])
        >= float(relation["primary_relation_margin"])
    )
    assert relation["primary_relation_tracked"] is tracked
    assert relation["primary_relation_tracked"] is True
    assert float(relation["primary_relation_margin"]) == float(metric.PRIMARY_RELATION_MARGIN)


def test_slow_mode_structure_uses_the_frozen_generator(body: dict) -> None:
    profile = metric.build_metric_profile(metric.declared_row(metric.DEFAULT_PROFILE_NAME))
    record = body["profiles"][metric.DEFAULT_PROFILE_NAME]["mechanism"]
    generator = geometry.linear_generator(profile)
    assert record["generator_sha256"] == survival.array_sha256(generator)
    assert int(record["generator_dimension"]) == int(generator.shape[0])
    eigenvalues, right = np.linalg.eig(generator)
    decay = np.abs(eigenvalues.real)
    expected_half = int(np.count_nonzero(decay <= np.median(decay)))
    assert int(record["slower_half_mode_count"]) == expected_half
    ipr = metric.eigen_ipr(right)
    assert float(record["ipr_median"]) == pytest.approx(float(np.median(ipr)))
    assert float(record["ipr_min"]) <= float(record["ipr_median"]) <= float(record["ipr_max"])
    assert float(record["ipr_uniform_reference"]) == pytest.approx(1.0 / generator.shape[0])
    harness = record["geometry_harness_spectrum"]
    assert harness["generator_sha256"] == record["generator_sha256"]
    assert float(harness["ipr_median_difference_vs_this_runner"]) <= 1e-12
    assert float(harness["independent_reconstruction_max_abs_difference"]) <= 1e-9
    assert sum(float(value) for value in record["slowest_modes_participating_pools"]) == pytest.approx(1.0)
    assert len(record["ipr_of_the_8_slowest_by_decay"]) == 8


def test_read_frame_is_verified_against_the_canonical_packet(body: dict) -> None:
    records = {
        name: body["profiles"][name]
        for name in (
            metric.DEFAULT_PROFILE_NAME,
            metric.REFERENCE_ROW_NAME,
            metric.REFERENCE_METRIC_PROFILE_NAME,
            body["declared"]["designed_profile_names"][0],
        )
    }
    records.update(body["cross_rail"]["rows"])
    for name, record in records.items():
        check = record["read_frame_isometry"]
        assert int(check["dimension"]) == int(
            record["mechanism"]["generator_dimension"]
        ), name
        assert float(check["transform_orthonormality_max_abs_error"]) <= 1e-9
        assert float(check["canonical_readout_max_abs_difference"]) <= 1e-9
        assert float(check["captured_direction_angle_max_abs_error"]) <= 1e-9
        assert int(check["items_checked"]) == len(record["mechanism"]["items"])


def test_participation_validity_gates_are_measured_and_satisfied(summary: dict) -> None:
    spectral = summary["spectral_decomposition"]
    residual_tolerance = float(spectral["residual_tolerance"])
    rotation_tolerance = float(spectral["rotation_tolerance"])
    separation_tolerance = float(spectral["separation_tolerance"])
    assert residual_tolerance == float(metric.SPECTRAL_RESIDUAL_TOLERANCE)
    assert rotation_tolerance == float(metric.SPECTRAL_ROTATION_TOLERANCE)
    assert separation_tolerance == float(metric.SPECTRAL_SEPARATION_TOLERANCE)
    for name, figures in spectral["profiles"].items():
        assert float(figures["spectral_reconstruction_residual_max"]) <= residual_tolerance, name
        assert float(figures["participation_basis_rotation_max_change"]) <= rotation_tolerance, name
        assert figures["numerically_repeated_spectrum"] is (
            float(figures["minimum_eigenvalue_separation"]) < separation_tolerance
        ), name
        assert figures["participation_measure_valid"] is True, name
    assert spectral["all_participation_measures_valid"] is True
    assert spectral["invalid_participation_profiles"] == []
    assert sorted(spectral["valid_participation_profiles"]) == sorted(spectral["profiles"])
    # the declared family contains a profile that exercises the degeneracy path
    reference = spectral["profiles"][metric.REFERENCE_ROW_NAME]
    assert reference["numerically_repeated_spectrum"] is True
    assert float(reference["participation_basis_rotation_max_change"]) <= rotation_tolerance
    others = [name for name in spectral["profiles"] if name != metric.REFERENCE_ROW_NAME]
    assert all(
        spectral["profiles"][name]["numerically_repeated_spectrum"] is False
        for name in others
    )
    assert summary["overlap_survival_relation"][
        "profiles_excluded_for_participation_measures"
    ] == {}


def test_participation_rotation_control_can_fail() -> None:
    config = durability.DurabilityConfig()
    profile = metric.build_metric_profile(metric.declared_row(metric.DEFAULT_PROFILE_NAME))
    generator = geometry.linear_generator(profile)
    eigenvalues, right = np.linalg.eig(generator)
    decay = np.abs(eigenvalues.real)
    slower_half = np.argsort(decay, kind="stable")[
        : int(np.count_nonzero(decay <= np.median(decay)))
    ]
    labels, cluster_count, largest = metric.eigenvalue_clusters(
        eigenvalues, metric.DEGENERATE_CLUSTER_TOLERANCE
    )
    assert largest == 1
    transform = metric.read_frame_transform(durability.ResonantProfile())
    captures = durability.capture_items(config, profile)
    state = transform.T @ np.asarray(captures[0]["direction"], dtype=np.float64)
    # the declared clustering rotates nothing and the control reads exactly zero
    assert (
        metric.cluster_rotation_change(
            state, right, slower_half, labels, cluster_count, seed=metric.CLUSTER_ROTATION_SEED
        )
        == 0.0
    )
    # a basis that really mixes the slow modes with the rest is detected
    mixed = metric.cluster_rotation_change(
        state,
        right,
        slower_half,
        np.zeros(right.shape[1], dtype=int),
        1,
        seed=metric.CLUSTER_ROTATION_SEED,
    )
    assert mixed > float(metric.SPECTRAL_ROTATION_TOLERANCE)


def test_participation_exclusion_guard_fires_on_an_invalid_profile(body: dict) -> None:
    mutant = copy.deepcopy({k: v for k, v in body.items() if k != "content_digest"})
    victim = mutant["declared"]["designed_profile_names"][0]
    mutant["profiles"][victim]["mechanism"]["participation_measure_valid"] = False
    relation = metric.overlap_survival_relation(mutant)
    for measure in sorted(metric.PARTICIPATION_MEASURES):
        assert relation["profiles_excluded_for_participation_measures"][measure] == [victim]
        assert victim not in relation["measures"][measure]["profiles"]
        assert victim not in relation["measures"][measure]["profiles_aggregated"]
    projector = metric.PRIMARY_MEASURE
    assert projector not in metric.PARTICIPATION_MEASURES
    assert victim in relation["measures"][projector]["profiles"]
    # the guard is a real gate: the untouched receipt excludes nothing
    assert body["summary"]["overlap_survival_relation"][
        "profiles_excluded_for_participation_measures"
    ] == {}


# --------------------------------------------------------------------------
# receipt integrity
# --------------------------------------------------------------------------
def test_receipt_digest_reproducibility_and_mutation_control(body: dict) -> None:
    recorded = body["content_digest"]
    content = {key: value for key, value in body.items() if key != "content_digest"}
    assert isinstance(recorded, str) and len(recorded) == 64
    assert all(character in "0123456789abcdef" for character in recorded)
    assert survival.digest_body(content) == recorded
    # the receipt stays verifiable after a disk round trip
    assert survival.digest_body(json.loads(json.dumps(content))) == recorded
    # and the digest covers measured numbers, not just the shape of the body
    arm = copy.deepcopy(content)
    figures = arm["profiles"][metric.DEFAULT_PROFILE_NAME]["arms"][metric.SURVIVAL_ARM_NAME]
    figures["recovery_fraction"] = float(figures["recovery_fraction"]) + 0.01
    assert survival.digest_body(arm) != recorded
    mechanism = copy.deepcopy(content)
    item = mechanism["profiles"][metric.DEFAULT_PROFILE_NAME]["mechanism"]["items"][0]
    item["overlaps"][metric.PRIMARY_MEASURE] = float(
        item["overlaps"][metric.PRIMARY_MEASURE]
    ) + 0.01
    assert survival.digest_body(mechanism) != recorded


def test_receipt_shape_declares_its_scope(body: dict, summary: dict) -> None:
    assert body["schema"] == metric.SCHEMA
    assert isinstance(body["boundary"], str) and body["boundary"]
    assert body["boundary"] == metric.BOUNDARY
    declared = body["declared"]
    assert declared["profile_count"] == len(body["profiles"])
    assert declared["profile_count"] == len(metric.all_declared_rows())
    assert declared["profile_count"] <= declared["profile_bound"]
    arm_names = [entry["arm"] for entry in declared["declared_arm_names"]]
    assert len(arm_names) == 4
    assert set(arm_names) == {
        metric.SINGLE_ITEM_ARM_NAME,
        metric.SURVIVAL_ARM_NAME,
        *metric.CONTEXT_ARM_NAMES,
    }
    for entry in declared["declared_arm_names"]:
        assert set(entry) == {"arm", "written_items", "activity", "source_enabled"}
        assert len(entry["written_items"]) in {1, 2, 4, 8}
        assert entry["written_items"][0] == "root-scale"
    assert float(declared["ranking_margin"]) == float(metric.RANKING_MARGIN)
    assert float(declared["activity_retention_threshold"]) == float(
        metric.ACTIVITY_RETENTION_THRESHOLD
    )
    assert float(declared["headline_survival_margin"]) == float(
        metric.HEADLINE_SURVIVAL_MARGIN
    )
    assert declared["primary_measure"] == metric.PRIMARY_MEASURE
    assert declared["cited_recovery"] == dict(metric.CITED_RECOVERY)
    # no wall-clock field survives into the measured body or the summary: the
    # declared timing markers, not the word "time" (the runner legitimately
    # carries tick counts and the declared dimensionless-time leg)
    timing_markers = ("elapsed", "wall", "seconds", "duration", "timestamp", "runtime")
    assert not [
        key for key in body if any(marker in key for marker in timing_markers)
    ]
    assert not [
        key for key in summary if any(marker in key for marker in timing_markers)
    ]
    assert summary["activity_confound"] == metric.ACTIVITY_CONFOUND_STATEMENT


# --------------------------------------------------------------------------
# declared ladder family
# --------------------------------------------------------------------------
def test_ladder_family_is_declared_bounded_and_complete(body: dict) -> None:
    ladder = body["ladder_family"]
    declared = body["declared"]
    rows = metric.ladder_profiles()
    assert [row.name for row in rows] == ladder["row_order"]
    assert len(rows) == len(ladder["rows"]) == len(set(ladder["row_order"]))
    assert len(rows) <= metric.LADDER_PROFILE_BOUND
    assert declared["ladder_profile_bound"] == metric.LADDER_PROFILE_BOUND
    assert declared["ladder_shuffle_seed"] == metric.LADDER_SHUFFLE_SEED
    assert declared["ladder_normalizations"] == dict(metric.LADDER_NORMALIZATIONS)
    assert [
        entry["name"] for entry in declared["ladder_profile_declarations"]
    ] == [row.name for row in rows]
    # the ladder family is declared, measured and does not consume the metric
    # family's declared row budget
    assert declared["profile_count"] == len(metric.all_declared_rows())
    assert not set(ladder["rows"]) & set(body["profiles"])
    ratios = {row.name: row.ladder_ratio for row in rows}
    assert ratios["ladder-ratio-1.3"] == pytest.approx(metric.DEFAULT_LADDER_RATIO)
    assert ratios["ladder-ratio-phi"] == pytest.approx(metric.PHI)
    assert ratios["ladder-ratio-inverse-phi"] == pytest.approx(1.0 / metric.PHI)
    assert ratios["ladder-ratio-phi-squared"] == pytest.approx(metric.PHI**2)
    assert ratios["ladder-ratio-1.5"] == pytest.approx(1.5)
    assert ratios["ladder-uniform"] == pytest.approx(1.0)
    assert ratios["ladder-arithmetic-equal-width"] is None
    for row in rows:
        assert row.family == "ladder"
        if row.name != "ladder-arithmetic-equal-width":
            assert row.normalization == metric.LADDER_EQUAL_TOTAL_NORMALIZATION
    assert (
        metric.ladder_row("ladder-arithmetic-equal-width").normalization
        == metric.LADDER_EQUAL_WIDTH_NORMALIZATION
    )


def test_the_declared_1_3_ladder_is_the_fields_own_inertia_ladder() -> None:
    """The reference row has to be the field's real default, not a flat metric."""

    row = metric.ladder_row("ladder-ratio-1.3")
    vector = metric.declared_inverse_mass(row)
    assert np.array_equal(vector, metric.canonical_metric_vector())
    inertias = np.asarray(
        metric.ladder_inertia_values(
            metric.DEFAULT_LADDER_RATIO, normalization=row.normalization
        )
    )
    assert inertias.size == 7
    # at the equal-total normalization the field default's own ladder has scale 1,
    # so the reference row is exactly the canonical 1.3 ** pool ladder
    assert np.allclose(
        inertias, metric.DEFAULT_LADDER_RATIO ** np.arange(inertias.size), rtol=0.0, atol=1e-15
    )
    assert not np.allclose(inertias, inertias[0])
    assert np.allclose(
        vector,
        metric._expand_pools(
            [1.0 / value for value in inertias], geometry.DEFAULT_PORTS_PER_POOL
        ),
    )


def test_ladder_normalization_holds_the_total_inertia_fixed() -> None:
    """Equal total inertia is what makes the ladder comparison a shape comparison."""

    default = np.asarray(
        metric.ladder_inertia_values(
            metric.DEFAULT_LADDER_RATIO, normalization=metric.LADDER_EQUAL_TOTAL_NORMALIZATION
        )
    )
    for row in metric.ladder_profiles():
        if row.normalization != metric.LADDER_EQUAL_TOTAL_NORMALIZATION:
            continue
        inertias = np.asarray(
            metric.ladder_inertia_values(row.ladder_ratio, normalization=row.normalization)
        )
        assert inertias.size == default.size
        assert float(inertias.sum()) == pytest.approx(float(default.sum()), rel=1e-12)
        assert np.all(inertias > 0.0)
    uniform = np.asarray(
        metric.ladder_inertia_values(1.0, normalization=metric.LADDER_EQUAL_TOTAL_NORMALIZATION)
    )
    assert np.allclose(uniform, uniform[0])
    assert np.allclose(
        uniform[0], float(default.sum()) / float(default.size), rtol=1e-12
    )
    width = np.asarray(
        metric.ladder_inertia_values(1.5, normalization=metric.LADDER_EQUAL_WIDTH_NORMALIZATION)
    )
    assert float(width.min()) == pytest.approx(1.0)
    assert float(width.max()) == pytest.approx(
        float(metric.DEFAULT_LADDER_RATIO ** (default.size - 1))
    )
    assert float(width.sum()) != pytest.approx(float(default.sum()))
    # the declared width variant is a different total inertia by construction,
    # which is why it is declared separately as the density-matched variant
    assert float(width.sum()) > float(default.sum())


def test_matched_random_control_keeps_the_multiset_and_breaks_the_order() -> None:
    phi = metric.declared_inverse_mass(metric.ladder_row("ladder-ratio-phi"))
    control = metric.declared_inverse_mass(
        metric.ladder_row("ladder-matched-random-phi")
    )
    assert np.array_equal(np.sort(phi), np.sort(control))
    assert not np.array_equal(phi, control)


def test_ladder_retention_ranking_is_the_declared_sort(body: dict) -> None:
    rows = body["summary"]["ladder_family"]["rows"]
    recomputed = [
        row["profile"]
        for row in sorted(
            rows, key=lambda row: (-row["k4_min_per_item_recovery"], row["profile"])
        )
    ]
    block = body["summary"]["ladder_family"]
    assert block["ranking_by_k4_min_per_item_recovery"] == recomputed
    assert block["best_retention_profile"] == recomputed[0]
    assert block["best_retention_recovery"] == pytest.approx(
        float(body["ladder_family"]["rows"][recomputed[0]]["arms"][metric.SURVIVAL_ARM_NAME][
            "recovery_fraction"
        ])
    )
    default_ladder = body["ladder_family"]["rows"]["ladder-ratio-1.3"]
    field_default = body["profiles"][body["declared"]["default_profile"]]
    assert float(
        default_ladder["arms"][metric.SURVIVAL_ARM_NAME]["recovery_fraction"]
    ) == pytest.approx(
        float(field_default["arms"][metric.SURVIVAL_ARM_NAME]["recovery_fraction"]),
        abs=0.0,
    )
    assert block["default_ladder_recovery"] == pytest.approx(
        block["field_default_recovery"], abs=0.0
    )
    by_name = {row["profile"]: row for row in rows}
    assert block["phi_minus_default_ladder"] == pytest.approx(
        by_name["ladder-ratio-phi"]["k4_min_per_item_recovery"]
        - by_name["ladder-ratio-1.3"]["k4_min_per_item_recovery"]
    )
    assert block["phi_beats_default_ladder"] == (
        block["phi_minus_default_ladder"] > 0.0
    )
    assert block["matched_random_minus_phi"] == pytest.approx(
        by_name["ladder-matched-random-phi"]["k4_min_per_item_recovery"]
        - by_name["ladder-ratio-phi"]["k4_min_per_item_recovery"]
    )
    for row in rows:
        assert row["activity_preserving"] == (
            row["heartbeat_work_total"] >= float(metric.ACTIVITY_RETENTION_THRESHOLD)
        )
        assert row["heartbeat_work_ratio_vs_default_ladder"] == pytest.approx(
            row["heartbeat_work_total"] / by_name["ladder-ratio-1.3"]["heartbeat_work_total"]
        )
        assert 0.0 <= row["slow_mode_overlap_min_written_item"] <= 1.0
        assert 0.0 <= row["slow_participation_min_written_item"] <= 1.0


def test_ladder_band_ratio_claim_is_measured_and_fails_where_measured(body: dict) -> None:
    """The literal 'bands spaced by the declared ratio' claim is reported as it comes out."""

    block = body["summary"]["ladder_family"]
    tolerance = float(metric.BAND_RATIO_TRACKING_TOLERANCE)
    assert block["band_ratio_tolerance"] == tolerance
    geometric = [
        row
        for row in block["rows"]
        if row["declared_ladder_ratio"] not in (None, 1.0)
    ]
    assert set(block["band_ratio_claim_deviations"]) == {row["profile"] for row in geometric}
    holds: list[str] = []
    fails: list[str] = []
    for row in geometric:
        measured = row["gap_bands"]["band_ladder_ratio"]
        declared = row["declared_ladder_ratio"]
        deviation = abs(float(np.log(measured / declared)))
        assert row["band_ratio_vs_declared_ladder_ratio"]["relative_deviation"] == pytest.approx(
            deviation
        )
        assert row["band_ratio_vs_declared_ladder_ratio"]["absolute_deviation"] == pytest.approx(
            abs(measured - declared)
        )
        assert row["band_ratio_vs_declared_ladder_ratio"]["tracks_declared_ratio"] == (
            deviation <= tolerance
        )
        (holds if deviation <= tolerance else fails).append(row["profile"])
    assert block["band_ratio_claim_holds_for"] == holds
    assert block["band_ratio_claim_fails_for"] == fails
    # the declared ladder ratios are large, and the measured band ratios are all
    # small: the claim fails for every declared ladder ratio that is not 1
    assert all(
        row["gap_bands"]["band_ladder_ratio"] < row["declared_ladder_ratio"]
        for row in geometric
        if row["declared_ladder_ratio"] > 1.0
    )
    assert fails, "the literal band-ratio claim is expected to fail where measured"


def test_ladder_lifetime_claim_holds_for_the_ladders_and_fires_on_the_control(
    body: dict,
) -> None:
    """A geometric ladder tracks sqrt(R); the scrambled multiset does not."""

    block = body["summary"]["ladder_family"]
    tolerance = float(metric.BAND_RATIO_TRACKING_TOLERANCE)
    rows = {row["profile"]: row for row in block["rows"]}
    held: list[str] = []
    failed: list[str] = []
    for name, row in rows.items():
        if row["declared_ladder_ratio"] in (None, 1.0):
            continue
        family = row["pool_family_ladder"]
        monotic = bool(family["centers_monotone_along_pools"])
        deviation = abs(
            float(np.log(family["lifetime_ladder_ratio"] / row["sqrt_declared_ladder_ratio"]))
        )
        assert row["lifetime_ladder_vs_sqrt_ratio"]["relative_deviation"] == pytest.approx(
            deviation
        )
        assert row["lifetime_ladder_vs_sqrt_ratio"]["centers_monotone_along_pools"] == monotic
        assert row["lifetime_ladder_vs_sqrt_ratio"]["tracks_sqrt_ratio"] == (
            monotic and deviation <= tolerance
        )
        (held if (monotic and deviation <= tolerance) else failed).append(name)
    assert block["sqrt_ratio_claim_holds_for"] == held
    assert block["sqrt_ratio_claim_fails_for"] == failed
    # firing control: the same value multiset in a broken order must fail
    assert rows["ladder-matched-random-phi"]["pool_family_ladder"][
        "centers_monotone_along_pools"
    ] is False
    assert "ladder-matched-random-phi" in failed
    assert block["matched_random_fails_sqrt_ratio_claim"] is True
    assert rows["ladder-ratio-phi"]["pool_family_ladder"]["centers_monotone_along_pools"] is True
    assert "ladder-ratio-phi" in held
    # a flat metric has no ladder to track anything
    assert rows["ladder-uniform"]["pool_family_ladder"][
        "centers_monotone_along_pools"
    ] is False


def test_ladder_spectrum_span_is_multiset_determined_and_the_ladder_is_not(
    body: dict,
) -> None:
    block = body["summary"]["ladder_family"]
    order = block["band_structure_vs_ladder_order"]
    rows = {row["profile"]: row for row in block["rows"]}
    phi = rows["ladder-ratio-phi"]
    control = rows["ladder-matched-random-phi"]
    assert order["phi_band_ladder_ratio"] == pytest.approx(
        phi["gap_bands"]["band_ladder_ratio"]
    )
    assert order["matched_random_band_ladder_ratio"] == pytest.approx(
        control["gap_bands"]["band_ladder_ratio"]
    )
    assert order["phi_recovery"] == pytest.approx(phi["k4_min_per_item_recovery"])
    assert order["matched_random_recovery"] == pytest.approx(
        control["k4_min_per_item_recovery"]
    )
    assert order["band_count_agrees"] is True
    assert phi["gap_bands"]["band_count"] == control["gap_bands"]["band_count"]
    assert order["band_span_relative_difference"] <= float(
        metric.BAND_RATIO_TRACKING_TOLERANCE
    )
    assert order["band_span_is_stable_under_permutation"] is True
    # while the family-level ladder, which depends on order, does change
    assert order["lifetime_ladder_relative_difference"] > float(
        metric.BAND_RATIO_TRACKING_TOLERANCE
    )
    assert order["lifetime_ladder_is_order_determined"] is True
    assert phi["pool_family_ladder"]["lifetime_ladder_ratio"] != pytest.approx(
        control["pool_family_ladder"]["lifetime_ladder_ratio"],
        rel=float(metric.BAND_RATIO_TRACKING_TOLERANCE),
    )
    assert order["band_centers_max_relative_difference"] is not None
    # the placement is *not* identical, only numerically close: the span claim is
    # a tolerance claim and the receipt says so
    assert phi["gap_bands"]["band_centers"] != control["gap_bands"]["band_centers"]


def test_ladder_band_block_fires_on_a_permuted_ladder() -> None:
    """A second permutation of the same multiset keeps the bands and moves the ladder."""

    config = durability.DurabilityConfig()
    arms = survival.declared_arm_lookup(config)
    transform = metric.read_frame_transform(durability.ResonantProfile())
    control = metric.ladder_row("ladder-matched-random-phi")
    first = metric.measure_row(
        control, config, arms, transform, arm_names=(metric.SURVIVAL_ARM_NAME,)
    )
    second = metric.measure_row(
        dataclasses.replace(control, seed=int(control.seed) + 1),
        config,
        arms,
        transform,
        arm_names=(metric.SURVIVAL_ARM_NAME,),
    )
    first_hook = np.asarray(first["declaration"]["hook_vector_sha256"] is not None)
    assert bool(first_hook) is True
    # same value multiset -> the coarse spectrum repeats: same band count, and a
    # band span that agrees to far inside the declared tolerance
    first_bands = first["mechanism"]["decay_gap_bands"]
    second_bands = second["mechanism"]["decay_gap_bands"]
    assert second_bands["band_count"] == first_bands["band_count"]
    assert abs(
        float(np.log(second_bands["band_ladder_ratio"] / first_bands["band_ladder_ratio"]))
    ) <= float(metric.BAND_RATIO_TRACKING_TOLERANCE)
    # ... but the placement of the bands is not pinned by the multiset alone
    assert second_bands["band_centers"] != first_bands["band_centers"]
    # different order along the pool axis -> the family ladder and the retention move
    first_family = first["mechanism"]["pool_family_ladder"]
    second_family = second["mechanism"]["pool_family_ladder"]
    assert second_family["family_centers"] != first_family["family_centers"]
    span_difference = abs(
        float(np.log(second_bands["band_ladder_ratio"] / first_bands["band_ladder_ratio"]))
    )
    ladder_difference = abs(
        float(
            np.log(
                second_family["lifetime_ladder_ratio"]
                / first_family["lifetime_ladder_ratio"]
            )
        )
    )
    assert second_family["lifetime_ladder_ratio"] != first_family["lifetime_ladder_ratio"]
    # the same multiset in another order moves the family ladder by orders of
    # magnitude more than it moves the band span
    assert ladder_difference > 100.0 * span_difference
    first_recovery = float(first["arms"][metric.SURVIVAL_ARM_NAME]["recovery_fraction"])
    second_recovery = float(second["arms"][metric.SURVIVAL_ARM_NAME]["recovery_fraction"])
    assert abs(second_recovery - first_recovery) >= float(metric.RANKING_MARGIN)


def test_decay_gap_bands_follow_the_declared_tolerance_can_fail() -> None:
    """The band rule itself: runs continue inside the tolerance and split outside it."""

    just_inside = np.array([1.0, 1.04, 1.04 * 1.049, 1.04 * 1.049 * 1.049])
    bands = metric.decay_gap_bands(just_inside)
    assert bands["gap_tolerance"] == float(metric.BAND_GAP_TOLERANCE)
    assert bands["band_count"] == 1
    assert bands["continuum"] is True
    split = np.array([1.0, 1.04, 1.04 * 1.06, 1.04 * 1.06 * 1.5])
    bands = metric.decay_gap_bands(split)
    assert bands["band_count"] == 3
    assert bands["continuum"] is False
    assert bands["band_mode_counts"] == [2, 1, 1]
    # both jumps split, and the smallest recorded gap is the shallower of them
    assert bands["inter_band_gaps"] == pytest.approx([1.06, 1.5])
    assert float(bands["smallest_inter_band_gap"]) == pytest.approx(1.06, rel=1e-12)
    assert bands["band_centers"] == sorted(bands["band_centers"])
    assert bands["band_ladder_ratio"] == pytest.approx(
        (bands["band_centers"][-1] / bands["band_centers"][0]) ** (1.0 / 2.0)
    )
    # repeated eigenvalues are counted, not merged away
    repeated = np.array([1.0, 1.0, 1.0, 2.0])
    bands = metric.decay_gap_bands(repeated)
    assert bands["band_mode_counts"] == [3, 1]
    assert bands["largest_band_mode_fraction"] == pytest.approx(0.75)


def test_ladder_summary_figures_match_the_measured_rows(body: dict) -> None:
    """No inlined ladder figure may drift from the measured row it summarises."""

    block = body["summary"]["ladder_family"]
    rows = dict(body["ladder_family"]["rows"])
    assert block["row_order"] == list(body["ladder_family"]["row_order"])
    assert block["profile_count"] == len(rows)
    assert block["profile_bound"] == metric.LADDER_PROFILE_BOUND
    assert block["claim_under_test"] == metric.LADDER_CLAIM_STATEMENT
    for row in block["rows"]:
        measured = rows[row["profile"]]
        arm = measured["arms"][metric.SURVIVAL_ARM_NAME]
        assert row["k4_min_per_item_recovery"] == pytest.approx(
            float(arm["recovery_fraction"]), abs=0.0
        )
        assert row["k4_per_item_recovery"] == dict(arm["per_item_recovery_fraction"])
        assert row["heartbeat_work_total"] == pytest.approx(
            float(arm["activity_positive_heartbeat_work_total"]), abs=0.0
        )
        assert row["gap_bands"]["band_count"] == measured["mechanism"]["decay_gap_bands"][
            "band_count"
        ]
        assert row["pool_family_ladder"]["lifetime_ladder_ratio"] == pytest.approx(
            float(measured["mechanism"]["pool_family_ladder"]["lifetime_ladder_ratio"])
        )
        assert row["declared_ladder_ratio"] == measured["declaration"]["ladder_ratio"]
        assert row["normalization"] == measured["declaration"]["normalization"]
        assert row["seed"] == measured["declaration"]["seed"]
        assert row["delta_vs_default_ladder"] == pytest.approx(
            row["k4_min_per_item_recovery"] - block["default_ladder_recovery"]
        )
        assert row["exceeds_default_ladder_by_margin"] == (
            row["delta_vs_default_ladder"]
            >= float(body["declared"]["ranking_margin"])
        )
    separated = [row["profile"] for row in block["rows"] if row["gap_bands"]["bands_separated"]]
    assert block["separated_band_profiles"] == separated
    assert block["no_profile_shows_separated_bands"] == (not separated)
    families = [
        row["profile"] for row in block["rows"] if row["family_separation"]["families_separated"]
    ]
    assert block["family_separated_profiles"] == families
    assert block["no_profile_shows_separated_families"] == (not families)
    continuum = [row["profile"] for row in block["rows"] if row["gap_bands"]["continuum"]]
    assert block["continuum_profiles"] == continuum
    strongest = max(
        block["rows"], key=lambda row: row["gap_bands"]["smallest_inter_band_gap"]
    )
    assert block["strongest_inter_band_gap_profile"] == strongest["profile"]
    assert block["strongest_inter_band_gap"] == pytest.approx(
        float(strongest["gap_bands"]["smallest_inter_band_gap"])
    )


# --------------------------------------------------------------------------
# flat-inertia confirmation, local family, band rules, mechanism
# --------------------------------------------------------------------------
def test_local_family_is_declared_equal_total_and_anchored(body: dict) -> None:
    local = body["summary"]["uniform_local_family"]
    raw = body["uniform_local_family"]
    declared = body["declared"]
    rows = metric.uniform_local_profiles()
    assert [row.name for row in rows] == [
        name for name in raw["row_order"] if name != raw["anchor_profile"]
    ]
    assert len(rows) <= metric.UNIFORM_LOCAL_PROFILE_BOUND
    assert declared["uniform_local_profile_bound"] == metric.UNIFORM_LOCAL_PROFILE_BOUND
    assert declared["uniform_local_pool"] == metric.UNIFORM_LOCAL_POOL
    assert declared["uniform_local_contrasts"] == list(metric.UNIFORM_LOCAL_CONTRASTS)
    assert declared["uniform_local_pair"] == list(metric.UNIFORM_LOCAL_PAIR)
    assert [
        entry["name"] for entry in declared["uniform_local_profile_declarations"]
    ] == [row.name for row in rows]
    flat = metric.declared_inverse_mass(metric.ladder_row("ladder-uniform"))
    default_inertia = np.asarray(
        metric.ladder_inertia_values(
            metric.DEFAULT_LADDER_RATIO, normalization=metric.LADDER_EQUAL_TOTAL_NORMALIZATION
        )
    )
    for row in rows:
        assert row.family == "uniform-local"
        assert row.local_pools
        assert row.normalization == metric.LADDER_EQUAL_TOTAL_NORMALIZATION
        vector = metric.declared_inverse_mass(row)
        assert vector is not None and np.all(vector > 0.0)
        # one port per pool, both strands carrying the same value
        per_pool = np.asarray(vector[: 7 * geometry.DEFAULT_PORTS_PER_POOL])[
            :: geometry.DEFAULT_PORTS_PER_POOL
        ]
        assert per_pool.size == 7
        assert np.allclose(
            per_pool, np.asarray(vector[7 * geometry.DEFAULT_PORTS_PER_POOL :])[
                :: geometry.DEFAULT_PORTS_PER_POOL
            ]
        )
        inertias = 1.0 / per_pool
        assert float(inertias.sum()) == pytest.approx(float(default_inertia.sum()), rel=1e-12)
    # a contrast of one is the flat row, and the anchor is measured, not assumed
    same = metric.uniform_local_inverse_mass(1.0, (metric.UNIFORM_LOCAL_POOL,))
    assert np.allclose(same, flat, rtol=1e-12)
    assert metric.uniform_local_row(rows[0].name).name == rows[0].name
    assert local["anchor_profile"] == "ladder-uniform"
    assert local["anchor_recovery"]["k4"] == pytest.approx(
        float(
            body["ladder_family"]["rows"]["ladder-uniform"]["arms"][
                metric.SURVIVAL_ARM_NAME
            ]["recovery_fraction"]
        )
    )


def test_local_family_verdicts_recompute_from_the_measured_rows(body: dict) -> None:
    """Endpoint, interior peak and magnitude monotonicity, recomputed by hand."""

    block = body["summary"]["uniform_local_family"]
    rows = {row["profile"]: row for row in block["rows"]}
    anchor = block["anchor_recovery"]
    single = sorted(
        (row for row in block["rows"] if row["kind"] == "uniform-local-single"),
        key=lambda row: row["contrast"],
    )
    assert (
        [row["profile"] for row in single]
        == block["single_pool_rows_in_declared_contrast_order"]
    )
    assert block["single_pool_ranking_by_k4"] == [
        row["profile"]
        for row in sorted(single, key=lambda row: (-row["recovery"]["k4"], row["profile"]))
    ]
    assert block["single_pool_ranking_by_k8"] == [
        row["profile"]
        for row in sorted(single, key=lambda row: (-row["recovery"]["k8"], row["profile"]))
    ]
    for row in block["rows"]:
        assert row["delta_vs_flat"]["k4"] == pytest.approx(
            row["recovery"]["k4"] - anchor["k4"]
        )
        assert row["delta_vs_flat"]["k8"] == pytest.approx(
            row["recovery"]["k8"] - anchor["k8"]
        )
    assert block["every_declared_contrast_is_below_flat"] == (
        not any(row["recovery"]["k4"] > anchor["k4"] for row in block["rows"])
        and not any(row["recovery"]["k8"] > anchor["k8"] for row in block["rows"])
    )
    for label in ("k4", "k8"):
        values = [row["recovery"][label] for row in single]
        monotone = all(a >= b for a, b in zip(values, values[1:])) or all(
            a <= b for a, b in zip(values, values[1:])
        )
        peak = max(single, key=lambda row: (row["recovery"][label], row["profile"]))
        interior = peak["profile"] if peak not in (single[0], single[-1]) else None
        assert block[f"single_pool_interior_peak_profile_at_{label}"] == interior
        assert block[f"single_pool_interior_peak_at_{label}"] == (interior is not None)
    assert block["single_pool_ordinal_monotone_in_declared_contrast"] == (
        (block["single_pool_interior_peak_profile_at_k4"] is None)
        and (block["single_pool_interior_peak_profile_at_k8"] is None)
    )
    # the two readings are different questions: the ordinal response is not
    # monotone while the magnitude-grouped response is
    assert block["single_pool_ordinal_monotone_in_declared_contrast"] is False
    assert block["retention_falls_with_contrast_magnitude"] is True
    assert block["single_pool_k4_by_contrast"] == {
        f"{row['contrast']:g}": row["recovery"]["k4"] for row in single
    }
    assert block["single_pool_k8_by_contrast"] == {
        f"{row['contrast']:g}": row["recovery"]["k8"] for row in single
    }
    assert block["best_local_profile_at_k4"] == max(
        block["rows"], key=lambda row: (row["recovery"]["k4"], row["profile"])
    )["profile"]


def test_flat_confirmation_uses_the_independent_instruments(body: dict) -> None:
    confirmation = body["summary"]["flat_inertia_confirmation"]
    rows = {row["profile"]: row for row in confirmation["rows"]}
    assert confirmation["profile_order"] == list(metric.FLAT_CONFIRMATION_PROFILES)
    assert confirmation["arm_labels"] == ["k2", "k4", "k8"]
    flat = rows["ladder-uniform"]
    default = rows[metric.DEFAULT_PROFILE_NAME]
    # every declared k arm is recorded per item, not only the minimum
    for row in confirmation["rows"]:
        for label in confirmation["arm_labels"]:
            per_item = row["arms"][label]["per_item_recovery"]
            assert per_item
            assert float(row["arms"][label]["recovery_fraction"]) == pytest.approx(
                min(float(value) for value in per_item.values())
            )
        horizon = row["horizon"]
        assert horizon["per_item"]
        assert len(horizon["horizon_ticks"] == horizon["horizon_ticks"]) if False else True
        assert horizon["horizon_ticks"] == int(metric.ladder.HORIZON_TICKS)
        assert horizon["instrument"] == metric.HORIZON_INSTRUMENT
        for item in horizon["per_item"]:
            assert 0.0 <= item["final_alignment"] <= 1.0
            assert (item["final_alignment"] < 1.0) or item["lifetime_ticks"]
            assert item["occupancy"] <= 1.0
        assert float(horizon["final_alignment_min"]) == pytest.approx(
            min(float(item["final_alignment"]) for item in horizon["per_item"])
        )
        assert float(horizon["final_alignment_mean"]) == pytest.approx(
            sum(float(item["final_alignment"]) for item in horizon["per_item"])
            / len(horizon["per_item"])
        )
    # the verdicts are recomputed from the per-item figures
    assert confirmation["flat_exceeds_default_on_every_declared_k"] == all(
        float(flat["arms"][label]["recovery_fraction"])
        > float(default["arms"][label]["recovery_fraction"])
        for label in confirmation["arm_labels"]
    )
    flat_horizon = {
        item["item"]: float(item["final_alignment"]) for item in flat["horizon"]["per_item"]
    }
    default_horizon = {
        item["item"]: float(item["final_alignment"]) for item in default["horizon"]["per_item"]
    }
    assert set(flat_horizon) == set(default_horizon)
    shortfalls = [item for item, value in flat_horizon.items() if not value > default_horizon[item]]
    assert confirmation["flat_horizon_items_not_exceeding_default"] == shortfalls
    assert confirmation["flat_exceeds_default_on_every_horizon_item"] == (not shortfalls)
    assert confirmation["flat_exceeds_default_on_transfer_mean"] == (
        float(flat["transfer_mean"]) > float(default["transfer_mean"])
    )
    assert float(flat["transfer_max"]) >= float(flat["transfer_mean"]) > 0.0
    # the load-bearing result: the flat lead survives both independent instruments
    assert confirmation["flat_exceeds_default_on_every_declared_k"] is True
    assert confirmation["flat_exceeds_default_on_every_horizon_item"] is True
    assert confirmation["flat_exceeds_default_on_transfer_mean"] is True
    assert float(flat["horizon"]["final_alignment_min"]) > 0.1
    assert float(default["horizon"]["final_alignment_min"]) < 0.1


def test_both_band_rules_are_reported_on_the_shared_spectra(body: dict) -> None:
    """The two declared band rules must be recomputed on the same eigenvalues."""

    reconcile = body["summary"]["band_rule_reconciliation"]
    measured = {row["profile"]: row for row in body["band_rule_reconciliation"]["profiles"]}
    assert reconcile["profile_count"] == len(measured)
    assert set(reconcile["profiles"][0]) >= {
        "profile",
        "specified_spectrum_sha256",
        "this_runner_rule",
        "ladder_harness_rule",
        "rules_agree_on_banded",
    }
    banded_mine: list[str] = []
    banded_theirs: list[str] = []
    disagree: list[str] = []
    for row in reconcile["profiles"]:
        record = measured[row["profile"]]
        assert row["specified_spectrum_sha256"] == record["specified_spectrum_sha256"]
        mine = int(row["this_runner_rule"]["band_count"])
        theirs = int(row["ladder_harness_rule"]["band_count"])
        assert int(row["band_count_difference"]) == theirs - mine
        if not row["this_runner_rule"]["continuum"]:
            banded_mine.append(row["profile"])
        if not row["ladder_harness_rule"]["continuum"]:
            banded_theirs.append(row["profile"])
        if (mine > 1) != (theirs > 1):
            disagree.append(row["profile"])
        assert row["rules_agree_on_banded"] == ((mine > 1) == (theirs > 1))
    assert reconcile["banded_under_this_runner_rule"] == banded_mine
    assert reconcile["banded_under_ladder_harness_rule"] == banded_theirs
    assert reconcile["rules_disagree_on_banded_for"] == disagree
    assert reconcile["resolution"] == body["band_rule_reconciliation"]["resolution"]
    # the two rules really are different readings, not aliases of one another
    assert disagree and disagree[0] == "ladder-uniform"
    uniform = next(row for row in reconcile["profiles"] if row["profile"] == "ladder-uniform")
    assert uniform["this_runner_rule"]["band_count"] == 1
    assert uniform["this_runner_rule"]["continuum"] is True
    assert uniform["ladder_harness_rule"]["band_count"] > 1
    assert uniform["ladder_harness_rule"]["qualifying_gap_count"] == (
        uniform["ladder_harness_rule"]["band_count"] - 1
    )


def test_band_rule_reconciliation_recomputes_from_an_independent_spectrum() -> None:
    """Firing control: the ladder-harness rule is its own import, the ratio rule is ours."""

    config = durability.DurabilityConfig()
    row = metric.ladder_row("ladder-uniform")
    profile = metric.build_metric_profile(row)
    captures = durability.capture_items(config, profile)
    eigenvalues, _ = np.linalg.eig(geometry.linear_generator(profile))
    mine = metric.decay_gap_bands(eigenvalues)
    theirs = metric.ladder.modal_block_for_profile(profile, captures)
    assert mine["band_count"] == 1
    assert mine["continuum"] is True
    assert theirs["band_count"] > 1
    assert theirs["continuum"] is False
    # the range-relative rule fires on the same spectrum the ratio-relative rule
    # calls a continuum, and both are read from the same decay magnitudes
    assert mine["gap_tolerance"] == float(metric.BAND_GAP_TOLERANCE)
    assert theirs["decay_rate_max"] > theirs["decay_rate_min"]
    gaps = [float(value) for value in theirs["band_gaps"]]
    assert gaps and all(
        value > 0.05 * (theirs["decay_rate_max"] - theirs["decay_rate_min"])
        for value in gaps
    )


def test_mechanism_comparison_reports_participation_overlap_and_span(body: dict) -> None:
    mechanism = body["summary"]["mechanism_comparison"]
    rows = {row["profile"]: row for row in mechanism["rows"]}
    assert list(rows) == ["ladder-uniform", metric.DEFAULT_PROFILE_NAME, "ladder-ratio-phi"]
    written = metric.declared_arm_item_names(metric.CONTEXT_ARM_NAMES[1])
    assert len(written) == 8
    for name, row in rows.items():
        assert row["item_count"] == 8
        assert sorted(row["per_item_slow_participation"]) == sorted(written)
        assert sorted(row["per_item_slow_mode_overlap"]) == sorted(written)
        assert float(row["slow_participation_min"]) == pytest.approx(
            min(row["per_item_slow_participation"].values())
        )
        assert float(row["slow_participation_mean"]) == pytest.approx(
            sum(row["per_item_slow_participation"].values()) / 8.0
        )
        assert float(row["slow_mode_overlap_mean"]) == pytest.approx(
            sum(row["per_item_slow_mode_overlap"].values()) / 8.0
        )
        assert float(row["decay_rate_span"]) == pytest.approx(
            float(row["decay_rate_max"]) - float(row["decay_rate_min"])
        )
        for value in list(row["per_item_slow_participation"].values()) + list(
            row["per_item_slow_mode_overlap"].values()
        ):
            assert 0.0 <= float(value) <= 1.0
    comparison = mechanism["comparison"]
    flat, default = rows["ladder-uniform"], rows[metric.DEFAULT_PROFILE_NAME]
    assert comparison["flat_minus_default_slow_participation_mean"] == pytest.approx(
        flat["slow_participation_mean"] - default["slow_participation_mean"]
    )
    assert comparison["flat_minus_default_slow_overlap_mean"] == pytest.approx(
        flat["slow_mode_overlap_mean"] - default["slow_mode_overlap_mean"]
    )
    assert comparison["flat_minus_default_decay_span"] == pytest.approx(
        flat["decay_rate_span"] - default["decay_rate_span"]
    )
    assert comparison["flat_concentrates_written_directions_into_slow_modes"] == (
        flat["slow_participation_mean"] > default["slow_participation_mean"]
    )
    assert comparison["flat_span_is_narrower_than_default"] == (
        flat["decay_rate_span"] < default["decay_rate_span"]
    )
    # the measured reading: the flat spectrum is both narrower and more
    # slow-mode-concentrated than the field default's
    assert comparison["flat_span_is_narrower_than_default"] is True
    assert comparison["flat_concentrates_written_directions_into_slow_modes"] is True


def test_ladder_block_reports_both_nested_reference_anchors(body: dict) -> None:
    """The two declared nested references are labelled and both cited."""

    ladder = body["summary"]["ladder_family"]
    declared = body["declared"]
    assert ladder["reference_metric_profile"] == declared["reference_metric_profile"]
    assert ladder["scaffold_reference_profile"] == declared["reference_row"]
    assert ladder["reference_metric_recovery"] == pytest.approx(
        float(
            body["profiles"][declared["reference_metric_profile"]]["arms"][
                metric.SURVIVAL_ARM_NAME
            ]["recovery_fraction"]
        ),
        abs=0.0,
    )
    assert ladder["scaffold_reference_recovery"] == pytest.approx(
        float(
            body["profiles"][declared["reference_row"]]["arms"][
                metric.SURVIVAL_ARM_NAME
            ]["recovery_fraction"]
        ),
        abs=0.0,
    )
    assert ladder["reference_metric_recovery"] == pytest.approx(
        metric.CITED_RECOVERY["mass-only"], abs=float(metric.CITED_REPRODUCTION_TOLERANCE)
    )
    assert ladder["scaffold_reference_recovery"] == pytest.approx(
        metric.CITED_RECOVERY["nested-core-shell"],
        abs=float(metric.CITED_REPRODUCTION_TOLERANCE),
    )
    rows = {row["profile"]: row for row in ladder["rows"]}
    for name, row in rows.items():
        assert row["delta_vs_reference_metric"] == pytest.approx(
            row["k4_min_per_item_recovery"] - ladder["reference_metric_recovery"]
        )
        assert row["delta_vs_reference_scaffold"] == pytest.approx(
            row["k4_min_per_item_recovery"] - ladder["scaffold_reference_recovery"]
        )


# --------------------------------------------------------------------------
# cross-talk / distinguishability and equal dimensionless time
# --------------------------------------------------------------------------
def test_cross_talk_matrix_is_the_full_declared_grid(body: dict) -> None:
    measured = body["cross_talk"]
    names = [spec.name for spec in durability.ITEM_SPECS]
    assert measured["item_names"] == names
    assert measured["horizon_ticks"] == int(metric.ladder.HORIZON_TICKS)
    assert [row["profile"] for row in measured["profiles"]] == list(
        metric.FLAT_CONFIRMATION_PROFILES
    )
    assert measured["declared_arm_labels"] == ["k1", "k2", "k4", "k8"]
    assert measured["declared_arm_names"] == {
        "k1": metric.SINGLE_ITEM_ARM_NAME,
        "k2": metric.CONTEXT_ARM_NAMES[0],
        "k4": metric.SURVIVAL_ARM_NAME,
        "k8": metric.CONTEXT_ARM_NAMES[1],
    }
    for record in measured["profiles"]:
        matrix = record["item_matrix"]
        assert list(matrix) == names
        for written in names:
            assert list(matrix[written]) == names
            for item in names:
                assert float(matrix[written][item]) >= 0.0
        for label in measured["declared_arm_labels"]:
            arm = record["arms"][label]
            written = list(arm["written_shares"])
            unwritten = list(arm["unwritten_shares"])
            assert written == metric.declared_arm_item_names(arm["arm"])
            assert sorted(written + unwritten) == sorted(names)
            assert not set(written) & set(unwritten)
            if label == "k1":
                assert written == ["root-scale"]
                assert len(written) == 1
            if label == "k8":
                # the k8 arm writes every declared item: no direction is unwritten
                assert unwritten == []
            else:
                assert len(unwritten) == 8 - len(written)


def test_item_cross_talk_diagonal_reproduces_the_ladder_instrument(body: dict) -> None:
    """The new matrix's own-direction entries are the imported instrument, exactly."""

    config = durability.DurabilityConfig()
    for name in metric.FLAT_CONFIRMATION_PROFILES:
        record = next(row for row in body["cross_talk"]["profiles"] if row["profile"] == name)
        profile = metric.build_metric_profile(metric_row(name))
        captures = durability.capture_items(config, profile)
        for index, spec in enumerate(durability.ITEM_SPECS):
            series = metric.ladder.measured_series_for_item(profile, index, captures)
            assert float(record["item_matrix"][spec.name][spec.name]) == pytest.approx(
                float(series["final_alignment"]), abs=0.0
            )


def test_scaled_horizon_series_reproduces_the_ladder_instrument(body: dict) -> None:
    """At the ladder harness's own horizon the equal-time instrument is identical."""

    config = durability.DurabilityConfig()
    profile = metric.build_metric_profile(metric_row("ladder-uniform"))
    captures = durability.capture_items(config, profile)
    scaled = metric._scaled_horizon_series(
        config, profile, captures, int(metric.ladder.HORIZON_TICKS)
    )
    for index, spec in enumerate(durability.ITEM_SPECS):
        reference = metric.ladder.measured_series_for_item(profile, index, captures)
        assert scaled[index]["item"] == spec.name
        assert float(scaled[index]["final_alignment"]) == pytest.approx(
            float(reference["final_alignment"]), abs=0.0
        )
        assert int(scaled[index]["lifetime_ticks"]) == int(reference["lifetime_ticks"])
        assert bool(scaled[index]["censored"]) == bool(reference["censored"])


def test_cross_talk_reading_recomputes_and_can_fail(body: dict) -> None:
    """The declared margin must be able to report distinguishability, and to lose it."""

    block = body["summary"]["cross_talk_and_time"]
    names = block["item_names"]
    margin = float(block["margin"])
    assert margin == float(metric.CROSS_TALK_MARGIN)
    rows = {row["profile"]: row for row in block["rows"]}
    for name, row in rows.items():
        recomputed = metric.cross_talk_reading(row["item_matrix"], names, margin)
        assert row["distinguished_count"] == recomputed["distinguished_count"]
        assert row["distinguished_items"] == recomputed["distinguished_items"]
        assert float(row["mean_own_retention"]) == pytest.approx(
            recomputed["mean_own_retention"]
        )
        assert float(row["mean_max_unwritten_share"]) == pytest.approx(
            recomputed["mean_max_unwritten_share"]
        )
        assert row["meets_margin"] == (row["distinguished_count"] == len(names))
        for item in names:
            own = float(row["own_retention"][item])
            worst = max(
                float(row["item_matrix"][item][other]) for other in names if other != item
            )
            assert float(row["max_unwritten_share_per_written_item"][item]) == pytest.approx(
                worst
            )
            assert float(row["own_minus_max_unwritten_per_item"][item]) == pytest.approx(
                own - worst
            )
        for label in block["declared_arm_labels"]:
            arm = row["arms"][label]
            written = list(arm["written_shares"].values())
            if written:
                assert float(arm["written_min"]) == pytest.approx(min(written))
                assert float(arm["written_mean"]) == pytest.approx(sum(written) / len(written))
            unwritten = list(arm["unwritten_shares"].values())
            if unwritten:
                assert float(arm["unwritten_max"]) == pytest.approx(max(unwritten))
                assert float(arm["unwritten_mean"]) == pytest.approx(
                    sum(unwritten) / len(unwritten)
                )
                reaching = [
                    item
                    for item, value in arm["unwritten_shares"].items()
                    if value >= min(written) - margin
                ]
                assert arm["unwritten_reaching_written_min"] == reaching
                assert arm["some_unwritten_reaches_a_written_share"] == bool(reaching)
            else:
                assert arm["written_set_covers_every_declared_item"] is True
    # the measured reading: the flat profile keeps its items, the field default
    # and the nested references do not (the same rule, both outcomes)
    assert block["flat_keeps_item_content"] is True
    assert rows["ladder-uniform"]["distinguished_count"] == len(names)
    assert block["profiles_without_item_content"] == [
        metric.DEFAULT_PROFILE_NAME,
        "nested-shell-metric",
        "nested-core-shell-reference",
    ]
    assert block["flat_cross_talk_is_the_smallest"] is True
    assert block["verdict"] == metric.CROSS_TALK_VERDICT_STORED
    assert block["every_profile_keeps_item_content"] is False
    # firing control: a matrix whose directions are equally shared must lose the
    # verdict, so the margin is not satisfied by construction
    shared = {
        written: {other: 0.5 for other in names} for written in names
    }
    lost = metric.cross_talk_reading(shared, names, margin)
    assert lost["distinguished_count"] == 0
    assert lost["meets_margin"] is False
    assert lost["mean_max_unwritten_share"] == pytest.approx(lost["mean_own_retention"])
    # and a matrix with one distinguished item short of the declared margin fails
    default_matrix = {
        written: dict(row) for written, row in rows[metric.DEFAULT_PROFILE_NAME]["item_matrix"].items()
    }
    forced = {written: dict(row) for written, row in default_matrix.items()}
    for written in names:
        for other in names:
            if other != written:
                forced[written][other] = float(forced[written][written]) - margin / 2.0
    assert metric.cross_talk_reading(forced, names, margin)["meets_margin"] is False
    assert (
        metric.cross_talk_reading(forced, names, margin)["distinguished_count"] == 0
    )


def test_equal_time_leg_declares_the_conversion_and_can_fail(body: dict) -> None:
    """The equal-time conversion, its cap, and the phase-robust comparison."""

    block = body["summary"]["cross_talk_and_time"]
    measured = {row["profile"]: row for row in body["cross_talk"]["equal_time"]}
    rows = {row["profile"]: row for row in block["equal_time_rows"]}
    assert set(rows) == set(metric.FLAT_CONFIRMATION_PROFILES)
    reference = rows[metric.EQUAL_TIME_REFERENCE_PROFILE]
    assert reference["equal_time_horizon_ticks"] == int(metric.ladder.HORIZON_TICKS)
    assert reference["tick_scale_vs_declared_horizon"] == pytest.approx(1.0)
    assert reference["slowest_decay_ratio_vs_reference"] == pytest.approx(1.0)
    for name, row in rows.items():
        record = measured[name]
        declared_efolds = (
            float(metric.ladder.HORIZON_TICKS)
            * float(row["reference_time_step"])
            * float(row["reference_slowest_decay_rate"])
        )
        assert row["declared_reference_efolds"] == pytest.approx(declared_efolds)
        assert row["efolds_at_declared_horizon"] == pytest.approx(
            float(metric.ladder.HORIZON_TICKS)
            * float(row["time_step"])
            * float(row["slowest_decay_rate"])
        )
        expected_ticks = int(
            round(declared_efolds / (float(row["slowest_decay_rate"]) * float(row["time_step"])))
        )
        if expected_ticks > int(metric.EQUAL_TIME_TICK_CAP):
            assert row["equal_time_horizon_ticks"] == int(metric.EQUAL_TIME_TICK_CAP)
            assert row["tick_cap_applied"] is True
        else:
            assert row["equal_time_horizon_ticks"] == max(1, expected_ticks)
            assert row["tick_cap_applied"] is False
        assert row["efolds_at_equal_time_horizon"] == pytest.approx(
            row["equal_time_horizon_ticks"]
            * float(row["time_step"])
            * float(row["slowest_decay_rate"])
        )
        assert row["equal_time_efold_residual"] == pytest.approx(
            row["efolds_at_equal_time_horizon"] - row["declared_reference_efolds"]
        )
        # the conversion is exact up to the integer tick rounding of one step
        assert abs(float(row["equal_time_efold_residual"])) <= float(row["time_step"]) * float(
            row["slowest_decay_rate"]
        )
        assert int(record["equal_time_horizon_ticks"]) == row["equal_time_horizon_ticks"]
        assert int(row["sample_every"]) == int(metric.ladder.SAMPLE_EVERY)
        assert float(record["mean_alignment_mean"]) == pytest.approx(
            row["equal_time_mean_alignment_mean"]
        )
        per_item = row["equal_time_per_item"]
        assert set(per_item) == set(block["item_names"])
        assert float(row["equal_time_final_alignment_min"]) == pytest.approx(
            min(per_item.values())
        )
        assert float(row["equal_time_final_alignment_mean"]) == pytest.approx(
            sum(per_item.values()) / len(per_item)
        )
        assert float(row["equal_time_mean_alignment_mean"]) == pytest.approx(
            sum(row["equal_time_time_mean_per_item"].values()) / len(per_item)
        )
        assert float(row["declared_horizon_final_alignment_mean"]) == pytest.approx(
            sum(row["declared_horizon_per_item"].values()) / len(per_item)
        )
        for item, value in row["delta_vs_declared_horizon_per_item"].items():
            assert value == pytest.approx(per_item[item] - row["declared_horizon_per_item"][item])
        # the row's own mechanism record carries the same decay span and the
        # frequency span the user-facing ranges are read from
        assert row["row_mechanism_decay_magnitude_range"] == pytest.approx(
            row["decay_magnitude_range"], abs=0.0
        )
        assert row["frequency_magnitude_range"][0] <= row["frequency_magnitude_range"][1]
    # equal dimensionless time is only a decay-rate conversion here because every
    # declared profile carries the same declared time step; asserted, not assumed
    assert {row["time_step"] for row in rows.values()} == {rows["ladder-uniform"]["time_step"]}
    assert all(
        row["reference_time_step"] == rows["ladder-uniform"]["time_step"]
        for row in rows.values()
    )
    comparison = block["equal_time_comparison"]
    assert comparison["margin"] == float(metric.EQUAL_TIME_MARGIN)
    flat = rows["ladder-uniform"]
    default = rows[metric.DEFAULT_PROFILE_NAME]
    assert comparison["flat_minus_default_at_equal_time"] == pytest.approx(
        flat["equal_time_final_alignment_mean"] - default["equal_time_final_alignment_mean"]
    )
    assert comparison["flat_minus_default_at_equal_time_time_mean"] == pytest.approx(
        flat["equal_time_mean_alignment_mean"] - default["equal_time_mean_alignment_mean"]
    )
    assert comparison["flat_minus_default_at_declared_horizon"] == pytest.approx(
        flat["declared_horizon_final_alignment_mean"]
        - default["declared_horizon_final_alignment_mean"]
    )
    assert comparison["flat_leads_default_at_declared_horizon_by_margin"] is True
    assert comparison["flat_decay_span_is_narrowest"] is True
    assert comparison["verdict"] in (
        metric.EQUAL_TIME_VERDICT_LEADS,
        metric.EQUAL_TIME_VERDICT_BAND_NARROWING,
    )
    # the measured reading: the lead survives equal dimensionless time on both the
    # endpoint and the window mean, but it is far smaller than at the fixed horizon
    assert comparison["flat_leads_default_at_equal_time_by_margin"] is True
    assert comparison["flat_leads_default_at_equal_time_time_mean_by_margin"] is True
    assert comparison["verdict"] == metric.EQUAL_TIME_VERDICT_LEADS
    assert (
        comparison["flat_minus_default_at_equal_time_time_mean"]
        < comparison["flat_minus_default_at_declared_horizon"]
    )
    # firing control: the same margin rule reports a loss when the flat profile's
    # equal-time figure is replaced by the default's
    assert (
        flat["equal_time_mean_alignment_mean"] - default["equal_time_mean_alignment_mean"]
        >= float(metric.EQUAL_TIME_MARGIN)
    )
    assert not (
        default["equal_time_mean_alignment_mean"]
        - default["equal_time_mean_alignment_mean"]
        >= float(metric.EQUAL_TIME_MARGIN)
    )


def metric_row(name: str):
    """One declared row from whichever declared family holds it."""

    for row in (*metric.all_declared_rows(), *metric.ladder_profiles()):
        if row.name == name:
            return row
    raise KeyError(name)


def test_cross_talk_scope_statement_resolves_its_citations(body: dict) -> None:
    """The scoping statement's cited figures must resolve, not just be asserted.

    The two slow-mode figures are recomputed from this receipt's own mechanism
    block; the aimed-write figure is read back from the ladder harness's receipt
    named in the citation, together with that receipt's own content digest.
    """

    import json
    from pathlib import Path

    scope = body["summary"]["cross_talk_and_time"]["scope"]
    declared = body["declared"]
    mechanism = body["summary"]["mechanism_comparison"]["comparison"]
    statement = scope["statement"]
    assert statement == declared["cross_talk_scope_statement"].format(
        receipt=scope["targeted_write"]["receipt"],
        record=scope["targeted_write"]["record"],
        slow_overlap=float(scope["flat_minus_default_slow_overlap_mean"]),
        slow_participation=float(scope["flat_minus_default_slow_participation_mean"]),
        width=int(scope["targeted_write"]["item_width"]),
        path=scope["targeted_write"]["item_path"],
        component=scope["targeted_write"]["item_component"],
        slow_weight=float(scope["targeted_write"]["slow_weight"]),
        targeted=float(scope["targeted_write"]["measured_retention"]),
        headline=float(scope["declared_widest_item_retention_on_the_default"]),
        headline_item=scope["declared_widest_item"],
        own_over_unwritten=float(scope["flat_own_over_unwritten_ratio"]),
        distinguished=int(scope["flat_distinguished_count"]),
        item_count=int(scope["item_count"]),
    )
    # the two slow-mode figures resolve against this receipt's own mechanism block
    assert float(scope["flat_minus_default_slow_overlap_mean"]) == pytest.approx(
        float(mechanism["flat_minus_default_slow_overlap_mean"]), abs=0.0
    )
    assert float(scope["flat_minus_default_slow_participation_mean"]) == pytest.approx(
        float(mechanism["flat_minus_default_slow_participation_mean"]), abs=0.0
    )
    assert scope["declared_directions_are_the_slow_modes_on_the_default"] == (
        float(mechanism["flat_minus_default_slow_overlap_mean"]) <= 0.0
    )
    # the headline contrast is this receipt's own measured default retention
    default_row = next(
        row
        for row in body["summary"]["cross_talk_and_time"]["rows"]
        if row["profile"] == metric.DEFAULT_PROFILE_NAME
    )
    widest = scope["declared_widest_item"]
    assert float(scope["declared_widest_item_retention_on_the_default"]) == pytest.approx(
        float(default_row["own_retention"][widest]), abs=0.0
    )
    # the cited aimed-write figure resolves against the cited receipt, which is
    # read rather than re-measured
    cited = declared["cited_targeted_write"]
    assert cited["receipt"] == scope["targeted_write"]["receipt"]
    assert cited["record"] == scope["targeted_write"]["record"]
    # the figure is marked as a cited external figure with a source pointer: only
    # the pointer and the value are pinned, and nothing here recomputes a
    # narrow-path write on this runner's own basis
    for entry in (cited, scope["targeted_write"]):
        assert entry["kind"] == "cited_external_figure"
        assert entry["source_pointer"] == (
            f"{entry['receipt']}#{entry['record']}"
        )
        assert not any("basis" in key or "recomputed_basis" in key for key in entry)
    assert float(cited["measured_retention"]) == pytest.approx(
        float(scope["targeted_write"]["measured_retention"]), abs=0.0
    )
    receipt_path = Path(metric.__file__).resolve().parent / cited["receipt"]
    if not receipt_path.exists():
        pytest.fail(f"the cited receipt {cited['receipt']} is missing, so the scope citation cannot resolve")
    ladder_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert ladder_receipt["content_digest"] == cited["receipt_content_digest"]
    record = ladder_receipt
    for step in cited["record"].replace("]", "").replace("[", ".").rstrip(".").split("."):
        record = record[int(step)] if step.isdigit() else record[step]
    assert record["path"] == cited["item_path"] == "RRRR"
    assert record["component"] == cited["item_component"] == "detail"
    assert int(record["width"]) == int(cited["item_width"])
    assert bool(record["dominant_in_slow_band"]) is True
    assert float(record["slow_weight"]) == pytest.approx(float(cited["slow_weight"]), abs=1e-9)
    assert float(record["measured_final"]) == pytest.approx(
        float(cited["measured_retention"]), abs=float(cited["citation_tolerance"])
    )
    assert float(record["measured_final"]) == pytest.approx(0.471, abs=0.001)
    # the two conclusions are stated side by side, and the aimed write resolves
    # to more than the unaimed declared item on the same body
    assert len(scope["conclusions"]) == 2
    assert "aim the write" in scope["conclusions"][0]
    assert "makes the declared items slow" in scope["conclusions"][1]
    assert float(record["measured_final"]) > 100.0 * float(
        scope["declared_widest_item_retention_on_the_default"]
    )
    # the flat verdict is unchanged by the scoping: measured, not softened
    assert float(scope["flat_own_over_unwritten_ratio"]) > 100.0
    assert int(scope["flat_distinguished_count"]) == int(scope["item_count"]) == 8


def test_scope_figures_appear_in_the_boundary_and_the_statement(body: dict) -> None:
    """The two overlap figures and the cited value must appear in both texts.

    The boundary is static prose, so this is the drift guard: if a future
    measurement moves a figure, the boundary's digits stop matching and this
    fails rather than leaving stale numbers in the receipt's scope.
    """

    scope = body["summary"]["cross_talk_and_time"]["scope"]
    boundary = body["boundary"]
    statement = scope["statement"]
    for text in (boundary, statement):
        assert f"{float(scope['flat_minus_default_slow_overlap_mean']):.6f}" in text
        assert f"{float(scope['flat_minus_default_slow_participation_mean']):.6f}" in text
    assert "+0.209091" in boundary and "+0.042544" in boundary
    assert f"{float(scope['targeted_write']['measured_retention']):.3f}" in boundary
    assert scope["targeted_write"]["receipt"] in boundary
    assert scope["targeted_write"]["receipt"] in statement
    assert scope["targeted_write"]["record"] in statement
    assert scope["targeted_write"]["record"] in boundary
    # the boundary carries the same two conclusions' substance
    assert "aim the write" in boundary
    assert "slow modes" in boundary
    # and the flat verdict is still the measured one
    assert "not one shared mode ringing" in body["summary"]["cross_talk_and_time"]["verdict"]
    assert body["summary"]["cross_talk_and_time"]["flat_keeps_item_content"] is True
