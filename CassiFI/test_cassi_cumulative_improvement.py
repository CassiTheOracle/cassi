from __future__ import annotations

from itertools import product
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT / "CassiMindField", ROOT / "CassiQwen"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from architecture_ir import ArchitectureIR, build_example
from architecture_synthesizer import synthesize_workspace, workspace_digest
from cassi_field_qwen_workbench import CassiFieldWorkMemory
from redesign_lab import (
    INVESTIGATION_PROCEDURE_ID,
    _architecture_research_space,
    _compile_question_documents,
    _investigation_trace,
    _construction_plan_search,
    _constraint_construction_task,
    _constraint_source_from_task,
    _execute_constraint_source,
    _learn_reasoning_regimes,
    _paired_reasoning_task,
    _execute_structured_source,
    _field_program_construction_task,
    _structured_source_from_task,
)


def test_promoted_successor_becomes_dynamic_construction_parent() -> None:
    seed_files, _ = build_example()
    seed_digest = workspace_digest(seed_files)
    first_question = _architecture_research_space(seed_files, seed_digest)[
        "question_options"
    ][0]
    first_hypothesis = _compile_question_documents(
        seed_files,
        seed_digest,
        first_question,
    )[0]
    promoted = synthesize_workspace(
        seed_files,
        ArchitectureIR.from_dict(first_hypothesis["architecture"]),
    )

    parent_digest = workspace_digest(promoted.files)
    next_question = _architecture_research_space(
        promoted.files,
        parent_digest,
        cycle=2,
    )["question_options"][1]
    successor_hypothesis = _compile_question_documents(
        promoted.files,
        parent_digest,
        next_question,
    )[0]
    successor = synthesize_workspace(
        promoted.files,
        ArchitectureIR.from_dict(successor_hypothesis["architecture"]),
    )

    novel_paths = set(successor.files) - set(promoted.files)
    assert len(novel_paths) == 1
    novel_path = novel_paths.pop()
    assert parent_digest[:10] in novel_path
    assert successor_hypothesis["parent_source_digest"] == parent_digest
    assert successor_hypothesis["construction_origin"] == (
        "field-composed-parent-topology"
    )
    assert successor_hypothesis["causal_prediction"]["novel_module"] == novel_path
    assert successor_hypothesis["architecture"]["migration"][
        "source_digest"
    ] == parent_digest


def test_executed_trajectory_learns_and_transfers_procedure(tmp_path: Path) -> None:
    traces = [
        _investigation_trace(
            compiler_family=family,
            candidate_id=f"candidate-{index}",
            assessment_operation_id=f"assessment-{index}",
            status="PASS",
        )
        for index, family in enumerate(("family-a", "family-b", "family-c"))
    ]
    with CassiFieldWorkMemory(tmp_path / "field") as memory:
        learned = memory.semantic(
            {
                "operation": "learn-procedure",
                "operation_id": "test:learn-investigation",
                "procedure_id": INVESTIGATION_PROCEDURE_ID,
                "traces": traces[:2],
                "holdout": traces[2:],
            },
            operation_label="test:learn-investigation",
        )["result"]
        assert learned["status"] == "supported"
        assert learned["candidates"][0]["measured_cost"]["net_saved_steps"] == 2

        applied = memory.semantic(
            {
                "operation": "invoke-procedure",
                "operation_id": "test:invoke-unfamiliar",
                "procedure_ref": learned["procedure"],
                "bindings": {"role_0": "candidate-unfamiliar"},
                "context": {"parent_source_digest": "a" * 64},
            },
            operation_label="test:invoke-unfamiliar",
        )["result"]

    assert applied["status"] == "supported"
    assert [row["op"] for row in applied["proposed_actions"]] == [
        "locate-binding",
        "compose-operations",
        "compile-successor",
    ]
    assert {
        row["candidate"] for row in applied["proposed_actions"]
    } == {"candidate-unfamiliar"}


def test_architecture_experience_constructs_unfamiliar_field_program() -> None:
    files, _ = build_example()
    parent_digest = workspace_digest(files)
    task = _field_program_construction_task(files, parent_digest)
    source = _structured_source_from_task(task)
    result = _execute_structured_source(source)
    prediction = task["causal_prediction"]

    assert task["source_world"] == "python-architecture"
    assert task["target_world"] == "cassifi-structured-field-program"
    assert result["execution"] == prediction
    assert result["compiled_source_sha256"]
    assert result["logical_steps"] > 0

    task_id = task["task_sha256"]
    comparison = _construction_plan_search(
        [
            {"op": "locate-binding", "candidate": task_id},
            {"op": "compose-operations", "candidate": task_id},
            {"op": "compile-successor", "candidate": task_id},
        ]
    )
    assert comparison["experienced"]["primitive_steps_examined"] == 3
    assert comparison["fresh_bounded_search"]["primitive_steps_examined"] == 6
    assert comparison["net_saved_steps"] == 3


def test_architecture_experience_constructs_exact_transition_constraint() -> None:
    files, _ = build_example()
    parent_digest = workspace_digest(files)
    task = _constraint_construction_task(files, parent_digest)
    source = _constraint_source_from_task(task)
    result = _execute_constraint_source(source)

    assert task["source_world"] == "python-architecture"
    assert task["target_world"] == "cassifi-boolean-transition-constraint"
    assert result["status"] == task["causal_prediction"]["status"]
    assert result["witness_audit"]["status"] == "PASS"
    assert (
        result["witness_audit"]["final"]
        == task["causal_prediction"]["final"]
    )
    assert result["compiled_problem_sha256"]
    assert result["field_transitions"] > 0


def test_architecture_experience_selects_exact_reasoning_regimes() -> None:
    files, _ = build_example()
    parent_digest = workspace_digest(files)
    task = _paired_reasoning_task(files, parent_digest)
    result = _learn_reasoning_regimes(task)
    sat = result["held_out"]["sat"]
    unsat = result["held_out"]["unsat"]

    assert sat["local_screen"]["status"] == "sat"
    assert sat["selected_regime"] == "local"
    assert sat["selected_execution"]["audit"] == {
        "checked": True,
        "status": "sat",
        "auditor": "original-source-evaluator",
        "witness_variables": 6,
    }
    assert unsat["local_screen"]["status"] == "exhausted"
    assert unsat["fresh_regime"] == "conflict"
    assert unsat["trained_regime"] == "algebraic"
    assert unsat["selected_regime"] == "algebraic"
    assert unsat["selected_execution"]["status"] == "unsat"
    assert unsat["selected_execution"]["certificate"]["kind"] == "hybrid"
    assert unsat["selected_execution"]["audit"]["checked"] is True
    assert (
        unsat["selected_execution"]["audit"]["auditor"]
        == "verify_hybrid_inference.audit_proof"
    )
    assert unsat["selected_execution"]["field_transitions"] == 1
    assert unsat["fresh_execution"]["field_transitions"] == 95
    assert result["unsat_field_transition_saving"] == 94

    source = task["sources"]["unsat_held_out"]
    names = source["inputs"]
    models = []
    for bits in product((0, 1), repeat=len(names)):
        values = dict(zip(names, bits))
        if all(
            any(values[name] == polarity for name, polarity in clause)
            for clause in source["clauses"]
        ):
            models.append(values)
    assert models == []
