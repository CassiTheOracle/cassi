"""Direct tests for the finite-obligations runner.

They hold the runner to the three finite statements it claims to have
recomputed: the corner-shift support action (UFA104) and its cutoff counts, the
fine multiplicity formula (UFA106) with its anchor table, relabelling
invariance and never-zero claim, and the first-chaos rank inequality (UFA46)
with its growth conclusion and its finite threshold screen.

Each item carries a can-fail margin: a control computation that would move the
measured number if the mechanism under test were missing (a suppressed
down-shift, a dropped channel factor, a position-indexed weight, a different
margin d).  Two checks are fired against real quantities: one anchor-table
entry is corrupted, and the receipt digest is driven by a mutated measured
value; both must report the change, so neither check is vacuous.

Everything runs in-process against the same functions the receipt is built
from, so a passing run is evidence about the real measurement.
"""

from __future__ import annotations

import copy
import itertools
import math

import pytest

from run_yang_mills_finite_obligations import (
    ALTERNATE_PAIRING_INDICES,
    ANCHORS,
    ARCSINE_DOMAIN_EDGE,
    CUTOFFS,
    CUTOFF_COUNTS,
    FUNDAMENTAL_SECTOR,
    INVARIANCE_DOMAIN,
    INVARIANCE_DOMAINS,
    PAIRING_CLASS,
    RANK_MARGIN_D,
    SEEDS,
    TABLE_DOMAIN,
    THRESHOLD_D_GRID,
    THRESHOLD_N_VALUES,
    TRIVIAL_SECTOR,
    anchor_mismatches,
    anchor_row_decomposition,
    anchor_row_decompositions,
    chain_eigenvalues,
    corner_shift_targets,
    fixed_rank_escape,
    fuse,
    multiplicity_f,
    multiplicity_table,
    multiplicity_terms,
    multiplicity_with_pairing,
    pairing_class_agreement,
    permutation_invariance,
    position_weighted_variant,
    position_weighted_variant_mismatches,
    rank_bound,
    rank_screen_item,
    reachable_family,
    required_rank,
    run,
    sector_spokes,
    sha256,
    threshold_screen,
)

# Declared separation: on the recomputed 0..3 table the largest value is 364 and
# the minimum is 1, so a non-constant table is separated from a constant one by
# a factor of 364; the margins below sit far inside that gap.
TABLE_SPREAD_MARGIN = 20
# Measured r_N/N over the screen is 0.125, 0.125, 0.15625, 0.15625, 0.15625 with
# asymptote 2 arcsin(d/4)/pi = 0.1608612.  The band is a declared separation
# from zero (which would falsify Omega(N)) and from 1/4 (superlinear).
RANK_FRACTION_BAND = (0.1, 0.2)


@pytest.fixture(scope="module")
def receipt() -> dict:
    return run()


# --- item 1: corner-shift support action (UFA104) --------------------------


def test_fuse_rule_is_the_declared_half_integer_spectrum() -> None:
    assert fuse(0, 1) == (1,)
    assert fuse(1, 1) == (0, 2)
    assert fuse(2, 3) == (1, 3, 5)
    assert fuse(0, 0) == (0,)
    for left in range(9):
        for right in range(9):
            values = fuse(left, right)
            # Odd-step ladder from |m-n| to m+n: a step-1 or parity-breaking
            # rule would fail both assertions below.
            assert len(values) == min(left, right) + 1
            assert all(value % 2 == (left + right) % 2 for value in values)
            assert values[0] == abs(left - right) and values[-1] == left + right


def test_corner_shift_drops_the_down_shift_only_at_label_zero() -> None:
    up_only = tuple(
        tuple(label + 1 if index == position else label for index, label in enumerate(sector))
        for position in range(4)
        for sector in [(0, 0, 0, 0)]
    )
    assert set(corner_shift_targets(TRIVIAL_SECTOR)) == set(up_only)
    assert len(corner_shift_targets(TRIVIAL_SECTOR)) == 4
    assert len(corner_shift_targets(FUNDAMENTAL_SECTOR)) == 8
    targets = corner_shift_targets((0, 2, 1, 0))
    # 6 = four up-shifts plus one down-shift from each of the two positive labels.
    assert len(targets) == 6
    assert all(min(target) >= 0 for target in targets)
    assert sum(1 for target in targets if sum(target) < 3) == 2
    # Margin: the down-shift branch is not decorative -- dropping it removes
    # exactly the targets of positive labels.
    assert set(targets) != set(up_only)


def test_reachable_family_is_the_full_cutoff_box(receipt: dict) -> None:
    rows = {tuple(row["seed"]): {} for row in receipt["support_action"]["cutoffs"]}
    for row in receipt["support_action"]["cutoffs"]:
        seed = tuple(row["seed"])
        cutoff = row["cutoff"]
        rows[seed][cutoff] = row
        assert row["reachable_count"] == CUTOFF_COUNTS[cutoff] == (cutoff + 1) ** 4
        assert row["full_cone_reached"]
        assert sum(row["layer_sizes"]) == row["reachable_count"]
        assert row["layer_sizes"][0] == 1
        # Every step changes one corner label by one, so the closure step is
        # the graph eccentricity: 4C from the trivial seed, max(4, 4(C-1))
        # from the fundamental seed because it can also walk down to the origin.
        expected_step = 4 * cutoff if seed == TRIVIAL_SECTOR else max(4, 4 * (cutoff - 1))
        assert row["closure_step"] == expected_step
    assert receipt["support_action"]["count_mismatches"] == []
    for cutoff in CUTOFFS:
        assert rows[TRIVIAL_SECTOR][cutoff]["closure_step"] == 4 * cutoff
        assert rows[FUNDAMENTAL_SECTOR][cutoff]["closure_step"] == max(4, 4 * (cutoff - 1))
    # The C=1 family is literally the whole box, sector by sector.
    assert {
        tuple(sector) for sector in rows[TRIVIAL_SECTOR][1]["reachable"]
    } == set(itertools.product(range(2), repeat=4))


def test_reachable_count_is_sensitive_to_the_down_shift() -> None:
    """Margin: a monotone-only action keeps labels in 1..C and never reaches the box."""

    def monotone_only(seed: tuple[int, ...], cutoff: int) -> int:
        seen = {seed}
        frontier = [seed]
        while frontier:
            nxt = []
            for sector in frontier:
                for target in corner_shift_targets(sector):
                    if max(target) > cutoff or target in seen:
                        continue
                    if any(target[index] < sector[index] for index in range(4)):
                        continue
                    seen.add(target)
                    nxt.append(target)
            frontier = nxt
        return len(seen)

    for cutoff in CUTOFFS:
        # Without down-shifts the fundamental seed never reaches a zero label,
        # so the closed family is the labelled box 1..C, not 0..C.
        assert monotone_only(FUNDAMENTAL_SECTOR, cutoff) == cutoff**4
        assert reachable_family(FUNDAMENTAL_SECTOR, cutoff)["reachable_count"] == (
            cutoff + 1
        ) ** 4
    assert monotone_only(FUNDAMENTAL_SECTOR, 1) == 1
    assert monotone_only(FUNDAMENTAL_SECTOR, 2) == 16


# --- item 2: fine multiplicity (UFA106) ------------------------------------


def test_anchor_table_recomputed_and_check_fires_on_corruption() -> None:
    computed = {
        sector: multiplicity_f(*sector) for sector in itertools.product(range(4), repeat=4)
    }
    anchors = {sector: computed[sector] for sector in ANCHORS}
    assert anchors == ANCHORS
    assert anchor_mismatches(anchors) == []
    # Firing control: corrupt one real anchor value in the recomputed table.
    corrupted = dict(computed)
    culprit = (1, 1, 1, 1)
    corrupted[culprit] = computed[culprit] + 1
    mismatches = anchor_mismatches(corrupted)
    assert mismatches == [
        {"sector": list(culprit), "measured": 15, "document_value": 14}
    ]
    # The genuine formula value is not the corrupted one, so the check above
    # cannot pass by accident on a table that recomputes 15.
    assert multiplicity_f(*culprit) == 14


def test_pairing_independence_with_falsification_margin() -> None:
    assert ALTERNATE_PAIRING_INDICES == ((0, 3), (1, 2))
    for sector in itertools.product(range(4), repeat=4):
        assert multiplicity_f(*sector) == multiplicity_f(*sector, "alternate")
    class_check = pairing_class_agreement()
    assert [row["pairing"] for row in class_check["rows"]] == [
        name for name, _ in PAIRING_CLASS
    ]
    assert class_check["all_three_matchings_agree"]
    # Margin: the pairing choice is not irrelevant in general -- a pairing that
    # pairs a spoke with itself disagrees somewhere, so the agreement above is a
    # real property of the three declared matchings.
    disagreements = 0
    for sector in itertools.product(range(3), repeat=4):
        broken = multiplicity_terms(sector, ((0, 0), (1, 2)))
        declared = multiplicity_terms(sector)
        if sum(count for _, count in broken) != sum(count for _, count in declared):
            disagreements += 1
    assert disagreements > 0


def test_relabelling_invariance_document_claim_and_stronger_statement(receipt: dict) -> None:
    square_symmetries = [
        (0, 1, 2, 3),
        (1, 2, 3, 0),
        (2, 3, 0, 1),
        (3, 0, 1, 2),
        (0, 3, 2, 1),
        (3, 2, 1, 0),
        (2, 1, 0, 3),
        (1, 0, 3, 2),
    ]
    table = multiplicity_table(TABLE_DOMAIN)
    for permutation in square_symmetries:
        for key, value in table.items():
            sector = tuple(int(part) for part in key.split(","))
            permuted = tuple(sector[index] for index in permutation)
            assert multiplicity_f(*permuted) == value
    evidence = receipt["multiplicity_table"]["relabelling_invariance"]
    assert evidence["document_claim_verified"]
    assert evidence["document_claim_replaced_by_full_symmetric_group"]
    assert not evidence["asymmetry_found_in_multiplicity"]
    # The status field states the scan as the basis and leaves the mechanism
    # open, with a named candidate only.
    status = evidence["status"]
    assert "established by the scan" in status
    assert "correct but not tight" in status
    assert "mechanism is left open" in status
    assert "candidate" in status and "recoupling identity" in status
    assert "reindex" not in status
    # Measured strengthening over three domains: all 24 relabellings preserve
    # the table, and no mismatch appears even on sectors carrying a zero label,
    # where the V_0 tensor V_1 = V_1 branch is active.
    domains = {row["domain"]: row for row in evidence["domains"]}
    assert sorted(domains) == list(INVARIANCE_DOMAINS)
    assert INVARIANCE_DOMAIN >= 5
    for domain, row in domains.items():
        assert row["preserving_count"] == math.factorial(4)
        assert row["permutation_mismatches"] == 0
        assert row["zero_label_subdomain_mismatches"] == 0
        assert row["sectors"] == (domain + 1) ** 4
        assert len(row["preserving_permutations"]) == row["preserving_count"]
    # The measured result carries the same domains under a keyed summary.
    summary = receipt["measured_result"]["relabelling_invariance"]["domains"]
    assert sorted(int(domain) for domain in summary) == list(INVARIANCE_DOMAINS)
    assert all(entry["permutation_mismatches"] == 0 for entry in summary.values())
    assert permutation_invariance(INVARIANCE_DOMAIN)["sectors_with_a_zero_label"] > 0


def test_relabelling_invariance_check_can_fail() -> None:
    """Margin: a position-indexed variant is not invariant, so the check is falsifiable."""
    control = position_weighted_variant_mismatches(TABLE_DOMAIN)
    assert control["mismatches"] > 0
    assert not control["invariant"]
    assert control["witness"] is not None
    witness = control["witness"]
    assert witness["value"] != witness["permuted_value"]
    assert control["mismatches"] < 24 * (TABLE_DOMAIN + 1) ** 4
    # The variant weights the same spoke configurations as the real sum, so the
    # failure is caused by the position weighting alone.
    assert len(multiplicity_terms((2, 2, 1, 1))) == 24
    assert position_weighted_variant(1, 1, 1, 1) == 8 < multiplicity_f(1, 1, 1, 1) == 14
    assert position_weighted_variant(2, 2, 1, 1) == 11 < multiplicity_f(2, 2, 1, 1) == 30


def test_fine_multiplicity_never_zero_with_spread_margin() -> None:
    table = multiplicity_table(TABLE_DOMAIN)
    values = list(table.values())
    assert min(values) == 1
    assert all(value > 0 for value in values)
    # Margin: the table is far from constant, so "minimum 1" is not degenerate.
    assert max(values) >= TABLE_SPREAD_MARGIN
    minimum_sectors = {
        tuple(int(part) for part in key.split(","))
        for key, value in table.items()
        if value == 1
    }
    assert minimum_sectors == {
        (0, 0, 0, 0),
        *[
            tuple(value if index == position else 0 for index in range(4))
            for position in range(4)
            for value in range(1, TABLE_DOMAIN + 1)
        ],
    }
    assert len(minimum_sectors) == 1 + 4 * TABLE_DOMAIN


def test_anchor_row_decompositions_sum_to_the_table_values(receipt: dict) -> None:
    fundamental = anchor_row_decomposition(FUNDAMENTAL_SECTOR)
    assert fundamental["weight_decomposition"] == [1, 0, 6, 4, 3]
    assert fundamental["agrees_with_document_decomposition"]
    assert fundamental["configurations"] == 16
    assert fundamental["contributing_configurations"] == 12
    assert receipt["multiplicity_table"]["anchor_row_decompositions"][
        "all_document_decompositions_agree"
    ]

    expected = {
        (1, 1, 1, 1): ([1, 0, 6, 4, 3], 16, 12),
        (2, 1, 1, 1): ([0, 0, 2, 8, 9], 16, 14),
        (2, 2, 1, 1): ([0, 0, 2, 11, 17], 24, 21),
    }
    decompositions = anchor_row_decompositions()
    rows = {tuple(row["sector"]): row for row in decompositions["rows"]}
    assert set(rows) == set(expected)
    for sector, (weights, configurations, contributing) in expected.items():
        row = rows[sector]
        assert row["weight_decomposition"] == weights
        assert row["configurations"] == configurations
        assert row["contributing_configurations"] == contributing
        assert sum(weights) == row["table_value"] == ANCHORS[sector]
        assert row["weights_sum_to_table_value"]
        assert sum(
            int(value) for value in row["contributing_configurations_by_active_spokes"].values()
        ) == contributing
        assert sum(
            int(value) for value in row["configuration_counts_by_active_spokes"].values()
        ) == configurations
    # Margin: the channel factor is load-bearing -- the weight total exceeds the
    # number of contributing configurations for two of the three anchors.
    assert rows[(2, 1, 1, 1)]["table_value"] > rows[(2, 1, 1, 1)]["contributing_configurations"]
    assert rows[(2, 2, 1, 1)]["table_value"] > rows[(2, 2, 1, 1)]["contributing_configurations"]
    assert decompositions["all_weights_sum_to_table_value"]
    # Every spoke contributes: the spoke label sets are exactly the four fuse sets.
    assert sector_spokes(FUNDAMENTAL_SECTOR) == ((0, 2), (0, 2), (0, 2), (0, 2))
    assert sector_spokes((2, 1, 1, 1)) == ((1, 3), (0, 2), (0, 2), (1, 3))


# --- item 3: first-chaos rank screen (UFA46) -------------------------------


def test_rank_screen_values_and_linear_growth(receipt: dict) -> None:
    rows = receipt["rank_screen"]["rows"]
    assert [row["N"] for row in rows] == [8, 16, 32, 64, 128]
    assert [row["required_rank"] for row in rows] == [1, 2, 5, 10, 20]
    for row in rows:
        n = row["N"]
        bound = rank_bound(n, RANK_MARGIN_D)
        assert row["bound"] == pytest.approx(bound)
        # Minimal integer: r_N + 1 clears the bound and r_N does not.
        assert row["required_rank"] + 1 >= bound > row["required_rank"]
        assert row["required_rank"] < n
        assert row["rank_fraction"] == pytest.approx(row["required_rank"] / n)
    growth = receipt["rank_screen"]["growth"]
    asymptote = 2.0 / math.pi * math.asin(RANK_MARGIN_D / 4.0)
    assert growth["asymptote_constant_2_over_pi_arcsin_d_over_4"] == pytest.approx(asymptote)
    ratios = growth["rank_over_N"]
    assert ratios == [1 / 8, 2 / 16, 5 / 32, 10 / 64, 20 / 128]
    for ratio in ratios:
        assert RANK_FRACTION_BAND[0] <= ratio <= RANK_FRACTION_BAND[1]
    assert ratios == sorted(ratios)
    # Omega(N) in the measured sense: a positive fraction of N, rising toward
    # the declared asymptote rather than decaying.
    assert min(ratios) >= RANK_FRACTION_BAND[0]
    assert growth["last_ratio_over_asymptote"] > growth["first_ratio_over_asymptote"]
    assert growth["last_ratio_over_asymptote"] > 0.9
    assert growth["degree_one_slope_fit"] == pytest.approx(asymptote, rel=0.05)


def test_rank_screen_is_sensitive_to_the_margin_d() -> None:
    """Margin: halving the declared margin d must lower the required rank."""

    strict = [required_rank(n, RANK_MARGIN_D) for n in (8, 16, 32, 64, 128)]
    loose = [required_rank(n, RANK_MARGIN_D / 2) for n in (8, 16, 32, 64, 128)]
    assert loose[0] == 0 and strict[0] == 1
    assert loose[-1] < strict[-1]
    assert all(loose[index] <= strict[index] for index in range(5))
    with pytest.raises(ValueError):
        rank_bound(8, 0.0)


def test_maximum_admissible_rank_boundary_and_gamma_N(receipt: dict) -> None:
    boundary = receipt["rank_screen"]["boundary"]
    # The map's own statement, quoted, so a reader sees refinement not correction.
    assert "0 < d <= 4" in boundary["map_fixed_rank_statement"]
    assert "fixed-rank retained first-chaos space" in boundary["map_fixed_rank_statement"]
    assert "Omega(N)" in boundary["map_fixed_rank_statement"]
    assert "does not correct that statement" in boundary["map_fixed_rank_statement"]
    assert "refines" in boundary["refinement_not_correction"]
    assert boundary["arcsine_domain_edge_d"] == ARCSINE_DOMAIN_EDGE == 4.0
    assert boundary["arcsine_domain_edge_refusal"]
    # The arcsine argument's own domain edge: the bound is exactly N + 1 at
    # d = 4, and no value is defined by the inequality above it.
    for n in (8, 16, 64):
        assert rank_bound(n, 4.0) == pytest.approx(n + 1)
        with pytest.raises(ValueError):
            rank_bound(n, 4.0 + 1e-9)
    # The refinement: with the largest rank the map permits, r_N = N - 1, the
    # condition holds exactly while d <= gamma_N, one epsilon either side.
    for row in boundary["rows"]:
        n = row["N"]
        gamma_n = chain_eigenvalues(n)[-1]
        assert row["maximum_admissible_rank"] == n - 1
        assert row["maximum_admissible_rank_boundary_gamma_N"] == pytest.approx(gamma_n)
        assert 3.9 < gamma_n < 4.0
        assert required_rank(n, gamma_n) == n - 1
        assert required_rank(n, gamma_n + 1e-6) == n
        assert row["rank_one_epsilon_above_boundary"] == n
        assert row["rank_one_epsilon_above_boundary_exceeds_maximum_rank"]
        assert row["rank_at_arcsine_domain_edge"] == n
    assert boundary["boundary_is_gamma_N_for_the_maximum_admissible_rank"]
    # The map's fixed-rank conclusion exercised on declared rows: for a fixed
    # rank and a fixed margin inside 0 < d <= 4 the ladder eventually exceeds it.
    escape = boundary["fixed_rank_escape"]
    assert escape == fixed_rank_escape()
    assert escape["every_declared_fixed_rank_is_exceeded"]
    for row in escape["rows"]:
        assert row["first_N_exceeding_fixed_rank"] > 0
        assert row["rank_at_witness"] > row["fixed_rank"]
        assert 0.0 < row["d"] <= ARCSINE_DOMAIN_EDGE
    ladder = [2**exponent for exponent in range(1, 15)]
    for row in escape["rows"]:
        smaller = [n for n in ladder if n < row["first_N_exceeding_fixed_rank"]]
        assert all(required_rank(n, row["d"]) <= row["fixed_rank"] for n in smaller)


def test_threshold_screen_grid_and_first_failure(receipt: dict) -> None:
    screen = receipt["rank_screen"]["threshold_screen"]
    assert screen["d_grid"] == list(THRESHOLD_D_GRID)
    assert screen["n_values"] == list(THRESHOLD_N_VALUES)
    assert min(THRESHOLD_D_GRID) == 1.0 and max(THRESHOLD_D_GRID) == ARCSINE_DOMAIN_EDGE
    assert 3.9 in THRESHOLD_D_GRID and 3.999 in THRESHOLD_D_GRID
    assert screen["rows"] == threshold_screen()["rows"]
    assert "0 < d <= 4" in screen["map_fixed_rank_statement"]
    assert screen["arcsine_domain_edge_d"] == ARCSINE_DOMAIN_EDGE
    assert "refinement, not a correction" in screen["consequence"]
    for row in screen["rows"]:
        n = row["N"]
        gamma_n = chain_eigenvalues(n)[-1]
        assert row["maximum_admissible_rank"] == n - 1
        assert row["boundary_gamma_N"] == pytest.approx(gamma_n)
        assert row["failing_d_interval_for_maximum_rank"] == f"d > {gamma_n!r}"
        ranks = [entry["required_rank"] for entry in row["grid_rows"]]
        assert ranks == sorted(ranks)  # required rank grows with the margin
        assert all(
            entry["rank_less_than_N"] == (entry["required_rank"] < n)
            for entry in row["grid_rows"]
        )
        # One grid step inside and the first failing grid step outside.
        failing = row["first_failing_grid_d"]
        inside = row["last_admissible_grid_d"]
        assert inside < failing
        assert inside <= gamma_n < failing
        assert required_rank(n, inside) < n
        assert required_rank(n, failing) >= n
        assert row["rank_at_boundary"] == n - 1
        assert row["rank_at_arcsine_domain_edge"] == n
        assert 0.0 < row["edge_minus_gamma_N"] < 0.1
        # The two grid points bracket the boundary: no grid point sits strictly
        # between them, so the first failure is located to grid resolution.
        assert not [
            d for d in THRESHOLD_D_GRID if inside < d < failing
        ]
    # The boundary sequence tends to the arcsine domain edge from below.
    differences = [row["edge_minus_gamma_N"] for row in screen["rows"]]
    assert differences == sorted(differences, reverse=True)
    assert differences[-1] < differences[0]
    assert screen["limit_gamma_N"] == ARCSINE_DOMAIN_EDGE
    assert screen["every_N_first_failure_below_edge"]


# --- receipt ---------------------------------------------------------------


def test_receipt_is_deterministic_and_digest_is_sensitive(receipt: dict) -> None:
    second = run()
    assert second["receipt_sha256"] == receipt["receipt_sha256"]
    assert second["measured_result"] == receipt["measured_result"]
    assert receipt["schema"] == "cassifi.yang-mills-finite-obligations.v1"
    assert receipt["duplication_check"]["not_found"]
    # Firing control on the digest: changing one recomputed quantity changes it.
    mutated = copy.deepcopy(receipt)
    mutated["measured_result"]["anchor_table"]["1,1,1,1"] = 15
    stripped = {
        key: value
        for key, value in mutated.items()
        if key not in ("receipt_sha256", "wall_seconds")
    }
    assert sha256(stripped) != receipt["receipt_sha256"]
    # Same control on a wall-clock-only difference: timing must not enter the digest.
    timing_only = {
        key: value
        for key, value in receipt.items()
        if key not in ("receipt_sha256", "wall_seconds")
    }
    assert sha256(timing_only) == receipt["receipt_sha256"]
    assert receipt["measured_result"]["reachable_counts"] == {
        f"C={cutoff},seed={seed}": CUTOFF_COUNTS[cutoff]
        for cutoff in CUTOFFS
        for seed in SEEDS
    }
    assert receipt["rank_screen"]["growth"]["growing_linearly"]
    assert receipt["conventions"]["mandated_cutoffs"] == [1, 2, 3]
    assert "supplemental" in receipt["conventions"]


def test_receipt_scope_line_states_the_finite_scope(receipt: dict) -> None:
    scope = receipt["scope"]
    assert "finite" in scope
    assert "uniform-in-cutoff" in scope
    assert "continuum" in scope
    assert "(UFA105)" in scope
    assert "multiplicity-space bases" in scope
    assert len(receipt["multiplicity_table"]["table"]) == (TABLE_DOMAIN + 1) ** 4
    assert receipt["multiplicity_table"]["table"]["1,1,1,1"] == ANCHORS[(1, 1, 1, 1)]
    assert rank_screen_item()["rows"] == receipt["rank_screen"]["rows"]
    assert multiplicity_with_pairing((2, 2, 1, 1), ((0, 1), (2, 3))) == 30
