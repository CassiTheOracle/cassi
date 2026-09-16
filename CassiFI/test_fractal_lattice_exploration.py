"""Independent verification of the fractal-lattice exploration runner.

Two layers:

* in-process machinery, no receipt needed: the declared rung laws, the rung writer's
  orientation and the entries it replaces, the rail-L1 identity on every declared arm,
  the nested depth-1 anchor's reproduction of the cited construction, the nested
  normalization, and the family partition.
* receipt re-evaluation, skipped when the receipt is absent: every declared check's
  quantity and verdict recomputed from the measured basis with this file's own margin
  arithmetic, the firing controls re-run, the silenced controls re-run, the continuity
  rows recomputed, the rung/nested/attribution blocks recomputed from the basis, and
  the content digest re-derived.

Every assertion here is an equality or a declared margin, so a plausible construction
error (a swapped rung orientation, a dropped normalization, a stale verdict, a
re-labelled depth) fails it.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pytest

import run_fractal_geometry_exploration as geometry
import run_fractal_lattice_exploration as R

RECEIPT_PATH = (
    Path(__file__).resolve().parent / "_diag" / "fractal-lattice" / "exploration.json"
)
EXPECTED_FAMILY_COUNTS = {"motif": 18, "lattice": 17, "nested": 20, "interaction": 8}
EXPECTED_RUNG_LAWS = ("uniform", "phi")
# the declared rung shapes: the two primary laws plus the six declared controls, all on the same body
EXPECTED_MOTIF_RUNG_LAWS = frozenset(R.RUNG_LAWS) | frozenset(R.RUNG_CONTROL_LAWS)
# the field's own rail places the two circuit bridges at these strand-pair coordinates
EXPECTED_BRIDGES = [[0, 28], [27, 55]]


@pytest.fixture(scope="module")
def receipt() -> Mapping[str, Any]:
    if not RECEIPT_PATH.exists():
        pytest.skip(f"receipt {RECEIPT_PATH} is not present; run the runner to verify it")
    with RECEIPT_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def inventory() -> tuple[R.LatticeArrangement, ...]:
    return R.arrangement_inventory()


def _arms_by_family(
    arms: tuple[R.LatticeArrangement, ...],
) -> dict[str, list[R.LatticeArrangement]]:
    grouped: dict[str, list[R.LatticeArrangement]] = {
        "motif": [], "lattice": [], "nested": [], "interaction": []
    }
    for arm in arms:
        grouped[R._family_of(arm.name)].append(arm)
    return grouped


def _recovery(basis: Mapping[str, Any], name: str, count: str) -> float:
    return float(basis["per_arrangement"][name]["survival_recovery"][count])


def _verdict(kind: str, target: float | None, baseline: float | None, margin: float) -> tuple[Any, Any]:
    """This file's own margin arithmetic: (quantity, holds)."""
    if target is None or baseline is None:
        return None, None
    if kind == R.KIND_DIFFERENCE:
        quantity = float(target) - float(baseline)
        return quantity, bool(quantity >= float(margin))
    if kind == R.KIND_ABSOLUTE_DIFFERENCE:
        quantity = abs(float(target) - float(baseline))
        return quantity, bool(quantity >= float(margin))
    if kind == R.KIND_INVARIANCE:
        quantity = abs(float(target))
        return quantity, bool(quantity <= float(margin))
    raise AssertionError(f"unknown check kind {kind!r}")


# ---------------------------------------------------------------------------
# in-process machinery
# ---------------------------------------------------------------------------

def test_inventory_partitions_into_the_declared_families(
    inventory: tuple[R.LatticeArrangement, ...],
) -> None:
    grouped = _arms_by_family(inventory)
    assert {family: len(arms) for family, arms in grouped.items()} == EXPECTED_FAMILY_COUNTS
    names = [arm.name for arm in inventory]
    assert len(set(names)) == len(names)
    rung_arms = [
        arm.name for arm in grouped["motif"] if arm.rungs
    ]
    # the two primary arms on the field's own body, then the six declared rung-shape controls
    assert rung_arms == [item[0] for item in R.MOTIF_RUNG_ARMS] + [
        item[0] for item in R.MOTIF_RUNG_LAW_CONTROL_ARMS
    ]
    laws = {arm.rung_law for arm in grouped["motif"] if arm.rungs}
    assert laws == set(EXPECTED_MOTIF_RUNG_LAWS)
    # the primary pair and the six controls differ only in the declared rung shape
    primary = frozenset(item[0] for item in R.MOTIF_RUNG_ARMS)
    controls = {arm.name for arm in grouped["motif"] if arm.rungs} - primary
    assert controls == {arm[0] for arm in R.MOTIF_RUNG_LAW_CONTROL_ARMS}
    # the lattice arms declare the canonical weight rule only, under the uniform rung set
    assert {arm.rung_law for arm in grouped["lattice"] if arm.rungs} == {"uniform"}
    assert {arm.depth for arm in grouped["nested"]} == set(R.NESTED_DEPTHS)
    assert {arm.shell_law for arm in grouped["nested"]} == set(R.SHELL_LAWS) | {
        R.NESTED_REFERENCE_LAW
    }
    # the depth-normalization control: the anchor plus one unnormalized arm per raw law and depth
    assert sorted(
        arm.name for arm in grouped["nested"] if not arm.normalized
    ) == sorted(R.nested_raw_family_names())
    # every interaction cell declares a ring rail at a declared fraction of the lattice budget
    interaction = grouped["interaction"]
    assert sorted((arm.name, arm.rail_fraction) for arm in interaction) == sorted(
        (arm[0], arm[1]) for arm in R.INTERACTION_ARMS
    )
    assert {arm.pattern for arm in interaction} == {R.INTERACTION_PATTERN}
    assert {
        arm.rail_fraction for arm in interaction
    } == set(R.INTERACTION_RAIL_FRACTIONS)
    assert not any(arm.rungs for arm in interaction if arm.rail_fraction == 0.0)
    assert all(arm.rungs for arm in interaction if arm.rail_fraction > 0.0)


def test_rung_laws_are_two_declared_sets_with_declared_scales() -> None:
    uniform = R.rung_law_scales("uniform")
    phi = R.rung_law_scales("phi")
    assert len(uniform) == len(phi) == R.POOLS * R.PORTS_PER_POOL == 28
    assert uniform == tuple([float(R.RUNG_SCALE)] * 28)
    assert all(
        math.isclose(phi[k], R.PHI ** k, rel_tol=1e-12, abs_tol=0.0) for k in range(28)
    )
    assert all(
        math.isclose(phi[k + 1] / phi[k], R.PHI, rel_tol=1e-12) for k in range(27)
    )
    assert min(phi) == 1.0 and max(phi) == R.PHI ** 27
    # the two laws are different declared sets, so no contrast between them can be vacuous
    assert sum(abs(value) for value in uniform) != sum(abs(value) for value in phi)
    with pytest.raises(R.ResonantNumericalError):
        R.rung_law_scales("no-such-law")


def test_rung_writer_sets_one_oriented_rung_at_every_position() -> None:
    ports = R.POOLS * R.PORTS_PER_POOL
    scales = tuple([0.25] * ports)
    base = R.field_rail()
    written, report = R.set_rungs(base, scales)
    assert np.array_equal(written, -written.T)
    # the declared orientation is Yang coordinate -> Yin coordinate with the antisymmetric
    # reverse entry, and it is the sign convention the field's own pool links use
    first_link = geometry.pool_link_port_pairs(
        (0, 1, 1.0), geometry.canonical_parts(R.PORTS_PER_POOL)
    )[0]
    canonical_rail = R.field_rail()
    assert canonical_rail[first_link[1], first_link[0]] > 0.0
    for position in range(ports):
        assert written[ports + position, position] == pytest.approx(0.25, abs=1e-12)
        assert written[position, ports + position] == pytest.approx(-0.25, abs=1e-12)
    assert report["orientation_max_absolute_deviation"] == 0.0
    assert report["rungs_set"] == ports
    assert report["rung_channel_l1"] == pytest.approx(0.25 * ports, rel=1e-12)
    assert report["canonical_entries_replaced"] == EXPECTED_BRIDGES
    assert report["replaced_entry_count"] == len(EXPECTED_BRIDGES)
    for (position, partner), magnitude in zip(
        report["canonical_entries_replaced"], report["replaced_entry_magnitudes"]
    ):
        assert magnitude == pytest.approx(abs(base[partner, position]), rel=1e-12)
        assert magnitude > 0.0
        assert written[position, partner] == pytest.approx(-0.25, abs=1e-12)
    # a symmetric bidirectional exchange cancels and cannot be declared: writing the same
    # magnitude on both sides leaves no rung in the rail
    symmetric = np.array(base, dtype=np.float64, copy=True)
    for position in range(ports):
        symmetric[position, ports + position] = 0.25
        symmetric[ports + position, position] = 0.25
    assert not np.array_equal(symmetric, -symmetric.T)
    with pytest.raises(R.ResonantNumericalError):
        R.set_rungs(base, tuple([0.25] * (ports - 1)))
    # a wrong orientation is detected rather than silently accepted
    flipped, flipped_report = R.set_rungs(base, tuple([-0.25] * ports))
    assert flipped_report["orientation_max_absolute_deviation"] == 0.0
    assert not np.array_equal(
        flipped[ports : ports + 1, 0:1], written[ports : ports + 1, 0:1]
    )


def test_motif_rung_channel_realizes_the_motif_budget_for_both_laws(
    inventory: tuple[R.LatticeArrangement, ...],
) -> None:
    budget = R.motif_reference_weight()
    factors = {}
    for arm in inventory:
        if R._family_of(arm.name) != "motif" or not arm.rungs:
            continue
        built = R.build_arrangement(arm)
        raw_total = sum(abs(value) for value in R.rung_law_scales(arm.rung_law))
        assert built.rung_weight == pytest.approx(budget, rel=1e-12)
        assert built.rung_weight == pytest.approx(
            sum(abs(scale) for scale in built.rung_scales), rel=1e-12
        )
        assert built.normalization_factor == pytest.approx(budget / raw_total, rel=1e-12)
        assert built.link_weight == 0.0 and built.links == ()
        factors[arm.rung_law] = built.normalization_factor
    assert set(factors) == set(EXPECTED_MOTIF_RUNG_LAWS)
    # the laws carry different raw totals, so their normalizations differ: no arm is
    # law-independent by accident, and the two primary laws differ from each other
    assert factors["phi"] != pytest.approx(factors["uniform"], rel=1e-6)
    # the reversed and the shuffled controls carry the phi ramp's own weight multiset, so their
    # declared raw totals, and therefore their normalization factors, are phi's exactly
    assert factors["phi-down"] == pytest.approx(factors["phi"], rel=1e-12)
    assert factors["shuffled-phi"] == pytest.approx(factors["phi"], rel=1e-12)
    # every other law is a different declared multiset
    others = {law: value for law, value in factors.items()
              if law not in ("phi", "phi-down", "shuffled-phi")}
    assert len({round(value, 12) for value in others.values()}) == len(others)


def test_rail_l1_identity_holds_on_every_declared_arm(
    inventory: tuple[R.LatticeArrangement, ...],
) -> None:
    for arm in inventory:
        profile, built, report = R.arrangement_profile(arm)
        rail = np.asarray(profile.projected_transport, dtype=np.float64)
        assert np.isfinite(rail).all()
        assert np.array_equal(rail, -rail.T), arm.name
        assert report["measured_rail_l1"] == pytest.approx(
            float(np.abs(rail).sum()), rel=1e-12
        )
        assert report["measured_rail_l1"] == pytest.approx(
            report["declared_rail_l1"], abs=1e-9
        ), arm.name
        assert report["rail_l1_absolute_difference"] <= 1e-9, arm.name
        audit = report["mass_metric_audit"]
        assert audit["per_port_count"] == rail.shape[0]
        assert math.isfinite(audit["min"]) and audit["min"] > 0.0
        assert audit["max"] >= audit["min"] and math.isfinite(audit["l1"])
        if arm.kind == "motif" and arm.rungs:
            assert report["rung_report"]["canonical_entries_replaced"] == EXPECTED_BRIDGES
            # the declared rail is the motif rail plus the declared rung channel, minus the
            # two endpoint bridges the rungs re-declare
            assert report["declared_rail_l1"] == pytest.approx(
                report["motif_rail_l1"]
                - 2.0 * report["cleared_entry_l1"]
                + 2.0 * report["rung_report"]["rung_channel_l1"],
                rel=1e-12,
            )
        if arm.kind == "nested":
            assert report["independent_reconstruction_max_absolute_difference"] == 0.0


def test_normalized_nested_arms_sit_on_the_geometry_budget(
    inventory: tuple[R.LatticeArrangement, ...],
) -> None:
    budget = R.lattice_reference_weight()
    normalized = [
        arm for arm in inventory if arm.kind == "nested" and arm.normalized
    ]
    raw = [arm for arm in inventory if arm.kind == "nested" and not arm.normalized]
    assert len(normalized) == len(R.SHELL_LAWS) * len(R.NESTED_DEPTHS)
    # the depth-normalization control: the anchor plus one new unnormalized arm per law and depth
    assert len(raw) == 1 + len(R.NESTED_RAW_ARMS)
    assert sorted(arm.name for arm in raw) == sorted(R.nested_raw_family_names())
    for arm in normalized:
        built = R.build_arrangement(arm)
        assert built.link_weight == pytest.approx(budget, rel=1e-12), arm.name
        assert built.rung_scales == ()
    anchor = R.arrangement_lookup(R.NESTED_ANCHOR_NAME)
    anchor_built = R.build_arrangement(anchor)
    assert anchor.normalized is False
    assert anchor_built.link_weight != pytest.approx(budget, rel=1e-3)


def test_nested_depth1_anchor_reproduces_the_cited_construction() -> None:
    anchor = R.arrangement_lookup(R.NESTED_ANCHOR_NAME)
    assert anchor.depth == 1 and anchor.shell_law == R.NESTED_REFERENCE_LAW
    assert R.SHELL_LAW_VALUES[R.NESTED_REFERENCE_LAW] == pytest.approx(0.7, rel=1e-12)
    anchor_profile, _built, report = R.arrangement_profile(anchor)
    cited_profile = geometry.build_profile(geometry.arrangement_named(R.NESTED_NAME))
    anchor_rail = np.asarray(anchor_profile.projected_transport, dtype=np.float64)
    cited_rail = np.asarray(cited_profile.projected_transport, dtype=np.float64)
    assert anchor_rail.shape == cited_rail.shape
    assert float(np.abs(anchor_rail - cited_rail).max()) == 0.0
    assert np.array_equal(anchor_rail, -anchor_rail.T)
    assert np.array_equal(
        np.asarray(anchor_profile.inertances, dtype=np.float64),
        np.asarray(cited_profile.inertances, dtype=np.float64),
    )
    assert report["mass_metric_audit"]["source"].startswith("projected_inv_mass: nested shell")
    # the lattice arms carry the field's default rail instead, which holds six further links
    lattice = R.arrangement_lookup(R.UNIFORM_MOTIF_NAME)
    _lattice_profile, _built, lattice_report = R.arrangement_profile(lattice)
    assert lattice_report["motif_rail_l1"] != pytest.approx(
        float(np.abs(anchor_rail).sum()), rel=1e-6
    )
    field_l1 = float(np.abs(R.field_rail()).sum())
    assert lattice_report["motif_rail_l1"] == pytest.approx(field_l1, rel=1e-12)
    assert field_l1 != pytest.approx(float(np.abs(anchor_rail).sum()), rel=1e-6)


# ---------------------------------------------------------------------------
# receipt re-evaluation
# ---------------------------------------------------------------------------

def test_receipt_scope_declares_every_family(receipt: Mapping[str, Any]) -> None:
    basis = receipt["comparisons"]["basis"]
    per = basis["per_arrangement"]
    assert len(per) == len(R.arrangement_inventory()) + len(R.reference_arrangements())
    assert set(basis["motif_names"]) == set(
        name for name in per if R._family_of(name) == "motif"
    )
    references = set(R.reference_arrangements())
    assert references <= set(per)
    assert set(basis["lattice_names"]) == {
        name for name in per if name not in references and R._family_of(name) == "lattice"
    }
    assert set(basis["nested_names"]) == {
        name for name in per if name not in references and R._family_of(name) == "nested"
    }
    assert set(basis["lattice_names"]).isdisjoint(references)
    assert tuple(basis["motif_rung_names"]) == tuple(
        item[0] for item in R.MOTIF_RUNG_ARMS
    ) + tuple(item[0] for item in R.MOTIF_RUNG_LAW_CONTROL_ARMS)
    assert set(basis["interaction_names"]) == {
        name for name in per if R._family_of(name) == "interaction"
    }
    assert set(basis["nested_raw_names"]) == {
        name for name in per
        if name not in references and R._family_of(name) == "nested"
        and not per[name]["normalized"]
    }
    assert set(basis["rung_law_control_names"]) == {
        arm[0] for arm in R.MOTIF_RUNG_LAW_CONTROL_ARMS
    }
    for name in basis["motif_rung_names"]:
        row = per[name]
        assert row["rung_channel_l1_one_sided"] == pytest.approx(
            basis["motif_reference_weight"], rel=1e-12
        )
        assert row["rung_canonical_entries_replaced"] == EXPECTED_BRIDGES
        assert row["rung_orientation_max_absolute_deviation"] == 0.0
        assert row["rail_l1_identity_absolute_difference"] <= 1e-9
        assert math.isfinite(row["rung_scale_min"]) and math.isfinite(row["rung_scale_max"])
    assert (
        per["motif-default-rungs-phi"]["rung_scale_max"]
        > per["motif-default-rungs"]["rung_scale_max"]
    )


def test_every_declared_check_recomputes_from_the_stored_basis(
    receipt: Mapping[str, Any],
) -> None:
    checks = receipt["comparisons"]["checks"]
    declared = {check.id for check in R.margin_checks()}
    assert {row["id"] for row in checks} == declared
    assert len(checks) == len(R.margin_checks()) >= 46
    unmeasured = [row["id"] for row in checks if row["status"] != "measured"]
    assert unmeasured == []
    for row in checks:
        quantity, holds = _verdict(row["kind"], row["target"], row["baseline"], row["margin"])
        assert quantity is not None
        assert row["quantity"] == pytest.approx(quantity, rel=1e-12, abs=1e-15), row["id"]
        assert row["holds"] is holds, row["id"]
        assert row["comparison"] == ("<=" if row["kind"] == R.KIND_INVARIANCE else ">=")
        if row["kind"] == R.KIND_DIFFERENCE:
            assert row["statement"]
    summary = receipt["comparisons"]["checks_summary"]
    holds = [row["holds"] for row in checks]
    assert summary["total"] == len(checks)
    assert summary["holding"] == sum(1 for value in holds if value is True)
    assert summary["failing"] == sum(1 for value in holds if value is False)
    assert summary["failing"] == len(summary["failing_ids"])
    assert summary["failing_ids"] == [row["id"] for row in checks if row["holds"] is False]
    # the declared hypotheses are a mixture of measured support and measured refutation: a
    # receipt that reported one verdict for every check would not be measuring them
    assert any(holds), "no declared check holds"
    for row in checks:
        if row["holds"] is False:
            assert row["quantity"] is not None and row["statement"], row["id"]


def test_every_declared_check_fires_in_both_verdicts(receipt: Mapping[str, Any]) -> None:
    basis = receipt["comparisons"]["basis"]
    stored = {row["id"]: row for row in receipt["comparisons"]["firing_controls"]}
    checks = {row["id"]: row for row in receipt["comparisons"]["checks"]}
    replayed = R.firing_controls(basis)
    assert {row["id"] for row in replayed} == set(stored)
    for row in stored.values():
        assert row["flips"] is (row["verdict_before"] is not row["verdict_after"]), row["id"]
        assert row["flips"] is True, row["id"]
    for row in replayed:
        before = stored[row["id"]]
        assert row["verdict_before"] is checks[row["id"]]["holds"] is before["verdict_before"]
        assert row["verdict_after"] is not row["verdict_before"], row["id"]
        assert row["flips"] is True, row["id"]
        assert row["direction"] == (
            "toward-violation" if row["verdict_before"] else "toward-satisfaction"
        ), row["id"]
        assert row["kind"] == before["kind"]
        assert before["mutation"]
    assert {row["verdict_before"] for row in replayed} == {True, False}


def test_silenced_controls_fall_silent(receipt: Mapping[str, Any]) -> None:
    basis = receipt["comparisons"]["basis"]
    replayed = R.silenced_controls(basis)
    assert len(replayed) == len(receipt["comparisons"]["silenced_controls"])
    assert replayed, "every separation check must have a silenced control"
    for row in replayed:
        assert row["holds"] is False, row["id"]
        assert row["silent"] is True, row["id"]
        assert row["quantity"] is not None
    invariance = {
        check.id for check in R.margin_checks() if check.kind == R.KIND_INVARIANCE
    }
    assert {row["id"] for row in replayed}.isdisjoint(invariance)
    assert set(receipt["comparisons"]["invariance_checks_without_silenced_control"]) == invariance


def test_continuity_rows_reproduce_the_cited_figures(receipt: Mapping[str, Any]) -> None:
    rows = receipt["comparisons"]["continuity"]
    assert rows
    for row in rows:
        difference = abs(float(row["measured"]) - float(row["cited"]))
        assert row["absolute_difference"] == pytest.approx(difference, rel=1e-12)
        assert row["holds"] is bool(difference <= float(row["allowance"])), row["id"]
    assert all(row["holds"] for row in rows), [
        row["id"] for row in rows if not row["holds"]
    ]
    for name, cited in R.CITED_K4_RECOVERY.items():
        matching = [
            row for row in rows
            if row["arrangement"] == name and row["quantity"] == "survival_k4_recovery"
        ]
        assert matching, name
        assert matching[0]["cited"] == pytest.approx(cited, rel=1e-12)
    control = receipt["comparisons"]["continuity_firing_control"]
    assert control is not None
    assert control["id"] in {row["id"] for row in rows}
    assert control["verdict_before"] is True
    assert control["verdict_after"] is False
    assert control["flips"] is True
    moved_row = next(row for row in rows if row["id"] == control["id"])
    assert control["measured_moved"] == pytest.approx(
        float(moved_row["cited"]) + 10.0 * float(moved_row["allowance"]), rel=1e-12
    )


def test_rung_block_matches_the_measured_basis(receipt: Mapping[str, Any]) -> None:
    basis = receipt["comparisons"]["basis"]
    block = receipt["comparisons"]["rung"]
    per = basis["per_arrangement"]
    assert block["rung_positions_declared"] == 28
    assert block["canonical_entries_replaced"] == EXPECTED_BRIDGES
    assert set(block["rung_laws"]) == set(EXPECTED_RUNG_LAWS)
    assert {row["arrangement"] for row in block["arms"]} == {
        item[0] for item in R.MOTIF_RUNG_ARMS
    }
    # the declared rung-law controls are the same body and the same channel under other shapes;
    # the control table holds the two primary default-body laws and the six control laws, and it
    # excludes the two coupling-law rung arms because those change the coupling law as well
    controls = block["law_controls"]
    assert {row["arrangement"] for row in controls["rows"]} == {
        item[0] for item in R.MOTIF_RUNG_ARMS[:2]
    } | {item[0] for item in R.MOTIF_RUNG_LAW_CONTROL_ARMS}
    assert {
        item[0] for item in R.MOTIF_RUNG_ARMS[2:]
    }.isdisjoint({row["arrangement"] for row in controls["rows"]})
    assert set(controls["laws"]) == set(EXPECTED_MOTIF_RUNG_LAWS)
    assert controls["table"]["law_count"] == len(EXPECTED_MOTIF_RUNG_LAWS)
    assert controls["table"]["channel_budget"] == pytest.approx(
        basis["motif_reference_weight"], rel=1e-12
    )
    assert controls["table"]["channel_max_relative_deviation"] <= R.MARGIN_WEIGHT_INVARIANCE
    for row in controls["rows"]:
        measured = per[row["arrangement"]]
        for count in ("k2", "k4", "k8"):
            assert row[count] == pytest.approx(
                measured["survival_recovery"][count], rel=1e-12
            ), (row["arrangement"], count)
        assert row["rung_channel_l1_one_sided"] == pytest.approx(
            basis["motif_reference_weight"], rel=1e-12
        ), row["arrangement"]
        assert row["rung_scale_sha256"] == R.rung_law_scale_digest(row["rung_law"])
    canonical = per[basis["uniform_motif_name"]]
    for row in block["arms"]:
        measured = per[row["arrangement"]]
        for count in ("k2", "k4", "k8"):
            assert row["survival_recovery"][count] == pytest.approx(
                measured["survival_recovery"][count], rel=1e-12
            )
            expected = measured["survival_recovery"][count] - canonical["survival_recovery"][count]
            assert row[f"survival_k{count[1]}_delta_vs_canonical"] == pytest.approx(
                expected, rel=1e-9, abs=1e-12
            )
        assert row["ipr_median"] == pytest.approx(measured["ipr_median"], rel=1e-12)
        assert row["rung_channel_l1_one_sided"] == pytest.approx(
            basis["motif_reference_weight"], rel=1e-12
        )
        assert row["rung_law"] == R.arrangement_lookup(row["arrangement"]).rung_law
    held = block["held_lattice_rung_result"]
    assert held["check"] == "survival_k4_rungs_change_the_result"
    assert held["cited"] == pytest.approx(0.0740669, rel=1e-9)
    # the cited held figure and this receipt's own row for the same check must agree: the
    # citation is a reproduction of a held result, not a substitute for the measurement
    held_row = next(
        row for row in receipt["comparisons"]["checks"] if row["id"] == held["check"]
    )
    assert held_row["status"] == "measured" and held_row["holds"] is True
    assert held["measured_in_this_receipt"] == pytest.approx(held_row["quantity"], rel=1e-12)
    assert held["absolute_difference_to_cited"] == pytest.approx(
        abs(held["measured_in_this_receipt"] - held["cited"]), rel=1e-9, abs=1e-15
    )
    assert held["agrees_within_declared_tolerance"] is bool(
        abs(held["measured_in_this_receipt"] - held["cited"]) <= R.MARGIN_RECOVERY
    )
    # the held lattice rung result is cited from the already-declared lattice arms, and those
    # arms really carry a rung channel in the receipt
    lattice_rungs = [
        name for name in basis["lattice_names"]
        if per[name]["rung_channel_l1_one_sided"] is not None
    ]
    assert lattice_rungs
    assert {row["arrangement"] for row in block["lattice_rung_arms_for_convention_comparison"]} == set(
        lattice_rungs
    )
    for row in block["lattice_rung_arms_for_convention_comparison"]:
        assert row["written_rung_channel_l1_one_sided"] > 0.0
        assert row["declared_rung_weight_canonical_rule"] > 0.0
    assert block["motif_rung_channel_max_relative_deviation"] <= R.MARGIN_WEIGHT_INVARIANCE
    assert block["top7_drive_ports_differing_from_canonical"] is not None


def test_nested_block_matches_the_measured_basis(receipt: Mapping[str, Any]) -> None:
    basis = receipt["comparisons"]["basis"]
    block = receipt["comparisons"]["nested"]
    per = basis["per_arrangement"]
    assert {row["arrangement"] for row in block["arms"]} == set(basis["nested_names"])
    assert block["depths"] == [int(depth) for depth in R.NESTED_DEPTHS]
    assert {row["depth"] for row in block["arms"]} == set(R.NESTED_DEPTHS)
    assert {row["shell_law"] for row in block["arms"]} == set(R.SHELL_LAWS) | {
        R.NESTED_REFERENCE_LAW
    }
    for row in block["arms"]:
        measured = per[row["arrangement"]]
        assert row["survival_recovery"] == pytest.approx(
            measured["survival_recovery"], rel=1e-12
        )
        assert row["depth"] == measured["nesting_depth"]
        assert row["shell_law"] == measured["shell_law"]
        assert row["normalized"] is measured["normalized"]
        assert row["rail_l1"] == pytest.approx(measured["rail_l1"], rel=1e-12)
        assert measured["mass_metric_min"] > 0.0
    anchor = block["depth1_reference_law_anchor"]
    assert anchor["arrangement"] == R.NESTED_ANCHOR_NAME
    assert anchor["measured_k4"] == pytest.approx(
        per[R.NESTED_ANCHOR_NAME]["survival_recovery"]["k4"], rel=1e-12
    )
    assert anchor["cited_k4"] == pytest.approx(R.CITED_K4_RECOVERY[R.NESTED_NAME], rel=1e-12)
    assert anchor["absolute_k4_difference_to_cited"] == pytest.approx(
        abs(anchor["measured_k4"] - anchor["cited_k4"]), rel=1e-9, abs=1e-15
    )
    assert anchor["absolute_k4_difference_to_cited"] <= R.MARGIN_RECOVERY
    assert anchor["rail_max_absolute_difference_to_the_cited_construction"] == 0.0
    assert anchor["measured_ipr_median"] == pytest.approx(
        per[R.NESTED_ANCHOR_NAME]["ipr_median"], rel=1e-12
    )
    same_run = block["same_run_single_nest"]
    assert same_run["arrangement"] == R.NESTED_NAME
    assert same_run["measured_k4"] == pytest.approx(
        per[R.NESTED_NAME]["survival_recovery"]["k4"], rel=1e-12
    )
    assert same_run["absolute_difference"] == pytest.approx(
        abs(same_run["measured_k4"] - same_run["cited_k4"]), rel=1e-9, abs=1e-15
    )
    axes = block["axes"]
    assert axes["depth_axis"]["law"] == R.NESTED_DEPTH_AXIS_LAW
    assert axes["depth_axis"]["deep"] == f"nested-d{R.NESTED_DEPTHS[-1]}-{R.NESTED_DEPTH_AXIS_LAW}"
    assert axes["shell_law_axis"]["depth"] == int(R.NESTED_LAW_AXIS_DEPTH)
    assert basis["nested_total_weight_max_relative_deviation"] <= R.MARGIN_WEIGHT_INVARIANCE


def test_attribution_block_matches_the_measured_basis(receipt: Mapping[str, Any]) -> None:
    basis = receipt["comparisons"]["basis"]
    block = receipt["comparisons"]["attribution"]
    per = basis["per_arrangement"]
    names = {row["leg"]: row["arrangement"] for row in block["arms"]}
    assert names == {
        "canonical": R.ATTRIBUTION_CANONICAL_NAME,
        "rail_only": R.ATTRIBUTION_RAIL_ONLY_NAME,
        "mass_only": R.ATTRIBUTION_MASS_ONLY_NAME,
        "compound": R.ATTRIBUTION_COMPOUND_NAME,
    }
    assert block["tolerance"] == pytest.approx(R.TOLERANCE_ATTRIBUTION_ADDITIVITY, rel=1e-12)
    assert block["rail_component_margin"] == pytest.approx(R.MARGIN_RAIL_COMPONENT, rel=1e-12)
    assert block["mass_component_margin"] == pytest.approx(R.MARGIN_MASS_COMPONENT, rel=1e-12)
    canonical = names["canonical"]
    for count in ("k2", "k4", "k8"):
        entry = block["per_count"][count]
        base = _recovery(basis, canonical, count)
        assert entry["canonical"] == pytest.approx(base, rel=1e-12)
        deltas = {
            leg: _recovery(basis, name, count) - base for leg, name in names.items() if leg != "canonical"
        }
        for leg, value in deltas.items():
            assert entry["legs"][leg] == pytest.approx(
                _recovery(basis, names[leg], count), rel=1e-12
            )
            assert entry["deltas_vs_canonical"][leg] == pytest.approx(value, rel=1e-9, abs=1e-12)
        residual = deltas["compound"] - (deltas["rail_only"] + deltas["mass_only"])
        assert entry["additivity_residual"] == pytest.approx(residual, rel=1e-9, abs=1e-12)
        assert entry["additive_within_tolerance"] is bool(
            abs(residual) <= R.TOLERANCE_ATTRIBUTION_ADDITIVITY
        )
    # the two single-channel legs are each a real channel: the rail leg carries the graded
    # inter-copy links and the mass leg carries the shell metric, so neither is the canonical body
    for leg in ("rail_only", "mass_only", "compound"):
        assert per[names[leg]]["mass_metric_diagonal_sha256"] != per[canonical][
            "mass_metric_diagonal_sha256"
        ] or leg == "rail_only"
    assert per[names["mass_only"]]["mass_metric_diagonal_sha256"] != per[canonical][
        "mass_metric_diagonal_sha256"
    ]
    contrast = block["best_lattice_k4_vs_same_run_single_nest"]
    assert contrast["best_lattice_name"] == basis["best_lattice_name"]
    assert contrast["best_lattice_k4"] == pytest.approx(
        per[basis["best_lattice_name"]]["survival_recovery"]["k4"], rel=1e-12
    )
    assert contrast["same_run_single_nest_k4"] == pytest.approx(
        per[R.NESTED_NAME]["survival_recovery"]["k4"], rel=1e-12
    )
    assert contrast["difference"] == pytest.approx(
        contrast["best_lattice_k4"] - contrast["same_run_single_nest_k4"], rel=1e-9, abs=1e-12
    )
    assert abs(contrast["difference"]) >= R.MARGIN_RECOVERY


def test_declared_channels_and_margins_are_reported(receipt: Mapping[str, Any]) -> None:
    declarations = receipt["declarations"]
    assert set(declarations["rung_laws"]) == set(EXPECTED_RUNG_LAWS)
    for law, entry in declarations["rung_laws"].items():
        raw = R.rung_law_scales(law)
        assert entry["raw_scales_at_positions_0_to_6"] == pytest.approx(
            list(raw[:7]), rel=1e-12
        )
        assert entry["raw_total_l1"] == pytest.approx(sum(abs(v) for v in raw), rel=1e-12)
        assert entry["declared_channel_total_rail_units"] == pytest.approx(
            R.motif_reference_weight(), rel=1e-12
        )
        scaled = [v * R.motif_reference_weight() / entry["raw_total_l1"] for v in raw[:7]]
        assert entry["normalized_scales_at_positions_0_to_6_phi_arm"] == pytest.approx(
            scaled, rel=1e-12
        )
    nested = declarations["nested_family"]
    assert nested["depths"] == [int(depth) for depth in R.NESTED_DEPTHS]
    assert nested["shell_laws"] == {law: float(value) for law, value in R.SHELL_LAW_VALUES.items()}
    anchor = nested["depth1_reference_law_anchor"]
    assert anchor["normalized"] is False
    assert anchor["law_value"] == pytest.approx(
        R.SHELL_LAW_VALUES[R.NESTED_REFERENCE_LAW], rel=1e-12
    )
    assert anchor["cited_figures"]["survival_k4_recovery"] == pytest.approx(
        R.CITED_K4_RECOVERY[R.NESTED_NAME], rel=1e-12
    )
    attribution = declarations["attribution"]
    assert attribution["canonical"] == R.ATTRIBUTION_CANONICAL_NAME
    assert attribution["compound"] == R.ATTRIBUTION_COMPOUND_NAME
    assert set(attribution["margins"]) == {
        "rail_component", "mass_component", "additivity_tolerance", "origin"
    }
    for key, value in receipt["declarations"]["margins"].items():
        assert isinstance(value, (int, float)) and math.isfinite(float(value)), key
    assert receipt["declarations"]["margins_origin"]
    assert declarations["normalization"]["motif_reference_weight"] == pytest.approx(
        R.motif_reference_weight(), rel=1e-12
    )
    assert declarations["normalization"]["lattice_reference_weight"] == pytest.approx(
        R.lattice_reference_weight(), rel=1e-12
    )
    assert "audit" in declarations["normalization"]
    assert declarations["spectrum_reporting"]
    assert declarations["continuity_scope"]
    assert any("rung" in line for line in declarations["boundary"])
    assert any("nested" in line for line in receipt["limitations"])


def test_receipt_renders_every_declared_section(receipt: Mapping[str, Any]) -> None:
    table = R.format_table(receipt)
    comparisons = receipt["comparisons"]
    named = [
        comparisons["rung"]["arms"][0]["arrangement"],
        comparisons["nested"]["arms"][0]["arrangement"],
        comparisons["attribution"]["arms"][0]["arrangement"],
        comparisons["continuity"][0]["arrangement"],
    ]
    for name in named:
        assert name in table, name
    assert "canonical entries replaced" in table
    assert "depth-1 reference-law anchor" in table
    assert "attribution k4" in table
    assert receipt["receipt_sha256"] in table
    assert "\n" in table


def test_receipt_is_finite_and_its_digest_re_derives(receipt: Mapping[str, Any]) -> None:
    stored = receipt["receipt_sha256"]
    assert isinstance(stored, str) and len(stored) == 64
    body = json.loads(json.dumps(receipt))
    body["receipt_sha256"] = None
    assert R.content_digest(body) == stored
    assert float(receipt["runtime_seconds"]) > 0.0
    R.assert_finite(body)


# ---------------------------------------------------------------------------
# runtime guard
# ---------------------------------------------------------------------------

def test_runtime_stays_under_the_declared_budget() -> None:
    started = time.perf_counter()
    for arm in R.arrangement_inventory()[:4]:
        R.arrangement_profile(arm)
    assert time.perf_counter() - started < 30.0


# ---------------------------------------------------------------------------
# the motif-rung claim: two arms, two declared checks, recomputed from the receipt
# ---------------------------------------------------------------------------

def _rung_rows(receipt: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    block = receipt["comparisons"]["rung"]["survival_k4_rows"]
    return {row["check"]: row for row in block["rows"]}


def _resolve(receipt: Mapping[str, Any], pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer against the receipt, so a reported figure is pinned."""
    node: Any = receipt
    for token in pointer.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def test_motif_rung_survival_rows_recompute_from_the_stored_basis(
    receipt: Mapping[str, Any],
) -> None:
    basis = receipt["comparisons"]["basis"]
    per = basis["per_arrangement"]
    canonical = basis["uniform_motif_name"]
    canonical_k4 = per[canonical]["survival_recovery"]["k4"]
    rows = _rung_rows(receipt)
    assert set(rows) == {
        "motif_rungs_change_survival_k4", "motif_phi_rungs_change_survival_k4"
    }
    expected_arm = {
        "motif_rungs_change_survival_k4": R.MOTIF_RUNG_ARMS[0][0],
        "motif_phi_rungs_change_survival_k4": R.MOTIF_RUNG_ARMS[1][0],
    }
    # each declared rung check covers its own arm and no other: the two arms carry different laws
    assert R.MOTIF_RUNG_ARMS[0][2] != R.MOTIF_RUNG_ARMS[1][2]
    verdicts = {}
    for check_id, row in rows.items():
        arm = expected_arm[check_id]
        assert row["covers_the_arm"] == arm
        assert row["compared_against"] == canonical
        arm_k4 = per[arm]["survival_recovery"]["k4"]
        assert row["arm_k4"] == pytest.approx(arm_k4, rel=1e-12)
        assert row["canonical_k4"] == pytest.approx(canonical_k4, rel=1e-12)
        # the stored delta is the stored basis' own difference, recomputed here
        delta = arm_k4 - canonical_k4
        assert row["k4_delta"] == pytest.approx(delta, rel=1e-9, abs=1e-15)
        # and it is judged against the row's own declared margin, by this file's own arithmetic
        quantity, holds = _verdict(R.KIND_ABSOLUTE_DIFFERENCE, arm_k4, canonical_k4, row["declared_margin"])
        assert row["measured_quantity"] == pytest.approx(quantity, rel=1e-12, abs=1e-15)
        assert row["verdict"] is holds
        assert row["declared_margin"] == pytest.approx(R.MARGIN_RECOVERY, rel=1e-12)
        verdicts[check_id] = holds
        # every figure this row reports is pinned to a JSON Pointer into the shipped receipt
        assert _resolve(receipt, row["pointers"]["arm_k4"]) == pytest.approx(
            row["arm_k4"], rel=1e-12
        )
        assert _resolve(receipt, row["pointers"]["canonical_k4"]) == pytest.approx(
            row["canonical_k4"], rel=1e-12
        )
        check_row = _resolve(receipt, row["pointers"]["check_row"])
        assert check_row["id"] == check_id
        assert check_row["quantity"] == pytest.approx(
            row["measured_quantity"], rel=1e-12, abs=1e-15
        )
        for count in ("k2", "k4", "k8"):
            for side in ("survival_recovery_pointers", "canonical_survival_recovery_pointers"):
                pointer = row[side][count]
                arm_name = (
                    row["covers_the_arm"] if side == "survival_recovery_pointers"
                    else row["compared_against"]
                )
                assert pointer == (
                    f"/comparisons/basis/per_arrangement/{arm_name}/survival_recovery/{count}"
                )
                assert _resolve(receipt, pointer) == pytest.approx(
                    per[arm_name]["survival_recovery"][count], rel=1e-12
                )
        assert _resolve(receipt, row["pointers"]["reconciliation_row"]) == row
    # the two rung arms are separate declared rows with separate verdicts, one each way
    assert verdicts == {
        "motif_rungs_change_survival_k4": False,
        "motif_phi_rungs_change_survival_k4": True,
    }
    # and the receipt's own check rows, the summary pair and the refuted list agree
    checks = {row["id"]: row for row in receipt["comparisons"]["checks"]}
    for check_id, holds in verdicts.items():
        assert checks[check_id]["holds"] is holds
        assert checks[check_id]["quantity"] == pytest.approx(
            abs(per[expected_arm[check_id]]["survival_recovery"]["k4"] - canonical_k4),
            rel=1e-9, abs=1e-15,
        )
    summary = receipt["comparisons"]["checks_summary"]
    pairs = {row["check"]: row for row in summary["rung_survival_k4_verdicts"]}
    assert set(pairs) == set(verdicts)
    for check_id, row in pairs.items():
        assert row["covers_the_arm"] == expected_arm[check_id]
        assert row["verdict"] is verdicts[check_id]
        assert row["margin"] == pytest.approx(R.MARGIN_RECOVERY, rel=1e-12)
    refuted = {row["check"]: row for row in receipt["comparisons"]["refuted_declared_hypotheses"]}
    assert "motif_rungs_change_survival_k4" in refuted
    assert "motif_phi_rungs_change_survival_k4" not in refuted
    assert summary["refuted"] == summary["failing"] == len(summary["refuted_ids"])
    assert set(summary["refuted_ids"]) == set(refuted)
    coverage = refuted["motif_rungs_change_survival_k4"]["arm_coverage"]
    assert R.MOTIF_RUNG_ARMS[0][0] in coverage["covers_the_arms"]
    assert R.MOTIF_RUNG_ARMS[1][0] in coverage["does_not_cover"]


def test_motif_rung_survival_rows_mutation_control_flips_the_verdict(
    receipt: Mapping[str, Any],
) -> None:
    basis = receipt["comparisons"]["basis"]
    checks = {check.id: check for check in R.margin_checks()}
    for check_id, arm in (
        ("motif_rungs_change_survival_k4", R.MOTIF_RUNG_ARMS[0][0]),
        ("motif_phi_rungs_change_survival_k4", R.MOTIF_RUNG_ARMS[1][0]),
    ):
        check = checks[check_id]
        before = R.evaluate_check(basis, check)
        assert before["status"] == "measured"
        # the receipt's own firing control moved this check's number and flipped its verdict
        fired = R.fire_check(json.loads(json.dumps(basis)), check)
        assert fired["flips"] is True
        assert fired["verdict_before"] is before["holds"]
        assert fired["verdict_after"] is not before["holds"]
        # the control is not vacuous: mutating the stored basis' own number flips this check, and
        # the sibling rung check is untouched by that mutation
        mutated = json.loads(json.dumps(basis))
        baseline = float(check.base_get(mutated))
        current = float(check.target_get(mutated))
        # place the target a half margin from the baseline when the check holds today (so the
        # separation falls below the margin), and two margins away when it does not (so it rises
        # above it): the mutation is derived from the check's own two sides, not from a direction
        moved = (
            baseline + 0.5 * float(check.margin) if before["holds"]
            else (
                baseline + 2.0 * float(check.margin) if current >= baseline
                else baseline - 2.0 * float(check.margin)
            )
        )
        check.target_put(mutated, moved)
        after = R.evaluate_check(mutated, check)
        assert after["holds"] is not before["holds"], check_id
        sibling_id = (
            "motif_phi_rungs_change_survival_k4"
            if check_id == "motif_rungs_change_survival_k4"
            else "motif_rungs_change_survival_k4"
        )
        sibling = checks[sibling_id]
        assert R.evaluate_check(mutated, sibling) == R.evaluate_check(basis, sibling)


# ---------------------------------------------------------------------------
# the rung-law controls
# ---------------------------------------------------------------------------

def test_rung_control_laws_declare_the_same_channel_under_different_shapes() -> None:
    ports = R.POOLS * R.PORTS_PER_POOL
    phi = R.rung_law_scales("phi")
    for law in R.RUNG_CONTROL_LAWS:
        scales = R.rung_law_scales(law)
        assert len(scales) == ports, law
    # the shuffled control carries the phi ramp's own multiset, so the two differ only in assignment
    shuffled = R.rung_law_scales("shuffled-phi")
    assert sorted(shuffled) == sorted(phi)
    assert tuple(shuffled) != tuple(phi)
    assert sorted(shuffled) == sorted(R.shuffled_phi_scales())
    assert R.shuffled_phi_scales() == R.shuffled_phi_scales()  # one fixed declared seed
    # the reversed control is the phi ramp reversed
    down = R.rung_law_scales("phi-down")
    assert down == pytest.approx(tuple(reversed(phi)), rel=1e-12)
    # the steep ramps are geometric like phi but with their own declared ratios
    for law, ratio in (("1.5x", 1.5), ("2.0x", 2.0)):
        scales = R.rung_law_scales(law)
        assert all(scales[k] == pytest.approx(ratio ** k, rel=1e-12) for k in range(ports))
        assert ratio != pytest.approx(R.PHI, rel=1e-6)
    # the centred control peaks in the middle and falls away both ways
    centred = R.rung_law_scales("centred")
    peak = max(centred)
    assert centred[R.SINGLE_RUNG_POSITION] == pytest.approx(peak, rel=1e-12)
    assert centred[0] < peak and centred[ports - 1] < peak
    assert centred == pytest.approx(tuple(reversed(centred)), rel=1e-12)
    # the single-position control puts the whole declared shape on one declared position
    single = R.rung_law_scales("single")
    assert sum(1 for value in single if value != 0.0) == 1
    assert single[R.SINGLE_RUNG_POSITION] != 0.0
    with pytest.raises(R.ResonantNumericalError):
        R.rung_law_scales("no-such-control-law")


def test_rung_law_control_arms_carry_one_declared_channel(
    inventory: tuple[R.LatticeArrangement, ...],
) -> None:
    budget = R.motif_reference_weight()
    built = {}
    for arm in inventory:
        if R._family_of(arm.name) != "motif" or not arm.rungs:
            continue
        current = R.build_arrangement(arm)
        # the same body, the same positions and the same declared rung channel total per law
        assert current.rung_weight == pytest.approx(budget, rel=1e-12), arm.name
        assert current.link_weight == 0.0 and current.links == ()
        assert len(current.rung_scales) == R.POOLS * R.PORTS_PER_POOL
        _profile, _built, report = R.arrangement_profile(arm)
        assert report["rung_report"]["canonical_entries_replaced"] == EXPECTED_BRIDGES
        built[arm.name] = current
    assert len(built) == len(R.MOTIF_RUNG_ARMS) + len(R.MOTIF_RUNG_LAW_CONTROL_ARMS)
    # the controls are one-position or ramp shapes, so their scale spans differ from the flat law
    flat = max(abs(v) for v in built[R.MOTIF_RUNG_ARMS[0][0]].rung_scales)
    single = max(abs(v) for v in built["motif-default-rungs-single"].rung_scales)
    assert single > flat
    reversed_phi = max(abs(v) for v in built["motif-default-rungs-phi-down"].rung_scales)
    phi = max(abs(v) for v in built[R.MOTIF_RUNG_ARMS[1][0]].rung_scales)
    assert reversed_phi == pytest.approx(phi, rel=1e-12)


def test_rung_law_control_rows_and_verdicts_match_the_stored_basis(
    receipt: Mapping[str, Any],
) -> None:
    basis = receipt["comparisons"]["basis"]
    per = basis["per_arrangement"]
    controls = receipt["comparisons"]["rung"]["law_controls"]
    rows = {row["rung_law"]: row for row in controls["rows"]}
    assert set(rows) == set(EXPECTED_MOTIF_RUNG_LAWS)
    # every law row's k2/k4/k8 is pinned to a JSON Pointer into the shipped receipt
    for row in controls["rows"]:
        assert set(row["survival_recovery_pointers"]) == {"k2", "k4", "k8"}
        for count, pointer in row["survival_recovery_pointers"].items():
            assert pointer == (
                f"/comparisons/basis/per_arrangement/{row['arrangement']}/survival_recovery/{count}"
            )
            assert _resolve(receipt, pointer) == pytest.approx(row[count], rel=1e-12)
    # the two bare-rung arms are both covered by this table, each with its own row
    assert R.MOTIF_RUNG_ARMS[0][0] in {row["arrangement"] for row in controls["rows"]}
    assert R.MOTIF_RUNG_ARMS[1][0] in {row["arrangement"] for row in controls["rows"]}
    # the shuffled control's declared scales are the phi ramp's under a different assignment:
    # the same multiset, a different scale digest
    assert rows["shuffled-phi"]["rung_scale_sha256"] == R._scale_digest("shuffled-phi")
    assert rows["shuffled-phi"]["rung_scale_sha256"] != rows["phi"]["rung_scale_sha256"]
    assert controls["assignment_controls"]["seed"] == R.SEED
    canonical_k4 = per[basis["uniform_motif_name"]]["survival_recovery"]["k4"]
    # the declared spread is the spread of the stored rows
    k4s = [row["k4"] for row in controls["rows"]]
    assert controls["table"]["k4_spread"] == pytest.approx(max(k4s) - min(k4s), rel=1e-12)
    assert controls["table"]["k4_max"] == pytest.approx(max(k4s), rel=1e-12)
    assert controls["table"]["k4_min"] == pytest.approx(min(k4s), rel=1e-12)
    assert controls["table"]["canonical_k4"] == pytest.approx(canonical_k4, rel=1e-12)
    # the margin the controls are judged against is declared in the receipt
    assert controls["margins"]["law_spread"] == pytest.approx(R.MARGIN_RECOVERY, rel=1e-12)
    assert controls["margins"]["channel_budget"] == pytest.approx(
        R.MARGIN_WEIGHT_INVARIANCE, rel=1e-12
    )
    specificity = controls["phi_specificity"]
    steep = [row["k4"] for row in controls["rows"] if row["rung_law"] in ("1.5x", "2.0x")]
    assert specificity["best_steep_ramp_k4"] == pytest.approx(max(steep), rel=1e-12)
    assert specificity["phi_minus_best_steep_ramp_k4_absolute_difference"] == pytest.approx(
        abs(rows["phi"]["k4"] - max(steep)), rel=1e-9, abs=1e-15
    )
    # the verdict the receipt reports for "is the gain phi-specific?" follows its own measured gap
    gap = specificity["phi_minus_best_steep_ramp_k4_absolute_difference"]
    assert specificity["within_margin"] is bool(gap <= R.MARGIN_RECOVERY)
    assert specificity["reading"] == (
        "shared by the steep ramps" if gap <= R.MARGIN_RECOVERY else "specific to the phi ramp"
    )
    # and the k8 reading is likewise the stored rows' own arithmetic
    k8 = controls["survival_at_k8"]
    assert k8["best_k8"] == pytest.approx(max(row["k8"] for row in controls["rows"]), rel=1e-12)
    assert k8["best_k8_delta_vs_canonical"] == pytest.approx(k8["best_k8"] - canonical_k8(receipt), rel=1e-9, abs=1e-15)
    assert k8["survives"] is bool(k8["best_k8_delta_vs_canonical"] >= R.MARGIN_RECOVERY)
    checks = {row["id"]: row for row in receipt["comparisons"]["checks"]}
    assert checks["rung_law_controls_survive_at_k8"]["holds"] is k8["survives"]
    assert checks["rung_law_controls_from_the_steep_ramps_reach_the_phi_gain"]["holds"] is (
        specificity["within_margin"]
    )
    for check_id, quantity in (
        ("rung_law_controls_separate_the_result", controls["table"]["k4_spread"]),
        ("single_rung_control_moves_survival_k4",
         controls["single_position_control"]["difference_from_canonical_k4"]),
        ("shuffled_phi_rung_control_differs_from_the_phi_ramp",
         controls["assignment_controls"]["shuffled_phi_vs_phi_k4_difference"]),
    ):
        assert checks[check_id]["quantity"] == pytest.approx(quantity, rel=1e-12, abs=1e-15)
        assert checks[check_id]["holds"] is bool(quantity >= R.MARGIN_RECOVERY)


def canonical_k8(receipt: Mapping[str, Any]) -> float:
    basis = receipt["comparisons"]["basis"]
    return float(
        basis["per_arrangement"][basis["uniform_motif_name"]]["survival_recovery"]["k8"]
    )


def test_rung_law_controls_fire_out_of_band(receipt: Mapping[str, Any]) -> None:
    """Every new control is falsifiable: the declared checks appear in both verdicts."""
    declared = {
        "rung_law_controls_separate_the_result",
        "rung_law_controls_from_the_steep_ramps_reach_the_phi_gain",
        "rung_law_controls_survive_at_k8",
        "single_rung_control_moves_survival_k4",
        "shuffled_phi_rung_control_differs_from_the_phi_ramp",
        "phi_rung_ramp_differs_from_its_own_reversal",
        "motif_rung_laws_give_distinct_survival_k4",
        "rung_law_controls_share_the_declared_channel_budget",
    }
    checks = {row["id"]: row for row in receipt["comparisons"]["checks"]}
    firing = {row["id"]: row for row in receipt["comparisons"]["firing_controls"]}
    silenced = {row["id"]: row for row in receipt["comparisons"]["silenced_controls"]}
    assert declared <= set(checks)
    verdicts = set()
    for check_id in declared:
        if checks[check_id]["kind"] == R.KIND_INVARIANCE:
            # the channel-budget invariance is proven by the silenced control, not fired
            assert checks[check_id]["holds"] is True
            assert check_id in receipt["comparisons"]["invariance_checks_without_silenced_control"]
            continue
        assert firing[check_id]["flips"] is True, check_id
        assert firing[check_id]["verdict_before"] is checks[check_id]["holds"]
        assert firing[check_id]["verdict_after"] is not checks[check_id]["holds"]
        verdicts.add(checks[check_id]["holds"])
    # the declared rung-law controls are shown holding and refuted, not only one way
    assert verdicts == {True, False}
    assert set(silenced) <= set(checks)


# ---------------------------------------------------------------------------
# the interaction grid
# ---------------------------------------------------------------------------

def test_interaction_grid_declares_the_declared_rail_fractions(
    inventory: tuple[R.LatticeArrangement, ...],
) -> None:
    budget = R.lattice_reference_weight()
    cells = [arm for arm in inventory if R._family_of(arm.name) == "interaction"]
    assert len(cells) == len(R.INTERACTION_ARMS)
    for arm in cells:
        built = R.build_arrangement(arm)
        fraction = float(arm.rail_fraction)
        assert 0.0 <= fraction <= 1.0
        assert built.link_weight + built.rung_weight == pytest.approx(
            fraction * budget, rel=1e-12
        ), arm.name
        if fraction == 0.0:
            # a zero declared scale is not a declaration: the rail is the field's own rail
            assert built.links == () and built.rung_scales == ()
            assert built.declared_total_weight == 0.0
        else:
            assert built.links and built.rung_scales
            assert len(built.rung_scales) == R.POOLS * R.PORTS_PER_POOL
            assert built.link_weight > 0.0 and built.rung_weight > 0.0
        # the mass leg declares the shell metric and the rail leg the canonical mass metric
        _profile, _built, report = R.arrangement_profile(arm)
        is_mass = report["mass_metric_audit"]["source"].startswith("projected_inv_mass")
        assert is_mass is (arm.mass == "core-shell"), arm.name


def test_interaction_grid_rows_match_the_stored_basis(receipt: Mapping[str, Any]) -> None:
    basis = receipt["comparisons"]["basis"]
    per = basis["per_arrangement"]
    grid = receipt["comparisons"]["interaction"]
    cells = grid["grid"]["cells"]
    assert [cell["rail_fraction"] for cell in cells] == [
        float(value) for value in R.INTERACTION_RAIL_FRACTIONS
    ]
    assert grid["grid"]["rail_budget"] == pytest.approx(
        basis["lattice_reference_weight"], rel=1e-12
    )
    for cell in cells:
        for leg in ("rail_leg_arm", "mass_leg_arm"):
            row = cell[leg]
            assert row is not None, (cell["rail_fraction"], leg)
            measured = per[row["arrangement"]]
            for count in ("k2", "k4", "k8"):
                assert row[count] == pytest.approx(
                    measured["survival_recovery"][count], rel=1e-12
                ), (row["arrangement"], count)
            assert row["rail_fraction"] == cell["rail_fraction"]
            assert row["declared_channel_total_weight"] == pytest.approx(
                R.build_arrangement(R.arrangement_lookup(row["arrangement"])).declared_total_weight,
                rel=1e-12,
            )
        # the mass leg carries the shell metric and the rail leg the canonical metric
        assert cell["mass_leg_arm"]["mass_metric_diagonal_sha256"] != (
            cell["rail_leg_arm"]["mass_metric_diagonal_sha256"]
        )
    # the two ends of the grid are the already-declared arms, reproduced to the declared tolerance
    reproductions = grid["reproductions"]
    assert grid["reproductions"]["max_absolute_difference"] <= R.MARGIN_DERIVATION_REPRODUCTION
    assert all(row["rail_identity"] for row in reproductions["rows"])
    expected_pairs = {
        (R.interaction_arm_name(0.0, "core-shell"), R.ATTRIBUTION_MASS_ONLY_NAME),
        (R.interaction_arm_name(0.0, "canonical"), R.UNIFORM_MOTIF_NAME),
        (R.interaction_arm_name(1.0, "canonical"), R.INTERACTION_RAIL_NAME),
        (R.interaction_arm_name(1.0, "core-shell"), R.INTERACTION_RAIL_MASS_NAME),
    }
    assert {(row["left"], row["right"]) for row in reproductions["rows"]} == expected_pairs
    for row in reproductions["rows"]:
        assert row["survival_max_absolute_difference"] <= R.MARGIN_DERIVATION_REPRODUCTION
    # the grid reproduces the declared arms and the declared arms carry those rows in the basis
    for left, right in expected_pairs:
        assert left in per and right in per


def test_interaction_grid_fit_and_damage_reading_follow_the_stored_cells(
    receipt: Mapping[str, Any],
) -> None:
    grid = receipt["comparisons"]["interaction"]
    terms = grid["interaction_terms"]
    mass = [cell["mass_leg_arm"] for cell in grid["grid"]["cells"]]
    assert terms["spread_of_the_mass_leg_over_the_grid"] == pytest.approx(
        max(row["k4"] for row in mass) - min(row["k4"] for row in mass), rel=1e-12
    )
    fit = grid["fits"]["mass_leg_k4_vs_rail_fraction"]
    fractions = [cell["rail_fraction"] for cell in grid["grid"]["cells"]]
    slope, intercept = np.polyfit(
        np.asarray(fractions, dtype=np.float64),
        np.asarray([row["k4"] for row in mass], dtype=np.float64),
        1,
    )
    assert fit["slope_per_unit_rail_fraction"] == pytest.approx(slope, rel=1e-9)
    assert fit["intercept_at_zero_rail_weight"] == pytest.approx(intercept, rel=1e-9)
    residual = [
        row["k4"] - (slope * fraction + intercept)
        for row, fraction in zip(mass, fractions)
    ]
    assert fit["max_absolute_residual"] == pytest.approx(
        max(abs(value) for value in residual), rel=1e-9, abs=1e-15
    )
    # the damage is read from the cells: monotone only if no step between cells rises
    steps = [mass[i + 1]["k4"] - mass[i]["k4"] for i in range(len(mass) - 1)]
    assert terms["mass_leg_largest_non_monotone_step"] == pytest.approx(
        max([0.0] + [value for value in steps if value > 0.0]), rel=1e-9, abs=1e-15
    )
    assert terms["mass_leg_monotone_decreasing"] is bool(all(value <= 1e-12 for value in steps))
    assert grid["shape_of_the_damage"] == (
        "monotone" if terms["mass_leg_monotone_decreasing"] else "non-monotone or thresholded"
    )
    # the declared margins are the ones the checks use
    checks = {row["id"]: row for row in receipt["comparisons"]["checks"]}
    assert checks["interaction_rail_weight_cuts_the_mass_gain"]["quantity"] == pytest.approx(
        terms["mass_gain_lost_to_the_full_rail_weight"], rel=1e-12
    )
    assert checks["interaction_rail_damage_is_monotone_in_rail_weight"]["holds"] is (
        terms["mass_leg_monotone_decreasing"]
    )
    assert checks["interaction_mass_leg_fit_is_linear_in_rail_weight"]["holds"] is bool(
        fit["max_absolute_residual"] <= grid["margins"]["linear_fit"]
    )
    assert checks["interaction_rail_damage_is_gradual_rather_than_thresholded"]["holds"] is bool(
        terms["half_slope_gap"] <= grid["margins"]["half_slope_gap"]
    )
    assert checks["interaction_grid_reproduces_the_declared_lattice_arms"]["holds"] is True


# ---------------------------------------------------------------------------
# the depth family without the equal-total normalization
# ---------------------------------------------------------------------------

def test_raw_nested_arms_really_vary_the_normalization(
    inventory: tuple[R.LatticeArrangement, ...],
) -> None:
    raw = {arm.name: arm for arm in inventory if not arm.normalized}
    names = {arm.name for arm in inventory}
    assert len(raw) == 1 + len(R.NESTED_RAW_ARMS)
    budget = R.lattice_reference_weight()
    for name, arm in raw.items():
        built = R.build_arrangement(arm)
        assert arm.normalized is False
        # unnormalized means the declared scales are written as the harness produces them
        assert built.normalization_factor == pytest.approx(1.0, rel=1e-12), name
        if arm.name == R.NESTED_ANCHOR_NAME:
            # the anchor carries the un-runged reference law at depth 1, off the equal-total budget
            assert arm.depth == 1 and arm.shell_law == R.NESTED_REFERENCE_LAW
            assert built.link_weight != pytest.approx(budget, rel=1e-3)
            continue
        assert arm.name.endswith("-raw")
        if arm.shell_law == R.NESTED_REFERENCE_LAW:
            # the reference law declares no equal-budget arm at any depth
            assert f"nested-d{arm.depth}-{arm.shell_law}" not in names
            continue
        counterpart = f"nested-d{arm.depth}-{arm.shell_law}"
        assert counterpart in names
        other = R.build_arrangement(R.arrangement_lookup(counterpart))
        assert other.normalized is True
        assert other.link_weight == pytest.approx(budget, rel=1e-12)
        # without the equal-total normalization the declared link channel still falls with depth,
        # which is the difference the depth-normalization control reads
        assert built.link_weight != pytest.approx(other.link_weight, rel=R.MARGIN_RAW_DECLARATION)


def test_depth_normalization_control_matches_the_stored_basis(
    receipt: Mapping[str, Any],
) -> None:
    basis = receipt["comparisons"]["basis"]
    per = basis["per_arrangement"]
    control = receipt["comparisons"]["nested"]["depth_normalization_control"]
    # the declared links are compared against the equal-budget family at the same depth and law
    assert control["declaration_margin"] == pytest.approx(R.MARGIN_RAW_DECLARATION, rel=1e-12)
    assert control["min_relative_declared_link_difference_from_the_equal_budget_family"] >= (
        R.MARGIN_RAW_DECLARATION
    )
    assert control["laws_without_an_equal_budget_counterpart"] == [R.NESTED_REFERENCE_LAW]
    assert control["laws_with_an_equal_budget_counterpart"] == ["uniform"]
    for row in control["raw_declared_link_channel_rows"]:
        measured = per[row["raw_arm"]]
        other = per[row["normalized_arm"]]
        assert row["raw_declared_link_channel"] == pytest.approx(
            measured["declared_link_channel_weight"], rel=1e-12
        )
        assert row["normalized_declared_link_channel"] == pytest.approx(
            other["declared_link_channel_weight"], rel=1e-12
        )
        assert row["relative_difference"] == pytest.approx(
            abs(row["raw_declared_link_channel"] - row["normalized_declared_link_channel"])
            / abs(row["normalized_declared_link_channel"]), rel=1e-9,
        )
    # the spreads are recomputed from the stored rows, per family and per normalization
    for key, rows in (
        ("reference_law_raw_k4", control["reference_law_raw_rows"]),
        ("uniform_law_raw_k4", control["uniform_law_raw_rows"]),
        ("uniform_law_equal_budget_k4", control["uniform_law_equal_budget_rows"]),
    ):
        values = [per[row["arrangement"]]["survival_recovery"]["k4"] for row in rows]
        assert control["spreads"][key] == pytest.approx(max(values) - min(values), rel=1e-12)
        for row in rows:
            assert row["k4"] == pytest.approx(
                per[row["arrangement"]]["survival_recovery"]["k4"], rel=1e-12
            )
            assert row["declared_link_channel_weight"] == pytest.approx(
                per[row["arrangement"]]["declared_link_channel_weight"], rel=1e-12
            )
    assert control["spreads"]["raw_minus_equal_budget_k4"] == pytest.approx(
        control["spreads"]["uniform_law_raw_k4"]
        - control["spreads"]["uniform_law_equal_budget_k4"], rel=1e-9, abs=1e-15
    )
    # the verdict's place is derived from the two spreads and the declared margin
    verdict = control["verdict"]
    flat_budget = control["spreads"]["uniform_law_equal_budget_k4"] <= R.MARGIN_RECOVERY
    flat_raw = control["spreads"]["uniform_law_raw_k4"] <= R.MARGIN_RECOVERY
    assert verdict["flat_depth_axis_under_equal_budget"] is flat_budget
    assert verdict["flat_depth_axis_without_the_normalization_unity_law"] is flat_raw
    assert verdict["place_of_the_flat_axis"] == (
        "depth itself" if (flat_budget and flat_raw)
        else "the equal-total normalization" if flat_budget
        else "the unnormalized reference-law family only"
    )
    assert verdict["reference_law_has_an_equal_budget_counterpart"] is False
    # the declared checks carry those verdicts, and the depth-null check is a real falsification
    checks = {row["id"]: row for row in receipt["comparisons"]["checks"]}
    assert checks["nested_raw_arms_are_declared_without_the_equal_budget_normalization"]["holds"] is True
    assert checks["nested_raw_reference_law_depth_changes_the_result"]["holds"] is (
        control["spreads"]["reference_law_raw_k4"] >= R.MARGIN_RECOVERY
    )
    assert checks["nested_raw_unity_law_depth_changes_the_result"]["holds"] is (
        control["spreads"]["uniform_law_raw_k4"] >= R.MARGIN_RECOVERY
    )
    assert checks["nested_depth_spread_is_the_normalizations_doing"]["holds"] is (
        control["spreads"]["raw_minus_equal_budget_k4"] >= R.MARGIN_RECOVERY
    )
    # the depth axis under the equal-total normalization stays as flat as it was declared
    assert control["spreads"]["uniform_law_equal_budget_k4"] <= R.MARGIN_RECOVERY
    # the flat axis is not the normalization's doing, and the receipt's own check says so
    assert checks["nested_depth_spread_is_the_normalizations_doing"]["holds"] is False
    assert "depth itself" in verdict["place_of_the_flat_axis"]


def test_depth_normalization_control_verdict_flips_under_mutation(
    receipt: Mapping[str, Any],
) -> None:
    basis = receipt["comparisons"]["basis"]
    checks = {check.id: check for check in R.margin_checks()}
    check = checks["nested_depth_spread_is_the_normalizations_doing"]
    before = R.evaluate_check(basis, check)
    assert before["status"] == "measured"
    mutated = json.loads(json.dumps(basis))
    mutated["nested_raw_minus_normalized_k4_spread"] = (
        2.0 * float(check.margin) if not before["holds"] else 0.0
    )
    after = R.evaluate_check(mutated, check)
    assert after["holds"] is not before["holds"]
    fired = R.fire_check(json.loads(json.dumps(basis)), check)
    assert fired["flips"] is True
    assert fired["verdict_before"] is before["holds"]
    assert fired["verdict_after"] is not before["holds"]


def test_receipt_reports_the_refuted_rows_with_their_arms(
    receipt: Mapping[str, Any],
) -> None:
    summary = receipt["comparisons"]["checks_summary"]
    refuted = receipt["comparisons"]["refuted_declared_hypotheses"]
    assert summary["refuted"] == summary["failing"] == len(refuted)
    assert summary["refuted_ids"] == summary["failing_ids"]
    assert {row["check"] for row in refuted} == set(summary["refuted_ids"])
    checks = {row["id"]: row for row in receipt["comparisons"]["checks"]}
    for row in refuted:
        assert checks[row["check"]]["holds"] is False
        assert row["measured_quantity"] == pytest.approx(
            checks[row["check"]]["quantity"], rel=1e-12, abs=1e-15
        )
        assert row["margin"] == pytest.approx(checks[row["check"]]["margin"], rel=1e-12)
        assert row["pointer"].startswith("/comparisons/checks/")
        resolved = _resolve(receipt, row["pointer"])
        assert resolved["id"] == row["check"]
        assert resolved["holds"] is False
        assert resolved["quantity"] == pytest.approx(row["measured_quantity"], rel=1e-12, abs=1e-15)
        assert row["statement"]
    # every refuted check that names arms names the arms it does not cover as well
    coverage = R.check_arm_coverage(receipt["comparisons"]["basis"])
    for row in refuted:
        if row["check"] in coverage:
            assert row["arm_coverage"]["covers_the_arms"] == coverage[row["check"]]["covers_the_arms"]

