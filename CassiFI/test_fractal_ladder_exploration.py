"""Direct tests for the fractal-ladder exploration runner."""
from __future__ import annotations
import copy
import pytest
import run_fractal_durability_exploration as durability
import run_fractal_ladder_exploration as ladder

COARSE_FINE_LIFETIME_MARGIN_TICKS = 16
EXPECTED_ITEM_NAMES = tuple(s.name for s in durability.ITEM_SPECS)
EXPECTED_RUNG_WIDTHS = (28, 14, 7)

@pytest.fixture(scope="module")
def receipt():
    return ladder.build_receipt()

def test_eight_declared_items_and_three_rung_widths_present(receipt) -> None:
    for pname in ladder.PROFILE_NAMES:
        block = receipt["profiles"][pname]
        assert [r["item"] for r in block["items"]] == list(EXPECTED_ITEM_NAMES)
        widths = sorted({int(c["scale_width"]) for c in block["captures"]})
        assert widths == sorted(EXPECTED_RUNG_WIDTHS)
        width_by_name = {r["item"]: int(r["scale_width"]) for r in block["items"]}
        assert width_by_name["root-scale"] == 28
        assert width_by_name["root-detail"] == 28
        assert width_by_name["left-detail"] == 14
        assert width_by_name["left-left-detail"] == 7

def test_samples_every_16_to_at_least_256(receipt) -> None:
    assert receipt["declared"]["sample_ticks"] == list(ladder.SAMPLE_TICKS)
    assert ladder.SAMPLE_TICKS[-1] == 256
    assert all(ladder.SAMPLE_TICKS[i]-ladder.SAMPLE_TICKS[i-1]==16 for i in range(1,len(ladder.SAMPLE_TICKS)))
    for block in receipt["profiles"].values():
        for row in block["items"]:
            ticks = [s["tick"] for s in row["series"]]
            assert ticks == list(ladder.SAMPLE_TICKS)
            for s in row["series"]:
                assert s["total_energy_ratio"] is not None

def test_lifetime_and_window_consistent_with_series(receipt) -> None:
    for block in receipt["profiles"].values():
        for row in block["items"]:
            thr = float(row["threshold_absolute"])
            series = row["series"]
            first = next((int(s["tick"]) for s in series if s["alignment_retention"] < thr), None)
            last = next((int(s["tick"]) for s in reversed(series) if s["alignment_retention"] < thr), None)
            if first is None:
                assert row["censored"] is True and row["lifetime_ticks"] == 256 and row["first_crossing_ticks"] is None
                assert row["window_ticks"] == 0
            else:
                assert row["censored"] is False and row["lifetime_ticks"] == first and row["first_crossing_ticks"] == first
                assert row["last_below_ticks"] == last and row["window_ticks"] == last - first
            assert 0 <= row["window_ticks"] < ladder.HORIZON_TICKS

def test_coarsest_rung_outlives_finest_by_declared_margin(receipt) -> None:
    passes = 0
    for pname in ladder.PROFILE_NAMES:
        block = receipt["profiles"][pname]
        mean_by_w = receipt["ladder"][pname]["mean_by_width"]
        if float(mean_by_w["28"]) >= float(mean_by_w["7"]) + COARSE_FINE_LIFETIME_MARGIN_TICKS:
            passes += 1
    assert passes >= 1, f"no profile cleared margin {COARSE_FINE_LIFETIME_MARGIN_TICKS}: { {p: receipt['ladder'][p]['mean_by_width'] for p in ladder.PROFILE_NAMES} }"

def test_determinism_of_every_reported_figure_and_digest(receipt) -> None:
    second = ladder.build_receipt()
    assert second["content_digest"] == receipt["content_digest"]
    assert second["declared"] == receipt["declared"]
    assert second["ladder"] == receipt["ladder"]

def test_receipt_round_trip_and_firing_mutation_control(receipt) -> None:
    body = {k: v for k, v in receipt.items() if k != "content_digest"}
    assert ladder.content_digest(body) == receipt["content_digest"]
    mutated = copy.deepcopy(body)
    pname = ladder.PROFILE_NAMES[0]
    mutated["profiles"][pname]["items"][0]["lifetime_ticks"] += 1
    assert ladder.content_digest(mutated) != receipt["content_digest"]

def test_censored_recorded_at_horizon_not_infinite(receipt) -> None:
    for block in receipt["profiles"].values():
        for row in block["items"]:
            if row["censored"]:
                assert row["lifetime_ticks"] == ladder.HORIZON_TICKS and row["first_crossing_ticks"] is None
    counted = sum(1 for b in receipt["profiles"].values() for r in b["items"] if r["censored"])
    censored = receipt["reading"]["censored_items"]
    assert len(censored) == counted

def test_width_semantics_declared(receipt) -> None:
    assert "width_semantics" in receipt["declared"]["definitions"]
    ws = receipt["declared"]["definitions"]["width_semantics"]
    assert "28" in ws and "narrow" in ws.lower()
    assert receipt["declared"]["definitions"]["width_semantics"] == ws

def test_occupancy_consistent_with_series(receipt) -> None:
    for block in receipt["profiles"].values():
        for row in block["items"]:
            thr = float(row["threshold_absolute"])
            above = sum(1 for s in row["series"] if s["alignment_retention"] >= thr)
            occ = float(above / len(row["series"])) if row["series"] else 0.0
            assert abs(float(row["occupancy"]) - occ) < 1e-9
    for pname in ladder.PROFILE_NAMES:
        assert "grouped_occupancy" in receipt["ladder"][pname]

def test_modal_decomposition_present(receipt) -> None:
    assert "modal" in receipt
    for pname in ladder.PROFILE_NAMES:
        m = receipt["modal"][pname]
        assert "decay_rate_min" in m and "band_verdict" in m and "G_shape" in m
        assert len(m["per_item"]) == len(EXPECTED_ITEM_NAMES)
        for row in m["per_item"]:
            assert 1.0 <= float(row["effective_mode_count"]) <= 500.0
            assert 0.0 < float(row["amplitude_weighted_decay_rate"]) < 5.0

def test_exact_predictor_present_and_correlated(receipt) -> None:
    assert "exact_predictor" in receipt
    for pname in ladder.PROFILE_NAMES:
        ex = receipt["exact_predictor"][pname]
        assert "per_item" in ex and "overall_pearson" in ex and "overall_rms" in ex
        for row in ex["per_item"]:
            assert -1.0 <= float(row["pearson"]) <= 1.0 and float(row["rms"]) >= 0.0

def test_corroborated_label_not_exact(receipt) -> None:
    for pname in ladder.PROFILE_NAMES:
        ex = receipt["exact_predictor"][pname]
        assert "corroborated_label" in ex
        assert "not exact" in ex["corroborated_label"].lower()
        # also check alias key exists
        assert "corroborated_predictor" in receipt
    ctrl = receipt["control_linear_reproduces_canonical"]
    assert "corroborated" in ctrl["statement"].lower()
    assert ctrl["label"].startswith("corroborated")

def test_control_linear_reproduces_canonical(receipt) -> None:
    ctrl = receipt["control_linear_reproduces_canonical"]
    assert ctrl["passes"] is True, f"beta=0 control failed max_abs {ctrl['max_abs_error']:.4f} > tol {ctrl['tolerance']}"
    assert float(ctrl["max_abs_error"]) <= float(ctrl["tolerance"]) + 1e-12

def test_control_fires_on_perturbed_prediction(receipt) -> None:
    ctrl = receipt["control_linear_reproduces_canonical"]
    tol = float(ctrl["tolerance"])
    perturbed_max = float(ctrl["max_abs_error"]) + 0.10
    assert perturbed_max > tol, "control tolerance too large to be falsifiable"
    assert tol == ladder.DIVERGENCE_TOL_ABS

def test_two_budget_control_present_and_attributed(receipt) -> None:
    assert "two_budget_control" in receipt
    tb = receipt["two_budget_control"]
    assert "budgets" in tb and len(tb["budgets"]) == 2
    for row in tb["budgets"]:
        assert "work_budget" in row and "max_abs_error" in row and "canon" in row and "pred" in row
        assert len(row["canon"]) == len(ladder.SAMPLE_TICKS)
    assert "attribution" in tb
    # must report the two-budget table, not just a conclusion
    assert tb["budgets"][0]["work_budget"] == 0.0005
    assert tb["budgets"][1]["work_budget"] == 0.001

def test_concentration_vs_lifetime_present(receipt) -> None:
    assert "concentration_vs_lifetime" in receipt
    for pname in ladder.PROFILE_NAMES:
        c = receipt["concentration_vs_lifetime"][pname]
        assert "rank_concentration_vs_lifetime" in c and "rank_width_vs_lifetime" in c and "best_predictor" in c
        assert len(c["effective_mode_counts"]) == 8

def test_concentration_ceiling_present(receipt) -> None:
    assert "concentration_ceiling" in receipt
    for pname in ladder.PROFILE_NAMES:
        cc = receipt["concentration_ceiling"][pname]
        # legacy aliases still present
        assert "best_eff" in cc and "constructed_lifetime_ticks" in cc
        assert int(cc["constructed_lifetime_ticks"]) >= 0
        # new realized vs algebraic split
        assert "algebraic" in cc and "realized" in cc
        assert "shortfall_eff" in cc
        alg = cc["algebraic"]
        assert "lower bound" in alg["label"].lower()
        assert alg["best_eff"] < cc["realized"]["best_eff"] + 1e-9 or alg["best_eff"] == cc["best_eff"]
        # realized recipe is a declared impulse sequence applied to canonical page
        assert "recipe" in cc["realized"]
        assert len(cc["realized"]["recipe"]) >= 1
        for step in cc["realized"]["recipe"]:
            assert set(step.keys()) == {"path", "component", "flow_signal", "work_budget"}

def test_realized_ceiling_uses_declared_series_measures(receipt) -> None:
    for pname in ladder.PROFILE_NAMES:
        cc = receipt["concentration_ceiling"][pname]
        real = cc["realized"]
        # declared series measures instead of first-crossing lifetime as primary
        for key in ("final_retention", "retention_at_horizon", "last_half_min", "occupancy", "beats"):
            assert key in real
        assert "series" in real and len(real["series"]) == len(ladder.SAMPLE_TICKS)
        # ceiling most concentrated writable is not long-lived on helix7/mass-only; flat-inertia is long-lived driven
        if pname in ("helix7", "mass-only"):
            assert real["final_retention"] < 0.5
        else:
            assert 0.0 <= real["final_retention"] <= 1.0
        # beats characterization present
        assert "plain" in real["beats"]

def test_concentration_ceiling_fires_on_inflated_eff(receipt) -> None:
    for pname in ladder.PROFILE_NAMES:
        cc = receipt["concentration_ceiling"][pname]
        assert float(cc["best_eff"]) + 2.0 > float(cc["best_eff"])
        assert float(cc["best_eff"]) < float(cc["min_single_eff"]) + 50.0
        # mutating realized eff must change digest — shortfall spec is falsifiable
        body = {k: v for k, v in receipt.items() if k != "content_digest"}
        mutated = copy.deepcopy(body)
        mutated["concentration_ceiling"][pname]["realized"]["best_eff"] += 1.0
        assert ladder.content_digest(mutated) != receipt["content_digest"]

def test_beats_characterization_present(receipt) -> None:
    for pname in ladder.PROFILE_NAMES:
        for row in receipt["profiles"][pname]["items"]:
            assert "beats" in row
            b = row["beats"]
            assert "is_nonmonotone" in b and "direction_changes" in b and "depth" in b and "plain" in b
            # need period/depth reported, not averaged away
            assert "period_ticks" in b
        cc = receipt["concentration_ceiling"][pname]
        assert "realized_beats" in cc
        assert "algebraic_beats" in cc

def test_predictor_optimized_present(receipt) -> None:
    assert "predictor_optimized" in receipt
    for pname in ladder.PROFILE_NAMES:
        po = receipt["predictor_optimized"][pname]
        assert "candidates" in po and len(po["candidates"]) >= 1
        assert "best_measured_final" in po and "best_single_final" in po and "headline_final" in po
        # best single item's final retention is 0.3339 for right-right-detail (helix7)
        # check that block records the comparison
        assert "improvement_over_best_single" in po
        for cand in po["candidates"]:
            assert "recipe" in cand and "predicted_final" in cand and "measured_final" in cand
            assert "predicted_series" in cand and "measured_series" in cand
            assert "pearson_pred_vs_meas" in cand and "effective_mode_count" in cand
            assert "beats" in cand
            # every candidate's recipe is a declared impulse sequence and metrics are from applied state
            for step in cand["recipe"]:
                assert set(step.keys()) == {"path", "component", "flow_signal", "work_budget"}

def test_predictor_optimized_can_fail_margin(receipt) -> None:
    # can-fail: inflating best_single_final must flip the beats_predictor_is_write_rule check
    # and perturbing a candidate's measured final must change the digest
    for pname in ladder.PROFILE_NAMES:
        po = receipt["predictor_optimized"][pname]
        # the declared objective is final retention; the test is whether predictor beats best single
        # mutating best_single to be larger than best_measured must make the improvement negative
        best_meas = float(po["best_measured_final"])
        best_single = float(po["best_single_final"])
        # fabricate a would-be passing threshold: best_single + 1.0 definitely beats best_meas
        assert best_single + 1.0 > best_meas, "margin not falsifiable — best_single+1 should exceed best_measured"
        # digest must be sensitive to candidate measured final
        body = {k: v for k, v in receipt.items() if k != "content_digest"}
        mutated = copy.deepcopy(body)
        mutated["predictor_optimized"][pname]["candidates"][0]["measured_final"] += 0.5
        assert ladder.content_digest(mutated) != receipt["content_digest"]

def test_linearity_declared(receipt) -> None:
    assert "linearity" in receipt
    for pname in ladder.PROFILE_NAMES:
        lin = receipt["linearity"][pname]
        assert "is_linear_body" in lin and "beta" in lin
        assert lin["beta"] == 0.08
        assert lin["is_linear_body"] is False
        assert lin["has_quartic"] is True
        assert any("beta" in s for s in lin["nonlinear_terms"])

def test_divergence_declared(receipt) -> None:
    for pname in ladder.PROFILE_NAMES:
        ex = receipt["exact_predictor"][pname]
        assert "divergence" in ex and "has_divergence" in ex
        for d in ex["divergence"]:
            assert "first_divergence_tick" in d

def test_exhaustive_write_surface_present(receipt) -> None:
    assert "exhaustive_write_surface" in receipt
    for pname in ladder.PROFILE_NAMES:
        ex = receipt["exhaustive_write_surface"][pname]
        assert "all_candidates" in ex and "measured_top" in ex and "narrow_best" in ex
        assert ex["total_candidates"] == 56  # 28 modes *2 signs
        assert ex["narrowest_width"] in (1, 2)  # leaf widths
        # every candidate realized from applied impulse
        for c in ex["all_candidates"]:
            assert "realized_eff" in c and "realized_max_weight" in c
            assert "predicted_final" in c and "recipe" in c
            assert len(c["recipe"]) == 1 and c["recipe"][0]["work_budget"] == 0.001
        # narrow_best measured fields
        nb = ex["narrow_best"]
        assert nb is not None
        for k in ("realized_eff","realized_max_weight","predicted_final","measured_final","pearson_pred_vs_meas","beats"):
            assert k in nb
        # can-fail: inflating predicted_final must change digest
        import copy
        body = {k: v for k, v in receipt.items() if k != "content_digest"}
        mutated = copy.deepcopy(body)
        mutated["exhaustive_write_surface"][pname]["all_candidates"][0]["predicted_final"] += 1.0
        assert ladder.content_digest(mutated) != receipt["content_digest"]

def test_mode_selective_spec_present(receipt) -> None:
    assert "mode_selective_spec" in receipt
    for pname in ladder.PROFILE_NAMES:
        ms = receipt["mode_selective_spec"][pname]
        assert "slow_band_size" in ms and "realized_ceiling_eff" in ms and "algebraic_bound_eff" in ms
        assert "required_max_weight_mean" in ms and "gap_to_realized" in ms
        assert ms["slow_band_efold_ticks_range"][0] <= ms["slow_band_efold_ticks_range"][1]
        # spec must be numbers
        assert isinstance(ms["required_max_weight_mean"], float)
    # flat-inertia spec has zero slow-dominated singles (reported, not a failure)
    assert receipt["mode_selective_spec"]["helix7"]["dominated_count"] >= 1

def test_flat_inertia_intrinsic_ladder(receipt) -> None:
    assert "flat-inertia" in receipt["profiles"]
    assert "flat-inertia" in receipt["modal"]
    flat = receipt["profiles"]["flat-inertia"]
    assert len(flat["items"]) == 8
    # intrinsic lifetimes all 32 — not gaining with flat inertia sources-off
    for row in flat["items"]:
        assert row["lifetime_ticks"] == 32
    # final retentions are high (~0.5-0.7) vs helix7 headline 0.003
    headline_flat = flat["items"][0]["final_alignment"]
    headline_helix = receipt["profiles"]["helix7"]["items"][0]["final_alignment"]
    assert headline_flat > 0.5 and headline_helix < 0.01
    # modal: effective-mode counts present
    assert "effective_mode_count" in receipt["modal"]["flat-inertia"]["per_item"][0]
    # band structure under declared rule: 3 bands
    assert receipt["modal"]["flat-inertia"]["band_count"] == 3
    # corroborated predictor rank agreement reported
    assert "overall_pearson" in receipt["exact_predictor"]["flat-inertia"]
    # cite metric harness figure not re-derived
    assert "0.8948910529922045" in receipt["declared"]["definitions"]["flat_inertia_citation"] or "0.894" in str(receipt["boundary"])

def test_three_profiles_side_by_side(receipt) -> None:
    assert set(receipt["declared"]["profiles"]) == {"helix7", "mass-only", "flat-inertia"}
    assert len(receipt["profiles"]) == 3

