"""Direct tests for the fractal placement exploration harness.

Everything is built in-process from the canonical modules; nothing is read from
disk and no scenario is replayed.  The tests assert observable behaviour of the
placement harness: the declared pin/pick-off construction, the declared per-port
scores, the modal basis gauge, the declared selection comparison, the exhaustive
write/read pair table, the declared margins, and the receipt's JSON/digest
contract.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

import run_fractal_geometry_exploration as geometry
import run_fractal_placement_exploration as placement

REQUIRED = placement.REQUIRED_ARRANGEMENTS


def receipt() -> dict:
    return placement.explore(placement.PlacementConfig.compact(), names=REQUIRED)


def record_of(built: dict, name: str) -> dict:
    return next(item for item in built["arrangements"] if item["construction"]["name"] == name)


def measured(name: str) -> dict:
    """One arrangement's declared placements, rebuilt directly through the module's own API."""
    profile = geometry.build_profile(geometry.arrangement_named(name))
    space = placement.placement_space(profile.ports_per_pool)
    basis = placement.modal_basis(profile)
    pins = placement.placement_state_pins(space, profile)
    pickoffs = placement.read_pickoffs(space, profile.port_count)
    drive_signature = placement.drive_signature(pins["pins"], basis)
    read_signature = placement.read_signature(pickoffs, basis)
    return {
        "profile": profile,
        "space": space,
        "basis": basis,
        "pins": pins,
        "pickoffs": pickoffs,
        "drive_signature": drive_signature,
        "read_signature": read_signature,
        "drive": placement.signature_scores(drive_signature, space),
        "read": placement.signature_scores(read_signature, space),
    }


# --------------------------------------------------------------------------
# declared constructions
# --------------------------------------------------------------------------
def test_the_write_pin_is_the_declared_port_state_pin():
    for name in REQUIRED:
        data = measured(name)
        space, pins = data["space"], data["pins"]
        assert pins["constraint_residual_max"] <= placement.PIN_TOLERANCE
        assert pins["unit_norm_deviation_max"] <= 1e-12
        # the pin is the declared common coordinate at that port, not something else
        assert pins["pattern_max_abs_difference"] <= placement.PIN_TOLERANCE
        assert pins["pins"].shape == (space.port_count, 4 * space.port_count)


def test_the_port_pin_reproduces_the_canonical_transceiver_input_lift():
    """The declared pin is the same object the production condensation keeps."""
    for name in REQUIRED:
        data = measured(name)
        space = data["space"]
        kernel, _receipt = geometry.subset_kernel(data["profile"], geometry.PORT_SUBSETS[0])
        lift = np.asarray(kernel["input_lift"], dtype=np.float64)
        output = np.asarray(kernel["output_rows"], dtype=np.float64)
        for column, port in enumerate(space.declared_drive_ports()):
            assert np.allclose(lift[:, column], data["pins"]["pins"][port], atol=1e-12), (name, port)
        for row, port in enumerate(space.declared_read_ports()):
            assert np.allclose(output[row], data["pickoffs"][port], atol=1e-12), (name, port)


def test_eigen_residual_against_the_generator_is_small():
    for name in REQUIRED:
        data = measured(name)
        basis, profile = data["basis"], data["profile"]
        vectors, eigenvalues = np.asarray(basis["vectors"]), np.asarray(basis["eigenvalues"])
        assert np.allclose(np.linalg.norm(vectors, axis=0), 1.0, atol=1e-12)
        assert np.allclose(
            np.asarray(basis["dual"]) @ vectors, np.eye(vectors.shape[0]), atol=1e-9
        )
        generator = geometry.linear_generator(profile)
        residual = float(
            np.linalg.norm(generator @ vectors - vectors * eigenvalues, ord="fro")
            / np.linalg.norm(generator, ord="fro")
        )
        assert residual <= placement.EIGEN_RESIDUAL_TOLERANCE, (name, residual)
        assert basis["eigendecomposition_residual"] == pytest.approx(residual, rel=1e-9)


# --------------------------------------------------------------------------
# declared scores
# --------------------------------------------------------------------------
def test_participation_vectors_sum_to_one_for_every_port():
    for name in REQUIRED:
        data = measured(name)
        for table in (data["drive"], data["read"]):
            assert table["unreached_ports"] == []
            participation = np.asarray(table["participation"])
            assert np.allclose(participation.sum(axis=1), 1.0, atol=1e-12)
            assert (participation >= 0.0).all()
            assert np.allclose(np.asarray(table["normalized"]).max(axis=1), 1.0, atol=1e-12)
            effective = np.asarray(table["effective_modes"])
            dominance = np.asarray(table["max_dominance"])
            distinguishability = np.asarray(table["distinguishability"])
            assert (effective >= 1.0).all()
            assert (effective <= data["basis"]["dimension"] + 1e-9).all()
            assert (dominance > 0.0).all() and (dominance <= 1.0).all()
            assert (distinguishability >= 0.0).all()
            assert (distinguishability <= 1.0 + 1e-12).all()
            rows = table["ports"]
            assert [row["port"] for row in rows] == list(data["space"].ports)
            raw = np.asarray(
                data["drive_signature"] if table is data["drive"] else data["read_signature"]
            )
            assert [row["signature_mass"] for row in rows] == pytest.approx(
                raw.sum(axis=1).tolist(), rel=1e-12
            )
            assert np.allclose(
                participation, raw / raw.sum(axis=1, keepdims=True), atol=1e-15
            )


def test_the_two_declared_directions_are_not_one_measurement():
    """The dual (drive) and primal (read) expansions must differ on a non-normal generator."""
    built = receipt()
    for name in REQUIRED:
        record = record_of(built, name)
        if record["basis"]["eigenvector_condition_number"] > 1.0 + 1e-9:
            assert record["placements"]["drive_dual_vs_euclidean_max_abs_difference"] > 1e-2, name


def test_declared_margins_separate_and_can_fail(monkeypatch):
    built = receipt()
    margins = built["arrangement_dependence"]["margins"]
    assert margins, "the compact run must carry the declared margins"
    for row in margins:
        assert row["measured"] >= row["margin"] and row["satisfied"] is True, row
    assert any(row["kind"] == "placement" for row in margins)
    assert any(row["kind"] == "arrangement" for row in margins)
    # the same declared rule applied to one placement against itself must fail
    monkeypatch.setattr(placement, "PLACEMENT_MARGIN_PAIRS", (("helix7", 0, 0),))
    self_comparison = placement.arrangement_dependence(built["arrangements"], 3)["margins"]
    self_row = next(row for row in self_comparison if row["kind"] == "placement")
    assert self_row["measured"] == 0.0 and self_row["satisfied"] is False


# --------------------------------------------------------------------------
# declared selection comparison
# --------------------------------------------------------------------------
def test_greedy_selection_is_self_consistent():
    built = receipt()
    for record in built["arrangements"]:
        selection = record["selection"]
        depth = selection["depth"]
        assert depth == 3
        for family in ("drive", "read", "joint"):
            entry = selection[family]
            for key in ("greedy_coverage", "declared_coverage", "restricted_greedy_coverage"):
                assert len(entry[key]) == depth
            assert entry["greedy_coverage"][0] >= entry["declared_coverage"][0] - 1e-12
            assert entry["restricted_greedy_coverage"][0] >= entry["declared_coverage"][0] - 1e-12
            for delta, greedy, declared in zip(
                entry["gain"]["delta"], entry["greedy_coverage"], entry["declared_coverage"]
            ):
                assert delta == pytest.approx(greedy - declared, rel=1e-12, abs=1e-12)
            assert entry["gain"]["max_ratio"] >= entry["gain"]["final_ratio"] - 1e-12
        assert len(set(selection["drive"]["greedy_ports"])) == depth
        assert len(set(tuple(pair) for pair in selection["joint"]["greedy_pairs"])) == depth
        declared = built["declarations"]["declared_drive_ports"]
        assert set(selection["drive"]["restricted_greedy_ports"]) <= set(declared)
        declared_pairs = [tuple(pair) for pair in built["declarations"]["declared_pairs"]]
        assert set(tuple(pair) for pair in selection["joint"]["restricted_greedy_pairs"]) <= set(declared_pairs)


def test_full_depth_greedy_reordering_matches_the_declared_set():
    built = placement.explore(placement.PlacementConfig(depth=7, include_retention=False), names=("flat-ladder",))
    selection = built["arrangements"][0]["selection"]
    assert selection["depth"] == 7
    for family in ("drive", "read", "joint"):
        entry = selection[family]
        # at full depth the restricted greedy set is exactly the declared set
        assert entry["restricted_greedy_coverage"][-1] == pytest.approx(
            entry["declared_coverage"][-1], rel=1e-12
        )
        assert len(entry["greedy_coverage"]) == 7
        # the declared ports are candidates, so the first greedy step cannot do worse;
        # later steps are greedy and are reported as measured, not as a guarantee
        assert entry["greedy_coverage"][0] >= entry["declared_coverage"][0] - 1e-12
        assert entry["gain"]["final_ratio"] == pytest.approx(
            entry["greedy_coverage"][-1] / entry["declared_coverage"][-1], rel=1e-12
        )
        assert len(entry["greedy_ports"] if family != "joint" else entry["greedy_pairs"]) == 7
    assert sorted(selection["drive"]["restricted_greedy_ports"]) == sorted(
        built["declarations"]["declared_drive_ports"]
    )


def test_selection_is_compared_against_the_declared_binding_order():
    built = receipt()
    declarations = built["declarations"]
    assert declarations["declared_drive_ports"] == [0, 4, 8, 12, 16, 20, 24]
    assert declarations["declared_read_ports"] == [1, 5, 9, 13, 17, 21, 25]
    assert declarations["declared_pairs"] == [
        [0, 1], [4, 5], [8, 9], [12, 13], [16, 17], [20, 21], [24, 25]
    ]
    for record in built["arrangements"]:
        selection = record["selection"]
        depth = selection["depth"]
        assert selection["drive"]["declared_ports"] == declarations["declared_drive_ports"][:depth]
        assert selection["read"]["declared_ports"] == declarations["declared_read_ports"][:depth]
        assert selection["joint"]["declared_pairs"] == declarations["declared_pairs"][:depth]


# --------------------------------------------------------------------------
# write/read pairs
# --------------------------------------------------------------------------
def test_every_declared_pair_carries_a_transfer_score():
    built = receipt()
    space = placement.placement_space()
    for record in built["arrangements"]:
        pairs = record["pairs"]
        matrix = np.asarray(pairs["transfer_matrix"], dtype=np.float64)
        reverse = np.asarray(pairs["reverse_transfer_matrix"], dtype=np.float64)
        assert matrix.shape == reverse.shape == (space.port_count, space.port_count)
        assert pairs["pair_count"] == space.port_count ** 2
        assert np.isfinite(matrix).all() and (matrix >= 0.0).all() and (matrix <= 1.0).all()
        flat = matrix.reshape(-1)
        assert pairs["max_transfer"] == pytest.approx(float(flat.max()), rel=1e-12)
        assert pairs["min_transfer"] == pytest.approx(float(flat.min()), rel=1e-12)
        assert pairs["best"][0]["transfer"] == pytest.approx(float(flat.max()), rel=1e-12)
        assert pairs["worst"][0]["transfer"] == pytest.approx(float(flat.min()), rel=1e-12)
        transfers = [row["transfer"] for row in pairs["best"]]
        assert transfers == sorted(transfers, reverse=True)
        worst = [row["transfer"] for row in pairs["worst"]]
        assert worst == sorted(worst)
        correlation = pairs["write_read_rank_correlation"]
        assert -1.0 <= correlation["port_spearman"] <= 1.0
        assert 0.0 <= correlation["best_partner_is_itself_fraction"] <= 1.0
        for row in pairs["best"]:
            assert matrix[row["write_port"], row["read_port"]] == pytest.approx(row["transfer"], rel=1e-12)


def test_write_and_read_quality_rank_together():
    """A port that excites many modes is generally also a port that sees many modes."""
    built = receipt()
    for record in built["arrangements"]:
        correlation = record["pairs"]["write_read_rank_correlation"]["port_spearman"]
        assert correlation > 0.5, (record["construction"]["name"], correlation)


# --------------------------------------------------------------------------
# arrangement dependence
# --------------------------------------------------------------------------
def test_top_placements_are_reported_and_overlap_is_measured():
    built = receipt()
    count = built["declarations"]["top_placements"]
    dependence = built["arrangement_dependence"]
    assert set(dependence["families"]["drive"]["top_sets"]) == set(REQUIRED)
    for record in built["arrangements"]:
        scores = [row["effective_modes"] for row in record["placements"]["drive"]["ports"]]
        expected = list(placement.top_indices(scores, count))
        assert [item["port"] for item in record["placements"]["top"]["drive"]] == expected
        ports = {row["port"]: row for row in record["placements"]["drive"]["ports"]}
        for item in record["placements"]["top"]["drive"]:
            assert item["effective_modes"] == pytest.approx(ports[item["port"]]["effective_modes"], rel=1e-12)
    for family in ("drive", "read", "joint"):
        entry = dependence["families"][family]
        for name in REQUIRED:
            assert len(entry["top_sets"][name]) == count
        assert len(entry["pairwise"]) == 3
        assert entry["min_jaccard"] <= entry["mean_jaccard"] <= entry["max_jaccard"]
        assert entry["consensus_size"] == len(entry["consensus"])
        normalised = {
            frozenset(tuple(item) if isinstance(item, (list, tuple)) else int(item) for item in entry["top_sets"][name])
            for name in REQUIRED
        }
        assert entry["distinct_top_sets"] == len(normalised)


def test_the_declared_required_arrangements_are_measured():
    built = receipt()
    assert {record["construction"]["name"] for record in built["arrangements"]} == set(REQUIRED)
    for record in built["arrangements"]:
        identity = record["placements"]["kernel_identity"]
        assert identity["kernel_status"]
        assert identity["input_lift_vs_port_pin_max_abs_difference"] <= 1e-12
        assert identity["output_rows_vs_port_pickoff_max_abs_difference"] <= 1e-12
        assert record["placements"]["pin_vs_canonical_common_pattern_max_abs_difference"] <= placement.PIN_TOLERANCE


# --------------------------------------------------------------------------
# receipt contract
# --------------------------------------------------------------------------
def test_receipt_is_json_clean_and_round_trips():
    built = receipt()
    rendered = json.dumps(placement._jsonable(built), sort_keys=True, allow_nan=False)
    assert json.loads(rendered) == json.loads(
        json.dumps(placement._jsonable(built), sort_keys=True, allow_nan=False)
    )
    assert built["schema"] == placement.SCHEMA
    assert built["declarations"]["schema"] == placement.RECEIPT_SCHEMA
    assert built["declarations"]["boundary"]
    assert built["limitations"]
    for record in built["arrangements"]:
        assert record["determinism"]["deterministic"] is True
        assert record["placements"]["drive"]["ports"]
        assert record["placements"]["read"]["ports"]


def test_receipt_digest_covers_the_measured_numbers_and_fires():
    built = receipt()
    assert built["receipt_sha256"] == placement.content_digest(built)
    assert len(built["receipt_sha256"]) == 64
    int(built["receipt_sha256"], 16)
    changed_score = json.loads(json.dumps(placement._jsonable(built)))
    changed_score["arrangements"][0]["placements"]["drive"]["ports"][3]["effective_modes"] += 1e-6
    assert placement.content_digest(changed_score) != built["receipt_sha256"]
    changed_pair = json.loads(json.dumps(placement._jsonable(built)))
    changed_pair["arrangements"][0]["pairs"]["transfer_matrix"][0][0] += 1e-9
    assert placement.content_digest(changed_pair) != built["receipt_sha256"]
    changed_ranking = json.loads(json.dumps(placement._jsonable(built)))
    changed_ranking["arrangements"][0]["selection"]["drive"]["greedy_ports"][0] += 1
    assert placement.content_digest(changed_ranking) != built["receipt_sha256"]


def test_rankings_and_digest_reproduce_across_runs():
    first, second = receipt(), receipt()
    assert first["receipt_sha256"] == second["receipt_sha256"]
    for left, right in zip(first["arrangements"], second["arrangements"]):
        assert left["placements"]["top"] == right["placements"]["top"]
        assert left["placements"]["drive"]["ports"] == right["placements"]["drive"]["ports"]
        assert left["selection"]["drive"]["greedy_ports"] == right["selection"]["drive"]["greedy_ports"]
        assert left["selection"]["joint"]["greedy_pairs"] == right["selection"]["joint"]["greedy_pairs"]
        assert left["pairs"]["transfer_matrix"] == right["pairs"]["transfer_matrix"]
        assert left["placements"]["pin_sha256"] == right["placements"]["pin_sha256"]
    # wall-clock fields are the only thing allowed to differ
    assert placement.canonical_digest(first) != placement.canonical_digest(second)
    assert placement.content_digest(first) == placement.content_digest(second)


def test_wall_clock_fields_do_not_participate_in_the_digest():
    built = receipt()
    wall_clock = json.loads(json.dumps(placement._jsonable(built)))
    wall_clock["runtime_seconds"] += 1000.0
    for record in wall_clock["arrangements"]:
        record["elapsed_seconds"] += 1000.0
    assert placement.content_digest(wall_clock) == built["receipt_sha256"]


def test_partial_runs_skip_absent_declared_margins():
    built = placement.explore(placement.PlacementConfig.compact(), names=("flat-ladder",))
    assert [record["construction"]["name"] for record in built["arrangements"]] == ["flat-ladder"]
    assert built["arrangement_dependence"]["margins"] == []
    assert set(built["arrangement_dependence"]["families"]["drive"]["top_sets"]) == {"flat-ladder"}
