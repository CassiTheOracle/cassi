"""Decision logic for the substitution probe.

The model-side behaviour lives in `probe_cassi_qi_substitution.py`, which needs
the harness binary and a GGUF. These tests cover the parts that decide whether a
run is a measurement: the difference count, the check table, and the conditions
under which the probe refuses to call a silent no-op a pass.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "research"
sys.path.insert(0, str(ROOT))

import probe_cassi_qi_substitution as probe  # noqa: E402


def arm(
    *,
    displacement: int,
    substitute: float,
    requested_displacement: int | None = None,
    requested_substitute: float | None = None,
    tokens: tuple[int, ...] = (1, 2, 3),
    differences: dict[str, int] | None = None,
    intervention: int = 0,
    graph_nodes: int = 1380,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "graph_nodes": graph_nodes,
        "requested_displacement": displacement if requested_displacement is None else requested_displacement,
        "requested_substitute": substitute if requested_substitute is None else requested_substitute,
        "displacement": displacement,
        "substitute": substitute,
        "intervention": intervention,
        "token_sha256": probe.token_sha256(list(tokens)),
        "generation_token_ids": list(tokens),
        "state_evolved": True,
        "state_max_abs_delta": 0.5,
    }
    for name, value in (differences or {}).items():
        entry[f"difference_vs_{name}"] = value
    return entry


def arms(**overrides: dict[str, object]) -> dict[str, dict[str, object]]:
    base = {
        "write_intact": arm(displacement=0, substitute=0.0, tokens=(1, 2, 3), graph_nodes=1380),
        "lesion": arm(displacement=3, substitute=0.0, tokens=(1, 9, 3), graph_nodes=1374),
        "relocated": arm(displacement=3, substitute=1.0e-6, tokens=(4, 5, 6), graph_nodes=1393),
        "seam_half": arm(displacement=3, substitute=0.5, tokens=(7, 8, 9), graph_nodes=1393),
        "seam_full": arm(displacement=3, substitute=1.0, tokens=(4, 5, 7), graph_nodes=1393),
    }
    base.update(overrides)
    for name, entry in base.items():
        for other in ("write_intact", "lesion", "relocated", "seam_full"):
            key = f"difference_vs_{other}"
            if key not in entry:
                entry[key] = probe.stream_differences(
                    list(entry["generation_token_ids"]), list(base[other]["generation_token_ids"]))
    return base


def guard(refused: bool = True) -> dict[str, object]:
    return {"refused": refused, "exit_code": 2 if refused else 0, "stderr_tail": ""}


def captures(
    *,
    full: float = 4.0e-3,
    half: float = 2.0e-3,
    relocated: float = 0.0,
    prompt_identical: bool = True,
    max_prompt_relative_delta: float = 0.0,
    shared_first_token: bool = True,
) -> dict[str, object]:
    return {
        "early_reach": {"seam_full": full, "seam_half": half, "relocated": relocated},
        "early_reach_deepest_layer": {"seam_full": full, "seam_half": half, "relocated": relocated},
        "reach_late": {"seam_full": full * 3.0, "seam_half": half, "relocated": relocated},
        "shared_first_token": shared_first_token,
        "first_tokens": {"seam_full": 4, "seam_half": 7, "relocated": 4},
        "prompt_identical": prompt_identical,
        "max_prompt_relative_delta": max_prompt_relative_delta,
    }


def test_stream_differences_counts_positions_and_length_excess() -> None:
    assert probe.stream_differences([1, 2, 3], [1, 2, 3]) == 0
    assert probe.stream_differences([1, 2, 3], [1, 9, 3]) == 1
    assert probe.stream_differences([1, 2, 3], [1, 2]) == 1
    assert probe.stream_differences([1, 2, 3], [4, 5]) == 3


def test_param_echo_accepts_the_stored_f32_share_and_refuses_a_dropped_flag() -> None:
    assert probe.params_match(3, 1.0e-6, 3, 9.999999974752427e-07) is True
    assert probe.params_match(3, 1.0, 3, 0.0) is False
    assert probe.params_match(3, 1.0, 0, 1.0) is False


def test_a_seam_that_does_not_scale_with_its_share_is_reported_as_failing() -> None:
    flat = probe.evaluate(arms(), guard(), captures(full=2.1e-3, half=2.0e-3))
    assert flat["checks"]["seam_dose_response_in_decode_captures"]["passed"] is False
    assert flat["verdict"] == "FAIL"


def test_a_seam_below_the_token_threshold_still_passes_on_its_measured_reach() -> None:
    below = arms(seam_full=arm(displacement=3, substitute=1.0, tokens=(4, 5, 6)),
                 seam_half=arm(displacement=3, substitute=0.5, tokens=(4, 5, 6)))
    evaluated = probe.evaluate(below, guard(), captures())
    assert evaluated["checks"]["seam_dose_response_in_decode_captures"][
        "committed_token_changes_vs_relocated"]["seam_full"] == 0
    assert evaluated["verdict"] == "PASS"


def test_a_dropped_parameter_is_reported_by_the_echo_check() -> None:
    dropped = arms(seam_full=arm(
        displacement=0, substitute=0.0, requested_displacement=3, requested_substitute=1.0,
        tokens=(7, 8, 9)))
    evaluated = probe.evaluate(dropped, guard(), captures())
    assert evaluated["checks"]["params_echoed_in_receipts"]["passed"] is False
    assert evaluated["verdict"] == "FAIL"


def test_a_dead_suppression_is_reported_before_any_seam_claim() -> None:
    dead = arms(lesion=arm(displacement=3, substitute=0.0, tokens=(1, 2, 3)))
    evaluated = probe.evaluate(dead, guard(), captures())
    assert evaluated["checks"]["suppression_is_live_at_layer"]["passed"] is False
    assert evaluated["verdict"] == "FAIL"


def test_an_accepted_substitution_guard_failure_fails_the_run() -> None:
    evaluated = probe.evaluate(arms(), guard(refused=False), captures())
    assert evaluated["checks"]["guard_refuses_unsuppressed_substitution"]["passed"] is False
    assert evaluated["verdict"] == "FAIL"


def test_a_frozen_field_is_reported_even_when_the_stream_changes() -> None:
    frozen = arms(seam_full=arm(displacement=3, substitute=1.0, tokens=(4, 5, 7)))
    frozen["seam_full"]["state_evolved"] = False
    evaluated = probe.evaluate(frozen, guard(), captures())
    assert evaluated["checks"]["field_evolves_while_it_supplies_the_state_write"]["passed"] is False
    assert evaluated["verdict"] == "FAIL"


def test_a_flat_seam_with_no_reach_is_reported() -> None:
    flat = probe.evaluate(arms(), guard(), captures(full=0.0, half=0.0))
    assert flat["checks"]["seam_dose_response_in_decode_captures"]["passed"] is False
    assert flat["verdict"] == "FAIL"


def test_a_seam_that_reaches_the_prompt_decode_is_reported() -> None:
    leaked = probe.evaluate(arms(), guard(), captures(prompt_identical=False, max_prompt_relative_delta=1.0e-3))
    assert leaked["checks"]["seam_is_decode_only"]["passed"] is False
    assert leaked["verdict"] == "FAIL"


def test_an_intervention_mismatch_invalidates_the_suppression_gate() -> None:
    # injection placement differs with the intervention, so the gate must refuse a
    # suppression difference measured across two of them
    mismatched = arms(write_intact=arm(displacement=0, substitute=0.0, tokens=(1, 2, 3), intervention=1))
    evaluated = probe.evaluate(mismatched, guard(), captures())
    assert evaluated["checks"]["suppression_is_live_at_layer"]["passed"] is False
    assert evaluated["checks"]["suppression_is_live_at_layer"]["interventions"]["write_intact"] == 1
    assert evaluated["verdict"] == "FAIL"


def test_a_seam_whose_first_token_differs_is_reported() -> None:
    # a differing first token means the early decode was not input-matched
    unshared = probe.evaluate(arms(), guard(), captures(shared_first_token=False))
    assert unshared["checks"]["seam_share_is_the_only_difference"]["passed"] is False
    assert unshared["verdict"] == "FAIL"


def test_a_measured_seam_passes_every_check() -> None:
    evaluated = probe.evaluate(arms(), guard(), captures())
    assert evaluated["verdict"] == "PASS"
    assert evaluated["checks"]["seam_dose_response_in_decode_captures"]["early_reach"] == {
        "seam_full": 4.0e-3, "seam_half": 2.0e-3, "relocated": 0.0}
    assert evaluated["checks"]["suppression_is_live_at_layer"]["token_difference_count"] == 1


def test_a_suppression_that_leaves_the_graph_unchanged_fails_the_gate() -> None:
    # the gate reads the graph, so an arm pair whose node counts match has no
    # suppressed write to point at however the tokens differ
    unsuppressed = arms(lesion=arm(displacement=3, substitute=0.0, tokens=(1, 9, 3), graph_nodes=1380))
    evaluated = probe.evaluate(unsuppressed, guard(), captures())
    assert evaluated["checks"]["suppression_is_live_at_layer"]["passed"] is False
    assert evaluated["verdict"] == "FAIL"


def test_a_suppression_holds_when_the_committed_stream_cannot_see_it() -> None:
    # a prompt whose continuation is settled commits the same tokens in both arms;
    # the absent state write is still measured, and the equality is reported
    settled = arms(lesion=arm(displacement=3, substitute=0.0, tokens=(1, 2, 3), graph_nodes=1374))
    evaluated = probe.evaluate(settled, guard(), captures())
    check = evaluated["checks"]["suppression_is_live_at_layer"]
    assert check["passed"] is True
    assert check["token_difference_count"] == 0
    assert evaluated["verdict"] == "PASS"
