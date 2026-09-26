"""Tests for the store scale-tree measurement.

Cheap by construction.  The sweep's own arms cost minutes per level and are not
re-run here; what is re-run is every predicate that has to keep holding, off the
delivered receipt itself and off the field's own rules:

  * every declared level ran and published its complete and measured triple
    counts, with the declared cap applied and published;
  * every reading in the published table equals its own numbers -- its floor
    recomputed from the finite-difference term and the numerical term, its
    at_the_floor/present/assignment_specific/counts_only flags recomputed, the
    fraction recomputed from the response and the positive control;
  * every per-level aggregate equals the count of its own rows, and the branch
    the receipt publishes is the branch the declared rule returns for those
    aggregates;
  * the branch rule is exercised on real records with a perturbed control and a
    perturbed surface, so each branch it can return is shown to be reachable --
    including the third branch, which the receipt reports as tested and
    non-firing;
  * the cross-resolution leg is matched against the surface census: the paths the
    matched table calls parent-surfaces-everywhere/child-surface-missing are the
    paths whose detail write the surface table records as executing at one
    resolution and refused at the other;
  * the port fallback carries the field's own refusal text, checked live against
    the field at one leaf path and one path beyond a leaf;
  * the receipt's own content digest, recomputed with the digest field popped,
    and changed by a mutation of a real published number.

Every can-fail check mutates a real measurement rather than a fixture: the
perturbations below act on the delivered receipt's own rows and records, and the
live checks call the field's own write and read paths.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Mapping

import pytest

import run_memory_consumer_path as consumer
import run_memory_store_scale as scale
import run_store_addressing_capacity as capacity
import run_store_addressing_rank as rank
import run_store_addressing_tree as tree

RECEIPT_PATH = tree.RECEIPT_PATH
BLOCK_PATHS = tree.BLOCK_PATHS
DECLARED_COUNTS = {4: {8, 16, 24, 28}, 8: {32}}


@pytest.fixture(scope="module")
def canonical() -> dict[str, Any]:
    # The documented run order is blocks first, then merge, then pytest, so an
    # absent receipt fails here with the commands that produce it rather than
    # reading as a broken harness in a tree where the runner has not been run.
    assert RECEIPT_PATH.exists(), (
        f"the merged receipt {RECEIPT_PATH} is missing; produce it from CassiFI with "
        "`python run_store_addressing_tree.py --block declared-profile`, "
        "`python run_store_addressing_tree.py --block higher-resolution`, then "
        "`python run_store_addressing_tree.py --block merge`"
    )
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def levels(canonical: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        level
        for _name, record in sorted(canonical["blocks"].items())
        for level in record["levels"].values()
        if bool(level.get("constructible"))
    ]


@pytest.fixture(scope="module")
def settings() -> rank.AddressingRankConfig:
    return rank.AddressingRankConfig()


def recompute_floor(
    row: Mapping[str, Any], settings: rank.AddressingRankConfig
) -> float:
    """The declared floor, from the row's own published responses.

    Two schemas are published, each with its own declared floor: the probe
    readings carry a finite-difference term and a numerical term, and the deposit
    reading carries the numerical term only against the parent's own deposit at
    its own surface.
    """

    treatment = row["treatment_response"]
    if "own_deposit_response" in row:
        return float(settings.epsilon_factor) * abs(
            float(row["own_deposit_response"] or 0.0)
        )
    own = row["own_response"]
    half = row["half_budget_response"]
    finite = (
        abs(float(treatment) - float(half))
        if treatment is not None and half is not None
        else 0.0
    )
    return max(
        float(settings.floor_factor) * finite,
        float(settings.epsilon_factor) * abs(float(own or 0.0)),
    )


# --------------------------------------------------------------------------
# the declared rule, off the field's own tree
# --------------------------------------------------------------------------
def test_the_declared_cap_selects_the_head_and_the_tail_of_the_level_order() -> None:
    """A capped level still measures its shallowest and its deepest parents."""

    for ports_per_pool, counts in tree.RESOLUTION_LEVELS:
        port_count = capacity.resolution_profile(int(ports_per_pool))[0].port_count
        for count in counts:
            catalogue = tree.level_catalogue(int(port_count), int(count))
            triples = catalogue["triples"]
            complete = [
                position
                for position, row in enumerate(triples)
                if str(row["triple_class"]) == "complete"
            ]
            selected = tree.selected_triples(triples, tree.MEASURED_TRIPLE_CAP)
            assert selected == sorted(selected)
            assert all(position in complete for position in selected)
            assert len(selected) == min(len(complete), tree.MEASURED_TRIPLE_CAP)
            if len(complete) <= tree.MEASURED_TRIPLE_CAP:
                assert selected == complete
            else:
                assert selected[0] == complete[0]
                assert selected[-1] == complete[-1]
            # a parent surface is always an interior node, and its children exist
            for position in complete:
                parent = triples[position]["parent"]
                assert int(parent["size"]) > 1
                assert str(parent["item"]["addressability"]) == "interior_node"
    # the cap binds somewhere, so the published check is not vacuous
    catalogue = tree.level_catalogue(28, 28)
    assert len(
        [
            row
            for row in catalogue["triples"]
            if str(row["triple_class"]) == "complete"
        ]
    ) > tree.MEASURED_TRIPLE_CAP


def test_the_declared_family_leaves_the_deeper_triples_to_the_port_fallback() -> None:
    """The child refusals the readings record are the field's own rule's leaves."""

    catalogue = tree.level_catalogue(28, 28)
    leaf_child = [
        row for row in catalogue["triples"] if str(row["triple_class"]) == "leaf_child"
    ]
    assert leaf_child, "the level the port fallback is for has no leaf-child triple"
    for row in leaf_child:
        classes = [str(child["node_class"]) for child in row["children"]]
        assert "leaf_port" in classes, (row["parent_path"], classes)
        for child in row["children"]:
            assert str(child["node_class"]) in (
                "leaf_port",
                "declared_detail",
                "declared_beyond",
            )
            if str(child["node_class"]) == "leaf_port":
                assert child["item"] is None
                assert str(child["scale"]["addressability"]) == "leaf_port"
            else:
                assert child["item"] is not None
                assert str(child["item"]["addressability"]) == "interior_node"


def test_the_field_refuses_a_leaf_detail_and_a_path_beyond_a_leaf() -> None:
    """The surface limitation the readings name is the field's own refusal."""

    profile = scale.flat_profile()
    owner, home = consumer.open_owner(profile, prefix="tree-test-")
    try:
        blank = float(
            scale.plain(
                owner.read_packet_deposit(
                    path="", component="scale", flow_signal=[1.0, 0.0]
                )
            )["recovered_deposit"]
        )
        assert blank == 0.0
        # a positive control first: an interior node's detail surface executes,
        # so the refusals below are the field's boundary and not a dead owner
        accepted = scale.plain(
            owner.write_packet_impulse(
                "tree-test:accepted",
                path="LLL",
                component="detail",
                flow_signal=[1.0, 0.0],
                work_budget=rank.PROBE_BUDGET,
            )
        )
        assert bool(scale.plain(accepted["impulse_receipt"])["accepted"]) is True
        leaf = capacity.measure_refusal(owner, "LLLL", "detail")
        beyond = capacity.measure_refusal(owner, "L" * 40, "detail")
        assert "no detail mode" in leaf, leaf
        assert "descends beyond a leaf" in beyond, beyond
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


# --------------------------------------------------------------------------
# the delivered receipt
# --------------------------------------------------------------------------
def test_the_receipt_publishes_the_declared_blocks_and_levels(
    canonical: Mapping[str, Any],
) -> None:
    assert canonical["schema"] == tree.SCHEMA
    assert set(canonical["blocks"]) == set(tree.BLOCK_PATHS)
    for name, record in canonical["blocks"].items():
        resolution = int(record["resolution"])
        assert record["schema"] == tree.BLOCK_SCHEMA
        assert record["block"] == name
        assert resolution in DECLARED_COUNTS
        if not bool(record["levels_override_used"]):
            assert {int(n) for n in record["points_run"]} == (
                DECLARED_COUNTS[resolution] - {int(row["n"]) for row in record["points_not_run"]}
            )
        assert bool(record["delivered_item_list_restored"]) is True
        for level in record["levels"].values():
            assert int(level["ports_per_pool"]) == resolution
            assert int(level["measured_triple_cap"]) == int(tree.MEASURED_TRIPLE_CAP)
            assert int(level["port_fallback_cap"]) == int(tree.PORT_FALLBACK_CAP)
    published = [(int(row["n"]), int(row["resolution"])) for row in canonical["table"]]
    assert len(published) == len(set(published))
    assert published


def test_every_level_publishes_its_complete_and_measured_triple_counts(
    levels: list[Mapping[str, Any]],
) -> None:
    for level in levels:
        readings = level["readings"]
        measured = int(readings["triples_measured"])
        complete = int(readings["complete_triples"])
        assert measured > 0
        assert 0 < measured <= complete
        assert measured <= int(level["measured_triple_cap"])
        assert len(level["measured"]) == measured
        assert len(level["measured_positions"]) == measured
        # every measured row is a complete triple of this level's own catalogue
        classes = {
            str(row["parent_path"]): str(row["triple_class"])
            for row in level["catalogue"]["triples"]
        }
        for row in level["measured"]:
            assert classes[str(row["parent_path"])] == "complete"
        # the surface limitations are recorded with the count of them
        assert int(readings["surface_limitation_triples"]) == len(
            level["surface_limitations"]
        )


def test_every_reading_in_the_table_equals_its_own_numbers(
    canonical: Mapping[str, Any], settings: rank.AddressingRankConfig
) -> None:
    """Outcome-agnostic: each published predicate must equal its own arithmetic."""

    for level in canonical["blocks"]["declared-profile"]["levels"].values():
        for name in tree.DECLARED_READINGS + ("descendants",):
            for row in level["measured"]:
                reading = row.get(name)
                if reading is None:
                    continue
                treatment = reading["treatment_response"]
                floor = recompute_floor(reading, settings)
                assert float(reading["floor"]) == pytest.approx(floor, rel=1e-12, abs=0.0)
                if "own_deposit_response" in reading:
                    own = reading["own_deposit_response"]
                    reference = reading["reference_child_deposit"]
                    assert bool(reading["at_the_floor"]) == (
                        treatment is not None and abs(float(treatment)) <= floor
                    )
                    assert bool(reading["present"]) == (
                        treatment is not None and abs(float(treatment)) > floor
                    )
                    assert bool(reading["the_positive_control_fires"]) == (
                        own is not None and abs(float(own)) > floor
                    )
                    children_fraction = reading[
                        "fraction_of_the_childrens_own_deposit"
                    ]
                    if treatment is None or reference in (None, 0.0):
                        assert children_fraction is None
                    else:
                        assert float(children_fraction) == pytest.approx(
                            float(treatment) / abs(float(reference)), rel=1e-12, abs=0.0
                        )
                    parents_fraction = reading["fraction_of_the_parents_own_deposit"]
                    if treatment is None or own in (None, 0.0):
                        assert parents_fraction is None
                    else:
                        assert float(parents_fraction) == pytest.approx(
                            float(treatment) / abs(float(own)), rel=1e-12, abs=0.0
                        )
                    continue
                own = reading["own_response"]
                fraction = reading["fraction_of_the_positive_control"]
                if treatment is None or own in (None, 0.0):
                    assert fraction is None
                else:
                    assert float(fraction) == pytest.approx(
                        float(treatment) / abs(float(own)), rel=1e-12, abs=0.0
                    )
                # a response the declared floor hides is exactly the case the
                # caveat names, and it is never also recorded as present
                if bool(reading["a_nonzero_response_the_declared_floor_hides"]):
                    assert abs(float(treatment)) > float(
                        settings.epsilon_factor
                    ) * abs(float(own))
                    assert floor > abs(float(treatment))
                    assert bool(reading["present"]) is False


def test_every_levels_aggregate_counts_its_own_rows(
    levels: list[Mapping[str, Any]],
) -> None:
    pairs = (
        ("containment", "readings_at_the_floor", "at_the_floor"),
        ("containment", "readings_present", "present"),
        ("containment", "readings_assignment_specific", "assignment_specific"),
        ("containment", "readings_counts_only", "counts_only"),
        ("aggregation", "readings_at_the_floor", "at_the_floor"),
        ("aggregation", "readings_present", "present"),
        ("sibling", "readings_at_the_floor", "at_the_floor"),
        ("sibling", "readings_present", "present"),
        ("descent", "readings_at_the_floor", "at_the_floor"),
        ("descent", "readings_present", "present"),
        ("descendants", "readings_at_the_floor", "at_the_floor"),
        ("descendants", "readings_present", "present"),
    )
    for level in levels:
        measured = level["measured"]
        for family, aggregate, field in pairs:
            aggregate_record = level["readings"][family]
            expected = len(
                [
                    row
                    for row in measured
                    if row.get(family) is not None and bool(row[family][field])
                ]
            )
            assert int(aggregate_record[aggregate]) == expected, (family, aggregate)
        # the measured-triple count every floor predicate is stated against
        assert int(level["readings"]["descendants"]["readings_measured"]) == len(
            [row for row in measured if row.get("descendants") is not None]
        )
        for family in ("containment", "aggregation", "sibling", "descent"):
            assert bool(level["readings"][family]["every_positive_control_fires"]) == (
                all(
                    bool(row[family]["the_positive_control_fires"])
                    for row in measured
                    if row.get(family) is not None
                )
            )


def test_the_published_branch_is_the_branch_the_declared_rule_returns(
    levels: list[Mapping[str, Any]],
) -> None:
    for level in levels:
        readings = level["readings"]
        assert str(readings["branch"]) == tree.level_branch(level, readings)


# --------------------------------------------------------------------------
# the branch is reachable -- including the third one
# --------------------------------------------------------------------------
def test_the_branch_rule_separates_a_floor_reading_from_a_present_one(
    levels: list[Mapping[str, Any]],
) -> None:
    """Perturbing a real reading moves the branch: the rule is not stuck."""

    level = next(
        level
        for level in levels
        if str(level["readings"]["branch"]) == "the_tree_is_decorative"
    )
    readings = json.loads(json.dumps(level["readings"]))
    assert tree.level_branch(level, readings) == "the_tree_is_decorative"
    # a reading present and assignment-specific at every measured triple is the
    # structural branch
    readings["containment"]["readings_at_the_floor"] = 0
    readings["containment"]["readings_present"] = readings["triples_measured"]
    readings["containment"]["readings_assignment_specific"] = readings["triples_measured"]
    assert tree.level_branch(level, readings) == "the_tree_is_structural"
    # reverting the counts returns the original branch
    readings["containment"]["readings_at_the_floor"] = readings["triples_measured"]
    readings["containment"]["readings_present"] = 0
    readings["containment"]["readings_assignment_specific"] = 0
    assert tree.level_branch(level, readings) == "the_tree_is_decorative"


def test_the_third_branch_is_reachable_and_the_receipt_says_why_it_did_not_return(
    levels: list[Mapping[str, Any]],
) -> None:
    """No parent surface exists -- reachable only by a parent with no surface.

    The receipt reports this branch as tested and non-firing because every
    parent's own detail write executes.  The test exercises the branch by taking
    a real level record and removing the parent surface the rule reads, then
    puts it back.
    """

    level = levels[0]
    readings = json.loads(json.dumps(level["readings"]))
    assert tree.level_branch(level, readings) != "no_field_exposed_parent_surface_exists"
    assert bool(readings["every_parent_surface_executes"]) is True
    assert int(readings["parents_with_an_executable_declared_detail_surface"]) == int(
        readings["parents_in_the_level"]
    )
    readings["every_parent_surface_executes"] = False
    assert (
        tree.level_branch(level, readings) == "no_field_exposed_parent_surface_exists"
    )
    readings["parents_in_the_level"] = 0
    assert (
        tree.level_branch(level, readings) == "no_field_exposed_parent_surface_exists"
    )
    for level in levels:
        assert str(level["readings"]["branch"]) != "no_field_exposed_parent_surface_exists"


def test_the_surface_census_is_the_evidence_for_the_third_branch(
    canonical: Mapping[str, Any],
) -> None:
    """Every parent the receipt names has its own detail surface, executed."""

    for _name, record in canonical["blocks"].items():
        by_path = record["surface_table"]["by_path"]
        for level in record["levels"].values():
            for row in level["measured"]:
                parent = str(row["parent_path"])
                assert bool(by_path[parent]["detail_write_executes"]) is True
                assert bool(by_path[parent]["detail_write_accepted"]) is True
                assert bool(by_path[parent]["detail_read_executes"]) is True


# --------------------------------------------------------------------------
# the companion, the descendants reading and the port fallback
# --------------------------------------------------------------------------
def test_the_scale_surface_companion_is_present_and_its_floor_is_named(
    canonical: Mapping[str, Any],
    levels: list[Mapping[str, Any]],
    settings: rank.AddressingRankConfig,
) -> None:
    """The companion's fractions are large; its floor is what hides them."""

    for level in levels:
        measured = level["measured"]
        companion = level["readings"]["companion_scale_surfaces"]
        fractions = [
            abs(float(row["companion_scale_surfaces"]["containment_scale"]["fraction_of_the_positive_control"]))
            for row in measured
            if row["companion_scale_surfaces"]["containment_scale"][
                "fraction_of_the_positive_control"
            ]
            is not None
        ]
        assert fractions, "the companion measured no scale-surface containment"
        assert min(fractions) > float(settings.epsilon_factor)
        assert float(companion["containment_scale_greatest_fraction"]) == pytest.approx(
            max(fractions), rel=1e-12
        )
        hidden = int(companion["readings_where_the_declared_floor_hides_a_nonzero_response"])
        assert hidden == len(
            [
                row
                for row in measured
                if bool(
                    row["companion_scale_surfaces"]["containment_scale"][
                        "a_nonzero_response_the_declared_floor_hides"
                    ]
                )
            ]
        )
        assert hidden > 0
        assert int(companion["containment_scale_present"]) == 0
        # the same responses pass the declared numerical floor alone: the zero
        # present count is the declared finite-difference term's doing
        for row in measured:
            reading = row["companion_scale_surfaces"]["containment_scale"]
            numerical = float(settings.epsilon_factor) * abs(
                float(reading["own_response"])
            )
            assert abs(float(reading["treatment_response"])) > numerical
        # the deposit reading at the same surfaces has no finite-difference term
        # and is published as present, which is what pins the caveat to the
        # probe arms rather than to the scale surfaces in general
        assert int(companion["aggregation_scale_present"]) > 0
        assert float(companion["aggregation_scale_greatest_fraction"]) > 1.0
        verdicts = canonical["reading"]["verdicts"]
        assert bool(
            verdicts["no_scale_surface_response_is_hidden_by_the_declared_floor"]
        ) is False
        assert bool(
            verdicts["the_scale_surface_reading_is_at_the_floor_under_the_declared_rule"]
        ) is False


def test_the_descendants_reading_is_supplementary_and_carries_its_own_floor(
    levels: list[Mapping[str, Any]], settings: rank.AddressingRankConfig
) -> None:
    for level in levels:
        readings = level["readings"]["descendants"]
        measured = [
            row["descendants"] for row in level["measured"] if row.get("descendants")
        ]
        assert int(readings["readings_measured"]) == len(measured)
        for reading in measured:
            assert float(reading["floor"]) == pytest.approx(
                recompute_floor(reading, settings), rel=1e-12, abs=0.0
            )
        assert int(readings["readings_at_the_floor"]) == len(
            [row for row in measured if bool(row["at_the_floor"])]
        )
        assert int(readings["readings_present"]) == len(
            [row for row in measured if bool(row["present"])]
        )
        # the placements the reading could not write are recorded, never hidden
        for row in level["measured"]:
            placements = row["descendant_placements"]
            assert int(placements["executable"]) + len(
                placements["not_a_node_at_this_resolution"]
            ) == 4


def test_a_change_in_the_descendants_reading_does_not_move_the_branch(
    levels: list[Mapping[str, Any]],
) -> None:
    """The supplementary reading is published beside the branch, not inside it."""

    level = levels[-1]
    readings = json.loads(json.dumps(level["readings"]))
    before = tree.level_branch(level, readings)
    readings["descendants"]["readings_present"] = 999
    readings["descendants"]["readings_at_the_floor"] = 0
    assert tree.level_branch(level, readings) == before


def test_the_port_fallback_is_measured_with_the_fields_own_refusal(
    canonical: Mapping[str, Any],
) -> None:
    measured_any = 0
    for _name, record in canonical["blocks"].items():
        by_path = record["surface_table"]["by_path"]
        for level in record["levels"].values():
            readings = level["readings"]["port_fallback"]
            rows = level["port_fallback_measured"]
            assert int(readings["measured"]) == len(rows)
            assert len(rows) <= int(level["port_fallback_cap"])
            if not rows:
                continue
            measured_any += len(rows)
            assert int(level["readings"]["surface_limitation_triples"]) >= len(rows)
            for row in rows:
                assert row["child_item_surfaces"].count(None) >= 1
                for child in row["child_detail_refusals"]:
                    if bool(child["item_surface_exists"]):
                        continue
                    assert "no detail mode" in str(
                        by_path[str(child["path"])]["detail_refusal"]
                    ), child
                containment = row["scale_containment"]
                assert containment["constructed_from_readouts"] is True
                assert bool(containment["at_the_floor"]) == (
                    abs(float(containment["treatment_response"]))
                    <= float(containment["floor"])
                )
    assert measured_any > 0, "the port fallback was never measured"


# --------------------------------------------------------------------------
# the cross-resolution leg
# --------------------------------------------------------------------------
def test_the_cross_resolution_leg_is_matched_and_agrees_with_the_census(
    canonical: Mapping[str, Any],
) -> None:
    cross = canonical["cross_resolution"]
    rows = cross["placement_patterns"]
    assert int(cross["patterns_named_by_either_block"]) == len(rows)
    both = [row for row in rows if len(row["measured_at_resolutions"]) >= 2]
    assert int(cross["patterns_measured_at_both_resolutions"]) == len(both)
    assert both, "no placement pattern was measured at both resolutions"
    expected = all(
        bool(row["the_same_kind_of_reading_at_every_resolution_that_measures_it"])
        for row in both
    )
    assert bool(
        cross["every_pattern_measured_at_both_resolutions_gives_the_same_kind_of_reading"]
    ) == expected
    for row in both:
        assert len(row["measured_at_resolutions"]) == len(
            [entry for entry in row["status_at_each_resolution"].values() if entry["status"] == "measured"]
        )
        # the matched control is the declared readings only, and it can fail: it
        # is recomputed here from the same rows the receipt publishes
        assert tree.placement_matches_across_resolutions(row) is bool(
            row["the_same_kind_of_reading_at_every_resolution_that_measures_it"]
        )
        assert bool(tree.placement_matches_across_resolutions(row))
        assert tree.placement_matches_across_resolutions(
            row, tree.SUPPLEMENTARY_FIELDS
        ) is row["the_same_supplementary_reading_at_every_resolution_that_measures_it"]
        for resolution, entry in row["status_at_each_resolution"].items():
            if entry["status"] != "measured":
                continue
            assert entry["at_counts"] == sorted(entry["at_counts"])
            for measurement in entry["entries"]:
                assert str(measurement["triple_class"]) == "complete"
                assert measurement["children_paths"] == row["children_paths"]
    assert list(cross["the_matched_control_compares"]) == list(tree.MATCHED_FIELDS)
    assert not set(tree.SUPPLEMENTARY_FIELDS) & set(cross["the_matched_control_compares"])
    # the supplementary reading's own cross-resolution difference is published
    # rather than folded into the control, and it names exactly the rows whose
    # supplementary readings differ
    published = cross[
        "patterns_where_the_supplementary_reading_differs_between_resolutions"
    ]
    expected_supplementary_diff = [
        {
            "parent_path": str(row["parent_path"]),
            "measured_at": [int(res) for res in row["measured_at_resolutions"]],
        }
        for row in both
        if row["the_same_supplementary_reading_at_every_resolution_that_measures_it"]
        is False
    ]
    assert [
        {"parent_path": entry["parent_path"], "measured_at": entry["measured_at"]}
        for entry in published
    ] == expected_supplementary_diff
    assert "not " in str(cross["supplementary_reading_scope"])
    # the named parent-surfaces-everywhere patterns are exactly the paths the
    # surface census records as executing at every resolution with a child that
    # does not: two independent parts of the receipt must agree
    named = set(
        cross[
            "patterns_where_the_parent_surface_exists_at_every_resolution_but_a_child_surface_does_not"
        ]
    )
    census = set()
    for row in rows:
        surfaces = row["surfaces_at_each_resolution"]
        if not surfaces or not all(
            bool(entry["parent_detail_write_executes"]) for entry in surfaces.values()
        ):
            continue
        if any(
            not all(bool(value) for value in entry["children_detail_write_executes"].values())
            for entry in surfaces.values()
        ):
            census.add(str(row["parent_path"]))
    assert named == census
    assert named


def test_the_matched_control_fires_on_a_real_row_and_ignores_the_supplementary_reading(
    canonical: Mapping[str, Any],
) -> None:
    """The split is doing work: a declared difference fails it, a supplementary one does not."""

    import copy

    rows = [
        row
        for row in canonical["cross_resolution"]["placement_patterns"]
        if row["the_same_kind_of_reading_at_every_resolution_that_measures_it"] is True
    ]
    assert rows, "no matched pattern agrees, so nothing to perturb"
    row = rows[0]
    resolutions = [
        resolution
        for resolution in sorted(row["status_at_each_resolution"], key=int)
        if row["status_at_each_resolution"][resolution]["status"] == "measured"
    ]
    assert len(resolutions) >= 2
    assert tree.placement_matches_across_resolutions(row) is True
    # a real declared reading moved at one resolution: the control must fire
    broken = copy.deepcopy(row)
    first = broken["status_at_each_resolution"][resolutions[0]]["entries"][0]
    original = bool(first["containment"]["at_the_floor"])
    first["containment"]["at_the_floor"] = not original
    assert tree.placement_matches_across_resolutions(broken) is False
    # the published flag is the row's own, so it is False on the mutated row too
    assert broken["the_same_kind_of_reading_at_every_resolution_that_measures_it"] is True
    # the same move on the supplementary reading only is not a declared difference
    supplementary = copy.deepcopy(row)
    second = supplementary["status_at_each_resolution"][resolutions[0]]["entries"][0]
    second["descendants"]["at_the_floor"] = not bool(
        second["descendants"]["at_the_floor"]
    )
    assert tree.placement_matches_across_resolutions(supplementary) is True
    assert (
        tree.placement_matches_across_resolutions(supplementary, tree.SUPPLEMENTARY_FIELDS)
        is False
    )


def test_the_cross_resolution_status_names_every_unmeasured_pattern(
    canonical: Mapping[str, Any],
) -> None:
    cross = canonical["cross_resolution"]
    for row in cross["placement_patterns"]:
        for resolution, entry in row["status_at_each_resolution"].items():
            assert str(entry["status"]) in {
                "measured",
                "no_parent_surface_at_this_resolution",
                "a_child_surface_does_not_exist_at_this_resolution",
                "not_measured_by_the_declared_cap_or_the_level_count",
            }, (row["parent_path"], resolution, entry["status"])


# --------------------------------------------------------------------------
# the level controls, and the receipt's own digest
# --------------------------------------------------------------------------
def test_a_level_control_can_fail_on_a_real_record(
    canonical: Mapping[str, Any],
    levels: list[Mapping[str, Any]],
) -> None:
    level = levels[0]
    readings = level["readings"]
    assert bool(readings["controls"]["every_zero_work_probe_was_rejected"]) is True
    assert bool(readings["controls"]["every_zero_work_probe_moved_nothing"]) is True
    assert bool(readings["controls"]["every_duplicate_matches_the_single_write"]) is True
    assert bool(readings["controls"]["every_shared_matches_the_single_write"]) is True
    surface_record = next(iter(canonical["blocks"].values()))["surface_table"]

    mutated = json.loads(json.dumps(level))
    mutated["measured"][0]["controls"]["zero_work_moves_nothing"] = False
    mutated_readings = tree.level_readings(mutated, surface_record)
    assert (
        bool(mutated_readings["controls"]["every_zero_work_probe_moved_nothing"]) is False
    )
    assert tree.level_branch(mutated, mutated_readings) == "inconclusive"

    mutated = json.loads(json.dumps(level))
    mutated["measured"][0]["controls"]["duplicate_matches_the_single_write"] = False
    mutated_readings = tree.level_readings(mutated, surface_record)
    assert (
        bool(mutated_readings["controls"]["every_duplicate_matches_the_single_write"])
        is False
    )
    assert tree.level_branch(mutated, mutated_readings) == "inconclusive"


def test_the_receipt_digest_covers_the_measurements(
    canonical: Mapping[str, Any],
) -> None:
    body = {key: value for key, value in canonical.items() if key != "receipt_digest"}
    assert canonical["receipt_digest"] == scale.receipt_digest(body)

    mutated = json.loads(json.dumps(body))
    level = next(
        level
        for record in mutated["blocks"].values()
        for level in record["levels"].values()
    )
    level["measured"][0]["containment"]["treatment_response"] = (
        float(level["measured"][0]["containment"]["treatment_response"]) + 1.0
    )
    assert scale.receipt_digest(mutated) != canonical["receipt_digest"]


def test_the_block_digests_cover_each_block(canonical: Mapping[str, Any]) -> None:
    for _name, record in canonical["blocks"].items():
        body = {key: value for key, value in record.items() if key != "content_digest"}
        assert record["content_digest"] == scale.receipt_digest(body)


# --------------------------------------------------------------------------
# the declared answers
# --------------------------------------------------------------------------
def test_the_receipt_declares_which_readings_carry_the_branch(
    canonical: Mapping[str, Any],
) -> None:
    declared = canonical["declared"]
    readings = declared["readings"]
    assert set(tree.DECLARED_READINGS) == {
        "containment",
        "aggregation",
        "sibling",
        "descent",
    }
    for name in tree.DECLARED_READINGS:
        assert f"R{tree.DECLARED_READINGS.index(name) + 1}_{name}" in readings
    assert "companion_scale" in readings
    assert "cross_resolution" in declared["controls"]
    assert "descendants_supplementary" in declared["controls"]
    assert set(declared["branch_rule"]) == {
        "the_tree_is_structural",
        "the_tree_is_decorative",
        "no_field_exposed_parent_surface_exists",
        "inconclusive",
    }
    text = str(declared["controls"]["cross_resolution"])
    assert "no surface is relabelled" in text
    # the companion's declaration is path-sensitive rather than a blanket false:
    # the root's scale surface is declared family item 0 and the rest are not
    companion = canonical["reading"]["companion_scale_surfaces"]
    assert list(companion["declared_items_among_these_surfaces"]) == ["<root>/scale"]
    assert "root" in str(companion["the_store_declares_these_item_surfaces"])
    assert bool(companion["carries_the_branch"]) is False


def test_the_receipt_carries_the_declared_surface_of_every_reading(
    canonical: Mapping[str, Any],
    levels: list[Mapping[str, Any]],
) -> None:
    """Each reading's field-exposed surface, its addressability and its kind.

    The declaration is one authority, ``capacity.declared_family``'s own item
    list, and it is published beside the numbers rather than assembled from them:
    a reader must be able to see which readings were taken at a declared item
    surface and which were not, without re-deriving the family.
    """

    declared = canonical["declared"]["reading_surfaces"]
    assert set(declared) == set(tree.READING_SURFACES)
    for name, entry in tree.READING_SURFACES.items():
        published = declared[name]
        for field in (
            "taken_at",
            "node_class",
            "declared_item",
            "declared_item_scope",
            "observed",
            "constructed",
            "construction",
            "parameters",
            "carries_the_branch",
        ):
            assert field in published, (name, field)
        assert published["observed"] is False
        assert published["constructed"] is True
        assert str(published["taken_at"]).strip()
        assert str(published["declared_item_scope"]).strip()
    # the four declared readings carry the branch; the companion, the
    # supplementary reading and the port fallback do not
    assert {
        name for name, entry in declared.items() if bool(entry["carries_the_branch"])
    } == {
        "R1_containment",
        "R2_aggregation",
        "R3_sibling",
        "R4_descent",
    }
    # the companion's declared item status is path-sensitive, not a false
    assert declared["companion_scale_containment"]["declared_item"] is None
    assert "root" in str(declared["companion_scale_containment"]["declared_item_scope"])
    assert declared["port_fallback_scale"]["declared_item"] is False
    assert declared["port_fallback_scale"]["node_class"] == "single_port_node"
    # each published reading carries its own row of the table
    seen = {name: 0 for name in tree.READING_SURFACES}
    for level in levels:
        for row in level["measured"]:
            for key in (
                "containment",
                "aggregation",
                "sibling",
                "descent",
                "descendants",
            ):
                reading = row.get(key)
                if reading is None:
                    continue
                name = str(reading["reading"])
                assert name in tree.READING_SURFACES, (row["parent_path"], key, name)
                assert str(reading["taken_at"]) == str(
                    tree.READING_SURFACES[name]["taken_at"]
                )
                assert str(reading["node_class"]) == str(
                    tree.READING_SURFACES[name]["node_class"]
                )
                assert reading["declared_item"] == tree.READING_SURFACES[name][
                    "declared_item"
                ]
                assert reading["observed"] is False
                assert bool(reading["carries_the_branch"]) is bool(
                    tree.READING_SURFACES[name]["carries_the_branch"]
                )
                seen[name] += 1
            for key in ("containment_scale", "aggregation_scale"):
                reading = row["companion_scale_surfaces"].get(key)
                if reading is None:
                    continue
                name = str(reading["reading"])
                assert name in tree.READING_SURFACES
                assert bool(reading["carries_the_branch"]) is False
                seen[name] += 1
        for row in level.get("port_fallback_measured", []):
            reading = row["scale_containment"]
            assert str(reading["reading"]) == "port_fallback_scale"
            assert bool(reading["carries_the_branch"]) is False
            assert reading["declared_item"] is False
            seen["port_fallback_scale"] += 1
    assert all(count > 0 for count in seen.values()), seen
    # the blocks carry the same declaration, so a block is readable on its own
    for record in canonical["blocks"].values():
        assert {
            name: entry["declared_item"]
            for name, entry in record["reading_surfaces"].items()
        } == {
            name: entry["declared_item"] for name, entry in tree.READING_SURFACES.items()
        }


def addressability_disagreements(record: Mapping[str, Any]) -> list[str]:
    """Every probed surface whose published labels disagree with the family.

    The family is re-derived here from ``capacity.declared_family`` at the
    block's own port count, so the check does not consult the runner's answer.
    """

    family = {
        (str(spec.path), str(spec.component))
        for spec in capacity.declared_family(int(record["profile"]["port_count"]))[
            "specs"
        ]
    }
    bad: list[str] = []
    for path, entry in record["surface_table"]["rows"].items():
        for key in ("detail", "scale"):
            surface = entry[key]
            if bool(surface["declared_family_item"]) is not (
                (str(path), key) in family
            ):
                bad.append(f"{path or '<root>'}/{key}: declared_family_item")
            if int(surface["node_class"] == "single_port_node") != int(
                int(entry["node_size"]) == 1
            ):
                bad.append(f"{path or '<root>'}/{key}: node_class")
    return bad


def test_every_published_surface_agrees_with_the_declared_family(
    canonical: Mapping[str, Any],
) -> None:
    """The addressability authority is `capacity.declared_family`, applied live.

    The published flag is re-derived here from the family itself at each block's
    own port count, so a surface cannot be labelled a declared item because the
    runner happens to expect it: the root's scale mode is family item 0, the
    root's detail mode is family item 1, every interior detail below them is an
    item, and no scale surface below the root and no single-port node is.  The
    check is exercised on a mutated copy of a real block, so it is shown to be
    able to fail rather than to agree by construction.
    """

    import copy

    for _name, record in canonical["blocks"].items():
        port_count = int(record["profile"]["port_count"])
        family = {
            (str(spec.path), str(spec.component))
            for spec in capacity.declared_family(port_count)["specs"]
        }
        assert ("", "scale") in family
        assert ("", "detail") in family
        # every probed surface carries its own addressability beside its outcome
        rows = record["surface_table"]["rows"]
        assert addressability_disagreements(record) == []
        assert len(rows) > 0
        root = rows[""]
        assert bool(root["detail"]["declared_family_item"]) is True
        assert bool(root["scale"]["declared_family_item"]) is True
        non_root = [entry for path, entry in rows.items() if path != ""]
        assert non_root
        assert all(
            bool(entry["scale"]["declared_family_item"]) is False for entry in non_root
        )
        assert all(
            bool(entry["detail"]["declared_family_item"]) is True
            for entry in non_root
            if int(entry["node_size"]) > 1
        )
        # the check fires on a real record with one label moved
        broken = copy.deepcopy(record)
        broken["surface_table"]["rows"][""]["scale"]["declared_family_item"] = False
        assert addressability_disagreements(broken) == ["<root>/scale: declared_family_item"]
        # and the refusals are the field's own, at the surfaces the family refuses
        by_path = record["surface_table"]["by_path"]
        assert by_path
        for path, entry in by_path.items():
            if int(rows[path]["node_size"]) <= 1:
                assert bool(entry["detail_write_executes"]) is False
                assert "no detail mode" in str(entry["detail_refusal"])
        for level in record["levels"].values():
            for row in level["measured"]:
                parent = str(row["parent_path"])
                parent_surface = row["surfaces"]["parent"]
                assert parent_surface["component"] == "detail"
                assert bool(parent_surface["declared_family_item"]) is True
                for child in row["surfaces"]["children"]:
                    assert child["component"] == "detail"
                    assert bool(child["declared_family_item"]) is True
                # the root's scale surface is the one scale surface the family
                # addresses; every other one is field-exposed and undeclared
                scale = row["surfaces"]["parent_scale"]
                assert bool(scale["declared_family_item"]) is (parent == "")
                assert str(scale["addressability"]) == "interior_node"


def test_the_tree_receipts_are_content_stable(canonical: Mapping[str, Any]) -> None:
    """Re-merging the same blocks reproduces the same receipt, digest included."""

    blocks = {
        name: json.loads(Path(path).read_text(encoding="utf-8"))
        for name, path in BLOCK_PATHS.items()
    }
    rebuilt = tree.merge_blocks(blocks)
    assert rebuilt["receipt_digest"] == canonical["receipt_digest"]
    assert rebuilt["reading"]["branch"] == canonical["reading"]["branch"]
