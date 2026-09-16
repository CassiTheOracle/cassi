"""Direct tests for the fractal-geometry arrangement exploration harness.

Everything is built in-process from the canonical module; nothing is read from
disk and no scenario is replayed.  The tests assert observable behaviour of the
harness: the declared construction contracts, the declared cross-arrangement
margins, and the receipt's JSON/digest contract.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

import run_fractal_geometry_exploration as geometry

LADDER_NEIGHBOURS = {(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6)}


def profile(name: str):
    return geometry.build_profile(geometry.arrangement_named(name))


def rail(name: str) -> np.ndarray:
    return np.asarray(profile(name).transport_matrix, dtype=np.float64)


def retention(name: str) -> dict:
    return geometry.retention_metrics(
        profile(name), pools=geometry.DEFAULT_IMPULSE_POOLS,
        work=geometry.DEFAULT_IMPULSE_WORK, ticks=geometry.DEFAULT_RETENTION_TICKS,
    )


# --------------------------------------------------------------------------
# construction invariants
# --------------------------------------------------------------------------
def test_every_arrangement_constructs_an_antisymmetric_bounded_rail():
    declared = geometry.arrangements()
    assert len(declared) >= 11
    for arrangement in declared:
        current = geometry.build_profile(arrangement)
        current_rail = np.asarray(current.transport_matrix, dtype=np.float64)
        assert current_rail.shape == (2 * current.port_count, 2 * current.port_count)
        assert current_rail.shape[0] == 56
        assert np.array_equal(current_rail, -current_rail.T), arrangement.name
        assert np.abs(current_rail).sum() > 0.0, arrangement.name
        assert np.isfinite(current_rail).all(), arrangement.name


def test_declared_strength_budget_matches_the_rail_actually_used():
    ports_per_pool = geometry.DEFAULT_PORTS_PER_POOL
    parts = geometry.canonical_parts(ports_per_pool)
    for arrangement in geometry.arrangements():
        if arrangement.kind != "declared-pool-graph":
            continue
        current = geometry.build_profile(arrangement)
        current_rail = np.asarray(current.transport_matrix, dtype=np.float64)
        # the rail must be exactly the sum of its declared link contributions
        expected = np.zeros_like(current_rail)
        declared = geometry.effective_links(arrangement, ports_per_pool=ports_per_pool)
        for link in declared:
            for source, destination, scale in geometry.pool_link_port_pairs(link, parts):
                weight = geometry._edge_weight(parts, source, destination, scale)
                expected[destination, source] += weight
                expected[source, destination] -= weight
                assert current_rail[destination, source] != 0.0, (arrangement.name, link)
                assert current_rail[destination, source] == pytest.approx(weight, rel=1e-12)
        hooks = geometry.hook_effect(current, quartic_probe=False)
        assert hooks["cross_pool_strength_l1"] > 0.0, arrangement.name
        assert hooks["cross_pool_strength_l1"] <= float(np.abs(expected).sum()) + 1e-12
        # every declared pool link is cross-pool, so the canonical intra rings and
        # strand bridges are the only entries outside the declared budget
        assert np.array_equal(
            current_rail - expected,
            np.asarray(geometry.rail_from_pool_links(()), dtype=np.float64),
        ), arrangement.name


def test_matched_density_rewire_reproduces_the_ladder_interaction_budget():
    ladder = geometry.hook_effect(profile("flat-ladder"), quartic_probe=False)
    rewire = geometry.hook_effect(profile("random-rewire-matched"), quartic_probe=False)
    quasiperiodic = geometry.hook_effect(profile("quasiperiodic-chain"), quartic_probe=False)
    assert rewire["cross_pool_entries"] == ladder["cross_pool_entries"]
    assert rewire["cross_pool_strength_l1"] == pytest.approx(
        ladder["cross_pool_strength_l1"], rel=1e-12
    ), "declared density matching must be realized in the rail"
    assert quasiperiodic["cross_pool_strength_l1"] == pytest.approx(
        ladder["cross_pool_strength_l1"], rel=1e-12
    )
    # matched density must not mean matched geometry
    assert rewire["coupled_pool_pairs"] != ladder["coupled_pool_pairs"]
    assert not np.allclose(
        np.asarray(profile("flat-ladder").transport_matrix),
        np.asarray(profile("random-rewire-matched").transport_matrix),
    )
    assert (
        quasiperiodic["cross_pool_strength_l1"] - rewire["cross_pool_strength_l1"]
    ) == pytest.approx(0.0, abs=1e-12)


def test_isolated_couples_no_pools():
    hooks = geometry.hook_effect(profile("isolated"), quartic_probe=False)
    assert hooks["coupled_pool_pairs"] == []
    assert hooks["cross_pool_entries"] == 0
    assert hooks["cross_pool_strength_l1"] == 0.0
    current = profile("isolated")
    doubled = geometry.cross_pool_gain_profile(current, geometry.RAIL_GAIN_PROBE)
    assert np.array_equal(
        np.asarray(doubled.transport_matrix), np.asarray(current.transport_matrix)
    ), "an arrangement with no cross-pool entries cannot respond to a cross-pool gain"
    unamplified = geometry.cross_pool_gain_profile(current, 1.0)
    assert np.array_equal(
        geometry.linear_generator(unamplified), geometry.linear_generator(current)
    )


def test_ladder_couples_only_its_declared_neighbours():
    hooks = geometry.hook_effect(profile("flat-ladder"), quartic_probe=False)
    assert {tuple(pair) for pair in hooks["coupled_pool_pairs"]} == LADDER_NEIGHBOURS
    sparse = geometry.hook_effect(profile("sparse-long-link"), quartic_probe=False)
    assert {tuple(pair) for pair in sparse["coupled_pool_pairs"]} == (
        LADDER_NEIGHBOURS | {(0, 3), (3, 6)}
    )
    pairs = geometry.hook_effect(profile("recursive-paired-loops"), quartic_probe=False)
    assert {tuple(pair) for pair in pairs["coupled_pool_pairs"]} == (
        LADDER_NEIGHBOURS | {(0, 6)}
    )


def test_topology_is_metadata_only_when_the_rail_is_projected():
    # a declared-hook arrangement uses its topology to build the rail ...
    hooked = geometry.hook_effect(profile("undivided"), quartic_probe=False)
    assert hooked["declared_topology"] == "undivided"
    assert hooked["topology_changes_rail"] is True
    # ... and a projected rail makes the topology metadata-only
    constructed = geometry.hook_effect(profile("flat-ladder"), quartic_probe=False)
    assert constructed["projected_transport_used"] is True
    assert constructed["topology_changes_rail"] is False
    # the reported edge rail is the rail itself exactly when nothing was projected
    for arrangement in geometry.arrangements():
        current = geometry.build_profile(arrangement)
        hooks = geometry.hook_effect(current, quartic_probe=False)
        assert hooks["rail_equals_edge_rail"] is (
            current.projected_transport is None
        ), arrangement.name
        assert hooks["projected_transport_used"] is (
            arrangement.kind == "declared-pool-graph"
        ), arrangement.name


def test_quartic_weights_leave_the_linear_spectrum_untouched():
    from dataclasses import replace

    current = profile("helix7")
    ramp = np.ones(current.port_count)
    ramp[:] = 1.0 + np.arange(current.port_count) / current.port_count
    weighted = replace(current, projected_quartic_weights=ramp)
    assert np.array_equal(geometry.linear_generator(current), geometry.linear_generator(weighted))
    probe = geometry.hook_effect(current)["quartic_probe"]
    assert probe["linear_generator_max_abs_difference"] == 0.0
    assert probe["linear_spectrum_changed"] is False
    # a common-mode impulse never drives the relative coordinate: the quartic
    # term must be invisible there
    assert probe["common_impulse"]["abs_retention_difference"] < geometry.QUARTIC_NULL_TOLERANCE
    assert probe["null_arm_within_tolerance"] is True
    # a counterflow impulse drives the relative coordinate directly: the quartic
    # term must move the retained energy
    assert (
        probe["counterflow_impulse"]["abs_retention_difference"]
        > geometry.QUARTIC_EFFECT_TOLERANCE
    )
    assert probe["nonlinear_retention_changed"] is True


def test_constructions_are_deterministic():
    for name in ("helix7", "flat-ladder", "random-rewire-matched", "nested-core-shell"):
        first, second = profile(name), profile(name)
        assert geometry.canonical_digest(first.as_dict()) == geometry.canonical_digest(second.as_dict())
        assert np.array_equal(
            np.asarray(first.transport_matrix), np.asarray(second.transport_matrix)
        )
        assert np.array_equal(geometry.linear_generator(first), geometry.linear_generator(second))
    # the declared rewire seed is fixed: a different seed is a different arrangement
    other = geometry.rail_from_pool_links(
        geometry._random_rewire_links(seed=geometry.RANDOM_SEED + 1)
    )
    assert not np.array_equal(
        other, geometry.rail_from_pool_links(geometry._random_rewire_links())
    )


# --------------------------------------------------------------------------
# metric sanity: one quantity must distinguish, one must stay invariant
# --------------------------------------------------------------------------
def test_retention_separates_graph_only_changes_from_mass_changes():
    ladder, rewire = retention("flat-ladder"), retention("random-rewire-matched")
    assert ladder["all_sites_measured"] and rewire["all_sites_measured"]
    # precondition: same mass metric, matched realized density, different pool graph
    assert np.array_equal(
        geometry.independent_mass(profile("flat-ladder")),
        geometry.independent_mass(profile("random-rewire-matched")),
    )
    ladder_rail = geometry.hook_effect(profile("flat-ladder"), quartic_probe=False)
    rewire_rail = geometry.hook_effect(profile("random-rewire-matched"), quartic_probe=False)
    assert ladder_rail["intra_pool_strength_l1"] == rewire_rail["intra_pool_strength_l1"]
    assert ladder_rail["cross_pool_strength_l1"] == pytest.approx(
        rewire_rail["cross_pool_strength_l1"], rel=1e-12
    )
    assert ladder_rail["coupled_pool_pairs"] != rewire_rail["coupled_pool_pairs"]
    differences = [
        abs(left["retention_ratio"] - right["retention_ratio"])
        for left, right in zip(ladder["by_pool"], rewire["by_pool"])
    ]
    assert max(differences) <= geometry.RAIL_INVARIANCE_TOLERANCE

    baseline, undivided = retention("helix7"), retention("undivided")
    baseline_site = {row["impulse_pool"]: row for row in baseline["by_pool"]}
    undivided_site = {row["impulse_pool"]: row for row in undivided["by_pool"]}
    assert not np.array_equal(
        geometry.independent_mass(profile("helix7")),
        geometry.independent_mass(profile("undivided")),
    )
    assert baseline["site_dependence"] > geometry.MASS_SENSITIVITY_MARGIN
    # the canonical mass ladder makes a mid-pool impulse decay differently than a
    # uniform-mass body; the arrangement-independent part is the graph, not the mass
    spread = max(
        abs(baseline_site[pool]["retention_ratio"] - undivided_site[pool]["retention_ratio"])
        for pool in baseline_site
    )
    assert spread >= geometry.MASS_SENSITIVITY_MARGIN
    # a uniform-mass body retains identically wherever the impulse lands
    assert undivided["site_dependence"] < 1e-6
    assert baseline["site_dependence"] > 1e-2


def test_mode_localization_distinguishes_a_chain_from_an_all_to_all_rail():
    chain = geometry.spectrum_metrics(profile("quasiperiodic-chain"), rail_gains=())
    all_to_all = geometry.spectrum_metrics(profile("nested-core-shell"), rail_gains=())
    assert chain["independent_reconstruction_max_abs_difference"] < 1e-12
    assert all_to_all["independent_reconstruction_max_abs_difference"] < 1e-12
    assert chain["ipr_median"] - all_to_all["ipr_median"] >= geometry.LOCALIZATION_MARGIN
    assert chain["ipr_min"] > all_to_all["ipr_min"]
    assert chain["ipr_by_mode"] != all_to_all["ipr_by_mode"]
    assert chain["maximum_growth_rate"] < 0.0
    assert all_to_all["maximum_growth_rate"] < 0.0
    assert chain["dimension"] == all_to_all["dimension"] == 112


def test_cross_pool_gain_probe_is_exact_at_unit_gain_and_moves_the_spectrum_when_stronger():
    for name in ("helix7", "quasiperiodic-chain"):
        current = profile(name)
        unit = geometry.cross_pool_gain_profile(current, 1.0)
        amplified = geometry.cross_pool_gain_profile(current, geometry.RAIL_GAIN_PROBE)
        assert np.array_equal(
            np.asarray(unit.transport_matrix), np.asarray(current.transport_matrix)
        )
        assert np.abs(
            geometry.linear_generator(unit) - geometry.linear_generator(current)
        ).max() <= 1e-12
        assert np.abs(
            geometry.linear_generator(amplified) - geometry.linear_generator(current)
        ).max() > 1e-12


# --------------------------------------------------------------------------
# receipt contract
# --------------------------------------------------------------------------
def receipt() -> dict:
    return geometry.explore(
        geometry.ExploreConfig.compact(),
        names=("helix7", "undivided", "flat-ladder", "random-rewire-matched"),
    )


def test_receipt_is_json_clean_and_round_trips():
    built = receipt()
    rendered = json.dumps(built, sort_keys=True, allow_nan=False)
    assert json.loads(rendered) == json.loads(json.dumps(built, sort_keys=True, allow_nan=False))
    for record in built["arrangements"]:
        assert record["construction"]["construction_rule"]
        assert record["construction"]["ports_per_pool"] == geometry.DEFAULT_PORTS_PER_POOL
        assert record["construction"]["state_dimension"] == 4 * record["construction"]["port_count"]
        assert record["determinism"]["deterministic"] is True
        assert len(record["spectrum"]["ipr_by_mode"]) == record["spectrum"]["dimension"]
        assert record["hooks"]["rail_antisymmetry_max_abs"] == 0.0
        assert record["access"]["subsets"]


def test_receipt_digest_covers_the_measured_numbers():
    built = receipt()
    assert built["receipt_sha256"] == geometry.content_digest(built)
    assert len(built["receipt_sha256"]) == 64
    int(built["receipt_sha256"], 16)
    # a changed measurement must change the digest
    tampered = json.loads(json.dumps(built))
    tampered["arrangements"][0]["retention"]["by_pool"][0]["retention_ratio"] += 1e-6
    assert geometry.content_digest(tampered) != built["receipt_sha256"]
    # wall-clock fields must not participate
    tampered = json.loads(json.dumps(built))
    tampered["runtime_seconds"] += 1000.0
    tampered["arrangements"][0]["elapsed_seconds"] += 1000.0
    assert geometry.content_digest(tampered) == built["receipt_sha256"]


def test_receipt_comparisons_are_guarded_for_partial_runs():
    built = receipt()
    declared = built["comparisons"]
    assert declared["retention_rail_invariance"]
    assert all(row["satisfied"] for row in declared["retention_rail_invariance"])
    assert all(row["margin"] == geometry.RAIL_INVARIANCE_TOLERANCE
               for row in declared["retention_rail_invariance"])
    names = {row["arrangement"] for row in declared["cross_pool_gain"]}
    assert names == {"helix7", "undivided", "flat-ladder", "random-rewire-matched"}
    assert all(row["unit_gain_rail_identical"] for row in declared["cross_pool_gain"])
    assert geometry.explore(
        geometry.ExploreConfig.compact(), names=("flat-ladder", "random-rewire-matched")
    )["comparisons"]["retention_mass_sensitivity"] == []


def test_receipt_digest_reproduces_across_runs():
    first, second = receipt(), receipt()
    assert first["receipt_sha256"] == second["receipt_sha256"]
    assert geometry.content_digest(first) == geometry.content_digest(second)
    assert geometry.strip_timing(first) == geometry.strip_timing(second)
    # wall-clock fields are the only thing allowed to differ
    assert geometry.canonical_digest(first) != geometry.canonical_digest(second)
