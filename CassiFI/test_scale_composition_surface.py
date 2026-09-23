"""Direct tests for the scale-composition-surface runner.

They hold the runner to the properties its receipt claims, without running the
store: the structural controls it builds are the strict ones it declares -- the
shuffled-parent control is refused where the field's own helper picks an ancestor
or a descendant, the non-ancestor control is never an ancestor, a descendant or an
equal parent, and the placement null is a non-sibling pair that can never be one
parent's two children -- and the branch rule never reads a missing arm, a vacuous
zero or an unmeasured comparison as evidence for either surface.

The tree the controls are built against is the field's own (``capacity``'s
declared profile), so a passing run is evidence about the real measurement's
controls rather than about a fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import run_scale_composition_surface as surface
import run_store_addressing_capacity as capacity
import run_store_addressing_tree as tree

RECEIPT = Path("_diag/scale-composition-surface/exploration.json")


@pytest.fixture(scope="module")
def level():
    """The declared profile's tree and its measured triples, as the runner uses them."""

    profile, _record = capacity.resolution_profile(4)
    sizes = {
        str(row["path"]): int(row["size"])
        for row in capacity.dyadic_nodes(int(profile.port_count))
    }
    depths = sorted(
        {int(row["depth"]) for row in capacity.dyadic_nodes(int(profile.port_count))}
    )
    catalogue = tree.level_catalogue(int(profile.port_count), 28)
    triples = catalogue["triples"]
    positions = tree.selected_triples(triples, surface.MEASURED_TRIPLE_CAP)
    return {
        "port_count": int(profile.port_count),
        "sizes": sizes,
        "depths": depths,
        "triples": triples,
        "positions": positions,
    }


def row(position: int, **overrides) -> dict:
    """One measured row with the fields the branch rule reads, and nothing else."""

    built = {
        "position": int(position),
        "arms": {"an_arm": {"differences": {"a_difference": 1.0}}},
        "flat_null": {
            "source": "non_sibling_pair_outside_the_subtree",
            "size_multiset_matched_to_the_children": True,
            "the_nodes_are_not_the_treated_parents_children": True,
            "the_pair_is_never_a_single_parents_children": True,
        },
        "readings": {},
    }
    built.update(overrides)
    return built


def scale_reading(**overrides) -> dict:
    record = {
        "the_shape": "plateau_above_the_numerical_term",
        "the_structural_separation": {
            "difference_from_the_structural_control": 1.0,
            "exceeds_the_numerical_term": True,
            "exceeds_the_measured_floor": True,
            "exceeds_the_comparison_floor": True,
        },
        "the_structural_control_exists": True,
        "the_positive_control_fires": True,
        "the_flat_null_exists": True,
    }
    record.update(overrides)
    return record


def count_reading(**overrides) -> dict:
    record = {
        "the_shape": "no_sweep_declared_for_this_path",
        "the_count_matters_at_a_constant_total_budget": True,
        "the_count_does_not_matter_at_a_constant_total_budget": False,
        "the_placement_matters": False,
        "the_placement_does_not_matter": True,
        "the_positive_control_fires": True,
    }
    record.update(overrides)
    return record


def branch(rows: list[dict], port_rows: list[dict] | None = None):
    return surface.level_branch(rows, port_rows or [], {})


def test_the_shuffled_control_refuses_a_cross_depth_choice(level) -> None:
    """The helper's own fallback is refused: at the root it picks a descendant."""

    ambiguous = level["triples"][level["positions"][0]]
    chosen = tree.shuffled_parent(level["triples"], level["positions"][0])
    accepted, record = surface.matched_shuffled(
        chosen,
        str(ambiguous["parent"]["path"]),
        int(ambiguous["parent"]["depth"]),
    )
    assert accepted is None, "a descendant is not a shuffled parent"
    assert record["accepted"] is False
    assert record["same_depth"] is False
    assert record["neither_ancestor_nor_descendant"] is False

    same_depth = level["triples"][level["positions"][1]]
    chosen = tree.shuffled_parent(level["triples"], level["positions"][1])
    accepted, record = surface.matched_shuffled(
        chosen,
        str(same_depth["parent"]["path"]),
        int(same_depth["parent"]["depth"]),
    )
    assert accepted is not None
    assert record["accepted"] is True and record["same_depth"] is True
    assert record["neither_ancestor_nor_descendant"] is True
    assert int(accepted["parent"]["depth"]) == int(same_depth["parent"]["depth"])


def test_the_non_ancestor_control_is_never_an_ancestor_a_descendant_or_equal(
    level,
) -> None:
    sizes = level["sizes"]
    for position in level["positions"]:
        triple = level["triples"][position]
        parent_path = str(triple["parent"]["path"])
        descendants = triple["descendants"]
        treatment = [
            descendants[0],
            descendants[2] if len(descendants) > 2 else descendants[0],
        ]
        unrelated, control = surface.unrelated_descendants(
            level["triples"],
            parent_path,
            template=treatment,
            count=len(treatment),
            sizes=sizes,
        )
        if unrelated is None:
            assert control == []
            continue
        other = str(unrelated["parent"]["path"])
        assert other != parent_path
        assert not other.startswith(parent_path)
        assert not parent_path.startswith(other)
        assert len(control) == len(treatment)
        assert sorted(
            (str(record["node_class"]), int(sizes.get(str(record["path"]), 0)))
            for record in control
        ) == sorted(
            (str(record["node_class"]), int(sizes.get(str(record["path"]), 0)))
            for record in treatment
        )


def test_the_placement_null_is_never_a_siblings_or_the_parents_children(level) -> None:
    sizes = level["sizes"]
    root = level["triples"][level["positions"][0]]
    pair, depth = surface.flat_null_pair(
        level["port_count"],
        parent_path=str(root["parent"]["path"]),
        child_paths=[str(child["path"]) for child in root["children"]],
        child_sizes=[int(root["parent"]["size"]) // 2] * 2,
        sizes=sizes,
        depths=level["depths"],
        min_size=1,
    )
    assert pair == [] and depth is None, "the root's subtree is the whole tree"

    deepest = level["triples"][level["positions"][-1]]
    sizes_of_children = [
        int(sizes.get(str(child["path"]), 0)) for child in deepest["children"]
    ]
    pair, depth = surface.flat_null_pair(
        level["port_count"],
        parent_path=str(deepest["parent"]["path"]),
        child_paths=[str(child["path"]) for child in deepest["children"]],
        child_sizes=sizes_of_children,
        sizes=sizes,
        depths=level["depths"],
        min_size=1,
    )
    if not pair:
        pytest.skip("this level's tree holds no matched non-sibling pair")
    assert len(pair) == 2
    paths = [str(record["path"]) for record in pair]
    assert sorted(int(sizes.get(path, 0)) for path in paths) == sorted(
        sizes_of_children
    )
    for path in paths:
        assert path not in {
            str(child["path"]) for child in deepest["children"]
        }, "the null is never the treated parent's own children"
        assert not path.startswith(str(deepest["parent"]["path"]))
    assert paths[0][:-1] != paths[1][:-1], "the two are never siblings of each other"


def test_a_missing_control_is_never_read_as_evidence() -> None:
    """An absent arm, and a present treatment with no measured control, vote nothing."""

    uncontrolled = [
        row(
            index,
            readings={
                "R-B_x": scale_reading(the_structural_control_exists=False)
            },
        )
        for index in range(2)
    ]
    verdict, reason, predicates = branch(uncontrolled)
    assert verdict == "inconclusive"
    assert (
        predicates[
            "rows_where_the_scale_path_carries_a_declared_sweep_and_a_control"
        ]
        == 0
    )
    assert "untested" in reason

    absent = [
        row(index, readings={"R-B_x": scale_reading(the_shape="not_measured")})
        for index in range(3)
    ]
    verdict, reason, predicates = branch(absent)
    assert verdict == "inconclusive", "an unbuilt treatment is not 'no response'"
    assert predicates["the_sweep_shapes_seen"] == ["not_measured"]
    assert "vacuous" in reason


def test_the_composition_branch_needs_presence_separation_and_the_count_test() -> None:
    rows = [
        row(
            index,
            readings={
                "R-B_x": scale_reading(),
                "R-D_x": count_reading(),
            },
        )
        for index in range(2)
    ]
    verdict, reason, predicates = branch(rows)
    assert verdict == "the_scale_surface_composes_from_its_children"
    assert (
        predicates[
            "rows_where_the_scale_path_carries_a_declared_sweep_and_a_control"
        ]
        == 2
    )
    assert predicates["rows_where_that_reading_separates_from_its_control"] == 2
    assert "not the same response as one child written at twice it" in reason
    assert "plateau above the numerical term" in reason


def test_a_sweep_that_keeps_climbing_is_named_a_budget_artifact() -> None:
    """A reading that rises at every declared budget is named, not read for magnitude."""

    rows = [
        row(
            index,
            readings={
                "R-B_x": scale_reading(the_shape="still_climbing_with_the_drive"),
                "R-D_x": count_reading(
                    the_count_matters_at_a_constant_total_budget=False,
                    the_count_does_not_matter_at_a_constant_total_budget=True,
                    the_placement_matters=False,
                    the_placement_does_not_matter=True,
                ),
            },
        )
        for index in range(2)
    ]
    verdict, reason, predicates = branch(rows)
    assert verdict == "the_scale_surface_is_a_magnitude_surface"
    assert (
        predicates["the_sweep"]["rows_whose_sweep_keeps_climbing_with_the_drive"] == 2
    )
    assert predicates["the_sweep_shapes_seen"] == ["still_climbing_with_the_drive"]


def test_a_silent_sweep_is_not_measurable_and_is_not_an_absent_reading() -> None:
    """Every declared point under the numerical term: silent, and bounded by it."""

    rows = [
        row(index, readings={"R-B_x": scale_reading(the_shape="under_the_numerical_term")})
        for index in range(2)
    ]
    verdict, reason, predicates = branch(rows)
    assert verdict == "not_measurable_in_this_path"
    assert (
        predicates["the_sweep"]["rows_whose_sweep_is_under_the_numerical_term"] == 2
    )
    assert "numerical term" in reason


def test_the_declared_budget_sweep_publishes_both_floor_terms_separately() -> None:
    """The two terms of the declared rule are published apart, never folded into one."""

    arms = {
        "children_scale_home": {"greatest_difference": 1.0},
        "children_scale_sweep_0p25": {"greatest_difference": 0.25},
        "children_scale_sweep_0p5": {"greatest_difference": 0.5},
        "children_scale_sweep_1p0": {"greatest_difference": 1.0},
        "children_scale_sweep_2p0": {"greatest_difference": 2.0},
        "children_scale_sweep_4p0": {"greatest_difference": 2.0},
        "parent_scale_own_sweep_0p25": {"greatest_difference": 1.0},
        "parent_scale_own_sweep_0p5": {"greatest_difference": 1.0},
        "parent_scale_own_sweep_1p0": {"greatest_difference": 1.0},
        "parent_scale_own_sweep_2p0": {"greatest_difference": 1.0},
        "parent_scale_own_sweep_4p0": {"greatest_difference": 1.0},
    }
    sweep = surface.budget_sweep(
        arms,
        treatment_prefix="children_scale_sweep",
        own_prefix="parent_scale_own_sweep",
        epsilon_factor=1e-9,
        floor_factor=10.0,
        write_budget=8.0,
    )
    assert sweep["the_shape"] == "plateau_above_the_numerical_term"
    assert sweep["the_shape_is_evidence"] is True
    plateau = sweep["the_plateau"]
    assert plateau["from_budget_multiple"] == 2.0
    assert plateau["numerical_term_compared_with"] == pytest.approx(1e-9)
    assert plateau["the_declared_rule_admits_the_plateau"] is True
    for point in sweep["points"]:
        terms = point["the_two_floor_terms"]
        assert set(terms) == {
            "half_budget_difference_times_the_factor",
            "numerical_term_epsilon_times_the_own_response",
        }
        assert isinstance(terms["half_budget_difference_times_the_factor"], (float, type(None)))
        assert point["the_binding_term_at_this_point"] in {
            None,
            "floor_factor_times_the_half_budget_difference",
            "epsilon_factor_times_the_own_response",
        }
    assert any(
        point["the_rule_admits_at_this_point"] is False for point in sweep["points"]
    ), "the declared rule must reject the climbing points rather than be vacuous"


def test_a_reading_that_scales_with_the_drive_can_never_clear_the_declared_rule() -> None:
    """The rule is worked out on paper: scaling is rejected by construction, not absence."""

    arms = {
        "children_scale_sweep_0p25": {"greatest_difference": 0.25},
        "children_scale_sweep_0p5": {"greatest_difference": 0.5},
        "children_scale_sweep_1p0": {"greatest_difference": 1.0},
        "children_scale_sweep_2p0": {"greatest_difference": 2.0},
        "children_scale_sweep_4p0": {"greatest_difference": 4.0},
        "parent_scale_own_sweep_0p25": {"greatest_difference": 1.0},
        "parent_scale_own_sweep_0p5": {"greatest_difference": 1.0},
        "parent_scale_own_sweep_1p0": {"greatest_difference": 1.0},
        "parent_scale_own_sweep_2p0": {"greatest_difference": 1.0},
        "parent_scale_own_sweep_4p0": {"greatest_difference": 1.0},
    }
    sweep = surface.budget_sweep(
        arms,
        treatment_prefix="children_scale_sweep",
        own_prefix="parent_scale_own_sweep",
        epsilon_factor=1e-9,
        floor_factor=10.0,
        write_budget=8.0,
    )
    assert sweep["the_shape"] == "still_climbing_with_the_drive"
    assert sweep["the_shape_is_a_budget_artifact"] is True
    assert (
        sweep["the_shape_says_the_declared_rule_rejects_this_reading_by_construction"]
        is True
    )
    assert sweep["the_plateau"] is None
    assert all(
        point["the_rule_admits_at_this_point"] is False
        for point in sweep["points"][1:]
    ), "a reading that halves when the drive halves cannot clear the half-budget term"


def test_an_equal_count_test_alone_does_not_make_a_composition_verdict() -> None:
    """Present and controlled, but the same total work placed as one child agrees."""

    rows = [
        row(
            index,
            readings={
                "R-B_x": scale_reading(),
                "R-D_x": count_reading(
                    the_count_matters_at_a_constant_total_budget=False,
                    the_count_does_not_matter_at_a_constant_total_budget=True,
                    the_placement_matters=False,
                    the_placement_does_not_matter=True,
                ),
            },
        )
        for index in range(2)
    ]
    verdict, reason, _predicates = branch(rows)
    assert verdict == "the_scale_surface_is_a_magnitude_surface"
    assert "how much and not which or how many children" in reason


def test_a_nonfinite_arm_makes_the_level_inconclusive() -> None:
    rows = [
        row(
            index,
            arms={"an_arm": {"differences": {"a_difference": float("nan")}}},
            readings={"R-B_x": scale_reading(), "R-D_x": count_reading()},
        )
        for index in range(2)
    ]
    verdict, reason, predicates = branch(rows)
    assert verdict == "inconclusive"
    assert predicates["every_arm_is_finite"] is False
    assert "non-finite" in reason


def test_the_runner_refuses_to_measure_if_a_pinned_artifact_moved() -> None:
    pins = surface.check_pins()
    assert pins["every_declaration_matches_its_pin"] is True
    found = {row["artifact"]: row["found"] for row in pins["checked"]}
    assert (
        found["run_store_addressing_tree.py"] == surface.PINNED_TREE_RUNNER_SHA256
    )
    for name, (path, digest) in surface.PINNED_TREE_BLOCK_DIGESTS.items():
        assert found[str(path)] == digest, name
    assert (
        found[str(surface.PINNED_TREE_RECEIPT_PATH)]
        == surface.PINNED_TREE_RECEIPT_DIGEST
    )


def test_the_merged_receipt_names_the_suppressing_term_at_every_level() -> None:
    if not RECEIPT.exists():
        pytest.skip("the merged receipt has not been produced in this checkout")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    measured = [row for row in receipt["table"] if row.get("constructible")]
    assert measured, "the merged receipt holds no measured level"
    assert set(receipt["branch_counts"]) == set(surface.BRANCHES)
    for row in measured:
        assert row["branch"] in surface.BRANCHES
        scope = row.get("sweep_shape_by_path") or {}
        assert "R-B_childrens_own_scale_surfaces" in scope
        assert row.get("count_test_separates") in (True, False)
    serialized = json.dumps(receipt)
    assert "proportional" not in serialized.lower(), (
        "the receipt must not carry the word the declared rule rejects by construction"
    )
    assert "\"present\": true" not in serialized.replace(" ", "").lower()
