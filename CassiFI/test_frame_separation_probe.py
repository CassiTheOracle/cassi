"""Frame-separation checks: internal criterion versus external frame decision.

Both the runner's cover search and the verifier's complete partition
enumeration are exercised, and their verdicts, censuses, and witnesses must
agree on every control and on the synthetic anchors.
"""

from __future__ import annotations

import run_frame_separation_probe as probe
import verify_frame_separation_probe as verifier


def test_element_triangle_criterion_matches_census() -> None:
    for name, formula in probe.CONTROLS:
        canonical = verifier.canonical(formula)
        census = verifier.basis_census(canonical)
        columns = verifier.dual_columns(canonical)
        classes = verifier.classes_of(columns)
        assert census["nullity"] == 3, name
        assert census["minimum"] == probe.census_width(formula), name
        assert (verifier.element_triangle(classes) is not None) == (census["minimum"] == 2), name


def test_frame_decisions_agree_on_controls_and_anchors() -> None:
    cases = [(name, verifier.classes_of(verifier.dual_columns(formula))) for name, formula in probe.CONTROLS]
    cases.append(("c4-incidence", verifier.classes_of(verifier.C4_INCIDENCE)))
    cases.append(("u37-general-position", list(verifier.U37_GENERAL_POSITION)))
    for name, classes in cases:
        witness, _ = probe.cover_witness(classes)
        assert (witness is not None) == verifier.frame_decision(classes), name


def test_width_three_controls_are_frame_without_element_triangle() -> None:
    wide = [(name, formula) for name, formula in probe.CONTROLS if probe.census_width(formula) == 3]
    assert len(wide) == 2
    for name, formula in wide:
        columns = verifier.dual_columns(verifier.canonical(formula))
        classes = verifier.classes_of(columns)
        assert verifier.element_triangle(classes) is None, name
        assert verifier.frame_decision(classes), name
        record = probe.evaluate_control(name, formula)
        assert record["frame"] and record["check"]["full_rank"], name
        independent = verifier.witness_support(record["witness"], columns)
        assert independent["frame"] and independent["max_support"] <= 2, name
        assert independent["max_support"] == record["check"]["max_support"], name


def test_width_two_controls_have_element_triangles_and_frames() -> None:
    narrow = [(name, formula) for name, formula in probe.CONTROLS if probe.census_width(formula) == 2]
    assert len(narrow) == 3
    for name, formula in narrow:
        columns = verifier.dual_columns(verifier.canonical(formula))
        classes = verifier.classes_of(columns)
        assert verifier.element_triangle(classes) is not None, name
        record = probe.evaluate_control(name, formula)
        assert record["check"]["frame"], name
        assert verifier.witness_support(record["witness"], columns)["frame"], name


def test_direct_sum_width_law_and_block_witness() -> None:
    components = [probe.CONTROLS[0][1], probe.CONTROLS[3][1]]
    record = probe.evaluate_sum("test-sum-n21", components)
    assert record["size"] == 21 and record["nullity"] == 6
    assert record["component_omega"] == [2, 3]
    assert record["omega"] == 3 and record["width_law_holds"]
    assert record["frame"] and record["check"]["max_support"] <= 2
    formula = probe.direct_sum(components)
    assert formula == verifier.direct_sum(components)
    columns = verifier.dual_columns(formula)
    assert len(columns) == 21 and len(columns[0]) == 6
    independent = verifier.witness_support(record["witness"], columns)
    assert independent["frame"] and independent["max_support"] <= 2
    assert independent["max_support"] == record["check"]["max_support"]


def test_unbounded_family_stays_width_three_and_frame() -> None:
    base = probe.CONTROLS[3][1]
    for blocks in (2, 3, 4):
        record = probe.evaluate_sum(f"test-x{blocks}", [base] * blocks)
        assert record["components"] == blocks
        assert record["size"] == 12 * blocks and record["nullity"] == 3 * blocks
        assert record["omega"] == 3 and record["width_law_holds"]
        assert record["frame"] and record["check"]["full_rank"]
        assert record["check"]["max_support"] <= 2
        columns = verifier.dual_columns(verifier.direct_sum([base] * blocks))
        assert verifier.witness_support(record["witness"], columns)["frame"]
