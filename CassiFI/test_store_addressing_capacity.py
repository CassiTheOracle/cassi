"""Tests for the store addressing capacity measurement.

The whole file is cheap by construction: the declared family rule, its census and
its orthogonality are read from the field's own pure mode rule, the boundary is
measured with a handful of owner writes, and the delivered receipt is checked by
recomputing its own content digest. The sweep's own arms cost minutes per level
and are not re-run here; what is re-run is every predicate that has to keep
holding: the rule's head identity with the delivered item list, the install and
restore of the extended list, the field's own refusals at the boundary, and the
per-level controls the receipt publishes.

Every can-fail check mutates a real measurement rather than a fixture: the
refusal checks call the field with a leaf path and a path beyond a leaf, the
restore check addresses an item the delivered list does not have, and the digest
check recomputes the receipt's own digest from its own body.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Mapping

import pytest

import run_fractal_durability_exploration as durability
import run_memory_consumer_path as consumer
import run_memory_store_scale as scale
import run_store_addressing_capacity as capacity
import run_store_addressing_rank as rank

RECEIPT_PATH = capacity.RECEIPT_PATH


@pytest.fixture(scope="module")
def canonical() -> dict[str, Any]:
    # The documented run order is runner first, then pytest, so an absent receipt
    # fails here with the commands that produce it rather than reading as a broken
    # harness in a tree where the runners have simply not been run.
    assert RECEIPT_PATH.exists(), (
        f"the merged receipt {RECEIPT_PATH} is missing; produce it from CassiFI with "
        "`python run_store_addressing_capacity.py --block declared-profile`, "
        "`python run_store_addressing_capacity.py --block higher-resolution`, then "
        "`python run_store_addressing_capacity.py --block merge`"
    )
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def family28() -> dict[str, Any]:
    return capacity.declared_family(28)


# --------------------------------------------------------------------------
# the declared rule itself
# --------------------------------------------------------------------------
def test_the_declared_rule_reproduces_the_delivered_item_list(
    family28: Mapping[str, Any],
) -> None:
    specs = family28["specs"]
    assert len(specs) == 28
    assert family28["head_matches_the_delivered_item_specs"] is True
    for index, delivered in enumerate(durability.ITEM_SPECS):
        spec = specs[index]
        assert (spec.name, spec.path, spec.component) == (
            delivered.name,
            delivered.path,
            delivered.component,
        )
        assert tuple(spec.flow_signal) == tuple(delivered.flow_signal)


def test_the_declared_family_is_the_port_count_at_every_resolution() -> None:
    for ports_per_pool in (4, 8, 16):
        port_count = 7 * ports_per_pool
        family = capacity.declared_family(port_count)
        assert len(family["specs"]) == port_count
        assert family["nodes"] == 2 * port_count - 1
        assert family["leaves"] == port_count
        assert len(family["refusals"]) == port_count
        assert all(int(row["size"]) == 1 for row in family["refusals"])
        assert sum(int(value) for value in family["depths"].values()) == port_count


def test_the_declared_family_is_orthonormal_at_the_measured_floor(
    family28: Mapping[str, Any],
) -> None:
    reading = capacity.family_orthogonality(28, family28["specs"])
    assert reading["items"] == 28
    assert reading["mode_norms_min"] == pytest.approx(1.0, abs=1e-12)
    assert reading["mode_norms_max"] == pytest.approx(1.0, abs=1e-12)
    assert reading["the_declared_family_is_orthonormal_at_the_measured_floor"] is True
    assert reading["greatest_absolute_off_diagonal_gram_entry"] <= 1e-12


def test_the_declared_rule_stops_only_at_its_own_leaves(
    family28: Mapping[str, Any],
) -> None:
    """The rule's own boundary is a leaf, and nothing else is refused."""

    sizes = {str(row["path"]): int(row["size"]) for row in capacity.dyadic_nodes(28)}
    for spec in family28["specs"]:
        if spec.path:
            assert sizes[spec.path] >= 2
    for row in family28["refusals"]:
        assert sizes[str(row["path"])] == 1
    # the first depth-4 candidate in the rule's own order is a leaf, so the count
    # the rule can address stops strictly below the number of tree nodes
    first_depth_four = next(
        row for row in capacity.dyadic_nodes(28) if int(row["depth"]) == 4
    )
    assert int(first_depth_four["size"]) == 1
    assert str(first_depth_four["path"]) == "LLLL"


# --------------------------------------------------------------------------
# the install the sweep relies on
# --------------------------------------------------------------------------
def test_the_extended_list_reaches_the_delivered_instruments_and_is_restored(
    family28: Mapping[str, Any],
) -> None:
    delivered = tuple(durability.ITEM_SPECS)
    extended = tuple(family28["specs"][:12])
    assert len(delivered) == capacity.DELIVERED_ITEM_COUNT
    with capacity.family_installed(extended):
        assert tuple(durability.ITEM_SPECS) == extended
        settings = capacity.level_settings(12)
        names = [spec.name for spec in extended]
        assert settings.as_dict()["item_names"] == names
        for index in range(12):
            assert rank.placement_spec(index, "specific", settings).name == names[index]
        assert rank.placement_spec(0, "shared", settings).name == names[0]
        assert rank.placement_spec(1, "duplicate", settings).name == names[0]
    assert tuple(durability.ITEM_SPECS) == delivered
    # the same address outside the install must fail: the extension is what makes
    # the twelfth item addressable, so this predicate is not vacuous
    with pytest.raises(IndexError):
        rank.placement_spec(11, "specific", capacity.level_settings(8))


# --------------------------------------------------------------------------
# the boundary, on the real surface
# --------------------------------------------------------------------------
def test_the_field_refuses_a_leaf_detail_and_a_path_beyond_a_leaf() -> None:
    profile = scale.flat_profile()
    assert int(profile.port_count) == 28
    owner, home = consumer.open_owner(profile, prefix="capacity-test-")
    try:
        blank = float(
            scale.plain(
                owner.read_packet_deposit(path="", component="scale", flow_signal=[1.0, 0.0])
            )["recovered_deposit"]
        )
        assert blank == 0.0
        accepted = scale.plain(
            owner.write_packet_impulse(
                "capacity-test:accepted",
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
def test_the_receipt_publishes_the_declared_rule_and_its_inventory(
    canonical: Mapping[str, Any],
) -> None:
    assert canonical["schema"] == capacity.SCHEMA
    inventories = {
        str(record["resolution"]): record["inventory"]
        for record in canonical["blocks"].values()
    }
    assert set(inventories) == {"4", "8"}
    assert int(inventories["4"]["addressable_count"]) == 28
    assert int(inventories["8"]["addressable_count"]) == 56
    for record in canonical["blocks"].values():
        assert record["inventory"]["the_addressable_count_is_the_port_count"] is True
        assert record["inventory"]["head_matches_the_delivered_item_specs"] is True
        assert record["delivered_item_list_restored"] is True
        orthogonality = record["census"]["orthogonality"]
        assert (
            orthogonality["greatest_absolute_off_diagonal_gram_entry"]
            <= 1e-12
        )
        outcomes = [str(row["outcome"]) for row in record["inventory"]["boundary"]]
        assert any("no detail mode" in text for text in outcomes), outcomes
        assert any("descends beyond a leaf" in text for text in outcomes), outcomes


def test_every_declared_level_is_accounted_for_by_the_blocks(
    canonical: Mapping[str, Any],
) -> None:
    """Every declared level ran, was cut, or was refused -- and the receipt says which."""

    declared = {4: {8, 16, 24, 28, 32}, 8: {32}}
    for name, record in canonical["blocks"].items():
        resolution = int(record["resolution"])
        run = {int(n) for n in record["points_run"]}
        cut = {int(row["n"]) for row in record["points_not_run"]}
        refused = {int(row["n"]) for row in record["points_not_constructible"]}
        assert run == {int(n) for n in record["counts_attempted"]} - cut - refused
        assert not (run & cut) and not (run & refused) and not (cut & refused)
        assert run | cut | refused == declared[resolution], (name, run, cut, refused)
        assert run, f"the block {name} ran no level at all"
        for row in record["points_not_run"]:
            assert str(row["reason"]).strip()
        for row in record["points_not_constructible"]:
            assert str(row["reason"]).strip()
        # the levels whose arms are cheapest come first, so a surviving budget
        # cannot have cut them: their absence would be a real shortfall
        if resolution == 4:
            assert {8, 16} <= run
        else:
            assert 32 in run
    # every declared level is in the published table exactly once per resolution
    published = [(int(row["n"]), int(row["resolution"])) for row in canonical["table"]]
    assert len(published) == len(set(published))


def test_every_measured_level_publishes_its_controls_and_consistent_readings(
    canonical: Mapping[str, Any],
) -> None:
    """Outcome-agnostic: each row's booleans must equal its own numbers."""

    rows = [row for row in canonical["table"] if bool(row["constructible"])]
    assert rows, "the sweep published no measured level"
    for row in rows:
        n = int(row["n"])
        # the statistic's own bookkeeping
        assert row["the_specific_arm_is_full_rank"] == (int(row["rank"]) == n)
        assert row["the_margin_exceeds_one"] == (
            float(row["margin_smallest_singular_value_against_tolerance"]) > 1.0
        )
        assert row["the_least_separation_reaches_the_predicted_value"] == (
            row["least_item_separation"] is not None
            and float(row["least_item_separation"])
            >= 1.0 - float(rank.LOSS_ALLOWANCE)
        )
        assert int(row["pairs_measured"]) == n * (n - 1)
        assert 0 <= int(row["pairs_above_the_contrast_floor"]) <= n * (n - 1)
        assert float(row["measured_finite_difference_floor"]) > 0.0
        assert float(row["tolerance"]) >= float(row["measured_finite_difference_floor"])
        assert float(row["smallest_singular_value"]) <= float(row["largest_singular_value"])
        assert int(row["hold_ticks"]) == int(rank.HOLD_TICKS)
        assert float(row["probe_budget"]) == float(rank.PROBE_BUDGET)
        assert float(row["measured_deposit_total_energy"]) > 0.0
        # the control booleans must equal their own numbers
        assert row["the_duplicate_arm_has_rank_one_below_the_item_count"] == (
            int(row["duplicate_rank"]) == n - 1
        )
        assert row["the_shared_arm_is_rank_one"] == (int(row["shared_rank"]) == 1)
        assert row["the_zero_work_probe_moves_nothing"] == (
            float(row["zero_work_probe_greatest_response"]) == 0.0
        )
        assert row["the_blank_page_reads_nothing"] == (
            float(row["blank_page_greatest_read"]) == 0.0
        )
        # the declared controls fire at every measured level: the duplicate
        # placement costs exactly one dimension, the shared placement carries one
        # direction, the zero-work probe is refused and moves nothing, and a blank
        # page reads nothing.  These are the declared operating semantics, not the
        # sweep's outcome, so they are required wherever a level ran.
        assert int(row["duplicate_rank"]) == n - 1
        assert float(row["duplicated_pair_separation"]) <= float(rank.CONTRAST_FLOOR)
        assert int(row["shared_rank"]) == 1
        assert bool(row["shared_arm_separates_no_pair"]) is True
        assert bool(row["zero_work_probes_are_rejected"]) is True
        assert float(row["zero_work_probe_greatest_response"]) == 0.0
        assert float(row["blank_page_greatest_read"]) == 0.0
        assert bool(row["the_blank_page_reads_nothing"]) is True


def test_the_structural_boundary_is_recorded_as_a_refusal_not_a_rank_failure(
    canonical: Mapping[str, Any],
) -> None:
    """The count the 28-port family cannot reach is published as a refusal.

    The structural probe costs no arm -- it is the inventory's own count and the
    stack's own error text -- so it is expected at the delivered resolution; if a
    block's declared budget cut it, the block must say so instead of leaving the
    boundary unrecorded.
    """

    block = canonical["blocks"]["declared-profile"]
    cut = {int(row["n"]) for row in block["points_not_run"]}
    if 32 in cut:
        assert all(
            str(row["reason"]).strip() for row in block["points_not_run"] if int(row["n"]) == 32
        )
        return
    rows = {int(row["n"]): row for row in canonical["table"] if int(row["resolution"]) == 4}
    assert 32 in rows
    structural = rows[32]
    assert bool(structural["constructible"]) is False
    assert int(structural["addressable_count"]) == 28
    assert int(structural["declared_family_size"]) == 28
    assert int(structural["n"]) == 32
    boundary = structural["boundary"]
    assert any("no detail mode" in str(row["outcome"]) for row in boundary), boundary
    assert any(
        str(row["path"]) == "LLLL" for row in boundary
    ), "the boundary probe must name the rule's own first refused leaf path"


def test_the_ceiling_branch_follows_only_the_published_numbers(
    canonical: Mapping[str, Any],
) -> None:
    ceiling = canonical["ceiling"]
    branch = str(ceiling["branch"])
    assert branch in {
        "capacity-tracks-the-declared-scale-tree",
        "capacity-is-dynamical",
        "smooth-degradation-with-no-ceiling",
        "mixed",
    }, branch
    constructible = [row for row in canonical["table"] if bool(row["constructible"])]
    healthy = [
        row
        for row in constructible
        if bool(row["the_specific_arm_is_full_rank"])
        and float(row["margin_smallest_singular_value_against_tolerance"]) > 1.0
        and bool(row["the_least_separation_reaches_the_predicted_value"])
    ]
    inventories = {
        int(record["resolution"]): int(record["inventory"]["addressable_count"])
        for record in canonical["blocks"].values()
    }
    assert inventories == {4: 28, 8: 56}
    if branch == "capacity-tracks-the-declared-scale-tree":
        # the declared reading: every constructed level is inside the bar and the
        # ceiling is the inventory, which is the port count at both resolutions
        assert len(healthy) == len(constructible)
        assert ceiling["ceiling"]["kind"] == "structural"
        assert int(ceiling["ceiling"]["n"]) > min(int(row["n"]) for row in constructible)
        assert ceiling["dynamical_ceiling"] is None
    elif branch == "capacity-is-dynamical":
        assert ceiling["dynamical_ceiling"] is not None
        assert len(healthy) < len(constructible)
    elif branch == "smooth-degradation-with-no-ceiling":
        assert ceiling["ceiling"] is None
        assert len(healthy) == len(constructible)
        assert ceiling["degradation_fit"]["fitted"] in (True, False)
    else:
        assert ceiling["ceiling"] is not None


def test_the_receipt_content_digest_recomputes(canonical: Mapping[str, Any]) -> None:
    published = str(canonical["receipt_digest"])
    body = json.loads(json.dumps(canonical))
    body.pop("receipt_digest")
    assert scale.receipt_digest(body) == published
    # the digest covers measured content, not the clock: a mutated measurement
    # must change it, so this check can fail
    mutated = json.loads(json.dumps(body))
    mutated["table"][0]["pairs_measured"] = int(mutated["table"][0]["pairs_measured"]) + 1
    assert scale.receipt_digest(mutated) != published
    # and a clock-only change must not move it
    clocked = json.loads(json.dumps(body))
    clocked["runtime_seconds"] = float(clocked["runtime_seconds"]) + 1000.0
    clocked["blocks"]["declared-profile"]["runtime_seconds"] = 1.0
    assert scale.receipt_digest(clocked) == published
    assert "runtime_seconds" in scale.STRIP_KEYS


def test_the_block_files_carry_their_own_digests() -> None:
    missing = [str(path) for path in capacity.BLOCK_PATHS.values() if not Path(path).exists()]
    assert not missing, (
        f"the declared block receipts {missing} are missing; produce them from CassiFI "
        "with `python run_store_addressing_capacity.py --block declared-profile` and "
        "`python run_store_addressing_capacity.py --block higher-resolution`"
    )
    for name, path in capacity.BLOCK_PATHS.items():
        body = json.loads(Path(path).read_text(encoding="utf-8"))
        assert body["schema"] == capacity.BLOCK_SCHEMA, name
        assert body["block"] == name
        published = body["content_digest"]
        assert scale.receipt_digest({k: v for k, v in body.items() if k != "content_digest"}) == published
        assert body["declared_counts"]
        assert body["points_run"] or body["points_not_constructible"]
